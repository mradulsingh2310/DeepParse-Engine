import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import type { WSMessage, RunStatus } from "../types";

interface UseWebSocketResult {
  connected: boolean;
  runStatus: RunStatus;
  messages: WSMessage[];
  lastMessage: WSMessage | null;
}

export function useWebSocket(onCacheUpdated?: () => void): UseWebSocketResult {
  const [connected, setConnected] = useState(false);
  const [runStatus, setRunStatus] = useState<RunStatus>({ status: "idle" });
  const onCacheUpdatedRef = useRef(onCacheUpdated);
  const [messages, setMessages] = useState<WSMessage[]>([]);
  const [lastMessage, setLastMessage] = useState<WSMessage | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    // eslint-disable-next-line react-hooks/exhaustive-deps

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

    ws.onopen = () => {
      console.log("WebSocket connected");
      setConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const message: WSMessage = JSON.parse(event.data);
        setLastMessage(message);
        setMessages((prev) => [...prev.slice(-99), message]); // Keep last 100 messages

        // Update run status based on message type
        switch (message.type) {
          case "run_started":
            setRunStatus({
              status: "running",
              message: message.data?.message,
            });
            break;
          case "model_started":
            setRunStatus({
              status: "running",
              message: message.data?.message,
              progress: message.data?.progress,
            });
            break;
          case "model_completed":
            setRunStatus((prev) => ({
              ...prev,
              message: message.data?.message,
            }));
            break;
          case "run_completed":
            setRunStatus({
              status: "completed",
              message: message.data?.message,
            });
            break;
          case "run_error":
            setRunStatus({
              status: "error",
              message: message.data?.error || message.data?.message,
            });
            break;
          case "cache_updated":
            // Trigger data refresh
            onCacheUpdatedRef.current?.();
            break;
        }
      } catch (err) {
        console.error("Failed to parse WebSocket message:", err);
      }
    };

    ws.onclose = () => {
      console.log("WebSocket disconnected");
      setConnected(false);
      wsRef.current = null;
      
      // Attempt to reconnect after 3 seconds
      reconnectTimeoutRef.current = setTimeout(() => {
        connect();
      }, 3000);
    };

    ws.onerror = (error) => {
      console.error("WebSocket error:", error);
    };

    wsRef.current = ws;
  }, [onCacheUpdated]);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  return {
    connected,
    runStatus,
    messages,
    lastMessage,
  };
}

