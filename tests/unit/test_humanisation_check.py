import numpy as np
import pandas as pd
import pytest

from benchmarks.comparisons.traceability import fingerprint_dict
from benchmarks.humanisation_check import compare, fidelity, provenance, rehumanise, run_paired, select_samples
from input_agent.src import dataset_generator_complexity, dataset_generator_completeness
from input_agent.src.models import Instruction
from tests.unit.test_comparison_metrics import base_config


# ---------------------------------------------------------------- selection

def test_selection_is_deterministic_and_per_level(monkeypatch):
    pools = {1: list(range(0, 50)), 16: list(range(50, 100)), 150: list(range(100, 150))}
    monkeypatch.setattr(select_samples, "level_pools", lambda axis: pools)

    first = select_samples.select(42, 25, {"complexity": [1, 16, 150]})
    again = select_samples.select(42, 25, {"complexity": [1, 16, 150]})
    only_16 = select_samples.select(42, 25, {"complexity": [16]})
    other_seed = select_samples.select(7, 25, {"complexity": [1, 16, 150]})

    assert first == again
    assert len(first) == 75
    for level, pool in pools.items():
        ids = [s["sample_idx"] for s in first if s["level"] == level]
        assert len(ids) == 25 and ids == sorted(ids) and set(ids) <= set(pool)
    assert [s for s in first if s["level"] == 16] == only_16  # a level's draw ignores the other levels
    assert first != other_seed


def test_selection_rejects_small_or_missing_levels(monkeypatch):
    monkeypatch.setattr(select_samples, "level_pools", lambda axis: {1: list(range(10))})
    with pytest.raises(ValueError):
        select_samples.select(42, 25, {"complexity": [1]})
    with pytest.raises(ValueError):
        select_samples.select(42, 5, {"complexity": [16]})


# ---------------------------------------------------------------- re-humanisation

class FakeLLM:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def llm(self, system_prompt, user_query):
        self.calls.append((system_prompt, user_query))
        return self.response


@pytest.mark.parametrize("axis", ["complexity", "completeness"])
def test_rehumanise_calls_the_original_humaniser_unchanged(axis):
    technical = {"operation": "SET", "path": "A001.tasks.T001.Duration", "value": 8}
    row = {"json_base": base_config()}
    if axis == "complexity":
        row["instruction_technical"] = technical
        direct = FakeLLM({"natural_query": "x"})
        dataset_generator_complexity.humanize_instruction(Instruction(**technical), row["json_base"], direct)
    else:
        row["instructions_technical"] = [technical, {"operation": "DELETE", "path": "A002.T_wait", "value": None}]
        direct = FakeLLM({"natural_query": "x"})
        dataset_generator_completeness.humanize_instruction_batch(
            [Instruction(**d) for d in row["instructions_technical"]], row["json_base"], direct
        )

    wrapped = FakeLLM({"natural_query": "Cambia la duración a 8 horas."})
    text, recorder = rehumanise.humanise(axis, row, wrapped)

    assert text == "Cambia la duración a 8 horas."
    assert wrapped.calls == direct.calls  # same system prompt and user turn as the generator builds
    assert (recorder.system_prompt, recorder.user_prompt) == direct.calls[0]


def test_rehumanise_keeps_the_generators_empty_result_on_errors():
    row = {"json_base": base_config(), "instruction_technical": {"operation": "DELETE", "path": "A001.T_wait", "value": None}}
    text, _ = rehumanise.humanise("complexity", row, FakeLLM({"error": "Could not parse"}))
    assert text == ""


def _raw(content, finish="stop", reasoning_field=None):
    return {"content": content, "finish_reason": finish, "reasoning_field": reasoning_field, "error": None}


