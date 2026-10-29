# Testkart Government Exam Intelligence & Publishing Multi-Agent System

A local-first, multi-agent intelligence platform for **Testkart** that discovers government examination notifications exclusively from verified official Indian government sources, extracts structured facts, validates claims against authoritative evidence, creates publication-ready blog drafts, and provides interfaces for human approval and mock publishing.

> [!IMPORTANT]
> **Phase: Local Development Only.**
> Live publishing to Testkart's website, CMS, or public APIs is strictly disabled in code (`ALLOW_LIVE_PUBLISHING = False`). Real email sending is deferred to a future phase; the system currently utilizes single-use, content-hash-bound tokens and mock publishers for local verification.

---

## 1. Architectural Overview

```
                                +-----------------------------+
                                |  Official Government Portals|
                                |   (.gov.in, .nic.in, etc.)  |
                                +--------------+--------------+
                                               |
                                               v
                                +-----------------------------+
                                | 1. Discovery Worker         |
                                |    - Domain Allowlist Guard |
                                |    - HTML Listing Parser    |
                                |    - Multi-Factor Dedupl.   |
                                +--------------+--------------+
                                               |
                                               v
                                +-----------------------------+
                                | 2. Extraction Worker        |
                                |    - PyMuPDF Page Extractor |
                                |    - Scanned PDF OCR Stub   |
                                |    - Structured Fact Parser |
                                +--------------+--------------+
                                               |
                                               v
                                +-----------------------------+
                                | 3. Verification Agent       |
                                |    - Verbatim Quote Matcher |
                                |    - Contradiction Detector |
                                |    - Immutable Notice Ver.  |
                                +--------------+--------------+
                                               |
                                               v
                                +-----------------------------+
                                | 4. Classification Agent     |
                                |    - Notice Category Match  |
                                |    - Template Selector      |
                                +--------------+--------------+
                                               |
                                               v
                                +-----------------------------+
                                | 5. Writing Agent            |
                                |    - Deterministic Jinja2   |
                                |    - Factual Markdown Draft |
                                |    - Content Hash Binding   |
                                +--------------+--------------+
                                               |
                                               v
                                +-----------------------------+
                                | 6. Quality-Assurance Agent  |
                                |    - Source Link Check      |
                                |    - Branding Validator     |
                                |    - Pass/Fail Quality Gate |
                                +--------------+--------------+
                                               |
                                               v
                                +-----------------------------+
                                | 7. Approval & Mock Publish  |
                                |    - Single-Use Hash Tokens |
                                |    - Replay-Protected Audit |
                                |    - MockPublisher (Tests)  |
                                +-----------------------------+
```

---

## 2. Source Verification & Allowlist Policy

The engine adheres to a strict evidence hierarchy:
- **Authoritative Evidence:** Only official government recruitment websites (`.gov.in`, `.nic.in`) and officially designated autonomous examination agencies (e.g., `ibps.in`, `nta.ac.in`).
- **Strictly Prohibited:** Commercial coaching portals (`testbook`, `adda247`), job scrapers (`sarkariresult`, `freejobalert`), social media posts, search snippets, and unverified blogs.
- **Domain & Redirect Validation:** Every HTTP request and every redirect hop is inspected. Any destination that does not match an allowlisted apex domain or exhibits lookalike patterns (e.g. `upsc-gov.in`, `upsc.com`) is rejected immediately with a `SecurityValidationError`.
- **Untrusted Input:** All downloaded HTML and PDF documents are treated strictly as untrusted data inputs, never as executable instructions or prompt injection targets.

### Initial Seed Registry (Representative Central & State Portals)
The seed registry includes 12 verified official portals across categories:
- **Central Recruitment:** UPSC (`upsc.gov.in`), SSC (`ssc.gov.in`)
- **Banking / Finance:** IBPS (`ibps.in`)
- **Railways:** Railway Recruitment Board Chandigarh (`rrbcdg.gov.in`)
- **Defence:** Join Indian Army (`joinindianarmy.nic.in`)
- **Teaching & Education:** National Testing Agency (`nta.ac.in`)
- **State Public Service Commissions (PSCs):**
  - Bihar: BPSC (`bpsc.bih.nic.in`)
  - Uttar Pradesh: UPPSC (`uppsc.up.nic.in`)
  - Madhya Pradesh: MPPSC (`mppsc.mp.gov.in`)
  - Karnataka: KPSC (`kpsc.kar.nic.in`)
  - Tamil Nadu: TNPSC (`tnpsc.gov.in`)
- **Subordinate Services:** DSSSB (`dsssb.delhi.gov.in`)

---

## 3. Technology Stack

