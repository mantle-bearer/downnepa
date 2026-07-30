from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
from contextlib import asynccontextmanager, contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = Path(os.getenv("DOWNNEPA_DB_PATH", ROOT / "data" / "downnepa.db"))
SPA_DIR = Path(os.getenv("DOWNNEPA_SPA_DIR", ROOT / "frontend" / "dist"))
SESSION_DAYS = int(os.getenv("DOWNNEPA_SESSION_DAYS", "14"))
TRUSTED_SOURCE_HOSTS = {
    host.strip().lower()
    for host in os.getenv(
        "DOWNNEPA_TRUSTED_SOURCE_HOSTS",
        "nerc.gov.ng,ikejaelectric.com,ekedp.com,nesistats.org",
    ).split(",")
    if host.strip()
}


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso_now() -> str:
    return utc_now().isoformat()


@contextmanager
def db():
    """Open a short-lived synchronous SQLite unit of work.

    Database-backed FastAPI handlers intentionally use regular ``def`` so
    Starlette executes them in its worker thread pool instead of blocking the
    async event loop.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=20)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=5000")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    key = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${key.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt_hex, expected = encoded.split("$", 2)
        if algorithm != "scrypt":
            return False
        actual = hash_password(password, bytes.fromhex(salt_hex)).split("$", 2)[2]
        return secrets.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


SCHEMA = """
CREATE TABLE IF NOT EXISTS areas (
  id INTEGER PRIMARY KEY,
  slug TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  lga TEXT NOT NULL,
  disco TEXT NOT NULL,
  service_band TEXT,
  feeder TEXT,
  aliases_json TEXT NOT NULL DEFAULT '[]',
  active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  display_name TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'member' CHECK(role IN ('member','admin')),
  trust_score REAL NOT NULL DEFAULT 0.5,
  points INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  token_hash TEXT UNIQUE NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  revoked_at TEXT
);
CREATE TABLE IF NOT EXISTS saved_places (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  area_id INTEGER NOT NULL REFERENCES areas(id),
  label TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(user_id, area_id)
);
CREATE TABLE IF NOT EXISTS reports (
  id INTEGER PRIMARY KEY,
  area_id INTEGER NOT NULL REFERENCES areas(id),
  user_id INTEGER NOT NULL REFERENCES users(id),
  state TEXT NOT NULL CHECK(state IN ('out','restored','unstable')),
  note TEXT,
  observed_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  review_state TEXT NOT NULL DEFAULT 'pending'
    CHECK(review_state IN ('pending','verified','rejected','quarantined')),
  dedupe_key TEXT UNIQUE NOT NULL
);
CREATE TABLE IF NOT EXISTS report_votes (
  id INTEGER PRIMARY KEY,
  report_id INTEGER NOT NULL REFERENCES reports(id),
  user_id INTEGER NOT NULL REFERENCES users(id),
  vote TEXT NOT NULL CHECK(vote IN ('confirm','dispute')),
  created_at TEXT NOT NULL,
  UNIQUE(report_id, user_id)
);
CREATE TABLE IF NOT EXISTS incidents (
  id INTEGER PRIMARY KEY,
  area_id INTEGER NOT NULL REFERENCES areas(id),
  state TEXT NOT NULL,
  confidence REAL NOT NULL,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  verified_at TEXT NOT NULL,
  evidence_count INTEGER NOT NULL,
  verification_method TEXT NOT NULL,
  source_summary TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS point_events (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  points INTEGER NOT NULL,
  reason TEXT NOT NULL,
  entity_type TEXT,
  entity_id TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS raw_source_records (
  id INTEGER PRIMARY KEY,
  pipeline_run_id INTEGER NOT NULL REFERENCES pipeline_runs(id),
  source TEXT NOT NULL,
  source_url TEXT NOT NULL,
  source_hash TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  received_at TEXT NOT NULL,
  validation_state TEXT NOT NULL,
  validation_errors TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS feeder_performance (
  id INTEGER PRIMARY KEY,
  raw_record_id INTEGER UNIQUE NOT NULL REFERENCES raw_source_records(id),
  disco TEXT NOT NULL,
  reporting_period_start TEXT NOT NULL,
  reporting_period_end TEXT NOT NULL,
  feeder_name TEXT NOT NULL,
  location TEXT NOT NULL,
  major_areas_served TEXT NOT NULL,
  average_supply_hours_per_day REAL NOT NULL,
  estimated_outage_hours_per_day REAL NOT NULL,
  current_band TEXT,
  regulatory_outcome TEXT,
  source_url TEXT NOT NULL,
  UNIQUE(disco, reporting_period_start, reporting_period_end, feeder_name)
);
CREATE TABLE IF NOT EXISTS pipeline_runs (
  id INTEGER PRIMARY KEY,
  source TEXT NOT NULL,
  source_url TEXT NOT NULL,
  source_hash TEXT NOT NULL,
  status TEXT NOT NULL,
  raw_count INTEGER NOT NULL DEFAULT 0,
  clean_count INTEGER NOT NULL DEFAULT 0,
  quarantined_count INTEGER NOT NULL DEFAULT 0,
  duplicate_count INTEGER NOT NULL DEFAULT 0,
  started_at TEXT NOT NULL,
  finished_at TEXT
);
CREATE TABLE IF NOT EXISTS model_versions (
  id INTEGER PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  task TEXT NOT NULL,
  artifact_uri TEXT NOT NULL,
  status TEXT NOT NULL,
  metrics_json TEXT NOT NULL,
  feature_schema TEXT NOT NULL,
  trained_at TEXT NOT NULL,
  activated_at TEXT
);
CREATE TABLE IF NOT EXISTS audit_events (
  id INTEGER PRIMARY KEY,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  detail TEXT,
  created_at TEXT NOT NULL
);
"""


AREA_SEEDS = [
    ("ikeja-gra", "Ikeja GRA", "Ikeja", "Ikeja Electric", "A", "Airport 11kV", '["GRA Ikeja","Joel Ogunnaike","Opebi"]'),
    ("ojodu-berger", "Ojodu Berger", "Kosofe", "Ikeja Electric", "B", "Olowora 11kV", '["Berger","Olowora","Isheri North","Omole Phase 2"]'),
    ("yaba", "Yaba", "Lagos Mainland", "Eko DisCo", "B", "Sabo 11kV", '["Sabo Yaba","Akoka","Onike","University Road"]'),
    ("lekki-phase-1", "Lekki Phase 1", "Eti-Osa", "Eko DisCo", "A", "Maroko 11kV", '["Admiralty Way","Fola Osibo","Maroko"]'),
    ("surulere", "Surulere", "Surulere", "Eko DisCo", "C", "Bode Thomas 11kV", '["Bode Thomas","Adeniran Ogunsanya","Aguda"]'),
    ("ajah", "Ajah", "Eti-Osa", "Eko DisCo", "B", "Ajah 11kV", '["Sangotedo","Badore","Abraham Adesanya"]'),
    ("maryland", "Maryland", "Kosofe", "Ikeja Electric", "A", "Maryland 11kV", '["Mende","Anthony Village","Ikorodu Road"]'),
    ("festac", "Festac Town", "Amuwo-Odofin", "Eko DisCo", "B", "Festac 11kV", '["Apple Junction","Amuwo","Satellite Town"]'),
    ("ikorodu", "Ikorodu", "Ikorodu", "Ikeja Electric", "C", "Ipakodo 11kV", '["Ipakodo","Agric","Ebute Ikorodu"]'),
    ("victoria-island", "Victoria Island", "Eti-Osa", "Eko DisCo", "A", "Kofo Abayomi 11kV", '["Akin Adesola","Adeola Odeku","Oniru"]')
]


def initialise() -> None:
    with db() as connection:
        connection.executescript(SCHEMA)
        connection.executemany(
            """INSERT OR IGNORE INTO areas
            (slug,name,lga,disco,service_band,feeder,aliases_json)
            VALUES(?,?,?,?,?,?,?)""",
            AREA_SEEDS,
        )
        admin_email = os.getenv("DOWNNEPA_ADMIN_EMAIL")
        admin_password = os.getenv("DOWNNEPA_ADMIN_PASSWORD")
        if admin_email and admin_password:
            connection.execute(
                """INSERT INTO users(email,password_hash,display_name,role,trust_score,points,created_at)
                VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(email) DO UPDATE SET role='admin'""",
                (admin_email.lower(), hash_password(admin_password), "DownNepa Admin", "admin", 1.0, 500, iso_now()),
            )


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialise()
    yield


app = FastAPI(title="DownNepa API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[item for item in os.getenv("DOWNNEPA_WEB_ORIGINS", "http://localhost:5173").split(",") if item],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SignupIn(BaseModel):
    display_name: str = Field(min_length=2, max_length=60)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ReportIn(BaseModel):
    area_slug: str
    state: Literal["out", "restored", "unstable"]
    note: str | None = Field(default=None, max_length=280)
    observed_at: datetime = Field(default_factory=utc_now)


class VoteIn(BaseModel):
    vote: Literal["confirm", "dispute"]


class SavedPlaceIn(BaseModel):
    area_slug: str
    label: str = Field(min_length=1, max_length=30)


class PipelineRow(BaseModel):
    disco: str
    reporting_period_start: str
    reporting_period_end: str
    feeder_name: str
    location: str
    major_areas_served: str
    average_supply_hours_per_day: float
    estimated_outage_hours_per_day: float | None = None
    current_band: str | None = None
    regulatory_outcome: str | None = None
    source_url: str


class PipelineImport(BaseModel):
    source: str
    source_url: str
    source_hash: str = Field(min_length=64, max_length=64)
    rows: list[PipelineRow] = Field(max_length=5000)


def issue_session(connection: sqlite3.Connection, user_id: int) -> str:
    token = secrets.token_urlsafe(36)
    connection.execute(
        "INSERT INTO sessions(user_id,token_hash,created_at,expires_at) VALUES(?,?,?,?)",
        (user_id, token_hash(token), iso_now(), (utc_now() + timedelta(days=SESSION_DAYS)).isoformat()),
    )
    return token


def user_response(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "email": row["email"],
        "display_name": row["display_name"],
        "role": row["role"],
        "trust_score": row["trust_score"],
        "points": row["points"],
    }


def current_user(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Sign in required")
    with db() as connection:
        row = connection.execute(
            """SELECT users.* FROM sessions JOIN users ON users.id=sessions.user_id
            WHERE sessions.token_hash=? AND sessions.revoked_at IS NULL
            AND sessions.expires_at>? AND users.status='active'""",
            (token_hash(authorization[7:]), iso_now()),
        ).fetchone()
    if not row:
        raise HTTPException(401, "Session expired")
    return row


def require_admin(user=Depends(current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Admin access required")
    return user


def award_points(connection: sqlite3.Connection, user_id: int, points: int, reason: str, entity_type: str, entity_id: str) -> None:
    exists = connection.execute(
        "SELECT 1 FROM point_events WHERE user_id=? AND reason=? AND entity_type=? AND entity_id=?",
        (user_id, reason, entity_type, entity_id),
    ).fetchone()
    if exists:
        return
    connection.execute(
        "INSERT INTO point_events(user_id,points,reason,entity_type,entity_id,created_at) VALUES(?,?,?,?,?,?)",
        (user_id, points, reason, entity_type, entity_id, iso_now()),
    )
    connection.execute("UPDATE users SET points=points+? WHERE id=?", (points, user_id))


@app.get("/api/health")
def health():
    with db() as connection:
        connection.execute("SELECT 1").fetchone()
    return {"status": "ok", "database": "sqlite-wal", "time": iso_now()}


@app.post("/api/auth/signup", status_code=201)
def signup(body: SignupIn):
    email = body.email.lower()
    with db() as connection:
        try:
            cursor = connection.execute(
                """INSERT INTO users(email,password_hash,display_name,created_at)
                VALUES(?,?,?,?)""",
                (email, hash_password(body.password), body.display_name.strip(), iso_now()),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(409, "An account already exists for this email")
        token = issue_session(connection, cursor.lastrowid)
        user = connection.execute("SELECT * FROM users WHERE id=?", (cursor.lastrowid,)).fetchone()
    return {"access_token": token, "user": user_response(user)}


@app.post("/api/auth/login")
def login(body: LoginIn):
    with db() as connection:
        user = connection.execute("SELECT * FROM users WHERE email=?", (body.email.lower(),)).fetchone()
        if not user or not verify_password(body.password, user["password_hash"]):
            raise HTTPException(401, "Incorrect email or password")
        if user["status"] != "active":
            raise HTTPException(403, "This account is unavailable")
        token = issue_session(connection, user["id"])
    return {"access_token": token, "user": user_response(user)}


@app.get("/api/auth/me")
def me(user=Depends(current_user)):
    return user_response(user)


@app.post("/api/auth/logout", status_code=204)
def logout(authorization: str = Header(), user=Depends(current_user)):
    with db() as connection:
        connection.execute("UPDATE sessions SET revoked_at=? WHERE token_hash=?", (iso_now(), token_hash(authorization[7:])))


@app.get("/api/areas")
def list_areas(search: str | None = Query(default=None, max_length=80)):
    with db() as connection:
        rows = connection.execute("SELECT * FROM areas WHERE active=1 ORDER BY name").fetchall()
    items = [{**dict(row), "aliases": json.loads(row["aliases_json"])} for row in rows]
    if search:
        needle = search.casefold()
        items = [
            item for item in items
            if needle in f"{item['name']} {item['lga']} {item['feeder']} {' '.join(item['aliases'])}".casefold()
        ]
    return items


@app.get("/api/status/{area_slug}")
def area_status(area_slug: str):
    with db() as connection:
        area = connection.execute("SELECT * FROM areas WHERE slug=?", (area_slug,)).fetchone()
        if not area:
            raise HTTPException(404, "Area not found")
        incident = connection.execute(
            "SELECT * FROM incidents WHERE area_id=? ORDER BY verified_at DESC LIMIT 1", (area["id"],)
        ).fetchone()
        reports = connection.execute(
            """SELECT reports.*, users.display_name FROM reports JOIN users ON users.id=reports.user_id
            WHERE area_id=? AND review_state!='rejected' ORDER BY created_at DESC LIMIT 12""",
            (area["id"],),
        ).fetchall()
    return {
        "area": {**dict(area), "aliases": json.loads(area["aliases_json"])},
        "status": incident["state"] if incident else "unknown",
        "confidence": round(float(incident["confidence"]) * 100) if incident else 0,
        "freshness": incident["verified_at"] if incident else None,
        "evidence_count": incident["evidence_count"] if incident else len(reports),
        "incident": dict(incident) if incident else None,
        "recent_reports": [dict(row) for row in reports],
        "prediction": None,
        "prediction_message": "ML prediction is not enabled yet",
    }


@app.get("/api/incidents")
def incidents(area_slug: str | None = None, limit: int = Query(default=50, ge=1, le=200)):
    sql = """SELECT incidents.*,areas.name area,areas.slug area_slug,areas.disco
    FROM incidents JOIN areas ON areas.id=incidents.area_id"""
    params: list[object] = []
    if area_slug:
        sql += " WHERE areas.slug=?"
        params.append(area_slug)
    sql += " ORDER BY incidents.verified_at DESC LIMIT ?"
    params.append(limit)
    with db() as connection:
        return [dict(row) for row in connection.execute(sql, params)]


@app.post("/api/reports", status_code=202)
def create_report(body: ReportIn, user=Depends(current_user)):
    with db() as connection:
        area = connection.execute("SELECT * FROM areas WHERE slug=?", (body.area_slug,)).fetchone()
        if not area:
            raise HTTPException(404, "Area not found")
        observed = body.observed_at.astimezone(UTC)
        bucket = observed.replace(minute=(observed.minute // 10) * 10, second=0, microsecond=0)
        dedupe = token_hash(f"{user['id']}:{area['id']}:{body.state}:{bucket.isoformat()}")
        try:
            cursor = connection.execute(
                """INSERT INTO reports(area_id,user_id,state,note,observed_at,created_at,dedupe_key)
                VALUES(?,?,?,?,?,?,?)""",
                (area["id"], user["id"], body.state, body.note, observed.isoformat(), iso_now(), dedupe),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(409, "You already submitted this observation recently")
        award_points(connection, user["id"], 5, "report_submitted", "report", str(cursor.lastrowid))
        connection.execute(
            "INSERT INTO audit_events(actor,action,entity_type,entity_id,detail,created_at) VALUES(?,?,?,?,?,?)",
            (str(user["id"]), "submit", "report", str(cursor.lastrowid), body.state, iso_now()),
        )
    return {"report_id": cursor.lastrowid, "review_state": "pending", "points_awarded": 5}


@app.post("/api/reports/{report_id}/vote")
def vote_report(report_id: int, body: VoteIn, user=Depends(current_user)):
    with db() as connection:
        report = connection.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
        if not report:
            raise HTTPException(404, "Report not found")
        if report["user_id"] == user["id"]:
            raise HTTPException(400, "You cannot vote on your own report")
        connection.execute(
            """INSERT INTO report_votes(report_id,user_id,vote,created_at) VALUES(?,?,?,?)
            ON CONFLICT(report_id,user_id) DO UPDATE SET vote=excluded.vote,created_at=excluded.created_at""",
            (report_id, user["id"], body.vote, iso_now()),
        )
        award_points(connection, user["id"], 2, "report_reviewed", "report", str(report_id))
        totals = connection.execute(
            "SELECT vote,COUNT(*) count FROM report_votes WHERE report_id=? GROUP BY vote", (report_id,)
        ).fetchall()
    return {"votes": {row["vote"]: row["count"] for row in totals}, "points_awarded": 2}


@app.get("/api/dashboard")
def dashboard(user=Depends(current_user)):
    with db() as connection:
        reports = [dict(row) for row in connection.execute(
            """SELECT reports.*,areas.name area FROM reports JOIN areas ON areas.id=reports.area_id
            WHERE user_id=? ORDER BY created_at DESC LIMIT 30""", (user["id"],)
        )]
        places = [dict(row) for row in connection.execute(
            """SELECT saved_places.*,areas.name area,areas.slug area_slug,areas.disco
            FROM saved_places JOIN areas ON areas.id=saved_places.area_id
            WHERE user_id=? ORDER BY created_at""", (user["id"],)
        )]
        events = [dict(row) for row in connection.execute(
            "SELECT * FROM point_events WHERE user_id=? ORDER BY created_at DESC LIMIT 30", (user["id"],)
        )]
        rank = connection.execute("SELECT COUNT(*)+1 FROM users WHERE points>?", (user["points"],)).fetchone()[0]
    points = user["points"]
    badges = [
        {"name": "First Light", "earned": points >= 5, "detail": "Submit your first report"},
        {"name": "Community Checker", "earned": points >= 20, "detail": "Confirm independent reports"},
        {"name": "Grid Guardian", "earned": points >= 100, "detail": "Reach 100 contribution points"},
    ]
    return {"user": user_response(user), "reports": reports, "saved_places": places, "point_events": events, "rank": rank, "badges": badges}


@app.post("/api/saved-places", status_code=201)
def save_place(body: SavedPlaceIn, user=Depends(current_user)):
    with db() as connection:
        area = connection.execute("SELECT * FROM areas WHERE slug=?", (body.area_slug,)).fetchone()
        if not area:
            raise HTTPException(404, "Area not found")
        connection.execute(
            """INSERT INTO saved_places(user_id,area_id,label,created_at) VALUES(?,?,?,?)
            ON CONFLICT(user_id,area_id) DO UPDATE SET label=excluded.label""",
            (user["id"], area["id"], body.label.strip(), iso_now()),
        )
    return {"saved": True}


@app.delete("/api/saved-places/{place_id}", status_code=204)
def remove_place(place_id: int, user=Depends(current_user)):
    with db() as connection:
        connection.execute("DELETE FROM saved_places WHERE id=? AND user_id=?", (place_id, user["id"]))


def source_host(url: str) -> str:
    from urllib.parse import urlparse
    return (urlparse(url).hostname or "").lower()


def validate_pipeline_row(row: PipelineRow, import_url: str) -> list[str]:
    errors: list[str] = []
    if source_host(row.source_url) not in TRUSTED_SOURCE_HOSTS or source_host(import_url) not in TRUSTED_SOURCE_HOSTS:
        errors.append("untrusted_source_domain")
    if not 0 <= row.average_supply_hours_per_day <= 24:
        errors.append("average_supply_hours_out_of_range")
    outage = row.estimated_outage_hours_per_day
    if outage is not None and abs((24 - row.average_supply_hours_per_day) - outage) > 0.05:
        errors.append("outage_hours_derivation_mismatch")
    if row.reporting_period_start > row.reporting_period_end:
        errors.append("invalid_reporting_period")
    if not row.feeder_name.strip() or not row.location.strip():
        errors.append("missing_feeder_or_location")
    return errors


@app.post("/api/admin/pipeline/import")
def import_pipeline(body: PipelineImport, admin=Depends(require_admin)):
    if source_host(body.source_url) not in TRUSTED_SOURCE_HOSTS:
        raise HTTPException(400, "Source domain is not on the trusted allowlist")
    clean = quarantined = duplicates = 0
    with db() as connection:
        run = connection.execute(
            """INSERT INTO pipeline_runs(source,source_url,source_hash,status,raw_count,started_at)
            VALUES(?,?,?,?,?,?)""",
            (body.source, body.source_url, body.source_hash, "running", len(body.rows), iso_now()),
        ).lastrowid
        for row in body.rows:
            errors = validate_pipeline_row(row, body.source_url)
            raw = connection.execute(
                """INSERT INTO raw_source_records
                (pipeline_run_id,source,source_url,source_hash,payload_json,received_at,validation_state,validation_errors)
                VALUES(?,?,?,?,?,?,?,?)""",
                (run, body.source, row.source_url, body.source_hash, row.model_dump_json(), iso_now(), "quarantined" if errors else "clean", json.dumps(errors)),
            ).lastrowid
            if errors:
                quarantined += 1
                continue
            try:
                connection.execute(
                    """INSERT INTO feeder_performance
                    (raw_record_id,disco,reporting_period_start,reporting_period_end,feeder_name,location,
                    major_areas_served,average_supply_hours_per_day,estimated_outage_hours_per_day,
                    current_band,regulatory_outcome,source_url)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        raw, row.disco, row.reporting_period_start, row.reporting_period_end,
                        row.feeder_name, row.location, row.major_areas_served,
                        row.average_supply_hours_per_day,
                        row.estimated_outage_hours_per_day if row.estimated_outage_hours_per_day is not None else 24 - row.average_supply_hours_per_day,
                        row.current_band, row.regulatory_outcome, row.source_url,
                    ),
                )
                clean += 1
            except sqlite3.IntegrityError:
                duplicates += 1
                connection.execute("UPDATE raw_source_records SET validation_state='duplicate' WHERE id=?", (raw,))
        connection.execute(
            """UPDATE pipeline_runs SET status='completed',clean_count=?,quarantined_count=?,
            duplicate_count=?,finished_at=? WHERE id=?""",
            (clean, quarantined, duplicates, iso_now(), run),
        )
        connection.execute(
            "INSERT INTO audit_events(actor,action,entity_type,entity_id,detail,created_at) VALUES(?,?,?,?,?,?)",
            (str(admin["id"]), "import", "pipeline_run", str(run), f"{clean} clean, {quarantined} quarantined", iso_now()),
        )
    return {"run_id": run, "raw": len(body.rows), "clean": clean, "quarantined": quarantined, "duplicates": duplicates}


@app.get("/api/admin/overview")
def admin_overview(admin=Depends(require_admin)):
    with db() as connection:
        return {
            "pending_reports": connection.execute("SELECT COUNT(*) FROM reports WHERE review_state='pending'").fetchone()[0],
            "verified_incidents": connection.execute("SELECT COUNT(*) FROM incidents").fetchone()[0],
            "users": connection.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "pipeline_runs": [dict(row) for row in connection.execute("SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT 20")],
            "reports": [dict(row) for row in connection.execute(
                """SELECT reports.*,areas.name area,users.email reporter FROM reports
                JOIN areas ON areas.id=reports.area_id JOIN users ON users.id=reports.user_id
                ORDER BY reports.created_at DESC LIMIT 50"""
            )],
            "audit_events": [dict(row) for row in connection.execute("SELECT * FROM audit_events ORDER BY id DESC LIMIT 50")],
        }


class ReviewIn(BaseModel):
    decision: Literal["verified", "rejected", "quarantined"]


@app.post("/api/admin/reports/{report_id}/review")
def review_report(report_id: int, body: ReviewIn, admin=Depends(require_admin)):
    with db() as connection:
        report = connection.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
        if not report:
            raise HTTPException(404, "Report not found")
        connection.execute("UPDATE reports SET review_state=? WHERE id=?", (body.decision, report_id))
        if body.decision == "verified":
            votes = connection.execute(
                "SELECT SUM(vote='confirm') confirms,SUM(vote='dispute') disputes FROM report_votes WHERE report_id=?",
                (report_id,),
            ).fetchone()
            evidence = 1 + int(votes["confirms"] or 0)
            confidence = min(0.98, 0.60 + evidence * 0.08 - int(votes["disputes"] or 0) * 0.1)
            connection.execute(
                """INSERT INTO incidents(area_id,state,confidence,started_at,verified_at,evidence_count,verification_method,source_summary)
                VALUES(?,?,?,?,?,?,?,?)""",
                (report["area_id"], report["state"], confidence, report["observed_at"], iso_now(), evidence, "admin_review", f"{evidence} community observations"),
            )
            award_points(connection, report["user_id"], 10, "report_verified", "report", str(report_id))
        connection.execute(
            "INSERT INTO audit_events(actor,action,entity_type,entity_id,detail,created_at) VALUES(?,?,?,?,?,?)",
            (str(admin["id"]), body.decision, "report", str(report_id), None, iso_now()),
        )
    return {"decision": body.decision}


if SPA_DIR.exists():
    assets = SPA_DIR / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        candidate = SPA_DIR / path
        if path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(SPA_DIR / "index.html")
