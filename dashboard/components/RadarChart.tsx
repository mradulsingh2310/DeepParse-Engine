import React from "react";
import {
  RadarChart as RechartsRadar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from "recharts";
import type { ModelChartData } from "../types";

interface RadarChartProps {
  data: ModelChartData[];
}

const MODEL_COLORS = [
  "#3b82f6", // Blue
  "#10b981", // Green
  "#f59e0b", // Amber
  "#ef4444", // Red
  "#8b5cf6", // Purple
];

export function RadarChart({ data }: RadarChartProps) {
  // Transform data for radar chart
  const radarData = [
    { dimension: "Schema", fullName: "Schema Compliance" },
    { dimension: "Structure", fullName: "Structural Accuracy" },
    { dimension: "Semantic", fullName: "Semantic Accuracy" },
    { dimension: "Config", fullName: "Config Accuracy" },
  ].map((dim) => {
    const point: Record<string, string | number> = {
      dimension: dim.dimension,
      fullName: dim.fullName,
    };
    
    data.forEach((model) => {
      const key = dim.dimension.toLowerCase() as keyof ModelChartData;
      point[model.name] = model[key] as number;
    });
    
    return point;
  });

  if (data.length === 0) {
    return (
      <div className="chart-empty">
        <p>No data available</p>
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={350}>
      <RechartsRadar data={radarData} margin={{ top: 20, right: 30, bottom: 20, left: 30 }}>
        <PolarGrid stroke="#3a3a4e" />
        <PolarAngleAxis
          dataKey="dimension"
          tick={{ fill: "#e5e7eb", fontSize: 12 }}
        />
        <PolarRadiusAxis
          angle={30}
          domain={[0, 100]}
          tick={{ fill: "#9ca3af", fontSize: 10 }}
          tickCount={5}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "#1a1a2e",
            border: "1px solid #3a3a4e",
            borderRadius: "8px",
            color: "#e5e7eb",
          }}
          formatter={(value: number, name: string) => [`${value}%`, name]}
        />
        <Legend
          wrapperStyle={{ paddingTop: "10px" }}
          formatter={(value: string) => (
            <span style={{ color: "#e5e7eb", fontSize: "12px" }}>
              {value.length > 20 ? value.slice(0, 17) + "..." : value}
            </span>
          )}
        />
        {data.map((model, index) => (
          <Radar
            key={model.key}
            name={model.name}
            dataKey={model.name}
            stroke={MODEL_COLORS[index % MODEL_COLORS.length]}
            fill={MODEL_COLORS[index % MODEL_COLORS.length]}
            fillOpacity={0.15}
            strokeWidth={2}
            animationDuration={800}
            animationBegin={index * 150}
          />
        ))}
      </RechartsRadar>
    </ResponsiveContainer>
  );
}

