# Supervised Local Pilot Report — Fresh Official Notices

**Project:** Testkart Government Exam Intelligence  
**Scope:** Controlled Supervised Local Pilot on Fresh Official Notices  
**Execution Date:** October 29, 2026  
**Environment:** Local Workstation (`D:\Agent`)  
**Pilot Dataset:** `PILOT_DATASET_MANIFEST.json` (15 fresh notices, 0% benchmark overlap)  
**Safety Invariants:** `ALLOW_LIVE_PUBLISHING = False`, `ENABLE_EMAIL_NOTIFICATIONS = False`, Local Mock Publisher Only  
**Overall Decision:** **GO FOR CONTROLLED EXPANSION OF LOCAL PILOT**

---

## 1. Executive Summary

Following the successful execution and passing of the End-to-End Editorial Acceptance Suite (14/14 passed) and Full Regression Suite (126/126 passed, Exit Code 0), a controlled supervised local pilot was initiated using a fresh, representative batch of official government notices.

The objectives of this pilot were to:
1. Probe live official listing endpoints across the five authorized authorities: **UPSC, SSC, NTA, UPPSC, and TNPSC**.
2. Assemble a fresh 15-document evaluation batch strictly verified against all 130 existing benchmark notices to ensure **0% overlap**.
3. Freeze extraction logic and preserve all existing benchmark manifests without tuning.
4. Run the complete local lifecycle: discovery, deduplication, multi-strategy extraction, article drafting, QA evaluation, human evidence review, audited overrides, and simulated mock publication.
5. Verify scheduler cron configuration for twice-daily scans at **06:00 and 18:00 Asia/Kolkata** and document operational boundaries.
6. Measure critical-field extraction reliability, reviewer workload, and failure modes across real-world heterogeneous document types.

---

## 2. Fresh Pilot Batch & Zero-Overlap Verification

### 2.1 Overlap Verification Across Existing Benchmarks
All 15 documents in the fresh pilot batch were checked against all five established benchmark manifests:
- `DEVELOPMENT_SET_MANIFEST.json` (13 notices)
- `FROZEN_HELD_OUT_DATASET_MANIFEST.json` (33 notices)
- `GENERALIZATION_SET_MANIFEST.json` (21 notices)
- `NEW_VALIDATION_DATASET_MANIFEST.json` (52 notices)
- `VERIFICATION_SET_MANIFEST.json` (11 notices)

**Total Benchmark Hashes Checked:** 130 unique SHA-256 hashes  
**Collisions Found:** **0 (0.0% overlap)**

### 2.2 Fresh Pilot Batch Manifest (`PILOT_DATASET_MANIFEST.json`)

