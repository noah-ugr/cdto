"""Summarize P-E vs vanilla improvements from benchmark UQ CSV files.

This module reads every ``uq_*_results.csv`` file under
``benchmarks/results/models/<model>/<axis>/`` and computes paired mean
improvements between ``planner_executor`` (P-E) and ``vanilla``.

The complexity axis is split into two regimes at ``--budget-safe-max-level``
(default 32): C <= 32 is budget-safe, and from C = 40 vanilla outputs start
to hit the 4096-token output budget (Claude and Llama truncate their largest
samples at C = 40). C <= 32 lies below every backend's C*_low measured in its
own tokens (Claude 34, Llama 38, gpt-oss 45, GPT-5.4 48). Pass 49 to reproduce
the earlier split at the cl100k C*_low. The completeness axis is kept as a
single regime.

Sign convention:
- For quality metrics (ExactMatch, F1Micro), positive means P-E is better.
- For efficiency and error metrics (Latency, TotalTokens, CollateralRate,
  OmissionRate), negative means P-E is better.

Produces three CSVs matching the three parts of table tab:cdto_improvement_summary:
  - cdto_vs_vanilla_by_model_axis_regime.csv  (individual table rows)
  - cdto_vs_vanilla_mean_per_model.csv        (per-model budget-safe mean, weighted by n)
  - cdto_vs_vanilla_overall.csv               (overall budget-safe mean, weighted by n)
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

import pandas as pd


PLANNER = "planner_executor"
VANILLA = "vanilla"

# Highest complexity level of the budget-safe regime (last level before C = 40).
BUDGET_SAFE_MAX_LEVEL = 32

# Regime labels.
REGIME_BUDGET_SAFE = "budget_safe"
REGIME_OUTPUT_WALL = "output_wall"
REGIME_COMPLETENESS = "completeness"


@dataclass(frozen=True)
class MetricSpec:
    name: str
    column: str
    scale: str
    unit: str


METRICS: list[MetricSpec] = [
    MetricSpec("ExactMatch",     "ExactMatch_Mean",     "abs", "%"),
    MetricSpec("F1Micro",        "F1Micro_Mean",        "abs", "%"),
    MetricSpec("Latency",        "Latency_Mean",        "rel", "%"),
    MetricSpec("TotalTokens",    "TotalTokens_Mean",    "rel", "%"),
    MetricSpec("CollateralRate", "CollateralRate_Mean", "abs", "%"),
    MetricSpec("OmissionRate",   "OmissionRate_Mean",   "abs", "%"),
]


def _resolve_results_root(results_root: str | Path | None) -> Path:
    if results_root is None:
        return Path(__file__).resolve().parent.parent / "results" / "models"
    root = Path(results_root)
    return root if root.is_absolute() else (Path.cwd() / root).resolve()


def _iter_uq_csvs(results_root: Path) -> Iterator[tuple[str, str, Path]]:
    for model_dir in sorted(p for p in results_root.iterdir() if p.is_dir()):
        for axis_dir in sorted(p for p in model_dir.iterdir() if p.is_dir()):
            for csv_path in sorted(axis_dir.glob("uq_*_results.csv")):
                yield model_dir.name, axis_dir.name, csv_path


def _read_uq_csv(csv_path: Path) -> pd.DataFrame:
    return pd.read_csv(csv_path, comment="#")


def _paired_improvement(planner_value: float, vanilla_value: float, metric: MetricSpec) -> float:
    if metric.scale == "abs":
        return (planner_value - vanilla_value) * 100.0

    if vanilla_value == 0:
        raise ZeroDivisionError(f"Vanilla value is zero for {metric.name}")
    return ((planner_value - vanilla_value) / abs(vanilla_value)) * 100.0


def _regime_for(axis: str, level: int, budget_safe_max_level: int) -> str:
    if axis == "completeness":
        return REGIME_COMPLETENESS
    if axis == "complexity":
        return REGIME_BUDGET_SAFE if level <= budget_safe_max_level else REGIME_OUTPUT_WALL
    return axis


def _collect_rows(results_root: Path, budget_safe_max_level: int) -> list[dict[str, object]]:
    """Extract one row per (model, axis, level, metric) with the P-E vs Vanilla delta."""
    rows: list[dict[str, object]] = []

    for model_name, axis_name, csv_path in _iter_uq_csvs(results_root):
        df = _read_uq_csv(csv_path)

        if "Approach" not in df.columns or "Level" not in df.columns:
            continue

        for level, level_df in df.groupby("Level", sort=True):
            by_approach = level_df.set_index("Approach")
            if PLANNER not in by_approach.index or VANILLA not in by_approach.index:
                continue

            planner_row = by_approach.loc[PLANNER]
            vanilla_row = by_approach.loc[VANILLA]
            regime = _regime_for(axis_name, int(level), budget_safe_max_level)

            for metric in METRICS:
                if metric.column not in by_approach.columns:
                    continue
                planner_value = planner_row[metric.column]
                vanilla_value = vanilla_row[metric.column]
                if pd.isna(planner_value) or pd.isna(vanilla_value):
                    continue

                rows.append({
                    "model":  model_name,
                    "axis":   axis_name,
                    "regime": regime,
                    "metric": metric.name,
                    "level":  int(level),
                    "delta":  _paired_improvement(float(planner_value), float(vanilla_value), metric),
                    "unit":   metric.unit,
                })

    return rows


# ══════════════════════════════════════════════════════════════════════════════
# The three tables we care about
# ══════════════════════════════════════════════════════════════════════════════

def _table_by_model_axis_regime(rows: list[dict[str, object]]) -> pd.DataFrame:
    """One row per (model, axis, regime, metric). Feeds the individual table rows."""
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return (
        df.groupby(["model", "axis", "regime", "metric", "unit"], as_index=False)
        .agg(mean_delta=("delta", "mean"), n_values=("delta", "count"))
        .sort_values(["model", "axis", "regime", "metric"])
        .reset_index(drop=True)
    )


def _table_mean_per_model(rows: list[dict[str, object]]) -> pd.DataFrame:
    """
    Per-model budget-safe mean, weighted by n. Feeds the 'Mean (budget-safe)'
    row of each model in tab:cdto_improvement_summary.

    Budget-safe = completeness + complexity C <= budget_safe_max_level.
    """
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df[df["regime"].isin([REGIME_COMPLETENESS, REGIME_BUDGET_SAFE])]
    if df.empty:
        return df
    # Weighted by n means: since every level contributes equally to the metric
    # sum, taking the mean over all rows in the filtered set IS the weighted
    # mean (weights = 1 per level).
    return (
        df.groupby(["model", "metric", "unit"], as_index=False)
        .agg(mean_delta=("delta", "mean"), n_values=("delta", "count"))
        .sort_values(["model", "metric"])
        .reset_index(drop=True)
    )


def _table_overall(rows: list[dict[str, object]]) -> pd.DataFrame:
    """
    Overall budget-safe mean across all models, weighted by n. Feeds the
    final 'Overall (budget-safe)' row of tab:cdto_improvement_summary.
    """
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df[df["regime"].isin([REGIME_COMPLETENESS, REGIME_BUDGET_SAFE])]
    if df.empty:
        return df
    return (
        df.groupby(["metric", "unit"], as_index=False)
        .agg(mean_delta=("delta", "mean"), n_values=("delta", "count"))
        .sort_values("metric")
        .reset_index(drop=True)
    )


def compute_tables(
    results_root: str | Path | None = None,
    budget_safe_max_level: int = BUDGET_SAFE_MAX_LEVEL,
) -> dict[str, pd.DataFrame]:
    root = _resolve_results_root(results_root)
    rows = _collect_rows(root, budget_safe_max_level)
    return {
        "by_model_axis_regime": _table_by_model_axis_regime(rows),
        "mean_per_model":       _table_mean_per_model(rows),
        "overall":              _table_overall(rows),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Output
# ══════════════════════════════════════════════════════════════════════════════

def _fmt(value: float) -> str:
    return "n/a" if pd.isna(value) else f"{value:+.2f}"


def print_summary(tables: dict[str, pd.DataFrame], budget_safe_max_level: int = BUDGET_SAFE_MAX_LEVEL) -> None:
    print(f"P-E vs Vanilla summary. Budget-safe complexity: C <= {budget_safe_max_level}\n")

    # ── Per-model, per-axis, per-regime ────────────────────────────────────
    by_car = tables["by_model_axis_regime"]
    if not by_car.empty:
        for model in by_car["model"].drop_duplicates().tolist():
            print(f"── {model} ──")
            model_df = by_car[by_car["model"] == model]
            for axis_val, regime_val in [
                ("completeness", REGIME_COMPLETENESS),
                ("complexity",   REGIME_BUDGET_SAFE),
                ("complexity",   REGIME_OUTPUT_WALL),
            ]:
                cell = model_df[(model_df["axis"] == axis_val) & (model_df["regime"] == regime_val)]
                if cell.empty:
                    continue
                n = int(cell["n_values"].iloc[0])
                print(f"  {axis_val} / {regime_val}  (n={n})")
                for metric in METRICS:
                    row = cell[cell["metric"] == metric.name]
                    if not row.empty:
                        print(f"    {metric.name:16s} {_fmt(float(row.iloc[0]['mean_delta']))}")
            print()

    # ── Mean per model (budget-safe) ───────────────────────────────────────
    per_model = tables["mean_per_model"]
    if not per_model.empty:
        print("── Mean per model (budget-safe, weighted by n) ──")
        for model in per_model["model"].drop_duplicates().tolist():
            model_df = per_model[per_model["model"] == model]
            print(f"  {model}")
            for metric in METRICS:
                row = model_df[model_df["metric"] == metric.name]
                if not row.empty:
                    print(f"    {metric.name:16s} {_fmt(float(row.iloc[0]['mean_delta']))}")
        print()

    # ── Overall ────────────────────────────────────────────────────────────
    overall = tables["overall"]
    if not overall.empty:
        n = int(overall["n_values"].iloc[0])
        print(f"── Overall (budget-safe, weighted by n, n={n}) ──")
        for metric in METRICS:
            row = overall[overall["metric"] == metric.name]
            if not row.empty:
                print(f"  {metric.name:16s} {_fmt(float(row.iloc[0]['mean_delta']))}")


def save_tables(tables: dict[str, pd.DataFrame], output_dir: str | Path, suffix: str = "") -> list[Path]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    saved: list[Path] = []
    for name, table in tables.items():
        path = output_path / f"cdto_vs_vanilla_{name}{suffix}.csv"
        table.to_csv(path, index=False, quoting=csv.QUOTE_MINIMAL)
        saved.append(path)
    return saved


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", default=None)
    parser.add_argument("--output-dir",   default=None)
    parser.add_argument("--budget-safe-max-level", type=int, default=BUDGET_SAFE_MAX_LEVEL,
                        help="Highest complexity level counted as budget-safe (49 = earlier C*_low split)")
    parser.add_argument("--output-suffix", default="",
                        help="Suffix appended to the output CSV names (e.g. _cut49)")
    parser.add_argument("--quiet",        action="store_true")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    tables = compute_tables(args.results_root, args.budget_safe_max_level)

    if args.output_dir is None:
        output_dir = _resolve_results_root(args.results_root).parent
    else:
        output_dir = Path(args.output_dir)
        if not output_dir.is_absolute():
            output_dir = (Path.cwd() / output_dir).resolve()

    saved = save_tables(tables, output_dir, args.output_suffix)

    if not args.quiet:
        print_summary(tables, args.budget_safe_max_level)
        print("\nSaved:")
        for path in saved:
            print(f"  {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())