def test_format_check():
    ok = rehumanise.format_check(_raw('{"natural_query": "Borra el tiempo de espera."}'), "Borra el tiempo de espera.")
    assert ok["ok"] and ok["problems"] == []

    fenced = rehumanise.format_check(_raw('```json\n{"natural_query": "x"}\n```'), "")
    assert not fenced["ok"] and fenced["parse_path"] == "fenced"

    thinking = rehumanise.format_check(_raw('<think>hmm</think>{"natural_query": "x"}'), "")
    assert not thinking["ok"] and "<think>" in thinking["reasoning_markers"]

    reasoning = rehumanise.format_check(_raw('{"natural_query": "x"}', reasoning_field="reasoning"), "x")
    assert not reasoning["ok"]

    truncated = rehumanise.format_check(_raw('{"natural_query": "x"}', finish="length"), "x")
    assert not truncated["ok"]

    extra_key = rehumanise.format_check(_raw('{"natural_query": "x", "note": "y"}'), "x")
    assert not extra_key["ok"] and extra_key["keys"] == ["natural_query", "note"]


# ---------------------------------------------------------------- fidelity

PROMPT_EXAMPLES = [
    ({"operation": "SET", "path": "A001.tasks.T002.Duration", "value": 8},
     "Mira, cambia a 8 horas la duración de la segunda tarea de la actividad uno."),
    ({"operation": "SET", "path": "A002.Start_disp", "value": 24},
     "Necesito que ajustes el retraso del primer inicio de la actividad 2 para que sea de 24 horas."),
    ({"operation": "SET", "path": "A003.tasks.T001.Requires_Shutdown", "value": True},
     "Anota por ahí que el primer paso de la tercera actividad ahora requiere parada de línea."),
    ({"operation": "APPEND", "path": "A002.Activity_Order_Before", "value": "A005"},
     "Por favor, añade una restricción para que la actividad 2 tenga que terminar antes de empezar la actividad 5."),
    ({"operation": "REMOVE_ITEM", "path": "A005.tasks.T007.Order_Before", "value": "T003"},
     "Quita la dependencia que obligaba a la tarea 7 a ejecutarse antes que la tarea 3 dentro de la actividad 5."),
    ({"operation": "SET", "path": "Simulation_period", "value": 17520},
     "Ajusta el horizonte de simulación a 17.520 horas."),
    ({"operation": "SET", "path": "A004.Team", "value": "TeamC"},
     "Asigna la cuadrilla C a la actividad A-004."),
    ({"operation": "DELETE", "path": "A012.tasks.T003.Order_Before", "value": None},
     "Borra las precedencias de la tarea 3 de la actividad 12."),
]


@pytest.mark.parametrize("instruction,text", PROMPT_EXAMPLES)
def test_fidelity_accepts_the_humaniser_prompt_examples(instruction, text):
    result = fidelity.check_request(text, [instruction])
    assert result["ok"], result["failures"]


@pytest.mark.parametrize("instruction,text,missing", [
    ({"operation": "SET", "path": "A001.tasks.T002.Duration", "value": 8},
     "Cambia la duración de la segunda tarea de la actividad uno.", "value"),
    ({"operation": "SET", "path": "A001.tasks.T002.Duration", "value": 8},
     "Cambia a 8 horas la duración de la segunda tarea de la actividad cuatro.", "activity"),
    ({"operation": "SET", "path": "A001.tasks.T002.Duration", "value": 8},
     "Cambia a 8 horas la duración de la actividad uno.", "task"),
    ({"operation": "SET", "path": "A002.Shift_duration", "value": 10},
     "Pon a 10 la actividad 2.", "parameter"),
])
def test_fidelity_flags_missing_mentions(instruction, text, missing):
    result = fidelity.check_request(text, [instruction])
    assert not result["ok"]
    assert missing in result["per_instruction"][0]["missing"]


def test_fidelity_flags_empty_requests_and_checks_every_instruction():
    assert fidelity.check_request("", [PROMPT_EXAMPLES[0][0]])["empty"]
    both = [PROMPT_EXAMPLES[0][0], PROMPT_EXAMPLES[1][0]]
    result = fidelity.check_request(PROMPT_EXAMPLES[0][1], both)
    assert not result["ok"] and len(result["failures"]) == 1 and result["failures"][0].startswith("#2")


