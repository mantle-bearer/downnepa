# DownNepa API

The FastAPI schema is available at `/docs` and `/openapi.json`. Important
boundaries are:

- Public: areas, location/street search, nearby locations, status, history,
  incidents, public reports, coverage, leaderboard, and temporary prediction.
- Member: signup/login/logout, reports and votes, saved places, location
  proposals, badges, streak progress, and notification preferences.
- Admin: evidence review, trusted-source acquisition/import, quarantine,
  location review, data-quality totals, audit events, and training snapshots.

`POST /api/v1/predict` is asynchronous and currently returns
`temporary: true`. It must never be interpreted as evidence. A future approved
model implements the async contract in `backend/app/ml/contract.py`.

Unknown `/api/*` routes return JSON 404 responses and are not swallowed by the
SPA fallback.
