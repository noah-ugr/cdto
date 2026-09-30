import copy

import pytest

from benchmarks.metrics.comparison_metrics import (
    _flatten_to_dict,
    calculate_excision_micro_f1,
    compare_json_exact,
)
from input_agent.src.PetriNetConfig import PetriConfigEngine


def activity(team: str, duration: int) -> dict:
    return {
        "tasks": {"T001": {"Duration": duration, "Requires_Shutdown": False, "Cost_per_hour": 100}},
        "T_period": 100,
        "T_wait": 5,
        "Start_disp": 0,
        "Team": team,
        "Team members": 2,
        "Shift_duration": 8,
    }


def base_config() -> dict:
    return {
        "runId": 1,
        "Teams": 3,
        "Simulation_period": 1000,
        "A001": activity("T1", 10),
        "A002": activity("T2", 20),
    }


def score(json_base: dict, json_gt: dict, json_pred: dict, legacy: bool = False) -> dict:
    """Score a prediction exactly as the benchmark runners do."""
    delta_gt = PetriConfigEngine(json_base).compute_delta(json_gt)
    delta_pred = PetriConfigEngine(json_base).compute_delta(json_pred)
    excision = calculate_excision_micro_f1(delta_gt, delta_pred, legacy_structural_keys=legacy)
    gt_keys = excision["gt_key_count"]
    pred_keys = excision["pred_key_count"]
    return {
        "em": float(compare_json_exact(json_gt, json_pred)),
        "f1": excision["f1_micro"],
        "omission_rate": excision["omissions"] / gt_keys if gt_keys else 0.0,
        "collateral_rate": excision["collateral_damage"] / pred_keys if pred_keys else 0.0,
    }


def gt_with_edits() -> dict:
    gt = base_config()
    gt["A001"]["T_wait"] = 9
    gt["A002"]["Team members"] = 4
    return gt


def gt_with_activity_changes() -> dict:
    gt = base_config()
    gt["A003"] = activity("T3", 30)
    del gt["A002"]
    return gt


@pytest.mark.parametrize("make_gt", [gt_with_edits, gt_with_activity_changes])
def test_prediction_identical_to_base_scores_zero(make_gt) -> None:
    base = base_config()
    result = score(base, make_gt(), copy.deepcopy(base))

    assert result == {"em": 0.0, "f1": 0.0, "omission_rate": 1.0, "collateral_rate": 0.0}


@pytest.mark.parametrize("make_gt", [gt_with_edits, gt_with_activity_changes])
def test_prediction_identical_to_gt_scores_perfect(make_gt) -> None:
    gt = make_gt()
    result = score(base_config(), gt, copy.deepcopy(gt))

    assert result == {"em": 1.0, "f1": 1.0, "omission_rate": 0.0, "collateral_rate": 0.0}


def test_empty_lists_produce_no_keys() -> None:
    delta = PetriConfigEngine(base_config()).compute_delta(gt_with_edits())

    assert "new_activities[]" not in _flatten_to_dict(delta)
    assert "deleted_activities[]" not in _flatten_to_dict(delta)
    assert _flatten_to_dict(delta, legacy_structural_keys=True)["new_activities[]"] == []


def replace_activities(add: str, delete: str) -> dict:
    pred = base_config()
    pred[add] = activity("T3", 30)
    del pred[delete]
    return pred


@pytest.mark.parametrize(
    "make_pred",
    [
        gt_with_activity_changes,                     # correct
        lambda: replace_activities("A004", "A001"),   # wrong add, wrong delete
        lambda: replace_activities("A003", "A001"),   # right add, wrong delete
    ],
)
def test_activity_changes_score_as_before(make_pred) -> None:
    base = base_config()
    gt = gt_with_activity_changes()
    pred = make_pred()

    assert score(base, gt, pred) == score(base, gt, pred, legacy=True)


def test_missed_activity_deletion_now_counts_as_omission() -> None:
    base = base_config()
    gt = gt_with_activity_changes()
    pred = {**base_config(), "A003": activity("T3", 30)}  # adds A003, keeps A002

    # Legacy matched the prediction's empty deleted_activities list as a key.
    assert score(base, gt, pred, legacy=True)["omission_rate"] == 0.0
    assert score(base, gt, pred)["omission_rate"] == 0.5


def test_legacy_flag_reproduces_structural_credit() -> None:
    base = base_config()
    result = score(base, gt_with_edits(), copy.deepcopy(base), legacy=True)

    # Two SET edits flatten to 6 keys; the two empty activity lists add 2 matches.
    assert result["f1"] == pytest.approx(4 / (4 + 6), abs=1e-6)
    assert result["omission_rate"] == pytest.approx(6 / 8)
    assert result["collateral_rate"] == 0.0