def test_spanish_number_words():
    assert "veintiuna" in fidelity.cardinal_words(21)
    assert "ciento cincuenta" in fidelity.cardinal_words(150)
    assert "doscientas" in fidelity.cardinal_words(200)
    assert "decimotercera" in fidelity.ordinal_words(13)
    assert "primer" in fidelity.ordinal_words(1)


# ---------------------------------------------------------------- comparison

def test_mcnemar_exact():
    first = np.array([0] * 6 + [1] * 10)
    second = np.array([1] * 6 + [1] * 10)
    test = compare.mcnemar_exact(first, second)
    assert (test["first_only"], test["second_only"]) == (0, 6)
    assert test["p"] == pytest.approx(2 * 0.5 ** 6)
    assert compare.mcnemar_exact(first, first)["p"] == 1.0


def test_bootstrap_ci():
    constant = np.full(20, 0.5)
    assert compare.bootstrap_ci(constant, np.zeros(20), 1, 500, 0.05) == pytest.approx((0.5, 0.5, 0.5))
    diff = np.r_[np.zeros(10), np.ones(10)]
    strata = np.r_[np.zeros(10), np.ones(10)]
    mean, lo, hi = compare.bootstrap_ci(diff, strata, 1, 500, 0.05)
    assert mean == 0.5 and lo == hi == 0.5  # stratified: each level resampled within itself
    assert compare.bootstrap_ci(diff, np.zeros(20), 3, 2000, 0.05) == compare.bootstrap_ci(diff, np.zeros(20), 3, 2000, 0.05)


def test_prompt_token_check_statuses():
    df = pd.DataFrame({
        "axis": ["complexity"] * 4, "level": [1] * 4, "sample_idx": [0, 1, 2, 3],
        "prompt_A": [2740, 2740, 0, 2740], "prompt_B": [2740, 2757, 2740, 5480], "prompt_C": [2750] * 4,
        "attempts_A": [1, 1, 1, 1], "attempts_B": [1, 1, 1, 2],
    })
    assert compare.prompt_token_check(df)["status"].tolist() == ["match", "mismatch", "unavailable", "retries_differ"]


# ---------------------------------------------------------------- provenance and configuration

def test_sample_timeout_is_recovered_from_the_fingerprint():
    summary = {
        "dataset_sha256": "abc", "selected_approaches": ["planner_executor", "vanilla"],
        "selected_complexities": [1, 16], "samples_per_complexity": 50, "model": {"model_name": "gpt-oss:20b"},
        "master_seed": 42,
        "fairness": {"shared_throttle": 0.35, "shared_max_retries": 2, "shared_backoff_base_s": 0.8,
                     "shared_jitter_s": 0.2, "max_workers_per_approach": 4},
    }
    summary["config_fingerprint_sha256"] = fingerprint_dict({
        "axis": "complexity", "dataset_sha256": "abc", "selected_approaches": ["planner_executor", "vanilla"],
        "selected_complexities": [1, 16], "samples_per_complexity": 50, "llm": {"model_name": "gpt-oss:20b"},
        "fairness": {"min_interval_s": 0.35, "max_retries": 2, "backoff_base_s": 0.8, "jitter_s": 0.2,
                     "max_workers": 4, "sample_timeout_s": 600.0, "master_seed": 42},
    })
    assert provenance.recover_sample_timeout(summary, "complexity") == {"value": 600.0, "fingerprint_matches": True}
    summary["config_fingerprint_sha256"] = "0" * 64
    assert provenance.recover_sample_timeout(summary, "complexity")["value"] is None


