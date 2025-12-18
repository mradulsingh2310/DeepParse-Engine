import React from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import type { ModelChartData } from "../types";

interface StackedChartProps {
  data: ModelChartData[];
}

const CATEGORY_COLORS = {
  schema: "#10b981",    // Green - Schema compliance
  structure: "#3b82f6", // Blue - Structural accuracy
  semantic: "#8b5cf6",  // Purple - Semantic accuracy
  config: "#f59e0b",    // Amber - Config accuracy
};

export function StackedChart({ data }: StackedChartProps) {
  // Transform data for stacked chart - show weighted contribution
  const stackedData = data.map((d) => ({
    name: d.name.length > 20 ? d.name.slice(0, 17) + "..." : d.name,
    fullName: d.name,
    provider: d.provider,
    // Weight each category according to AGGREGATE_WEIGHTS from scorer.py
    schema: Math.round(d.schema * 0.15),     // 15% weight
    structure: Math.round(d.structure * 0.20), // 20% weight
    semantic: Math.round(d.semantic * 0.30),   // 30% weight
    config: Math.round(d.config * 0.35),       // 35% weight
    total: d.overall,
  }));

  return (
    <ResponsiveContainer width="100%" height={400}>
      <BarChart
        data={stackedData}
        margin={{ top: 20, right: 30, left: 20, bottom: 80 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="#2a2a3e" vertical={false} />
        <XAxis
          dataKey="name"
          tick={{ fill: "#9ca3af", fontSize: 11 }}
          axisLine={{ stroke: "#3a3a4e" }}
          tickLine={{ stroke: "#3a3a4e" }}
          angle={-45}
          textAnchor="end"
          height={80}
          interval={0}
        />
        <YAxis
          domain={[0, 100]}
          tick={{ fill: "#9ca3af", fontSize: 12 }}
          axisLine={{ stroke: "#3a3a4e" }}
          tickLine={{ stroke: "#3a3a4e" }}
          label={{
            value: "Weighted Score (%)",
            angle: -90,
            position: "insideLeft",
            fill: "#9ca3af",
            fontSize: 12,
          }}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "#1a1a2e",
            border: "1px solid #3a3a4e",
            borderRadius: "8px",
            color: "#e5e7eb",
          }}
          formatter={(value: number, name: string) => {
            const labels: Record<string, string> = {
              schema: "Schema (15%)",
              structure: "Structure (20%)",
              semantic: "Semantic (30%)",
              config: "Config (35%)",
            };
            return [`${value}%`, labels[name] || name];
          }}
          labelFormatter={(label: string, payload: Array<{ payload?: { fullName?: string } }>) => {
            if (payload?.[0]?.payload?.fullName) {
              return `Model: ${payload[0].payload.fullName}`;
            }
            return label;
          }}
        />
        <Legend
          wrapperStyle={{ paddingTop: "20px" }}
          formatter={(value: string) => {
            const labels: Record<string, string> = {
              schema: "Schema (15%)",
              structure: "Structure (20%)",
              semantic: "Semantic (30%)",
              config: "Config (35%)",
            };
            return <span style={{ color: "#e5e7eb" }}>{labels[value] || value}</span>;
          }}
        />
        <Bar
          dataKey="schema"
          stackId="a"
          fill={CATEGORY_COLORS.schema}
          radius={[0, 0, 0, 0]}
          animationDuration={800}
        />
        <Bar
          dataKey="structure"
          stackId="a"
          fill={CATEGORY_COLORS.structure}
          radius={[0, 0, 0, 0]}
          animationDuration={800}
          animationBegin={200}
        />
        <Bar
          dataKey="semantic"
          stackId="a"
          fill={CATEGORY_COLORS.semantic}
          radius={[0, 0, 0, 0]}
          animationDuration={800}
          animationBegin={400}
        />
        <Bar
          dataKey="config"
          stackId="a"
          fill={CATEGORY_COLORS.config}
          radius={[4, 4, 0, 0]}
          animationDuration={800}
          animationBegin={600}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}

