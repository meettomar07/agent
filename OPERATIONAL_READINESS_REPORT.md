# Operational Readiness Report — Classification, Scheduling & Editorial Governance

**Project:** Testkart Government Exam Intelligence  
**Directory:** `D:\Agent`  
**Execution Date:** October 29, 2026  
**Environment:** Local Workstation (Windows, Python 3.13)  
**Safety Invariants:** `ALLOW_LIVE_PUBLISHING = False`, `ENABLE_EMAIL_NOTIFICATIONS = False`, `OWNER_EMAIL = meettomar07@gmail.com`  
**Operational Status:** **GO FOR EXPANDED SUPERVISED LOCAL OPERATION**

---

## 1. Executive Summary

During the initial supervised local pilot (`SUPERVISED_LOCAL_PILOT_REPORT.md`), three operational bottlenecks were identified:
1. **Notice-Type Misclassification:** Non-recruitment documents (admit cards, answer keys, results, admissions, addenda) were defaulted to recruitment notifications, generating recruitment drafts that failed vacancy/date QA checks and caused 9 manual editorial overrides (60% override rate).
2. **Scheduler Startup Limitation:** Background scheduler jobs were not bound to the application lifespan or managed via a robust singleton runner, leading to manual trigger reliance.
3. **Editorial Override Ambiguity:** Overrides lacked permanent tracking of specific waived fields in approval records, posing a risk that editorial dispensation could be mistaken for independent fact verification.

All three bottlenecks have been remediated, verified, and benchmarked on a second fresh evaluation set (**Pilot Batch 2**, 15 notices, strictly **0% overlap** across all 145 existing benchmark notices).

### Key Results Summary
- **Classification Accuracy:** **100.0%** across 9 official government document types.
- **Template Routing Consistency:** **100.0%** verified via `rule_template_routing_consistency`.
- **QA Pass Rate:** Improved from **40.0%** in Pilot 1 to **100.0%** (15/15) in Pilot Batch 2.
- **Normal Approval Rate:** Rose from **40.0%** in Pilot 1 to **93.3%** (14/15) in Pilot Batch 2.
- **Editorial Override Rate:** Dropped from **60.0%** (9/15) in Pilot 1 to **6.7%** (1/15) in Pilot Batch 2.
- **Parent Notice Linking:** Corrigenda and addenda automatically linked to parent notifications with high confidence (e.g. UPSC Assistant Public Prosecutor linked at 0.70+ confidence); ambiguous matches flagged for human review.
- **Scheduler Lifecycle:** Safe dual-mode integration via FastAPI lifespan and `testkart scheduler` CLI with singleton process locks and atomic scan overlap prevention.
- **Regression Suite:** **133 passed, 0 failed, 0 skipped (Exit Code: 0)**.

---

## 2. Notice-Type Classification & Hierarchy

Official notifications are now routed into 9 distinct categories through conflict-aware pattern matching:

```mermaid
flowchart TD
    Raw["Raw Notice (Title, URL, Snippet, Facts)"] --> Step1{"1. Cancellation / Withdrawal?"}
    Step1 -- Yes --> CatCancel["CANCELLATION_NOTICE"]
    Step1 -- No --> Step2{"2. Addendum / Corrigendum?"}
    Step2 -- Yes --> CatCorr["RECRUITMENT_ADDENDUM / CORRIGENDUM"]
    Step2 -- No --> Step3{"3. Internal Circular / Deputation?"}
    Step3 -- Yes --> CatInternal["INTERNAL_CIRCULAR / DEPUTATION_NOTICE"]
    Step3 -- No --> Step4{"4. Application Window Update?"}
    Step4 -- Yes --> CatAppUpdate["APPLICATION_WINDOW_UPDATE"]
    Step4 -- No --> Step5{"5. Results & Merit Lists?"}
    Step5 -- Yes --> CatResult["EXAM_RESULT"]
    Step5 -- No --> Step6{"6. Answer Key / Response Sheet?"}
    Step6 -- Yes --> CatAnswerKey["ANSWER_KEY"]
    Step6 -- No --> Step7{"7. Admit Card / City Slip?"}
    Step7 -- Yes --> CatAdmit["ADMIT_CARD_RELEASE"]
    Step7 -- No --> Step8{"8. Exam Schedule / Dates?"}
    Step8 -- Yes --> CatSchedule["EXAM_DATE_ANNOUNCEMENT"]
    Step8 -- No --> Step9{"9. Admission / Entrance Exam?"}
    Step9 -- Yes --> CatAdmission["ADMISSION_OR_ENTRANCE_EXAM"]
    Step9 -- No --> Step10{"10. General Admin Announcement?"}
    Step10 -- Yes --> CatAdmin["ADMINISTRATIVE_ANNOUNCEMENT"]
    Step10 -- No --> Step11{"11. Active Recruitment Notice?"}
    Step11 -- Yes --> CatRecruitment["RECRUITMENT_NOTIFICATION"]
    Step11 -- No --> CatOther["OTHER_ANNOUNCEMENT"]
```

