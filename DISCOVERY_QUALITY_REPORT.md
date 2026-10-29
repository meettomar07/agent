# Testkart Government Exam Intelligence — Discovery Quality Audit & Notice Triage Report

**Report Date:** 2026-10-27  
**Scan-Run ID:** `scan_7f9f617043c0`  
**Execution Environment:** Local Development (`http://127.0.0.1:8000`)  
**Safety Status:** `ALLOW_LIVE_PUBLISHING = False` strictly enforced. Zero external publishing or CMS connectivity.

---

## 1. Executive Summary & Scan Verification

Following the initial live discovery scan across five approved government recruitment portals, this comprehensive quality audit evaluates all **1,944 canonical notices** stored in the local SQLite database.

| Metric | Count | Percentage | Description / Editorial Significance |
| :--- | :--- | :--- | :--- |
| **Total Canonical Notices** | **1,944** | 100.0% | Discovered across 5 approved official authorities in run `scan_7f9f617043c0`. |
| **Historical Portal Archives** | **1,428** | **73.5%** | Pre-2026 notifications (dating back to 2018 on NTA and 2012 on TNPSC). |
| **Expired Opportunities** | **244** | **12.6%** | Notices from 2026 where application deadlines or exams have already passed. |
| **Unknown Date Markers** | **209** | **10.8%** | General guidelines, user manuals, and notices without parseable dates. |
| **Actionable Current Opportunities** | **63** | **3.2%** | **Actively open recruitments or notices published within the rolling 60-day window.** |
| **Recruitment Notifications** | **161** | 8.3% | Core recruitment notifications across active and historical cycles. |
| **Cancellation / Withdrawal Notices** | **2** | 0.1% | Explicit cancellations; 100% safeguarded from generating open recruitment drafts. |
| **Corrigenda & Amendments** | **44** | 2.3% | Modifications, revisions, and vacancy adjustments to primary notices. |
| **Application Window Updates** | **67** | 3.4% | Last-date extensions and registration re-openings. |
| **Duplicate / Series Groups** | **34 groups (96 notices)** | 4.9% | Partitioned into 28 multi-year cycles, 22 revision series, and 46 proposed merges. |

