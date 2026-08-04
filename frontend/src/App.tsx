import { FormEvent, ReactNode, useEffect, useRef, useState } from "react";

type Status = "on" | "out" | "unstable" | "unknown";
type ReportState = "out" | "restored" | "unstable";
type User = {
  id: number;
  email: string;
  display_name: string;
  role: "member" | "admin";
  trust_score: number;
  points: number;
};
type SupplyDay = { day: string; available_hours: number; observation_count: number; source_summary: string };
type Area = {
  slug: string;
  name: string;
  lga: string;
  disco: string;
  service_band: string;
  feeder: string;
  aliases: string[];
  status: Status;
  confidence: number;
  reports: number;
  freshness: string;
  supply: number | null;
  history: SupplyDay[];
};
type Incident = {
  id: number;
  area: string;
  area_slug: string;
  state: ReportState;
  confidence: number;
  verified_at: string;
  evidence_count: number;
  source_summary: string;
};

const EMPTY_AREA: Area = {
  slug: "",
  name: "Select an area",
  lga: "Lagos",
  disco: "",
  service_band: "?",
  feeder: "Search by area, street or landmark",
  aliases: [],
  status: "unknown",
  confidence: 0,
  reports: 0,
  freshness: "No location selected",
  supply: null,
  history: [],
};

const api = {
  token: () => localStorage.getItem("downnepa_token"),
  async call(path: string, options: RequestInit = {}) {
    const token = this.token();
    const response = await fetch(path, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(options.headers || {}),
      },
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Something went wrong" }));
      const detail = Array.isArray(error.detail)
        ? error.detail.map((item: { msg?: string }) => item.msg || "Invalid value").join(". ")
        : error.detail;
      throw new Error(detail || "Something went wrong");
    }
    return response.status === 204 ? null : response.json();
  },
};

function navigate(path: string) {
  history.pushState({}, "", path);
  dispatchEvent(new PopStateEvent("popstate"));
  const hash = new URL(path, location.origin).hash;
  requestAnimationFrame(() => {
    if (hash) document.querySelector(hash)?.scrollIntoView({ behavior: "smooth" });
    else scrollTo({ top: 0, behavior: "smooth" });
  });
}

function monitorPath() {
  const slug = localStorage.getItem("downnepa_last_area");
  return slug ? `/?area=${encodeURIComponent(slug)}#monitor` : "/#monitor";
}

function useEscape(close: () => void) {
  useEffect(() => {
    const handler = (event: KeyboardEvent) => event.key === "Escape" && close();
    addEventListener("keydown", handler);
    return () => removeEventListener("keydown", handler);
  }, [close]);
}

function formatRelative(value: string | null | undefined) {
  if (!value) return "No recent verified evidence";
  const seconds = Math.max(0, (Date.now() - new Date(value).getTime()) / 1000);
  if (seconds < 60) return "Just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} hr ago`;
  return `${Math.floor(seconds / 86400)} day${seconds < 172800 ? "" : "s"} ago`;
}

function stateToStatus(state: string): Status {
  if (state === "restored") return "on";
  return (["on", "out", "unstable"].includes(state) ? state : "unknown") as Status;
}

function Logo() {
  return (
    <a className="brand" href="/" onClick={(event) => { event.preventDefault(); navigate("/"); }} aria-label="DownNepa home">
      <span className="logo-mark" aria-hidden="true">ϟ</span><b>Down<span>Nepa</span></b><small>Lagos</small>
    </a>
  );
}

function Header({ user, theme, toggleTheme, onAuth, onLogout }: {
  user: User | null; theme: string; toggleTheme: () => void; onAuth: () => void; onLogout: () => void;
}) {
  const [menu, setMenu] = useState(false);
  const go = (path: string) => { setMenu(false); navigate(path); };
  return (
    <header className="header">
      <Logo />
      <nav aria-label="Main navigation">
        <a href="/#monitor">Monitor</a><a href="/#incidents">Incidents</a><a href="/#coverage">Coverage</a>
        {user && <a href="/dashboard" onClick={(event) => { event.preventDefault(); go("/dashboard"); }}>Dashboard</a>}
        {user?.role === "admin" && <a href="/admin" onClick={(event) => { event.preventDefault(); go("/admin"); }}>Admin</a>}
      </nav>
      <div className="head-actions">
        <button className="theme-button" onClick={toggleTheme} aria-label={`Use ${theme === "dark" ? "light" : "dark"} mode`}>{theme === "dark" ? "☀" : "☾"}</button>
        <button className="menu-button" onClick={() => setMenu(!menu)} aria-expanded={menu} aria-controls="mobile-menu" aria-label="Open navigation">☰</button>
        {user ? <div className="user-menu"><button onClick={() => go("/dashboard")}><span>{user.display_name.slice(0, 1).toUpperCase()}</span>{user.display_name.split(" ")[0]}</button><button className="logout" onClick={onLogout}>Log out</button></div> : <button className="auth-button" onClick={onAuth}>Sign up / Log in</button>}
      </div>
      {menu && <nav className="mobile-menu" id="mobile-menu" aria-label="Mobile navigation"><button onClick={() => go("/#monitor")}>Monitor</button><button onClick={() => go("/#incidents")}>Incidents</button><button onClick={() => go("/#coverage")}>Coverage</button>{user && <button onClick={() => go("/dashboard")}>Dashboard</button>}{user?.role === "admin" && <button onClick={() => go("/admin")}>Admin</button>}{user && <button onClick={onLogout}>Log out</button>}</nav>}
    </header>
  );
}

