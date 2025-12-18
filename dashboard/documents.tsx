import React from "react";
import { createRoot } from "react-dom/client";
import { DocumentExplorer } from "./components/DocumentExplorer";
import "./styles.css";

function DocumentPage() {
  return (
    <div className="doc-page">
      <header className="header">
        <div className="header-content">
          <div className="logo">
            <span className="logo-icon">📊</span>
            <h1>OCR-AI Evaluation Dashboard</h1>
          </div>
          <div className="header-actions">
            <a className="btn btn-ghost" href="/">
              Dashboard
            </a>
          </div>
        </div>
      </header>

      <main className="doc-main">
        <header className="doc-header">
          <div>
            <div className="doc-pill">Documents</div>
            <h1>PDF & JSON Explorer</h1>
            <p>
              Browse input PDFs, open model outputs, and compare against the source of truth with LLM
              evaluation notes. Use the dashboard for scores; use this page for deep dives.
            </p>
          </div>
        </header>

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

