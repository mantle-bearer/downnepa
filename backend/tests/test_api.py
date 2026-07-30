import importlib

from fastapi.testclient import TestClient


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

        status = client.get("/api/status/ojodu-berger").json()
        assert status["status"] == "out"
        assert status["prediction"] is None

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
