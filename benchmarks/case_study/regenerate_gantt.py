"""Regenerates the Gantt comparison of Subsection 4.2 (gantt_chart_comparison.pdf) from fresh
simulations of S_0 and S_{k+1}.

The figure is built from the engine outputs: each configuration is simulated in a new process
(input_agent.src.fresh_simulation), its calculated_task_durations.xlsx gives the start and end of every
task execution, and both are drawn in two panels that share the time axis. plot_gantt_comparison.py
redraws these simulations in the format of the paper's figure. This script also writes the
per-activity Gantt charts of the repository (input_agent.src.visualization.generate_gantt_charts, the ones
the xAI shows) for each configuration.

S_0 is the case-study configuration of core/api.py (read with ast, without importing core/api.py);
S_{k+1} is S_0 with A002.T002.Duration = 85 and A002.T_wait = 6.

Writes benchmarks/results/case_study_gantt/<run_id>/: gantt_chart_comparison.pdf and .png, for each
configuration its config, general_outputs_all.json, calculated_task_durations.xlsx and per-activity
charts, and manifest.json.
"""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

ACTIVITY_COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]


def case_configurations() -> dict:
    tree = ast.parse((REPO_ROOT / "core" / "api.py").read_text(encoding="utf-8"))
    s0 = next(
        ast.literal_eval(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Dict)
        and any(getattr(t, "attr", None) == "initial_input" for t in node.targets)
    )
    s1 = copy.deepcopy(s0)
    s1["A002"]["tasks"]["T002"]["Duration"] = 85
    s1["A002"]["T_wait"] = 6
    return {"S_0": s0, "S_k+1": s1}


def task_bars(config: dict, durations_xlsx: Path) -> list:
    """(row label, requires shutdown, activity index, [(start, width), ...]) per task, in configuration order.
    Engine columns are t0007{j}{i}_Start/_End with j the task position and i the activity position."""
    import pandas as pd

    df = pd.read_excel(durations_xlsx, sheet_name="Durations")
    activities = [k for k in config if k not in ("runId", "Teams", "Simulation_period")]
    rows = []
    for i, act in enumerate(activities, start=1):
        act_rows = df[df["Activity"].astype(str) == f"Activity_02{i}"]
        for j, (tid, task) in enumerate(config[act]["tasks"].items(), start=1):
            start_col, end_col = f"t0007{j}{i}_Start", f"t0007{j}{i}_End"
            bars = []
            if start_col in act_rows and end_col in act_rows:
                for start, end in zip(act_rows[start_col], act_rows[end_col], strict=True):
                    if pd.notna(start) and pd.notna(end):
                        bars.append((float(start), float(end) - float(start)))
            label = f"{act}·{tid} ({task['Duration']} h)"
            rows.append((label, bool(task.get("Requires_Shutdown")), i - 1, bars))
    return rows


def plot_comparison(panels: list, horizon: float, output_pdf: Path) -> None:
    """panels: [(title, rows)] with rows as returned by task_bars."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    height = max(len(rows) for _, rows in panels)
    fig, axes = plt.subplots(
        len(panels), 1, sharex=True, figsize=(12, 1.6 + 0.45 * height * len(panels))
    )
    for ax, (title, rows) in zip(axes, panels, strict=True):
        for y, (_label, shutdown, act_index, bars) in enumerate(reversed(rows)):
            ax.broken_barh(
                bars,
                (y - 0.35, 0.7),
                facecolors=ACTIVITY_COLORS[act_index % len(ACTIVITY_COLORS)],
                edgecolor="black",
                linewidth=0.4,
                hatch="///" if shutdown else None,
            )
        ax.set_yticks(range(len(rows)))
        ax.set_yticklabels([label for label, *_ in reversed(rows)], fontsize=9)
        ax.set_title(title, fontsize=10, loc="left")
        ax.grid(axis="x", linestyle=":", linewidth=0.5)
    axes[-1].set_xlim(0, horizon)
    axes[-1].set_xlabel("Simulation time (h)")
    fig.legend(
        handles=[
            Patch(facecolor="white", edgecolor="black", hatch="///", label="Requires shutdown")
        ],
        loc="upper right",
        fontsize=8,
    )
    fig.tight_layout()
    fig.savefig(output_pdf, bbox_inches="tight")
    fig.savefig(output_pdf.with_suffix(".png"), dpi=200, bbox_inches="tight")
    plt.close(fig)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True
    ).stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--run-id", default=None)
    parser.add_argument(
        "--out-root", default=str(REPO_ROOT / "benchmarks/results/case_study_gantt")
    )
    args = parser.parse_args()

    from input_agent.src.fresh_simulation import run_petrinets_simulation_fresh
    from input_agent.src.visualization import generate_gantt_charts

    run_id = args.run_id or f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_{uuid.uuid4().hex[:6]}"
    run_dir = Path(args.out_root).resolve() / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    configs = case_configurations()
    panels, kpis = [], {}
    with tempfile.TemporaryDirectory(prefix="cdto_gantt_") as tmp:
        for label, config in configs.items():
            io_dir = Path(tmp) / label
            general, _ = run_petrinets_simulation_fresh(config, io_dir=io_dir)
            results = io_dir / "outputs" / "results"
            out = run_dir / label
            out.mkdir()
            (out / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
            for name in ("general_outputs_all.json", "calculated_task_durations.xlsx"):
                shutil.copy2(results / name, out / name)
            generate_gantt_charts(
                str(out / "calculated_task_durations.xlsx"), output_dir=str(out / "per_activity")
            )
            kpis[label] = general
            title = (
                f"{label}: intervention {general['Intervention_time_hours']:.0f} h, "
                f"net plan availability {general['Net_plan_availability_percent']:.1f} %, "
                f"P4 busy {general['P4_total_busy_hours']:.0f} h"
            )
            panels.append((title, task_bars(config, out / "calculated_task_durations.xlsx")))

    horizon = float(configs["S_0"]["Simulation_period"])
    plot_comparison(panels, horizon, run_dir / "gantt_chart_comparison.pdf")

    files = sorted(p for p in run_dir.rglob("*") if p.is_file())
    manifest = {
        "run_id": run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git": {
            "head": git("rev-parse", "HEAD"),
            "dirty_paths": git(
                "status",
                "--porcelain",
                "--",
                "input_agent",
                "core",
                "utils",
                "config",
                "Modules",
                "PetriNetModules",
            ).splitlines(),
            "script_commit": git(
                "log", "-1", "--format=%H", "--", "benchmarks/case_study/regenerate_gantt.py"
            ),
        },
        "simulation": "input_agent.src.fresh_simulation.run_petrinets_simulation_fresh (one new process per configuration)",
        "configurations": {
            "S_0": "core/api.py initial_input",
            "S_k+1": "S_0 with A002.T002.Duration = 85 and A002.T_wait = 6",
        },
        "kpis": kpis,
        "files": {str(p.relative_to(run_dir)).replace("\\", "/"): sha256_file(p) for p in files},
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(run_dir)


if __name__ == "__main__":
    main()
