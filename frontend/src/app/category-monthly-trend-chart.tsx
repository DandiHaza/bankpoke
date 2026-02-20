"use client";

import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type CategoryMonthlyTrendRow = {
  month: number;
  values: Record<string, number>;
};

type CategoryMonthlyTrendChartProps = {
  categories: string[];
  rows: CategoryMonthlyTrendRow[];
  allCategories?: string[];
};

const BAR_COLORS = ["#4e79a7", "#59a14f", "#f28e2b", "#e15759", "#76b7b2", "#b07aa1"];

type TrendChartDatum = {
  monthLabel: string;
  [key: string]: number | string;
};

function formatKrw(value: number): string {
  return `${new Intl.NumberFormat("ko-KR").format(value)}원`;
}

export default function CategoryMonthlyTrendChart({
  categories,
  rows,
  allCategories,
}: CategoryMonthlyTrendChartProps) {
  const selectableCategories = allCategories || categories;
  const [selectedCategories, setSelectedCategories] = useState<Set<string>>(
    new Set(categories)
  );
  const [isEditing, setIsEditing] = useState(false);

  useEffect(() => {
    setSelectedCategories((previous) => {
      const next = new Set(
        Array.from(previous).filter((category) => selectableCategories.includes(category))
      );

      if (next.size === 0) {
        for (const category of categories) {
          next.add(category);
        }
      }

      return next;
    });
  }, [categories, selectableCategories]);

  const toggleCategory = (category: string) => {
    const updated = new Set(selectedCategories);
    if (updated.has(category)) {
      updated.delete(category);
    } else {
      updated.add(category);
    }
    setSelectedCategories(updated);
  };

  const selectAll = () => {
    setSelectedCategories(new Set(selectableCategories));
  };

  const deselectAll = () => {
    setSelectedCategories(new Set());
  };

  const chartData: TrendChartDatum[] = rows.map((row) => {
    const mapped: TrendChartDatum = { monthLabel: `${row.month}월` };
    for (const category of selectableCategories) {
      mapped[category] = row.values[category] ?? 0;
    }
    return mapped;
  });

  const displayCategories = selectableCategories.filter((cat) => selectedCategories.has(cat));
  const effectiveCategories = displayCategories.length > 0 ? displayCategories : categories;

  return (
    <div style={{ width: "100%", display: "grid", gap: 12 }}>
      {!isEditing && (
        <button
          onClick={() => setIsEditing(true)}
          style={{
            padding: "6px 12px",
            background: "#f0f0f0",
            color: "#333",
            border: "1px solid #ddd",
            borderRadius: 6,
            cursor: "pointer",
            fontSize: 13,
            fontWeight: 500,
            width: "fit-content",
          }}
        >
          수정
        </button>
      )}
      {isEditing && (
        <>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <button
              onClick={selectAll}
              style={{
                padding: "6px 12px",
                background: "#2b6ed9",
                color: "#fff",
                border: "none",
                borderRadius: 6,
                cursor: "pointer",
                fontSize: 13,
                fontWeight: 500,
              }}
            >
              모두 선택
            </button>
            <button
              onClick={deselectAll}
              style={{
                padding: "6px 12px",
                background: "#e8e8e8",
                color: "#333",
                border: "none",
                borderRadius: 6,
                cursor: "pointer",
                fontSize: 13,
                fontWeight: 500,
              }}
            >
              모두 해제
            </button>
            <button
              onClick={() => setIsEditing(false)}
              style={{
                padding: "6px 12px",
                background: "#666",
                color: "#fff",
                border: "none",
                borderRadius: 6,
                cursor: "pointer",
                fontSize: 13,
                fontWeight: 500,
                marginLeft: "auto",
              }}
            >
              완료
            </button>
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
              gap: 8,
            }}
          >
            {selectableCategories.map((category, index) => (
              <label
                key={category}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  cursor: "pointer",
                  padding: "6px 8px",
                  borderRadius: 6,
                  background: selectedCategories.has(category) ? "#e8f0ff" : "#f9f9f9",
                  border: `1px solid ${selectedCategories.has(category) ? "#2b6ed9" : "#dce5f4"}`,
                }}
              >
                <input
                  type="checkbox"
                  checked={selectedCategories.has(category)}
                  onChange={() => toggleCategory(category)}
                  style={{ cursor: "pointer" }}
                />
                <span style={{ fontSize: 13, color: "#333" }}>{category}</span>
                <div
                  style={{
                    width: 12,
                    height: 12,
                    borderRadius: 2,
                    background: BAR_COLORS[selectableCategories.indexOf(category) % BAR_COLORS.length],
                  }}
                />
              </label>
            ))}
          </div>
        </>
      )}
      <div style={{ width: "100%", height: 320 }}>
        <ResponsiveContainer>
          <BarChart data={chartData} margin={{ top: 8, right: 12, left: 4, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#d7dfef" />
            <XAxis dataKey="monthLabel" />
            <YAxis tickFormatter={(value: number) => new Intl.NumberFormat("ko-KR").format(value)} />
            <Tooltip formatter={(value: number) => formatKrw(value)} />
            <Legend />
            {effectiveCategories.map((category) => (
              <Bar
                key={category}
                name={category}
                dataKey={category}
                fill={BAR_COLORS[selectableCategories.indexOf(category) % BAR_COLORS.length]}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
