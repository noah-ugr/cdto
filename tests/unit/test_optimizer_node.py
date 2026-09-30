"""The optimizer applies S* like a batch: working copy, check, and commit or rejection with the same
consequences in the queue as the executor (DOMINIO: the candidate is simulated; RED DE PETRI or
limites: feedback only). A committed S* is then simulated and explained before the chat, against
the configuration before the optimization."""

import copy
import logging

import pytest
from langchain_core.messages import HumanMessage

from input_agent.src import fresh_simulation, narrativeProcess
from input_agent.sub_agents import optimizer
from tests.unit.case_study import IWO_OUTPUT, case_configs

# S* se escribe con la numeración de actividades de la entrada de la IWO (utils/mapping_utils).
pytestmark = pytest.mark.engine

if not logging.getLogger().handlers:
    logging.getLogger().addHandler(logging.NullHandler())

from input_agent import nodes


def fake_optimizer(result):
    class FakeOptimizerAgent:
        def __init__(self, llm):
            pass

        def optimize(self, user_query, json_input=None):
            return result(json_input)

    return FakeOptimizerAgent


def optimizer_state(s1, **extra):
    s0, _, _ = case_configs()
    state = {
        "messages": [HumanMessage(content="Optimize the system to reach at least 90 %.")],
        "original_config": s0,
        "current_config": copy.deepcopy(s1),
        "retry_count": 0,
        "task_queue": [],
    }
    state.update(extra)
    return state


def run_optimizer(monkeypatch, s_star_of, success=True, **extra):
    monkeypatch.setattr(nodes, "get_llm", lambda: None)
    monkeypatch.setattr(
        nodes,
        "OptimizerAgent",
        fake_optimizer(
            lambda current: (success, {"AVAILABILITY_TARGET": 0.9}, s_star_of(current), "done")
        ),
    )
    _, s1, _ = case_configs()
    return s1, nodes.node_optimizer(optimizer_state(s1, **extra))


def s_star_with(changes=()):
    """S* of the case (IWO_OUTPUT on the current configuration) with some decision variables changed."""

    def build(current):
        s_star = optimizer.build_s_star(current, IWO_OUTPUT)
        for act, field, value in changes:
            s_star[act][field] = value
        return s_star

    return build


def test_valid_s_star_is_committed(monkeypatch):
    s1, result = run_optimizer(monkeypatch, s_star_with())
    assert result["current_config"] == optimizer.build_s_star(s1, IWO_OUTPUT)
    assert result["validation_errors"] == [] and result["validation_violations"] == []
    assert any(
        "Optimizer aplicó los cambios exitosamente" in log for log in result["execution_log"]
    )
    assert "KPIs extraídos: ['AVAILABILITY_TARGET']" in result["execution_log"][0]


def test_domain_failure_simulates_the_rejected_s_star(monkeypatch):
    # Shift_duration > 24 violates rangos (DOMINIO): same consequences as a batch of the planner.
    _, result = run_optimizer(monkeypatch, s_star_with([("A001", "Shift_duration", 30)]))
    assert "current_config" not in result
    assert result["task_queue"] == ["simulator", "xai", "feedback"]
    assert result["episodic_loop"] is True
    assert result["episodic_config"]["A001"]["Shift_duration"] == 30
    assert [(v["rule"], v["group"]) for v in result["validation_violations"]] == [
        ("rangos", "DOMINIO")
    ]


def test_net_failure_goes_to_feedback_without_simulation(monkeypatch):
    # Team members = 0 violates dom_int (RED DE PETRI): the candidate is not simulated.
    _, result = run_optimizer(monkeypatch, s_star_with([("A002", "Team members", 0)]))
    assert "current_config" not in result
    assert result["task_queue"] == ["feedback"]
    assert result["episodic_loop"] is False
    assert "episodic_config" not in result
    assert [(v["rule"], v["group"]) for v in result["validation_violations"]] == [
        ("dom_int", "RED DE PETRI")
    ]


@pytest.mark.parametrize(
    "success, s_star_of",
    [(False, lambda current: None), (True, lambda current: None), (True, lambda current: current)],
    ids=["optimizer-failed", "no-output", "nothing-changes"],
)
def test_nothing_is_applied_without_a_changed_s_star(monkeypatch, success, s_star_of):
    _, result = run_optimizer(monkeypatch, s_star_of, success=success)
    assert "current_config" not in result
    assert "task_queue" not in result


def test_the_executor_keeps_its_behaviour():
    _, s1, _ = case_configs()
    state = optimizer_state(
        s1,
        proposed_plan={
            "thought_process": "",
            "instructions": [{"operation": "SET", "path": "A001.T_period", "value": 0}],
        },
    )
    result = nodes.node_executor(state)
    assert result["task_queue"] == ["simulator", "xai", "feedback"]
    assert result["execution_log"][0].startswith("Executor detectó errores de validación")


# --- after the commit: simulator and xai, against the configuration before the optimization ---


