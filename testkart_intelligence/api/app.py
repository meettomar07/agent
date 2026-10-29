"""Local FastAPI web interface and REST API for Testkart Government Exam Intelligence."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Request
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, Field
from jinja2 import Environment, FileSystemLoader

from testkart_intelligence.config import settings
from testkart_intelligence.database.connection import get_db, init_db
from testkart_intelligence.registry.service import SourceRegistryService, seed_sources_if_empty
from testkart_intelligence.discovery.engine import DiscoveryEngine
from testkart_intelligence.writing.generator import WritingAgent
from testkart_intelligence.writing.qa import QualityAssuranceAgent
from testkart_intelligence.security.approvals import ApprovalService, ApprovalSecurityError
from testkart_intelligence.publishing.mock_publisher import MockPublisher, MockPublishingError
from testkart_intelligence.editorial.service import (
    EditorialService,
    StaleVersionConflictError,
    ApprovalBlockedError,
    EditorialSecurityError,
)
from testkart_intelligence.editorial.security import (
    validate_editorial_request,
    safe_render_markdown,
    is_safe_document_path,
)


EDITORIAL_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "editorial" / "templates"
jinja_editorial_env = Environment(
    loader=FileSystemLoader(str(EDITORIAL_TEMPLATES_DIR)),
    autoescape=True,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ensure database schema is ready and sources are seeded."""
    init_db()
    with get_db() as conn:
        seed_sources_if_empty(conn)
    yield


app = FastAPI(
    title="Testkart Government Exam Intelligence",
    description="Local-first multi-agent intelligence platform for discovering, extracting, and verifying official government recruitment notices.",
    version="0.1.0",
    lifespan=lifespan,
)


# Request schemas
class ApprovalDecisionRequest(BaseModel):
    raw_token: str
    decision: str  # "APPROVED" | "REJECTED"
    decision_notes: Optional[str] = None


class ApprovalRequestCreate(BaseModel):
    reviewer_email: str = Field(default_factory=lambda: settings.OWNER_EMAIL)


class DraftSaveRequest(BaseModel):
    expected_version_id: str
    title: str
    content_markdown: str
    editor_email: str = Field(default_factory=lambda: settings.OWNER_EMAIL)


class EditorialDecisionRequest(BaseModel):
    expected_version_id: str
    expected_content_hash: str
    decision: str  # "APPROVE" | "REJECT" | "REQUEST_CORRECTION"
    editor_email: str = Field(default_factory=lambda: settings.OWNER_EMAIL)
    notes: Optional[str] = None
    is_override: bool = False
    override_reason: Optional[str] = None


class PreviewRenderRequest(BaseModel):
    content_markdown: str


class NoticeFlagRequest(BaseModel):
    flag: str
    notes: str
    proposed_category: Optional[str] = None
    author: str = "human_editor"


class FactCorrectRequest(BaseModel):
    corrected_value: str
    reason: str
    reviewer_email: str = Field(default_factory=lambda: settings.OWNER_EMAIL)


class FactConfirmRequest(BaseModel):
    reviewer_email: str = Field(default_factory=lambda: settings.OWNER_EMAIL)


# --- API Endpoints ---

@app.get("/api/status")
def get_system_status() -> Dict[str, Any]:
    """Retrieve system overview metrics."""
    with get_db() as conn:
        src_total = conn.execute("SELECT count(*) as c FROM official_sources").fetchone()["c"]
        src_active = conn.execute("SELECT count(*) as c FROM official_sources WHERE enabled = 1").fetchone()["c"]
        scans_count = conn.execute("SELECT count(*) as c FROM scan_runs").fetchone()["c"]
        notices_count = conn.execute("SELECT count(*) as c FROM canonical_notices").fetchone()["c"]
        articles_count = conn.execute("SELECT count(*) as c FROM blog_articles").fetchone()["c"]
        qa_passed = conn.execute("SELECT count(*) as c FROM blog_articles WHERE status = 'QA_PASSED'").fetchone()["c"]
        approved = conn.execute("SELECT count(*) as c FROM blog_articles WHERE status = 'APPROVED'").fetchone()["c"]

    return {
        "sources": {"total": src_total, "active": src_active},
        "scans": {"total_runs": scans_count},
        "notices": {"total_discovered": notices_count},
        "articles": {
            "total_drafts": articles_count,
            "qa_passed": qa_passed,
            "approved": approved,
        },
        "live_publishing_enabled": False,  # Hard guard
    }


