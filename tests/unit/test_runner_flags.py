"""Runner flags --sample-ids, --instruction-override, --log-raw-responses and
--request-profile are opt-in: without them the runners behave as before."""

import importlib
import json
import os
from types import SimpleNamespace

import pytest

from benchmarks.comparisons.sample_overrides import (
    apply_instruction_overrides,
    load_instruction_overrides,
    load_sample_ids,
    restrict_to_sample_ids,
)
from benchmarks.comparisons.traceability import fingerprint_dict, sha256_file
from input_agent.src.llm import _record_raw_call
from tests.unit.test_comparison_metrics import base_config, gt_with_edits

AXES = {
    "complexity": {
        "module": "benchmarks.comparisons.benchmark_compare_complexity",
        "level_field": "complexity_nodes", "text_key": "instruction_natural", "technical_key": "instruction_technical",
        "levels_key": "selected_complexities", "samples_key": "samples_per_complexity", "filter_kw": "complexity_filter",
    },
    "completeness": {
        "module": "benchmarks.comparisons.benchmark_compare_completeness",
        "level_field": "completeness", "text_key": "instructions_natural", "technical_key": "instructions_technical",
        "levels_key": "selected_completeness", "samples_key": "samples_per_completeness", "filter_kw": "completeness_filter",
    },
}
PREVIOUS_DEFAULTS = {
    "output": None, "max_samples": None, "min_interval": 0.35, "max_retries": 2, "backoff_base": 0.8,
    "jitter": 0.2, "max_workers": 4, "llm_mode": "auto", "llm_model": None, "llm_model_version": None,
    "llm_base_url": None, "llm_temperature": 0.0, "llm_seed": None, "llm_timeout": 600.0, "run_tag": None,
    "master_seed": 42, "approach": "both", "sample_timeout": 600.0, "legacy_structural_keys": False,
}
NEW_FLAGS = {"sample_ids": None, "instruction_override": None, "log_raw_responses": False, "request_profile": None}


@pytest.fixture
def restore_environ():
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)


def _technical(axis, idx):
    instr = {"operation": "SET", "path": "A001.T_wait", "value": 9 + idx}
    return instr if axis == "complexity" else [instr]


def _dataset(tmp_path, axis, levels=(1, 1, 2, 2)):
    spec = AXES[axis]
    rows = []
    for idx, level in enumerate(levels):
        rows.append({
            spec["level_field"]: level,
            "activities_count": 2,
            "tasks_per_act_count": 1,
            "json_base": base_config(),
            spec["technical_key"]: _technical(axis, idx),
            spec["text_key"]: f"original request {idx}",
            "json_gt": gt_with_edits(),
        })
    path = tmp_path / f"{axis}.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path, rows


def _run(runner, axis, dataset, out, monkeypatch, seen, **flags):
    spec = AXES[axis]

    def fake_planner_executor(example):
        seen.append(example)
        _record_raw_call("openai_compatible", SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="{}", model_extra={}), finish_reason="stop")],
            usage=None, model="m", system_fingerprint=None,
        ))
        return {"json_pred": example["json_gt"], "planner_instructions": [], "validation_errors": [],
                "error_blob": "", "token_usage": {"prompt": 3, "completion": 2, "total": 5}}

    monkeypatch.setattr(runner, "run_planner_executor_once", fake_planner_executor)
    runner.run_benchmark(
        dataset_path=str(dataset), output_path=str(out), max_samples=None,
        **{spec["samples_key"]: None, spec["filter_kw"]: None},
        min_interval_s=0.0, max_retries=2, backoff_base_s=0.8, jitter_s=0.2, approach="planner_executor",
        max_workers=1, llm_mode="openai_compatible", llm_temperature=0.0, llm_seed=None, llm_timeout_s=600.0,
        llm_model_name="gpt-oss:20b", llm_model_version=None, llm_base_url=None, run_tag=None, master_seed=42,
        sample_timeout_s=600.0, **flags,
    )
    return json.loads(out.read_text(encoding="utf-8"))


@pytest.mark.parametrize("axis", AXES)
def test_parser_defaults_are_unchanged(axis):
    runner = importlib.import_module(AXES[axis]["module"])
    args = vars(runner.build_arg_parser().parse_args([]))
    assert {k: args[k] for k in PREVIOUS_DEFAULTS} == PREVIOUS_DEFAULTS
    assert {k: args[k] for k in NEW_FLAGS} == NEW_FLAGS


