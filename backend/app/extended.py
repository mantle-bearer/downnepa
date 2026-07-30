"""Normalized location, community, pipeline and prediction APIs."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import sqlite3
import urllib.request
from datetime import UTC, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field

from .catalog import BADGES, CHILDREN, GROUPS, slugify
from .main import current_user, db, iso_now, require_admin, source_host

router = APIRouter(prefix="/api/v1")
LAGOS_TZ = ZoneInfo("Africa/Lagos")

SCHEMA = """
CREATE TABLE IF NOT EXISTS locations(
 id INTEGER PRIMARY KEY,slug TEXT UNIQUE NOT NULL,canonical_name TEXT NOT NULL,
 normalized_name TEXT NOT NULL,location_type TEXT NOT NULL,
 service_area_id INTEGER NOT NULL REFERENCES areas(id),
 parent_location_id INTEGER REFERENCES locations(id),latitude REAL,longitude REAL,
 verification_state TEXT NOT NULL,source_type TEXT NOT NULL,source_group TEXT,
 source_count INTEGER NOT NULL DEFAULT 0,active INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS location_aliases(
 id INTEGER PRIMARY KEY,location_id INTEGER NOT NULL REFERENCES locations(id),
 alias TEXT NOT NULL,normalized_alias TEXT NOT NULL,source_type TEXT NOT NULL,
 UNIQUE(location_id,normalized_alias));
CREATE TABLE IF NOT EXISTS location_import_records(
 id INTEGER PRIMARY KEY,source_type TEXT NOT NULL,source_group TEXT NOT NULL,
 raw_name TEXT NOT NULL,raw_payload_json TEXT NOT NULL,normalized_name TEXT NOT NULL,
 parsed_location_type TEXT,validation_errors TEXT NOT NULL DEFAULT '[]',
 review_state TEXT NOT NULL,canonical_location_id INTEGER REFERENCES locations(id),
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
 UNIQUE(source_type,source_group,raw_name));
CREATE TABLE IF NOT EXISTS location_review_events(
 id INTEGER PRIMARY KEY,import_record_id INTEGER NOT NULL REFERENCES location_import_records(id),
 actor_user_id INTEGER REFERENCES users(id),action TEXT NOT NULL,old_state TEXT,
 new_state TEXT NOT NULL,notes TEXT,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS badge_definitions(
 id INTEGER PRIMARY KEY,badge_key TEXT UNIQUE NOT NULL,name TEXT NOT NULL,
 description TEXT NOT NULL,rule_kind TEXT NOT NULL,threshold INTEGER NOT NULL,
 active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS user_badges(
 id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),
 badge_id INTEGER NOT NULL REFERENCES badge_definitions(id),earned_at TEXT NOT NULL,
 UNIQUE(user_id,badge_id));
CREATE TABLE IF NOT EXISTS user_streaks(
 user_id INTEGER PRIMARY KEY REFERENCES users(id),current_streak INTEGER NOT NULL DEFAULT 0,
 longest_streak INTEGER NOT NULL DEFAULT 0,last_qualifying_date TEXT,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS referrals(
 id INTEGER PRIMARY KEY,referrer_user_id INTEGER NOT NULL REFERENCES users(id),
 referred_user_id INTEGER UNIQUE NOT NULL REFERENCES users(id),code TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending',created_at TEXT NOT NULL,qualified_at TEXT);
CREATE TABLE IF NOT EXISTS notification_preferences(
 id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),
 outage INTEGER NOT NULL DEFAULT 1,restoration INTEGER NOT NULL DEFAULT 1,
 unstable INTEGER NOT NULL DEFAULT 1,weekly_summary INTEGER NOT NULL DEFAULT 0,
 streak_reminder INTEGER NOT NULL DEFAULT 0,community_updates INTEGER NOT NULL DEFAULT 0,
 updated_at TEXT NOT NULL,UNIQUE(user_id));
CREATE TABLE IF NOT EXISTS push_subscriptions(
 id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),
 endpoint_hash TEXT UNIQUE NOT NULL,endpoint TEXT NOT NULL,p256dh TEXT NOT NULL,
 auth TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_locations_name ON locations(normalized_name);
CREATE INDEX IF NOT EXISTS idx_alias_name ON location_aliases(normalized_alias);
CREATE INDEX IF NOT EXISTS idx_location_area ON locations(service_area_id);
CREATE INDEX IF NOT EXISTS idx_location_parent ON locations(parent_location_id);
CREATE INDEX IF NOT EXISTS idx_report_area_time ON reports(area_id,observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_incident_area_time ON incidents(area_id,started_at DESC);
"""


def ensure_column(connection: sqlite3.Connection, table: str, name: str, declaration: str) -> None:
    columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
    if name not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {declaration}")


def install(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA)
    for name, declaration in [
        ("latitude", "REAL"),
        ("longitude", "REAL"),
        ("boundary_status", "TEXT NOT NULL DEFAULT 'unverified'"),
        ("source_type", "TEXT NOT NULL DEFAULT 'nepawatch_reference'"),
        ("source_confidence", "TEXT NOT NULL DEFAULT 'unverified'"),
    ]:
        ensure_column(connection, "areas", name, declaration)
    ensure_column(connection, "saved_places", "notifications_enabled", "INTEGER NOT NULL DEFAULT 0")
    ensure_column(connection, "pipeline_runs", "parser_version", "TEXT NOT NULL DEFAULT 'manual-v1'")
    ensure_column(connection, "users", "referral_code", "TEXT")
    now = iso_now()
    for name, count, kind, lga, disco, lat, lng, active in GROUPS:
        slug = slugify(name)
        connection.execute(
            """INSERT INTO areas(slug,name,lga,disco,service_band,feeder,aliases_json,active,
               latitude,longitude,boundary_status,source_type,source_confidence)
               VALUES(?,?,?,?,NULL,NULL,'[]',?,?,?,?,?,?)
               ON CONFLICT(slug) DO UPDATE SET name=excluded.name,lga=excluded.lga,
               disco=excluded.disco,active=excluded.active,latitude=excluded.latitude,
               longitude=excluded.longitude,boundary_status=excluded.boundary_status""",
            (
                slug,name,lga,disco,active,lat,lng,
                "excluded_non_lagos" if not active else "unverified",
                "nepawatch_reference","unverified",
            ),
        )
        area_id = connection.execute("SELECT id FROM areas WHERE slug=?", (slug,)).fetchone()["id"]
        connection.execute(
            """INSERT INTO locations(slug,canonical_name,normalized_name,location_type,
               service_area_id,latitude,longitude,verification_state,source_type,source_group,
               source_count,active,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(slug) DO UPDATE SET canonical_name=excluded.canonical_name,
               service_area_id=excluded.service_area_id,active=excluded.active,
               updated_at=excluded.updated_at""",
            (
                slug,name,name.casefold(),kind,area_id,lat,lng,
                "rejected_non_lagos" if not active else "reference_unverified",
                "nepawatch_reference",name,count,active,now,now,
            ),
        )
        location_id = connection.execute("SELECT id FROM locations WHERE slug=?", (slug,)).fetchone()["id"]
        connection.execute(
            """INSERT INTO location_import_records(source_type,source_group,raw_name,
               raw_payload_json,normalized_name,parsed_location_type,validation_errors,
               review_state,canonical_location_id,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(source_type,source_group,raw_name) DO UPDATE SET
               review_state=excluded.review_state,updated_at=excluded.updated_at""",
            (
                "nepawatch_reference",name,name,json.dumps({"source_entry_count":count}),
                name.casefold(),kind,json.dumps(["outside_lagos"]) if not active else "[]",
                "rejected" if not active else "active_reference",location_id,now,now,
            ),
        )
    for parent_name, children in CHILDREN.items():
        parent = connection.execute(
            "SELECT id,service_area_id,latitude,longitude FROM locations WHERE slug=?",
            (slugify(parent_name),),
        ).fetchone()
        if not parent:
            continue
        for child in children:
            child_slug = slugify(child)
            connection.execute(
                """INSERT INTO locations(slug,canonical_name,normalized_name,location_type,
                   service_area_id,parent_location_id,latitude,longitude,verification_state,
                   source_type,source_group,active,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(slug) DO UPDATE SET service_area_id=excluded.service_area_id,
                   parent_location_id=excluded.parent_location_id,updated_at=excluded.updated_at""",
                (
                    child_slug,child,child.casefold(),"landmark",parent["service_area_id"],
                    parent["id"],parent["latitude"],parent["longitude"],"reference_unverified",
                    "nepawatch_reference",parent_name,1,now,now,
                ),
            )
            child_id = connection.execute(
                "SELECT id FROM locations WHERE slug=?", (child_slug,)
            ).fetchone()["id"]
            connection.execute(
                "INSERT OR IGNORE INTO location_aliases(location_id,alias,normalized_alias,source_type) VALUES(?,?,?,?)",
                (child_id,child,child.casefold(),"nepawatch_reference"),
            )
    for badge in BADGES:
        connection.execute(
            """INSERT INTO badge_definitions(badge_key,name,description,rule_kind,threshold)
               VALUES(?,?,?,?,?) ON CONFLICT(badge_key) DO UPDATE SET
               name=excluded.name,description=excluded.description,
               rule_kind=excluded.rule_kind,threshold=excluded.threshold""",
            badge,
        )
    for row in connection.execute("SELECT id FROM users WHERE referral_code IS NULL").fetchall():
        code = "DN" + hashlib.sha256(f"downnepa:{row['id']}".encode()).hexdigest()[:8].upper()
        connection.execute("UPDATE users SET referral_code=? WHERE id=?", (code,row["id"]))


def process_qualifying_contribution(
    connection: sqlite3.Connection,
    user_id: int,
    state: str,
    observed_at: datetime,
    report_id: int,
) -> None:
    """Update streak and badges once for an accepted contribution."""
    local_date = observed_at.astimezone(LAGOS_TZ).date()
    current = connection.execute(
        "SELECT * FROM user_streaks WHERE user_id=?", (user_id,)
    ).fetchone()
    previous = current["last_qualifying_date"] if current else None
    if previous != local_date.isoformat():
        yesterday = (local_date - timedelta(days=1)).isoformat()
        streak = (current["current_streak"] + 1) if current and previous == yesterday else 1
        longest = max(streak, current["longest_streak"] if current else 0)
        connection.execute(
            """INSERT INTO user_streaks
            (user_id,current_streak,longest_streak,last_qualifying_date,updated_at)
            VALUES(?,?,?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET
            current_streak=excluded.current_streak,
            longest_streak=excluded.longest_streak,
            last_qualifying_date=excluded.last_qualifying_date,
            updated_at=excluded.updated_at""",
            (user_id, streak, longest, local_date.isoformat(), iso_now()),
        )
    totals = {
        "reports": connection.execute(
            "SELECT COUNT(*) FROM reports WHERE user_id=? AND review_state!='rejected'",
            (user_id,),
        ).fetchone()[0],
        "restorations": connection.execute(
            "SELECT COUNT(*) FROM reports WHERE user_id=? AND state='restored' "
            "AND review_state!='rejected'",
            (user_id,),
        ).fetchone()[0],
        "streak": connection.execute(
            "SELECT current_streak FROM user_streaks WHERE user_id=?", (user_id,)
        ).fetchone()[0],
        "night": connection.execute(
            "SELECT COUNT(*) FROM reports WHERE user_id=? AND "
            "CAST(strftime('%H',observed_at) AS INTEGER)>=22",
            (user_id,),
        ).fetchone()[0],
        "early": connection.execute(
            "SELECT COUNT(*) FROM reports WHERE user_id=? AND "
            "CAST(strftime('%H',observed_at) AS INTEGER)<6",
            (user_id,),
        ).fetchone()[0],
    }
    for badge in connection.execute(
        "SELECT * FROM badge_definitions WHERE active=1"
    ).fetchall():
        if totals.get(badge["rule_kind"], 0) >= badge["threshold"]:
            connection.execute(
                """INSERT OR IGNORE INTO user_badges(user_id,badge_id,earned_at)
                VALUES(?,?,?)""",
                (user_id, badge["id"], iso_now()),
            )
    connection.execute(
        """INSERT INTO audit_events(actor,action,entity_type,entity_id,detail,created_at)
        VALUES(?,?,?,?,?,?)""",
        (str(user_id), "gamification_processed", "report", str(report_id), state, iso_now()),
    )


def status_for(connection: sqlite3.Connection, area_id: int) -> dict:
    incident = connection.execute(
        "SELECT * FROM incidents WHERE area_id=? ORDER BY verified_at DESC LIMIT 1",(area_id,)
    ).fetchone()
    return {
        "status": incident["state"] if incident else "unknown",
        "confidence": round(incident["confidence"]*100) if incident else 0,
        "freshness": incident["verified_at"] if incident else None,
        "evidence_count": incident["evidence_count"] if incident else 0,
    }


BASE_SELECT = """SELECT l.*,a.name service_area,a.slug service_area_slug,a.lga,a.disco,
 a.service_band,a.feeder,p.canonical_name parent_name FROM locations l
 JOIN areas a ON a.id=l.service_area_id LEFT JOIN locations p ON p.id=l.parent_location_id"""


def location_payload(connection: sqlite3.Connection, row: sqlite3.Row) -> dict:
    return {
        "id":row["id"],"slug":row["slug"],"canonical_name":row["canonical_name"],
        "location_type":row["location_type"],"service_area":row["service_area"],
        "service_area_slug":row["service_area_slug"],"parent":row["parent_name"],
        "lga":row["lga"],"disco":row["disco"],"band":row["service_band"],
        "feeder":row["feeder"],"latitude":row["latitude"],"longitude":row["longitude"],
        "verification_state":row["verification_state"],**status_for(connection,row["service_area_id"]),
    }


@router.get("/locations/search")
def search_locations(q: str=Query(min_length=1,max_length=100),limit:int=Query(20,ge=1,le=50)):
    needle=f"%{q.strip().casefold()}%"
    with db() as connection:
        rows=connection.execute(
            BASE_SELECT+""" LEFT JOIN location_aliases la ON la.location_id=l.id
            WHERE l.active=1 AND (l.normalized_name LIKE ? OR la.normalized_alias LIKE ?
            OR a.name LIKE ?) GROUP BY l.id ORDER BY
            CASE WHEN l.normalized_name=? THEN 0 ELSE 1 END,l.canonical_name LIMIT ?""",
            (needle,needle,needle,q.strip().casefold(),limit),
        ).fetchall()
        return {"query":q,"results":[location_payload(connection,row) for row in rows]}


def distance(lat1:float,lng1:float,lat2:float,lng2:float)->float:
    p1,p2=math.radians(lat1),math.radians(lat2)
    dp,dl=math.radians(lat2-lat1),math.radians(lng2-lng1)
    value=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 6371*2*math.atan2(math.sqrt(value),math.sqrt(1-value))


@router.get("/locations/nearby")
def nearby(lat:float=Query(ge=6.2,le=6.8),lng:float=Query(ge=2.6,le=4.4),limit:int=8):
    with db() as connection:
        rows=connection.execute(BASE_SELECT+" WHERE l.active=1 AND l.latitude IS NOT NULL").fetchall()
        rows=sorted(rows,key=lambda row:distance(lat,lng,row["latitude"],row["longitude"]))[:limit]
        return {"results":[{**location_payload(connection,row),"distance_km":round(distance(lat,lng,row["latitude"],row["longitude"]),2)} for row in rows]}


@router.get("/locations/{slug}")
def get_location(slug:str):
    with db() as connection:
        row=connection.execute(BASE_SELECT+" WHERE l.slug=? AND l.active=1",(slug,)).fetchone()
        if not row: raise HTTPException(404,"Location not found")
        return location_payload(connection,row)


@router.get("/reports/public")
def public_reports(limit:int=Query(30,ge=1,le=100)):
    with db() as connection:
        rows=connection.execute(
            """SELECT reports.id,reports.state,reports.note,reports.observed_at,
            reports.review_state,areas.name area,areas.slug area_slug,
            users.display_name FROM reports JOIN areas ON areas.id=reports.area_id
            JOIN users ON users.id=reports.user_id WHERE reports.review_state!='rejected'
            ORDER BY reports.observed_at DESC LIMIT ?""",(limit,)
        ).fetchall()
        return {"reports":[dict(row) for row in rows]}


@router.get("/status/{area_slug}/history")
def history(area_slug:str,days:int=Query(30,ge=1,le=365)):
    since=(datetime.now(UTC)-timedelta(days=days)).isoformat()
    with db() as connection:
        area=connection.execute("SELECT * FROM areas WHERE slug=? AND active=1",(area_slug,)).fetchone()
        if not area: raise HTTPException(404,"Area not found")
        rows=connection.execute(
            "SELECT * FROM incidents WHERE area_id=? AND verified_at>=? ORDER BY verified_at DESC",
            (area["id"],since),
        ).fetchall()
        return {"area":area["name"],"incidents":[dict(row) for row in rows]}


@router.get("/discos/coverage")
def coverage():
    with db() as connection:
        rows=connection.execute("SELECT disco,COUNT(*) area_count FROM areas WHERE active=1 GROUP BY disco").fetchall()
        return {"mapped_locations":connection.execute("SELECT COUNT(*) FROM locations WHERE active=1").fetchone()[0],
                "discos":[{**dict(row),"boundary_notice":"Reference coverage; official feeder boundaries require review."} for row in rows]}


class PredictIn(BaseModel):
    location_slug:str
    horizon_hours:int=Field(6,ge=1,le=48)


@router.post("/predict")
async def predict(body:PredictIn):
    await asyncio.sleep(0)
    with db() as connection:
        row=connection.execute(
            "SELECT l.*,a.id area_id,a.service_band FROM locations l JOIN areas a ON a.id=l.service_area_id WHERE l.slug=? AND l.active=1",
            (body.location_slug,),
        ).fetchone()
        if not row: raise HTTPException(404,"Location not found")
        recent=connection.execute(
            "SELECT COUNT(*) FROM incidents WHERE area_id=? AND state='out' AND verified_at>=?",
            (row["area_id"],(datetime.now(UTC)-timedelta(days=30)).isoformat()),
        ).fetchone()[0]
    baseline={"A":.12,"B":.24,"C":.36,"D":.46,"E":.58}.get(row["service_band"],.30)
    probability=min(.85,baseline+min(recent,10)*.025)
    return {"available":True,"temporary":True,"model_status":"no_approved_model",
            "location":{"slug":row["slug"],"name":row["canonical_name"]},
            "horizon_hours":body.horizon_hours,"outage_probability":round(probability,3),
            "warning":"Temporary heuristic for interface testing; not a trained ML prediction.",
            "generated_at":iso_now()}


class ProposalIn(BaseModel):
    name:str=Field(min_length=2,max_length=120)
    expected_area_slug:str
    location_type:str="custom"
    note:str|None=Field(None,max_length=280)


@router.post("/locations/proposals",status_code=202)
def proposal(body:ProposalIn,user=Depends(current_user)):
    with db() as connection:
        area=connection.execute("SELECT * FROM areas WHERE slug=? AND active=1",(body.expected_area_slug,)).fetchone()
        if not area: raise HTTPException(404,"Expected area not found")
        cursor=connection.execute(
            """INSERT INTO location_import_records(source_type,source_group,raw_name,
            raw_payload_json,normalized_name,parsed_location_type,review_state,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?, ?,?)""",
            ("member_proposal",area["name"],body.name,body.model_dump_json(),
             body.name.casefold(),body.location_type,"pending",iso_now(),iso_now()),
        )
        connection.execute(
            "INSERT INTO audit_events(actor,action,entity_type,entity_id,detail,created_at) VALUES(?,?,?,?,?,?)",
            (str(user["id"]),"propose","location_import_record",str(cursor.lastrowid),body.note,iso_now()),
        )
        return {"proposal_id":cursor.lastrowid,"review_state":"pending"}


class SavedUpdate(BaseModel):
    label:str|None=Field(None,min_length=1,max_length=30)
    notifications_enabled:bool|None=None


@router.patch("/saved-places/{place_id}")
def update_saved(place_id:int,body:SavedUpdate,user=Depends(current_user)):
    changes=body.model_dump(exclude_none=True)
    if not changes: raise HTTPException(400,"No changes supplied")
    sql=", ".join(f"{key}=?" for key in changes)
    values=[int(value) if isinstance(value,bool) else value for value in changes.values()]
    with db() as connection:
        cursor=connection.execute(
            f"UPDATE saved_places SET {sql} WHERE id=? AND user_id=?",
            (*values,place_id,user["id"]),
        )
        if not cursor.rowcount: raise HTTPException(404,"Saved place not found")
        return {"updated":True}


@router.get("/community/leaderboard")
def leaderboard(period:Literal["weekly","monthly","all"]="weekly",limit:int=20):
    delta={"weekly":7,"monthly":30,"all":36500}[period]
    since=(datetime.now(UTC)-timedelta(days=delta)).isoformat()
    with db() as connection:
        rows=connection.execute(
            """SELECT users.id,users.display_name,users.trust_score,
            COALESCE(SUM(point_events.points),0) valid_points
            FROM users LEFT JOIN point_events ON point_events.user_id=users.id
            AND point_events.created_at>=? WHERE users.status='active' GROUP BY users.id
            ORDER BY valid_points DESC,users.trust_score DESC LIMIT ?""",(since,limit)
        ).fetchall()
        return {"period":period,"entries":[{**dict(row),"rank":index+1} for index,row in enumerate(rows)]}


@router.get("/community/badges")
def badges(user=Depends(current_user)):
    with db() as connection:
        reports=connection.execute("SELECT COUNT(*) FROM reports WHERE user_id=? AND review_state!='rejected'",(user["id"],)).fetchone()[0]
        streak=connection.execute("SELECT current_streak FROM user_streaks WHERE user_id=?",(user["id"],)).fetchone()
        rows=connection.execute(
            """SELECT badge_definitions.*,user_badges.earned_at FROM badge_definitions
            LEFT JOIN user_badges ON user_badges.badge_id=badge_definitions.id
            AND user_badges.user_id=? WHERE badge_definitions.active=1""",(user["id"],)
        ).fetchall()
        values={"reports":reports,"streak":streak["current_streak"] if streak else 0}
        return {"badges":[{**dict(row),"progress":min(row["threshold"],values.get(row["rule_kind"],0)),
                           "earned":bool(row["earned_at"])} for row in rows]}


class Preferences(BaseModel):
    outage:bool=True; restoration:bool=True; unstable:bool=True
    weekly_summary:bool=False; streak_reminder:bool=False; community_updates:bool=False


@router.get("/notifications/preferences")
def get_preferences(user=Depends(current_user)):
    with db() as connection:
        row=connection.execute("SELECT * FROM notification_preferences WHERE user_id=?",(user["id"],)).fetchone()
        return dict(row) if row else Preferences().model_dump()


@router.put("/notifications/preferences")
def put_preferences(body:Preferences,user=Depends(current_user)):
    values=[int(value) for value in body.model_dump().values()]
    with db() as connection:
        connection.execute(
            """INSERT INTO notification_preferences(user_id,outage,restoration,unstable,
            weekly_summary,streak_reminder,community_updates,updated_at) VALUES(?,?,?,?,?,?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET outage=excluded.outage,
            restoration=excluded.restoration,unstable=excluded.unstable,
            weekly_summary=excluded.weekly_summary,streak_reminder=excluded.streak_reminder,
            community_updates=excluded.community_updates,updated_at=excluded.updated_at""",
            (user["id"],*values,iso_now()),
        )
        return {"updated":True}


@router.get("/admin/locations/review")
def review_queue(state:str="pending",admin=Depends(require_admin)):
    del admin
    with db() as connection:
        return {"records":[dict(row) for row in connection.execute(
            "SELECT * FROM location_import_records WHERE review_state=? ORDER BY created_at",(state,)
        ).fetchall()]}


class ReviewLocation(BaseModel):
    decision:Literal["approved","rejected","quarantined"]
    notes:str|None=Field(None,max_length=500)


@router.post("/admin/locations/{record_id}/review")
def review_location(record_id:int,body:ReviewLocation,admin=Depends(require_admin)):
    with db() as connection:
        row=connection.execute("SELECT * FROM location_import_records WHERE id=?",(record_id,)).fetchone()
        if not row: raise HTTPException(404,"Review record not found")
        connection.execute("UPDATE location_import_records SET review_state=?,updated_at=? WHERE id=?",(body.decision,iso_now(),record_id))
        connection.execute(
            "INSERT INTO location_review_events(import_record_id,actor_user_id,action,old_state,new_state,notes,created_at) VALUES(?,?,?,?,?,?,?)",
            (record_id,admin["id"],"review",row["review_state"],body.decision,body.notes,iso_now()),
        )
        return {"decision":body.decision}


@router.get("/admin/data-quality")
def data_quality(admin=Depends(require_admin)):
    del admin
    with db() as connection:
        return {"source_groups_accounted_for":connection.execute(
            "SELECT COUNT(DISTINCT source_group) FROM location_import_records WHERE source_type='nepawatch_reference'"
        ).fetchone()[0],"active_locations":connection.execute(
            "SELECT COUNT(*) FROM locations WHERE active=1").fetchone()[0],
            "inactive_non_lagos":connection.execute("SELECT COUNT(*) FROM locations WHERE active=0").fetchone()[0]}


@router.get("/admin/training-snapshot")
def snapshot(admin=Depends(require_admin)):
    with db() as connection:
        rows=[dict(row) for row in connection.execute(
            """SELECT incidents.id incident_id,incidents.state,incidents.confidence,
            incidents.started_at,incidents.ended_at,incidents.verified_at,
            incidents.evidence_count,incidents.verification_method,areas.slug area_slug,
            areas.service_band,areas.latitude,areas.longitude FROM incidents
            JOIN areas ON areas.id=incidents.area_id
            WHERE incidents.verification_method!='demo' ORDER BY incidents.started_at"""
        ).fetchall()]
    digest=hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()
    return {"schema_version":"downnepa-training-v1","generated_at":iso_now(),
            "generated_by":admin["id"],"record_count":len(rows),"sha256":digest,
            "exclusions":["pending reports","rejected reports","predictions","demo incidents"],
            "records":rows}


class AcquireIn(BaseModel):
    source:Literal["NERC","Ikeja Electric","Eko DisCo"]
    source_url:str


@router.post("/admin/pipeline/acquire",status_code=202)
async def acquire(body:AcquireIn,admin=Depends(require_admin)):
    del admin
    if source_host(body.source_url) not in {"nerc.gov.ng","www.nerc.gov.ng","ikejaelectric.com","www.ikejaelectric.com","ekedp.com","www.ekedp.com"}:
        raise HTTPException(400,"Source domain is not approved")
    def download():
        request=urllib.request.Request(body.source_url,headers={"User-Agent":"DownNepaDataPipeline/1.0"})
        with urllib.request.urlopen(request,timeout=25) as response:
            return response.read(10_000_001),response.headers.get("Content-Type","")
    try: payload,content_type=await asyncio.to_thread(download)
    except OSError as error: raise HTTPException(502,"Trusted source could not be acquired") from error
    if len(payload)>10_000_000: raise HTTPException(413,"Source response exceeds 10 MB")
    digest=hashlib.sha256(payload).hexdigest()
    with db() as connection:
        run=connection.execute(
            "INSERT INTO pipeline_runs(source,source_url,source_hash,status,raw_count,parser_version,started_at,finished_at) VALUES(?,?,?,?,?,?,?,?)",
            (body.source,body.source_url,digest,"acquired",1,"raw-acquire-v1",iso_now(),iso_now()),
        ).lastrowid
    return {"run_id":run,"source_hash":digest,"content_type":content_type,"byte_count":len(payload)}