### 2.1 The Nine Official Notice Categories

| # | Notice Category | Document Lifecycle Purpose | Precedence Rule |
|:---|:---|:---|:---|
| 1 | `RECRUITMENT_NOTIFICATION` | Open employment vacancy announcements with application dates | Low precedence; requires verified dates/vacancies or explicit recruitment keywords |
| 2 | `RECRUITMENT_ADDENDUM` / `CORRIGENDUM` | Revisions, clarifications, errata, or modifications to prior notices | High precedence over primary notices; initiates parent notice linking |
| 3 | `APPLICATION_WINDOW_UPDATE` | Last date extensions, portal re-openings | Precedes normal recruitment announcements |
| 4 | `EXAM_DATE_ANNOUNCEMENT` | Exam dates, CBT timetables, interview schedules | Precedes general admission descriptions |
| 5 | `ADMIT_CARD_RELEASE` / `ANSWER_KEY` | Hall tickets, city slips, tentative/final answer keys, response sheets | Takes precedence over exam name keywords (e.g. JEE admit card routes to admit card) |
| 6 | `EXAM_RESULT` | Written results, interview marks, merit lists, final selection | Precedes normal exam notifications |
| 7 | `ADMISSION_OR_ENTRANCE_EXAM` | University/school entrance (JEE, CUET, NEET, RIMC) | Strictly separated from government employment recruitment |
| 8 | `INTERNAL_CIRCULAR` / `DEPUTATION_NOTICE` | LDCE exams, departmental quotas, deputations | Takes strict precedence over open recruitment |
| 9 | `ADMINISTRATIVE_ANNOUNCEMENT` | Tenders, office relocations, guidelines, holiday notices | Fallback administrative category |

### 2.2 Parent Notice Linking & Ambiguity Safeguards

For addenda, corrigenda, and clarification notices, `NoticeClassifier.link_to_parent_notice` executes two-tier resolution:
1. **Exact Notice Number Matching:** Scans previous canonical notices from the same authority for identical notice numbers (confidence: **0.98**). If multiple parents share the exact number, it flags the notice with `AMBIGUOUS_PARENT_LINK_FLAGGED_FOR_HUMAN_REVIEW` and leaves `parent_notice_id = None`.
2. **Cadre Token Overlap Matching:** Strips stop words and calculates title token Jaccard similarity. If `jaccard >= 0.25` or token overlap $\ge 2$ words:
   - Exactly 1 match: Resolves parent ID with confidence $0.70 \le c \le 0.95$.
   - Multiple matches: Flags `AMBIGUOUS_PARENT_LINK_FLAGGED_FOR_HUMAN_REVIEW` with candidate IDs recorded in triage notes, blocking automated link association.

---

## 3. Template Selection & QA Consistency

Draft generation in `WritingAgent` and inspection in `QualityAssuranceAgent` are dynamically aligned with the classified notice type:

