from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field

DB_PATH = Path(os.getenv("DOWNNEPA_DB_PATH", Path(__file__).parents[1] / "downnepa.db"))
ADMIN_KEY = os.getenv("DOWNNEPA_ADMIN_KEY", "local-admin-only")
DEV_MODE = os.getenv("DOWNNEPA_ENV", "development") == "development"


@contextmanager
def db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def now() -> str:
    return datetime.now(UTC).isoformat()


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def init_db() -> None:
    with db() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS areas (
              id INTEGER PRIMARY KEY, slug TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
              lga TEXT NOT NULL, disco TEXT NOT NULL, service_band TEXT,
              feeder TEXT, active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL,
              role TEXT NOT NULL DEFAULT 'member', trust_score REAL NOT NULL DEFAULT 0.5,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS login_challenges (
              id INTEGER PRIMARY KEY, email TEXT NOT NULL, code_hash TEXT NOT NULL,
              expires_at TEXT NOT NULL, used_at TEXT, attempts INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS sessions (
              id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
              token_hash TEXT UNIQUE NOT NULL, expires_at TEXT NOT NULL, revoked_at TEXT
            );
            CREATE TABLE IF NOT EXISTS reports (
              id INTEGER PRIMARY KEY, area_id INTEGER NOT NULL REFERENCES areas(id),
              user_id INTEGER NOT NULL REFERENCES users(id),
              state TEXT NOT NULL CHECK(state IN ('out','restored','unstable')),
              note TEXT, observed_at TEXT NOT NULL, created_at TEXT NOT NULL,
              review_state TEXT NOT NULL DEFAULT 'pending',
              dedupe_key TEXT UNIQUE NOT NULL
            );
            CREATE TABLE IF NOT EXISTS incidents (
              id INTEGER PRIMARY KEY, area_id INTEGER NOT NULL REFERENCES areas(id),
              state TEXT NOT NULL, confidence REAL NOT NULL,
              started_at TEXT NOT NULL, ended_at TEXT, verified_at TEXT NOT NULL,
              evidence_count INTEGER NOT NULL, verification_method TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS pipeline_runs (
              id INTEGER PRIMARY KEY, source TEXT NOT NULL, status TEXT NOT NULL,
              raw_count INTEGER NOT NULL DEFAULT 0, clean_count INTEGER NOT NULL DEFAULT 0,
              quarantined_count INTEGER NOT NULL DEFAULT 0,
              started_at TEXT NOT NULL, finished_at TEXT
            );
            CREATE TABLE IF NOT EXISTS model_versions (
              id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, task TEXT NOT NULL,
              artifact_uri TEXT NOT NULL, status TEXT NOT NULL,
              metrics_json TEXT NOT NULL, feature_schema TEXT NOT NULL,
              trained_at TEXT NOT NULL, activated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS audit_events (
              id INTEGER PRIMARY KEY, actor TEXT NOT NULL, action TEXT NOT NULL,
              entity_type TEXT NOT NULL, entity_id TEXT NOT NULL,
              detail TEXT, created_at TEXT NOT NULL
            );
            """
        )
        seeds = [
            ("ikeja-gra", "Ikeja GRA", "Ikeja", "Ikeja Electric", "A", "Airport 11kV"),
            ("ojodu-berger", "Ojodu Berger", "Kosofe", "Ikeja Electric", "B", "Olowora 11kV"),
            ("yaba", "Yaba", "Lagos Mainland", "Eko DisCo", "B", "Sabo 11kV"),
            ("lekki-phase-1", "Lekki Phase 1", "Eti-Osa", "Eko DisCo", "A", "Maroko 11kV"),
            ("surulere", "Surulere", "Surulere", "Eko DisCo", "C", "Bode Thomas 11kV"),
        ]
        connection.executemany(
            "INSERT OR IGNORE INTO areas(slug,name,lga,disco,service_band,feeder) VALUES(?,?,?,?,?,?)",
            seeds,
        )
        connection.execute(
            """INSERT OR IGNORE INTO model_versions
            (name,task,artifact_uri,status,metrics_json,feature_schema,trained_at,activated_at)
            VALUES(?,?,?,?,?,?,?,?)""",
            (
                "lagos-risk-v0.3", "six_hour_outage_risk",
                "models/lagos-risk-v0.3/model.joblib", "active",
                '{"roc_auc":0.81,"brier":0.16}', "lagos-risk-features-v1", now(), now(),
            ),
        )


app = FastAPI(title="DownNepa API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("DOWNNEPA_WEB_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    init_db()


class LoginStart(BaseModel):
    email: EmailStr


class LoginVerify(LoginStart):
    code: str = Field(min_length=6, max_length=6)


class ReportIn(BaseModel):
    area_slug: str
    state: Literal["out", "restored", "unstable"]
    note: str | None = Field(default=None, max_length=280)
    observed_at: datetime


def current_user(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Sign in required for contributions")
    with db() as connection:
        row = connection.execute(
            """SELECT users.* FROM sessions JOIN users ON users.id=sessions.user_id
            WHERE sessions.token_hash=? AND sessions.revoked_at IS NULL
            AND sessions.expires_at>?""",
            (digest(authorization[7:]), now()),
        ).fetchone()
    if not row:
        raise HTTPException(401, "Session expired")
    return row


def admin(x_admin_key: str | None = Header(default=None)):
    if not secrets.compare_digest(x_admin_key or "", ADMIN_KEY):
        raise HTTPException(403, "Admin access required")


@app.get("/health")
def health():
    return {"status": "ok", "database": "sqlite", "time": now()}


@app.get("/v1/areas")
def areas():
    with db() as connection:
        return [dict(row) for row in connection.execute("SELECT * FROM areas WHERE active=1 ORDER BY name")]


@app.get("/v1/status/{area_slug}")
def status(area_slug: str):
    with db() as connection:
        area = connection.execute("SELECT * FROM areas WHERE slug=?", (area_slug,)).fetchone()
        if not area:
            raise HTTPException(404, "Area not found")
        incident = connection.execute(
            "SELECT * FROM incidents WHERE area_id=? ORDER BY verified_at DESC LIMIT 1", (area["id"],)
        ).fetchone()
    return {
        "area": dict(area),
        "status": incident["state"] if incident else "unknown",
        "confidence": incident["confidence"] if incident else 0,
        "freshness": incident["verified_at"] if incident else None,
        "evidence_count": incident["evidence_count"] if incident else 0,
        "source": "verified_incident" if incident else "insufficient_evidence",
    }


@app.post("/v1/auth/start")
def auth_start(body: LoginStart):
    code = f"{secrets.randbelow(1_000_000):06d}"
    expires = (datetime.now(UTC) + timedelta(minutes=10)).isoformat()
    with db() as connection:
        connection.execute(
            "INSERT INTO login_challenges(email,code_hash,expires_at) VALUES(?,?,?)",
            (body.email.lower(), digest(code), expires),
        )
    # Production sends this through a mail adapter. It is returned only in local development.
    return {"sent": True, "expires_in_seconds": 600, "development_code": code if DEV_MODE else None}


@app.post("/v1/auth/verify")
def auth_verify(body: LoginVerify, response: Response):
    email = body.email.lower()
    with db() as connection:
        challenge = connection.execute(
            """SELECT * FROM login_challenges WHERE email=? AND used_at IS NULL
            AND expires_at>? ORDER BY id DESC LIMIT 1""",
            (email, now()),
        ).fetchone()
        if not challenge or not secrets.compare_digest(challenge["code_hash"], digest(body.code)):
            raise HTTPException(400, "Invalid or expired code")
        connection.execute("UPDATE login_challenges SET used_at=? WHERE id=?", (now(), challenge["id"]))
        connection.execute(
            "INSERT OR IGNORE INTO users(email,created_at) VALUES(?,?)", (email, now())
        )
        user = connection.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        token = secrets.token_urlsafe(32)
        connection.execute(
            "INSERT INTO sessions(user_id,token_hash,expires_at) VALUES(?,?,?)",
            (user["id"], digest(token), (datetime.now(UTC) + timedelta(days=14)).isoformat()),
        )
    return {"access_token": token, "token_type": "bearer", "user": {"email": email, "role": user["role"]}}


@app.post("/v1/reports", status_code=202)
def create_report(body: ReportIn, user=Depends(current_user)):
    with db() as connection:
        area = connection.execute("SELECT * FROM areas WHERE slug=?", (body.area_slug,)).fetchone()
        if not area:
            raise HTTPException(404, "Area not found")
        bucket = body.observed_at.astimezone(UTC).replace(minute=(body.observed_at.minute // 10) * 10, second=0, microsecond=0)
        dedupe = digest(f"{user['id']}:{area['id']}:{body.state}:{bucket.isoformat()}")
        try:
            cursor = connection.execute(
                """INSERT INTO reports(area_id,user_id,state,note,observed_at,created_at,dedupe_key)
                VALUES(?,?,?,?,?,?,?)""",
                (area["id"], user["id"], body.state, body.note, body.observed_at.isoformat(), now(), dedupe),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(409, "A matching report was already received")
    return {"report_id": cursor.lastrowid, "review_state": "pending", "message": "Report recorded as evidence"}


@app.get("/v1/admin/overview", dependencies=[Depends(admin)])
def admin_overview():
    with db() as connection:
        counts = {
            "pending_reports": connection.execute("SELECT COUNT(*) FROM reports WHERE review_state='pending'").fetchone()[0],
            "verified_incidents": connection.execute("SELECT COUNT(*) FROM incidents").fetchone()[0],
            "quarantined_records": connection.execute("SELECT COALESCE(SUM(quarantined_count),0) FROM pipeline_runs").fetchone()[0],
        }
        models = [dict(row) for row in connection.execute("SELECT * FROM model_versions ORDER BY trained_at DESC")]
        reports = [dict(row) for row in connection.execute(
            """SELECT reports.*, areas.name area, users.email reporter FROM reports
            JOIN areas ON areas.id=reports.area_id JOIN users ON users.id=reports.user_id
            ORDER BY reports.created_at DESC LIMIT 30"""
        )]
    return {**counts, "models": models, "reports": reports}


@app.post("/v1/admin/reports/{report_id}/verify", dependencies=[Depends(admin)])
def verify_report(report_id: int):
    with db() as connection:
        report = connection.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
        if not report:
            raise HTTPException(404, "Report not found")
        connection.execute("UPDATE reports SET review_state='verified' WHERE id=?", (report_id,))
        connection.execute(
            """INSERT INTO incidents(area_id,state,confidence,started_at,verified_at,evidence_count,verification_method)
            VALUES(?,?,?,?,?,?,?)""",
            (report["area_id"], report["state"], 0.72, report["observed_at"], now(), 1, "admin_review"),
        )
        connection.execute(
            "INSERT INTO audit_events(actor,action,entity_type,entity_id,created_at) VALUES(?,?,?,?,?)",
            ("admin", "verify", "report", str(report_id), now()),
        )
    return {"verified": True}


@app.post("/v1/admin/models/{name}/activate", dependencies=[Depends(admin)])
def activate_model(name: str):
    with db() as connection:
        model = connection.execute("SELECT * FROM model_versions WHERE name=?", (name,)).fetchone()
        if not model:
            raise HTTPException(404, "Model not registered")
        connection.execute("UPDATE model_versions SET status='retired' WHERE task=? AND status='active'", (model["task"],))
        connection.execute("UPDATE model_versions SET status='active',activated_at=? WHERE name=?", (now(), name))
        connection.execute(
            "INSERT INTO audit_events(actor,action,entity_type,entity_id,created_at) VALUES(?,?,?,?,?)",
            ("admin", "activate", "model_version", name, now()),
        )
    return {"active_model": name}

