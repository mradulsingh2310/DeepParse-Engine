import React, { useEffect, useMemo, useState } from "react";
import type {
  PdfInfo,
  ModelOutputInfo,
  ModelDetailResponse,
  EvaluationDetail,
  SectionEvaluation,
  FieldEvaluation,
  ModelScores,
} from "../types";

function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${Math.round(value * 100)}%`;
}

function formatScore(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${Math.round(value)}%`;
}

function isLikelyLlmReasoning(evaluation: EvaluationDetail | null): boolean {
  if (!evaluation?.sections) return false;
  return evaluation.sections.some((section: SectionEvaluation) =>
    section.fields.some((field: FieldEvaluation) => Boolean(field.reasoning))
  );
}

function ScoreBadge({ label, value }: { label: string; value: number | null | undefined }) {
  return (
    <div className="score-badge-card">
      <div className="score-badge-label">{label}</div>
      <div className="score-badge-value">{formatPercent(value)}</div>
    </div>
  );
}

interface JsonPaneProps {
  title: string;
  data: any;
}

function JsonPane({ title, data }: JsonPaneProps) {
  const hasData = Boolean(data);

  return (
    <div className="json-pane">
      <div className="json-pane-header">
        <h4>{title}</h4>
        <span className="json-pane-subtitle">
          {hasData ? "Rendered JSON" : "Awaiting data"}
        </span>
      </div>
      <pre className="json-block">
        {hasData ? JSON.stringify(data, null, 2) : "No data loaded"}
      </pre>
    </div>
  );
}

