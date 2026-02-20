# Ingestion & Validation Pipeline (MVP)

## 목적
이 문서는 `data-management-plan.md`를 실제 구현으로 옮기기 위한 ingest 파이프라인 기준서입니다.

## 1. 입력 포맷 표준화
입력 컬럼(원본):
- 날짜, 시간, 타입, 대분류, 소분류, 내용, 금액, 화폐, 결제수단, 메모

정규화 전처리 규칙:
1. `occurred_at = 날짜 + 시간` (KST 파싱)
2. 공백/제어문자 제거, 전각문자 정규화
3. 금액은 정수형으로 파싱 (`1,234` -> `1234`)
4. `currency` 기본값 KRW
5. 비어있는 메모/내용은 NULL 처리

## 2. 타입/부호 정합성 규칙
- expense: `signed_amount <= 0` 기대
- income: `signed_amount >= 0` 기대
- transfer: 부호 자유, 대신 페어링 시 부호 반대 쌍 기대

위배 시:
- 거래는 저장하되 `review_required=true`
- 경고 코드 예시:
  - `SIGN_MISMATCH_EXPENSE_POSITIVE`
  - `SIGN_MISMATCH_INCOME_NEGATIVE`

## 3. 중복 방지 (idempotent import)
`row_hash` 계산 권장 키:
- 날짜 + 시간 + 타입 + 금액 + 화폐 + 결제수단 + 내용

같은 `row_hash` 재유입 시:
- raw_import 중복 삽입 방지
- transaction_entry도 생성 스킵

## 4. 결제수단 정규화
`payment_method.name_original` -> `name_normalized` 맵핑 규칙:
- 연속 공백 축소
- 괄호/특수문자 표준화
- 카드 suffix 통일 (`체크`, `체크카드` 등)

초기에는 룰 기반으로 생성하고, 추후 수동 병합 UI 제공.

## 5. 내계좌이체 페어링
후보 조건:
1. type=transfer
2. same currency
3. abs(signed_amount) 동일
4. occurred_at 간격 5분 이내
5. 결제수단/내용 패턴이 내계좌이체 사전에 포함

성공 시:
- 동일 `transfer_group_id` 부여
- 두 거래 모두 `review_required=false`

실패 시:
- `review_required=true`
- `/transfers/unmatched`로 노출

## 6. 배치 처리 순서
1. 파일 업로드 -> `import_batch` 생성(pending)
2. row별 raw 저장 + hash 계산
3. 정규화 후 `transaction_entry` upsert
4. validation warning 기록
5. transfer pairing
6. batch 상태 completed/failed 업데이트

## 7. 최소 모니터링 지표
- Import 성공률
- 경고 발생률(sign mismatch, uncategorized)
- transfer unmatched 비율
- 자동분류 적중률(수동 교정 대비)
