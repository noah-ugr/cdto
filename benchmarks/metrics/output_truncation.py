"""Diagnose output-budget truncation from raw benchmark JSON.

This module reads ``benchmark_compare_<axis>.json`` under
``benchmarks/results/models/<model>/<axis>/`` and classifies every call by
whether it hit the output budget and what kind of content came back.

What the raw logs contain:
- ``token_usage.{prompt, completion, total}`` per call. On Ollama's
  OpenAI-compatible endpoint ``completion`` is ``eval_count``, which counts
  reasoning and content tokens together.
- ``error_blob``, ``attempts`` and ``latency_s``; ``json_pred`` only for
  failed cases.
- No ``finish_reason`` / ``done_reason``, no raw response text and no
  separate reasoning field. Truncation is therefore inferred from the
  completion count reaching the request limit (``max_tokens = 4096``, the
  LLMService default when ``max_tokens`` is None).

Per-call content classes (``at limit`` means completion >= threshold):
- empty:       no content ("Empty LLM response"); at the limit, the whole
               budget went to reasoning.
- cut_json:    at the limit and either no JSON object could be parsed
               ("Could not parse JSON object from LLM response") or
               ``json_pred == json_base``. On a cut JSON the extractor's
               last-resort scan recovers only an inner object (a task or an
               activity), which lacks ``json_pred``/``runId``, so it falls
               back to ``json_base`` without logging an error.
- malformed:   below the limit and no JSON object could be parsed.
- other_shape: below the limit and ``json_pred == json_base``: a complete
               JSON with another shape, or one that applied no change.
- timeout:     discarded by the per-sample firewall timeout.
- parsed:      any other response.

F1 and omission are read from ``benchmark_compare_<axis>_rescored.json`` (the
corrected metric, see ``rescore_results.py``) when it exists.

Content size for vanilla calls is estimated by tokenizing the parsed
prediction (or the ground truth for exact matches) wrapped as
``{"json_pred": ...}`` with compact separators, so it is a lower bound on
content and an upper bound on reasoning.
"""

from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path
from typing import Iterable

import pandas as pd
from scipy.stats import spearmanr

try:
    import tiktoken
except ImportError:  # content-size estimates are skipped without it
    tiktoken = None


PLANNER = "planner_executor"
VANILLA = "vanilla"
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

MAX_TOKENS = 4096
TRUNC_THRESHOLD = 4090

EMPTY_MARK = "Empty LLM response"
UNPARSEABLE_MARK = "Could not parse JSON object"

VALUE_COLS = ["completion", "cls", "content_est", "gt_content", "f1_micro", "omission_rate"]


def _resolve_results_root(results_root: str | Path | None) -> Path:
    if results_root is None:
        return Path(__file__).resolve().parent.parent / "results" / "models"
    root = Path(results_root)
    return root if root.is_absolute() else (Path.cwd() / root).resolve()


def _load_encoder():
    if tiktoken is None:
        return None
    try:
        return tiktoken.get_encoding("o200k_harmony")
    except ValueError:
        return tiktoken.get_encoding("o200k_base")


def _count_tokens(encoder, obj) -> int | None:
    if encoder is None or obj is None:
        return None
    return len(encoder.encode(json.dumps({"json_pred": obj}, ensure_ascii=False)))


def _load_ground_truth(dataset_path: str | None) -> dict[int, tuple[str, dict]]:
    """Map dataset line index to (natural instruction, json_gt)."""
    if not dataset_path:
        return {}
    path = Path(dataset_path)
    path = path if path.is_absolute() else REPO_ROOT / path
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    return {
        i: (r.get("instructions_natural") or r.get("instruction_natural"), r.get("json_gt"))
        for i, r in enumerate(records)
    }


def _classify(record: dict, pred_is_base: bool, at_limit: bool) -> str:
    if record.get("is_timeout"):
        return "timeout"
    blob = record.get("error_blob") or ""
    if EMPTY_MARK in blob:
        return "empty"
    if UNPARSEABLE_MARK in blob:
        return "cut_json" if at_limit else "malformed"
    if pred_is_base:
        return "cut_json" if at_limit else "other_shape"
    return "parsed"


