"use client";

import { useMemo, useState } from "react";

type Status = "on" | "out" | "unstable" | "unknown";

type Area = {
  slug: string;
  name: string;
  lga: string;
  disco: "Ikeja Electric" | "Eko DisCo";
  band: "A" | "B" | "C";
  status: Status;
  freshness: string;
  confidence: number;
  reports: number;
  risk: number;
  supply: number;
  feeder: string;
  updated: string;
  history: number[];
};

const AREAS: Area[] = [
  {
    slug: "ikeja-gra",
    name: "Ikeja GRA",
    lga: "Ikeja",
    disco: "Ikeja Electric",
    band: "A",
    status: "on",
    freshness: "8 mins ago",
    confidence: 92,
    reports: 7,
    risk: 18,
    supply: 21.4,
    feeder: "Airport 11kV",
    updated: "10:42 WAT",
    history: [20.1, 21.7, 18.4, 22.2, 20.8, 21.2, 21.4],
  },
  {
    slug: "ojodu-berger",
    name: "Ojodu Berger",
    lga: "Kosofe",
    disco: "Ikeja Electric",
    band: "B",
    status: "unstable",
    freshness: "14 mins ago",
    confidence: 76,
    reports: 4,
    risk: 48,
    supply: 16.8,
    feeder: "Olowora 11kV",
    updated: "10:36 WAT",
    history: [15.2, 17.4, 13.8, 18.1, 16.9, 15.7, 16.8],
  },
  {
    slug: "yaba",
    name: "Yaba",
    lga: "Lagos Mainland",
    disco: "Eko DisCo",
    band: "B",
    status: "out",
    freshness: "3 mins ago",
    confidence: 95,
    reports: 12,
    risk: 71,
    supply: 14.3,
    feeder: "Sabo 11kV",
    updated: "10:47 WAT",
    history: [17.8, 15.1, 16.4, 12.8, 18.2, 15.4, 14.3],
  },
  {
    slug: "lekki-phase-1",
    name: "Lekki Phase 1",
    lga: "Eti-Osa",
    disco: "Eko DisCo",
    band: "A",
    status: "on",
    freshness: "19 mins ago",
    confidence: 84,
    reports: 5,
    risk: 24,
    supply: 20.6,
    feeder: "Maroko 11kV",
    updated: "10:31 WAT",
    history: [19.9, 21.3, 20.8, 19.4, 22.1, 20.2, 20.6],
  },
  {
    slug: "surulere",
    name: "Surulere",
    lga: "Surulere",
    disco: "Eko DisCo",
    band: "C",
    status: "unknown",
    freshness: "2 hrs ago",
    confidence: 28,
    reports: 1,
    risk: 39,
    supply: 12.7,
    feeder: "Bode Thomas 11kV",
    updated: "08:46 WAT",
    history: [14.2, 13.6, 11.9, 15.1, 12.3, 13.4, 12.7],
  },
];

const INCIDENTS = [
  { area: "Yaba", event: "Outage verified", time: "3 mins ago", source: "8 residents + feeder notice", status: "out" },
  { area: "Ojodu Berger", event: "Supply unstable", time: "14 mins ago", source: "4 independent reports", status: "unstable" },
  { area: "Lekki Phase 1", event: "Power restored", time: "19 mins ago", source: "3 residents confirmed", status: "on" },
  { area: "Ikeja GRA", event: "Power restored", time: "42 mins ago", source: "Community verified", status: "on" },
];

const STATUS_COPY: Record<Status, { label: string; sentence: string }> = {
  on: { label: "Power available", sentence: "Recent verified reports indicate that electricity is currently available." },
  out: { label: "Outage verified", sentence: "Multiple independent reports indicate an active power outage." },
  unstable: { label: "Supply unstable", sentence: "Residents are reporting repeated interruptions or low-quality supply." },
  unknown: { label: "Status uncertain", sentence: "There is not enough recent evidence to state the current condition." },
};

