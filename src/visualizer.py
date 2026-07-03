"""Matplotlib-only visual dashboard for completed race analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # Keep CLI execution reliable on machines without a display.
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.data_cleaning import add_clean_lap_flag, get_clean_laps


COMPOUND_COLOURS = {"S": "#E10600", "M": "#FFD12E", "H": "#F0F0F0", "I": "#00D7C1", "W": "#4AA3FF"}
BACKGROUND = "#101218"
PANEL = "#1A1F2B"
TEXT = "#E8EDF5"
GRID = "#4A5263"


def _style_axis(axis: plt.Axes, title: str, x_label: str = "") -> None:
    axis.set_facecolor(PANEL)
    axis.set_title(title, color=TEXT, fontsize=15, fontweight="bold", pad=14)
    axis.set_xlabel(x_label, color=TEXT)
    axis.tick_params(colors=TEXT, labelsize=9)
    axis.grid(axis="x", color=GRID, alpha=0.35, linewidth=0.7)
    for spine in axis.spines.values():
        spine.set_color(GRID)


def _save(figure: plt.Figure, path: Path) -> Path:
    figure.patch.set_facecolor(BACKGROUND)
    figure.tight_layout()
    figure.savefig(path, dpi=160, facecolor=figure.get_facecolor(), bbox_inches="tight")
    plt.close(figure)
    return path


def _driver_colours(results: dict[str, dict[str, Any]]) -> dict[str, str]:
    return {code: item["team_colour"] for code, item in results.items()}


def plot_pace_ranking(summary: pd.DataFrame, results: dict[str, dict[str, Any]], output_dir: Path) -> Path:
    """Plot full-grid average clean pace; lower is faster."""
    frame = summary.sort_values("average_clean_pace", ascending=False)
    figure, axis = plt.subplots(figsize=(11, 8))
    axis.barh(frame["driver_code"], frame["average_clean_pace"], color=[results[code]["team_colour"] for code in frame["driver_code"]])
    _style_axis(axis, "Full-Grid Race Pace Ranking", "Average clean lap pace (seconds; lower is faster)")
    return _save(figure, output_dir / "full_grid_pace_ranking.png")


def plot_consistency_ranking(summary: pd.DataFrame, results: dict[str, dict[str, Any]], output_dir: Path) -> Path:
    """Plot the full-grid consistency leaderboard."""
    frame = summary.sort_values("consistency_score")
    figure, axis = plt.subplots(figsize=(11, 8))
    axis.barh(frame["driver_code"], frame["consistency_score"], color=[results[code]["team_colour"] for code in frame["driver_code"]])
    _style_axis(axis, "Full-Grid Consistency Ranking", "Consistency score / 100")
    axis.set_xlim(0, 105)
    return _save(figure, output_dir / "full_grid_consistency_ranking.png")


def plot_tyre_management_ranking(summary: pd.DataFrame, results: dict[str, dict[str, Any]], output_dir: Path) -> Path:
    """Plot the full-grid tyre-management leaderboard."""
    frame = summary.sort_values("tyre_management_score")
    figure, axis = plt.subplots(figsize=(11, 8))
    axis.barh(frame["driver_code"], frame["tyre_management_score"], color=[results[code]["team_colour"] for code in frame["driver_code"]])
    _style_axis(axis, "Full-Grid Tyre Management Ranking", "Tyre management score / 100")
    axis.set_xlim(0, 105)
    return _save(figure, output_dir / "full_grid_tyre_management_ranking.png")


def plot_team_pace(summary: pd.DataFrame, results: dict[str, dict[str, Any]], output_dir: Path) -> Path:
    """Compare 11 teams using the mean clean pace of their two drivers."""
    frame = summary.groupby("team", as_index=False)["average_clean_pace"].mean().sort_values("average_clean_pace", ascending=False)
    team_colours = {item["team"]: item["team_colour"] for item in results.values()}
    figure, axis = plt.subplots(figsize=(11, 6.5))
    axis.barh(frame["team"], frame["average_clean_pace"], color=[team_colours[team] for team in frame["team"]])
    _style_axis(axis, "Team Pace Comparison", "Mean clean lap pace (seconds; lower is faster)")
    return _save(figure, output_dir / "team_pace_comparison.png")


def plot_driver_battle(race_laps: pd.DataFrame, comparison: dict[str, Any], output_dir: Path) -> Path:
    """Plot clean-lap pace traces for any two selected drivers."""
    first, second = comparison["driver_a"], comparison["driver_b"]
    figure, axis = plt.subplots(figsize=(12, 6))
    for result in (first, second):
        laps = get_clean_laps(race_laps.loc[race_laps["driver_code"] == result["driver_code"]])
        axis.plot(laps["lap_number"], laps["lap_time_sec"], marker="o", markersize=2.8, linewidth=1.4, label=result["driver_code"], color=result["team_colour"])
    _style_axis(axis, f"Driver Battle: {first['driver_code']} vs {second['driver_code']}", "Lap number")
    axis.set_ylabel("Clean lap time (seconds)", color=TEXT)
    axis.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT)
    return _save(figure, output_dir / f"driver_battle_{first['driver_code']}_vs_{second['driver_code']}.png")


def plot_strategy_timeline(race_laps: pd.DataFrame, results: dict[str, dict[str, Any]], output_dir: Path) -> Path:
    """Show tyre-compound blocks for every driver throughout the race."""
    order = sorted(results, key=lambda code: results[code]["final_position"], reverse=True)
    figure, axis = plt.subplots(figsize=(14, 9))
    for row_index, code in enumerate(order):
        driver_laps = race_laps.loc[race_laps["driver_code"] == code]
        for _, stint in driver_laps.groupby("stint", sort=True):
            start = int(stint["lap_number"].min())
            end = int(stint["lap_number"].max())
            compound = str(stint["compound"].iloc[0])
            axis.barh(row_index, end - start + 1, left=start - 1, height=0.72, color=COMPOUND_COLOURS[compound], edgecolor=BACKGROUND)
        pit_laps = driver_laps.loc[driver_laps["is_pit_lap"], "lap_number"]
        axis.scatter(pit_laps - 0.5, [row_index] * len(pit_laps), marker="|", color="#00E5FF", s=180, zorder=3)
    axis.set_yticks(range(len(order)), [f"{code}  P{results[code]['final_position']}" for code in order])
    _style_axis(axis, "Strategy Timeline — Tyre Compounds and Pit Stops", "Race lap")
    axis.set_ylabel("Driver / final position", color=TEXT)
    legend_handles = [plt.Rectangle((0, 0), 1, 1, color=colour, label=compound) for compound, colour in COMPOUND_COLOURS.items()]
    legend_handles.append(plt.Line2D([], [], color="#00E5FF", marker="|", linestyle="", markersize=12, label="Pit lap"))
    axis.legend(handles=legend_handles, loc="lower right", facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, ncol=4)
    return _save(figure, output_dir / "full_grid_strategy_timeline.png")


def plot_pace_heatmap(race_laps: pd.DataFrame, results: dict[str, dict[str, Any]], output_dir: Path) -> Path:
    """Visualise each driver's relative lap pace across the completed race."""
    annotated = add_clean_lap_flag(race_laps)
    order = sorted(results, key=lambda code: results[code]["final_position"])
    total_laps = int(race_laps["total_laps"].max())
    matrix: list[np.ndarray] = []
    for code in order:
        driver = annotated.loc[annotated["driver_code"] == code].sort_values("lap_number")
        values = np.full(total_laps, np.nan, dtype=float)
        clean = driver.loc[driver["is_clean_lap"]]
        clean_median = clean["lap_time_sec"].median()
        for _, row in clean.iterrows():
            lap_index = int(row["lap_number"]) - 1
            if 0 <= lap_index < total_laps:
                values[lap_index] = float(row["lap_time_sec"]) - float(clean_median)
        matrix.append(values)
    data = np.ma.masked_invalid(np.asarray(matrix, dtype=float))
    figure, axis = plt.subplots(figsize=(14, 8))
    cmap = plt.colormaps["coolwarm"].copy()
    cmap.set_bad("#252A35")
    image = axis.imshow(data, aspect="auto", interpolation="nearest", cmap=cmap, vmin=-1.0, vmax=1.0)
    axis.set_yticks(range(len(order)), [f"{code}  P{results[code]['final_position']}" for code in order])
    _style_axis(axis, "Race Pace Heatmap", "Lap number (grey = excluded non-clean lap)")
    axis.set_ylabel("Driver / final position", color=TEXT)
    colourbar = figure.colorbar(image, ax=axis, pad=0.015)
    colourbar.set_label("Relative clean lap pace (seconds)", color=TEXT)
    colourbar.ax.tick_params(colors=TEXT)
    return _save(figure, output_dir / "race_pace_heatmap.png")