def _load_calls(model: str, axis_dir: Path, axis: str, encoder, threshold: int, input_suffix: str | None) -> pd.DataFrame:
    path = axis_dir / f"benchmark_compare_{axis}.json"
    if input_suffix and (axis_dir / f"benchmark_compare_{axis}_{input_suffix}.json").exists():
        path = axis_dir / f"benchmark_compare_{axis}_{input_suffix}.json"
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    failed = {(r["approach"], r[axis], r["sample_idx"]): r for r in raw["failed_cases"]}
    ground_truth = _load_ground_truth(raw["summary"].get("dataset_path"))
    gt_tokens: dict[int, int | None] = {}

    rows = []
    for r in raw["detailed_results"]:
        fc = failed.get((r["approach"], r[axis], r["sample_idx"]))
        completion = int((r.get("token_usage") or {}).get("completion") or 0)
        pred_is_base = fc is not None and fc.get("json_pred") == fc.get("json_base")
        cls = _classify(r, pred_is_base, completion >= threshold)

        instruction, json_gt = ground_truth.get(r["sample_idx"], (None, None))
        if instruction != r.get("instruction_natural"):
            json_gt = None  # dataset line does not match this call

        content_est = gt_content = None
        if r["approach"] == VANILLA:
            if r["sample_idx"] not in gt_tokens:
                gt_tokens[r["sample_idx"]] = _count_tokens(encoder, json_gt)
            gt_content = gt_tokens[r["sample_idx"]]
            if cls == "parsed":
                content_est = _count_tokens(encoder, fc["json_pred"]) if fc else gt_content

        rows.append({
            "model":         model,
            "approach":      r["approach"],
            "level":         int(r[axis]),
            "completion":    completion,
            "cls":           cls,
            "content_est":   content_est,
            "gt_content":    gt_content,
            "f1_micro":      float(r["f1_micro"]),
            "omission_rate": float(r["omission_rate"]),
        })
    return pd.DataFrame(rows)


def _summarize_level(g: pd.DataFrame, max_tokens: int, threshold: int) -> pd.Series:
    trunc = g["completion"] >= threshold
    ok = ~trunc
    est = ok & g["content_est"].notna()
    return pd.Series({
        "n":                            len(g),
        "n_no_usage":                   int((g["completion"] == 0).sum()),
        "pct_length_inferred":          100 * (g["completion"] >= max_tokens).mean(),
        "pct_completion_ge_threshold":  100 * trunc.mean(),
        "pct_empty_content":            100 * (g["cls"] == "empty").mean(),
        "pct_cut_json":                 100 * (g["cls"] == "cut_json").mean(),
        "pct_malformed_json":           100 * (g["cls"] == "malformed").mean(),
        "pct_other_shape_or_unchanged": 100 * (g["cls"] == "other_shape").mean(),
        "pct_timeout":                  100 * (g["cls"] == "timeout").mean(),
        "completion_mean":              g["completion"].mean(),
        "content_est_mean":             g.loc[est, "content_est"].astype(float).mean(),
        "reasoning_est_mean":           (g.loc[est, "completion"] - g.loc[est, "content_est"].astype(float)).mean(),
        "gt_content_tok_mean":          g["gt_content"].astype(float).mean(),
        "f1_all":                       g["f1_micro"].mean(),
        "omission_all":                 g["omission_rate"].mean(),
        "n_trunc":                      int(trunc.sum()),
        "f1_trunc":                     g.loc[trunc, "f1_micro"].mean(),
        "omission_trunc":               g.loc[trunc, "omission_rate"].mean(),
        "n_not_trunc":                  int(ok.sum()),
        "f1_not_trunc":                 g.loc[ok, "f1_micro"].mean(),
        "omission_not_trunc":           g.loc[ok, "omission_rate"].mean(),
    })


