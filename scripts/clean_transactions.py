#!/usr/bin/env python3
"""Normalize TSV transaction exports into app-friendly CSV schema."""

from __future__ import annotations

import argparse
import csv
import uuid
from decimal import Decimal, InvalidOperation
from pathlib import Path

INPUT_HEADERS = [
    "날짜",
    "시간",
    "타입",
    "대분류",
    "소분류",
    "내용",
    "금액",
    "화폐",
    "결제수단",
    "메모",
]

OUTPUT_HEADERS = [
    "id",
    "date",
    "amount",
    "description",
    "merchant",
    "method",
    "direction",
    "raw_category",
    "memo",
]


def _parse_amount(value: str) -> Decimal:
    normalized = value.strip().replace(",", "")
    try:
        return Decimal(normalized)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid amount value: {value!r}") from exc


def _build_raw_category(main_category: str, sub_category: str) -> str:
    main = main_category.strip()
    sub = sub_category.strip()
    if not main or not sub:
        return ""
    return f"{main}>{sub}"


def normalize_row(row: dict[str, str]) -> dict[str, str]:
    amount_text = (row.get("금액") or "").strip()
    amount_value = _parse_amount(amount_text)

    description = (row.get("내용") or "").strip()

    return {
        "id": str(uuid.uuid4()),
        "date": (row.get("날짜") or "").strip(),
        "amount": amount_text,
        "description": description,
        # TODO: merchant normalization with dedicated parser/map
        "merchant": description,
        "method": (row.get("결제수단") or "").strip(),
        "direction": "income" if amount_value > 0 else "expense",
        "raw_category": _build_raw_category(
            row.get("대분류") or "", row.get("소분류") or ""
        ),
        "memo": (row.get("메모") or "").strip(),
    }


def clean_transactions(input_path: Path, output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with input_path.open("r", encoding="utf-8-sig", newline="") as in_file, output_path.open(
        "w", encoding="utf-8", newline=""
    ) as out_file:
        reader = csv.DictReader(in_file, delimiter="\t")
        missing_headers = [h for h in INPUT_HEADERS if h not in (reader.fieldnames or [])]
        if missing_headers:
            raise ValueError(f"Missing required headers: {', '.join(missing_headers)}")

        writer = csv.DictWriter(out_file, fieldnames=OUTPUT_HEADERS)
        writer.writeheader()

        for row in reader:
            writer.writerow(normalize_row(row))
            count += 1

    return count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="input_path", required=True, help="Input TSV path")
    parser.add_argument("--out", dest="output_path", required=True, help="Output CSV path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = clean_transactions(Path(args.input_path), Path(args.output_path))
    print(f"Wrote {rows} rows to {args.output_path}")


if __name__ == "__main__":
    main()
