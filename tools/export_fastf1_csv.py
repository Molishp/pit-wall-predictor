"""Export FastF1 session data into the local race folder structure.

This helper is optional: it only runs on a machine where FastF1 is installed and
network access is allowed. It writes one folder per race in season order so the
real-data importer can ingest the files later.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = ROOT_DIR / "data" / "real" / "raw_sources"


def _slug(value: str) -> str:
    return "".join(character.lower() if character.isalnum() else "_" for character in value).strip("_").replace("__", "_")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a FastF1 race session to CSV files.")
    parser.add_argument("--season", type=int, required=True, help="Season year, e.g. 2026")
    parser.add_argument("--round", dest="round_number", type=int, required=True, help="Race round number")
    parser.add_argument("--race-name", required=True, help="Race name, e.g. Australian Grand Prix")
    parser.add_argument("--session", default="R", help="Session type, usually R for race")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT), help="Base folder for exported race folders")
    args = parser.parse_args()

    try:
        import fastf1  # type: ignore
    except Exception as error:
        print("FastF1 is not installed in this environment.")
        print("Install it with: python -m pip install fastf1")
        print(f"Import error: {error}")
        return 1

    race_folder = Path(args.output_root) / f"{args.round_number:02d}_{_slug(args.race_name)}"
    race_folder.mkdir(parents=True, exist_ok=True)

    session = fastf1.get_session(args.season, args.round_number, args.session)
    session.load()

    laps_path = race_folder / "laps.csv"
    session.laps.to_csv(laps_path, index=False)

    outputs = [laps_path]
    if hasattr(session, "results") and session.results is not None:
        results_path = race_folder / "results.csv"
        session.results.to_csv(results_path, index=False)
        outputs.append(results_path)

    print("Export complete:")
    for path in outputs:
        print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