- **Runtime:** Python 3.11+ (verified on Python 3.13)
- **Database:** SQLite with WAL mode, foreign key enforcement, and indexes
- **Document & Web Parsing:** PyMuPDF (`pymupdf`), BeautifulSoup4 (`bs4`), HTTPX
- **Data Validation & Settings:** Pydantic v2 & Pydantic-Settings
- **Scheduling:** APScheduler (Asia/Kolkata timezone, twice-daily cron triggers)
- **Templates:** Jinja2
- **Local API & Dashboard:** FastAPI & Uvicorn
- **Testing:** pytest

---

## 4. Setup and Installation

### 1. Clone & Enter Directory
```powershell
cd d:\Agent
```

### 2. Install Dependencies
```powershell
pip install -e .
```
Or install core dependencies directly:
```powershell
pip install httpx beautifulsoup4 pymupdf pydantic pydantic-settings fastapi uvicorn apscheduler jinja2 pytest python-dateutil
```

### 3. Initialize Database & Seed Official Sources
```powershell
python -m testkart_intelligence.cli init
```
This initializes `data/testkart.db` and loads the verified official portals.

---

## 5. CLI Commands

### List Official Sources
```powershell
python -m testkart_intelligence.cli sources list
```

### Enable or Disable a Source
```powershell
python -m testkart_intelligence.cli sources disable --code UPSC
python -m testkart_intelligence.cli sources enable --code UPSC
```

### Trigger a Manual Discovery Scan
```powershell
# Scan all enabled sources
python -m testkart_intelligence.cli scan

# Or scan a single specific source
python -m testkart_intelligence.cli scan --source UPSC
```

### Display System Status
```powershell
python -m testkart_intelligence.cli status
```

---

## 6. Running Local Web Dashboard & API

Launch the local FastAPI service:
```powershell
uvicorn testkart_intelligence.api.app:app --host 127.0.0.1 --port 8000 --reload
```

Open your browser to:
- **Web Dashboard:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Interactive Swagger Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

Key API Endpoints:
- `GET /api/status`: Overall system metrics and live publishing guard verification
- `GET /api/sources`: List official portals and their verification status
- `POST /api/sources/{source_id}/toggle`: Enable or disable sources
- `GET /api/scans`: Historical scan run logs with errors and timings
- `POST /api/scans/run`: Trigger manual discovery scan
- `GET /api/notices`: Discovered canonical notices
- `GET /api/notices/{notice_id}`: Notice versions and extracted facts with evidence
- `GET /api/articles`: Blog article drafts and QA statuses
- `POST /api/articles/{article_id}/approval-token`: Create single-use approval token
- `POST /api/approvals/decide`: Submit human approval/rejection decision
- `POST /api/articles/{article_id}/mock-publish`: Execute mock publisher (guarded)

---

## 7. Testing & Quality Assurance

Run the automated test suite with pytest:
```powershell
pytest -v --tb=short
```

The test suite contains **63 automated unit, integration, and regression tests** (100% passing across 10 test modules):
1. **Security & Domain Allowlist:** Official domain checks, rejection of lookalike and commercial domains (`upsc-gov.in`, `sarkariresult.com`), SSRF IP address rejection, embedded credential blocking, and redirect chain validation.
2. **Host-Specific TLS & Header Resilience:** Legacy OpenSSL `SECLEVEL=1` ciphers scoped strictly to allowlisted hosts (`ibps.in`, `rrbcdg.gov.in`); modern `SECLEVEL=2` enforced everywhere else. Lenient header fallback for non-compliant government portals (`kpsc.kar.nic.in`).
3. **Streaming & Size Control:** Streaming chunk consumption enforcing `MAX_DOCUMENT_SIZE_BYTES` upfront to prevent memory exhaustion and DoS bombs.
4. **Soft-404 Detection:** Detection of error-page redirects (e.g. `FileNotFound.aspx`, `error.aspx`) ensuring failed sources are never misclassified as empty successes.
5. **Discovery & Deduplication:** HTML table link parsing, advt number detection, URL normalization, new notice detection, unchanged deduplication, and revision detection on document hash change.
6. **SSC Official REST API:** Automated discovery and attachment parsing for Staff Selection Commission (`ssc.gov.in/api/general-website/portal/notice-boards`).
7. **Extraction & Verification:** Multi-page PDF text extraction via PyMuPDF, corrupted/empty PDF handling, scanned document fallback interface, fact extraction (multi-date ranges, narrative vacancies, dates, qualifications), and contradiction detection.
8. **Factual Integrity Remediation:** Strict cancellation precedence over generic keywords, scanned PDF drafting blocks (<50 chars/page), elimination of question counts matched as vacancies, digit requirement in notice numbers, and heading fragment rejection.
9. **Editorial Review Interface (Stage 6):**
   - Dashboard views: Newly discovered notices, drafts awaiting review, blocked documents, revisions/corrigenda, approved/rejected drafts, scan health.
   - Side-by-side evidence inspection: Extracted facts, confidence, verification statuses, verbatim excerpts, PDF page references, document SHA-256 hashes, and safe official portal links.
   - Draft Editor & Version Invalidation: Markdown editing with live preview, author attribution (`human_editor:<email>`), automatic invalidation of prior approvals upon modification, and new immutable version generation.
   - Concurrency & Stale Tab Guards: Rejection of edits or approvals submitted against outdated version IDs or mismatched content hashes (`409 Conflict`).
   - Review Safeguards & Audited Overrides: Hard block on normal approval when critical recruitment facts (dates, vacancies) are unverified or documents are unreadable; audited editorial override requiring recorded justification and editor identity.
   - Security & XSS Neutralization: Bound strictly to `127.0.0.1`, unauthorized external host/origin rejection, complete HTML escaping, and event handler neutralization.
   - Live Publishing Guard: `ALLOW_LIVE_PUBLISHING = False` strictly asserted across all editorial actions.