| Pilot ID | Authority | Source Code | Title / Description | Format & Size | SHA-256 Hash |
|:---|:---|:---:|:---|:---:|:---|
| **pilot_01** | Staff Selection Commission | `SSC` | Sub-Inspector in Delhi Police & CAPFs Examination | PDF (715.4 KB) | `cd8800911a6c...` |
| **pilot_02** | Staff Selection Commission | `SSC` | Combined Hindi Translators Exam 2026 (Answer Keys) | PDF (117.5 KB) | `5e32d9e86f79...` |
| **pilot_03** | Staff Selection Commission | `SSC` | Grade 'C' Stenographers Limited Dept. Exam (LDCE) | PDF (276.1 KB) | `b038f451a978...` |
| **pilot_04** | Union Public Service Commission | `UPSC` | Addendum Notice: 03 Posts of Law Officer, GNCTD | HTML (29.2 KB) | `6740ef1a5c42...` |
| **pilot_05** | Union Public Service Commission | `UPSC` | Addendum Notice: 140 Posts of Asst Public Prosecutor | HTML (29.3 KB) | `4de436feb3cf...` |
| **pilot_06** | Union Public Service Commission | `UPSC` | Addendum Notice: 05 Posts of Asst Public Prosecutor (CBI) | HTML (29.4 KB) | `af23000f4765...` |
| **pilot_07** | Tamil Nadu Public Service Commission | `TNPSC` | Rashtriya Indian Military College (July-2024 Term) | PDF (202.8 KB) | `10ed22a0f3f9...` |
| **pilot_08** | Tamil Nadu Public Service Commission | `TNPSC` | Rashtriya Indian Military College (Jan-2025 Term) | PDF (196.9 KB) | `b4150b0c1662...` |
| **pilot_09** | Tamil Nadu Public Service Commission | `TNPSC` | Combined Engineering Subordinate Services Exam | PDF (2.36 MB) | `8bbe3214b0a5...` |
| **pilot_10** | Uttar Pradesh Public Service Commission | `UPPSC` | Samiksha Adhikari / Sahayak Samiksha Adhikari (English) | HTML (159.9 KB) | `5286cc1f8968...` |
| **pilot_11** | Uttar Pradesh Public Service Commission | `UPPSC` | Samiksha Adhikari / Sahayak Samiksha Adhikari (Hindi) | HTML (159.9 KB) | `85feb864f3a8...` |
| **pilot_12** | National Testing Agency | `NTA` | Advisory & Instructions Registration JEE Main 2026 | PDF (714.1 KB) | `d24733397846...` |
| **pilot_13** | National Testing Agency | `NTA` | Extension of Last Date for Application Form (UGC-NET) | PDF (398.3 KB) | `abf6b8a9cebd...` |
| **pilot_14** | National Testing Agency | `NTA` | Correction in Particulars of Online Application Form | PDF (915.9 KB) | `588e5ef8b1e7...` |
| **pilot_15** | National Testing Agency | `NTA` | Relocation of NTA Office (Administrative Notice) | PDF (235.7 KB) | `5081418ee394...` |

---

## 3. End-to-End Workflow Execution & Governance Results

Each notice was executed sequentially through discovery deduplication, document ingestion, multi-strategy fact extraction, automated draft generation, QA rule inspection, editorial review gating, and mock publication.

| Pilot ID | Authority | QA Score | Can Normally Approve | Decision Type | Reviewer Action / Blocker Reason | Simulated Publish URL |
|:---|:---:|:---:|:---:|:---|:---|:---|
| **pilot_01** | SSC | 60.0 | **NO** | `OVERRIDE_APPROVED` | Candidate writeup; dates not in document; override recorded | `https://mock.testkart.local/blog/staff-selection-commission-sub-inspector...` |
| **pilot_02** | SSC | 60.0 | **NO** | `OVERRIDE_APPROVED` | Tentative answer key upload; override recorded | `https://mock.testkart.local/blog/staff-selection-commission-combined-hindi...` |
| **pilot_03** | SSC | 20.0 | **NO** | `BLOCKED_MANUAL` | QA blocked: internal departmental competition (`rule_recruitment_not_internal`) | *None (Publishing Blocked)* |
| **pilot_04** | UPSC | 60.0 | **NO** | `OVERRIDE_APPROVED` | Addendum notice: 03 vacancies verified; application closed; override recorded | `https://mock.testkart.local/blog/union-public-service-commission-addendum-notice-03-posts...` |
| **pilot_05** | UPSC | 60.0 | **NO** | `OVERRIDE_APPROVED` | Addendum notice: 140 vacancies verified; application closed; override recorded | `https://mock.testkart.local/blog/union-public-service-commission-addendum-notice-140-posts...` |
| **pilot_06** | UPSC | 60.0 | **NO** | `OVERRIDE_APPROVED` | Addendum notice: 05 vacancies verified; application closed; override recorded | `https://mock.testkart.local/blog/union-public-service-commission-addendum-notice-05-posts...` |
| **pilot_07** | TNPSC | 60.0 | **NO** | `BLOCKED_MANUAL` | School entrance admission notice; missing employment vacancy facts | *None (Publishing Blocked)* |
| **pilot_08** | TNPSC | 60.0 | **NO** | `BLOCKED_MANUAL` | School entrance admission notice; missing employment vacancy facts | *None (Publishing Blocked)* |
| **pilot_09** | TNPSC | **100.0** | **YES** | **`ORDINARY_APPROVED`** | Full recruitment notice: 1,083 posts, Diploma, 18-32 yrs, all dates verified | `https://mock.testkart.local/blog/tamil-nadu-public-service-commission-combined-engineering...` |
| **pilot_10** | UPPSC | 60.0 | **NO** | `BLOCKED_MANUAL` | Portal framing page; vacancy table in attachment; approval blocked | *None (Publishing Blocked)* |
| **pilot_11** | UPPSC | 60.0 | **NO** | `BLOCKED_MANUAL` | Portal framing page (Hindi); attachment not rendered; approval blocked | *None (Publishing Blocked)* |
| **pilot_12** | NTA | 60.0 | **NO** | `OVERRIDE_APPROVED` | Advisory on JEE registration; override recorded | `https://mock.testkart.local/blog/national-testing-agency-advisory-and-instructions...` |
| **pilot_13** | NTA | 60.0 | **NO** | `OVERRIDE_APPROVED` | Application date extension notice; override recorded | `https://mock.testkart.local/blog/national-testing-agency-extension-of-last-date...` |
| **pilot_14** | NTA | 60.0 | **NO** | `OVERRIDE_APPROVED` | Form correction window announcement; override recorded | `https://mock.testkart.local/blog/national-testing-agency-3-correction-in-particulars...` |
| **pilot_15** | NTA | 60.0 | **NO** | `OVERRIDE_APPROVED` | Office relocation administrative notice; override recorded | `https://mock.testkart.local/blog/national-testing-agency-relocation-of-nta-office` |

