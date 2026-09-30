"""
Configuration of the original gpt-oss:20b run (condition A) and where each
value lives in the code.

The original runner manifests were overwritten by the bootstrap manifests,
so the run configuration is read from the ``summary`` block of the logged
results. ``sample_timeout_s`` is not in the summary: it is recovered by
recomputing the run's config fingerprint for candidate values, which also
confirms every other fairness setting and the master seed.

The context length the server used is not logged either. A lower bound comes
from the logged tokens: Ollama cannot evaluate a prompt longer than its
context (it truncates it) nor generate past it, so num_ctx >= the largest
prompt + completion of any single-attempt call.

    python -m benchmarks.humanisation_check.provenance
prints both, plus the P-E prompt-token spread per level and a time estimate.
"""

from __future__ import annotations

import argparse
import json
import statistics
from typing import Any, Dict, Iterable, List, Optional

from benchmarks.comparisons.traceability import fingerprint_dict
from benchmarks.humanisation_check.common import AXES, PLANNER, REPO_ROOT, a_results_path, load_json

MAX_TOKENS_DEFAULT = 4096        # LLMService: self.max_tokens or 4096
TRUNC_THRESHOLD = 4090           # benchmarks/metrics/output_truncation.py
SAMPLE_TIMEOUT_CANDIDATES = (600.0, 120.0, 300.0, 900.0, 1200.0, 1800.0, 3600.0)

# Both gpt-oss:20b runs (28 April 2026, 14:32 and 17:52 UTC) used llm.py as of
# a224cae: the bootstrap manifest written between them records HEAD a224cae,
# and the next llm.py commits are of 29 April. That version sent
# openai_compatible requests without the JSON suffix and without
# response_format; fb1d634 (29 April) added both. The logged P-E prompt
# tokens agree: rendered with the harmony template, the plain planner prompt
# reproduces all 1 550 of them up to a constant, while the suffix would add
# 17 tokens.
ORIGINAL_REQUEST_PROFILE = "2026-04-28-benchmark"

_LEVELS_KEY = {"complexity": "selected_complexities", "completeness": "selected_completeness"}
_SAMPLES_KEY = {"complexity": "samples_per_complexity", "completeness": "samples_per_completeness"}


def _locate(relpath: str, needle: str) -> str:
    path = REPO_ROOT / relpath
    try:
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if needle in line:
                return f"{relpath}:{n}"
    except OSError:
        pass
    return f"{relpath} (not found: {needle!r})"


def recover_sample_timeout(summary: dict, axis: str) -> Dict[str, Any]:
    """Find the sample_timeout_s that reproduces the logged config fingerprint."""
    levels_key, samples_key = _LEVELS_KEY[axis], _SAMPLES_KEY[axis]
    fairness = summary["fairness"]
    for timeout in SAMPLE_TIMEOUT_CANDIDATES:
        for with_legacy_key in (False, True):
            payload = {
                "axis": axis,
                "dataset_sha256": summary["dataset_sha256"],
                "selected_approaches": summary["selected_approaches"],
                levels_key: summary[levels_key],
                samples_key: summary[samples_key],
                "llm": summary["model"],
                "fairness": {
                    "min_interval_s": fairness["shared_throttle"],
                    "max_retries": fairness["shared_max_retries"],
                    "backoff_base_s": fairness["shared_backoff_base_s"],
                    "jitter_s": fairness["shared_jitter_s"],
                    "max_workers": fairness["max_workers_per_approach"],
                    "sample_timeout_s": timeout,
                    "master_seed": summary["master_seed"],
                },
            }
            if with_legacy_key:
                payload["legacy_structural_keys"] = False
            if fingerprint_dict(payload) == summary["config_fingerprint_sha256"]:
                return {"value": timeout, "fingerprint_matches": True}
    return {"value": None, "fingerprint_matches": False}


