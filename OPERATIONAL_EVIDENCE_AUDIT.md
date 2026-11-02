# Operational Evidence Audit & Discrepancy Reconciliation

**Project:** Testkart Government Exam Intelligence  
**Directory:** `D:\Agent`  
**Audit Date:** November 2, 2026  
**Audited Artifacts:**
- `30_DAY_SUPERVISED_PILOT_REPORT.md`
- `scratch/run_30_day_operational_pilot.py`
- `data/operational_pilot_30day.db`
- `data/testkart.db`
- `tests/test_30_day_operational_pilot.py`

---

## 1. Executive Metric Reconciliation & Root Cause Analysis

### 1.1 The Reported Discrepancy
An initial audit of `30_DAY_SUPERVISED_PILOT_REPORT.md` revealed a numeric discrepancy between the Executive Summary and the Source-Wise Operational Reliability table:
- **Executive Summary stated:** `300 Source Checks, 294 Successes, 6 Failures (98.00% Reliability)`
- **Source-Wise Table stated:** `305 Scans Attempted, 301 Successful, 4 Failed (98.69% Reliability)`

### 1.2 Mathematical & Database Reconciliation
Every metric was recalculated directly from the pilot database (`data/operational_pilot_30day.db`):

```sql
-- 1. Scan Runs Count
SELECT scan_type, status, count(*) FROM scan_runs GROUP BY scan_type, status;
-- Result: 61 scan runs, ALL status = 'COMPLETED', scan_type = 'SCHEDULED'

-- 2. Scan Source Logs Count
SELECT status, count(*) FROM scan_source_logs GROUP BY status;
-- Result: 
--   SUCCESS_NO_NEW: 283
--   SUCCESS_NEW:     18
--   FAILED:           4
-- Total Source Logs: 305
```

#### Detailed Breakdown of the 61 Scan Runs:
1. **60 Simulated 30-Day Windows (Days 1–30 at 06:00 and 18:00 Asia/Kolkata):**
   - 60 scheduled windows $\times$ 5 official sources = **300 source checks**.
   - Exactly **4 simulated failure events** were programmed into the 30-day timeline:
     - Day 4 Window 1 (`2026-10-04T06:00:00Z`): SSC Portal HTTP 503 (`Service Unavailable - Scheduled Maintenance`).
     - Day 11 Window 1 (`2026-10-11T06:00:00Z`): UPPSC Portal Socket Timeout (`Network Connection Timeout (15.0s)`).
     - Day 19 Window 1 (`2026-10-19T06:00:00Z`): NTA Portal HTTP 500 (`Internal Server Error`).
     - Day 22 Window 2 (`2026-10-22T18:00:00Z`): TNPSC Soft 404 (`SoftErrorPageDetected: filenotfound.aspx`).
   - Outcome of the 300 simulated checks:
     - Successful: **296** ($280 \text{ SUCCESS\_NO\_NEW} + 16 \text{ SUCCESS\_NEW}$)
     - Failed: **4**
     - Reliability: $\frac{296}{300} = \mathbf{98.67\%}$
2. **1 Live Wall-Clock Scheduler Test Scan (`scan_9f67dbbec97e`):**
   - Executed during Step 1 (`sched_live.scan_job()`) to verify live APScheduler background worker thread execution against the pilot database.
   - Checked all 5 enabled sources (UPSC, SSC, NTA, UPPSC, TNPSC).
   - Outcome: **5 source checks, 5 successful** ($3 \text{ SUCCESS\_NO\_NEW} + 2 \text{ SUCCESS\_NEW}$), **0 failures**.
   - Timestamp: `2026-11-02T07:11:29.951599+00:00`.
3. **Database Cumulative Total:**
   - Total Scans: $60 \text{ simulated} + 1 \text{ live} = \mathbf{61 \text{ scan runs}}$.
   - Total Source Checks: $300 \text{ simulated} + 5 \text{ live} = \mathbf{305 \text{ source checks}}$.
   - Total Successful Checks: $296 + 5 = \mathbf{301 \text{ successful checks}}$.
   - Total Failed Checks: $4 + 0 = \mathbf{4 \text{ failed checks}}$.
   - Overall Reliability: $\frac{301}{305} = \mathbf{98.69\%}$.

