"""Run the PitWall-Predictor CLI, Tkinter GUI, or local browser UI."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

DEFAULT_RACE = "Barcelona-Catalunya Grand Prix"
DEFAULT_DRIVER = "HAM"
DEFAULT_COMPARISON_DRIVER = "RUS"
ROOT_DIR = Path(__file__).resolve().parent


def _default_web_port() -> int:
    """Use Render's PORT when present, otherwise keep the local default."""
    try:
        return int(os.environ.get("PORT", "8000"))
    except ValueError:
        return 8000


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pit Wall Predictor - F1 2026 post-race strategy analyzer"
    )
    parser.add_argument("--race", default=DEFAULT_RACE, help="Race name from data/race_calendar_2026.csv")
    parser.add_argument("--driver", default=DEFAULT_DRIVER, help="Primary driver code (default: HAM)")
    parser.add_argument("--compare", default=DEFAULT_COMPARISON_DRIVER, help="Comparison driver code (default: RUS)")
    parser.add_argument("--season", default=2026, type=int, help="Season (Version 1 provides 2026 only)")
    parser.add_argument(
        "--animations",
        action="store_true",
        help="Generate Version 5 HTML replays (takes longer than the static dashboard)",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch the Version 6 colourful Tkinter pit-wall dashboard",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Launch the Version 7 local browser dashboard",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host for --web mode (default: 127.0.0.1)")
    parser.add_argument("--port", default=_default_web_port(), type=int, help="Port for --web mode (default: 8000, or PORT env var when hosted)")
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not automatically open the browser when starting --web mode",
    )
    return parser.parse_args()


def run_demo(
    race_name: str,
    selected_driver: str,
    comparison_driver: str,
    season: int = 2026,
    generate_replays: bool = False,
) -> int:
    """Run all completed Version 1-5 analyses and return a command-line exit code."""
    try:
        from src.animations import generate_animations
        from src.data_loader import get_race_laps, get_race_status, load_all_data
        from src.driver_analysis import build_grid_summary
        from src.driver_comparison import compare_drivers
        from src.report_generator import write_reports
        from src.tyre_degradation import fit_tyre_degradation
        from src.visualizer import generate_dashboard
        from src.real_data_importer import has_real_bundle

        calendar, drivers, teams, laps = load_all_data()
        data_label = "imported real-data" if has_real_bundle() else "synthetic demo"
        status = get_race_status(calendar, race_name, season)
        if status is None:
            available = ", ".join(calendar["race_name"].tolist())
            print(f"Race '{race_name}' is not in the local 2026 calendar. Available races: {available}")
            return 2
        if status != "completed":
            print("Race data not available yet. This tool is currently a post-race analyzer.")
            return 0
        race_laps = get_race_laps(laps, race_name, season)
        if race_laps.empty:
            print("Race data not available yet. This tool is currently a post-race analyzer.")
            return 0
        available_drivers = set(race_laps["driver_code"])
        invalid_codes = [code for code in (selected_driver, comparison_driver) if code not in available_drivers]
        if invalid_codes:
            print(f"Driver data not available for: {', '.join(invalid_codes)}. Use one of: {', '.join(sorted(available_drivers))}")
            return 2

        print("=" * 72)
        print("PIT WALL PREDICTOR | F1 2026 POST-RACE STRATEGY ANALYZER")
        print("=" * 72)
        print(f"Loading {race_name} ({len(race_laps)} {data_label} lap records)")
        print(f"Grid loaded: {len(drivers)} drivers, {len(teams)} teams")

        summary, results = build_grid_summary(race_laps)
        comparison = compare_drivers(results, selected_driver, comparison_driver)
        selected = results[selected_driver]
        fit_compound = "M" if "M" in selected["compound_usage"] else selected["compound_usage"].split(", ")[0]
        tyre_fit = fit_tyre_degradation(race_laps, selected_driver, fit_compound)

        reports = write_reports(summary, results, comparison, tyre_fit, ROOT_DIR / "outputs" / "reports")
        plots = generate_dashboard(summary, results, race_laps, comparison, tyre_fit, ROOT_DIR / "outputs" / "plots")
        animation_exports = []
        if generate_replays:
            print("\nGenerating Matplotlib replay animations. This takes a little longer...")
            animation_exports = generate_animations(race_laps, results, tyre_fit, ROOT_DIR / "outputs" / "animations")

        print("\nRACE ENGINEER SUMMARY")
        print(f"Driver: {selected['driver_code']} - {selected['driver_name']} ({selected['team']})")
        print(f"Final position: P{selected['final_position']}")
        print(f"Average clean pace: {selected['average_clean_pace']:.3f} sec")
        print(f"Fastest clean lap: {selected['fastest_lap']:.3f} sec")
        print(f"Consistency: {selected['consistency_score']:.1f}/100 | Tyre management: {selected['tyre_management_score']:.1f}/100")
        print(f"Pit stops: {selected['pit_stops']} | Best stint: {selected['best_stint']['compound']} L{selected['best_stint']['start_lap']}-L{selected['best_stint']['end_lap']}")
        print(f"Race engineer score: {selected['race_engineer_score']:.1f}/100 - {selected['rating']}")
        print(f"Badge earned: {selected['badge_earned']}")
        print(f"Verdict: {selected['race_engineer_verdict']}")
        print("\nDRIVER BATTLE")
        print(comparison["verdict"])
        if tyre_fit is not None:
            print("\nSCIPY TYRE DEGRADATION MODEL")
            print(f"{tyre_fit['driver_code']} {tyre_fit['compound']}: base {tyre_fit['base_pace']:.3f}s, linear {tyre_fit['linear_degradation']:.4f}s/lap, quadratic {tyre_fit['quadratic_degradation']:.5f}s/lap^2, RMSE {tyre_fit['rmse']:.3f}s")
        else:
            print("\nSCIPY TYRE DEGRADATION MODEL: not enough clean same-compound laps for a stable fit.")
        print("\nOUTPUTS SAVED")
        print(f"- Data source: {data_label} bundle")
        print(f"- {reports['summary_csv']}")
        print(f"- {reports['markdown_report']}")
        print(f"- {len(plots)} Matplotlib plots in {ROOT_DIR / 'outputs' / 'plots'}")
        if animation_exports:
            print(f"- {len(animation_exports)} animation result(s) in {ROOT_DIR / 'outputs' / 'animations'}")
            for export in animation_exports:
                print(f"  {export.name}: {export.message}")
        return 0
    except FileNotFoundError as error:
        print(f"Data file problem: {error}")
        return 1
    except Exception as error:  # A CLI portfolio project should fail helpfully, not noisily.
        print(f"PitWall-Predictor could not complete the analysis: {error}")
        return 1


if __name__ == "__main__":
    arguments = _parse_arguments()
    if arguments.gui:
        from src.gui import run_gui

        sys.exit(run_gui())
    if arguments.web:
        from src.web_app import run_web_app

        sys.exit(run_web_app(arguments.host, arguments.port, not arguments.no_browser))
    sys.exit(run_demo(arguments.race, arguments.driver.upper(), arguments.compare.upper(), arguments.season, arguments.animations))
