"""Diagnostic routine after a rejection: the xAI and the feedback receive the delta between S_k and the
rejected candidate (not the last commit's) and the structured violations, and the candidate's KPIs are
compared with S_k, not with S_0."""

import copy
import json
import logging
from typing import ClassVar

import pytest
from langchain_core.messages import HumanMessage

from input_agent.src import fresh_simulation, narrativeProcess
from input_agent.src.models import FeedbackResponse
from input_agent.sub_agents.feedback import FeedbackAgent
from input_agent.sub_agents.narrative import NarrativeAgent
from tests.unit.case_study import case_configs

if not logging.getLogger().handlers:
    logging.getLogger().addHandler(logging.NullHandler())

from input_agent import nodes


def task(duration, codes=None):
    t = {"Duration": duration, "Requires_Shutdown": False}
    if codes:
        t.update(taskDependency=True, taskCode=codes)
    return t


def activity(tasks, **extra):
    a = {
        "tasks": tasks,
        "T_period": 720,
        "T_wait": 6,
        "Start_disp": 1,
        "Team": "TeamA",
        "Team members": 2,
        "Shift_duration": 8,
    }
    a.update(extra)
    return a


S0 = {
    "runId": 25,
    "Teams": 1,
    "Simulation_period": 2000,
    "A001": activity({"T001": task(10)}),
    "A002": activity(
        {"T001": task(80), "T002": task(100, ["T001"]), "T003": task(60, ["T001"])}, T_wait=4
    ),
}
S_K = copy.deepcopy(S0)
S_K["A002"]["tasks"]["T002"]["Duration"] = 85
S_K["A002"]["T_wait"] = 6


def rejection(instruction):
    state = {
        "proposed_plan": {"thought_process": "", "instructions": [instruction]},
        "original_config": copy.deepcopy(S0),
        "current_config": copy.deepcopy(S_K),
        "retry_count": 0,
        "delta": {"activity_values": {"A002": {"T_wait": {"old": 4, "new": 6}}}},  # last commit's
    }
    return nodes.node_executor(state)


def test_executor_passes_the_delta_between_s_k_and_the_candidate():
    result = rejection({"operation": "DELETE", "path": "A002.tasks.T001"})
    assert result["task_queue"] == ["simulator", "xai", "feedback"]
    delta = result["episodic_delta"]
    assert delta["deleted_tasks"] == {"A002": ["T001"]}
    # Nothing of the last commit (T002 = 85, T_wait = 6) appears: the delta is against S_k, not S_0.
    assert delta["activity_values"] == {} and delta["task_values"] == {}


def test_violations_say_that_the_deleted_task_no_longer_exists():
    # The executor passes S_k to the validator, so the message says the batch deleted T001.
    result = rejection({"operation": "DELETE", "path": "A002.tasks.T001"})
    assert [v["detail"] for v in result["validation_violations"]] == [
        "A002.T002 lists T001 in taskCode, but T001 no longer exists in A002",
        "A002.T003 lists T001 in taskCode, but T001 no longer exists in A002",
    ]


def test_petri_net_rejection_also_passes_the_delta():
    result = rejection({"operation": "SET", "path": "A002.tasks", "value": {}})
    assert result["task_queue"] == ["feedback"]
    assert sorted(result["episodic_delta"]["deleted_tasks"]["A002"]) == ["T001", "T002", "T003"]


def kpi(name):
    return f"general_results[0].{name}"