function Modal({ close, className = "", labelledBy, children }: { close: () => void; className?: string; labelledBy: string; children: ReactNode }) {
  useEscape(close);
  return <div className="modal-backdrop" onMouseDown={close}><section className={`modal ${className}`} role="dialog" aria-modal="true" aria-labelledby={labelledBy} onMouseDown={(event) => event.stopPropagation()}><button className="close" onClick={close} aria-label="Close dialog">×</button>{children}</section></div>;
}

function AuthModal({ close, onSuccess }: { close: () => void; onSuccess: (data: { access_token: string; user: User }) => void }) {
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [show, setShow] = useState(false);
  const emailRef = useRef<HTMLInputElement>(null);
  useEffect(() => emailRef.current?.focus(), []);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const data = await api.call(`/api/auth/${mode}`, { method: "POST", body: JSON.stringify(mode === "signup" ? { display_name: name, email, password } : { email, password }) });
      onSuccess(data);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Authentication failed"); }
    finally { setBusy(false); }
  }
  return <Modal close={close} className="auth-modal" labelledBy="auth-title"><span className="eyebrow">Member access</span><h2 id="auth-title">{mode === "login" ? "Welcome back" : "Join your power community"}</h2><p>No email verification. Enter your details and continue.</p><div className="auth-tabs" role="tablist"><button role="tab" aria-selected={mode === "login"} className={mode === "login" ? "active" : ""} onClick={() => { setMode("login"); setError(""); }}>Log in</button><button role="tab" aria-selected={mode === "signup"} className={mode === "signup" ? "active" : ""} onClick={() => { setMode("signup"); setError(""); }}>Create account</button></div><form onSubmit={submit}>{mode === "signup" && <label>Display name<input required minLength={2} value={name} onChange={(event) => setName(event.target.value)} autoComplete="name" placeholder="Goodluck Igbokwe" /></label>}<label>Email address<input ref={emailRef} required type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" placeholder="you@example.com" /></label><label>Password<div className="password-field"><input required minLength={mode === "signup" ? 8 : 1} type={show ? "text" : "password"} value={password} onChange={(event) => setPassword(event.target.value)} autoComplete={mode === "signup" ? "new-password" : "current-password"} placeholder={mode === "signup" ? "At least 8 characters" : "Your password"} /><button type="button" onClick={() => setShow(!show)} aria-label={`${show ? "Hide" : "Show"} password`}>{show ? "Hide" : "Show"}</button></div></label>{error && <div className="form-error" role="alert">{error}</div>}<button className="primary wide" disabled={busy}>{busy ? "Please wait…" : mode === "login" ? "Log in" : "Create my account"}</button></form><small>Monitoring remains available without an account.</small></Modal>;
}