function Bars({ values }: { values: number[] }) {
  return (
    <div className="history-bars" aria-label="Seven-day supply hours chart">
      {values.map((value, index) => (
        <div className="bar-wrap" key={`${value}-${index}`}>
          <span className="bar-value">{value.toFixed(0)}h</span>
          <span className="bar-track">
            <span className="bar-fill" style={{ height: `${Math.max(12, (value / 24) * 100)}%` }} />
          </span>
          <span className="bar-day">{["Thu", "Fri", "Sat", "Sun", "Mon", "Tue", "Today"][index]}</span>
        </div>
      ))}
    </div>
  );
}

function StatusDot({ status }: { status: Status | string }) {
  return <span className={`status-dot ${status}`} aria-hidden="true" />;
}

function AccessDialog({
  intent,
  area,
  close,
  complete,
}: {
  intent: "out" | "restored" | "signin";
  area: Area;
  close: () => void;
  complete: (message: string) => void;
}) {
  const [step, setStep] = useState<"email" | "code" | "done">("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const reportLabel = intent === "out" ? "Light don go" : "Light don come";

  function sendCode(event: React.FormEvent) {
    event.preventDefault();
    if (email.includes("@")) setStep("code");
  }

  function verify(event: React.FormEvent) {
    event.preventDefault();
    if (code.length === 6) setStep("done");
  }

  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={close}>
      <section className="access-dialog" role="dialog" aria-modal="true" aria-labelledby="access-title" onMouseDown={(event) => event.stopPropagation()}>
        <button className="dialog-close" type="button" onClick={close} aria-label="Close">×</button>
        <span className="eyebrow">{intent === "signin" ? "Passwordless access" : "Contribute evidence"}</span>
        <h2 id="access-title">{step === "done" && intent !== "signin" ? "Confirm your observation" : "No password. Just a quick code."}</h2>
        {step === "email" && <form onSubmit={sendCode}>
          <p>Enter your email. We will send a six-digit code that expires in 10 minutes.</p>
          <label>Email address<input autoFocus required type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" /></label>
          <button type="submit">Send my code →</button>
          <small>Public monitoring never needs an account.</small>
        </form>}
        {step === "code" && <form onSubmit={verify}>
          <p>Enter the code sent to <strong>{email}</strong>. For this review build, any six digits demonstrate the flow.</p>
          <label>Six-digit code<input autoFocus required inputMode="numeric" pattern="[0-9]{6}" maxLength={6} value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))} placeholder="000000" /></label>
          <button type="submit">Verify code →</button>
          <button className="text-action" type="button" onClick={() => setStep("email")}>Use another email</button>
        </form>}
        {step === "done" && intent === "signin" && <div className="dialog-complete">
          <span>✓</span><p>You are signed in for this review session.</p>
          <button type="button" onClick={() => complete("Signed in. You can now contribute evidence and save places.")}>Continue</button>
        </div>}
        {step === "done" && intent !== "signin" && <div className="report-confirm">
          <div><small>Area</small><strong>{area.name}</strong></div>
          <div><small>Observation</small><strong>{reportLabel}</strong></div>
          <p>This is stored as a report, not a verified incident. It will be deduplicated and reconciled with independent evidence.</p>
          <button type="button" onClick={() => complete(`${reportLabel} report received for ${area.name}. It is pending independent verification.`)}>Submit observation →</button>
        </div>}
      </section>
    </div>
  );
}

