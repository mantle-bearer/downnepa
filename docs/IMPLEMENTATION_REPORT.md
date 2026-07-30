# NepaWatch parity implementation report

DownNepa implements the approved non-ML product scope with FastAPI, SQLite WAL,
React, Vite, `uv`, Uvicorn, and Ruff.

Implemented:

- Public monitoring without authentication and searchable Lagos area,
  street, landmark, LGA, feeder, and alias records.
- The complete 63-group reference catalog, child-location hierarchy,
  provenance state, source counts, inactive non-Lagos preservation, nearby
  lookup, and admin review queue.
- Password signup/login with no email-verification dependency, sessions,
  roles, referrals, saved places, and preferences.
- Reports, voting, evidence review, verified incidents, confidence, history,
  audit records, points, streaks, leaderboard, and 18 badge definitions.
- Trusted-domain acquisition, hashed pipeline runs, validation, quarantine,
  deduplication, canonical records, data-quality metrics, and immutable
  training snapshots.
- Async `/api/v1/predict` temporary response and a loosely coupled async model
  contract, integrity-checked JSON runtime, and standard-library training
  script. Real model results remain intentionally pending.
- Responsive light/dark SPA, anonymous core journey, dashboards, admin area,
  manifest, service worker, offline shell, and Render blueprint.

The reference catalog is discovery metadata, not an assertion of official
electricity boundaries. Admin verification and trusted records remain the
authority layer.
