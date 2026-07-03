"""Single-driver and full-grid post-race calculations."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.data_cleaning import get_clean_laps
from src.scoring import apply_scores


def _stint_summary(driver_laps: pd.DataFrame, clean_laps: pd.DataFrame) -> list[dict[str, Any]]:
    """Summarise each tyre stint, including a simple linear degradation estimate."""
    stints: list[dict[str, Any]] = []
    for stint_number, stint_laps in driver_laps.groupby("stint", sort=True):
        clean_stint = clean_laps.loc[clean_laps["stint"] == stint_number]
        average = None if clean_stint.empty else round(float(clean_stint["lap_time_sec"].mean()), 3)
        if len(clean_stint) >= 2 and clean_stint["tyre_age"].nunique() >= 2:
            slope = float(np.polyfit(clean_stint["tyre_age"], clean_stint["lap_time_sec"], 1)[0])
        else:
            slope = None
        stints.append({
            "stint": int(stint_number),
            "compound": str(stint_laps["compound"].iloc[0]),
            "start_lap": int(stint_laps["lap_number"].min()),
            "end_lap": int(stint_laps["lap_number"].max()),
            "laps": int(len(stint_laps)),
            "clean_laps": int(len(clean_stint)),
            "average_clean_pace": average,
            "degradation_rate_sec_per_lap": None if slope is None else round(slope, 4),
        })
    return stints


def analyze_driver(race_laps: pd.DataFrame, driver_code: str) -> dict[str, Any]:
    """Analyse one driver's completed race using only clean laps for pace metrics."""
    driver_laps = race_laps.loc[race_laps["driver_code"] == driver_code].sort_values("lap_number").copy()
    if driver_laps.empty:
        raise ValueError(f"No lap data found for driver '{driver_code}'.")
    clean_laps = get_clean_laps(driver_laps)
    if clean_laps.empty:
        raise ValueError(f"No clean laps remain for {driver_code}; check the source data.")
    stints = _stint_summary(driver_laps, clean_laps)
    usable_stints = [stint for stint in stints if stint["average_clean_pace"] is not None]
    best_stint = min(usable_stints, key=lambda stint: stint["average_clean_pace"])
    worst_stint = max(usable_stints, key=lambda stint: stint["average_clean_pace"])
    compound_pace = (
        clean_laps.groupby("compound")["lap_time_sec"].mean().round(3).to_dict()
    )
    final_row = driver_laps.iloc[-1]
    return {
        "driver_code": driver_code,
        "driver_name": str(final_row["driver_name"]),
        "driver_number": int(final_row["driver_number"]),
        "team": str(final_row["team"]),
        "team_colour": str(final_row["team_colour"]),
        "race_name": str(final_row["race_name"]),
        "total_laps": int(final_row["total_laps"]),
        "final_position": int(final_row["position"]),
        "average_clean_pace": round(float(clean_laps["lap_time_sec"].mean()), 3),
        "fastest_lap": round(float(clean_laps["lap_time_sec"].min()), 3),
        "slowest_clean_lap": round(float(clean_laps["lap_time_sec"].max()), 3),
        "lap_time_std": round(float(clean_laps["lap_time_sec"].std(ddof=0)), 3),
        "number_clean_laps": int(len(clean_laps)),
        "pit_stops": int(driver_laps["is_pit_lap"].sum()),
        "compound_usage": ", ".join(clean_laps["compound"].drop_duplicates().tolist()),
        "average_pace_per_compound": compound_pace,
        "stints": stints,
        "best_stint": best_stint,
        "worst_stint": worst_stint,
    }


def build_grid_summary(race_laps: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, dict[str, Any]]]:
    """Return a 22-driver summary table and detailed results keyed by driver code."""
    raw_results = {code: analyze_driver(race_laps, code) for code in sorted(race_laps["driver_code"].unique())}
    fastest_average_pace = min(result["average_clean_pace"] for result in raw_results.values())
    results = {code: apply_scores(result, fastest_average_pace) for code, result in raw_results.items()}
    rows = []
    for result in results.values():
        rows.append({
            "final_position": result["final_position"],
            "driver_code": result["driver_code"],
            "driver_name": result["driver_name"],
            "team": result["team"],
            "average_clean_pace": result["average_clean_pace"],
            "fastest_lap": result["fastest_lap"],
            "consistency_score": result["consistency_score"],
            "tyre_management_score": result["tyre_management_score"],
            "pit_stops": result["pit_stops"],
            "best_stint": f"{result['best_stint']['compound']} (L{result['best_stint']['start_lap']}-{result['best_stint']['end_lap']})",
            "worst_stint": f"{result['worst_stint']['compound']} (L{result['worst_stint']['start_lap']}-{result['worst_stint']['end_lap']})",
            "race_engineer_score": result["race_engineer_score"],
            "badge_earned": result["badge_earned"],
            "rating": result["rating"],
        })
    return pd.DataFrame(rows).sort_values("final_position").reset_index(drop=True), results

