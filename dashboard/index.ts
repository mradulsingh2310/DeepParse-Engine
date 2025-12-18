/**
 * OCR-AI Dashboard Server
 * Bun.serve() with API routes, WebSocket, and HTML imports
 */

import { spawn } from "bun";
import path from "path";
import type { ServerWebSocket } from "bun";
import index from "./index.html";
import documents from "./documents.html";

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

// Pricing per-million tokens (must mirror src/config/pricing.py)
const pricingPerMillion: Record<string, Record<string, { input: number; output: number }>> = {
  openai: {
    "gpt-5": { input: 1.25, output: 10.0 },
    "gpt-5.2": { input: 2.5, output: 15.0 },
    "gpt-5-mini": { input: 0.25, output: 2.0 },
    "gpt-5-nano": { input: 0.05, output: 0.4 },
  },
  google: {
    "gemini-2.5-flash": { input: 0.3, output: 2.5 },
    "gemini-2.5-flash-image": { input: 0.3, output: 2.5 },
    "gemini-3-flash-preview": { input: 0.3, output: 2.5 },
  },
  bedrock: {
    "amazon.nova-pro-v1:0": { input: 0.8, output: 3.2 },
    "qwen.qwen3-vl-235b-a22b": { input: 0.18, output: 0.54 },
    "google.gemma-3-27b-it": { input: 0.15, output: 0.6 },
    "nvidia.nemotron-nano-12b-v2": { input: 0.06, output: 0.24 },
  },
  anthropic: {
    "claude-sonnet-4-5-20250929": { input: 3.0, output: 15.0 },
    "claude-haiku-4-5-20251001": { input: 0.8, output: 4.0 },
  },
  deepseek: {
    "deepseek-ocr": { input: 0.0, output: 0.0 }, // Local Ollama - free
  },
};

// Project paths
const projectRoot = new URL("..", import.meta.url).pathname;
const inputDir = `${projectRoot}/input`;
const sourceDir = `${projectRoot}/source_of_truth`;
const outputDir = `${projectRoot}/output`;
const evalResultsDir = `${projectRoot}/evaluation_results`;

