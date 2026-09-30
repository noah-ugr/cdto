
import pandas as pd
import matplotlib

# Force a non-interactive backend to keep plotting thread-safe in headless/parallel contexts.
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib as mpl
from pathlib import Path
import numpy as np
import string
from typing import List, Optional, Dict, Any, Tuple, Callable

# ---------------------------------------------------------
# Global font: Times New Roman + larger base font sizes
# ---------------------------------------------------------
mpl.rcParams["font.family"] = "serif"
mpl.rcParams["font.serif"] = ["Times New Roman"]

mpl.rcParams["font.size"] = 16
mpl.rcParams["axes.titlesize"] = 18
mpl.rcParams["axes.labelsize"] = 16
mpl.rcParams["xtick.labelsize"] = 15
mpl.rcParams["ytick.labelsize"] = 15
mpl.rcParams["legend.fontsize"] = 15


# ---------------------------------------------------------
# Helper: safely convert a cell to float or NaN
# ---------------------------------------------------------
def safe_float(val):
    if pd.isna(val):
        return np.nan
    if isinstance(val, str) and not val.strip():
        return np.nan
    try:
        return float(val)
    except (TypeError, ValueError):
        return np.nan


def _merge_intervals(intervals: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """Merge overlapping or touching [start, end] intervals."""
    if not intervals:
        return []

    sorted_intervals = sorted(intervals, key=lambda x: x[0])
    merged = [sorted_intervals[0]]

    for start, end in sorted_intervals[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))

    return merged


def _build_time_warp(
    starts: np.ndarray,
    ends: np.ndarray,
    idle_gap_scale: float = 0.05,
    min_gap_to_condense: float = 0.0,
) -> Callable[[float], float]:
    """
    Build a piecewise-linear mapping for time compression.

    - Task-active intervals keep scale 1.0 (durations preserved).
    - Idle gaps are scaled by `idle_gap_scale` (0.0 removes gaps, 0.05 keeps 5%).
    """
    if len(starts) == 0:
        return lambda t: t

    idle_gap_scale = float(np.clip(idle_gap_scale, 0.0, 1.0))
    valid_intervals = [(float(s), float(e)) for s, e in zip(starts, ends) if e >= s]
    merged = _merge_intervals(valid_intervals)

    if len(merged) <= 1 and idle_gap_scale >= 1.0:
        return lambda t: t

    compressed_starts = []
    compressed_ends = []

    compressed_cursor = merged[0][0]
    prev_end = merged[0][0]

    for start, end in merged:
        gap = start - prev_end
        if gap > 0:
            gap_scale = idle_gap_scale if gap >= min_gap_to_condense else 1.0
            compressed_cursor += gap * gap_scale

        comp_start = compressed_cursor
        comp_end = comp_start + (end - start)

        compressed_starts.append(comp_start)
        compressed_ends.append(comp_end)

        compressed_cursor = comp_end
        prev_end = end

    def transform(t: float) -> float:
        t = float(t)

        if t <= merged[0][0]:
            return t

        for i, (start, end) in enumerate(merged):
            comp_start = compressed_starts[i]
            comp_end = compressed_ends[i]

            if start <= t <= end:
                return comp_start + (t - start)

            if i < len(merged) - 1:
                next_start = merged[i + 1][0]
                if end < t < next_start:
                    gap = next_start - end
                    gap_scale = idle_gap_scale if gap >= min_gap_to_condense else 1.0
                    return comp_end + (t - end) * gap_scale

        last_end = merged[-1][1]
        last_comp_end = compressed_ends[-1]
        return last_comp_end + (t - last_end) * idle_gap_scale

    return transform


