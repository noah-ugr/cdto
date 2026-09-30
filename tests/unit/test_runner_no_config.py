import importlib

import pytest

from benchmarks.metrics.rescore_results import score_prediction
from tests.unit.test_comparison_metrics import base_config, gt_with_edits

RUNNERS = [
    "benchmarks.comparisons.benchmark_compare_complexity",
    "benchmarks.comparisons.benchmark_compare_completeness",
]
FIELDS = ["f1_micro", "f1_keys", "f1_values", "collateral_damage", "omissions", "collateral_rate", "omission_rate"]


@pytest.mark.parametrize("module", RUNNERS)
def test_call_without_config_is_scored_as_json_base(module) -> None:
    runner = importlib.import_module(module)
    example = {"json_base": base_config(), "json_gt": gt_with_edits()}

    scores = runner._score_json_base(example)

    assert scores["f1_micro"] == 0.0
    assert scores["omission_rate"] == 1.0
    assert scores["collateral_rate"] == 0.0
    expected = score_prediction(example["json_base"], example["json_gt"], example["json_base"])
    assert scores == {f: expected[f] for f in FIELDS}


@pytest.mark.parametrize("module", RUNNERS)
def test_legacy_runs_keep_hard_coded_zeros(module) -> None:
    runner = importlib.import_module(module)
    example = {"json_base": base_config(), "json_gt": gt_with_edits()}

    scores = runner._score_json_base(example, legacy_structural_keys=True)

    assert all(scores[f] == 0 for f in FIELDS)
