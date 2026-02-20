import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.db import get_connection


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / "test.db"
    previous_db_path = main.DB_PATH
    main.DB_PATH = str(db_path)

    with TestClient(main.app) as test_client:
        yield test_client

    main.DB_PATH = previous_db_path


def _insert_expense_row(
    db_path: str,
    date: str,
    amount: str,
    raw_category: str,
) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO transactions (
                id, date, amount, description, merchant, method,
                direction, raw_category, memo
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                date,
                amount,
                "desc",
                "merchant",
                "method",
                "expense",
                raw_category,
                "",
            ),
        )


def _insert_income_row(
    db_path: str,
    date: str,
    amount: str,
    raw_category: str,
) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO transactions (
                id, date, amount, description, merchant, method,
                direction, raw_category, memo
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                date,
                amount,
                "income-desc",
                "income-merchant",
                "method",
                "income",
                raw_category,
                "",
            ),
        )


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_transaction_reflects_in_summary(client: TestClient) -> None:
    response = client.post(
        "/api/transactions",
        json={
            "date": "2026-02-20",
            "direction": "income",
            "category": "급여>월급",
            "description": "월급",
            "amount": 10000,
            "method": "토스",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert isinstance(payload["id"], str)

    summary = client.get("/api/summary?year=2026&month=2")
    assert summary.status_code == 200
    assert summary.json()["income"] == 10000


def test_import_transactions_csv(client: TestClient) -> None:
    csv_content = (
        "id,date,amount,description,merchant,method,direction,raw_category,memo\n"
        "row-1,2026-02-20,-12000,점심,점심,카드,expense,식비>한식,\n"
        "row-2,2026-02-20,30000,환급,환급,입출금,income,기타수입>미분류,\n"
    )

    response = client.post(
        "/api/transactions/import",
        files={"file": ("import.csv", csv_content.encode("utf-8"), "text/csv")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["imported"] == 2

    summary = client.get("/api/summary?year=2026&month=2")
    assert summary.status_code == 200
    assert summary.json()["income"] == 30000
    assert summary.json()["expense"] == 12000


def test_import_transactions_replace_month(client: TestClient) -> None:
    _insert_expense_row(main.DB_PATH, "2026-02-10", "-10000", "식비>한식")

    csv_content = (
        "id,date,amount,description,merchant,method,direction,raw_category,memo\n"
        "row-3,2026-02-22,-7000,저녁,저녁,카드,expense,식비>한식,\n"
    )

    response = client.post(
        "/api/transactions/import",
        data={"replace_month": "true", "year": "2026", "month": "2"},
        files={"file": ("replace.csv", csv_content.encode("utf-8"), "text/csv")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["imported"] == 1
    assert payload["deleted"] >= 1

    summary = client.get("/api/summary?year=2026&month=2")
    assert summary.status_code == 200
    assert summary.json()["expense"] == 7000


def test_import_transactions_skips_overlapping_without_replace(client: TestClient) -> None:
    _insert_expense_row(main.DB_PATH, "2026-02-10", "-10000", "식비>한식")

    csv_content = (
        "id,date,amount,description,merchant,method,direction,raw_category,memo\n"
        "new-1,2026-02-10,-10000,desc,merchant,method,expense,식비>한식,\n"
        "new-2,2026-02-11,-3000,새 거래,새 거래,카드,expense,식비>배달,\n"
    )

    response = client.post(
        "/api/transactions/import",
        data={"replace_month": "false"},
        files={"file": ("dedup.csv", csv_content.encode("utf-8"), "text/csv")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["imported"] == 1
    assert payload["skipped_duplicates"] == 1

    summary = client.get("/api/summary?year=2026&month=2")
    assert summary.status_code == 200
    assert summary.json()["expense"] == 13000


def test_summary_empty_month(client: TestClient) -> None:
    response = client.get("/api/summary?year=2026&month=2")
    assert response.status_code == 200
    assert response.json() == {
        "year": 2026,
        "month": 2,
        "income": 0,
        "expense": 0,
        "net_cashflow": 0,
        "transaction_count": 0,
    }


def test_summary_invalid_month(client: TestClient) -> None:
    response = client.get("/api/summary?year=2026&month=13")
    assert response.status_code == 422


def test_category_breakdown_sorted(client: TestClient) -> None:
    _insert_expense_row(main.DB_PATH, "2026-02-10", "-10000", "식비>한식")
    _insert_expense_row(main.DB_PATH, "2026-02-11", "-3000", "식비>한식")
    _insert_expense_row(main.DB_PATH, "2026-02-12", "-2000", "생활>생필품")

    response = client.get("/api/category-breakdown?year=2026&month=2")
    assert response.status_code == 200

    payload = response.json()
    assert payload[0] == {"category": "식비>한식", "amount": 13000}
    assert payload[1] == {"category": "생활>생필품", "amount": 2000}


def test_category_monthly_trend(client: TestClient) -> None:
    _insert_expense_row(main.DB_PATH, "2026-01-15", "-12000", "식비>한식")
    _insert_expense_row(main.DB_PATH, "2026-02-10", "-7000", "식비>한식")
    _insert_expense_row(main.DB_PATH, "2026-02-11", "-3000", "교통>철도")

    response = client.get("/api/category-monthly-trend?year=2026&top=2")
    assert response.status_code == 200

    payload = response.json()
    assert payload["year"] == 2026
    assert payload["categories"] == ["식비>한식", "교통>철도"]
    assert payload["rows"] == [
        {"month": 1, "values": {"식비>한식": 12000, "교통>철도": 0}},
        {"month": 2, "values": {"식비>한식": 7000, "교통>철도": 3000}},
    ]


def test_category_monthly_trend_grouped_major(client: TestClient) -> None:
    _insert_expense_row(main.DB_PATH, "2026-02-10", "-7000", "식비>한식")
    _insert_expense_row(main.DB_PATH, "2026-02-11", "-3000", "식비>배달")
    _insert_expense_row(main.DB_PATH, "2026-02-12", "-5000", "교통>버스")

    response = client.get("/api/category-monthly-trend?year=2026&top=2&group_level=major")
    assert response.status_code == 200

    payload = response.json()
    assert payload["categories"] == ["식비", "교통"]
    assert payload["rows"] == [
        {"month": 2, "values": {"식비": 10000, "교통": 5000}},
    ]


def test_expense_transactions_grouped_major(client: TestClient) -> None:
    _insert_expense_row(main.DB_PATH, "2026-02-10", "-10000", "식비>한식")
    _insert_expense_row(main.DB_PATH, "2026-02-11", "-3000", "식비>배달")
    _insert_expense_row(main.DB_PATH, "2026-02-12", "-2000", "생활>생필품")

    response = client.get("/api/expense-transactions?year=2026&month=2&group_level=major")
    assert response.status_code == 200

    payload = response.json()
    assert payload[0]["category"] == "식비"
    assert payload[0]["total_amount"] == 13000
    assert payload[0]["count"] == 2
    assert payload[1]["category"] == "생활"
    assert payload[1]["total_amount"] == 2000


def test_update_expense_transaction_by_match(client: TestClient) -> None:
    _insert_expense_row(main.DB_PATH, "2026-02-10", "-10000", "식비>한식")

    list_response = client.get("/api/expense-transactions?year=2026&month=2&group_level=full")
    assert list_response.status_code == 200
    item = list_response.json()[0]["items"][0]

    patch_response = client.patch(
        "/api/expense-transactions",
        json={
            "original": {
                "date": item["date"],
                "category": item["category"],
                "description": item["description"],
                "amount": item["amount"],
                "method": item["method"],
            },
            "updated": {
                "description": "점심 식사",
            },
        },
    )
    assert patch_response.status_code == 200
    assert patch_response.json() == {"status": "ok"}

    with get_connection(main.DB_PATH) as conn:
        row = conn.execute(
            "SELECT description, merchant FROM transactions WHERE id = ?",
            (item["id"],),
        ).fetchone()

    assert row is not None
    assert row["description"] == "점심 식사"
    assert row["merchant"] == "점심 식사"


def test_excluded_expense_not_in_spending_aggregates(client: TestClient) -> None:
    _insert_expense_row(main.DB_PATH, "2026-02-10", "-10000", "식비>한식")

    list_response = client.get("/api/expense-transactions?year=2026&month=2&group_level=full")
    assert list_response.status_code == 200
    item = list_response.json()[0]["items"][0]

    exclude_response = client.patch(
        f"/api/expense-transactions/{item['id']}",
        json={"excluded": True},
    )
    assert exclude_response.status_code == 200

    summary_response = client.get("/api/summary?year=2026&month=2")
    assert summary_response.status_code == 200
    assert summary_response.json()["expense"] == 0

    breakdown_response = client.get("/api/category-breakdown?year=2026&month=2")
    assert breakdown_response.status_code == 200
    assert breakdown_response.json() == []


def test_expense_transactions_excludes_excluded_by_default(client: TestClient) -> None:
    _insert_expense_row(main.DB_PATH, "2026-02-10", "-10000", "식비>한식")
    _insert_expense_row(main.DB_PATH, "2026-02-11", "-3000", "식비>배달")

    base_response = client.get("/api/expense-transactions?year=2026&month=2&group_level=full")
    assert base_response.status_code == 200
    item_id = base_response.json()[0]["items"][0]["id"]

    exclude_response = client.patch(
        f"/api/expense-transactions/{item_id}",
        json={"excluded": True},
    )
    assert exclude_response.status_code == 200

    default_response = client.get("/api/expense-transactions?year=2026&month=2&group_level=full")
    assert default_response.status_code == 200
    default_items = [item for group in default_response.json() for item in group["items"]]
    assert all(item["id"] != item_id for item in default_items)

    include_response = client.get(
        "/api/expense-transactions?year=2026&month=2&group_level=full&include_excluded=true"
    )
    assert include_response.status_code == 200
    include_items = [item for group in include_response.json() for item in group["items"]]
    excluded_item = next(item for item in include_items if item["id"] == item_id)
    assert excluded_item["excluded"] is True


def test_income_transactions_grouped_major(client: TestClient) -> None:
    _insert_income_row(main.DB_PATH, "2026-02-10", "10000", "급여>월급")
    _insert_income_row(main.DB_PATH, "2026-02-11", "3000", "급여>보너스")
    _insert_income_row(main.DB_PATH, "2026-02-12", "2000", "기타>환급")

    response = client.get("/api/income-transactions?year=2026&month=2&group_level=major")
    assert response.status_code == 200

    payload = response.json()
    assert payload[0]["category"] == "급여"
    assert payload[0]["total_amount"] == 13000
    assert payload[0]["count"] == 2
    assert payload[1]["category"] == "기타"
    assert payload[1]["total_amount"] == 2000


def test_update_income_transaction_by_match(client: TestClient) -> None:
    _insert_income_row(main.DB_PATH, "2026-02-10", "10000", "급여>월급")

    list_response = client.get("/api/income-transactions?year=2026&month=2&group_level=full")
    assert list_response.status_code == 200
    item = list_response.json()[0]["items"][0]

    patch_response = client.patch(
        "/api/income-transactions",
        json={
            "original": {
                "date": item["date"],
                "category": item["category"],
                "description": item["description"],
                "amount": item["amount"],
                "method": item["method"],
            },
            "updated": {
                "description": "월급 입금",
            },
        },
    )
    assert patch_response.status_code == 200
    assert patch_response.json() == {"status": "ok"}

    with get_connection(main.DB_PATH) as conn:
        row = conn.execute(
            "SELECT description, merchant FROM transactions WHERE id = ?",
            (item["id"],),
        ).fetchone()

    assert row is not None
    assert row["description"] == "월급 입금"
    assert row["merchant"] == "월급 입금"


def test_excluded_income_not_in_summary_income(client: TestClient) -> None:
    _insert_income_row(main.DB_PATH, "2026-02-10", "10000", "급여>월급")

    list_response = client.get("/api/income-transactions?year=2026&month=2&group_level=full")
    assert list_response.status_code == 200
    item = list_response.json()[0]["items"][0]

    exclude_response = client.patch(
        f"/api/income-transactions/{item['id']}",
        json={"excluded": True},
    )
    assert exclude_response.status_code == 200

    summary_response = client.get("/api/summary?year=2026&month=2")
    assert summary_response.status_code == 200
    assert summary_response.json()["income"] == 0


def test_income_transactions_excludes_excluded_by_default(client: TestClient) -> None:
    _insert_income_row(main.DB_PATH, "2026-02-10", "10000", "급여>월급")
    _insert_income_row(main.DB_PATH, "2026-02-11", "3000", "급여>보너스")

    base_response = client.get("/api/income-transactions?year=2026&month=2&group_level=full")
    assert base_response.status_code == 200
    item_id = base_response.json()[0]["items"][0]["id"]

    exclude_response = client.patch(
        f"/api/income-transactions/{item_id}",
        json={"excluded": True},
    )
    assert exclude_response.status_code == 200

    default_response = client.get("/api/income-transactions?year=2026&month=2&group_level=full")
    assert default_response.status_code == 200
    default_items = [item for group in default_response.json() for item in group["items"]]
    assert all(item["id"] != item_id for item in default_items)

    include_response = client.get(
        "/api/income-transactions?year=2026&month=2&group_level=full&include_excluded=true"
    )
    assert include_response.status_code == 200
    include_items = [item for group in include_response.json() for item in group["items"]]
    excluded_item = next(item for item in include_items if item["id"] == item_id)
    assert excluded_item["excluded"] is True


def test_import_auto_exclude_transfer(client: TestClient) -> None:
    csv_content = """id,date,amount,description,merchant,method,direction,raw_category,memo
t1,2026-02-15,-100000,은행이체,은행,bank,expense,이체,
t2,2026-02-16,-50000,마트,마트,card,expense,식비,"""

    response = client.post(
        "/api/transactions/import",
        data={"replace_month": False},
        files={"file": ("test.csv", csv_content)},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["imported"] == 2

    expense_response = client.get("/api/expense-transactions?year=2026&month=2&group_level=major")
    assert expense_response.status_code == 200
    expense_items = [item for group in expense_response.json() for item in group["items"]]
    
    # 이체는 excluded=true이므로 기본 조회에서 안 나와야 함
    transfer_items = [item for item in expense_items if item["description"] == "은행이체"]
    assert len(transfer_items) == 0
    
    # 식비는 excluded=false이므로 기본 조회에서 나와야 함
    food_items = [item for item in expense_items if item["description"] == "마트"]
    assert len(food_items) == 1
    
    # include_excluded=true로 조회하면 이체도 나와야 함
    all_response = client.get("/api/expense-transactions?year=2026&month=2&group_level=major&include_excluded=true")
    assert all_response.status_code == 200
    all_items = [item for group in all_response.json() for item in group["items"]]
    transfer_excluded_items = [item for item in all_items if item["description"] == "은행이체"]
    assert len(transfer_excluded_items) == 1
    assert transfer_excluded_items[0]["excluded"] is True


def test_reimport_after_edit_should_not_duplicate(client: TestClient) -> None:
    """수정 후 재import 시 중복되지 않아야 함"""
    # 1차 import
    csv_content = """id,date,amount,description,merchant,method,direction,raw_category,memo
t1,2026-02-15,-50000,마트,마트,card,expense,식비,"""

    response = client.post(
        "/api/transactions/import",
        data={"replace_month": False},
        files={"file": ("test.csv", csv_content)},
    )
    assert response.status_code == 200
    assert response.json()["imported"] == 1
    
    # 첫 번째 조회 - 1개만 있어야 함
    before = client.get("/api/expense-transactions?year=2026&month=2&group_level=full")
    before_items = [item for group in before.json() for item in group["items"]]
    assert len(before_items) == 1
    item_id = before_items[0]["id"]
    
    # 거래 수정 (금액 변경: 50000 -> 60000)
    patch_response = client.patch(
        f"/api/expense-transactions/{item_id}",
        json={"amount": 60000}
    )
    assert patch_response.status_code == 200
    
    # 2차 import (원본 데이터 재수입 - 50000)
    response2 = client.post(
        "/api/transactions/import",
        data={"replace_month": False},
        files={"file": ("test.csv", csv_content)},
    )
    assert response2.status_code == 200
    # 원본 데이터와 수정된 데이터가 겹치面 스킵되어야 함
    assert response2.json()["skipped_duplicates"] == 1
    assert response2.json()["imported"] == 0
    
    # 최종 조회 - 1개만 있어야 함 (수정된 60000)
    after = client.get("/api/expense-transactions?year=2026&month=2&group_level=full")
    after_items = [item for group in after.json() for item in group["items"]]
    assert len(after_items) == 1
    assert after_items[0]["amount"] == 60000


def test_reimport_after_exclude_should_not_reappear(client: TestClient) -> None:
    """제외 후 재import 시 제외된 거래가 다시 나타나면 안 됨"""
    # 1차 import
    csv_content = """id,date,amount,description,merchant,method,direction,raw_category,memo
t1,2026-02-15,-50000,마트,마트,card,expense,식비,"""

    response = client.post(
        "/api/transactions/import",
        data={"replace_month": False},
        files={"file": ("test.csv", csv_content)},
    )
    assert response.status_code == 200
    assert response.json()["imported"] == 1
    
    # 첫 번째 조회 - 1개 있음
    before = client.get("/api/expense-transactions?year=2026&month=2&group_level=full")
    before_items = [item for group in before.json() for item in group["items"]]
    assert len(before_items) == 1
    item_id = before_items[0]["id"]
    
    # 거래 제외 처리
    patch_response = client.patch(
        f"/api/expense-transactions/{item_id}",
        json={"excluded": True}
    )
    assert patch_response.status_code == 200
    
    # 제외 후 조회 - 0개
    after_exclude = client.get("/api/expense-transactions?year=2026&month=2&group_level=full")
    after_exclude_items = [item for group in after_exclude.json() for item in group["items"]]
    assert len(after_exclude_items) == 0
    
    # 2차 import (원본 데이터 재수입)
    response2 = client.post(
        "/api/transactions/import",
        data={"replace_month": False},
        files={"file": ("test.csv", csv_content)},
    )
    assert response2.status_code == 200
    # 스킵되어야 함
    assert response2.json()["skipped_duplicates"] == 1
    assert response2.json()["imported"] == 0
    
    # 최종 조회 - 여전히 0개 (제외된 상태 유지)
    after_reimport = client.get("/api/expense-transactions?year=2026&month=2&group_level=full")
    after_reimport_items = [item for group in after_reimport.json() for item in group["items"]]
    assert len(after_reimport_items) == 0
    
    # include_excluded=true로는 1개 (제외됨 상태로)
    all_response = client.get("/api/expense-transactions?year=2026&month=2&group_level=full&include_excluded=true")
    all_items = [item for group in all_response.json() for item in group["items"]]
    assert len(all_items) == 1
    assert all_items[0]["excluded"] is True


def test_reimport_with_replace_month_after_edit(client: TestClient) -> None:
    """replace_month=true로 재import 하면 수정 내역이 사라짐"""
    # 1차 import
    csv_content = """id,date,amount,description,merchant,method,direction,raw_category,memo
t1,2026-02-15,-50000,마트,마트,card,expense,식비,
t2,2026-02-16,-30000,카페,카페,card,expense,식비,"""

    response = client.post(
        "/api/transactions/import",
        data={"replace_month": False},
        files={"file": ("test.csv", csv_content)},
    )
    assert response.status_code == 200
    assert response.json()["imported"] == 2
    
    # 첫 번째 조회 - 2개
    before = client.get("/api/expense-transactions?year=2026&month=2&group_level=full")
    before_items = [item for group in before.json() for item in group["items"]]
    assert len(before_items) == 2
    
    # 첫 번째 거래 수정 (금액 변경)
    t1_id = [item for item in before_items if item["description"] == "마트"][0]["id"]
    patch_response = client.patch(
        f"/api/expense-transactions/{t1_id}",
        json={"amount": 60000}
    )
    assert patch_response.status_code == 200
    
    # 수정 확인
    after_edit = client.get("/api/expense-transactions?year=2026&month=2&group_level=full")
    after_edit_items = [item for group in after_edit.json() for item in group["items"]]
    t1_after = [item for item in after_edit_items if item["description"] == "마트"][0]
    assert t1_after["amount"] == 60000
    
    # 2차 import - replace_month=true로 전체 재업로드
    response2 = client.post(
        "/api/transactions/import",
        data={"replace_month": True, "year": 2026, "month": 2},
        files={"file": ("test.csv", csv_content)},
    )
    assert response2.status_code == 200
    # deleted=2 (기존 2개 삭제), imported=2 (새로 2개 추가)
    assert response2.json()["deleted"] == 2
    assert response2.json()["imported"] == 2
    
    # 최종 조회 - 2개 (수정 전 원본으로 돌아가야 함)
    after_reimport = client.get("/api/expense-transactions?year=2026&month=2&group_level=full")
    after_reimport_items = [item for group in after_reimport.json() for item in group["items"]]
    t1_final = [item for item in after_reimport_items if item["description"] == "마트"][0]
    # replace_month=true는 기존 데이터를 물리적으로 삭제하고 새로 추가하므로, 수정이 사라짐
    assert t1_final["amount"] == 50000  # 원본값으로 돌아감
