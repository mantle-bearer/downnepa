# Data provenance and training boundary

The 63 NEPAWatch reference groups and their child street/landmark names are
stored as explicitly unverified reference data. They improve discovery but do
not claim official feeder boundaries. Non-Lagos entries found in the source
material remain preserved and inactive.

Trusted records follow this path:

1. Acquire bytes only from an allowlisted NERC or distribution-company host.
2. Hash and record the source URL, parser version, run time, and raw count.
3. Validate schema, ranges, reporting period, derivation, and source domain.
4. Keep invalid records quarantined; never silently discard them.
5. Reconcile clean records into canonical incidents through attributable admin
   review.
6. Export only verified, non-demo incidents in the versioned training snapshot.

Pending reports, rejected reports, quarantined source rows, demo incidents, and
all model predictions are excluded from training. This prevents a model from
learning from its own guesses.
