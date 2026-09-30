"""
Paired comparison of conditions A, B and C on the selected samples.

Humanisation effect (the only basis for the conclusion): exact match, F1
micro, omission rate and collateral rate, per level, per axis and in total,
for A, B and C, with paired differences C - B and B - A, a 95 % percentile
bootstrap interval (10 000 resamples of samples; stratified by level for axis
and overall totals) and the exact McNemar test for exact match. C - B is
repeated without the samples whose new request the fidelity check flagged.
Latency is not compared.

Controls, reported apart and not part of the conclusion:
- prompt tokens: for every sample B's must equal A's. The P-E prompt is the
  planner system prompt plus the request, so a difference means the prompt,
  the chat template or the context differ and B - A is not valid. Calls
  without logged usage or with different retry counts are listed apart;
- completion tokens of B against A per level (median and range), a check of
  the reasoning effort on the new server;
- mean tokens (total, prompt, completion) and share of truncated calls
  (completion >= 4090, as in output_truncation.py), with the finish reason
  logged for B and C;
- timeouts per condition and level, A included.
B - A is printed next to the new server's settings that could make it differ
from the old one (read from the run manifest; none were logged for A).

Adjudication of discordant pairs: ``discordant_pairs_<approach>.md`` lists
every sample where B and C differ in exact match, with the technical
instruction, both requests, the batch gpt-oss:20b emitted in B and in C and
the edits that differ from the ground truth, plus a ``cause`` column to fill
by hand (humanisation, model or unclear). Rerunning compare keeps the causes
already filled. Once every row has a cause, C - B is also reported without
the samples classified as humanisation (``excl_humanisation`` block), with
intervals and McNemar, for the four effect metrics.

    python -m benchmarks.humanisation_check.compare --run-dir <run-dir>
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.stats import binomtest

from benchmarks.comparisons.traceability import derive_group_seed
from benchmarks.humanisation_check.common import (
    AXES,
    MANIFEST_FILE,
    PLANNER,
    VANILLA,
    a_results_path,
    load_dataset,
    load_json,
    resolve_run_dir,
    selected_samples,
    write_json,
)
from benchmarks.humanisation_check.provenance import TRUNC_THRESHOLD

CONDITIONS = ("A", "B", "C")
EFFECT_METRICS = {  # name: (column, scale)
    "exact_match_pct": ("em", 100.0),
    "f1_micro": ("f1", 1.0),
    "omission_rate": ("omission", 1.0),
    "collateral_rate": ("collateral", 1.0),
}
CONTROL_METRICS = {
    "tokens_total": ("tokens", 1.0),
    "tokens_prompt": ("prompt", 1.0),
    "tokens_completion": ("completion", 1.0),
    "truncated_pct": ("truncated", 100.0),
}
PAIRS = (("C", "B"), ("B", "A"))
CAUSES = ("humanisation", "model", "unclear")
SERVER_SETTINGS = ["OLLAMA_KV_CACHE_TYPE", "OLLAMA_FLASH_ATTENTION", "OLLAMA_MAX_LOADED_MODELS", "OLLAMA_NUM_PARALLEL",
                   "OLLAMA_CONTEXT_LENGTH"]


def _is_timeout(rec: dict) -> bool:
    """Firewall timeout, or a request that failed on its timeout."""
    text = f"{rec.get('error_blob') or ''} {rec.get('error_msg') or ''}".lower()
    return bool(rec.get("is_timeout")) or "timed out" in text


def _record_row(rec: dict, condition: str) -> dict:
    usage = rec.get("token_usage") or {}
    completion = int(usage.get("completion") or 0)
    calls = rec.get("raw_calls") or []
    return {
        f"em_{condition}": float(rec["exact_match"]),
        f"f1_{condition}": float(rec["f1_micro"]),
        f"omission_{condition}": float(rec["omission_rate"]),
        f"collateral_{condition}": float(rec["collateral_rate"]),
        f"tokens_{condition}": int(usage.get("total") or 0),
        f"prompt_{condition}": int(usage.get("prompt") or 0),
        f"completion_{condition}": completion,
        f"truncated_{condition}": float(completion >= TRUNC_THRESHOLD),
        f"attempts_{condition}": int(rec.get("attempts") or 1),
        f"timeout_{condition}": _is_timeout(rec),
        f"finish_{condition}": calls[-1].get("finish_reason") if calls else None,
    }


def load_condition(path: Path, axis: str, approach: str, condition: str) -> pd.DataFrame:
    data = load_json(path)
    rows = [
        {"axis": axis, "level": int(r[axis]), "sample_idx": int(r["sample_idx"]), **_record_row(r, condition)}
        for r in data["detailed_results"] if r["approach"] == approach
    ]
    return pd.DataFrame(rows)


def paired_table(run_dir: Path, approach: str) -> pd.DataFrame:
    selection = pd.DataFrame(selected_samples(run_dir))
    frames = []
    for axis in AXES:
        ids = selection[selection["axis"] == axis]
        if ids.empty:
            continue
        paths = {
            "A": a_results_path(axis),
            "B": run_dir / f"benchmark_compare_{axis}_B.json",
            "C": run_dir / f"benchmark_compare_{axis}_C.json",
        }
        merged = ids[["axis", "level", "sample_idx"]].copy()
        for condition, path in paths.items():
            if not path.exists():
                raise SystemExit(f"missing {path}")
            cond = load_condition(path, axis, approach, condition)
            merged = merged.merge(cond, on=["axis", "level", "sample_idx"], how="left")
        missing = merged[[f"em_{c}" for c in CONDITIONS]].isna().any(axis=1)
        if missing.any():
            raise SystemExit(f"{axis}: {int(missing.sum())} selected samples lack a result in some condition")
        frames.append(merged)
    return pd.concat(frames, ignore_index=True)


def fidelity_flags(run_dir: Path) -> Optional[pd.DataFrame]:
    paths = sorted(run_dir.glob("fidelity_*.csv"))
    if not paths:
        return None
    table = pd.read_csv(paths[0])
    return table[["axis", "sample_idx", "new_ok"]]


def _scopes(df: pd.DataFrame):
    yield "all", "all", df
    for axis, g in df.groupby("axis", sort=False):
        yield axis, "all", g
        for level, gl in g.groupby("level"):
            yield axis, str(level), gl


def bootstrap_ci(diff: np.ndarray, strata: np.ndarray, seed: int, n_boot: int, alpha: float) -> tuple:
    rng = np.random.default_rng(seed)
    sums = np.zeros(n_boot)
    for s in np.unique(strata):
        d = diff[strata == s]
        sums += d[rng.integers(0, len(d), size=(n_boot, len(d)))].sum(axis=1)
    boot = sums / len(diff)
    lo, hi = np.quantile(boot, [alpha / 2, 1 - alpha / 2])
    return float(diff.mean()), float(lo), float(hi)


def mcnemar_exact(first: np.ndarray, second: np.ndarray) -> Dict[str, float]:
    """Exact McNemar test: two-sided binomial test on the discordant pairs."""
    b = int(((first == 1) & (second == 0)).sum())
    c = int(((first == 0) & (second == 1)).sum())
    p = 1.0 if b + c == 0 else float(binomtest(min(b, c), b + c, 0.5).pvalue)
    return {"first_only": b, "second_only": c, "p": p}


def compare(df: pd.DataFrame, subset: str, seed: int, n_boot: int, alpha: float) -> List[dict]:
    """Humanisation effect: EM, F1 micro, omission and collateral with bootstrap CIs and McNemar."""
    rows = []
    for axis, level, g in _scopes(df):
        strata = (g["axis"] + ":" + g["level"].astype(str)).to_numpy()
        for metric, (col, scale) in EFFECT_METRICS.items():
            row = {"subset": subset, "axis": axis, "level": level, "n": len(g), "metric": metric}
            for condition in CONDITIONS:
                row[condition] = round(float(g[f"{col}_{condition}"].mean()) * scale, 4)
            for first, second in PAIRS:
                diff = (g[f"{col}_{first}"] - g[f"{col}_{second}"]).to_numpy(dtype=float) * scale
                key = f"{first}-{second}"
                mean, lo, hi = bootstrap_ci(
                    diff, strata, derive_group_seed(seed, f"{subset}:{axis}:{level}:{metric}:{key}", 0), n_boot, alpha
                )
                row.update({key: round(mean, 4), f"{key}_lo": round(lo, 4), f"{key}_hi": round(hi, 4)})
                if col == "em":
                    test = mcnemar_exact(g[f"em_{first}"].to_numpy(), g[f"em_{second}"].to_numpy())
                    row.update({
                        f"mcnemar_{key}_p": round(test["p"], 6),
                        f"mcnemar_{key}_{first}_only": test["first_only"],
                        f"mcnemar_{key}_{second}_only": test["second_only"],
                    })
            rows.append(row)
    return rows


def controls(df: pd.DataFrame) -> pd.DataFrame:
    """Mean tokens and share of truncated calls per condition, with plain paired differences."""
    rows = []
    for axis, level, g in _scopes(df):
        for metric, (col, scale) in CONTROL_METRICS.items():
            row = {"axis": axis, "level": level, "n": len(g), "metric": metric}
            for condition in CONDITIONS:
                row[condition] = round(float(g[f"{col}_{condition}"].mean()) * scale, 2)
            row["C-B"] = round(row["C"] - row["B"], 2)
            row["B-A"] = round(row["B"] - row["A"], 2)
            rows.append(row)
    return pd.DataFrame(rows)


def completion_by_level(df: pd.DataFrame) -> pd.DataFrame:
    """Completion tokens per condition and level (median and range); B vs A is the server control."""
    rows = []
    for axis, level, g in _scopes(df):
        row = {"axis": axis, "level": level, "n": len(g)}
        for condition in CONDITIONS:
            values = g[f"completion_{condition}"]
            row.update({
                f"{condition}_median": float(values.median()),
                f"{condition}_min": int(values.min()),
                f"{condition}_max": int(values.max()),
            })
        paired = g[(g["completion_A"] > 0) & (g["completion_B"] > 0)]
        row["B_minus_A_median"] = float((paired["completion_B"] - paired["completion_A"]).median()) if len(paired) else None
        row["B_over_A_median_ratio"] = (
            round(row["B_median"] / row["A_median"], 3) if row["A_median"] else None
        )
        rows.append(row)
    return pd.DataFrame(rows)


def timeouts_by_level(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for axis, level, g in _scopes(df):
        rows.append({"axis": axis, "level": level, "n": len(g),
                     **{condition: int(g[f"timeout_{condition}"].sum()) for condition in CONDITIONS}})
    return pd.DataFrame(rows)


def prompt_token_check(df: pd.DataFrame) -> pd.DataFrame:
    def status(r):
        if r["prompt_A"] == 0 or r["prompt_B"] == 0:
            return "unavailable"
        if r["attempts_A"] != r["attempts_B"]:
            return "retries_differ"
        return "match" if r["prompt_A"] == r["prompt_B"] else "mismatch"

    out = df[["axis", "level", "sample_idx", "prompt_A", "prompt_B", "prompt_C", "attempts_A", "attempts_B"]].copy()
    out["status"] = df.apply(status, axis=1)
    out["B_minus_A"] = out["prompt_B"] - out["prompt_A"]
    return out


# ---------------------------------------------------------------- server differences

def server_difference_sources(run_dir: Path) -> List[str]:
    """New-server settings that could make B differ from A (nothing of this was logged for A)."""
    path = run_dir / MANIFEST_FILE
    if not path.exists():
        return []
    manifest = load_json(path)
    env = (manifest.get("environment") or {}).get("server") or {}
    config = (manifest.get("config") or {}).get("new") or {}
    sources = [f"{key}={env[key]}" for key in SERVER_SETTINGS if env.get(key) not in (None, "")]
    version = (manifest.get("ollama") or {}).get("version")
    if version:
        sources.insert(0, f"Ollama {version}")
    if config:
        sources.append(f"model {config.get('model_name')} loaded with num_ctx {config.get('num_ctx')}")
        sources.append(f"{config.get('max_workers')} workers (4 in the original run)")
    model = ((manifest.get("ollama") or {}).get("models") or {}).get(config.get("model_name"), {})
    if model.get("template_has_current_date"):
        sources.append("chat template stamps the current date (different from the original run's)")
    return sources


# ---------------------------------------------------------------- adjudication of discordant pairs

def _as_config(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return ast.literal_eval(value)
    return value


def _short(value: Any, limit: int = 160) -> str:
    text = json.dumps(value, ensure_ascii=False)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def config_diff(gt: Any, pred: Any, path: str = "") -> List[str]:
    """Leaf-level differences between ground truth and prediction."""
    if isinstance(gt, dict) and isinstance(pred, dict):
        out = []
        for key in sorted(set(gt) | set(pred), key=str):
            sub = f"{path}.{key}" if path else str(key)
            if key not in pred:
                out.append(f"`{sub}`: missing from the prediction (GT {_short(gt[key])})")
            elif key not in gt:
                out.append(f"`{sub}`: not in the GT (prediction {_short(pred[key])})")
            else:
                out += config_diff(gt[key], pred[key], sub)
        return out
    return [] if gt == pred else [f"`{path}`: GT {_short(gt)} / prediction {_short(pred)}"]


def _instruction_text(instr: Any) -> str:
    if not isinstance(instr, dict):
        return str(instr)
    op = str(instr.get("operation", "")).split(".")[-1]
    value = instr.get("value")
    return f"{op} {instr.get('path')}" + ("" if value is None else f" = {json.dumps(value, ensure_ascii=False)}")


def load_details(run_dir: Path, approach: str, axes: Iterable[str]) -> Dict[Tuple[str, str, int], Tuple[dict, Optional[dict]]]:
    """(condition, axis, sample_idx) -> (detailed_result, failed_case) for B and C."""
    out = {}
    for axis in axes:
        for condition in ("B", "C"):
            data = load_json(run_dir / f"benchmark_compare_{axis}_{condition}.json")
            failed = {int(fc["sample_idx"]): fc for fc in data["failed_cases"] if fc.get("approach") == approach}
            for rec in data["detailed_results"]:
                if rec["approach"] == approach:
                    idx = int(rec["sample_idx"])
                    out[(condition, axis, idx)] = (rec, failed.get(idx))
    return out


def read_causes(path: Path) -> Dict[Tuple[str, int], str]:
    """Causes already written in the adjudication table of ``path``."""
    if not path.exists():
        return {}
    causes = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not line.lstrip().startswith("|") or len(cells) != 6 or not cells[2].isdigit():
            continue
        cause = cells[5].lower().replace("humanization", "humanisation")
        if cause and cause not in CAUSES:
            raise SystemExit(f"{path}: cause '{cells[5]}' for sample {cells[2]} is not one of {', '.join(CAUSES)}")
        if cause:
            causes[(cells[0], int(cells[2]))] = cause
    return causes


def write_discordant_pairs(
    path: Path,
    discordant: pd.DataFrame,
    details: Dict[Tuple[str, str, int], Tuple[dict, Optional[dict]]],
    fidelity: Optional[pd.DataFrame],
    causes: Dict[Tuple[str, int], str],
    approach: str,
) -> None:
    datasets = {axis: load_dataset(axis) for axis in discordant["axis"].unique()}
    fid = {}
    if fidelity is not None:
        for _, row in fidelity.fillna("").iterrows():
            fid[(row["axis"], int(row["sample_idx"]))] = row

    lines = [
        f"# Discordant pairs: B and C differ in exact match ({approach})",
        "",
        "Fill the `cause` column with one of:",
        "- `humanisation`: the difference comes from the new request text (it drops, adds or changes "
        "something the instruction asks, e.g. an inverted precedence);",
        "- `model`: the new request is faithful and the difference comes from how gpt-oss:20b reads it;",
        "- `unclear`.",
        "",
        "compare keeps the causes filled here when it rewrites this file. Once every row has a cause it also "
        "reports C - B without the samples classified as `humanisation`.",
        "",
        "| axis | level | sample_idx | EM B | EM C | cause |",
        "|---|---|---|---|---|---|",
    ]
    for _, r in discordant.iterrows():
        cause = causes.get((r["axis"], int(r["sample_idx"])), "")
        lines.append(f"| {r['axis']} | {r['level']} | {r['sample_idx']} | {int(r['em_B'])} | {int(r['em_C'])} | {cause} |")

    for _, r in discordant.iterrows():
        axis, idx = r["axis"], int(r["sample_idx"])
        row = datasets[axis][idx]
        (rec_b, failed_b), (rec_c, failed_c) = details[("B", axis, idx)], details[("C", axis, idx)]
        technical = rec_b.get("instruction_technical")
        technical = technical if isinstance(technical, list) else [technical]
        lines += ["", f"## {axis} level {r['level']}, sample {idx} (EM B {int(r['em_B'])}, EM C {int(r['em_C'])})", "",
                  "**Technical instruction**", ""]
        lines += [f"{i}. `{_instruction_text(t)}`" for i, t in enumerate(technical, 1)]
        lines += ["", f"**Original request (B)**: {rec_b.get('instruction_natural')}", "",
                  f"**New request (C)**: {rec_c.get('instruction_natural')}", ""]
        if (axis, idx) in fid:
            f = fid[(axis, idx)]
            lines += [f"**Fidelity of the new request**: {'ok' if f['new_ok'] in (True, 'True') else f['new_failures']}"
                      f"; direction warnings: {f.get('new_direction_warnings') or 'none'}"
                      f"; unit warnings: {f.get('new_unit_warnings') or 'none'}", ""]
        for condition, rec, failed in (("B", rec_b, failed_b), ("C", rec_c, failed_c)):
            batch = rec.get("planner_instructions") or []
            lines += [f"**Batch emitted by gpt-oss:20b in {condition}**", ""]
            lines += [f"- `{_instruction_text(i)}`" for i in batch] or ["- (no instructions)"]
            if rec.get("error_blob") or rec.get("error_msg"):
                lines.append(f"- error: {rec.get('error_blob') or rec.get('error_msg')}")
            lines += ["", f"**Edits that differ from the GT in {condition}**", ""]
            if float(rec["exact_match"]) == 1.0:
                lines.append("- none (exact match)")
            else:
                pred = _as_config(failed["json_pred"]) if failed and "json_pred" in failed else row["json_base"]
                if not (failed and "json_pred" in failed):
                    lines.append("- no configuration returned (timeout or error): scored as the base configuration")
                lines += [f"- {d}" for d in config_diff(row["json_gt"], pred)] or ["- none"]
            lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Paired A/B/C comparison of the humanisation check")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--approach", choices=[PLANNER, VANILLA], default=PLANNER)
    parser.add_argument("--n-boot", type=int, default=10_000)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=42)
    return parser


def _fmt(row: dict, key: str) -> str:
    return f"{row[key]:+8.3f} [{row[key + '_lo']:+.3f}, {row[key + '_hi']:+.3f}]"


def _scope(r) -> str:
    return f"{r['axis']}:{r['level']}"


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_dir = resolve_run_dir(args.run_dir)
    tag = args.approach
    df = paired_table(run_dir, args.approach)

    tokens = prompt_token_check(df)
    counts = tokens["status"].value_counts().to_dict()
    valid = counts.get("mismatch", 0) == 0

    rows = compare(df, "all", args.seed, args.n_boot, args.alpha)
    flags = fidelity_flags(run_dir)
    n_flagged = None
    if flags is not None:
        df = df.merge(flags, on=["axis", "sample_idx"], how="left")
        kept = df[df["new_ok"].fillna(False).astype(bool)]
        n_flagged = int(len(df) - len(kept))
        if len(kept):
            rows += compare(kept, "fidelity_ok", args.seed, args.n_boot, args.alpha)
        else:
            print("Every new request is fidelity-flagged: no fidelity_ok block")

    # Adjudication of the pairs where B and C differ in exact match.
    discordant = df[df["em_B"] != df["em_C"]]
    discordant_path = run_dir / f"discordant_pairs_{tag}.md"
    causes = read_causes(discordant_path)
    fidelity_paths = sorted(run_dir.glob("fidelity_*.csv"))
    details = load_details(run_dir, args.approach, discordant["axis"].unique()) if len(discordant) else {}
    write_discordant_pairs(discordant_path, discordant, details,
                           pd.read_csv(fidelity_paths[0]) if fidelity_paths else None, causes, tag)
    keys = {(a, int(i)) for a, i in zip(discordant["axis"], discordant["sample_idx"], strict=True)}
    classified = {k: v for k, v in causes.items() if k in keys}
    adjudication = {
        "file": discordant_path.name,
        "n_discordant": len(keys),
        "classified": {c: sum(v == c for v in classified.values()) for c in CAUSES},
        "unclassified": len(keys) - len(classified),
        "complete": bool(keys) and len(classified) == len(keys),
    }
    if adjudication["complete"]:
        humanisation = {k for k, v in classified.items() if v == "humanisation"}
        kept = df[[(a, int(i)) not in humanisation for a, i in zip(df["axis"], df["sample_idx"], strict=True)]]
        if len(kept):
            rows += compare(kept, "excl_humanisation", args.seed, args.n_boot, args.alpha)
    effect = pd.DataFrame(rows)
    sources = server_difference_sources(run_dir)
    control = controls(df)
    completion = completion_by_level(df)
    timeouts = timeouts_by_level(df)

    effect.to_csv(run_dir / f"comparison_{tag}.csv", index=False)
    control.to_csv(run_dir / f"controls_{tag}.csv", index=False)
    completion.to_csv(run_dir / f"completion_by_level_{tag}.csv", index=False)
    timeouts.to_csv(run_dir / f"timeouts_{tag}.csv", index=False)
    df.to_csv(run_dir / f"paired_samples_{tag}.csv", index=False)
    tokens.to_csv(run_dir / f"prompt_tokens_{tag}.csv", index=False)
    finish = {c: df[f"finish_{c}"].value_counts(dropna=False).to_dict() for c in ("B", "C")}
    agreement = {c: int(((df[f"finish_{c}"] == "length") == (df[f"truncated_{c}"] == 1)).sum()) for c in ("B", "C")}
    write_json(run_dir / f"comparison_summary_{tag}.json", {
        "approach": args.approach,
        "n_samples": len(df),
        "conclusion_metrics": list(EFFECT_METRICS),
        "control_metrics": [*CONTROL_METRICS, "completion tokens by level", "timeouts", "prompt tokens B vs A"],
        "prompt_tokens_B_vs_A": counts,
        "b_minus_a_valid": valid,
        "b_minus_a_possible_sources": sources,
        "fidelity_flagged_excluded": n_flagged,
        "adjudication": adjudication,
        "timeouts": {c: int(df[f"timeout_{c}"].sum()) for c in CONDITIONS},
        "finish_reason": {c: {str(k): v for k, v in finish[c].items()} for c in finish},
        "finish_reason_agrees_with_completion_rule": agreement,
        "bootstrap": {"n_boot": args.n_boot, "alpha": args.alpha, "seed": args.seed,
                      "resampling": "paired samples; stratified by level for axis and overall totals"},
    })

    print(f"Prompt tokens B vs A: {counts}  ->  {'VALID' if valid else 'NOT VALID: prompt or context differ'}")
    if sources:
        print("Possible sources of B - A differences (new server; not logged for A): " + "; ".join(sources))
    if n_flagged is not None:
        print(f"Fidelity-flagged samples excluded in the fidelity_ok block: {n_flagged}")
    print(f"Discordant pairs (EM B != EM C): {adjudication['n_discordant']} -> {discordant_path.name}; "
          f"classified {adjudication['classified']}, unclassified {adjudication['unclassified']}"
          + ("" if adjudication["complete"] or not keys else "  (excl_humanisation block once every row has a cause)"))

    print("\n######## Humanisation effect: EM, F1 micro, omission, collateral ########")
    for subset in effect["subset"].unique():
        print(f"\n=== {subset} ===")
        for metric in EFFECT_METRICS:
            sub = effect[(effect["subset"] == subset) & (effect["metric"] == metric)]
            print(f"\n{metric}")
            print(f"  {'scope':18s} {'n':>4} {'A':>9} {'B':>9} {'C':>9}   {'C-B [95% CI]':>28}   {'B-A [95% CI]':>28}")
            for _, r in sub.iterrows():
                line = (f"  {_scope(r):18s} {r['n']:>4} {r['A']:>9.3f} {r['B']:>9.3f} {r['C']:>9.3f}   "
                        f"{_fmt(r, 'C-B'):>28}   {_fmt(r, 'B-A'):>28}")
                if metric == "exact_match_pct":
                    line += f"   McNemar p C-B {r['mcnemar_C-B_p']:.3f}, B-A {r['mcnemar_B-A_p']:.3f}"
                print(line)

    print("\n######## Controls (not part of the conclusion) ########")
    print("\nCompletion tokens, median [min-max]: server control B vs A")
    print(f"  {'scope':18s} {'n':>4} {'A':>22} {'B':>22} {'C':>22}  {'B-A med':>8} {'B/A':>6}")
    for _, r in completion.iterrows():
        cells = [f"{r[f'{c}_median']:.0f} [{r[f'{c}_min']}-{r[f'{c}_max']}]" for c in CONDITIONS]
        diff = "" if pd.isna(r["B_minus_A_median"]) else f"{r['B_minus_A_median']:+.0f}"
        ratio = "" if pd.isna(r["B_over_A_median_ratio"]) else f"{r['B_over_A_median_ratio']:.2f}"
        print(f"  {_scope(r):18s} {r['n']:>4} {cells[0]:>22} {cells[1]:>22} {cells[2]:>22}  {diff:>8} {ratio:>6}")
    print("\nTimeouts per condition")
    print(f"  {'scope':18s} {'n':>4} {'A':>4} {'B':>4} {'C':>4}")
    for _, r in timeouts.iterrows():
        print(f"  {_scope(r):18s} {r['n']:>4} {r['A']:>4} {r['B']:>4} {r['C']:>4}")
    print("\nMean tokens and truncated calls")
    print(f"  {'scope':18s} {'metric':18s} {'A':>9} {'B':>9} {'C':>9} {'C-B':>9} {'B-A':>9}")
    for _, r in control[control["level"] == "all"].iterrows():
        print(f"  {_scope(r):18s} {r['metric']:18s} {r['A']:>9.1f} {r['B']:>9.1f} {r['C']:>9.1f} {r['C-B']:>+9.1f} {r['B-A']:>+9.1f}")
    print(f"  finish reason B {finish['B']}, C {finish['C']}")

    print(f"\nTables -> {run_dir}: comparison_{tag}.csv (effect), controls_{tag}.csv, completion_by_level_{tag}.csv, "
          f"timeouts_{tag}.csv, paired_samples_{tag}.csv, prompt_tokens_{tag}.csv, {discordant_path.name}")
    return 0 if valid else 3


if __name__ == "__main__":
    raise SystemExit(main())
