"use client";

import { useState } from "react";

type AddTransactionFormProps = {
  apiBaseUrl: string;
  initialYear: number;
  initialMonth: number;
};

function pad2(value: number): string {
  return value.toString().padStart(2, "0");
}

export default function AddTransactionForm({
  apiBaseUrl,
  initialYear,
  initialMonth,
}: AddTransactionFormProps) {
  const [date, setDate] = useState(`${initialYear}-${pad2(initialMonth)}-01`);
  const [direction, setDirection] = useState<"income" | "expense">("expense");
  const [category, setCategory] = useState("");
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    const parsedAmount = Number.parseInt(amount, 10);
    if (Number.isNaN(parsedAmount) || parsedAmount <= 0) {
      setError("금액은 1 이상 숫자여야 합니다.");
      return;
    }

    if (!date.trim() || !description.trim()) {
      setError("날짜와 내용을 입력해 주세요.");
      return;
    }

    setIsSaving(true);
    setMessage(null);
    setError(null);

    try {
      const response = await fetch(`${apiBaseUrl}/api/transactions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          date,
          direction,
          category,
          description,
          amount: parsedAmount,
          method,
        }),
      });

      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
        setError(payload?.detail ?? "거래 저장에 실패했습니다.");
        return;
      }

      setMessage("저장되었습니다.");
      setAmount("");
      setDescription("");
      setCategory("");
      setMethod("");
      window.location.reload();
    } catch {
      setError("저장 중 네트워크 오류가 발생했습니다.");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div style={{ display: "grid", gap: 8 }}>
      <div style={{ display: "grid", gridTemplateColumns: "120px 1fr 120px 1fr", gap: 8 }}>
        <label htmlFor="tx-date">날짜</label>
        <input id="tx-date" type="date" value={date} onChange={(event) => setDate(event.target.value)} />

        <label htmlFor="tx-direction">구분</label>
        <select
          id="tx-direction"
          value={direction}
          onChange={(event) => setDirection(event.target.value as "income" | "expense")}
        >
          <option value="expense">지출</option>
          <option value="income">수입</option>
        </select>

        <label htmlFor="tx-category">카테고리</label>
        <input
          id="tx-category"
          placeholder="예: 식비>한식"
          value={category}
          onChange={(event) => setCategory(event.target.value)}
        />

        <label htmlFor="tx-description">내용</label>
        <input
          id="tx-description"
          placeholder="예: 점심"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
        />

        <label htmlFor="tx-amount">금액</label>
        <input
          id="tx-amount"
          type="number"
          min={1}
          value={amount}
          onChange={(event) => setAmount(event.target.value)}
        />

        <label htmlFor="tx-method">결제수단</label>
        <input
          id="tx-method"
          placeholder="예: 토스뱅크"
          value={method}
          onChange={(event) => setMethod(event.target.value)}
        />
      </div>

      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <button type="button" onClick={submit} disabled={isSaving}>
          {isSaving ? "저장 중..." : "거래 추가"}
        </button>
        {message ? <span style={{ color: "#1d7a46" }}>{message}</span> : null}
        {error ? <span style={{ color: "#b63a3a" }}>{error}</span> : null}
      </div>
    </div>
  );
}
