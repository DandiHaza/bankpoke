import CategoryPieChart from "./category-pie-chart";
import CategoryMonthlyTrendChart from "./category-monthly-trend-chart";
import ExpenseTransactionsEditor from "./expense-transactions-editor";
import IncomeTransactionsEditor from "./income-transactions-editor";
import ImportTransactionsForm from "./import-transactions-form";
import type { CSSProperties } from "react";

type HealthResponse = {
  status: string;
};

type SummaryResponse = {
  year: number;
  month: number;
  income: number;
  expense: number;
  net_cashflow: number;
  transaction_count: number;
};

type CategoryBreakdownItem = {
  category: string;
  amount: number;
};

type CategoryMonthlyTrendRow = {
  month: number;
  values: Record<string, number>;
};

type MajorCategoryMonthlyTrend = {
  categories: string[];
  rows: CategoryMonthlyTrendRow[];
};

type ExpenseTransactionItem = {
  id: string;
  date: string;
  category: string;
  description: string;
  amount: number;
  method: string;
  excluded: boolean;
};

type ExpenseCategoryTransactions = {
  category: string;
  total_amount: number;
  count: number;
  items: ExpenseTransactionItem[];
};

type IncomeTransactionItem = {
  id: string;
  date: string;
  category: string;
  description: string;
  amount: number;
  method: string;
  excluded: boolean;
};

type IncomeCategoryTransactions = {
  category: string;
  total_amount: number;
  count: number;
  items: IncomeTransactionItem[];
};

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8001";
const TOP_BREAKDOWN_COUNT = 8;
const TOP_TREND_COUNT = 4;
const SECTION_CARD_STYLE: CSSProperties = {
  background: "#ffffff",
  border: "1px solid #dce5f4",
  borderRadius: 12,
  boxShadow: "0 6px 18px rgba(26, 59, 124, 0.08)",
  padding: 16,
};