function AreaSearch({ area, onSelect }: { area: Area; onSelect: (slug: string) => void }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    const needle = query.trim();
    if (!needle) { setMatches([]); setLoading(false); setError(""); return; }
    const controller = new AbortController(); setLoading(true); setError("");
    const timer = setTimeout(() => fetch(`/api/v1/locations/search?q=${encodeURIComponent(needle)}&limit=30`, { signal: controller.signal })
      .then(async (response) => { if (!response.ok) throw new Error("Location search is unavailable"); return response.json(); })
      .then((payload) => setMatches(payload.results))
      .catch((reason) => { if (reason.name !== "AbortError") setError(reason.message); })
      .finally(() => setLoading(false)), 250);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [query]);
  return <div className="area-search"><label id="area-search-label">Where in Lagos?</label><button className="area-trigger" onClick={() => setOpen(!open)} aria-expanded={open} aria-labelledby="area-search-label"><span className="target" aria-hidden="true">⌖</span><span><strong>{area.name}</strong><small>{area.lga}{area.disco ? ` · ${area.disco} · Band ${area.service_band || "?"}` : ""}</small></span><b aria-hidden="true">⌄</b></button>{open && <div className="area-popover"><div className="search-input"><span aria-hidden="true">⌕</span><input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search area, street or feeder…" aria-label="Search Lagos locations" /></div><div className="area-results" aria-live="polite">{loading && <div className="no-results"><strong>Searching Lagos…</strong></div>}{error && <div className="no-results"><strong>Search unavailable</strong><span>{error}. Please try again.</span></div>}{!loading && !error && matches.map((item) => { const status = stateToStatus(String(item.status)); const slug = String(item.service_area_slug); return <button className={slug === area.slug ? "selected" : ""} key={`${item.slug}-${item.canonical_name}`} onClick={() => { onSelect(slug); setOpen(false); setQuery(""); }}><i className={`dot ${status}`} /><span><strong>{String(item.canonical_name)}</strong><small>{String(item.parent || item.lga)}</small></span><em>{String(item.disco)} · Band {String(item.band || "?")}</em><b>{statusCopy[status].label}</b></button>; })}{!loading && !error && query && !matches.length && <div className="no-results"><strong>No mapped location found</strong><span>Try an LGA, nearby landmark or feeder name.</span></div>}{!query && <div className="no-results"><strong>Start typing to search</strong><span>Areas, streets and landmarks are searchable.</span></div>}</div></div>}</div>;
}

const statusCopy: Record<Status, { label: string; detail: string }> = {
  on: { label: "Power available", detail: "Recent verified evidence indicates electricity is currently available." },
  out: { label: "Outage verified", detail: "Multiple independent observations indicate an active outage." },
  unstable: { label: "Supply unstable", detail: "Residents report repeated interruptions or low-quality supply." },
  unknown: { label: "Status uncertain", detail: "There is not enough recent evidence to state the current condition." },
};

