import csv
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "clean_transactions.py"
spec = importlib.util.spec_from_file_location("clean_transactions", MODULE_PATH)
ct = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(ct)

REQUIRED_HEADER = "\t".join(ct.INPUT_HEADERS)


def _write_tsv(path: Path, rows: list[list[str]]) -> None:
    body = "\n".join("\t".join(row) for row in rows)
    path.write_text(f"{REQUIRED_HEADER}\n{body}\n", encoding="utf-8")


def test_normalize_row_maps_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ct.uuid, "uuid4", lambda: "fixed-uuid")

    out = ct.normalize_row(
        {
            "날짜": "2026-02-01",
            "내용": "스타벅스",
            "금액": "-4900",
            "결제수단": "카드",
            "대분류": "식비",
            "소분류": "카페",
            "메모": "테이크아웃",
        }
    )

    assert out == {
        "id": "fixed-uuid",
        "date": "2026-02-01",
        "amount": "-4900",
        "description": "스타벅스",
        "merchant": "스타벅스",
        "method": "카드",
        "direction": "expense",
        "raw_category": "식비>카페",
        "memo": "테이크아웃",
    }


def test_direction_income_for_positive_amount(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ct.uuid, "uuid4", lambda: "uuid-income")
    out = ct.normalize_row({"금액": "10000", "내용": "급여"})
    assert out["direction"] == "income"


def test_raw_category_empty_if_any_part_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ct.uuid, "uuid4", lambda: "uuid-category")

    out_main_missing = ct.normalize_row({"금액": "-1", "대분류": "", "소분류": "카페"})
    out_sub_missing = ct.normalize_row({"금액": "-1", "대분류": "식비", "소분류": ""})

    assert out_main_missing["raw_category"] == ""
    assert out_sub_missing["raw_category"] == ""


def test_clean_transactions_writes_fixed_output_schema(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sequence = iter(["uuid-1", "uuid-2"])
    monkeypatch.setattr(ct.uuid, "uuid4", lambda: next(sequence))

    in_path = tmp_path / "input.tsv"
    out_path = tmp_path / "output.csv"

    _write_tsv(
        in_path,
        [
            ["2026-02-01", "09:00", "지출", "식비", "카페", "라떼", "-4500", "KRW", "카드", ""],
            ["2026-02-02", "10:00", "수입", "급여", "월급", "2월 급여", "3000000", "KRW", "계좌", ""],
        ],
    )

    count = ct.clean_transactions(in_path, out_path)

    assert count == 2
    rows = list(csv.DictReader(out_path.open("r", encoding="utf-8")))
    assert rows[0]["id"] == "uuid-1"
    assert rows[0]["direction"] == "expense"
    assert rows[1]["id"] == "uuid-2"
    assert rows[1]["direction"] == "income"
    assert list(rows[0].keys()) == ct.OUTPUT_HEADERS


def test_clean_transactions_raises_on_missing_headers(tmp_path: Path) -> None:
    in_path = tmp_path / "bad.tsv"
    out_path = tmp_path / "output.csv"
    in_path.write_text("날짜\t시간\n2026-01-01\t09:00\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Missing required headers"):
        ct.clean_transactions(in_path, out_path)


def test_cli_generates_output_file(tmp_path: Path) -> None:
    in_path = tmp_path / "input.tsv"
    out_path = tmp_path / "output.csv"
    _write_tsv(
        in_path,
        [["2026-02-01", "09:00", "지출", "식비", "카페", "커피", "-4500", "KRW", "카드", ""]],
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/clean_transactions.py",
            "--in",
            str(in_path),
            "--out",
            str(out_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    assert "Wrote 1 rows" in result.stdout
    assert out_path.exists()
