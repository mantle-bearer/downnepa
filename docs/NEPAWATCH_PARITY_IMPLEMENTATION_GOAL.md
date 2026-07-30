# DownNepa: End-to-End NepaWatch Parity and Data-Quality Implementation Goal

## 1. Mission

Transform DownNepa from a partially static Lagos outage-monitoring SPA into a
fully operational, evidence-driven electricity monitoring platform for Lagos
State.

The finished product must preserve DownNepa's stronger architecture:

- FastAPI backend
- SQLite database in WAL mode
- React/Vite SPA served by FastAPI
- ordinary email-and-password authentication
- no mandatory email verification
- public monitoring without authentication
- authenticated reporting and community features
- administrator evidence review
- trusted-source ingestion pipeline
- strict separation between observations, verified incidents and predictions
- versioned, replaceable ML model contract

At the same time, it must recover the useful location intelligence, interaction
depth, community features and PWA behavior discovered in the supplied
NepaWatch JavaScript files.

This document is an implementation goal, not a request for a superficial UI
copy. Complete the work from database design through production verification.
Do not leave mock public data, disconnected buttons, placeholder features or
silent fallbacks that pretend a feature succeeded.

---

## 2. Source material

The reverse-engineering audit was based on these supplied NepaWatch files:

- `app.js`
- `index.js`
- `nigeria_data.js`
- `predict.js`

The source files collectively contain approximately:

- 9,243 lines
- 576 KB of JavaScript and markup
- 63 Lagos search groups
- 6,224 hard-coded Lagos location entries
- 3,453 unique location strings
- 164 Lagos coordinate records
- 125 Lagos parent-child relationships
- 37 broad Lagos DISCO service areas
- 18 badge definitions
- 30 demonstration feed reports
- 11 Nigerian DISCO definitions
- 255 nationwide area-band assignments
- 249 nationwide coordinates
- 36 nationwide detailed street groups
- 443 nationwide street entries
- 37 state/FCT metadata records

The NepaWatch files are reference material. They are not automatically trusted
data. Do not copy their Supabase configuration, credentials, endpoints, service
keys, branding, analytics identifiers or advertising identifiers into
DownNepa.

---

## 3. Non-negotiable product rules

### 3.1 Public access

Unauthenticated visitors must be able to:

- search Lagos areas, streets, estates and landmarks
- inspect current evidence-derived status
- inspect confidence and freshness
- inspect recent verified incidents
- inspect public report activity
- use geolocation and nearby-area discovery
- view the map
- view DISCO coverage
- inspect historical verified supply information

Authentication must not be required for core monitoring.

### 3.2 Authentication

Authentication must:

- use ordinary email and password
- allow a normal memorable password
- enforce a reasonable minimum length, not arbitrary complexity rules
- not require email verification
- not depend on sending a login code
- not pretend that an email was sent
- support login, logout and persistent sessions
- support password visibility toggles
- provide a safe password-reset strategy

If outbound email is not configured, password reset must be explicitly
unavailable or admin-assisted. Never display a false success message claiming a
reset email was sent.

### 3.3 Evidence integrity

The following entities must remain separate:

1. A resident observation
2. A confirmation or dispute
3. A trusted-source record
4. A canonical verified incident
5. A status projection derived from evidence
6. An ML prediction

Predictions must never:

- create resident reports
- become verification evidence
- verify their own output
- enter a training dataset as ground truth
- silently override fresh human or official evidence

Only verified incidents may be exported into a training snapshot.

### 3.4 No fake live data

Seed data may be used only in development/test fixtures and must be clearly
marked. Production UI must not present fabricated outage reports, confidence
values, member counts or supply histories as live facts.

### 3.5 No blind NepaWatch data import

NepaWatch's Lagos arrays contain substantial duplication and contamination:

- 6,224 total entries
- 3,453 globally unique strings
- 2,771 repeated entries
- approximately 44.5% cross-group duplication

Some large groups contain unrelated Lagos-wide locations:

- Ojodu/Omole: 715 entries, 298 internally unique
- Ikeja GRA: 534 entries, 477 internally unique
- Maryland/Anthony: 458 entries, 406 internally unique
- Allen/Opebi: 437 entries, 385 internally unique
- Agege: 395 entries, 356 internally unique

The implementation must stage, normalize, classify, validate and review source
records before they become active DownNepa locations.

---

## 4. Definition of done

The goal is complete only when:

- all approved Lagos location groups exist in SQLite
- street and landmark search is backend-driven
- coordinates and geographic hierarchy are stored in SQLite
- the public SPA no longer uses hard-coded operational status data
- public status, feed, incidents, confidence and history come from APIs
- all relevant controls work on desktop and mobile
- authentication works without verification email
- member dashboards use real account data
- report confirmation and dispute flows work
- saved places support exact locations and notification preferences
- map and geolocation flows work
- the complete approved gamification model works
- admin location review and trusted-source controls work
- the ingestion pipeline has staging, quarantine and provenance
- PWA installation and update behavior work
- ML prediction remains disabled until an approved model is available
- Ruff, pytest, TypeScript and production build checks pass
- end-to-end browser flows pass
- no known critical or high-severity defects remain
- no mock operational data appears in production

---

# Part I: Lagos Location Intelligence

## 5. Canonical location taxonomy

Do not store every search term as an undifferentiated `area`.

Every location must have a type:

- `service_area`
- `neighbourhood`
- `estate`
- `street`
- `road`
- `corridor`
- `landmark`
- `market`
- `campus`
- `hospital`
- `transport_hub`
- `bridge`
- `beach`
- `commercial_centre`
- `custom`

