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
  type TooltipProps,
} from "recharts";
import type { ModelChartData, PricingRate } from "../types";

interface RadarChartProps {
  data: ModelChartData[];
  pricing?: Record<string, PricingRate>;
}

const MODEL_COLORS = [
  "#3b82f6", // Blue
  "#10b981", // Green
  "#f59e0b", // Amber
  "#ef4444", // Red
  "#8b5cf6", // Purple
];

const SCORE_DESCRIPTIONS: Record<string, string> = {
  Schema: "Schema compliance: JSON follows the expected schema (required fields, types, enums).",
  Structure: "Structural accuracy: correct sections/fields present and matched.",
  Semantic: "Semantic accuracy: field names/options mean the same (LLM-judged).",
  Config: "Config accuracy: mandatory, notes, attachments, and work-order settings match.",
};

function CustomTooltip({
  active,
  payload,
  label,
  pricing,
  providerByName,
}: TooltipProps<number, string> & {
  pricing?: Record<string, PricingRate>;
  providerByName: Record<string, string>;
}) {
  if (!active || !payload || payload.length === 0) return null;

  const fullName = (payload[0]?.payload as { fullName?: string })?.fullName ?? label;
  const description = SCORE_DESCRIPTIONS[label] ?? "";
  const modelName = payload[0]?.name;
  const provider = modelName ? providerByName[modelName] : undefined;
  const rate = provider && modelName ? pricing?.[`${provider}:${modelName}`] : undefined;

  return (
    <div className="tooltip-card">
      <div className="tooltip-title">{fullName}</div>
      <div className="tooltip-subtitle">{description}</div>
      {rate && (
        <div className="tooltip-subtitle">
          {provider} / {modelName} — ${rate.input.toFixed(2)}/1M in · ${rate.output.toFixed(2)}/1M out
        </div>
      )}
      {payload.map((entry) => (
        <div className="tooltip-line" key={entry.name}>
          <span
            className="tooltip-dot"
            style={{
              backgroundColor: entry.color,
            }}
          />
          <span className="tooltip-label">{entry.name}</span>
          <span className="tooltip-value">
            {typeof entry.value === "number"
              ? `${entry.value.toFixed(1).replace(/\\.0$/, "")}%`
              : entry.value}
          </span>
        </div>
      ))}
    </div>
  );
}

export function RadarChart({ data, pricing }: RadarChartProps) {
  const providerByName = React.useMemo(() => {
    const map: Record<string, string> = {};
    data.forEach((m) => {
      map[m.name] = m.provider;
    });
    return map;
  }, [data]);

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
        <PolarGrid stroke="#e2e8f0" />
        <PolarAngleAxis
          dataKey="dimension"
          tick={{ fill: "#0f172a", fontSize: 12 }}
        />
        <PolarRadiusAxis
          angle={30}
          domain={[0, 100]}
          tick={{ fill: "#475569", fontSize: 10 }}
          tickCount={5}
        />
        <Tooltip content={<CustomTooltip pricing={pricing} providerByName={providerByName} />} />
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

