import importlib

import pytest
from fastapi.testclient import TestClient

from backend.scripts.train_model import verified_snapshot_records


def test_training_snapshot_integrity_is_enforced():
    with pytest.raises(ValueError, match="integrity"):
        verified_snapshot_records(
            {
                "schema_version": "downnepa-training-v1",
                "sha256": "0" * 64,
                "records": [{"state": "out"}],
            }
        )


def test_complete_non_ml_flow(tmp_path, monkeypatch):
    monkeypatch.setenv("DOWNNEPA_DB_PATH", str(tmp_path / "downnepa.db"))
    monkeypatch.setenv("DOWNNEPA_ADMIN_EMAIL", "admin@downnepa.com")
    monkeypatch.setenv("DOWNNEPA_ADMIN_PASSWORD", "adminpassword")

    module = importlib.import_module("backend.app.main")
    with TestClient(module.app) as client:
        signup = client.post(
            "/api/auth/signup",
            json={
                "display_name": "Test Resident",
                "email": "resident@example.com",
                "password": "normalpass123",
            },
        )
        assert signup.status_code == 201
        assert signup.json()["user"]["referral_code"].startswith("DN")
        assert len(signup.json()["user"]["referral_code"]) == 18
        token = signup.json()["access_token"]
        auth = {"Authorization": f"Bearer {token}"}

        search = client.get("/api/areas", params={"search": "Olowora"})
        assert search.status_code == 200
        assert search.json()[0]["slug"] == "ojodu-berger"

        report = client.post(
            "/api/reports",
            headers=auth,
            json={"area_slug": "ojodu-berger", "state": "out", "note": "Whole street affected"},
        )
        assert report.status_code == 202
        assert report.json()["points_awarded"] == 5
        badges_before_review = client.get("/api/v1/community/badges", headers=auth).json()
        assert not any(item["earned"] for item in badges_before_review["badges"])

        dashboard = client.get("/api/dashboard", headers=auth)
        assert dashboard.status_code == 200
        assert dashboard.json()["user"]["points"] == 5

        admin_login = client.post(
            "/api/auth/login",
            json={"email": "admin@downnepa.com", "password": "adminpassword"},
        )
        admin = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
        reviewed = client.post(
            f"/api/admin/reports/{report.json()['report_id']}/review",
            headers=admin,
            json={"decision": "verified"},
        )
        assert reviewed.status_code == 200
        badges_after_review = client.get("/api/v1/community/badges", headers=auth).json()
        assert next(
            item for item in badges_after_review["badges"] if item["badge_key"] == "first_report"
        )["earned"]

        status = client.get("/api/status/ojodu-berger").json()
        assert status["status"] == "out"
        assert status["prediction"] is None

        street_search = client.get("/api/v1/locations/search", params={"q": "Banana Island"}).json()
        assert street_search["results"][0]["canonical_name"] == "Banana Island"
        assert street_search["results"][0]["service_area_slug"] == "ikoyi"

        proposal = client.post(
            "/api/v1/locations/proposals",
            headers=auth,
            json={
                "name": "Test Power Street",
                "expected_area_slug": "ikoyi",
                "location_type": "street",
            },
        )
        approved = client.post(
            f"/api/v1/admin/locations/{proposal.json()['proposal_id']}/review",
            headers=admin,
            json={"decision": "approved", "notes": "Verified during test"},
        )
        assert approved.status_code == 200
        proposed_search = client.get(
            "/api/v1/locations/search", params={"q": "Test Power Street"}
        ).json()
        assert proposed_search["results"][0]["canonical_name"] == "Test Power Street"

        referred_signup = client.post(
            "/api/auth/signup",
            json={
                "display_name": "Referred Resident",
                "email": "referred@example.com",
                "password": "normalpass123",
                "referral_code": signup.json()["user"]["referral_code"],
            },
        )
        referred_auth = {"Authorization": f"Bearer {referred_signup.json()['access_token']}"}
        referred_report = client.post(
            "/api/reports",
            headers=referred_auth,
            json={"area_slug": "ikoyi", "state": "restored"},
        ).json()
        client.post(
            f"/api/admin/reports/{referred_report['report_id']}/review",
            headers=admin,
            json={"decision": "verified"},
        )
        with module.db() as connection:
            referral = connection.execute(
                "SELECT * FROM referrals WHERE referred_user_id=?",
                (referred_signup.json()["user"]["id"],),
            ).fetchone()
            assert referral["status"] == "qualified"
            assert referral["qualified_at"]

        pipeline = client.post(
            "/api/admin/pipeline/import",
            headers=admin,
            json={
                "source": "NERC test",
                "source_url": "https://nerc.gov.ng",
                "source_hash": "a" * 64,
                "rows": [
                    {
                        "disco": "Eko DisCo",
                        "reporting_period_start": "2026-06-01",
                        "reporting_period_end": "2026-06-30",
                        "feeder_name": "Sabo 11kV",
                        "location": "Yaba",
                        "major_areas_served": "Yaba, Akoka",
                        "average_supply_hours_per_day": 18.4,
                        "estimated_outage_hours_per_day": 5.6,
                        "current_band": "B",
                        "source_url": "https://nerc.gov.ng",
                    }
                ],
            },
        )
        assert pipeline.status_code == 200
        assert pipeline.json()["clean"] == 1

        rejected = client.post(
            f"/api/admin/reports/{report.json()['report_id']}/review",
            headers=admin,
            json={"decision": "rejected"},
        )
        assert rejected.status_code == 200
        badges_after_rejection = client.get("/api/v1/community/badges", headers=auth).json()
        assert not next(
            item for item in badges_after_rejection["badges"] if item["badge_key"] == "first_report"
        )["earned"]