Recommended relationship:

```text
DISCO
  └── service area
       └── neighbourhood/estate
            └── street/landmark/campus/hospital/market
```

A street or landmark may resolve to one canonical monitoring service area.
Search results must retain the specific location while status aggregation uses
the appropriate monitoring parent.

## 6. The 63 discovered Lagos search groups

These are the 63 top-level keys found in NepaWatch's Lagos search object. They
must all be evaluated, but not all should become independent service areas.

| # | Source group | Source entries | Proposed classification | Initial disposition |
|---:|---|---:|---|---|
| 1 | Ikeja GRA | 534 | service area | keep after aggressive cleanup |
| 2 | Ikeja (Allen/Opebi) | 437 | service area | keep after aggressive cleanup |
| 3 | Maryland/Anthony | 458 | service area | keep after aggressive cleanup |
| 4 | Ogba | 389 | service area | keep after aggressive cleanup |
| 5 | Agege | 395 | service area | keep after aggressive cleanup |
| 6 | Alimosho/Ipaja | 371 | service area | keep after aggressive cleanup |
| 7 | Ojodu/Omole | 715 | service area | keep after aggressive cleanup |
| 8 | Kosofe/Ketu | 98 | service area | keep and validate |
| 9 | Gbagada | 63 | service area | keep and validate |
| 10 | Ilupeju | 83 | service area | keep and validate |
| 11 | Mushin | 88 | service area | keep and validate |
| 12 | Surulere | 143 | service area | keep and validate |
| 13 | Yaba | 112 | service area | keep and validate |
| 14 | Oshodi/Isolo | 96 | service area | keep and validate |
| 15 | Shomolu/Bariga | 72 | service area | keep and validate |
| 16 | Ebute Metta | 71 | service area | keep and validate |
| 17 | Apapa | 95 | service area | keep and validate |
| 18 | Lagos Island | 119 | service area | keep and validate |
| 19 | Ikoyi | 119 | service area | keep and validate |
| 20 | Victoria Island | 131 | service area | keep and validate |
| 21 | Obalende/CMS | 83 | neighbourhood/service area | validate parent boundary |
| 22 | Lekki Phase 1 | 119 | service area | keep and validate |
| 23 | Lekki Phase 2/Ikota | 106 | service area | keep and validate |
| 24 | Ajah | 107 | service area | keep and validate |
| 25 | Chevron/Lekki-Epe Expressway | 106 | corridor/service area | normalize name and boundary |
| 26 | Igbo Efon/Ilasan | 60 | neighbourhood | keep under validated parent |
| 27 | Ibeju-Lekki | 83 | service area | keep and validate |
| 28 | Festac Town | 107 | service area | keep and validate |
| 29 | Amuwo Odofin | 83 | service area/neighbourhood | resolve against Festac |
| 30 | Ojo/Alaba | 94 | service area | keep and validate |
| 31 | Badagry | 94 | service area | keep and validate |
| 32 | Ikorodu | 94 | service area | keep and validate |
| 33 | Magodo | 71 | service area | keep and validate |
| 34 | Ojota/Oregun | 50 | service area | keep and validate |
| 35 | Onikan/Lagos Mainland | 49 | neighbourhood | correct ambiguous naming |
| 36 | Epe | 70 | service area | keep and validate |
| 37 | Akoka | 9 | neighbourhood | parent to Yaba where appropriate |
| 38 | UNILAG | 37 | campus | parent to Yaba/Akoka |
| 39 | YABATECH | 12 | campus | parent to Yaba |
| 40 | Lagos State University (LASU) | 19 | campus | keep, resolve Ojo service area |
| 41 | Covenant University | 14 | campus | exclude from Lagos launch |
| 42 | Babcock University | 12 | campus | exclude from Lagos launch |
| 43 | Pan-Atlantic University | 8 | campus | keep under Ajah/Ibeju corridor |
| 44 | Caleb University | 10 | campus | validate Lagos boundary and parent |
| 45 | Eko Hotel | 8 | landmark | parent to Victoria Island |
| 46 | Murtala Muhammed Airport | 11 | transport hub | parent to Ikeja |
| 47 | Ikeja City Mall | 7 | commercial centre | parent to Allen/Opebi |
| 48 | The Palms Lekki | 7 | commercial centre | parent to Lekki Phase 1 |
| 49 | Balogun Market | 10 | market | parent to Lagos Island |
| 50 | Computer Village Ikeja | 7 | commercial centre | parent to Allen/Opebi |
| 51 | Alaba International Market | 7 | market | parent to Ojo/Alaba |
| 52 | Oshodi Market | 7 | market | parent to Oshodi/Isolo |
| 53 | Mile 12 Market | 6 | market | parent to Kosofe/Ketu |
| 54 | National Theatre | 6 | landmark | validate Surulere/Iganmu parent |
| 55 | Tafawa Balewa Square | 6 | landmark | parent to Lagos Island |
| 56 | Lekki Conservation Centre | 6 | landmark | parent to Lekki Phase 2/Ikota |
| 57 | Landmark Beach | 7 | beach/landmark | parent to Oniru/Lekki Phase 1 |
| 58 | Elegushi Beach | 6 | beach/landmark | parent to Lekki Phase 1 |
| 59 | Nike Art Gallery | 5 | landmark | parent to Lekki Phase 1 |
| 60 | LUTH | 9 | hospital | resolve Idi-Araba/Surulere parent |
| 61 | LASUTH | 7 | hospital | parent to Ikeja |
| 62 | Third Mainland Bridge | 6 | bridge/corridor | searchable, never status parent |
| 63 | Lagos-Ibadan Expressway | 10 | corridor | restrict to Lagos segment |