export function DocumentExplorer() {
  const [pdfs, setPdfs] = useState<PdfInfo[]>([]);
  const [selectedPdf, setSelectedPdf] = useState<PdfInfo | null>(null);
  const [models, setModels] = useState<ModelOutputInfo[]>([]);
  const [selectedModel, setSelectedModel] = useState<ModelOutputInfo | null>(null);
  const [sourceJson, setSourceJson] = useState<any>(null);
  const [modelJson, setModelJson] = useState<any>(null);
  const [evaluation, setEvaluation] = useState<EvaluationDetail | null>(null);
  const [cacheScores, setCacheScores] = useState<ModelScores | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch PDF list on mount
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch("/api/pdfs");
        const data = await res.json();
        setPdfs(data.pdfs || []);
        if (data.pdfs && data.pdfs.length > 0) {
          setSelectedPdf(data.pdfs[0]);
        }
      } catch (err) {
        console.error(err);
        setError("Failed to load available PDFs");
      }
    })();
  }, []);

  // Fetch models when PDF changes
  useEffect(() => {
    if (!selectedPdf) return;

    (async () => {
      try {
        setLoading(true);
        setError(null);
        setModels([]);
        setSelectedModel(null);
        setModelJson(null);
        setEvaluation(null);
        setCacheScores(null);

        const res = await fetch(`/api/pdfs/${selectedPdf.stem}/models`);
        if (!res.ok) throw new Error("Failed to load models");
        const data = await res.json();
        const list: ModelOutputInfo[] = data.models || [];
        setModels(list);
        if (list.length > 0) {
          setSelectedModel(list[0]);
        }
      } catch (err) {
        console.error(err);
        setError("Failed to load models for selected PDF");
      } finally {
        setLoading(false);
      }
    })();
  }, [selectedPdf]);

  // Fetch model details when selection changes
  useEffect(() => {
    if (!selectedPdf || !selectedModel) return;

    (async () => {
      try {
        setLoading(true);
        setError(null);
        const res = await fetch(
          `/api/pdfs/${selectedPdf.stem}/models/${selectedModel.providerDir}/${selectedModel.modelDir}`
        );
        if (!res.ok) throw new Error("Failed to load model output");
        const data: ModelDetailResponse = await res.json();
        setSourceJson(data.source);
        setModelJson(data.model);
        setEvaluation(data.evaluation);
        setCacheScores(data.cacheScores);
      } catch (err) {
        console.error(err);
        setError("Failed to load model details");
      } finally {
        setLoading(false);
      }
    })();
  }, [selectedPdf, selectedModel]);

  const activeScores = useMemo(() => {
    const evalScores = evaluation?.scores;
    if (evalScores) {
      return {
        overall: evalScores.overall_score,
        schema: evalScores.schema_compliance,
        structure: evalScores.structural_accuracy,
        semantic: evalScores.semantic_accuracy,
        config: evalScores.config_accuracy,
        source: "evaluation",
      };
    }
    if (cacheScores) {
      return { ...cacheScores, source: "cache" } as const;
    }
    return null;
  }, [evaluation, cacheScores]);

  return (
    <section className="document-explorer">
      <div className="section-header">
        <div>
          <p className="eyebrow">Documents</p>
          <h3>PDF & JSON Explorer</h3>
          <p className="subtext">
            Browse input PDFs, open model outputs, and compare against the source of truth with
            LLM evaluation notes.
          </p>
        </div>
        {activeScores && (
          <div className="score-chip">
            Overall Score: {formatPercent(activeScores.overall)}
            <span className="score-chip-sub">
              {activeScores.source === "evaluation" ? "LLM evaluation" : "Cache average"}
            </span>
          </div>
        )}
      </div>

      <div className="selector-row">
        <div className="selector">
          <label htmlFor="pdf-select">PDF</label>
          <select
            id="pdf-select"
            value={selectedPdf?.stem || ""}
            onChange={(e) => {
              const next = pdfs.find((p) => p.stem === e.target.value) || null;
              setSelectedPdf(next);
            }}
          >
            {pdfs.map((pdf) => (
              <option key={pdf.stem} value={pdf.stem}>
                {pdf.name} {pdf.best_score ? `(${pdf.best_score}%)` : ""}
              </option>
            ))}
          </select>
        </div>

        <div className="selector">
          <label htmlFor="model-select">Model Output</label>
          <select
            id="model-select"
            value={selectedModel ? `${selectedModel.providerDir}/${selectedModel.modelDir}` : ""}
            onChange={(e) => {
              const [providerDir, modelDir] = e.target.value.split("/");
              const next =
                models.find((m) => m.providerDir === providerDir && m.modelDir === modelDir) || null;
              setSelectedModel(next);
            }}
            disabled={models.length === 0}
          >
            {models.map((model) => (
              <option
                key={`${model.providerDir}/${model.modelDir}`}
                value={`${model.providerDir}/${model.modelDir}`}
              >
                {model.metadata.provider} / {model.metadata.model_id}
                {model.scores?.overall ? ` (${formatPercent(model.scores.overall)})` : ""}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      <div className="viewer-grid">
        <div className="pdf-viewer-card">
          <div className="pdf-header">
            <h4>Original PDF</h4>
            <span className="muted">
              {selectedPdf ? selectedPdf.name : "Select a PDF to view"}
            </span>
          </div>
          {selectedPdf ? (
            <iframe
              title="pdf-viewer"
              src={`/api/pdfs/${selectedPdf.stem}/pdf`}
              className="pdf-frame"
            />
          ) : (
            <div className="empty-state small cardish">
              <div className="empty-icon">📄</div>
              <p>Select a PDF to preview</p>
              <span className="muted">Choose a document to load the viewer.</span>
            </div>
          )}
        </div>

        <div className="json-split">
          <JsonPane title="Source of Truth" data={sourceJson} />
          <JsonPane
            title={
              selectedModel
                ? `${selectedModel.metadata.provider} / ${selectedModel.metadata.model_id}`
                : "Model Output"
            }
            data={modelJson}
          />
        </div>
      </div>

      <div className="evaluation-panel">
        <div className="evaluation-header">
          <h4>Evaluation Details</h4>
          <span className="muted">
            {isLikelyLlmReasoning(evaluation)
              ? "Reasoning from LLM evaluation"
              : "No LLM reasoning detected (deterministic cache)"}
          </span>
        </div>

        {loading && (
          <div className="loading-inline">
            <div className="spinner small" />
            <span>Loading evaluation...</span>
          </div>
        )}

        {!loading && !evaluation && (
          <div className="empty-state small cardish">
            <div className="empty-icon">ℹ️</div>
            <p>No detailed evaluation found for this model yet.</p>
            <span className="muted">
              Run the LLM evaluation pipeline to see reasoning and per-field scores.
            </span>
          </div>
        )}

        {activeScores && (
          <div className="score-badge-grid">
            <ScoreBadge label="Overall" value={activeScores.overall} />
            <ScoreBadge label="Schema" value={activeScores.schema} />
            <ScoreBadge label="Structure" value={activeScores.structure} />
            <ScoreBadge label="Semantic" value={activeScores.semantic} />
            <ScoreBadge label="Config" value={activeScores.config} />
          </div>
        )}

        {evaluation && evaluation.sections && evaluation.sections.length > 0 && (
          <div className="section-cards">
            {evaluation.sections.map((section, idx) => (
              <div key={`${section.source_section_name}-${idx}`} className="section-card">
                <div className="section-card-header">
                  <div>
                    <div className="section-title">{section.source_section_name}</div>
                    <div className="muted">
                      Matched fields: {section.matched_fields}/{section.source_field_count}
                    </div>
                  </div>
                  <div className="section-score">{formatPercent(section.section_score)}</div>
                </div>
                <div className="field-grid">
                  {section.fields.map((field, fIdx) => (
                    <div key={`${field.source_field_id}-${fIdx}`} className="field-card">
                      <div className="field-header">
                        <div>
                          <div className="field-name">{field.source_name}</div>
                          <div className="muted">
                            {field.model_name ? `Model: ${field.model_name}` : "Missing in model"}
                          </div>
                        </div>
                        <div className="field-score">{formatPercent(field.overall_score)}</div>
                      </div>
                      <div className="field-meta">
                        <span>Name: {formatPercent(field.name_similarity)}</span>
                        <span>Options: {formatPercent(field.options_similarity || field.options_exact_match)}</span>
                      </div>
                      <div className="field-reason">
                        {field.reasoning || "No LLM reasoning provided for this field."}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

