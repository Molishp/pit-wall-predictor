"""Transparent clean-lap rules used throughout the post-race analysis."""

from __future__ import annotations

import pandas as pd


EXCLUDED_FLAGS = ["is_pit_lap", "is_safety_car_lap", "is_in_lap", "is_out_lap"]


def get_clean_laps(driver_laps: pd.DataFrame, outlier_seconds: float = 4.0) -> pd.DataFrame:
    """Remove non-representative laps before comparing race pace.

    Pit, safety-car, in- and out-laps are never clean laps.  From the remaining
    rows, laps more than ``outlier_seconds`` slower than the driver's median are
    removed.  This straightforward rule is intentionally easy to audit.
    """
    if driver_laps.empty:
        return driver_laps.copy()
    candidate = driver_laps.copy()
    excluded = candidate[EXCLUDED_FLAGS].any(axis=1)
    candidate = candidate.loc[~excluded].copy()
    if candidate.empty:
        return candidate
    median_lap = candidate["lap_time_sec"].median()
    return candidate.loc[candidate["lap_time_sec"] <= median_lap + outlier_seconds].copy()


def add_clean_lap_flag(race_laps: pd.DataFrame, outlier_seconds: float = 4.0) -> pd.DataFrame:
    """Annotate each row with ``is_clean_lap`` using each driver's own median."""
    annotated = race_laps.copy()
    annotated["is_clean_lap"] = False
    for driver_code, group in annotated.groupby("driver_code"):
        clean_index = get_clean_laps(group, outlier_seconds).index
        annotated.loc[clean_index, "is_clean_lap"] = True
    return annotated