def original_run_config(axis: str, a_json: Optional[dict] = None) -> Dict[str, Any]:
    """Settings of condition A for ``axis``, from the logged summary."""
    a_json = a_json if a_json is not None else load_json(a_results_path(axis))
    s = a_json["summary"]
    model, fairness = s["model"], s["fairness"]
    runtime = (s.get("llm") or {}).get("runtime") or {}
    timeout = recover_sample_timeout(s, axis)
    return {
        "run_id": s["run_id"],
        "timestamp_utc": s["timestamp_utc"],
        "dataset_sha256": s["dataset_sha256"],
        "provider": model["provider"],
        "llm_mode": model["llm_mode"],
        "model_name": model["model_name"],
        "model_version": model["model_version"],
        "base_url": model["base_url"],
        "temperature": model["temperature"],
        "seed": model["seed"],
        "llm_timeout_s": model["timeout_s"],
        "max_tokens": runtime.get("max_tokens"),
        "max_tokens_effective": runtime.get("max_tokens") or MAX_TOKENS_DEFAULT,
        "min_interval_s": fairness["shared_throttle"],
        "max_retries": fairness["shared_max_retries"],
        "backoff_base_s": fairness["shared_backoff_base_s"],
        "jitter_s": fairness["shared_jitter_s"],
        "max_workers": fairness["max_workers_per_approach"],
        "master_seed": s["master_seed"],
        "samples_per_level": s[_SAMPLES_KEY[axis]],
        "sample_timeout_s": timeout["value"],
        "sample_timeout_recovered_from_fingerprint": timeout["fingerprint_matches"],
        "request_profile": ORIGINAL_REQUEST_PROFILE,
        "code_commit": "a224cae (HEAD recorded by the bootstrap manifest written between the two runs)",
        "extra_body": None,
        "extra_body_source": "LLM_EXTRA_BODY_JSON was not defined in the original run (author's statement; not logged)",
        "num_ctx": "not logged (>= 17485: longest untruncated prompt of the gpt-oss runs)",
        "config_fingerprint_sha256": s["config_fingerprint_sha256"],
        "not_logged": [
            "Ollama version", "model digest", "server context length (OLLAMA_CONTEXT_LENGTH / num_ctx)",
            "OLLAMA_NUM_PARALLEL", "GPU",
        ],
    }


def code_locations() -> List[Dict[str, str]]:
    """Where each run setting is defined; the new run uses the same code paths."""
    llm = "input_agent/src/llm.py"
    cx = "benchmarks/comparisons/benchmark_compare_complexity.py"
    nodes = "input_agent/nodes.py"
    return [
        {"setting": "mode openai_compatible", "where": _locate(cx, "or \"openai_compatible\"")},
        {"setting": "request format of the original run (profile 2026-04-28-benchmark)", "where": _locate(llm, '"2026-04-28-benchmark": {')},
        {"setting": "max_tokens 4096 (max_tokens None)", "where": _locate(llm, 'request_kwargs["max_tokens"] = self.max_tokens or 4096')},
        {"setting": "response_format json_object (current format; dropped by the profile)", "where": _locate(llm, '"response_format": {"type": "json_object"}')},
        {"setting": "JSON-only suffix (current format; dropped by the profile)", "where": _locate(llm, "IMPORTANT: Respond ONLY with valid JSON object")},
        {"setting": "extra_body from LLM_EXTRA_BODY_JSON", "where": _locate(llm, 'os.getenv("LLM_EXTRA_BODY_JSON")')},
        {"setting": "temperature 0.0 (greedy), no top_p/top_k sent", "where": _locate(cx, '"--llm-temperature", type=float, default=0.0')},
        {"setting": "seed None", "where": _locate(cx, '"--llm-seed", type=int, default=None')},
        {"setting": "planner LLM from env (temperature, seed, timeout, model, URL)", "where": _locate(nodes, "def get_llm")},
        {"setting": "request timeout 600 s", "where": _locate(cx, '"--llm-timeout", type=float, default=600.0')},
        {"setting": "sample (firewall) timeout 600 s", "where": _locate(cx, '"--sample-timeout"')},
        {"setting": "throttle 0.35 s", "where": _locate(cx, '"--min-interval", type=float, default=0.35')},
        {"setting": "retries 2", "where": _locate(cx, '"--max-retries", type=int, default=2')},
        {"setting": "backoff 0.8 s", "where": _locate(cx, '"--backoff-base", type=float, default=0.8')},
        {"setting": "jitter 0.2 s", "where": _locate(cx, '"--jitter", type=float, default=0.2')},
        {"setting": "4 workers per approach", "where": _locate(cx, '"--max-workers", type=int, default=4')},
        {"setting": "master seed 42", "where": _locate(cx, '"--master-seed", type=int, default=42')},
        {"setting": "sub-agents off: no context retrieval", "where": _locate(cx, '"context_data": "",')},
        {"setting": "sub-agents off: no deterministic validation / recovery loop", "where": _locate(cx, '"skip_deterministic_validation": True,')},
        {"setting": "sub-agents off: only planner + deterministic executor", "where": _locate(cx, "planner_out = node_planner(state)")},
        {"setting": "benchmark mode in the executor", "where": _locate(nodes, "if skip_validation:")},
        {"setting": "corrected metric (legacy_structural_keys False)", "where": _locate("benchmarks/metrics/comparison_metrics.py", "def calculate_excision_micro_f1")},
        {"setting": "calls without configuration scored as json_base", "where": _locate(cx, "def _score_json_base")},
    ]


