"""
Compute the empirical output-budget saturation threshold C*
defined as the lowest complexity level at which the mean Vanilla
output length reaches the fixed budget B = 4096 tokens.

Vanilla output = full JSON_gt serialized. Tokenization proxy = tiktoken
cl100k_base.

On the complexity dataset this gives C*_max = 49, C*_mean = 90 and
C*_median = 115, the cl100k C*_low, C*_mean and C*_high of the legacy
markers in core/plot_complexity.py. The per-backend thresholds of
benchmarks/aggregator/c_star.py rescale these lengths per backend
(c_star_by_backend.py); GPT-5.4's are 48, 90 and 115.

Writes what it prints to --output-csv (default
benchmarks/results/budget_complexity_cl100k.csv): one row per level with n,
mean, median, min and max length, and a marker column naming the thresholds
that fall at that level (c_star_low, c_star_mean, c_star_high).
"""

import argparse
import csv
import json
from collections import defaultdict
from statistics import mean, median
from pathlib import Path

import tiktoken


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATASET_PATH = REPO_ROOT / "benchmarks" / "datasets" / "benchmark_dataset_1_150.jsonl"
DEFAULT_OUTPUT_CSV = REPO_ROOT / "benchmarks" / "results" / "budget_complexity_cl100k.csv"
B = 4096

enc = tiktoken.get_encoding("cl100k_base")


def token_len(obj):
    """Tokens of a JSON object serialized as compactly as possible."""
    serialized = json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
    return len(enc.encode(serialized))


def load_jsonl(path):
    samples = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            samples.append(json.loads(line))
    return samples


def compute_c_star(samples):
    lengths_by_c = defaultdict(list)
    for s in samples:
        c = s["complexity_nodes"]
        gt = s["json_gt"]
        lengths_by_c[c].append(token_len(gt))

    stats_by_c = {
        c: {
            "n": len(v),
            "mean": mean(v),
            "median": median(v),
            "max": max(v),
            "min": min(v),
        }
        for c, v in sorted(lengths_by_c.items())
    }

    c_star_mean = next(
        (c for c, st in stats_by_c.items() if st["mean"] >= B), None
    )
    c_star_median = next(
        (c for c, st in stats_by_c.items() if st["median"] >= B), None
    )
    c_star_max = next(
        (c for c, st in stats_by_c.items() if st["max"] >= B), None
    )

    return stats_by_c, c_star_mean, c_star_median, c_star_max


def write_csv(path, stats, c_star_mean, c_star_median, c_star_max):
    """One row per level, with the thresholds that fall at it in the marker column."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["complexity", "n", "mean", "median", "min", "max", "marker"])
        for c, st in stats.items():
            marker = [name for name, level in (("c_star_low", c_star_max), ("c_star_mean", c_star_mean),
                                               ("c_star_high", c_star_median)) if level == c]
            writer.writerow([c, st["n"], round(st["mean"], 1), st["median"], st["min"], st["max"], ";".join(marker)])


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", default=str(DATASET_PATH),
                        help="Complexity dataset JSONL (default: benchmarks/datasets/benchmark_dataset_1_150.jsonl)")
    parser.add_argument("--output-csv", default=str(DEFAULT_OUTPUT_CSV),
                        help="CSV of the printed table (default: benchmarks/results/budget_complexity_cl100k.csv)")
    args = parser.parse_args()

    samples = load_jsonl(args.dataset)
    print(f"Loaded {len(samples)} samples\n")

    stats, c_star_mean, c_star_median, c_star_max = compute_c_star(samples)

    print(f"{'C':>4}  {'n':>4}  {'mean':>8}  {'median':>8}  {'min':>6}  {'max':>6}")
    for c, st in stats.items():
        marker = ""
        if c == c_star_mean:
            marker += "  <-- C*_mean"
        if c == c_star_median:
            marker += "  <-- C*_median"
        if c == c_star_max:
            marker += "  <-- C*_max"
        print(
            f"{c:>4}  {st['n']:>4}  {st['mean']:>8.1f}  "
            f"{st['median']:>8.1f}  {st['min']:>6}  {st['max']:>6}"
            f"{marker}"
        )

    print()
    print(f"C* (based on mean)   = {c_star_mean}")
    print(f"C* (based on median) = {c_star_median}")
    print(f"C* (first level with any sample >= B) = {c_star_max}")

    write_csv(args.output_csv, stats, c_star_mean, c_star_median, c_star_max)
    print(f"Saved: {args.output_csv}")


if __name__ == "__main__":
    main()