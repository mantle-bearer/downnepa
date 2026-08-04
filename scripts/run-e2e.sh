#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
e2e_db="$project_root/.artifacts/e2e.db"

mkdir -p "$project_root/.artifacts"
cd "$project_root"
npm --prefix frontend run build
DOWNNEPA_DB_PATH="$e2e_db" uv run python backend/scripts/seed_demo.py --db "$e2e_db"
exec env DOWNNEPA_DB_PATH="$e2e_db" uv run uvicorn backend.app.main:app \
  --host 127.0.0.1 --port 8001