async function fetchJson<T>(url: string): Promise<T | null> {
  try {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

async function resolveApiBaseUrl(): Promise<string> {
  const candidates = [
    process.env.NEXT_PUBLIC_API_BASE_URL,
    DEFAULT_API_BASE_URL,
    "http://127.0.0.1:8000",
  ].filter((value, index, array): value is string => Boolean(value) && array.indexOf(value) === index);

  for (const candidate of candidates) {
    const health = await fetchJson<HealthResponse>(`${candidate}/api/health`);
    if (health?.status === "ok") {
      return candidate;
    }
  }

  return process.env.NEXT_PUBLIC_API_BASE_URL ?? DEFAULT_API_BASE_URL;
}

function formatKrw(value: number): string {
  return new Intl.NumberFormat("ko-KR").format(value);
}

function toMajorCategory(category: string): string {
  const [major] = category.split(">", 1);
  return major?.trim() || "미분류";
}

function parseIntInRange(
  value: string | string[] | undefined,
  fallback: number,
  min: number,
  max: number,
): number {
  const text = Array.isArray(value) ? value[0] : value;
  if (!text) {
    return fallback;
  }

  const parsed = Number.parseInt(text, 10);
  if (Number.isNaN(parsed) || parsed < min || parsed > max) {
    return fallback;
  }

  return parsed;
}

function buildMajorMonthlyTrend(
  monthlyExpenseGroups: Array<ExpenseCategoryTransactions[] | null>,
  allowedCategories?: string[],
): MajorCategoryMonthlyTrend {
  const totalsByMajor = new Map<string, number>();
  const monthCategoryTotals = new Map<number, Map<string, number>>();

  for (let index = 0; index < monthlyExpenseGroups.length; index += 1) {
    const month = index + 1;
    const groups = monthlyExpenseGroups[index] ?? [];
    const monthTotals = new Map<string, number>();

    for (const group of groups) {
      const major = toMajorCategory(group.category);
      const amount = group.total_amount;
      totalsByMajor.set(major, (totalsByMajor.get(major) ?? 0) + amount);
      monthTotals.set(major, (monthTotals.get(major) ?? 0) + amount);
    }

    monthCategoryTotals.set(month, monthTotals);
  }

  let categories = Array.from(totalsByMajor.entries())
    .sort((left, right) => right[1] - left[1])
    .map(([category]) => category);

  if (allowedCategories) {
    categories = categories.filter((c) => allowedCategories.includes(c));
  } else {
    categories = categories.slice(0, TOP_TREND_COUNT);
  }

  const rows: CategoryMonthlyTrendRow[] = [];
  for (let month = 1; month <= 12; month += 1) {
    const monthTotals = monthCategoryTotals.get(month) ?? new Map<string, number>();
    const values: Record<string, number> = {};
    for (const category of categories) {
      values[category] = monthTotals.get(category) ?? 0;
    }

    if (categories.length > 0) {
      rows.push({ month, values });
    }
  }

  return { categories, rows };
}

export default async function HomePage({
  searchParams,
}: {
  searchParams?: Record<string, string | string[] | undefined>;
}) {
  const today = new Date();
  const defaultYear = today.getFullYear();
  const defaultMonth = today.getMonth() + 1;

  const year = parseIntInRange(searchParams?.year, defaultYear, 2000, 2100);
  const month = parseIntInRange(searchParams?.month, defaultMonth, 1, 12);
  const apiBaseUrl = await resolveApiBaseUrl();

  const [health, summary, categoryBreakdown, expenseByCategory, incomeByCategory, ...monthlyExpenseGroups] = await Promise.all([
    fetchJson<HealthResponse>(`${apiBaseUrl}/api/health`),
    fetchJson<SummaryResponse>(`${apiBaseUrl}/api/summary?year=${year}&month=${month}`),
    fetchJson<CategoryBreakdownItem[]>(
      `${apiBaseUrl}/api/category-breakdown?year=${year}&month=${month}`,
    ),
    fetchJson<ExpenseCategoryTransactions[]>(
      `${apiBaseUrl}/api/expense-transactions?year=${year}&month=${month}&group_level=major`,
    ),
    fetchJson<IncomeCategoryTransactions[]>(
      `${apiBaseUrl}/api/income-transactions?year=${year}&month=${month}&group_level=major`,
    ),
    ...Array.from({ length: 12 }, (_unused, monthIndex) =>
      fetchJson<ExpenseCategoryTransactions[]>(
        `${apiBaseUrl}/api/expense-transactions?year=${year}&month=${monthIndex + 1}&group_level=major`,
      ),
    ),
  ]);

  const majorBreakdownMap = new Map<string, number>();
  for (const item of categoryBreakdown ?? []) {
    const major = toMajorCategory(item.category);
    majorBreakdownMap.set(major, (majorBreakdownMap.get(major) ?? 0) + item.amount);
  }

  const majorBreakdownArray = Array.from(majorBreakdownMap.entries())
    .map(([category, amount]) => ({ category, amount }))
    .sort((left, right) => right.amount - left.amount);

  const topBreakdown = majorBreakdownArray.slice(0, TOP_BREAKDOWN_COUNT);

  const monthlyTrendMajor = buildMajorMonthlyTrend(
    monthlyExpenseGroups,
    majorBreakdownArray.map((item) => item.category),
  );

  return (
    <main style={{ maxWidth: 980, display: "grid", gap: 16 }}>
      <h1 style={{ margin: 0, color: "#1b4d8a" }}>BankPoke</h1>
      <p style={{ margin: 0, color: health?.status === "ok" ? "#1d7a46" : "#b63a3a" }}>
        백엔드 연결 상태: {health?.status === "ok" ? "정상" : "연결 실패"}
      </p>

      <form
        method="get"
        style={{
          ...SECTION_CARD_STYLE,
          display: "grid",
          gridTemplateColumns: "auto 120px auto 80px auto",
          alignItems: "center",
          gap: 8,
        }}
      >
        <label htmlFor="year">연도</label>
        <input
          id="year"
          name="year"
          type="number"
          min={2000}
          max={2100}
          defaultValue={year}
          style={{ padding: "6px 8px" }}
        />
        <label htmlFor="month">월</label>
        <input
          id="month"
          name="month"
          type="number"
          min={1}
          max={12}
          defaultValue={month}
          style={{ padding: "6px 8px" }}
        />
        <button
          type="submit"
          style={{
            padding: "6px 10px",
            background: "#2b6ed9",
            color: "#ffffff",
            border: "none",
            borderRadius: 8,
            cursor: "pointer",
          }}
        >
          조회
        </button>
      </form>

      <section style={SECTION_CARD_STYLE}>
        <h2 style={{ margin: "0 0 8px" }}>CSV/TSV 파일 가져오기</h2>
        <ImportTransactionsForm apiBaseUrl={apiBaseUrl} initialYear={year} initialMonth={month} />
      </section>

      <section style={SECTION_CARD_STYLE}>
        <h2 style={{ margin: "0 0 8px" }}>{summary?.year ?? year}년 {summary?.month ?? month}월 거래요약</h2>
        {summary ? (
          <ul style={{ margin: 0, paddingLeft: 20, display: "grid", gap: 6 }}>
            <li>수입: {formatKrw(summary.income)}원</li>
            <li>지출: {formatKrw(summary.expense)}원</li>
            <li>순현금흐름: {formatKrw(summary.net_cashflow)}원</li>
            <li>거래 건수: {summary.transaction_count}건</li>
          </ul>
        ) : (
          <p style={{ margin: 0 }}>월 요약 데이터를 불러오지 못했습니다.</p>
        )}
      </section>

      <section style={SECTION_CARD_STYLE}>
        <h2 style={{ margin: "0 0 8px" }}>지출 분석</h2>
        {topBreakdown.length > 0 ? (
          <>
            <CategoryPieChart data={topBreakdown} />
            <ul style={{ margin: 0, paddingLeft: 20, display: "grid", gap: 6 }}>
              {topBreakdown.map((item) => (
                <li key={item.category}>
                  {item.category}: {formatKrw(item.amount)}원
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p style={{ margin: 0 }}>카테고리 지출 데이터가 없습니다.</p>
        )}
      </section>

      <section style={SECTION_CARD_STYLE}>
        <h2 style={{ margin: "0 0 8px" }}>지출 월별 추이</h2>
        {monthlyTrendMajor && monthlyTrendMajor.categories.length > 0 && monthlyTrendMajor.rows.length > 0 ? (
          <CategoryMonthlyTrendChart
            categories={monthlyTrendMajor.categories}
            rows={monthlyTrendMajor.rows}
            allCategories={majorBreakdownArray.map((item) => item.category)}
          />
        ) : (
          <p style={{ margin: 0 }}>월별 추이 데이터가 없습니다.</p>
        )}
      </section>

      <section style={SECTION_CARD_STYLE}>
        <h2 style={{ margin: "0 0 8px" }}>소비 내역</h2>
        {expenseByCategory && expenseByCategory.length > 0 ? (
          <ExpenseTransactionsEditor apiBaseUrl={apiBaseUrl} groups={expenseByCategory} />
        ) : (
          <p style={{ margin: 0 }}>분류별 소비 내역이 없습니다.</p>
        )}
      </section>

      <section style={SECTION_CARD_STYLE}>
        <h2 style={{ margin: "0 0 8px" }}>수입 내역</h2>
        {incomeByCategory && incomeByCategory.length > 0 ? (
          <IncomeTransactionsEditor apiBaseUrl={apiBaseUrl} groups={incomeByCategory} />
        ) : (
          <p style={{ margin: 0 }}>분류별 수입 내역이 없습니다.</p>
        )}
      </section>
    </main>
  );
}