export default function Home() {
  const [areaSlug, setAreaSlug] = useState("ojodu-berger");
  const [searchOpen, setSearchOpen] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [accessIntent, setAccessIntent] = useState<"out" | "restored" | "signin" | null>(null);
  const area = useMemo(() => AREAS.find((item) => item.slug === areaSlug) ?? AREAS[0], [areaSlug]);
  const copy = STATUS_COPY[area.status];

  function chooseArea(slug: string) {
    setAreaSlug(slug);
    setSearchOpen(false);
    setNotice(null);
  }

  return (
    <main className="site-shell">
      <header className="topbar">
        <a className="brand" href="#monitor" aria-label="DownNepa home">
          <span className="brand-mark"><i /></span>
          <span className="brand-name">Down<span>Nepa</span></span>
          <small>Lagos</small>
        </a>
        <nav className="desktop-nav" aria-label="Primary navigation">
          <a className="active" href="#monitor">Monitor</a>
          <a href="#incidents">Incidents</a>
          <a href="#trust">How it works</a>
          <a href="#coverage">Coverage</a>
          <a href="/admin">Admin</a>
        </nav>
        <div className="top-actions">
          <button className="icon-button" type="button" aria-label="Toggle theme">◐</button>
          <button className="sign-in-button" type="button" onClick={() => setAccessIntent("signin")}>
            Sign in
          </button>
        </div>
      </header>

      {notice && (
        <div className="notice" role="status">
          <span>{notice}</span>
          <button type="button" onClick={() => setNotice(null)} aria-label="Dismiss notice">×</button>
        </div>
      )}

      <section className="monitor-section" id="monitor">
        <div className="intro">
          <div>
            <span className="eyebrow"><i /> Lagos electricity, clearly reported</span>
            <h1>Know if light dey.<br /><em>Before you step out.</em></h1>
            <p>
              Live community reports, verified incidents and honest outage predictions
              for Lagos. Monitoring is always open, no account required.
            </p>
          </div>
          <div className="live-summary">
            <span className="pulse" />
            <strong>24 areas active</strong>
            <small>updated moments ago</small>
          </div>
        </div>

        <div className="area-picker">
          <label htmlFor="area-select">Where in Lagos?</label>
          <button
            id="area-select"
            className="area-select-button"
            type="button"
            aria-haspopup="listbox"
            aria-expanded={searchOpen}
            onClick={() => setSearchOpen((open) => !open)}
          >
            <span className="pin">⌖</span>
            <span><strong>{area.name}</strong><small>{area.lga} · {area.disco}</small></span>
            <span className="chevron">⌄</span>
          </button>
          {searchOpen && (
            <div className="area-menu" role="listbox" aria-label="Select a Lagos area">
              {AREAS.map((item) => (
                <button
                  type="button"
                  role="option"
                  aria-selected={item.slug === area.slug}
                  className={item.slug === area.slug ? "selected" : ""}
                  key={item.slug}
                  onClick={() => chooseArea(item.slug)}
                >
                  <StatusDot status={item.status} />
                  <span><strong>{item.name}</strong><small>{item.disco} · Band {item.band}</small></span>
                  <b>{STATUS_COPY[item.status].label}</b>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="dashboard-grid">
          <article className={`status-card ${area.status}`}>
            <div className="card-topline">
              <span>Current status</span>
              <span className="verified-chip">{area.confidence >= 70 ? "Verified evidence" : "Limited evidence"}</span>
            </div>
            <div className="status-main">
              <div className="power-orb">
                <span>ϟ</span>
                <i />
              </div>
              <div>
                <p className="area-name">{area.name}</p>
                <h2>{copy.label}</h2>
                <p className="status-sentence">{copy.sentence}</p>
              </div>
            </div>
            <div className="evidence-row">
              <div><strong>{area.confidence}%</strong><span>confidence</span></div>
              <div><strong>{area.reports}</strong><span>independent reports</span></div>
              <div><strong>{area.freshness}</strong><span>latest evidence</span></div>
            </div>
            <div className="card-foot">
              <span><StatusDot status={area.status} /> Last checked {area.updated}</span>
              <button type="button" onClick={() => setNotice(`Evidence for ${area.name}: community reports are reconciled separately from model predictions.`)}>
                View evidence →
              </button>
            </div>
          </article>

          <aside className="report-card">
            <span className="card-label">Help your area stay accurate</span>
            <h3>What is happening near you?</h3>
            <p>Your observation stays separate from predictions until it is independently verified.</p>
            <div className="report-actions">
              <button type="button" className="report-out" onClick={() => setAccessIntent("out")}>
                <span>↓</span><strong>Light don go</strong><small>Report an outage</small>
              </button>
              <button type="button" className="report-back" onClick={() => setAccessIntent("restored")}>
                <span>ϟ</span><strong>Light don come</strong><small>Report restoration</small>
              </button>
            </div>
            <small className="auth-note">Monitoring stays public. Quick sign-in is required only to prevent duplicate or anonymous abuse.</small>
          </aside>
        </div>
      </section>

      <section className="insight-grid">
        <article className="panel history-panel">
          <div className="panel-heading">
            <div><span className="card-label">Observed supply</span><h3>Last 7 days in {area.name}</h3></div>
            <div className="metric"><strong>{area.supply}h</strong><small>daily average</small></div>
          </div>
          <Bars values={area.history} />
          <div className="source-note">
            <span>Community observations</span>
            <span>Verified incidents only</span>
          </div>
        </article>

        <article className="panel risk-panel">
          <div className="panel-heading">
            <div><span className="card-label">Next 6 hours</span><h3>Outage risk</h3></div>
            <span className={`risk-badge ${area.risk >= 60 ? "high" : area.risk >= 35 ? "medium" : "low"}`}>
              {area.risk >= 60 ? "High" : area.risk >= 35 ? "Moderate" : "Low"}
            </span>
          </div>
          <div className="risk-score">
            <strong>{area.risk}%</strong>
            <div className="risk-track"><span style={{ width: `${area.risk}%` }} /></div>
          </div>
          <p>
            Based on verified outage history, service band, time of day and
            recent Lagos weather. Predictions never create incident reports.
          </p>
          <div className="model-line">
            <span>Baseline model</span><b>lagos-risk-v0.3</b><small>Evaluated 28 Jul 2026</small>
          </div>
        </article>
      </section>

      <section className="incidents-section" id="incidents">
        <div className="section-title">
          <div><span className="eyebrow">Verified across Lagos</span><h2>What just happened</h2></div>
          <button type="button" onClick={() => setNotice("The full incident explorer is part of the next DownNepa milestone.")}>Explore all incidents →</button>
        </div>
        <div className="incident-list">
          {INCIDENTS.map((incident) => (
            <article key={`${incident.area}-${incident.event}`}>
              <span className={`incident-icon ${incident.status}`}><StatusDot status={incident.status} /></span>
              <div><h3>{incident.area}</h3><p>{incident.event}</p></div>
              <span className="incident-source">{incident.source}</span>
              <time>{incident.time}</time>
            </article>
          ))}
        </div>
      </section>

      <section className="trust-section" id="trust">
        <div className="trust-copy">
          <span className="eyebrow">Built for trustworthy data</span>
          <h2>Reports are evidence.<br />Not automatic truth.</h2>
          <p>
            DownNepa keeps community observations, verified incidents and model
            predictions in separate layers. That prevents the model from
            learning from its own guesses.
          </p>
          <a href="#monitor">See how status is verified →</a>
        </div>
        <div className="trust-steps">
          <div><b>01</b><span><strong>Observe</strong><small>A resident reports a power change.</small></span></div>
          <div><b>02</b><span><strong>Corroborate</strong><small>Independent people and official sources add evidence.</small></span></div>
          <div><b>03</b><span><strong>Verify</strong><small>Reports merge into one auditable outage incident.</small></span></div>
          <div><b>04</b><span><strong>Learn</strong><small>Only verified incidents enter versioned training data.</small></span></div>
        </div>
      </section>

      <section className="coverage-section" id="coverage">
        <article>
          <span className="disco-mark ie">IE</span>
          <div><span className="card-label">Lagos North</span><h3>Ikeja Electric</h3><p>Ikeja, Alimosho, Ikorodu, Oshodi, Agege, Shomolu and surrounding areas.</p></div>
          <strong>14 areas live</strong>
        </article>
        <article>
          <span className="disco-mark ek">EK</span>
          <div><span className="card-label">Lagos South</span><h3>Eko DisCo</h3><p>Lagos Island, Yaba, Surulere, Apapa, Lekki, Ajah, Festac and surrounding areas.</p></div>
          <strong>10 areas live</strong>
        </article>
      </section>

      <footer>
        <div className="brand footer-brand">
          <span className="brand-mark"><i /></span>
          <span className="brand-name">Down<span>Nepa</span></span>
        </div>
        <p>Clearer electricity information for Lagos, built from evidence.</p>
        <div><a href="#trust">Data policy</a><a href="#coverage">Coverage</a><a href="/admin">Admin</a><a href="#monitor">Monitor</a></div>
      </footer>
      {accessIntent && <AccessDialog
        intent={accessIntent}
        area={area}
        close={() => setAccessIntent(null)}
        complete={(message) => { setAccessIntent(null); setNotice(message); }}
      />}
    </main>
  );
}
