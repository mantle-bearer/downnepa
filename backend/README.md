# DownNepa FastAPI service

This is the authoritative API and SQLite implementation. The hosted Sites build
uses a review adapter because its runtime does not run Python.

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Set `DOWNNEPA_ADMIN_KEY` outside local development. Set `DOWNNEPA_ENV=production`
to stop returning one-time login codes in API responses and connect the mail
delivery adapter before launch.

The database uses WAL mode and is created at `backend/downnepa.db` by default.
OpenAPI documentation is available at `/docs`.

