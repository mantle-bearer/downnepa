from __future__ import annotations

from importlib import import_module

from .contract import OutageRiskModel


def load_model(entrypoint: str) -> OutageRiskModel:
    """Load `package.module:factory` without coupling the API to its ML library."""
    module_name, factory_name = entrypoint.split(":", 1)
    model = getattr(import_module(module_name), factory_name)()
    if not hasattr(model, "predict") or not hasattr(model, "feature_schema"):
        raise TypeError("Model does not implement the DownNepa risk contract")
    return model

