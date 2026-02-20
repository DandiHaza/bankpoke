# 토스 대체 MVP 6개 PR 계획

## PR1 — 프로젝트 스캐폴딩 (현재 PR)
- 변경 파일
  - `backend/app/main.py`, `backend/app/db.py`, `backend/requirements.txt`, `backend/tests/test_health.py`
  - `frontend/package.json`, `frontend/src/app/*`, TypeScript/Next 설정 파일
- 실행 커맨드
  - `pip install -r backend/requirements.txt`
  - `PYTHONPATH=backend pytest -q backend/tests`
  - `uvicorn app.main:app --app-dir backend --reload --port 8000`
  - `cd frontend && npm install && npm run dev`
- 완료 조건
  - 백엔드 health endpoint 정상 응답
  - 프론트 dev 서버 실행 및 기본 화면 렌더

## PR2 — CSV 업로드/적재 API
- 변경 파일(예정)
  - `backend/app/routes/upload.py`, `backend/app/services/ingest.py`, `backend/tests/test_upload.py`
- 실행 커맨드(예정)
  - `curl -F file=@data/cleaned_transactions.csv http://localhost:8000/api/upload`
- 완료 조건(예정)
  - CSV 적재 성공, 중복 ID 처리 정책 반영

## PR3 — 분류기 실행 + DB 저장
- 변경 파일(예정)
  - `backend/app/services/classify.py`, `backend/app/routes/classify.py`, `backend/tests/test_classify_api.py`
- 실행 커맨드(예정)
  - `curl -X POST http://localhost:8000/api/classify/run`
- 완료 조건(예정)
  - 적재 거래에 classification row 저장

## PR4 — summary 집계 API
- 변경 파일(예정)
  - `backend/app/routes/summary.py`, `backend/app/services/summary.py`, `backend/tests/test_summary_api.py`
- 실행 커맨드(예정)
  - `curl "http://localhost:8000/api/summary?from=2026-01&to=2026-12"`
- 완료 조건(예정)
  - `monthly_totals`, `category_trend`, `category_share` 스키마 응답

## PR5 — 대시보드 UI 구현
- 변경 파일(예정)
  - `frontend/src/app/page.tsx`, `frontend/src/components/*`
- 실행 커맨드(예정)
  - `cd frontend && npm run dev`
- 완료 조건(예정)
  - 월 범위 선택, 카드 3개, 멀티라인 추이, 비중 차트, 테이블 + 실제지출 필터 구현

## PR6 — E2E 정리/문서화
- 변경 파일(예정)
  - `README.md`, `docs/*`, 통합 테스트
- 실행 커맨드(예정)
  - 전체 실행/검증 명령 모음 제공
- 완료 조건(예정)
  - 로컬에서 업로드→분류→요약→대시보드 확인 가능한 MVP 완성