10. **Revisions & Deadline Changes:** Multi-version notice and article updates, automatic reset of article status to `DRAFT` upon revision, token invalidation on content changes, and corrigenda handling.
11. **Classification & Writing:** Notice categorisation across 9 categories, Jinja2 factual template generation, lowercase Testkart branding verification.
12. **Quality Gate:** Category-aware QA agent blocking drafts with missing source links, unverified facts, or heading fragments.
13. **Approvals & Publishing Guard:** Single-use tokens, replay protection, content-hash binding, token invalidation on content modification, mock publisher idempotency, and strict failsafe assertion that live publishing cannot be triggered.
14. **Scheduler & Startup Recovery:** Overlap prevention lock, twice-daily cron in Asia/Kolkata timezone, FastAPI endpoint status checks, and automatic recovery of orphaned scans on startup.
15. **End-to-End Pipeline:** Full 12-step lifecycle from mock portal discovery through extraction, verification, draft creation, QA pass, approval, and mock publishing.

---

## 8. Local Editorial Review Interface

The system features a local-first editorial dashboard designed for human-in-the-loop verification before any article can advance.

### Starting the Editorial Dashboard
To launch the dashboard locally on `127.0.0.1:8000`:
```powershell
# Using Testkart CLI
testkart serve

# Or using python module
python -m testkart_intelligence.cli serve

# Or using Uvicorn directly
uvicorn testkart_intelligence.api.app:app --host 127.0.0.1 --port 8000
```
Then navigate to: **`http://127.0.0.1:8000`**

### Dashboard Layout & Features

```
+----------------------------------------------------------------------------------------------------+
| Testkart Intelligence        [PHASE: LOCAL DEVELOPMENT ONLY • LIVE PUBLISHING DISABLED]   127.0.0.1|
+----------------------------------------------------------------------------------------------------+
| [Overview]  [Newly Discovered (12)]  [Drafts Awaiting Review (4)]  [Blocked (3)]  [Revisions]      |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
| +-------------------------+ +-------------------------+ +----------------------------------------+ |
| | Newly Discovered: 12    | | Awaiting Review: 4      | | Blocked / QA Failures: 3               | |
| +-------------------------+ +-------------------------+ +----------------------------------------+ |
|                                                                                                    |
| === DRAFTS AWAITING EDITORIAL REVIEW ===                                                           |
| ID          Authority    Title                                     Status     Version   Action     |
| art_geo26   UPSC         Combined Geo-Scientist Exam 2026          QA_PASSED  v1        [Edit ->]  |
|                                                                                                    |
| === BLOCKED DOCUMENTS & EXTRACTION FAILURES ===                                                    |
| ID          Authority    Title                                     Block Reason         Action     |
| not_bpsc69  BPSC         Assistant Professor Scanned Circular      SCANNED PDF (<50c)   [Inspect]  |
+----------------------------------------------------------------------------------------------------+
```

### Side-by-Side Draft Editor & Evidence Inspection (`/editorial/articles/{id}`)

