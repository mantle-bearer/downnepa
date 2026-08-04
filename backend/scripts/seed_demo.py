#!/usr/bin/env python3
"""Seed a deterministic, extensive DownNepa dataset for local UX and E2E testing."""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        default=os.getenv("DOWNNEPA_DB_PATH", "data/downnepa.db"),
        help="SQLite database path (default: data/downnepa.db)",
    )
    return parser.parse_args()


args = parse_args()
os.environ["DOWNNEPA_DB_PATH"] = str(Path(args.db).resolve())
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.main import db, hash_password, initialise  # noqa: E402

SEED_VERSION = "mock_seed_v1"
DEMO_PASSWORD = "DownNepaDemo!2026"
MEMBER_EMAIL = "member@demo.downnepa.com"
ADMIN_EMAIL = "admin@demo.downnepa.com"
NAMES = [
    "Adaeze Okafor",
    "Tunde Adebayo",
    "Amaka Eze",
    "Chinedu Nwosu",
    "Bola Balogun",
    "Kemi Adeyemi",
    "Femi Johnson",
    "Yetunde Lawal",
    "Ifeanyi Obi",
    "Aisha Bello",
    "Kunle Ajayi",
    "Zainab Musa",
    "Seyi Ogunleye",
    "Nneka Umeh",
    "Emeka Okoli",
    "Funmi George",
    "Damilola Peters",
    "Uche Ezenwa",
]
REPORT_NOTES = [
    "Whole street went off at the same time.",
    "Low voltage before the outage started.",
    "Transformer area is affected; adjoining street still has power.",
    "Power returned and has remained stable for over twenty minutes.",
    "Repeated interruptions in the last hour.",
    "Estate security confirmed the feeder interruption.",
    None,
]


def stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat()


