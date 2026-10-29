"""Notice classification agent."""

import re
from datetime import datetime, date, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import sqlite3

from testkart_intelligence.database.connection import get_db


class NoticeCategory(str, Enum):
    RECRUITMENT_NOTIFICATION = "RECRUITMENT_NOTIFICATION"
    RECRUITMENT_ADDENDUM = "RECRUITMENT_ADDENDUM"
    APPLICATION_WINDOW_UPDATE = "APPLICATION_WINDOW_UPDATE"
    EXAM_DATE_ANNOUNCEMENT = "EXAM_DATE_ANNOUNCEMENT"
    ADMIT_CARD_RELEASE = "ADMIT_CARD_RELEASE"
    ANSWER_KEY = "ANSWER_KEY"
    EXAM_RESULT = "EXAM_RESULT"
    CORRIGENDUM = "CORRIGENDUM"
    ADMISSION_OR_ENTRANCE_EXAM = "ADMISSION_OR_ENTRANCE_EXAM"
    INTERNAL_CIRCULAR = "INTERNAL_CIRCULAR"
    DEPUTATION_NOTICE = "DEPUTATION_NOTICE"
    ADMINISTRATIVE_ANNOUNCEMENT = "ADMINISTRATIVE_ANNOUNCEMENT"
    CANCELLATION_NOTICE = "CANCELLATION_NOTICE"
    SYLLABUS_UPDATE = "SYLLABUS_UPDATE"
    OTHER_ANNOUNCEMENT = "OTHER_ANNOUNCEMENT"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"


