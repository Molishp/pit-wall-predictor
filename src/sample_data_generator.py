"""Create reproducible fictional 2026 race data for offline demonstrations.

The generator deliberately models broad racing effects rather than real Formula 1
timing.  It gives the rest of the project realistic-looking data to analyse while
keeping the repository fully offline and reproducible.
"""

from __future__ import annotations

import csv
import random
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"


TEAMS: list[dict[str, str]] = [
    {"team": "Mercedes", "short_team_name": "Mercedes", "primary_colour": "#00D2BE", "secondary_colour": "#000000", "car_accent_colour": "#C0C0C0", "engine_or_power_unit": "Mercedes", "base_country": "Great Britain", "performance_tier": "Tier 1"},
    {"team": "Ferrari", "short_team_name": "Ferrari", "primary_colour": "#E8002D", "secondary_colour": "#FFD700", "car_accent_colour": "#FFFFFF", "engine_or_power_unit": "Ferrari", "base_country": "Italy", "performance_tier": "Tier 1"},
    {"team": "McLaren", "short_team_name": "McLaren", "primary_colour": "#FF8700", "secondary_colour": "#47C7FC", "car_accent_colour": "#FFFFFF", "engine_or_power_unit": "Mercedes", "base_country": "Great Britain", "performance_tier": "Tier 1"},
    {"team": "Red Bull Racing", "short_team_name": "Red Bull", "primary_colour": "#1E41FF", "secondary_colour": "#FF003C", "car_accent_colour": "#FFD700", "engine_or_power_unit": "Ford", "base_country": "Austria", "performance_tier": "Tier 1"},
    {"team": "Alpine", "short_team_name": "Alpine", "primary_colour": "#FF87BC", "secondary_colour": "#0093CC", "car_accent_colour": "#FFFFFF", "engine_or_power_unit": "Mercedes", "base_country": "France", "performance_tier": "Tier 3"},
    {"team": "Racing Bulls", "short_team_name": "Racing Bulls", "primary_colour": "#6692FF", "secondary_colour": "#FFFFFF", "car_accent_colour": "#1534CC", "engine_or_power_unit": "Ford", "base_country": "Italy", "performance_tier": "Tier 3"},
    {"team": "Haas F1 Team", "short_team_name": "Haas", "primary_colour": "#B6BABD", "secondary_colour": "#E6002B", "car_accent_colour": "#FFFFFF", "engine_or_power_unit": "Ferrari", "base_country": "United States", "performance_tier": "Tier 3"},
    {"team": "Williams", "short_team_name": "Williams", "primary_colour": "#005AFF", "secondary_colour": "#00A0DE", "car_accent_colour": "#FFFFFF", "engine_or_power_unit": "Mercedes", "base_country": "Great Britain", "performance_tier": "Tier 2"},
    {"team": "Audi", "short_team_name": "Audi", "primary_colour": "#FF0000", "secondary_colour": "#000000", "car_accent_colour": "#FFFFFF", "engine_or_power_unit": "Audi", "base_country": "Germany", "performance_tier": "Tier 2"},
    {"team": "Aston Martin", "short_team_name": "Aston Martin", "primary_colour": "#229971", "secondary_colour": "#CEDC00", "car_accent_colour": "#FFFFFF", "engine_or_power_unit": "Honda", "base_country": "Great Britain", "performance_tier": "Tier 2"},
    {"team": "Cadillac", "short_team_name": "Cadillac", "primary_colour": "#D4AF37", "secondary_colour": "#111111", "car_accent_colour": "#FFFFFF", "engine_or_power_unit": "Ferrari", "base_country": "United States", "performance_tier": "Tier 3"},
]

