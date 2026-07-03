"""SciPy quadratic tyre-degradation fitting for post-race clean laps."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import curve_fit

from src.data_cleaning import get_clean_laps


def _quadratic_model(tyre_age: np.ndarray | float, base_pace: float, linear: float, quadratic: float) -> np.ndarray | float:
    return base_pace + linear * tyre_age + quadratic * np.asarray(tyre_age) ** 2


def predict_lap_time(base_pace: float, tyre_age: float | np.ndarray, coefficients: tuple[float, float]) -> float | np.ndarray:
    """Predict clean lap time from tyre age and fitted linear/quadratic terms."""
    linear, quadratic = coefficients
    return _quadratic_model(tyre_age, base_pace, linear, quadratic)


def calculate_rmse(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Return root-mean-square model error in seconds."""
    return float(np.sqrt(np.mean((np.asarray(actual) - np.asarray(predicted)) ** 2)))


def estimate_degradation_rate(coefficients: tuple[float, float], tyre_age: float) -> float:
    """Return the local slope a + 2*b*age in seconds per lap."""
    linear, quadratic = coefficients
    return float(linear + 2.0 * quadratic * tyre_age)


def interpret_tyre_degradation(linear: float, quadratic: float, rmse: float) -> str:
    """Translate fitted terms into an approachable engineering sentence."""
    late_rate = estimate_degradation_rate((linear, quadratic), 15)
    if late_rate < 0.055:
        management = "smooth and controlled"
    elif late_rate < 0.11:
        management = "noticeable but manageable"
    else:
        management = "steep, suggesting a tyre drop-off"
    confidence = "a close fit" if rmse < 0.35 else "a useful approximation with normal race variability"
    return f"The fitted degradation trend is {management}; RMSE of {rmse:.2f}s indicates {confidence}."


def fit_tyre_degradation(race_laps: pd.DataFrame, driver_code: str, compound: str) -> dict[str, Any] | None:
    """Fit Lap Time = Base Pace + a*Tyre Age + b*Tyre Age² for clean laps.

    The calculation is post-race descriptive modelling, not a pre-race forecast.
    It pools same-compound clean laps from the selected driver's stints.
    """
    driver_laps = race_laps.loc[race_laps["driver_code"] == driver_code]
    clean = get_clean_laps(driver_laps)
    sample = clean.loc[clean["compound"] == compound].sort_values("tyre_age")
    if len(sample) < 5 or sample["tyre_age"].nunique() < 4:
        return None
    ages = sample["tyre_age"].to_numpy(dtype=float)
    lap_times = sample["lap_time_sec"].to_numpy(dtype=float)
    try:
        parameters, _ = curve_fit(_quadratic_model, ages, lap_times, p0=(float(lap_times.min()), 0.04, 0.001), maxfev=10_000)
    except (RuntimeError, ValueError):
        return None
    base_pace, linear, quadratic = (float(value) for value in parameters)
    predicted = _quadratic_model(ages, base_pace, linear, quadratic)
    rmse = calculate_rmse(lap_times, predicted)
    return {
        "driver_code": driver_code,
        "compound": compound,
        "base_pace": round(base_pace, 4),
        "linear_degradation": round(linear, 5),
        "quadratic_degradation": round(quadratic, 6),
        "rmse": round(rmse, 4),
        "sample_size": int(len(sample)),
        "tyre_age": ages,
        "actual_lap_times": lap_times,
        "predicted_lap_times": predicted,
        "interpretation": interpret_tyre_degradation(linear, quadratic, rmse),
    }

