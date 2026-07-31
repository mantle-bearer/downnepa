"""Dependency-free runtime for approved DownNepa logistic-model artifacts."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Mapping

from .contract import Prediction


class JsonLogisticModel:
    def __init__(self, artifact_path: Path) -> None:
        artifact = json.loads(artifact_path.read_text())
        integrity = artifact.pop("sha256")
        canonical = json.dumps(artifact, sort_keys=True, separators=(",", ":")).encode()
        if hashlib.sha256(canonical).hexdigest() != integrity:
            raise ValueError("Model artifact integrity check failed")
        if artifact["lifecycle_state"] not in {"active", "shadow"}:
            raise ValueError("Only active or shadow models may be loaded")
        self.name = artifact["model_version"]
        self.feature_schema = artifact["feature_schema"]
        self.features = artifact["features"]
        self.weights = artifact["weights"]
        self.intercept = artifact["intercept"]

    async def predict(self, features: Mapping[str, float | int | str]) -> Prediction:
        def calculate() -> float:
            score = self.intercept
            for name in self.features:
                score += self.weights[name] * float(features[name])
            return 1 / (1 + math.exp(-max(-30, min(30, score))))

        probability = await asyncio.to_thread(calculate)
        return Prediction(
            probability=probability,
            model_version=self.name,
            feature_schema=self.feature_schema,
            generated_at=datetime.now(UTC).isoformat(),
        )
