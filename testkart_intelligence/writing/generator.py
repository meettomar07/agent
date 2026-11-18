"""Writing Agent for generating publication-ready blog drafts from verified facts."""

import hashlib
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse
from jinja2 import Environment, FileSystemLoader

from testkart_intelligence.config import settings
from testkart_intelligence.database.connection import get_db
from testkart_intelligence.classification.classifier import NoticeCategory


TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def generate_slug(title: str, authority: str) -> str:
    """Generate SEO-friendly URL slug."""
    text = f"{authority} {title}".lower()
    clean = re.sub(r"[^a-z0-9\s-]", "", text)
    slug = re.sub(r"[\s-]+", "-", clean).strip("-")
    return slug[:100]


class WritingAgent:
    """Generates factual, SEO-ready blog drafts using verified facts only."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def select_template(self, classification: str) -> str:
        """Select the appropriate template based on notice classification."""
        if classification == NoticeCategory.CANCELLATION_NOTICE.value:
            return "cancellation.md.j2"
        elif classification == NoticeCategory.RECRUITMENT_NOTIFICATION.value:
            return "recruitment.md.j2"
        elif classification == NoticeCategory.EXAM_DATE_ANNOUNCEMENT.value:
            return "exam_schedule.md.j2"
        elif classification == NoticeCategory.ADMIT_CARD_RELEASE.value:
            return "admit_card.md.j2"
        elif classification in (NoticeCategory.EXAM_RESULT.value, NoticeCategory.ANSWER_KEY.value):
            return "result_answer_key.md.j2"
        elif classification in (NoticeCategory.CORRIGENDUM.value, NoticeCategory.RECRUITMENT_ADDENDUM.value):
            return "corrigendum.md.j2"
        elif classification in (NoticeCategory.INTERNAL_CIRCULAR.value, NoticeCategory.DEPUTATION_NOTICE.value):
            return "internal_circular.md.j2"
        elif classification in (NoticeCategory.ADMISSION_OR_ENTRANCE_EXAM.value, NoticeCategory.ADMINISTRATIVE_ANNOUNCEMENT.value):
            return "announcement.md.j2"
        else:
            return "announcement.md.j2"

    def draft_article(
        self,
        notice_id: str,
        notice_version_id: Optional[str] = None,
    ) -> Tuple[str, str, str]:
        """Draft a blog article for a canonical notice from verified facts.

        Returns:
            Tuple of (article_id, article_version_id, content_hash)
        """
        now_iso = datetime.now(timezone.utc).isoformat()

        with get_db(self.db_path) as conn:
            # 1. Fetch notice details
            notice_row = conn.execute(
                "SELECT * FROM canonical_notices WHERE id = ?",
                (notice_id,),
            ).fetchone()
            if not notice_row:
                raise ValueError(f"Notice {notice_id} not found")

            # Guard: check for human-review required or unreadable status
            if notice_row["classification"] == NoticeCategory.HUMAN_REVIEW_REQUIRED.value:
                raise ValueError(f"Notice {notice_id} requires human review: classification uncertain or conflicting")

            if notice_row["status"] in (
                "SCANNED_OCR_BLOCKED_FLAGGED_FOR_HUMAN_REVIEW",
                "NON_UNICODE_ENCODING_FLAGGED_FOR_HUMAN_REVIEW",
                "HUMAN_REVIEW_REQUIRED",
            ):
                raise ValueError(
                    f"Notice {notice_id} is flagged for human review (status={notice_row['status']}): "
                    f"automated drafting halted to preserve factual integrity"
                )

            # 2. Fetch latest notice version if not provided
            if not notice_version_id:
                v_row = conn.execute(
                    "SELECT id FROM notice_versions WHERE notice_id = ? ORDER BY version_number DESC LIMIT 1",
                    (notice_id,),
                ).fetchone()
                if not v_row:
                    raise ValueError(f"No document version found for notice {notice_id}")
                notice_version_id = v_row["id"]

            # 3. Fetch verified facts (preferring editor-corrected value if present)
            facts_cursor = conn.execute(
                """
                SELECT fact_key, fact_value, corrected_value, verified_status
                FROM extracted_facts
                WHERE notice_version_id = ? AND verified_status = 'VERIFIED'
                """,
                (notice_version_id,),
            )
            facts = {
                f["fact_key"]: (f["corrected_value"] or f["fact_value"])
                for f in facts_cursor.fetchall()
            }

            # Derive clean portal URL, short exam name, and SEO article title
            raw_url = facts.get("official_source_url") or notice_row["normalized_url"] or ""
            parsed = urlparse(raw_url)
            portal_url = f"{parsed.scheme}://{parsed.netloc}/" if parsed.scheme and parsed.netloc else raw_url

            short_name = (
                facts.get("short_name")
                or facts.get("exam_name")
                or notice_row["title"]
            ).strip()
            if len(short_name) > 75:
                short_name = short_name[:72].rsplit(" ", 1)[0]

            if facts.get("blog_title"):
                article_title = facts["blog_title"].strip()
            else:
                auth = (notice_row["authority_name"] or "").strip()
                raw_t = (notice_row["title"] or "").strip()
                if auth and auth.lower() in raw_t.lower():
                    article_title = raw_t
                elif auth:
                    article_title = f"{auth} {raw_t}"
                else:
                    article_title = raw_t

            if len(article_title) > settings.MAX_TITLE_LENGTH:
                article_title = article_title[: settings.MAX_TITLE_LENGTH - 3].rstrip() + "..."

            # 4. Select template and render content
            template_name = self.select_template(notice_row["classification"])
            template = self.jinja_env.get_template(template_name)
            markdown_content = template.render(
                notice=dict(notice_row),
                facts=facts,
                short_name=short_name,
                portal_url=portal_url,
                article_title=article_title,
            ).strip()

            # 5. Compute content hash
            content_hash = hashlib.sha256(markdown_content.encode("utf-8")).hexdigest()

            # 6. Generate slug and meta
            slug = generate_slug(article_title, "")
            meta_desc = (
                facts.get("meta_description")
                or f"{article_title}. Check official overview, important dates, eligibility, fee, selection process and official portal links."
            )
            keywords = f"{notice_row['authority_name']}, {notice_row['category']}, {short_name}, govt jobs, exam notification"

            # 7. Check if article already exists for this notice
            art_row = conn.execute(
                "SELECT id FROM blog_articles WHERE canonical_notice_id = ?",
                (notice_id,),
            ).fetchone()

            if art_row:
                article_id = art_row["id"]
                # Invalidate prior approval/QA status on revision: reset to DRAFT
                conn.execute(
                    """
                    UPDATE blog_articles
                    SET title = ?, template_type = ?, status = 'DRAFT', updated_at = ?
                    WHERE id = ?
                    """,
                    (article_title, template_name, now_iso, article_id),
                )
            else:
                article_id = f"art_{uuid.uuid4().hex[:12]}"
                # Ensure unique slug
                existing_slug = conn.execute("SELECT id FROM blog_articles WHERE slug = ?", (slug,)).fetchone()
                if existing_slug:
                    slug = f"{slug}-{uuid.uuid4().hex[:4]}"

                conn.execute(
                    """
                    INSERT INTO blog_articles (
                        id, canonical_notice_id, template_type, status, title, slug,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, 'DRAFT', ?, ?, ?, ?)
                    """,
                    (article_id, notice_id, template_name, article_title, slug, now_iso, now_iso),
                )

            # Determine article version number
            last_art_v = conn.execute(
                "SELECT max(version_number) as max_v FROM article_versions WHERE article_id = ?",
                (article_id,),
            ).fetchone()
            art_version_num = (last_art_v["max_v"] or 0) + 1
            art_version_id = f"arv_{uuid.uuid4().hex[:12]}"

            conn.execute(
                """
                INSERT INTO article_versions (
                    id, article_id, version_number, content_markdown, content_hash,
                    title, meta_description, keywords, generated_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'deterministic_template', ?)
                """,
                (
                    art_version_id,
                    article_id,
                    art_version_num,
                    markdown_content,
                    content_hash,
                    article_title,
                    meta_desc,
                    keywords,
                    now_iso,
                ),
            )

            # Update current version on blog article
            conn.execute(
                "UPDATE blog_articles SET current_version_id = ? WHERE id = ?",
                (art_version_id, article_id),
            )

        return article_id, art_version_id, content_hash
