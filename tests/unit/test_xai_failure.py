"""A failed xAI is not reported as a success: when xAI_simulation returns None (it catches its own
errors, e.g. a lost connection to the LLM), node_xai records the failure in the log and in
execution_log, and /chat answers with success false."""

import asyncio
import logging

import pytest
from langchain_core.messages import HumanMessage

from input_agent.src import narrativeProcess

if not logging.getLogger().handlers:
    logging.getLogger().addHandler(logging.NullHandler())

from core import api
from input_agent import nodes


def xai_state(episodic):
    return {
        "simulation_ready": True,
        "episodic_loop": episodic,
        "simulation_paths": {"stats_json": ""},
        "episodic_paths": {"stats_json": ""},
        "delta": {},
        "baseline_report": "base",
        "baseline_kpis": {"k": 1.0},
        "current_kpis": {"k": 2.0},
        "kpi_delta": {},
    }


@pytest.mark.parametrize(
    "episodic, detail",
    [
        (False, "el análisis no devolvió informe."),
        (True, "el análisis episódico no devolvió informe."),
    ],
    ids=["standard", "episodic"],
)
def test_xai_without_report_is_recorded_as_a_failure(monkeypatch, caplog, episodic, detail):
    monkeypatch.setattr(narrativeProcess, "xAI_simulation", lambda input_data: None)
    with caplog.at_level(logging.ERROR, logger=nodes.logger.name):
        result = nodes.node_xai(xai_state(episodic))
    assert result == {"xai_failed": True, "execution_log": [f"❌ xAI falló: {detail}"]}
    assert [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR] == [
        f"❌ xAI falló: {detail}"
    ]


def test_xai_with_report_is_not_a_failure(monkeypatch):
    monkeypatch.setattr(narrativeProcess, "xAI_simulation", lambda input_data: "report")
    result = nodes.node_xai(xai_state(False))
    assert "xai_failed" not in result
    assert result["report"] == "report"
    assert result["execution_log"] == ["✅ xAI análisis completado. Reporte mostrado arriba."]


def test_each_turn_starts_without_an_xai_failure(monkeypatch):
    class FakeOrchestrator:
        def __init__(self, llm):
            pass

        def orchestrate(self, message):
            return type("Queue", (), {"steps": ["simulator", "xai"]})()

    monkeypatch.setattr(nodes, "OrchesterAgent", FakeOrchestrator)
    monkeypatch.setattr(nodes, "get_llm", lambda: None)
    state = {"messages": [HumanMessage(content="Simulate")], "execution_log": [], "xai_failed": True}
    assert nodes.node_orchestrator(state)["xai_failed"] is False


def chat_with_xai_report(monkeypatch, report):
    """/chat on a graph whose turn is a simulation and node_xai with the given xAI_simulation result."""
    monkeypatch.setattr(narrativeProcess, "xAI_simulation", lambda input_data: report)

    class Graph:
        def invoke(self, input_state, config):
            state = {**input_state, **xai_state(False), "final_response": "answer"}
            return {**state, **nodes.node_xai(state)}

    for name in (
        "graph",
        "baseline_report",
        "last_config",
        "simulation_ready",
        "baseline_kpis",
        "current_kpis",
        "kpi_delta",
        "last_visualizations",
    ):
        monkeypatch.setattr(api.app_state, name, getattr(api.app_state, name))
    monkeypatch.setattr(api.AppState, "_load_visualizations", lambda self: None)
    api.app_state.graph = Graph()
    api.app_state.baseline_report = "base"  # no cold-start simulation
    return asyncio.run(api.chat(api.ChatRequest(message="Simulate", thread_id="t")))


def test_chat_answers_with_success_false_when_the_xai_fails(monkeypatch):
    response = chat_with_xai_report(monkeypatch, None)
    assert response.success is False
    assert response.message == "The xAI analysis failed and produced no report; see execution_log."
    assert response.response == "answer"
    assert response.execution_log == ["❌ xAI falló: el análisis no devolvió informe."]
    assert response.xai_report is None


def test_chat_answers_with_success_true_when_the_xai_reports(monkeypatch):
    response = chat_with_xai_report(monkeypatch, "report")
    assert response.success is True
    assert response.message is None
    assert response.xai_report == "report"
