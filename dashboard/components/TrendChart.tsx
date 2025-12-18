import React, { useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  type TooltipProps,
} from "recharts";
import type { EvaluationCache, TrendDataPoint, PricingRate } from "../types";

interface TrendChartProps {
  cache: EvaluationCache | null;
  pricing?: Record<string, PricingRate>;
}

const MODEL_COLORS = [
  "#3b82f6", // Blue
  "#10b981", // Green
  "#f59e0b", // Amber
  "#ef4444", // Red
  "#8b5cf6", // Purple
  "#ec4899", // Pink
  "#06b6d4", // Cyan
];

export function TrendChart({ cache, pricing }: TrendChartProps) {
  const { trendData, modelKeys } = useMemo(() => {
    if (!cache) {
      return { trendData: [], modelKeys: [] };
    }

    // Collect all timestamps and scores
    const timestampMap = new Map<string, Record<string, number>>();
    const keys: string[] = [];

    Object.entries(cache.models).forEach(([key, model]) => {
      keys.push(key);
      
      model.run_history.forEach((run) => {
        const date = new Date(run.timestamp).toLocaleDateString();
        
        if (!timestampMap.has(run.timestamp)) {
          timestampMap.set(run.timestamp, { date } as any);
        }
        
        const entry = timestampMap.get(run.timestamp)!;
        entry[key] = Math.round(run.overall_score * 100);
      });
    });

    // Convert to array and sort by timestamp
    const data: TrendDataPoint[] = Array.from(timestampMap.entries())
      .sort(([a], [b]) => new Date(a).getTime() - new Date(b).getTime())
      .map(([timestamp, values]) => ({
        timestamp,
        date: String(values.date ?? ""),
        ...values,
      }));

    return { trendData: data, modelKeys: keys };
  }, [cache]);

  if (trendData.length === 0) {
    return (
      <div className="chart-empty">
        <p>No run history available</p>
        <span>Run the pipeline multiple times to see trends</span>
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart
        data={trendData}
        margin={{ top: 20, right: 30, left: 20, bottom: 10 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis
          dataKey="date"
          tick={{ fill: "#475569", fontSize: 11 }}
          axisLine={{ stroke: "#e2e8f0" }}
          tickLine={{ stroke: "#e2e8f0" }}
        />
        <YAxis
          domain={[0, 100]}
          tick={{ fill: "#475569", fontSize: 12 }}
          axisLine={{ stroke: "#e2e8f0" }}
          tickLine={{ stroke: "#e2e8f0" }}
          label={{
            value: "Score (%)",
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
            const modelKey = entry?.name as string;
            const rate = modelKey ? pricing?.[modelKey] : undefined;
            const value = entry?.value;
            return (
              <div className="tooltip-card">
                <div className="tooltip-title">{modelKey}</div>
                {rate && (
                  <div className="tooltip-subtitle">
                    ${rate.input.toFixed(2)}/1M in · ${rate.output.toFixed(2)}/1M out
                  </div>
                )}
                <div className="tooltip-line">
                  <span className="tooltip-dot" style={{ background: entry.color }} />
                  <span className="tooltip-label">Score</span>
                  <span className="tooltip-value">
                    {typeof value === "number" ? `${value}%` : value}
                  </span>
                </div>
                {props.label && (
                  <div className="tooltip-subtitle">Date: {props.label}</div>
                )}
              </div>
            );
          }}
        />
        <Legend
          wrapperStyle={{ paddingTop: "10px" }}
          formatter={(value: string) => (
            <span style={{ color: "#e5e7eb", fontSize: "11px" }}>
              {value.length > 25 ? value.slice(0, 22) + "..." : value}
            </span>
          )}
        />
        {modelKeys.map((key, index) => (
          <Line
            key={key}
            type="monotone"
            dataKey={key}
            stroke={MODEL_COLORS[index % MODEL_COLORS.length]}
            strokeWidth={2}
            dot={{ fill: MODEL_COLORS[index % MODEL_COLORS.length], r: 4 }}
            activeDot={{ r: 6 }}
            animationDuration={800}
            animationBegin={index * 100}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