function ReportModal({ area, user, initialState, close, onNeedAuth, onDone }: { area: Area; user: User | null; initialState: ReportState; close: () => void; onNeedAuth: () => void; onDone: (message: string) => void }) {
  const [state, setState] = useState<ReportState>(initialState);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (!user) return <Modal close={close} className="compact" labelledBy="report-auth-title"><span className="eyebrow">Sign in to contribute</span><h2 id="report-auth-title">Monitoring stays public. Reporting needs an account.</h2><p>Accounts reduce duplicate abuse and give you credit when your report is verified.</p><button className="primary wide" onClick={onNeedAuth}>Sign up or log in</button></Modal>;
  async function submit() {
    setBusy(true); setError("");
    try { await api.call("/api/reports", { method: "POST", body: JSON.stringify({ area_slug: area.slug, state, note: note || null, observed_at: new Date().toISOString() }) }); onDone(`Report received for ${area.name}. You earned 5 points.`); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not submit report"); }
    finally { setBusy(false); }
  }
  return <Modal close={close} className="report-modal" labelledBy="report-title"><span className="eyebrow">Community observation</span><h2 id="report-title">What is happening in {area.name}?</h2><p>Your observation remains separate from verified incidents until corroborated.</p><div className="state-picker"><button className={state === "out" ? "active out" : ""} onClick={() => setState("out")} aria-pressed={state === "out"}><b>↓</b>Light don go</button><button className={state === "restored" ? "active on" : ""} onClick={() => setState("restored")} aria-pressed={state === "restored"}><b>ϟ</b>Light don come</button><button className={state === "unstable" ? "active unstable" : ""} onClick={() => setState("unstable")} aria-pressed={state === "unstable"}><b>≈</b>Unstable</button></div><label>Optional context<textarea maxLength={280} value={note} onChange={(event) => setNote(event.target.value)} placeholder="For example: transformer sparked, low voltage, whole street affected…" /></label><div className="char-count">{note.length}/280</div>{error && <div className="form-error" role="alert">{error}</div>}<button className="primary wide" disabled={busy} onClick={submit}>{busy ? "Submitting…" : "Submit observation"}</button></Modal>;
}

function Bars({ area }: { area: Area }) {
  const days = area.history.length ? area.history : Array.from({ length: 7 }, (_, index) => ({ day: `empty-${index}`, available_hours: 0, observation_count: 0, source_summary: "" }));
  return <div className="bars">{days.map((item) => <div key={item.day}><span>{item.available_hours.toFixed(0)}h</span><i><b style={{ height: `${item.available_hours / 24 * 100}%` }} /></i><small>{item.day.startsWith("empty") ? "—" : new Date(`${item.day}T12:00:00`).toLocaleDateString(undefined, { weekday: "short" })}</small></div>)}</div>;
}

function EvidenceModal({ area, incident, close }: { area: Area; incident?: Incident | null; close: () => void }) {
  const shownArea = incident?.area || area.name;
  const confidence = incident ? Math.round(incident.confidence * 100) : area.confidence;
  const count = incident?.evidence_count ?? area.reports;
  return <Modal close={close} className="evidence-modal" labelledBy="evidence-title"><span className="eyebrow">Evidence ledger</span><h2 id="evidence-title">{shownArea}</h2><div className="evidence-score"><strong>{confidence}%</strong><span>confidence from {count} independent observation{count === 1 ? "" : "s"}</span></div><ul><li><i className={`dot ${stateToStatus(incident?.state || area.status)}`} /><span><strong>{incident?.source_summary || "Recent resident confirmation"}</strong><small>Trust-weighted evidence · {formatRelative(incident?.verified_at || (area.freshness === "No location selected" ? null : area.freshness))}</small></span></li><li><i className="dot unstable" /><span><strong>Feeder metadata checked</strong><small>{area.feeder} · {area.disco || "Lagos service area"}</small></span></li><li><i className="dot unknown" /><span><strong>No prediction used</strong><small>Status is derived only from verified evidence</small></span></li></ul><p className="audit-note">Every verification decision is recorded in the admin audit trail.</p></Modal>;
}

function PublicMonitor({ user, onAuth }: { user: User | null; onAuth: () => void }) {
  const [area, setArea] = useState(EMPTY_AREA);
  const [loadingArea, setLoadingArea] = useState(false);
  const [reporting, setReporting] = useState<ReportState | null>(null);
  const [notice, setNotice] = useState("");
  const [evidence, setEvidence] = useState(false);
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);
  const [allIncidents, setAllIncidents] = useState(false);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [coverage, setCoverage] = useState<{ mapped_locations: number; discos: Array<{ disco: string; area_count: number }> } | null>(null);
  async function loadArea(slug: string, updateUrl = true) {
    if (!slug) return;
    setLoadingArea(true);
    try {
      const data = await api.call(`/api/status/${encodeURIComponent(slug)}`);
      setArea({ slug: data.area.slug, name: data.area.name, lga: data.area.lga, disco: data.area.disco, service_band: data.area.service_band || "?", feeder: data.area.feeder || "Feeder pending verification", aliases: data.area.aliases || [], status: stateToStatus(data.status), confidence: data.confidence, reports: data.evidence_count, freshness: formatRelative(data.freshness), supply: data.supply_average, history: data.supply_history || [] });
      localStorage.setItem("downnepa_last_area", data.area.slug);
      if (updateUrl) history.replaceState({}, "", `/?area=${encodeURIComponent(data.area.slug)}#monitor`);
    } catch (reason) { setNotice(reason instanceof Error ? reason.message : "Could not load area status"); }
    finally { setLoadingArea(false); }
  }
  useEffect(() => {
    api.call("/api/v1/discos/coverage").then(setCoverage).catch(() => setCoverage(null));
    api.call("/api/incidents?limit=30").then(setIncidents).catch(() => setIncidents([]));
    const slug = new URLSearchParams(location.search).get("area");
    if (slug) loadArea(slug, false);
  }, []);
  function startReport(state: ReportState) { if (!area.slug) { setNotice("Select an area before reporting power status."); return; } setReporting(state); }
  async function save() { if (!area.slug) { setNotice("Select an area before saving a place."); return; } if (!user) { onAuth(); return; } try { await api.call("/api/saved-places", { method: "POST", body: JSON.stringify({ area_slug: area.slug, label: area.name }) }); setNotice(`${area.name} saved to your dashboard.`); } catch (reason) { setNotice(reason instanceof Error ? reason.message : "Could not save place"); } }
  const shownIncidents = incidents.slice(0, allIncidents ? incidents.length : 4);
  return <main>{notice && <div className="toast" role="status">{notice}<button onClick={() => setNotice("")} aria-label="Dismiss message">×</button></div>}<section className="hero" id="monitor"><div className="hero-copy"><span className="eyebrow"><i /> Lagos electricity, clearly reported</span><h1>Know if light dey.<br /><em>Before you step out.</em></h1><p>Search your area or street, inspect verified evidence and report power changes. Monitoring is always open.</p></div><div className="live-chip"><i /><span><strong>{coverage ? `${coverage.mapped_locations} locations mapped` : "Coverage unavailable"}</strong><small>Evidence updated continuously</small></span></div><AreaSearch area={area} onSelect={loadArea} />{loadingArea && <div className="loading-note" role="status">Loading verified area evidence…</div>}<div className="status-layout"><article className={`status-card ${area.status}`}><header><span>Current status</span><b>{area.confidence >= 70 ? "Verified evidence" : "Limited evidence"}</b></header><div className="status-core"><div className="power-orb" aria-hidden="true">ϟ<i /></div><div><small>{area.name} · {area.feeder}</small><h2>{statusCopy[area.status].label}</h2><p>{statusCopy[area.status].detail}</p></div></div><div className="evidence-metrics"><div><strong>{area.confidence}%</strong><small>Confidence</small></div><div><strong>{area.reports}</strong><small>Independent reports</small></div><div><strong>{area.freshness}</strong><small>Latest evidence</small></div></div><footer><span><i className={`dot ${area.status}`} /> Source: verified observations</span><button disabled={!area.slug} onClick={() => { setSelectedIncident(null); setEvidence(true); }}>View evidence →</button></footer></article><aside className="action-card"><span className="eyebrow">Help your area stay accurate</span><h3>What is happening near you?</h3><p>Reports become useful evidence after independent corroboration.</p><div><button className="out-action" onClick={() => startReport("out")}><b>↓</b><span><strong>Light don go</strong><small>Report an outage</small></span></button><button className="on-action" onClick={() => startReport("restored")}><b>ϟ</b><span><strong>Light don come</strong><small>Report restoration</small></span></button></div><button className="save-action" disabled={!area.slug} onClick={save}>☆ {area.slug ? `Save ${area.name}` : "Select an area to save"}</button></aside></div></section><section className="insights"><article className="panel"><header><div><span className="eyebrow">Observed supply</span><h3>Last 7 days in {area.name}</h3></div><div className="metric"><strong>{area.supply === null ? "—" : `${area.supply}h`}</strong><small>Daily average</small></div></header><Bars area={area} /><footer><span>● Verified incidents</span><span>● Corroborated observations</span></footer></article><article className="panel prediction-disabled"><span className="eyebrow">Prediction model</span><h3>Outage prediction coming next</h3><div className="disabled-orb">ML</div><p>The search, evidence, reporting and data pipeline are operational. Probability output remains disabled until a trained model passes evaluation.</p><button disabled>Prediction unavailable</button></article></section><section className="incident-section" id="incidents"><header><div><span className="eyebrow">Verified across Lagos</span><h2>What just happened</h2></div>{incidents.length > 4 && <button onClick={() => setAllIncidents(!allIncidents)}>{allIncidents ? "Show less" : "Explore all incidents"} →</button>}</header>{shownIncidents.length ? <div className="incident-list">{shownIncidents.map((item) => { const status = stateToStatus(item.state); return <article key={item.id}><span className={`incident-symbol ${status}`}><i className={`dot ${status}`} /></span><div><strong>{item.area}</strong><small>{statusCopy[status].label}</small></div><span>{item.source_summary}</span><time dateTime={item.verified_at}>{formatRelative(item.verified_at)}</time><button onClick={() => { setSelectedIncident(item); setEvidence(true); }}>Details</button></article>; })}</div> : <div className="empty incident-empty"><b>✓</b><strong>No verified incidents yet</strong><span>Verified events will appear here as evidence is reconciled.</span></div>}</section><section className="trust-section"><div><span className="eyebrow">Built for trustworthy data</span><h2>Reports are evidence.<br />Not automatic truth.</h2><p>Community observations, official source records, verified incidents and predictions remain separate. The model never learns from its own guesses.</p></div><ol><li><b>01</b><span><strong>Observe</strong><small>A resident reports a power change.</small></span></li><li><b>02</b><span><strong>Corroborate</strong><small>Independent people or trusted sources add evidence.</small></span></li><li><b>03</b><span><strong>Verify</strong><small>Evidence becomes one auditable incident.</small></span></li><li><b>04</b><span><strong>Learn</strong><small>Only verified incidents enter training data.</small></span></li></ol></section><section className="coverage" id="coverage">{(coverage?.discos || []).map((item) => <article key={item.disco}><b>{item.disco.startsWith("Ikeja") ? "IE" : "EK"}</b><div><span className="eyebrow">Lagos coverage</span><h3>{item.disco}</h3><p>Reference service areas and searchable neighbourhoods across Lagos.</p></div><strong>{item.area_count} service areas</strong></article>)}</section>{reporting && <ReportModal area={area} user={user} initialState={reporting} close={() => setReporting(null)} onNeedAuth={() => { setReporting(null); onAuth(); }} onDone={(message) => { setReporting(null); setNotice(message); }} />}{evidence && <EvidenceModal area={area} incident={selectedIncident} close={() => setEvidence(false)} />}</main>;
}