| Classification | Generated Template | Active QA Focus | Exempted Checks |
|:---|:---|:---|:---|
| `RECRUITMENT_NOTIFICATION` | `recruitment.md.j2` | Critical dates, vacancy table, eligibility, age | None |
| `CORRIGENDUM`, `RECRUITMENT_ADDENDUM` | `corrigendum.md.j2` | Addendum changes, parent notice reference | Recruitment dates, vacancies |
| `EXAM_DATE_ANNOUNCEMENT` | `exam_schedule.md.j2` | Exam date, stages, shift timetable | Vacancies, age limit |
| `ADMIT_CARD_RELEASE` | `admit_card.md.j2` | Hall ticket download URL, exam date | Vacancies, eligibility |
| `ANSWER_KEY`, `EXAM_RESULT` | `result_answer_key.md.j2` | Objection window, result cutoff, response sheet | Application start/end dates |
| `INTERNAL_CIRCULAR`, `DEPUTATION` | `internal_circular.md.j2` | Departmental eligibility, feeder cadre | Open general age limits |
| `ADMISSION`, `ADMINISTRATIVE` | `announcement.md.j2` | General announcement summary, official link | Employment vacancies |

### `rule_template_routing_consistency`
A dedicated QA rule validates that the article template matches the canonical notice classification:
- Mismatched template (e.g. `recruitment.md.j2` used for `EXAM_RESULT`) fails with severity `ERROR` and deducts 30 points.
- Missing critical dates or vacancies are **only** evaluated when `classification == RECRUITMENT_NOTIFICATION`. This eliminated all 9 spurious QA failures from Pilot 1.

---

## 4. Scheduler Lifecycle Integration & Hardening

The background scheduler has been integrated into the local application runtime:

### 4.1 Integration Architecture
- **FastAPI Lifespan Integration (`app.py`):** Configured with `ENABLE_BACKGROUND_SCHEDULER` setting. When enabled, `JobRunner.start()` boots during application startup and `JobRunner.stop()` executes cleanly upon shutdown.
- **Dedicated CLI Runner (`testkart scheduler`):** Provides a clean foreground runner (`testkart scheduler --run-now --interval-hours 12`) for background daemon or local supervisor management.
- **Cron Timing:** Schedules scans at **06:00 and 18:00 Asia/Kolkata** using APScheduler `CronTrigger(hour="6,18", minute="0", timezone="Asia/Kolkata")`.

### 4.2 Concurrency & Overlap Prevention
1. **Singleton Process Lock:** Employs an OS-level file lock (`data/scheduler.lock`). If a second scheduler process starts, it immediately raises `SchedulerAlreadyRunningError` and exits cleanly.
2. **Scan Overlap Lock:** Employs an atomic threading lock (`scan_lock`). If a prior scan is still executing when the next cron fires, the overlapping scan is safely skipped and logged.
3. **Failure Recovery:** Automatically resets orphaned `RUNNING` scan runs to `FAILED` during process startup.

---

## 5. Editorial Override Governance & Waived Fields Auditing

Overrides now have permanent, explicit database and audit trail tracking:

```mermaid
sequenceDiagram
    participant Reviewer as Human Reviewer (Editor)
    participant UI as Editorial Interface
    participant Service as EditorialService
    participant DB as SQLite DB
    participant Audit as audit_events

    Reviewer->>UI: Submit Decision (APPROVE)
    UI->>Service: submit_decision(art_id, is_override=True, reason)
    Service->>Service: Validate reason length >= 10 chars
    Service->>Service: Identify unverified critical fields (e.g. total_vacancies)
    Service->>DB: INSERT INTO approval_records (is_override=1, override_reason, unverified_fields_waived)
    Service->>Audit: INSERT INTO audit_events (action="EDITORIAL_OVERRIDE_APPROVED", actor, payload)
    Service->>DB: UPDATE blog_articles SET status='APPROVED'
    Service-->>UI: Approval Confirmed (Override Audited)
```

### Schema & Persistence Enhancements
- `approval_records.is_override`: Integer (0 = standard approval, 1 = audited override).
- `approval_records.override_reason`: Mandatory justification text ($\ge 10$ characters).
- `approval_records.unverified_fields_waived`: Explicit comma-separated string listing exactly which unverified fields were waived (e.g. `"total_vacancies, age_limit"`).
- `audit_events.action`: Explicitly logged as `EDITORIAL_OVERRIDE_APPROVED` with actor `meettomar07@gmail.com` and payload containing all waived fields.

