"""Database connection and lifecycle management for Testkart Intelligence."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional
from testkart_intelligence.config import settings


SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Create a configured sqlite3 connection with WAL mode and foreign keys enabled."""
    target_path = db_path or settings.DATABASE_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        str(target_path),
        timeout=30.0,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 10000;")
    return conn


@contextmanager
def get_db(db_path: Optional[Path] = None) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for managing transactions with automatic commit/rollback."""
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Optional[Path] = None) -> None:
    """Initialize database tables and indexes from schema.sql."""
    with get_db(db_path) as conn:
        # Migration: Ensure canonical_notices has triage & recency columns if table was created earlier
        try:
            existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(canonical_notices)").fetchall()}
            if existing_cols:
                migrations = [
                    ("published_date", "TEXT"),
                    ("application_start_date", "TEXT"),
                    ("application_end_date", "TEXT"),
                    ("recency_status", "TEXT NOT NULL DEFAULT 'UNKNOWN'"),
                    ("triage_flag", "TEXT NOT NULL DEFAULT 'NONE'"),
                    ("triage_notes", "TEXT"),
                ]
                for col_name, col_type in migrations:
                    if col_name not in existing_cols:
                        conn.execute(f"ALTER TABLE canonical_notices ADD COLUMN {col_name} {col_type};")

            # Migration: Ensure extracted_facts has editorial correction & confirmation columns
            existing_fact_cols = {row["name"] for row in conn.execute("PRAGMA table_info(extracted_facts)").fetchall()}
            if existing_fact_cols:
                fact_migrations = [
                    ("corrected_value", "TEXT"),
                    ("corrected_by", "TEXT"),
                    ("correction_reason", "TEXT"),
                    ("corrected_at", "TEXT"),
                    ("is_confirmed", "INTEGER NOT NULL DEFAULT 0"),
                    ("confirmed_by", "TEXT"),
                    ("confirmed_at", "TEXT"),
                ]
                for col_name, col_type in fact_migrations:
                    if col_name not in existing_fact_cols:
                        conn.execute(f"ALTER TABLE extracted_facts ADD COLUMN {col_name} {col_type};")
        except Exception:
            pass

        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            schema_sql = f.read()
        conn.executescript(schema_sql)