> [!IMPORTANT]
> **Key Architectural Insight for Editorial Teams:**
> Over **73% of notices in government portals are historical archive records** retained indefinitely on web pages (e.g., NTA's `NoticeBoardArchive` spans 2018–2024; TNPSC retains table entries from 2012). Inferring active status from scan discovery time would generate hundreds of obsolete blog posts. The system now enforces strict **Temporal Recency Stratification**, routing only the **63 verified CURRENT opportunities** into drafting review pipelines.

---

## 2. Authority-by-Authority Source Audit & Data Integrity

The discovery scan strictly restricted requests to the five authorized official authorities:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Scan Run: scan_7f9f617043c0                     │
│                        Total Discovered: 1,944                         │
└────────────────────────────────────────────────────────────────────────┘
        │
        ├── NTA (National Testing Agency)              1,620 notices (83.3%)
        ├── TNPSC (Tamil Nadu Public Service Comm.)      291 notices (15.0%)
        ├── UPSC (Union Public Service Commission)        20 notices ( 1.0%)
        ├── SSC (Staff Selection Commission)              10 notices ( 0.5%)
        └── UPPSC (Uttar Pradesh Public Service Comm.)     3 notices ( 0.2%)
```

### Breakdown by Authority

| Authority Name | Code | Notices Discovered | Current | Expired | Historical | Unknown | Primary Content Characteristics |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **National Testing Agency** | `src_nta` | **1,620** | 42 | 182 | **1,288** | 108 | Paginated archive table dating from 2018 to 2024; high density of exam city slips, answer keys, scorecards, and public notices. |
| **Tamil Nadu Public Service Commission** | `src_tnpsc` | **291** | 12 | 58 | **140** | 81 | Single comprehensive HTML archive table spanning 2012 to 2024. Table rows include direct links to advertisement PDFs. |
| **Union Public Service Commission** | `src_upsc` | **20** | **7** | 3 | 0 | 10 | Active recruitment announcements and exam notices; high factual density (vacancies, syllabus, dates). |
| **Staff Selection Commission** | `src_ssc` | **10** | **2** | 1 | 0 | 7 | Dynamic portal notices covering multi-stage exam dates, answer keys, and active recruitments. |
| **Uttar Pradesh Public Service Commission** | `src_uppsc` | **3** | 0 | 0 | 0 | 3 | ASP.NET advertisement portal. High-yield active recruitment notices with embedded direct registration links. |

### Sampling & Link Reachability Audit

A representative sample of discovered notices was subjected to live HTTP reachability and payload validation:

1. **UPSC Notice (`not_7f9f617043c0_0002`)**:
   - Title: *Combined Geo-Scientist (Preliminary) Examination, 2026*
   - URL: `https://upsc.gov.in/sites/default/files/Notif-CGSE-2026-engl-040924.pdf`
   - Verification: Returned `HTTP 200 OK` (789,142 bytes). Magic byte inspection confirmed valid `%PDF-1.4`.
2. **SSC Notice (`not_7f9f617043c0_0024`)**:
   - Title: *Notice of Examination for Phase-XII/2024/Selection Posts*
   - URL: `https://ssc.gov.in/api/attachment/uploads/docViewer/Notice_phase_xii_2024.pdf`
   - Verification: Returned `HTTP 200 OK` (1,245,610 bytes). Magic byte confirmed valid `%PDF-1.6`.
3. **NTA Notice (`not_7f9f617043c0_0045`)**:
   - Title: *Public Notice: Joint CSIR-UGC NET December 2024*
   - URL: `https://nta.ac.in/Notice_20241012142210.pdf`
   - Verification: Returned `HTTP 200 OK` (241,850 bytes). Valid `%PDF-1.5`.
4. **UPPSC Portal (`src_uppsc`)**:
   - URL: `https://uppsc.up.nic.in/View_Advertisement.aspx`
   - Verification: ASP.NET rejects HTTP `HEAD` method with 404, but responds with `HTTP 200 OK` (166,512 bytes HTML table) to HTTP `GET`.
5. **TNPSC Historical Purge Discovery**:
   - Verified that active TNPSC notices (2023–2024) return `HTTP 200 OK`.
   - Discovered that certain older TNPSC rows from 2012/2015 return `HTTP 404 Not Found` because TNPSC pruned old PDFs from their disk storage while retaining legacy table entries. The discovery engine safely flags these as `EXTRACTION_FAILED` without crashing.

---

## 3. Duplicates, Multi-Year Cycles, and Revision Analysis

Exact duplicate URLs were prevented at ingestion by normalized SHA-256 URL hashing (`idx_canonical_url`). However, title-similarity and entity-analysis revealed **34 duplicate/series clusters (96 notices)** requiring triage:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   Clusters Requiring Triage: 34 groups                 │
│                          (96 canonical notices)                        │
└────────────────────────────────────────────────────────────────────────┘
        │
        ├── 1. Multi-Year Cycles (28 notices)
        │      Annual recurring exams (e.g. TNPSC RIMC Admissions 2015-2024)
        │      Action: PRESERVED independently; linked by exam series ID
        │
        ├── 2. Sequential Revision Series (22 notices)
        │      Sequential corrigenda / extensions (e.g. CUET-PG amendments)
        │      Action: LINKED as parent-child revisions; resets approval state
        │
        └── 3. Proposed Merges (46 notices)
               Identical notice titles on same portal listing
               Action: FLAGGED for human review; no automated deletion
```

### 1. Multi-Year Recurring Exam Cycles (28 Notices)
- **Pattern:** Titles such as *"Rashtriya Indian Military College (RIMC) Admission"* appearing identically in 2015, 2017, 2019, 2021, 2023, and 2024.
- **Safety Decision:** These are **NOT duplicates**. They represent separate examination years and cycles. Each record is preserved independently in `canonical_notices` with `triage_flag = 'MULTI_YEAR_CYCLE'`.

### 2. Sequential Revision Series (22 Notices)
- **Pattern:** Sequential notices amending the same examination (e.g., NTA CUET-PG 2024 Initial Notice &rarr; Extension of Last Date &rarr; Correction Window &rarr; City Slip Release).
- **Safety Decision:** Assigned `triage_flag = 'REVISION_SERIES'`. When drafting occurs, the latest corrigendum automatically invalidates any pending approvals of prior versions.

### 3. Proposed Merges (46 Notices)
- **Pattern:** Identical notice titles published across multiple tabs or mirror paths on the same domain (e.g., UPSC *"Notice regarding Advt No 05/2026"*).
- **Safety Decision:** Assigned `triage_flag = 'PROPOSED_DUPLICATE'`. In accordance with safety rules, **records are never automatically deleted**. Editors can inspect both rows and confirm a merge via the dashboard review interface.

---

## 4. Notice Classification Hierarchy & Factual Safety

All 1,944 notices were classified using the prioritized rule hierarchy:

| Notice Category | Count | % Share | Safety Guardrails Enforced |
| :--- | :--- | :--- | :--- |
| `OTHER_ANNOUNCEMENT` | 1,170 | 60.2% | Generic instructions, committee lists, tenders, and non-recruitment updates. |
| `EXAM_RESULT` | 189 | 9.7% | Merit lists, selection lists, marks statements, and final recommendations. |
| `ANSWER_KEY` | 162 | 8.3% | Provisional keys, challenge windows, and final key releases. |
| `RECRUITMENT_NOTIFICATION` | 161 | 8.3% | Direct recruitment notifications, vacancy tables, and eligibility circulars. |
| `ADMIT_CARD_RELEASE` | 102 | 5.2% | Hall tickets, e-admit cards, and examination city intimation slips. |
| `APPLICATION_WINDOW_UPDATE` | 67 | 3.4% | Last-date extensions, registration portal re-openings, and fee payment grace periods. |
| `CORRIGENDUM` | 44 | 2.3% | Post adjustments, age relaxation addenda, and center changes. |
| `EXAM_DATE_ANNOUNCEMENT` | 39 | 2.0% | CBT calendars, interview schedules, and timetable announcements. |
| `SYLLABUS_UPDATE` | 8 | 0.4% | Schemes of examination, pattern modifications, and negative marking circulars. |
| `CANCELLATION_NOTICE` | 2 | 0.1% | **Strict cancellation precedence enforced. Zero active recruitment generated.** |

### Cancellation Safety Verification
- Notices `not_7f9f617043c0_1204` and `not_7f9f617043c0_1589` contain explicit cancellation terms: *"Cancellation of recruitment process for the post of..."*.
- **Precedence Verification:** The classifier prioritized `KEYWORDS_CANCELLATION` over incidental keywords like *"recruitment"* or *"posts"*.
- **Integrity Rule:** The drafting agent blocks article generation for cancellation notices, preventing false recruitment notifications or claims of active vacancies.

---

## 5. Recency Assessment & Temporal Stratification

Government recruitment websites rarely delete obsolete notices. To safeguard against publishing outdated opportunities as active recruitments, notices were stratified into four recency states:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   Temporal Recency Stratification                      │
│                          (1,944 Canonical Notices)                     │
└────────────────────────────────────────────────────────────────────────┘
        │
        ├── 1. HISTORICAL (1,428 notices / 73.5%)
        │      Dated 2018–2025. Preserved as archival references.
        │
        ├── 2. EXPIRED (244 notices / 12.6%)
        │      Dated 2026, but application deadline or exam has passed.
        │
        ├── 3. UNKNOWN (209 notices / 10.8%)
        │      No date markers in URL, title, or listing text.
        │
        └── 4. CURRENT (63 notices / 3.2%)
               ★ Actionable opportunities (active deadline or published ≤60 days).
```

### Recency Status Breakdown
1. **`CURRENT` (63 Notices / 3.2%)**:
   - Actively open application deadlines or published within the last 60 days of the reference date (`2026-10-27`).
   - Represents the **only** candidate pool eligible for recruitment article generation.
2. **`EXPIRED` (244 Notices / 12.6%)**:
   - Notifications from the 2026 examination cycle whose application deadlines have lapsed.
   - Useful for exam date tracking, admit cards, and result monitoring, but ineligible for "Apply Now" article drafting.
3. **`HISTORICAL` (1,428 Notices / 73.5%)**:
   - Archives dating from 2018 through 2025.
   - Retained in the database for precedent checking, duplicate matching, and exam pattern history.
4. **`UNKNOWN` (209 Notices / 10.8%)**:
   - General guidelines (e.g. *"Instructions for PwBD Candidates"*, *"OMR Sheet Filling Rules"*).
   - Require human review before any editorial use.

---

## 6. Local Dashboard Enhancements & Triage Controls

To support editors in navigating the 1,944 discovered records, the following dashboard improvements were implemented and verified locally at `http://127.0.0.1:8000`:

### 1. Dashboard Overview Metrics & Warning Banner
- Displays cards for:
  - **Actionable Current Opportunities (63)** (green highlight)
  - **Historical Portal Archives (1,428)** (muted grey highlight)
  - **Expired Notices (244)** (warning amber highlight)
  - **Total Discovered (1,944)**
  - **Flagged for Human Review**
- Prominent **Portal Archive Architecture Warning Banner** alerting editors that 73.5% of records are archives, with one-click buttons to filter for actionable opportunities.

### 2. Multi-Field Filter Bar
Added interactive GET filtering across:
- **Authority:** UPSC, SSC, NTA, UPPSC, TNPSC
- **Category:** All 10 notice categories
- **Recency:** `CURRENT`, `EXPIRED`, `HISTORICAL`, `UNKNOWN`
- **Review Status:** `DISCOVERED`, `EXTRACTED`, `HUMAN_REVIEW_REQUIRED`, `SCANNED_OCR_BLOCKED`, etc.
- **Search:** Free-text matching on title, notice number, and URL.

### 3. Visual Recency & Triage Badges
- `CURRENT` opportunities rendered with prominent green badge and soft green row background.
- `HISTORICAL` notices rendered with muted badge and reduced opacity.
- Triage flags (`PROPOSED_DUPLICATE`, `REVISION_SERIES`, `MULTI_YEAR_CYCLE`) highlighted with hoverable editorial notes.

### 4. Interactive "Flag for Review" Modal & REST API
- Editors can flag any notice directly from the list view.
- Provides options to override category, flag duplicates, or note factual discrepancies.
- Submits to `POST /api/editorial/notices/{id}/flag`, updating the database and logging an entry to the immutable `audit_events` table.

---

## 7. Deliverables & Acceptance Verification

### Deliverables Produced:
1. `NOTICE_TRIAGE_AUDIT.csv`: Complete 1,944-row audit dataset with 15 columns:
   `notice_id`, `authority_name`, `category`, `classification`, `notice_number`, `title`, `normalized_url`, `published_date`, `application_start_date`, `application_end_date`, `recency_status`, `triage_flag`, `triage_notes`, `manual_audit_check`, `discovered_at`.
2. `DISCOVERY_QUALITY_REPORT.md`: This comprehensive audit report.
3. Updated Local Editorial Interface:
   - `testkart_intelligence/api/app.py`: Web & REST endpoints with multi-field filtering and flagging.
   - `testkart_intelligence/editorial/service.py`: Service logic for dashboard metrics, query filters, and flag persistence.
   - `testkart_intelligence/classification/classifier.py`: Triage date extractor and classifier regex enhancements.
   - `testkart_intelligence/editorial/templates/editorial_dashboard.html`: Archive alert and distinction cards.
   - `testkart_intelligence/editorial/templates/editorial_notices_list.html`: Interactive filters, recency badges, and review modal.

### Test Suite Results:
- **Total Tests Collected:** 68
- **Tests Passing:** **68 passed in 9.62s** (100% pass rate)
- **New Tests Added:** `tests/test_discovery_quality_and_triage.py` (4 acceptance tests verifying date triage, API filters, editorial flagging, and dashboard metrics).
- **Hard Guardrail Check:** `ALLOW_LIVE_PUBLISHING = False` verified across all test runs and application routes.

---

## 8. Summary Decision & Next Phase Readiness

The first live discovery scan and triage audit confirmed that the system correctly discovers and catalogues official notices across all five approved government portals. By distinguishing **63 actionable current opportunities** from **1,428 historical archives**, the platform prevents obsolete notifications from entering the drafting pipeline.

The local system is ready for selective, human-in-the-loop drafting on verified **CURRENT** recruitment notices.
