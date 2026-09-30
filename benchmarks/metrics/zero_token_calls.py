"""Effect of vanilla calls that logged zero tokens on the budget-safe P-E vs vanilla means.

Some vanilla calls log ``token_usage.total == 0``: firewall timeouts (scored as
failures) and completed calls for which the server returned no usage. Both pull
the vanilla token mean down. This module recomputes the budget-safe mean of the
per-level P-E vs vanilla deltas (completeness + complexity C <= 32, as in
``cdto_vs_vanilla_summary.py``) under four scenarios:

- as_logged:        all calls;
- drop_unpaired:    zero-token vanilla calls removed from vanilla only;
- drop_paired:      the affected samples removed from both approaches;
- drop_timeouts:    only the firewall timeouts removed, paired.

Deltas use the summary's conventions: percentage points for ExactMatch,
F1Micro, CollateralRate and OmissionRate; relative % for Latency and
TotalTokens. Reads the re-scored JSONs (``--suffix``) so F1, collateral and
omission follow the corrected metric; exact match and tokens are identical in
both files.

Outputs:
- ``zero_token_calls.csv``: the two regimes pooled (completeness + complexity
  C <= 32), per model and scenario.
- ``zero_token_calls_by_axis.csv``: the same scenarios for each regime on its
  own, complexity C <= 32 and completeness, with ``ExactMatchChange``, the
  exact-match delta minus that of ``as_logged`` (pp).

It also prints, per model, the figures of the footnote in Section 5 under
``drop_paired``: the TotalTokens delta of each regime and the largest change
of the exact-match delta across the two.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import pandas as pd


PLANNER = "planner_executor"
VANILLA = "vanilla"
BUDGET_SAFE_MAX_LEVEL = 32

METRICS = {  # name: (record field, scale)
    "ExactMatch":     ("exact_match", "abs"),
    "F1Micro":        ("f1_micro", "abs"),
    "Latency":        ("latency_s", "rel"),
    "TotalTokens":    ("tokens", "rel"),
    "CollateralRate": ("collateral_rate", "abs"),
    "OmissionRate":   ("omission_rate", "abs"),
}


def _resolve_results_root(results_root: str | Path | None) -> Path:
    if results_root is None:
        return Path(__file__).resolve().parent.parent / "results" / "models"
    root = Path(results_root)
    return root if root.is_absolute() else (Path.cwd() / root).resolve()


def _load_axis(model_dir: Path, axis: str, suffix: str) -> pd.DataFrame:
    path = model_dir / axis / f"benchmark_compare_{axis}_{suffix}.json"
    if not path.exists():
        path = model_dir / axis / f"benchmark_compare_{axis}.json"
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    df = pd.DataFrame(raw["detailed_results"])
    df["tokens"] = df["token_usage"].map(lambda u: (u or {}).get("total") or 0)
    df["timeout"] = df["is_timeout"].eq(True) if "is_timeout" in df else False
    df["axis"] = axis
    df["level"] = df[axis]
    fields = [field for field, _ in METRICS.values()]
    return df[["axis", "level", "sample_idx", "approach", "timeout", *fields]]


def _budget_safe_mean(df: pd.DataFrame) -> dict[str, float]:
    means = df.groupby(["axis", "level", "approach"]).mean(numeric_only=True).unstack("approach")
    result = {}
    for metric, (field, scale) in METRICS.items():
        pe, va = means[(field, PLANNER)], means[(field, VANILLA)]
        delta = (pe - va) * 100 if scale == "abs" else (pe - va) / va.abs() * 100
        result[metric] = delta.mean()
    result["n_levels"] = len(means)
    return result


def analyze_model(model_dir: Path, budget_safe_max_level: int, suffix: str) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    df = pd.concat([_load_axis(model_dir, a, suffix) for a in ("complexity", "completeness")], ignore_index=True)
    df = df[(df["axis"] == "completeness") | (df["level"] <= budget_safe_max_level)]

    key = pd.Series(list(zip(df["axis"], df["level"], df["sample_idx"])), index=df.index)
    zero = (df["tokens"] == 0) & (df["approach"] == VANILLA)
    zero_keys = set(key[zero])
    timeout_keys = set(key[df["timeout"]])

    counts = {
        "vanilla_calls":         int((df["approach"] == VANILLA).sum()),
        "zero_token_calls":      int(zero.sum()),
        "zero_token_complexity": int((zero & (df["axis"] == "complexity")).sum()),
        "zero_token_completeness": int((zero & (df["axis"] == "completeness")).sum()),
        "timeouts":              int((zero & df["timeout"]).sum()),
    }
    scenarios = {
        "as_logged":     pd.Series(True, index=df.index),
        "drop_unpaired": ~zero,
        "drop_paired":   ~key.isin(zero_keys),
        "drop_timeouts": ~key.isin(timeout_keys),
    }
    table = pd.DataFrame({name: _budget_safe_mean(df[keep]) for name, keep in scenarios.items()}).T

    # Each regime on its own, with the same scenario masks.
    by_axis = []
    for axis in ("complexity", "completeness"):
        in_axis = df["axis"] == axis
        axis_table = pd.DataFrame(
            {name: _budget_safe_mean(df[in_axis & keep]) for name, keep in scenarios.items()}
        ).T
        axis_table["ExactMatchChange"] = axis_table["ExactMatch"] - axis_table.loc["as_logged", "ExactMatch"]
        axis_table["zero_token_calls"] = int((zero & in_axis).sum())
        by_axis.append(axis_table.rename_axis("scenario").reset_index().assign(axis=axis))
    return counts, table, pd.concat(by_axis, ignore_index=True)


def footnote_figures(by_axis: pd.DataFrame, scenario: str = "drop_paired") -> dict[str, float | str]:
    """TotalTokens delta of each regime and the largest exact-match change across both, under scenario."""
    rows = by_axis[by_axis["scenario"] == scenario].set_index("axis")
    largest = rows["ExactMatchChange"].abs().idxmax()
    return {
        "scenario": scenario,
        "tokens_complexity": float(rows.loc["complexity", "TotalTokens"]),
        "tokens_completeness": float(rows.loc["completeness", "TotalTokens"]),
        "exact_match_change": float(rows.loc[largest, "ExactMatchChange"]),
        "exact_match_change_axis": largest,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results-root", default=None)
    parser.add_argument("--models", nargs="+", default=["llama3.1_latest", "gpt-oss_20b"])
    parser.add_argument("--budget-safe-max-level", type=int, default=BUDGET_SAFE_MAX_LEVEL)
    parser.add_argument("--suffix", default="rescored", help="Suffix of the re-scored JSONs to read")
    parser.add_argument("--output", default=None,
                        help="CSV path. Defaults to benchmarks/results/zero_token_calls.csv")
    parser.add_argument("--output-by-axis", default=None,
                        help="Per-regime CSV path. Defaults to benchmarks/results/zero_token_calls_by_axis.csv")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    root = _resolve_results_root(args.results_root)

    frames, axis_frames = [], []
    pd.set_option("display.width", 200)
    for model in args.models:
        counts, table, by_axis = analyze_model(root / model, args.budget_safe_max_level, args.suffix)
        print(f"-- {model}: {counts}")
        print(table.round(2).to_string())
        figures = footnote_figures(by_axis)
        print(
            f"   {figures['scenario']}: TotalTokens complexity (C <= {args.budget_safe_max_level}) "
            f"{figures['tokens_complexity']:+.1f} %, completeness {figures['tokens_completeness']:+.1f} %; "
            f"largest ExactMatch change {figures['exact_match_change']:+.1f} pp ({figures['exact_match_change_axis']})"
        )
        print()
        frames.append(table.assign(model=model, **counts).rename_axis("scenario").reset_index())
        axis_frames.append(by_axis.assign(model=model, complexity_max_level=args.budget_safe_max_level))

    output = Path(args.output) if args.output else root.parent / "zero_token_calls.csv"
    pd.concat(frames, ignore_index=True).to_csv(output, index=False)
    print(f"Saved: {output}")
    output_by_axis = Path(args.output_by_axis) if args.output_by_axis else root.parent / "zero_token_calls_by_axis.csv"
    pd.concat(axis_frames, ignore_index=True).to_csv(output_by_axis, index=False)
    print(f"Saved: {output_by_axis}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
