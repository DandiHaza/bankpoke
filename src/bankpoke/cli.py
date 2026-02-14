from __future__ import annotations

import argparse
import json

from .mvp import LedgerService, load_file_text


def main() -> None:
    parser = argparse.ArgumentParser(description="bankpoke MVP CLI")
    parser.add_argument("--db", default="bankpoke.db", help="SQLite database path")

    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init-db", help="initialize database")

    import_cmd = sub.add_parser("import", help="import TSV ledger file")
    import_cmd.add_argument("--file", required=True, help="TSV file path")

    summary_cmd = sub.add_parser("summary", help="monthly summary")
    summary_cmd.add_argument("--year", required=True, type=int)
    summary_cmd.add_argument("--month", required=True, type=int)

    sub.add_parser("unmatched-transfers", help="list unmatched transfers")

    args = parser.parse_args()
    svc = LedgerService(args.db)

    try:
        if args.cmd == "init-db":
            svc.init_db()
            print("ok")
        elif args.cmd == "import":
            data = load_file_text(args.file)
            result = svc.import_tsv(data)
            print(json.dumps(result.__dict__, ensure_ascii=False))
        elif args.cmd == "summary":
            print(json.dumps(svc.monthly_summary(args.year, args.month), ensure_ascii=False))
        elif args.cmd == "unmatched-transfers":
            rows = svc.unmatched_transfers()
            print(json.dumps([dict(r) for r in rows], ensure_ascii=False))
    finally:
        svc.close()


if __name__ == "__main__":
    main()
