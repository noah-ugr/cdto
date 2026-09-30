"""LLMService: the current request format is untouched; profiles and raw capture are opt-in."""

import copy
from types import SimpleNamespace

import pytest

from input_agent.src.llm import LLMService, capture_raw_responses

SYSTEM = "Eres un planificador."
USER = "Cambia la duración de la tarea 2 de la actividad 1 a 8 horas."
SUFFIX = "\n\nIMPORTANT: Respond ONLY with valid JSON object, no markdown, no extra text."


def _completion(content, finish_reason="stop", reasoning=None):
    extra = {"reasoning": reasoning} if reasoning else {}
    message = SimpleNamespace(content=content, model_extra=extra)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message, finish_reason=finish_reason)],
        usage=SimpleNamespace(prompt_tokens=11, completion_tokens=7, total_tokens=18),
        model="gpt-oss:20b",
        system_fingerprint="fp_ollama",
    )


class FakeClient:
    def __init__(self, completion):
        self.completion = completion
        self.requests = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.requests.append(copy.deepcopy(kwargs))
        return self.completion


def _service(monkeypatch, content='{"instructions": []}', profile=None, env=None, **kwargs):
    for key in ("LLM_REQUEST_PROFILE", "LLM_EXTRA_BODY_JSON", "BENCHMARK_LLM_EXTRA_BODY_JSON"):
        monkeypatch.delenv(key, raising=False)
    for key, value in (env or {}).items():
        monkeypatch.setenv(key, value)
    service = LLMService(mode="openai_compatible", model="gpt-oss:20b", base_url="http://x/v1",
                         request_profile=profile, **kwargs)
    service.client = FakeClient(_completion(content))
    return service


def test_current_format_is_unchanged(monkeypatch):
    service = _service(monkeypatch, env={"LLM_EXTRA_BODY_JSON": '{"think": true}'})
    response, usage = service.llm_with_usage(SYSTEM, USER)

    assert service.client.requests == [{
        "messages": [
            {"role": "system", "content": SYSTEM + SUFFIX},
            {"role": "user", "content": USER},
        ],
        "model": "gpt-oss:20b",
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "max_tokens": 4096,
        "extra_body": {"think": True},
    }]
    assert response == {"instructions": []}
    assert usage == {"prompt": 11, "completion": 7, "total": 18}
    assert "request_profile" not in service.get_runtime_metadata()


def test_capture_does_not_change_the_request_or_the_result(monkeypatch):
    plain = _service(monkeypatch)
    captured = _service(monkeypatch)
    expected = plain.llm_with_usage(SYSTEM, USER)
    with capture_raw_responses() as records:
        result = captured.llm_with_usage(SYSTEM, USER)

    assert result == expected
    assert captured.client.requests == plain.client.requests
    assert len(records) == 1
    assert records[0]["finish_reason"] == "stop"
    assert records[0]["content"] == '{"instructions": []}'
    assert records[0]["request"]["params"]["max_tokens"] == 4096


def test_nothing_is_recorded_outside_the_capture_block(monkeypatch):
    service = _service(monkeypatch)
    with capture_raw_responses() as records:
        pass
    service.llm_with_usage(SYSTEM, USER)
    assert records == []


def test_capture_keeps_reasoning_and_failed_parses(monkeypatch):
    service = _service(monkeypatch)
    service.client = FakeClient(_completion('{"json_pred": {"runId": 1', finish_reason="length", reasoning="thinking..."))
    with capture_raw_responses() as records:
        response, _ = service.llm_with_usage(SYSTEM, USER)

    assert "error" in response
    assert records[0]["finish_reason"] == "length"
    assert records[0]["reasoning"] == "thinking..."
    assert records[0]["reasoning_field"] == "reasoning"
    assert records[0]["content"].startswith('{"json_pred"')
    assert records[0]["error"]


def test_benchmark_profile_reproduces_the_april_format(monkeypatch):
    service = _service(monkeypatch, profile="2026-04-28-benchmark", env={"LLM_EXTRA_BODY_JSON": '{"think": true}'})
    service.llm_with_usage(SYSTEM, USER)

    assert service.client.requests == [{
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": USER},
        ],
        "model": "gpt-oss:20b",
        "temperature": 0,
        "max_tokens": 4096,
        "extra_body": {"think": True},
    }]
    assert service.get_runtime_metadata()["request_profile"] == "2026-04-28-benchmark"


def test_benchmark_profile_keeps_lenient_json_extraction(monkeypatch):
    service = _service(monkeypatch, content='```json\n{"instructions": []}\n```', profile="2026-04-28-benchmark")
    assert service.llm(SYSTEM, USER) == {"instructions": []}


def test_humaniser_profile_reproduces_the_march_format(monkeypatch):
    service = _service(monkeypatch, content='{"natural_query": "Cambia..."}', profile="2026-03-humaniser",
                       env={"LLM_EXTRA_BODY_JSON": '{"think": true}'}, temperature=0.7)
    assert service.llm(SYSTEM, USER) == {"natural_query": "Cambia..."}

    assert service.client.requests == [{
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": USER},
        ],
        "model": "gpt-oss:20b",
        "temperature": 0.7,
        "response_format": {"type": "json_object"},
    }]


def test_humaniser_profile_parses_with_json_loads_only(monkeypatch):
    service = _service(monkeypatch, content='```json\n{"natural_query": "x"}\n```', profile="2026-03-humaniser")
    response = service.llm(SYSTEM, USER)
    assert "error" in response and response.get("natural_query", "") == ""


def test_explicit_max_tokens_is_kept_by_the_humaniser_profile(monkeypatch):
    service = _service(monkeypatch, content='{"natural_query": "x"}', profile="2026-03-humaniser", max_tokens=256)
    service.llm(SYSTEM, USER)
    assert service.client.requests[0]["max_tokens"] == 256


def test_profile_from_environment(monkeypatch):
    service = _service(monkeypatch, env={"LLM_REQUEST_PROFILE": "2026-04-28-benchmark"})
    assert service.request_profile == "2026-04-28-benchmark"


def test_unknown_profile_and_other_modes_are_rejected(monkeypatch):
    monkeypatch.delenv("LLM_REQUEST_PROFILE", raising=False)
    with pytest.raises(ValueError):
        LLMService(mode="openai_compatible", request_profile="1999", base_url="http://x/v1")
    with pytest.raises(ValueError):
        LLMService(mode="openai", api_key="k", request_profile="2026-04-28-benchmark")
