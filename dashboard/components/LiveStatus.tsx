import React from "react";
import type { RunStatus } from "../types";

interface LiveStatusProps {
  connected: boolean;
  runStatus: RunStatus;
}

export function LiveStatus({ connected, runStatus }: LiveStatusProps) {
  const getStatusColor = () => {
    if (!connected) return "status-disconnected";
    switch (runStatus.status) {
      case "running":
        return "status-running";
      case "completed":
        return "status-success";
      case "error":
        return "status-error";
      default:
        return "status-idle";
    }
  };

  const getStatusText = () => {
    if (!connected) return "Disconnected";
    switch (runStatus.status) {
      case "running":
        return runStatus.progress
          ? `Running (${runStatus.progress.current}/${runStatus.progress.total})`
          : "Running...";
      case "completed":
        return "Completed";
      case "error":
        return "Error";
      default:
        return "Ready";
    }
  };

  return (
    <div className={`live-status ${getStatusColor()}`}>
      <span className="status-dot" />
      <span className="status-text">{getStatusText()}</span>
    </div>
  );
}