## 7. Broad Lagos DISCO coverage

The source's nationwide configuration defines 37 broad Lagos areas:

### Ikeja Electric, Lagos North

1. Ikeja GRA
2. Ikeja (Allen/Opebi)
3. Maryland/Anthony
4. Ogba
5. Agege
6. Alimosho/Ipaja
7. Ojodu/Omole
8. Kosofe/Ketu
9. Gbagada
10. Ilupeju
11. Mushin
12. Oshodi/Isolo
13. Shomolu/Bariga
14. Ikorodu
15. Magodo
16. Ojota/Oregun
17. Computer Village Ikeja
18. Murtala Muhammed Airport

### Eko Electric, Lagos South

1. Lagos Island
2. Ikoyi
3. Victoria Island
4. Obalende/CMS
5. Ebute Metta
6. Apapa
7. Surulere
8. Yaba
9. Lekki Phase 1
10. Lekki Phase 2/Ikota
11. Ajah
12. Chevron/Lekki-Epe Expressway
13. Igbo Efon/Ilasan
14. Ibeju-Lekki
15. Festac Town
16. Amuwo Odofin
17. Ojo/Alaba
18. Badagry
19. Epe

These are candidate service areas, not verified feeder boundaries. Store their
source as `nepawatch_reference`, confidence as `unverified`, and require admin
review or an authoritative source before calling them official.

## 8. Required initial parent-child relationships

Seed at minimum the following relationships after validation:

| Child | Parent |
|---|---|
| Allen Avenue | Ikeja (Allen/Opebi) |
| Opebi | Ikeja (Allen/Opebi) |
| Toyin Street Ikeja | Ikeja (Allen/Opebi) |
| Computer Village Ikeja | Ikeja (Allen/Opebi) |
| Ikeja City Mall | Ikeja (Allen/Opebi) |
| Agidingbi | Ikeja (Allen/Opebi) |
| Alausa/Secretariat | Ikeja (Allen/Opebi) |
| LASUTH | Ikeja GRA |
| Murtala Muhammed Airport | Ikeja GRA |
| Magodo Phase 1 | Magodo |
| Magodo Phase 2 | Magodo |
| Ojodu Berger | Ojodu/Omole |
| Omole Phase 1 | Ojodu/Omole |
| Omole Phase 2 | Ojodu/Omole |
| Ketu | Kosofe/Ketu |
| Alapere | Kosofe/Ketu |
| Ogudu | Kosofe/Ketu |
| Ogudu GRA | Kosofe/Ketu |
| Mile 12 Market | Kosofe/Ketu |
| Anthony Village | Maryland/Anthony |
| Palmgrove | Maryland/Anthony |
| Onipanu | Maryland/Anthony |
| Fadeyi | Maryland/Anthony |
| UNILAG | Yaba |
| YABATECH | Yaba |
| Akoka | Yaba |
| FCE Akoka | Yaba |
| Iwaya | Yaba |
| Makoko | Yaba |
| Oyingbo | Yaba |
| The Palms Lekki | Lekki Phase 1 |
| Landmark Beach | Lekki Phase 1 |
| Elegushi Beach | Lekki Phase 1 |
| Nike Art Gallery | Lekki Phase 1 |
| Oniru Estate | Lekki Phase 1 |
| Osapa London | Lekki Phase 2/Ikota |
| Agungi | Lekki Phase 2/Ikota |
| Jakande Estate Lekki | Lekki Phase 2/Ikota |
| Lekki Conservation Centre | Lekki Phase 2/Ikota |
| VGC | Chevron/Lekki-Epe Expressway |
| Abraham Adesanya | Ajah |
| Sangotedo | Ajah |
| Awoyaya | Ajah |
| Bogije | Ajah |
| Abijo | Ajah |
| Pan-Atlantic University | Ajah |
| Adeola Odeku | Victoria Island |
| Ahmadu Bello Way | Victoria Island |
| Ozumba Mbadiwe | Victoria Island |
| Eko Hotel | Victoria Island |
| Eko Atlantic City | Victoria Island |
| Bar Beach | Victoria Island |
| 1004 Estate | Victoria Island |
| Banana Island | Ikoyi |
| Parkview Estate Ikoyi | Ikoyi |
| Bourdillon Road Ikoyi | Ikoyi |
| Osborne Estate | Ikoyi |
| Dolphin Estate | Ikoyi |
| Balogun Market | Lagos Island |
| Marina | Lagos Island |
| Broad Street | Lagos Island |
| CMS Lagos | Lagos Island |
| Tafawa Balewa Square | Lagos Island |
| Idumota | Lagos Island |
| Adeniji Adele | Lagos Island |
| Obalende/CMS | Lagos Island |
| Apapa GRA | Apapa |
| Apapa Port | Apapa |
| Tin Can Island | Apapa |
| Tin Can Island Port | Apapa |
| Kirikiri | Apapa |
| Oshodi Market | Oshodi/Isolo |
| Isolo | Oshodi/Isolo |
| Ejigbo | Oshodi/Isolo |
| Mafoluku | Oshodi/Isolo |
| Ajao Estate | Oshodi/Isolo |
| Ojuelegba | Surulere |
| Iponri | Surulere |
| Eko Hospital Surulere | Surulere |
| Mile 2 | Festac Town |
| Alakija | Festac Town |
| Satellite Town | Festac Town |
| Trade Fair Complex | Festac Town |
| Agboju | Festac Town |
| Alaba International Market | Ojo/Alaba |
| Ajangbadi | Ojo/Alaba |
| Iba | Ojo/Alaba |
| Iyana Ipaja | Alimosho/Ipaja |
| Idimu | Alimosho/Ipaja |
| Egbe | Alimosho/Ipaja |
| Akowonjo | Alimosho/Ipaja |
| Shasha | Alimosho/Ipaja |
| Ayobo | Alimosho/Ipaja |
| Abule Egba | Alimosho/Ipaja |
| Dopemu | Alimosho/Ipaja |
| Pen Cinema Agege | Agege |
| Ikorodu GRA | Ikorodu |
| Agric Ikorodu | Ikorodu |
| Imota | Ikorodu |
| Igbogbo | Ikorodu |
| Bayeku | Ikorodu |
| Ikorodu Bus Terminal | Ikorodu |
| Eleko | Ibeju-Lekki |
| Gbagada General Hospital | Gbagada |
| Reddington Hospital VI | Victoria Island |

