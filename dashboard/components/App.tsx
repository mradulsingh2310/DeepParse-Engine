import React, { useCallback } from "react";
import { useEvaluationData } from "../hooks/useEvaluationData";
import { useWebSocket } from "../hooks/useWebSocket";
import { Leaderboard } from "./Leaderboard";
import { OverallChart } from "./OverallChart";
import { StackedChart } from "./StackedChart";
import { RadarChart } from "./RadarChart";
import { TrendChart } from "./TrendChart";
import { RunButton } from "./RunButton";
import { LiveStatus } from "./LiveStatus";

export function App() {
  const {
    summaries,
    selectedCache,
    chartData,
    loading,
    error,
    refetch,
    selectSource,
  } = useEvaluationData();

  const handleCacheUpdated = useCallback(() => {
    refetch();
  }, [refetch]);

  const { connected, runStatus, messages } = useWebSocket(handleCacheUpdated);

  // Get source file name for display
  const sourceName = selectedCache?.source_file
    ? selectedCache.source_file.split("/").pop()?.replace(".json", "")
    : null;

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
            <LiveStatus connected={connected} runStatus={runStatus} />
            <RunButton runStatus={runStatus} onComplete={refetch} />
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="main">
        {loading && !selectedCache ? (
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
            {summaries.length > 1 && (
              <div className="source-selector">
                <label>Source File:</label>
                <select
                  value={selectedCache?.source_file || ""}
                  onChange={(e) => selectSource(e.target.value)}
                >
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
            )}

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
            </section>

            {/* Charts Grid */}
            <section className="charts-grid">
              {chartData.length > 0 && (
                <>
                  <div className="chart-card chart-wide" style={{ "--delay": "0" } as React.CSSProperties}>
                    <h3>Model Performance Rankings</h3>
                    <OverallChart data={chartData} />
                  </div>

                  <div className="chart-card chart-wide" style={{ "--delay": "1" } as React.CSSProperties}>
                    <h3>Score Breakdown by Category</h3>
                    <StackedChart data={chartData} />
                  </div>

                  <div className="chart-card" style={{ "--delay": "2" } as React.CSSProperties}>
                    <h3>Multi-dimensional Comparison</h3>
                    <RadarChart data={chartData.slice(0, 5)} />
                  </div>

                  <div className="chart-card" style={{ "--delay": "3" } as React.CSSProperties}>
                    <h3>Score Trends Over Time</h3>
                    <TrendChart cache={selectedCache} />
                  </div>
                </>
              )}
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
          {selectedCache?.last_updated
            ? new Date(selectedCache.last_updated).toLocaleString()
            : "—"}
        </p>
      </footer>
    </div>
  );
}

