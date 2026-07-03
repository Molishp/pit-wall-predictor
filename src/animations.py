"""Matplotlib-only replay animations with a safe static-image fallback.

Animations are exported as self-contained HTML files through Matplotlib's own
``HTMLWriter``.  That keeps the project free from external video writers and
Pillow.  If the local Matplotlib setup cannot save an animation, a final-frame
PNG is saved instead so the analysis remains useful.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import matplotlib

matplotlib.use("Agg")  # The CLI must work without a desktop display server.
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, HTMLWriter
import numpy as np
import pandas as pd


BACKGROUND = "#101218"
PANEL = "#1A1F2B"
TEXT = "#E8EDF5"
GRID = "#4A5263"
COMPOUND_COLOURS = {"S": "#E10600", "M": "#FFD12E", "H": "#F0F0F0", "I": "#00D7C1", "W": "#4AA3FF"}


@dataclass
class AnimationExport:
    """Outcome of an animation request, including fallback information."""

    name: str
    path: Path | None
    used_fallback: bool
    message: str


def _setup_axis(axis: plt.Axes, title: str, x_label: str, y_label: str = "") -> None:
    axis.set_facecolor(PANEL)
    axis.set_title(title, color=TEXT, fontsize=14, fontweight="bold", pad=12)
    axis.set_xlabel(x_label, color=TEXT)
    axis.set_ylabel(y_label, color=TEXT)
    axis.tick_params(colors=TEXT)
    axis.grid(axis="x", color=GRID, alpha=0.35, linewidth=0.7)
    for spine in axis.spines.values():
        spine.set_color(GRID)


def _save_animation_or_fallback(
    name: str,
    animation: FuncAnimation,
    figure: plt.Figure,
    html_path: Path,
    fallback_path: Path,
    draw_final_frame: Callable[[], None],
    fps: int = 8,
) -> AnimationExport:
    """Export portable HTML or save a static final frame when that fails."""
    try:
        # HTMLWriter is included with Matplotlib and does not need ffmpeg/Pillow.
        writer = HTMLWriter(fps=fps, embed_frames=True, default_mode="loop")
        animation.save(html_path, writer=writer, dpi=90)
        return AnimationExport(name, html_path, False, f"Saved HTML animation: {html_path.name}")
    except Exception as error:  # Keep a missing/broken writer from breaking the CLI.
        draw_final_frame()
        figure.savefig(fallback_path, dpi=150, facecolor=figure.get_facecolor(), bbox_inches="tight")
        return AnimationExport(
            name,
            fallback_path,
            True,
            f"Animation export failed ({error}). Saved static final frame: {fallback_path.name}",
        )
    finally:
        plt.close(figure)


def create_race_pace_replay(
    race_laps: pd.DataFrame, results: dict[str, dict[str, Any]], output_dir: Path
) -> AnimationExport:
    """Animate cars moving along lap progress using their cumulative race times."""
    ordered_codes = sorted(results, key=lambda code: results[code]["final_position"])
    total_laps = int(race_laps["total_laps"].iloc[0])
    prepared = race_laps.sort_values(["driver_code", "lap_number"]).copy()
    prepared["cumulative_time"] = prepared.groupby("driver_code")["lap_time_sec"].cumsum()
    cumulative_table = (
        prepared.pivot(index="lap_number", columns="driver_code", values="cumulative_time")
        .reindex(range(1, total_laps + 1))
        .ffill()
    )
    lap_time_table = (
        prepared.pivot(index="lap_number", columns="driver_code", values="lap_time_sec")
        .reindex(range(1, total_laps + 1))
        .ffill()
    )
    compound_table = (
        prepared.pivot(index="lap_number", columns="driver_code", values="compound")
        .reindex(range(1, total_laps + 1))
        .ffill()
    )

    figure, axis = plt.subplots(figsize=(13, 8))
    figure.patch.set_facecolor(BACKGROUND)
    _setup_axis(axis, "Race Pace Replay", "Race progress (laps)", "Final classification lane")
    lane_positions = np.arange(len(ordered_codes), 0, -1, dtype=float)
    axis.set_xlim(-0.5, total_laps + 1.8)
    axis.set_ylim(0.2, len(ordered_codes) + 0.8)
    axis.set_yticks(lane_positions, [f"P{results[code]['final_position']}" for code in ordered_codes])
    axis.set_axisbelow(True)
    scatter = axis.scatter([], [], marker=">", s=105, edgecolors="#05070A", linewidths=0.7, zorder=3)
    labels = [axis.text(0, lane, "", color=TEXT, fontsize=7.5, va="center", zorder=4) for lane in lane_positions]
    title = axis.title

    def draw_frame(lap: int) -> tuple[Any, ...]:
        frame = cumulative_table.loc[lap].reindex(ordered_codes)
        lap_times = lap_time_table.loc[lap].reindex(ordered_codes)
        compounds = compound_table.loc[lap].reindex(ordered_codes)
        leader_code = str(frame.idxmin())
        leader_time = float(frame.min())
        leader_lap_time = max(float(lap_times.loc[leader_code]), 1.0)
        gaps = frame.to_numpy(dtype=float) - leader_time
        # Time gaps turn into a fractional-lap distance: pit losses visibly push
        # a marker backwards, while the leader remains at the current race lap.
        progress = np.clip(lap - gaps / leader_lap_time, 0.0, float(total_laps))
        scatter.set_offsets(np.column_stack((progress, lane_positions)))
        scatter.set_color([results[code]["team_colour"] for code in ordered_codes])
        for index, code in enumerate(ordered_codes):
            labels[index].set_position((progress[index] + 0.35, lane_positions[index]))
            driver_number = int(results[code]["driver_number"])
            compound = str(compounds.loc[code]) if pd.notna(compounds.loc[code]) else ""
            labels[index].set_text(f"{code} #{driver_number} {compound}")
        title.set_text(f"Race Pace Replay — Lap {lap}/{total_laps}")
        return (scatter, *labels, title)

    animation = FuncAnimation(figure, draw_frame, frames=range(1, total_laps + 1), interval=125, blit=False)
    return _save_animation_or_fallback(
        "Race pace replay",
        animation,
        figure,
        output_dir / "race_pace_replay.html",
        output_dir / "race_pace_replay_final_frame.png",
        lambda: draw_frame(total_laps),
    )


def create_tyre_degradation_animation(tyre_fit: dict[str, Any] | None, output_dir: Path) -> AnimationExport:
    """Reveal clean tyre-age data and the fitted curve one observation at a time."""
    if tyre_fit is None:
        return AnimationExport(
            "Tyre degradation replay",
            None,
            False,
            "Skipped tyre degradation animation: insufficient clean same-compound laps for a fit.",
        )
    ages = np.asarray(tyre_fit["tyre_age"], dtype=float)
    actual = np.asarray(tyre_fit["actual_lap_times"], dtype=float)
    predicted = np.asarray(tyre_fit["predicted_lap_times"], dtype=float)
    order = np.argsort(ages)
    ages, actual, predicted = ages[order], actual[order], predicted[order]
    figure, axis = plt.subplots(figsize=(11, 6.5))
    figure.patch.set_facecolor(BACKGROUND)
    _setup_axis(axis, f"Tyre Degradation Replay: {tyre_fit['driver_code']} on {tyre_fit['compound']}", "Tyre age (laps)", "Lap time (seconds)")
    axis.set_xlim(max(0, ages.min() - 1), ages.max() + 1)
    margin = max(0.35, (actual.max() - actual.min()) * 0.15)
    axis.set_ylim(actual.min() - margin, actual.max() + margin)
    points = axis.scatter([], [], color="#FFD12E", edgecolor="#111111", linewidth=0.5, label="Actual clean laps", zorder=3)
    line, = axis.plot([], [], color="#00E5FF", linewidth=2.5, label="Quadratic degradation fit")
    note = axis.text(0.02, 0.96, "", transform=axis.transAxes, va="top", color=TEXT, fontsize=9, bbox={"facecolor": BACKGROUND, "edgecolor": GRID, "alpha": 0.85, "pad": 7})
    axis.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, loc="lower right")

    def draw_frame(frame: int) -> tuple[Any, ...]:
        count = max(1, frame)
        points.set_offsets(np.column_stack((ages[:count], actual[:count])))
        line.set_data(ages[:count], predicted[:count])
        note.set_text(f"Observation {count}/{len(ages)}\nRMSE: {tyre_fit['rmse']:.3f}s")
        return points, line, note

    animation = FuncAnimation(figure, draw_frame, frames=range(1, len(ages) + 1), interval=160, blit=False)
    return _save_animation_or_fallback(
        "Tyre degradation replay",
        animation,
        figure,
        output_dir / f"tyre_degradation_replay_{tyre_fit['driver_code']}_{tyre_fit['compound']}.html",
        output_dir / f"tyre_degradation_replay_{tyre_fit['driver_code']}_{tyre_fit['compound']}_final_frame.png",
        lambda: draw_frame(len(ages)),
        fps=6,
    )


def create_pit_stop_timeline_animation(
    race_laps: pd.DataFrame, results: dict[str, dict[str, Any]], output_dir: Path
) -> AnimationExport:
    """Fill every driver's tyre-strategy blocks lap by lap, highlighting pit laps."""
    ordered_codes = sorted(results, key=lambda code: results[code]["final_position"], reverse=True)
    total_laps = int(race_laps["total_laps"].iloc[0])
    figure, axis = plt.subplots(figsize=(14, 9))
    figure.patch.set_facecolor(BACKGROUND)
    _setup_axis(axis, "Pit Stop Timeline Replay", "Race lap", "Driver / final position")
    axis.set_xlim(0, total_laps + 1)
    axis.set_ylim(-0.8, len(ordered_codes) - 0.2)
    axis.set_yticks(range(len(ordered_codes)), [f"{code}  P{results[code]['final_position']}" for code in ordered_codes])
    axis.set_axisbelow(True)
    patches: list[tuple[Any, int, int]] = []
    pit_positions: list[tuple[float, int]] = []
    for row_index, code in enumerate(ordered_codes):
        driver_laps = race_laps.loc[race_laps["driver_code"] == code]
        for _, stint in driver_laps.groupby("stint", sort=True):
            start = int(stint["lap_number"].min())
            end = int(stint["lap_number"].max())
            compound = str(stint["compound"].iloc[0])
            patch = axis.barh(row_index, 0, left=start - 1, height=0.72, color=COMPOUND_COLOURS[compound], edgecolor=BACKGROUND)[0]
            patches.append((patch, start, end))
        pit_positions.extend((float(lap) - 0.5, row_index) for lap in driver_laps.loc[driver_laps["is_pit_lap"], "lap_number"])
    pit_markers = axis.scatter([], [], marker="|", color="#00E5FF", s=180, zorder=3, label="Pit lap")
    legend_handles = [plt.Rectangle((0, 0), 1, 1, color=colour, label=compound) for compound, colour in COMPOUND_COLOURS.items()]
    legend_handles.append(plt.Line2D([], [], color="#00E5FF", marker="|", linestyle="", markersize=12, label="Pit lap"))
    axis.legend(handles=legend_handles, loc="lower right", facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, ncol=4)
    title = axis.title

    def draw_frame(lap: int) -> tuple[Any, ...]:
        for patch, start, end in patches:
            visible_width = max(0, min(lap, end) - start + 1)
            patch.set_width(visible_width)
        visible_pits = [(x, y) for x, y in pit_positions if x + 0.5 <= lap]
        pit_markers.set_offsets(np.asarray(visible_pits) if visible_pits else np.empty((0, 2)))
        title.set_text(f"Pit Stop Timeline Replay — Lap {lap}/{total_laps}")
        return (*[item[0] for item in patches], pit_markers, title)

    animation = FuncAnimation(figure, draw_frame, frames=range(1, total_laps + 1), interval=125, blit=False)
    return _save_animation_or_fallback(
        "Pit stop timeline replay",
        animation,
        figure,
        output_dir / "pit_stop_timeline_replay.html",
        output_dir / "pit_stop_timeline_replay_final_frame.png",
        lambda: draw_frame(total_laps),
    )


def generate_animations(
    race_laps: pd.DataFrame,
    results: dict[str, dict[str, Any]],
    tyre_fit: dict[str, Any] | None,
    output_dir: Path,
) -> list[AnimationExport]:
    """Generate the three Version 5 replays, retaining useful fallbacks on failure."""
    output_dir.mkdir(parents=True, exist_ok=True)
    return [
        create_race_pace_replay(race_laps, results, output_dir),
        create_tyre_degradation_animation(tyre_fit, output_dir),
        create_pit_stop_timeline_animation(race_laps, results, output_dir),
    ]