Do not use a bridge as the parent of an outage area. A bridge can be a search
target that resolves to adjacent areas, but electricity status must be attached
to an actual service location.

## 9. Location staging and cleanup pipeline

Create a deterministic import pipeline:

```text
raw reference
  → parse
  → normalize
  → exact deduplicate
  → fuzzy candidate grouping
  → classify location type
  → validate Lagos boundary
  → validate/assign parent
  → geocode
  → score confidence
  → quarantine questionable records
  → admin review
  → activate canonical location
```

### 9.1 Normalization

Normalize:

- Unicode dashes and apostrophes
- whitespace
- case
- abbreviations such as `St`, `Street`, `Rd`, `Road`
- `B/Stop`, `Bus Stop`
- `VI`, `Victoria Island`
- `GRA`
- duplicate suffixes
- parenthetical naming
- slash-separated combined areas

Keep:

- canonical display name
- normalized name
- aliases
- original raw value

### 9.2 Duplicate detection

Use:

- exact normalized name
- normalized name plus parent
- coordinate distance
- fuzzy similarity
- address-component comparison

Records within approximately 180–200 metres are candidates for merging, not
automatically identical. Admin review is required where names conflict.

### 9.3 Fabricated-record quarantine

Quarantine suspicious generated combinations such as:

- arbitrary street + `Bank`
- arbitrary street + `Church`
- arbitrary street + `Mosque`
- arbitrary street + `School`
- arbitrary street + `Hospital`
- arbitrary street + `Police Station`
- arbitrary street + `Market`
- arbitrary street + `Bus Stop`

Such a location can become active only if confirmed by geocoding, an
authoritative directory or admin review.

### 9.4 Boundary validation

Reject or quarantine:

- locations outside Lagos State
- nationwide locations accidentally placed under Lagos groups
- Covenant University for the Lagos launch
- Babcock University for the Lagos launch
- portions of Lagos-Ibadan Expressway outside Lagos
- ambiguous records without a resolvable Lagos parent

---

# Part II: Database and Backend

## 10. Required database entities

Extend or normalize the SQLite schema. Use proper foreign keys and indexes.

### 10.1 `discos`

- `id`
- `slug`
- `name`
- `short_name`
- `active`
- `created_at`
- `updated_at`

### 10.2 `service_areas`

- `id`
- `slug`
- `name`
- `lga`
- `disco_id`
- `service_band`
- `feeder_name`
- `latitude`
- `longitude`
- `boundary_status`
- `source_type`
- `source_url`
- `source_confidence`
- `active`
- timestamps

### 10.3 `locations`

- `id`
- `slug`
- `canonical_name`
- `normalized_name`
- `location_type`
- `service_area_id`
- `parent_location_id`
- `latitude`
- `longitude`
- `geocode_precision`
- `verification_state`
- `source_type`
- `source_url`
- `source_record_id`
- `created_by_user_id`
- `active`
- timestamps

### 10.4 `location_aliases`

- `id`
- `location_id`
- `alias`
- `normalized_alias`
- `source_type`
- unique normalized alias scoped appropriately

### 10.5 `location_import_records`

- immutable raw payload
- source file/source URL
- source group
- raw name
- raw parent
- parsed location type
- coordinates
- normalization result
- validation errors
- review state
- canonical location link
- timestamps

### 10.6 `location_review_events`

- actor
- raw record
- action
- old state
- new state
- notes
- timestamp

### 10.7 Existing evidence entities

Preserve and improve:

- users
- sessions
- saved places
- reports
- report votes
- incidents
- point events
- pipeline runs
- raw source records
- feeder performance
- model versions
- audit events

### 10.8 New community entities

Add:

- badge definitions
- user badges
- streak state
- referral records
- notification preferences
- push subscriptions
- notification delivery log
- area leaderboard snapshots, if necessary
- weekly champion records

## 11. Required indexes

At minimum:

- normalized location name
- normalized alias
- service area
- parent location
- latitude/longitude lookup support
- report area and observed time
- incident area and start/end time
- votes by report/user
- sessions by token hash and expiry
- saved places by user
- pipeline run and state
- audit event time
- badge ownership by user

## 12. API contract

Use versioned API routes or preserve existing routes with a documented stable
contract. Do not break the SPA silently.

### 12.1 Public location APIs

- `GET /api/areas`
- `GET /api/locations/search?q=...`
- `GET /api/locations/{slug}`
- `GET /api/locations/nearby?lat=...&lng=...`
- `GET /api/status/{area_slug}`
- `GET /api/status/{area_slug}/history`
- `GET /api/incidents`
- `GET /api/reports/public`
- `GET /api/discos/coverage`

Search results must include:

- canonical name
- matched alias
- type
- service area
- parent
- LGA
- DISCO
- band if verified
- feeder if verified
- coordinates where appropriate
- current evidence status
- confidence
- freshness