function Dashboard({ user }: { user: User }) {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");
  const load = () => api.call("/api/dashboard").then(setData).catch((reason) => setError(reason.message));
  useEffect(() => { void load(); }, []);
  const fallback = { user, rank: 1, reports: [], saved_places: [], point_events: [], badges: [{ name: "First Light", earned: user.points >= 5, detail: "Submit your first report" }, { name: "Community Checker", earned: user.points >= 20, detail: "Confirm reports" }, { name: "Grid Guardian", earned: user.points >= 100, detail: "Reach 100 points" }] };
  const d = data || fallback;
  async function removePlace(id: number) { try { await api.call(`/api/saved-places/${id}`, { method: "DELETE" }); load(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not remove saved place"); } }
  return <main className="workspace"><aside className="workspace-rail"><Logo /><nav><button className="active" aria-current="page">Overview</button><button onClick={() => navigate(monitorPath())}>Monitor Lagos</button>{user.role === "admin" && <button onClick={() => navigate("/admin")}>Admin area</button>}</nav><div className="rail-user"><span>{user.display_name[0]}</span><div><strong>{user.display_name}</strong><small>{d.user.points} points</small></div></div></aside><section className="workspace-main"><header><div><span className="eyebrow">Member dashboard</span><h1>Good to see you, {user.display_name.split(" ")[0]}.</h1><p>Your places, contributions and community trust in one view.</p></div><button className="primary" onClick={() => navigate(monitorPath())}>+ Report power status</button></header>{error && <div className="form-error" role="alert">{error}</div>}<div className="dashboard-stats"><article><span>Contribution points</span><strong>{d.user.points}</strong><small>Rank #{d.rank} this month</small></article><article><span>Trust score</span><strong>{Math.round(d.user.trust_score * 100)}%</strong><small>Improves with verified reports</small></article><article><span>Reports submitted</span><strong>{d.reports.length}</strong><small>{d.reports.filter((report: any) => report.review_state === "verified").length} verified</small></article><article><span>Saved places</span><strong>{d.saved_places.length}</strong><small>Monitor home, work or school</small></article></div><div className="dashboard-grid"><section className="workspace-panel places"><header><div><span className="eyebrow">Quick monitoring</span><h2>Saved places</h2></div><button onClick={() => navigate(monitorPath())}>Add place</button></header>{d.saved_places.length ? d.saved_places.map((place: any) => <article key={place.id}><span className="place-icon">⌖</span><div><strong>{place.label}</strong><small>{place.area} · {place.disco}</small></div><div className="place-actions"><button onClick={() => navigate(`/?area=${place.area_slug}#monitor`)}>Monitor →</button><button className="danger-link" onClick={() => removePlace(place.id)}>Remove</button></div></article>) : <div className="empty"><b>☆</b><strong>No saved places yet</strong><span>Search for an area and save it for one-click monitoring.</span><button onClick={() => navigate(monitorPath())}>Find my area</button></div>}</section><section className="workspace-panel badges"><header><div><span className="eyebrow">Community progress</span><h2>Badges</h2></div></header>{d.badges.map((badge: any) => <article className={badge.earned ? "earned" : ""} key={badge.name}><b>{badge.earned ? "✓" : "◇"}</b><div><strong>{badge.name}</strong><small>{badge.detail}</small></div><span>{badge.earned ? "Earned" : "Locked"}</span></article>)}</section></div><section className="workspace-panel activity"><header><div><span className="eyebrow">Accountability</span><h2>Your contribution history</h2></div></header>{d.reports.length ? <div className="activity-list">{d.reports.map((report: any) => <article key={report.id}><i className={`dot ${stateToStatus(report.state)}`} /><div><strong>{report.area}</strong><small>{statusCopy[stateToStatus(report.state)].label} · {new Date(report.created_at).toLocaleString()}</small></div><span className={`review-state ${report.review_state}`}>{report.review_state}</span></article>)}</div> : <div className="empty horizontal"><b>↗</b><span><strong>Your reports will appear here</strong><small>Verified contributions earn additional points and improve your trust score.</small></span></div>}</section></section></main>;
}

function Admin({ user }: { user: User }) {
  const [tab, setTab] = useState<"overview" | "pipeline" | "audit">("overview");
  const [data, setData] = useState<any>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const load = () => api.call("/api/admin/overview").then(setData).catch((reason) => setMessage(reason.message));
  useEffect(() => { void load(); }, []);
  if (user.role !== "admin") return <RouteGate title="Admin access required" action="Back to dashboard" onAction={() => navigate("/dashboard")} />;
  const d = data || { pending_reports: 0, verified_incidents: 0, users: 0, pipeline_runs: [], reports: [], audit_events: [] };
  async function review(id: number, decision: string) { if (!confirm(`Mark report R-${id} as ${decision}? This decision is added to the audit trail.`)) return; try { await api.call(`/api/admin/reports/${id}/review`, { method: "POST", body: JSON.stringify({ decision }) }); setMessage(`Report R-${id} marked ${decision}.`); await load(); } catch (reason) { setMessage(reason instanceof Error ? reason.message : "Review failed"); } }
  async function demoImport() { setBusy(true); setMessage(""); const row = { disco: "Eko DisCo", reporting_period_start: "2026-06-01", reporting_period_end: "2026-06-30", feeder_name: `Sabo sample ${Date.now()} 11kV`, location: "Yaba", major_areas_served: "Yaba, Akoka, Onike", average_supply_hours_per_day: 18.4, estimated_outage_hours_per_day: 5.6, current_band: "B", regulatory_outcome: "Performance observation", source_url: "https://nerc.gov.ng" }; try { const sourceHash = Date.now().toString(16).padEnd(64, "0"); const result = await api.call("/api/admin/pipeline/import", { method: "POST", body: JSON.stringify({ source: "NERC verified sample", source_url: "https://nerc.gov.ng", source_hash: sourceHash, rows: [row] }) }); setMessage(`Pipeline run ${result.run_id}: ${result.clean} clean, ${result.quarantined} quarantined.`); await load(); } catch (reason) { setMessage(reason instanceof Error ? reason.message : "Import failed"); } finally { setBusy(false); } }
  return <main className="workspace admin-workspace"><aside className="workspace-rail"><Logo /><nav><button className={tab === "overview" ? "active" : ""} onClick={() => setTab("overview")}>Review queue</button><button className={tab === "pipeline" ? "active" : ""} onClick={() => setTab("pipeline")}>Data pipeline</button><button className={tab === "audit" ? "active" : ""} onClick={() => setTab("audit")}>Audit trail</button><button onClick={() => navigate("/dashboard")}>Member dashboard</button></nav><div className="rail-user"><span>{user.display_name[0]}</span><div><strong>{user.display_name}</strong><small>Administrator</small></div></div></aside><section className="workspace-main"><header><div><span className="eyebrow">Protected operations</span><h1>{tab === "overview" ? "Evidence review" : tab === "pipeline" ? "Trusted data pipeline" : "Audit trail"}</h1><p>Every decision is attributable and predictions remain outside the evidence layer.</p></div><button className="secondary" onClick={() => navigate("/")}>View public monitor ↗</button></header>{message && <div className="admin-message" role="status">{message}<button onClick={() => setMessage("")} aria-label="Dismiss message">×</button></div>}<div className="dashboard-stats"><article><span>Pending review</span><strong>{d.pending_reports}</strong><small>Evidence groups</small></article><article><span>Verified incidents</span><strong>{d.verified_incidents}</strong><small>Canonical records</small></article><article><span>Members</span><strong>{d.users}</strong><small>Active contributors</small></article><article><span>Pipeline runs</span><strong>{d.pipeline_runs.length}</strong><small>Recent imports</small></article></div>{tab === "overview" && <section className="workspace-panel admin-table"><header><div><span className="eyebrow">Reconciliation queue</span><h2>Reports awaiting a decision</h2></div></header>{d.reports.length ? d.reports.map((report: any) => <article key={report.id}><div><small>R-{report.id}</small><strong>{report.area}</strong></div><div><small>Observed</small><strong>{statusCopy[stateToStatus(report.state)].label}</strong></div><div><small>Reporter</small><span>{report.reporter}</span></div><span className={`review-state ${report.review_state}`}>{report.review_state}</span><div><button onClick={() => review(report.id, "quarantined")}>Quarantine</button><button onClick={() => review(report.id, "rejected")}>Reject</button><button className="verify" onClick={() => review(report.id, "verified")}>Verify</button></div></article>) : <div className="empty"><b>✓</b><strong>Review queue is clear</strong><span>New member observations will appear here.</span></div>}</section>}{tab === "pipeline" && <section className="workspace-panel pipeline-panel"><header><div><span className="eyebrow">Raw → validate → quarantine → canonical</span><h2>NERC and trusted-source ingestion</h2></div><button className="primary" disabled={busy} onClick={demoImport}>{busy ? "Running…" : "Run verified sample"}</button></header><div className="pipeline-flow"><span><small>Raw snapshots</small><b>Immutable</b></span><i>→</i><span><small>Schema + domain</small><b>Validate</b></span><i>→</i><span><small>Invalid rows</small><b>Quarantine</b></span><i>→</i><span><small>Clean records</small><b>Canonical</b></span></div><div className="source-health"><article><i className="dot on" /><div><strong>NERC official records</strong><small>nerc.gov.ng · trusted domain</small></div><b>Healthy</b></article><article><i className="dot on" /><div><strong>Ikeja Electric notices</strong><small>ikejaelectric.com · trusted domain</small></div><b>Configured</b></article><article><i className="dot on" /><div><strong>Eko DisCo notices</strong><small>ekedp.com · trusted domain</small></div><b>Configured</b></article></div><div className="run-list">{d.pipeline_runs.length ? d.pipeline_runs.map((run: any) => <article key={run.id}><strong>RUN-{run.id}</strong><span>{run.source}</span><span>{run.clean_count} clean · {run.quarantined_count} quarantined · {run.duplicate_count} duplicates</span><b>{run.status}</b></article>) : <div className="empty compact-empty"><strong>No pipeline runs yet</strong><span>Run a verified sample to test ingestion.</span></div>}</div><div className="guardrail"><strong>Training guardrail</strong><p>Only reconciled, verified incidents can be exported to a model-training snapshot. Raw, pending, quarantined and predicted records are excluded.</p></div></section>}{tab === "audit" && <section className="workspace-panel audit-list"><header><div><span className="eyebrow">Immutable operations log</span><h2>Recent admin and user actions</h2></div></header>{d.audit_events.length ? d.audit_events.map((event: any) => <article key={event.id}><span>{event.action}</span><div><strong>{event.entity_type} #{event.entity_id}</strong><small>{event.detail || "No additional detail"}</small></div><time>{new Date(event.created_at).toLocaleString()}</time><b>Actor {event.actor}</b></article>) : <div className="empty"><strong>No audit events yet</strong></div>}</section>}</section></main>;
}

function RouteGate({ title, action, onAction }: { title: string; action: string; onAction: () => void }) { return <main className="not-found"><Logo /><h1>{title}</h1><p>Sign in with the appropriate account to continue.</p><button onClick={onAction}>{action}</button></main>; }
function Footer() { return <footer className="public-footer"><Logo /><p>Clearer electricity information for Lagos, built from evidence.</p><div><a href="/#monitor">Monitor</a><a href="/#incidents">Incidents</a><a href="/#coverage">Coverage</a></div></footer>; }

export default function App() {
  const [path, setPath] = useState(location.pathname);
  const [user, setUser] = useState<User | null>(null);
  const [auth, setAuth] = useState(false);
  const [sessionReady, setSessionReady] = useState(!api.token());
  const [theme, setTheme] = useState(() => localStorage.getItem("downnepa_theme") || "dark");
  useEffect(() => { const handler = () => setPath(location.pathname); addEventListener("popstate", handler); return () => removeEventListener("popstate", handler); }, []);
  useEffect(() => { document.documentElement.dataset.theme = theme; localStorage.setItem("downnepa_theme", theme); }, [theme]);
  useEffect(() => { if (api.token()) api.call("/api/auth/me").then(setUser).catch(() => localStorage.removeItem("downnepa_token")).finally(() => setSessionReady(true)); }, []);
  useEffect(() => { if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {}); }, []);
  function authenticated(data: { access_token: string; user: User }) { localStorage.setItem("downnepa_token", data.access_token); setUser(data.user); setAuth(false); navigate("/dashboard"); }
  async function logout() { try { await api.call("/api/auth/logout", { method: "POST" }); } catch { /* local logout still succeeds */ } localStorage.removeItem("downnepa_token"); setUser(null); navigate("/"); }
  let page: ReactNode;
  if (!sessionReady) page = <main className="app-loading" role="status">Loading DownNepa…</main>;
  else if (path === "/dashboard") page = user ? <Dashboard user={user} /> : <RouteGate title="Sign in to view your dashboard" action="Sign up or log in" onAction={() => setAuth(true)} />;
  else if (path === "/admin") page = user ? <Admin user={user} /> : <RouteGate title="Admin sign-in required" action="Log in" onAction={() => setAuth(true)} />;
  else page = <><Header user={user} theme={theme} toggleTheme={() => setTheme(theme === "dark" ? "light" : "dark")} onAuth={() => setAuth(true)} onLogout={logout} /><PublicMonitor user={user} onAuth={() => setAuth(true)} /><Footer /></>;
  return <>{page}{auth && <AuthModal close={() => setAuth(false)} onSuccess={authenticated} />}</>;
}
