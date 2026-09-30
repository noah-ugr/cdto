import copy
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import ClassVar

import pytest
from langchain_core.messages import HumanMessage

from input_agent.src.models import FeedbackResponse
from input_agent.src.tools import DOMINIO, RED_DE_PETRI

# Por si acaso: con un handler en el root logger, el basicConfig de nodes.py no instala el suyo.
if not logging.getLogger().handlers:
    logging.getLogger().addHandler(logging.NullHandler())

from input_agent import nodes

REPO_ROOT = Path(__file__).resolve().parents[2]


def activity(tasks, **extra):
    a = {
        "tasks": tasks,
        "T_period": 200,
        "T_wait": 5,
        "Start_disp": 1,
        "Team": "TeamA",
        "Team members": 2,
        "Shift_duration": 8,
        "Activity_Order_Enforced": True,
        "Activity_Order_Before": [],
    }
    a.update(extra)
    return a


def task(duration, before=()):
    return {
        "Duration": duration,
        "Requires_Shutdown": False,
        "Order_Enforced": True,
        "Order_Before": list(before),
    }


BASE = {
    "runId": 1,
    "Teams": 1,
    "Simulation_period": 1000,
    "A001": activity(
        {"T001": task(1, ["T002"]), "T002": task(2, ["T003"]), "T003": task(3)},
        Activity_Order_Before=["A002"],
    ),
    "A002": activity({"T001": task(4)}, Activity_Order_Before=["A003"]),
    "A003": activity({"T001": task(5)}),
}


def executor_state(*instructions, skip=False):
    return {
        "proposed_plan": {"thought_process": "", "instructions": list(instructions)},
        "original_config": copy.deepcopy(BASE),
        "current_config": copy.deepcopy(BASE),
        "retry_count": 0,
        "skip_deterministic_validation": skip,
    }


@pytest.fixture(autouse=True)
def no_simulation(monkeypatch):
    from input_agent.src import fresh_simulation

    def boom(*args, **kwargs):
        raise AssertionError("el executor no debe simular")

    monkeypatch.setattr(fresh_simulation, "run_petrinets_simulation_fresh", boom)


# --- comprobación de rutas antes de aplicar ----------------------------------------------------


@pytest.mark.parametrize(
    "instruction, kind",
    [
        ({"operation": "SET", "path": "A009.T_period", "value": 3}, "engine_error"),
        ({"operation": "APPEND", "path": "T003.Order_Before", "value": "T001"}, "engine_error"),
        ({"operation": "DELETE", "path": "A001.Foo"}, "delete_missing"),
        ({"operation": "REMOVE_ITEM", "path": "A001.Foo", "value": "A002"}, "remove_list_missing"),
    ],
)
def test_unresolved_route_aborts_without_applying(instruction, kind):
    valid_first = {"operation": "SET", "path": "A001.T_wait", "value": 7}
    result = nodes.node_executor(executor_state(valid_first, instruction))

    assert result["task_queue"] == []
    assert "current_config" not in result
    assert len(result["validation_errors"]) == 1
    assert result["validation_errors"][0].startswith(f"Ruta no resuelta ({kind})")


def test_remove_item_of_absent_value_is_not_a_route_error():
    result = nodes.node_executor(
        executor_state(
            {"operation": "REMOVE_ITEM", "path": "A001.Activity_Order_Before", "value": "A009"}
        )
    )
    assert result["current_config"]["A001"]["Activity_Order_Before"] == ["A002"]


def test_benchmark_mode_is_unchanged():
    # Sin comprobación de rutas ni renumeración: aplica lo que puede, como antes.
    result = nodes.node_executor(
        executor_state(
            {"operation": "SET", "path": "A001.T_wait", "value": 7},
            {"operation": "DELETE", "path": "A009.T_period"},
            {
                "operation": "SET",
                "path": "A001.tasks.T001_new",
                "value": {"Duration": 9, "Requires_Shutdown": False},
            },
            skip=True,
        )
    )
    assert result["current_config"]["A001"]["T_wait"] == 7
    assert "T001_new" in result["current_config"]["A001"]["tasks"]