### 12.2 Authenticated APIs

- signup
- login
- logout
- current user
- report submission
- report confirmation
- report dispute
- custom-location proposal
- saved-place create
- saved-place edit
- saved-place delete
- saved-place notification toggle
- dashboard
- contribution history
- badges
- leaderboard
- referrals
- notification settings
- push-subscription create/delete

### 12.3 Admin APIs

- location import
- location review queue
- approve/reject/merge location
- edit parent/service area
- trusted-source import
- report review
- incident reconciliation
- pipeline overview
- audit trail
- badge management
- announcement management
- maintenance-state management
- model-version management
- training snapshot export

### 12.4 Error behavior

- API routes must return JSON errors.
- SPA browser routes must return the SPA fallback.
- Unknown `/api/...` paths must not return `index.html`.
- Validation errors must be useful and stable.
- Authentication failures must not reveal whether an unrelated email exists.
- Rate-limit and duplicate-report errors must be explicit.

## 13. SQLite concurrency boundary

SQLite operations remain synchronous.

- Keep database-backed FastAPI handlers as regular `def` functions so FastAPI
  runs them in its thread pool.
- Use async handlers for genuinely asynchronous network operations.
- Do not wrap SQLite calls in fake async functions.
- Keep WAL mode, busy timeout and short transactions.
- Never hold a transaction while waiting for an external HTTP request.

---

# Part III: Dynamic Public Monitoring

## 14. Remove frontend operational constants

Delete the current frontend authority represented by hard-coded:

- area statuses
- confidence percentages
- report totals
- evidence freshness
- supply history
- feeder status
- incident cards
- member counts
- area counts

Static fixtures may remain only in test files or Storybook-style development
fixtures.

## 15. Search experience

The search/dropdown must:

- load from the backend
- support keyboard navigation
- support areas, streets, estates and landmarks
- show local results immediately
- debounce network search
- highlight the matched name/alias
- display type and parent area
- display DISCO and band only when verified
- display status summary
- handle empty, loading and error states
- work on mobile
- preserve selected area in the URL
- restore selection after refresh

Optional external map search must:

- use a backend proxy or compliant client integration
- search only Nigeria and preferably Lagos bounds
- respect Nominatim usage requirements
- never expose a false “saved” state
- allow a result to be proposed as a custom location

## 16. Status card

The public status card must show:

- canonical monitoring area
- selected exact location
- DISCO
- verified feeder, if known
- current state:
  - power available
  - outage
  - unstable
  - uncertain
- confidence score
- number of independent reports
- number of confirmations/disputes
- latest evidence time
- evidence source mix
- status validity window
- clear uncertain state when evidence is insufficient

## 17. Evidence ledger

The evidence modal/page must list real evidence:

- recent resident observations
- confirmations
- disputes
- official notice
- verified incident
- feeder-performance source
- review state
- timestamps

It must explicitly state that ML prediction was not used when prediction is
disabled.

## 18. Public report feed

Implement:

- latest reports
- today/all filter
- outage/restoration/unstable filter
- area and parent-area filter
- pagination or cursor loading
- confirmation count
- dispute count
- flagged/quarantined presentation
- source label
- report age
- active outage duration
- accessible status labels
- live refresh

Do not use fabricated seed reports in production.

## 19. Live updates

Because SQLite has no Supabase realtime channel, implement a clean replacement:

Preferred initial approach:

- lightweight polling with ETag or `updated_since`
- visibility-aware pause/resume
- backoff on errors
- immediate refresh after local actions

Optional later approach:

- Server-Sent Events
- WebSocket only if justified

Do not build a complex WebSocket system merely to imitate Supabase.

---

# Part IV: Maps, GPS and Custom Locations

## 20. Map requirements

Use Leaflet/OpenStreetMap or an equivalent open solution.

Support:

- user marker
- selected-location marker
- nearby status markers
- colour-coded status
- status popup
- distance
- map recenter
- mobile gestures
- accessible non-map fallback

## 21. Geolocation

Implement:

1. High-accuracy attempt
2. Lower-accuracy fallback
3. Permission-denied state
4. Timeout state
5. Accuracy indicator
6. Nearest canonical location
7. Nearest service area
8. Nearby areas
9. Optional reverse geocoding
10. Explicit save action

Do not start continuous background location tracking without an explicit user
choice. Prefer privacy and battery safety over NepaWatch's always-on behavior.

## 22. Custom location proposal

An authenticated member may propose a missing place.

Required fields:

- location name
- expected area
- type
- optional map pin
- optional note

The proposal must:

- be geocoded
- be checked for nearby duplicates
- enter a pending review state
- not immediately become authoritative
- be visible to admins
- generate an audit record

---

# Part V: Authentication and Member Experience

## 23. Authentication flows

Required:

- signup
- login
- logout
- session restoration
- password show/hide
- duplicate-account handling
- invalid-credential handling
- normal password requirement
- no email-verification gate

Password reset:

- implement only with a real delivery mechanism, or
- clearly provide admin-assisted reset for the capstone

Google login is optional and must not delay the core release.

## 24. Member dashboard

Must include real:

- points
- trust score
- rank
- current streak
- longest streak
- report count
- verified-report count
- confirmation count
- saved places
- badges
- recent activity
- notification settings
- referral information

## 25. Saved places

Support:

- Home
- Work
- School
- Custom
- custom label
- exact street/landmark
- parent service area
- status
- notifications on/off
- edit
- delete
- one-click monitor

---

# Part VI: Reporting, Verification and Trust

## 26. Report types

