"""Gantt comparison of Subsection 4.2 in the format of the paper's figure (gantt_chart_comparison.pdf):
one row per task execution (a, b, c...), a blue bar for the baseline S_0 and an orange bar for the
modified configuration S_{k+1} just below it, idle gaps scaled x0.05, start and end times as ticks
(blue for S_0, orange for S_{k+1}), and a table with the times and their differences.

It does not simulate. It reads the fresh simulations that regenerate_gantt.py saved (--source, one
folder per configuration with config.json, calculated_task_durations.xlsx and
general_outputs_all.json) and checks their hashes against that run's manifest.

Two variants, each as PDF and PNG:
- gantt_A001: A001, transitions t000731, t000711 and t000721, first two executions (as in the paper);
- gantt_A002: every task of A002, first two executions.

Transition t0007{j}{i} is task T00j of activity A00i: the engine takes j from the digits of the task
ID and i from those of the activity ID.

Writes benchmarks/results/case_study_gantt/<run_id>/ with the figures, gantt_tables.json (the rows of
each table) and manifest.json (source, hashes, KPIs of both configurations, commits).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import string
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_SOURCE = REPO_ROOT / "benchmarks/results/case_study_gantt/20260929T084426Z_gantt"
CONFIGS = {"baseline": "S_0", "modified": "S_k+1"}
BLUE, ORANGE = "#4472C4", "#ED7D31"  # colours of the paper's figure
IDLE_GAP_SCALE = 0.05
EXECUTIONS = (1, 2)
VARIANTS = {
    # name: (activity, transitions in the order of the paper's figure, or None for all the activity's tasks)
    "gantt_A001": ("A001", ["t000731", "t000711", "t000721"]),
    "gantt_A002": ("A002", None),
}


def digits(key: str) -> int:
    return int(re.findall(r"\d+", key)[0])


def transition_of(activity: str, task: str) -> str:
    """Transition of a task, as the engine names it: t0007{task digits}{activity digits}."""
    return f"t0007{digits(task)}{digits(activity) % 10}"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True).stdout.strip()


def load_source(source: Path) -> dict:
    """Configurations, durations and KPIs of S_0 and S_{k+1}, checked against the source manifest."""
    import pandas as pd

    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    data = {}
    for role, folder in CONFIGS.items():
        files = {name: source / folder / name for name in ("config.json", "calculated_task_durations.xlsx", "general_outputs_all.json")}
        for name, path in files.items():
            if not path.exists():
                raise SystemExit(f"falta {path}: vuelve a ejecutar regenerate_gantt.py")
            recorded = manifest["files"].get(f"{folder}/{name}")
            if recorded != sha256_file(path):
                raise SystemExit(f"{path} no coincide con el hash del manifest de {source.name}")
        data[role] = {
            "config": json.loads(files["config.json"].read_text(encoding="utf-8")),
            "durations": pd.read_excel(files["calculated_task_durations.xlsx"], sheet_name="Durations"),
            "kpis": json.loads(files["general_outputs_all.json"].read_text(encoding="utf-8"))["general_results"][0],
        }
    return data


def times(durations, activity: str, transition: str, execution: int):
    rows = durations[(durations["Activity"] == f"Activity_02{digits(activity) % 10}") & (durations["Execution"] == execution)]
    if rows.empty or f"{transition}_Start" not in rows:
        raise SystemExit(f"{transition} no tiene la ejecución {execution} en calculated_task_durations.xlsx")
    row = rows.iloc[0]
    return float(row[f"{transition}_Start"]), float(row[f"{transition}_End"])


def table_rows(data: dict, activity: str, transitions) -> list:
    """One row per execution of each transition, ordered by execution and baseline start, labelled a, b, c..."""
    tasks = data["baseline"]["config"][activity]["tasks"]
    by_transition = {transition_of(activity, tid): f"{activity}.{tid}" for tid in tasks}
    for role in ("modified",):
        if {transition_of(activity, tid) for tid in data[role]["config"][activity]["tasks"]} != set(by_transition):
            raise SystemExit(f"{activity} no tiene las mismas tareas en S_0 y S_k+1")
    transitions = transitions or sorted(by_transition)
    rows = []
    for execution in EXECUTIONS:
        entries = []
        for transition in transitions:
            b_start, b_end = times(data["baseline"]["durations"], activity, transition, execution)
            m_start, m_end = times(data["modified"]["durations"], activity, transition, execution)
            entries.append({
                "transition": transition, "task": by_transition[transition], "execution": execution,
                "baseline_start": b_start, "baseline_end": b_end, "modified_start": m_start, "modified_end": m_end,
                "delta_start": m_start - b_start, "delta_end": m_end - b_end,
            })
        rows += sorted(entries, key=lambda e: e["baseline_start"])
    for i, row in enumerate(rows):
        row["label"] = string.ascii_lowercase[i]
    return rows


def plot_variant(rows: list, output_pdf: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.patches import Patch

    from input_agent.src.visualization import _build_time_warp  # the repo's idle-gap compression

    starts = [r[f"{s}_start"] for r in rows for s in ("baseline", "modified")]
    ends = [r[f"{s}_end"] for r in rows for s in ("baseline", "modified")]
    warp = _build_time_warp(np.array(starts), np.array(ends), idle_gap_scale=IDLE_GAP_SCALE)
    span = warp(max(ends)) - warp(min(starts))

    # visualization.py sets Times New Roman globally; the paper's figure uses matplotlib's defaults.
    with plt.style.context("default"):
        width = 15.0
        plot_h, table_h = 1.6 + 0.55 * len(rows), 0.5 + 0.3 * (len(rows) + 1)
        fig, (ax, ax_table) = plt.subplots(
            2, 1, figsize=(width, plot_h + table_h), gridspec_kw={"height_ratios": [plot_h, table_h]}
        )

        offset, height = 0.2, 0.36
        for y, row in enumerate(rows):
            for scenario, color, dy in (("baseline", BLUE, offset), ("modified", ORANGE, -offset)):
                x0, x1 = warp(row[f"{scenario}_start"]), warp(row[f"{scenario}_end"])
                ax.barh(y + dy, x1 - x0, left=x0, height=height, color=color, edgecolor="black", linewidth=0.6, zorder=2)
                ax.text((x0 + x1) / 2, y + dy, row["label"], ha="center", va="center", color="white",
                        fontsize=12, fontweight="bold", zorder=3)

        boundaries = {
            scenario: sorted({row[f"{scenario}_{edge}"] for row in rows for edge in ("start", "end")})
            for scenario in ("baseline", "modified")
        }
        positions = sorted({warp(t) for values in boundaries.values() for t in values})
        for x in positions:
            ax.axvline(x, color="gray", alpha=0.35, linewidth=0.8, zorder=0)
        ax.set_xticks(positions)
        ax.set_xticklabels([])
        ax.set_yticks(range(len(rows)))
        ax.set_yticklabels([row["label"] for row in rows], fontsize=14)
        ax.set_ylabel("Task", fontsize=16)
        ax.grid(True, axis="y", alpha=0.35, linewidth=0.7, zorder=0)
        pad = 0.01 * span
        ax.set_xlim(warp(min(starts)) - pad, warp(max(ends)) + pad)
        ax.set_ylim(-0.7, len(rows) - 0.3)

        # Tick labels in two rows: baseline times in blue, modified times in orange.
        labels = {}
        for scenario, color, dy in (("baseline", BLUE, -5), ("modified", ORANGE, -24)):
            labels[scenario] = [
                ax.annotate(f"{t:.0f}", xy=(warp(t), 0), xycoords=ax.get_xaxis_transform(), xytext=(0, dy),
                            textcoords="offset points", ha="center", va="top", color=color, fontsize=12,
                            fontweight="bold")
                for t in boundaries[scenario]
            ]
        ax.set_xlabel(f"Time (idle gaps scaled ×{IDLE_GAP_SCALE})", fontsize=16, labelpad=34)  # noqa: RUF001
        ax.legend(
            handles=[Patch(facecolor=BLUE, edgecolor="black", label="Baseline ($S_0$)"),
                     Patch(facecolor=ORANGE, edgecolor="black", label="Modified ($S_{k+1}$)")],
            loc="lower center", bbox_to_anchor=(0.5, 1.01), ncol=2, fontsize=13,
        )

        ax_table.axis("off")
        columns = ["Label", "Transition", "Task", "Baseline Start", "Baseline End", "Modified Start",
                   "Modified End", "ΔStart", "ΔEnd"]
        cells = [
            [r["label"], r["transition"], r["task"], f"{r['baseline_start']:.1f}", f"{r['baseline_end']:.1f}",
             f"{r['modified_start']:.1f}", f"{r['modified_end']:.1f}", f"{r['delta_start']:+.1f}", f"{r['delta_end']:+.1f}"]
            for r in rows
        ]
        table = ax_table.table(cellText=cells, colLabels=columns, loc="center", cellLoc="center",
                               colWidths=[0.06, 0.12, 0.11, 0.12, 0.12, 0.12, 0.12, 0.09, 0.09])
        table.auto_set_font_size(False)
        table.set_fontsize(12)
        for j in range(len(columns)):
            table[(0, j)].set_facecolor(BLUE)
            table[(0, j)].set_text_props(weight="bold", color="white")
        for i in range(1, len(cells) + 1):
            for j in range(len(columns)):
                table[(i, j)].set_facecolor("#F2F2F2" if i % 2 else "#E7E6E6")
        table.scale(1, 1.3)

        fig.tight_layout()
        # If two tick labels of the same colour overlap, move the later one right just enough.
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        for texts in labels.values():
            previous = None
            for text in texts:
                box = text.get_window_extent(renderer)
                if previous is not None and box.x0 < previous.x1 + 3:
                    shift = (previous.x1 + 3 - box.x0) * 72 / fig.dpi
                    text.xyann = (text.xyann[0] + shift, text.xyann[1])
                    box = text.get_window_extent(renderer)
                previous = box
        fig.savefig(output_pdf, bbox_inches="tight")
        fig.savefig(output_pdf.with_suffix(".png"), dpi=200, bbox_inches="tight")
        plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", default=str(DEFAULT_SOURCE), help="output folder of regenerate_gantt.py")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--out-root", default=str(REPO_ROOT / "benchmarks/results/case_study_gantt"))
    args = parser.parse_args()

    source = Path(args.source).resolve()
    data = load_source(source)
    run_id = args.run_id or f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_gantt_paper_format"
    run_dir = Path(args.out_root).resolve() / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    tables = {}
    for name, (activity, transitions) in VARIANTS.items():
        tables[name] = table_rows(data, activity, transitions)
        plot_variant(tables[name], run_dir / f"{name}.pdf")
    (run_dir / "gantt_tables.json").write_text(json.dumps(tables, indent=2), encoding="utf-8")

    source_manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    files = sorted(p for p in run_dir.rglob("*") if p.is_file())
    manifest = {
        "run_id": run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source": {"folder": str(source.relative_to(REPO_ROOT)).replace("\\", "/"), "run_id": source_manifest.get("run_id"),
                   "head": source_manifest.get("git", {}).get("head"), "hashes_checked": True},
        "simulated": False,
        "git": {"head": git("rev-parse", "HEAD"),
                "script_commit": git("log", "-1", "--format=%H", "--", "benchmarks/case_study/plot_gantt_comparison.py")},
        "configurations": source_manifest.get("configurations"),
        "kpis": {CONFIGS[role]: data[role]["kpis"] for role in CONFIGS},
        "transitions": {name: {r["transition"]: r["task"] for r in rows} for name, rows in tables.items()},
        "files": {str(p.relative_to(run_dir)).replace("\\", "/"): sha256_file(p) for p in files},
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(run_dir)


if __name__ == "__main__":
    main()
