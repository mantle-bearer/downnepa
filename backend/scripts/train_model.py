"""Train a small auditable logistic baseline from a verified snapshot.

The script deliberately uses only Python's standard library. It refuses demo,
small, or single-class datasets and emits an integrity-hashed candidate
artifact; an administrator must separately approve its lifecycle state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import secrets
from datetime import datetime
from pathlib import Path

FEATURES = ["service_band_numeric", "hour", "weekday", "evidence_count"]


def feature_row(row: dict) -> dict:
    observed = datetime.fromisoformat(row["started_at"])
    return {
        **row,
        "service_band_numeric": {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5}.get(
            row.get("service_band"), 3
        ),
        "hour": observed.hour / 23,
        "weekday": observed.weekday() / 6,
        "evidence_count": min(float(row.get("evidence_count", 1)), 10) / 10,
    }


def verified_snapshot_records(snapshot: dict) -> list[dict]:
    """Return integrity-checked, non-demo training records."""
    if snapshot.get("schema_version") != "downnepa-training-v1":
        raise ValueError("Unsupported training snapshot")
    rows = snapshot["records"]
    digest = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
    if not secrets.compare_digest(digest, snapshot.get("sha256", "")):
        raise ValueError("Training snapshot integrity check failed")
    if any(row.get("verification_method") == "demo" for row in rows):
        raise ValueError("Demo records cannot train a model")
    return rows


def sigmoid(value: float) -> float:
    return 1 / (1 + math.exp(-max(-30, min(30, value))))


def train(rows: list[dict], iterations: int = 2000, rate: float = 0.05) -> tuple[dict, float]:
    if len(rows) < 100:
        raise ValueError("At least 100 verified incidents are required")
    labels = [1 if row["state"] == "out" else 0 for row in rows]
    if len(set(labels)) < 2:
        raise ValueError("Training data must contain outage and non-outage examples")
    weights = {feature: 0.0 for feature in FEATURES}
    intercept = 0.0
    for _ in range(iterations):
        gradients = {feature: 0.0 for feature in FEATURES}
        bias = 0.0
        for row, label in zip(rows, labels, strict=True):
            score = intercept + sum(weights[name] * float(row[name]) for name in FEATURES)
            error = sigmoid(score) - label
            bias += error
            for name in FEATURES:
                gradients[name] += error * float(row[name])
        scale = rate / len(rows)
        intercept -= scale * bias
        for name in FEATURES:
            weights[name] -= scale * gradients[name]
    predictions = [
        sigmoid(intercept + sum(weights[name] * float(row[name]) for name in FEATURES))
        for row in rows
    ]
    accuracy = sum(
        (value >= 0.5) == bool(label) for value, label in zip(predictions, labels, strict=True)
    ) / len(rows)
    return {"weights": weights, "intercept": intercept}, accuracy


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    snapshot = json.loads(args.snapshot.read_text())
    rows = verified_snapshot_records(snapshot)
    digest = snapshot["sha256"]
    parameters, accuracy = train([feature_row(row) for row in rows])
    artifact = {
        "model_version": args.version,
        "feature_schema": "downnepa-risk-v1",
        "lifecycle_state": "candidate",
        "features": FEATURES,
        **parameters,
        "metrics": {"training_accuracy": accuracy, "record_count": len(rows)},
        "training_snapshot_sha256": digest,
    }
    canonical = json.dumps(artifact, sort_keys=True, separators=(",", ":")).encode()
    artifact["sha256"] = hashlib.sha256(canonical).hexdigest()
    args.output.write_text(json.dumps(artifact, indent=2) + "\n")


if __name__ == "__main__":
    main()
