"""Simple, visible scoring rules for the gamified race-engineer layer."""

from __future__ import annotations

from typing import Any


def _clip(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def consistency_score(lap_time_std: float) -> float:
    """Reward low lap-time scatter; 0.20 s standard deviation scores 94/100."""
    return round(_clip(100.0 - lap_time_std * 30.0), 1)


def tyre_management_score(degradation_rates: list[float]) -> float:
    """Score a driver by the average positive clean-lap degradation per stint."""
    positive_rates = [max(0.0, rate) for rate in degradation_rates if rate is not None]
    if not positive_rates:
        return 70.0
    average_rate = sum(positive_rates) / len(positive_rates)
    return round(_clip(100.0 - average_rate * 430.0), 1)


def pace_score(average_pace: float, fastest_average_pace: float) -> float:
    """Convert pace deficit to an easy-to-read 0-100 score."""
    return round(_clip(100.0 - (average_pace - fastest_average_pace) * 22.0), 1)


def stint_execution_score(stint_averages: list[float]) -> float:
    """Reward a strategy whose clean stints stay close in average pace."""
    if len(stint_averages) < 2:
        return 75.0
    spread = max(stint_averages) - min(stint_averages)
    return round(_clip(100.0 - spread * 18.0), 1)


def rating_name(score: float) -> str:
    """Return the light-hearted, professional overall rating requested by the brief."""
    if score >= 95:
        return "Master Strategist"
    if score >= 85:
        return "Pit Wall Pro"
    if score >= 70:
        return "Solid Race Engineer"
    if score >= 50:
        return "Risky Strategy Call"
    return "Ferrari Strategy Department"


def apply_scores(result: dict[str, Any], fastest_average_pace: float) -> dict[str, Any]:
    """Add transparent scores, a primary badge, and a friendly verdict to analysis."""
    result = result.copy()
    degradation_rates = [stint["degradation_rate_sec_per_lap"] for stint in result["stints"]]
    stint_averages = [stint["average_clean_pace"] for stint in result["stints"] if stint["average_clean_pace"] is not None]
    result["consistency_score"] = consistency_score(result["lap_time_std"])
    result["tyre_management_score"] = tyre_management_score(degradation_rates)
    result["pace_score"] = pace_score(result["average_clean_pace"], fastest_average_pace)
    result["stint_execution_score"] = stint_execution_score(stint_averages)
    result["race_engineer_score"] = round(
        0.35 * result["pace_score"]
        + 0.25 * result["consistency_score"]
        + 0.25 * result["tyre_management_score"]
        + 0.15 * result["stint_execution_score"],
        1,
    )
    result["rating"] = rating_name(result["race_engineer_score"])

    badges: list[str] = []
    if result["pace_score"] >= 96:
        badges.append("Race Pace Beast")
    if result["consistency_score"] >= 93:
        badges.append("Consistency Champion")
    if result["tyre_management_score"] >= 88:
        badges.append("Tyre Whisperer")
    if result["stint_execution_score"] >= 92:
        badges.append("Stint Monster")
    if result["final_position"] <= 3:
        badges.append("Clean Air King")
    if any(rate is not None and rate > 0.13 for rate in degradation_rates):
        badges.append("Tyre Cliff Victim")
    if not badges:
        badges.append("Pit Wall Pro" if result["race_engineer_score"] >= 80 else "Smooth Operator")
    result["badges"] = badges
    result["badge_earned"] = badges[0]
    result["race_engineer_verdict"] = _verdict(result)
    return result


def _verdict(result: dict[str, Any]) -> str:
    """Create an understandable race-engineer-style conclusion."""
    best = result["best_stint"]
    worst = result["worst_stint"]
    driver = result["driver_code"]
    pace = "strong" if result["pace_score"] >= 85 else "steady" if result["pace_score"] >= 65 else "workmanlike"
    consistency = "very consistent" if result["consistency_score"] >= 90 else "reasonably consistent"
    text = (
        f"{driver} showed {pace} clean-air pace and was {consistency} once non-representative laps were removed. "
        f"The best phase was stint {best['stint']} on {best['compound']} tyres"
    )
    if worst["stint"] != best["stint"]:
        text += f", while stint {worst['stint']} was the slowest phase. "
    else:
        text += ". "
    if result["tyre_management_score"] >= 85:
        text += "Tyre degradation was controlled well across the strategy."
    elif result["tyre_management_score"] < 65:
        text += "The degradation trend suggests the tyres reached their limit too quickly."
    else:
        text += "Tyre management was acceptable, with room to smooth the long-run drop-off."
    return text