def compute_tables(
    results_root: str | Path | None = None,
    axis: str = "completeness",
    models: list[str] | None = None,
    max_tokens: int = MAX_TOKENS,
    threshold: int = TRUNC_THRESHOLD,
    input_suffix: str | None = "rescored",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    root = _resolve_results_root(results_root)
    encoder = _load_encoder()

    calls = pd.concat(
        [
            _load_calls(m, root / m / axis, axis, encoder, threshold, input_suffix)
            for m in models or ["gpt-oss_20b", "llama3.1_latest"]
        ],
        ignore_index=True,
    )
    by_level = (
        calls.groupby(["model", "approach", "level"])[VALUE_COLS]
        .apply(_summarize_level, max_tokens=max_tokens, threshold=threshold)
        .reset_index()
    )
    return calls, by_level


def _trend_summary(levels: pd.DataFrame) -> dict[str, float]:
    levels = levels.set_index("level").sort_index()
    lo, hi = levels.index.min(), levels.index.max()
    pct = levels["pct_completion_ge_threshold"]
    rho = spearmanr(levels.index, pct).statistic if pct.nunique() > 1 else float("nan")
    drop_all = levels.at[lo, "f1_all"] - levels.at[hi, "f1_all"]
    drop_ok = levels.at[lo, "f1_not_trunc"] - levels.at[hi, "f1_not_trunc"]
    return {
        "lo": lo, "hi": hi,
        "trunc_lo": pct.at[lo], "trunc_hi": pct.at[hi], "rho": rho,
        "f1_lo": levels.at[lo, "f1_all"], "f1_hi": levels.at[hi, "f1_all"],
        "f1_ok_lo": levels.at[lo, "f1_not_trunc"], "f1_ok_hi": levels.at[hi, "f1_not_trunc"],
        "n_ok_hi": levels.at[hi, "n_not_trunc"],
        "f1_ok_min": levels["f1_not_trunc"].min(), "f1_ok_max": levels["f1_not_trunc"].max(),
        "drop_all": drop_all, "drop_ok": drop_ok,
        "share_removed": 1 - drop_ok / drop_all if drop_all else float("nan"),
    }


def print_summary(calls: pd.DataFrame, by_level: pd.DataFrame, threshold: int) -> None:
    table_cols = {
        "level": "K", "n": "n",
        "pct_length_inferred": "%len", "pct_completion_ge_threshold": f"%>={threshold}",
        "pct_empty_content": "%empty", "pct_cut_json": "%cut_json",
        "pct_other_shape_or_unchanged": "%other_shape",
        "completion_mean": "out_tok", "reasoning_est_mean": "reason_est", "content_est_mean": "content_est",
        "f1_trunc": "F1_tr", "f1_not_trunc": "F1_ok",
        "omission_trunc": "Om_tr", "omission_not_trunc": "Om_ok",
    }
    for (model, approach), levels in by_level.groupby(["model", "approach"]):
        print(f"-- {model} / {approach} --")
        print(levels[list(table_cols)].rename(columns=table_cols).round(2).to_string(index=False))

        sub = calls[(calls["model"] == model) & (calls["approach"] == approach)]
        crosstab = pd.crosstab(sub["completion"] >= threshold, sub["cls"])
        crosstab.index = [f"out>={threshold}" if t else f"out<{threshold}" for t in crosstab.index]
        print("\n" + crosstab.to_string())

        if approach == VANILLA:
            t = _trend_summary(levels)
            print(
                f"\nTruncated K={t['lo']}: {t['trunc_lo']:.0f}%  K={t['hi']}: {t['trunc_hi']:.0f}%  "
                f"(Spearman rho over K = {t['rho']:.2f})"
            )
            print(
                f"F1 drop K={t['lo']}->{t['hi']}: all {t['f1_lo']:.3f}->{t['f1_hi']:.3f} ({t['drop_all']:.3f}); "
                f"not truncated {t['f1_ok_lo']:.3f}->{t['f1_ok_hi']:.3f} ({t['drop_ok']:.3f}, n={t['n_ok_hi']:.0f} at K={t['hi']}); "
                f"share removed = {100 * t['share_removed']:.0f}%"
            )
            print(f"Not-truncated F1 range over all levels: {t['f1_ok_min']:.3f}-{t['f1_ok_max']:.3f}")
        print()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results-root", default=None)
    parser.add_argument("--axis",         default="completeness")
    parser.add_argument("--models",       nargs="+", default=None)
    parser.add_argument("--max-tokens",   type=int, default=MAX_TOKENS)
    parser.add_argument("--threshold",    type=int, default=TRUNC_THRESHOLD)
    parser.add_argument("--input-suffix", default="rescored",
                        help="Read benchmark_compare_<axis>_<suffix>.json when present (corrected metric); "
                             "pass '' for the logged scores")
    parser.add_argument("--output",       default=None,
                        help="CSV path. Defaults to benchmarks/results/truncation_<axis>_by_level.csv")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    calls, by_level = compute_tables(
        args.results_root, args.axis, args.models, args.max_tokens, args.threshold, args.input_suffix
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # empty truncated/not-truncated groups
        print_summary(calls, by_level, args.threshold)

    output = Path(args.output) if args.output else (
        _resolve_results_root(args.results_root).parent / f"truncation_{args.axis}_by_level.csv"
    )
    by_level.to_csv(output, index=False)
    print(f"Saved: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