def test_committed_s_star_is_simulated_and_explained_before_the_chat(monkeypatch):
    s1, result = run_optimizer(monkeypatch, s_star_with())
    assert result["task_queue"] == ["simulator", "xai"]
    assert result["reference_config"] == s1
    # The delta is S_{k+1} -> S*: the edits of category B are not in it.
    team = result["delta"]["activity_values"]["A001"]["Team members"]
    assert (team["old"], team["new"]) == (2, 20)
    assert result["delta"]["task_values"] == {}


def test_later_tasks_stay_after_simulator_and_xai(monkeypatch):
    _, result = run_optimizer(monkeypatch, s_star_with(), task_queue=["xai", "temporal_xai"])
    assert result["task_queue"] == ["simulator", "xai", "temporal_xai"]


def kpi(name):
    return f"general_results[0].{name}"


def test_simulator_measures_s_star_against_the_configuration_before_the_optimization(
    monkeypatch, tmp_path
):
    _, s1, _ = case_configs()
    io_dir = tmp_path / "io"
    monkeypatch.setenv("CDTO_IO_DIR", str(io_dir))
    state = {
        "episodic_loop": False,
        "current_config": optimizer.build_s_star(s1, IWO_OUTPUT),
        "reference_config": s1,
        "simulation_paths": {
            "stats_json": str(io_dir / "outputs" / "results" / "general_outputs_all.json")
        },
        "baseline_kpis": {kpi("Intervention_time_hours"): 1130.0},
    }
    result = nodes.node_simulator(state)
    delta = result["kpi_delta"]
    # The reference is S_{k+1} (1088 h, 956 h, 282 h), not S_0.
    assert delta[kpi("Intervention_time_hours")]["baseline"] == 1088.0
    assert delta[kpi("P4_total_busy_hours")]["baseline"] == 956.0
    assert delta[kpi("Net_plan_unavailability_hours")]["baseline"] == 282.0
    assert delta[kpi("Net_plan_availability_percent")]["current"] >= 90.0
    assert result["reference_kpis"][kpi("Intervention_time_hours")] == 1088.0
    assert "episodic_reference_kpis" not in result


def test_simulator_simulates_the_reference_first(monkeypatch):
    calls = []
    monkeypatch.setattr(
        fresh_simulation,
        "run_petrinets_simulation_fresh",
        lambda **kw: calls.append((kw["input"], kw.get("io_dir") is not None)),
    )
    monkeypatch.setattr(
        nodes, "load_kpis_from_stats", lambda path: {"k": 90.0 if "cdto_ref_" in path else 99.0}
    )
    state = {
        "episodic_loop": False,
        "current_config": {"which": "S*"},
        "reference_config": {"which": "before"},
        "simulation_paths": {"stats_json": "stats.json"},
        "baseline_kpis": {"k": 80.0},
    }
    result = nodes.node_simulator(state)
    assert calls == [({"which": "before"}, True), ({"which": "S*"}, False)]
    assert (
        result["kpi_delta"]["k"]["baseline"] == 90.0 and result["kpi_delta"]["k"]["current"] == 99.0
    )


@pytest.mark.parametrize("reference_kpis", [{"k": 1088.0}, {}])
def test_xai_compares_with_the_configuration_before_the_optimization(monkeypatch, reference_kpis):
    captured = {}
    monkeypatch.setattr(
        narrativeProcess, "xAI_simulation", lambda input_data: captured.update(input_data) or "r"
    )
    state = {
        "simulation_ready": True,
        "episodic_loop": False,
        "simulation_paths": {"stats_json": ""},
        "delta": {"activity_values": {"A001": {"Team members": {"old": 2, "new": 20}}}},
        "baseline_report": "base",
        "baseline_kpis": {"k": 1130.0},
        "reference_kpis": reference_kpis,
        "current_kpis": {"k": 591.0},
        "kpi_delta": {},
    }
    nodes.node_xai(state)
    if reference_kpis:
        assert captured["baseline_kpis"] == {"k": 1088.0}
        assert captured["kpi_reference"] == "configuration before the optimization"
    else:
        assert captured["baseline_kpis"] == {"k": 1130.0}
        assert "kpi_reference" not in captured


def test_each_turn_starts_without_a_reference(monkeypatch):
    class FakeOrchestrator:
        def __init__(self, llm):
            pass

        def orchestrate(self, message):
            return type("Queue", (), {"steps": ["simulator", "xai"]})()

    monkeypatch.setattr(nodes, "OrchesterAgent", FakeOrchestrator)
    monkeypatch.setattr(nodes, "get_llm", lambda: None)
    state = {
        "messages": [HumanMessage(content="Simulate")],
        "execution_log": [],
        "reference_config": {"runId": 25},
        "reference_kpis": {"k": 1.0},
    }
    result = nodes.node_orchestrator(state)
    assert result["reference_config"] == {} and result["reference_kpis"] == {}
