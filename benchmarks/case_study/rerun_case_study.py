"""Re-run of the case study of Subsection 4.2 with the current validator, through the same code path
as the web demo (core/api.py): AppState.initialize() and the /chat endpoint function, one thread, the
queries of tab:agent_eval in order. Queries 1-7 (categories A to E) always run; query 8 (category
F: the IWO optimisation) only with --with-optimization. The comparison query of category F (S_0,
S_{k+1} and S* in one report) is not run: the CDTO keeps no record of past states to compare.

What it adds around core/api.py, without changing it:
- load_dotenv is disabled before any import, so .env cannot reintroduce model, URL or seed values;
  every LLM setting comes from the process environment and is checked before the first call;
- the root logger writes <run_dir>/agent_debug.log (core/api.py configures logging on import, which
  otherwise stops input_agent/nodes.py from opening it);
- the working directory is <CDTO_IO_DIR>/work, so the episodic vector store (./chroma_episodic_db),
  the wiki store and agent_FULL.png start empty and stay out of the results;
- the graph is wrapped to keep each query's final state;
- the graph is streamed (updates + values, same final state as invoke) to keep what each node wrote,
  so the batch emitted by the planner is recorded even after the executor clears it;
- the run never stops on an unexpected state: for queries 3, 4 and 5 it records the planner batch and
  its paths, whether every path resolved, whether the executor committed, rejected or aborted, and
  the resulting configuration; state_before_q5 records which of the two edits (A002.T002.Duration =
  85, A002.T_wait = 6) were actually applied, and query 5 runs on whatever state there is.

The IWO optimiser (query 8) reads and writes C:/tmp/io regardless of CDTO_IO_DIR (core/main.py
_paths_for_pipeline and the optimizer formulation), so --with-optimization requires CDTO_IO_DIR to be
that folder.

Writes benchmarks/results/case_study_rerun/<run_id>/ with, per query, the full response, the node
updates, the final state and the configuration before and after the step; for query 5, the
violations (as the executor wrote them, before the simulator clears validation_errors), the rejected
candidate, the output of its simulation, the explanation and the feedback; agent_debug.log; and
manifest.json with the model, its digest, the commits, the agent fixes the run depends on (as
RELEASE.json lists them, with its SHA-256) and the environment (keys redacted). The run does not
start unless RELEASE.json lists every one of those fixes (benchmarks/case_study/release_info.py
writes it from the git history).
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmarks.case_study.release_info import RELEASE_FILE, ReleaseError, read_fixes  # noqa: E402

QUERIES = [
    "What are the duration and shutdown requirement of each task in A002?",
    "How many technicians are assigned to A001 and what is its dispatch start time?",
    "Task T002 in A002 is causing delays. Reduce its duration by 15 %.",
    "Increase the dispatching wait time of A002 by 50 %.",
    "Remove task T001 from A002; it looks like a redundant initial check.",
    "Simulate the updated configuration and explain the performance difference versus the original baseline.",
    "What happens between t=400 and t=410 h? Show the A001–A002 handoff sequence.",
    "Net plan availability of 87.5 % is insufficient. Optimize the system to reach at least 90 %.",
]
CATEGORY = {5: "C", 6: "D", 7: "E", 8: "F"}
OPTIMIZATION_QUERIES = {8}
EDIT_QUERIES = {3, 4, 5}
OPTIMIZER_IO_DIR = Path("C:/tmp/io")  # hardcoded in core/main.py and the optimizer formulation
REQUIRED_EQUAL = {
    "LLM_PROVIDER": "openai_compatible",
    "BENCHMARK_LLM_PROVIDER": "openai_compatible",
}
MODEL_VARS = ("LLM_MODEL", "BENCHMARK_LLM_MODEL")
URL_VARS = ("LLM_BASE_URL", "BENCHMARK_LLM_BASE_URL")
# Variables that would override the model, URL or request format in LLMService or get_llm.
MUST_BE_UNSET = (
    "OLLAMA_MODEL", "OPENAI_COMPATIBLE_MODEL", "OPENAI_BASE_URL", "OPENAI_COMPATIBLE_BASE_URL",
    "OLLAMA_BASE_URL", "LLM_EXTRA_BODY_JSON", "BENCHMARK_LLM_EXTRA_BODY_JSON", "LLM_REQUEST_PROFILE", "LLM_MODE",
)
RECORDED_VARS = (
    "LLM_PROVIDER", "LLM_MODEL", "LLM_BASE_URL", "LLM_TEMPERATURE", "LLM_SEED", "LLM_TIMEOUT", "LLM_API_KEY",
    "BENCHMARK_LLM_PROVIDER", "BENCHMARK_LLM_MODEL", "BENCHMARK_LLM_BASE_URL", "BENCHMARK_LLM_TEMPERATURE",
    "BENCHMARK_LLM_SEED", "BENCHMARK_LLM_TIMEOUT", "BENCHMARK_LLM_API_KEY", "OPENAI_COMPATIBLE_API_KEY",
    "CDTO_IO_DIR", *MUST_BE_UNSET,
)
SECRET_VARS = {"LLM_API_KEY", "BENCHMARK_LLM_API_KEY", "OPENAI_COMPATIBLE_API_KEY"}
STATE_KEYS = (
    "final_response", "execution_log", "validation_errors", "validation_violations", "correction_history",
    "proposed_plan", "delta", "report", "episodic_report", "current_config", "episodic_config",
    "episodic_delta", "episodic_reference_kpis", "reference_config", "reference_kpis",
    "baseline_kpis", "current_kpis", "kpi_delta", "retry_count", "episodic_loop", "simulation_ready",
    "task_queue", "current_task", "token_usage", "context_data",
)
def fail(message: str) -> None:
    print(f"ABORT: {message}", file=sys.stderr)
    sys.exit(2)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True).stdout.strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dump(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def check_environment(model: str, base_url: str) -> None:
    for var, expected in REQUIRED_EQUAL.items():
        if os.environ.get(var) != expected:
            fail(f"{var} debe valer {expected!r} (vale {os.environ.get(var)!r})")
    for var in MODEL_VARS:
        if os.environ.get(var) != model:
            fail(f"{var} debe valer {model!r} (vale {os.environ.get(var)!r})")
    for var in URL_VARS:
        if os.environ.get(var) != base_url:
            fail(f"{var} debe valer {base_url!r} (vale {os.environ.get(var)!r})")
    present = [v for v in MUST_BE_UNSET if v in os.environ]
    if present:
        fail(f"estas variables tienen que estar sin definir: {present}")
    if not os.environ.get("CDTO_IO_DIR"):
        fail("CDTO_IO_DIR no está definida")


def redacted_environment() -> dict:
    return {
        var: ("<set>" if var in SECRET_VARS else os.environ[var]) if var in os.environ else None
        for var in RECORDED_VARS
    }


def plain(value):
    """JSON-friendly copy: messages become {type, content}; the rest is left to json's default=str."""
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if hasattr(value, "content") and hasattr(value, "type"):
        return {"type": value.type, "content": value.content}
    return value


