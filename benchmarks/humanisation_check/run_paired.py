"""
Run conditions B (original requests) and C (re-humanised requests) on the new
server, interleaved sample by sample.

Every call goes through the runners' own ``process_sample`` with the runners'
default settings, which must equal the original run's (checked against the
logged summaries, the recovered fingerprint, the author's statement for
LLM_EXTRA_BODY_JSON and the planner LLM actually built; a mismatch aborts):
openai_compatible, temperature 0, seed None, max_tokens None -> 4096, no
extra_body, request timeout 600 s, sample timeout 600 s, throttle 0.35 s,
2 retries, backoff 0.8 s, jitter 0.2 s, sub-agents off, corrected metric.
Requests use the format of the original run (request profile
``2026-04-28-benchmark``: no JSON suffix, no response_format), as the
runners' ``--request-profile`` does. C differs from B only in the request
text, substituted with the same helper as the runners'
``--instruction-override``. Finish reason, raw response (with reasoning, if
Ollama returns it) and request parameters are logged per call.

Declared deviations (listed in the configuration table and the manifest):
- concurrency: the original run used 4 workers; here the number of workers
  equals the server's OLLAMA_NUM_PARALLEL (2 on the server of the recorded run), so every request is
  decoded as soon as it arrives and no call can reach the timeout while
  queued on the server. Without a known OLLAMA_NUM_PARALLEL only 1 worker is
  accepted;
- model name, with ``--derived-model``: a model created FROM gpt-oss:20b that
  only sets num_ctx, for servers whose default context cannot be changed. Its
  weights blob, chat template, system prompt, details and other default
  parameters must equal gpt-oss:20b's, or the run aborts.

The model must be loaded entirely on GPU with a context of at least 8192
tokens (read from /api/ps and recorded): at high K the P-E prompt plus the
4096-token budget reaches about 7 100 tokens, so a 4096 context would cut
generations short and inflate truncation.

On a shared server only our own models are unloaded (the humaniser, plus
``--also-unload``); other loaded models are recorded and left alone.

Interleaving: per level, B and C of each sample are submitted back to back
(which one goes first alternates with the sample's position) to one pool
sharing one P-E throttle, so both conditions get exactly the same
concurrency and server state. P-E always runs; vanilla only with
``--include-vanilla`` (after P-E of each level, as the runners do).

Before any call the humaniser is unloaded (keep_alive 0) and the evaluated
model is loaded; GPU residency and context are checked again after every
level.

Outputs in the run dir: ``calls.jsonl`` (one line per call, appended as they
finish; ``--resume`` continues from it), ``benchmark_compare_<axis>_<B|C>.json``
in the runners' format, and ``manifest.json``.

    python -m benchmarks.humanisation_check.run_paired --run-dir <run-dir> \
        --llm-base-url http://localhost:<PORT>/v1 --ssh-host <HOST>
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import platform
import subprocess
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from tqdm import tqdm

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv() -> None:
        return

from benchmarks.comparisons.sample_overrides import load_instruction_overrides, override_example
from benchmarks.comparisons.traceability import infer_seed_effective, pkg_version
from benchmarks.humanisation_check import ollama_api
from benchmarks.humanisation_check.common import (
    AXES,
    CALLS_FILE,
    EVALUATED_MODEL,
    MANIFEST_FILE,
    PLANNER,
    SAMPLE_IDS_FILE,
    VANILLA,
    a_results_path,
    file_ref,
    find_requests_file,
    git_state,
    load_dataset,
    load_json,
    read_jsonl,
    resolve_run_dir,
    write_json,
)
from benchmarks.humanisation_check.provenance import (
    MAX_TOKENS_DEFAULT,
    ORIGINAL_REQUEST_PROFILE,
    code_locations,
    full_design_completion_tokens,
    original_run_config,
    time_estimate,
)
from input_agent.src.llm import REQUEST_PROFILES

CONDITIONS = ("B", "C")
COMPARED_SETTINGS = [
    "provider", "model_name", "num_ctx", "request_profile", "extra_body", "temperature", "seed", "llm_timeout_s",
    "max_tokens_effective", "min_interval_s", "max_retries", "backoff_base_s", "jitter_s", "max_workers",
    "sample_timeout_s", "master_seed",
]
INFORMATIONAL_SETTINGS = {"num_ctx"}  # not logged for the original run: shown, not compared
DECLARED_DEVIATIONS = {
    "max_workers": "workers = OLLAMA_NUM_PARALLEL of the new server, so no call waits in the server queue "
                   "or reaches the timeout there; B and C share the same pool and concurrency",
}
MIN_CONTEXT = 8192  # P-E prompt + 4096-token budget reaches ~7 100 tokens at high K
SERVER_ENV_KEYS = [
    "OLLAMA_CONTEXT_LENGTH", "OLLAMA_NUM_PARALLEL", "OLLAMA_FLASH_ATTENTION", "OLLAMA_KV_CACHE_TYPE",
    "OLLAMA_MAX_LOADED_MODELS", "OLLAMA_KEEP_ALIVE", "OLLAMA_NEW_ENGINE", "OLLAMA_SCHED_SPREAD",
    "CUDA_VISIBLE_DEVICES",
]
CLIENT_ENV_KEYS = ["LLM_EXTRA_BODY_JSON", "BENCHMARK_LLM_EXTRA_BODY_JSON", "LLM_REQUEST_PROFILE"]


def runner_defaults() -> Dict[str, Any]:
    """Default settings of both runners (they must agree)."""
    parsed = {
        axis: vars(importlib.import_module(spec.runner).build_arg_parser().parse_args([]))
        for axis, spec in AXES.items()
    }
    keys = ["min_interval", "max_retries", "backoff_base", "jitter", "max_workers",
            "llm_temperature", "llm_seed", "llm_timeout", "master_seed", "sample_timeout"]
    first, second = parsed["complexity"], parsed["completeness"]
    differing = [k for k in keys if first[k] != second[k]]
    if differing:
        raise SystemExit(f"runner defaults differ between axes: {differing}")
    return first


def new_run_config(model: str, request_profile: Optional[str], max_workers: int,
                   extra_body: Optional[dict] = None, num_ctx: Optional[int] = None) -> Dict[str, Any]:
    d = runner_defaults()
    return {
        "provider": "openai_compatible",
        "model_name": model,
        "num_ctx": num_ctx,
        "request_profile": request_profile,
        "extra_body": extra_body,
        "temperature": d["llm_temperature"],
        "seed": d["llm_seed"],
        "llm_timeout_s": d["llm_timeout"],
        "max_tokens_effective": MAX_TOKENS_DEFAULT,
        "min_interval_s": d["min_interval"],
        "max_retries": d["max_retries"],
        "backoff_base_s": d["backoff_base"],
        "jitter_s": d["jitter"],
        "max_workers": max_workers,
        "sample_timeout_s": d["sample_timeout"],
        "master_seed": d["master_seed"],
        "legacy_structural_keys": False,
    }


def resolve_workers(requested: Optional[int], server_parallel: Optional[str]) -> int:
    """Workers such that no request waits in the server queue: at most OLLAMA_NUM_PARALLEL."""
    parallel = int(server_parallel) if server_parallel not in (None, "") else None
    if parallel is None:
        if requested == 1:
            return 1  # one request in flight at a time never queues
        raise SystemExit(
            "OLLAMA_NUM_PARALLEL of the server is unknown: set it explicitly and pass --ssh-host/--server-info, "
            "or run with --max-workers 1"
        )
    workers = parallel if requested is None else requested
    if not 1 <= workers <= parallel:
        raise SystemExit(f"--max-workers {workers} with OLLAMA_NUM_PARALLEL={parallel} would queue calls on the server")
    return workers


def compare_configs(
    new: Dict[str, Any],
    originals: Dict[str, Dict[str, Any]],
    deviations: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """One row per setting; a mismatch is acceptable only as a declared deviation."""
    declared = {**DECLARED_DEVIATIONS, **(deviations or {})}
    rows = []
    for key in COMPARED_SETTINGS:
        row = {"setting": key, "new": new.get(key)}
        for axis, cfg in originals.items():
            row[f"original_{axis}"] = cfg.get(key)
        known = [
            cfg[key] for cfg in originals.values()
            if key in cfg and not (key == "sample_timeout_s" and not cfg.get("sample_timeout_recovered_from_fingerprint"))
        ]
        if key in INFORMATIONAL_SETTINGS or not known:
            row["match"] = None
        else:
            row["match"] = all(v == row["new"] for v in known)
        row["declared_deviation"] = declared.get(key) if row["match"] is False else None
        rows.append(row)
    return rows


def server_environment(server_info: Optional[dict], stated: Iterable[str]) -> Dict[str, Any]:
    """
    Server environment collected over SSH, plus the values stated with --server-env
    (used when a variable was not collected); disagreements are listed.
    """
    collected = (server_info or {}).get("env_effective") or {}
    stated_env = {}
    for item in stated or []:
        key, _, value = item.partition("=")
        stated_env[key.strip()] = value.strip()
    return {
        "collected": collected,
        "stated": stated_env,
        "effective": {**stated_env, **collected},
        "disagreements": {k: {"collected": collected[k], "stated": v}
                          for k, v in stated_env.items() if k in collected and collected[k] != v},
    }


def collect_server_info(ssh_host: Optional[str], path: Optional[str], run_dir: Path) -> Optional[dict]:
    if path:
        return load_json(path)
    if not ssh_host:
        return None
    script = (Path(__file__).parent / "collect_server_info.py").read_bytes()
    try:
        proc = subprocess.run(["ssh", ssh_host, "python3", "-"], input=script, capture_output=True, timeout=180)
        info = json.loads(proc.stdout.decode("utf-8"))
    except Exception as exc:
        return {"error": f"ssh {ssh_host}: {exc}"}
    write_json(run_dir / "server_info.json", info)
    return info


def check_loaded(status: Dict[str, Any], model: str, skip_gpu_check: bool) -> None:
    """The model must be entirely on GPU and loaded with at least MIN_CONTEXT tokens of context."""
    if not status.get("fully_on_gpu") and not skip_gpu_check:
        raise SystemExit(f"{model} is not entirely on GPU: {status}")
    context = status.get("context_length")
    if context is None or int(context) < MIN_CONTEXT:
        raise SystemExit(
            f"{model} is loaded with context {context}, below {MIN_CONTEXT}: P-E prompt plus the 4096-token "
            "budget would not fit. Use --derived-model (num_ctx 32768) or raise the server's context length."
        )


def prepare_server(base_url: str, model: str, unload_names: List[str], skip_gpu_check: bool) -> Dict[str, Any]:
    """
    Unload our own models (humaniser, and any named with --also-unload), load the
    evaluated model and require it fully on GPU with enough context. Models of
    other users of a shared server are recorded, never unloaded.
    """
    summary = ollama_api.server_summary(base_url, list(dict.fromkeys([model, EVALUATED_MODEL, *unload_names])))
    if "error" in summary:
        raise SystemExit(f"Ollama API not reachable at {base_url}: {summary['error']}")
    if not summary["models"][model]["present"]:
        raise SystemExit(f"{model} is not on the server")

    unloaded = {}
    for entry in ollama_api.loaded(base_url):
        name = entry.get("name") or entry.get("model")
        if name != model and name in unload_names:
            unloaded[name] = ollama_api.unload(base_url, name)
    if not all(unloaded.values()):
        raise SystemExit(f"could not unload: {[n for n, ok in unloaded.items() if not ok]}")

    ollama_api.preload(base_url, model)
    entries = ollama_api.loaded(base_url)
    entry = ollama_api.find(entries, model)
    status = ollama_api.gpu_status(entry) if entry else {"fully_on_gpu": False, "error": "not loaded"}
    others = [ollama_api.gpu_status(e) for e in entries if e is not entry]
    for other in others:
        print(f"Note: {other['name']} is also loaded (another user's model?); it is left alone. "
              f"On GPU: {other['fraction_on_gpu']}")
    check_loaded(status, model, skip_gpu_check)
    summary.update({"unloaded": unloaded, "evaluated_model_at_start": status, "other_loaded_at_start": others})
    return summary


def aggregate(records: List[dict]) -> Dict[str, Any]:
    n = len(records)
    if not n:
        return {"total_samples": 0}

    def avg(field):
        return sum(float(r.get(field) or 0.0) for r in records) / n

    tokens = [int((r.get("token_usage") or {}).get("total") or 0) for r in records]
    successes = int(sum(float(r.get("exact_match") or 0.0) for r in records))
    return {
        "total_samples": n,
        "json_exact_successes": successes,
        "failures": n - successes,
        "exact_match_pct": round(100.0 * successes / n, 2),
        "excision_micro_f1_avg": round(avg("f1_micro"), 4),
        "excision_key_f1_avg": round(avg("f1_keys"), 4),
        "excision_value_f1_avg": round(avg("f1_values"), 4),
        "collateral_damage_avg": round(avg("collateral_damage"), 4),
        "omissions_avg": round(avg("omissions"), 4),
        "collateral_rate_avg": round(avg("collateral_rate"), 4),
        "omission_rate_avg": round(avg("omission_rate"), 4),
        "avg_latency_s": round(avg("latency_s"), 4),
        "avg_total_tokens": round(sum(tokens) / n, 2),
        "avg_attempts": round(avg("attempts"), 3),
        "timeouts": sum(1 for r in records if r.get("is_timeout")),
    }


def write_condition_outputs(run_dir: Path, calls: List[dict], common_summary: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """One runner-format results file per condition and axis."""
    outputs: Dict[str, Dict[str, Any]] = defaultdict(dict)
    grouped: Dict[tuple, List[dict]] = defaultdict(list)
    for call in calls:
        grouped[(call["condition"], call["axis"])].append(call)
    for (condition, axis), group in sorted(grouped.items()):
        detailed = [c["detailed_result"] for c in group if c.get("detailed_result")]
        failed = [c["failed_case"] for c in group if c.get("failed_case")]
        by_level: Dict[str, Dict[str, Any]] = defaultdict(dict)
        levels = sorted({int(r[axis]) for r in detailed})
        approaches = sorted({r["approach"] for r in detailed})
        for level in levels:
            for approach in approaches:
                by_level[str(level)][approach] = aggregate(
                    [r for r in detailed if int(r[axis]) == level and r["approach"] == approach]
                )
        path = run_dir / f"benchmark_compare_{axis}_{condition}.json"
        write_json(path, {
            "summary": {
                **common_summary,
                "condition": condition,
                "axis": axis,
                "dataset_path": AXES[axis].dataset,
                "selected_levels": levels,
                "selected_approaches": approaches,
                "total_samples": len({r["sample_idx"] for r in detailed}),
                "instruction_source": "dataset" if condition == "B" else common_summary["requests_file"],
                "approaches": {a: aggregate([r for r in detailed if r["approach"] == a]) for a in approaches},
            },
            f"by_{axis}": by_level,
            "detailed_results": detailed,
            "failed_cases": failed,
            "manifest_path": str(run_dir / MANIFEST_FILE),
        })
        outputs[condition][axis] = file_ref(path)
    return outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run conditions B and C interleaved on the new server")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--llm-base-url", required=True, help="OpenAI-compatible URL, e.g. http://localhost:<PORT>/v1")
    parser.add_argument("--requests", default=None, help="requests_<model>.jsonl (default: the only one in the run dir)")
    parser.add_argument("--derived-model", default=None,
                        help="Model created FROM gpt-oss:20b that only sets num_ctx (e.g. gpt-oss-20b-ctx32k); "
                             "used for B and C after checking weights, template and parameters")
    parser.add_argument("--also-unload", nargs="*", default=[],
                        help="Models of yours to unload besides the humaniser (models of other users are never unloaded)")
    parser.add_argument("--ssh-host", default=None, help="Collect GPU and Ollama environment over SSH")
    parser.add_argument("--server-info", default=None, help="JSON printed by collect_server_info.py (instead of --ssh-host)")
    parser.add_argument("--server-env", nargs="*", default=[], metavar="KEY=VALUE",
                        help="Server settings as stated by the administrator, recorded in the manifest "
                             "(and used when not collected over SSH)")
    parser.add_argument("--max-workers", type=int, default=None,
                        help="Workers shared by B and C; default and maximum: the server's OLLAMA_NUM_PARALLEL")
    parser.add_argument("--include-vanilla", action="store_true", help="Also run the vanilla branch (off by default)")
    parser.add_argument("--request-profile", choices=[*sorted(REQUEST_PROFILES), "current"], default=ORIGINAL_REQUEST_PROFILE,
                        help="Request format; the default reproduces the original run's")
    parser.add_argument("--resume", action="store_true", help=f"Continue from an existing {CALLS_FILE}")
    parser.add_argument("--check-only", action="store_true", help="Checks and manifest only; no benchmark calls")
    parser.add_argument("--allow-config-mismatch", action="store_true")
    parser.add_argument("--skip-gpu-check", action="store_true")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_dir = resolve_run_dir(args.run_dir)
    calls_path = run_dir / CALLS_FILE
    manifest_path = run_dir / MANIFEST_FILE
    if calls_path.exists() and not (args.resume or args.check_only):
        raise SystemExit(f"{calls_path} exists; pass --resume to continue it")
    if args.check_only and calls_path.exists():
        manifest_path = run_dir / "manifest_check.json"  # keep the run's manifest intact

    selection = load_json(run_dir / SAMPLE_IDS_FILE)
    samples = selection["samples"]
    axes = [axis for axis in AXES if any(s["axis"] == axis for s in samples)]
    requests_path = find_requests_file(run_dir, args.requests)
    requests_meta_path = requests_path.with_suffix(".meta.json")
    requests_meta = load_json(requests_meta_path) if requests_meta_path.exists() else None
    humanizer = (requests_meta or {}).get("humanizer_model") or read_jsonl(requests_path)[0]["humanizer_model"]

    datasets = {axis: load_dataset(axis) for axis in axes}
    overrides = {axis: load_instruction_overrides(requests_path, axis) for axis in axes}
    for s in samples:
        row = datasets[s["axis"]][s["sample_idx"]]
        rec = overrides[s["axis"]].get(s["sample_idx"])
        if rec is None:
            raise SystemExit(f"no re-humanised request for {s['axis']} sample {s['sample_idx']}")
        if rec.get("instruction_natural_original") not in (None, row[AXES[s["axis"]].text_key]):
            raise SystemExit(f"{s['axis']} sample {s['sample_idx']}: original request differs from the dataset")
        override_example(row, rec, AXES[s["axis"]].text_key, AXES[s["axis"]].technical_key)  # raises on mismatch

    load_dotenv()  # as the runners do
    approaches = [PLANNER] + ([VANILLA] if args.include_vanilla else [])
    request_profile = None if args.request_profile == "current" else args.request_profile

    server_info = collect_server_info(args.ssh_host, args.server_info, run_dir)
    server_environment_record = server_environment(server_info, args.server_env)
    server_env = server_environment_record["effective"]
    for key, values in server_environment_record["disagreements"].items():
        print(f"WARNING: {key} collected as {values['collected']!r} but stated as {values['stated']!r}")
    workers = resolve_workers(args.max_workers, server_env.get("OLLAMA_NUM_PARALLEL"))

    model = args.derived_model or EVALUATED_MODEL
    deviations: Dict[str, str] = {}
    derivation = None
    if args.derived_model:
        derivation = ollama_api.derivation_check(args.llm_base_url, EVALUATED_MODEL, model)
        print(f"Derived model {model} vs {EVALUATED_MODEL}: {derivation['checks']} num_ctx={derivation['num_ctx']}")
        if not derivation["ok"]:
            raise SystemExit(f"{model} is not {EVALUATED_MODEL} with only num_ctx changed: {json.dumps(derivation, indent=1)}")
        deviations["model_name"] = (
            f"{model} = FROM {EVALUATED_MODEL} + PARAMETER num_ctx {derivation['num_ctx']}: weights blob, chat template, "
            "system prompt, details and other parameters verified identical; only num_ctx changes"
        )

    server = prepare_server(args.llm_base_url, model, list(dict.fromkeys([humanizer, *args.also_unload])),
                            args.skip_gpu_check)
    digest = server["models"][model].get("digest")

    # Planner-Executor reads its LLM settings from the environment, set exactly as the runners set it.
    config = new_run_config(model, request_profile, workers,
                            num_ctx=server["evaluated_model_at_start"].get("context_length"))
    runners = {axis: importlib.import_module(AXES[axis].runner) for axis in axes}
    runners[axes[0]]._configure_planner_executor_env(
        config["provider"], config["model_name"], config["temperature"], config["seed"],
        config["llm_timeout_s"], args.llm_base_url,
    )
    if request_profile:
        os.environ["LLM_REQUEST_PROFILE"] = request_profile
    else:
        os.environ.pop("LLM_REQUEST_PROFILE", None)
    from input_agent.nodes import get_llm
    planner_llm = get_llm()
    planner_runtime = planner_llm.get_runtime_metadata()
    config["extra_body"] = planner_llm.extra_body
    if (planner_llm.max_tokens is not None or planner_llm.request_profile != request_profile
            or planner_runtime["temperature"] != config["temperature"]):
        raise SystemExit(f"planner LLM differs from the intended configuration: {planner_runtime}")

    originals = {axis: original_run_config(axis) for axis in axes}
    comparison = compare_configs(config, originals, deviations)
    undeclared = [row for row in comparison if row["match"] is False and not row["declared_deviation"]]
    print(f"  {'setting':22s} {'original (both axes, or complexity / completeness)':52s} new")
    for row in comparison:
        values = list(dict.fromkeys(str(row[f"original_{axis}"]) for axis in axes))
        orig = " / ".join(values)
        flag = ""
        if row["match"] is False:
            flag = "   (declared deviation)" if row["declared_deviation"] else "   <-- MISMATCH"
        elif row["setting"] in INFORMATIONAL_SETTINGS:
            flag = "   (not logged for the original run)"
        print(f"  {row['setting']:22s} {orig[:52]:52s} {row['new']}{flag}")
    if undeclared and not args.allow_config_mismatch:
        raise SystemExit("configuration differs from the original run")

    run_llm_metadata = {
        "provider": config["provider"],
        "llm_mode": config["provider"],
        "model_name": config["model_name"],
        "model_version": f"sha256:{digest}" if digest else None,
        "base_url": args.llm_base_url,
        "temperature": config["temperature"],
        "seed": config["seed"],
        "seed_effective": infer_seed_effective(config["provider"], config["seed"]),
        "timeout_s": config["llm_timeout_s"],
    }

    estimate = {}
    for axis in axes:
        a_json = load_json(a_results_path(axis))
        ids = [s["sample_idx"] for s in samples if s["axis"] == axis]
        estimate[axis] = {a: time_estimate(a_json, axis, ids, a, config["max_workers"]) for a in approaches}
    tokens = 2 * sum(e["completion_tokens"] for per_axis in estimate.values() for e in per_axis.values())
    print(f"\nB + C ({', '.join(approaches)}, {workers} worker(s)): about {tokens:,} completion tokens as in A; "
          + ", ".join(f"{tokens / rate / 60:.0f} min at {rate} tok/s" for rate in (50, 100, 150)))

    manifest: Dict[str, Any] = {
        "run_id": run_dir.name,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "checked" if args.check_only else "running",
        "design": {
            "A": "logged gpt-oss:20b results of the original run (old server, original requests), re-scored",
            "B": "new server, original requests",
            "C": f"new server, requests re-humanised by {humanizer}",
            "effect": "C - B (humanisation); B - A checks that the new server reproduces the old one",
            "approaches": approaches,
            "interleaving": "per level, B and C of each sample submitted back to back (order alternates with "
                            "sample position) to one pool of max_workers sharing one throttle per approach",
        },
        "git": git_state(),
        "client": {
            "python": sys.version.split()[0],
            "platform": f"{platform.system()} {platform.machine()} {platform.release()}",
            "packages": {p: pkg_version(p) for p in ("openai", "httpx", "langchain-core", "langgraph", "pydantic", "numpy", "scipy")},
            "openai_client_max_retries": 2,
        },
        "ollama": server,
        "server_info": server_info,
        "derived_model": derivation,
        "environment": {
            "client": {k: os.environ.get(k) for k in CLIENT_ENV_KEYS},
            "client_effective_extra_body": planner_llm.extra_body,
            "server": {k: server_env.get(k) for k in SERVER_ENV_KEYS},
            "server_collected": server_environment_record["collected"],
            "server_stated": server_environment_record["stated"],
            "server_disagreements": server_environment_record["disagreements"],
            "context_length_reported_by_ps": server["evaluated_model_at_start"].get("context_length"),
            "min_context_required": MIN_CONTEXT,
        },
        "config": {
            "new": config,
            "original": originals,
            "comparison": comparison,
            "deviations": {
                row["setting"]: {"original": [row[f"original_{axis}"] for axis in axes], "new": row["new"],
                                 "reason": row["declared_deviation"]}
                for row in comparison if row["declared_deviation"]
            },
            "concurrency": {"workers": workers, "server_OLLAMA_NUM_PARALLEL": server_env.get("OLLAMA_NUM_PARALLEL"),
                            "shared_by_B_and_C": True},
            "planner_llm_runtime": planner_runtime,
            "run_llm_metadata": run_llm_metadata,
            "code_locations": code_locations(),
        },
        "sample_ids": {"file": file_ref(run_dir / SAMPLE_IDS_FILE), "seed": selection["seed"],
                       "per_level": selection["per_level"], "samples": samples},
        "humanizer": {
            "model": humanizer,
            "requests_file": file_ref(requests_path),
            "meta": {k: (requests_meta or {}).get(k) for k in ("ollama", "llm_settings", "format_check", "empty_requests")},
        },
        "fidelity": [file_ref(p) for p in sorted(run_dir.glob("fidelity_*.csv"))],
        "time_estimate_old_server": estimate,
        "gpu_checks": [],
    }
    write_json(manifest_path, manifest)
    if args.check_only:
        print(f"Checks passed; manifest -> {manifest_path}")
        return 0

    done = set()
    if calls_path.exists():
        for call in read_jsonl(calls_path):
            done.add((call["condition"], call["axis"], call["approach"], call["sample_idx"]))
        print(f"Resuming: {len(done)} calls already logged")

    lock = threading.Lock()
    llm_vanilla = None
    if args.include_vanilla:
        from input_agent.src.llm import LLMService
        llm_vanilla = LLMService(
            mode=config["provider"], api_key=runners[axes[0]]._resolve_api_key(config["provider"]),
            temperature=config["temperature"], seed=config["seed"], model=config["model_name"],
            base_url=args.llm_base_url, timeout=config["llm_timeout_s"],
        )
    throttles = {a: runners[axes[0]].ApproachThrottle(min_interval_s=config["min_interval_s"]) for a in approaches}
    started = time.perf_counter()

    with open(calls_path, "a", encoding="utf-8") as sink:
        for axis in axes:
            spec, runner = AXES[axis], runners[axis]
            for level in sorted({s["level"] for s in samples if s["axis"] == axis}):
                ids = [s["sample_idx"] for s in samples if s["axis"] == axis and s["level"] == level]
                for approach in approaches:
                    tasks = []
                    for pos, idx in enumerate(ids):
                        row = datasets[axis][idx]
                        variants = {"B": row, "C": override_example(row, overrides[axis][idx], spec.text_key, spec.technical_key)}
                        for condition in (CONDITIONS if pos % 2 == 0 else CONDITIONS[::-1]):
                            if (condition, axis, approach, idx) not in done:
                                tasks.append((condition, idx, variants[condition]))
                    if not tasks:
                        continue
                    with ThreadPoolExecutor(max_workers=config["max_workers"]) as pool:
                        futures = {
                            pool.submit(
                                runner.process_sample, idx, example, level, approach,
                                config["max_retries"], config["backoff_base_s"], config["jitter_s"],
                                throttles[approach], llm_vanilla, run_llm_metadata,
                                config["sample_timeout_s"], False, True,
                            ): (condition, idx)
                            for condition, idx, example in tasks
                        }
                        for future in tqdm(as_completed(futures), total=len(futures), desc=f"{axis} L{level} {approach}", unit="call"):
                            condition, idx = futures[future]
                            call = {"condition": condition, "axis": axis, "level": level, "approach": approach, "sample_idx": idx}
                            try:
                                result = future.result()
                                call.update(detailed_result=result["detailed_result"], failed_case=result["failed_case"])
                            except Exception as exc:
                                call["error"] = str(exc)
                            with lock:
                                sink.write(json.dumps(call, ensure_ascii=False) + "\n")
                                sink.flush()
                entry = ollama_api.find(ollama_api.loaded(args.llm_base_url), model)
                check = {"axis": axis, "level": level, **(ollama_api.gpu_status(entry) if entry else {"fully_on_gpu": False})}
                manifest["gpu_checks"].append(check)
                write_json(manifest_path, manifest)
                if entry is not None:  # an idle model may have been unloaded between levels; it reloads as before
                    check_loaded(check, model, args.skip_gpu_check)

    calls = read_jsonl(calls_path)
    errors = [c for c in calls if c.get("error")]
    common_summary = {
        "run_id": run_dir.name,
        "model": run_llm_metadata,
        "request_profile": request_profile,
        "master_seed": config["master_seed"],
        "legacy_structural_keys": False,
        "fairness": {
            "shared_throttle": config["min_interval_s"],
            "shared_max_retries": config["max_retries"],
            "shared_backoff_base_s": config["backoff_base_s"],
            "shared_jitter_s": config["jitter_s"],
            "max_workers_per_approach": config["max_workers"],
            "sample_timeout_s": config["sample_timeout_s"],
        },
        "requests_file": file_ref(requests_path),
    }
    results = [c["detailed_result"] for c in calls if c.get("detailed_result")]
    timeouts = [(c["condition"], c["axis"], c["level"], c["sample_idx"]) for c in calls
                if (c.get("detailed_result") or {}).get("is_timeout")]
    completion = sum(int((r.get("token_usage") or {}).get("completion") or 0) for r in results)
    latency = sum(float(r.get("latency_s") or 0.0) for r in results)
    rate = completion / latency if latency else None
    manifest.update({
        "status": "completed" if not errors else "completed_with_errors",
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_s": round(time.perf_counter() - started, 1),
        "calls": {"logged": len(calls), "errors": len(errors), "timeouts": timeouts, "file": file_ref(calls_path)},
        "throughput": {"completion_tokens": completion, "sum_latency_s": round(latency, 1),
                       "completion_tokens_per_s": None if rate is None else round(rate, 1)},
        "outputs": write_condition_outputs(run_dir, calls, common_summary),
    })
    write_json(manifest_path, manifest)
    print(f"\n{len(calls)} calls ({len(errors)} errors, {len(timeouts)} timeouts) in {manifest['elapsed_s'] / 60:.1f} min; "
          f"manifest -> {manifest_path}")
    if rate:
        full = full_design_completion_tokens()
        print(f"Throughput: {rate:.0f} completion tokens/s; the full design (~{full:,} completion tokens for B + C, P-E) "
              f"would take about {full / rate / 60:.0f} min at this rate")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
