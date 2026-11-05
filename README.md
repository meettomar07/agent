# Testkart Government Exam Intelligence & Publishing Multi-Agent System

A local-first, multi-agent intelligence and publishing platform for **Testkart** that discovers government examination notifications exclusively from verified official Indian government portals, extracts structured recruitment facts, verifies claims against verbatim document evidence, generates publication-ready blog drafts, and provides an audited editorial review interface for human verification, correction, approval, and mock publishing.

> [!IMPORTANT]
> **Operational Status: Supervised Pilot & Release Candidate Verified.**
> - **Live Publishing:** Strictly disabled in code and runtime configuration (`ALLOW_LIVE_PUBLISHING = False`). Only `MockPublisher` is permitted.
> - **External Notifications:** Email dispatch is strictly disabled (`ENABLE_EMAIL_NOTIFICATIONS = False`).
> - **Localhost Boundary:** The editorial dashboard and API are strictly bound to `127.0.0.1:8000`.
> - **Zero Fabrication:** The system strictly prohibits synthetic or fabricated pilot scans, notices, or human reviewer actions.

---

## Table of Contents

1. [Executive Summary & Core Philosophy](#1-executive-summary--core-philosophy)
2. [Current System Status & Key Metrics](#2-current-system-status--key-metrics)
3. [Architectural Overview & 7 Pipeline Stages](#3-architectural-overview--7-pipeline-stages)
4. [Safety Invariants & Non-Negotiable Guardrails](#4-safety-invariants--non-negotiable-guardrails)
5. [Repository Structure & Data Layout](#5-repository-structure--data-layout)
6. [Quickstart & Onboarding Guide](#6-quickstart--onboarding-guide)
7. [Comprehensive CLI Reference](#7-comprehensive-cli-reference)
8. [Editorial Review Dashboard User Guide](#8-editorial-review-dashboard-user-guide)
9. [Official Sources Registry (12 Authorized Portals)](#9-official-sources-registry-12-authorized-portals)
10. [Scheduler & Windows Process Lifecycle](#10-scheduler--windows-process-lifecycle)
11. [Database Schema & Data Model Reference](#11-database-schema--data-model-reference)
12. [Testing, Verification & Quality Gates](#12-testing-verification--quality-gates)
13. [Operational Runbook & Troubleshooting](#13-operational-runbook--troubleshooting)
14. [Future Production Roadmap & Hand-off Checklist](#14-future-production-roadmap--hand-off-checklist)
15. [Documentation Index & References](#15-documentation-index--references)

---

## 1. Executive Summary & Core Philosophy

Government examination candidates in India frequently suffer from misinformation, expired deadlines, hallucinated vacancy numbers, and deceptive clickbait published by unverified coaching blogs and aggregators.

**Testkart Intelligence** solves this with an anti-hallucination, evidence-first multi-agent architecture:
- **Authoritative Ingestion Only:** Notices are harvested directly from official `.gov.in`, `.nic.in`, or explicitly verified autonomous bodies (e.g. `ibps.in`, `nta.ac.in`). All commercial scrapers, coaching websites, and social media links are blocked at the networking layer.
- **Verbatim Evidence Linking:** Every single extracted recruitment fact (dates, vacancies, age limit, qualifications, fees) is immutably linked to a verbatim quote snippet and specific page number in the official PDF/HTML document.
- **Fail-Closed Quality Gates:** If a critical recruitment fact cannot be authoritatively verified or if a PDF is unreadable, automated approval is blocked.
- **Human-in-the-Loop Supervision:** Human editors review drafts side-by-side with original official documents. Any editorial change generates an immutable version $N+1$, invalidates prior approvals, and logs a tamper-evident audit entry.

---

## 2. Current System Status & Key Metrics

| Metric | Current Status / Value | Verified By |
| :--- | :--- | :--- |
| **Release Readiness** | **Phase 3 End-to-End Acceptance Approved** | 10/10 operational scenarios passed |
| **Automated Test Suite** | **185 passed** / 185 tests (100% green) | `pytest -q` (519s execution) |
| **Diagnostic Health** | **7 / 7 Suites Passed** (`[PASS]`) | `python -m testkart_intelligence.cli doctor` |
| **Tracked Canonical Notices** | **1,986 notices** | `data/real_world_pilot_30day.db` |
| **Recorded Scan Runs** | **8 runs** (1 baseline, 6 missed window detections, 1 live) | Audited scan runs table |
| **Archived Documents** | **396 files** (26.15 MB) | `data/documents/` local repository |
| **Active Official Portals** | **12 / 12 portals enabled** | Source registry & security allowlist |
| **Runtime Environment** | Python 3.13.13 on Windows 10/11 (x64) | Tested on CPython 3.11+ |
| **Live Publishing State** | **STRICTLY DISABLED (`False`)** | Security assertion & API guardrails |
| **Notification Dispatch** | **STRICTLY DISABLED (`False`)** | Zero external SMTP/OAuth dispatches |

---

## 3. Architectural Overview & 7 Pipeline Stages

```
                                 +-------------------------------------+
                                 |    12 Official Government Portals   |
                                 |  (.gov.in, .nic.in, ibps.in, etc.)  |
                                 +------------------+------------------+
                                                    |
                                                    v
                                 +-------------------------------------+
                                 | 1. Source Registry & Security Guard |
                                 |    - Strict Domain Allowlist        |
                                 |    - Host-Scoped TLS (SECLEVEL=1/2) |
                                 |    - SSRF & Credential Interception |
                                 +------------------+------------------+
                                                    |
                                                    v
                                 +-------------------------------------+
                                 | 2. Discovery Engine & Crawlers      |
                                 |    - HTML Listing & Table Parsers   |
                                 |    - SSC Official REST API Parser   |
                                 |    - SHA-256 Multi-Factor Dedupl.   |
                                 |    - Corrigenda & Revision Linking  |
                                 +------------------+------------------+
                                                    |
                                                    v
                                 +-------------------------------------+
                                 | 3. Document Extraction & OCR Gate   |
                                 |    - PyMuPDF Page Text Extractor    |
                                 |    - Visual Layout Row Clusterer    |
                                 |    - Tabular Multi-Column Extractor |
                                 |    - Scanned PDF Gate (<50 chars)   |
                                 +------------------+------------------+
                                                    |
                                                    v
                                 +-------------------------------------+
                                 | 4. Fact Extractor & Verifier        |
                                 |    - Dates, Vacancies, Age, Fees    |
                                 |    - Verbatim Excerpt Matching      |
                                 |    - Document Page Referencing      |
                                 |    - Contradiction & Conflict Check |
                                 +------------------+------------------+
                                                    |
                                                    v
                                 +-------------------------------------+
                                 | 5. Notice Classifier & Writer       |
                                 |    - 9-Class Recruitment Classifier |
                                 |    - Deterministic Jinja2 Templates |
                                 |    - SHA-256 Content Hash Binding   |
                                 +------------------+------------------+
                                                    |
                                                    v
                                 +-------------------------------------+
                                 | 6. Quality Assurance Gate           |
                                 |    - Missing Fact Detection         |
                                 |    - Official Link Integrity Check  |
                                 |    - Lowercase Branding Rule        |
                                 |    - Strict Score Gate (Min 85.0)   |
                                 +------------------+------------------+
                                                    |
                                                    v
                                 +-------------------------------------+
                                 | 7. Local Editorial Dashboard        |
                                 |    - Side-by-Side Evidence Review   |
                                 |    - Audited Overrides & Edits      |
                                 |    - Version Invalidation (vN+1)    |
                                 |    - Single-Use Hash Tokens         |
                                 |    - Guarded Mock Publisher         |
                                 +-------------------------------------+
```

### Stage Details

1. **Official Source Registry & Security Allowlist (`testkart_intelligence/security/`)**
   - Validates all outbound network targets against `OFFICIAL_DOMAIN_ALLOWLIST`.
   - Inspects redirect hops: any destination outside allowlisted domains raises `SecurityValidationError`.
   - Automatically handles legacy government TLS handshakes by applying OpenSSL `SECLEVEL=1` strictly to allowlisted legacy servers (`ibps.in`, `rrbcdg.gov.in`) while keeping modern `SECLEVEL=2` everywhere else.
   - Blocks SSRF targets (private 10.x, 192.168.x, 127.x, 169.254.x, and cloud metadata endpoints).

2. **Discovery Engine (`testkart_intelligence/discovery/`)**
   - Discovers new notices using specialized parsers:
     - HTML listing parser with soft-404 and error-redirect detection (`FileNotFound.aspx`, `error.aspx`).
     - Staff Selection Commission official REST API client (`ssc.gov.in/api/general-website/portal/notice-boards`).
   - Computes canonical URL normalization, advertisement number normalization, and document SHA-256 hashing.
   - Detects revisions: if a notice URL publishes an updated PDF with a differing hash, an immutable `notice_version` ($v2$) is generated and parent-child corrigendum linkage is created.

3. **Document Extraction & Layout Reconstruction (`testkart_intelligence/extraction/`)**
   - Uses PyMuPDF (`pymupdf`) for high-fidelity text extraction.
   - **Rotated & Multi-Column Layouts:** Employs `_reconstruct_layout_lines` to cluster bounding boxes into horizontal visual rows, properly handling pages rotated 90°, 180°, or 270° and multi-column tables.
   - **Tabular Extraction:** Extracts structured vacancy, post-wise, and category-wise grids via `TableExtractor`.
   - **Scanned Document Reliability Gate:** Pages with <50 characters of extractable text are tagged as scanned and blocked from automated article drafting until reviewed or OCR-processed.

4. **Fact Extraction & Traceable Verification (`testkart_intelligence/extraction/`)**
   - Extracts 8 critical recruitment attributes: `application_start_date`, `application_end_date`, `exam_date`, `total_vacancies`, `age_limit`, `eligibility`, `application_fee`, and `salary_pay_scale`.
   - Verifies each fact against the raw text: checks verbatim snippet occurrence, page number, confidence score, and checks for contradictory date ranges or conflicting vacancy numbers.

5. **Classification & Deterministic Writing (`testkart_intelligence/classification/`, `writing/`)**
   - Classifies notices into 9 standard categories: `NEW_RECRUITMENT`, `CORRIGENDUM`, `EXAM_DATE_ANNOUNCEMENT`, `ADMIT_CARD`, `ANSWER_KEY`, `RESULT`, `APPLICATION_WINDOW_UPDATE`, `SYLLABUS_PATTERN`, `OTHER_ANNOUNCEMENT`.
   - Renders factual markdown drafts via deterministic Jinja2 templates.
   - Computes an immutable SHA-256 `content_hash` across the generated title and markdown body.

6. **Quality Assurance Gate (`testkart_intelligence/writing/qa_agent.py`)**
   - Runs automated rule checks: document readability, presence of critical recruitment dates, absence of placeholder tokens, correct lowercase `testkart` branding, valid source URLs, and heading fragment rejection.
   - Computes a QA score (0-100). Drafts scoring below 85.0 or failing critical rules are flagged as `QA_FAILED` and blocked from approval.

7. **Local Editorial Dashboard & Mock Publishing (`testkart_intelligence/api/`)**
   - A local-first FastAPI interface running on `127.0.0.1:8000`.
   - Provides side-by-side comparison between the official document evidence and the draft.
   - Enforces single-use approval tokens, audited overrides with mandatory justification, and concurrency conflict protection (`409 Conflict`).
   - Mock publishing verifies payload delivery without modifying external systems.

---

## 4. Safety Invariants & Non-Negotiable Guardrails

These safety invariants are enforced at the architectural, database, and code levels:

> [!CAUTION]
> 1. **Live Publishing is Strictly Disabled:** `settings.ALLOW_LIVE_PUBLISHING = False` is hardcoded in `config.py` and guarded by assertions in `api/routes/publishing.py`. Live API calls to external CMS or web endpoints will immediately raise `RuntimeError`.
> 2. **External Email Notifications are Disabled:** `settings.ENABLE_EMAIL_NOTIFICATIONS = False`. No outbound SMTP connections or socket calls are permitted during local operation.
> 3. **Pilot Data Preservation:** The pilot database `data/real_world_pilot_30day.db` contains 1,986 real official notices. Never modify, truncate, or overwrite this database with synthetic test fixtures. All automated tests run against in-memory databases or temporary `tmp_path` copies.
> 4. **No Fabricated Records:** Scan runs, notices, and human reviewer actions must never be fabricated. Missed scan windows caused by machine downtime are recorded honestly as `MISSED` with zero discovered notices.
> 5. **Strict Domain Allowlist:** Only verified official domains ending in `.gov.in`, `.nic.in`, or explicitly verified autonomous portal domains (`ibps.in`, `nta.ac.in`) may be requested.

---

## 5. Repository Structure & Data Layout

```
d:\Agent
├── data/                                # Local persistent storage (gitignored except seed)
│   ├── real_world_pilot_30day.db       # Real-world 30-day pilot database (1,986 notices, WAL mode)
│   ├── testkart.db                     # Default seed database
│   ├── documents/                      # Local PDF/HTML cache (396 files, 26.15 MB)
│   ├── validation_notices/             # 33 held-out real official notices for accuracy benchmarking
│   └── scheduler.lock                  # Transient scheduler PID lock (created only when running)
├── testkart_intelligence/               # Core application package
│   ├── api/                            # Local FastAPI editorial dashboard & REST API
│   │   ├── app.py                      # FastAPI application factory & lifespan
│   │   └── routes/                     # Dashboard HTML and JSON API endpoints
│   ├── classification/                 # 9-class notice categorization and triage
│   ├── database/                       # SQLite connection management & schema migrations
│   │   ├── connection.py               # Path coercion, WAL mode, foreign key enforcement
│   │   ├── models.py                   # Pydantic data transfer objects
│   │   └── schema.sql                  # Full relational DDL (13 tables, indexes)
│   ├── discovery/                      # Web scraping, SSC API, deduplication engine
│   ├── editorial/                      # Workflow review, override auditing, metrics
│   ├── extraction/                     # PDF layout reconstruction, table extraction, facts
│   ├── publishing/                     # Mock publisher & publishing guardrails
│   ├── registry/                       # Official portal registry & seed service
│   ├── scheduler/                      # APScheduler job runner, PID locks, missed window detector
│   ├── security/                       # Domain allowlist, TLS cipher configuration, input sanitization
│   ├── writing/                        # Jinja2 factual templates, QA agent, rule engine
│   ├── cli.py                          # Unified CLI entry point (`python -m testkart_intelligence.cli`)
│   ├── config.py                       # Pydantic settings & environment defaults
│   └── diagnostics.py                  # Read-only system doctor (`cli doctor`)
├── tests/                               # Comprehensive test suite (185 automated tests)
│   ├── test_cli_doctor.py              # Tests for all 7 diagnostic suites
│   ├── test_windows_process_lifecycle.py # Normal, Ctrl+C, SIGBREAK, and abrupt shutdown tests
│   ├── test_release_cb01_cb02_mj01.py  # Path coercion, PID validation, lock cleanup tests
│   ├── test_end_to_end_product_acceptance.py # 10 mandatory operational acceptance scenarios
│   ├── test_pre_production_accuracy_evaluation.py # 33-document held-out accuracy evaluation
│   └── ...                             # 22 additional unit, integration, and regression suites
├── scratch/                             # Benchmarking and offline evaluation scripts
├── pyproject.toml                       # Python package dependencies and build configuration
└── README.md                            # Comprehensive project guide (this document)
```

---

## 6. Quickstart & Onboarding Guide

### Prerequisites
- **Operating System:** Windows 10/11, Linux, or macOS (Windows verified)
- **Python:** Python 3.11, 3.12, or 3.13 (CPython 3.13.13 verified)
- **Git:** Git 2.40+ installed

### Step 1: Environment Setup
```powershell
# Navigate to the repository
cd d:\Agent

# Create and activate a Python virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Upgrade pip and install the package in editable mode
python -m pip install --upgrade pip
pip install -e .
```

### Step 2: Run Read-Only System Diagnostics
Before starting any services, verify system health using the `doctor` command:
```powershell
python -m testkart_intelligence.cli doctor
```
*Expected result:* All 7 diagnostic categories must report `[PASS]`.

### Step 3: Launch the Editorial Review Dashboard
Start the local FastAPI review dashboard on `http://127.0.0.1:8000`:
```powershell
python -m testkart_intelligence.cli serve --host 127.0.0.1 --port 8000
```
Open your browser to:
- **Web Dashboard:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Swagger API Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### Step 4: Run a Manual Discovery Scan
To fetch the latest notices from active official portals:
```powershell
# Scan all 12 enabled official portals
python -m testkart_intelligence.cli scan

# Or scan a single specific portal (e.g. UPSC)
python -m testkart_intelligence.cli scan --source UPSC
```

### Step 5: Start the Background Scheduler Daemon
To run the automated twice-daily discovery scheduler (06:00 and 18:00 IST):
```powershell
python -m testkart_intelligence.cli scheduler
```
*Note: Press `Ctrl+C` to terminate cleanly. The PID lock in `data/scheduler.lock` will be safely removed.*

---

## 7. Comprehensive CLI Reference

All operational tasks can be managed via `python -m testkart_intelligence.cli <command>`.

| Command | Subcommand / Options | Description |
| :--- | :--- | :--- |
| **`doctor`** | `--db PATH` | Runs read-only diagnostic check across configuration, safety flags, DB integrity, whitelist, lock file, and storage. |
| **`status`** | *none* | Displays quick operational counts (sources, scans, notices discovered, drafts, QA passed). |
| **`metrics`** | *none* | Shows cumulative operational metrics, reliability %, uptime %, and mock publication counts. |
| **`scan`** | `[--source CODE]` | Triggers an immediate discovery scan across all enabled sources or a specific source code. |
| **`serve`** | `[--host H] [--port P]` | Starts the local Uvicorn web dashboard server (default: `127.0.0.1:8000`). |
| **`scheduler`**| *none* | Runs the foreground twice-daily scheduler daemon with PID locking and graceful shutdown. |
| **`sources`** | `list [--enabled-only]` | Lists all registered official government sources, domains, and active statuses. |
| **`sources`** | `enable --code CODE` | Enables discovery scans for a specified authority (e.g. `--code UPSC`). |
| **`sources`** | `disable --code CODE`| Disables discovery scans for a specified authority. |
| **`triage`**  | *none* | Runs discovery quality triage and recency breakdown across all canonical notices. |
| **`init`**    | *none* | Initializes the database schema and seeds official government portals if empty. |

---

## 8. Editorial Review Dashboard User Guide

The editorial dashboard provides human-in-the-loop oversight to ensure that no blog post is published without human verification.

### Key Views & Navigation
1. **Overview (`/`):** Summary cards displaying total notices, pending drafts, blocked documents, active sources, and scan health.
2. **Canonical Notices (`/editorial/notices`):** Search and filter all discovered notices by authority, category, recency, or keyword.
3. **Draft Articles (`/editorial/articles`):** Review drafts categorized by status (`AWAITING_REVIEW`, `QA_PASSED`, `APPROVED`, `REJECTED`).
4. **Scan History (`/editorial/scans`):** Audit trail of every scan run, including timestamps, sources checked, notices discovered, and downtime missed windows.

### Side-by-Side Review & Editing (`/editorial/articles/{id}`)
- **Left Panel (Authoritative Evidence):**
  - Official source portal URL and download link to the local PDF/HTML document copy.
  - Document SHA-256 hash.
  - Extracted facts with verbatim quote snippets, page numbers, and verification status (`VERIFIED`, `CONTRADICTORY`, `MISSING`).
- **Right Panel (Draft Editor & Markdown Preview):**
  - Live editable Markdown draft and rendered preview.
  - QA rule check report with pass/fail reasons.
  - Actions:
    - **Approve Draft:** Permitted only when critical facts (dates, vacancies) are verified and QA passes. Generates single-use hash-bound approval token.
    - **Audited Editorial Override:** If automated extraction missed a fact that the editor sees in the document, the editor can submit an override with a mandatory justification explanation ($\ge 10$ characters).
    - **Save Edit (vN+1):** Any text change generates version $N+1$, resets status to `DRAFT`, and invalidates prior approvals.
    - **Reject:** Marks the draft as rejected with recorded reasoning.
    - **Mock Publish:** Simulates publishing payload delivery for approved articles.

---

## 9. Official Sources Registry (12 Authorized Portals)

All 12 sources are verified official government recruitment bodies and are currently **ENABLED**:

| Code | Authority Name | State / Level | Category | Verified Official Domain | Retrieval |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **UPSC** | Union Public Service Commission | Central | Central Recruitment | `www.upsc.gov.in` | HTML / PDF |
| **SSC** | Staff Selection Commission | Central | Central Recruitment | `ssc.gov.in` | Official REST API |
| **NTA** | National Testing Agency | Central | Teaching & Eligibility | `nta.ac.in` | HTML / PDF |
| **IBPS** | Institute of Banking Personnel Selection | Central | Banking Recruitment | `ibps.in` | HTML / Legacy TLS |
| **RRB_CHD** | Railway Recruitment Board (Chandigarh) | Central | Railway Recruitment | `rrbcdg.gov.in` | HTML / Legacy TLS |
| **JOIN_ARMY** | Indian Army Recruitment (Join Indian Army) | Central | Defence Recruitment | `joinindianarmy.nic.in` | HTML / PDF |
| **UPPSC** | Uttar Pradesh Public Service Commission | Uttar Pradesh | State PSC | `uppsc.up.nic.in` | HTML / PDF |
| **TNPSC** | Tamil Nadu Public Service Commission | Tamil Nadu | State PSC | `www.tnpsc.gov.in` | HTML / PDF |
| **BPSC** | Bihar Public Service Commission | Bihar | State PSC | `bpsc.bih.nic.in` | HTML / PDF |
| **MPPSC** | Madhya Pradesh Public Service Commission | Madhya Pradesh | State PSC | `mppsc.mp.gov.in` | HTML / PDF |
| **KPSC** | Karnataka Public Service Commission | Karnataka | State PSC | `kpsc.kar.nic.in` | HTML / Lenient HTTP |
| **DSSSB** | Delhi Subordinate Services Selection Board | Delhi | Subordinate Services | `dsssb.delhi.gov.in` | HTML / PDF |

### Adding a New Source Safely
1. Verify the domain belongs to `.gov.in`, `.nic.in`, or an official statutory body.
2. Add the apex domain to `OFFICIAL_DOMAIN_ALLOWLIST` in `testkart_intelligence/security/allowlist.py`.
3. Add the authority code to `ALL_AUTHORIZED_OFFICIAL_SOURCES` in `testkart_intelligence/diagnostics.py` and `APPROVED_SOURCES` in `testkart_intelligence/discovery/engine.py`.
4. Insert the source record into `official_sources` via `SourceRegistryService`.

---

## 10. Scheduler & Windows Process Lifecycle

The discovery scheduler runs twice daily at **06:00 and 18:00 IST** (Asia/Kolkata).

### Process Concurrency & PID Locking
- **Lock File:** Stored at `data/scheduler.lock`. Contains the active process PID, start timestamp, and hostname.
- **Mutual Exclusion:** Prevents concurrent scheduler instances. Attempting to start a second scheduler raises `SchedulerAlreadyRunningError`.
- **Windows PID Validation:** On startup, the scheduler verifies if the PID recorded in the lock file corresponds to an active Python process (via Windows `tasklist`).
- **Stale Lock Recovery:** If the PID does not exist (e.g. system reboot or power outage), the stale lock is safely pruned and logged.
- **Safe Signal Handling:** Interception of `SIGINT` (Ctrl+C), `SIGTERM`, and Windows `SIGBREAK` ensures the lock is cleanly deleted during process termination without deleting locks owned by other processes.

### Downtime Gap Detection (Missed Windows)
When the scheduler starts after a period of machine sleep or downtime:
- It checks for scheduled scan windows that were missed while the machine was off.
- For each missed window, it records an entry in `scan_runs` with `status = 'MISSED'` and `scan_type = 'SCHEDULED'`.
- It **does not fabricate** scan records or mock discovered notices.
- The operator can trigger a manual scan (`python -m testkart_intelligence.cli scan`) to safely catch up on new notices.

---

## 11. Database Schema & Data Model Reference

The SQLite schema (`testkart_intelligence/database/schema.sql`) enforces relational integrity with WAL journal mode and foreign keys enabled:

1. `official_sources`: Registry of official government examination portals with status, failure counters, and domains.
2. `scan_runs`: Audit history of scheduled and manual scan executions (`COMPLETED`, `FAILED`, `MISSED`).
3. `scan_source_logs`: Granular per-portal execution records, response latency (ms), and error logs.
4. `canonical_notices`: Canonical identity of examinations, normalized URLs, categories, and triage flags.
5. `notice_versions`: Immutable document versions storing SHA-256 hashes, local PDF/HTML paths, and raw text.
6. `extracted_facts`: Traceable facts linked to verbatim document quotes, page numbers, and verification statuses.
7. `fact_corrections_log`: Audit ledger of all human editor corrections, recording previous values and reasons.
8. `blog_articles`: Blog drafts with current version IDs, categories, and publication lifecycle statuses.
9. `article_versions`: Immutable Markdown versions, content hashes, and author attribution.
10. `qa_results`: Detailed rule-by-rule pass/fail test results, scores, and failure messages.
11. `approval_records`: Replay-protected approvals with single-use token hashes, reviewer emails, and override logs.
12. `publishing_jobs`: Publishing attempt records, mock publisher payloads, and published URLs.
13. `audit_events`: Comprehensive tamper-evident ledger for all significant actions and decisions.

---

## 12. Testing, Verification & Quality Gates

The system includes a 185-test regression and acceptance suite.

### Running Tests
```powershell
# Run the complete test suite
pytest -q

# Run specific test modules
pytest tests/test_end_to_end_product_acceptance.py -v
pytest tests/test_cli_doctor.py -v
pytest tests/test_windows_process_lifecycle.py -v
```

### Mandatory Acceptance Scenarios Verified (`test_end_to_end_product_acceptance.py`)
1. **Standard Recruitment Notice:** Normal end-to-end processing with dates, vacancies, QA pass, approval, and mock publish.
2. **Missing Application Dates Notice:** Blocks normal approval; requires human clarification or override.
3. **Contradictory Recruitment Facts Notice:** Detects date or vacancy contradictions; blocks publication.
4. **Multi-Date Examination Timetable:** Accurately extracts multi-stage schedules without truncation.
5. **Corrigendum Extending Deadline:** Links corrigendum to parent notice, updates timeline, resets draft.
6. **Corrigendum Modifying Vacancies:** Updates vacancy numbers and invalidates prior approvals.
7. **Notice Cancellation:** Overrides generic recruitment templates and formats strict cancellation alert.
8. **Duplicate Notice Ingestion:** Discards unchanged duplicate notices idempotently using document hashes.
9. **Corrupt PDF Ingestion:** Handles zero-byte or malformed PDF gracefully without crashing.
10. **Official Source Unavailable:** Handles portal downtime or 5xx errors; logs failures without aborting scan.

---

## 13. Operational Runbook & Troubleshooting

### Common Operational Issues

#### Issue 1: "Scheduler lock file already held" (`SchedulerAlreadyRunningError`)
- **Cause:** A scheduler process is already running or a previous process was abruptly killed.
- **Resolution:**
  1. Check if a scheduler process is active:
     ```powershell
     Get-Process python | Select-Object Id, ProcessName
     ```
  2. Run `python -m testkart_intelligence.cli doctor` — the diagnostic checker will inspect the PID in `data/scheduler.lock` and report whether the process is alive.
  3. If no scheduler process is running, delete the orphaned lock file:
     ```powershell
     Remove-Item data/scheduler.lock
     ```

#### Issue 2: Legacy TLS Handshake Failure on `ibps.in` or `rrbcdg.gov.in`
- **Cause:** Some government portals run legacy SSL/TLS servers requiring OpenSSL `SECLEVEL=1` ciphers.
- **Resolution:** Testkart Intelligence automatically applies `SECLEVEL=1` strictly to these two allowlisted domains in `testkart_intelligence/security/client.py`. No manual SSL modification is necessary.

#### Issue 3: Portal Returns HTTP 403 or Cloudflare Challenge
- **Cause:** Government portal WAF rate-limiting.
- **Resolution:**
  - Increase crawl delay in `.env`: `TESTKART_RATE_LIMIT_DELAY_SECONDS=2.5`.
  - Use single-source scanning during off-peak hours: `python -m testkart_intelligence.cli scan --source UPSC`.

---

## 14. Future Production Roadmap & Hand-off Checklist

When transferring ownership or transitioning from supervised local pilot to production:

- [ ] **Step 1: Production OCR Integration**
  - Connect `testkart_intelligence/extraction/ocr.py` to an enterprise OCR service (e.g. Google Cloud Document AI, Cloud Vision API, or local Tesseract) for Hindi and scanned vernacular circulars.
- [ ] **Step 2: Authenticated Email Dispatch**
  - Implement authenticated SMTP/SES in `testkart_intelligence/editorial/notifications.py` to deliver expiring approval links to designated reviewers.
- [ ] **Step 3: Testkart Live CMS Publisher**
  - Implement `TestkartCmsPublisher` implementing `PublisherInterface` in `publishing/`.
  - Configure production OAuth credentials, API keys, and endpoint URLs.
  - Review and obtain administrative approval before flipping `ALLOW_LIVE_PUBLISHING = True`.
- [ ] **Step 4: All-India Portal Expansion**
  - Expand `official_sources` registry to cover remaining State PSCs, High Courts, and Police Recruitment Boards across all 28 states and 8 UTs.

---

## 15. Documentation Index & References

For deep-dive architecture reviews and experimental logs, refer to these deliverables in the workspace:

| Document | Description |
| :--- | :--- |
| **`END_TO_END_PRODUCT_ACCEPTANCE_REPORT.md`** | Complete Phase 3 acceptance test report across 10 operational scenarios. |
| **`RELEASE_REMEDIATION_PHASE_2_REPORT.md`** | Windows process lifecycle, PID lock recovery, and `cli doctor` implementation. |
| **`30_DAY_SUPERVISED_PILOT_REPORT.md`** | 30-day operational pilot findings, notice discovery rates, and latency logs. |
| **`REAL_WORLD_VALIDATION_REPORT.md`** | Real-world validation against live Indian government exam notifications. |
| **`PRE_PRODUCTION_ACCURACY_EVALUATION.csv`**| 33-notice held-out pre-production accuracy evaluation benchmark. |
| **`SOURCE_COVERAGE_MATRIX.csv`** | Portal coverage, domain allowlist status, and retrieval methods. |
| **`TABLE_AND_ELIGIBILITY_REMEDIATION_REPORT.md`**| Layout reconstruction and structured table extraction documentation. |

---

### Maintainer & Project Owner
- **Primary Contact:** Meet Tomar (`meettomar07@gmail.com`)
- **Repository:** [https://github.com/meettomar07/agent.git](https://github.com/meettomar07/agent.git)
- **License:** Proprietary — All Rights Reserved to Testkart (India).
