from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = Path(__file__).with_name("hotmail_accounts.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE,
    password TEXT,
    firstname TEXT,
    lastname TEXT,
    birthdate TEXT,
    created_time TEXT,
    status TEXT DEFAULT 'created',
    last_activity_at TEXT,
    proxy TEXT,
    warmup_note TEXT
);
"""


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(SCHEMA)
        conn.commit()


def upsert_account(account: Dict[str, Any]) -> None:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO accounts (email, password, firstname, lastname, birthdate, created_time)
            VALUES (:email, :password, :firstname, :lastname, :birthdate, :created_time)
            ON CONFLICT(email) DO UPDATE SET
                password=excluded.password,
                firstname=excluded.firstname,
                lastname=excluded.lastname,
                birthdate=excluded.birthdate,
                created_time=excluded.created_time,
                status='created'
            """,
            account,
        )
        conn.commit()


def fetch_pending_accounts(limit: Optional[int] = 3, status_filter: Optional[str] = "created") -> List[Dict[str, Any]]:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        query = "SELECT * FROM accounts"
        params: list[Any] = []
        if status_filter and status_filter.lower() != "all":
            query += " WHERE status=?"
            params.append(status_filter)
        query += " ORDER BY created_time DESC"
        if limit is not None and limit > 0:
            query += " LIMIT ?"
            params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def fetch_all_emails(status_filter: Optional[str] = None) -> List[str]:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        query = "SELECT email FROM accounts"
        params: list[Any] = []
        if status_filter and status_filter.lower() != "all":
            query += " WHERE status=?"
            params.append(status_filter)
        query += " ORDER BY created_time DESC"
        rows = conn.execute(query, params).fetchall()
        return [row[0] for row in rows if row[0]]


def update_warmup_status(
    email: str,
    *,
    status: str,
    proxy: Optional[str] = None,
    note: Optional[str] = None,
    last_activity_at: Optional[str] = None,
) -> None:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            UPDATE accounts
            SET status=?, proxy=COALESCE(?, proxy), warmup_note=COALESCE(?, warmup_note), last_activity_at=COALESCE(?, last_activity_at)
            WHERE email=?
            """,
            (status, proxy, note, last_activity_at, email),
        )
        conn.commit()
