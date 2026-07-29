# DownNepa Product and Architecture Plan

## 1. Product definition

DownNepa is a Lagos-first electricity availability and outage intelligence
product. It lets anyone check the latest known power state of an area without
creating an account, while signed-in residents can submit and verify reports,
save places, and contribute trustworthy incident data.

The product is deliberately narrower than a nationwide tracker:

- Geography: Lagos State only for the first release.
- Distribution companies: Ikeja Electric and Eko Electricity Distribution.
- Primary public value: current status, freshness, confidence, recent history,
  and upcoming risk for a selected Lagos area.
- Primary data value: convert noisy community reports and official records into
  verified outage incidents suitable for model training.
- Primary ML value: versioned models can be introduced, evaluated, activated,
  rolled back, and replaced without coupling the application to one model.

## 2. Product principles

1. Monitoring remains public. Authentication must never block basic status,
   history, area search, or prediction viewing.
2. Predictions and observations remain separate. A model prediction must never
   be silently stored as a verified outage report.
3. Every status includes freshness and confidence. “Unknown” is preferable to
   an invented answer.
4. Electrical topology is more important than a large street catalogue.
   Location records should eventually connect to a DisCo, business unit,
   injection substation, feeder, and service band.
5. Community input is evidence, not immediate truth. Reports become verified
   incidents only after reconciliation.
6. Model versions are replaceable plugins. The web application depends on an
   inference contract, not a specific scikit-learn class or pickle file.
7. Admin actions are auditable. Verification, rejection, model activation,
   rollback, source ingestion and user moderation create immutable audit events.
8. SQLite is used intentionally. Writes are short, WAL mode is enabled, and
   background ingestion/training jobs do not hold long transactions.

## 3. Release scope

### Public, unauthenticated

- Search or select a Lagos area.
- See latest status: power available, outage reported, unstable, or unknown.
- See freshness, confidence, number of independent reports and source mix.
- View recent outage/restoration timeline.
- View a compact seven-day availability chart.
- View current outage risk and the active model version.
- Browse Lagos-wide recent verified incidents.
- Inspect Ikeja Electric and Eko DisCo coverage summary.
- Install the PWA.

### Lightweight authenticated member

- Submit “power out”, “power restored”, or “unstable supply”.
- Confirm or dispute reports affecting the same area.
- Save home, work, school, or another place.
- View personal contribution history and trust status.
- Receive future alert support through an adapter without coupling alerts to
  the initial release.

### Administrator

- Overview of pending reports, verified incidents, source health and model
  status.
- Review, merge, verify, reject and flag reports.
- Manage Lagos areas, aliases, coordinates, DisCo and feeder metadata.
- Run or inspect ingestion pipeline batches.
- Inspect raw, cleaned, quarantined and verified records.
- Register model versions and evaluation metadata.
- Activate, shadow, retire or roll back a model.
- View prediction outcomes and data-quality warnings.
- Review users, abuse signals and audit events.

### Explicitly deferred

- Nationwide coverage.
- Billing, payment or tariff comparison.
- Guaranteed real-time alerts.
- Exact feeder mapping for every Lagos street before a credible source exists.
- Automatic retraining directly from unverified community reports.
- Model-generated reports in the public incident feed.

## 4. User roles and access

| Capability | Anonymous | Member | Admin |
| --- | --- | --- | --- |
| Monitor areas | Yes | Yes | Yes |
| View history and predictions | Yes | Yes | Yes |
| Submit outage/restoration report | Prompt for lightweight sign-in | Yes | Yes |
| Confirm or dispute | Prompt for lightweight sign-in | Yes | Yes |
| Save places | Device-local preview, account for sync | Yes | Yes |
| Review reports | No | No | Yes |
| Manage pipeline | No | No | Yes |
| Manage model versions | No | No | Yes |

## 5. Authentication decision

The production FastAPI service will use passwordless email one-time codes or
magic links as the primary flow. Users enter only an email address and a short
code. No strong-password rules are required because no reusable password is
created.

Authentication controls write attribution and saved places, not public
monitoring.

Session design:

- Short-lived signed session cookie.
- HttpOnly, Secure, SameSite=Lax.
- Rotating session identifiers stored as hashes.
- One-time codes are hashed, expire quickly, are single-use and rate-limited.
- Admin authorization is a server-side role check on every protected request.
- A development-only seeded admin is allowed only when explicitly enabled.

For the hosted Sites review surface, optional Sign in with ChatGPT may be used
only as a preview identity mechanism. It is not the production DownNepa
authentication architecture.

