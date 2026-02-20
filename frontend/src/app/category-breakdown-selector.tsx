"use client";

import { useState } from "react";
import CategoryPieChart from "./category-pie-chart";

type BreakdownItem = {
  category: string;
  amount: number;
};

type CategoryBreakdownSelectorProps = {
  allCategories: BreakdownItem[];
};

export default function CategoryBreakdownSelector({
  allCategories,
}: CategoryBreakdownSelectorProps) {
  const categories = allCategories.map((item) => item.category);
  const [selectedCategories, setSelectedCategories] = useState<Set<string>>(
    new Set(categories)
  );

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
    setSelectedCategories(new Set(categories));
  };

  const deselectAll = () => {
    setSelectedCategories(new Set());
  };

  const filteredData = allCategories.filter((item) =>
    selectedCategories.has(item.category)
  );

  function formatKrw(value: number): string {
    return new Intl.NumberFormat("ko-KR").format(value);
  }

  return (
    <div style={{ width: "100%", display: "grid", gap: 12 }}>
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
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))",
          gap: 8,
        }}
      >
        {categories.map((category) => (
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
          </label>
        ))}
      </div>
      {filteredData.length > 0 ? (
        <>
          <CategoryPieChart data={filteredData} />
          <ul style={{ margin: 0, paddingLeft: 20, display: "grid", gap: 6 }}>
            {filteredData.map((item) => (
              <li key={item.category}>
                {item.category}: {formatKrw(item.amount)}원
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p style={{ margin: 0 }}>선택된 카테고리의 지출 데이터가 없습니다.</p>
      )}
    </div>
  );
}