### 1.3 Root Cause of the Discrepancy
In `scratch/run_30_day_operational_pilot.py`, the markdown generator dynamically pulled the Source-Wise Table directly from the database query `cum_metrics` (correctly printing `305 checks, 301 successful, 4 failed`), but the author had mistakenly entered a static placeholder in the Executive Summary table (`300 checks, 294 successes, 6 failures`), erroneously assuming 6 failure events instead of the 4 actual failure events.

The report has been reconciled using strictly verified database-backed figures.

---

## 2. Reviewer Activity & Approval Integrity Audit

### 2.1 Complete Inspection of Approval Records
An inspection of `approval_records` in `data/operational_pilot_30day.db` reveals exactly 10 approval records:

| # | Approval ID | Article ID & Version | Notice & Authority | Reviewer Email | Decided Timestamp (UTC) | Delta from Prior | Decision Notes |
| :-: | :--- | :--- | :--- | :--- | :--- | :-: | :--- |
| 1 | `appr_137e9bc5db72` | `art_658235be0271` (v1) | Civil Services 2026 (UPSC) | `meettomar07@gmail.com` | `2026-11-02T07:11:34.216053` | Baseline | UPSC Gazette verified. |
| 2 | `appr_71d7d45acd97` | `art_cc9dc29d1d1b` (v1) | Combined Graduate Level 2026 (SSC) | `meettomar07@gmail.com` | `2026-11-02T07:11:34.397252` | +181 ms | SSC CGL Gazette verified. |
| 3 | `appr_35ce30eefbca` | `art_b8def5df5e70` (v1) | Combined State Services 2026 (UPPSC) | `meettomar07@gmail.com` | `2026-11-02T07:11:34.579204` | +182 ms | UPPSC PCS verified. |
| 4 | `appr_b8d4bd9454f8` | `art_6c834ad82992` (v1) | Corrigendum to CGL 2026 (SSC) | `meettomar07@gmail.com` | `2026-11-02T07:11:34.791020` | +212 ms | Deadline extension verified. |
| 5 | `appr_3eed12e0456d` | `art_969bae1c54a1` (v1) | SWAYAM July 2026 Semester (NTA) | `meettomar07@gmail.com` | `2026-11-02T07:11:35.011299` | +220 ms | Entrance bulletin verified. |
| 6 | `appr_bc45b4676231` | `art_5dd3fcf2873d` (v1) | Addendum: PCS Exam 2026 (UPPSC) | `meettomar07@gmail.com` | `2026-11-02T07:11:35.222379` | +211 ms | Addendum verified. |
| 7 | `appr_c551d201d4ad` | `art_1dcd530efb19` (v1) | Joint CSIR-UGC NET Dec 2026 (NTA) | `meettomar07@gmail.com` | `2026-11-02T07:11:35.443329` | +221 ms | Exam schedule verified. |
| 8 | `appr_f6e9b83ba136` | `art_dbb963f7805b` (v1) | Geo-Scientist Schedule 2027 (UPSC) | `meettomar07@gmail.com` | `2026-11-02T07:11:35.638779` | +195 ms | Timetable verified. |
| 9 | `appr_5b837655e126` | `art_6069f1b74075` (v1) | Cancellation of Advt A-1/E-1 (UPPSC) | `meettomar07@gmail.com` | `2026-11-02T07:11:35.859587` | +221 ms | Cancellation notice published. |
| 10 | `appr_06de4f9a9347` | `art_76fed9bc2a64` (v1) | Corrigendum-II: CGL 2026 (SSC) | `meettomar07@gmail.com` | `2026-11-02T07:11:36.103227` | +244 ms | Corrigendum II approved. |

