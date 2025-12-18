import React, { useState, useMemo } from "react";
import type { ModelChartData, EvaluationCache } from "../types";

interface LeaderboardProps {
  data: ModelChartData[];
  cache: EvaluationCache | null;
}

type SortKey = "rank" | "name" | "provider" | "overall" | "schema" | "structure" | "semantic" | "config" | "runCount" | "totalCost";
type SortDirection = "asc" | "desc";

function getScoreClass(score: number): string {
  if (score >= 80) return "score-high";
  if (score >= 60) return "score-medium";
  if (score >= 40) return "score-low";
  return "score-critical";
}

export function Leaderboard({ data, cache }: LeaderboardProps) {
  const [sortKey, setSortKey] = useState<SortKey>("overall");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  const sortedData = useMemo(() => {
    const sorted = [...data].sort((a, b) => {
      let aVal: string | number;
      let bVal: string | number;

      switch (sortKey) {
        case "rank":
          aVal = data.indexOf(a);
          bVal = data.indexOf(b);
          break;
        case "name":
          aVal = a.name.toLowerCase();
          bVal = b.name.toLowerCase();
          break;
        case "provider":
          aVal = a.provider.toLowerCase();
          bVal = b.provider.toLowerCase();
          break;
        default:
          aVal = a[sortKey] as number;
          bVal = b[sortKey] as number;
      }

      if (typeof aVal === "string" && typeof bVal === "string") {
        return sortDirection === "asc"
          ? aVal.localeCompare(bVal)
          : bVal.localeCompare(aVal);
      }

      return sortDirection === "asc"
        ? (aVal as number) - (bVal as number)
        : (bVal as number) - (aVal as number);
    });

    return sorted;
  }, [data, sortKey, sortDirection]);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDirection((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDirection("desc");
    }
  };

  const getSortIcon = (key: SortKey) => {
    if (sortKey !== key) return "↕";
    return sortDirection === "asc" ? "↑" : "↓";
  };

  const getModelDetails = (key: string) => {
    if (!cache) return null;
    return cache.models[key];
  };

  return (
    <div className="leaderboard">
      <table>
        <thead>
          <tr>
            <th onClick={() => handleSort("rank")} className="sortable">
              <span className="th-content">
                <span>#</span>
                <span className={`sort-icon ${sortKey === "rank" ? "active" : ""}`}>
                  {getSortIcon("rank")}
                </span>
              </span>
            </th>
            <th onClick={() => handleSort("name")} className="sortable">
              <span className="th-content">
                <span>Model</span>
                <span className={`sort-icon ${sortKey === "name" ? "active" : ""}`}>
                  {getSortIcon("name")}
                </span>
              </span>
            </th>
            <th onClick={() => handleSort("provider")} className="sortable">
              <span className="th-content">
                <span>Provider</span>
                <span className={`sort-icon ${sortKey === "provider" ? "active" : ""}`}>
                  {getSortIcon("provider")}
                </span>
              </span>
            </th>
            <th onClick={() => handleSort("schema")} className="sortable">
              <span className="th-content">
                <span>Schema</span>
                <span className={`sort-icon ${sortKey === "schema" ? "active" : ""}`}>
                  {getSortIcon("schema")}
                </span>
              </span>
            </th>
            <th onClick={() => handleSort("structure")} className="sortable">
              <span className="th-content">
                <span>Structure</span>
                <span className={`sort-icon ${sortKey === "structure" ? "active" : ""}`}>
                  {getSortIcon("structure")}
                </span>
              </span>
            </th>
            <th onClick={() => handleSort("semantic")} className="sortable">
              <span className="th-content">
                <span>Semantic</span>
                <span className={`sort-icon ${sortKey === "semantic" ? "active" : ""}`}>
                  {getSortIcon("semantic")}
                </span>
              </span>
            </th>
            <th onClick={() => handleSort("config")} className="sortable">
              <span className="th-content">
                <span>Config</span>
                <span className={`sort-icon ${sortKey === "config" ? "active" : ""}`}>
                  {getSortIcon("config")}
                </span>
              </span>
            </th>
            <th onClick={() => handleSort("overall")} className="sortable overall-col">
              <span className="th-content">
                <span>Overall</span>
                <span className={`sort-icon ${sortKey === "overall" ? "active" : ""}`}>
                  {getSortIcon("overall")}
                </span>
              </span>
            </th>
            <th onClick={() => handleSort("runCount")} className="sortable">
              <span className="th-content">
                <span>Runs</span>
                <span className={`sort-icon ${sortKey === "runCount" ? "active" : ""}`}>
                  {getSortIcon("runCount")}
                </span>
              </span>
            </th>
            <th onClick={() => handleSort("totalCost")} className="sortable">
              <span className="th-content">
                <span>Cost</span>
                <span className={`sort-icon ${sortKey === "totalCost" ? "active" : ""}`}>
                  {getSortIcon("totalCost")}
                </span>
              </span>
            </th>
          </tr>
        </thead>
        <tbody>
          {sortedData.map((model, index) => {
            const details = getModelDetails(model.key);
            const isExpanded = expandedRow === model.key;

            return (
              <React.Fragment key={model.key}>
                <tr
                  className={`leaderboard-row ${isExpanded ? "expanded" : ""}`}
                  onClick={() => setExpandedRow(isExpanded ? null : model.key)}
                  style={{ "--row-delay": index } as React.CSSProperties}
                >
                  <td className="rank-cell">
                    <span className={`rank-badge rank-${index < 3 ? index + 1 : "other"}`}>
                      {data.indexOf(model) + 1}
                    </span>
                  </td>
                  <td className="model-cell">
                    <span className="model-name">{model.name}</span>
                  </td>
                  <td className="provider-cell">
                    <span className={`provider-badge provider-${model.provider.toLowerCase()}`}>
                      {model.provider}
                    </span>
                  </td>
                  <td className={getScoreClass(model.schema)}>{model.schema}%</td>
                  <td className={getScoreClass(model.structure)}>{model.structure}%</td>
                  <td className={getScoreClass(model.semantic)}>{model.semantic}%</td>
                  <td className={getScoreClass(model.config)}>{model.config}%</td>
                  <td className={`overall-cell ${getScoreClass(model.overall)}`}>
                    <strong>{model.overall}%</strong>
                  </td>
                  <td className="runs-cell">{model.runCount}</td>
                  <td className="cost-cell">
                    {model.totalCost > 0 ? `$${model.totalCost.toFixed(4)}` : "—"}
                  </td>
                </tr>
                {isExpanded && details && (
                  <tr className="details-row">
                    <td colSpan={10}>
                      <div className="model-details">
                        <div className="detail-grid">
                          <div className="detail-item">
                            <span className="detail-label">Best Score</span>
                            <span className="detail-value">
                              {Math.round(details.best_score * 100)}%
                            </span>
                          </div>
                          <div className="detail-item">
                            <span className="detail-label">Latest Score</span>
                            <span className="detail-value">
                              {Math.round(details.latest_score * 100)}%
                            </span>
                          </div>
                          <div className="detail-item">
                            <span className="detail-label">Best Run</span>
                            <span className="detail-value">
                              {details.best_run_timestamp
                                ? new Date(details.best_run_timestamp).toLocaleString()
                                : "—"}
                            </span>
                          </div>
                          <div className="detail-item">
                            <span className="detail-label">Latest Run</span>
                            <span className="detail-value">
                              {details.latest_run_timestamp
                                ? new Date(details.latest_run_timestamp).toLocaleString()
                                : "—"}
                            </span>
                          </div>
                          <div className="detail-item">
                            <span className="detail-label">Total Cost</span>
                            <span className="detail-value">
                              {details.total_cost > 0 ? `$${details.total_cost.toFixed(4)}` : "—"}
                            </span>
                          </div>
                          <div className="detail-item">
                            <span className="detail-label">Avg Cost/Run</span>
                            <span className="detail-value">
                              {details.total_cost > 0 && details.run_count > 0
                                ? `$${(details.total_cost / details.run_count).toFixed(4)}`
                                : "—"}
                            </span>
                          </div>
                          <div className="detail-item">
                            <span className="detail-label">Input Tokens</span>
                            <span className="detail-value">
                              {details.total_input_tokens > 0
                                ? details.total_input_tokens.toLocaleString()
                                : "—"}
                            </span>
                          </div>
                          <div className="detail-item">
                            <span className="detail-label">Output Tokens</span>
                            <span className="detail-value">
                              {details.total_output_tokens > 0
                                ? details.total_output_tokens.toLocaleString()
                                : "—"}
                            </span>
                          </div>
                        </div>
                        {details.run_history.length > 0 && (
                          <div className="run-history">
                            <h4>Recent Runs</h4>
                            <div className="history-list">
                              {details.run_history.slice(-5).reverse().map((run, i) => (
                                <div key={i} className="history-item">
                                  <span className="history-date">
                                    {new Date(run.timestamp).toLocaleDateString()}
                                  </span>
                                  <span className={`history-score ${getScoreClass(run.overall_score * 100)}`}>
                                    {Math.round(run.overall_score * 100)}%
                                  </span>
                                  {run.cost !== undefined && run.cost > 0 && (
                                    <span className="history-cost">
                                      ${run.cost.toFixed(4)}
                                    </span>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

