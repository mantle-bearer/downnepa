#!/usr/bin/env bash
set -euo pipefail

export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/downnepa-uv-cache}"

if [[ ! -f frontend/dist/index.html ]]; then
  npm --prefix frontend ci
  npm --prefix frontend run build
fi

exec uv run --frozen --no-dev uvicorn backend.app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}"
