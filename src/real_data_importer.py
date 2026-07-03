"""Import source-tracked real race CSVs into the local project schema.

The dashboard can work with either the bundled synthetic demo data or an
imported real-data bundle. This module focuses on the real-data path:

- read a source manifest that lists one CSV per completed race;
- download or copy those CSVs into a local cache;
- normalize each file into the app's lap-level schema; and
- write a consolidated bundle the rest of the project can load.

The importer is intentionally flexible because different CSV sources expose
slightly different column names. It accepts FastF1-style exports and other
lap-table CSVs with similar data.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
REAL_DIR = DATA_DIR / "real"
RAW_DIR = REAL_DIR / "raw_sources"

CALENDAR_FILE = REAL_DIR / "race_calendar_2026.csv"
LAPS_FILE = REAL_DIR / "2026_real_race_laps.csv"
MANIFEST_FILE = REAL_DIR / "source_manifest.csv"
SOURCE_INDEX_FILE = REAL_DIR / "source_index.json"

BOOLEAN_COLUMNS = ["is_pit_lap", "is_safety_car_lap", "is_out_lap", "is_in_lap"]


@dataclass(frozen=True)
class ImportRow:
    season: int
    race_name: str
    race_date: str
    country: str
    circuit: str
    status: str
    source_url: str
    source_type: str = "csv"
    source_note: str = ""
    local_csv: str = ""
    total_laps: int | None = None


def _slug(value: str) -> str:
    return "".join(character.lower() if character.isalnum() else "_" for character in value).strip("_").replace("__", "_")


def _as_bool(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_manifest(manifest_path: Path) -> list[ImportRow]:
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Real-data manifest not found: {manifest_path}. Create one from completed-race CSV sources."
        )
    frame = pd.read_csv(manifest_path).fillna("")
    required = {"season", "race_name", "race_date", "country", "circuit", "status"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Manifest is missing required columns: {', '.join(sorted(missing))}")
    rows: list[ImportRow] = []
    for record in frame.to_dict(orient="records"):
        source_url = str(record.get("source_url") or "").strip()
        local_csv = str(record.get("local_csv") or "").strip()
        if not source_url and not local_csv:
            raise ValueError(
                f"{record.get('race_name', 'A race')}: provide either source_url or local_csv in the manifest."
            )
        rows.append(
            ImportRow(
                season=int(record["season"]),
                race_name=str(record["race_name"]),
                race_date=str(record["race_date"]),
                country=str(record["country"]),
                circuit=str(record["circuit"]),
                status=str(record["status"] or "completed"),
                source_url=source_url,
                source_type=str(record.get("source_type") or "csv"),
                source_note=str(record.get("source_note") or ""),
                local_csv=local_csv,
                total_laps=int(record["total_laps"]) if str(record.get("total_laps") or "").strip() else None,
            )
        )
    return rows


def _load_driver_metadata() -> pd.DataFrame:
    path = DATA_DIR / "driver_metadata.csv"
    if not path.exists():
        raise FileNotFoundError(f"Driver metadata file not found: {path}")
    return pd.read_csv(path)


def _load_team_metadata() -> pd.DataFrame:
    path = DATA_DIR / "team_metadata.csv"
    if not path.exists():
        raise FileNotFoundError(f"Team metadata file not found: {path}")
    return pd.read_csv(path)


def _find_column(frame: pd.DataFrame, candidates: list[str]) -> str | None:
    lower_to_actual = {str(column).strip().lower(): column for column in frame.columns}
    for candidate in candidates:
        actual = lower_to_actual.get(candidate.strip().lower())
        if actual is not None:
            return actual
    return None


def _parse_lap_time(value: object) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)) and not pd.isna(value):
        return float(value)
    text = str(value).strip()
    if not text or text.lower() in {"nan", "nat", "none"}:
        return None
    numeric = text.replace(",", "")
    try:
        return float(numeric)
    except ValueError:
        pass
    td = pd.to_timedelta(text, errors="coerce")
    if pd.isna(td):
        return None
    return float(td.total_seconds())


def _parse_int(value: object, default: int | None = None) -> int | None:
    if value is None or pd.isna(value):
        return default
    text = str(value).strip()
    if not text or text.lower() in {"nan", "nat", "none"}:
        return default
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return default


def _parse_float(value: object, default: float = 0.0) -> float:
    if value is None or pd.isna(value):
        return default
    text = str(value).strip()
    if not text or text.lower() in {"nan", "nat", "none"}:
        return default
    try:
        return float(text)
    except (TypeError, ValueError):
        return default


def _normalize_compound(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip().upper()
    if not text:
        return ""
    mapping = {
        "SOFT": "S",
        "MEDIUM": "M",
        "HARD": "H",
        "INTERMEDIATE": "I",
        "WET": "W",
    }
    return mapping.get(text, text[0])


def _read_source_csv(source: ImportRow, cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    if source.local_csv:
        local = Path(source.local_csv)
        if not local.is_absolute():
            local = (ROOT_DIR / local).resolve()
        if not local.exists():
            raise FileNotFoundError(f"Local source CSV not found: {local}")
        cached = cache_dir / local.name
        shutil.copy2(local, cached)
        return cached
    parsed = urlparse(source.source_url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"Unsupported source URL: {source.source_url}")
    safe_name = f"{_slug(source.race_name)}.csv"
    cached = cache_dir / safe_name
    request = Request(source.source_url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=60) as response, cached.open("wb") as handle:
        shutil.copyfileobj(response, handle)
    return cached


def _normalize_laps(frame: pd.DataFrame, source: ImportRow, drivers: pd.DataFrame, teams: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame.columns = [str(column).strip() for column in frame.columns]
    rename_map = {}
    alias_groups = {
        "driver_code": ["driver_code", "driver", "driverid"],
        "driver_name": ["driver_name", "driverfullname", "full_name", "name"],
        "driver_number": ["driver_number", "number", "car_number"],
        "team": ["team", "constructor", "team_name"],
        "lap_number": ["lap_number", "lapnumber", "lap"],
        "lap_time_sec": ["lap_time_sec", "laptime", "lap_time", "lap_time_seconds"],
        "compound": ["compound", "tyre", "tire", "tyre_compound"],
        "tyre_age": ["tyre_age", "tyrelife", "tirelife"],
        "stint": ["stint"],
        "position": ["position", "pos"],
        "gap_to_leader_sec": ["gap_to_leader_sec", "gaptoleader", "gap"],
        "interval_to_car_ahead_sec": ["interval_to_car_ahead_sec", "interval", "intervaltoahead"],
        "is_pit_lap": ["is_pit_lap", "pitlap"],
        "is_safety_car_lap": ["is_safety_car_lap", "safetycar", "safety_car", "sc"],
        "is_out_lap": ["is_out_lap", "outlap"],
        "is_in_lap": ["is_in_lap", "inlap"],
    }
    for target, candidates in alias_groups.items():
        actual = _find_column(frame, candidates)
        if actual is not None:
            rename_map[actual] = target
    frame = frame.rename(columns=rename_map)

    driver_code_col = _find_column(frame, ["driver_code"])
    driver_name_col = _find_column(frame, ["driver_name"])
    team_col = _find_column(frame, ["team"])
    lap_number_col = _find_column(frame, ["lap_number"])
    lap_time_col = _find_column(frame, ["lap_time_sec"])

    if lap_number_col is None or lap_time_col is None:
        raise ValueError(f"{source.race_name}: CSV must include lap number and lap time columns.")
    if driver_code_col is None and driver_name_col is None:
        raise ValueError(f"{source.race_name}: CSV must include a driver code or driver name column.")

    driver_lookup = drivers.copy()
    driver_lookup["driver_code"] = driver_lookup["driver_code"].astype(str).str.upper()
    driver_by_code = driver_lookup.set_index("driver_code").to_dict(orient="index")
    driver_by_name = driver_lookup.assign(driver_name_key=driver_lookup["driver_name"].astype(str).str.lower()).set_index("driver_name_key").to_dict(orient="index")
    team_lookup = teams.copy()
    team_lookup["team"] = team_lookup["team"].astype(str)
    team_by_name = team_lookup.set_index("team").to_dict(orient="index")

    rows: list[dict[str, Any]] = []
    total_laps = source.total_laps

    for _, group in frame.groupby(driver_code_col if driver_code_col else driver_name_col, dropna=False):
        driver_code = None
        driver_name = None
        team = None
        number = None
        if driver_code_col is not None and str(group.iloc[0][driver_code_col]).strip():
            driver_code = str(group.iloc[0][driver_code_col]).strip().upper()
            driver_info = driver_by_code.get(driver_code, {})
            driver_name = str(group.iloc[0][driver_name_col]).strip() if driver_name_col and str(group.iloc[0].get(driver_name_col, "")).strip() else driver_info.get("driver_name", driver_code)
            team = str(group.iloc[0][team_col]).strip() if team_col and str(group.iloc[0].get(team_col, "")).strip() else driver_info.get("team", "")
            number = int(driver_info.get("driver_number") or driver_info.get("official_number") or 0) or None
        else:
            driver_name = str(group.iloc[0][driver_name_col]).strip()
            driver_info = driver_by_name.get(driver_name.lower(), {})
            driver_code = str(driver_info.get("driver_code") or driver_name[:3]).upper()
            team = str(group.iloc[0][team_col]).strip() if team_col and str(group.iloc[0].get(team_col, "")).strip() else driver_info.get("team", "")
            number = int(driver_info.get("driver_number") or driver_info.get("official_number") or 0) or None

        team_info = team_by_name.get(team, {})
        team_colour = str(team_info.get("primary_colour") or "#FFFFFF")
        driver_name = driver_name or str(driver_by_code.get(driver_code, {}).get("driver_name") or driver_code)
        number = number or int(driver_by_code.get(driver_code, {}).get("driver_number") or 0) or None

        group = group.copy()
        group[lap_number_col] = pd.to_numeric(group[lap_number_col], errors="coerce").astype("Int64")
        group[lap_time_col] = group[lap_time_col].map(_parse_lap_time)
        group = group.dropna(subset=[lap_number_col, lap_time_col])
        group = group.sort_values(lap_number_col)
        if total_laps is None and not group.empty:
            total_laps = int(group[lap_number_col].max())

        stint_col = _find_column(group, ["stint"])
        compound_col = _find_column(group, ["compound"])
        tyre_age_col = _find_column(group, ["tyre_age"])
        pit_in_col = _find_column(group, ["pitintime", "is_in_lap"])
        pit_out_col = _find_column(group, ["pitouttime", "is_out_lap"])
        safety_col = _find_column(group, ["trackstatus", "is_safety_car_lap"])
        pos_col = _find_column(group, ["position"])
        gap_col = _find_column(group, ["gap_to_leader_sec"])
        interval_col = _find_column(group, ["interval_to_car_ahead_sec"])

        per_driver = []
        cumulative = 0.0
        for record in group.to_dict(orient="records"):
            lap_number = int(record[lap_number_col])
            lap_time = float(record[lap_time_col])
            cumulative += lap_time
            pit_in = record.get(pit_in_col) if pit_in_col else None
            pit_out = record.get(pit_out_col) if pit_out_col else None
            safety = record.get(safety_col) if safety_col else None
            is_pit_lap = _as_bool(record.get("is_pit_lap")) or pd.notna(pit_in) or pd.notna(pit_out)
            is_out_lap = _as_bool(record.get("is_out_lap")) or pd.notna(pit_out)
            is_in_lap = _as_bool(record.get("is_in_lap")) or pd.notna(pit_in) or is_pit_lap
            if safety is None:
                is_safety = _as_bool(record.get("is_safety_car_lap"))
            else:
                safety_text = str(safety).strip().lower()
                is_safety = safety_text not in {"", "0", "1"} and ("sc" in safety_text or "safety" in safety_text or safety_text == "4")
            per_driver.append(
                {
                    "season": int(source.season),
                    "race_name": source.race_name,
                    "country": source.country,
                    "circuit": source.circuit,
                    "total_laps": int(total_laps or lap_number),
                    "driver_code": driver_code,
                    "driver_name": driver_name,
                    "driver_number": number,
                    "team": team,
                    "team_colour": team_colour,
                    "lap_number": lap_number,
                    "lap_time_sec": round(lap_time, 3),
                    "compound": _normalize_compound(record.get(compound_col)) if compound_col else "",
                    "tyre_age": _parse_int(record.get(tyre_age_col), 0) if tyre_age_col else 0,
                    "stint": _parse_int(record.get(stint_col), 1) if stint_col else 1,
                    "position": _parse_int(record.get(pos_col), 0) if pos_col else 0,
                    "gap_to_leader_sec": _parse_float(record.get(gap_col), 0.0) if gap_col else 0.0,
                    "interval_to_car_ahead_sec": _parse_float(record.get(interval_col), 0.0) if interval_col else 0.0,
                    "is_pit_lap": bool(is_pit_lap),
                    "is_safety_car_lap": bool(is_safety),
                    "is_out_lap": bool(is_out_lap),
                    "is_in_lap": bool(is_in_lap),
                    "_cumulative_time": cumulative,
                }
            )
        rows.extend(per_driver)

    normalized = pd.DataFrame(rows)
    if normalized.empty:
        raise ValueError(f"{source.race_name}: no lap rows could be normalized from {source.source_url or source.local_csv}.")

    if source.total_laps is None:
        normalized["total_laps"] = normalized.groupby(["race_name", "driver_code"])["lap_number"].transform("max")

    output_rows: list[dict[str, Any]] = []
    for lap_number, lap_rows in normalized.groupby("lap_number"):
        lap_rows = lap_rows.sort_values("_cumulative_time")
        leader_time = float(lap_rows.iloc[0]["_cumulative_time"])
        ordered = lap_rows.to_dict(orient="records")
        previous_cumulative: float | None = None
        for index, row in enumerate(ordered, start=1):
            row["position"] = index
            row["gap_to_leader_sec"] = round(float(row["_cumulative_time"]) - leader_time, 3)
            row["interval_to_car_ahead_sec"] = 0.0 if previous_cumulative is None else round(float(row["_cumulative_time"]) - previous_cumulative, 3)
            previous_cumulative = float(row["_cumulative_time"])
            row.pop("_cumulative_time", None)
            output_rows.append(row)

    final = pd.DataFrame(output_rows)
    for column in BOOLEAN_COLUMNS:
        if column in final.columns:
            final[column] = final[column].map(bool)
    return final.sort_values(["race_name", "lap_number", "position", "driver_code"]).reset_index(drop=True)


def import_real_data(manifest_path: str | Path, output_dir: str | Path = REAL_DIR, overwrite: bool = False) -> dict[str, Path]:
    """Import CSV sources listed in a manifest into the local real-data bundle."""
    manifest_path = Path(manifest_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / "raw_sources"
    raw_dir.mkdir(parents=True, exist_ok=True)
    calendar_path = output_dir / CALENDAR_FILE.name
    laps_path = output_dir / LAPS_FILE.name
    manifest_copy_path = output_dir / MANIFEST_FILE.name
    source_index_path = output_dir / SOURCE_INDEX_FILE.name

    manifest = _read_manifest(manifest_path)
    if not manifest:
        raise ValueError("The source manifest does not contain any rows.")

    drivers = _load_driver_metadata()
    teams = _load_team_metadata()
    bundle_rows: list[pd.DataFrame] = []
    calendar_rows: list[dict[str, Any]] = []
    source_index: list[dict[str, Any]] = []

    for source in manifest:
        race_folder = raw_dir / f"{source.season}_{source.race_name}"
        race_folder = race_folder.parent / f"{int(source.season)}_{_slug(source.race_name)}"
        cached_csv = _read_source_csv(source, race_folder)
        source_frame = pd.read_csv(cached_csv)
        normalized = _normalize_laps(source_frame, source, drivers, teams)
        bundle_rows.append(normalized)
        calendar_rows.append(
            {
                "round": len(calendar_rows) + 1,
                "race_name": source.race_name,
                "country": source.country,
                "circuit": source.circuit,
                "race_date": source.race_date,
                "total_laps": int(normalized["total_laps"].max()),
                "status": source.status,
                "track_image_url": "",
            }
        )
        source_index.append(
            {
                "race_name": source.race_name,
                "season": source.season,
                "source_url": source.source_url,
                "source_type": source.source_type,
                "source_note": source.source_note,
                "cached_csv": str(cached_csv.relative_to(output_dir)),
                "sha256": _sha256(cached_csv),
                "rows": int(len(normalized)),
            }
        )

    calendar = pd.DataFrame(calendar_rows).sort_values("round").reset_index(drop=True)
    laps = pd.concat(bundle_rows, ignore_index=True)

    if not overwrite:
        for path in (calendar_path, laps_path):
            if path.exists():
                raise FileExistsError(
                    f"{path} already exists. Pass overwrite=True to replace an existing real-data bundle."
                )

    calendar.to_csv(calendar_path, index=False)
    laps.to_csv(laps_path, index=False)
    if manifest_path.resolve() != manifest_copy_path.resolve():
        shutil.copy2(manifest_path, manifest_copy_path)
    with source_index_path.open("w", encoding="utf-8") as handle:
        json.dump(source_index, handle, indent=2)
    return {"calendar": calendar_path, "laps": laps_path, "manifest": manifest_copy_path, "source_index": source_index_path}


def load_real_bundle() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load the imported real-data bundle if it exists."""
    calendar = pd.read_csv(CALENDAR_FILE)
    drivers = _load_driver_metadata()
    teams = _load_team_metadata()
    laps = pd.read_csv(LAPS_FILE)
    for column in BOOLEAN_COLUMNS:
        if column in laps.columns:
            laps[column] = laps[column].map(_as_bool)
    return calendar, drivers, teams, laps


