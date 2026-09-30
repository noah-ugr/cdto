"""Per-backend output-budget thresholds C*, in each backend's own tokens.

budget_complexity.py measures C* in cl100k tokens. A backend emits a different
number of tokens for the same JSON, and gpt-oss adds reasoning, so this module
rescales the cl100k length L of every ground truth per backend:

- L: cl100k length of json_gt serialized compactly (``token_len`` in
  budget_complexity.py).
- r_b: median of completion tokens / L over the vanilla calls of the complexity
  axis with exact match (their output is json_gt). The length is r_b x L.
- m_b: median of completion tokens - L over the same calls. For gpt-oss, which
  spends a roughly constant number of reasoning tokens on top of the JSON, the
  length is L + m_b.
- C*_low, C*_mean, C*_high: first level of the complexity dataset (all 2900
  lines) whose maximum, mean or median length reaches B = 4096, as
  ``compute_c_star`` in budget_complexity.py.

Reads ``benchmark_compare_complexity.json`` under
``benchmarks/results/models/<model>/complexity/``. No new inference. The
C*_low values are the markers in benchmarks/aggregator/c_star.py: the script
compares them and exits with status 1 if any differs.

Writes ``--output-csv`` (default ``benchmarks/results/c_star_by_backend.csv``),
one row per backend plus the cl100k row:

- outputs: number of vanilla calls with exact match;
- median_ratio, median_offset: completion tokens / L and completion - L,
  medians over those calls;
- r_b, m_b: the scaling used, as in the supplementary table (r_b = 1 for
  gpt-oss, m_b = 0 for the others);
- c_star_low, c_star_mean, c_star_high;
- marker, matches_marker: C*_low in c_star.py and whether it is equal.

``--variants`` also prints r_b and m_b under the definitions that do not
reproduce those markers (completeness axis, both axes, ratio of sums, other
serializations).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Callable, Iterable

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmarks.aggregator.c_star import C_STAR_LOW_BY_MODEL  # noqa: E402
from benchmarks.metrics.budget_complexity import B, DATASET_PATH, enc, load_jsonl, token_len  # noqa: E402


COMPLETENESS_DATASET = REPO_ROOT / "benchmarks" / "datasets" / "benchmark_dataset_completeness_1_16_50samples.jsonl"
DEFAULT_OUTPUT_CSV = REPO_ROOT / "benchmarks" / "results" / "c_star_by_backend.csv"
VANILLA = "vanilla"

# model slug: (label, how r_b / m_b rescale L)
MODELS = {
    "claude-sonnet-4-6": ("Claude Sonnet 4.6", "ratio"),
    "llama3.1_latest":   ("Llama 3.1 8B", "ratio"),
    "gpt-oss_20b":       ("gpt-oss:20b", "offset"),
    "gpt-5.4":           ("GPT-5.4", "ratio"),
}

SERIALIZERS: dict[str, Callable[[object], str]] = {
    "compact": lambda o: json.dumps(o, separators=(",", ":"), ensure_ascii=False),
    "default": lambda o: json.dumps(o, ensure_ascii=False),
    "indent2": lambda o: json.dumps(o, indent=2, ensure_ascii=False),
}


def _resolve_results_root(results_root: str | Path | None) -> Path:
    if results_root is None:
        return REPO_ROOT / "benchmarks" / "results" / "models"
    root = Path(results_root)
    return root if root.is_absolute() else (Path.cwd() / root).resolve()


def correct_vanilla_calls(results_root: Path, model: str, axis: str, samples: list[dict]) -> list[tuple[int, dict]]:
    """(completion tokens, json_gt) of every vanilla call of ``axis`` with exact match."""
    path = results_root / model / axis / f"benchmark_compare_{axis}.json"
    with open(path, encoding="utf-8") as f:
        records = json.load(f)["detailed_results"]
    return [
        (r["token_usage"]["completion"], samples[r["sample_idx"]]["json_gt"])
        for r in records
        if r["approach"] == VANILLA and r["exact_match"] == 1.0
    ]


def ratio_and_offset(calls: list[tuple[int, dict]], length: Callable[[object], int] = token_len) -> tuple[float, float, float]:
    """(median ratio, ratio of sums, median offset) of completion tokens against ``length``."""
    lengths = [length(gt) for _, gt in calls]
    completions = [c for c, _ in calls]
    return (
        median(c / n for c, n in zip(completions, lengths, strict=True)),
        sum(completions) / sum(lengths),
        median(c - n for c, n in zip(completions, lengths, strict=True)),
    )


def thresholds(levels_and_lengths: list[tuple[int, int]], transform: Callable[[int], float]) -> tuple[int | None, int | None, int | None]:
    """(C*_low, C*_mean, C*_high): first level whose max, mean or median length reaches B."""
    by_level = defaultdict(list)
    for level, n in levels_and_lengths:
        by_level[level].append(transform(n))
    stats = {level: (max(v), mean(v), median(v)) for level, v in sorted(by_level.items())}

    def first(i: int) -> int | None:
        return next((level for level, st in stats.items() if st[i] >= B), None)

    return first(0), first(1), first(2)


def per_backend(results_root: Path, samples: list[dict]) -> pd.DataFrame:
    levels_and_lengths = [(s["complexity_nodes"], token_len(s["json_gt"])) for s in samples]
    rows = []
    for model, (label, kind) in MODELS.items():
        calls = correct_vanilla_calls(results_root, model, "complexity", samples)
        ratio, _, offset = ratio_and_offset(calls)
        if kind == "offset":
            r_b, m_b = 1.0, offset
        else:
            r_b, m_b = ratio, 0.0
        low, avg, high = thresholds(levels_and_lengths, lambda n, r=r_b, m=m_b: r * n + m)
        marker = C_STAR_LOW_BY_MODEL.get(model)
        rows.append({
            "backend": label, "model": model, "outputs": len(calls), "scaling": kind,
            "median_ratio": round(ratio, 3), "median_offset": round(offset, 1),
            "r_b": round(r_b, 3), "m_b": round(m_b, 1),
            "c_star_low": low, "c_star_mean": avg, "c_star_high": high,
            "marker": marker, "matches_marker": marker == low,
        })
    rows.append({
        "backend": "cl100k (r = 1)", "model": "", "outputs": None, "scaling": "none",
        "median_ratio": None, "median_offset": None, "r_b": 1.0, "m_b": 0.0,
        **dict(zip(("c_star_low", "c_star_mean", "c_star_high"), thresholds(levels_and_lengths, lambda n: n), strict=True)),
        "marker": None, "matches_marker": None,
    })
    table = pd.DataFrame(rows)
    for column in ("outputs", "marker"):
        table[column] = table[column].astype("Int64")
    return table


def variants(results_root: Path, samples_by_axis: dict[str, list[dict]]) -> pd.DataFrame:
    rows = []
    for model, (label, _) in MODELS.items():
        calls_by_axis = {
            axis: correct_vanilla_calls(results_root, model, axis, samples)
            for axis, samples in samples_by_axis.items()
        }
        calls_by_axis["both"] = calls_by_axis["complexity"] + calls_by_axis["completeness"]
        for axis, calls in calls_by_axis.items():
            for name, serialize in SERIALIZERS.items():
                med, sums, offset = ratio_and_offset(calls, lambda o, s=serialize: len(enc.encode(s(o))))
                rows.append({
                    "backend": label, "axis": axis, "serialization": name, "n_correct": len(calls),
                    "median_ratio": round(med, 3), "ratio_of_sums": round(sums, 3), "median_offset": round(offset, 1),
                })
    return pd.DataFrame(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results-root", default=None,
                        help="Folder with <model>/<axis>/benchmark_compare_<axis>.json (default: benchmarks/results/models)")
    parser.add_argument("--dataset", default=str(DATASET_PATH), help="Complexity dataset JSONL")
    parser.add_argument("--completeness-dataset", default=str(COMPLETENESS_DATASET),
                        help="Completeness dataset JSONL (only for --variants)")
    parser.add_argument("--variants", action="store_true", help="Also print the definitions that do not reproduce C*")
    parser.add_argument("--output-csv", default=str(DEFAULT_OUTPUT_CSV),
                        help="CSV for the per-backend table (default: benchmarks/results/c_star_by_backend.csv)")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    results_root = _resolve_results_root(args.results_root)
    samples = load_jsonl(args.dataset)

    table = per_backend(results_root, samples)
    print(table.to_string(index=False))
    table.to_csv(args.output_csv, index=False)
    print(f"Saved: {args.output_csv}")

    if args.variants:
        samples_by_axis = {"complexity": samples, "completeness": load_jsonl(args.completeness_dataset)}
        print()
        print(variants(results_root, samples_by_axis).to_string(index=False))

    mismatched = table[table["matches_marker"].eq(False)]
    if not mismatched.empty:
        print(f"\nC*_low differs from benchmarks/aggregator/c_star.py for: {', '.join(mismatched['model'])}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
