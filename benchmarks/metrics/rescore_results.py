"""Re-score logged benchmark samples with the corrected excision metric.

Reads ``benchmark_compare_<axis>.json`` under
``benchmarks/results/models/<model>/<axis>/`` and recomputes F1 micro,
collateral and omission for every logged call, without new inference:

- exact matches: the prediction is ``json_gt``;
- other calls: ``json_pred``, ``json_base`` and ``json_gt`` from ``failed_cases``;
- calls without a usable configuration (firewall timeouts and hard kills,
  which log no ``json_pred``): scored as ``json_base``, with base and ground
  truth taken from dataset line ``sample_idx``.

Exact match, latency and tokens are copied unchanged. The script checks that
exact match recomputed from the configurations agrees with the log, that no
exact-match or token value changes, and that the legacy metric reproduces
every logged F1/collateral/omission value (timeouts excepted: the runner
logged hard-coded zeros for them).

Writes ``benchmark_compare_<axis>_<suffix>.json`` next to the original, which
is left untouched.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmarks.metrics.comparison_metrics import calculate_excision_micro_f1, compare_json_exact  # noqa: E402
from input_agent.src.PetriNetConfig import PetriConfigEngine  # noqa: E402
MODELS = ["claude-sonnet-4-6", "gpt-5.4", "gpt-oss_20b", "llama3.1_latest"]
AXES = ["complexity", "completeness"]

METRIC_FIELDS = [
    "f1_micro", "f1_keys", "f1_values",
    "collateral_damage", "omissions", "collateral_rate", "omission_rate",
]
UNCHANGED_FIELDS = ["exact_match", "exact_match_score", "token_usage", "latency_s"]
SUMMARY_FIELDS = {  # summary average -> record field
    "excision_micro_f1_avg": "f1_micro",
    "excision_key_f1_avg":   "f1_keys",
    "excision_value_f1_avg": "f1_values",
    "collateral_damage_avg": "collateral_damage",
    "omissions_avg":         "omissions",
    "collateral_rate_avg":   "collateral_rate",
    "omission_rate_avg":     "omission_rate",
}
TOLERANCE = 1e-6


def _resolve_results_root(results_root: str | Path | None) -> Path:
    if results_root is None:
        return Path(__file__).resolve().parent.parent / "results" / "models"
    root = Path(results_root)
    return root if root.is_absolute() else (Path.cwd() / root).resolve()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _as_config(value):
    return ast.literal_eval(value) if isinstance(value, str) else value


def _load_dataset(dataset_path: str) -> list[dict]:
    path = Path(dataset_path)
    path = path if path.is_absolute() else REPO_ROOT / path
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _score_from_deltas(json_gt, json_pred, delta_gt, delta_pred, legacy_structural_keys: bool) -> dict:
    excision = calculate_excision_micro_f1(delta_gt, delta_pred, legacy_structural_keys=legacy_structural_keys)
    gt_keys = int(excision["gt_key_count"])
    pred_keys = int(excision["pred_key_count"])
    omissions = int(excision["omissions"])
    collateral = int(excision["collateral_damage"])
    return {
        "exact_match":       float(compare_json_exact(json_gt, json_pred)),
        "f1_micro":          round(float(excision["f1_micro"]), 6),
        "f1_keys":           round(float(excision["f1_keys"]), 6),
        "f1_values":         round(float(excision["f1_values"]), 6),
        "collateral_damage": collateral,
        "omissions":         omissions,
        "collateral_rate":   round(collateral / pred_keys if pred_keys else 0.0, 6),
        "omission_rate":     round(omissions / gt_keys if gt_keys else 0.0, 6),
    }


def score_prediction(json_base, json_gt, json_pred, legacy_structural_keys: bool = False) -> dict:
    """Score one prediction exactly as the benchmark runners do."""
    return _score_both(json_base, json_gt, json_pred)[1 if legacy_structural_keys else 0]


def _score_both(json_base, json_gt, json_pred) -> tuple[dict, dict]:
    """Return (corrected, legacy) scores, computing the deltas once."""
    delta_gt = PetriConfigEngine(json_base).compute_delta(json_gt)
    delta_pred = PetriConfigEngine(json_base).compute_delta(json_pred)
    return (
        _score_from_deltas(json_gt, json_pred, delta_gt, delta_pred, legacy_structural_keys=False),
        _score_from_deltas(json_gt, json_pred, delta_gt, delta_pred, legacy_structural_keys=True),
    )


def _recompute_summary(raw: dict, axis: str) -> None:
    groups: dict[tuple[str, str | None], list[dict]] = defaultdict(list)
    for rec in raw["detailed_results"]:
        groups[(rec["approach"], None)].append(rec)
        groups[(rec["approach"], str(rec[axis]))].append(rec)

    def _update(block: dict, records: list[dict]) -> None:
        for summary_key, field in SUMMARY_FIELDS.items():
            if summary_key in block:
                block[summary_key] = round(sum(float(r[field]) for r in records) / len(records), 4)

    for approach, block in raw["summary"].get("approaches", {}).items():
        _update(block, groups[(approach, None)])
    for level, by_approach in raw.get(f"by_{axis}", {}).items():
        for approach, block in by_approach.items():
            _update(block, groups[(approach, str(level))])


def rescore_file(
    json_path: Path,
    axis: str,
    legacy_structural_keys: bool,
    dataset_cache: dict[str, list[dict]],
) -> tuple[dict, dict, pd.DataFrame]:
    with open(json_path, encoding="utf-8") as f:
        raw = json.load(f)

    dataset_path = raw["summary"]["dataset_path"]
    if dataset_path not in dataset_cache:
        dataset_cache[dataset_path] = _load_dataset(dataset_path)
    dataset = dataset_cache[dataset_path]

    failed = {(r["approach"], r[axis], r["sample_idx"]): r for r in raw["failed_cases"]}
    checks: Counter = Counter()
    rows = []

    for rec in raw["detailed_results"]:
        before = {f: json.dumps(rec.get(f)) for f in UNCHANGED_FIELDS}
        old = {f: rec[f] for f in METRIC_FIELDS}
        fc = failed.get((rec["approach"], rec[axis], rec["sample_idx"]))

        if fc is not None and "json_pred" in fc:
            base, gt, pred = (_as_config(fc[k]) for k in ("json_base", "json_gt", "json_pred"))
            source = "failed_case"
        else:
            line = dataset[rec["sample_idx"]]
            instruction = line.get("instruction_natural") or line.get("instructions_natural")
            if instruction != rec["instruction_natural"]:
                raise ValueError(f"{json_path}: dataset line {rec['sample_idx']} does not match the record")
            base, gt = line["json_base"], line["json_gt"]
            if rec["exact_match"] == 1.0:
                pred, source = gt, "exact_match"
            else:
                pred, source = base, "no_config"

        corrected, legacy = _score_both(base, gt, pred)
        checks[f"source_{source}"] += 1
        checks["em_recomputed_mismatch"] += int(corrected["exact_match"] != rec["exact_match"])
        if source != "no_config":
            checks["legacy_mismatch"] += int(any(abs(legacy[f] - old[f]) > TOLERANCE for f in METRIC_FIELDS))

        new = legacy if legacy_structural_keys else corrected
        for target in (rec, fc):
            if target is not None:
                target.update({f: new[f] for f in METRIC_FIELDS})

        checks["unchanged_field_changed"] += int(any(json.dumps(rec.get(f)) != before[f] for f in UNCHANGED_FIELDS))
        rows.append({
            "approach": rec["approach"],
            "level": rec[axis],
            "source": source,
            **{f"old_{f}": old[f] for f in ("f1_micro", "collateral_rate", "omission_rate")},
            **{f"new_{f}": new[f] for f in ("f1_micro", "collateral_rate", "omission_rate")},
        })

    _recompute_summary(raw, axis)
    raw["summary"]["rescoring"] = {
        "source_file": json_path.name,
        "source_sha256": _sha256(json_path),
        "legacy_structural_keys": legacy_structural_keys,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "checks": dict(checks),
    }
    return raw, dict(checks), pd.DataFrame(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results-root", default=None)
    parser.add_argument("--models", nargs="+", default=MODELS)
    parser.add_argument("--axes",   nargs="+", default=AXES, choices=AXES)
    parser.add_argument("--legacy-structural-keys", action="store_true",
                        help="Re-score with the pre-correction metric (should reproduce the logged values)")
    parser.add_argument("--suffix", default=None,
                        help="Output suffix. Defaults to 'rescored' ('rescored_legacy' with --legacy-structural-keys)")
    parser.add_argument("--validation-csv", default=None,
                        help="Optional path for the per-file validation summary")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    root = _resolve_results_root(args.results_root)
    suffix = args.suffix or ("rescored_legacy" if args.legacy_structural_keys else "rescored")

    dataset_cache: dict[str, list[dict]] = {}
    summary_rows = []
    failures = 0
    for model in args.models:
        for axis in args.axes:
            json_path = root / model / axis / f"benchmark_compare_{axis}.json"
            if not json_path.exists():
                continue
            raw, checks, rows = rescore_file(json_path, axis, args.legacy_structural_keys, dataset_cache)

            out_path = json_path.with_name(f"benchmark_compare_{axis}_{suffix}.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(raw, f, indent=2)

            bad = checks.get("em_recomputed_mismatch", 0) + checks.get("legacy_mismatch", 0) \
                + checks.get("unchanged_field_changed", 0)
            failures += bad
            means = rows.groupby("approach")[[c for c in rows.columns if c.startswith(("old_", "new_"))]].mean()
            print(f"-- {model} / {axis}: {len(rows)} records -> {out_path.name}")
            print(f"   checks: {checks}")
            print(means.round(4).to_string())
            summary_rows.append({"model": model, "axis": axis, "records": len(rows), **checks})

    if args.validation_csv:
        pd.DataFrame(summary_rows).fillna(0).to_csv(args.validation_csv, index=False)
        print(f"Saved: {args.validation_csv}")
    print("\nAll checks passed." if failures == 0 else f"\n{failures} check failures.")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