def _calls(a_json: dict, axis: str, approach: Optional[str] = None, levels: Optional[Iterable[int]] = None) -> List[dict]:
    wanted = None if levels is None else set(levels)
    out = []
    for r in a_json["detailed_results"]:
        if approach and r["approach"] != approach:
            continue
        if wanted is not None and int(r[axis]) not in wanted:
            continue
        usage = r.get("token_usage") or {}
        out.append({
            "approach": r["approach"],
            "level": int(r[axis]),
            "sample_idx": int(r["sample_idx"]),
            "prompt": int(usage.get("prompt") or 0),
            "completion": int(usage.get("completion") or 0),
            "attempts": int(r.get("attempts") or 1),
            "latency_s": float(r.get("latency_s") or 0.0),
            "is_timeout": bool(r.get("is_timeout")),
        })
    return out


def context_requirements(a_json: dict, axis: str) -> Dict[str, Any]:
    """Lower bound on the server context from single-attempt calls with logged usage."""
    calls = [c for c in _calls(a_json, axis) if c["attempts"] == 1 and c["prompt"] > 0]
    out: Dict[str, Any] = {}
    for approach in sorted({c["approach"] for c in calls}):
        group = [c for c in calls if c["approach"] == approach]
        totals = [c["prompt"] + c["completion"] for c in group]
        at_limit = [c for c in group if c["completion"] >= TRUNC_THRESHOLD]
        out[approach] = {
            "n_calls": len(group),
            "max_prompt": max(c["prompt"] for c in group),
            "max_prompt_plus_completion": max(totals),
            "n_at_output_limit": len(at_limit),
            "max_completion": max(c["completion"] for c in group),
            # If the context had cut generation, completions would stop below 4096 at a common total.
            "totals_at_output_limit": sorted({c["prompt"] + c["completion"] for c in at_limit})[-5:],
        }
    per_approach = list(out.values())
    bound = max(v["max_prompt_plus_completion"] for v in per_approach)
    out["num_ctx_lower_bound"] = bound
    # With context shifting, generation can run past num_ctx; the prompt alone still has to fit.
    out["num_ctx_lower_bound_if_context_shift"] = max(v["max_prompt"] for v in per_approach) + 1
    out["num_ctx_suggested"] = 1 << (bound - 1).bit_length()
    return out


def prompt_spread(a_json: dict, axis: str, levels: Iterable[int]) -> Dict[int, Dict[str, int]]:
    """P-E prompt tokens per level: a narrow spread means prompt caching did not shrink the counts."""
    out = {}
    for level in levels:
        prompts = [c["prompt"] for c in _calls(a_json, axis, PLANNER, [level]) if c["prompt"] > 0 and c["attempts"] == 1]
        if prompts:
            out[level] = {"n": len(prompts), "min": min(prompts), "median": int(statistics.median(prompts)), "max": max(prompts)}
    return out


def time_estimate(a_json: dict, axis: str, sample_ids: Iterable[int], approach: str, max_workers: int) -> Dict[str, float]:
    """
    Size of these calls in condition A: completion tokens (which set the decoding time) and the
    old server's latencies, which include its own queueing and are only a rough guide.
    """
    wanted = set(sample_ids)
    calls = [c for c in _calls(a_json, axis, approach) if c["sample_idx"] in wanted]
    lat = sum(c["latency_s"] for c in calls)
    return {
        "n_calls": len(calls),
        "completion_tokens": sum(c["completion"] for c in calls),
        "prompt_tokens": sum(c["prompt"] for c in calls),
        "sum_latency_s_old_server": round(lat, 1),
        "wall_s_old_latencies": round(lat / max(1, max_workers), 1),
    }


def full_design_completion_tokens(per_level: int = 25, conditions: int = 2) -> int:
    """Expected P-E completion tokens of the default design: per level, per_level x A's mean, per condition."""
    total = 0.0
    for axis, spec in AXES.items():
        a_json = load_json(a_results_path(axis))
        for level in spec.levels:
            comp = [c["completion"] for c in _calls(a_json, axis, PLANNER, [level])]
            total += per_level * statistics.mean(comp) if comp else 0.0
    return round(total * conditions)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Original gpt-oss:20b run configuration and context requirements")
    parser.add_argument("--run-dir", default=None, help="If given, estimate the time of B and C for its sample IDs")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report: Dict[str, Any] = {"code_locations": code_locations()}
    samples = None
    if args.run_dir:
        from benchmarks.humanisation_check.common import resolve_run_dir, selected_samples
        samples = selected_samples(resolve_run_dir(args.run_dir))
    for axis, spec in AXES.items():
        a_json = load_json(a_results_path(axis))
        cfg = original_run_config(axis, a_json)
        entry = {
            "config": cfg,
            "context": context_requirements(a_json, axis),
            "planner_prompt_tokens_by_level": prompt_spread(a_json, axis, spec.levels),
        }
        if samples is not None:
            ids = [s["sample_idx"] for s in samples if s["axis"] == axis]
            entry["time_on_old_server"] = {
                approach: time_estimate(a_json, axis, ids, approach, cfg["max_workers"])
                for approach in (PLANNER, "vanilla")
            }
        report[axis] = entry
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