def main() -> None:
    initialise()
    now = datetime.now(UTC).replace(microsecond=0)
    password_hash = hash_password(DEMO_PASSWORD, bytes.fromhex("01" * 16))
    with db() as connection:
        demo_users = [(ADMIN_EMAIL, "DownNepa Demo Admin", "admin", 1.0)] + [
            (
                MEMBER_EMAIL if index == 0 else f"member{index + 1:02d}@demo.downnepa.com",
                name,
                "member",
                0.58 + (index % 7) * 0.055,
            )
            for index, name in enumerate(NAMES)
        ]
        for email, name, role, trust in demo_users:
            connection.execute(
                """INSERT INTO users(
                email,password_hash,display_name,role,trust_score,points,status,created_at)
                VALUES(?,?,?,?,?,0,'active',?)
                ON CONFLICT(email) DO UPDATE SET password_hash=excluded.password_hash,
                display_name=excluded.display_name,role=excluded.role,trust_score=excluded.trust_score,
                status='active'""",
                (email, password_hash, name, role, trust, stamp(now - timedelta(days=120))),
            )

        users = connection.execute(
            "SELECT * FROM users WHERE email LIKE '%@demo.downnepa.com' ORDER BY id"
        ).fetchall()
        areas = connection.execute("SELECT * FROM areas WHERE active=1 ORDER BY id").fetchall()
        user_ids = [row["id"] for row in users if row["role"] == "member"]

        connection.execute(
            """DELETE FROM report_votes WHERE report_id IN
            (SELECT id FROM reports WHERE dedupe_key LIKE ?)""",
            (f"{SEED_VERSION}:%",),
        )
        connection.execute("DELETE FROM point_events WHERE reason LIKE 'mock_%'")
        connection.execute("DELETE FROM saved_places WHERE label LIKE 'Demo %'")
        connection.execute("DELETE FROM incidents WHERE verification_method=?", (SEED_VERSION,))
        connection.execute("DELETE FROM audit_events WHERE actor='seed'")

        report_ids: list[int] = []
        for index in range(180):
            area = areas[index % min(36, len(areas))]
            user_id = user_ids[index % len(user_ids)]
            state = ("out", "restored", "unstable", "out", "restored")[index % 5]
            review_state = (
                "pending"
                if index < 42
                else "quarantined"
                if index % 17 == 0
                else "rejected"
                if index % 13 == 0
                else "verified"
            )
            observed = now - timedelta(hours=index * 3 + index % 7)
            dedupe_key = f"{SEED_VERSION}:{index:04d}"
            connection.execute(
                """INSERT INTO reports(
                area_id,user_id,state,note,observed_at,created_at,review_state,dedupe_key)
                VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(dedupe_key) DO UPDATE SET
                area_id=excluded.area_id,user_id=excluded.user_id,state=excluded.state,
                note=excluded.note,observed_at=excluded.observed_at,created_at=excluded.created_at,
                review_state=excluded.review_state""",
                (
                    area["id"],
                    user_id,
                    state,
                    REPORT_NOTES[index % len(REPORT_NOTES)],
                    stamp(observed),
                    stamp(observed + timedelta(minutes=2)),
                    review_state,
                    dedupe_key,
                ),
            )
            report_id = connection.execute(
                "SELECT id FROM reports WHERE dedupe_key=?", (dedupe_key,)
            ).fetchone()["id"]
            report_ids.append(report_id)
            if review_state == "verified":
                connection.execute(
                    """INSERT INTO point_events(
                    user_id,points,reason,entity_type,entity_id,created_at)
                    VALUES(?,10,'mock_verified','report',?,?)""",
                    (user_id, str(report_id), stamp(observed + timedelta(minutes=15))),
                )
            connection.execute(
                """INSERT INTO point_events(user_id,points,reason,entity_type,entity_id,created_at)
                VALUES(?,5,'mock_submitted','report',?,?)""",
                (user_id, str(report_id), stamp(observed + timedelta(minutes=2))),
            )

        for index, report_id in enumerate(report_ids[:120]):
            reporter = connection.execute(
                "SELECT user_id FROM reports WHERE id=?", (report_id,)
            ).fetchone()["user_id"]
            voters = [user_id for user_id in user_ids if user_id != reporter]
            for offset in range(1 + index % 4):
                voter = voters[(index + offset) % len(voters)]
                vote = "dispute" if (index + offset) % 19 == 0 else "confirm"
                connection.execute(
                    """INSERT OR REPLACE INTO report_votes(report_id,user_id,vote,created_at)
                    VALUES(?,?,?,?)""",
                    (report_id, voter, vote, stamp(now - timedelta(hours=index * 3 - offset))),
                )

        for index in range(96):
            area = areas[index % min(32, len(areas))]
            state = ("out", "restored", "unstable", "restored")[index % 4]
            verified = now - timedelta(minutes=8 + index * 48)
            evidence = 2 + index % 8
            confidence = min(0.98, 0.62 + evidence * 0.045)
            connection.execute(
                """INSERT INTO incidents(area_id,state,confidence,started_at,ended_at,verified_at,
                evidence_count,verification_method,source_summary) VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    area["id"],
                    state,
                    confidence,
                    stamp(verified - timedelta(minutes=20)),
                    stamp(verified) if state == "restored" else None,
                    stamp(verified),
                    evidence,
                    SEED_VERSION,
                    f"{evidence} residents"
                    + (" + trusted source" if index % 6 == 0 else " confirmed"),
                ),
            )

        for area_index, area in enumerate(areas):
            band_baseline = {"A": 21.0, "B": 17.5, "C": 12.5, "D": 8.5, "E": 4.5}.get(
                area["service_band"], 13.5
            )
            for day_offset in range(14):
                supply_day = date.today() - timedelta(days=day_offset)
                variation = ((area_index * 3 + day_offset * 5) % 9 - 4) * 0.55
                available = max(1.0, min(24.0, band_baseline + variation))
                connection.execute(
                    """INSERT INTO supply_daily(
                    area_id,day,available_hours,observation_count,source_summary)
                    VALUES(?,?,?,?,?) ON CONFLICT(area_id,day) DO UPDATE SET
                    available_hours=excluded.available_hours,
                    observation_count=excluded.observation_count,
                    source_summary=excluded.source_summary""",
                    (
                        area["id"],
                        supply_day.isoformat(),
                        round(available, 1),
                        3 + (area_index + day_offset) % 18,
                        "Seeded verified observations",
                    ),
                )

        for user_index, user_id in enumerate(user_ids):
            for place_index in range(3):
                area = areas[(user_index * 4 + place_index) % len(areas)]
                label = ("Demo Home", "Demo Work", "Demo Family")[place_index]
                connection.execute(
                    """INSERT INTO saved_places(
                    user_id,area_id,label,created_at,notifications_enabled)
                    VALUES(?,?,?,?,?) ON CONFLICT(user_id,area_id) DO UPDATE SET
                    label=excluded.label,notifications_enabled=excluded.notifications_enabled""",
                    (
                        user_id,
                        area["id"],
                        label,
                        stamp(now - timedelta(days=30 - place_index)),
                        place_index != 2,
                    ),
                )

        for run_index in range(8):
            source_hash = hashlib.sha256(
                f"{SEED_VERSION}:pipeline:{run_index}".encode()
            ).hexdigest()
            existing = connection.execute(
                "SELECT id FROM pipeline_runs WHERE source_hash=?", (source_hash,)
            ).fetchone()
            if existing:
                continue
            started = now - timedelta(days=run_index * 4 + 1)
            connection.execute(
                """INSERT INTO pipeline_runs(source,source_url,source_hash,status,raw_count,
                clean_count,quarantined_count,duplicate_count,started_at,finished_at,parser_version)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    f"Demo trusted import {run_index + 1}",
                    "https://nerc.gov.ng",
                    source_hash,
                    "completed",
                    18 + run_index,
                    14 + run_index,
                    2 + run_index % 3,
                    2,
                    stamp(started),
                    stamp(started + timedelta(seconds=12)),
                    "seed-v1",
                ),
            )

        for index in range(60):
            created = now - timedelta(minutes=index * 19)
            action = ("submit", "verified", "import", "quarantined", "login")[index % 5]
            entity_type = ("report", "report", "pipeline_run", "report", "session")[index % 5]
            connection.execute(
                """INSERT INTO audit_events(actor,action,entity_type,entity_id,detail,created_at)
                VALUES('seed',?,?,?,?,?)""",
                (
                    action,
                    entity_type,
                    str(1000 + index),
                    f"{SEED_VERSION} realistic test event",
                    stamp(created),
                ),
            )

        for user_id in user_ids:
            points = connection.execute(
                "SELECT COALESCE(SUM(points),0) FROM point_events WHERE user_id=?", (user_id,)
            ).fetchone()[0]
            connection.execute("UPDATE users SET points=? WHERE id=?", (points, user_id))
        connection.execute("UPDATE users SET points=500 WHERE email=?", (ADMIN_EMAIL,))

    print(f"Seeded {args.db}")
    print(f"Member login: {MEMBER_EMAIL} / {DEMO_PASSWORD}")
    print(f"Admin login:  {ADMIN_EMAIL} / {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
