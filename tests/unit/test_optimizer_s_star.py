"""S* only changes the IWO decision variables (Team members, Shift_duration, Start_disp and T_wait of
each activity); everything else comes from the current configuration: tasks with Requires_Shutdown,
precedences, flags and Simulation_period."""

import copy
import json
from types import SimpleNamespace

import pytest

from input_agent.sub_agents import optimizer
from tests.unit.case_study import IWO_OUTPUT, case_configs

# S* se escribe con la numeración de actividades de la entrada de la IWO (utils/mapping_utils).
pytestmark = pytest.mark.engine


def test_s_star_changes_only_the_decision_variables():
    _, s1, _ = case_configs()
    before = copy.deepcopy(s1)
    s_star = optimizer.build_s_star(s1, IWO_OUTPUT)

    expected = copy.deepcopy(s1)
    for act, act_id in (("A001", "ActID1"), ("A002", "ActID2")):
        for field in optimizer.DECISION_FIELDS:
            expected[act][field] = IWO_OUTPUT["PNIpnt"][act_id][field]
    assert s_star == expected
    assert s1 == before
    # What the IWO output lost is kept.
    assert s_star["Simulation_period"] == 2000
    assert s_star["A002"]["activityCode"] == ["A001"]
    assert s_star["A002"]["tasks"]["T004"]["taskCode"] == ["T002", "T003"]
    assert s_star["A002"]["tasks"]["T003"]["Requires_Shutdown"] is True


def test_decision_batch_sets_only_what_changes():
    _, s1, _ = case_configs()
    batch = optimizer.decision_batch(s1, optimizer.build_s_star(s1, IWO_OUTPUT))
    # Shift_duration stays at 8 (8.0 == 8), so it is not set.
    assert [(i.operation.value, i.path) for i in batch.instructions] == [
        ("SET", "A001.Team members"),
        ("SET", "A001.Start_disp"),
        ("SET", "A001.T_wait"),
        ("SET", "A002.Team members"),
        ("SET", "A002.Start_disp"),
        ("SET", "A002.T_wait"),
    ]
    assert optimizer.decision_batch(s1, s1).instructions == []


def test_missing_activity_or_variable_is_an_error():
    _, s1, _ = case_configs()
    without_act = copy.deepcopy(IWO_OUTPUT)
    del without_act["PNIpnt"]["ActID2"]
    with pytest.raises(ValueError, match="ActID2"):
        optimizer.build_s_star(s1, without_act)
    without_field = copy.deepcopy(IWO_OUTPUT)
    del without_field["PNIpnt"]["ActID1"]["T_wait"]
    with pytest.raises(ValueError, match="T_wait"):
        optimizer.build_s_star(s1, without_field)


def test_run_optimizer_returns_s_star(monkeypatch, tmp_path):
    _, s1, _ = case_configs()
    shared = tmp_path / "petrinet_shared_dicts.json"
    shared.write_text(json.dumps(IWO_OUTPUT), encoding="utf-8")
    monkeypatch.setattr(optimizer, "SHARED_DICTS_JSON", shared)
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["json_input"] = json.loads(kwargs["env"]["JSON_INPUT"])
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(optimizer.subprocess, "run", fake_run)
    success, s_star, _ = optimizer.OptimizerAgent(None)._run_optimizer(
        "iwo", {"AVAILABILITY_TARGET": 0.9}, s1
    )
    assert success is True
    assert seen["json_input"] == s1
    assert s_star == optimizer.build_s_star(s1, IWO_OUTPUT)
