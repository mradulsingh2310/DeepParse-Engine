import React from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  LabelList,
} from "recharts";
import type { ModelChartData } from "../types";

interface OverallChartProps {
  data: ModelChartData[];
}

// Color scale based on score
function getScoreColor(score: number): string {
  if (score >= 80) return "#10b981"; // Green
  if (score >= 60) return "#f59e0b"; // Amber
  if (score >= 40) return "#f97316"; // Orange
  return "#ef4444"; // Red
}

// Provider colors
const PROVIDER_COLORS: Record<string, string> = {
  bedrock: "#ff9900",
  google: "#4285f4",
  deepseek: "#6366f1",
  anthropic: "#d97706",
  openai: "#10a37f",
};

function getProviderColor(provider: string): string {
  return PROVIDER_COLORS[provider.toLowerCase()] || "#8b5cf6";
}

export function OverallChart({ data }: OverallChartProps) {
  return (
    <ResponsiveContainer width="100%" height={Math.max(300, data.length * 45)}>
      <BarChart
        data={data}
        layout="vertical"
        margin={{ top: 10, right: 80, left: 10, bottom: 10 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
        <XAxis
          type="number"
          domain={[0, 100]}
          tick={{ fill: "#475569", fontSize: 12 }}
          axisLine={{ stroke: "#e2e8f0" }}
          tickLine={{ stroke: "#e2e8f0" }}
        />
        <YAxis
          type="category"
          dataKey="name"
          width={180}
          tick={{ fill: "#0f172a", fontSize: 12 }}
          axisLine={{ stroke: "#e2e8f0" }}
          tickLine={false}
          tickFormatter={(value) => {
            // Truncate long model names
            return value.length > 25 ? value.slice(0, 22) + "..." : value;
          }}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "#ffffff",
            border: "1px solid #e2e8f0",
            borderRadius: "8px",
            color: "#0f172a",
          }}
          formatter={(value: number) => [
            `${value}%`,
            `Overall Score`,
          ]}
          labelFormatter={(label: string) => `Model: ${label}`}
        />
        <Bar
          dataKey="overall"
          radius={[0, 4, 4, 0]}
          animationDuration={800}
          animationBegin={0}
        >
          {data.map((entry, index) => (
            <Cell
              key={`cell-${index}`}
              fill={getScoreColor(entry.overall)}
              style={{ filter: "brightness(1.1)" }}
            />
          ))}
          <LabelList
            dataKey="overall"
            position="right"
            formatter={(value: number) => `${value}%`}
            fill="#e5e7eb"
            fontSize={12}
            fontWeight={600}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

