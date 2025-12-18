import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useEvaluationData } from "../hooks/useEvaluationData";
import { useWebSocket } from "../hooks/useWebSocket";
import { Leaderboard } from "./Leaderboard";
import { OverallChart } from "./OverallChart";
import { StackedChart } from "./StackedChart";
import { RadarChart } from "./RadarChart";
import { TrendChart } from "./TrendChart";
import { RunButton } from "./RunButton";
import { LiveStatus } from "./LiveStatus";
import { LogViewer } from "./LogViewer";
import type { PricingTable, PricingRate } from "../types";

type PricingSortKey = "provider" | "model" | "input" | "output";
type PricingSortDir = "asc" | "desc";

export function App() {
  const {
    summaries,
    selectedCache,
    chartData,
    loading,
    error,
    isAggregated,
    refetch,
    selectSource,
  } = useEvaluationData();

  const handleCacheUpdated = useCallback(() => {
    refetch();
  }, [refetch]);

  const { connected, runStatus, messages } = useWebSocket(handleCacheUpdated);
  const [pricing, setPricing] = useState<PricingTable | null>(null);
  const [pricingError, setPricingError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<PricingSortKey>("provider");
  const [sortDir, setSortDir] = useState<PricingSortDir>("asc");

  const handlePricingSort = useCallback(
    (key: PricingSortKey) => {
      if (sortKey === key) {
        setSortDir((prev) => (prev === "asc" ? "desc" : "asc"));
      } else {
        setSortKey(key);
        setSortDir("asc");
      }
    },
    [sortKey]
  );

  const getPricingSortIcon = useCallback(
    (key: PricingSortKey) => {
      if (sortKey !== key) return "↕";
      return sortDir === "asc" ? "↑" : "↓";
    },
    [sortDir, sortKey]
  );

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch("/api/pricing");
        if (!res.ok) throw new Error("Failed to fetch pricing");
        const data = await res.json();
        setPricing(data.pricing || {});
        setPricingError(null);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to load pricing";
        setPricingError(message);
      }
    })();
  }, []);

  // Get source file name for display
  const sourceName = isAggregated
    ? "All Files"
    : selectedCache?.source_file
    ? selectedCache.source_file.split("/").pop()?.replace(".json", "")
    : null;

  const pricingRows = useMemo(() => {
    if (!pricing) return [];
    const rows = Object.entries(pricing).flatMap(([provider, models]) =>
      Object.entries(models).map(([model, rate]) => ({
        id: `${provider}/${model}`,
        provider,
        model,
        input: rate.input,
        output: rate.output,
      }))
    );

    return rows.sort((a, b) => {
      const dir = sortDir === "asc" ? 1 : -1;
      if (sortKey === "input" || sortKey === "output") {
        return (a[sortKey] - b[sortKey]) * dir || a.provider.localeCompare(b.provider) || a.model.localeCompare(b.model);
      }
      const first = a[sortKey].localeCompare(b[sortKey]) * dir;
      if (first !== 0) return first;
      return a.model.localeCompare(b.model);
    });
  }, [pricing, sortDir, sortKey]);

  const pricingLookup = useMemo<Record<string, PricingRate>>(() => {
    if (!pricing) return {};
    const map: Record<string, PricingRate> = {};
    Object.entries(pricing).forEach(([provider, models]) => {
      Object.entries(models).forEach(([model, rate]) => {
        map[`${provider}:${model}`] = rate;
        map[`${provider}/${model}`] = rate; // alias for safety
      });
    });
    return map;
  }, [pricing]);

  return (
    <div className="dashboard">
      {/* Header */}
      <header className="header">
        <div className="header-content">
          <div className="logo">
            <span className="logo-icon">📊</span>
            <h1>OCR-AI Evaluation Dashboard</h1>
          </div>
          <div className="header-actions">
            <a className="btn btn-ghost" href="/documents">
              Documents
            </a>
            <LiveStatus connected={connected} runStatus={runStatus} />
            <RunButton runStatus={runStatus} onComplete={refetch} />
          </div>
        </div>
      </header>

      {/* Log Viewer - Shows when running or has messages */}
      <LogViewer 
        messages={messages} 
        isRunning={runStatus.status === "running"} 
      />

      {/* Main Content */}
      <main className="main">
        {loading && chartData.length === 0 ? (
          <div className="loading-state">
            <div className="spinner" />
            <p>Loading evaluation data...</p>
          </div>
        ) : error ? (
          <div className="error-state">
            <p>Error: {error}</p>
            <button onClick={refetch} className="btn btn-primary">
              Retry
            </button>
          </div>
        ) : chartData.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">📋</div>
            <h2>No Evaluation Data</h2>
            <p>Run the extraction pipeline to generate evaluation results.</p>
            <RunButton runStatus={runStatus} onComplete={refetch} />
          </div>
        ) : (
          <>
            {/* Source Selector */}
            <div className="source-selector">
              <label>Source File:</label>
              <select
                value={isAggregated ? "all" : selectedCache?.source_file || ""}
                onChange={(e) => selectSource(e.target.value)}
              >
                <option value="all">
                  All Files ({summaries.reduce((sum, s) => sum + s.model_count, 0)} models)
                </option>
                {summaries.map((s) => {
                  const fileName = s.source_file.split("/").pop()?.replace(".json", "") ?? s.source_file;
                  return (
                    <option key={s.source_file} value={s.source_file}>
                      {fileName} ({s.model_count} models)
                    </option>
                  );
                })}
              </select>
            </div>

            {/* Stats Summary */}
            <section className="stats-grid">
              <div className="stat-card" style={{ "--delay": "0" } as React.CSSProperties}>
                <div className="stat-value">{chartData.length}</div>
                <div className="stat-label">Models Evaluated</div>
              </div>
              <div className="stat-card" style={{ "--delay": "1" } as React.CSSProperties}>
                <div className="stat-value">
                  {chartData[0] ? `${chartData[0].overall}%` : "—"}
                </div>
                <div className="stat-label">Best Score</div>
              </div>
              <div className="stat-card" style={{ "--delay": "2" } as React.CSSProperties}>
                <div className="stat-value">
                  {chartData.length > 0
                    ? `${Math.round(chartData.reduce((a, b) => a + b.overall, 0) / chartData.length)}%`
                    : "—"}
                </div>
                <div className="stat-label">Average Score</div>
              </div>
              <div className="stat-card" style={{ "--delay": "3" } as React.CSSProperties}>
                <div className="stat-value">
                  {chartData[0]?.name ?? "—"}
                </div>
                <div className="stat-label">Top Model</div>
              </div>
              <div className="stat-card" style={{ "--delay": "4" } as React.CSSProperties}>
                <div className="stat-value">
                  {chartData.length > 0
                    ? `$${chartData.reduce((a, b) => a + b.totalCost, 0).toFixed(4)}`
                    : "—"}
                </div>
                <div className="stat-label">Total Cost</div>
              </div>
            </section>

            {/* Charts Grid */}
            <section className="charts-grid">
              {chartData.length > 0 && (
                <>
                  <div className="chart-card chart-wide" style={{ "--delay": "0" } as React.CSSProperties}>
                    <h3>Model Performance Rankings</h3>
                    <OverallChart data={chartData} pricing={pricingLookup} />
                  </div>

                  <div className="chart-card chart-wide" style={{ "--delay": "1" } as React.CSSProperties}>
                    <h3>Score Breakdown by Category</h3>
                    <StackedChart data={chartData} pricing={pricingLookup} />
                  </div>

                  <div className="chart-card" style={{ "--delay": "2" } as React.CSSProperties}>
                    <h3>Multi-dimensional Comparison</h3>
                    <RadarChart data={chartData.slice(0, 5)} pricing={pricingLookup} />
                  </div>

                  <div className="chart-card" style={{ "--delay": "3" } as React.CSSProperties}>
                    <h3>Score Trends Over Time</h3>
                    {isAggregated ? (
                      <div className="chart-empty">
                        <p>Trend data available for individual files</p>
                        <span>Select a specific file to view score trends over time</span>
                      </div>
                    ) : (
                      <TrendChart cache={selectedCache} pricing={pricingLookup} />
                    )}
                  </div>
                </>
              )}
            </section>

            {/* Pricing (below charts) */}
            <section className="leaderboard-section pricing-section" style={{ "--delay": "5" } as React.CSSProperties}>
              <div className="pricing-card-header">
                <div>
                  <h3>Per-million token pricing</h3>
                  <p className="muted">
                    Input and output USD rates from <code>src/config/pricing.py</code>
                  </p>
                </div>
              </div>
              {pricingError && <div className="alert alert-error">{pricingError}</div>}
              <div className="leaderboard pricing-leaderboard">
                <table>
                  <thead>
                    <tr>
                      <th onClick={() => handlePricingSort("provider")} className="sortable">
                        <span className="th-content">
                          <span>Provider</span>
                          <span className={`sort-icon ${sortKey === "provider" ? "active" : ""}`}>
                            {getPricingSortIcon("provider")}
                          </span>
                        </span>
                      </th>
                      <th onClick={() => handlePricingSort("model")} className="sortable">
                        <span className="th-content">
                          <span>Model</span>
                          <span className={`sort-icon ${sortKey === "model" ? "active" : ""}`}>
                            {getPricingSortIcon("model")}
                          </span>
                        </span>
                      </th>
                      <th onClick={() => handlePricingSort("input")} className="sortable">
                        <span className="th-content">
                          <span>Input / 1M tokens</span>
                          <span className={`sort-icon ${sortKey === "input" ? "active" : ""}`}>
                            {getPricingSortIcon("input")}
                          </span>
                        </span>
                      </th>
                      <th onClick={() => handlePricingSort("output")} className="sortable">
                        <span className="th-content">
                          <span>Output / 1M tokens</span>
                          <span className={`sort-icon ${sortKey === "output" ? "active" : ""}`}>
                            {getPricingSortIcon("output")}
                          </span>
                        </span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {pricingRows.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="pricing-empty">
                          Loading pricing…
                        </td>
                      </tr>
                    ) : (
                      pricingRows.map((row, idx) => (
                        <tr className="pricing-row" key={row.id} style={{ "--row-delay": idx } as React.CSSProperties}>
                          <td className="provider-cell">
                            <span className={`provider-badge provider-${row.provider.toLowerCase()}`}>
                              {row.provider}
                            </span>
                          </td>
                          <td className="model-cell">
                            <span className="model-name">{row.model}</span>
                          </td>
                          <td className="num-cell">${row.input.toFixed(4)}</td>
                          <td className="num-cell">${row.output.toFixed(4)}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </section>

            {/* Leaderboard */}
            <section className="leaderboard-section" style={{ "--delay": "4" } as React.CSSProperties}>
              <h3>Model Leaderboard</h3>
              <Leaderboard data={chartData} cache={selectedCache} />
            </section>

          </>
        )}
      </main>

      {/* Footer */}
      <footer className="footer">
        <p>
          OCR-AI Evaluation Dashboard • Last updated:{" "}
          {isAggregated && summaries.length > 0
            ? new Date(Math.max(...summaries.map(s => new Date(s.last_updated).getTime()))).toLocaleString()
            : selectedCache?.last_updated
            ? new Date(selectedCache.last_updated).toLocaleString()
            : "—"}
        </p>
      </footer>
    </div>
  );
}

