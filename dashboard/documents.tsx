import React from "react";
import { createRoot } from "react-dom/client";
import { DocumentExplorer } from "./components/DocumentExplorer";
import "./styles.css";

function DocumentPage() {
  return (
    <div className="doc-page">
      <header className="doc-hero">
        <div className="doc-hero-left">
          <div className="doc-pill">Documents</div>
          <h1>PDF & JSON Explorer</h1>
          <p>
            Browse input PDFs, open model outputs, and compare against the source of truth with
            LLM evaluation notes. Use the dashboard for scores; use this page for deep dives.
          </p>
          <div className="doc-actions">
            <a className="btn btn-primary" href="/">Back to Dashboard</a>
            <a className="btn btn-ghost" href="/api/evaluations" target="_blank" rel="noreferrer">
              View Evaluation API
            </a>
          </div>
        </div>
        <div className="doc-hero-right">
          <div className="doc-card">
            <div className="doc-card-title">Workflow</div>
            <ol>
              <li>Select a PDF to load its source and outputs</li>
              <li>Pick a model output to render JSON side by side</li>
              <li>Review LLM reasoning and scores per field</li>
            </ol>
          </div>
        </div>
      </header>

      <main className="doc-main">
        <DocumentExplorer />
      </main>
    </div>
  );
}

const root = createRoot(document.getElementById("doc-root")!);
root.render(
  <React.StrictMode>
    <DocumentPage />
  </React.StrictMode>
);