# --- rechazo por grupo -------------------------------------------------------------------------


def test_domain_only_rejection_keeps_previous_design():
    result = nodes.node_executor(
        executor_state({"operation": "SET", "path": "A001.T_period", "value": 0})
    )

    assert result["task_queue"] == ["simulator", "xai", "feedback"]
    assert result["episodic_loop"] is True
    assert result["episodic_config"]["A001"]["T_period"] == 0
    assert result["validation_violations"] == [
        {
            "rule": "rangos",
            "group": DOMINIO,
            "path": "A001.T_period",
            "detail": "A001.T_period is 0; it must be > 0",
        }
    ]
    assert result["validation_errors"] == [
        "[rangos | DOMINIO] A001.T_period: A001.T_period is 0; it must be > 0"
    ]


def test_petri_net_rejection_is_not_simulated():
    result = nodes.node_executor(executor_state({"operation": "DELETE", "path": "A001.T_wait"}))

    assert result["task_queue"] == ["feedback"]
    assert result["episodic_loop"] is False
    assert "episodic_config" not in result
    assert result["validation_violations"] == [
        {
            "rule": "campos_leidos",
            "group": RED_DE_PETRI,
            "path": "A001.T_wait",
            "detail": "A001 has no T_wait field",
        }
    ]
    assert result["retry_count"] == 1


def test_limites_rejection_is_not_simulated():
    tasks = {f"T{j:03d}": {"Duration": 1, "Requires_Shutdown": False} for j in range(1000)}
    tasks["T1000"] = {"Duration": 1, "Requires_Shutdown": False}
    result = nodes.node_executor(
        executor_state({"operation": "SET", "path": "A003.tasks", "value": tasks})
    )

    assert result["task_queue"] == ["feedback"]
    assert result["episodic_loop"] is False
    assert "episodic_config" not in result
    assert "limites" in {v["rule"] for v in result["validation_violations"]}
    assert {v["group"] for v in result["validation_violations"]} == {DOMINIO}


def test_mixed_rejection_counts_as_petri_net():
    result = nodes.node_executor(
        executor_state(
            {"operation": "SET", "path": "A001.T_period", "value": 0},
            {"operation": "SET", "path": "A001.tasks", "value": {}},
        )
    )
    assert result["task_queue"] == ["feedback"]
    assert {v["group"] for v in result["validation_violations"]} == {DOMINIO, RED_DE_PETRI}


def test_commit():
    result = nodes.node_executor(
        executor_state({"operation": "SET", "path": "A001.T_wait", "value": 0})
    )
    assert result["current_config"]["A001"]["T_wait"] == 0
    assert result["validation_errors"] == [] and result["validation_violations"] == []
    assert "task_queue" not in result


# --- extremo a extremo con IDs temporales del Planner -------------------------------------------


def test_intermediate_task_with_temporary_id_is_admitted_and_renumbered():
    new_task = task(9, ["T002"])
    result = nodes.node_executor(
        executor_state(
            {"operation": "SET", "path": "A001.tasks.T001_new", "value": new_task},
            {"operation": "REMOVE_ITEM", "path": "A001.tasks.T001.Order_Before", "value": "T002"},
            {"operation": "APPEND", "path": "A001.tasks.T001.Order_Before", "value": "T001_new"},
        )
    )
    tasks = result["current_config"]["A001"]["tasks"]
    assert result["validation_errors"] == []
    assert list(tasks) == ["T001", "T002", "T003", "T004"]
    assert [tasks[t]["Duration"] for t in tasks] == [1, 9, 2, 3]
    assert [tasks[t]["Order_Before"] for t in tasks] == [["T002"], ["T003"], ["T004"], []]


