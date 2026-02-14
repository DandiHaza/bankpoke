# bankpoke MVP

가계부 앱 MVP 백엔드(로컬 SQLite 기반)입니다.

## 기능
- TSV 가계부 내역 import
- 중복 import 방지(row hash)
- 타입/금액 부호 정합성 경고(`review_required`)
- 내계좌이체 자동 페어링(5분/동일 절대금액/반대 부호)
- 월간 요약 조회

## 실행
```bash
PYTHONPATH=src python -m bankpoke.cli --db bankpoke.db init-db
PYTHONPATH=src python -m bankpoke.cli --db bankpoke.db import --file sample.tsv
PYTHONPATH=src python -m bankpoke.cli --db bankpoke.db summary --year 2026 --month 2
```

## 테스트
```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```
