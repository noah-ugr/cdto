"""/config/update replaces the configuration through _apply_batch: the candidate is checked and
committed, or rejected with its violations and the current configuration kept."""

import asyncio
import copy
import logging

import pytest

if not logging.getLogger().handlers:
    logging.getLogger().addHandler(logging.NullHandler())

from core import api
from input_agent import nodes
from input_agent.src.PetriNetConfig import PetriConfigEngine
from tests.unit.case_study import case_configs


@pytest.fixture
def app_state(monkeypatch):
    s0, _, _ = case_configs()
    monkeypatch.setattr(api.app_state, "initial_input", copy.deepcopy(s0))
    monkeypatch.setattr(api.app_state, "last_config", copy.deepcopy(s0))
    return api.app_state


def update(config):
    return asyncio.run(api.update_config(api.ConfigRequest(config=config)))


def test_valid_configuration_is_committed(app_state):
    _, s1, _ = case_configs()
    response = update(s1)
    assert response.success is True
    assert app_state.last_config == s1
    assert response.current_config == s1
    assert response.validation_violations == []


def test_domain_violation_is_rejected_with_its_violations(app_state):
    s0, _, candidate = case_configs()  # S_{k+1} without A002.T001
    response = update(candidate)
    assert response.success is False
    assert app_state.last_config == s0
    assert response.current_config == s0
    assert [(v["rule"], v["group"], v["detail"]) for v in response.validation_violations] == [
        (
            "referencias",
            "DOMINIO",
            "A002.T002 lists T001 in taskCode, but T001 no longer exists in A002",
        ),
        (
            "referencias",
            "DOMINIO",
            "A002.T003 lists T001 in taskCode, but T001 no longer exists in A002",
        ),
    ]
    assert response.validation_errors[0].startswith("[referencias | DOMINIO] A002.tasks.T002")


def test_petri_net_violation_is_rejected(app_state):
    s0, _, _ = case_configs()
    candidate = copy.deepcopy(s0)
    del candidate["Simulation_period"]
    response = update(candidate)
    assert response.success is False
    assert app_state.last_config == s0
    assert [(v["rule"], v["group"]) for v in response.validation_violations] == [
        ("campos_leidos", "RED DE PETRI")
    ]


def test_update_goes_through_apply_batch(monkeypatch, app_state):
    calls = []
    real = nodes._apply_batch
    monkeypatch.setattr(
        nodes,
        "_apply_batch",
        lambda state, batch, actor: calls.append(actor) or real(state, batch, actor),
    )
    update(case_configs()[1])
    assert calls == ["Config update"]


def applied(current, new):
    return PetriConfigEngine(current).apply_batch(nodes.replacement_batch(current, new))


def test_replacement_batch_writes_only_what_changes():
    s0, s1, _ = case_configs()
    batch = nodes.replacement_batch(s0, s1)
    assert [(i.operation.value, i.path) for i in batch.instructions] == [("SET", "A002")]
    assert applied(s0, s1) == s1


def test_replacement_batch_adds_and_removes_top_level_keys():
    s0, _, _ = case_configs()
    new = copy.deepcopy(s0)
    new["A003"] = copy.deepcopy(s0["A001"])
    del new["runId"]
    batch = nodes.replacement_batch(s0, new)
    assert [(i.operation.value, i.path) for i in batch.instructions] == [
        ("DELETE", "runId"),
        ("SET", "A003"),
    ]
    result = applied(s0, new)
    assert result == new and list(result) == list(new)


def test_replacement_batch_keeps_the_order_of_the_new_configuration():
    s0, _, _ = case_configs()
    reordered = {
        key: copy.deepcopy(s0[key])
        for key in ("runId", "Teams", "Simulation_period", "A002", "A001")
    }
    result = applied(s0, reordered)
    assert result == reordered and list(result) == list(reordered)