def serializable_state(state: dict) -> dict:
    out = {key: plain(state.get(key)) for key in STATE_KEYS if key in state}
    out["messages"] = plain(state.get("messages", []))
    return out


class GraphRecorder:
    """Delegates to the compiled graph. invoke streams it (updates + values, same final state as
    invoke) and keeps what each node wrote and the final state."""

    def __init__(self, graph):
        self._graph = graph
        self.last_input = None
        self.last_final_state = None
        self.last_updates = []

    def invoke(self, input_state, config=None, **kwargs):
        self.last_input = input_state
        self.last_updates, final = [], None
        for mode, chunk in self._graph.stream(input_state, config=config, stream_mode=["updates", "values"], **kwargs):
            if mode == "updates":
                self.last_updates += [{"node": node, "update": update} for node, update in (chunk or {}).items()]
            else:
                final = chunk
        self.last_final_state = final
        return final

    def __getattr__(self, name):
        return getattr(self._graph, name)


def edit_report(updates: list, config_before: dict, config_after: dict, find_unresolved_routes, batch_model) -> dict:
    """Planner batch(es), route check, executor outcome and resulting configuration of one query."""
    plans = [u["update"].get("proposed_plan") for u in updates if u["node"] == "planner"]
    executions = [u["update"] for u in updates if u["node"] == "executor"]
    report = {"planner_batches": [], "executor_runs": [], "config_after": config_after}
    for plan in plans:
        entry = {"plan": plain(plan), "paths": None, "routes_resolved": None, "unresolved_routes": None}
        instructions = plan.get("instructions") if isinstance(plan, dict) else None
        if instructions:
            entry["paths"] = [i.get("path") if isinstance(i, dict) else None for i in instructions]
            try:
                unresolved = find_unresolved_routes(config_before, batch_model(thought_process="", instructions=instructions))
                entry["routes_resolved"], entry["unresolved_routes"] = not unresolved, unresolved
            except Exception as exc:  # noqa: BLE001
                entry["unresolved_routes"] = f"el batch no cumple ModificationBatch: {exc}"
        report["planner_batches"].append(entry)
    for update in executions:
        violations = update.get("validation_violations") or []
        errors = update.get("validation_errors") or []
        if "current_config" in update:
            outcome = "commit"
        elif violations:
            outcome = "rechazo (" + " + ".join(sorted({v["group"] for v in violations})) + ")"
        elif errors:
            routes = any(str(e).startswith("Ruta no resuelta") for e in errors)
            outcome = "error crítico (rutas)" if routes else "error crítico"
        else:
            outcome = "sin cambios"
        report["executor_runs"].append({
            "outcome": outcome, "validation_violations": violations, "validation_errors": errors,
            "task_queue": update.get("task_queue"), "execution_log": update.get("execution_log"),
        })
    report["outcome"] = report["executor_runs"][-1]["outcome"] if report["executor_runs"] else "el executor no se ejecutó"
    return report


