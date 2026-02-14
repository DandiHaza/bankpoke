# 가계부 데이터 관리 설계 제안

## 1) 핵심 목표
- **원본 보존**: CSV/엑셀 원본은 절대 수정하지 않고 `raw_import`로 저장.
- **정규화 저장**: 화면/통계/검색은 정규화된 `transaction` 중심으로 조회.
- **추적 가능성**: 한 건의 거래가 어디서 왔고 어떤 규칙으로 정리됐는지 이력 보존.
- **자동 분류 + 수동 교정**: 자동화하되 사용자가 즉시 수정 가능하게 설계.

---

## 2) 현재 데이터에서 보이는 특성
샘플 데이터 기준으로 아래 특성이 뚜렷합니다.

1. **이체가 매우 많고, 입출금 쌍으로 기록됨**
   - 예: `세이프박스 +120000` / `내계좌로 이체 -120000`
   - 내부자산 이동은 소비/수입 통계에서 제외 필요.

2. **금액 부호 품질 이슈 가능성**
   - 타입은 `지출`인데 금액이 양수인 케이스(예: `쿠팡 7990`)가 보임.
   - 정합성 검증 규칙 필수.

3. **대분류/소분류의 `미분류` 비중 높음**
   - 초기엔 원본 우선 저장 + 규칙 기반 자동 분류가 중요.

4. **결제수단 표현이 길고 중복 가능성 높음**
   - 예: 카드명/간편결제명이 다양하여 정규화 필요.

5. **소액 반복 수입/저축 이벤트 존재**
   - 복권 당첨, 동전모으기, 캐시백 등은 별도 태그로 추적 시 유용.

---

## 3) 권장 데이터 모델 (MVP)

### A. 원본 테이블
### `raw_import`
- `id` (PK)
- `source_type` (`csv`, `xlsx`, `manual`)
- `source_filename`
- `imported_at`
- `raw_payload` (JSON/JSONB, 한 행 원본)
- `row_hash` (중복 방지용)

> 역할: 재처리/디버깅/감사 대응용 원본 보관.

### B. 정규화 거래 테이블
### `transaction`
- `id` (PK)
- `occurred_at` (datetime, `날짜+시간` 결합)
- `type` (`income`, `expense`, `transfer`)
- `direction` (`in`, `out`, `neutral`)  
  - 타입과 금액 부호가 충돌할 때 보정 기준으로 사용
- `amount` (절대값)
- `signed_amount` (원본 부호 반영)
- `currency` (기본 KRW)
- `merchant_or_counterparty` (`내용`)
- `category_major_id` (FK)
- `category_minor_id` (FK)
- `payment_method_id` (FK)
- `note`
- `raw_import_id` (FK)
- `status` (`active`, `deleted`, `merged`)

### C. 분류 마스터
### `category_major`
- `id`, `name`, `type_scope` (`expense/income/common`)

### `category_minor`
- `id`, `major_id`, `name`

### D. 결제수단 마스터
### `payment_method`
- `id`
- `name_original`
- `name_normalized`
- `method_kind` (`bank_account`, `card`, `easy_pay`, `cash`, `etc`)
- `issuer`
- `last4` (있다면)

### E. 계좌/자산 관점(선택 권장)
### `asset_account`
- `id`, `name`, `account_type` (`checking`, `savings`, `pocket`, `pay_wallet`)

### `transaction_account_link`
- `transaction_id`
- `asset_account_id`
- `role` (`source`, `destination`, `payment`)

> 추후 순자산 리포트(계좌 잔액 추이)까지 확장 가능.

---

## 4) 이체(transfer) 처리 규칙
가계부 정확도를 위해 가장 중요합니다.

1. **내계좌이체 자동 페어링**
   - 조건 예시:
     - 같은 날짜/근접 시간(예: ±5분)
     - 금액 절대값 동일
     - 통화 동일
     - 상대 설명 (`세이프박스`, `내계좌로 이체`) 패턴 매칭
   - 결과:
     - `transfer_group_id`로 묶기
     - 소비/수입 합계에서 제외

2. **외부 송금(친구 정산 등)은 transfer로 유지하되 분석 분리**
   - `transfer_external` 플래그 또는 별도 하위분류로 분리.

3. **페어링 실패 건 큐잉**
   - 자동 페어링 실패 건은 “검토 필요” 목록으로 노출.

---

## 5) 정합성(데이터 품질) 규칙
수입/지출 통계가 틀어지지 않게 ingest 단계에서 검사합니다.

- `type=expense`인데 `signed_amount > 0`이면 경고.
- `type=income`인데 `signed_amount < 0`이면 경고.
- 동일 `occurred_at + signed_amount + merchant + payment_method` 중복 시 후보 처리.
- `currency != KRW` 발생 시 환율 테이블 필요 플래그.
- `미분류` 비율(예: 30% 이상) 시 자동 분류 모델/룰 개선 알림.

---

## 6) 자동 분류 전략 (룰 기반 → ML 보조)

1. **1단계(필수): 룰 기반**
   - 키워드 사전:
     - `쿠팡`, `더마켓` → 식비/쇼핑 후보
     - `한국전력공사` → 주거/통신-전기세
     - `우아한형제들`, `쿠팡이츠` → 식비-배달
   - 결제수단 기반 룰:
     - 특정 카드 사용 시 우선 카테고리 힌트 부여.

2. **2단계(선택): 사용자 교정 학습**
   - 사용자가 수정한 분류를 `category_feedback`에 저장.
   - 이후 동일 가맹점/키워드 등장 시 개인화 우선 적용.

---

## 7) 조회/리포트 관점에서의 최소 API
- `GET /transactions?from&to&type&category&method`
- `GET /summary/monthly` (수입/지출/이체/순현금흐름)
- `GET /summary/categories` (대/소분류 합계)
- `GET /transfers/unmatched`
- `POST /transactions/:id/reclassify`
- `POST /imports` (파일 업로드 + 비동기 파싱)

---

## 8) 운영 관점 권장사항
- 모든 금액은 내부적으로 `정수(원 단위)` 저장.
- 타임존은 `Asia/Seoul` 고정 후 UTC 병행 저장.
- 원본 행 해시(`row_hash`)로 **멱등 import** 보장.
- 월 마감 스냅샷 테이블(`monthly_snapshot`)을 두면 통계 성능이 좋아짐.

---

## 9) 바로 시작 가능한 구현 순서
1. `raw_import`, `transaction`, `category`, `payment_method` 스키마 우선 구축.
2. CSV Importer + 정합성 검사 + 오류 리포트 JSON 구현.
3. `내계좌이체` 페어링 로직(규칙 기반) 구현.
4. 월별 요약 API 2~3개 구현.
5. 분류 교정 UI/엔드포인트 추가.

이 순서면 빠르게 MVP를 만들고, 이후 정확도(자동분류/페어링)와 분석(자산추이)을 단계적으로 고도화할 수 있습니다.