```
+----------------------------------------------------------------------------------------------------+
| Draft Editor: UPSC Combined Geo-Scientist Exam 2026 (v1)                                           |
| Status: QA_PASSED • Content Hash: a7f8b92... • Author: agent_writer                                |
+----------------------------------------------------------------------------------------------------+
| [LEFT COLUMN: OFFICIAL EVIDENCE]             | [RIGHT COLUMN: DRAFT EDITOR & PREVIEW]              |
|                                              |                                                     |
| Portal URL: https://upsc.gov.in/geo-2026.pdf | Title: [ UPSC Combined Geo-Scientist 2026 ...     ] |
| Document Hash: 8f4e21a...                    | [ Markdown Editor ]   [ Formatted Preview ]         |
| [Download Verified PDF (Local Copy)]         |                                                     |
|                                              | # Union Public Service Commission                   |
| EXTRACTED FACTS & TRACEABLE EVIDENCE:        | Combined Geo-Scientist Examination 2026             |
| - total_vacancies: 85 [VERIFIED]             |                                                     |
|   Excerpt: "There are 85 vacancies in total" | | Field | Value |                                   |
|   Page: 2                                    | | Vacancies | 85 |                                  |
| - application_start_date: 15/11/2026         |                                                     |
| - application_end_date: 15/12/2026           | --------------------------------------------------- |
|                                              | [Save Draft (v2)] [Request Correction] [Reject]     |
| QA CHECKS:                                   |                                                     |
| - rule_document_readability: PASS            |                                                     |
| - rule_recruitment_critical_dates: PASS      | [✔ Approve Draft (v1)]                              |
+----------------------------------------------------------------------------------------------------+
```

### Review Safeguards Enforced:
1. **Normal Approval Block:** Normal one-click approval is disabled if material factual claims are unverified (missing start/end dates, missing vacancies) or if the document is scanned (<50 chars/page).
2. **Audited Editorial Override:** If an editor verifies facts directly from an official PDF that automated regex missed, they may submit an override by providing a mandatory explanation (min 10 characters) and editor identity.
3. **Approval Invalidation on Edit:** Editing an approved article immediately generates version $N+1$, resets status to `DRAFT`, and invalidates prior approval records.
4. **Concurrency Conflict Protection:** Submitting actions against outdated versions or mismatched content hashes returns `409 Conflict`.
5. **Localhost Binding & XSS Immunity:** Endpoints are bound to `127.0.0.1`; all Markdown rendering strictly escapes HTML and strips event handlers.
6. **Live Publishing Boundary:** `ALLOW_LIVE_PUBLISHING = False` is hardcoded; no approval or override can trigger live CMS publication.

For complete real-world validation findings, evaluation metrics, and source matrices, refer to:
- [REAL_WORLD_VALIDATION_REPORT.md](file:///D:/Agent/REAL_WORLD_VALIDATION_REPORT.md)
- [SOURCE_COVERAGE_MATRIX.csv](file:///D:/Agent/SOURCE_COVERAGE_MATRIX.csv)
- [FACT_EXTRACTION_EVALUATION.csv](file:///D:/Agent/FACT_EXTRACTION_EVALUATION.csv)
- [AUDIT_REPORT.md](file:///D:/Agent/AUDIT_REPORT.md)
- [VALIDATION_GATE_REPORT.md](file:///D:/Agent/VALIDATION_GATE_REPORT.md)

---

## 8. Database Schema & Versioning

The SQLite schema maintains an immutable audit trail:
- `official_sources`: Authoritative portal registry with verification status and failure counters
- `scan_runs` & `scan_source_logs`: Persistent history of scheduled and manual scan executions
- `canonical_notices`: Canonical identity of examinations and recruitment drives
- `notice_versions`: Immutable document versions with SHA-256 hashes, raw text, and local PDF/HTML storage paths
- `extracted_facts`: Traceable facts linked to document page numbers, verbatim quote snippets, confidence scores, and verification status (`VERIFIED`, `CONTRADICTORY`, `MISSING`)
- `blog_articles` & `article_versions`: Version-tracked markdown drafts with content hashes and QA statuses
- `qa_results`: Detailed test results for each QA rule check
- `approval_records`: Replay-protected approval records with single-use tokens, reviewer emails, and expiry dates
- `publishing_jobs`: Publishing attempt records with mock status and published URLs
- `audit_events`: Tamper-evident ledger of all critical decisions and actions

---

## 9. Next Implementation Steps (Future Phases)

1. **Systematic Source Expansion:**
   - Extend the source registry to encompass all 28 states and 8 Union Territories across India (State PSCs, Subordinate Selection Boards, Police Recruitment Boards, High Courts, Municipal Corporations).
   - Implement RSS feed parsers for government portals providing standard XML/RSS feeds.
2. **Production OCR Integration:**
   - Connect `OcrEngineInterface` to an OCR pipeline (e.g., Tesseract or Google Cloud Vision OCR) for scanned vernacular and Hindi/regional language notifications.
3. **Email Approval Delivery:**
   - Integrate authenticated email dispatch (e.g. SMTP or Google Workspace OAuth) to email draft previews with expiring single-use approval links to designated human reviewers.
4. **Live CMS Integration (Only When Authorized):**
   - Implement `TestkartCmsPublisher` implementing `PublisherInterface`, protected by two-factor reviewer authentication and hash-matched publishing guards.