DRIVERS: list[dict[str, Any]] = [
    {"driver_code": "RUS", "driver_name": "George Russell", "driver_number": 63, "team": "Mercedes", "nationality": "Great Britain", "short_name": "Russell"},
    {"driver_code": "ANT", "driver_name": "Kimi Antonelli", "driver_number": 12, "team": "Mercedes", "nationality": "Italy", "short_name": "Antonelli"},
    {"driver_code": "LEC", "driver_name": "Charles Leclerc", "driver_number": 16, "team": "Ferrari", "nationality": "Monaco", "short_name": "Leclerc"},
    {"driver_code": "HAM", "driver_name": "Lewis Hamilton", "driver_number": 44, "team": "Ferrari", "nationality": "Great Britain", "short_name": "Hamilton"},
    {"driver_code": "NOR", "driver_name": "Lando Norris", "driver_number": 4, "team": "McLaren", "nationality": "Great Britain", "short_name": "Norris"},
    {"driver_code": "PIA", "driver_name": "Oscar Piastri", "driver_number": 81, "team": "McLaren", "nationality": "Australia", "short_name": "Piastri"},
    {"driver_code": "VER", "driver_name": "Max Verstappen", "driver_number": 1, "team": "Red Bull Racing", "nationality": "Netherlands", "short_name": "Verstappen"},
    {"driver_code": "HAD", "driver_name": "Isack Hadjar", "driver_number": 6, "team": "Red Bull Racing", "nationality": "France", "short_name": "Hadjar"},
    {"driver_code": "GAS", "driver_name": "Pierre Gasly", "driver_number": 10, "team": "Alpine", "nationality": "France", "short_name": "Gasly"},
    {"driver_code": "COL", "driver_name": "Franco Colapinto", "driver_number": 43, "team": "Alpine", "nationality": "Argentina", "short_name": "Colapinto"},
    {"driver_code": "LAW", "driver_name": "Liam Lawson", "driver_number": 30, "team": "Racing Bulls", "nationality": "New Zealand", "short_name": "Lawson"},
    {"driver_code": "LIN", "driver_name": "Arvid Lindblad", "driver_number": 41, "team": "Racing Bulls", "nationality": "Great Britain", "short_name": "Lindblad"},
    {"driver_code": "OCO", "driver_name": "Esteban Ocon", "driver_number": 31, "team": "Haas F1 Team", "nationality": "France", "short_name": "Ocon"},
    {"driver_code": "BEA", "driver_name": "Oliver Bearman", "driver_number": 87, "team": "Haas F1 Team", "nationality": "Great Britain", "short_name": "Bearman"},
    {"driver_code": "SAI", "driver_name": "Carlos Sainz", "driver_number": 55, "team": "Williams", "nationality": "Spain", "short_name": "Sainz"},
    {"driver_code": "ALB", "driver_name": "Alexander Albon", "driver_number": 23, "team": "Williams", "nationality": "Thailand", "short_name": "Albon"},
    {"driver_code": "HUL", "driver_name": "Nico Hulkenberg", "driver_number": 27, "team": "Audi", "nationality": "Germany", "short_name": "Hulkenberg"},
    {"driver_code": "BOR", "driver_name": "Gabriel Bortoleto", "driver_number": 5, "team": "Audi", "nationality": "Brazil", "short_name": "Bortoleto"},
    {"driver_code": "ALO", "driver_name": "Fernando Alonso", "driver_number": 14, "team": "Aston Martin", "nationality": "Spain", "short_name": "Alonso"},
    {"driver_code": "STR", "driver_name": "Lance Stroll", "driver_number": 18, "team": "Aston Martin", "nationality": "Canada", "short_name": "Stroll"},
    {"driver_code": "PER", "driver_name": "Sergio Perez", "driver_number": 11, "team": "Cadillac", "nationality": "Mexico", "short_name": "Perez"},
    {"driver_code": "BOT", "driver_name": "Valtteri Bottas", "driver_number": 77, "team": "Cadillac", "nationality": "Finland", "short_name": "Bottas"},
]