def plot_tyre_degradation(tyre_fit: dict[str, Any] | None, output_dir: Path) -> Path | None:
    """Plot actual clean laps and its fitted SciPy quadratic model."""
    if tyre_fit is None:
        return None
    ages = np.asarray(tyre_fit["tyre_age"], dtype=float)
    actual = np.asarray(tyre_fit["actual_lap_times"], dtype=float)
    predicted = np.asarray(tyre_fit["predicted_lap_times"], dtype=float)
    order = np.argsort(ages)
    figure, axis = plt.subplots(figsize=(10, 6))
    axis.scatter(ages, actual, color="#FFD12E", edgecolor="#111111", linewidth=0.5, label="Actual clean laps", zorder=3)
    axis.plot(ages[order], predicted[order], color="#00E5FF", linewidth=2.5, label="Quadratic degradation fit")
    _style_axis(axis, f"Tyre Degradation: {tyre_fit['driver_code']} on {tyre_fit['compound']}", "Tyre age (laps)")
    axis.set_ylabel("Lap time (seconds)", color=TEXT)
    axis.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT)
    axis.text(0.02, 0.96, f"RMSE: {tyre_fit['rmse']:.3f}s\n{tyre_fit['interpretation']}", transform=axis.transAxes, va="top", color=TEXT, fontsize=9, bbox={"facecolor": BACKGROUND, "edgecolor": GRID, "alpha": 0.85, "pad": 7})
    return _save(figure, output_dir / f"tyre_degradation_{tyre_fit['driver_code']}_{tyre_fit['compound']}.png")


def generate_dashboard(
    summary: pd.DataFrame,
    results: dict[str, dict[str, Any]],
    race_laps: pd.DataFrame,
    comparison: dict[str, Any],
    tyre_fit: dict[str, Any] | None,
    output_dir: Path,
) -> list[Path]:
    """Generate the Version 4 static dashboard and return saved plot paths."""
    output_dir.mkdir(parents=True, exist_ok=True)
    plots: list[Path | None] = [
        plot_pace_ranking(summary, results, output_dir),
        plot_consistency_ranking(summary, results, output_dir),
        plot_tyre_management_ranking(summary, results, output_dir),
        plot_team_pace(summary, results, output_dir),
        plot_driver_battle(race_laps, comparison, output_dir),
        plot_strategy_timeline(race_laps, results, output_dir),
        plot_pace_heatmap(race_laps, results, output_dir),
        plot_tyre_degradation(tyre_fit, output_dir),
    ]
    return [path for path in plots if path is not None]
