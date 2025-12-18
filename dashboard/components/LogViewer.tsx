import React, { useEffect, useRef } from "react";
import type { WSMessage } from "../types";

interface LogViewerProps {
  messages: WSMessage[];
  isRunning: boolean;
}

function getMessageColor(type: WSMessage["type"]): string {
  switch (type) {
    case "run_started":
      return "log-info";
    case "model_started":
      return "log-progress";
    case "model_completed":
      return "log-success";
    case "run_completed":
      return "log-success";
    case "run_error":
      return "log-error";
    case "cache_updated":
      return "log-info";
    default:
      return "log-default";
  }
}

function getMessageIcon(type: WSMessage["type"]): string {
  switch (type) {
    case "run_started":
      return "🚀";
    case "model_started":
      return "⏳";
    case "model_completed":
      return "✅";
    case "run_completed":
      return "🎉";
    case "run_error":
      return "❌";
    case "cache_updated":
      return "📊";
    case "connected":
      return "🔌";
    default:
      return "📝";
  }
}

function formatTimestamp(timestamp: string): string {
  try {
    return new Date(timestamp).toLocaleTimeString();
  } catch {
    return "";
  }
}

export function LogViewer({ messages, isRunning }: LogViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [messages]);

  // Filter to show only pipeline-related messages
  const pipelineMessages = messages.filter(
    (m) => m.type !== "connected"
  );

  if (pipelineMessages.length === 0 && !isRunning) {
    return null;
  }

  return (
    <div className="log-viewer">
      <div className="log-header">
        <h3>
          <span className="log-icon">📋</span>
          Pipeline Logs
          {isRunning && <span className="log-running-indicator" />}
        </h3>
        {pipelineMessages.length > 0 && (
          <span className="log-count">{pipelineMessages.length} messages</span>
        )}
      </div>
      <div className="log-container" ref={containerRef}>
        {pipelineMessages.length === 0 ? (
          <div className="log-empty">
            <span>Waiting for pipeline output...</span>
          </div>
        ) : (
          pipelineMessages.map((msg, index) => (
            <div
              key={`${msg.timestamp}-${index}`}
              className={`log-entry ${getMessageColor(msg.type)}`}
            >
              <span className="log-entry-icon">{getMessageIcon(msg.type)}</span>
              <span className="log-entry-time">
                {formatTimestamp(msg.timestamp)}
              </span>
              <span className="log-entry-message">
                {msg.data?.message || msg.data?.error || msg.type}
              </span>
              {msg.data?.progress && (
                <span className="log-entry-progress">
                  [{msg.data.progress.current}/{msg.data.progress.total}]
                </span>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