RACES: list[dict[str, Any]] = [
    {"round": 1, "race_name": "Australian Grand Prix", "country": "Australia", "circuit": "Albert Park, Melbourne", "race_date": "2026-03-08", "total_laps": 58, "status": "completed"},
    {"round": 2, "race_name": "Chinese Grand Prix", "country": "China", "circuit": "Shanghai International Circuit, Shanghai", "race_date": "2026-03-15", "total_laps": 56, "status": "completed"},
    {"round": 3, "race_name": "Japanese Grand Prix", "country": "Japan", "circuit": "Suzuka Circuit, Suzuka", "race_date": "2026-03-29", "total_laps": 53, "status": "completed"},
    {"round": 4, "race_name": "Miami Grand Prix", "country": "United States", "circuit": "Miami International Autodrome, Miami", "race_date": "2026-05-03", "total_laps": 57, "status": "completed"},
    {"round": 5, "race_name": "Canadian Grand Prix", "country": "Canada", "circuit": "Circuit Gilles Villeneuve, Montreal", "race_date": "2026-05-24", "total_laps": 70, "status": "completed"},
    {"round": 6, "race_name": "Monaco Grand Prix", "country": "Monaco", "circuit": "Circuit de Monaco, Monaco", "race_date": "2026-06-07", "total_laps": 78, "status": "completed"},
    {"round": 7, "race_name": "Barcelona-Catalunya Grand Prix", "country": "Spain", "circuit": "Circuit de Barcelona-Catalunya, Barcelona", "race_date": "2026-06-14", "total_laps": 66, "status": "completed"},
    {"round": 8, "race_name": "Austrian Grand Prix", "country": "Austria", "circuit": "Red Bull Ring, Spielberg", "race_date": "2026-06-28", "total_laps": 71, "status": "completed"},
    {"round": 9, "race_name": "British Grand Prix", "country": "Great Britain", "circuit": "Silverstone", "race_date": "2026-07-05", "total_laps": 52, "status": "upcoming"},
    {"round": 10, "race_name": "Belgian Grand Prix", "country": "Belgium", "circuit": "Spa-Francorchamps", "race_date": "2026-07-19", "total_laps": 44, "status": "upcoming"},
    {"round": 11, "race_name": "Hungarian Grand Prix", "country": "Hungary", "circuit": "Hungaroring", "race_date": "2026-07-26", "total_laps": 70, "status": "upcoming"},
    {"round": 12, "race_name": "Dutch Grand Prix", "country": "Netherlands", "circuit": "Zandvoort", "race_date": "2026-08-23", "total_laps": 72, "status": "upcoming"},
    {"round": 13, "race_name": "Italian Grand Prix", "country": "Italy", "circuit": "Monza", "race_date": "2026-09-06", "total_laps": 53, "status": "upcoming"},
    {"round": 14, "race_name": "Spanish Grand Prix", "country": "Spain", "circuit": "Madrid", "race_date": "2026-09-13", "total_laps": 57, "status": "upcoming"},
    {"round": 15, "race_name": "Azerbaijan Grand Prix", "country": "Azerbaijan", "circuit": "Baku", "race_date": "2026-09-27", "total_laps": 51, "status": "upcoming"},
    {"round": 16, "race_name": "Singapore Grand Prix", "country": "Singapore", "circuit": "Marina Bay", "race_date": "2026-10-11", "total_laps": 62, "status": "upcoming"},
    {"round": 17, "race_name": "United States Grand Prix", "country": "United States", "circuit": "COTA", "race_date": "2026-10-25", "total_laps": 56, "status": "upcoming"},
    {"round": 18, "race_name": "Mexico City Grand Prix", "country": "Mexico", "circuit": "Autodromo Hermanos Rodriguez", "race_date": "2026-11-01", "total_laps": 71, "status": "upcoming"},
    {"round": 19, "race_name": "Sao Paulo Grand Prix", "country": "Brazil", "circuit": "Interlagos", "race_date": "2026-11-08", "total_laps": 71, "status": "upcoming"},
    {"round": 20, "race_name": "Las Vegas Grand Prix", "country": "United States", "circuit": "Las Vegas Strip Circuit", "race_date": "2026-11-21", "total_laps": 50, "status": "upcoming"},
    {"round": 21, "race_name": "Qatar Grand Prix", "country": "Qatar", "circuit": "Lusail", "race_date": "2026-11-29", "total_laps": 57, "status": "upcoming"},
    {"round": 22, "race_name": "Abu Dhabi Grand Prix", "country": "United Arab Emirates", "circuit": "Yas Marina", "race_date": "2026-12-06", "total_laps": 58, "status": "upcoming"},
]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write a list of dictionaries to CSV using its first row as the schema."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _strategy(total_laps: int, driver_index: int, rng: random.Random) -> tuple[list[int], list[str]]:
    """Return pit laps and compounds for a simple one- or two-stop strategy."""
    two_stop = (driver_index + rng.randint(0, 3)) % 3 == 0
    if two_stop:
        stops = [int(total_laps * rng.uniform(0.25, 0.32)), int(total_laps * rng.uniform(0.58, 0.68))]
        patterns = [["S", "M", "H"], ["M", "H", "S"], ["S", "H", "M"]]
    else:
        stops = [int(total_laps * rng.uniform(0.42, 0.56))]
        patterns = [["M", "H"], ["H", "M"], ["S", "H"]]
    return stops, patterns[(driver_index + rng.randint(0, 10)) % len(patterns)]