def test_intermediate_activity_with_temporary_id_is_admitted_and_renumbered():
    new_activity = activity({"T001": task(8)}, Activity_Order_Before=["A003"])
    result = nodes.node_executor(
        executor_state(
            {"operation": "SET", "path": "A002_new", "value": new_activity},
            {"operation": "REMOVE_ITEM", "path": "A002.Activity_Order_Before", "value": "A003"},
            {"operation": "APPEND", "path": "A002.Activity_Order_Before", "value": "A002_new"},
        )
    )
    config = result["current_config"]
    assert result["validation_errors"] == []
    assert [k for k in config if k.startswith("A")] == ["A001", "A002", "A003", "A004"]
    assert [config[a]["tasks"]["T001"]["Duration"] for a in ("A002", "A003", "A004")] == [4, 8, 5]
    assert [config[a]["Activity_Order_Before"] for a in ("A001", "A002", "A003", "A004")] == [
        ["A002"],
        ["A003"],
        ["A004"],
        [],
    ]


# --- feedback -----------------------------------------------------------------------------------


class FakeFeedbackAgent:
    calls: ClassVar[list] = []

    def __init__(self, llm):
        pass

    def analyze_error(self, query, validation_issues, episodic_report, delta=None):
        FakeFeedbackAgent.calls.append({"issues": validation_issues, "report": episodic_report})
        return FeedbackResponse(diagnosis="diagnóstico", suggestion="sugerencia")


def feedback_state(tmp_path, **extra):
    state = {
        "messages": [HumanMessage(content="quita la espera de A001")],
        "validation_errors": [
            "[campos_leidos | RED DE PETRI] A001.T_wait: A001 has no T_wait field"
        ],
        "validation_violations": [
            {
                "rule": "campos_leidos",
                "group": RED_DE_PETRI,
                "path": "A001.T_wait",
                "detail": "A001 has no T_wait field",
            }
        ],
        "retry_count": 1,
        "episodic_loop": False,
        "episodic_report": "informe episódico",
        "episodic_paths": {"manual_csv": str(tmp_path / "episodic.csv")},
        "correction_history": [],
    }
    state.update(extra)
    return state


@pytest.fixture
def fake_feedback(monkeypatch):
    monkeypatch.setattr(nodes, "FeedbackAgent", FakeFeedbackAgent)
    monkeypatch.setattr(nodes, "get_llm", lambda: None)
    FakeFeedbackAgent.calls = []
    return FakeFeedbackAgent


def test_petri_net_feedback_receives_structured_violations(fake_feedback, tmp_path):
    state = feedback_state(tmp_path)
    result = nodes.node_feedback(state, {"configurable": {"episodic_store": None}})
    assert fake_feedback.calls == [{"issues": state["validation_violations"], "report": ""}]
    assert result["correction_history"] == ["Intento #1: diagnóstico. Sugerencia: sugerencia"]
    assert (tmp_path / "episodic.csv").exists()


def test_domain_feedback_keeps_episodic_path(fake_feedback, tmp_path):
    # Tras la simulación del candidato rechazado, el feedback episódico recibe el informe episódico
    # y las violaciones estructuradas.
    state = feedback_state(tmp_path, episodic_loop=True)
    nodes.node_feedback(state, {"configurable": {"episodic_store": None}})
    assert fake_feedback.calls == [
        {"issues": state["validation_violations"], "report": "informe episódico"}
    ]


# --- importar nodes.py no toca agent_debug.log --------------------------------------------------


@pytest.mark.parametrize("existing", [None, "contenido previo\n"])
def test_importing_nodes_does_not_touch_debug_log(tmp_path, existing):
    log = tmp_path / "agent_debug.log"
    if existing is not None:
        log.write_text(existing, encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    subprocess.run(
        [sys.executable, "-c", "import input_agent.nodes"],
        cwd=tmp_path,
        env=env,
        check=True,
        capture_output=True,
    )
    if existing is None:
        assert not log.exists()
    else:
        assert log.read_text(encoding="utf-8") == existing