Support:

- outage
- restoration
- unstable supply

Optional context:

- whole street affected
- low voltage
- transformer issue
- sparks/fire
- planned maintenance
- note, maximum 280 characters

## 27. Duplicate and abuse control

Implement:

- recent duplicate key
- per-user rate limit
- per-location rate limit
- self-confirmation prevention
- one vote per user/report
- account status checks
- trust weighting
- suspicious activity logging

## 28. Confirmation flow

Nearby or relevant saved-place users can respond:

- confirm
- dispute
- not sure

`Not sure` must not write a vote.

Eligibility uses:

- exact service area
- direct parent/child relationship
- relevant saved place
- optional distance threshold

Never use broad sibling matching for high-confidence verification.

## 29. Incident reconciliation

Admin verification must:

- group corroborating observations
- preserve all evidence links
- create one canonical incident
- record confidence
- record verification method
- record actor and timestamp
- award points
- update trust scores
- remain reversible through an audit event, not destructive deletion

---

# Part VII: Gamification and Community

## 30. Badge catalogue

Implement these 18 badges as database-backed definitions:

| Key | Name | Requirement |
|---|---|---|
| `first_report` | First Report | Submit first report |
| `first_restore` | Light Bringer | Submit first restoration |
| `night_owl` | Night Owl | Report between midnight and 5 AM WAT |
| `early_bird` | Early Bird | Report before 7 AM WAT |
| `streak_3` | 3-Day Streak | Report 3 consecutive days |
| `reports_10` | 10 Reports | Submit 10 reports |
| `streak_7` | Area Guardian | Report 7 consecutive days |
| `reports_25` | Power Watcher | Submit 25 reports |
| `streak_14` | Power Tracker | Report 14 consecutive days |
| `reports_50` | Outage Hero | Submit 50 reports |
| `streak_30` | NEPA Veteran | Report 30 consecutive days |
| `reports_100` | Power General | Submit 100 reports |
| `streak_60` | Consistent | Report 60 consecutive days |
| `reports_200` | Data Champion | Submit 200 reports |
| `streak_100` | Grid Watcher | Report 100 consecutive days |
| `weekly_champion` | Weekly Champion | Highest valid weekly contribution |
| `reports_500` | Legend | Submit 500 reports |
| `referral_3` | Community Builder | Three successful referrals |

Every badge needs:

- icon
- colour
- description
- requirement
- progress
- earned timestamp
- share text
- accessible locked/earned state

## 31. Streak rules

Use Africa/Lagos time.

- One qualifying contribution per day advances the streak.
- Multiple reports in one day do not add multiple streak days.
- Missing a day resets current streak.
- Longest streak is retained.
- Quarantined/rejected abuse must not count.
- Correct reversal after admin review must be supported.
- Streak updates must be idempotent.

## 32. Points and trust

Define an explicit point table. Example:

- accepted observation: small points
- confirmed observation: points
- verified observation: bonus
- useful confirmation: points
- rejected/spam activity: no points or penalty
- trusted-source/admin actions: no public gamification unless intended

Trust score must be explainable and bounded. Do not let raw report volume alone
create high trust.

## 33. Leaderboard

Support:

- weekly period
- monthly period
- all-time period
- Lagos-wide ranking
- area ranking
- valid contributions only
- best badge
- streak
- privacy-safe display name
- tie-breaking rule

## 34. Area rivalry and weekly champion

Implement only after rankings are reliable.

- deterministic weekly boundaries
- real area statistics
- no random competitor
- no fabricated power-hour comparison
- store champion record
- award badge idempotently

## 35. Referrals

Support:

- unique referral code
- signup attribution
- fraud-resistant successful referral definition
- referral count
- Community Builder badge after three valid referrals

---

# Part VIII: Notifications and PWA

## 36. Notification preferences

Allow global and per-place preferences:

- outage
- restoration
- unstable supply
- weekly summary
- streak reminder
- community updates

## 37. Push notifications

Implement:

- service worker
- subscription endpoint
- VAPID keys through environment variables
- enable/disable
- permission states
- iOS installed-PWA guidance
- subscription refresh
- safe removal
- delivery log
- deduplication/cooldown

Never copy NepaWatch's VAPID key.

## 38. Email notifications

Email is optional for the first production milestone but must be truthful.

If implemented:

- environment-driven provider
- outage/restoration templates
- saved-place matching
- delivery logs
- retry policy
- opt-out
- rate limits

No verification email is required for account use.

## 39. Engagement notifications

Only implement after core outage alerts are reliable:

- streak-at-risk
- weekly summary
- inactivity reminder
- weekly champion

Do not send manipulative or excessive notifications.

## 40. PWA

Required:

- DownNepa manifest
- correct icons
- service worker
- offline shell
- explicit offline-data state
- install prompt
- iOS instructions
- update detection
- cache invalidation
- standalone detection

Never display stale outage status as current while offline. Show the last-updated
time and an offline warning.

---

# Part IX: Trusted Data Pipeline

## 41. Source classes

Support:

- NERC
- Ikeja Electric
- Eko DisCo
- official government notices
- manually reviewed structured imports

Potential sources must be configurable, not hard-coded as automatically trusted.

## 42. Pipeline stages

```text
acquire
  → immutable raw snapshot
  → parse
  → schema validation
  → source-domain validation
  → semantic validation
  → deduplicate
  → quarantine
  → admin review
  → canonical record
```

## 43. Provenance

Every imported canonical record must retain:

- source
- source URL
- retrieval time
- source hash
- parser version
- raw record link
- validation results
- review actor
- review time

## 44. Pipeline behavior

