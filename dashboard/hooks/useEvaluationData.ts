import { useState, useEffect, useCallback } from "react";
import type { EvaluationCache, EvaluationSummary, ModelChartData } from "../types";

interface UseEvaluationDataResult {
  summaries: EvaluationSummary[];
  selectedCache: EvaluationCache | null;
  chartData: ModelChartData[];
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
  selectSource: (source: string) => Promise<void>;
}

export function useEvaluationData(): UseEvaluationDataResult {
  const [summaries, setSummaries] = useState<EvaluationSummary[]>([]);
  const [selectedCache, setSelectedCache] = useState<EvaluationCache | null>(null);
  const [chartData, setChartData] = useState<ModelChartData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Transform cache data to chart-friendly format
  const transformToChartData = useCallback((cache: EvaluationCache): ModelChartData[] => {
    return Object.entries(cache.models).map(([key, model]) => {
      const avgScore = model.run_count > 0 ? model.total_overall_score / model.run_count : 0;
      const avgSchema = model.run_count > 0 ? model.total_schema_compliance / model.run_count : 0;
      const avgStructure = model.run_count > 0 ? model.total_structural_accuracy / model.run_count : 0;
      const avgSemantic = model.run_count > 0 ? model.total_semantic_accuracy / model.run_count : 0;
      const avgConfig = model.run_count > 0 ? model.total_config_accuracy / model.run_count : 0;

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
      // Extract filename stem from source path
      const sourceStem = source.split("/").pop()?.replace(".json", "") || source;
      const response = await fetch(`/api/evaluations/${sourceStem}`);
      if (!response.ok) throw new Error("Failed to fetch cache");
      const cache: EvaluationCache = await response.json();
      setSelectedCache(cache);
      setChartData(transformToChartData(cache));
      setError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [transformToChartData]);

  // Initial fetch and auto-select first source
  const refetch = useCallback(async () => {
    setLoading(true);
    const evals = await fetchSummaries();
    if (evals.length > 0) {
      await selectSource(evals[0].source_file);
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
    refetch,
    selectSource,
  };
}