### 2.2 Forensic Finding: Simulated Programmatic Driver vs Human Interaction
- **Elapsed Duration:** All 10 approval records were generated within **1.887 seconds** (`07:11:34.216` to `07:11:36.103` UTC).
- **Execution Mechanism:** Every decision was submitted programmatically via `editorial.submit_decision(..., editor_email="meettomar07@gmail.com", client_ip="127.0.0.1")` called from the driver script `scratch/run_30_day_operational_pilot.py`.
- **Finding:** **ZERO real human editorial interactions took place during the pilot run.** The email `meettomar07@gmail.com` was passed as an automated parameter to exercise the approval workflow, token validation, and mock publishing triggers.
- **Reporting Rule:** In accordance with strict operational integrity, these approvals must be designated as **"Automated Simulated Approvals (Test Driver)"** and never reported as real human editorial review. Actual human review metrics in the live pilot must remain at `0` until a real human reviewer evaluates drafts via the web interface.

---

## 3. Test Evidence & Failure Traceback Audit

### 3.1 Initial Test Suite Failures (Run 1: `task-8674`)
During initial execution of `tests/test_30_day_operational_pilot.py`, 4 tests failed out of 6:

```text
FAILED tests/test_30_day_operational_pilot.py::test_notice_lifecycle_all_states - KeyError: 'extracted_facts'
FAILED tests/test_30_day_operational_pilot.py::test_corrigendum_and_update_lifecycle_scenarios - AssertionError: assert 'exam_schedule.md.j2' == 'EXAM_DATE_ANNOUNCEMENT'
FAILED tests/test_30_day_operational_pilot.py::test_reliability_and_recovery_drills - testkart_intelligence.extraction.pdf_extractor.PdfExtractionError: Failed to open PDF: Failed to open stream
FAILED tests/test_30_day_operational_pilot.py::test_operational_metrics_service_and_actor_auditing - sqlite3.IntegrityError: FOREIGN KEY constraint failed
```

#### Diagnostic Analysis & Remediations:
1. **`KeyError: 'extracted_facts'` in `test_notice_lifecycle_all_states`:**
   - *Cause:* Test asserted `editor_data["extracted_facts"]`, whereas `EditorialService.get_draft_editor()` structures facts under `editor_data["critical_fields_summary"]` and `editor_data["notice_review"]["extracted_facts"]`.
   - *Fix:* Updated assertion to check `editor_data["critical_fields_summary"]`.
2. **`AssertionError` on Template Type in `test_corrigendum_and_update_lifecycle_scenarios`:**
   - *Cause:* `blog_articles.template_type` stores Jinja template file names (`exam_schedule.md.j2`, `cancellation.md.j2`), not category enum strings (`EXAM_DATE_ANNOUNCEMENT`).
   - *Fix:* Asserted actual template filename `exam_schedule.md.j2`.
3. **`PdfExtractionError` in `test_reliability_and_recovery_drills`:**
   - *Cause:* `verifier.process_and_verify_document()` passed corrupt byte streams directly to `PdfDocumentExtractor.extract()`, raising an unhandled `PdfExtractionError`.
   - *Application Defect Remediated:* In `verifier.py`, wrapped extraction in a `try/except Exception` block. When corrupt or truncated byte streams are encountered, `verifier.py` sets `is_corrupt_doc = True`, records `canonical_status = "SCANNED_OCR_BLOCKED_FLAGGED_FOR_HUMAN_REVIEW"`, and logs an unreadable document fact item. This guarantees resilient graceful degradation without crashing.
4. **`sqlite3.IntegrityError: FOREIGN KEY constraint failed` in `test_operational_metrics_service_and_actor_auditing`:**
   - *Cause:* Test attempted to insert into `extracted_facts` referencing `ver_test_01` before inserting the parent `notice_versions` and `canonical_notices` rows.
   - *Fix:* Inserted valid parent records before creating the extracted fact.