- A changed source creates a new raw snapshot.
- Duplicate canonical rows are not recreated.
- Invalid rows are never silently discarded.
- Partial imports report exact counts.
- Reruns are idempotent.
- Failed imports do not corrupt canonical data.
- External HTTP calls are asynchronous.
- SQLite writes remain synchronous and transactionally short.

---

# Part X: Prediction and ML Boundary

## 45. Current release behavior

Prediction remains disabled until:

- enough verified incident data exists
- a training snapshot is approved
- evaluation metrics meet thresholds
- model artifact integrity is verified
- an admin activates a model version

The UI must show an honest unavailable state.

## 46. NepaWatch heuristic inventory to preserve as research

Record, but do not automatically deploy:

- Band A-E outage baselines
- expected supply hours
- 11 DISCO-specific band baselines
- 11 DISCO-specific supply-hour tables
- 11 DISCO rotation durations
- 11 DISCO maximum outage-duration tables
- southern 24-hour demand curve
- northern 24-hour demand curve
- central 24-hour demand curve
- seven weekday factors
- feeder rotation adjustment
- weather multiplier
- report time decay
- confirmation boost
- dispute penalty
- per-DISCO training cap
- live human ground-truth override
- duration estimate
- next-event estimate

These are hypotheses and feature-engineering candidates, not verified facts.

## 47. Model plugin contract

The model loader must support:

- model name
- version
- task
- artifact URI/path
- artifact hash
- feature schema version
- trained-at timestamp
- evaluation metrics
- status:
  - candidate
  - shadow
  - active
  - retired
  - rejected
- load failure
- prediction timeout
- fallback to unavailable

No model-specific logic should leak into report or incident services.

## 48. Training snapshot

Snapshot must include only:

- verified incidents
- canonical locations
- approved feeder metadata
- trusted weather history
- explicit feature timestamps

Exclude:

- pending reports
- rejected reports
- quarantined reports
- demo seed data
- AI-generated reports
- prior predictions
- unreviewed custom locations

---

# Part XI: Admin Area

## 49. Admin sections

Required:

1. Evidence review
2. Incident reconciliation
3. Location review
4. Location merge
5. Trusted-source pipeline
6. Quarantine
7. DISCO/service-area management
8. Badge definitions
9. User moderation
10. Audit trail
11. Model versions
12. Training snapshots
13. Announcements
14. Maintenance state

## 50. Admin safety

- Require admin role on every server endpoint.
- Never rely only on hidden frontend navigation.
- Audit every material action.
- Prefer reversible state transitions.
- Never hard-delete evidence through normal admin workflows.
- Require confirmation for merges and destructive operations.

---

# Part XII: UX and Product Details

## 51. Theme

Dark and light themes must:

- persist
- respect initial system preference
- work on every page and modal
- maintain contrast
- apply to maps and charts where possible

## 52. Public landing experience

Implement real:

- live activity ticker
- current report count
- mapped-location count
- live area grid
- DISCO coverage
- outage/restoration summaries
- authentication entry
- announcement banner

Do not show fake membership or report counts.

## 53. Navigation

Public:

- Monitor
- Live reports
- Incidents
- Coverage
- Community
- Sign up/login

Member:

- Dashboard
- Saved places
- Contributions
- Achievements
- Notifications
- Profile

Admin:

- Admin workspace
- Return to member dashboard
- Return to public monitor

## 54. Onboarding

After signup:

1. Explain public monitoring versus contribution.
2. Ask for optional location.
3. Offer search or map selection.
4. Offer saved-place setup.
5. Explain confirmations and trust.
6. Offer notifications without blocking product use.

Onboarding must be dismissible and must not repeatedly reappear.

## 55. Accessibility

- keyboard-operable search
- focus trapping in modals
- visible focus
- semantic buttons
- status not communicated by colour alone
- screen-reader labels
- reduced-motion support
- form errors associated with fields
- sufficient contrast

---

# Part XIII: Implementation Phases

## 56. Phase 0: Baseline and safety

- Create a feature branch.
- Record current API contracts.
- Run current tests.
- Add missing integration-test scaffolding.
- Identify all frontend mock operational data.
- Do not change production deployment automatically.

Exit criteria:

- baseline recorded
- current failures understood
- implementation plan mapped to commits

## 57. Phase 1: Location schema and staging

- Create normalized location schema.
- Build import parser for NepaWatch reference data.
- Stage all source records.
- Generate cleanup report.
- Exclude non-Lagos records.
- Add admin review queue.
- Seed approved service areas and hierarchy.

Exit criteria:

- no blind raw import
- all 63 source groups accounted for
- every raw item is active, merged, rejected or quarantined
- provenance retained

## 58. Phase 2: Backend-driven public monitor

- Replace frontend location constants.
- Implement search API.
- Load real status and incidents.
- Load evidence ledger.
- Load history.
- Load coverage counts.
- Add honest empty/uncertain states.

Exit criteria:

- frontend has no operational mock data
- admin-verified incident updates public UI
- search covers approved locations

## 59. Phase 3: Reports and verification

- Exact-location report submission
- Confirm/dispute/not-sure flow
- Abuse controls
- Parent-area logic
- Live polling
- Dynamic feed
- Incident reconciliation

Exit criteria:

- complete resident-to-verified-incident flow passes E2E

## 60. Phase 4: Maps and saved places

- Coordinates
- Nearby search
- GPS
- Reverse geocoding
- Map picker
- Custom location proposals
- Saved place types/edit/delete/preferences

Exit criteria:

- GPS and manual search both resolve correctly
- custom location never bypasses review

## 61. Phase 5: Gamification and community