# ---------------------------------------------------------
# Helper to plot one activity as Gantt + table
# ---------------------------------------------------------
def plot_activity_gantt(
    act_df,
    activity_name,
    output_path,
    show_plot: bool = False,
    condense_idle_gaps: bool = True,
    idle_gap_scale: float = 0.05,
    min_gap_to_condense: float = 0.0,
):
    """
    Plots a Gantt chart for a single activity.
    
    Args:
        act_df: DataFrame with activity task data
        activity_name: Name of the activity
        output_path: Path where to save the chart
        show_plot: Whether to display the plot
        condense_idle_gaps: Compress idle time gaps between executed tasks
        idle_gap_scale: Fraction of each idle gap to keep (0.0 remove, 1.0 no compression)
        min_gap_to_condense: Minimum gap size required to apply compression
    
    Returns:
        Path to saved chart, or None if no data to plot
    """
    # columns like t0007..._Start
    start_cols = [
        c for c in act_df.columns
        if c.endswith("_Start") and c != "Activity_Start"
    ]

    gantt_rows = []

    for _, row in act_df.iterrows():
        exec_no = (
            int(row["Execution"])
            if "Execution" in row and not pd.isna(row["Execution"])
            else None
        )

        for sc in start_cols:
            base = sc[:-6]  # remove "_Start"
            ec = base + "_End"

            start_raw = row.get(sc)
            end_raw = row.get(ec)

            start = safe_float(start_raw)
            end = safe_float(end_raw)

            # skip if either is missing / blank / non-numeric
            if pd.isna(start) or pd.isna(end):
                continue

            duration = end - start

            gantt_rows.append(
                {
                    "transition": base,
                    "execution": exec_no if exec_no is not None else -1,
                    "start": start,
                    "end": end,
                    "duration": duration,
                }
            )

    if not gantt_rows:
        print(f"⚠️ No valid start/end durations to plot for {activity_name}")
        return None

    gantt_df = (
        pd.DataFrame(gantt_rows)
        .sort_values("start")
        .reset_index(drop=True)
    )

    # letters a, b, c, ...
    letters = []
    for i in range(len(gantt_df)):
        if i < 26:
            letters.append(string.ascii_lowercase[i])
        else:
            letters.append(string.ascii_lowercase[i % 26] + str(i // 26))
    gantt_df["bar_letter"] = letters

    y_positions = np.arange(len(gantt_df))

    if condense_idle_gaps:
        time_warp = _build_time_warp(
            gantt_df["start"].to_numpy(),
            gantt_df["end"].to_numpy(),
            idle_gap_scale=idle_gap_scale,
            min_gap_to_condense=min_gap_to_condense,
        )
        gantt_df["plot_start"] = gantt_df["start"].map(time_warp)
        gantt_df["plot_end"] = gantt_df["end"].map(time_warp)
        gantt_df["plot_duration"] = gantt_df["plot_end"] - gantt_df["plot_start"]
    else:
        gantt_df["plot_start"] = gantt_df["start"]
        gantt_df["plot_end"] = gantt_df["end"]
        gantt_df["plot_duration"] = gantt_df["duration"]

    starts = gantt_df["plot_start"].values
    durations = gantt_df["plot_duration"].values

    # Calculate dynamic figure size based on number of tasks
    n_tasks = len(gantt_df)
    
    # Fixed width, dynamic height (like plot_delta_uq.py style)
    fig_width = 14
    # Allocate ~0.35 inches per task for the Gantt chart, min 5, max 10
    gantt_height = np.clip(n_tasks * 0.35, 5, 10)
    # Fixed table height
    table_height = 2.5
    fig_height = gantt_height + table_height
    
    fig, (ax_plot, ax_table) = plt.subplots(
        2, 1,
        figsize=(fig_width, fig_height),
        gridspec_kw={"height_ratios": [gantt_height, table_height]}
    )
    # Format like plot_delta_uq.py: tight_layout with reserved space
    plt.subplots_adjust(hspace=0.08)

    # ----------------- Gantt plot -----------------
    ax_plot.barh(y_positions, durations, left=starts, align="center", color='steelblue', alpha=0.8)

    # Place labels in center of each bar using the PLOT coordinates (compressed if applicable)
    for i, row in gantt_df.iterrows():
        y = y_positions[i]
        # Use plot coordinates (already compressed if needed)
        x_center = row["plot_start"] + row["plot_duration"] / 2.0
        ax_plot.text(
            x_center, y, row["bar_letter"],
            va="center", ha="center", fontsize=15, fontweight='bold', color='white'
        )

    ax_plot.set_yticks(y_positions)
    ax_plot.set_yticklabels(gantt_df["bar_letter"].tolist())
    if condense_idle_gaps:
        ax_plot.set_xlabel(f"Time (idle gaps scaled ×{idle_gap_scale:.2f})", fontsize=16)
    else:
        ax_plot.set_xlabel("Time", fontsize=16)
    ax_plot.set_ylabel("Task", fontsize=16)
    # Grid: horizontal lines at task positions ONLY
    ax_plot.grid(True, axis="y", which='major', linestyle="-", alpha=0.35, linewidth=0.7, zorder=0)
    
    # Vertical grid lines: ONLY at task boundaries, not in gaps
    # Disable default x-grid and draw custom vertical lines at task intervals
    ax_plot.grid(False, axis="x")
    
    # Draw vertical lines only where tasks exist (at their start and end positions)
    for _, row in gantt_df.iterrows():
        x_start = row["plot_start"]
        x_end = row["plot_end"]
        # Vertical lines at task boundaries
        ax_plot.axvline(x_start, color='gray', linestyle="-", alpha=0.4, linewidth=0.8, zorder=0)
        ax_plot.axvline(x_end, color='gray', linestyle="-", alpha=0.4, linewidth=0.8, zorder=0)
    
    # Set x-axis limits to only show task range (exclude massive gaps if condensed)
    plot_min = gantt_df["plot_start"].min() * 0.98
    plot_max = gantt_df["plot_end"].max() * 1.02
    ax_plot.set_xlim(plot_min, plot_max)
    ax_plot.margins(y=0.02)

    if condense_idle_gaps:
        # Show only task boundary times: start and end of each bar.
        boundary_pairs = []
        for _, row in gantt_df.iterrows():
            boundary_pairs.append((float(row["plot_start"]), float(row["start"])))
            boundary_pairs.append((float(row["plot_end"]), float(row["end"])))

        boundary_pairs.sort(key=lambda item: item[0])

        plot_ticks = []
        tick_labels = []
        seen_ticks = set()
        for plot_x, orig_x in boundary_pairs:
            key = round(plot_x, 8)
            if key in seen_ticks:
                continue
            seen_ticks.add(key)
            plot_ticks.append(plot_x)
            tick_labels.append(f"{orig_x:.0f}" if abs(orig_x - round(orig_x)) < 1e-6 else f"{orig_x:.1f}")

        ax_plot.set_xticks(plot_ticks)
        ax_plot.set_xticklabels(tick_labels, rotation=0, fontsize=15)
    else:
        # Show only task boundary times here as well.
        boundary_pairs = []
        for _, row in gantt_df.iterrows():
            boundary_pairs.append((float(row["plot_start"]), float(row["start"])))
            boundary_pairs.append((float(row["plot_end"]), float(row["end"])))

        boundary_pairs.sort(key=lambda item: item[0])

        plot_ticks = []
        tick_labels = []
        seen_ticks = set()
        for plot_x, orig_x in boundary_pairs:
            key = round(plot_x, 8)
            if key in seen_ticks:
                continue
            seen_ticks.add(key)
            plot_ticks.append(plot_x)
            tick_labels.append(f"{orig_x:.0f}" if abs(orig_x - round(orig_x)) < 1e-6 else f"{orig_x:.1f}")

        ax_plot.set_xticks(plot_ticks)
        ax_plot.set_xticklabels(tick_labels, rotation=0, fontsize=15)

    # ----------------- Duration table -----------------
    ax_table.axis("off")

    table_data = [
        [
            row["bar_letter"],
            row["transition"],
            f"{row['start']:.1f}",
            f"{row['end']:.1f}",
            f"{row['duration']:.2f}",
        ]
        for _, row in gantt_df.iterrows()
    ]
    col_labels = ["Label", "Transition", "Start", "End", "Duration"]

    # Column widths (relative): more compact layout
    col_widths = [0.08, 0.35, 0.19, 0.19, 0.19]

    table = ax_table.table(
        cellText=table_data,
        colLabels=col_labels,
        loc="center",
        cellLoc="center",
        colWidths=col_widths
    )
    table.auto_set_font_size(False)
    table.set_fontsize(14)

    # Style header row
    for i in range(len(col_labels)):
        cell = table[(0, i)]
        cell.set_facecolor('#4472C4')  # professional blue
        cell.set_text_props(weight='bold', color='white', fontsize=14)
    
    # Alternate row colors for better readability
    for i in range(1, len(table_data) + 1):
        for j in range(len(col_labels)):
            cell = table[(i, j)]
            if i % 2 == 0:
                cell.set_facecolor('#E7E6E6')  # light gray
            else:
                cell.set_facecolor('#F2F2F2')  # lighter gray
            cell.set_text_props(fontsize=13)

    # Better scaling
    table.scale(0.85, 1.3)

    # Save with high DPI like plot_delta_uq.py for paper quality
    plt.tight_layout(rect=(0, 0.02, 1, 0.98))
    plt.savefig(output_path, dpi=160, bbox_inches="tight")

    pdf_output_path = Path(output_path).with_suffix(".pdf")
    plt.savefig(pdf_output_path, bbox_inches="tight")

    print(f"✅ Gantt chart saved to: {output_path}")
    print(f"✅ Gantt chart saved to: {pdf_output_path}")
    
    if show_plot:
        plt.show()
    else:
        plt.close()
    
    return output_path


def generate_gantt_charts(
    durations_path: str,
    output_dir: str = ".",
    show_plots: bool = False,
    condense_idle_gaps: bool = True,
    idle_gap_scale: float = 0.05,
    min_gap_to_condense: float = 0.0,
) -> List[str]:
    """
    Generates Gantt charts for all activities in the durations file.
    
    Args:
        durations_path: Path to the calculated_task_durations.xlsx file
        output_dir: Directory where to save the Gantt chart images
        show_plots: Whether to display plots interactively
        condense_idle_gaps: Compress idle time gaps in Gantt charts
        idle_gap_scale: Fraction of idle gap to keep (0.0 remove, 1.0 no compression)
        min_gap_to_condense: Minimum gap size required to compress
    
    Returns:
        List of paths to saved Gantt chart images
    """
    # ---------------------------------------------------------
    # Load durations workbook
    #   na_values forces blanks to become NaN
    # ---------------------------------------------------------
    dur_path = Path(durations_path)
    if not dur_path.exists():
        raise FileNotFoundError(f"Durations file not found: {durations_path}")
    
    dur_df = pd.read_excel(
        dur_path,
        sheet_name=0,
        na_values=["", " ", "  "]  # treat blanks/whitespace as NaN
    )

    print("📊 Durations columns:", dur_df.columns.tolist())
    print(dur_df.head())

    # All distinct activities present
    activities = sorted(dur_df["Activity"].astype(str).unique())
    print(f"🎯 Activities found: {activities}")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    generated_charts = []

    # ---------------------------------------------------------
    # Loop over ALL activities and plot each
    #   Blank cells are now safely skipped.
    # ---------------------------------------------------------
    for activity_to_plot in activities:
        act_df = dur_df[dur_df["Activity"].astype(str) == activity_to_plot].copy()
        
        output_path = output_dir / f"gantt_{activity_to_plot}.png"
        
        result = plot_activity_gantt(
            act_df,
            activity_to_plot,
            output_path,
            show_plot=show_plots,
            condense_idle_gaps=condense_idle_gaps,
            idle_gap_scale=idle_gap_scale,
            min_gap_to_condense=min_gap_to_condense,
        )
        
        if result:
            generated_charts.append(result)
    
    print(f"\n✅ Generated {len(generated_charts)} Gantt charts")
    return generated_charts


def get_gantt_summary(durations_path: str) -> Dict[str, Any]:
    """
    Extracts a summary of activities and their task counts.
    
    Args:
        durations_path: Path to the calculated_task_durations.xlsx file
    
    Returns:
        Dictionary with Gantt chart summary
    """
    dur_df = pd.read_excel(Path(durations_path), sheet_name=0, na_values=["", " ", "  "])
    
    activities = sorted(dur_df["Activity"].astype(str).unique())
    
    summary = {
        "total_activities": len(activities),
        "activities": activities,
        "task_counts": {}
    }
    
    for activity in activities:
        act_df = dur_df[dur_df["Activity"].astype(str) == activity]
        # Count non-empty start columns
        start_cols = [c for c in act_df.columns if c.endswith("_Start") and c != "Activity_Start"]
        task_count = 0
        for col in start_cols:
            if not act_df[col].isna().all():
                task_count += 1
        summary["task_counts"][activity] = task_count
    
    return summary


# For backward compatibility
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        path = "calculated_task_durations.xlsx"
    
    charts = generate_gantt_charts(path, show_plots=True)
    summary = get_gantt_summary(path)
    print("\n📋 Gantt Summary:")
    print(f"  - Total activities: {summary['total_activities']}")
    for act, count in summary['task_counts'].items():
        print(f"  - {act}: {count} tasks")
