"""SQLite storage for monthly revenue snapshots."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, Optional

DEFAULT_DB_PATH = Path("data") / "revinv.sqlite3"

_COLUMNS = [
    "company_id",
    "company_name",
    "industry",
    "data_ym",
    "revenue",
    "revenue_prev_month",
    "revenue_prev_year_month",
    "mom_pct",
    "yoy_pct",
    "cumulative_revenue",
    "cumulative_revenue_prev_year",
    "cumulative_yoy_pct",
    "remark",
    "report_date",
]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS monthly_revenue (
    company_id TEXT NOT NULL,
    company_name TEXT,
    industry TEXT,
    data_ym TEXT NOT NULL,
    revenue REAL,
    revenue_prev_month REAL,
    revenue_prev_year_month REAL,
    mom_pct REAL,
    yoy_pct REAL,
    cumulative_revenue REAL,
    cumulative_revenue_prev_year REAL,
    cumulative_yoy_pct REAL,
    remark TEXT,
    report_date TEXT,
    PRIMARY KEY (company_id, data_ym)
);
"""


def connect(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(_SCHEMA)
    return conn


def upsert_monthly_revenue(conn: sqlite3.Connection, records: Iterable[dict]) -> int:
    """Insert or update monthly revenue records, keyed on (company_id, data_ym)."""
    placeholders = ", ".join("?" for _ in _COLUMNS)
    column_list = ", ".join(_COLUMNS)
    update_clause = ", ".join(
        f"{c}=excluded.{c}" for c in _COLUMNS if c not in ("company_id", "data_ym")
    )
    sql = (
        f"INSERT INTO monthly_revenue ({column_list}) VALUES ({placeholders}) "
        f"ON CONFLICT(company_id, data_ym) DO UPDATE SET {update_clause}"
    )
    rows = [tuple(r.get(c) for c in _COLUMNS) for r in records]
    with conn:
        conn.executemany(sql, rows)
    return len(rows)


def fetch_latest_ym(conn: sqlite3.Connection) -> Optional[str]:
    row = conn.execute("SELECT MAX(data_ym) FROM monthly_revenue").fetchone()
    return row[0] if row else None


def load_snapshot(conn: sqlite3.Connection, data_ym: str) -> list[dict]:
    conn.row_factory = sqlite3.Row
    cur = conn.execute("SELECT * FROM monthly_revenue WHERE data_ym = ?", (data_ym,))
    return [dict(row) for row in cur.fetchall()]