5. **`ValueError` in `WritingAgent.draft_article` on Blocked Notice:**
   - *Cause:* Test attempted to call `writer.draft_article(blocked_id)` where `status = SCANNED_OCR_BLOCKED_FLAGGED_FOR_HUMAN_REVIEW`. `WritingAgent` has a built-in safeguard halting automated drafting of unreadable documents.
   - *Fix:* Exercised `ApprovalBlockedError` by supplying an extracted recruitment notice with missing critical dates, which drafts successfully but blocks normal approval.
6. **`AttributeError: 'MatchType' has no attribute 'DUPLICATE_IDENTICAL'`:**
   - *Cause:* Test checked for non-existent enum member.
   - *Fix:* Checked for `MatchType.UNCHANGED`.

### 3.2 Final Regression Test Execution (`task-8740`)
Following all code remediations, the full regression suite was executed across all 23 test modules:

- **Exact Command:** `pytest tests/ -q`
- **Total Test Items Collected:** 146
- **Test Outcomes:**
  - **Passed:** 146
  - **Failed:** 0
  - **Skipped:** 0
- **Execution Time:** 298.84 seconds (0:04:58)
- **Actual Exit Code:** `0`

---

## 4. Data Integrity & Isolation Audit

### 4.1 Evaluation Dataset Isolation
All 9 dataset manifests and ground-truth files were verified against git `HEAD`:

| Manifest File | Document Count | Integrity Status |
| :--- | :---: | :---: |
| `DEVELOPMENT_SET_MANIFEST.json` | 13 | Verified (Frozen) |
| `FROZEN_HELD_OUT_DATASET_MANIFEST.json` | 33 | Verified (Frozen) |
| `GENERALIZATION_SET_MANIFEST.json` | 21 | Verified (Frozen) |
| `INDEPENDENT_ACCURACY_AUDIT_MANIFEST.json` | 15 | Verified (Frozen) |
| `NEW_VALIDATION_DATASET_MANIFEST.json` | 52 | Verified (Frozen) |
| `PILOT_BATCH_2_MANIFEST.json` | 15 | Verified (Frozen) |
| `PILOT_DATASET_MANIFEST.json` | 15 | Verified (Frozen) |
| `VERIFICATION_SET_MANIFEST.json` | 11 | Verified (Frozen) |
| `REMEDIATION_EVALUATION_MANIFEST.json` | 15 | Verified (Frozen) |
| **Total Benchmark Universe** | **190 documents (175 prior + 15 fresh)** | **0 collisions** |

### 4.2 Database Isolation
The pilot test driver operated against `data/operational_pilot_30day.db`. The primary production/local database `data/testkart.db` was verified:

```sql
-- data/testkart.db state:
scan_runs:           4
canonical_notices:   1,944
blog_articles:       8
approval_records:    5
publishing_jobs:     0 (100% mock published, 0 live)
```
`data/testkart.db` is completely intact and isolated from the pilot run.

### 4.3 Git Working Tree
- Working tree clean.
- Untracked diagnostic files (`scratch/audit_pilot_evidence.py`) preserved in scratch directory.

---

## 5. Correction of Readiness Conclusion

| Pilot Phase | Operational Reality | Evidence Type | Validated Conclusion |
| :--- | :--- | :--- | :--- |
| **Simulated 30-Day Execution** | 60 sequential scan windows, 300 checks, 6 corrigendum scenarios, 8 recovery drills | Deterministic programmatic test driver | **VALIDATED (Simulation)** |
| **Live Scheduler Test** | Real APScheduler background thread execution, Asia/Kolkata cron trigger, lock contention check | Live wall-clock process (4,058 ms) | **VALIDATED (Short-duration)** |
| **Real-World Operational Pilot** | 30 actual calendar days with daily wall-clock scans and human editorial reviews | Not yet conducted | **PENDING EXECUTION** |

### Revised Recommendation
> [!WARNING]
> **Operational Status: GO FOR SUPERVISED LOCAL OPERATION ONLY**  
> Unattended production deployment is **NOT** recommended. The system must operate under supervised local conditions with real human editorial oversight for 30 actual calendar days before production CMS/web publication is considered.
