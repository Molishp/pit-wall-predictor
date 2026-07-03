"""CSV loading and race selection helpers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.real_data_importer import has_real_bundle, load_real_bundle
from src.sample_data_generator import ensure_sample_data


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
BOOLEAN_COLUMNS = ["is_pit_lap", "is_safety_car_lap", "is_out_lap", "is_in_lap"]


def _as_bool(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def load_all_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load the imported real bundle when present, otherwise boot the demo bundle."""
    if has_real_bundle():
        real_calendar, drivers, teams, laps = load_real_bundle()
        full_calendar_path = DATA_DIR / "race_calendar_2026.csv"
        if full_calendar_path.exists():
            full_calendar = pd.read_csv(full_calendar_path)
            real_by_race = real_calendar.set_index("race_name", drop=False)
            merged_rows = []
            for _, row in full_calendar.iterrows():
                race_name = row["race_name"]
                if race_name in real_by_race.index:
                    merged_rows.append(real_by_race.loc[race_name].to_dict())
                else:
                    merged_rows.append(row.to_dict())
            calendar = pd.DataFrame(merged_rows).sort_values("round").reset_index(drop=True)
        else:
            calendar = real_calendar
        return calendar, drivers, teams, laps
    ensure_sample_data()
    calendar = pd.read_csv(DATA_DIR / "race_calendar_2026.csv")
    drivers = pd.read_csv(DATA_DIR / "driver_metadata.csv")
    teams = pd.read_csv(DATA_DIR / "team_metadata.csv")
    laps = pd.read_csv(DATA_DIR / "2026_sample_race_laps.csv")
    for column in BOOLEAN_COLUMNS:
        laps[column] = laps[column].map(_as_bool)
    return calendar, drivers, teams, laps


def get_race_laps(laps: pd.DataFrame, race_name: str, season: int = 2026) -> pd.DataFrame:
    """Return one race's data or an empty frame if it has not been generated."""
    return laps.loc[(laps["season"] == season) & (laps["race_name"] == race_name)].copy()


def get_race_status(calendar: pd.DataFrame, race_name: str, season: int = 2026) -> str | None:
    """Look up a race status from the local calendar."""
    del season  # The version-one calendar is intentionally fixed to 2026.
    matches = calendar.loc[calendar["race_name"] == race_name, "status"]
    return None if matches.empty else str(matches.iloc[0])


def list_completed_races(calendar: pd.DataFrame) -> list[str]:
    """Return selectable post-race analysis options."""
    return calendar.loc[calendar["status"] == "completed", "race_name"].tolist()
