"""Per-level tables of the benchmark from the per-cell UQ CSVs.

These are the per-level means and 95 % intervals that the note of tab:cdto_improvement_summary
says are archived in the repository. The intervals are those of Supplementary Material C
(supp:uq, Uncertainty estimation).

This module reads ``uq_<axis>_results.csv`` under
``benchmarks/results/models/<model>/<axis>/``. Those CSVs are built by
``petri_net_uq.py`` from ``benchmark_compare_<axis>_rescored.json``, so F1,
collateral rate and omission rate are those of the corrected excision metric
(empty delta lists are not keys, see ``comparison_metrics.py``). Exact match,
tokens and latency are the logged values.

Each cell is one (backend, axis, approach, level) with n = 50: the mean and
its 95 % interval (exact match: double bootstrap; the other metrics: BCa),
as in the CSVs. No resampling is done here.

Writes to ``--output-dir`` (default ``benchmarks/results/per_level/``):
  - per_level_<axis>.csv   one row per backend and level, both approaches
  - per_level_tables.md    one accuracy table and one cost table per backend and axis
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Iterable

import pandas as pd


PLANNER = "planner_executor"
VANILLA = "vanilla"
APPROACHES = {PLANNER: "PE", VANILLA: "Vanilla"}
AXES = ["complexity", "completeness"]

MODELS = {
    "claude-sonnet-4-6": "Claude Sonnet 4.6",
    "gpt-5.4": "GPT-5.4",
    "gpt-oss_20b": "gpt-oss:20b",
    "llama3.1_latest": "Llama 3.1 8B",
}

# (CSV prefix, table header, number format)
ACCURACY = [
    ("ExactMatch", "Exact match", "{:.2f}"),
    ("F1Micro", "F1 micro", "{:.3f}"),
    ("CollateralRate", "Collateral rate", "{:.3f}"),
    ("OmissionRate", "Omission rate", "{:.3f}"),
]
COST = [
    ("TotalTokens", "Total tokens", "{:.0f}"),
    ("Latency", "Latency (s)", "{:.1f}"),
]

AXIS_LEVEL = {
    "complexity": "C = activities x tasks per activity",
    "completeness": "C = instructions in the request (N = 16)",
}


def _resolve(path: str | Path | None, default: Path) -> Path:
    if path is None:
        return default
    path = Path(path)
    return path if path.is_absolute() else (Path.cwd() / path).resolve()


def _read_manifest(csv_path: Path) -> dict[str, str]:
    """The ``# key: value`` lines petri_net_uq.py writes before the header."""
    manifest = {}
    with open(csv_path, encoding="utf-8") as f:
        for line in f:
            if not line.startswith("#"):
                break
            key, sep, value = line[1:].strip().partition(":")
            if sep and value.strip():
                manifest[key.strip()] = value.strip()
    return manifest


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_cells(results_root: Path, axis: str) -> tuple[pd.DataFrame, list[dict]]:
    """Wide frame (one row per backend and level) and the provenance of each source CSV."""
    frames, sources = [], []
    for model, label in MODELS.items():
        csv_path = results_root / model / axis / f"uq_{axis}_results.csv"
        if not csv_path.exists():
            continue
        df = pd.read_csv(csv_path, comment="#")
        manifest = _read_manifest(csv_path)
        sources.append({
            "backend": label,
            "csv": csv_path,
            "csv_sha256": _sha256(csv_path),
            "input_file": manifest.get("input_file", ""),
            "input_sha256": manifest.get("input_sha256", ""),
            "uq_run_id": manifest.get("run_id", ""),
        })

        metric_cols = [c for c in df.columns if c not in ("Approach", "Level", "NSamples")]
        wide = None
        for approach, tag in APPROACHES.items():
            part = df[df["Approach"] == approach].set_index("Level")
            part = part[["NSamples", *metric_cols]].add_prefix(f"{tag}_")
            wide = part if wide is None else wide.join(part, how="outer")
        wide = wide.reset_index()
        wide.insert(0, "Backend", label)
        frames.append(wide)

    table = pd.concat(frames, ignore_index=True)
    return table.sort_values(["Backend", "Level"], key=_backend_order).reset_index(drop=True), sources


def _backend_order(col: pd.Series) -> pd.Series:
    if col.name == "Backend":
        order = {label: i for i, label in enumerate(MODELS.values())}
        return col.map(order)
    return col