def test_new_run_uses_the_runner_defaults():
    config = run_paired.new_run_config("gpt-oss:20b", provenance.ORIGINAL_REQUEST_PROFILE, max_workers=1)
    assert config == {
        "provider": "openai_compatible", "model_name": "gpt-oss:20b", "num_ctx": None,
        "request_profile": "2026-04-28-benchmark",
        "extra_body": None, "temperature": 0.0, "seed": None, "llm_timeout_s": 600.0, "max_tokens_effective": 4096,
        "min_interval_s": 0.35, "max_retries": 2, "backoff_base_s": 0.8, "jitter_s": 0.2, "max_workers": 1,
        "sample_timeout_s": 600.0, "master_seed": 42, "legacy_structural_keys": False,
    }


def _original(**changes):
    base = run_paired.new_run_config("gpt-oss:20b", provenance.ORIGINAL_REQUEST_PROFILE, max_workers=4)
    return {**base, "sample_timeout_recovered_from_fingerprint": True, **changes}


def test_config_comparison_flags_mismatches_and_declared_deviations():
    new = run_paired.new_run_config("gpt-oss:20b", provenance.ORIGINAL_REQUEST_PROFILE, max_workers=1)
    rows = {r["setting"]: r for r in run_paired.compare_configs(new, {"complexity": _original(min_interval_s=1.0)})}
    assert rows["min_interval_s"]["match"] is False and rows["min_interval_s"]["declared_deviation"] is None
    assert rows["max_workers"]["match"] is False and rows["max_workers"]["declared_deviation"]
    assert rows["seed"]["match"] is True and rows["extra_body"]["match"] is True  # None is a stated value

    with_extra_body = {**new, "extra_body": {"reasoning_effort": "low"}}
    rows = {r["setting"]: r for r in run_paired.compare_configs(with_extra_body, {"complexity": _original()})}
    assert rows["extra_body"]["match"] is False and rows["extra_body"]["declared_deviation"] is None

    unrecovered = _original(sample_timeout_s=None, sample_timeout_recovered_from_fingerprint=False)
    rows = {r["setting"]: r for r in run_paired.compare_configs(new, {"complexity": unrecovered})}
    assert rows["sample_timeout_s"]["match"] is None


@pytest.mark.parametrize("requested,parallel,expected", [
    (None, "1", 1), (None, "4", 4), (1, "4", 1), (1, None, 1),
])
def test_workers_never_exceed_the_server_parallelism(requested, parallel, expected):
    assert run_paired.resolve_workers(requested, parallel) == expected


@pytest.mark.parametrize("requested,parallel", [(4, "1"), (None, None), (4, None), (0, "2")])
def test_workers_that_could_queue_are_rejected(requested, parallel):
    with pytest.raises(SystemExit):
        run_paired.resolve_workers(requested, parallel)


def test_original_config_records_extra_body_as_undefined():
    fairness = {"shared_throttle": 0.35, "shared_max_retries": 2, "shared_backoff_base_s": 0.8,
                "shared_jitter_s": 0.2, "max_workers_per_approach": 4}
    summary = {
        "run_id": "r", "timestamp_utc": "t", "dataset_sha256": "abc", "selected_approaches": ["planner_executor"],
        "selected_complexities": [1], "samples_per_complexity": 50, "master_seed": 42, "fairness": fairness,
        "model": {"provider": "openai_compatible", "llm_mode": "openai_compatible", "model_name": "gpt-oss:20b",
                  "model_version": None, "base_url": None, "temperature": 0.0, "seed": None, "timeout_s": 600.0},
        "config_fingerprint_sha256": "0" * 64,
    }
    cfg = provenance.original_run_config("complexity", {"summary": summary})
    assert "extra_body" in cfg and cfg["extra_body"] is None
    assert "LLM_EXTRA_BODY_JSON" not in cfg["not_logged"]


