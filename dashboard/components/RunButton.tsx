import React, { useState, useCallback } from "react";
import type { RunStatus } from "../types";

interface RunButtonProps {
  runStatus: RunStatus;
  onComplete?: () => void;
}

export function RunButton({ runStatus, onComplete }: RunButtonProps) {
  const [localLoading, setLocalLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleClick = useCallback(async () => {
    if (runStatus.status === "running" || localLoading) return;

    setLocalLoading(true);
    setError(null);
    
    try {
      console.log("Triggering pipeline...");
      const response = await fetch("/api/run", { 
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      const data = await response.json();
      console.log("Pipeline response:", data);

      if (!response.ok) {
        setError(data.error || "Failed to start pipeline");
        console.error("Failed to start pipeline:", data.error);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setError(message);
      console.error("Error triggering pipeline:", err);
    } finally {
      // Keep loading true until WebSocket says it's done
      // The localLoading just indicates we sent the request
      setLocalLoading(false);
    }
  }, [runStatus.status, localLoading]);

  const isRunning = runStatus.status === "running" || localLoading;
  const progress = runStatus.progress;

  return (
    <div className="run-button-container">
      <button
        className={`run-button ${isRunning ? "running" : ""} ${error ? "error" : ""}`}
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
      {error && <span className="run-error" title={error}>Error</span>}
    </div>
  );
}

