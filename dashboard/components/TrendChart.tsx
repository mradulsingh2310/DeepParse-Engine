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
} from "recharts";
import type { EvaluationCache, TrendDataPoint } from "../types";

interface TrendChartProps {
  cache: EvaluationCache | null;
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

export function TrendChart({ cache }: TrendChartProps) {
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
        <CartesianGrid strokeDasharray="3 3" stroke="#2a2a3e" />
        <XAxis
          dataKey="date"
          tick={{ fill: "#9ca3af", fontSize: 11 }}
          axisLine={{ stroke: "#3a3a4e" }}
          tickLine={{ stroke: "#3a3a4e" }}
        />
        <YAxis
          domain={[0, 100]}
          tick={{ fill: "#9ca3af", fontSize: 12 }}
          axisLine={{ stroke: "#3a3a4e" }}
          tickLine={{ stroke: "#3a3a4e" }}
          label={{
            value: "Score (%)",
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
          formatter={(value: number, name: string) => [`${value}%`, name]}
          labelFormatter={(label: string) => `Date: ${label}`}
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