- Points/trust
- 18 badges
- streaks
- leaderboards
- weekly champion
- referrals
- area rivalry

Exit criteria:

- award logic is idempotent
- rejected activity cannot retain unearned rewards

## 62. Phase 6: PWA and notifications

- Service worker
- manifest/icons
- push subscription
- preferences
- outage/restoration alert dispatch
- install/update experience

Exit criteria:

- real push test succeeds
- offline UI never presents stale data as current

## 63. Phase 7: Pipeline hardening and model readiness

- Complete trusted-source adapters
- parser versioning
- quarantine workflow
- training snapshot export
- model registry hardening
- keep prediction disabled

Exit criteria:

- only verified incidents appear in snapshot

## 64. Phase 8: Production verification

- full backend tests
- full frontend tests
- E2E browser suite
- responsive inspection
- accessibility check
- security check
- cold-start test
- Render-style production boot
- SQLite persistence test
- deployment documentation

Exit criteria:

- all quality gates pass
- no critical/high defects
- no dead controls
- no false success messages

---

# Part XIV: Required Tests

## 65. Backend tests

Cover:

- signup without verification
- login/logout/session expiry
- member/admin authorization
- location normalization
- location hierarchy
- search aliases
- nearby calculation
- boundary validation
- custom location quarantine
- report creation
- duplicate report rejection
- self-confirmation rejection
- confirmation/dispute idempotency
- incident reconciliation
- points and trust
- all 18 badges
- streak boundaries in WAT
- saved places
- pipeline validation
- provenance
- snapshot exclusion rules
- API 404 JSON behavior
- SPA fallback behavior

## 66. Frontend tests

Cover:

- area search
- keyboard navigation
- status states
- evidence modal
- report modal
- auth modal
- dashboard
- saved places
- badge progress
- leaderboard
- map loading/error
- notification preference states
- light/dark themes
- empty/loading/error/offline states

## 67. End-to-end journeys

### Anonymous monitor

1. Open site.
2. Search street.
3. Select result.
4. View status and evidence.
5. View public feed.
6. Attempt report and receive auth prompt.

### Member contribution

1. Sign up with ordinary password.
2. Log in immediately.
3. Set location.
4. Submit outage.
5. See report in history/feed.
6. Earn correct points/badge.

### Independent confirmation

1. Second user logs in.
2. Opens relevant area.
3. Confirms first report.
4. Confirmation count changes.
5. Admin reconciles.
6. Canonical incident appears publicly.

### Dispute

1. User disputes incorrect report.
2. Duplicate dispute is blocked.
3. Report receives review signal.
4. Admin can quarantine/reject.

### Saved place

1. Add Home from map result.
2. Edit label.
3. Toggle notifications.
4. Monitor it.
5. Delete it.

### Admin pipeline

1. Import valid and invalid rows.
2. Valid row becomes canonical.
3. Invalid row is quarantined.
4. Duplicate is counted.
5. Audit log records action.

### Training snapshot

1. Create mixed reports and incidents.
2. Export snapshot.
3. Verify only canonical verified incidents are included.

---

# Part XV: Quality Gates and Commands

## 68. Required commands

```bash
uv sync
uv run ruff format --check backend
uv run ruff check backend
uv run pytest
npm --prefix frontend ci
npm --prefix frontend run build
```

Add frontend test and E2E commands when the relevant test runner is introduced.

## 69. Production boot

Verify:

```bash
uv run --frozen --no-dev uvicorn backend.app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}"
```

Then test:

- `/api/health`
- `/api/areas`
- a known SPA route
- an unknown SPA route
- an unknown API route
- static assets
- database write/read

---

# Part XVI: Deliverables

## 70. Required repository deliverables

- normalized database schema
- migration/initialization strategy
- location staging importer
- cleanup report
- approved seed dataset
- backend services and APIs
- dynamic React SPA
- admin location-review UI
- map/geolocation UI
- report verification UI
- saved-place UI
- gamification/community UI
- notification/PWA implementation
- trusted-source adapters
- training snapshot exporter
- tests
- deployment instructions
- architecture documentation
- API documentation
- data provenance documentation

## 71. Required implementation report

At completion, produce:

- files changed
- schema changes
- API changes
- source records processed
- active locations
- merged duplicates
- quarantined records
- rejected non-Lagos records
- unverified records remaining
- tests run and results
- known limitations
- deployment configuration
- model status

---

# Part XVII: Prohibited shortcuts

Do not:

- import all 6,224 strings directly into active locations
- leave the ten-area frontend constant as the authority
- claim “live” while showing fixtures
- use random status values
- use random leaderboard values
- call heuristic output “trained ML”
- enable predictions without evaluation
- let predictions become evidence
- send false email-success messages
- hide broken features
- swallow all errors silently
- rely on client-side admin checks
- copy Supabase keys or URLs
- copy NepaWatch VAPID keys
- copy advertising IDs
- add email verification
- require login for public monitoring
- deploy without explicit approval

---

# Part XVIII: Final Codex instruction

Treat this document as the product goal and acceptance contract.

Work phase by phase. Before each phase:

1. Inspect the existing implementation.
2. Identify affected contracts.
3. State the phase plan.
4. Preserve unrelated user changes.

After each phase:

1. Run relevant tests.
2. Inspect the diff.
3. Update documentation.
4. Record remaining gaps.

Do not stop after generating scaffolding. Continue until every applicable
acceptance criterion in this document is either:

- implemented and verified, or
- explicitly blocked by a real external dependency or user decision.

When blocked, report the exact blocker and continue with every independent task
that remains possible.

Do not push, merge or deploy without explicit user approval.

