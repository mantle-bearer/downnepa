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
- Passwordless email-code contribution flow
- Outage, restoration, and unstable-supply reports
- Evidence confidence and freshness indicators
- Admin reconciliation and quarantine queue
- Raw, clean, quarantined, and verified pipeline stages
- Active, shadow, retired, and rejected model lifecycle
- Replaceable ML model contract
- PWA-ready responsive interface

## Architecture

The repository contains two deliberately separated runtimes:

- `app/`: Next.js/Vinext review interface deployed through ChatGPT Sites
- `backend/`: authoritative FastAPI and SQLite API

The hosted interface currently uses deterministic review data because Sites
does not run Python. Production deployment should configure the frontend API
adapter to communicate with the separately deployed FastAPI service.

The detailed product, database, pipeline, authentication, and ML design is in
[`docs/PRODUCT_AND_ARCHITECTURE_PLAN.md`](docs/PRODUCT_AND_ARCHITECTURE_PLAN.md).

## Frontend

Requirements:

- Node.js 22.13 or newer

```bash
npm ci
npm run dev
```

Useful checks:

```bash
npm run build
npm test
npm run lint
```

## FastAPI backend

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The service creates `backend/downnepa.db`, enables SQLite WAL mode, and exposes
OpenAPI documentation at `http://localhost:8000/docs`.

Configure at least these variables before a production deployment:

```text
DOWNNEPA_ENV=production
DOWNNEPA_ADMIN_KEY=<strong-random-secret>
DOWNNEPA_WEB_ORIGINS=https://your-production-domain
```

Production authentication requires an email-delivery adapter for one-time
codes. Development mode returns the code in the API response for local testing.

## Source-of-truth rules

1. A resident submission is an observation, not an incident.
2. Reconciliation merges corroborating evidence into a canonical incident.
3. Predictions never create reports or verified incidents.
4. Only verified incidents enter training snapshots.
5. Model activation and admin decisions must create audit events.

