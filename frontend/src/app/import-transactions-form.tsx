"use client";

import { useState } from "react";

type ImportTransactionsFormProps = {
  apiBaseUrl: string;
  initialYear: number;
  initialMonth: number;
};

export default function ImportTransactionsForm({
  apiBaseUrl,
  initialYear,
  initialMonth,
}: ImportTransactionsFormProps) {
  const [file, setFile] = useState<File | null>(null);
  const [replaceMonth, setReplaceMonth] = useState(true);
  const [year, setYear] = useState(String(initialYear));
  const [month, setMonth] = useState(String(initialMonth));
  const [isUploading, setIsUploading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const upload = async () => {
    if (!file) {
      setError("CSV/TSV 파일을 선택해 주세요.");
      return;
    }

    setIsUploading(true);
    setMessage(null);
    setError(null);

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("replace_month", String(replaceMonth));
      if (replaceMonth) {
        formData.append("year", year);
        formData.append("month", month);
      }

      const response = await fetch(`${apiBaseUrl}/api/transactions/import`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
        setError(payload?.detail ?? "파일 가져오기에 실패했습니다.");
        return;
      }

      const payload = (await response.json()) as { imported: number; deleted: number };
      setMessage(`가져오기 완료: ${payload.imported}건${payload.deleted ? ` (기존 ${payload.deleted}건 삭제)` : ""}`);
      window.location.reload();
    } catch {
      setError("파일 가져오기 중 네트워크 오류가 발생했습니다.");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div style={{ display: "grid", gap: 10 }}>
      <input
        type="file"
        accept=".csv,.tsv,text/csv,text/tab-separated-values"
        onChange={(event) => setFile(event.target.files?.[0] ?? null)}
      />

      <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <input
          type="checkbox"
          checked={replaceMonth}
          onChange={(event) => setReplaceMonth(event.target.checked)}
        />
        해당 월 기존 데이터 삭제 후 가져오기
      </label>

      {replaceMonth ? (
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <label htmlFor="import-year">연도</label>
          <input
            id="import-year"
            type="number"
            min={2000}
            max={2100}
            value={year}
            onChange={(event) => setYear(event.target.value)}
            style={{ width: 120 }}
          />
          <label htmlFor="import-month">월</label>
          <input
            id="import-month"
            type="number"
            min={1}
            max={12}
            value={month}
            onChange={(event) => setMonth(event.target.value)}
            style={{ width: 80 }}
          />
        </div>
      ) : null}

      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <button type="button" onClick={upload} disabled={isUploading}>
          {isUploading ? "가져오는 중..." : "파일 가져오기"}
        </button>
        {message ? <span style={{ color: "#1d7a46" }}>{message}</span> : null}
        {error ? <span style={{ color: "#b63a3a" }}>{error}</span> : null}
      </div>

      <p style={{ margin: 0, color: "#5a6480", fontSize: 13 }}>
        지원 형식: cleaned CSV(id,date,amount,...) 또는 원본 TSV(날짜, 금액, 타입, ...)
      </p>
    </div>
  );
}
