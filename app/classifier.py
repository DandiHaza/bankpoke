#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Transaction:
    id: str
    date: str
    amount: str
    description: str
    merchant: str
    method: str
    raw_category: str
    memo: str


@dataclass
class ClassificationResult:
    direction: str
    expense_kind: str
    category: str | None
    confidence: float
    rules_fired: list[str]


@dataclass
class Rule:
    name: str
    priority: int
    pattern: re.Pattern[str]
    expense_kind: str
    category: str | None
    direction: str | None
    confidence: float


def load_rules(path: str | Path = "config/rules.yaml") -> list[Rule]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rules = []
    for item in data["rules"]:
        rules.append(
            Rule(
                name=item["name"],
                priority=int(item["priority"]),
                pattern=re.compile(item["pattern"], re.IGNORECASE),
                expense_kind=item["expense_kind"],
                category=item.get("category"),
                direction=item.get("direction"),
                confidence=float(item.get("confidence", 0.8)),
            )
        )
    return sorted(rules, key=lambda r: r.priority, reverse=True)


def _base_direction(amount: str) -> str:
    return "income" if float(str(amount).replace(",", "").strip()) > 0 else "expense"


def _haystack(transaction: Transaction) -> str:
    return " ".join(
        [
            transaction.description,
            transaction.merchant,
            transaction.method,
            transaction.raw_category,
            transaction.memo,
        ]
    ).lower()


def classify_transaction(transaction: Transaction, rules: list[Rule] | None = None) -> ClassificationResult:
    rulebook = rules if rules is not None else load_rules()
    direction = _base_direction(transaction.amount)
    matched: Rule | None = None
    text = _haystack(transaction)

    for rule in rulebook:
        if rule.pattern.search(text):
            matched = rule
            break

    if matched:
        final_direction = matched.direction or direction
        category = matched.category if matched.expense_kind == "real" else None
        return ClassificationResult(
            direction=final_direction,
            expense_kind=matched.expense_kind,
            category=category,
            confidence=matched.confidence,
            rules_fired=[matched.name],
        )

    if direction == "expense":
        return ClassificationResult(
            direction="expense",
            expense_kind="real",
            category="etc",
            confidence=0.5,
            rules_fired=["default_expense_real"],
        )

    return ClassificationResult(
        direction="income",
        expense_kind="other",
        category=None,
        confidence=0.5,
        rules_fired=["default_income_other"],
    )


def _demo_transactions() -> list[Transaction]:
    return [
        Transaction("1", "2026-02-01", "-4900", "스타벅스", "스타벅스", "카드", "식비>카페", ""),
        Transaction("2", "2026-02-01", "-15000", "점심식사", "백반집", "카드", "식비>외식", ""),
        Transaction("3", "2026-02-01", "-1250", "지하철", "서울교통공사", "교통카드", "교통>대중교통", ""),
        Transaction("4", "2026-02-01", "-42000", "쿠팡 주문", "쿠팡", "카드", "쇼핑>온라인", ""),
        Transaction("5", "2026-02-01", "-8900", "넷플릭스", "NETFLIX", "카드", "구독>OTT", ""),
        Transaction("6", "2026-02-01", "-120000", "카드대금", "카드사", "계좌", "", ""),
        Transaction("7", "2026-02-01", "-500000", "적금 납입", "은행", "계좌", "", ""),
        Transaction("8", "2026-02-01", "30000", "환불", "쇼핑몰", "계좌", "", "주문 취소"),
        Transaction("9", "2026-02-01", "-100000", "내 계좌 이체", "나", "계좌", "", ""),
        Transaction("10", "2026-02-01", "-50000", "ATM 출금", "은행", "체크", "", ""),
    ]


def run_demo() -> None:
    rules = load_rules()
    for tx in _demo_transactions():
        result = classify_transaction(tx, rules)
        print(
            f"{tx.id}: direction={result.direction}, expense_kind={result.expense_kind}, "
            f"category={result.category}, confidence={result.confidence}, rules={result.rules_fired}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Rule-based transaction classifier")
    parser.add_argument("--demo", action="store_true", help="Print classification results for 10 examples")
    parser.add_argument("--rules", default="config/rules.yaml", help="Rules YAML path")
    args = parser.parse_args()

    if args.demo:
        run_demo()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
