# 거래 분류 규칙(1차, Rule-based)

## 입력/출력
- 입력 `Transaction`
  - `id,date,amount,description,merchant,method,raw_category,memo`
- 출력 `ClassificationResult`
  - `direction: income|expense`
  - `expense_kind: real|transfer|repayment|saving_invest|refund|cash_withdrawal|other`
  - `category` (expense_kind이 `real`인 경우만 설정)
  - `confidence` (0~1)
  - `rules_fired` (적용된 룰 이름 목록)

## 정책
1. 기본 방향(`direction`)은 금액 부호로 계산
   - amount > 0: `income`
   - else: `expense`
2. 룰 매칭은 `description + merchant + method + raw_category + memo` 텍스트에 대해 수행
3. 충돌 시 우선순위(`priority`)가 가장 높은 룰 1개만 적용
4. “실제지출 제외”를 강하게 적용
   - `transfer_internal` / `repayment_card_or_loan` / `saving_or_invest` / `refund_or_cancel`
   - 위 룰에 걸리면 `expense_kind=real`로 분류하지 않음
5. 룰 미매칭 fallback
   - expense: `real + etc`
   - income: `other`

## 룰 관리
- 룰 파일: `config/rules.yaml`
- 현재는 YAML 파일에 JSON 호환 포맷으로 저장(파서 의존성 최소화)
- 각 룰 필드
  - `name`, `priority`, `pattern(정규식)`, `expense_kind`, `category?(선택)`, `direction?(선택)`, `confidence`

## CLI
데모 10건을 분류해 출력:

```bash
python app/classifier.py --demo
```
