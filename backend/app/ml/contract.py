from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol


@dataclass(frozen=True)
class Prediction:
    probability: float
    model_version: str
    feature_schema: str
    generated_at: str


class OutageRiskModel(Protocol):
    """Stable boundary implemented by every six-hour risk model."""

    name: str
    feature_schema: str

    def predict(self, features: Mapping[str, float | int | str]) -> Prediction:
        ...

