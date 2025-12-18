/**
 * OCR-AI Dashboard Server
 * Bun.serve() with API routes, WebSocket, and HTML imports
 */

import { spawn } from "bun";
import type { ServerWebSocket } from "bun";
import index from "./index.html";

// Types
interface WSData {
  id: string;
}

// Store connected WebSocket clients
const wsClients = new Set<ServerWebSocket<WSData>>();

// Pipeline run state
let pipelineRunning = false;
let pipelineProcess: ReturnType<typeof spawn> | null = null;

// Broadcast message to all connected clients
function broadcast(message: object) {
  const payload = JSON.stringify({
    ...message,
    timestamp: new Date().toISOString(),
  });
  
  for (const client of wsClients) {
    client.send(payload);
  }
}

// Read all cache files from evaluation_results
async function getEvaluationCaches(): Promise<object[]> {
  const cacheDir = `${projectRoot}/evaluation_results`;
  const caches: object[] = [];
  
  try {
    const fs = await import("fs/promises");
    const files = await fs.readdir(cacheDir);
    
    for (const filename of files) {
      if (filename.startsWith("cache_") && filename.endsWith(".json")) {
        const filePath = `${cacheDir}/${filename}`;
        const content = await Bun.file(filePath).text();
        const cache = JSON.parse(content);
        caches.push(cache);
      }
    }
  } catch (error) {
    console.error("Error reading cache files:", error);
  }
  
  return caches;
}

// Get summary of all evaluations
async function getEvaluationsSummary() {
  const caches = await getEvaluationCaches();
  
  return caches.map((cache: any) => {
    const models = Object.values(cache.models || {}) as any[];
    const scores = models.map(m => m.total_overall_score / m.run_count);
    const avgScore = scores.length > 0 
      ? scores.reduce((a, b) => a + b, 0) / scores.length 
      : null;
    
    // Find best model
    let bestModel = null;
    let bestScore = 0;
    for (const [key, model] of Object.entries(cache.models || {}) as [string, any][]) {
      if (model.best_score > bestScore) {
        bestScore = model.best_score;
        bestModel = key;
      }
    }
    
    return {
      source_file: cache.source_file,
      last_updated: cache.last_updated,
      model_count: models.length,
      best_model: bestModel,
      best_score: bestScore || null,
      average_score: avgScore,
    };
  });
}

// Get project root directory (parent of dashboard)
const projectRoot = new URL("..", import.meta.url).pathname;

// Run the extraction pipeline
async function runPipeline() {
  if (pipelineRunning) {
    return { error: "Pipeline is already running" };
  }
  
  pipelineRunning = true;
  broadcast({ type: "run_started", data: { message: "Starting extraction pipeline..." } });
  
  try {
    console.log("Starting pipeline from:", projectRoot);
    
    // Spawn the main.py process from project root
    pipelineProcess = spawn({
      cmd: ["python", "main.py"],
      cwd: projectRoot,
      stdout: "pipe",
      stderr: "pipe",
      env: { ...process.env },
    });
    
    // Stream stdout
    const decoder = new TextDecoder();
    const stdout = pipelineProcess.stdout;
    
    if (stdout && typeof stdout !== "number") {
      const reader = (stdout as ReadableStream<Uint8Array>).getReader();
      
      (async () => {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          
          const text = decoder.decode(value);
          const lines = text.split("\n").filter(l => l.trim());
          
          for (const line of lines) {
            // Parse progress from output
            if (line.includes("[") && line.includes("/") && line.includes("]")) {
              const match = line.match(/\[(\d+)\/(\d+)\]/);
              if (match && match[1] && match[2]) {
                const current = match[1];
                const total = match[2];
                broadcast({
                  type: "model_started",
                  data: {
                    message: line.trim(),
                    progress: { current: parseInt(current), total: parseInt(total) },
                  },
                });
              }
            } else if (line.includes("SUCCESS:")) {
              broadcast({
                type: "model_completed",
                data: { message: line.trim() },
              });
            } else if (line.includes("ERROR:")) {
              broadcast({
                type: "run_error",
                data: { message: line.trim() },
              });
            } else if (line.trim()) {
              // Broadcast all other non-empty output lines
              broadcast({
                type: "model_started",
                data: { message: line.trim() },
              });
            }
          }
        }
      })();
    }
    
    // Also capture stderr
    const stderr = pipelineProcess.stderr;
    if (stderr && typeof stderr !== "number") {
      const stderrReader = (stderr as ReadableStream<Uint8Array>).getReader();
      const stderrDecoder = new TextDecoder();
      
      (async () => {
        while (true) {
          const { done, value } = await stderrReader.read();
          if (done) break;
          const text = stderrDecoder.decode(value);
          console.error("Pipeline stderr:", text);
          broadcast({ type: "run_error", data: { message: text.trim() } });
        }
      })();
    }
    
    // Wait for process to complete
    const exitCode = await pipelineProcess.exited;
    
    pipelineRunning = false;
    pipelineProcess = null;
    
    if (exitCode === 0) {
      broadcast({ type: "run_completed", data: { message: "Pipeline completed successfully" } });
      broadcast({ type: "cache_updated", data: { message: "Evaluation cache updated" } });
      return { success: true, message: "Pipeline completed successfully" };
    } else {
      const errorMsg = `Pipeline exited with code ${exitCode}`;
      console.error(errorMsg);
      broadcast({ type: "run_error", data: { error: errorMsg } });
      return { error: errorMsg };
    }
  } catch (error) {
    pipelineRunning = false;
    pipelineProcess = null;
    const errorMessage = error instanceof Error ? error.message : String(error);
    console.error("Pipeline error:", errorMessage);
    broadcast({ type: "run_error", data: { error: errorMessage } });
    return { error: errorMessage };
  }
}