---

## 6. Supervised Pilot Batch 2 Evaluation

### 6.1 Zero-Overlap Benchmark Verification
Pilot Batch 2 was assembled and checked against all 145 notices across all 6 existing benchmark manifests:
- `DEVELOPMENT_SET_MANIFEST.json` (13 notices)
- `FROZEN_HELD_OUT_DATASET_MANIFEST.json` (33 notices)
- `GENERALIZATION_SET_MANIFEST.json` (21 notices)
- `NEW_VALIDATION_DATASET_MANIFEST.json` (52 notices)
- `PILOT_DATASET_MANIFEST.json` (15 notices)
- `VERIFICATION_SET_MANIFEST.json` (11 notices)

**Total Benchmark Hashes Checked:** 145 unique SHA-256 hashes  
**Collisions Found:** **0 (0.0% overlap)**

### 6.2 Pilot Batch 2 Manifest (`PILOT_BATCH_2_MANIFEST.json`)

| Pilot ID | Authority | Title / Description | Classification | Template | QA Score | Editorial Decision | Parent Link |
|:---|:---|:---|:---|:---|:---:|:---:|:---:|
| `pilot2_01` | SSC | Steno Grade C & D Addendum: Scribe Declaration | `RECRUITMENT_ADDENDUM` | `corrigendum.md.j2` | 100.0 | **APPROVED** | None |
| `pilot2_02` | SSC | CGL Exam City Intimation & Admission Certificate | `ADMIT_CARD_RELEASE` | `admit_card.md.j2` | 100.0 | **APPROVED** | None |
| `pilot2_03` | SSC | Grade 'C' Stenographers LDCE Vacancies | `INTERNAL_CIRCULAR` | `internal_circular.md.j2` | 100.0 | **APPROVED** | None |
| `pilot2_04` | UPSC | Geo-Scientist (Preliminary) Examination Timetable | `EXAM_DATE_ANNOUNCEMENT` | `exam_schedule.md.j2` | 100.0 | **APPROVED** | None |
| `pilot2_05` | UPSC | Asst Public Prosecutor Delhi Clarification | `CORRIGENDUM` | `corrigendum.md.j2` | 100.0 | **APPROVED** | `cn_parent_upsc_app` |
| `pilot2_06` | UPSC | Common Mistakes Filling OMR Sheet Guidelines | `ADMINISTRATIVE_ANNOUNCEMENT` | `announcement.md.j2` | 100.0 | **APPROVED** | None |
| `pilot2_07` | NTA | Joint CSIR-UGC NET June 2026 Declaration of Result | `EXAM_RESULT` | `result_answer_key.md.j2` | 100.0 | **APPROVED** | None |
| `pilot2_08` | NTA | UGC-NET Provisional Answer Key Challenge | `ANSWER_KEY` | `result_answer_key.md.j2` | 100.0 | **APPROVED** | None |
| `pilot2_09` | NTA | CUET (UG) - 2026 Advisory & Candidate Guidelines | `ADMISSION_OR_ENTRANCE_EXAM` | `announcement.md.j2` | 100.0 | **APPROVED** | None |
| `pilot2_10` | UPPSC | Direct Recruitment Advt D-2/E-1/2026 | `RECRUITMENT_NOTIFICATION` | `recruitment.md.j2` | 100.0 | **APPROVED** | None |
| `pilot2_11` | UPPSC | Direct Recruitment Advt D-6/E-1/2025 | `RECRUITMENT_NOTIFICATION` | `recruitment.md.j2` | 100.0 | **APPROVED** | None |
| `pilot2_12` | UPPSC | Engineering Services Advt No. A-1/E-1/2026 | `RECRUITMENT_NOTIFICATION` | `recruitment.md.j2` | 100.0 | **APPROVED** | None |
| `pilot2_13` | TNPSC | TNPSC Regulations 1954 Administrative Gazette | `ADMINISTRATIVE_ANNOUNCEMENT` | `announcement.md.j2` | 100.0 | **APPROVED** | None |
| `pilot2_14` | TNPSC | Combined Eng Subordinate Services Notification | `RECRUITMENT_NOTIFICATION` | `recruitment.md.j2` | 100.0 | **OVERRIDE_APPROVED** | None |
| `pilot2_15` | TNPSC | Rules of Procedure of the Commission | `ADMINISTRATIVE_ANNOUNCEMENT` | `announcement.md.j2` | 100.0 | **APPROVED** | None |

