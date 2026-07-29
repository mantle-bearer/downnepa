"use client";

import { useState } from "react";

const REVIEW_QUEUE = [
  { id: "R-1042", area: "Yaba", state: "Light don go", evidence: "8 reports · official notice", age: "3m", score: 96 },
  { id: "R-1041", area: "Ojodu Berger", state: "Unstable supply", evidence: "4 independent reports", age: "14m", score: 76 },
  { id: "R-1038", area: "Surulere", state: "Light don come", evidence: "1 new account", age: "32m", score: 28 },
];

const PIPELINES = [
  { source: "Community observations", state: "Healthy", detail: "214 raw · 198 clean · 16 quarantined", run: "2m ago" },
  { source: "DisCo public notices", state: "Healthy", detail: "12 raw · 11 clean · 1 quarantined", run: "18m ago" },
  { source: "Weather enrichment", state: "Delayed", detail: "Next retry in 11 minutes", run: "49m ago" },
];

const MODELS = [
  { name: "lagos-risk-v0.3", state: "Active", auc: ".81", brier: ".16", data: "3,842 incidents", date: "28 Jul" },
  { name: "lagos-risk-v0.4-rc1", state: "Shadow", auc: ".84", brier: ".14", data: "4,109 incidents", date: "29 Jul" },
  { name: "lagos-risk-v0.2", state: "Retired", auc: ".77", brier: ".20", data: "3,106 incidents", date: "02 Jun" },
];

export default function Admin() {
  const [queue, setQueue] = useState(REVIEW_QUEUE);
  const [tab, setTab] = useState<"overview" | "pipeline" | "models">("overview");
  const [message, setMessage] = useState("Review workspace uses deterministic data. Production actions are handled by the FastAPI admin API.");

  function review(id: string, action: "verified" | "quarantined") {
    setQueue((items) => items.filter((item) => item.id !== id));
    setMessage(`${id} ${action}. An immutable audit event was prepared.`);
  }

  return (
    <main className="admin-shell">
      <aside className="admin-rail">
        <a className="brand" href="/" aria-label="Back to DownNepa monitor">
          <span className="brand-mark"><i /></span>
          <span className="brand-name">Down<span>Nepa</span></span>
        </a>
        <nav>
          <button className={tab === "overview" ? "active" : ""} onClick={() => setTab("overview")}>Overview</button>
          <button className={tab === "pipeline" ? "active" : ""} onClick={() => setTab("pipeline")}>Data pipeline</button>
          <button className={tab === "models" ? "active" : ""} onClick={() => setTab("models")}>Model registry</button>
        </nav>
        <div className="admin-user"><span>AG</span><div><strong>Admin</strong><small>Role verified</small></div></div>
      </aside>

      <section className="admin-main">
        <header className="admin-head">
          <div><span className="eyebrow">Protected operations</span><h1>{tab === "overview" ? "Trust overview" : tab === "pipeline" ? "Data pipeline" : "Model registry"}</h1></div>
          <a href="/">View public monitor ↗</a>
        </header>
        <div className="admin-banner" role="status"><span>i</span>{message}</div>

        {tab === "overview" && <>
          <div className="admin-metrics">
            <article><span>Pending review</span><strong>{queue.length}</strong><small>evidence groups</small></article>
            <article><span>Verified today</span><strong>27</strong><small>canonical incidents</small></article>
            <article><span>Source health</span><strong>92%</strong><small>1 delayed connector</small></article>
            <article><span>Active model</span><strong className="small-value">v0.3</strong><small>shadow: v0.4-rc1</small></article>
          </div>
          <section className="admin-panel">
            <div className="admin-panel-title"><div><span className="card-label">Reconciliation queue</span><h2>Reports awaiting a decision</h2></div><b>{queue.length} open</b></div>
            <div className="review-table">
              {queue.map((item) => <article key={item.id}>
                <div><small>{item.id}</small><strong>{item.area}</strong></div>
                <div><small>Observed state</small><strong>{item.state}</strong></div>
                <div><small>Evidence</small><span>{item.evidence}</span></div>
                <div className="confidence"><small>Confidence</small><strong>{item.score}%</strong></div>
                <time>{item.age}</time>
                <div className="review-actions"><button onClick={() => review(item.id, "quarantined")}>Quarantine</button><button onClick={() => review(item.id, "verified")}>Verify</button></div>
              </article>)}
              {!queue.length && <div className="empty-state">Queue clear. No observation becomes an incident without a recorded decision.</div>}
            </div>
          </section>
        </>}

        {tab === "pipeline" && <section className="admin-panel">
          <div className="admin-panel-title"><div><span className="card-label">Raw → clean → verified</span><h2>Source runs and quarantine</h2></div><button onClick={() => setMessage("Manual ingestion run queued with id PIPE-208.")}>Run ingestion</button></div>
          <div className="pipeline-flow"><span>Raw snapshots<b>226</b></span><i>→</i><span>Validated<b>209</b></span><i>→</i><span>Quarantine<b>17</b></span><i>→</i><span>Verified incidents<b>27</b></span></div>
          <div className="source-table">{PIPELINES.map((item) => <article key={item.source}><span className={`source-state ${item.state.toLowerCase()}`} /> <strong>{item.source}</strong><span>{item.detail}</span><b>{item.state}</b><time>{item.run}</time></article>)}</div>
          <div className="guardrail"><strong>Training guardrail</strong><p>Only verified incidents enter training snapshots. Predictions, pending reports and quarantined rows are excluded by construction.</p></div>
        </section>}

        {tab === "models" && <section className="admin-panel">
          <div className="admin-panel-title"><div><span className="card-label">Loosely coupled inference</span><h2>Six-hour outage risk models</h2></div><button onClick={() => setMessage("Model registration expects an artifact URI, feature schema, checksum and evaluation record.")}>Register model</button></div>
          <div className="model-table">{MODELS.map((model) => <article key={model.name}>
            <div><strong>{model.name}</strong><small>{model.data} · trained {model.date}</small></div>
            <span className={`model-state ${model.state.toLowerCase()}`}>{model.state}</span>
            <div><small>ROC AUC</small><strong>{model.auc}</strong></div>
            <div><small>Brier</small><strong>{model.brier}</strong></div>
            <button disabled={model.state === "Active"} onClick={() => setMessage(`${model.name} activation requires a final confirmation and creates a rollback point.`)}>{model.state === "Active" ? "Serving" : "Review"}</button>
          </article>)}</div>
          <div className="guardrail"><strong>Stable plugin contract</strong><p>The API loads each artifact through the same predict(features) boundary. Candidate, shadow, active, retired and rejected are registry states, not application rewrites.</p></div>
        </section>}
      </section>
    </main>
  );
}