---

## 4. Critical-Field Extraction & Governance Metrics

### 4.1 Field Extraction Statistics (Across 15 Pilot Documents)

| Critical Field | Extracted & Verified | Extracted & Unverified | Absent / Not Applicable | Notes on Document Distribution |
|:---|:---:|:---:|:---:|:---|
| **Total Vacancies** | **5** (33.3%) | 0 (0.0%) | 10 (66.7%) | Extracted in full notice (1083 in `pilot_09`) and addenda (03, 140, 05 in `pilot_04-06`, 48387 in `pilot_01`). Not applicable in advisories/calendars. |
| **Eligibility Requirements** | **1** (6.7%) | 0 (0.0%) | 14 (93.3%) | Extracted in full notice (`pilot_09`: Diploma in Civil Engg). Addenda/advisories contain no qualification sections. |
| **Age Limit & Relaxations** | **1** (6.7%) | 0 (0.0%) | 14 (93.3%) | Extracted in full notice (`pilot_09`: 18 to 32 years). |
| **Application Start Date** | **1** (6.7%) | 0 (0.0%) | 14 (93.3%) | Extracted in full notice (`pilot_09`: 03.02.2023). |
| **Application Closing Date** | **1** (6.7%) | 0 (0.0%) | 14 (93.3%) | Extracted in full notice (`pilot_09`: 04.03.2023). |
| **Examination Dates** | **4** (26.7%) | 0 (0.0%) | 11 (73.3%) | Extracted in full notice (`pilot_09`: 27.05.2023) and date advisories. |

### 4.2 Reviewer Workload & Decisions

- **Total Documents Evaluated:** 15
- **Ordinary Approval Granted:** 1 (6.7%) — `pilot_09` achieved a flawless **100.0% QA score** with zero corrections required.
- **Ordinary Approval Strictly Blocked:** **14 (93.3%)**
  - **Audited Editorial Overrides:** 9 (60.0%) — Approved only after recording explicit justifications in `audit_events` (for addenda, date extensions, advisories).
  - **Blocked Requiring Manual Resolution:** 5 (33.3%) — Kept blocked (internal departmental exams, school entrance exams, web portal wrappers).
- **Unsupported Claims in Drafts:** **0** (all generated claims strictly anchored to verified extracted facts).
- **Processing Performance:**
  - Average pipeline latency per document: **0.84 seconds**
  - Minimum latency: 0.06 seconds
  - Maximum latency: 6.09 seconds (2.36 MB PDF extraction)
  - Total batch elapsed time: 12.59 seconds

---

## 5. Scheduler Verification (06:00 & 18:00 Asia/Kolkata)

