"""
Select the humanisation-check samples with a fixed seed.

For every level the pool is the set of samples gpt-oss:20b ran under P-E in
the original benchmark (condition A), which must equal the dataset's samples
at that level. From each pool ``--per-level`` IDs are drawn with
``random.Random(derive_group_seed(seed, "humanisation_check:<axis>", level))``,
so the draw of a level does not depend on the other levels.

Writes ``<run-dir>/sample_ids.json``, which the runners also accept through
``--sample-ids``.

    python -m benchmarks.humanisation_check.select_samples --run-dir benchmarks/results/humanisation_check/<run_id>
"""

from __future__ import annotations

import argparse
import random
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, Iterable, List

from benchmarks.comparisons.traceability import derive_group_seed
from benchmarks.humanisation_check.common import (
    AXES,
    EVALUATED_MODEL,
    PLANNER,
    SAMPLE_IDS_FILE,
    a_results_path,
    file_ref,
    load_dataset,
    load_json,
    resolve_run_dir,
    write_json,
)


def level_pools(axis: str) -> Dict[int, List[int]]:
    """Sample IDs per level that condition A ran under P-E, checked against the dataset."""
    a = load_json(a_results_path(axis))
    from_a: Dict[int, set] = defaultdict(set)
    for rec in a["detailed_results"]:
        if rec["approach"] == PLANNER:
            from_a[int(rec[axis])].add(int(rec["sample_idx"]))

    from_dataset: Dict[int, set] = defaultdict(set)
    for idx, row in enumerate(load_dataset(axis)):
        from_dataset[int(row[AXES[axis].level_field])].add(idx)

    pools = {}
    for level, ids in from_a.items():
        if ids != from_dataset[level]:
            raise ValueError(f"{axis} level {level}: condition A samples differ from the dataset's")
        pools[level] = sorted(ids)
    return pools


def select(seed: int, per_level: int, levels_by_axis: Dict[str, Iterable[int]]) -> List[dict]:
    samples = []
    for axis, levels in levels_by_axis.items():
        pools = level_pools(axis)
        for level in levels:
            pool = pools.get(level)
            if pool is None:
                raise ValueError(f"{axis} level {level} was not run in condition A")
            if len(pool) < per_level:
                raise ValueError(f"{axis} level {level} has {len(pool)} samples, fewer than {per_level}")
            rng = random.Random(derive_group_seed(seed, f"humanisation_check:{axis}", level))
            samples += [
                {"axis": axis, "level": level, "sample_idx": idx}
                for idx in sorted(rng.sample(pool, per_level))
            ]
    return samples


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--run-dir", required=True, help="benchmarks/results/humanisation_check/<run_id>")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--per-level", type=int, default=25)
    parser.add_argument("--complexity-levels", type=int, nargs="*", default=list(AXES["complexity"].levels))
    parser.add_argument("--completeness-levels", type=int, nargs="*", default=list(AXES["completeness"].levels))
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing sample_ids.json")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_dir = resolve_run_dir(args.run_dir)
    out = run_dir / SAMPLE_IDS_FILE
    if out.exists() and not args.overwrite:
        raise SystemExit(f"{out} exists; pass --overwrite to replace it")

    levels_by_axis = {"complexity": args.complexity_levels, "completeness": args.completeness_levels}
    levels_by_axis = {axis: levels for axis, levels in levels_by_axis.items() if levels}
    samples = select(args.seed, args.per_level, levels_by_axis)

    write_json(out, {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "seed": args.seed,
        "per_level": args.per_level,
        "levels": levels_by_axis,
        "selection": (
            "random.Random(derive_group_seed(seed, 'humanisation_check:<axis>', level))"
            ".sample(pool, per_level), sorted"
        ),
        "pool": f"sample_idx of the {EVALUATED_MODEL} planner_executor calls in condition A, "
                "equal to the dataset's samples at that level",
        "condition_a": {axis: file_ref(a_results_path(axis)) for axis in levels_by_axis},
        "datasets": {axis: file_ref(AXES[axis].dataset_path) for axis in levels_by_axis},
        "samples": samples,
    })
    counts = defaultdict(int)
    for s in samples:
        counts[(s["axis"], s["level"])] += 1
    for (axis, level), n in sorted(counts.items()):
        print(f"{axis:12s} level {level:>3}: {n} samples")
    print(f"{len(samples)} sample IDs -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
