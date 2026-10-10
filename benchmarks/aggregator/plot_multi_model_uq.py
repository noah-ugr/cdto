"""
Aggregate multi-model UQ CSVs and generate combined CI95 plots.

Expected input per model:
  benchmarks/results/models/<model_slug>/<axis>/uq_<axis>[_tag]_results.csv

By default the figure has the six metrics in a 2 x 3 grid. --panels picks an
ordered subset of them (em, f1, latency, tokens, fp, fn) and --layout the grid
(e.g. 1x3, 2x2).
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
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

# Top of the panels; the bottom is set by the height of the legend.
TIGHT_LAYOUT_TOP = 0.98

# ── C* saturation markers (complexity axis only) ──────────────────────────────
# Per-backend thresholds and band live in benchmarks/aggregator/c_star.py.
C_STAR_BAND_ALPHA = 0.18

# ── Curves ────────────────────────────────────────────────────────────────────
LINE_WIDTH = 2.5
MARKER_SIZE = 6
MARKEVERY = 2
CI_BAND_ALPHA = 0.15

# ── Legend ────────────────────────────────────────────────────────────────────
# Two rows (one column per pair of entries) when they fit the width of the
# panels, otherwise the last pair in a third row.
LEGEND_BBOX = (0.5, -0.01)
LEGEND_BORDERPAD = 0.9
LEGEND_HANDLETEXTPAD = 1.0
LEGEND_COLUMNSPACING = 2.2
LEGEND_MAX_WIDTH = 0.95          # fraction of the figure width that the panels span
LEGEND_GAP = 0.25                # inches between the legend and the x-labels (plus the layout pad)
LINE_STYLE_COLOR = "#333333"     # dark grey of the P-E / baseline entries
LINE_STYLE_MARKER_SIZE = 9

# ── Figures with a subset of the panels (--panels / --layout) ─────────────────
# Same width as the six-panel figure. Each panel prints larger at the text
# width of the paper (16.5 cm), so the fonts are larger.
SUBSET_FONT_SIZE_AXIS_LABEL = 32
SUBSET_FONT_SIZE_TICK_LABEL = 28
SUBSET_FONT_SIZE_SUBPLOT_LABEL = 30
SUBSET_FONT_SIZE_LEGEND = 28
SUBSET_X_TICK_SPACING = 1.4      # inches of panel width per x-tick interval (at most)
SUBSET_LEGEND_COLUMNSPACING = 1.5
SUBSET_ROW_HEIGHT = 5.0          # inches per row of panels, plus the legend below


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


@dataclass(frozen=True)
class FigureStyle:
    figsize: tuple[float, float]
    grow_for_legend: bool        # add the legend below figsize (otherwise it fits inside)
    font_size_axis_label: float
    font_size_tick_label: float
    font_size_subplot_label: float
    font_size_legend: float
    legend_columnspacing: float
    x_nbins: int


SIX_PANEL_STYLE = FigureStyle(
    figsize=FIGSIZE,
    grow_for_legend=False,
    font_size_axis_label=FONT_SIZE_AXIS_LABEL,
    font_size_tick_label=FONT_SIZE_TICK_LABEL,
    font_size_subplot_label=FONT_SIZE_SUBPLOT_LABEL,
    font_size_legend=FONT_SIZE_LEGEND,
    legend_columnspacing=LEGEND_COLUMNSPACING,
    x_nbins=10,                  # MaxNLocator default
)


def _subset_style(n_rows: int, n_cols: int) -> FigureStyle:
    """Style of a figure with fewer panels: same width, larger fonts."""
    return FigureStyle(
        figsize=(FIGSIZE[0], n_rows * SUBSET_ROW_HEIGHT),
        grow_for_legend=True,
        font_size_axis_label=SUBSET_FONT_SIZE_AXIS_LABEL,
        font_size_tick_label=SUBSET_FONT_SIZE_TICK_LABEL,
        font_size_subplot_label=SUBSET_FONT_SIZE_SUBPLOT_LABEL,
        font_size_legend=SUBSET_FONT_SIZE_LEGEND,
        legend_columnspacing=SUBSET_LEGEND_COLUMNSPACING,
        x_nbins=max(3, min(10, int(FIGSIZE[0] / n_cols / SUBSET_X_TICK_SPACING))),
    )


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

# --panels keys, in the order of METRICS. fp: collateral edits, fn: omissions.
PANEL_KEYS = {
    "em":      "ExactMatch",
    "f1":      "F1Micro",
    "latency": "Latency",
    "tokens":  "TotalTokens",
    "fp":      "CollateralRate",
    "fn":      "OmissionRate",
}
DEFAULT_LAYOUT = (2, 3)


def _default_layout(n_panels: int) -> tuple[int, int]:
    """One row up to three panels, otherwise two rows (six panels: 2 x 3)."""
    if n_panels <= 3:
        return 1, n_panels
    return 2, math.ceil(n_panels / 2)


_HIGH_CONTRAST_COLORS = [
    "#1f77b4", "#d62728", "#2ca02c", "#ff7f0e",
    "#9467bd", "#8c564b", "#e377c2", "#17becf",
    "#bcbd22", "#7f7f7f",
]

# Approach → line style
_APPROACH_STYLE: Dict[str, dict] = {
    "planner_executor": dict(linestyle="-",  marker="o", label="P-E"),
    "vanilla":          dict(linestyle="--", marker="s", label="Single-pass baseline"),
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
# Legend (below the subplots)
# ══════════════════════════════════════════════════════════════════════════════

def _attach_legends(
    fig: plt.Figure,
    models: List[str],
    approaches: List[str],
    colors: Dict[str, str],
    model_labels: Dict[str, str],
    include_c_star: bool = False,
    fontsize: float = FONT_SIZE_LEGEND,
    columnspacing: float = LEGEND_COLUMNSPACING,
) -> float:
    """
    Build the legend at the bottom of the figure and return its height in inches.
    Models come first (colour patches), then the line style of each approach.
    If include_c_star is True, two additional entries are appended: the per-LLM
    C*_low triangle and the saturation band.
    """
    model_handles = [
        mpatches.Patch(color=colors[m], label=model_labels.get(m, m))
        for m in models
    ]
    approach_handles = [
        mlines.Line2D(
            [], [],
            color=LINE_STYLE_COLOR,
            linestyle=style["linestyle"],
            marker=style["marker"],
            linewidth=LINE_WIDTH,
            markersize=LINE_STYLE_MARKER_SIZE,
            label=style["label"],
        )
        for style in (_APPROACH_STYLE.get(a, _DEFAULT_APPROACH_STYLE) for a in approaches)
    ]

    handles = model_handles + approach_handles

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
                label=r"$C^{*}_{\mathrm{low}}$ per LLM",
            ),
            mpatches.Patch(
                color=C_STAR_BAND_COLOR,
                alpha=2 * C_STAR_BAND_ALPHA,
                label=r"$C^{*}$ zone " f"({band_lo}–{band_hi})",
            ),
        ]
        handles.extend(c_star_handles)

    # One column per pair of entries (two rows). If that is wider than the
    # panels, the last pair moves to a third row of its own.
    pairs = [handles[i:i + 2] for i in range(0, len(handles), 2)]
    layouts = [pairs]
    if len(pairs) > 2:
        last, blank = pairs[-1], mlines.Line2D([], [], linestyle="none", label="")
        layouts.append([
            pair + [last[i] if i < len(last) else blank]
            for i, pair in enumerate(pairs[:-1])
        ])

    renderer = fig.canvas.get_renderer()
    for columns in layouts:
        entries = [h for column in columns for h in column]
        legend = fig.legend(
            entries,
            [h.get_label() for h in entries],
            loc="lower center",
            ncol=len(columns),
            frameon=True,
            framealpha=0.97,
            edgecolor="#444444",
            fontsize=fontsize,
            handlelength=3.0,
            handletextpad=LEGEND_HANDLETEXTPAD,
            columnspacing=columnspacing,
            borderpad=LEGEND_BORDERPAD,
            bbox_to_anchor=LEGEND_BBOX,
        )
        extent = legend.get_window_extent(renderer)
        if extent.width <= LEGEND_MAX_WIDTH * fig.bbox.width or columns is layouts[-1]:
            return extent.height / fig.dpi
        legend.remove()


# ══════════════════════════════════════════════════════════════════════════════
# Main plot function
# ══════════════════════════════════════════════════════════════════════════════

def plot_multi_model_uq(
    df: pd.DataFrame,
    models: List[str],
    axis: str,
    out_path: Path,
    model_labels: Dict[str, str] | None = None,
    panels: List[str] | None = None,
    layout: tuple[int, int] | None = None,
) -> None:
    """
    panels: ordered PANEL_KEYS to draw (default: the six, in METRICS order).
    layout: (rows, cols) of the grid (default: _default_layout of the panels).
    The default panels and layout give the six-panel _v2 figure.
    """
    if model_labels is None:
        model_labels = {m: m for m in models}
    if panels is None:
        panels = list(PANEL_KEYS)
    if layout is None:
        layout = _default_layout(len(panels))
    n_rows, n_cols = layout
    if n_rows * n_cols < len(panels):
        raise ValueError(f"Layout {n_rows}x{n_cols} has fewer cells than the {len(panels)} panels.")

    metric_by_key = {m[0]: m for m in METRICS}
    metrics = [metric_by_key[PANEL_KEYS[p]] for p in panels]

    approaches = sorted(df["Approach"].unique().tolist())
    colors     = _palette(models)
    include_c_star = axis == "complexity"

    if list(panels) == list(PANEL_KEYS) and tuple(layout) == DEFAULT_LAYOUT:
        fig_style = SIX_PANEL_STYLE
    else:
        fig_style = _subset_style(n_rows, n_cols)

    x_label = "Complexity (C)" if axis == "complexity" else "Completeness (K)"

    fig, axes = plt.subplots(n_rows, n_cols, figsize=fig_style.figsize, squeeze=False)
    flat_axes = axes.flatten()
    for ax in flat_axes[len(metrics):]:
        ax.remove()

    for ax, (metric_key, title, y_label) in zip(flat_axes, metrics):
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

        ax.set_xlabel(x_label, fontsize=fig_style.font_size_axis_label)
        ax.set_ylabel(y_label, fontsize=fig_style.font_size_axis_label)
        ax.xaxis.set_major_locator(MaxNLocator(nbins=fig_style.x_nbins, integer=True))
        ax.xaxis.set_major_formatter(StrMethodFormatter("{x:.0f}"))
        ax.grid(True, linestyle="--", alpha=0.35)
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(axis="both", which="major", labelsize=fig_style.font_size_tick_label)
        ax.set_ylim(y_lo, y_hi)

        if include_c_star:
            x_all_for_ax = df["Level"].to_numpy()
            _draw_c_star_markers(ax, x_all_for_ax, colors)

    # Add centered subplot labels (a, b, c, ...) in the order of the panels.
    subplot_labels = [f"({chr(ord('a') + i)})" for i in range(len(metrics))]
    for ax, label in zip(flat_axes, subplot_labels):
        ax.text(
            0.5, 1.02,
            label,
            transform=ax.transAxes,
            fontsize=fig_style.font_size_subplot_label,
            fontweight='bold',
            va='bottom', ha='center'
        )

    legend_height = _attach_legends(
        fig, models, approaches, colors, model_labels,
        include_c_star=include_c_star,
        fontsize=fig_style.font_size_legend,
        columnspacing=fig_style.legend_columnspacing,
    )

    # Panels above the legend: grow the figure for it, or reserve its height.
    width, height = fig_style.figsize
    if fig_style.grow_for_legend:
        fig.set_size_inches(width, height + legend_height + LEGEND_GAP)
    bottom = LEGEND_BBOX[1] + (legend_height + LEGEND_GAP) / fig.get_figheight()
    plt.tight_layout(rect=(0, bottom, 1, TIGHT_LAYOUT_TOP))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"✓ Saved figure: {out_path}")


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def _parse_layout(value: str) -> tuple[int, int]:
    """'1x3' -> (1, 3)."""
    try:
        rows, cols = (int(v) for v in value.lower().split("x"))
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected ROWSxCOLS, e.g. 1x3 or 2x2, got {value!r}")
    if rows < 1 or cols < 1:
        raise argparse.ArgumentTypeError(f"rows and columns must be positive, got {value!r}")
    return rows, cols


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
    parser.add_argument("--panels",       nargs="+", choices=list(PANEL_KEYS), default=None,
                        help="Ordered metrics to draw (default: em f1 latency tokens fp fn). "
                             "fp is the collateral rate and fn the omission rate.")
    parser.add_argument("--layout",       type=_parse_layout, default=None,
                        help="Grid as ROWSxCOLS, e.g. 1x3 or 2x2 (default: 2x3 for the six "
                             "panels, one row up to three, otherwise two rows).")
    args = parser.parse_args()

    if args.panels and len(set(args.panels)) != len(args.panels):
        parser.error("--panels must not repeat a metric.")
    panels = args.panels or list(PANEL_KEYS)
    layout = args.layout or _default_layout(len(panels))
    if layout[0] * layout[1] < len(panels):
        parser.error(f"--layout {layout[0]}x{layout[1]} has fewer cells than the {len(panels)} panels.")
    if (args.panels or args.layout) and not args.output:
        parser.error("--output is required with --panels or --layout, "
                     "so that the six-panel _v2 figure is not overwritten.")

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
                        model_labels=model_labels, panels=panels, layout=layout)


if __name__ == "__main__":
    main()