// Read all cache files from evaluation_results
async function getEvaluationCaches(): Promise<object[]> {
  const cacheDir = evalResultsDir;
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
    let bestModel: string | null = null;
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

function sanitizeStem(stem: string): string {
  return stem.replace(/[^a-zA-Z0-9_\-]/g, "");
}

async function readJsonFile(filePath: string): Promise<any | null> {
  const file = Bun.file(filePath);
  if (!(await file.exists())) return null;
  try {
    const text = await file.text();
    return JSON.parse(text);
  } catch (error) {
    console.error("Failed to read JSON file:", filePath, error);
    return null;
  }
}

async function resolveFileByStem(dir: string, stem: string, extensions: string[]): Promise<string | null> {
  try {
    const fs = await import("fs/promises");
    const entries = await fs.readdir(dir);
    for (const entry of entries) {
      const parsed = path.parse(entry);
      if (parsed.name === stem && extensions.includes(parsed.ext.toLowerCase())) {
        return path.join(dir, entry);
      }
    }
  } catch (error) {
    console.error("Failed to resolve file by stem:", dir, stem, error);
  }
  return null;
}

async function listAvailablePdfs() {
  const pdfs: Array<{
    name: string;
    stem: string;
    path: string;
    source_exists: boolean;
    model_count: number;
    best_score: number | null;
    average_score: number | null;
  }> = [];

  const fs = await import("fs/promises");
  try {
    const entries = await fs.readdir(inputDir);
    for (const entry of entries) {
      if (!entry.toLowerCase().endsWith(".pdf")) continue;
      const stem = path.parse(entry).name;
      const sourcePath = path.join(sourceDir, `${stem}.json`);
      const sourceExists = await Bun.file(sourcePath).exists();

      // Derive model outputs and cached scores
      const modelOutputs = await findModelOutputsForStem(stem);
      const cache = await loadCache(stem);
      const bestScore = cache ? cache.best_score ?? cache.average_score ?? null : null;
      const averageScore = cache?.average_score ?? null;

      pdfs.push({
        name: entry,
        stem,
        path: path.join(inputDir, entry),
        source_exists: sourceExists,
        model_count: modelOutputs.length,
        best_score: bestScore ? Math.round(bestScore * 100) : null,
        average_score: averageScore ? Math.round(averageScore * 100) : null,
      });
    }
  } catch (error) {
    console.error("Failed to list PDFs:", error);
  }

  // Sort alphabetically for stable UI
  return pdfs.sort((a, b) => a.name.localeCompare(b.name));
}

async function findModelOutputsForStem(stem: string) {
  const outputs: Array<{
    providerDir: string;
    modelDir: string;
    filePath: string;
    metadata: {
      provider: string;
      model_id: string;
      supporting_model_id: string | null;
    };
  }> = [];

  const fs = await import("fs/promises");
  const stack: string[] = [outputDir];

  while (stack.length > 0) {
    const current = stack.pop()!;
    let dirEntries: Array<any> = [];
    try {
      dirEntries = await fs.readdir(current, { withFileTypes: true } as any);
    } catch (error) {
      console.error("Failed to read directory:", current, error);
      continue;
    }

    for (const entry of dirEntries) {
      const entryPath = path.join(current, entry.name);
      if ((entry as any).isDirectory()) {
        stack.push(entryPath);
      } else if ((entry as any).isFile() && entry.name === `${stem}.json`) {
        const relative = path.relative(outputDir, entryPath);
        const [providerDir = "unknown", modelDir = "unknown"] = relative.split(path.sep);
        const json = await readJsonFile(entryPath);
        const meta = json?._metadata ?? {};
        outputs.push({
          providerDir,
          modelDir,
          filePath: entryPath,
          metadata: {
            provider: meta.provider ?? providerDir,
            model_id: meta.model_id ?? modelDir,
            supporting_model_id: meta.supporting_model_id ?? null,
          },
        });
      }
    }
  }

  return outputs;
}

async function loadCache(stem: string) {
  const cachePath = path.join(evalResultsDir, `cache_${stem}.json`);
  const cache = await readJsonFile(cachePath);
  if (!cache) return null;

  // Pre-compute helper fields
  const models = cache.models || {};
  let best_score: number | null = null;
  let average_score: number | null = null;
  const scores: number[] = [];
  for (const model of Object.values(models) as any[]) {
    const score = model.latest_score ?? model.best_score ?? null;
    if (score !== null) scores.push(score);
    if (score !== null && (best_score === null || score > best_score)) {
      best_score = score;
    }
  }
  if (scores.length > 0) {
    average_score = scores.reduce((a, b) => a + b, 0) / scores.length;
  }

  return { ...cache, best_score, average_score };
}

async function loadLatestEvaluationReport(stem: string) {
  const fs = await import("fs/promises");
  try {
    const entries = await fs.readdir(evalResultsDir);
    const matches = entries
      .filter((name) => name.startsWith(`evaluation_${stem}_`) && name.endsWith(".json"))
      .map((name) => ({
        name,
        time: name.match(/_(\d{8}_\d{6})\.json$/)?.[1] ?? "",
      }))
      .sort((a, b) => b.time.localeCompare(a.time));

    if (matches.length === 0) return null;
    const latestPath = path.join(evalResultsDir, matches[0].name);
    const report = await readJsonFile(latestPath);
    return report;
  } catch (error) {
    // If directory missing, just return null
    return null;
  }
}

function sanitizeModelId(value: string | undefined | null): string {
  if (!value) return "";
  return value.replace(/[\.\:\/]/g, "_");
}

function findEvaluationForModel(report: any, metadata: { provider: string; model_id: string }) {
  if (!report?.evaluations) return null;
  const targetSanitized = sanitizeModelId(metadata.model_id);

  for (const evaluation of report.evaluations as any[]) {
    const evalMeta = evaluation.metadata || evaluation.metadata;
    const evalModelId = evalMeta?.model_id ?? "";
    const evalSanitized = sanitizeModelId(evalModelId);
    if (evalSanitized === targetSanitized || evalModelId === metadata.model_id) {
      return evaluation;
    }
  }
  return null;
}

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
    "/documents": documents,

    // API: List available PDFs
    "/api/pdfs": {
      GET: async () => {
        const pdfs = await listAvailablePdfs();
        return Response.json({ pdfs });
      },
    },

    // API: Stream a PDF by stem
    "/api/pdfs/:stem/pdf": {
      GET: async (req) => {
        const stem = sanitizeStem(req.params.stem);
        const pdfPath = await resolveFileByStem(inputDir, stem, [".pdf"]);
        if (!pdfPath) {
          return new Response("PDF not found", { status: 404 });
        }
        const file = Bun.file(pdfPath);
        return new Response(file, {
          headers: { "Content-Type": "application/pdf" },
        });
      },
    },

    // API: Get source of truth JSON for a PDF
    "/api/pdfs/:stem/source": {
      GET: async (req) => {
        const stem = sanitizeStem(req.params.stem);
        const sourcePath = path.join(sourceDir, `${stem}.json`);
        const source = await readJsonFile(sourcePath);
        if (!source) {
          return Response.json({ error: "Source of truth not found" }, { status: 404 });
        }
        return Response.json({ source, stem });
      },
    },

    // API: Pricing per million tokens (mirrors src/config/pricing.py)
    "/api/pricing": {
      GET: () => Response.json({ pricing: pricingPerMillion }),
    },

    // API: List model outputs for a PDF stem
    "/api/pdfs/:stem/models": {
      GET: async (req) => {
        const stem = sanitizeStem(req.params.stem);
        const models = await findModelOutputsForStem(stem);
        const cache = await loadCache(stem);
        const report = await loadLatestEvaluationReport(stem);

        const modelsWithScores = models.map((entry) => {
          const cacheKey = `${entry.metadata.provider}:${entry.metadata.model_id}`;
          const cacheEntry = cache?.models?.[cacheKey];

          const runCount = cacheEntry?.run_count ?? 0;
          const avgScore = runCount
            ? cacheEntry.total_overall_score / runCount
            : cacheEntry?.latest_score ?? cacheEntry?.best_score ?? null;

          const avgSchema = runCount ? cacheEntry.total_schema_compliance / runCount : null;
          const avgStructure = runCount ? cacheEntry.total_structural_accuracy / runCount : null;
          const avgSemantic = runCount ? cacheEntry.total_semantic_accuracy / runCount : null;
          const avgConfig = runCount ? cacheEntry.total_config_accuracy / runCount : null;

          return {
            ...entry,
            scores: avgScore !== null ? {
              overall: avgScore,
              schema: avgSchema,
              structure: avgStructure,
              semantic: avgSemantic,
              config: avgConfig,
            } : null,
            run_count: runCount,
            cache_key: cacheKey,
          };
        });

        return Response.json({
          stem,
          models: modelsWithScores,
          cache_available: !!cache,
          report_available: !!report,
        });
      },
    },

    // API: Get model output and evaluation detail
    "/api/pdfs/:stem/models/:provider/:model": {
      GET: async (req) => {
        const stem = sanitizeStem(req.params.stem);
        const providerDir = sanitizeStem(req.params.provider);
        const modelDir = sanitizeStem(req.params.model);

        const outputPath = path.join(outputDir, providerDir, modelDir, `${stem}.json`);
        const modelJson = await readJsonFile(outputPath);
        if (!modelJson) {
          return Response.json({ error: "Model output not found" }, { status: 404 });
        }

        const sourcePath = path.join(sourceDir, `${stem}.json`);
        const sourceJson = await readJsonFile(sourcePath);

        const metadata = modelJson._metadata ?? {
          provider: providerDir,
          model_id: modelDir,
          supporting_model_id: null,
        };

        const cache = await loadCache(stem);
        const cacheKey = `${metadata.provider}:${metadata.model_id}`;
        const cacheEntry = cache?.models?.[cacheKey];
        const runCount = cacheEntry?.run_count ?? 0;
        const avgScore = runCount
          ? cacheEntry.total_overall_score / runCount
          : cacheEntry?.latest_score ?? cacheEntry?.best_score ?? null;

        const cacheScores = cacheEntry
          ? {
              overall: avgScore,
              schema: runCount ? cacheEntry.total_schema_compliance / runCount : null,
              structure: runCount ? cacheEntry.total_structural_accuracy / runCount : null,
              semantic: runCount ? cacheEntry.total_semantic_accuracy / runCount : null,
              config: runCount ? cacheEntry.total_config_accuracy / runCount : null,
              run_count: runCount,
            }
          : null;

        const report = await loadLatestEvaluationReport(stem);
        const evaluation = report ? findEvaluationForModel(report, metadata) : null;

        return Response.json({
          stem,
          providerDir,
          modelDir,
          model: modelJson,
          source: sourceJson,
          metadata,
          evaluation,
          cacheScores,
        });
      },
    },
    
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
  GET  /api/pricing           - Get pricing per million tokens
  POST /api/run               - Trigger extraction pipeline
  GET  /api/status            - Get pipeline status
  WS   /ws                    - WebSocket for real-time updates
`);

