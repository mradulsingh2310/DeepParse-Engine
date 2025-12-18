import React, { useState, useCallback } from "react";
import type { RunStatus } from "../types";

interface RunButtonProps {
  runStatus: RunStatus;
  onComplete?: () => void;
}

export function RunButton({ runStatus, onComplete }: RunButtonProps) {
  const [localLoading, setLocalLoading] = useState(false);

  const handleClick = useCallback(async () => {
    if (runStatus.status === "running" || localLoading) return;

    setLocalLoading(true);
    try {
      const response = await fetch("/api/run", { method: "POST" });
      const data = await response.json();

      if (!response.ok) {
        console.error("Failed to start pipeline:", data.error);
      }
    } catch (error) {
      console.error("Error triggering pipeline:", error);
    } finally {
      setLocalLoading(false);
    }
  }, [runStatus.status, localLoading]);

  const isRunning = runStatus.status === "running" || localLoading;
  const progress = runStatus.progress;

  return (
    <button
      className={`run-button ${isRunning ? "running" : ""}`}
      onClick={handleClick}
      disabled={isRunning}
    >
      {isRunning ? (
        <>
          <span className="run-spinner" />
          <span className="run-text">
            {progress
              ? `Running ${progress.current}/${progress.total}...`
              : "Starting..."}
          </span>
        </>
      ) : (
        <>
          <span className="run-icon">▶</span>
          <span className="run-text">Run Extraction</span>
        </>
      )}
    </button>
  );
}

