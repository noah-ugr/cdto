"""Shared benchmark metrics package.

Import from this package in benchmark runners to avoid duplicated metric logic.
"""

from benchmarks.metrics.comparison_metrics import (
    compare_json_exact,
    calculate_excision_micro_f1,
    _zero_token_usage,
    _merge_token_usage
)

__all__ = [
    "compare_json_exact",
    "calculate_excision_micro_f1",
    "_zero_token_usage",
    "_merge_token_usage"
]