@pytest.mark.engine
def test_rejected_candidate_is_compared_with_the_current_configuration(monkeypatch, tmp_path):
    # Subsection 4.2: candidate C (S_{k+1} without A002.T001) against S_{k+1}. Against S_0 it would
    # be -90 h, -220 h and +32 h; the +32 h of unavailability come from T_wait, already in S_{k+1}.
    _, s1, candidate = case_configs()
    io_dir = tmp_path / "io"
    monkeypatch.setenv("CDTO_IO_DIR", str(io_dir))
    state = {
        "episodic_loop": True,
        "episodic_config": candidate,
        "current_config": s1,
        "episodic_paths": {
            "stats_json": str(io_dir / "outputs" / "results" / "general_outputs_all.json")
        },
        "baseline_kpis": {
            kpi("Intervention_time_hours"): 1130.0,
            kpi("P4_total_busy_hours"): 1002.0,
        },
    }
    result = nodes.node_simulator(state)
    delta = result["kpi_delta"]
    assert delta[kpi("Intervention_time_hours")]["baseline"] == 1088.0
    assert delta[kpi("Intervention_time_hours")]["delta_abs"] == -48.0
    assert delta[kpi("P4_total_busy_hours")]["baseline"] == 956.0
    assert delta[kpi("P4_total_busy_hours")]["delta_abs"] == -174.0
    assert delta[kpi("Net_plan_unavailability_hours")]["baseline"] == 282.0
    assert delta[kpi("Net_plan_unavailability_hours")]["delta_abs"] == 0.0
    assert result["episodic_reference_kpis"][kpi("Intervention_time_hours")] == 1088.0


def test_standard_simulation_is_still_compared_with_the_baseline(monkeypatch):
    calls = []
    monkeypatch.setattr(
        fresh_simulation, "run_petrinets_simulation_fresh", lambda **kw: calls.append(kw["input"])
    )
    monkeypatch.setattr(nodes, "load_kpis_from_stats", lambda path: {"k": 80.0})
    state = {
        "episodic_loop": False,
        "current_config": {"which": "current"},
        "simulation_paths": {"stats_json": "stats.json"},
        "baseline_kpis": {"k": 100.0},
    }
    result = nodes.node_simulator(state)
    assert calls == [{"which": "current"}]
    assert result["kpi_delta"]["k"]["baseline"] == 100.0
    assert "episodic_reference_kpis" not in result


def test_episodic_xai_receives_the_candidate_delta_and_violations(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        narrativeProcess,
        "xAI_simulation",
        lambda input_data: captured.update(input_data) or "report",
    )
    violations = [
        {
            "rule": "referencias",
            "group": "DOMINIO",
            "path": "A002.tasks.T002.taskCode",
            "detail": "x",
        }
    ]
    state = {
        "simulation_ready": True,
        "episodic_loop": True,
        "episodic_paths": {"stats_json": ""},
        "delta": {"last": "commit"},
        "episodic_delta": {"deleted_tasks": {"A002": ["T001"]}},
        "validation_violations": violations,
        "baseline_report": "base",
        "baseline_kpis": {"k": 1130.0},
        "episodic_reference_kpis": {"k": 1088.0},
        "current_kpis": {"k": 1040.0},
        "kpi_delta": {},
    }
    nodes.node_xai(state)
    assert captured["delta"] == {"deleted_tasks": {"A002": ["T001"]}}
    assert captured["validation_violations"] == violations
    # The KPI table compares the candidate with S_k.
    assert captured["baseline_kpis"] == {"k": 1088.0}
    assert "S_k" in captured["kpi_reference"]


@pytest.mark.parametrize("episodic", [True, False])
def test_xai_logs_the_delta_it_receives(monkeypatch, caplog, episodic):
    monkeypatch.setattr(narrativeProcess, "xAI_simulation", lambda input_data: "report")
    state = {
        "simulation_ready": True,
        "episodic_loop": episodic,
        "episodic_paths": {"stats_json": ""},
        "simulation_paths": {"stats_json": ""},
        "delta": {"last": "commit"},
        "episodic_delta": {"deleted_tasks": {"A002": ["T001"]}},
    }
    with caplog.at_level(logging.INFO, logger=nodes.logger.name):
        nodes.node_xai(state)
    [line] = [
        r.getMessage() for r in caplog.records if "Delta disponible para xAI" in r.getMessage()
    ]
    if episodic:
        assert "deleted_tasks" in line and "last" not in line
    else:
        assert "'last': 'commit'" in line


class FakeLLM:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    def llm(self, prompt, content):
        self.calls.append(content)
        return self.reply


class FakeTrace:
    stats: ClassVar[dict] = {}


