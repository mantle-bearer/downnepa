# DownNepa

DownNepa is a Lagos-first electricity outage monitoring and prediction product.
Anyone can check recent power status, confidence, evidence freshness, verified
incidents, supply history, and short-term outage risk without creating an
account.

Community observations are deliberately kept separate from verified incidents
and model predictions. Only verified incidents are eligible for model-training
datasets.

Live interface: https://downnepa.igbokwegoodluck8.chatgpt.site

## Product capabilities

- Anonymous outage monitoring for Lagos areas
- Ordinary email-and-password signup with no verification-email dependency
- Outage, restoration, and unstable-supply reports
- Evidence confidence and freshness indicators
- Admin reconciliation and quarantine queue
- Raw, clean, quarantined, and verified pipeline stages
- Active, shadow, retired, and rejected model lifecycle
- Replaceable ML model contract
- PWA-ready responsive interface

## Architecture

The repository contains two runtimes served as one deployment:

- `frontend/`: React/Vite single-page application
- `backend/`: authoritative FastAPI and SQLite API that serves `frontend/dist`

The earlier Sites interface remains in `app/` as deployment history. Replit
uses `frontend/`, `backend/`, `run.sh`, and `.replit`.

The detailed product, database, pipeline, authentication, and ML design is in
[`docs/PRODUCT_AND_ARCHITECTURE_PLAN.md`](docs/PRODUCT_AND_ARCHITECTURE_PLAN.md).

## Frontend

Requirements:

- Node.js 22.13 or newer

```bash
cd frontend
npm ci
npm run dev
```

Useful checks:

```bash
npm run build
```

## FastAPI backend

```bash
uv sync
uv run uvicorn backend.app.main:app --reload
```

The service creates `backend/downnepa.db`, enables SQLite WAL mode, and exposes
OpenAPI documentation at `http://localhost:8000/docs`.

The API uses FastAPI's asynchronous ASGI lifecycle and Uvicorn server. Routes
that access SQLite deliberately remain synchronous: FastAPI runs those
blocking handlers in its worker thread pool, so SQLite work does not block the
event loop. Browser requests and all other naturally asynchronous I/O remain
asynchronous.

Run the complete backend quality gate with:

```bash
uv run ruff format --check backend
uv run ruff check backend
uv run pytest
```

Configure at least these variables before a production deployment:

```text
DOWNNEPA_ENV=production
DOWNNEPA_ADMIN_KEY=<strong-random-secret>
DOWNNEPA_WEB_ORIGINS=https://your-production-domain
```

Authentication uses ordinary email and password signup/login. It does not send
verification email or one-time codes.

## Replit deployment

Import this repository into Replit and create a Reserved VM deployment. The
included `.replit` file installs the Python and frontend dependencies, builds
the SPA, and starts Uvicorn on Replit's assigned `PORT`. Python dependencies
are installed reproducibly from `uv.lock`; no `pip` command is required.

Add the values from `.env.example` as Replit Secrets. Use a persistent Reserved
VM because the application intentionally stores its SQLite database on disk.

## Trusted-source ingestion

An administrator can import normalized feeder-performance rows through the
admin UI or API. The pipeline stores immutable raw records, validates source
domains and numeric constraints, quarantines invalid rows, deduplicates clean
rows, and writes canonical feeder-performance records.

For an extracted NERC CSV:

```bash
uv run python backend/scripts/ingest_nerc_csv.py data.csv \
  --admin-email admin@example.com \
  --admin-password your-password \
  --source-url https://nerc.gov.ng/path/to/source.pdf
```

## Source-of-truth rules

1. A resident submission is an observation, not an incident.
2. Reconciliation merges corroborating evidence into a canonical incident.
3. Predictions never create reports or verified incidents.
4. Only verified incidents enter training snapshots.
5. Model activation and admin decisions must create audit events.