@pytest.mark.parametrize("axis", AXES)
def test_run_without_flags_is_unchanged(axis, tmp_path, monkeypatch, restore_environ):
    spec = AXES[axis]
    runner = importlib.import_module(spec["module"])
    dataset, rows = _dataset(tmp_path, axis)
    os.environ["LLM_REQUEST_PROFILE"] = "2026-03-humaniser"  # must not leak into a run without the flag
    seen = []
    result = _run(runner, axis, dataset, tmp_path / "out.json", monkeypatch, seen)

    assert sorted(ex[spec["text_key"]] for ex in seen) == sorted(r[spec["text_key"]] for r in rows)
    assert all(ex["json_gt"] == gt_with_edits() for ex in seen)
    assert "LLM_REQUEST_PROFILE" not in os.environ

    summary = result["summary"]
    assert not {"sample_ids_file", "instruction_override_file", "request_profile"} & set(summary)
    assert all("raw_calls" not in r for r in result["detailed_results"])
    expected_fingerprint = fingerprint_dict({
        "axis": axis,
        "dataset_sha256": sha256_file(dataset),
        "selected_approaches": ["planner_executor"],
        spec["levels_key"]: [1, 2],
        spec["samples_key"]: None,
        "llm": summary["model"],
        "legacy_structural_keys": False,
        "fairness": {"min_interval_s": 0.0, "max_retries": 2, "backoff_base_s": 0.8, "jitter_s": 0.2,
                     "max_workers": 1, "sample_timeout_s": 600.0, "master_seed": 42},
    })
    assert summary["config_fingerprint_sha256"] == expected_fingerprint
    assert result["summary"]["approaches"]["planner_executor"]["exact_match_pct"] == 100.0


@pytest.mark.parametrize("axis", AXES)
def test_sample_ids_and_override_change_only_the_request(axis, tmp_path, monkeypatch, restore_environ):
    spec = AXES[axis]
    runner = importlib.import_module(spec["module"])
    dataset, rows = _dataset(tmp_path, axis)
    ids = tmp_path / "ids.json"
    ids.write_text(json.dumps({"samples": [
        {"axis": axis, "level": 1, "sample_idx": 1},
        {"axis": axis, "level": 2, "sample_idx": 2},
        {"axis": "other", "level": 9, "sample_idx": 99},
    ]}), encoding="utf-8")
    overrides = tmp_path / "requests.jsonl"
    overrides.write_text("\n".join(json.dumps({
        "axis": axis, "sample_idx": i, "instruction_technical": rows[i][spec["technical_key"]],
        "instruction_natural": f"new request {i}",
    }) for i in (1, 2)), encoding="utf-8")

    seen = []
    result = _run(runner, axis, dataset, tmp_path / "out.json", monkeypatch, seen,
                  sample_ids_path=str(ids), instruction_override_path=str(overrides),
                  log_raw_responses=True, request_profile="2026-04-28-benchmark")

    assert sorted(ex[spec["text_key"]] for ex in seen) == ["new request 1", "new request 2"]
    for ex in seen:
        idx = int(ex[spec["text_key"]].split()[-1])
        original = {k: v for k, v in rows[idx].items() if k != spec["text_key"]}
        assert {k: v for k, v in ex.items() if k != spec["text_key"]} == original
    assert sorted(r["sample_idx"] for r in result["detailed_results"]) == [1, 2]
    assert all(r["raw_calls"][0]["finish_reason"] == "stop" for r in result["detailed_results"])
    summary = result["summary"]
    assert summary["request_profile"] == "2026-04-28-benchmark"
    assert summary["sample_ids_file"]["sha256"] == sha256_file(ids)
    assert summary["instruction_override_file"]["sha256"] == sha256_file(overrides)
    assert os.environ["LLM_REQUEST_PROFILE"] == "2026-04-28-benchmark"


def test_unknown_sample_id_and_level_mismatch_are_rejected():
    grouped = {1: [(0, {}), (1, {})], 2: [(2, {})]}
    assert {lvl: [i for i, _ in s] for lvl, s in restrict_to_sample_ids(grouped, {1: 1, 2: None}).items()} == {1: [1], 2: [2]}
    with pytest.raises(ValueError, match="not in the dataset"):
        restrict_to_sample_ids(grouped, {7: None})
    with pytest.raises(ValueError, match="level differs"):
        restrict_to_sample_ids(grouped, {2: 1})


def test_override_must_match_the_technical_instruction(tmp_path):
    grouped = {1: [(0, {"instruction_natural": "a", "instruction_technical": {"path": "x"}})]}
    good = {0: {"sample_idx": 0, "instruction_natural": "b", "instruction_technical": {"path": "x"}}}
    bad = {0: {"sample_idx": 0, "instruction_natural": "b", "instruction_technical": {"path": "y"}}}
    replaced = apply_instruction_overrides(grouped, good, "instruction_natural", "instruction_technical")
    assert replaced[1][0][1] == {"instruction_natural": "b", "instruction_technical": {"path": "x"}}
    assert grouped[1][0][1]["instruction_natural"] == "a"  # the dataset example is not modified
    with pytest.raises(ValueError, match="does not match"):
        apply_instruction_overrides(grouped, bad, "instruction_natural", "instruction_technical")
    with pytest.raises(ValueError, match="no override"):
        apply_instruction_overrides(grouped, {}, "instruction_natural", "instruction_technical")


def test_loaders_filter_by_axis(tmp_path):
    ids = tmp_path / "ids.json"
    ids.write_text(json.dumps([{"axis": "complexity", "sample_idx": 3, "level": 16}, {"axis": "completeness", "sample_idx": 4}]))
    assert load_sample_ids(ids, "complexity") == {3: 16}
    reqs = tmp_path / "r.jsonl"
    reqs.write_text(json.dumps({"axis": "completeness", "sample_idx": 4, "instruction_natural": "t"}) + "\n")
    assert list(load_instruction_overrides(reqs, "completeness")) == [4]
    with pytest.raises(ValueError):
        load_instruction_overrides(reqs, "complexity")
