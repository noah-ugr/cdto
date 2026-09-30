"""Offline pass of the deterministic validator over the recorded P-E batches.

No new inference. For every planner_executor record of the rescored benchmark JSONs:

1. The candidate configuration is rebuilt with the executor exactly as the benchmark ran it
   (input_agent.nodes.node_executor with skip_deterministic_validation=True, i.e.
   ModificationBatch + PetriConfigEngine.apply_batch on a copy of json_base).
2. The validating path of the executor is then replayed without new code: the route check
   (input_agent.src.tools.find_unresolved_routes), PetriConfigEngine.reindex_structure on a copy of
   the candidate, and the validator (input_agent.src.tools.check_configuration).

Categories (mutually exclusive, in this order):
  a           no usable batch: empty instructions, or the batch does not satisfy ModificationBatch
  b           the batch parses but some route does not resolve (the executor aborts before applying)
  c1-base     rejected; the GT and the base are inadmissible
  c1-request  rejected; the GT is inadmissible and the base is admissible
  c2          rejected; the GT is admissible
  d0          admitted; EM = 1 and the GT is admissible
  d1          admitted; EM = 0 and the GT is admissible
  d2          admitted; the GT is inadmissible
The base is checked with an empty batch and the GT with the dataset instruction(s) as its batch.

Per rule group (DOMINIO, RED DE PETRI) the same categories are computed with the validator
restricted to that group: a configuration is rejected (or inadmissible) by the group when it has
at least one violation of a rule of that group. Categories a and b do not depend on the group.

Also writes, per axis, how many dataset bases and GTs each rule rejects, and (separately) the check
over the configurations returned by vanilla.
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import csv
import hashlib
import io
import json
import logging
import platform
import subprocess
import sys
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if not logging.getLogger().handlers:
    logging.getLogger().addHandler(logging.NullHandler())

import numpy as np  # noqa: E402

from benchmarks.metrics.comparison_metrics import compare_json_exact  # noqa: E402
from input_agent import nodes  # noqa: E402
from input_agent.src.models import ModificationBatch  # noqa: E402
from input_agent.src.PetriNetConfig import PetriConfigEngine  # noqa: E402
from input_agent.src.tools import DOMINIO, RED_DE_PETRI, RULES, check_configuration, find_unresolved_routes  # noqa: E402

BACKENDS = ["claude-sonnet-4-6", "gpt-5.4", "gpt-oss_20b", "llama3.1_latest"]
AXES = {
    "complexity": REPO_ROOT / "benchmarks/datasets/benchmark_dataset_1_150.jsonl",
    "completeness": REPO_ROOT / "benchmarks/datasets/benchmark_dataset_completeness_1_16_50samples.jsonl",
}
LEVEL_FIELD = {"complexity": "complexity_nodes", "completeness": "completeness"}
GROUPS = {"all": None, "DOMINIO": DOMINIO, "RED_DE_PETRI": RED_DE_PETRI}
BOOTSTRAP_B = 10_000
BOOTSTRAP_SEED = 42
EMPTY_BATCH = ModificationBatch(thought_process="", instructions=[])


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True).stdout.strip()


def rescored_path(backend: str, axis: str) -> Path:
    return REPO_ROOT / f"benchmarks/results/models/{backend}/{axis}/benchmark_compare_{axis}_rescored.json"


def reference_batch(example: Dict[str, Any]) -> ModificationBatch:
    instructions = example.get("instructions_technical") or [example["instruction_technical"]]
    return ModificationBatch(thought_process="", instructions=instructions)


def violations_of(config: Any, batch: ModificationBatch) -> List[Dict[str, str]]:
    return [v.to_dict() for v in check_configuration(config, batch)]


def rejected_by(violations: List[Dict[str, str]], group: Optional[str]) -> bool:
    return any(group is None or v["group"] == group for v in violations)


# ---------------------------------------------------------------------------
# Per-batch classification
# ---------------------------------------------------------------------------

def run_executor(base: Dict[str, Any], instructions: List[Any]) -> Dict[str, Any]:
    state = {
        "proposed_plan": {"thought_process": "", "instructions": copy.deepcopy(instructions)},
        "original_config": copy.deepcopy(base),
        "current_config": copy.deepcopy(base),
        "retry_count": 0,
        "skip_deterministic_validation": True,
    }
    with contextlib.redirect_stdout(io.StringIO()):
        return nodes.node_executor(state)


def classify_pe(record: Dict[str, Any], example: Dict[str, Any], json_pred: Optional[Dict[str, Any]], checks: Counter) -> Dict[str, Any]:
    base, gt = example["json_base"], example["json_gt"]
    instructions = record.get("planner_instructions") or []
    row: Dict[str, Any] = {
        "em": int(record["exact_match"] == 1.0),
        "base_violations": violations_of(base, EMPTY_BATCH),
        "gt_violations": violations_of(gt, reference_batch(example)),
        "violations": [],
        "route_issues": [],
        "n_instructions": len(instructions),
    }
    if not instructions:
        row.update(category="a", subcategory="a-empty")
        return row
    out = run_executor(base, instructions)
    if "current_config" not in out:
        row.update(category="a", subcategory="a-schema", error=" | ".join(map(str, out.get("validation_errors", []))))
        return row
    candidate = out["current_config"]
    if row["em"]:
        same = compare_json_exact(gt, candidate)
        checks["em1_candidate_equals_gt"] += same
        checks["em1_candidate_differs_from_gt"] += not same
    elif json_pred is not None:
        same = compare_json_exact(json_pred, candidate)
        checks["em0_candidate_equals_recorded_pred"] += same
        checks["em0_candidate_differs_from_recorded_pred"] += not same

    batch = ModificationBatch(thought_process="", instructions=copy.deepcopy(instructions))
    unresolved = find_unresolved_routes(base, batch)
    if unresolved:
        row.update(category="b", subcategory="b", route_issues=unresolved)
        return row

    engine = PetriConfigEngine(candidate)
    with contextlib.redirect_stdout(io.StringIO()):
        engine.reindex_structure()
    checks["reindex_changed_candidate"] += engine.data != candidate
    row["violations"] = violations_of(engine.data, batch)
    row.update(category="cd")  # resolved per group in categorize()
    return row


def categorize(row: Dict[str, Any], group: Optional[str]) -> str:
    """Category of the batch with the validator restricted to `group` (None = all rules)."""
    if row["category"] in ("a", "b"):
        return row["category"]
    rejected = rejected_by(row["violations"], group)
    gt_bad = rejected_by(row["gt_violations"], group)
    base_bad = rejected_by(row["base_violations"], group)
    if rejected:
        if not gt_bad:
            return "c2"
        return "c1-base" if base_bad else "c1-request"
    if gt_bad:
        return "d2"
    return "d0" if row["em"] else "d1"


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def bootstrap_ci(successes: int, n: int, salt: str) -> Tuple[Optional[float], Optional[float]]:
    """Percentile bootstrap of a proportion. Resampling n Bernoulli units with replacement is
    exactly Binomial(n, p_hat), so the B draws are taken from it directly."""
    if n == 0:
        return None, None
    seed = int(hashlib.sha256(f"{BOOTSTRAP_SEED}:{salt}".encode()).hexdigest()[:8], 16)
    draws = np.random.default_rng(seed).binomial(n, successes / n, size=BOOTSTRAP_B) / n
    return float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def summarize(rows: List[Dict[str, Any]], group_key: str, rule_group: str) -> Dict[str, Any]:
    cats = Counter(categorize(r, GROUPS[rule_group]) for r in rows)
    n = len(rows)
    c1 = cats["c1-base"] + cats["c1-request"]
    c = c1 + cats["c2"]
    out: Dict[str, Any] = {
        "group": group_key, "rule_group": rule_group, "n": n,
        "a": cats["a"], "b": cats["b"], "c": c, "c1": c1,
        "c1_base": cats["c1-base"], "c1_request": cats["c1-request"], "c2": cats["c2"],
        "d0": cats["d0"], "d1": cats["d1"], "d2": cats["d2"],
    }
    for name, num, den in (
        ("rejrate", c, n),
        ("c1_base_rate", cats["c1-base"], n),
        ("c1_request_rate", cats["c1-request"], n),
        ("c2_rate", cats["c2"], n),
        ("c1_over_c", c1, c),
        ("c2_over_c2_d1", cats["c2"], cats["c2"] + cats["d1"]),
    ):
        lo, hi = bootstrap_ci(num, den, f"{group_key}:{rule_group}:{name}")
        out[name] = num / den if den else None
        out[f"{name}_ci_lo"], out[f"{name}_ci_hi"] = lo, hi
    return out


def grouped(rows: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        for key in (
            "total",
            f"axis={r['axis']}",
            f"backend={r['backend']}",
            f"backend={r['backend']}|axis={r['axis']}",
            f"axis={r['axis']}|level={r['level']}",
            f"backend={r['backend']}|axis={r['axis']}|level={r['level']}",
        ):
            groups[key].append(r)
    return groups


def write_csv(path: Path, rows: Iterable[Dict[str, Any]], fieldnames: Optional[List[str]] = None) -> None:
    rows = list(rows)
    fieldnames = fieldnames or list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in r.items()})


def c2_breakdown(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for key, members in [("total", rows)] + sorted(_by(rows, lambda r: f"axis={r['axis']}").items()) + sorted(
        _by(rows, lambda r: f"backend={r['backend']}").items()
    ):
        c2 = [r for r in members if categorize(r, None) == "c2"]
        counts = Counter(rule for r in c2 for rule in {v["rule"] for v in r["violations"]})
        out.append({"group": key, "c2": len(c2), **{f"rule_{rule}": counts[rule] for rule in RULES}})
    return out


def c2_examples(rows: List[Dict[str, Any]], per_rule: int = 3) -> Dict[str, List[Dict[str, Any]]]:
    picked: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        if categorize(r, None) != "c2":
            continue
        for rule in sorted({v["rule"] for v in r["violations"]}):
            if len(picked[rule]) < per_rule:
                picked[rule].append({
                    "backend": r["backend"], "axis": r["axis"], "level": r["level"], "sample_idx": r["sample_idx"],
                    "em": r["em"], "instructions": r["instructions"],
                    "violations": [v for v in r["violations"] if v["rule"] == rule][:5],
                })
    return dict(sorted(picked.items()))


def _by(rows, key_fn):
    groups = defaultdict(list)
    for r in rows:
        groups[key_fn(r)].append(r)
    return groups


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rules-commit", required=True, help="commit that froze the validator rules")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--out-root", default=str(REPO_ROOT / "benchmarks/results/validator_pass"))
    args = parser.parse_args()

    run_id = args.run_id or f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_{args.rules_commit[:7]}_{uuid.uuid4().hex[:6]}"
    out_dir = Path(args.out_root) / run_id
    out_dir.mkdir(parents=True, exist_ok=False)

    datasets = {ax: [json.loads(line) for line in p.open(encoding="utf-8")] for ax, p in AXES.items()}
    checks: Counter = Counter()
    pe_rows: List[Dict[str, Any]] = []
    vanilla_rows: List[Dict[str, Any]] = []
    inputs = {}

    for backend in BACKENDS:
        for axis in AXES:
            path = rescored_path(backend, axis)
            inputs[f"{backend}/{axis}"] = {"path": str(path.relative_to(REPO_ROOT)), "sha256": sha256_file(path)}
            data = json.loads(path.read_text(encoding="utf-8"))
            failed = {(f["approach"], f["sample_idx"]): f for f in data.get("failed_cases", [])}
            for record in data["detailed_results"]:
                example = datasets[axis][record["sample_idx"]]
                meta = {"backend": backend, "axis": axis, "level": example[LEVEL_FIELD[axis]], "sample_idx": record["sample_idx"]}
                pred = failed.get((record["approach"], record["sample_idx"]), {}).get("json_pred")
                if record["approach"] == "planner_executor":
                    row = classify_pe(record, example, pred, checks)
                    row["instructions"] = record.get("planner_instructions") or []
                    pe_rows.append({**meta, **row})
                elif record["approach"] == "vanilla":
                    em = int(record["exact_match"] == 1.0)
                    config = example["json_gt"] if em else pred
                    found = violations_of(config, EMPTY_BATCH) if config is not None else None
                    vanilla_rows.append({
                        **meta, "em": em,
                        "config_source": ("json_gt (EM=1)" if em else "failed_cases.json_pred") if config is not None else "missing",
                        "admissible": None if found is None else int(not found),
                        "rules": sorted({v["rule"] for v in found or []}),
                        "violations": found or [],
                    })

    for r in pe_rows:
        r["category_all"] = categorize(r, None)
        r["category_dominio"] = categorize(r, DOMINIO)
        r["category_red"] = categorize(r, RED_DE_PETRI)
    write_csv(out_dir / "pe_batches.csv", pe_rows, [
        "backend", "axis", "level", "sample_idx", "em", "category_all", "category_dominio", "category_red",
        "n_instructions", "violations", "gt_violations", "base_violations", "route_issues", "error", "instructions",
    ])
    groups = grouped(pe_rows)
    summary = [summarize(members, key, rule_group) for key, members in groups.items() for rule_group in GROUPS]
    write_csv(out_dir / "pe_summary.csv", summary)
    write_csv(out_dir / "pe_c2_by_rule.csv", c2_breakdown(pe_rows))
    (out_dir / "pe_c2_examples.json").write_text(json.dumps(c2_examples(pe_rows), ensure_ascii=False, indent=2), encoding="utf-8")

    # Dataset: bases (empty batch) and GTs (reference batch), per rule and axis
    dataset_rows, per_rule = [], []
    for axis, rows in datasets.items():
        base_counts, gt_counts = Counter(), Counter()
        base_any = gt_any = 0
        for idx, example in enumerate(rows):
            base_v = violations_of(example["json_base"], EMPTY_BATCH)
            gt_v = violations_of(example["json_gt"], reference_batch(example))
            base_any += bool(base_v)
            gt_any += bool(gt_v)
            for rule in {v["rule"] for v in base_v}:
                base_counts[rule] += 1
            for rule in {v["rule"] for v in gt_v}:
                gt_counts[rule] += 1
            dataset_rows.append({
                "axis": axis, "sample_idx": idx, "level": example[LEVEL_FIELD[axis]],
                "base_rules": sorted({v["rule"] for v in base_v}), "gt_rules": sorted({v["rule"] for v in gt_v}),
                "gt_violations": gt_v,
            })
        per_rule.append({"axis": axis, "config": "base", "n": len(rows), "any_rule": base_any, **{r: base_counts[r] for r in RULES}})
        per_rule.append({"axis": axis, "config": "gt", "n": len(rows), "any_rule": gt_any, **{r: gt_counts[r] for r in RULES}})
    write_csv(out_dir / "dataset_rules_by_axis.csv", per_rule)
    write_csv(out_dir / "dataset_pass.csv", dataset_rows)
    write_csv(out_dir / "vanilla_pass.csv", vanilla_rows)

    script = Path(__file__).resolve()
    manifest = {
        "run_id": run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "rules_commit": args.rules_commit,
        "head_commit": git("rev-parse", "HEAD"),
        "worktree_clean_for_validator": git("status", "--porcelain", "--", "input_agent", "benchmarks/metrics/validator_pass.py") == "",
        "commits": {
            "validator (input_agent/src/tools.py)": git("log", "-1", "--format=%H", "--", "input_agent/src/tools.py"),
            "reindex_structure (input_agent/src/PetriNetConfig.py)": git("log", "-1", "--format=%H", "--", "input_agent/src/PetriNetConfig.py"),
            "executor (input_agent/nodes.py)": git("log", "-1", "--format=%H", "--", "input_agent/nodes.py"),
            "script (benchmarks/metrics/validator_pass.py)": git("log", "-1", "--format=%H", "--", "benchmarks/metrics/validator_pass.py"),
        },
        "rules": RULES,
        "script": {"path": str(script.relative_to(REPO_ROOT)), "sha256": sha256_file(script)},
        "datasets": {ax: {"path": str(p.relative_to(REPO_ROOT)), "sha256": sha256_file(p)} for ax, p in AXES.items()},
        "inputs": inputs,
        "reconstruction": "node_executor with skip_deterministic_validation=True on a copy of json_base; then find_unresolved_routes, reindex_structure and check_configuration",
        "categories": {
            "a": "no usable batch (empty instructions, or ModificationBatch schema error)",
            "b": "some route does not resolve (find_unresolved_routes)",
            "c1-base": "rejected; GT and base inadmissible",
            "c1-request": "rejected; GT inadmissible, base admissible",
            "c2": "rejected; GT admissible",
            "d0": "admitted; EM=1, GT admissible",
            "d1": "admitted; EM=0, GT admissible",
            "d2": "admitted; GT inadmissible",
            "per_rule_group": "same categories with the validator restricted to the group's rules",
            "base_and_gt_batches": "base checked with an empty batch; GT with the dataset instruction(s)",
        },
        "bootstrap": {"method": "percentile, Binomial(n, p_hat) draws == nonparametric resampling of Bernoulli units", "B": BOOTSTRAP_B, "seed": BOOTSTRAP_SEED},
        "checks": dict(checks),
        "python": platform.python_version(),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(out_dir)


if __name__ == "__main__":
    main()
