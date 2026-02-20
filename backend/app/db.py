from __future__ import annotations

import sqlite3
from pathlib import Path


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with get_connection(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id TEXT PRIMARY KEY,
                date TEXT NOT NULL,
                amount TEXT NOT NULL,
                description TEXT NOT NULL,
                merchant TEXT NOT NULL,
                method TEXT NOT NULL,
                direction TEXT,
                raw_category TEXT,
                memo TEXT,
                is_excluded INTEGER NOT NULL DEFAULT 0,
                import_fingerprint TEXT
            )
            """
        )
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(transactions)").fetchall()
        }
        if "is_excluded" not in columns:
            conn.execute(
                """
                ALTER TABLE transactions
                ADD COLUMN is_excluded INTEGER NOT NULL DEFAULT 0
                """
            )
        if "import_fingerprint" not in columns:
            conn.execute(
                """
                ALTER TABLE transactions
                ADD COLUMN import_fingerprint TEXT
                """
            )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS classifications (
                transaction_id TEXT PRIMARY KEY,
                direction TEXT NOT NULL,
                expense_kind TEXT NOT NULL,
                category TEXT,
                confidence REAL NOT NULL,
                rules_fired TEXT NOT NULL,
                FOREIGN KEY(transaction_id) REFERENCES transactions(id)
            )
            """
        )
