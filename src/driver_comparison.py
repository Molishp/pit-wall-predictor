"""Driver-battle comparison logic for any pair in the generated grid."""

from __future__ import annotations

from typing import Any


def compare_drivers(results: dict[str, dict[str, Any]], driver_a: str, driver_b: str) -> dict[str, Any]:
    """Compare two detailed driver results and provide a concise verdict."""
    if driver_a not in results or driver_b not in results:
        raise ValueError("Both drivers must have a completed-race result.")
    first, second = results[driver_a], results[driver_b]
    pace_delta = round(first["average_clean_pace"] - second["average_clean_pace"], 3)
    faster = first if pace_delta < 0 else second
    consistent = first if first["consistency_score"] >= second["consistency_score"] else second
    tyre_manager = first if first["tyre_management_score"] >= second["tyre_management_score"] else second
    position_winner = first if first["final_position"] < second["final_position"] else second
    verdict = (
        f"{faster['driver_code']} had the stronger average clean pace by {abs(pace_delta):.3f}s per lap. "
        f"{consistent['driver_code']} was more consistent, while {tyre_manager['driver_code']} managed degradation better. "
        f"The finishing advantage went to {position_winner['driver_code']} (P{position_winner['final_position']})."
    )
    return {
        "driver_a": first,
        "driver_b": second,
        "average_pace_difference_sec": pace_delta,
        "faster_driver": faster["driver_code"],
        "more_consistent_driver": consistent["driver_code"],
        "better_tyre_manager": tyre_manager["driver_code"],
        "better_final_position": position_winner["driver_code"],
        "verdict": verdict,
    }

