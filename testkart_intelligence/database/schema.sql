-- Testkart Intelligence SQLite Database Schema
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- 1. Official Sources Registry
CREATE TABLE IF NOT EXISTS official_sources (
    id TEXT PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    state TEXT NOT NULL,
    official_domain TEXT NOT NULL,
    listing_url TEXT NOT NULL,
    retrieval_method TEXT NOT NULL DEFAULT 'html_scrape',
    verification_status TEXT NOT NULL DEFAULT 'VERIFIED',
    enabled INTEGER NOT NULL DEFAULT 1,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    last_checked_at TEXT,
    last_success_at TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sources_domain ON official_sources(official_domain);
CREATE INDEX IF NOT EXISTS idx_sources_enabled ON official_sources(enabled);
CREATE INDEX IF NOT EXISTS idx_sources_category ON official_sources(category);

-- 2. Scan Runs History
CREATE TABLE IF NOT EXISTS scan_runs (
    id TEXT PRIMARY KEY,
    scan_type TEXT NOT NULL, -- 'SCHEDULED' | 'MANUAL'
    status TEXT NOT NULL,    -- 'RUNNING' | 'COMPLETED' | 'FAILED'
    started_at TEXT NOT NULL,
    completed_at TEXT,
    sources_checked INTEGER NOT NULL DEFAULT 0,
    notices_found INTEGER NOT NULL DEFAULT 0,
    errors_count INTEGER NOT NULL DEFAULT 0,
    error_summary TEXT
);

CREATE INDEX IF NOT EXISTS idx_scan_runs_status ON scan_runs(status);
CREATE INDEX IF NOT EXISTS idx_scan_runs_started ON scan_runs(started_at);

-- 3. Source Level Scan Execution Logs
CREATE TABLE IF NOT EXISTS scan_source_logs (
    id TEXT PRIMARY KEY,
    scan_run_id TEXT NOT NULL REFERENCES scan_runs(id) ON DELETE CASCADE,
    source_id TEXT NOT NULL REFERENCES official_sources(id),
    status TEXT NOT NULL, -- 'SUCCESS_NEW' | 'SUCCESS_NO_NEW' | 'FAILED'
    notices_found_count INTEGER NOT NULL DEFAULT 0,
    response_time_ms INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    checked_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_scan_source_logs_run ON scan_source_logs(scan_run_id);
CREATE INDEX IF NOT EXISTS idx_scan_source_logs_source ON scan_source_logs(source_id);

-- 4. Canonical Notices
CREATE TABLE IF NOT EXISTS canonical_notices (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES official_sources(id),
    authority_name TEXT NOT NULL,
    notice_number TEXT,
    title TEXT NOT NULL,
    normalized_url TEXT NOT NULL,
    category TEXT NOT NULL,
    state TEXT NOT NULL,
    classification TEXT NOT NULL DEFAULT 'OTHER_ANNOUNCEMENT',
    status TEXT NOT NULL DEFAULT 'DISCOVERED',
    published_date TEXT,
    application_start_date TEXT,
    application_end_date TEXT,
    recency_status TEXT NOT NULL DEFAULT 'UNKNOWN',
    triage_flag TEXT NOT NULL DEFAULT 'NONE',
    triage_notes TEXT,
    parent_notice_id TEXT REFERENCES canonical_notices(id),
    relation_type TEXT,
    relation_confidence REAL,
    first_discovered_at TEXT NOT NULL,
    last_updated_at TEXT NOT NULL,
    UNIQUE(source_id, normalized_url)
);

CREATE INDEX IF NOT EXISTS idx_notices_source ON canonical_notices(source_id);
CREATE INDEX IF NOT EXISTS idx_notices_status ON canonical_notices(status);
CREATE INDEX IF NOT EXISTS idx_notices_classification ON canonical_notices(classification);
CREATE INDEX IF NOT EXISTS idx_notices_norm_url ON canonical_notices(normalized_url);
CREATE INDEX IF NOT EXISTS idx_notices_recency ON canonical_notices(recency_status);
CREATE INDEX IF NOT EXISTS idx_notices_triage_flag ON canonical_notices(triage_flag);

-- 5. Notice Versions (Immutable Document & Version Tracking)
CREATE TABLE IF NOT EXISTS notice_versions (
    id TEXT PRIMARY KEY,
    notice_id TEXT NOT NULL REFERENCES canonical_notices(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    document_url TEXT NOT NULL,
    document_hash TEXT NOT NULL,
    document_type TEXT NOT NULL, -- 'PDF' | 'HTML'
    storage_path TEXT NOT NULL,
    raw_text TEXT,
    page_count INTEGER DEFAULT 1,
    retrieved_at TEXT NOT NULL,
    UNIQUE(notice_id, version_number),
    UNIQUE(notice_id, document_hash)
);

CREATE INDEX IF NOT EXISTS idx_notice_versions_hash ON notice_versions(document_hash);

-- 6. Extracted Facts & Traceable Evidence
CREATE TABLE IF NOT EXISTS extracted_facts (
    id TEXT PRIMARY KEY,
    notice_version_id TEXT NOT NULL REFERENCES notice_versions(id) ON DELETE CASCADE,
    fact_key TEXT NOT NULL,
    fact_value TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 1.0,
    evidence_text TEXT,
    page_number INTEGER DEFAULT 1,
    verified_status TEXT NOT NULL DEFAULT 'VERIFIED', -- 'VERIFIED' | 'UNVERIFIED' | 'CONTRADICTORY' | 'MISSING'
    verification_notes TEXT,
    corrected_value TEXT,
    corrected_by TEXT,
    correction_reason TEXT,
    corrected_at TEXT,
    is_confirmed INTEGER NOT NULL DEFAULT 0,
    confirmed_by TEXT,
    confirmed_at TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_extracted_facts_version ON extracted_facts(notice_version_id);
CREATE INDEX IF NOT EXISTS idx_extracted_facts_key ON extracted_facts(fact_key);
CREATE INDEX IF NOT EXISTS idx_extracted_facts_confirmed ON extracted_facts(is_confirmed);

-- 6b. Editorial Fact Corrections History Log
CREATE TABLE IF NOT EXISTS fact_corrections_log (
    id TEXT PRIMARY KEY,
    fact_id TEXT NOT NULL REFERENCES extracted_facts(id) ON DELETE CASCADE,
    notice_version_id TEXT NOT NULL,
    fact_key TEXT NOT NULL,
    original_value TEXT NOT NULL,
    corrected_value TEXT NOT NULL,
    reviewer_email TEXT NOT NULL,
    correction_reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fact_corrections_fact ON fact_corrections_log(fact_id);

-- 7. Blog Articles
CREATE TABLE IF NOT EXISTS blog_articles (
    id TEXT PRIMARY KEY,
    canonical_notice_id TEXT NOT NULL REFERENCES canonical_notices(id) ON DELETE CASCADE,
    template_type TEXT NOT NULL,
    current_version_id TEXT,
    status TEXT NOT NULL DEFAULT 'DRAFT', -- 'DRAFT' | 'QA_PASSED' | 'QA_FAILED' | 'PENDING_APPROVAL' | 'APPROVED' | 'REJECTED'
    title TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_articles_status ON blog_articles(status);
CREATE INDEX IF NOT EXISTS idx_articles_notice ON blog_articles(canonical_notice_id);

-- 8. Article Versions (Immutable Content Hash Versions)
CREATE TABLE IF NOT EXISTS article_versions (
    id TEXT PRIMARY KEY,
    article_id TEXT NOT NULL REFERENCES blog_articles(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    content_markdown TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    title TEXT NOT NULL,
    meta_description TEXT,
    keywords TEXT,
    generated_by TEXT NOT NULL DEFAULT 'agent_writer',
    created_at TEXT NOT NULL,
    UNIQUE(article_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_article_versions_hash ON article_versions(content_hash);

-- 9. QA Check Results
CREATE TABLE IF NOT EXISTS qa_results (
    id TEXT PRIMARY KEY,
    article_version_id TEXT NOT NULL REFERENCES article_versions(id) ON DELETE CASCADE,
    passed INTEGER NOT NULL,
    score REAL NOT NULL,
    rule_name TEXT NOT NULL,
    severity TEXT NOT NULL, -- 'ERROR' | 'WARNING' | 'INFO'
    message TEXT NOT NULL,
    details_json TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_qa_results_version ON qa_results(article_version_id);

-- 10. Future Approval Records (Token Bound & Replay Protected)
CREATE TABLE IF NOT EXISTS approval_records (
    id TEXT PRIMARY KEY,
    article_version_id TEXT NOT NULL REFERENCES article_versions(id) ON DELETE CASCADE,
    content_hash TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    reviewer_email TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING', -- 'PENDING' | 'APPROVED' | 'REJECTED' | 'EXPIRED' | 'INVALIDATED'
    expires_at TEXT NOT NULL,
    decided_at TEXT,
    decision_notes TEXT,
    is_override INTEGER NOT NULL DEFAULT 0,
    override_reason TEXT,
    unverified_fields_waived TEXT,
    client_ip TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_approval_token_hash ON approval_records(token_hash);
CREATE INDEX IF NOT EXISTS idx_approval_version ON approval_records(article_version_id);

-- 11. Publishing Jobs (Live Publishing Guarded)
CREATE TABLE IF NOT EXISTS publishing_jobs (
    id TEXT PRIMARY KEY,
    article_version_id TEXT NOT NULL REFERENCES article_versions(id) ON DELETE CASCADE,
    approval_record_id TEXT REFERENCES approval_records(id),
    publisher_name TEXT NOT NULL DEFAULT 'mock_publisher',
    is_mock INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'PENDING', -- 'PENDING' | 'COMPLETED' | 'FAILED' | 'BLOCKED'
    attempt_count INTEGER NOT NULL DEFAULT 0,
    published_url TEXT,
    response_payload TEXT,
    created_at TEXT NOT NULL,
    executed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_pub_jobs_status ON publishing_jobs(status);

-- 12. Audit Events
CREATE TABLE IF NOT EXISTS audit_events (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    action TEXT NOT NULL,
    actor TEXT NOT NULL,
    payload_json TEXT,
    timestamp TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_events(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_events(timestamp);
