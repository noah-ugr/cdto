"""
plot_delta_uq.py  (v2 — paired-delta bootstrap)
================================================
Three delta figures for the PetriNet LLM Benchmark paper.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Callable

import matplotlib
matplotlib.use("Agg")
import matplotlib.lines as mlines
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator, StrMethodFormatter
import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from scipy import stats
import math

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmarks.comparisons.traceability import normalize_model_slug  # noqa: E402
from benchmarks.aggregator.c_star import (  # noqa: E402
    C_STAR_BAND, C_STAR_BAND_COLOR, C_STAR_MARKER, C_STAR_MARKER_EDGE, C_STAR_MARKER_SIZE,
    c_star_low, draw_c_star_markers,
)


# ══════════════════════════════════════════════════════════════════════════════
# STYLE CONFIGURATION (edit all sizes / colors here)
# ══════════════════════════════════════════════════════════════════════════════

# ── Global font sizes ─────────────────────────────────────────────────────────
FONT_SIZE_BASE = 26
FONT_SIZE_AXIS_LABEL = 26
FONT_SIZE_TICK_LABEL = 20
FONT_SIZE_SUBPLOT_LABEL = 24
FONT_SIZE_LEGEND_MAIN = 24
FONT_SIZE_LEGEND_EXPL = 22

# ── Font family ───────────────────────────────────────────────────────────────
FONT_FAMILY = "serif"
FONT_SERIF = ["Times New Roman"]

# ── Figure geometry ───────────────────────────────────────────────────────────
# The subplot grid keeps its original size. The extra height at the bottom
# is added ONLY to accommodate the legends, so subplots are not compressed.
PLOTS_FIGSIZE = (20, 10)             # width, height reserved for the subplots
LEGEND_EXTRA_HEIGHT = 3         # inches added below for the two legends
FIGSIZE = (PLOTS_FIGSIZE[0], PLOTS_FIGSIZE[1] + LEGEND_EXTRA_HEIGHT)
DPI = 160

# Fraction of total figure height reserved at the bottom for the legends.
# Computed from LEGEND_EXTRA_HEIGHT so it stays consistent.
_LEGEND_FRAC = LEGEND_EXTRA_HEIGHT / FIGSIZE[1]
TIGHT_LAYOUT_RECT = (0, _LEGEND_FRAC, 1, 1.0)

# ── C* saturation markers (complexity axis only) ──────────────────────────────
# Per-backend thresholds and band live in benchmarks/aggregator/c_star.py.
# Series triangles take the series colour; the reference model (figs 2-3) is black.
C_STAR_REFERENCE_COLOR = "#111111"
C_STAR_BAND_ALPHA = 0.15

# ── Curves ────────────────────────────────────────────────────────────────────
LINE_WIDTH = 2.8
CI_BAND_ALPHA = 0.22

# ── Legend layout ─────────────────────────────────────────────────────────────
# Positions in figure-fraction coordinates. Y is close to 0 for bottom-anchored.
LEGEND_MAIN_BBOX = (0.1, 0.01)
LEGEND_EXPL_BBOX = (0.92, 0.01)
LEGEND_BORDERPAD = 0.9
LEGEND_HANDLETEXTPAD = 1.0
LEGEND_COLUMNSPACING = 2.0


plt.rcParams.update({
    "font.family":      FONT_FAMILY,
    "font.serif":       FONT_SERIF,
    "font.size":        FONT_SIZE_BASE,
    "axes.titlesize":   FONT_SIZE_BASE + 2,
    "axes.labelsize":   FONT_SIZE_AXIS_LABEL,
    "xtick.labelsize":  FONT_SIZE_TICK_LABEL,
    "ytick.labelsize":  FONT_SIZE_TICK_LABEL,
    "legend.fontsize":  FONT_SIZE_LEGEND_MAIN,
})


# ══════════════════════════════════════════════════════════════════════════════
# Metric definitions
# ══════════════════════════════════════════════════════════════════════════════

METRICS: list[tuple[str, str, str, tuple | None]] = [
    ("ExactMatch",     "Exact Match",       "Δ Exact Match",                        None),
    ("F1Micro",        "Excision Micro-F1", "Δ F1 Score",                           None),
    ("Latency",        "Latency (s)",       "Δ Latency (s)\n(+ = A is faster)",     None),
    ("TotalTokens",    "Total Tokens",      "Δ Tokens\n(+ = A is cheaper)",         None),
    ("CollateralRate", "Collateral Rate",   "Δ Collateral Rate\n(+ = A has fewer)", None),
    ("OmissionRate",   "Omission Rate",     "Δ Omission Rate\n(+ = A has fewer)",   None),
]

LOWER_IS_BETTER: set[str] = {"Latency", "TotalTokens", "CollateralRate", "OmissionRate"}

ARCH_YLABEL_OVERRIDES: dict[str, str] = {
    "Latency":        "Δ Seconds\n(+ = A is faster)",
    "TotalTokens":    "Δ Tokens\n(+ = A is cheaper)",
    "CollateralRate": "Δ collateral/pred\n(+ = A has fewer)",
    "OmissionRate":   "Δ omissions/gt\n(+ = A has fewer)",
}

METRIC_EXTRACTORS: dict[str, Callable[[dict], float]] = {
    "ExactMatch":     lambda r: float(r["exact_match"]),
    "F1Micro":        lambda r: float(r["f1_micro"]),
    "Latency":        lambda r: float(r["latency_s"]),
    "TotalTokens":    lambda r: float(r["token_usage"]["total"]),
    "CollateralRate": lambda r: float(r["collateral_rate"]),
    "OmissionRate":   lambda r: float(r["omission_rate"]),
}

PLANNER = "planner_executor"
VANILLA = "vanilla"

ZERO_COLOR       = "#444444"
BAND_ABOVE_COLOR = "#d4edda"
BAND_BELOW_COLOR = "#f8d7da"
BAND_ALPHA       = 0.35

HIGH_CONTRAST_COLORS = [
    "#1f77b4", "#d62728", "#2ca02c", "#ff7f0e",
    "#9467bd", "#8c564b", "#e377c2", "#17becf",
    "#bcbd22", "#7f7f7f",
]

Groups = dict[tuple[str, int], list[dict]]


# ══════════════════════════════════════════════════════════════════════════════
# BCa bootstrap
# ══════════════════════════════════════════════════════════════════════════════

def _bca_bootstrap(
    data: np.ndarray,
    statistic: Callable[[np.ndarray], float] = np.mean,
    n_iter: int = 10_000,
    alpha: float = 0.05,
    rng: np.random.Generator | None = None,
    seed: int = 0,
) -> tuple[float, float, float]:
    rng = rng or np.random.default_rng(seed)
    n = len(data)
    theta_hat = float(statistic(data))

    idx = rng.integers(0, n, size=(n_iter, n))
    boot_stats = (
        data[idx].mean(axis=1)
        if statistic is np.mean
        else np.array([statistic(data[idx[i]]) for i in range(n_iter)])
    )

    prop_below = np.clip(np.mean(boot_stats < theta_hat), 1e-6, 1 - 1e-6)
    z0 = stats.norm.ppf(prop_below)

    jack_stats = (
        (data.sum() - data) / (n - 1)
        if statistic is np.mean
        else np.array([statistic(np.delete(data, i)) for i in range(n)])
    )
    jack_mean = jack_stats.mean()
    diffs     = jack_mean - jack_stats
    num = np.sum(diffs ** 3)
    den = 6.0 * (np.sum(diffs ** 2) ** 1.5)
    a_hat = num / den if den != 0 else 0.0

    z_lo = stats.norm.ppf(alpha / 2)
    z_hi = stats.norm.ppf(1 - alpha / 2)

    def _adj(z_k: float) -> float:
        numer = z0 + z_k
        denom = 1.0 - a_hat * (z0 + z_k)
        if denom == 0:
            return alpha / 2 if z_k < 0 else 1 - alpha / 2
        return float(stats.norm.cdf(z0 + numer / denom))

    pct_lo = np.clip(_adj(z_lo), 0.0, 1.0)
    pct_hi = np.clip(_adj(z_hi), 0.0, 1.0)

    return (
        theta_hat,
        float(np.percentile(boot_stats, 100 * pct_lo)),
        float(np.percentile(boot_stats, 100 * pct_hi)),
    )


# ══════════════════════════════════════════════════════════════════════════════
# JSON loading
# ══════════════════════════════════════════════════════════════════════════════

def _load_json_groups(
    json_path: Path,
    axis: str,
    sort_key: str | None = None,
) -> Groups:
    level_field = "complexity" if axis == "complexity" else "completeness"

    with json_path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)

    groups: Groups = {}
    for rec in raw["detailed_results"]:
        level = int(rec[level_field])
        key   = (rec["approach"], level)
        groups.setdefault(key, []).append(rec)

    if sort_key:
        groups = {
            k: sorted(v, key=lambda r: r[sort_key])
            for k, v in groups.items()
        }

    return groups


def _json_path_for_model(
    results_root: Path,
    model: str,
    axis: str,
    run_tag: str | None,
) -> Path:
    slug = normalize_model_slug(model)
    tag  = f"_{normalize_model_slug(run_tag)}" if run_tag else ""
    candidates = [
        results_root / slug / axis / f"benchmark_compare_{axis}{tag}.json",
        results_root / slug / axis / f"benchmark_{axis}{tag}.json",
        results_root / slug / f"benchmark_compare_{axis}{tag}.json",
    ]
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError(
        f"Raw JSON not found for model '{model}'.\nTried:\n"
        + "\n".join(f"  {p}" for p in candidates)
    )


# ══════════════════════════════════════════════════════════════════════════════
# Paired-delta bootstrap
# ══════════════════════════════════════════════════════════════════════════════

def _delta_bootstrap_one(
    records_a: list[dict],
    records_b: list[dict],
    metric: str,
    invert: bool,
    alpha: float,
    n_iter: int,
    seed: int,
) -> tuple[float, float, float]:
    extractor = METRIC_EXTRACTORS[metric]
    n = min(len(records_a), len(records_b))
    if n == 0:
        return (np.nan, np.nan, np.nan)

    arr_a = np.array([extractor(r) for r in records_a[:n]], dtype=float)
    arr_b = np.array([extractor(r) for r in records_b[:n]], dtype=float)

    delta = arr_b - arr_a if invert else arr_a - arr_b

    rng = np.random.default_rng(seed)
    return _bca_bootstrap(delta, np.mean, n_iter, alpha, rng, seed)


def _build_delta_df(
    groups_a: Groups,
    groups_b: Groups,
    approach_a: str,
    approach_b: str,
    alpha: float,
    n_iter: int,
    base_seed: int,
    n_jobs: int,
    invert_lower_is_better: bool = False,
) -> pd.DataFrame:
    levels = sorted(
        lv
        for (ap, lv) in groups_a
        if ap == approach_a and (approach_b, lv) in groups_b
    )

    seed_matrix = np.random.default_rng(base_seed).integers(
        0, 2**32, size=(len(levels), len(METRICS))
    )

    def _one_level(i: int, level: int) -> dict:
        ra = groups_a.get((approach_a, level), [])
        rb = groups_b.get((approach_b, level), [])
        row: dict = {"Level": level}
        for j, (metric, *_) in enumerate(METRICS):
            invert = invert_lower_is_better and metric in LOWER_IS_BETTER
            mean_d, lo, hi = _delta_bootstrap_one(
                ra, rb, metric,
                invert=invert,
                alpha=alpha,
                n_iter=n_iter,
                seed=int(seed_matrix[i, j]),
            )
            row[f"{metric}_Mean_delta"]     = mean_d
            row[f"{metric}_CI_lower_delta"] = lo
            row[f"{metric}_CI_upper_delta"] = hi
        return row

    rows = Parallel(n_jobs=n_jobs, verbose=0)(
        delayed(_one_level)(i, level) for i, level in enumerate(levels)
    )
    return pd.DataFrame(rows).sort_values("Level").reset_index(drop=True)


def _architecture_delta_df(groups: Groups, **kw) -> pd.DataFrame:
    return _build_delta_df(
        groups_a=groups, groups_b=groups,
        approach_a=PLANNER, approach_b=VANILLA,
        invert_lower_is_better=True,
        **kw,
    )


def _model_delta_df(
    groups_ref: Groups,
    groups_other: Groups,
    approach: str,
    **kw,
) -> pd.DataFrame:
    return _build_delta_df(
        groups_a=groups_ref, groups_b=groups_other,
        approach_a=approach, approach_b=approach,
        invert_lower_is_better=True,
        **kw,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Y-axis auto-range
# ══════════════════════════════════════════════════════════════════════════════

def _auto_ylimits(
    series: list[tuple[str, pd.DataFrame]],
    metric: str,
    margin_frac: float = 0.15,
) -> tuple[float, float]:
    mean_col = f"{metric}_Mean_delta"
    lo_col   = f"{metric}_CI_lower_delta"
    hi_col   = f"{metric}_CI_upper_delta"

    vals: list[float] = [0.0]
    for _, d in series:
        if d.empty:
            continue
        for col in (mean_col, lo_col, hi_col):
            if col in d.columns:
                arr = d[col].dropna().to_numpy()
                vals.extend(arr[np.isfinite(arr)].tolist())

    minv = min(vals)
    maxv = max(vals)
    span = maxv - minv

    if span <= 0 or not np.isfinite(span):
        center = minv
        half = max(abs(center) * 0.2, 0.05)
        return center - half, center + half

    margin = span * margin_frac
    return minv - margin, maxv + margin


# ══════════════════════════════════════════════════════════════════════════════
# Plot helpers
# ══════════════════════════════════════════════════════════════════════════════

def _series_colors(n: int) -> list[str]:
    return [HIGH_CONTRAST_COLORS[i % len(HIGH_CONTRAST_COLORS)] for i in range(n)]


def _draw_panel(
    ax: plt.Axes,
    series: list[tuple[str, pd.DataFrame]],
    metric: str,
    metric_title: str,
    y_label: str,
    x_label: str,
    colors: list[str],
    axis: str,
    c_star_markers: list[tuple[float, str]] | None = None,
) -> None:
    mean_col = f"{metric}_Mean_delta"
    lo_col   = f"{metric}_CI_lower_delta"
    hi_col   = f"{metric}_CI_upper_delta"

    y_lo, y_hi = _auto_ylimits(series, metric)

    ax.axhspan(0,    y_hi, color=BAND_ABOVE_COLOR, alpha=BAND_ALPHA, zorder=0, linewidth=0)
    ax.axhspan(y_lo, 0,    color=BAND_BELOW_COLOR, alpha=BAND_ALPHA, zorder=0, linewidth=0)
    ax.axhline(0, color=ZERO_COLOR, linewidth=1.2, linestyle="--", zorder=2)

    x_all: list[float] = []
    for (label, delta_df), color in zip(series, colors):
        if delta_df.empty or mean_col not in delta_df.columns:
            continue
        x  = delta_df["Level"].to_numpy()
        y  = delta_df[mean_col].to_numpy()
        lo = delta_df[lo_col].to_numpy()
        hi = delta_df[hi_col].to_numpy()

        ax.plot(x, y, linewidth=LINE_WIDTH, color=color, label=label, zorder=4)
        ax.fill_between(x, lo, hi, color=color, alpha=CI_BAND_ALPHA, zorder=3)
        x_all.extend(x.tolist())

    ax.set_xlabel(x_label, fontsize=FONT_SIZE_AXIS_LABEL)
    ax.set_ylabel(y_label, fontsize=FONT_SIZE_AXIS_LABEL)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.xaxis.set_major_formatter(StrMethodFormatter("{x:.0f}"))
    ax.grid(True, linestyle="--", alpha=0.35, zorder=1)
    ax.tick_params(axis="both", which="major", labelsize=FONT_SIZE_TICK_LABEL)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_ylim(y_lo, y_hi)

    if axis == "complexity" and x_all:
        draw_c_star_markers(ax, np.asarray(x_all), c_star_markers or [], band_alpha=C_STAR_BAND_ALPHA)


def _attach_legend(
    fig: plt.Figure,
    axes: np.ndarray,
    n_series: int,
    mode: str,
    axis: str,
) -> None:
    """
    Two side-by-side legend boxes below the subplots:
      LEFT  — series + green/red bands + (if complexity) C* markers.
      RIGHT — plain-language A/B explanation.
    """
    handles, labels = axes.flatten()[0].get_legend_handles_labels()

    band_above = mpatches.Patch(
        color=BAND_ABOVE_COLOR, alpha=0.9,
        label="GREEN zone: A is better",
    )
    band_below = mpatches.Patch(
        color=BAND_BELOW_COLOR, alpha=0.9,
        label="RED zone: B is better",
    )

    leg1_handles = handles + [band_above, band_below]
    leg1_labels  = labels  + [band_above.get_label(), band_below.get_label()]

    if axis == "complexity":
        def _triangle(color: str, label: str) -> mlines.Line2D:
            return mlines.Line2D(
                [], [],
                linestyle="none",
                marker=C_STAR_MARKER,
                markersize=C_STAR_MARKER_SIZE,
                color=color,
                markeredgecolor=C_STAR_MARKER_EDGE,
                label=label,
            )

        if mode == "architecture":
            c_star_handles = [_triangle("#9a9a9a", r"$C^{*}_{\mathrm{low}}$ per model (series colour)")]
        else:
            c_star_handles = [
                _triangle("#9a9a9a", r"$C^{*}_{\mathrm{low}}$ of B (series colour)"),
                _triangle(C_STAR_REFERENCE_COLOR, r"$C^{*}_{\mathrm{low}}$ of A"),
            ]
        band_lo, band_hi = C_STAR_BAND
        c_star_handles.append(mpatches.Patch(
            color=C_STAR_BAND_COLOR,
            alpha=2 * C_STAR_BAND_ALPHA,
            label=r"$C^{*}$ zone " f"({band_lo}–{band_hi})",
        ))
        leg1_handles.extend(c_star_handles)
        leg1_labels.extend(h.get_label() for h in c_star_handles)

    ncol1 = 2

    fig.legend(
        leg1_handles, leg1_labels,
        loc="lower left",
        ncol=ncol1,
        frameon=True,
        framealpha=0.97,
        edgecolor="#444444",
        fontsize=FONT_SIZE_LEGEND_MAIN,
        handlelength=3.0,
        handletextpad=LEGEND_HANDLETEXTPAD,
        columnspacing=LEGEND_COLUMNSPACING,
        borderpad=LEGEND_BORDERPAD,
        bbox_to_anchor=LEGEND_MAIN_BBOX,
    )

    if mode == "architecture":
        expl_a = "A = Planner-Executor:\nplan first, then execute step by step"
        expl_b = "B = Vanilla:\nsingle-pass answer, no explicit planning"
    else:
        expl_a = "A = Reference model\n(baseline)"
        expl_b = "B = Compared model\n(each colour = one model)"

    def _text_patch(txt: str) -> mpatches.Patch:
        return mpatches.Patch(facecolor="none", edgecolor="none", label=txt)

    fig.legend(
        [_text_patch(expl_a), _text_patch(expl_b)],
        [expl_a, expl_b],
        loc="lower right",
        ncol=1,
        frameon=True,
        framealpha=0.97,
        edgecolor="#444444",
        fontsize=FONT_SIZE_LEGEND_EXPL,
        handlelength=0,
        handletextpad=0,
        borderpad=LEGEND_BORDERPAD,
        bbox_to_anchor=LEGEND_EXPL_BBOX,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Figure builders
# ══════════════════════════════════════════════════════════════════════════════

def _figure_architecture_effect(
    model_series: list[tuple[str, pd.DataFrame]],
    axis: str,
    out_path: Path,
    c_star_lows: list[float | None] | None = None,
) -> None:
    x_label = "Complexity (C)" if axis == "complexity" else "Completeness (K)"
    fig, axes = plt.subplots(2, 3, figsize=FIGSIZE)
    colors = _series_colors(len(model_series))
    c_star_markers = [(c, color) for c, color in zip(c_star_lows or [], colors) if c is not None]

    for ax, (metric, title, y_label, _) in zip(axes.flatten(), METRICS):
        _draw_panel(
            ax, model_series, metric,
            metric_title=title,
            y_label=ARCH_YLABEL_OVERRIDES.get(metric, y_label),
            x_label=x_label,
            colors=colors,
            axis=axis,
            c_star_markers=c_star_markers,
        )

    subplot_labels = ['(a)', '(b)', '(c)', '(d)', '(e)', '(f)']
    for ax, label in zip(axes.flatten(), subplot_labels):
        ax.text(
            0.5, 1.02,
            label,
            transform=ax.transAxes,
            fontsize=FONT_SIZE_SUBPLOT_LABEL,
            fontweight='bold',
            va='bottom', ha='center'
        )

    _attach_legend(fig, axes, len(model_series), mode="architecture", axis=axis)
    plt.tight_layout(rect=TIGHT_LAYOUT_RECT)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"✓ Fig 1 saved: {out_path}")


def _figure_model_effect_within(
    comparison_series: list[tuple[str, pd.DataFrame]],
    approach: str,
    axis: str,
    out_path: Path,
    c_star_lows: list[float | None] | None = None,
    reference_c_star: float | None = None,
) -> None:
    x_label = "Complexity (C)" if axis == "complexity" else "Completeness (K)"

    fig, axes = plt.subplots(2, 3, figsize=FIGSIZE)
    colors = _series_colors(len(comparison_series))
    c_star_markers = [(c, color) for c, color in zip(c_star_lows or [], colors) if c is not None]
    if reference_c_star is not None:
        c_star_markers.append((reference_c_star, C_STAR_REFERENCE_COLOR))

    for ax, (metric, title, y_label, _) in zip(axes.flatten(), METRICS):
        _draw_panel(
            ax, comparison_series, metric,
            metric_title=title,
            y_label=y_label,
            x_label=x_label,
            colors=colors,
            axis=axis,
            c_star_markers=c_star_markers,
        )

    subplot_labels = ['(a)', '(b)', '(c)', '(d)', '(e)', '(f)']
    for ax, label in zip(axes.flatten(), subplot_labels):
        ax.text(
            0.5, 1.02,
            label,
            transform=ax.transAxes,
            fontsize=FONT_SIZE_SUBPLOT_LABEL,
            fontweight='bold',
            va='bottom', ha='center'
        )

    _attach_legend(fig, axes, len(comparison_series), mode="model_effect", axis=axis)
    plt.tight_layout(rect=TIGHT_LAYOUT_RECT)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=DPI)
    plt.close(fig)
    is_fig2 = approach == PLANNER
    print(f"✓ {'Fig 2' if is_fig2 else 'Fig 3'} saved: {out_path}")


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Paired-delta BCa bootstrap figures from raw benchmark JSONs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--labels", nargs="+", default=None)
    parser.add_argument("--reference-model", default=None)
    parser.add_argument("--reference-label", default=None)
    parser.add_argument("--axis", choices=["complexity", "completeness"], required=True)
    parser.add_argument("--results-root", default="benchmarks/results/models")
    parser.add_argument("--run-tag", default=None)
    parser.add_argument("--sort-key", default=None)
    parser.add_argument("--n-iter", type=int, default=10_000)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-jobs", type=int, default=-1)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    if len(args.models) < 2:
        raise ValueError("--models requires at least two model names.")

    models = args.models
    labels = args.labels if args.labels else models
    if len(labels) != len(models):
        raise ValueError("--labels must have the same number of entries as --models.")

    label_by_model = dict(zip(models, labels))
    results_root   = (REPO_ROOT / args.results_root).resolve()

    print(f"\n[plot_delta_uq] Loading {len(models)} model JSONs  (axis={args.axis})")
    model_groups: dict[str, Groups] = {}
    for model in models:
        json_path = _json_path_for_model(results_root, model, args.axis, args.run_tag)
        print(f"  {label_by_model[model]:30s}  ←  {json_path.relative_to(REPO_ROOT)}")
        model_groups[model] = _load_json_groups(json_path, args.axis, args.sort_key)

    bkw = dict(alpha=args.alpha, n_iter=args.n_iter, n_jobs=args.n_jobs)
    rng_master = np.random.default_rng(args.seed)

    reference_model   = args.reference_model or models[0]
    if reference_model not in model_groups:
        raise ValueError(f"--reference-model '{reference_model}' not in --models.")
    reference_label   = args.reference_label or label_by_model[reference_model]
    comparison_models = [m for m in models if m != reference_model]

    tag_slug = f"_{normalize_model_slug(args.run_tag)}" if args.run_tag else ""
    out_dir  = (
        Path(args.output_dir).resolve() if args.output_dir
        else results_root / "aggregated" / f"delta_{args.axis}{tag_slug}"
    )

    # ══ Figure 1 — Architecture Effect ═══════════════════════════════════════
    print("\n[plot_delta_uq] Fig 1 — Architecture Effect  (paired BCa on δ)")
    fig1_series: list[tuple[str, pd.DataFrame]] = []
    for model in models:
        seed = int(rng_master.integers(0, 2**32))
        df = _architecture_delta_df(groups=model_groups[model], base_seed=seed, **bkw)
        fig1_series.append((label_by_model[model], df))

    _figure_architecture_effect(
        model_series=fig1_series,
        axis=args.axis,
        out_path=out_dir / "fig1_architecture_effect.pdf",
        c_star_lows=[c_star_low(m) for m in models],
    )

    # ══ Figures 2 & 3 — Model Effect ═════════════════════════════════════════
    for approach, fname, desc in [
        (PLANNER, "fig2_model_effect_agentic.pdf",  "Fig 2 — Model Effect Agentic"),
        (VANILLA, "fig3_model_effect_vanilla.pdf",  "Fig 3 — Model Effect Vanilla"),
    ]:
        print(f"\n[plot_delta_uq] {desc}  (paired BCa on δ)")
        comp_series: list[tuple[str, pd.DataFrame]] = []
        for other in comparison_models:
            seed = int(rng_master.integers(0, 2**32))
            df = _model_delta_df(
                groups_ref=model_groups[reference_model],
                groups_other=model_groups[other],
                approach=approach,
                base_seed=seed,
                **bkw,
            )
            comp_series.append((f"{reference_label} − {label_by_model[other]}", df))

        _figure_model_effect_within(
            comparison_series=comp_series,
            approach=approach,
            axis=args.axis,
            out_path=out_dir / fname,
            c_star_lows=[c_star_low(m) for m in comparison_models],
            reference_c_star=c_star_low(reference_model),
        )

    print(f"\n[plot_delta_uq] Done. Figures saved to: {out_dir}")


if __name__ == "__main__":
    main()