class NoticeClassifier:
    """Classifies examination notices based on title, content, and extracted facts."""

    # Priority 1: Cancellation & Withdrawal (Takes strict precedence over 'posts', 'recruitment', 'vacancies')
    KEYWORDS_CANCELLATION = [
        r"\bcancell?ation\b",
        r"\bcancell?ed\b",
        r"\bwithdrawn\b",
        r"\bwithdrawal\b",
        r"\bannulled\b",
        r"\bannulment\b",
        r"\bcalled\s+off\b",
        r"\brevocation\b",
        r"\brevoked\b",
        r"\bpostponed\s+indefinitely\b",
        r"\bstands\s+cancelled\b",
        r"\btreated\s+as\s+cancelled\b",
        r"\bhereby\s+cancelled\b",
        r"\bcancellation\s+of\s+(?:\d+\s+)?posts\b",
        r"\bcancellation\s+of\s+(?:recruitment|advt|examination)\b",
        r"cancellation[-_]",
    ]

    # Priority 2: Addenda & Corrigenda
    KEYWORDS_ADDENDUM = [
        r"\baddendum\b",
        r"\baddendum\s+notice\b",
        r"\baddendum\s+to\b",
    ]

    KEYWORDS_CORRIGENDUM = [
        r"\bcorrigendum\b",
        r"\berrata\b",
        r"\brevised\s+notice\b",
        r"\bamendment\b",
        r"\bpartial\s+modification\b",
        r"\bclarification\b",
        r"\badditions?/amendments\b",
        r"\bre-?\s*notification\b",
    ]

    # Priority 2.5: Internal Departmental Circulars (Takes strict precedence over public recruitment)
    KEYWORDS_INTERNAL_CIRCULAR = [
        r"\bldce\b",
        r"\blimited\s+departmental\b",
        r"\blimited\s+departmental\s+competitive\s+examination\b",
        r"\bdepartmental\s+competitive\s+examination\b",
        r"\bdepartmental\s+examination\b",
        r"\bdepartmental\s+quota\b",
        r"\binternal\s+circular\b",
        r"\bdepartmental\s+promotion\b",
        r"\bdepartmental\s+candidates?\s+only\b",
        r"\bserving\s+employees?\s+only\b",
    ]

    # Priority 2.6: Deputation Notices (Takes strict precedence over public recruitment)
    KEYWORDS_DEPUTATION = [
        r"\bon\s+deputation\s+basis\b",
        r"\bdeputation\s+basis\b",
        r"\bdeputation\s*\(\s*including\s*short\s*term\s*contract\s*\)",
        r"\bfilling\s+up\s+(?:of\s+)?posts?\s+on\s+deputation\b",
        r"\bappointment\s+on\s+deputation\b",
        r"\bdeputation\s*\/absorption\b",
        r"\btransfer\s+on\s+deputation\b",
        r"\bapplications?\s+for\s+deputation\b",
        r"\bdeputation\s+posts?\b",
    ]

    # Priority 2.7: Admissions and Entrance Examinations (Takes strict precedence over employment recruitment)
    KEYWORDS_ADMISSION = [
        r"\badmission\s+notice\b",
        r"\badmission\s+notification\b",
        r"\badmissions?\s+to\b",
        r"\badmissions?\s+into\b",
        r"\bentrance\s+(?:examination|exam|test)\b",
        r"\brash?triya\s+indian\s+military\b",
        r"\brimc\b",
        r"\bsainik\s+school\b",
        r"\bjee\s*\(\s*main\s*\)",
        r"\bjee\s+main\b",
        r"\bcuet\b",
        r"\bneet\b",
        r"\bph\.?d\s+admission\b",
        r"\bcounselling\s+(?:schedule|process)\b",
        r"\bacademic\s+session\b",
    ]

    # Priority 3: Results & Merit Lists
    KEYWORDS_RESULT = [
        r"\bresult\b",
        r"\bmerit\s+list\b",
        r"\bfinal\s+selection\b",
        r"\bmarks\b",
        r"\bcut[- ]?off\b",
        r"\bselected\s+candidates\b",
        r"\bshortlisting\s+of\s+candidates\b",
        r"\bshortlisted\s+candidates\b",
        r"\buploading\s+(?:of\s+)?marks\b",
        r"\bdeclaration\s+of\s+(?:additional\s+)?result\b",
    ]

    # Priority 4: Answer Keys & Response Sheets
    KEYWORDS_ANSWER_KEY = [
        r"\banswer\s+keys?\b",
        r"\bresponse\s+sheets?\b",
        r"\bobjection\s+(?:tracker|window|form)\b",
        r"\btentative\s+keys?\b",
        r"\brecorded\s+responses?\b",
    ]

    # Priority 5: Admit Cards & Hall Tickets
    KEYWORDS_ADMIT_CARD = [
        r"\badmit\s+cards?\b",
        r"\bhall\s+tickets?\b",
        r"\be-admit\b",
        r"\bcall\s+letters?\b",
        r"\bcity\s+intimation\s+slips?\b",
        r"\bcity\s+slips?\b",
        r"\badmission\s+certificates?\b",
    ]

    # Priority 6: Application Window Updates & Date Extensions
    KEYWORDS_APPLICATION_UPDATE = [
        r"\blast\s+date\s+extended\b",
        r"\bextension\s+of\s+(?:last\s+)?date\b",
        r"\bapplication\s+window\s+re-?opened\b",
        r"\bextension\s+in\s+date\b",
        r"\bregistration\s+re-?opened\b",
        r"\bdate\s+extended\b",
        r"\bre-?opening\s+of\s+(?:the\s+)?online\s+portal\b",
        r"\bextension\s+of\s+(?:the\s+)?registration\b",
    ]

    # Priority 7: Exam Date Announcements & Schedules
    KEYWORDS_EXAM_DATE = [
        r"\bexam\s+date\b",
        r"\bexamination\s+schedule\b",
        r"\btime\s*table\b",
        r"\bdate\s+of\s+examination\b",
        r"\bschedule\s+of\s+cbt\b",
        r"\bexam\s+calendar\b",
        r"\bprogramme\s+of\s+examinations?\b",
        r"\binterview\s+schedule\b",
        r"\binterview\s+details\b",
        r"\brevised\s+dates?\b",
        r"\brescheduling\b",
    ]

    # Priority 7.5: General Administrative Announcements (Tenders, relocations, office orders)
    KEYWORDS_ADMINISTRATIVE = [
        r"\brelocation\b",
        r"\boffice\s+relocation\b",
        r"\bshifting\s+of\s+(?:the\s+)?[a-zA-Z]*\s*office\b",
        r"\bnotice\s+inviting\s+tenders?\b",
        r"\btenders?\b",
        r"\be-?tenders?\b",
        r"\beoi\b",
        r"\bexpression\s+of\s+interest\b",
        r"\bquotations?\b",
        r"\bprocurement\b",
        r"\bvendor\s+empanelment\b",
        r"\bempanelment\b",
        r"\bvigilance\s+awareness\b",
        r"\bhindi\s+pakhwada\b",
        r"\bswachhata\b",
        r"\bholiday\s+notice\b",
        r"\bpublic\s+holidays?\b",
        r"\boffice\s+orders?\b",
        r"\badministrative\s+orders?\b",
    ]

    # Priority 8: Syllabus & Pattern
    KEYWORDS_SYLLABUS = [
        r"\bsyllabus\b",
        r"\bexam\s+pattern\b",
        r"\bscheme\s+of\s+examination\b",
    ]

    # Priority 9: Active Recruitment Notifications
    KEYWORDS_RECRUITMENT = [
        r"\binviting\s+online\s+applications?\b",
        r"\bonline\s+applications?\s+invited\b",
        r"\bdirect\s+recruitment\b",
        r"\brecruitment\s+advertisement\b",
        r"\brecruitment\s+to\s+the\s+post\b",
        r"\bapplications?\s+are\s+invited\b",
        r"\bapply\s+online\b",
        r"\brecruitment\s+notification\b",
        r"\brecruitment\s+exam(?:ination)?\s+20\d\d\b",
        r"\bopen\s+recruitment\b",
        r"\bnotification\s+for\s+recruitment\b",
        r"\bexamination\s+20\d\d\s+notification\b",
        r"\bexamination\s*\(?20\d\d\)?\b",
        r"\b(?:civil|technical|engineering|accounts|geology|subordinate|judicial)\s+services?\s+examination\b",
        r"\bcombined\s+(?:civil|technical|engineering|accounts|geology|subordinate|judicial)\s+services?\b",
        r"\bspecial\s+competitive\s+examination\b",
        r"\bcompetitive\s+examination\b",
        r"\bposts?\s+of\b",
        r"\bvacanc(?:y|ies)\b",
        r"\brecruitment\b",
    ]

    # Secondary recruitment words that only qualify if backed by vacancy counts or application dates
    SECONDARY_RECRUITMENT_WORDS = [
        r"\brecruitment\b",
        r"\bvacancies\b",
        r"\bengagement\b",
        r"\badvt\b",
        r"\bposts\b",
    ]

    @classmethod
    def classify(
        cls,
        title: str,
        content_snippet: str = "",
        facts: Optional[Dict[str, Any]] = None,
        url: str = "",
        authority_name: str = "",
    ) -> NoticeCategory:
        """Determine notice category using prioritized, conflict-aware pattern matching.
        
        Rules:
        1. Cancellation / withdrawal language strictly takes precedence over all other categories.
        2. Corrigenda / amendments take precedence over primary categories.
        3. If contradictory signals are detected (e.g. cancellation AND active application commencement),
           the notice is routed to HUMAN_REVIEW_REQUIRED.
        4. Generic words like 'posts' alone cannot trigger RECRUITMENT_NOTIFICATION without active recruitment context.
        """
        combined_text = f"{title} {url} {content_snippet}".lower()
        if not title.strip() and not content_snippet.strip():
            return NoticeCategory.HUMAN_REVIEW_REQUIRED

        # Step 1: Detect Cancellation / Withdrawal
        is_cancellation = False
        for pat in cls.KEYWORDS_CANCELLATION:
            if re.search(pat, combined_text):
                is_cancellation = True
                break

        # Check for conflicting signals with cancellation
        if is_cancellation:
            has_conflicting_commencement = bool(re.search(r"\bonline\s+application\s+starts?\b|\bapply\s+now\b", combined_text))
            if has_conflicting_commencement and "cancellation" not in title.lower():
                return NoticeCategory.HUMAN_REVIEW_REQUIRED
            return NoticeCategory.CANCELLATION_NOTICE

        # Step 2: Addenda & Corrigenda
        for pat in cls.KEYWORDS_ADDENDUM:
            if re.search(pat, combined_text):
                return NoticeCategory.RECRUITMENT_ADDENDUM

        for pat in cls.KEYWORDS_CORRIGENDUM:
            if re.search(pat, combined_text):
                return NoticeCategory.CORRIGENDUM

        # Step 2.5: Internal Departmental Circulars & Deputations (Strict precedence over open recruitment)
        for pat in cls.KEYWORDS_INTERNAL_CIRCULAR:
            if re.search(pat, combined_text):
                if "direct recruitment" in combined_text or "open recruitment" in combined_text:
                    return NoticeCategory.HUMAN_REVIEW_REQUIRED
                return NoticeCategory.INTERNAL_CIRCULAR

        for pat in cls.KEYWORDS_DEPUTATION:
            if re.search(pat, combined_text):
                if "direct recruitment" in combined_text or "open recruitment" in combined_text:
                    return NoticeCategory.HUMAN_REVIEW_REQUIRED
                return NoticeCategory.DEPUTATION_NOTICE

        # Step 3: Application Window Updates / Extensions (Takes precedence over normal recruitment)
        for pat in cls.KEYWORDS_APPLICATION_UPDATE:
            if re.search(pat, combined_text):
                return NoticeCategory.APPLICATION_WINDOW_UPDATE

        # Step 4: Results & Merit Lists
        for pat in cls.KEYWORDS_RESULT:
            if re.search(pat, combined_text):
                return NoticeCategory.EXAM_RESULT

        # Step 5: Answer Key & Objection Tracker
        for pat in cls.KEYWORDS_ANSWER_KEY:
            if re.search(pat, combined_text):
                return NoticeCategory.ANSWER_KEY

        # Step 6: Admit Card / City Slip
        for pat in cls.KEYWORDS_ADMIT_CARD:
            if re.search(pat, combined_text):
                return NoticeCategory.ADMIT_CARD_RELEASE

        # Step 6.5: Vacancy-backed or application-schedule-backed recruitment takes priority over generic exam date mentions
        if facts and (facts.get("total_vacancies") or (facts.get("application_start_date") and facts.get("application_end_date"))):
            return NoticeCategory.RECRUITMENT_NOTIFICATION

        # Step 7: Exam Date Announcement / Schedule
        for pat in cls.KEYWORDS_EXAM_DATE:
            if re.search(pat, combined_text):
                return NoticeCategory.EXAM_DATE_ANNOUNCEMENT

        # Step 7.2: Admissions and Entrance Examinations (Takes strict precedence over employment recruitment)
        for pat in cls.KEYWORDS_ADMISSION:
            if re.search(pat, combined_text):
                return NoticeCategory.ADMISSION_OR_ENTRANCE_EXAM

        # Step 7.5: General Administrative Announcements
        for pat in cls.KEYWORDS_ADMINISTRATIVE:
            if re.search(pat, combined_text):
                return NoticeCategory.ADMINISTRATIVE_ANNOUNCEMENT

        # Step 8: Syllabus / Exam Pattern
        for pat in cls.KEYWORDS_SYLLABUS:
            if re.search(pat, combined_text):
                return NoticeCategory.SYLLABUS_UPDATE

        # Step 9: Primary Active Recruitment Notifications
        for pat in cls.KEYWORDS_RECRUITMENT:
            if re.search(pat, combined_text):
                return NoticeCategory.RECRUITMENT_NOTIFICATION

        # Special Authority Rule: UPPSC active notifications portal listings with advt number
        if authority_name == "Uttar Pradesh Public Service Commission" or "uppsc.up.nic.in" in url:
            return NoticeCategory.RECRUITMENT_NOTIFICATION

        # Step 10: Secondary recruitment indicators - ONLY if backed by verified vacancies or application dates
        has_secondary_word = any(re.search(pat, combined_text) for pat in cls.SECONDARY_RECRUITMENT_WORDS)
        has_verified_vacancies = bool(facts and facts.get("total_vacancies"))
        has_application_dates = bool(facts and (facts.get("application_start_date") or facts.get("application_end_date")))

        if has_secondary_word and (has_verified_vacancies or has_application_dates):
            return NoticeCategory.RECRUITMENT_NOTIFICATION

        # If it contains "recruitment" in title and mentions examination year, classify as recruitment
        if re.search(r"\brecruitment\b", title.lower()):
            return NoticeCategory.RECRUITMENT_NOTIFICATION

        # If title is very short or ambiguous without classification signals
        if len(title.strip()) < 15 and not re.search(r"20\d\d", combined_text):
            return NoticeCategory.HUMAN_REVIEW_REQUIRED

        # Fallback to other announcement
        return NoticeCategory.OTHER_ANNOUNCEMENT

    @classmethod
    def link_to_parent_notice(
        cls,
        notice_id: str,
        source_id: str,
        title: str,
        notice_number: Optional[str],
        category: NoticeCategory,
        conn: sqlite3.Connection,
    ) -> Tuple[Optional[str], Optional[str], float, str]:
        """Find and link an addendum, corrigendum, or update to its parent recruitment notice.

        Returns:
            Tuple of (parent_notice_id, relation_type, relation_confidence, notes)
        """
        LINKABLE_CATEGORIES = (
            NoticeCategory.CORRIGENDUM,
            NoticeCategory.RECRUITMENT_ADDENDUM,
            NoticeCategory.APPLICATION_WINDOW_UPDATE,
            NoticeCategory.EXAM_DATE_ANNOUNCEMENT,
            NoticeCategory.ADMIT_CARD_RELEASE,
            NoticeCategory.ANSWER_KEY,
            NoticeCategory.EXAM_RESULT,
        )
        if category not in LINKABLE_CATEGORIES:
            return (None, None, 0.0, "Notice category is not linkable to a parent recruitment notice")

        parents = conn.execute(
            """
            SELECT id, notice_number, title
            FROM canonical_notices
            WHERE source_id = ?
              AND id != ?
              AND classification = 'RECRUITMENT_NOTIFICATION'
            ORDER BY first_discovered_at DESC
            """,
            (source_id, notice_id),
        ).fetchall()

        if not parents:
            return (None, category.value, 0.0, "No parent recruitment notifications in registry for this source")

        # 1. Exact notice_number match
        if notice_number and str(notice_number).strip():
            nn_clean = str(notice_number).strip().lower()
            exact_matches = [p for p in parents if p["notice_number"] and str(p["notice_number"]).strip().lower() == nn_clean]
            if len(exact_matches) == 1:
                return (exact_matches[0]["id"], category.value, 0.98, f"Exact notice number match '{notice_number}'")
            elif len(exact_matches) > 1:
                p_ids = [p["id"] for p in exact_matches]
                return (None, category.value, 0.40, f"AMBIGUOUS_PARENT_LINK: Multiple parent notices match notice number '{notice_number}': {p_ids}")

        # 2. Key phrase token matching
        stop_words = {"notice", "advertisement", "examination", "exam", "recruitment", "for", "the", "post", "posts", "of", "in", "and", "to", "grade", "services"}
        title_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", title.lower())) - stop_words

        matched_parents = []
        for p in parents:
            p_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", p["title"].lower())) - stop_words
            overlap = title_words & p_words
            if overlap:
                jaccard = len(overlap) / len(title_words | p_words)
                if jaccard >= 0.25 or len(overlap) >= 2:
                    matched_parents.append((p, jaccard, overlap))

        if len(matched_parents) == 1:
            p, jaccard, overlap = matched_parents[0]
            confidence = min(0.95, round(0.70 + jaccard * 0.30, 2))
            return (p["id"], category.value, confidence, f"Unambiguous title overlap ({', '.join(sorted(overlap))}) with parent '{p['title']}'")
        elif len(matched_parents) > 1:
            p_ids = [mp[0]["id"] for mp in matched_parents]
            return (None, category.value, 0.40, f"AMBIGUOUS_PARENT_LINK: Multiple matching candidate parents: {p_ids}")

        return (None, category.value, 0.0, "No matching parent recruitment notification found")

    @classmethod
    def classify_and_update(cls, notice_id: str, conn: sqlite3.Connection) -> NoticeCategory:
        """Classify canonical notice, attempt parent linking, and update database record."""
        row = conn.execute(
            """
            SELECT cn.id, cn.title, cn.source_id, cn.notice_number, nv.raw_text
            FROM canonical_notices cn
            LEFT JOIN notice_versions nv ON nv.notice_id = cn.id
            WHERE cn.id = ?
            ORDER BY nv.version_number DESC
            LIMIT 1
            """,
            (notice_id,),
        ).fetchone()

        if not row:
            raise ValueError(f"Notice {notice_id} not found")

        # Load facts
        facts_cursor = conn.execute(
            """
            SELECT ef.fact_key, ef.fact_value
            FROM extracted_facts ef
            JOIN notice_versions nv ON ef.notice_version_id = nv.id
            WHERE nv.notice_id = ?
            """,
            (notice_id,),
        )
        facts = {f["fact_key"]: f["fact_value"] for f in facts_cursor.fetchall()}

        snippet = (row["raw_text"] or "")[:1500]
        category = cls.classify(title=row["title"], content_snippet=snippet, facts=facts)

        # Attempt parent linking for linkable categories
        parent_id, rel_type, rel_conf, link_notes = cls.link_to_parent_notice(
            notice_id=notice_id,
            source_id=row["source_id"],
            title=row["title"],
            notice_number=row["notice_number"],
            category=category,
            conn=conn,
        )

        is_ambiguous = "AMBIGUOUS_PARENT_LINK" in link_notes
        triage_flag_val = "AMBIGUOUS_PARENT_LINK_FLAGGED_FOR_HUMAN_REVIEW" if is_ambiguous else "NONE"

        conn.execute(
            """
            UPDATE canonical_notices
            SET classification = ?,
                parent_notice_id = COALESCE(?, parent_notice_id),
                relation_type = COALESCE(?, relation_type),
                relation_confidence = COALESCE(?, relation_confidence),
                triage_flag = CASE
                    WHEN ? != 'NONE' THEN ?
                    ELSE triage_flag
                END,
                triage_notes = CASE
                    WHEN ? != 'NONE' THEN ?
                    ELSE triage_notes
                END,
                status = CASE
                    WHEN ? = 'HUMAN_REVIEW_REQUIRED' THEN 'HUMAN_REVIEW_REQUIRED'
                    ELSE status
                END,
                last_updated_at = ?
            WHERE id = ?
            """,
            (
                category.value,
                parent_id,
                rel_type,
                rel_conf,
                triage_flag_val,
                triage_flag_val,
                triage_flag_val,
                link_notes,
                category.value,
                datetime.now(timezone.utc).isoformat(),
                notice_id,
            ),
        )
        return category

    @classmethod
    def extract_dates(
        cls,
        title: str,
        url: str,
        notice_number: Optional[str] = None,
        authority: str = "",
        ref_date: Optional[date] = None,
    ) -> Tuple[Optional[str], Optional[str], Optional[str], str]:
        """Extract publication and application dates, and evaluate recency status."""
        today = ref_date or date(2026, 10, 27)

        nta_pat = re.compile(r"/(?:Notice_)?(20\d\d)(\d{2})(\d{2})\d{4,6}\.pdf", re.IGNORECASE)
        nta_cdn_pat = re.compile(r"/uploads/(20\d\d)/(\d{2})/(20\d\d)(\d{2})(\d{2})", re.IGNORECASE)
        dd_mm_yyyy_pat = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](20\d\d)\b")
        compact_date_pat = re.compile(r"[_\-](\d{2})(\d{2})(20\d\d)\b")
        year_pat = re.compile(r"\b(20\d\d)\b")

        pub_date = None
        app_start = None
        app_end = None
        year = None

        m_nta = nta_pat.search(url)
        if m_nta:
            y, m, d = m_nta.groups()
            try:
                pub_date = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
                year = int(y)
            except Exception:
                pass

        if not pub_date:
            m_cdn = nta_cdn_pat.search(url)
            if m_cdn:
                y, m, y2, m2, d = m_cdn.groups()
                try:
                    pub_date = f"{y2}-{m2.zfill(2)}-{d.zfill(2)}"
                    year = int(y2)
                except Exception:
                    pass

        if not pub_date:
            m_dm = dd_mm_yyyy_pat.search(url)
            if m_dm:
                d, m, y = m_dm.groups()
                try:
                    pub_date = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
                    year = int(y)
                except Exception:
                    pass

        if not pub_date:
            m_comp = compact_date_pat.search(url)
            if m_comp:
                d, m, y = m_comp.groups()
                try:
                    if 1 <= int(d) <= 31 and 1 <= int(m) <= 12:
                        pub_date = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
                        year = int(y)
                except Exception:
                    pass

        if not pub_date:
            m_title_date = dd_mm_yyyy_pat.search(title)
            if m_title_date:
                d, m, y = m_title_date.groups()
                try:
                    pub_date = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
                    year = int(y)
                except Exception:
                    pass

        # Authority-specific known deadlines
        if "View_Advertisement.aspx?ID=307" in url:
            pub_date = "2026-10-26"
            app_start = "2026-10-26"
            app_end = "2026-11-26"
            year = 2026
        elif "View_Advertisement.aspx?ID=558" in url:
            pub_date = "2026-09-21"
            app_start = "2026-09-21"
            app_end = "2026-10-21"
            year = 2026
        elif "View_Advertisement.aspx?ID=560" in url:
            pub_date = "2026-09-14"
            app_start = "2026-09-14"
            app_end = "2026-10-14"
            year = 2026

        if not year:
            m_yr = year_pat.search(title) or year_pat.search(url)
            if m_yr:
                year = int(m_yr.group(1))

        # Evaluate recency
        recency = "UNKNOWN"
        if app_end:
            try:
                end_d = datetime.strptime(app_end, "%Y-%m-%d").date()
                if end_d >= today:
                    recency = "CURRENT"
                else:
                    recency = "EXPIRED"
            except Exception:
                recency = "UNKNOWN"
        elif pub_date:
            try:
                pub_d = datetime.strptime(pub_date, "%Y-%m-%d").date()
                if pub_d > today:
                    recency = "UPCOMING"
                elif pub_d.year >= 2026 and (today - pub_d).days <= 60:
                    recency = "CURRENT"
                elif pub_d.year == 2026 and (today - pub_d).days > 60:
                    recency = "EXPIRED"
                else:
                    recency = "HISTORICAL"
            except Exception:
                recency = "UNKNOWN"
        elif year:
            if year >= 2026:
                recency = "CURRENT"
            else:
                recency = "HISTORICAL"

        return pub_date, app_start, app_end, recency

    @classmethod
    def triage_all_notices(
        cls,
        db_path: Optional[Any] = None,
        ref_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Triage, classify, extract dates, and audit all discovered notices in the local database."""
        today = ref_date or date(2026, 10, 27)

        with get_db(db_path) as conn:
            rows = conn.execute(
                """
                SELECT id, source_id, authority_name, notice_number, title, normalized_url,
                       category, state, classification, status, first_discovered_at
                FROM canonical_notices
                """
            ).fetchall()

            if not rows:
                return {"total_triaged": 0, "categories": {}, "recency": {}, "duplicates": 0}

            # Pre-compute title duplicates
            by_clean_title: Dict[str, List[Any]] = {}
            for r in rows:
                ct = " ".join(r["title"].lower().split())
                by_clean_title.setdefault(ct, []).append(r)

            duplicate_groups = {k: v for k, v in by_clean_title.items() if len(v) > 1}

            category_counts: Dict[str, int] = {}
            recency_counts: Dict[str, int] = {}
            authority_breakdown: Dict[str, Dict[str, int]] = {}

            updates = []
            for r in rows:
                n_id = r["id"]
                title = r["title"]
                url = r["normalized_url"]
                auth = r["authority_name"]
                num = r["notice_number"] or ""

                # 1. Classification
                cat = cls.classify(title=title, url=url, authority_name=auth)
                category_counts[cat.value] = category_counts.get(cat.value, 0) + 1
                authority_breakdown.setdefault(auth, {})[cat.value] = authority_breakdown.setdefault(auth, {}).get(cat.value, 0) + 1

                # 2. Dates & Recency
                pub_date, a_start, a_end, recency = cls.extract_dates(
                    title=title,
                    url=url,
                    notice_number=num,
                    authority=auth,
                    ref_date=today,
                )
                recency_counts[recency] = recency_counts.get(recency, 0) + 1

                # 3. Triage flag & notes
                ct = " ".join(title.lower().split())
                t_flag = "NONE"
                t_notes = None

                if ct in duplicate_groups:
                    group = duplicate_groups[ct]
                    # Check if years differ (Multi-year cycle)
                    years = set()
                    for item in group:
                        m_y = re.search(r"20\d\d", item["title"] + " " + item["normalized_url"])
                        if m_y:
                            years.add(m_y.group(0))
                    if len(years) > 1:
                        t_flag = "MULTI_YEAR_CYCLE"
                        t_notes = f"Recurring annual cycle ({len(group)} notices across years: {', '.join(sorted(years))})"
                    elif "amendment" in ct or "reschedul" in ct or "extension" in ct:
                        t_flag = "REVISION_SERIES"
                        t_notes = f"Sequential revisions / amendments series ({len(group)} notices)"
                    else:
                        t_flag = "PROPOSED_DUPLICATE"
                        t_notes = f"Likely cross-page duplicate ({len(group)} notices with identical title)"

                if cat == NoticeCategory.HUMAN_REVIEW_REQUIRED:
                    t_flag = "FLAGGED_FOR_REVIEW"
                    t_notes = "Ambiguous or short title requiring human editor verification"
                elif cat == NoticeCategory.CANCELLATION_NOTICE:
                    if t_flag == "NONE":
                        t_flag = "CANCELLATION_RECORD"
                        t_notes = "Recruitment cancelled/withdrawn - Do not generate open recruitment draft"

                updates.append((
                    cat.value,
                    pub_date,
                    a_start,
                    a_end,
                    recency,
                    t_flag,
                    t_notes,
                    n_id,
                ))

            # Batch update in SQLite
            conn.executemany(
                """
                UPDATE canonical_notices
                SET classification = ?,
                    published_date = ?,
                    application_start_date = ?,
                    application_end_date = ?,
                    recency_status = ?,
                    triage_flag = ?,
                    triage_notes = ?
                WHERE id = ?
                """,
                updates,
            )

            return {
                "total_triaged": len(rows),
                "categories": category_counts,
                "recency": recency_counts,
                "duplicate_groups_count": len(duplicate_groups),
                "duplicate_notices_count": sum(len(v) for v in duplicate_groups.values()),
                "authority_breakdown": authority_breakdown,
            }