### 5.1 Configuration & CronTrigger Verification
The scheduling architecture was inspected and verified via programmatic test execution:
- **Configured Timezone:** `Asia/Kolkata` (`settings.TIMEZONE`)
- **Scan Hours:** `[6, 18]` (`settings.SCAN_HOURS`)
- **Scan Minutes:** `0` (`settings.SCAN_MINUTES`)
- **Trigger Type:** `CronTrigger(hour='6,18', minute=0, timezone='Asia/Kolkata')`

### 5.2 Next Fire Times in Asia/Kolkata
Using the active workstation clock (`2026-10-29 16:31:30 IST`), APScheduler calculated the next four fire times:
1. `2026-10-29 18:00:00 IST` (Today at 18:00)
2. `2026-10-30 06:00:00 IST` (Tomorrow at 06:00)
3. `2026-10-30 18:00:00 IST` (Tomorrow at 18:00)
4. `2026-10-31 06:00:00 IST` (Day after tomorrow at 06:00)

### 5.3 Operational Limitations Documented
> [!IMPORTANT]
> **Operational Finding:**  
> The `ScanScheduler` class correctly configures the cron trigger and includes non-blocking thread locking (`self._lock.acquire(blocking=False)`) to prevent overlapping runs.  
> However, `ScanScheduler` is currently not initialized inside the FastAPI `lifespan` handler in `testkart_intelligence/api/app.py`. When running `cli serve`, the scheduler must either be started via a dedicated background daemon process or explicitly mounted into the FastAPI application lifespan. Unattended execution should not be claimed until this integration is enabled.

---

## 6. Real-World Document Stream Insights & Failure Analysis

The fresh pilot batch revealed key insights about the live document streams of official government portals:

1. **Heterogeneous Document Stream:**
   Live portals publish not only comprehensive initial recruitment advertisements, but also addenda (updating vacancy counts), corrigenda (extending dates), candidate result writeups, entrance test announcements, and administrative relocations.
2. **Safeguard Invariant Strength:**
   When an addendum or non-recruitment notice was ingested under the default `RECRUITMENT_NOTIFICATION` pipeline, the QA agent and approval gate performed exactly as designed: **ordinary approval was blocked in 100% of cases**. Zero incomplete articles were allowed to pass without human intervention.
3. **Internal Departmental Guard:**
   `pilot_03` (SSC Limited Departmental Exam) triggered `rule_recruitment_not_internal`, scoring 20.0% on QA and halting drafting. This confirms that internal government promotions are successfully quarantined from public job candidate articles.
4. **HTML Portal Framing:**
   UPPSC notices (`pilot_10` and `pilot_11`) returned ASP.NET framing pages with links to secondary attachment views rather than direct inline tables. The extractor correctly identified the lack of critical dates in the wrapper HTML, blocking approval and preventing hallucinated article text.

---

## 7. Pilot Recommendation

### **Recommendation: GO FOR CONTROLLED EXPANSION OF LOCAL PILOT**

The supervised local pilot has demonstrated that:
1. **Zero Contamination:** The evaluation dataset has 0% overlap with existing benchmarks.
2. **Flawless Safety Gates:** Ordinary approval is strictly blocked whenever critical fields are absent, unverified, or contradictory.
3. **Audited Transparency:** Every override requires mandatory justification logged to `audit_events`.
4. **Publishing Isolation:** `ALLOW_LIVE_PUBLISHING = False` and `ENABLE_EMAIL_NOTIFICATIONS = False` remain strictly enforced. Zero external side effects occurred.

### Next Steps for Pilot Expansion:
- **Triage Pre-filter:** Enhance `NoticeClassifier` before drafting to automatically assign specialized templates for `ADDENDUM`, `DATE_EXTENSION`, and `EXAM_SCHEDULE` notices, reducing reviewer workload while keeping ordinary approval gates strict.
- **FastAPI Lifespan Mount:** Mount `ScanScheduler` into `app.py` lifespan with an opt-in configuration flag (`ENABLE_BACKGROUND_SCHEDULER = True/False`).
