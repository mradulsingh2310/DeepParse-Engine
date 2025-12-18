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
  type TooltipProps,
} from "recharts";
import type { ModelChartData, PricingRate } from "../types";

interface StackedChartProps {
  data: ModelChartData[];
  pricing?: Record<string, PricingRate>;
}

const CATEGORY_COLORS = {
  schema: "#10b981",    // Green - Schema compliance
  structure: "#3b82f6", // Blue - Structural accuracy
  semantic: "#8b5cf6",  // Purple - Semantic accuracy
  config: "#f59e0b",    // Amber - Config accuracy
};

export function StackedChart({ data, pricing }: StackedChartProps) {
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
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
        <XAxis
          dataKey="name"
          tick={{ fill: "#475569", fontSize: 11 }}
          axisLine={{ stroke: "#e2e8f0" }}
          tickLine={{ stroke: "#e2e8f0" }}
          angle={-45}
          textAnchor="end"
          height={80}
          interval={0}
        />
        <YAxis
          domain={[0, 100]}
          tick={{ fill: "#475569", fontSize: 12 }}
          axisLine={{ stroke: "#e2e8f0" }}
          tickLine={{ stroke: "#e2e8f0" }}
          label={{
            value: "Weighted Score (%)",
            angle: -90,
            position: "insideLeft",
            fill: "#475569",
            fontSize: 12,
          }}
        />
        <Tooltip
          content={(props: TooltipProps<number, string>) => {
            if (!props.active || !props.payload || props.payload.length === 0) return null;
            const entry = props.payload[0];
            const provider = entry?.payload?.provider;
            const fullName = entry?.payload?.fullName;
            const rate = provider && fullName ? pricing?.[`${provider}:${fullName}`] : undefined;
            const labels: Record<string, string> = {
              schema: "Schema (15%)",
              structure: "Structure (20%)",
              semantic: "Semantic (30%)",
              config: "Config (35%)",
            };

            return (
              <div className="tooltip-card">
                <div className="tooltip-title">
                  {provider && fullName ? `${provider} / ${fullName}` : fullName || "Model"}
                </div>
                {rate && (
                  <div className="tooltip-subtitle">
                    ${rate.input.toFixed(2)}/1M in · ${rate.output.toFixed(2)}/1M out
                  </div>
                )}
                {props.payload.map((p) => (
                  <div className="tooltip-line" key={p.name}>
                    <span
                      className="tooltip-dot"
                      style={{ background: CATEGORY_COLORS[p.name as keyof typeof CATEGORY_COLORS] }}
                    />
                    <span className="tooltip-label">{labels[p.name] || p.name}</span>
                    <span className="tooltip-value">
                      {typeof p.value === "number" ? `${p.value}%` : p.value}
                    </span>
                  </div>
                ))}
                {entry?.payload?.total !== undefined && (
                  <div className="tooltip-line total-line">
                    <span className="tooltip-label">Overall</span>
                    <span className="tooltip-value">{entry.payload.total}%</span>
                  </div>
                )}
              </div>
            );
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
            return <span style={{ color: "#0f172a" }}>{labels[value] || value}</span>;
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

