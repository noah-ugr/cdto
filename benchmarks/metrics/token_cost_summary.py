"""Summarize P-E vs vanilla token cost along the complexity axis.

This module reads ``uq_complexity_results.csv`` for every model under
``benchmarks/results/models/<model>/complexity/`` and computes the three
token-cost quantities quoted in the paper:

  - tokflat:   relative range (max - min) / min of the mean P-E TotalTokens
               across all complexity levels; the macro takes the maximum over
               backends.
  - tokgrowth: ratio of the mean vanilla TotalTokens at the highest level to
               the lowest level; the macro takes the minimum over backends so
               that "at least" holds for all of them.
  - tokcross:  first evaluated level at which the mean P-E TotalTokens is
               below the vanilla mean, reported per backend together with
               whether P-E stays cheaper at every higher level.

With ``--exclude-zero-tokens`` the means are recomputed from the raw
``benchmark_compare_complexity.json`` records, dropping calls whose logged
``token_usage.total`` is zero (calls with no token usage recorded).

Writes what it prints to ``--output-csv``, one row per (scope, quantity):
the per-model quantities with the model as scope, and the three macros with
scope ``macro`` and the model they are taken from. The default is
``benchmarks/results/token_cost_summary.csv``, or
``token_cost_summary_exclude_zero_tokens.csv`` with ``--exclude-zero-tokens``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, Iterator

import pandas as pd


PLANNER = "planner_executor"
VANILLA = "vanilla"
AXIS = "complexity"

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
PER_MODEL_QUANTITIES = (
    "n_levels", "pe_min", "pe_max", "pe_rel_range", "pe_rel_endpoints",
    "va_lo", "va_hi", "va_ratio_hi_lo", "first_cross", "stays_cheaper",
)


def _resolve_results_root(results_root: str | Path | None) -> Path:
    if results_root is None:
        return Path(__file__).resolve().parent.parent / "results" / "models"
    root = Path(results_root)
    return root if root.is_absolute() else (Path.cwd() / root).resolve()


def _iter_models(results_root: Path, models: list[str] | None) -> Iterator[tuple[str, Path]]:
    names = models or sorted(p.name for p in results_root.iterdir() if p.is_dir())
    for name in names:
        axis_dir = results_root / name / AXIS
        if (axis_dir / f"uq_{AXIS}_results.csv").exists():
            yield name, axis_dir


def _tokens_from_uq_csv(axis_dir: Path) -> pd.DataFrame:
    df = pd.read_csv(axis_dir / f"uq_{AXIS}_results.csv", comment="#")
    return df.pivot(index="Level", columns="Approach", values="TotalTokens_Mean").sort_index()


def _tokens_from_raw_json(axis_dir: Path) -> pd.DataFrame:
    with open(axis_dir / f"benchmark_compare_{AXIS}.json", encoding="utf-8") as f:
        raw = json.load(f)
    df = pd.DataFrame(
        {
            "Approach": r["approach"],
            "Level": r[AXIS],
            "tokens": (r.get("token_usage") or {}).get("total") or 0,
        }
        for r in raw["detailed_results"]
    )
    df = df[df["tokens"] > 0]
    return df.groupby(["Level", "Approach"])["tokens"].mean().unstack().sort_index()


def _summarize_model(tokens: pd.DataFrame) -> dict[str, object]:
    planner = tokens[PLANNER]
    vanilla = tokens[VANILLA]
    cheaper = planner < vanilla

    first_cross = int(cheaper.idxmax()) if cheaper.any() else None
    stays_cheaper = bool(cheaper.loc[first_cross:].all()) if first_cross is not None else False
    lo, hi = tokens.index.min(), tokens.index.max()

    return {
        "n_levels":          len(tokens),
        "pe_min":            planner.min(),
        "pe_max":            planner.max(),
        "pe_rel_range":      (planner.max() - planner.min()) / planner.min(),
        "pe_rel_endpoints":  (planner.loc[hi] - planner.loc[lo]) / planner.loc[lo],
        "va_lo":             vanilla.loc[lo],
        "va_hi":             vanilla.loc[hi],
        "va_ratio_hi_lo":    vanilla.loc[hi] / vanilla.loc[lo],
        "first_cross":       first_cross,
        "stays_cheaper":     stays_cheaper,
    }


def compute_summary(
    results_root: str | Path | None = None,
    models: list[str] | None = None,
    exclude_zero_tokens: bool = False,
) -> pd.DataFrame:
    root = _resolve_results_root(results_root)
    loader = _tokens_from_raw_json if exclude_zero_tokens else _tokens_from_uq_csv

    rows = {name: _summarize_model(loader(axis_dir)) for name, axis_dir in _iter_models(root, models)}
    if not rows:
        raise FileNotFoundError(f"No uq_{AXIS}_results.csv found under {root}")
    return pd.DataFrame(rows).T


def compute_macros(summary: pd.DataFrame) -> dict[str, tuple[str, str]]:
    """(value as printed in the macro, model it comes from) of tokflat, tokgrowth and tokcross."""
    rel_range = summary["pe_rel_range"].astype(float)
    growth = summary["va_ratio_hi_lo"].astype(float)
    crosses = sorted(set(summary["first_cross"].dropna().astype(int)))
    cross = str(crosses[0]) if len(crosses) == 1 else f"{crosses[0]}--{crosses[-1]}"
    return {
        "tokflat":   (f"{100 * rel_range.max():.1f}", str(rel_range.idxmax())),
        "tokgrowth": (f"{growth.min():.1f}", str(growth.idxmin())),
        "tokcross":  (cross, "all"),
    }


def summary_rows(summary: pd.DataFrame) -> pd.DataFrame:
    """Long table of what print_summary prints: per-model quantities and the three macros."""
    rows = [
        {"scope": model, "quantity": quantity, "value": row[quantity], "from": model}
        for model, row in summary.iterrows()
        for quantity in PER_MODEL_QUANTITIES
    ]
    rows += [
        {"scope": "macro", "quantity": name, "value": value, "from": source}
        for name, (value, source) in compute_macros(summary).items()
    ]
    return pd.DataFrame(rows, columns=["scope", "quantity", "value", "from"])


def print_summary(summary: pd.DataFrame) -> None:
    print("-- Per model --")
    for model, row in summary.iterrows():
        print(f"  {model}")
        print(f"    P-E relative range       {100 * row['pe_rel_range']:6.2f} %")
        print(f"    P-E endpoints (hi vs lo) {100 * row['pe_rel_endpoints']:6.2f} %")
        print(f"    Vanilla hi / lo          {row['va_ratio_hi_lo']:6.2f} x")
        print(f"    First P-E < vanilla      {row['first_cross']}  (stays cheaper: {row['stays_cheaper']})")
    print()

    macros = compute_macros(summary)
    flat, flat_from = macros["tokflat"]
    growth, growth_from = macros["tokgrowth"]
    cross, _ = macros["tokcross"]
    print("-- Macros --")
    print(f"  \\newcommand{{\\tokflat}}{{{flat}\\,\\%}}   % max over backends: {flat_from}")
    print(f"  \\newcommand{{\\tokgrowth}}{{{growth}}}   % min over backends: {growth_from}")
    print(f"  \\newcommand{{\\tokcross}}{{{cross}}}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results-root",        default=None)
    parser.add_argument("--models",              nargs="+", default=None)
    parser.add_argument("--exclude-zero-tokens", action="store_true",
                        help="Recompute means from raw JSON, dropping records with zero logged tokens.")
    parser.add_argument("--output-csv",          default=None,
                        help="CSV of the printed figures (default: benchmarks/results/token_cost_summary[_exclude_zero_tokens].csv)")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    summary = compute_summary(args.results_root, args.models, args.exclude_zero_tokens)
    print_summary(summary)

    suffix = "_exclude_zero_tokens" if args.exclude_zero_tokens else ""
    output_csv = args.output_csv or RESULTS_DIR / f"token_cost_summary{suffix}.csv"
    summary_rows(summary).to_csv(output_csv, index=False)
    print(f"\nSaved: {output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