def _cell(row: pd.Series, tag: str, metric: str, fmt: str) -> str:
    mean = row.get(f"{tag}_{metric}_Mean")
    lo = row.get(f"{tag}_{metric}_CI_Lower")
    hi = row.get(f"{tag}_{metric}_CI_Upper")
    if pd.isna(mean):
        return "n/a"
    return f"{fmt.format(mean)} [{fmt.format(lo)}, {fmt.format(hi)}]"


def _markdown_table(rows: pd.DataFrame, metrics: list[tuple[str, str, str]]) -> list[str]:
    header = ["C", "n"] + [f"{name} {tag}" for _, name, _ in metrics for tag in APPROACHES.values()]
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---:" for _ in header) + "|"]
    for _, row in rows.iterrows():
        n_pe, n_v = row.get("PE_NSamples"), row.get("Vanilla_NSamples")
        n = f"{int(n_pe)}" if n_pe == n_v else f"{n_pe:.0f}/{n_v:.0f}"
        cells = [f"{int(row['Level'])}", n]
        for metric, _, fmt in metrics:
            cells += [_cell(row, tag, metric, fmt) for tag in APPROACHES.values()]
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def render_markdown(tables: dict[str, pd.DataFrame], sources: dict[str, list[dict]]) -> str:
    out = [
        "# Per-level results",
        "",
        "Per-level means and 95 % intervals behind the note of `tab:cdto_improvement_summary`;",
        "the intervals are those of Supplementary Material C (Uncertainty estimation).",
        "",
        "Generated by `python benchmarks/metrics/per_level_tables.py` from the per-cell CSVs",
        "`benchmarks/results/models/<backend>/<axis>/uq_<axis>_results.csv`. No new inference.",
        "",
        "- **Metric.** F1 micro, collateral rate and omission rate are those of the corrected excision",
        "  metric: `benchmark_compare_<axis>_rescored.json`, in which empty delta lists",
        "  (`new_activities[]`, `deleted_activities[]` and any empty `old[]`/`new[]`) are not keys.",
        "  Exact match, tokens and latency are the logged values.",
        "- **Cells.** One cell is one (backend, axis, approach, level) with n = 50. Each value is the",
        "  mean and its 95 % interval: double bootstrap for exact match, BCa with 10 000 resamples",
        "  for the other metrics, master seed 42 ([benchmark.md](../../../docs/benchmark.md#bootstrap)).",
        "- **Approaches.** PE is the planner-executor in benchmark mode; Vanilla returns the full",
        "  configuration. Lower is better for collateral rate, omission rate, tokens and latency.",
        "- **Calls without a configuration** (firewall timeouts, hard kills) are scored as `json_base`",
        "  with zero tokens and zero latency.",
        "",
    ]
    for axis, table in tables.items():
        out += [f"## {axis.capitalize()} axis", "", f"Level: {AXIS_LEVEL[axis]}.", ""]
        for label in MODELS.values():
            rows = table[table["Backend"] == label]
            if rows.empty:
                continue
            out += [f"### {label}, {axis}", "", "Accuracy", ""]
            out += _markdown_table(rows, ACCURACY)
            out += ["", "Cost", ""]
            out += _markdown_table(rows, COST)
            out.append("")
    out += ["## Sources", "", "| Axis | Backend | CSV SHA-256 | UQ run | Input (`_rescored.json`) SHA-256 |",
            "|---|---|---|---|---|"]
    for axis, entries in sources.items():
        for s in entries:
            out.append(f"| {axis} | {s['backend']} | `{s['csv_sha256'][:16]}…` | `{s['uq_run_id']}` | `{s['input_sha256']}` |")
    out.append("")
    return "\n".join(out)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results-root", default=None,
                        help="Folder with <model>/<axis>/uq_<axis>_results.csv (default: benchmarks/results/models)")
    parser.add_argument("--output-dir", default=None,
                        help="Output folder (default: benchmarks/results/per_level)")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    repo_root = Path(__file__).resolve().parent.parent.parent
    results_root = _resolve(args.results_root, repo_root / "benchmarks" / "results" / "models")
    output_dir = _resolve(args.output_dir, repo_root / "benchmarks" / "results" / "per_level")
    output_dir.mkdir(parents=True, exist_ok=True)

    tables, sources = {}, {}
    for axis in AXES:
        table, axis_sources = load_cells(results_root, axis)
        tables[axis], sources[axis] = table, axis_sources
        csv_path = output_dir / f"per_level_{axis}.csv"
        table.to_csv(csv_path, index=False)
        print(f"Saved: {csv_path} ({len(table)} rows)")

    md_path = output_dir / "per_level_tables.md"
    md_path.write_text(render_markdown(tables, sources), encoding="utf-8")
    print(f"Saved: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
