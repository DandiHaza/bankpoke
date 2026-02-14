from __future__ import annotations

import csv
import hashlib
import io
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable


DATE_FMT = "%Y-%m-%d %H:%M"

TYPE_MAP = {
    "수입": "income",
    "지출": "expense",
    "이체": "transfer",
}


@dataclass
class ImportResult:
    imported: int
    skipped_duplicates: int
    review_required: int


class LedgerService:
    """MVP ledger backend with SQLite storage."""

    def __init__(self, db_path: str = "bankpoke.db") -> None:
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def close(self) -> None:
        self.conn.close()

    def init_db(self) -> None:
        cur = self.conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                occurred_at TEXT NOT NULL,
                type TEXT NOT NULL CHECK (type IN ('income','expense','transfer')),
                amount INTEGER NOT NULL,
                signed_amount INTEGER NOT NULL,
                currency TEXT NOT NULL DEFAULT 'KRW',
                major_category TEXT,
                minor_category TEXT,
                content TEXT,
                payment_method TEXT,
                note TEXT,
                row_hash TEXT NOT NULL UNIQUE,
                transfer_group_id TEXT,
                transfer_external INTEGER NOT NULL DEFAULT 0,
                review_required INTEGER NOT NULL DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_transactions_occurred_at ON transactions (occurred_at);
            CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions (type);
            CREATE INDEX IF NOT EXISTS idx_transactions_transfer_group_id ON transactions (transfer_group_id);
            """
        )
        self.conn.commit()

    def import_tsv(self, raw_text: str) -> ImportResult:
        reader = csv.DictReader(io.StringIO(raw_text), delimiter="\t")
        imported = 0
        skipped_duplicates = 0
        review_required = 0

        for row in reader:
            normalized = self._normalize_row(row)
            if normalized is None:
                continue

            try:
                self.conn.execute(
                    """
                    INSERT INTO transactions (
                        occurred_at, type, amount, signed_amount, currency,
                        major_category, minor_category, content, payment_method, note,
                        row_hash, transfer_external, review_required
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        normalized["occurred_at"],
                        normalized["type"],
                        normalized["amount"],
                        normalized["signed_amount"],
                        normalized["currency"],
                        normalized["major_category"],
                        normalized["minor_category"],
                        normalized["content"],
                        normalized["payment_method"],
                        normalized["note"],
                        normalized["row_hash"],
                        normalized["transfer_external"],
                        normalized["review_required"],
                    ),
                )
                imported += 1
                if normalized["review_required"]:
                    review_required += 1
            except sqlite3.IntegrityError:
                skipped_duplicates += 1

        self.conn.commit()
        self._pair_internal_transfers()
        return ImportResult(imported, skipped_duplicates, review_required)

    def monthly_summary(self, year: int, month: int) -> dict[str, int]:
        start = datetime(year, month, 1)
        end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)

        cur = self.conn.execute(
            """
            SELECT type, signed_amount, transfer_group_id
            FROM transactions
            WHERE occurred_at >= ? AND occurred_at < ?
            """,
            (start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S")),
        )

        income = 0
        expense = 0
        transfer = 0
        for row in cur.fetchall():
            tx_type = row["type"]
            signed = int(row["signed_amount"])
            if tx_type == "income":
                income += max(0, signed)
            elif tx_type == "expense":
                expense += abs(min(0, signed))
            else:
                if row["transfer_group_id"] is None:
                    transfer += abs(signed)

        return {
            "income": income,
            "expense": expense,
            "transfer_unmatched": transfer,
            "net_cashflow": income - expense,
        }

    def unmatched_transfers(self) -> list[sqlite3.Row]:
        cur = self.conn.execute(
            """
            SELECT *
            FROM transactions
            WHERE type = 'transfer' AND transfer_group_id IS NULL
            ORDER BY occurred_at ASC
            """
        )
        return cur.fetchall()

    def _normalize_row(self, row: dict[str, str]) -> dict[str, object] | None:
        date_s = (row.get("날짜") or "").strip()
        time_s = (row.get("시간") or "00:00").strip()
        if not date_s:
            return None

        occurred = datetime.strptime(f"{date_s} {time_s}", DATE_FMT)
        raw_type = (row.get("타입") or "").strip()
        tx_type = TYPE_MAP.get(raw_type, "transfer")

        signed_amount = int(str(row.get("금액", "0")).replace(",", "").strip() or "0")
        amount = abs(signed_amount)
        currency = (row.get("화폐") or "KRW").strip() or "KRW"

        content = self._none_if_blank(row.get("내용"))
        payment_method = self._none_if_blank(row.get("결제수단"))
        major_category = self._none_if_blank(row.get("대분류"))
        minor_category = self._none_if_blank(row.get("소분류"))
        note = self._none_if_blank(row.get("메모"))

        review_required = 0
        if tx_type == "expense" and signed_amount > 0:
            review_required = 1
        elif tx_type == "income" and signed_amount < 0:
            review_required = 1

        transfer_external = 1 if tx_type == "transfer" and not self._is_internal_transfer(content) else 0

        hash_input = "|".join(
            [date_s, time_s, raw_type, str(signed_amount), currency, payment_method or "", content or ""]
        )
        row_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

        return {
            "occurred_at": occurred.strftime("%Y-%m-%d %H:%M:%S"),
            "type": tx_type,
            "amount": amount,
            "signed_amount": signed_amount,
            "currency": currency,
            "major_category": major_category,
            "minor_category": minor_category,
            "content": content,
            "payment_method": payment_method,
            "note": note,
            "row_hash": row_hash,
            "transfer_external": transfer_external,
            "review_required": review_required,
        }

    @staticmethod
    def _none_if_blank(value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned if cleaned else None

    @staticmethod
    def _is_internal_transfer(content: str | None) -> bool:
        if content is None:
            return False
        keywords = ["세이프박스", "내계좌로 이체", "동전 모으기", "저금통", "카드잔액 자동충전"]
        return any(k in content for k in keywords)

    def _pair_internal_transfers(self) -> None:
        cur = self.conn.execute(
            """
            SELECT id, occurred_at, signed_amount, currency, content
            FROM transactions
            WHERE type = 'transfer' AND transfer_group_id IS NULL
            ORDER BY occurred_at ASC
            """
        )
        candidates = [dict(row) for row in cur.fetchall()]

        used: set[int] = set()
        for left in candidates:
            if left["id"] in used:
                continue
            if not self._is_internal_transfer(left.get("content")):
                continue
            left_dt = datetime.strptime(left["occurred_at"], "%Y-%m-%d %H:%M:%S")
            for right in candidates:
                if right["id"] in used or right["id"] == left["id"]:
                    continue
                if right["currency"] != left["currency"]:
                    continue
                if right["signed_amount"] != -left["signed_amount"]:
                    continue

                right_dt = datetime.strptime(right["occurred_at"], "%Y-%m-%d %H:%M:%S")
                if abs(right_dt - left_dt) > timedelta(minutes=5):
                    continue

                group_id = hashlib.md5(f"{left['id']}:{right['id']}".encode("utf-8")).hexdigest()
                self.conn.execute(
                    "UPDATE transactions SET transfer_group_id = ?, review_required = 0 WHERE id IN (?, ?)",
                    (group_id, left["id"], right["id"]),
                )
                used.add(left["id"])
                used.add(right["id"])
                break

        self.conn.commit()


def load_file_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()