## 6. System architecture

```text
Web/PWA
  |
  | HTTPS JSON API
  v
FastAPI application
  |-- public monitoring routes
  |-- passwordless authentication
  |-- report and verification services
  |-- admin services
  |-- prediction service
  |-- pipeline orchestration service
  |
  v
SQLite database in WAL mode
  |-- operational tables
  |-- raw ingestion records
  |-- canonical incidents
  |-- prediction logs/outcomes
  |-- model registry
  |-- audit events
  |
  +--> model artifacts directory
  +--> source snapshots / pipeline exports
```

The deployed Sites UI cannot execute a Python/FastAPI process. The implementation
therefore uses a frontend adapter boundary:

- `FastApiClient`: production adapter for the real FastAPI service.
- `ReviewDataClient`: deterministic hosted review data for the Sites deployment.

The review adapter demonstrates all states and interactions without pretending
to be the production database. The FastAPI contract remains authoritative.

## 7. FastAPI package boundaries

```text
backend/
  app/
    main.py
    config.py
    db/
      connection.py
      migrations/
    api/
      public.py
      auth.py
      reports.py
      admin.py
      pipeline.py
      models.py
    domain/
      locations.py
      reports.py
      incidents.py
      predictions.py
      model_registry.py
    repositories/
      locations.py
      reports.py
      incidents.py
      predictions.py
      model_registry.py
    services/
      authentication.py
      report_reconciliation.py
      incident_builder.py
      prediction.py
      pipeline.py
    ml/
      contract.py
      loader.py
      versions/
    schemas/
    security/
    tests/
```

API routes depend on services, services depend on repository protocols, and
repositories own SQL. ML implementations depend only on the model contract.

## 8. Core SQLite schema

### Identity

- `users`
  - id, email, display_name, role, trust_score, status, created_at
- `login_challenges`
  - id, email, code_hash, expires_at, used_at, attempts
- `sessions`
  - id, user_id, token_hash, expires_at, revoked_at

### Geography and electrical topology

- `discos`
  - id, code, name
- `areas`
  - id, slug, name, lga, latitude, longitude, disco_id, feeder_id,
    service_band, topology_confidence, active
- `area_aliases`
  - id, area_id, alias, source
- `feeders`
  - id, disco_id, code, name, injection_substation, business_unit,
    service_band, source_url, source_date, confidence

### Community evidence

- `reports`
  - id, reporter_id, area_id, feeder_id, event_type, observed_at,
    submitted_at, latitude, longitude, source, status, notes
- `report_votes`
  - id, report_id, voter_id, verdict, created_at
- `report_evidence`
  - id, report_id, evidence_type, value, metadata_json

### Canonical truth

- `outage_incidents`
  - id, area_id, feeder_id, started_at, restored_at, duration_minutes,
    verification_status, confidence_score, source_count, created_at
- `incident_reports`
  - incident_id, report_id, relation_type, weight
- `status_snapshots`
  - id, area_id, status, confidence_score, observed_at, incident_id

### Pipeline

- `data_sources`
  - id, name, source_type, base_url, enabled, schedule, parser_version
- `ingestion_runs`
  - id, source_id, started_at, completed_at, status, records_seen,
    records_accepted, records_quarantined, checksum, error_summary
- `raw_observations`
  - id, ingestion_run_id, external_id, payload_json, observed_at,
    checksum, ingested_at
- `clean_observations`
  - id, raw_id, area_id, feeder_id, event_type, observed_at,
    quality_score, normalization_version
- `quarantined_observations`
  - id, raw_id, reason_code, detail, reviewed_at, reviewer_id

### ML

- `model_versions`
  - id, name, version, artifact_uri, artifact_sha256, feature_schema_version,
    training_data_version, metrics_json, status, created_at, activated_at
- `model_deployments`
  - id, model_version_id, mode, traffic_percent, started_at, ended_at
- `predictions`
  - id, model_version_id, area_id, predicted_for, generated_at,
    outage_probability, expected_duration_minutes, confidence,
    feature_snapshot_json
- `prediction_outcomes`
  - id, prediction_id, incident_id, outcome, evaluated_at

### Governance

- `audit_events`
  - id, actor_id, action, entity_type, entity_id, before_json,
    after_json, created_at

## 9. Report-to-incident reconciliation

Reports never directly become training labels.

