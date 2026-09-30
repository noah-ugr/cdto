"""Shared normalization helpers for benchmark metric calculations.

These helpers guarantee deterministic comparisons across approaches by:
- coercing numeric values to float
- recursively normalizing nested dict/list structures
- producing stable JSON-serialized representations
"""

from __future__ import annotations

import json
from typing import Any


def normalize_value(value: Any) -> Any:
    """Normalize benchmark values for robust equality and set comparisons.

    Rules:
    - bool stays bool (to avoid bool -> float coercion)
    - int/float are converted to float
    - list/dict are normalized recursively
    - unknown scalar types are returned as-is
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return [normalize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: normalize_value(item) for key, item in value.items()}
    return value


def canonicalize_unordered_list(values: list[Any]) -> list[str]:
    """Return a deterministic, order-insensitive representation for list values."""
    return sorted(
        json.dumps(normalize_value(value), sort_keys=True, ensure_ascii=False)
        for value in values
    )


def serialize_metric_value(value: Any) -> str:
    """Serialize a normalized value to a deterministic JSON string."""
    return json.dumps(normalize_value(value), sort_keys=True, ensure_ascii=False)
