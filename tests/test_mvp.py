import unittest

from bankpoke.mvp import LedgerService


SAMPLE = """날짜\t시간\t타입\t대분류\t소분류\t내용\t금액\t화폐\t결제수단\t메모
2026-02-13\t10:24\t이체\t내계좌이체\t미분류\t세이프박스\t1000\tKRW\t입출금통장\t
2026-02-13\t10:24\t이체\t내계좌이체\t미분류\t내계좌로 이체\t-1000\tKRW\t세이프박스\t
2026-02-13\t00:52\t지출\t온라인쇼핑\t인터넷쇼핑\t(주)카카오\t-5800\tKRW\t입출금통장\t
2026-02-10\t20:48\t지출\t온라인쇼핑\t인터넷쇼핑\t쿠팡\t7990\tKRW\t나라사랑(체크)\t
2026-02-10\t11:30\t수입\t금융수입\t미분류\t프렌즈 체크카드 캐시백\t5006\tKRW\t입출금통장\t
"""


class TestLedgerMVP(unittest.TestCase):
    def setUp(self) -> None:
        self.svc = LedgerService(":memory:")
        self.svc.init_db()

    def tearDown(self) -> None:
        self.svc.close()

    def test_import_and_summary(self) -> None:
        result = self.svc.import_tsv(SAMPLE)
        self.assertEqual(result.imported, 5)
        self.assertEqual(result.skipped_duplicates, 0)
        self.assertEqual(result.review_required, 1)

        summary = self.svc.monthly_summary(2026, 2)
        self.assertEqual(summary["income"], 5006)
        self.assertEqual(summary["expense"], 5800)

    def test_idempotent_import(self) -> None:
        first = self.svc.import_tsv(SAMPLE)
        second = self.svc.import_tsv(SAMPLE)

        self.assertEqual(first.imported, 5)
        self.assertEqual(second.imported, 0)
        self.assertEqual(second.skipped_duplicates, 5)

    def test_transfer_pairing(self) -> None:
        self.svc.import_tsv(SAMPLE)
        unmatched = self.svc.unmatched_transfers()
        # internal transfer should be paired and excluded from unmatched
        self.assertEqual(len(unmatched), 0)


if __name__ == "__main__":
    unittest.main()
