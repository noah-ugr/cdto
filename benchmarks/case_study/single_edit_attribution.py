"""Single-edit simulations behind the causal attributions of Subsection 4.2.

S_{k+1} differs from S_0 in two edits (A002.tasks.T002.Duration 100 -> 85 and A002.T_wait 4 -> 6).
To tell which edit causes each KPI change, each one is simulated alone on S_0, next to S_0 and
S_{k+1}, every configuration in a new process (input_agent.src.fresh_simulation). For each one the
script records the KPIs and the calendar duration of every task of A002 in each execution
(Duration_t0007{j}2 of calculated_task_durations.xlsx; for the shutdown task A002.T003, t000732).

S_0 is the case-study configuration of core/api.py (read with ast, as regenerate_gantt.py does).

Writes benchmarks/results/case_study_attribution/<run_id>/ with one folder per configuration
(config.json, general_outputs_all.json, calculated_task_durations.xlsx), summary.json,
summary.csv and manifest.json.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from regenerate_gantt import case_configurations  # noqa: E402  (same folder)

KPIS = ("Intervention_time_hours", "P4_total_busy_hours", "Net_plan_availability_percent", "Net_plan_unavailability_hours")
A002_TASKS = ("T001", "T002", "T003", "T004")


def configurations() -> dict:
    cases = case_configurations()
    s0 = cases["S_0"]
    t_wait = copy.deepcopy(s0)
    t_wait["A002"]["T_wait"] = 6
    t002 = copy.deepcopy(s0)
    t002["A002"]["tasks"]["T002"]["Duration"] = 85
    return {
        "S_0": (s0, "core/api.py initial_input"),
        "S_0_T_wait_6": (t_wait, "S_0 with only A002.T_wait = 6"),
        "S_0_T002_85": (t002, "S_0 with only A002.tasks.T002.Duration = 85"),
        "S_k+1": (cases["S_k+1"], "S_0 with both edits"),
    }


def a002_calendar_durations(durations_xlsx: Path) -> dict:
    """{task: [calendar duration of execution 1, 2, ...]} for A002 (Activity_022)."""
    import pandas as pd

    df = pd.read_excel(durations_xlsx, sheet_name="Durations")
    rows = df[df["Activity"] == "Activity_022"].sort_values("Execution")
    return {task: [float(v) for v in rows[f"Duration_t0007{int(task[1:])}2"]] for task in A002_TASKS}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True).stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--out-root", default=str(REPO_ROOT / "benchmarks/results/case_study_attribution"))
    args = parser.parse_args()

    from input_agent.src.fresh_simulation import run_petrinets_simulation_fresh

    run_id = args.run_id or f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_single_edits"
    run_dir = Path(args.out_root).resolve() / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    summary = {}
    with tempfile.TemporaryDirectory(prefix="cdto_attr_") as tmp:
        for label, (config, description) in configurations().items():
            io_dir = Path(tmp) / label
            general, _ = run_petrinets_simulation_fresh(config, io_dir=io_dir)
            out = run_dir / label
            out.mkdir()
            (out / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
            for name in ("general_outputs_all.json", "calculated_task_durations.xlsx"):
                shutil.copy2(io_dir / "outputs" / "results" / name, out / name)
            summary[label] = {
                "description": description,
                "kpis": {k: general[k] for k in KPIS},
                "a002_calendar_durations": a002_calendar_durations(out / "calculated_task_durations.xlsx"),
            }

    base = summary["S_0"]
    for entry in summary.values():
        entry["kpi_delta_vs_S_0"] = {k: entry["kpis"][k] - base["kpis"][k] for k in KPIS}
        entry["a002_T003_delta_vs_S_0"] = [
            new - old for new, old in zip(entry["a002_calendar_durations"]["T003"], base["a002_calendar_durations"]["T003"], strict=True)
        ]
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    with (run_dir / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["configuration", *KPIS, *(f"A002.{t}_calendar_h_exec{i}" for t in A002_TASKS for i in (1, 2))])
        for label, entry in summary.items():
            durations = entry["a002_calendar_durations"]
            writer.writerow([label, *(entry["kpis"][k] for k in KPIS), *(durations[t][i] for t in A002_TASKS for i in (0, 1))])

    files = sorted(p for p in run_dir.rglob("*") if p.is_file())
    manifest = {
        "run_id": run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git": {
            "head": git("rev-parse", "HEAD"),
            "dirty_paths": git("status", "--porcelain", "--", "input_agent", "core", "utils", "config", "Modules", "PetriNetModules").splitlines(),
            "script_commit": git("log", "-1", "--format=%H", "--", "benchmarks/case_study/single_edit_attribution.py"),
        },
        "simulation": "input_agent.src.fresh_simulation.run_petrinets_simulation_fresh (one new process per configuration)",
        "configurations": {label: description for label, (_, description) in configurations().items()},
        "summary": summary,
        "files": {str(p.relative_to(run_dir)).replace("\\", "/"): sha256_file(p) for p in files},
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(run_dir)


if __name__ == "__main__":
    main()