def _generate_laps() -> list[dict[str, Any]]:
    """Build all completed-race lap rows, then derive running positions and gaps."""
    rng = random.Random(2026)
    team_colours = {team["team"]: team["primary_colour"] for team in TEAMS}
    team_offsets = {"Tier 1": 0.0, "Tier 2": 0.72, "Tier 3": 1.30}
    driver_offsets = {driver["driver_code"]: (index % 6 - 2.5) * 0.045 for index, driver in enumerate(DRIVERS)}
    safety_car_laps = {1: {25, 26, 27}, 2: set(), 3: {19, 20}, 4: {34, 35, 36}, 5: set(), 6: {48, 49}, 7: {29, 30}, 8: {43, 44}}
    all_rows: list[dict[str, Any]] = []

    for race in (item for item in RACES if item["status"] == "completed"):
        race_rows: list[dict[str, Any]] = []
        circuit_base = 88.5 + (race["round"] % 4) * 1.6
        for driver_index, driver in enumerate(DRIVERS):
            team = next(item for item in TEAMS if item["team"] == driver["team"])
            stops, compounds = _strategy(race["total_laps"], driver_index, rng)
            stint = 1
            tyre_age = 0
            compound = compounds[0]
            cumulative_time = 0.0
            for lap in range(1, race["total_laps"] + 1):
                is_pit_lap = lap in stops
                is_out_lap = lap - 1 in stops
                is_in_lap = is_pit_lap
                if is_out_lap:
                    stint += 1
                    compound = compounds[stint - 1]
                    tyre_age = 0
                tyre_age += 1
                compound_degradation = {"S": 0.072, "M": 0.047, "H": 0.030}[compound]
                degradation = compound_degradation * (tyre_age - 1) + 0.0007 * (tyre_age - 1) ** 2
                lap_time = circuit_base + team_offsets[team["performance_tier"]] + driver_offsets[driver["driver_code"]]
                lap_time += degradation + rng.gauss(0, 0.22)
                is_safety_car_lap = lap in safety_car_laps[race["round"]]
                if is_safety_car_lap:
                    lap_time += rng.uniform(35, 42)
                if is_pit_lap:
                    lap_time += rng.uniform(19.5, 23.0)
                elif is_out_lap:
                    lap_time += rng.uniform(1.2, 2.2)
                if not is_safety_car_lap and not is_pit_lap and rng.random() < 0.018:
                    lap_time += rng.uniform(2.5, 6.0)
                cumulative_time += lap_time
                race_rows.append({
                    "season": 2026, "round": race["round"], "race_name": race["race_name"], "country": race["country"],
                    "circuit": race["circuit"], "total_laps": race["total_laps"], "driver_code": driver["driver_code"],
                    "driver_name": driver["driver_name"], "driver_number": driver["driver_number"], "team": driver["team"],
                    "team_colour": team_colours[driver["team"]], "lap_number": lap, "lap_time_sec": round(lap_time, 3),
                    "compound": compound, "tyre_age": tyre_age, "stint": stint, "position": 0, "gap_to_leader_sec": 0.0,
                    "interval_to_car_ahead_sec": 0.0, "is_pit_lap": is_pit_lap, "is_safety_car_lap": is_safety_car_lap,
                    "is_out_lap": is_out_lap, "is_in_lap": is_in_lap, "_cumulative_time": cumulative_time,
                })

        for lap in range(1, race["total_laps"] + 1):
            lap_rows = [row for row in race_rows if row["lap_number"] == lap]
            lap_rows.sort(key=lambda row: row["_cumulative_time"])
            leader_time = lap_rows[0]["_cumulative_time"]
            for position, row in enumerate(lap_rows, start=1):
                row["position"] = position
                row["gap_to_leader_sec"] = round(row["_cumulative_time"] - leader_time, 3)
                row["interval_to_car_ahead_sec"] = 0.0 if position == 1 else round(row["_cumulative_time"] - lap_rows[position - 2]["_cumulative_time"], 3)
            # Keep every cumulative time available while calculating intervals,
            # then remove the internal generator-only value from the CSV rows.
            for row in lap_rows:
                del row["_cumulative_time"]
        all_rows.extend(race_rows)
    return all_rows


def ensure_sample_data(force: bool = False) -> dict[str, Path]:
    """Create missing metadata and synthetic lap data; return their paths.

    Set ``force=True`` only when deliberately regenerating the deterministic
    fictional dataset.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    paths = {
        "drivers": DATA_DIR / "driver_metadata.csv",
        "teams": DATA_DIR / "team_metadata.csv",
        "calendar": DATA_DIR / "race_calendar_2026.csv",
        "laps": DATA_DIR / "2026_sample_race_laps.csv",
    }
    if force or not paths["drivers"].exists():
        driver_rows = [{**driver, "avatar_file": f"assets/drivers/{driver['driver_code']}.png", "driver_status": "active"} for driver in DRIVERS]
        _write_csv(paths["drivers"], driver_rows)
    if force or not paths["teams"].exists():
        _write_csv(paths["teams"], TEAMS)
    if force or not paths["calendar"].exists():
        _write_csv(paths["calendar"], RACES)
    if force or not paths["laps"].exists():
        _write_csv(paths["laps"], _generate_laps())
    return paths


if __name__ == "__main__":
    created = ensure_sample_data()
    print("Synthetic sample data is ready:")
    for name, path in created.items():
        print(f"- {name}: {path}")
