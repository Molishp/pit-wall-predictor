"""Small helpers for local driver metadata and optional local avatar files."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def get_driver_metadata(drivers: pd.DataFrame, driver_code: str) -> pd.Series:
    """Return one driver's local metadata, with a clear error for invalid codes."""
    match = drivers.loc[drivers["driver_code"] == driver_code]
    if match.empty:
        raise ValueError(f"Unknown driver code '{driver_code}'.")
    return match.iloc[0]


def avatar_available(project_root: Path, avatar_file: str) -> bool:
    """Check optional avatar availability without making any image a requirement."""
    return (project_root / avatar_file).is_file()

