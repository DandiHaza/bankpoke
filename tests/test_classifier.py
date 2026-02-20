from app.classifier import Transaction, classify_transaction, load_rules


RULES = load_rules("config/rules.yaml")


def tx(amount: str, description: str, merchant: str = "", raw_category: str = "", memo: str = "", method: str = "카드") -> Transaction:
    return Transaction(
        id="x",
        date="2026-02-01",
        amount=amount,
        description=description,
        merchant=merchant or description,
        method=method,
        raw_category=raw_category,
        memo=memo,
    )


def test_transfer_rule():
    out = classify_transaction(tx("-100000", "내 계좌 이체"), RULES)
    assert out.expense_kind == "transfer"
    assert out.rules_fired == ["transfer_internal"]


def test_repayment_rule():
    out = classify_transaction(tx("-330000", "카드대금 납부"), RULES)
    assert out.expense_kind == "repayment"


def test_saving_invest_rule():
    out = classify_transaction(tx("-200000", "적금 자동이체"), RULES)
    assert out.expense_kind == "saving_invest"


def test_refund_forces_income_direction():
    out = classify_transaction(tx("-12000", "주문 취소 환불"), RULES)
    assert out.expense_kind == "refund"
    assert out.direction == "income"


def test_cash_withdrawal_rule():
    out = classify_transaction(tx("-50000", "ATM 출금"), RULES)
    assert out.expense_kind == "cash_withdrawal"


def test_category_cafe_rule():
    out = classify_transaction(tx("-4900", "스타벅스"), RULES)
    assert out.expense_kind == "real"
    assert out.category == "cafe"


def test_category_food_rule():
    out = classify_transaction(tx("-9900", "점심 식당"), RULES)
    assert out.category == "food"


def test_category_transport_rule():
    out = classify_transaction(tx("-1250", "지하철"), RULES)
    assert out.category == "transport"


def test_category_shopping_rule():
    out = classify_transaction(tx("-42000", "쿠팡 주문"), RULES)
    assert out.category == "shopping"


def test_category_living_rule():
    out = classify_transaction(tx("-58000", "관리비"), RULES)
    assert out.category == "living"


def test_category_subscription_rule():
    out = classify_transaction(tx("-8900", "넷플릭스"), RULES)
    assert out.category == "subscription"


def test_category_medical_rule():
    out = classify_transaction(tx("-22000", "병원 진료"), RULES)
    assert out.category == "medical"


def test_category_education_rule():
    out = classify_transaction(tx("-130000", "학원 수강료"), RULES)
    assert out.category == "education"


def test_category_leisure_rule():
    out = classify_transaction(tx("-15000", "영화 관람"), RULES)
    assert out.category == "leisure"


def test_category_gift_rule():
    out = classify_transaction(tx("-50000", "생일 선물"), RULES)
    assert out.category == "gift"


def test_category_travel_rule():
    out = classify_transaction(tx("-350000", "항공권 예약"), RULES)
    assert out.category == "travel"


def test_priority_non_real_wins_over_real_category():
    out = classify_transaction(tx("-100000", "카드대금 스타벅스"), RULES)
    assert out.expense_kind == "repayment"
    assert out.category is None


def test_default_expense_real_etc_when_no_match():
    out = classify_transaction(tx("-7777", "정체불명 지출"), RULES)
    assert out.expense_kind == "real"
    assert out.category == "etc"


def test_default_income_other_when_no_match():
    out = classify_transaction(tx("500000", "급여"), RULES)
    assert out.direction == "income"
    assert out.expense_kind == "other"