def _paired(**columns):
    n = len(next(iter(columns.values())))
    base = {"axis": ["complexity"] * n, "level": [1] * n}
    for c in compare.CONDITIONS:
        base.setdefault(f"timeout_{c}", [False] * n)
        base.setdefault(f"completion_{c}", [100] * n)
    base.update(columns)
    return pd.DataFrame(base)


def test_timeouts_are_counted_per_condition_and_level():
    df = _paired(level=[1, 1, 5], timeout_A=[True, False, False], timeout_C=[False, True, True])
    table = compare.timeouts_by_level(df).set_index(["axis", "level"])
    assert table.loc[("all", "all"), ["A", "B", "C"]].tolist() == [1, 0, 2]
    assert table.loc[("complexity", "5"), ["A", "B", "C"]].tolist() == [0, 0, 1]
    assert compare._is_timeout({"error_blob": "Request timed out."})
    assert compare._is_timeout({"is_timeout": True}) and not compare._is_timeout({"error_blob": ""})


def test_completion_tokens_by_level_give_median_and_range():
    df = _paired(completion_A=[200, 300, 400], completion_B=[220, 330, 400])
    row = compare.completion_by_level(df).iloc[0]
    assert (row["A_median"], row["A_min"], row["A_max"]) == (300, 200, 400)
    assert (row["B_median"], row["B_min"], row["B_max"]) == (330, 220, 400)
    assert row["B_minus_A_median"] == 20 and row["B_over_A_median_ratio"] == 1.1


def test_latency_and_tokens_are_not_effect_metrics():
    assert set(compare.EFFECT_METRICS) == {"exact_match_pct", "f1_micro", "omission_rate", "collateral_rate"}
    assert not any("latency" in m for m in {**compare.EFFECT_METRICS, **compare.CONTROL_METRICS})


# ---------------------------------------------------------------- derived model, context and server

BLOB = "a" * 64
BASE_SHOW = {
    "modelfile": f"# Modelfile\nFROM /usr/share/ollama/.ollama/models/blobs/sha256-{BLOB}\nTEMPLATE ...",
    "template": "<|start|>system<|message|>Current date: {{ currentDate }}",
    "parameters": "temperature 1",
    "details": {"family": "gptoss", "parameter_size": "20.9B", "quantization_level": "MXFP4", "parent_model": ""},
    "model_info": {"gptoss.context_length": 131072},
}


def _derived_show(**changes):
    derived = {**BASE_SHOW, "parameters": "temperature 1\nnum_ctx 32768",
               "details": {**BASE_SHOW["details"], "parent_model": "gpt-oss:20b"}}
    derived.update(changes)
    return derived


@pytest.mark.parametrize("changes,ok", [
    ({}, True),
    ({"template": "other template"}, False),
    ({"modelfile": "FROM /blobs/sha256-" + "b" * 64}, False),
    ({"parameters": "temperature 0.5\nnum_ctx 32768"}, False),
    ({"parameters": "temperature 1"}, False),
    ({"system": "You are..."}, False),
])
def test_derivation_check(monkeypatch, changes, ok):
    from benchmarks.humanisation_check import ollama_api
    shows = {"gpt-oss:20b": BASE_SHOW, "gpt-oss-20b-ctx32k": _derived_show(**changes)}
    monkeypatch.setattr(ollama_api, "show", lambda url, name: shows[name])
    result = ollama_api.derivation_check("http://x", "gpt-oss:20b", "gpt-oss-20b-ctx32k")
    assert result["ok"] is ok
    if ok:
        assert result["num_ctx"] == 32768 and result["parameters_only_in_derived"] == [("num_ctx", "32768")]


@pytest.mark.parametrize("status", [
    {"fully_on_gpu": True, "context_length": 4096},
    {"fully_on_gpu": True, "context_length": None},
    {"fully_on_gpu": False, "context_length": 32768},
])
def test_loaded_model_needs_gpu_and_context(status):
    with pytest.raises(SystemExit):
        run_paired.check_loaded(status, "gpt-oss-20b-ctx32k", skip_gpu_check=False)