@app.get("/api/sources")
def list_sources(
    enabled_only: bool = False,
    category: Optional[str] = None,
    state: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List configured official government recruitment portals."""
    service = SourceRegistryService()
    return service.list_sources(enabled_only=enabled_only, category=category, state=state)


@app.post("/api/sources/{source_id}/toggle")
def toggle_source(source_id: str, enabled: bool) -> Dict[str, Any]:
    """Enable or disable an official source."""
    service = SourceRegistryService()
    updated = service.set_enabled(source_id, enabled)
    if not updated:
        raise HTTPException(status_code=404, detail="Source not found")
    return {"source_id": source_id, "enabled": enabled}


@app.get("/api/scans")
def list_scans(limit: int = 20) -> List[Dict[str, Any]]:
    """Retrieve history of discovery scans."""
    with get_db() as conn:
        cursor = conn.execute(
            """
            SELECT id, scan_type, status, started_at, completed_at,
                   sources_checked, notices_found, errors_count, error_summary
            FROM scan_runs
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]


@app.post("/api/scans/run")
def trigger_scan(source_code: Optional[str] = None) -> Dict[str, Any]:
    """Manually run discovery scan across official sources."""
    engine = DiscoveryEngine()
    return engine.run_scan(scan_type="MANUAL", source_code=source_code)