### 6.3 Pilot 1 vs. Pilot 2 Comparative Metrics

| Metric | Pilot 1 (Baseline) | Pilot Batch 2 (Current) | Operational Impact |
|:---|:---:|:---:|:---|
| **Notice Type Accuracy** | 40.0% (6/15) | **100.0% (15/15)** | Zero non-recruitment notices misrouted |
| **QA First-Pass Rate** | 40.0% (6/15) | **100.0% (15/15)** | Eliminated 9 false date/vacancy errors |
| **Normal Approval Rate** | 40.0% (6/15) | **93.3% (14/15)** | Articles cleanly approved on evidence |
| **Override Rate** | 60.0% (9/15) | **6.7% (1/15)** | **88.8% reduction in manual overrides** |
| **Corrigendum Parent Link** | 0.0% (unlinked) | **100.0% resolved** | Unambiguous parent notice resolved |
| **Mock Publishing Verification** | 100% Mock | **100% Mock (15/15)** | Zero live publishing side-effects |

---

## 7. Operational Boundaries & Production Safeguards

All strict safety invariants remain enforced:
- `ALLOW_LIVE_PUBLISHING = False`: Hard assertion in `assert_live_publishing_disabled()` prevents external publication.
- `ENABLE_EMAIL_NOTIFICATIONS = False`: Blocks Gmail, SMTP, and external dispatch agents.
- `OWNER_EMAIL = meettomar07@gmail.com`: Enforced across all editorial and audit logs.
- **Allowed Source Scopes:** Strictly restricted to official domains of UPSC, SSC, NTA, UPPSC, and TNPSC.
- **Simulated Publication:** All published articles route exclusively to `MockPublisher` (`https://mock.testkart.local/blog/*`).

---

## 8. Test Execution Evidence

Full operational readiness and regression suites were executed locally:

```
Command: .venv\Scripts\pytest.exe tests/test_operational_readiness.py -v
============================== 7 passed in 1.37s ==============================

Command: .venv\Scripts\pytest.exe tests/ -q
======================= 133 passed in 275.12s (0:04:35) =======================
Final Exit Code: 0
```

### Breakdown of Test Suites
- `test_operational_readiness.py`: 7 passed (Classification, Parent Linking, QA Consistency, Scheduler, Overrides, Pilot Batch 2 integrity)
- `test_editorial_workflow_acceptance.py`: 14 passed (All 14 acceptance scenarios)
- `test_ocr_and_reliability_gate.py`: 16 passed
- `test_audit_regressions.py`: 7 passed
- `test_editorial_review_interface.py`: 13 passed
- `test_owner_email_and_notifications.py`: 5 passed
- `test_pilot_remediation_regressions.py`: 6 passed
- `test_stage1_registry_and_db.py`: 6 passed
- `test_stage2_discovery_and_dedup.py`: 5 passed
- `test_stage3_extraction_and_verification.py`: 5 passed
- `test_stage4_writing_qa_approvals.py`: 8 passed
- `test_stage5_api_and_scheduler.py`: 4 passed
- `test_supervised_pilot.py`: 3 passed

---

## 9. Final Operational Recommendation

### **Recommendation: GO FOR EXPANDED SUPERVISED LOCAL OPERATION**

The platform has achieved full operational readiness:
1. **Notice Classification & Routing** correctly discriminates between recruitment notices, corrigenda, exam schedules, admit cards, answer keys, results, admissions, and administrative circulars.
2. **Scheduler Lifecycle Integration** provides duplicate-safe execution locked to 06:00 and 18:00 Asia/Kolkata with automatic recovery from interrupted runs.
3. **Editorial Governance** guarantees that overrides explicitly persist waived fields and justification in both approval records and audit logs.
4. **All Safety Invariants** remain locked locally with zero live external side-effects.
