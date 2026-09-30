"""Per-backend output-budget saturation markers for complexity-axis figures.

C* depends on the tokenizer, so it is given per backend in its own tokens.
benchmarks/metrics/c_star_by_backend.py derives the values below, without
new inference:

- L: cl100k length of json_gt serialized compactly (token_len in
  benchmarks/metrics/budget_complexity.py).
- r_b: median of completion tokens / L over the vanilla calls of the
  complexity axis with exact match, whose output is json_gt. Claude 1.443,
  Llama 1.282, GPT-5.4 1.005.
- m_b: median of completion tokens - L over the same calls. gpt-oss spends
  296 tokens on reasoning on top of the JSON, so its length is L + m_b.
- C*_low, C*_mean, C*_high: first level of the 2900-line complexity dataset
  whose maximum, mean or median length reaches the 4096-token budget
  (compute_c_star in budget_complexity.py).

| Backend | C*_low | C*_mean | C*_high |
|---|---|---|---|
| Claude Sonnet 4.6 (x 1.443) | 34 | 47 | 47 |
| Llama 3.1 8B (x 1.282) | 38 | 70 | 80 |
| gpt-oss:20b (+ 296) | 45 | 90 | 100 |
| GPT-5.4 (x 1.005) | 48 | 90 | 115 |

GPT-5.4's C*_low is 49 with r_b rounded to 1.00, the cl100k threshold. gpt-oss
gives 44-46 for 200-400 reasoning tokens.

The band is the union of the per-backend C*_low..C*_high intervals, from
Claude's C*_low (34) to GPT-5.4's C*_high (115).
"""

from __future__ import annotations

import numpy as np
from matplotlib.transforms import offset_copy

from benchmarks.comparisons.traceability import normalize_model_slug


C_STAR_LOW_BY_MODEL = {
    "claude-sonnet-4-6": 34,
    "llama3.1_latest":   38,
    "gpt-oss_20b":       45,
    "gpt-5.4":           48,
}
C_STAR_BAND = (34, 115)

C_STAR_MARKER = "v"
C_STAR_MARKER_SIZE = 12
C_STAR_MARKER_EDGE = "#222222"
C_STAR_STACK_GAP = 6             # triangles closer than this (in C) are stacked

C_STAR_BAND_COLOR = "#ffb84d"    # amber, clearly visible on white


def c_star_low(model: str) -> int | None:
    """C*_low of a backend, or None when it has no marker."""
    return C_STAR_LOW_BY_MODEL.get(normalize_model_slug(model))


def draw_c_star_markers(
    ax,
    x_values: np.ndarray,
    markers: list[tuple[float, str]],
    band_alpha: float,
) -> None:
    """
    Shade the saturation band on a complexity-axis subplot and draw one
    triangle per (C*_low, colour) on the top edge, stacking the ones that
    would overlap.
    """
    if x_values.size == 0:
        return

    x_min, x_max = float(np.min(x_values)), float(np.max(x_values))

    band_lo, band_hi = C_STAR_BAND
    if band_lo <= x_max and band_hi >= x_min:
        ax.axvspan(
            max(band_lo, x_min),
            min(band_hi, x_max),
            color=C_STAR_BAND_COLOR,
            alpha=band_alpha,
            zorder=0,
        )

    placed: list[float] = []
    for c_val, color in sorted(markers, key=lambda m: m[0]):
        if not x_min <= c_val <= x_max:
            continue
        stack = sum(abs(c_val - p) < C_STAR_STACK_GAP for p in placed)
        placed.append(c_val)
        ax.plot(
            c_val, 1.0,
            linestyle="none",
            marker=C_STAR_MARKER,
            markersize=C_STAR_MARKER_SIZE,
            color=color,
            markeredgecolor=C_STAR_MARKER_EDGE,
            transform=offset_copy(
                ax.get_xaxis_transform(), fig=ax.figure,
                y=stack * C_STAR_MARKER_SIZE, units="points",
            ),
            clip_on=False,
            zorder=5,
        )