def has_real_bundle() -> bool:
    return CALENDAR_FILE.exists() and LAPS_FILE.exists()


def bundle_summary() -> dict[str, Any]:
    if not has_real_bundle():
        return {"available": False, "message": "No imported real-data bundle found."}
    calendar = pd.read_csv(CALENDAR_FILE)
    laps = pd.read_csv(LAPS_FILE)
    manifest = pd.read_csv(MANIFEST_FILE) if MANIFEST_FILE.exists() else pd.DataFrame()
    return {
        "available": True,
        "races": int(len(calendar)),
        "laps": int(len(laps)),
        "completed": int((calendar["status"].astype(str).str.lower() == "completed").sum()) if "status" in calendar.columns else 0,
        "manifest_rows": int(len(manifest)),
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Import real race CSVs into the Pit Wall Predictor bundle.")
    parser.add_argument("--manifest", required=True, help="CSV manifest listing race_name, race_date, source_url/local_csv, and metadata.")
    parser.add_argument("--output-dir", default=str(REAL_DIR), help="Destination directory for the imported bundle.")
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing imported bundle.")
    args = parser.parse_args()
    result = import_real_data(args.manifest, args.output_dir, overwrite=args.overwrite)
    print("Imported real-data bundle:")
    for name, path in result.items():
        print(f"- {name}: {path}")
