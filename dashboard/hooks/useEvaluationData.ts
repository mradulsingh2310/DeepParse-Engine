import { useState, useEffect, useCallback } from "react";
import type { EvaluationCache, EvaluationSummary, ModelChartData, CachedModelResult } from "../types";

interface UseEvaluationDataResult {
  summaries: EvaluationSummary[];
  selectedCache: EvaluationCache | null;
  chartData: ModelChartData[];
  loading: boolean;
  error: string | null;
  isAggregated: boolean;
  refetch: () => Promise<void>;
  selectSource: (source: string) => Promise<void>;
}

export function useEvaluationData(): UseEvaluationDataResult {
  const [summaries, setSummaries] = useState<EvaluationSummary[]>([]);
  const [selectedCache, setSelectedCache] = useState<EvaluationCache | null>(null);
  const [chartData, setChartData] = useState<ModelChartData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isAggregated, setIsAggregated] = useState(false);

  // Transform cache data to chart-friendly format
  const transformToChartData = useCallback((cache: EvaluationCache): ModelChartData[] => {
    return Object.entries(cache.models).map(([key, model]) => {
      const avgScore = model.run_count > 0 ? model.total_overall_score / model.run_count : 0;
      const avgSchema = model.run_count > 0 ? model.total_schema_compliance / model.run_count : 0;
      const avgStructure = model.run_count > 0 ? model.total_structural_accuracy / model.run_count : 0;
      const avgSemantic = model.run_count > 0 ? model.total_semantic_accuracy / model.run_count : 0;
      const avgConfig = model.run_count > 0 ? model.total_config_accuracy / model.run_count : 0;
      const avgCost = model.run_count > 0 ? (model.total_cost || 0) / model.run_count : 0;

      return {
        key,
        name: model.model_id,
        provider: model.provider,
        overall: Math.round(avgScore * 100),
        schema: Math.round(avgSchema * 100),
        structure: Math.round(avgStructure * 100),
        semantic: Math.round(avgSemantic * 100),
        config: Math.round(avgConfig * 100),
        runCount: model.run_count,
        totalCost: model.total_cost || 0,
        averageCost: avgCost,
        totalInputTokens: model.total_input_tokens || 0,
        totalOutputTokens: model.total_output_tokens || 0,
      };
    }).sort((a, b) => b.overall - a.overall);
  }, []);

  // Aggregate multiple caches into a single chart data set
  const aggregateCaches = useCallback((caches: EvaluationCache[]): ModelChartData[] => {
    const aggregated: Record<string, CachedModelResult> = {};

    // Combine models across all caches
    caches.forEach((cache) => {
      Object.entries(cache.models).forEach(([key, model]) => {
        if (aggregated[key]) {
          // Merge: sum up totals and run counts
          const existing = aggregated[key];
          aggregated[key] = {
            ...existing,
            run_count: existing.run_count + model.run_count,
            total_schema_compliance: existing.total_schema_compliance + model.total_schema_compliance,
            total_structural_accuracy: existing.total_structural_accuracy + model.total_structural_accuracy,
            total_semantic_accuracy: existing.total_semantic_accuracy + model.total_semantic_accuracy,
            total_config_accuracy: existing.total_config_accuracy + model.total_config_accuracy,
            total_overall_score: existing.total_overall_score + model.total_overall_score,
            total_cost: (existing.total_cost || 0) + (model.total_cost || 0),
            total_input_tokens: (existing.total_input_tokens || 0) + (model.total_input_tokens || 0),
            total_output_tokens: (existing.total_output_tokens || 0) + (model.total_output_tokens || 0),
            best_score: Math.max(existing.best_score, model.best_score),
            latest_score: model.latest_score > existing.latest_score ? model.latest_score : existing.latest_score,
            latest_run_timestamp: model.latest_run_timestamp && existing.latest_run_timestamp
              ? (model.latest_run_timestamp > existing.latest_run_timestamp ? model.latest_run_timestamp : existing.latest_run_timestamp)
              : model.latest_run_timestamp || existing.latest_run_timestamp,
          };
        } else {
          // First occurrence of this model
          aggregated[key] = { ...model };
        }
      });
    });

    // Transform aggregated data to chart format
    return Object.entries(aggregated).map(([key, model]) => {
      const avgScore = model.run_count > 0 ? model.total_overall_score / model.run_count : 0;
      const avgSchema = model.run_count > 0 ? model.total_schema_compliance / model.run_count : 0;
      const avgStructure = model.run_count > 0 ? model.total_structural_accuracy / model.run_count : 0;
      const avgSemantic = model.run_count > 0 ? model.total_semantic_accuracy / model.run_count : 0;
      const avgConfig = model.run_count > 0 ? model.total_config_accuracy / model.run_count : 0;
      const avgCost = model.run_count > 0 ? (model.total_cost || 0) / model.run_count : 0;

      return {
        key,
        name: model.model_id,
        provider: model.provider,
        overall: Math.round(avgScore * 100),
        schema: Math.round(avgSchema * 100),
        structure: Math.round(avgStructure * 100),
        semantic: Math.round(avgSemantic * 100),
        config: Math.round(avgConfig * 100),
        runCount: model.run_count,
        totalCost: model.total_cost || 0,
        averageCost: avgCost,
        totalInputTokens: model.total_input_tokens || 0,
        totalOutputTokens: model.total_output_tokens || 0,
      };
    }).sort((a, b) => b.overall - a.overall);
  }, []);

  // Fetch all evaluation summaries
  const fetchSummaries = useCallback(async () => {
    try {
      const response = await fetch("/api/evaluations");
      if (!response.ok) throw new Error("Failed to fetch evaluations");
      const data = await response.json();
      setSummaries(data.evaluations || []);
      return data.evaluations || [];
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setError(message);
      return [];
    }
  }, []);

  // Fetch specific cache by source name
  const selectSource = useCallback(async (source: string) => {
    setLoading(true);
    try {
      // Special case: "all" means aggregate all files
      if (source === "all" || source === "") {
        const evals = await fetchSummaries();
        if (evals.length === 0) {
          setSelectedCache(null);
          setChartData([]);
          setIsAggregated(false);
          setLoading(false);
          return;
        }

        // Fetch all caches
        const caches: EvaluationCache[] = [];
        for (const evalSummary of evals) {
          const sourceStem = evalSummary.source_file.split("/").pop()?.replace(".json", "") || evalSummary.source_file;
          try {
            const response = await fetch(`/api/evaluations/${sourceStem}`);
            if (response.ok) {
              const cache: EvaluationCache = await response.json();
              caches.push(cache);
            }
          } catch (err) {
            console.warn(`Failed to fetch cache for ${sourceStem}:`, err);
          }
        }

        if (caches.length > 0) {
          setSelectedCache(null); // No single cache selected in aggregated view
          setChartData(aggregateCaches(caches));
          setIsAggregated(true);
        } else {
          setSelectedCache(null);
          setChartData([]);
          setIsAggregated(false);
        }
        setError(null);
      } else {
        // Fetch specific cache
        const sourceStem = source.split("/").pop()?.replace(".json", "") || source;
        const response = await fetch(`/api/evaluations/${sourceStem}`);
        if (!response.ok) throw new Error("Failed to fetch cache");
        const cache: EvaluationCache = await response.json();
        setSelectedCache(cache);
        setChartData(transformToChartData(cache));
        setIsAggregated(false);
        setError(null);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [transformToChartData, aggregateCaches, fetchSummaries]);

  // Initial fetch and auto-select aggregated view
  const refetch = useCallback(async () => {
    setLoading(true);
    const evals = await fetchSummaries();
    if (evals.length > 0) {
      // Default to aggregated view
      await selectSource("all");
    } else {
      setLoading(false);
    }
  }, [fetchSummaries, selectSource]);

  useEffect(() => {
    refetch();
  }, []);

  return {
    summaries,
    selectedCache,
    chartData,
    loading,
    error,
    isAggregated,
    refetch,
    selectSource,
  };
}