1. Accept a signed-in user report.
2. Normalise the area and optional feeder.
3. Apply duplicate and spam checks.
4. Search for a compatible open incident window.
5. Add the report as evidence or create a candidate incident.
6. Accumulate independent confirmations and disputes.
7. Compare related areas only when feeder/topology evidence supports it.
8. Mark an incident verified when configurable evidence thresholds are met.
9. Pair an outage start with a credible restoration event.
10. Freeze a versioned training snapshot; later corrections create new versions
    rather than silently rewriting past datasets.

Initial verification policy:

- One official source can verify an incident.
- Two independent trusted members can verify an incident.
- Three ordinary independent members can verify an incident.
- Conflicting evidence moves the incident to admin review.
- Model predictions never count as independent evidence.

## 10. Data pipeline

### Stages

1. Extract
   - NERC feeder performance appendices.
   - Ikeja Electric and Eko DisCo planned outage notices.
   - Community reports.
   - Weather observations.
   - Grid-event notices.
2. Preserve raw
   - Store original payload, source, timestamp and checksum.
3. Validate
   - Required fields, timestamp bounds, Lagos boundary, known source.
4. Normalise
   - Area aliases, feeder names, timezone, event types and coordinates.
5. Deduplicate
   - External identifiers, checksums and spatiotemporal similarity.
6. Reconcile
   - Link observations to candidate or existing incidents.
7. Verify
   - Apply evidence policy and admin review.
8. Feature
   - Generate point-in-time-correct model features.
9. Snapshot
   - Produce immutable training dataset versions.
10. Monitor
   - Pipeline counts, quarantine reasons, source freshness and drift.

### Pipeline qualities

- Every derived row traces back to raw source records.
- Parser and normalisation versions are stored.
- Jobs are idempotent.
- Failed rows are quarantined rather than dropped.
- Training features cannot use information recorded after prediction time.
- Personally identifying reporter data is excluded from training exports.

## 11. Prediction targets

The first release should not attempt one vague “power AI” model.

### Model A: current-status confidence

Purpose: reconcile recent observations into `available`, `outage`, `unstable`,
or `unknown`.

This can begin as a deterministic evidence model and does not need to be
marketed as ML.

### Model B: next-window outage risk

Target:

> Will a verified outage start in this area/feeder during the next six hours?

Initial features:

- hour, weekday, month and rainy-season indicator
- DisCo and service band
- rolling outage counts over 24 hours, 7 days and 30 days
- rolling average and median outage duration
- time since last verified restoration
- recent official supply-hours performance
- planned-maintenance flag
- grid-event flag
- rainfall, wind and storm indicators

### Model C: restoration duration

Deferred until enough verified incident start/end pairs exist.

## 12. Model plugin contract

Every model implementation supplies:

- `metadata()`
  - name, semantic version, training dataset version, feature schema version,
    supported task and artifact checksum
- `load(artifact_path)`
- `validate_feature_schema(features)`
- `predict(features)`
  - outage probability, optional duration, confidence and explanation fields
- `healthcheck()`

The loader:

1. Reads the active model record.
2. Verifies artifact checksum.
3. Resolves a registered implementation.
4. Validates feature-schema compatibility.
5. Loads the artifact once and caches it.
6. Falls back to a deterministic baseline if loading fails.
7. Logs the exact model version and feature snapshot for every prediction.

Supported lifecycle states:

- candidate
- shadow
- active
- retired
- rejected

Only one active version exists for a task. Rollback changes the deployment
pointer; it does not overwrite artifacts.

## 13. Model evaluation and trust

- Chronological train/validation/test split.
- Group-aware evaluation by feeder or area.
- Metrics: ROC-AUC, PR-AUC, Brier score, calibration curve, recall at a chosen
  alert threshold and false-alert rate.
- Compare against simple baselines:
  - service-band probability
  - previous-period status
  - rolling area outage rate
- Do not claim accuracy without the evaluation window and sample size.
- Display “insufficient data” rather than a probability for unsupported areas.
- Track post-deployment prediction outcomes and calibration drift.
- Shadow models receive real feature snapshots but cannot affect public output.

## 14. Public information architecture

### Home / monitor

- DownNepa wordmark and Lagos-only badge.
- Area search and “use my location”.
- Immediate current-status card with freshness and confidence.
- Two prominent report actions, visible but sign-in-gated only when pressed.
- Seven-day availability chart.
- Current outage risk with explicit model/version and limitation language.
- Recent verified incidents.
- IE/EKEDC system summary.
- Trust explanation: official, community and model signals are distinct.

### Area detail

- Current state and evidence.
- Timeline of verified incidents.
- Supply-hours trend.
- Prediction forecast.
- Feeder metadata when verified.
- Report and confirmation actions.

