import React, { useState, useMemo } from "react";
import type { ModelChartData, EvaluationCache } from "../types";

interface LeaderboardProps {
  data: ModelChartData[];
  cache: EvaluationCache | null;
}

type SortKey = "rank" | "name" | "provider" | "overall" | "schema" | "structure" | "semantic" | "config" | "runCount";
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
              # {getSortIcon("rank")}
            </th>
            <th onClick={() => handleSort("name")} className="sortable">
              Model {getSortIcon("name")}
            </th>
            <th onClick={() => handleSort("provider")} className="sortable">
              Provider {getSortIcon("provider")}
            </th>
            <th onClick={() => handleSort("schema")} className="sortable">
              Schema {getSortIcon("schema")}
            </th>
            <th onClick={() => handleSort("structure")} className="sortable">
              Structure {getSortIcon("structure")}
            </th>
            <th onClick={() => handleSort("semantic")} className="sortable">
              Semantic {getSortIcon("semantic")}
            </th>
            <th onClick={() => handleSort("config")} className="sortable">
              Config {getSortIcon("config")}
            </th>
            <th onClick={() => handleSort("overall")} className="sortable overall-col">
              Overall {getSortIcon("overall")}
            </th>
            <th onClick={() => handleSort("runCount")} className="sortable">
              Runs {getSortIcon("runCount")}
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
                </tr>
                {isExpanded && details && (
                  <tr className="details-row">
                    <td colSpan={9}>
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