// Server
const server = Bun.serve({
  port: 3000,
  idleTimeout: 200,
  
  routes: {
    // Serve dashboard
    "/": index,
    
    // API: Get all evaluations summary
    "/api/evaluations": {
      GET: async () => {
        const evaluations = await getEvaluationsSummary();
        return Response.json({ evaluations });
      },
    },
    
    // API: Get specific evaluation cache
    "/api/evaluations/:source": {
      GET: async (req) => {
        const source = req.params.source;
        const cacheDir = `${projectRoot}/evaluation_results`;
        const filePath = `${cacheDir}/cache_${source}.json`;
        
        try {
          const file = Bun.file(filePath);
          if (await file.exists()) {
            const content = await file.text();
            return Response.json(JSON.parse(content));
          }
          return Response.json({ error: "Cache not found" }, { status: 404 });
        } catch (error) {
          console.error("Error reading cache:", error);
          return Response.json({ error: "Failed to read cache" }, { status: 500 });
        }
      },
    },
    
    // API: Run extraction pipeline (returns immediately, runs in background)
    "/api/run": {
      POST: async () => {
        if (pipelineRunning) {
          return Response.json({ error: "Pipeline is already running" }, { status: 400 });
        }
        
        // Start pipeline in background - don't await it
        runPipeline().catch((err) => {
          console.error("Pipeline error:", err);
        });
        
        return Response.json({ success: true, message: "Pipeline started" });
      },
    },
    
    // API: Get run status
    "/api/status": {
      GET: () => {
        return Response.json({
          status: pipelineRunning ? "running" : "idle",
        });
      },
    },
  },
  
  // WebSocket support
  websocket: {
    open(ws: ServerWebSocket<WSData>) {
      ws.data = { id: crypto.randomUUID() };
      wsClients.add(ws);
      ws.send(JSON.stringify({
        type: "connected",
        timestamp: new Date().toISOString(),
        data: { message: "Connected to dashboard server" },
      }));
      console.log(`WebSocket client connected: ${ws.data.id}`);
    },
    
    message(ws: ServerWebSocket<WSData>, message: string | Buffer) {
      // Handle incoming messages if needed
      console.log(`Message from ${ws.data.id}:`, message);
    },
    
    close(ws: ServerWebSocket<WSData>) {
      wsClients.delete(ws);
      console.log(`WebSocket client disconnected: ${ws.data.id}`);
    },
  },
  
  // Upgrade HTTP to WebSocket
  fetch(req, server) {
    const url = new URL(req.url);
    
    if (url.pathname === "/ws") {
      const upgraded = server.upgrade(req, { data: { id: "" } });
      if (upgraded) return undefined;
      return new Response("WebSocket upgrade failed", { status: 400 });
    }
    
    // Let routes handle other requests
    return undefined;
  },
  
  development: {
    hmr: true,
    console: true,
  },
});

console.log(`
🚀 OCR-AI Dashboard running at http://localhost:${server.port}

API Endpoints:
  GET  /api/evaluations       - List all evaluation caches
  GET  /api/evaluations/:id   - Get specific cache
  POST /api/run               - Trigger extraction pipeline
  GET  /api/status            - Get pipeline status
  WS   /ws                    - WebSocket for real-time updates
`);

