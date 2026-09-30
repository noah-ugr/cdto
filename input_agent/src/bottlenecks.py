# -*- coding: utf-8 -*-
"""
Created on Tue Feb 10 11:19:06 2026

@author: mhagh

Refactored by: Noah Masegosa Caceres (@ugr)
Description: Bottleneck analysis tool for Petri nets.
             Generates heatmap showing token accumulation over time.
"""

import pandas as pd
import numpy as np
import matplotlib

# Force a non-interactive backend to avoid Tk/Tkinter thread issues in parallel runs.
matplotlib.use("Agg")

import matplotlib.pyplot as plt
from pathlib import Path
from typing import Optional, Tuple, Dict, Any


def analyze_bottlenecks(
    trace_path: str,
    output_dir: str = ".",
    topN: int = 15,
    show_plot: bool = False
) -> Tuple[pd.DataFrame, str]:
    """
    Analyzes bottlenecks in a Petri net simulation trace.
    
    Args:
        trace_path: Path to the simulator output Excel file (e.g., Petrinet_A_simulator.xlsx)
        output_dir: Directory where to save the heatmap image
        topN: Number of top bottleneck places to show in heatmap
        show_plot: Whether to display the plot interactively
    
    Returns:
        Tuple containing:
        - DataFrame with bottleneck rankings
        - Path to the saved heatmap image
    """
    # === 1) Load your simulator output ===
    df = pd.read_excel(trace_path)

    # Basic checks
    if "time" not in df.columns:
        raise ValueError("Column 'time' not found in trace file.")
    
    place_cols = [c for c in df.columns if c not in ["time", "transitions"]]
    
    if not place_cols:
        raise ValueError("No place columns found in trace file.")

    # Sort by time just in case
    df = df.sort_values("time").reset_index(drop=True)

    # === 2) Time-weighted bottleneck score per place ===
    t = df["time"].to_numpy()

    # dt between rows (assume marking is constant over [t_i, t_{i+1}))
    dt = np.diff(t)
    if len(dt) == 0:
        raise ValueError("Not enough rows to compute dt. Need at least 2 logged steps.")

    total_time = dt.sum()
    if total_time <= 0:
        raise ValueError("Total simulated time is zero or negative. Check your time column.")

    scores = []
    for p in place_cols:
        m = df[p].to_numpy()

        # time-weighted average marking (WIP)
        wip = (m[:-1] * dt).sum() / total_time

        # percent of time marked (tokens > 0)
        pct_marked = ((m[:-1] > 0) * dt).sum() / total_time

        # maximum marking observed
        mmax = np.max(m)

        scores.append((p, wip, pct_marked, mmax))

    rank = pd.DataFrame(scores, columns=["place", "avg_tokens_WIP", "pct_time_marked", "max_tokens"])
    rank = rank.sort_values("avg_tokens_WIP", ascending=False).reset_index(drop=True)

    print("\n📊 Top bottleneck places by avg_tokens_WIP:\n")
    print(rank.head(topN))

    # === 3) Heatmap for top-N places ===
    top_places = rank["place"].head(topN).tolist()

    # Build heatmap matrix: rows = places, cols = time steps
    H = df[top_places].to_numpy().T  # shape: (topN, n_steps)

    plt.figure(figsize=(14, 5))
    plt.imshow(H, aspect="auto", cmap="YlOrRd")
    plt.yticks(range(len(top_places)), top_places, fontsize=10)
    plt.xticks([0, len(t)//2, len(t)-1], [f"{t[0]:.2f}", f"{t[len(t)//2]:.2f}", f"{t[-1]:.2f}"])
    plt.xlabel("Simulation step (time increases left→right)", fontsize=12)
    plt.ylabel("Places (top bottlenecks)", fontsize=12)
    plt.title("Petri Net Bottleneck Heatmap (tokens in places over time)", fontsize=14, fontweight='bold')
    plt.colorbar(label="Token count")
    plt.tight_layout()
    
    # Save heatmap
    output_path = Path(output_dir) / "bottleneck_heatmap.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"✅ Heatmap saved to: {output_path}")
    
    if show_plot:
        plt.show()
    else:
        plt.close()
    
    return rank, str(output_path)


def get_bottleneck_summary(rank_df: pd.DataFrame, topN: int = 10) -> Dict[str, Any]:
    """
    Extracts a summary dictionary from the bottleneck rankings.
    
    Args:
        rank_df: DataFrame with bottleneck rankings
        topN: Number of top bottlenecks to include
    
    Returns:
        Dictionary with bottleneck summary
    """
    top_bottlenecks = rank_df.head(topN)
    
    return {
        "top_bottlenecks": top_bottlenecks.to_dict(orient='records'),
        "total_places_analyzed": len(rank_df),
        "highest_wip_place": top_bottlenecks.iloc[0]["place"] if not top_bottlenecks.empty else None,
        "highest_wip_value": float(top_bottlenecks.iloc[0]["avg_tokens_WIP"]) if not top_bottlenecks.empty else 0.0
    }


# For backward compatibility
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        path = "Petrinet_A_simulator.xlsx"
    
    rank, heatmap_path = analyze_bottlenecks(path, show_plot=True)
    summary = get_bottleneck_summary(rank)
    print("\n📋 Bottleneck Summary:")
    print(f"  - Highest WIP place: {summary['highest_wip_place']}")
    print(f"  - WIP value: {summary['highest_wip_value']:.4f}")
