"use client";

import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

type CategoryBreakdownItem = {
  category: string;
  amount: number;
};

type CategoryPieChartProps = {
  data: CategoryBreakdownItem[];
};

const PIE_COLORS = ["#4e79a7", "#59a14f", "#f28e2b", "#e15759", "#76b7b2", "#edc948", "#b07aa1", "#ff9da7"];

function formatKrw(value: number): string {
  return `${new Intl.NumberFormat("ko-KR").format(value)}원`;
}

export default function CategoryPieChart({ data }: CategoryPieChartProps) {
  return (
    <div style={{ width: "100%", height: 260 }}>
      <ResponsiveContainer>
        <PieChart>
          <Pie data={data} dataKey="amount" nameKey="category" cx="50%" cy="50%" outerRadius={90}>
            {data.map((item, index) => (
              <Cell key={item.category} fill={PIE_COLORS[index % PIE_COLORS.length]} />
            ))}
          </Pie>
          <Tooltip formatter={(value: number) => formatKrw(value)} />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
