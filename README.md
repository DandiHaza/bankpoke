# bankpoke MVP

가계부 앱 MVP 백엔드(로컬 SQLite 기반)입니다.

## 기능
- TSV 가계부 내역 import
- 중복 import 방지(row hash)
- 타입/금액 부호 정합성 경고(`review_required`)
- 내계좌이체 자동 페어링(5분/동일 절대금액/반대 부호)
- 월간 요약 조회
- 카테고리 지출 합계/비중 차트
- 카테고리 월별 추이 차트

## 실행
### 가상환경(venv) 생성 및 활성화
```bash
python -m venv .venv
source .venv/bin/activate
```

```powershell
# PowerShell (Windows)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

```bash
PYTHONPATH=src python -m bankpoke.cli --db bankpoke.db init-db
PYTHONPATH=src python -m bankpoke.cli --db bankpoke.db import --file sample.tsv
PYTHONPATH=src python -m bankpoke.cli --db bankpoke.db summary --year 2026 --month 2
python scripts/clean_transactions.py --in "/mnt/data/가계부 - 2월 .tsv" --out data/cleaned_transactions.csv
python app/classifier.py --demo
```

## 테스트
```bash
PYTHONPATH=src python -m unittest discover -s tests -v
pytest -q
```

## BankPoke (Next.js + FastAPI + SQLite)
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
PYTHONPATH=backend uvicorn app.main:app --reload --port 8000
cd frontend && npm install && npm run dev
```

```powershell
# PowerShell (Windows)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt

$env:PYTHONPATH="backend"
C:/Bankpoke/.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir backend --reload --port 8000

Set-Location frontend
npm install
npm run dev
```

### 웹페이지 로컬 접속 방법
1. 백엔드 실행 (프로젝트 루트에서)
```bash
PYTHONPATH=backend uvicorn app.main:app --reload --port 8000
```
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt

$env:PYTHONPATH="backend"
C:/Bankpoke/.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir backend --reload --port 8000
```
2. 프론트엔드 실행 (새 터미널에서)
```bash
cd frontend
npm install
npm run dev
```
3. 브라우저 접속
- 웹페이지: `http://127.0.0.1:3000`
- 헬스체크: `http://127.0.0.1:8000/api/health`

참고:
- 프론트가 다른 API 포트를 보도록 되어 있으면 `NEXT_PUBLIC_API_BASE_URL` 환경변수를 맞춰주세요.
- 예: `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8001 npm run dev`
- PowerShell 예: `$env:NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:8001"; npm run dev`

### 웹 데이터 적재(backend DB)
```bash
python scripts/import_tsv_to_backend_db.py --in "data/가계부 - 2월 .tsv" --db "backend/data/app.db"
```

### API (요약)
- `GET /api/health`
- `GET /api/summary?year=2026&month=2`
- `GET /api/category-breakdown?year=2026&month=2`
- `GET /api/category-monthly-trend?year=2026&top=4`

PR 진행 계획: `docs/mvp-pr-plan.md`

## 업데이트 로그 (2026-02-19)

### 프론트엔드 기능/UX
- `지출 월별 추이`에 대분류 선택 UI 추가
	- `수정` 버튼 클릭 시 카테고리 선택 UI 노출
	- `모두 선택` / `모두 해제` 지원
- `지출 분석`의 대분류 기준을 `지출 월별 추이` 카테고리에 반영
- 거래 요약 제목을 `YYYY년 MM월 거래요약`으로 변경
- 거래 요약 목록에서 `조회 월` 항목 제거

### 거래 내역 편집/제외 개선
- 소비/수입 내역 편집 저장 시 전체 리로드 제거, 로컬 상태만 갱신
- 저장 동작을 `해당 항목만 제자리(in-place) 업데이트`도록 변경
	- 저장 시 다른 항목/그룹이 함께 바뀌는 부작용 완화
- 소비/수입 내역에 `대분류 전체 제외` 기능 추가 및 복구
- 제외 처리 요청을 안정적으로 수행하도록 요청 흐름 보강

### 안정화/버그 수정
- API 베이스 URL 연결 실패 시 폴백 로직 보강(8001 → 8000)
- 월별 추이 차트가 비어 보이던 케이스에 대한 표시 안정화
- 거래 ID 타입 차이로 버튼 동작이 막히던 케이스 방어 로직 추가