def test_loaded_model_with_enough_context_passes():
    run_paired.check_loaded({"fully_on_gpu": True, "context_length": 32768}, "m", skip_gpu_check=False)


def test_derived_model_and_workers_are_declared_deviations():
    new = run_paired.new_run_config("gpt-oss-20b-ctx32k", provenance.ORIGINAL_REQUEST_PROFILE, max_workers=2, num_ctx=32768)
    original = _original(num_ctx="not logged")
    rows = {r["setting"]: r for r in run_paired.compare_configs(new, {"complexity": original}, {"model_name": "derived"})}
    assert rows["model_name"]["declared_deviation"] == "derived"
    assert rows["max_workers"]["declared_deviation"]
    assert rows["num_ctx"]["match"] is None  # informational: not logged for the original run
    assert not [r for r in rows.values() if r["match"] is False and not r["declared_deviation"]]


def test_server_environment_merges_collected_and_stated():
    record = run_paired.server_environment(
        {"env_effective": {"OLLAMA_NUM_PARALLEL": "2", "OLLAMA_KV_CACHE_TYPE": "f16"}},
        ["OLLAMA_KV_CACHE_TYPE=q8_0", "OLLAMA_FLASH_ATTENTION=1"],
    )
    assert record["effective"] == {"OLLAMA_NUM_PARALLEL": "2", "OLLAMA_KV_CACHE_TYPE": "f16", "OLLAMA_FLASH_ATTENTION": "1"}
    assert record["disagreements"] == {"OLLAMA_KV_CACHE_TYPE": {"collected": "f16", "stated": "q8_0"}}


# ---------------------------------------------------------------- fidelity warnings

SAMPLE_211 = [
    {"operation": "SET", "path": "runId", "value": 3952},
    {"operation": "SET", "path": "A001.Start_disp", "value": 105},
    {"operation": "APPEND", "path": "A001.tasks.T006.Order_Before", "value": "T005"},
    {"operation": "REMOVE_ITEM", "path": "A002.tasks.T005.Order_Before", "value": "T006"},
]


def test_direction_and_unit_warnings_on_sample_211_like_text():
    original = ("Pon el identificador de ejecución a 3952 y ajusta el desplazamiento inicial de la actividad 1 a 105, "
                "añade que la tarea 6 de la actividad 1 debe terminar antes de que empiece la tarea 5 de la misma, y quita "
                "la regla que obligaba a que la tarea 5 de la actividad 2 terminara antes de empezar la tarea 6 de la actividad 2.")
    inverted = ("Cambia el identificador de ejecución a 3952, retrasa 105 minutos el inicio de la actividad 1, haz que la "
                "tarea 6 de la actividad 1 termine antes de que empiece la tarea 5, y elimina la regla por la que la tarea 6 "
                "de la actividad 2 terminaba antes que la 5.")
    clean = fidelity.check_request(original, SAMPLE_211)
    assert clean["direction_warnings"] == [] and clean["unit_warnings"] == []

    warned = fidelity.check_request(inverted, SAMPLE_211)
    assert warned["ok"]  # warnings never flag a request
    assert len(warned["direction_warnings"]) == 1 and warned["direction_warnings"][0].startswith("#4 ")
    assert warned["unit_warnings"] == ["#2 Start_disp = 105: '105 minutos'"]


@pytest.mark.parametrize("text,warn", [
    ("Haz que la tarea 5 de la actividad 3 dependa de la tarea 6.", False),
    ("Haz que la tarea 6 de la actividad 3 dependa de la tarea 5.", True),
    ("La tarea 6 de la actividad 3 va antes que la tarea 5.", False),
    ("La tarea 5 de la actividad 3 va después de la tarea 6.", False),
])
def test_direction_warning_reads_forward_and_backward_cues(text, warn):
    instr = {"operation": "APPEND", "path": "A003.tasks.T006.Order_Before", "value": "T005"}
    assert bool(fidelity.direction_warning(fidelity.normalize(text), instr)) is warn


