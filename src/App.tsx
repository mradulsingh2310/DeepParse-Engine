import { APITester } from "./APITester";
import "./index.css";

type SegmentKey = "dataAccess" | "governance" | "licensing" | "feedback";

type Bar = {
  label: string;
  change: string;
  values: { key: SegmentKey; value: number }[];
};

const palette: Record<SegmentKey, { label: string; color: string }> = {
  dataAccess: { label: "Data access", color: "var(--color-cyan)" },
  governance: { label: "Governance", color: "var(--color-indigo)" },
  licensing: { label: "Licensing", color: "var(--color-amber)" },
  feedback: { label: "Public feedback", color: "var(--color-green)" },
};

const opennessBars: Bar[] = [
  {
    label: "United States",
    change: "+2.1",
    values: [
      { key: "dataAccess", value: 32 },
      { key: "governance", value: 24 },
      { key: "licensing", value: 14 },
      { key: "feedback", value: 10 },
    ],
  },
  {
    label: "United Kingdom",
    change: "+1.4",
    values: [
      { key: "dataAccess", value: 30 },
      { key: "governance", value: 22 },
      { key: "licensing", value: 16 },
      { key: "feedback", value: 9 },
    ],
  },
  {
    label: "Germany",
    change: "+0.6",
    values: [
      { key: "dataAccess", value: 27 },
      { key: "governance", value: 21 },
      { key: "licensing", value: 13 },
      { key: "feedback", value: 11 },
    ],
  },
  {
    label: "Canada",
    change: "+1.0",
    values: [
      { key: "dataAccess", value: 28 },
      { key: "governance", value: 20 },
      { key: "licensing", value: 12 },
      { key: "feedback", value: 12 },
    ],
  },
];

const headlineMetrics = [
  {
    label: "Global openness index",
    value: "74.2",
    change: "+1.4",
    sublabel: "vs last month",
  },
  {
    label: "Countries tracked",
    value: "46",
    change: "+3",
    sublabel: "added recently",
  },
  {
    label: "Average transparency",
    value: "81%",
    change: "+0.9",
    sublabel: "steady improvement",
  },
];

const featuredInsights = [
  "North America leads with resilient data access and licensing clarity.",
  "Europe shows balanced governance with strong civic feedback loops.",
  "Emerging markets are catching up fast on transparent policy releases.",
];

function StackBar({ bar }: { bar: Bar }) {
  const total = bar.values.reduce((sum, segment) => sum + segment.value, 0);

  return (
    <div className="bar-row">
      <div className="bar-label">
        <span className="bar-label__name">{bar.label}</span>
        <span className="bar-label__change">{bar.change}</span>
      </div>
      <div className="stack">
        {bar.values.map((segment) => {
          const meta = palette[segment.key];
          return (
            <div
              key={segment.key}
              className="stack__segment"
              style={{
                width: `${(segment.value / total) * 100}%`,
                background: meta.color,
              }}
              aria-label={`${meta.label}: ${segment.value} points`}
            />
          );
        })}
      </div>
      <div className="bar-value">{total.toFixed(0)}</div>
    </div>
  );
}

export function App() {
  return (
    <div className="page-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand__dot" />
          <div>
            <div className="brand__title">Artificial Analysis</div>
            <div className="brand__subtitle">Openness Index</div>
          </div>
        </div>
        <div className="topbar__actions">
          <button className="ghost-button">Methodology</button>
          <button className="solid-button">Download report</button>
        </div>
      </header>

      <main className="page-content">
        <section className="hero">
          <div className="hero__copy glass-card">
            <div className="pill">Live benchmark</div>
            <h1>
              Openness index, refactored with clean analytics-inspired visuals
            </h1>
            <p>
              A calmer, editorial layout inspired by{" "}
              <a
                className="link"
                target="_blank"
                rel="noreferrer"
                href="https://artificialanalysis.ai/?openness=openness-index-components-stacked-bar-chart"
              >
                Artificial Analysis
              </a>{" "}
              so you can scan signals, compare regions, and test the API without
              fighting the UI.
            </p>
            <div className="metrics-grid">
              {headlineMetrics.map((metric) => (
                <div key={metric.label} className="metric-card">
                  <div className="metric-card__label">{metric.label}</div>
                  <div className="metric-card__value">
                    {metric.value}
                    <span className="metric-card__suffix">pts</span>
                  </div>
                  <div className="metric-card__change">
                    {metric.change} • {metric.sublabel}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="insights glass-card">
            <div className="section-title">
              <span className="section-title__dot" />
              Field notes
            </div>
            <ul className="insights__list">
              {featuredInsights.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
            <div className="insights__footer">
              Updated hourly • Source: compiled public datasets
            </div>
          </div>
        </section>

        <section className="chart-panel glass-card">
          <div className="panel-header">
            <div>
              <div className="section-title">
                <span className="section-title__dot" />
                Openness index by component
              </div>
              <p className="panel-subtitle">
                Stacked view across key markets. Hover to inspect proportions.
              </p>
            </div>
            <div className="legend">
              {Object.entries(palette).map(([key, meta]) => (
                <div key={key} className="legend__item">
                  <span
                    className="legend__swatch"
                    style={{ background: meta.color }}
                  />
                  {meta.label}
                </div>
              ))}
            </div>
          </div>

          <div className="stacked-bars">
            {opennessBars.map((bar) => (
              <StackBar key={bar.label} bar={bar} />
            ))}
          </div>
        </section>

        <section className="api-panel glass-card">
          <div className="panel-header">
            <div>
              <div className="section-title">
                <span className="section-title__dot" />
                Try the API
              </div>
              <p className="panel-subtitle">
                Run a quick ping against your local endpoints without leaving
                the page.
              </p>
            </div>
            <a className="link subtle-link" href="/api/hello">
              View example response
            </a>
          </div>
          <APITester />
        </section>
      </main>
    </div>
  );
}

export default App;
