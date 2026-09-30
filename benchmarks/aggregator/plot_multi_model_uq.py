"""
Aggregate multi-model UQ CSVs and generate combined CI95 plots.

Expected input per model:
  benchmarks/results/models/<model_slug>/<axis>/uq_<axis>[_tag]_results.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.lines as mlines
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator, StrMethodFormatter
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

import sys
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmarks.comparisons.traceability import normalize_model_slug
from benchmarks.aggregator.c_star import (
    C_STAR_BAND, C_STAR_BAND_COLOR, C_STAR_MARKER, C_STAR_MARKER_EDGE, C_STAR_MARKER_SIZE,
    c_star_low, draw_c_star_markers,
)


# ══════════════════════════════════════════════════════════════════════════════
# STYLE CONFIGURATION (edit all sizes / colors here)
# ══════════════════════════════════════════════════════════════════════════════

# ── Global font sizes ─────────────────────────────────────────────────────────
FONT_SIZE_BASE = 26
FONT_SIZE_AXIS_LABEL = 26        # x-label and y-label of each subplot
FONT_SIZE_TICK_LABEL = 24        # x-tick and y-tick labels
FONT_SIZE_SUBPLOT_LABEL = 24     # the "(a)", "(b)", ... labels above each subplot
FONT_SIZE_LEGEND = 24            # bottom legend

# ── Font family ───────────────────────────────────────────────────────────────
FONT_FAMILY = "serif"
FONT_SERIF = ["Times New Roman"]

# ── Figure geometry ───────────────────────────────────────────────────────────
FIGSIZE = (18, 10)
DPI = 160

# Reserve room at the bottom of the figure for the legend and its gap.
TIGHT_LAYOUT_RECT = (0, 0.14, 1, 0.98)

# ── C* saturation markers (complexity axis only) ──────────────────────────────
# Per-backend thresholds and band live in benchmarks/aggregator/c_star.py.
C_STAR_BAND_ALPHA = 0.18

# ── Curves ────────────────────────────────────────────────────────────────────
LINE_WIDTH = 2.5
MARKER_SIZE = 6
MARKEVERY = 2
CI_BAND_ALPHA = 0.15

# ── Legend ────────────────────────────────────────────────────────────────────
LEGEND_NCOL = 4                  # models (4) + C* entries (2) fit better in 4 cols wrapped
LEGEND_BBOX = (0.5, -0.01)
LEGEND_BORDERPAD = 0.9
LEGEND_HANDLETEXTPAD = 1.0
LEGEND_COLUMNSPACING = 2.2


plt.rcParams.update({
    "font.family":      FONT_FAMILY,
    "font.serif":       FONT_SERIF,
    "font.size":        FONT_SIZE_BASE,
    "axes.titlesize":   FONT_SIZE_BASE + 2,
    "axes.labelsize":   FONT_SIZE_AXIS_LABEL,
    "xtick.labelsize":  FONT_SIZE_TICK_LABEL,
    "ytick.labelsize":  FONT_SIZE_TICK_LABEL,
    "legend.fontsize":  FONT_SIZE_LEGEND,
})


# ══════════════════════════════════════════════════════════════════════════════
# Metrics (2 rows × 3 cols order)
# ══════════════════════════════════════════════════════════════════════════════

METRICS = [
    ("ExactMatch",     "Exact Match",       "Exact Match"),
    ("F1Micro",        "Excision Micro-F1", "F1 Score"),
    ("Latency",        "Latency",           "Latency (s)"),
    ("TotalTokens",    "Total Tokens",      "Tokens"),
    ("CollateralRate", "Collateral Rate",   "Collateral Rate"),
    ("OmissionRate",   "Omission Rate",     "Omission Rate"),
]

_HIGH_CONTRAST_COLORS = [
    "#1f77b4", "#d62728", "#2ca02c", "#ff7f0e",
    "#9467bd", "#8c564b", "#e377c2", "#17becf",
    "#bcbd22", "#7f7f7f",
]

# Approach → line style
_APPROACH_STYLE: Dict[str, dict] = {
    "planner_executor": dict(linestyle="-",  marker="o",
                             label="Planner-Executor  (agentic: plan then execute)"),
    "vanilla":          dict(linestyle="--", marker="s",
                             label="Vanilla  (monolithic: single-step answer)"),
}
_DEFAULT_APPROACH_STYLE = dict(linestyle=":", marker="^", label="unknown")


# ══════════════════════════════════════════════════════════════════════════════
# C* helper
# ══════════════════════════════════════════════════════════════════════════════

def _draw_c_star_markers(ax, x_values: np.ndarray, colors: Dict[str, str]) -> None:
    """
    Shade the saturation band on a complexity-axis subplot and mark each
    backend's C*_low with a triangle in that backend's colour on the top edge.
    """
    markers = [(c_star_low(m), color) for m, color in colors.items() if c_star_low(m) is not None]
    draw_c_star_markers(ax, x_values, markers, band_alpha=C_STAR_BAND_ALPHA)


# ══════════════════════════════════════════════════════════════════════════════
# I/O helpers
# ══════════════════════════════════════════════════════════════════════════════

def _read_uq_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing UQ CSV: {path}")
    return pd.read_csv(path, comment="#")


def _build_uq_path(results_root: Path, model_name: str, axis: str, run_tag: str | None) -> Path:
    model_slug = normalize_model_slug(model_name)
    axis_dir   = results_root / model_slug / axis
    tag        = f"_{normalize_model_slug(run_tag)}" if run_tag else ""
    return axis_dir / f"uq_{axis}{tag}_results.csv"


def _combine_model_frames(
    results_root: Path,
    models: List[str],
    axis: str,
    run_tag: str | None,
) -> pd.DataFrame:
    frames: List[pd.DataFrame] = []
    for model in models:
        csv_path = _build_uq_path(results_root, model, axis, run_tag)
        df = _read_uq_csv(csv_path)
        df["Model"] = model
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def _palette(models: List[str]) -> Dict[str, str]:
    return {m: _HIGH_CONTRAST_COLORS[i % len(_HIGH_CONTRAST_COLORS)] for i, m in enumerate(models)}


# ══════════════════════════════════════════════════════════════════════════════
# Auto y-limits (data-driven, always includes zero, with small margin)
# ══════════════════════════════════════════════════════════════════════════════

def _auto_ylimits(
    df: pd.DataFrame,
    models: List[str],
    approaches: List[str],
    metric: str,
    margin_frac: float = 0.12,
) -> tuple[float, float]:
    mean_col = f"{metric}_Mean"
    lo_col   = f"{metric}_CI_Lower"
    hi_col   = f"{metric}_CI_Upper"

    vals: list[float] = []
    for col in (mean_col, lo_col, hi_col):
        if col in df.columns:
            arr = df[col].dropna().to_numpy()
            vals.extend(arr[np.isfinite(arr)].tolist())

    if not vals:
        return -1.0, 1.0

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
# Legend (single row below the subplots)
# ══════════════════════════════════════════════════════════════════════════════

def _attach_legends(
    fig: plt.Figure,
    models: List[str],
    approaches: List[str],
    colors: Dict[str, str],
    model_labels: Dict[str, str],
    include_c_star: bool = False,
) -> None:
    """
    Build the legend at the bottom of the figure.
    Models come first (colour patches). If include_c_star is True, two
    additional entries are appended: the per-backend C*_low triangle and the
    saturation band.
    """
    model_handles = [
        mpatches.Patch(color=colors[m], label=model_labels.get(m, m))
        for m in models
    ]

    handles = list(model_handles)

    if include_c_star:
        band_lo, band_hi = C_STAR_BAND
        c_star_handles = [
            mlines.Line2D(
                [], [],
                linestyle="none",
                marker=C_STAR_MARKER,
                markersize=C_STAR_MARKER_SIZE,
                color="#9a9a9a",
                markeredgecolor=C_STAR_MARKER_EDGE,
                label=r"$C^{*}_{\mathrm{low}}$ per backend",
            ),
            mpatches.Patch(
                color=C_STAR_BAND_COLOR,
                alpha=2 * C_STAR_BAND_ALPHA,
                label=r"$C^{*}$ zone " f"({band_lo}–{band_hi})",
            ),
        ]
        handles.extend(c_star_handles)

    fig.legend(
        handles,
        [h.get_label() for h in handles],
        loc="lower center",
        ncol=LEGEND_NCOL,
        frameon=True,
        framealpha=0.97,
        edgecolor="#444444",
        fontsize=FONT_SIZE_LEGEND,
        handlelength=3.0,
        handletextpad=LEGEND_HANDLETEXTPAD,
        columnspacing=LEGEND_COLUMNSPACING,
        borderpad=LEGEND_BORDERPAD,
        bbox_to_anchor=LEGEND_BBOX,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Main plot function
# ══════════════════════════════════════════════════════════════════════════════

def plot_multi_model_uq(
    df: pd.DataFrame,
    models: List[str],
    axis: str,
    out_path: Path,
    model_labels: Dict[str, str] | None = None,
) -> None:
    if model_labels is None:
        model_labels = {m: m for m in models}

    approaches = sorted(df["Approach"].unique().tolist())
    colors     = _palette(models)

    x_label = "Complexity (C)" if axis == "complexity" else "Completeness (K)"

    fig, axes = plt.subplots(2, 3, figsize=FIGSIZE)
    flat_axes = axes.flatten()

    for ax, (metric_key, title, y_label) in zip(flat_axes, METRICS):
        mean_col = f"{metric_key}_Mean"
        lo_col   = f"{metric_key}_CI_Lower"
        hi_col   = f"{metric_key}_CI_Upper"

        y_lo, y_hi = _auto_ylimits(df, models, approaches, metric_key)

        for model in models:
            model_df = df[df["Model"] == model]
            for approach in approaches:
                sub = model_df[model_df["Approach"] == approach].sort_values("Level")
                if sub.empty:
                    continue

                x  = sub["Level"].to_numpy()
                y  = sub[mean_col].to_numpy()
                lo = sub[lo_col].to_numpy()
                hi = sub[hi_col].to_numpy()

                style = _APPROACH_STYLE.get(approach, _DEFAULT_APPROACH_STYLE)
                color = colors[model]

                ax.plot(
                    x, y,
                    linestyle=style["linestyle"],
                    marker=style["marker"],
                    markevery=MARKEVERY,
                    markersize=MARKER_SIZE,
                    linewidth=LINE_WIDTH,
                    color=color,
                    label=model_labels.get(model, model),
                )
                ax.fill_between(x, lo, hi, color=color, alpha=CI_BAND_ALPHA)

        ax.set_xlabel(x_label, fontsize=FONT_SIZE_AXIS_LABEL)
        ax.set_ylabel(y_label, fontsize=FONT_SIZE_AXIS_LABEL)
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.xaxis.set_major_formatter(StrMethodFormatter("{x:.0f}"))
        ax.grid(True, linestyle="--", alpha=0.35)
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(axis="both", which="major", labelsize=FONT_SIZE_TICK_LABEL)
        ax.set_ylim(y_lo, y_hi)

        if axis == "complexity":
            x_all_for_ax = df["Level"].to_numpy()
            _draw_c_star_markers(ax, x_all_for_ax, colors)

    # Add centered subplot labels (a, b, c, ...).
    subplot_labels = ['(a)', '(b)', '(c)', '(d)', '(e)', '(f)']
    for ax, label in zip(flat_axes, subplot_labels):
        ax.text(
            0.5, 1.02,
            label,
            transform=ax.transAxes,
            fontsize=FONT_SIZE_SUBPLOT_LABEL,
            fontweight='bold',
            va='bottom', ha='center'
        )

    _attach_legends(
        fig, models, approaches, colors, model_labels,
        include_c_star=(axis == "complexity"),
    )

    plt.tight_layout(rect=TIGHT_LAYOUT_RECT)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"✓ Saved figure: {out_path}")


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Aggregate model UQ CSVs and produce combined CI95 plots"
    )
    parser.add_argument("--models",       nargs="+", required=True,
                        help="Model names (same as benchmark --llm-model)")
    parser.add_argument("--labels",       nargs="+", default=None,
                        help="Display labels aligned with --models.")
    parser.add_argument("--axis",         choices=["complexity", "completeness"], required=True)
    parser.add_argument("--results-root", default="benchmarks/results/models",
                        help="Root folder for model-scoped outputs")
    parser.add_argument("--run-tag",      default=None,
                        help="Optional run tag used when generating UQ CSV names")
    parser.add_argument("--output",       default=None,
                        help="Output PNG path. If omitted uses benchmarks/results/models/aggregated/")
    args = parser.parse_args()

    models = args.models
    labels = args.labels if args.labels else models
    if len(labels) != len(models):
        raise ValueError("--labels must have the same number of entries as --models.")
    model_labels = dict(zip(models, labels))

    results_root = (REPO_ROOT / args.results_root).resolve()
    df = _combine_model_frames(
        results_root=results_root,
        models=models,
        axis=args.axis,
        run_tag=args.run_tag,
    )

    if args.output:
        out_path = (REPO_ROOT / args.output).resolve()
    else:
        tag = f"_{normalize_model_slug(args.run_tag)}" if args.run_tag else ""
        out_path = (
            results_root / "aggregated" / f"multi_model_uq_{args.axis}{tag}_v2.pdf"
        ).resolve()

    # Ensure output uses PDF extension
    out_path = out_path.with_suffix('.pdf')

    plot_multi_model_uq(df=df, models=models, axis=args.axis, out_path=out_path,
                        model_labels=model_labels)


if __name__ == "__main__":
    main()