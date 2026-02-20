from __future__ import annotations

import csv
from contextlib import asynccontextmanager
from decimal import Decimal, InvalidOperation
import hashlib
import io
import uuid
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .db import get_connection, init_db


DB_PATH = "backend/data/app.db"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db(DB_PATH)
    yield


app = FastAPI(title="Bankpoke TOSS Alternative MVP API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class MonthlySummary(BaseModel):
    year: int
    month: int
    income: int
    expense: int
    net_cashflow: int
    transaction_count: int


class CategoryBreakdownItem(BaseModel):
    category: str
    amount: int


class CategoryMonthlyTrendRow(BaseModel):
    month: int
    values: dict[str, int]


class CategoryMonthlyTrendResponse(BaseModel):
    year: int
    categories: list[str]
    rows: list[CategoryMonthlyTrendRow]


class ExpenseTransactionItem(BaseModel):
    id: str
    date: str
    category: str
    description: str
    amount: int
    method: str
    excluded: bool


class ExpenseCategoryTransactions(BaseModel):
    category: str
    total_amount: int
    count: int
    items: list[ExpenseTransactionItem]


class ExpenseTransactionUpdateRequest(BaseModel):
    date: str | None = None
    category: str | None = None
    description: str | None = None
    amount: int | None = None
    method: str | None = None
    excluded: bool | None = None


class ExpenseTransactionMatchRequest(BaseModel):
    date: str
    category: str
    description: str
    amount: int
    method: str
    excluded: bool = False


class ExpenseTransactionUpdateByMatchRequest(BaseModel):
    original: ExpenseTransactionMatchRequest
    updated: ExpenseTransactionUpdateRequest


class IncomeTransactionItem(BaseModel):
    id: str
    date: str
    category: str
    description: str
    amount: int
    method: str
    excluded: bool


class IncomeCategoryTransactions(BaseModel):
    category: str
    total_amount: int
    count: int
    items: list[IncomeTransactionItem]


class IncomeTransactionUpdateRequest(BaseModel):
    date: str | None = None
    category: str | None = None
    description: str | None = None
    amount: int | None = None
    method: str | None = None
    excluded: bool | None = None


class IncomeTransactionMatchRequest(BaseModel):
    date: str
    category: str
    description: str
    amount: int
    method: str
    excluded: bool = False


class IncomeTransactionUpdateByMatchRequest(BaseModel):
    original: IncomeTransactionMatchRequest
    updated: IncomeTransactionUpdateRequest


class CreateTransactionRequest(BaseModel):
    date: str
    direction: Literal["income", "expense"]
    category: str
    description: str
    amount: int
    method: str = ""
    memo: str = ""
    excluded: bool = False


TYPE_TO_DIRECTION = {
    "수입": "income",
    "지출": "expense",
}


def _parse_amount_to_abs_int(value: object) -> int | None:
    try:
        return abs(int(Decimal(str(value))))
    except (InvalidOperation, ValueError):
        return None


def _parse_amount_to_signed_int(value: object) -> int | None:
    try:
        return int(Decimal(str(value)))
    except (InvalidOperation, ValueError):
        return None


def _month_prefix(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def _major_category(raw_category: str) -> str:
    major, *_ = raw_category.split(">", 1)
    return major.strip() or "미분류"


def _normalize_cleaned_row(row: dict[str, str]) -> dict[str, str] | None:
    date = (row.get("date") or "").strip()
    if not date:
        return None

    amount = _parse_amount_to_signed_int(row.get("amount"))
    if amount is None:
        return None

    direction = (row.get("direction") or "").strip().lower()
    if direction not in {"income", "expense"}:
        direction = "income" if amount >= 0 else "expense"

    signed_amount = abs(amount) if direction == "income" else -abs(amount)
    description = (row.get("description") or "").strip()
    if not description:
        return None

    return {
        "id": (row.get("id") or "").strip() or str(uuid.uuid4()),
        "date": date,
        "amount": str(signed_amount),
        "description": description,
        "merchant": (row.get("merchant") or "").strip() or description,
        "method": (row.get("method") or "").strip(),
        "direction": direction,
        "raw_category": (row.get("raw_category") or "").strip() or "미분류",
        "memo": (row.get("memo") or "").strip(),
    }


def _normalize_tsv_row(row: dict[str, str]) -> dict[str, str] | None:
    date = (row.get("날짜") or "").strip()
    if not date:
        return None

    amount = _parse_amount_to_signed_int((row.get("금액") or "").replace(",", ""))
    if amount is None:
        return None

    tx_type = (row.get("타입") or "").strip()
    direction = TYPE_TO_DIRECTION.get(tx_type)
    if direction not in {"income", "expense"}:
        direction = "income" if amount >= 0 else "expense"

    signed_amount = abs(amount) if direction == "income" else -abs(amount)
    description = (row.get("내용") or "").strip()
    if not description:
        return None

    main_category = (row.get("대분류") or "").strip()
    sub_category = (row.get("소분류") or "").strip()
    raw_category = f"{main_category}>{sub_category}" if main_category and sub_category else "미분류"

    return {
        "id": str(uuid.uuid4()),
        "date": date,
        "amount": str(signed_amount),
        "description": description,
        "merchant": description,
        "method": (row.get("결제수단") or "").strip(),
        "direction": direction,
        "raw_category": raw_category,
        "memo": (row.get("메모") or "").strip(),
    }


def _decode_uploaded_text(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise HTTPException(status_code=400, detail="파일 인코딩을 읽을 수 없습니다. UTF-8/CP949 파일을 사용해 주세요.")


def _detect_delimiter(file_name: str, header_line: str) -> str:
    if file_name.lower().endswith(".tsv"):
        return "\t"
    if file_name.lower().endswith(".csv"):
        return ","
    return "\t" if header_line.count("\t") > header_line.count(",") else ","


def _transaction_dedup_key(row: dict[str, str]) -> tuple[str, str, str, str, str, str]:
    return (
        row["date"].strip(),
        row["amount"].strip(),
        row["description"].strip(),
        row["method"].strip(),
        row["direction"].strip(),
        row["raw_category"].strip(),
    )


def _transaction_fingerprint(row: dict[str, str]) -> str:
    key = "|".join(_transaction_dedup_key(row))
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _transaction_fallback_key_with_method(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        row["date"].strip(),
        row["amount"].strip(),
        row["direction"].strip(),
        row["method"].strip(),
    )


def _transaction_fallback_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        row["date"].strip(),
        row["amount"].strip(),
        row["direction"].strip(),
    )


def _transaction_fallback_key_without_amount(row: dict[str, str]) -> tuple[str, str, str, str]:
    """amount를 제외한 fallback key (수정된 거래 매칭용)"""
    return (
        row["date"].strip(),
        row["description"].strip(),
        row["direction"].strip(),
        row["method"].strip(),
    )


def _build_transaction_updates(
    payload: ExpenseTransactionUpdateRequest | IncomeTransactionUpdateRequest,
    direction: str,
) -> dict[str, str]:
    updates: dict[str, str] = {}

    if payload.date is not None:
        cleaned_date = payload.date.strip()
        if not cleaned_date:
            raise HTTPException(status_code=400, detail="date cannot be blank")
        updates["date"] = cleaned_date

    if payload.category is not None:
        cleaned_category = payload.category.strip()
        updates["raw_category"] = cleaned_category or "미분류"

    if payload.description is not None:
        updates["description"] = payload.description.strip()
        updates["merchant"] = payload.description.strip()

    if payload.method is not None:
        updates["method"] = payload.method.strip()

    if payload.amount is not None:
        if payload.amount <= 0:
            raise HTTPException(status_code=400, detail="amount must be greater than 0")
        signed_amount = -abs(payload.amount) if direction == "expense" else abs(payload.amount)
        updates["amount"] = str(signed_amount)

    if payload.excluded is not None:
        updates["is_excluded"] = "1" if payload.excluded else "0"

    return updates


def _apply_transaction_update(transaction_id: str, updates: dict[str, str], direction: str) -> int:
    set_clause = ", ".join(f"{column} = ?" for column in updates)
    values = list(updates.values())
    values.append(transaction_id)

    with get_connection(DB_PATH) as conn:
        cursor = conn.execute(
            f"""
            UPDATE transactions
            SET {set_clause}
            WHERE id = ? AND direction = ?
            """,
            [*values, direction],
        )
        conn.commit()

    return cursor.rowcount


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/transactions")
def create_transaction(payload: CreateTransactionRequest) -> dict[str, str]:
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="amount must be greater than 0")

    cleaned_date = payload.date.strip()
    if not cleaned_date:
        raise HTTPException(status_code=400, detail="date cannot be blank")

    cleaned_category = payload.category.strip() or "미분류"
    cleaned_description = payload.description.strip()
    if not cleaned_description:
        raise HTTPException(status_code=400, detail="description cannot be blank")

    signed_amount = abs(payload.amount) if payload.direction == "income" else -abs(payload.amount)

    transaction_id = str(uuid.uuid4())
    with get_connection(DB_PATH) as conn:
        fingerprint = _transaction_fingerprint(
            {
                "date": cleaned_date,
                "amount": str(signed_amount),
                "description": cleaned_description,
                "method": payload.method.strip(),
                "direction": payload.direction,
                "raw_category": cleaned_category,
            }
        )
        conn.execute(
            """
            INSERT INTO transactions (
                id, date, amount, description, merchant, method,
                direction, raw_category, memo, is_excluded, import_fingerprint
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                transaction_id,
                cleaned_date,
                str(signed_amount),
                cleaned_description,
                cleaned_description,
                payload.method.strip(),
                payload.direction,
                cleaned_category,
                payload.memo.strip(),
                1 if payload.excluded else 0,
                fingerprint,
            ),
        )
        conn.commit()

    return {"status": "ok", "id": transaction_id}


@app.post("/api/transactions/import")
async def import_transactions(
    file: UploadFile = File(...),
    replace_month: bool = Form(False),
    year: int | None = Form(None),
    month: int | None = Form(None),
) -> dict[str, int | str]:
    AUTO_EXCLUDED_CATEGORIES = {"이체", "내부이체", "transfer", "internal transfer"}

    if not file.filename:
        raise HTTPException(status_code=400, detail="파일명이 필요합니다.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="비어 있는 파일입니다.")

    text = _decode_uploaded_text(content)
    header_line = text.splitlines()[0] if text.splitlines() else ""
    delimiter = _detect_delimiter(file.filename, header_line)

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    fieldnames = set(reader.fieldnames or [])
    is_cleaned_schema = {"date", "amount", "description"}.issubset(fieldnames)
    is_raw_tsv_schema = {"날짜", "금액", "내용"}.issubset(fieldnames)

    if not is_cleaned_schema and not is_raw_tsv_schema:
        raise HTTPException(
            status_code=400,
            detail="지원하지 않는 헤더 형식입니다. cleaned CSV 또는 가계부 TSV를 업로드해 주세요.",
        )

    normalized_rows: list[dict[str, str]] = []
    for row in reader:
        normalized = _normalize_cleaned_row(row) if is_cleaned_schema else _normalize_tsv_row(row)
        if normalized is not None:
            normalized_rows.append(normalized)

    if not normalized_rows:
        raise HTTPException(status_code=400, detail="가져올 수 있는 거래가 없습니다.")

    deleted = 0
    if replace_month:
        target_year = year
        target_month = month

        if target_year is None or target_month is None:
            month_keys = {row["date"][:7] for row in normalized_rows if len(row["date"]) >= 7}
            if len(month_keys) != 1:
                raise HTTPException(
                    status_code=400,
                    detail="여러 월 데이터가 포함되어 있어 교체할 월을 지정해야 합니다.",
                )

            key = next(iter(month_keys))
            target_year = int(key[:4])
            target_month = int(key[5:7])

        if target_year < 2000 or target_year > 2100 or target_month < 1 or target_month > 12:
            raise HTTPException(status_code=400, detail="year/month 값이 올바르지 않습니다.")

        prefix = _month_prefix(target_year, target_month)
        with get_connection(DB_PATH) as conn:
            cursor = conn.execute(
                "DELETE FROM transactions WHERE date LIKE ?",
                (f"{prefix}%",),
            )
            conn.commit()
            deleted = cursor.rowcount

    skipped_duplicates = 0

    with get_connection(DB_PATH) as conn:
        existing_rows = conn.execute(
            """
            SELECT id, date, amount, description, method, direction, raw_category, import_fingerprint
            FROM transactions
            """
        ).fetchall()
        seen_fingerprints = {
            str(existing_row["import_fingerprint"]).strip()
            for existing_row in existing_rows
            if existing_row["import_fingerprint"] is not None and str(existing_row["import_fingerprint"]).strip()
        }

        fallback_with_method_map: dict[tuple[str, str, str, str], list[str]] = {}
        fallback_map: dict[tuple[str, str, str], list[str]] = {}
        fallback_without_amount_map: dict[tuple[str, str, str, str], list[str]] = {}

        for existing_row in existing_rows:
            existing_model = {
                "date": str(existing_row["date"]),
                "amount": str(existing_row["amount"]),
                "description": str(existing_row["description"]),
                "method": str(existing_row["method"]),
                "direction": str(existing_row["direction"]),
                "raw_category": str(existing_row["raw_category"]),
            }
            row_id = str(existing_row["id"])
            key_with_method = _transaction_fallback_key_with_method(existing_model)
            key = _transaction_fallback_key(existing_model)
            key_without_amount = _transaction_fallback_key_without_amount(existing_model)
            fallback_with_method_map.setdefault(key_with_method, []).append(row_id)
            fallback_map.setdefault(key, []).append(row_id)
            fallback_without_amount_map.setdefault(key_without_amount, []).append(row_id)

        for row in normalized_rows:
            fingerprint = _transaction_fingerprint(row)
            if fingerprint in seen_fingerprints:
                skipped_duplicates += 1
                continue

            matched_existing_id: str | None = None
            key_with_method = _transaction_fallback_key_with_method(row)
            candidates_with_method = fallback_with_method_map.get(key_with_method, [])
            if len(candidates_with_method) == 1:
                matched_existing_id = candidates_with_method[0]
            else:
                key = _transaction_fallback_key(row)
                candidates = fallback_map.get(key, [])
                if len(candidates) == 1:
                    matched_existing_id = candidates[0]
                else:
                    # amount를 제외한 매칭 (수정된 거래용)
                    key_without_amount = _transaction_fallback_key_without_amount(row)
                    candidates_without_amount = fallback_without_amount_map.get(key_without_amount, [])
                    if len(candidates_without_amount) == 1:
                        matched_existing_id = candidates_without_amount[0]

            if matched_existing_id is not None:
                conn.execute(
                    """
                    UPDATE transactions
                    SET import_fingerprint = ?
                    WHERE id = ?
                    """,
                    (fingerprint, matched_existing_id),
                )
                seen_fingerprints.add(fingerprint)
                skipped_duplicates += 1
                continue

            is_excluded = 1 if row["raw_category"].strip() in AUTO_EXCLUDED_CATEGORIES else 0
            conn.execute(
                """
                INSERT INTO transactions (
                    id, date, amount, description, merchant, method,
                    direction, raw_category, memo, is_excluded, import_fingerprint
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    row["date"],
                    row["amount"],
                    row["description"],
                    row["merchant"],
                    row["method"],
                    row["direction"],
                    row["raw_category"],
                    row["memo"],
                    is_excluded,
                    fingerprint,
                ),
            )
            seen_fingerprints.add(fingerprint)
            key_with_method = _transaction_fallback_key_with_method(row)
            key = _transaction_fallback_key(row)
            key_without_amount = _transaction_fallback_key_without_amount(row)
            fallback_with_method_map.setdefault(key_with_method, []).append(row["id"])
            fallback_map.setdefault(key, []).append(row["id"])
            fallback_without_amount_map.setdefault(key_without_amount, []).append(row["id"])
        conn.commit()

    return {
        "status": "ok",
        "imported": len(normalized_rows) - skipped_duplicates,
        "skipped_duplicates": skipped_duplicates,
        "deleted": deleted,
    }


@app.get("/api/summary", response_model=MonthlySummary)
def summary(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
) -> MonthlySummary:

    prefix = _month_prefix(year, month)
    income = 0
    expense = 0
    transaction_count = 0

    with get_connection(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT amount, direction, is_excluded
            FROM transactions
            WHERE date LIKE ?
            """,
            (f"{prefix}%",),
        ).fetchall()

    for row in rows:
        amount = _parse_amount_to_abs_int(row["amount"])
        if amount is None:
            continue

        direction = (row["direction"] or "").strip().lower()
        is_excluded = bool(row["is_excluded"])

        transaction_count += 1
        if is_excluded and direction in ("income", "expense"):
            continue

        if direction == "income":
            income += amount
        elif direction == "expense":
            expense += amount

    return MonthlySummary(
        year=year,
        month=month,
        income=income,
        expense=expense,
        net_cashflow=income - expense,
        transaction_count=transaction_count,
    )


@app.get("/api/category-breakdown", response_model=list[CategoryBreakdownItem])
def category_breakdown(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
) -> list[CategoryBreakdownItem]:

    prefix = _month_prefix(year, month)
    totals: dict[str, int] = {}

    with get_connection(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT raw_category, amount
            FROM transactions
                        WHERE date LIKE ?
                            AND direction = 'expense'
                            AND COALESCE(is_excluded, 0) = 0
            """,
            (f"{prefix}%",),
        ).fetchall()

    for row in rows:
        category = (row["raw_category"] or "").strip() or "미분류"
        amount = _parse_amount_to_abs_int(row["amount"])
        if amount is None:
            continue

        totals[category] = totals.get(category, 0) + amount

    sorted_items = sorted(totals.items(), key=lambda item: item[1], reverse=True)
    return [CategoryBreakdownItem(category=category, amount=amount) for category, amount in sorted_items]


@app.get("/api/category-monthly-trend", response_model=CategoryMonthlyTrendResponse)
def category_monthly_trend(
    year: int = Query(..., ge=2000, le=2100),
    top: int = Query(5, ge=1, le=10),
    include_empty_months: bool = Query(False),
    group_level: str = Query("full", pattern="^(major|full)$"),
) -> CategoryMonthlyTrendResponse:

    prefix = f"{year:04d}-"
    totals_by_category: dict[str, int] = {}
    totals_by_month_category: dict[tuple[int, str], int] = {}

    with get_connection(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT date, raw_category, amount
            FROM transactions
                        WHERE date LIKE ?
                            AND direction = 'expense'
                            AND COALESCE(is_excluded, 0) = 0
            """,
            (f"{prefix}%",),
        ).fetchall()

    for row in rows:
        date_text = str(row["date"])
        raw_category = (row["raw_category"] or "").strip() or "미분류"
        category = _major_category(raw_category) if group_level == "major" else raw_category
        amount = _parse_amount_to_abs_int(row["amount"])
        if amount is None:
            continue

        try:
            month = int(date_text[5:7])
        except ValueError:
            continue

        totals_by_category[category] = totals_by_category.get(category, 0) + amount
        key = (month, category)
        totals_by_month_category[key] = totals_by_month_category.get(key, 0) + amount

    top_categories = [
        category
        for category, _amount in sorted(totals_by_category.items(), key=lambda item: item[1], reverse=True)[:top]
    ]

    trend_rows: list[CategoryMonthlyTrendRow] = []
    for month in range(1, 13):
        values = {category: totals_by_month_category.get((month, category), 0) for category in top_categories}
        if not include_empty_months and all(value == 0 for value in values.values()):
            continue
        trend_rows.append(CategoryMonthlyTrendRow(month=month, values=values))

    return CategoryMonthlyTrendResponse(year=year, categories=top_categories, rows=trend_rows)


@app.get("/api/expense-transactions", response_model=list[ExpenseCategoryTransactions])
def expense_transactions(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    group_level: str = Query("major", pattern="^(major|full)$"),
    include_excluded: bool = Query(False),
) -> list[ExpenseCategoryTransactions]:
    prefix = _month_prefix(year, month)

    grouped: dict[str, list[ExpenseTransactionItem]] = {}

    with get_connection(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT id, date, raw_category, description, amount, method, is_excluded
            FROM transactions
                        WHERE date LIKE ?
                            AND direction = 'expense'
                            AND (? = 1 OR COALESCE(is_excluded, 0) = 0)
            ORDER BY date DESC
            """,
                        (f"{prefix}%", 1 if include_excluded else 0),
        ).fetchall()

    for row in rows:
        raw_category = (row["raw_category"] or "").strip() or "미분류"
        category = _major_category(raw_category) if group_level == "major" else raw_category

        amount = _parse_amount_to_abs_int(row["amount"])
        if amount is None:
            continue

        item = ExpenseTransactionItem(
            id=str(row["id"]),
            date=str(row["date"]),
            category=raw_category,
            description=(row["description"] or "").strip(),
            amount=amount,
            method=(row["method"] or "").strip(),
            excluded=bool(row["is_excluded"]),
        )
        grouped.setdefault(category, []).append(item)

    response: list[ExpenseCategoryTransactions] = []
    for category, items in grouped.items():
        total_amount = sum(item.amount for item in items)
        response.append(
            ExpenseCategoryTransactions(
                category=category,
                total_amount=total_amount,
                count=len(items),
                items=items,
            )
        )

    response.sort(key=lambda entry: entry.total_amount, reverse=True)
    return response


@app.patch("/api/expense-transactions/{transaction_id}")
def update_expense_transaction(
    transaction_id: str,
    payload: ExpenseTransactionUpdateRequest,
) -> dict[str, str]:
    updates = _build_transaction_updates(payload, "expense")

    if not updates:
        raise HTTPException(status_code=400, detail="no fields to update")

    # 현재 거래 정보 조회 후 fingerprint 재계산 필요 여부 확인
    with get_connection(DB_PATH) as conn:
        row = conn.execute(
            "SELECT date, amount, description, method, raw_category FROM transactions WHERE id = ? AND direction = 'expense'",
            (transaction_id,),
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="expense transaction not found")

    # 수정된 필드들을 현재값과 병합
    updated_date = updates.get("date", str(row["date"]))
    updated_amount = updates.get("amount", str(row["amount"]))
    updated_description = updates.get("description", str(row["description"]))
    updated_method = updates.get("method", str(row["method"]))
    updated_category = updates.get("raw_category", str(row["raw_category"]))

    # fingerprint 재계산
    new_fingerprint = _transaction_fingerprint({
        "date": updated_date,
        "amount": updated_amount,
        "description": updated_description,
        "method": updated_method,
        "direction": "expense",
        "raw_category": updated_category,
    })
    updates["import_fingerprint"] = new_fingerprint

    rowcount = _apply_transaction_update(transaction_id, updates, "expense")
    if rowcount == 0:
        raise HTTPException(status_code=404, detail="expense transaction not found")

    return {"status": "ok"}


@app.patch("/api/expense-transactions")
def update_expense_transaction_by_match(
    payload: ExpenseTransactionUpdateByMatchRequest,
) -> dict[str, str]:
    updates = _build_transaction_updates(payload.updated, "expense")
    if not updates:
        raise HTTPException(status_code=400, detail="no fields to update")

    if payload.original.amount <= 0:
        raise HTTPException(status_code=400, detail="original amount must be greater than 0")

    with get_connection(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT id, amount
            FROM transactions
            WHERE direction = 'expense'
              AND date = ?
              AND COALESCE(raw_category, '') = ?
              AND COALESCE(description, '') = ?
              AND COALESCE(method, '') = ?
                            AND COALESCE(is_excluded, 0) = ?
            """,
            (
                payload.original.date.strip(),
                payload.original.category.strip(),
                payload.original.description.strip(),
                payload.original.method.strip(),
                                1 if payload.original.excluded else 0,
            ),
        ).fetchall()

    matched_ids: list[str] = []
    for row in rows:
        amount = _parse_amount_to_abs_int(row["amount"])
        if amount == payload.original.amount:
            matched_ids.append(str(row["id"]))

    if len(matched_ids) == 0:
        raise HTTPException(status_code=404, detail="expense transaction not found")

    if len(matched_ids) > 1:
        raise HTTPException(status_code=409, detail="multiple transactions matched; cannot update safely")

    rowcount = _apply_transaction_update(matched_ids[0], updates, "expense")
    if rowcount == 0:
        raise HTTPException(status_code=404, detail="expense transaction not found")

    return {"status": "ok"}


@app.get("/api/income-transactions", response_model=list[IncomeCategoryTransactions])
def income_transactions(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    group_level: str = Query("major", pattern="^(major|full)$"),
    include_excluded: bool = Query(False),
) -> list[IncomeCategoryTransactions]:
    prefix = _month_prefix(year, month)

    grouped: dict[str, list[IncomeTransactionItem]] = {}

    with get_connection(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT id, date, raw_category, description, amount, method, is_excluded
            FROM transactions
            WHERE date LIKE ?
              AND direction = 'income'
              AND (? = 1 OR COALESCE(is_excluded, 0) = 0)
            ORDER BY date DESC
            """,
            (f"{prefix}%", 1 if include_excluded else 0),
        ).fetchall()

    for row in rows:
        raw_category = (row["raw_category"] or "").strip() or "미분류"
        category = _major_category(raw_category) if group_level == "major" else raw_category

        amount = _parse_amount_to_abs_int(row["amount"])
        if amount is None:
            continue

        item = IncomeTransactionItem(
            id=str(row["id"]),
            date=str(row["date"]),
            category=raw_category,
            description=(row["description"] or "").strip(),
            amount=amount,
            method=(row["method"] or "").strip(),
            excluded=bool(row["is_excluded"]),
        )
        grouped.setdefault(category, []).append(item)

    response: list[IncomeCategoryTransactions] = []
    for category, items in grouped.items():
        total_amount = sum(item.amount for item in items)
        response.append(
            IncomeCategoryTransactions(
                category=category,
                total_amount=total_amount,
                count=len(items),
                items=items,
            )
        )

    response.sort(key=lambda entry: entry.total_amount, reverse=True)
    return response


@app.patch("/api/income-transactions/{transaction_id}")
def update_income_transaction(
    transaction_id: str,
    payload: IncomeTransactionUpdateRequest,
) -> dict[str, str]:
    updates = _build_transaction_updates(payload, "income")

    if not updates:
        raise HTTPException(status_code=400, detail="no fields to update")

    # 현재 거래 정보 조회 후 fingerprint 재계산 필요 여부 확인
    with get_connection(DB_PATH) as conn:
        row = conn.execute(
            "SELECT date, amount, description, method, raw_category FROM transactions WHERE id = ? AND direction = 'income'",
            (transaction_id,),
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="income transaction not found")

    # 수정된 필드들을 현재값과 병합
    updated_date = updates.get("date", str(row["date"]))
    updated_amount = updates.get("amount", str(row["amount"]))
    updated_description = updates.get("description", str(row["description"]))
    updated_method = updates.get("method", str(row["method"]))
    updated_category = updates.get("raw_category", str(row["raw_category"]))

    # fingerprint 재계산
    new_fingerprint = _transaction_fingerprint({
        "date": updated_date,
        "amount": updated_amount,
        "description": updated_description,
        "method": updated_method,
        "direction": "income",
        "raw_category": updated_category,
    })
    updates["import_fingerprint"] = new_fingerprint

    rowcount = _apply_transaction_update(transaction_id, updates, "income")
    if rowcount == 0:
        raise HTTPException(status_code=404, detail="income transaction not found")

    return {"status": "ok"}


@app.patch("/api/income-transactions")
def update_income_transaction_by_match(
    payload: IncomeTransactionUpdateByMatchRequest,
) -> dict[str, str]:
    updates = _build_transaction_updates(payload.updated, "income")
    if not updates:
        raise HTTPException(status_code=400, detail="no fields to update")

    if payload.original.amount <= 0:
        raise HTTPException(status_code=400, detail="original amount must be greater than 0")

    with get_connection(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT id, amount
            FROM transactions
            WHERE direction = 'income'
              AND date = ?
              AND COALESCE(raw_category, '') = ?
              AND COALESCE(description, '') = ?
              AND COALESCE(method, '') = ?
              AND COALESCE(is_excluded, 0) = ?
            """,
            (
                payload.original.date.strip(),
                payload.original.category.strip(),
                payload.original.description.strip(),
                payload.original.method.strip(),
                1 if payload.original.excluded else 0,
            ),
        ).fetchall()

    matched_ids: list[str] = []
    for row in rows:
        amount = _parse_amount_to_abs_int(row["amount"])
        if amount == payload.original.amount:
            matched_ids.append(str(row["id"]))

    if len(matched_ids) == 0:
        raise HTTPException(status_code=404, detail="income transaction not found")

    if len(matched_ids) > 1:
        raise HTTPException(status_code=409, detail="multiple transactions matched; cannot update safely")

    rowcount = _apply_transaction_update(matched_ids[0], updates, "income")
    if rowcount == 0:
        raise HTTPException(status_code=404, detail="income transaction not found")

    return {"status": "ok"}