@app.get("/api/notices")
def list_notices(
    status: Optional[str] = None,
    classification: Optional[str] = None,
    recency: Optional[str] = None,
    authority: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """List discovered canonical notices with rich filtering."""
    service = EditorialService()
    return service.list_notices_by_view(
        view="all",
        limit=limit,
        offset=offset,
        authority=authority,
        category=classification,
        recency=recency,
        review_status=status,
        search=search,
    )


@app.get("/api/notices/{notice_id}")
def get_notice_detail(notice_id: str) -> Dict[str, Any]:
    """Retrieve notice metadata, version history, and verified extracted facts."""
    with get_db() as conn:
        notice = conn.execute("SELECT * FROM canonical_notices WHERE id = ?", (notice_id,)).fetchone()
        if not notice:
            raise HTTPException(status_code=404, detail="Notice not found")

        versions = conn.execute(
            "SELECT * FROM notice_versions WHERE notice_id = ? ORDER BY version_number DESC",
            (notice_id,),
        ).fetchall()

        latest_v_id = versions[0]["id"] if versions else None
        facts = []
        if latest_v_id:
            facts = conn.execute(
                "SELECT * FROM extracted_facts WHERE notice_version_id = ? ORDER BY fact_key",
                (latest_v_id,),
            ).fetchall()

        return {
            "notice": dict(notice),
            "versions": [dict(v) for v in versions],
            "extracted_facts": [dict(f) for f in facts],
        }


@app.get("/api/articles")
def list_articles(status: Optional[str] = None) -> List[Dict[str, Any]]:
    """List blog article drafts."""
    query = "SELECT * FROM blog_articles WHERE 1=1"
    params: List[Any] = []
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY updated_at DESC"

    with get_db() as conn:
        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


@app.get("/api/articles/{article_id}")
def get_article_detail(article_id: str) -> Dict[str, Any]:
    """Retrieve full blog article draft with QA checks and versions."""
    with get_db() as conn:
        article = conn.execute("SELECT * FROM blog_articles WHERE id = ?", (article_id,)).fetchone()
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")

        versions = conn.execute(
            "SELECT * FROM article_versions WHERE article_id = ? ORDER BY version_number DESC",
            (article_id,),
        ).fetchall()

        latest_v = versions[0] if versions else None
        qa_results = []
        if latest_v:
            qa_results = conn.execute(
                "SELECT * FROM qa_results WHERE article_version_id = ?",
                (latest_v["id"],),
            ).fetchall()

        return {
            "article": dict(article),
            "latest_version": dict(latest_v) if latest_v else None,
            "qa_results": [dict(q) for q in qa_results],
        }


@app.post("/api/articles/{article_id}/approval-token")
def request_approval_token(article_id: str, req: ApprovalRequestCreate) -> Dict[str, Any]:
    """Create a single-use approval token bound to current article content hash."""
    with get_db() as conn:
        art = conn.execute("SELECT current_version_id, status FROM blog_articles WHERE id = ?", (article_id,)).fetchone()
        if not art or not art["current_version_id"]:
            raise HTTPException(status_code=404, detail="Article or version not found")

        if art["status"] not in ("QA_PASSED", "DRAFT"):
            raise HTTPException(status_code=400, detail=f"Cannot request approval for article with status '{art['status']}'")

    service = ApprovalService()
    record_id, raw_token = service.create_approval_request(
        article_version_id=art["current_version_id"],
        reviewer_email=req.reviewer_email,
    )
    return {
        "approval_record_id": record_id,
        "token": raw_token,
        "article_id": article_id,
        "instructions": "In production this single-use link is delivered via email to the human editor.",
    }


@app.post("/api/approvals/decide")
def decide_approval(req: ApprovalDecisionRequest) -> Dict[str, Any]:
    """Process human approval or rejection of an article draft."""
    service = ApprovalService()
    try:
        result = service.decide_approval(
            raw_token=req.raw_token,
            decision=req.decision,
            decision_notes=req.decision_notes,
        )
        return result
    except ApprovalSecurityError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/articles/{article_id}/mock-publish")
def trigger_mock_publish(article_id: str) -> Dict[str, Any]:
    """Simulate publishing of an approved draft using MockPublisher."""
    with get_db() as conn:
        art = conn.execute(
            """
            SELECT ba.id, ba.current_version_id, ba.status, av.content_hash, ar.id as approval_id
            FROM blog_articles ba
            JOIN article_versions av ON ba.current_version_id = av.id
            LEFT JOIN approval_records ar ON ar.article_version_id = av.id AND ar.status = 'APPROVED'
            WHERE ba.id = ?
            ORDER BY ar.decided_at DESC
            LIMIT 1
            """,
            (article_id,),
        ).fetchone()

        if not art:
            raise HTTPException(status_code=404, detail="Article not found")

        if art["status"] != "APPROVED" or not art["approval_id"]:
            raise HTTPException(
                status_code=400,
                detail="Draft must be explicitly APPROVED by human reviewer prior to publication",
            )

        publisher = MockPublisher()
        try:
            res = publisher.publish(
                article_version_id=art["current_version_id"],
                content_hash=art["content_hash"],
                approval_record_id=art["approval_id"],
            )
            return res
        except MockPublishingError as exc:
            raise HTTPException(status_code=400, detail=str(exc))


# --- Editorial Review & Human-in-the-Loop Web Views ---

@app.get("/", response_class=HTMLResponse)
def editorial_dashboard(request: Request):
    """Local Editorial Dashboard Overview."""
    validate_editorial_request(request)
    service = EditorialService()
    metrics = service.get_dashboard_metrics()
    awaiting_articles = service.list_articles_by_view(view="awaiting", limit=8)
    blocked_notices = service.list_notices_by_view(view="blocked", limit=8)
    new_notices = service.list_notices_by_view(view="new", limit=8)

    template = jinja_editorial_env.get_template("editorial_dashboard.html")
    rendered = template.render(
        active_tab="dashboard",
        metrics=metrics,
        awaiting_articles=awaiting_articles,
        blocked_notices=blocked_notices,
        new_notices=new_notices,
    )
    return HTMLResponse(content=rendered)


@app.get("/editorial/notices", response_class=HTMLResponse)
def editorial_notices_view(
    request: Request,
    view: str = "all",
    authority: Optional[str] = None,
    category: Optional[str] = None,
    recency: Optional[str] = None,
    review_status: Optional[str] = None,
    pub_date: Optional[str] = None,
    deadline: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    """Filtered catalog of discovered official notices."""
    validate_editorial_request(request)
    service = EditorialService()
    metrics = service.get_dashboard_metrics()
    notices = service.list_notices_by_view(
        view=view,
        limit=limit,
        offset=offset,
        authority=authority,
        category=category,
        recency=recency,
        review_status=review_status,
        pub_date=pub_date,
        deadline=deadline,
        search=search,
    )

    tab_map = {
        "new": "notices_new",
        "blocked": "notices_blocked",
        "revisions": "notices_revisions",
        "current": "notices_current",
        "recruitment": "notices_recruitment",
    }
    template = jinja_editorial_env.get_template("editorial_notices_list.html")
    rendered = template.render(
        active_tab=tab_map.get(view, "notices_all"),
        current_view=view,
        metrics=metrics,
        notices=notices,
        filter_authority=authority or "",
        filter_category=category or "",
        filter_recency=recency or "",
        filter_review_status=review_status or "",
        filter_pub_date=pub_date or "",
        filter_deadline=deadline or "",
        filter_search=search or "",
        limit=limit,
        offset=offset,
    )
    return HTMLResponse(content=rendered)


@app.post("/api/editorial/notices/{notice_id}/flag")
def api_editorial_flag_notice(
    notice_id: str,
    req: NoticeFlagRequest,
    request: Request,
) -> Dict[str, Any]:
    """Flag a notice for editorial review (misclassified, proposed duplicate, etc.)."""
    validate_editorial_request(request)
    service = EditorialService()
    try:
        return service.flag_notice_for_review(
            notice_id=notice_id,
            flag=req.flag,
            notes=req.notes,
            proposed_category=req.proposed_category,
            author=req.author,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/editorial/notices/{notice_id}", response_class=HTMLResponse)
def editorial_notice_detail_view(notice_id: str, request: Request):
    """Notice metadata, version history, document hash, and extracted facts verification view."""
    validate_editorial_request(request)
    service = EditorialService()
    try:
        details = service.get_notice_review(notice_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    template = jinja_editorial_env.get_template("editorial_notice_detail.html")
    rendered = template.render(
        active_tab="notices_all",
        metrics=service.get_dashboard_metrics(),
        **details,
    )
    return HTMLResponse(content=rendered)


@app.get("/editorial/articles", response_class=HTMLResponse)
def editorial_articles_view(request: Request, view: str = "awaiting"):
    """Filtered catalog of blog article drafts."""
    validate_editorial_request(request)
    service = EditorialService()
    metrics = service.get_dashboard_metrics()
    articles = service.list_articles_by_view(view=view, limit=100)

    tab_map = {
        "awaiting": "articles_awaiting",
        "decided": "articles_decided",
    }
    template = jinja_editorial_env.get_template("editorial_articles_list.html")
    rendered = template.render(
        active_tab=tab_map.get(view, "articles_all"),
        current_view=view,
        metrics=metrics,
        articles=articles,
    )
    return HTMLResponse(content=rendered)


@app.get("/editorial/articles/{article_id}", response_class=HTMLResponse)
def editorial_article_editor_view(article_id: str, request: Request):
    """Interactive draft editor with side-by-side evidence, QA reports, and approval safeguards."""
    validate_editorial_request(request)
    service = EditorialService()
    try:
        details = service.get_draft_editor(article_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    initial_rendered = safe_render_markdown(details["current_version"]["content_markdown"])

    template = jinja_editorial_env.get_template("editorial_draft_editor.html")
    rendered = template.render(
        active_tab="articles_awaiting",
        metrics=service.get_dashboard_metrics(),
        initial_rendered_preview=initial_rendered,
        **details,
    )
    return HTMLResponse(content=rendered)


@app.get("/editorial/scans", response_class=HTMLResponse)
def editorial_scans_view(request: Request):
    """Portal scan health, execution logs, and diagnostics."""
    validate_editorial_request(request)
    service = EditorialService()
    metrics = service.get_dashboard_metrics()
    scan_health = service.get_scan_health_summary()

    template = jinja_editorial_env.get_template("editorial_scans.html")
    rendered = template.render(
        active_tab="scans",
        metrics=metrics,
        scan_health=scan_health,
    )
    return HTMLResponse(content=rendered)


@app.get("/editorial/documents/{version_id}/download")
def download_local_document(version_id: str, request: Request):
    """Safely stream downloaded official PDF document from local disk without arbitrary URL fetching."""
    validate_editorial_request(request)
    with get_db() as conn:
        row = conn.execute(
            "SELECT storage_path, document_type, document_hash FROM notice_versions WHERE id = ?",
            (version_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Document version not found")

        safe_path = is_safe_document_path(row["storage_path"])
        if not safe_path:
            raise HTTPException(
                status_code=404,
                detail="Official document file not present on local disk or outside allowed storage directory",
            )

        media_type = "application/pdf" if row["document_type"] == "PDF" else "text/html"
        filename = f"{version_id}_{row['document_hash'][:8]}.{row['document_type'].lower()}"
        return FileResponse(
            path=str(safe_path),
            media_type=media_type,
            filename=filename,
        )


# --- Editorial REST API Endpoints ---

@app.post("/api/editorial/articles/{article_id}/save")
def api_editorial_save_draft(article_id: str, req: DraftSaveRequest, request: Request) -> Dict[str, Any]:
    """Save editor modifications to an article draft.

    Creates an incremented article version, attributes author as editor,
    resets approval status, and runs automated QA checks.
    """
    validate_editorial_request(request)
    service = EditorialService()
    try:
        return service.save_draft(
            article_id=article_id,
            expected_version_id=req.expected_version_id,
            title=req.title,
            content_markdown=req.content_markdown,
            editor_email=req.editor_email,
        )
    except StaleVersionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/editorial/articles/{article_id}/decide")
def api_editorial_decide(article_id: str, req: EditorialDecisionRequest, request: Request) -> Dict[str, Any]:
    """Process explicit human editorial decision (Approve, Reject, Request Correction).

    Enforces concurrency checks, normal approval blocks on unverified facts,
    and audited editorial overrides with mandatory justification.
    """
    validate_editorial_request(request)
    service = EditorialService()
    client_ip = request.client.host if request.client else "127.0.0.1"
    try:
        return service.submit_decision(
            article_id=article_id,
            expected_version_id=req.expected_version_id,
            expected_content_hash=req.expected_content_hash,
            decision=req.decision,
            editor_email=req.editor_email,
            notes=req.notes,
            is_override=req.is_override,
            override_reason=req.override_reason,
            client_ip=client_ip,
        )
    except StaleVersionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (ApprovalBlockedError, EditorialSecurityError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/editorial/articles/{article_id}/preview")
def api_editorial_preview(article_id: str, req: PreviewRenderRequest, request: Request) -> Dict[str, Any]:
    """Safely render Markdown draft into HTML with complete tag escaping and XSS protection."""
    validate_editorial_request(request)
    rendered = safe_render_markdown(req.content_markdown)
    return {"rendered_html": rendered}


@app.post("/api/editorial/facts/{fact_id}/correct")
def api_editorial_correct_fact(fact_id: str, req: FactCorrectRequest, request: Request) -> Dict[str, Any]:
    """Allow reviewers to correct an extracted recruitment fact without overwriting machine value."""
    validate_editorial_request(request)
    service = EditorialService()
    try:
        return service.correct_fact(
            fact_id=fact_id,
            corrected_value=req.corrected_value,
            reason=req.reason,
            reviewer_email=req.reviewer_email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/editorial/facts/{fact_id}/confirm")
def api_editorial_confirm_fact(fact_id: str, req: FactConfirmRequest, request: Request) -> Dict[str, Any]:
    """Allow reviewers to explicitly confirm an extracted recruitment fact."""
    validate_editorial_request(request)
    service = EditorialService()
    try:
        return service.confirm_fact(
            fact_id=fact_id,
            reviewer_email=req.reviewer_email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
