#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import sqlite3
import uuid
from pathlib import Path

TYPE_TO_DIRECTION = {
    "수입": "income",
    "지출": "expense",
    "이체": "transfer",
}


def build_raw_category(main: str, sub: str) -> str:
    main_clean = (main or "").strip()
    sub_clean = (sub or "").strip()
    if not main_clean or not sub_clean:
        return ""
    return f"{main_clean}>{sub_clean}"


def import_tsv_to_db(tsv_path: Path, db_path: Path) -> int:
    if not tsv_path.exists():
        raise FileNotFoundError(f"Input TSV not found: {tsv_path}")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))

    try:
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
                memo TEXT
            )
            """
        )

        conn.execute("DELETE FROM transactions")

        inserted = 0
        with tsv_path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file, delimiter="\t")
            for row in reader:
                description = (row.get("내용") or "").strip()
                direction = TYPE_TO_DIRECTION.get((row.get("타입") or "").strip(), "transfer")

                conn.execute(
                    """
                    INSERT INTO transactions (
                        id, date, amount, description, merchant, method,
                        direction, raw_category, memo
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        (row.get("날짜") or "").strip(),
                        (row.get("금액") or "").strip(),
                        description,
                        description,
                        (row.get("결제수단") or "").strip(),
                        direction,
                        build_raw_category(row.get("대분류") or "", row.get("소분류") or ""),
                        (row.get("메모") or "").strip(),
                    ),
                )
                inserted += 1

        conn.commit()
        return inserted
    finally:
        conn.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import Bankpoke TSV into backend SQLite DB")
    parser.add_argument("--in", dest="input_path", required=True, help="Input TSV path")
    parser.add_argument("--db", dest="db_path", required=True, help="Target SQLite DB path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    inserted = import_tsv_to_db(Path(args.input_path), Path(args.db_path))
    print(f"Imported {inserted} rows into {args.db_path}")


if __name__ == "__main__":
    main()