@pytest.mark.parametrize("instruction,text,expected", [
    ({"path": "A001.tasks.T002.Duration", "value": 8}, "a 8 horas", []),
    ({"path": "A001.tasks.T002.Duration", "value": 8}, "a 8 minutos", ["Duration = 8: '8 minutos'"]),
    ({"path": "A001.Team members", "value": 4}, "a 4 horas", ["Team members = 4: '4 horas'"]),
    ({"path": "A001.tasks.T002.Cost_per_hour", "value": 300}, "en 300 euros", ["Cost_per_hour = 300: '300 euros'"]),
    ({"path": "A001.T_period", "value": 168}, "cada 168 dias", ["T_period = 168: '168 dias'"]),
])
def test_unit_warnings(instruction, text, expected):
    assert fidelity.unit_warnings(fidelity.normalize(text), {"operation": "SET", **instruction}) == expected


# ---------------------------------------------------------------- adjudication

def test_config_diff_lists_leaf_differences():
    gt = {"A001": {"T_wait": 9, "tasks": {"T005": {"Order_Before": []}}}, "runId": 1}
    pred = {"A001": {"T_wait": 5, "tasks": {"T005": {"Order_Before": ["T006"]}}}, "runId": 1, "extra": 2}
    assert compare.config_diff(gt, pred) == [
        "`A001.T_wait`: GT 9 / prediction 5",
        '`A001.tasks.T005.Order_Before`: GT [] / prediction ["T006"]',
        "`extra`: not in the GT (prediction 2)",
    ]


def _discordant_fixture(monkeypatch):
    base, gt = base_config(), base_config()
    gt["A001"]["T_wait"] = 9
    monkeypatch.setattr(compare, "load_dataset", lambda axis: {211: {"json_base": base, "json_gt": gt}})
    pred = base_config()
    pred["A001"]["T_wait"] = 7
    tech = [{"operation": "SET", "path": "A001.T_wait", "value": 9}]
    details = {
        ("B", "completeness", 211): ({"instruction_technical": tech, "instruction_natural": "orig", "exact_match": 1.0,
                                      "planner_instructions": tech}, None),
        ("C", "completeness", 211): ({"instruction_technical": tech, "instruction_natural": "new", "exact_match": 0.0,
                                      "planner_instructions": [{**tech[0], "value": 7}]}, {"json_pred": pred}),
    }
    discordant = pd.DataFrame({"axis": ["completeness"], "level": [5], "sample_idx": [211], "em_B": [1.0], "em_C": [0.0]})
    return discordant, details


def test_discordant_pairs_file_keeps_filled_causes(monkeypatch, tmp_path):
    discordant, details = _discordant_fixture(monkeypatch)
    path = tmp_path / "discordant_pairs_planner_executor.md"
    compare.write_discordant_pairs(path, discordant, details, None, {}, "planner_executor")
    text = path.read_text(encoding="utf-8")
    row = "| completeness | 5 | 211 | 1 | 0 |  |"
    assert row in text
    assert "`A001.T_wait`: GT 9 / prediction 7" in text and "- none (exact match)" in text
    assert compare.read_causes(path) == {}

    path.write_text(text.replace(row, "| completeness | 5 | 211 | 1 | 0 | Humanisation |"), encoding="utf-8")
    causes = compare.read_causes(path)
    assert causes == {("completeness", 211): "humanisation"}
    compare.write_discordant_pairs(path, discordant, details, None, causes, "planner_executor")
    assert compare.read_causes(path) == causes


def test_invalid_cause_is_rejected(tmp_path):
    path = tmp_path / "d.md"
    path.write_text("| axis | level | sample_idx | EM B | EM C | cause |\n|---|---|---|---|---|---|\n"
                    "| complexity | 16 | 752 | 1 | 0 | prompt |\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        compare.read_causes(path)