def only_case_edits(s0: dict, config: dict) -> bool:
    """True if config differs from S_0 only in A002.tasks.T002.Duration and A002.T_wait."""
    if not isinstance(config, dict):
        return False
    a, b = copy.deepcopy(s0), copy.deepcopy(config)
    for cfg in (a, b):
        a002 = cfg.get("A002")
        if isinstance(a002, dict):
            a002.pop("T_wait", None)
            (a002.get("tasks") or {}).get("T002", {}).pop("Duration", None)
    return a == b


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--out-root", default=str(REPO_ROOT / "benchmarks/results/case_study_rerun"))
    parser.add_argument("--thread-id", default="case_study_rerun")
    parser.add_argument("--with-optimization", action="store_true",
                        help="also run query 8 (IWO optimisation; estimated 30 min to 3 h)")
    parser.add_argument("--preflight-only", action="store_true", help="check environment, server and model, then stop")
    args = parser.parse_args()

    check_environment(args.model, args.base_url)
    try:
        fixes = read_fixes(RELEASE_FILE)
    except ReleaseError as exc:
        fail(str(exc))
    io_dir = Path(os.environ["CDTO_IO_DIR"]).expanduser().resolve()
    if io_dir.exists() and any(io_dir.iterdir()):
        fail(f"CDTO_IO_DIR tiene que estar vacía o no existir: {io_dir}")
    if args.with_optimization and os.path.normcase(str(io_dir)) != os.path.normcase(str(OPTIMIZER_IO_DIR.resolve())):
        fail(f"con --with-optimization, CDTO_IO_DIR tiene que ser {OPTIMIZER_IO_DIR} (el optimizador usa esa ruta fija)")

    run_id = args.run_id or f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_{uuid.uuid4().hex[:6]}"
    run_dir = Path(args.out_root).resolve() / run_id
    if run_dir.exists():
        fail(f"ya existe {run_dir}")

    # Server and model, before any LLM call.
    sys.path.insert(0, str(REPO_ROOT))
    from benchmarks.humanisation_check import ollama_api

    try:
        server = {"version": ollama_api.version(args.base_url), "model": ollama_api.model_summary(args.base_url, args.model)}
    except Exception as exc:  # noqa: BLE001
        fail(f"no se puede consultar el servidor Ollama en {args.base_url}: {exc}")
    if not server["model"].get("digest"):
        fail(f"el servidor no tiene el modelo {args.model!r}")
    if args.preflight_only:
        print(json.dumps({"environment": redacted_environment(), "server": server, "fixes": fixes}, indent=2, ensure_ascii=False))
        return

    run_dir.mkdir(parents=True)
    work_dir = io_dir / "work"
    work_dir.mkdir(parents=True)

    # .env must not add values: load_dotenv becomes a no-op before core/api.py and narrativeProcess import it.
    import dotenv

    dotenv.load_dotenv = lambda *a, **k: False

    root = logging.getLogger()
    handler = logging.FileHandler(run_dir / "agent_debug.log", mode="w", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    os.chdir(work_dir)
    from core import api
    from input_agent import nodes
    from input_agent.src.llm import LLMService
    from input_agent.src.models import ModificationBatch
    from input_agent.src.tools import find_unresolved_routes

    started = datetime.now(timezone.utc).isoformat()
    api.app_state.thread_id = args.thread_id
    api.app_state.initialize()
    recorder = GraphRecorder(api.app_state.graph)
    api.app_state.graph = recorder

    runtimes = {}
    for name, llm in (("nodes.get_llm", nodes.get_llm()), ("LLMService()", LLMService())):
        runtimes[name] = {"mode": llm.mode, "model": llm.model, "base_url": str(getattr(llm.client, "base_url", "")),
                          "temperature": llm.temperature, "seed": llm.seed, "timeout": llm.timeout}
        if llm.model != args.model or not runtimes[name]["base_url"].startswith(args.base_url.rstrip("/")):
            fail(f"{name} resuelve {runtimes[name]}, no {args.model} en {args.base_url}")

    s0 = copy.deepcopy(api.app_state.initial_input)
    dump(run_dir / "S0.json", s0)

    results_dir = io_dir / "outputs" / "results"
    queries = []
    state_check = None
    for index, query in enumerate(QUERIES, start=1):
        if index in OPTIMIZATION_QUERIES and not args.with_optimization:
            queries.append({"index": index, "category": CATEGORY.get(index), "query": query, "skipped": "sin --with-optimization"})
            continue
        qdir = run_dir / f"q{index}"
        config_before = copy.deepcopy(api.app_state.last_config)
        dump(qdir / "config_before.json", config_before)
        if index == 5:
            a002 = (config_before or {}).get("A002", {})
            t002 = (a002.get("tasks") or {}).get("T002", {}).get("Duration")
            t_wait = a002.get("T_wait")
            state_check = {
                "A002.tasks.T002.Duration": t002,
                "A002.T_wait": t_wait,
                "applied_T002_Duration_85": t002 == 85,
                "applied_T_wait_6": t_wait == 6,
                "only_those_edits_vs_S0": only_case_edits(s0, config_before),
            }
        repo_before = set(REPO_ROOT.iterdir())
        t0 = time.perf_counter()
        response = asyncio.run(api.chat(api.ChatRequest(message=query, thread_id=args.thread_id)))
        elapsed = time.perf_counter() - t0
        final_state = recorder.last_final_state or {}
        config_after = copy.deepcopy(api.app_state.last_config)
        dump(qdir / "response.json", response.model_dump())
        dump(qdir / "node_updates.json", plain(recorder.last_updates))
        dump(qdir / "final_state.json", serializable_state(final_state))
        dump(qdir / "config_after.json", config_after)
        # Outputs of the simulations of this query; in query 5 they are those of the rejected candidate.
        results_copy = qdir / ("rejected_candidate_simulation" if index == 5 else "io_results")
        if results_dir.exists():
            shutil.copytree(results_dir, results_copy)
        summary = {"index": index, "category": CATEGORY.get(index), "query": query, "success": response.success,
                   "elapsed_s": round(elapsed, 1), "message": response.message}
        if index in EDIT_QUERIES:
            report = edit_report(recorder.last_updates, config_before, config_after, find_unresolved_routes, ModificationBatch)
            dump(qdir / "edit_report.json", report)
            summary["outcome"] = report["outcome"]
            summary["routes_resolved"] = [b["routes_resolved"] for b in report["planner_batches"]]
        if index == 5:
            # From the executor's update: the simulator clears validation_errors before the final state.
            executor_updates = [u["update"] for u in recorder.last_updates if u["node"] == "executor"]
            rejection = executor_updates[-1] if executor_updates else {}
            dump(qdir / "violations.json", {
                "source": "executor node update",
                "validation_violations": rejection.get("validation_violations"),
                "validation_errors": rejection.get("validation_errors"),
                "episodic_delta": rejection.get("episodic_delta"),
            })
            dump(qdir / "rejected_candidate.json", final_state.get("episodic_config"))
            state_check["candidate_simulated"] = any("Episódica" in entry for entry in final_state.get("execution_log", []))
            (qdir / "explanation.md").write_text(final_state.get("episodic_report") or "", encoding="utf-8")
            dump(qdir / "feedback.json", {
                "correction_history": final_state.get("correction_history"),
                "execution_log": final_state.get("execution_log"),
                "final_response": response.response,
            })
        if index == 8:
            shared = REPO_ROOT / "Modules" / "petrinet_shared_dicts.json"
            if shared.exists():
                shutil.copy2(shared, qdir / "optimizer_petrinet_shared_dicts.json")
            # The optimizer subprocess runs in the repo root and leaves its convergence plots there.
            for created in sorted(set(REPO_ROOT.iterdir()) - repo_before):
                if created.is_file():
                    shutil.move(str(created), str(qdir / created.name))
                    summary.setdefault("moved_from_repo_root", []).append(created.name)
        queries.append(summary)

    handler.flush()
    files = sorted(p for p in run_dir.rglob("*") if p.is_file())
    manifest = {
        "run_id": run_id,
        "started_utc": started,
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "command": sys.argv,
        "code_path": "core/api.py: AppState.initialize() and the /chat endpoint function, one thread",
        "thread_id": args.thread_id,
        "with_optimization": args.with_optimization,
        "git": {
            "head": git("rev-parse", "HEAD"),
            "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
            "dirty_paths": git("status", "--porcelain", "--", "input_agent", "core", "utils", "config", "Modules",
                               "PetriNetModules", "optimizers").splitlines(),
            "validator_commit": git("log", "-1", "--format=%H", "--", "input_agent/src/tools.py"),
            "executor_commit": git("log", "-1", "--format=%H", "--", "input_agent/nodes.py"),
            "reindex_commit": git("log", "-1", "--format=%H", "--", "input_agent/src/PetriNetConfig.py"),
            "script_commit": git("log", "-1", "--format=%H", "--", "benchmarks/case_study/rerun_case_study.py"),
            "fixes": fixes,
            "release_sha256": sha256_file(RELEASE_FILE),
        },
        "model": args.model,
        "base_url": args.base_url,
        "server": server,
        "llm_runtimes": runtimes,
        "environment": redacted_environment(),
        "dotenv": "disabled (load_dotenv is a no-op for this run)",
        "io_dir": str(io_dir),
        "state_before_q5": state_check,
        "queries": queries,
        "python": platform.python_version(),
        "files": {str(p.relative_to(run_dir)).replace("\\", "/"): sha256_file(p) for p in files},
    }
    dump(run_dir / "manifest.json", manifest)
    print(run_dir)


if __name__ == "__main__":
    main()