def test_narrative_puts_the_violations_in_its_input():
    llm = FakeLLM({"report": "2. KPI Changes\n| KPI | Baseline | Current | Delta abs | Delta % |"})
    violations = [
        {
            "rule": "referencias",
            "group": "DOMINIO",
            "path": "A002.tasks.T003.taskCode",
            "detail": "x",
        }
    ]
    NarrativeAgent(None, llm).generate_full_narrative(
        [],
        FakeTrace(),
        delta_context={"deleted_tasks": {"A002": ["T001"]}},
        baseline_report="base",
        validation_violations=violations,
    )
    [content] = llm.calls
    assert "deleted_tasks" in content
    assert json.dumps(violations, ensure_ascii=False) in content


def test_narrative_without_violations_is_unchanged():
    llm = FakeLLM({"report": "2. KPI Changes\n| KPI | Baseline | Current | Delta abs | Delta % |"})
    NarrativeAgent(None, llm).generate_full_narrative(
        [], FakeTrace(), delta_context={"a": 1}, baseline_report="base"
    )
    assert "Validation Violations" not in llm.calls[0]
    assert "KPI Reference" not in llm.calls[0]


def test_narrative_states_the_kpi_reference():
    llm = FakeLLM({"report": "2. KPI Changes\n| KPI | Baseline | Current | Delta abs | Delta % |"})
    NarrativeAgent(None, llm).generate_full_narrative(
        [],
        FakeTrace(),
        delta_context={"a": 1},
        baseline_report="base",
        baseline_kpis={"k": 1088.0},
        current_kpis={"k": 1040.0},
        kpi_reference="current configuration S_k (before the rejected change)",
    )
    [content] = llm.calls
    assert "KPI Reference: the Baseline column" in content and "S_k" in content
    assert "| K | 1088.0000 | 1040.0000 | -48.0000 |" in content


@pytest.mark.parametrize("episodic_report", ["informe episódico", ""])
def test_feedback_agent_puts_the_delta_in_its_input(episodic_report):
    llm = FakeLLM({"diagnosis": "d", "suggestion": "s"})
    violations = [
        {
            "rule": "referencias",
            "group": "DOMINIO",
            "path": "A002.tasks.T002.taskCode",
            "detail": "x",
        }
    ]
    FeedbackAgent(llm).analyze_error(
        "q", violations, episodic_report, delta={"deleted_tasks": {"A002": ["T001"]}}
    )
    [content] = llm.calls
    assert "Rejected Candidate Delta" in content and "deleted_tasks" in content
    assert json.dumps(violations) in content


class FakeFeedbackAgent:
    calls: ClassVar[list] = []

    def __init__(self, llm):
        pass

    def analyze_error(self, query, validation_issues, episodic_report, delta=None):
        FakeFeedbackAgent.calls.append(
            {"issues": validation_issues, "report": episodic_report, "delta": delta}
        )
        return FeedbackResponse(diagnosis="d", suggestion="s")


@pytest.mark.parametrize("episodic_loop", [True, False])
def test_feedback_receives_violations_and_delta(monkeypatch, tmp_path, episodic_loop):
    monkeypatch.setattr(nodes, "FeedbackAgent", FakeFeedbackAgent)
    monkeypatch.setattr(nodes, "get_llm", lambda: None)
    FakeFeedbackAgent.calls = []
    violations = [
        {
            "rule": "referencias",
            "group": "DOMINIO",
            "path": "A002.tasks.T002.taskCode",
            "detail": "x",
        }
    ]
    state = {
        "messages": [HumanMessage(content="Remove task T001 from A002")],
        "validation_errors": ["[referencias | DOMINIO] A002.tasks.T002.taskCode: x"],
        "validation_violations": violations,
        "episodic_delta": {"deleted_tasks": {"A002": ["T001"]}},
        "retry_count": 1,
        "episodic_loop": episodic_loop,
        "episodic_report": "informe episódico" if episodic_loop else "",
        "episodic_paths": {"manual_csv": str(tmp_path / "episodic.csv")},
        "correction_history": [],
    }
    nodes.node_feedback(state, {"configurable": {"episodic_store": None}})
    [call] = FakeFeedbackAgent.calls
    assert call["issues"] == violations
    assert call["delta"] == {"deleted_tasks": {"A002": ["T001"]}}