### Account

- Passwordless entry.
- Saved places.
- Contribution history.
- Trust and privacy settings.

### Admin

- Operations overview.
- Verification queue.
- Incidents.
- Pipeline runs and quarantine.
- Lagos topology.
- Models and deployments.
- Users and audit log.

## 15. Visual direction

The attached NEPAWatch stylesheet establishes a useful dark utility-app
direction, but DownNepa should not look like a clone.

DownNepa visual system:

- Near-black green-tinted background.
- Electric lime for healthy/available and primary actions.
- Coral red for outages.
- Amber for unstable or uncertain.
- Warm off-white typography.
- Dense operational data in clean cards with more breathing room than
  NEPAWatch.
- Bricolage-style display typography paired with a neutral sans-serif body.
- Mobile-first PWA with a desktop control-room layout.
- Status is never communicated by colour alone; icons and text accompany it.

## 16. PWA

Manifest:

- name: DownNepa Lagos
- short name: DownNepa
- description: Lagos electricity outage monitoring and community reporting
- standalone display
- portrait-primary orientation
- utilities and news categories
- theme/background colours aligned to the product

Offline behavior:

- Cache the application shell.
- Preserve the most recently viewed public status with a visible “cached”
  timestamp.
- Queue no report silently. A report requires confirmed online submission.

## 17. Security and abuse prevention

- Parameterised SQL only.
- CSRF protection for cookie-authenticated writes.
- Rate limits by account, IP hash and area.
- One active report of the same type per user/area cooldown.
- No self-confirmation.
- Unique vote constraint per user/report.
- Server-side role checks for every admin route.
- Sanitised free-text fields and strict length limits.
- Coarse public coordinates; exact user coordinates are not publicly exposed.
- Audit sensitive admin actions.
- Back up the SQLite database and model artifacts separately.
- Integrity-check SQLite backups and test restoration.

## 18. SQLite operating model

- WAL journal mode.
- Foreign keys enabled.
- Busy timeout configured.
- Short write transactions.
- Appropriate composite indexes for area/time, feeder/time, status and source.
- Ingestion jobs process bounded batches.
- Training reads from immutable snapshots rather than locking operational
  tables.
- A single application instance owns writes for the capstone deployment.
- Document the future PostgreSQL migration boundary without implementing it
  prematurely.

## 19. Testing strategy

### Backend

- Domain unit tests.
- Repository integration tests against temporary SQLite databases.
- API tests for anonymous monitoring, auth, member writes and admin isolation.
- Pipeline idempotency and quarantine tests.
- Incident-reconciliation scenarios.
- Model-contract compatibility and fallback tests.

### Frontend

- Public status viewing without authentication.
- Sign-in prompt appears only on write actions.
- Area switching.
- Report/restore interaction.
- Prediction limitation and version display.
- Admin navigation and filtering.
- Responsive mobile and desktop layouts.
- Keyboard navigation, focus visibility and screen-reader labels.

### Data and ML

- Schema validation.
- Leakage checks.
- Duplicate raw-observation checks.
- Point-in-time feature tests.
- Artifact checksum and feature-version tests.
- Reproducible training manifest.

## 20. Delivery milestones

### Milestone 1: reviewable product shell

- Complete public monitoring experience with realistic Lagos data.
- Responsive visual system and PWA metadata.
- Anonymous core access.
- Report and sign-in interaction prototypes.

### Milestone 2: functional product workflows

- Area monitoring, report flow, confirmations, saved places and account flow.
- Admin verification, pipeline and model registry surfaces.
- Data/service adapter boundary.

### Milestone 3: FastAPI and SQLite service

- Production schema and migrations.
- Public API, passwordless auth, reports, verification and admin endpoints.
- Pipeline ingestion/reconciliation.
- Model registry and baseline model plugin.

### Milestone 4: training notebook and model v1

- Versioned dataset snapshot.
- Baseline and trained-model comparison.
- Calibration and evaluation report.
- Registered artifact and shadow deployment.

## 21. Acceptance criteria for this build

- An anonymous visitor can monitor Lagos outage status without signing in.
- The UI distinguishes observations, verified incidents and predictions.
- Report actions explain why lightweight sign-in is needed.
- Lagos is split between Ikeja Electric and Eko DisCo.
- The application demonstrates recent status, history and prediction.
- The admin experience exposes verification, data pipeline and model versions.
- The architecture does not depend on Supabase.
- FastAPI and SQLite are the declared production backend.
- The model interface supports version activation and rollback.
- No model output is automatically treated as verified training truth.
