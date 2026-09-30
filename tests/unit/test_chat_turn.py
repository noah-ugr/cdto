"""The chat summarises the current query: it reads only this turn's execution log (execution_log
accumulates every query of the thread) and the report produced in this turn."""

import logging
from typing import ClassVar

import pytest
from langchain_core.messages import HumanMessage

if not logging.getLogger().handlers:
    logging.getLogger().addHandler(logging.NullHandler())

from input_agent import nodes

Q5_LOGS = [
    "Executor detectó errores de validación: [...]. Reprogramando tareas de recuperación: ['simulator', 'xai', 'feedback'].",
    "Simulación (Episódica) ejecutada exitosamente.",
    "✅ xAI análisis episódico completado. Reporte mostrado arriba.",
    "Feedback Agent diagnosticó el error y generó una sugerencia. Último diagnóstico: removing T001 broke a safety check. "
    "Sugerencia: keep T001 in A002.",
]


class FakeOrchestrator:
    def __init__(self, llm):
        pass

    def orchestrate(self, message):
        return type("Queue", (), {"steps": ["simulator", "xai"]})()


def test_orchestrator_starts_a_new_turn(monkeypatch):
    monkeypatch.setattr(nodes, "OrchesterAgent", FakeOrchestrator)
    monkeypatch.setattr(nodes, "get_llm", lambda: None)
    state = {
        "messages": [HumanMessage(content="Simulate the updated configuration")],
        "execution_log": Q5_LOGS,
        "report": "old report",
        "episodic_report": "old episodic report",
    }
    result = nodes.node_orchestrator(state)
    assert result["turn_log_start"] == len(Q5_LOGS)
    assert result["report"] == "" and result["episodic_report"] == ""


class FakeChatAgent:
    calls: ClassVar[list] = []

    def __init__(self, llm):
        pass

    def generate_response(self, query, message_history, context_info):
        FakeChatAgent.calls.append({"history": message_history, "context": context_info})
        return {"response": "resumen"}


@pytest.fixture
def fake_chat(monkeypatch):
    monkeypatch.setattr(nodes, "ChatAgent", FakeChatAgent)
    monkeypatch.setattr(nodes, "get_llm", lambda: None)
    FakeChatAgent.calls = []
    return FakeChatAgent


def chat_state(turn_logs, **extra):
    state = {
        "messages": [HumanMessage(content="query")],
        "execution_log": Q5_LOGS + turn_logs,
        "turn_log_start": len(Q5_LOGS),
        "current_config": {"runId": 25},
        "validation_errors": [],
        "report": "",
        "episodic_report": "",
        "baseline_report": "",
    }
    state.update(extra)
    return state


def test_simulation_turn_summarises_its_own_report(fake_chat):
    state = chat_state(
        [
            "Simulación (Estándar) ejecutada exitosamente.",
            "✅ xAI análisis completado. Reporte mostrado arriba.",
        ],
        report="Q6 REPORT: intervention 1130 -> 1088 h",
    )
    nodes.node_chat(state)
    [call] = fake_chat.calls
    assert "keep T001" not in call["history"] and "keep T001" not in call["context"]
    assert "Q6 REPORT" in call["context"]
    assert "Simulación (Estándar)" in call["history"]


def test_temporal_turn_summarises_its_own_report(fake_chat):
    state = chat_state(
        ["✅ Análisis temporal completado. Reporte mostrado arriba."],
        report="Q7 REPORT: t4 at 409 h, t3 at 410 h",
    )
    nodes.node_chat(state)
    [call] = fake_chat.calls
    assert "keep T001" not in call["history"]
    assert "Q7 REPORT" in call["context"]
    assert "IMPORTANT" in call["context"]


def test_turn_without_xai_does_not_inherit_previous_xai(fake_chat):
    nodes.node_chat(chat_state(["Context updated with relevant information: A002 durations"]))
    [call] = fake_chat.calls
    assert "IMPORTANT" not in call["context"]
    assert call["history"] == "Context updated with relevant information: A002 durations"
