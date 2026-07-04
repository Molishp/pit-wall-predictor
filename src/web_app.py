"""Local browser UI for Pit Wall Predictor using only the Python standard library.

The web layer is intentionally thin: it serves one HTML/CSS/JavaScript page and
delegates every race calculation, plot, report, and replay to the existing
backend modules.  No Flask, no FastAPI, no React build step.
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import html
import json
import mimetypes
import os
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import webbrowser

import numpy as np
import pandas as pd

from src.data_cleaning import get_clean_laps
from src.data_loader import get_race_laps, get_race_status, load_all_data
from src.driver_analysis import build_grid_summary
from src.driver_comparison import compare_drivers
from src.report_generator import write_reports

try:  # Optional in this runtime; the web UI can still start without them.
    from src.animations import generate_animations
except Exception:  # pragma: no cover - runtime capability guard
    generate_animations = None

try:  # Optional in this runtime; the web UI can still start without them.
    from src.tyre_degradation import fit_tyre_degradation
except Exception:  # pragma: no cover - runtime capability guard
    fit_tyre_degradation = None

try:  # Optional in this runtime; the web UI can still start without them.
    from src.visualizer import generate_dashboard
except Exception:  # pragma: no cover - runtime capability guard
    generate_dashboard = None


ROOT_DIR = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT_DIR / "assets"
DEFAULT_RACE = "Barcelona-Catalunya Grand Prix"
DEFAULT_DRIVER = "HAM"
DEFAULT_COMPARISON_DRIVER = "RUS"
POST_RACE_MESSAGE = "Race data not available yet. This tool is currently a post-race analyzer."
F1_MEDIA_TRANSFORM_PORTRAIT = "https://media.formula1.com/image/upload/c_fill%2Cw_720/q_auto/v1740000001"
F1_MEDIA_TRANSFORM_CAR = "https://media.formula1.com/image/upload/c_lfill%2Cw_3392/q_auto/v1740000001"

DRIVER_MEDIA: dict[str, dict[str, Any]] = {
    "RUS": {"number": 63, "profile": "https://www.formula1.com/en/drivers/george-russell", "photo": f"{F1_MEDIA_TRANSFORM_PORTRAIT}/common/f1/2026/mercedes/georus01/2026mercedesgeorus01right.webp"},
    "ANT": {"number": 12, "profile": "https://www.formula1.com/en/drivers/kimi-antonelli", "photo": f"{F1_MEDIA_TRANSFORM_PORTRAIT}/common/f1/2026/mercedes/andant01/2026mercedesandant01right.webp"},
    "LEC": {"number": 16, "profile": "https://www.formula1.com/en/drivers/charles-leclerc", "photo": f"{F1_MEDIA_TRANSFORM_PORTRAIT}/common/f1/2026/ferrari/chalec01/2026ferrarichalec01right.webp"},
    "HAM": {"number": 44, "profile": "https://www.formula1.com/en/drivers/lewis-hamilton", "photo": f"{F1_MEDIA_TRANSFORM_PORTRAIT}/common/f1/2026/ferrari/lewham01/2026ferrarilewham01right.webp"},
    "NOR": {"number": 1, "profile": "https://www.formula1.com/en/drivers/lando-norris", "photo": f"{F1_MEDIA_TRANSFORM_PORTRAIT}/common/f1/2026/mclaren/lannor01/2026mclarenlannor01right.webp"},
    "PIA": {"number": 81, "profile": "https://www.formula1.com/en/drivers/oscar-piastri", "photo": f"{F1_MEDIA_TRANSFORM_PORTRAIT}/common/f1/2026/mclaren/oscpia01/2026mclarenoscpia01right.webp"},
    "VER": {"number": 3, "profile": "https://www.formula1.com/en/drivers/max-verstappen", "photo": f"{F1_MEDIA_TRANSFORM_PORTRAIT}/common/f1/2026/redbullracing/maxver01/2026redbullracingmaxver01right.webp"},
    "HAD": {"number": 6, "profile": "https://www.formula1.com/en/drivers/isack-hadjar", "photo": f"{F1_MEDIA_TRANSFORM_PORTRAIT}/common/f1/2026/redbullracing/isahad01/2026redbullracingisahad01right.webp"},
    "GAS": {"number": 10, "profile": "https://www.formula1.com/en/drivers/pierre-gasly", "photo": f"{F1_MEDIA_TRANSFORM_PORTRAIT}/common/f1/2026/alpine/piegas01/2026alpinepiegas01right.webp"},
    "COL": {"number": 43, "profile": "https://www.formula1.com/en/drivers/franco-colapinto", "photo": f"{F1_MEDIA_TRANSFORM_PORTRAIT}/common/f1/2026/alpine/fracol01/2026alpinefracol01right.webp"},
    "LAW": {"number": 30, "profile": "https://www.formula1.com/en/drivers/liam-lawson", "photo": f"{F1_MEDIA_TRANSFORM_PORTRAIT}/common/f1/2026/racingbulls/lialaw01/2026racingbullslialaw01right.webp"},
    "LIN": {"number": 41, "profile": "https://www.formula1.com/en/drivers/arvid-lindblad", "photo": f"{F1_MEDIA_TRANSFORM_PORTRAIT}/common/f1/2026/racingbulls/arvlin01/2026racingbullsarvlin01right.webp"},
    "OCO": {"number": 31, "profile": "https://www.formula1.com/en/drivers/esteban-ocon", "photo": f"{F1_MEDIA_TRANSFORM_PORTRAIT}/common/f1/2026/haas/estoco01/2026haasestoco01right.webp"},
    "BEA": {"number": 87, "profile": "https://www.formula1.com/en/drivers/oliver-bearman", "photo": f"{F1_MEDIA_TRANSFORM_PORTRAIT}/common/f1/2026/haas/olibea01/2026haasolibea01right.webp"},
    "SAI": {"number": 55, "profile": "https://www.formula1.com/en/drivers/carlos-sainz", "photo": f"{F1_MEDIA_TRANSFORM_PORTRAIT}/common/f1/2026/williams/carsai01/2026williamscarsai01right.webp"},
    "ALB": {"number": 23, "profile": "https://www.formula1.com/en/drivers/alexander-albon", "photo": f"{F1_MEDIA_TRANSFORM_PORTRAIT}/common/f1/2026/williams/alealb01/2026williamsalealb01right.webp"},
    "HUL": {"number": 27, "profile": "https://www.formula1.com/en/drivers/nico-hulkenberg", "photo": f"{F1_MEDIA_TRANSFORM_PORTRAIT}/common/f1/2026/audi/nichul01/2026audinichul01right.webp"},
    "BOR": {"number": 5, "profile": "https://www.formula1.com/en/drivers/gabriel-bortoleto", "photo": f"{F1_MEDIA_TRANSFORM_PORTRAIT}/common/f1/2026/audi/gabbor01/2026audigabbor01right.webp"},
    "ALO": {"number": 14, "profile": "https://www.formula1.com/en/drivers/fernando-alonso", "photo": f"{F1_MEDIA_TRANSFORM_PORTRAIT}/common/f1/2026/astonmartin/feralo01/2026astonmartinferalo01right.webp"},
    "STR": {"number": 18, "profile": "https://www.formula1.com/en/drivers/lance-stroll", "photo": f"{F1_MEDIA_TRANSFORM_PORTRAIT}/common/f1/2026/astonmartin/lanstr01/2026astonmartinlanstr01right.webp"},
    "PER": {"number": 11, "profile": "https://www.formula1.com/en/drivers/sergio-perez", "photo": f"{F1_MEDIA_TRANSFORM_PORTRAIT}/common/f1/2026/cadillac/serper01/2026cadillacserper01right.webp"},
    "BOT": {"number": 77, "profile": "https://www.formula1.com/en/drivers/valtteri-bottas", "photo": f"{F1_MEDIA_TRANSFORM_PORTRAIT}/common/f1/2026/cadillac/valbot01/2026cadillacvalbot01right.webp"},
}

TEAM_MEDIA: dict[str, dict[str, str]] = {
    "Mercedes": {
        "profile": "https://www.formula1.com/en/teams/mercedes",
        "car": f"{F1_MEDIA_TRANSFORM_CAR}/common/f1/2026/mercedes/2026mercedescarright.webp",
        "logo": "https://media.formula1.com/image/upload/c_fit%2Ch_64/q_auto/v1740000001/common/f1/2025/mercedes/2025mercedeslogowhite.webp",
    },
    "Ferrari": {
        "profile": "https://www.formula1.com/en/teams/ferrari",
        "car": f"{F1_MEDIA_TRANSFORM_CAR}/common/f1/2026/ferrari/2026ferraricarright.webp",
        "logo": "https://media.formula1.com/image/upload/c_fit%2Ch_64/q_auto/v1740000001/common/f1/2025/ferrari/2025ferrarilogolight.webp",
    },
    "McLaren": {
        "profile": "https://www.formula1.com/en/teams/mclaren",
        "car": f"{F1_MEDIA_TRANSFORM_CAR}/common/f1/2026/mclaren/2026mclarencarright.webp",
        "logo": "https://media.formula1.com/image/upload/c_fit%2Ch_64/q_auto/v1740000001/common/f1/2025/mclaren/2025mclarenlogowhite.webp",
    },
    "Red Bull Racing": {
        "profile": "https://www.formula1.com/en/teams/red-bull-racing",
        "car": f"{F1_MEDIA_TRANSFORM_CAR}/common/f1/2026/redbullracing/2026redbullracingcarright.webp",
        "logo": "https://media.formula1.com/image/upload/c_fit%2Ch_64/q_auto/v1740000001/common/f1/2025/redbullracing/2025redbullracinglogowhite.webp",
    },
    "Alpine": {
        "profile": "https://www.formula1.com/en/teams/alpine",
        "car": f"{F1_MEDIA_TRANSFORM_CAR}/common/f1/2026/alpine/2026alpinecarright.webp",
        "logo": "https://media.formula1.com/image/upload/c_fit%2Ch_64/q_auto/v1740000001/common/f1/2025/alpine/2025alpinelogowhite.webp",
    },
    "Racing Bulls": {
        "profile": "https://www.formula1.com/en/teams/racing-bulls",
        "car": f"{F1_MEDIA_TRANSFORM_CAR}/common/f1/2026/racingbulls/2026racingbullscarright.webp",
        "logo": "https://media.formula1.com/image/upload/c_fit%2Ch_64/q_auto/v1740000001/common/f1/2025/racingbulls/2025racingbullslogowhite.webp",
    },
    "Haas F1 Team": {
        "profile": "https://www.formula1.com/en/teams/haas",
        "car": f"{F1_MEDIA_TRANSFORM_CAR}/common/f1/2026/haas/2026haascarright.webp",
        "logo": "https://media.formula1.com/image/upload/c_fit%2Ch_64/q_auto/v1740000001/common/f1/2025/haas/2025haaslogowhite.webp",
    },
    "Williams": {
        "profile": "https://www.formula1.com/en/teams/williams",
        "car": f"{F1_MEDIA_TRANSFORM_CAR}/common/f1/2026/williams/2026williamscarright.webp",
        "logo": "https://media.formula1.com/image/upload/c_fit%2Ch_64/q_auto/v1740000001/common/f1/2025/williams/2025williamslogowhite.webp",
    },
    "Audi": {
        "profile": "https://www.formula1.com/en/teams/audi",
        "car": f"{F1_MEDIA_TRANSFORM_CAR}/common/f1/2026/audi/2026audicarright.webp",
        "logo": "https://media.formula1.com/image/upload/c_fit%2Ch_64/q_auto/v1740000001/common/f1/2026/audi/2026audilogowhite.webp",
    },
    "Aston Martin": {
        "profile": "https://www.formula1.com/en/teams/aston-martin",
        "car": f"{F1_MEDIA_TRANSFORM_CAR}/common/f1/2026/astonmartin/2026astonmartincarright.webp",
        "logo": "https://media.formula1.com/image/upload/c_fit%2Ch_64/q_auto/v1740000001/common/f1/2025/astonmartin/2025astonmartinlogowhite.webp",
    },
    "Cadillac": {
        "profile": "https://www.formula1.com/en/teams/cadillac",
        "car": f"{F1_MEDIA_TRANSFORM_CAR}/common/f1/2026/cadillac/2026cadillaccarright.webp",
        "logo": "https://media.formula1.com/image/upload/c_fit%2Ch_64/q_auto/v1740000001/common/f1/2026/cadillac/2026cadillaclogowhite.webp",
    },
}


def _jsonable(value: Any) -> Any:
    """Convert pandas/numpy/path objects into JSON-friendly values."""
    if value is None:
        return None
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _path_to_url(path: Path | None) -> str | None:
    """Expose project output files through the local web server."""
    if path is None:
        return None
    try:
        relative = path.resolve().relative_to(ROOT_DIR.resolve())
    except ValueError:
        return None
    return "/" + relative.as_posix()


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return re.sub(r"_+", "_", cleaned)


def _local_asset_url(relative_path: str) -> str | None:
    path = ROOT_DIR / relative_path
    if path.exists() and path.is_file():
        return "/" + Path(relative_path).as_posix()
    return None


def _driver_photo_url(driver_code: str) -> str | None:
    return _local_asset_url(f"assets/drivers/{driver_code}.webp") or DRIVER_MEDIA.get(driver_code, {}).get("photo")


def _team_car_url(team_name: str) -> str | None:
    return _local_asset_url(f"assets/cars/{_slug(team_name)}.webp") or TEAM_MEDIA.get(team_name, {}).get("car")


def _team_logo_url(team_name: str) -> str | None:
    return _local_asset_url(f"assets/team_logos/{_slug(team_name)}.webp") or TEAM_MEDIA.get(team_name, {}).get("logo")


def _track_map_asset_url(row: pd.Series | dict[str, Any]) -> str | None:
    try:
        round_no = int(row["round"])
        race_name = str(row["race_name"])
    except (KeyError, TypeError, ValueError):
        return None
    stem = f"assets/track_maps/{round_no:02d}_{_slug(race_name)}"
    for extension in ("svg", "png", "webp", "jpg", "jpeg"):
        url = _local_asset_url(f"{stem}.{extension}")
        if url:
            return url
    return None


def _compound_colour(compound: str) -> str:
    return {"S": "#E10600", "M": "#FFD12E", "H": "#F3F4F8"}.get(compound, "#7A8498")


PLOT_CATALOG: dict[str, dict[str, str]] = {
    "all": {
        "title": "Complete plot pack",
        "description": "Generate every Matplotlib dashboard plot for the selected race.",
    },
    "pace": {
        "title": "Full-grid race pace ranking",
        "description": "Ranks every driver by average clean lap pace. Lower lap time means stronger race pace.",
    },
    "consistency": {
        "title": "Full-grid consistency ranking",
        "description": "Shows which drivers kept lap times most stable after non-representative laps were removed.",
    },
    "tyres": {
        "title": "Full-grid tyre management ranking",
        "description": "Compares how smoothly each driver's clean-lap pace changed with tyre age.",
    },
    "team_pace": {
        "title": "Team pace comparison",
        "description": "Averages the two drivers from each team to compare team-level clean race pace.",
    },
    "battle": {
        "title": "Driver battle trace",
        "description": "Plots clean-lap pace for the selected driver and comparison driver across the race.",
    },
    "timeline": {
        "title": "Full-grid strategy timeline",
        "description": "Shows tyre compound blocks and pit stops for the full grid.",
    },
    "heatmap": {
        "title": "Race pace heatmap",
        "description": "Shows relative lap pace across the race. Grey cells are excluded non-clean laps.",
    },
    "degradation": {
        "title": "Tyre degradation curve",
        "description": "Plots clean laps against tyre age and overlays the SciPy quadratic degradation fit.",
    },
}

REPLAY_CATALOG: dict[str, dict[str, str]] = {
    "all": {
        "title": "Complete replay pack",
        "description": "Generate every lightweight browser replay available for the selected race.",
    },
    "race_pace": {
        "title": "Race pace replay",
        "description": "Animates race progress using lap position, gap, and compound data.",
    },
    "tyre_degradation": {
        "title": "Tyre degradation replay",
        "description": "Animates clean tyre-age observations and the fitted degradation trend.",
    },
    "pit_timeline": {
        "title": "Pit stop timeline replay",
        "description": "Animates tyre-strategy blocks lap by lap and highlights pit stops.",
    },
}

REPORT_CATALOG: dict[str, dict[str, str]] = {
    "pdf": {
        "title": "PDF strategy report",
        "description": "Portfolio-ready PDF summary with battle notes, full-grid ranking, and modelling assumptions.",
    },
    "markdown": {
        "title": "Markdown race report",
        "description": "GitHub-friendly text report with the full-grid table, battle verdict, and tyre model note.",
    },
    "csv": {
        "title": "CSV driver summary",
        "description": "Spreadsheet-friendly all-driver race summary with scores and ranking metrics.",
    },
    "all": {
        "title": "Complete report pack",
        "description": "Export PDF, Markdown, and CSV versions together.",
    },
}


def _plot_key_from_name(filename: str) -> str:
    lower = filename.lower()
    if lower.startswith("full_grid_pace_ranking"):
        return "pace"
    if lower.startswith("full_grid_consistency"):
        return "consistency"
    if lower.startswith("full_grid_tyre_management"):
        return "tyres"
    if lower.startswith("team_pace"):
        return "team_pace"
    if lower.startswith("driver_battle"):
        return "battle"
    if lower.startswith("full_grid_strategy_timeline"):
        return "timeline"
    if lower.startswith("race_pace_heatmap"):
        return "heatmap"
    if lower.startswith("tyre_degradation"):
        return "degradation"
    return "all"


def _replay_key_from_name(filename: str) -> str:
    lower = filename.lower()
    if lower.startswith("race_pace_replay"):
        return "race_pace"
    if lower.startswith("tyre_degradation_replay"):
        return "tyre_degradation"
    if lower.startswith("pit_stop_timeline"):
        return "pit_timeline"
    return "all"


def _report_key_from_name(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return "pdf"
    if lower.endswith(".md"):
        return "markdown"
    if lower.endswith(".csv"):
        return "csv"
    return "all"


WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
WIKIMEDIA_COMMONS_RAW_URL = "https://upload.wikimedia.org/wikipedia/commons"
TRACK_REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (Codex)"}

TRACK_PAGE_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Albert Park", ("Albert Park Grand Prix Circuit", "Albert Park Circuit")),
    ("Shanghai International Circuit", ("Shanghai International Circuit",)),
    ("Suzuka Circuit", ("Suzuka Circuit",)),
    ("Miami International Autodrome", ("Miami International Autodrome",)),
    ("Circuit Gilles Villeneuve", ("Circuit Gilles Villeneuve",)),
    ("Circuit de Monaco", ("Circuit de Monaco",)),
    ("Circuit de Barcelona-Catalunya", ("Circuit de Barcelona-Catalunya", "Formula1 Circuit Catalunya")),
    ("Red Bull Ring", ("Red Bull Ring",)),
    ("Silverstone", ("Silverstone Circuit",)),
    ("Spa-Francorchamps", ("Circuit de Spa-Francorchamps",)),
    ("Hungaroring", ("Hungaroring",)),
    ("Zandvoort", ("Circuit Zandvoort", "Circuit Park Zandvoort", "CM.com Circuit Zandvoort")),
    ("Monza", ("Autodromo Nazionale di Monza", "Autodromo Nazionale Monza")),
    ("Madrid", ("Madring", "Madring (2026)", "Circuito de Madrid")),
    ("Baku", ("Baku City Circuit",)),
    ("Marina Bay", ("Marina Bay Street Circuit",)),
    ("COTA", ("Circuit of the Americas",)),
    ("Autodromo Hermanos Rodriguez", ("Autódromo Hermanos Rodríguez",)),
    ("Interlagos", ("Autódromo José Carlos Pace",)),
    ("Las Vegas Strip Circuit", ("Las Vegas Strip Circuit",)),
    ("Lusail", ("Lusail International Circuit",)),
    ("Yas Marina", ("Yas Marina Circuit",)),
)


def _format_svg_number(value: float | int) -> str:
    return f"{float(value):g}"


def _fetch_url_text(url: str, timeout: int = 25, retries: int = 2) -> str:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            request = urllib.request.Request(url, headers=TRACK_REQUEST_HEADERS)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as error:
            last_error = error
            if error.code in {429, 500, 502, 503, 504} and attempt < retries:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise
        except urllib.error.URLError as error:
            last_error = error
            if attempt < retries:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise
    if last_error is not None:
        raise last_error
    raise RuntimeError("Unable to fetch URL.")


def _wikipedia_json(params: dict[str, Any]) -> dict[str, Any]:
    payload = dict(params)
    payload["format"] = "json"
    payload.setdefault("origin", "*")
    url = f"{WIKIPEDIA_API_URL}?{urlencode(payload)}"
    return json.loads(_fetch_url_text(url))


def _search_wikipedia_titles(query: str) -> list[str]:
    if not query.strip():
        return []
    data = _wikipedia_json({
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": 6,
        "srnamespace": 0,
    })
    results = data.get("query", {}).get("search", [])
    return [str(item.get("title", "")) for item in results if item.get("title")]


def _track_candidate_titles(race_name: str, circuit_name: str) -> list[str]:
    haystack = f"{race_name} {circuit_name}".lower()
    candidates: list[str] = []
    for needle, titles in TRACK_PAGE_HINTS:
        if needle.lower() in haystack:
            candidates.extend(titles)
    if circuit_name.strip():
        candidates.append(circuit_name.strip())
        if "," in circuit_name:
            candidates.append(circuit_name.split(",", 1)[0].strip())
    if race_name.strip():
        candidates.append(race_name.strip())
        candidates.append(race_name.replace(" Grand Prix", "").strip())
    seen: set[str] = set()
    ordered: list[str] = []
    for candidate in candidates:
        cleaned = candidate.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        ordered.append(cleaned)
    return ordered


def _score_track_svg_filename(filename: str) -> int:
    lower = filename.lower()
    if not lower.endswith(".svg"):
        return -10_000
    if any(blocked in lower for blocked in ("logo", "icon", "flag", "portrait", "driver", "photo", "emblem")):
        return -5_000
    score = 50
    if "map" in lower:
        score += 90
    if "layout" in lower:
        score += 90
    if "circuit" in lower:
        score += 45
    if "track" in lower:
        score += 35
    if "street" in lower:
        score += 20
    if "grand prix" in lower:
        score += 10
    if "formula1" in lower or "formula 1" in lower:
        score += 10
    return score


def _commons_raw_svg_url(filename: str) -> str:
    normalized = filename.replace(" ", "_")
    digest = hashlib.md5(normalized.encode("utf-8")).hexdigest()
    return f"{WIKIMEDIA_COMMONS_RAW_URL}/{digest[0]}/{digest[:2]}/{quote(normalized)}"


def _page_svg_candidates(page_title: str) -> list[str]:
    data = _wikipedia_json({
        "action": "query",
        "prop": "images",
        "titles": page_title,
        "imlimit": 50,
    })
    pages = data.get("query", {}).get("pages", {})
    page = next(iter(pages.values()), {})
    images = []
    for image in page.get("images", []) or []:
        title = str(image.get("title", ""))
        if title.lower().endswith(".svg") and ":" in title:
            images.append(title.split(":", 1)[1])
    images.sort(key=_score_track_svg_filename, reverse=True)
    return images


def _parse_svg_viewbox(root: ET.Element) -> str:
    view_box = root.attrib.get("viewBox") or root.attrib.get("viewbox")
    if view_box:
        return view_box
    width = root.attrib.get("width", "")
    height = root.attrib.get("height", "")
    width_match = re.search(r"[-+]?[0-9]*\.?[0-9]+", width)
    height_match = re.search(r"[-+]?[0-9]*\.?[0-9]+", height)
    if width_match and height_match:
        return f"0 0 {_format_svg_number(float(width_match.group(0)))} {_format_svg_number(float(height_match.group(0)))}"
    return "0 0 1000 620"


def _element_style(element: ET.Element) -> str:
    pieces = [str(element.attrib.get("style", ""))]
    for key in ("fill", "fill-rule", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin", "stroke-opacity", "fill-opacity", "opacity", "display", "visibility", "transform"):
        value = element.attrib.get(key)
        if value is not None:
            pieces.append(f"{key}:{value}")
    return ";".join(piece for piece in pieces if piece).lower()


def _select_track_path(root: ET.Element) -> ET.Element | None:
    best_score = -1
    best_element: ET.Element | None = None
    for element in root.iter():
        if not str(element.tag).endswith("path"):
            continue
        d = element.attrib.get("d")
        if not d:
            continue
        score = len(d)
        style = _element_style(element)
        element_id = str(element.attrib.get("id", "")).lower()
        if "display:none" in style or "visibility:hidden" in style or "opacity:0" in style:
            continue
        if "fill:none" in style:
            score += 5_000
        if "stroke:" in style:
            score += 1_000
        stroke_width = re.search(r"stroke-width:([0-9.]+)", style)
        if stroke_width:
            score += int(float(stroke_width.group(1)) * 120)
        if any(token in style for token in ("stroke:#ffffff", "stroke:white", "stroke:#fff")):
            score += 1_500
        if element_id.startswith("text") or element_id.startswith("label"):
            score -= 1_000
        if "legend" in element_id or "marker" in element_id or "arrow" in element_id:
            score -= 1_000
        if score > best_score:
            best_score = score
            best_element = element
    return best_element


def _extract_track_map(svg_text: str) -> dict[str, Any] | None:
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError:
        return None
    path = _select_track_path(root)
    if path is None:
        return None
    path_d = path.attrib.get("d")
    if not path_d:
        return None
    return {
        "view_box": _parse_svg_viewbox(root),
        "path_d": path_d,
        "path_transform": path.attrib.get("transform"),
        "path_id": path.attrib.get("id"),
    }


def _load_track_map_from_page(page_title: str, race_name: str, circuit_name: str) -> dict[str, Any] | None:
    for file_name in _page_svg_candidates(page_title):
        try:
            svg_text = _fetch_url_text(_commons_raw_svg_url(file_name))
        except Exception:
            continue
        track_map = _extract_track_map(svg_text)
        if track_map:
            track_map.update({
                "source_page": page_title,
                "source_file": file_name,
                "source_url": f"https://en.wikipedia.org/wiki/{quote(page_title.replace(' ', '_'))}",
                "raw_svg_url": _commons_raw_svg_url(file_name),
                "race_name": race_name,
                "circuit_name": circuit_name,
            })
            return track_map
    return None


class PitWallWebService:
    """Stateful bridge between HTTP requests and the existing analysis modules."""

    def __init__(self) -> None:
        self.calendar, self.drivers, self.teams, self.all_laps = load_all_data()
        self._race_cache: dict[tuple[str, int], dict[str, Any]] = {}
        self._track_cache: dict[tuple[str, int], dict[str, Any] | None] = {}

    def _calendar_row(self, race_name: str, season: int = 2026) -> pd.Series | None:
        if "season" in self.calendar.columns:
            matches = self.calendar.loc[(self.calendar["race_name"] == race_name) & (self.calendar["season"] == season)]
        else:
            matches = self.calendar.loc[self.calendar["race_name"] == race_name]
        if matches.empty:
            return None
        return matches.iloc[0]

    def _load_track_map(self, race_name: str, season: int = 2026) -> dict[str, Any] | None:
        row = self._calendar_row(race_name, season)
        if row is None:
            return None
        circuit_name = str(row["circuit"])
        cache_key = (circuit_name, season)
        if cache_key in self._track_cache:
            return self._track_cache[cache_key]
        if _track_map_asset_url(row):
            self._track_cache[cache_key] = None
            return None

        track_map: dict[str, Any] | None = None
        candidates = _track_candidate_titles(race_name, circuit_name)
        for page_title in candidates:
            try:
                track_map = _load_track_map_from_page(page_title, race_name, circuit_name)
            except Exception:
                continue
            if track_map is not None:
                break
        if track_map is None:
            fallback_candidates: list[str] = []
            try:
                fallback_candidates.extend(_search_wikipedia_titles(circuit_name))
            except Exception:
                pass
            try:
                fallback_candidates.extend(_search_wikipedia_titles(race_name))
            except Exception:
                pass
            for page_title in fallback_candidates:
                try:
                    track_map = _load_track_map_from_page(page_title, race_name, circuit_name)
                except Exception:
                    continue
                if track_map is not None:
                    break

        self._track_cache[cache_key] = track_map
        return track_map

    def bootstrap(self) -> dict[str, Any]:
        """Return selector and card metadata for the browser UI."""
        calendar = self.calendar.copy()
        drivers = self.drivers.copy()
        teams = self.teams.copy()
        calendar["track_image_url"] = calendar.apply(_track_map_asset_url, axis=1)
        drivers["official_number"] = drivers["driver_code"].map(lambda code: DRIVER_MEDIA.get(str(code), {}).get("number"))
        drivers["profile_url"] = drivers["driver_code"].map(lambda code: DRIVER_MEDIA.get(str(code), {}).get("profile", "https://www.formula1.com/en/drivers"))
        drivers["photo_url"] = drivers["driver_code"].map(lambda code: _driver_photo_url(str(code)))
        teams["profile_url"] = teams["team"].map(lambda team: TEAM_MEDIA.get(str(team), {}).get("profile", "https://www.formula1.com/en/teams"))
        teams["car_image_url"] = teams["team"].map(lambda team: _team_car_url(str(team)))
        teams["logo_url"] = teams["team"].map(lambda team: _team_logo_url(str(team)))
        return {
            "default_race": DEFAULT_RACE,
            "default_driver": DEFAULT_DRIVER,
            "default_compare": DEFAULT_COMPARISON_DRIVER,
            "track_map": None,
            "calendar": calendar.to_dict(orient="records"),
            "drivers": drivers.to_dict(orient="records"),
            "teams": teams.to_dict(orient="records"),
        }

    def _load_race(self, race_name: str, season: int = 2026) -> dict[str, Any]:
        cache_key = (race_name, season)
        if cache_key in self._race_cache:
            return self._race_cache[cache_key]

        status = get_race_status(self.calendar, race_name, season)
        if status is None:
            available = self.calendar["race_name"].tolist()
            raise ValueError(f"Race '{race_name}' is not in the local 2026 calendar. Available races: {', '.join(available)}")
        if status != "completed":
            return {
                "ok": False,
                "status": status,
                "race_name": race_name,
                "message": POST_RACE_MESSAGE,
            }

        race_laps = get_race_laps(self.all_laps, race_name, season)
        if race_laps.empty:
            return {
                "ok": False,
                "status": "missing",
                "race_name": race_name,
                "message": POST_RACE_MESSAGE,
            }

        summary, results = build_grid_summary(race_laps)
        payload = {
            "ok": True,
            "status": "completed",
            "race_name": race_name,
            "race_laps": race_laps,
            "summary": summary,
            "results": results,
        }
        self._race_cache[cache_key] = payload
        return payload

    def _tyre_fit(self, race_laps: pd.DataFrame, results: dict[str, dict[str, Any]], driver_code: str) -> dict[str, Any] | None:
        if not callable(fit_tyre_degradation):
            return None
        result = results[driver_code]
        compound = "M" if "M" in result["compound_usage"] else result["compound_usage"].split(", ")[0]
        return fit_tyre_degradation(race_laps, driver_code, compound)

    def _driver_trace(self, race_laps: pd.DataFrame, driver_code: str) -> list[dict[str, Any]]:
        clean_laps = get_clean_laps(race_laps.loc[race_laps["driver_code"] == driver_code])
        return [
            {
                "lap": int(row.lap_number),
                "time": round(float(row.lap_time_sec), 3),
                "compound": str(row.compound),
            }
            for row in clean_laps.sort_values("lap_number").itertuples()
        ]

    def _strategy_rows(self, race_laps: pd.DataFrame, results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        total_laps = int(race_laps["total_laps"].iloc[0])
        rows: list[dict[str, Any]] = []
        for code in sorted(results, key=lambda item: results[item]["final_position"]):
            driver_laps = race_laps.loc[race_laps["driver_code"] == code]
            stints = []
            for _, stint in driver_laps.groupby("stint", sort=True):
                start = int(stint["lap_number"].min())
                end = int(stint["lap_number"].max())
                compound = str(stint["compound"].iloc[0])
                stints.append({
                    "compound": compound,
                    "start": start,
                    "end": end,
                    "laps": end - start + 1,
                    "colour": _compound_colour(compound),
                })
            rows.append({
                "driver_code": code,
                "position": int(results[code]["final_position"]),
                "team_colour": results[code]["team_colour"],
                "total_laps": total_laps,
                "stints": stints,
                "pit_laps": [int(lap) for lap in driver_laps.loc[driver_laps["is_pit_lap"], "lap_number"].tolist()],
            })
        return rows

    @staticmethod
    def _stint_plan_text(result: dict[str, Any]) -> str:
        """Return a short compound/lap plan that is easy to scan in the web UI."""
        pieces = []
        for stint in result.get("stints", []):
            pieces.append(
                f"{stint['compound']} L{stint['start_lap']}-{stint['end_lap']}"
            )
        return " → ".join(pieces) if pieces else "No stint data"

    @staticmethod
    def _pit_laps_for(race_laps: pd.DataFrame, driver_code: str) -> list[int]:
        driver_laps = race_laps.loc[race_laps["driver_code"] == driver_code]
        return [int(lap) for lap in driver_laps.loc[driver_laps["is_pit_lap"], "lap_number"].tolist()]

    def _driver_strategy_card(self, race_laps: pd.DataFrame, result: dict[str, Any]) -> dict[str, Any]:
        pit_laps = self._pit_laps_for(race_laps, result["driver_code"])
        best = result["best_stint"]
        worst = result["worst_stint"]
        return {
            "driver_code": result["driver_code"],
            "driver_name": result["driver_name"],
            "team": result["team"],
            "position": result["final_position"],
            "score": result["race_engineer_score"],
            "average_clean_pace": result["average_clean_pace"],
            "consistency_score": result["consistency_score"],
            "tyre_management_score": result["tyre_management_score"],
            "pit_laps": pit_laps,
            "pit_lap_text": ", ".join(f"L{lap}" for lap in pit_laps) if pit_laps else "No stops",
            "stint_plan": self._stint_plan_text(result),
            "best_phase": f"{best['compound']} · L{best['start_lap']}-{best['end_lap']}",
            "weak_phase": f"{worst['compound']} · L{worst['start_lap']}-{worst['end_lap']}",
        }

    @staticmethod
    def _metric_winner(selected_value: float, rival_value: float, lower_is_better: bool = False) -> str:
        if lower_is_better:
            return "selected" if selected_value <= rival_value else "rival"
        return "selected" if selected_value >= rival_value else "rival"

    def _strategy_insights(
        self,
        race_laps: pd.DataFrame,
        results: dict[str, dict[str, Any]],
        comparison: dict[str, Any],
        driver_code: str,
        comparison_code: str,
    ) -> dict[str, Any]:
        """Translate post-race metrics into readable strategy-room talking points."""
        selected = results[driver_code]
        rival = results[comparison_code]
        selected_card = self._driver_strategy_card(race_laps, selected)
        rival_card = self._driver_strategy_card(race_laps, rival)

        pace_delta = float(selected["average_clean_pace"]) - float(rival["average_clean_pace"])
        consistency_delta = float(selected["consistency_score"]) - float(rival["consistency_score"])
        tyre_delta = float(selected["tyre_management_score"]) - float(rival["tyre_management_score"])
        score_delta = float(selected["race_engineer_score"]) - float(rival["race_engineer_score"])

        selected_first_stop = selected_card["pit_laps"][0] if selected_card["pit_laps"] else None
        rival_first_stop = rival_card["pit_laps"][0] if rival_card["pit_laps"] else None
        if selected_first_stop is None or rival_first_stop is None:
            stop_timing = "One of the drivers had no recorded pit stop, so stop timing is not directly comparable."
            stop_value = "N/A"
        else:
            stop_gap = selected_first_stop - rival_first_stop
            if stop_gap < 0:
                stop_timing = f"{driver_code} made the first stop {abs(stop_gap)} lap(s) earlier than {comparison_code}."
                stop_value = f"{driver_code} -{abs(stop_gap)} lap"
            elif stop_gap > 0:
                stop_timing = f"{driver_code} stayed out {stop_gap} lap(s) longer before the first stop."
                stop_value = f"{driver_code} +{stop_gap} lap"
            else:
                stop_timing = f"Both drivers made their first stop on lap {selected_first_stop}."
                stop_value = "Same lap"

        faster_code = driver_code if pace_delta <= 0 else comparison_code
        tyre_code = driver_code if tyre_delta >= 0 else comparison_code
        consistent_code = driver_code if consistency_delta >= 0 else comparison_code
        score_code = driver_code if score_delta >= 0 else comparison_code

        headline = f"{driver_code} vs {comparison_code}: strategy battle room"
        intro = (
            f"{comparison['verdict']} The timeline below shows compounds and pit laps, "
            "while the cards explain where the strategy difference actually came from."
        )

        cards = [
            {
                "label": "Clean pace edge",
                "value": f"{faster_code} by {abs(pace_delta):.3f}s/lap",
                "detail": "Lower clean-lap average is faster after removing pit, safety-car, in- and out-laps.",
                "winner": "selected" if faster_code == driver_code else "rival",
            },
            {
                "label": "First-stop timing",
                "value": stop_value,
                "detail": stop_timing,
                "winner": "neutral",
            },
            {
                "label": "Tyre management",
                "value": f"{tyre_code} +{abs(tyre_delta):.1f} pts",
                "detail": "Higher score means a smoother degradation trend across clean stint laps.",
                "winner": "selected" if tyre_code == driver_code else "rival",
            },
            {
                "label": "Engineer score swing",
                "value": f"{score_code} +{abs(score_delta):.1f} pts",
                "detail": "Combined pace, consistency, tyre management, and stint execution score.",
                "winner": "selected" if score_code == driver_code else "rival",
            },
        ]

        notes = [
            f"{driver_code} plan: {selected_card['stint_plan']} · pit laps {selected_card['pit_lap_text']}.",
            f"{comparison_code} plan: {rival_card['stint_plan']} · pit laps {rival_card['pit_lap_text']}.",
            f"Best phase for {driver_code}: {selected_card['best_phase']}; weakest phase: {selected_card['weak_phase']}.",
            f"Best phase for {comparison_code}: {rival_card['best_phase']}; weakest phase: {rival_card['weak_phase']}.",
        ]
        if abs(pace_delta) < 0.15:
            notes.append("Clean pace was close, so strategy execution and tyre consistency mattered more than raw speed.")
        elif faster_code == driver_code:
            notes.append(f"{driver_code} had the better clean-air speed; the key question is whether the stops protected that pace.")
        else:
            notes.append(f"{comparison_code} had the cleaner pace advantage; {driver_code} needed strategy or consistency to offset it.")
        if abs(tyre_delta) >= 5:
            notes.append(f"The tyre-management gap is meaningful: {tyre_code} kept the long-run drop-off under better control.")
        else:
            notes.append("Tyre management was close enough that the race was decided more by pace and track position.")

        return {
            "focus_codes": [driver_code, comparison_code],
            "headline": headline,
            "intro": intro,
            "cards": cards,
            "notes": notes,
            "selected": selected_card,
            "rival": rival_card,
            "winners": {
                "pace": faster_code,
                "consistency": consistent_code,
                "tyres": tyre_code,
                "score": score_code,
            },
        }

    @staticmethod
    def _file_payload(path: Path, key: str, catalog: dict[str, dict[str, str]], summary: str, kind: str) -> dict[str, Any]:
        item = catalog.get(key, catalog.get("all", {"title": path.name, "description": ""}))
        return {
            "name": path.name,
            "url": _path_to_url(path),
            "key": key,
            "kind": kind,
            "title": item["title"],
            "description": item["description"],
            "summary": summary,
        }

    @staticmethod
    def _plot_summary(
        key: str,
        summary: pd.DataFrame,
        results: dict[str, dict[str, Any]],
        comparison: dict[str, Any],
        tyre_fit: dict[str, Any] | None,
    ) -> str:
        fastest = summary.sort_values("average_clean_pace").iloc[0]
        most_consistent = summary.sort_values("consistency_score", ascending=False).iloc[0]
        tyre_best = summary.sort_values("tyre_management_score", ascending=False).iloc[0]
        driver_a = comparison["driver_a"]
        driver_b = comparison["driver_b"]
        if key == "pace":
            return f"{fastest['driver_code']} leads clean race pace at {float(fastest['average_clean_pace']):.3f}s per lap. This plot is best for spotting raw speed after pit and safety-car noise is removed."
        if key == "consistency":
            return f"{most_consistent['driver_code']} has the highest consistency score at {float(most_consistent['consistency_score']):.1f}/100. Use this to see who delivered repeatable lap times."
        if key == "tyres":
            return f"{tyre_best['driver_code']} tops tyre management with {float(tyre_best['tyre_management_score']):.1f}/100. Higher values indicate smoother degradation trends."
        if key == "team_pace":
            team_frame = summary.groupby("team", as_index=False)["average_clean_pace"].mean().sort_values("average_clean_pace")
            best_team = team_frame.iloc[0]
            return f"{best_team['team']} has the strongest two-driver clean pace average at {float(best_team['average_clean_pace']):.3f}s."
        if key == "battle":
            return comparison["verdict"]
        if key == "timeline":
            stop_counts = {code: int(result["pit_stops"]) for code, result in results.items()}
            max_stops = max(stop_counts.values()) if stop_counts else 0
            busy = sorted([code for code, count in stop_counts.items() if count == max_stops])
            return f"The timeline shows compound choices and pit laps for all 22 drivers. Highest stop count: {max_stops}, used by {', '.join(busy[:5])}."
        if key == "heatmap":
            return "The heatmap highlights relative pace swings lap by lap. Grey areas are laps excluded from clean-lap analysis."
        if key == "degradation":
            if tyre_fit is None:
                return "Tyre degradation fit was not available because there were not enough clean same-compound laps."
            return f"{tyre_fit['driver_code']} {tyre_fit['compound']} tyre model RMSE is {float(tyre_fit['rmse']):.3f}s. {tyre_fit['interpretation']}"
        return f"Generated the complete plot pack for {driver_a['driver_code']} vs {driver_b['driver_code']}."

    @staticmethod
    def _replay_summary(key: str, race_name: str, driver_code: str, used_fallback: bool, detail: str) -> str:
        fallback = " A static final-frame fallback was used." if used_fallback else ""
        if key == "race_pace":
            return f"Race pace replay for {race_name}: the browser animates lap-by-lap position, gap, lap time, and compound data without heavy server rendering.{fallback}"
        if key == "tyre_degradation":
            return f"Tyre degradation replay for {driver_code}: clean tyre-age points appear over the fitted curve to show how lap time changes through a stint.{fallback}"
        if key == "pit_timeline":
            return f"Pit stop timeline replay for {race_name}: compound blocks fill lap by lap and pit laps are highlighted as the race unfolds.{fallback}"
        return f"{detail}{fallback}"

    def _write_browser_replay(
        self,
        key: str,
        race_name: str,
        driver_code: str,
        race_laps: pd.DataFrame,
        results: dict[str, dict[str, Any]],
        tyre_fit: dict[str, Any] | None,
    ) -> Path:
        """Write a compact HTML/JS replay that is fast enough for free hosting."""
        output_dir = ROOT_DIR / "outputs" / "animations"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{_slug(f'{race_name}_{driver_code}_{key}_browser_replay')}.html"

        total_laps = int(race_laps["lap_number"].max()) if not race_laps.empty else 1
        ordered_results = sorted(results.values(), key=lambda item: int(item.get("final_position", 99)))
        max_gap = 1.0
        drivers_payload: list[dict[str, Any]] = []
        for result in ordered_results:
            code = str(result["driver_code"])
            driver_laps = race_laps.loc[race_laps["driver_code"] == code].sort_values("lap_number")
            frames: list[dict[str, Any]] = []
            for _, lap in driver_laps.iterrows():
                raw_gap = lap.get("gap_to_leader_sec", 0.0)
                gap = 0.0 if pd.isna(raw_gap) else float(raw_gap)
                if not np.isfinite(gap):
                    gap = 0.0
                max_gap = max(max_gap, gap)
                frames.append({
                    "lap": int(lap["lap_number"]),
                    "position": int(lap.get("position", result.get("final_position", 0))),
                    "gap": round(gap, 3),
                    "time": round(float(lap.get("lap_time_sec", 0.0) or 0.0), 3),
                    "compound": str(lap.get("compound", "")),
                    "pit": bool(lap.get("is_pit_lap", False)),
                })
            drivers_payload.append({
                "code": code,
                "name": str(result.get("driver_name", code)),
                "team": str(result.get("team", "")),
                "colour": str(result.get("team_colour", "#00e5ff")),
                "final_position": int(result.get("final_position", 99)),
                "score": float(result.get("race_engineer_score", 0.0)),
                "stints": result.get("stints", []),
                "pit_laps": sorted(driver_laps.loc[driver_laps["is_pit_lap"], "lap_number"].astype(int).unique().tolist()),
                "frames": frames,
            })

        tyre_payload: dict[str, Any] | None = None
        if tyre_fit is not None:
            tyre_payload = {
                "driver": str(tyre_fit.get("driver_code", driver_code)),
                "compound": str(tyre_fit.get("compound", "")),
                "rmse": float(tyre_fit.get("rmse", 0.0)),
                "base": float(tyre_fit.get("base_pace", 0.0)),
                "linear": float(tyre_fit.get("linear_degradation", 0.0)),
                "quadratic": float(tyre_fit.get("quadratic_degradation", 0.0)),
                "ages": [float(value) for value in np.asarray(tyre_fit.get("tyre_age", [])).tolist()],
                "actual": [float(value) for value in np.asarray(tyre_fit.get("actual_lap_times", [])).tolist()],
                "predicted": [float(value) for value in np.asarray(tyre_fit.get("predicted_lap_times", [])).tolist()],
                "interpretation": str(tyre_fit.get("interpretation", "")),
            }

        title = REPLAY_CATALOG.get(key, REPLAY_CATALOG["race_pace"])["title"]
        payload = {
            "type": key,
            "title": title,
            "race": race_name,
            "driver": driver_code,
            "total_laps": total_laps,
            "max_gap": round(max_gap, 3),
            "drivers": drivers_payload,
            "tyre": tyre_payload,
        }

        template = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>__PAGE_TITLE__</title>
  <style>
    :root { color-scheme: dark; --bg:#070a12; --panel:#101827; --line:rgba(255,255,255,.14); --muted:#a9b4c7; --text:#f5f7fb; --blue:#0a84ff; --green:#39ff8f; }
    * { box-sizing:border-box; }
    body { margin:0; font-family:Inter,Segoe UI,Arial,sans-serif; background:radial-gradient(circle at 20% 0%, rgba(10,132,255,.18), transparent 34rem), var(--bg); color:var(--text); }
    .app { width:min(980px, calc(100% - 28px)); margin:0 auto; padding:18px 0; }
    .hero { display:flex; justify-content:space-between; gap:16px; align-items:flex-end; border:1px solid var(--line); border-radius:22px; padding:18px; background:rgba(16,24,39,.82); box-shadow:0 24px 70px rgba(0,0,0,.28); }
    .eyebrow { color:#00e5ff; font-size:.72rem; letter-spacing:.16em; text-transform:uppercase; font-weight:900; }
    h1 { margin:.35rem 0 .25rem; font-size:clamp(1.8rem,5vw,3.1rem); line-height:.95; letter-spacing:-.05em; }
    p { color:var(--muted); line-height:1.5; margin:.35rem 0 0; }
    .chip { border:1px solid rgba(57,255,143,.28); border-radius:999px; padding:9px 12px; color:#baffd2; background:rgba(57,255,143,.09); font-weight:900; white-space:nowrap; }
    .controls { margin:14px 0; display:grid; grid-template-columns:auto 1fr auto; gap:10px; align-items:center; border:1px solid var(--line); border-radius:18px; padding:12px; background:rgba(255,255,255,.04); }
    button { border:1px solid rgba(10,132,255,.45); border-radius:14px; padding:10px 16px; background:linear-gradient(135deg,#0a84ff,#00c7ff); color:white; font-weight:950; cursor:pointer; }
    input[type=range] { width:100%; accent-color:#0a84ff; }
    .lap { font-weight:950; color:#d8e7ff; min-width:82px; text-align:right; }
    .stage { border:1px solid var(--line); border-radius:22px; padding:14px; background:rgba(16,24,39,.76); min-height:360px; overflow:hidden; }
    .race-row { display:grid; grid-template-columns:74px 1fr 88px; align-items:center; gap:10px; padding:7px 0; border-bottom:1px solid rgba(255,255,255,.06); }
    .driver-code { font-weight:950; color:#fff; }
    .track { height:24px; border-radius:999px; background:rgba(255,255,255,.08); position:relative; overflow:hidden; }
    .car { position:absolute; top:3px; width:34px; height:18px; border-radius:999px; transform:translateX(-50%); box-shadow:0 0 14px currentColor; transition:left .18s ease; }
    .meta { color:var(--muted); font-size:.78rem; text-align:right; }
    .pit { color:#ffd12e; font-weight:950; }
    .timeline-row { display:grid; grid-template-columns:84px 1fr; gap:12px; align-items:center; margin:10px 0; }
    .timeline { position:relative; display:flex; height:28px; border-radius:999px; overflow:hidden; background:rgba(255,255,255,.08); }
    .stint { min-width:4px; }
    .cursor { position:absolute; top:-4px; bottom:-4px; width:3px; background:#fff; box-shadow:0 0 14px #fff; }
    svg { width:100%; height:360px; display:block; }
    .note { margin-top:12px; border:1px solid rgba(57,255,143,.18); border-radius:16px; padding:12px; background:rgba(57,255,143,.07); color:#dfffea; }
    @media (max-width:700px) { .hero,.controls { grid-template-columns:1fr; display:grid; } .race-row { grid-template-columns:54px 1fr; } .meta { grid-column:2; text-align:left; } }
  </style>
</head>
<body>
  <main class="app">
    <section class="hero">
      <div>
        <div class="eyebrow">Pit Wall Predictor | Browser Replay</div>
        <h1>__TITLE__</h1>
        <p>__RACE__ · Generated instantly from loaded race CSV data.</p>
      </div>
      <div class="chip" id="statusChip">Ready</div>
    </section>
    <section class="controls">
      <button id="playButton" type="button">Play</button>
      <input id="lapSlider" type="range" min="1" max="__TOTAL_LAPS__" value="1">
      <div class="lap" id="lapLabel">Lap 1</div>
    </section>
    <section class="stage" id="stage"></section>
    <div class="note" id="note"></div>
  </main>
  <script>
    const replay = __DATA_JSON__;
    let currentLap = 1;
    let playing = false;
    let timer = null;
    const slider = document.getElementById("lapSlider");
    const label = document.getElementById("lapLabel");
    const stage = document.getElementById("stage");
    const note = document.getElementById("note");
    const playButton = document.getElementById("playButton");
    const statusChip = document.getElementById("statusChip");
    const compoundColours = {S:"#ff4560", M:"#ffd12e", H:"#f4f7fb", I:"#39ff8f", W:"#25a7ff"};
    const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
    const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
    function frameFor(driver, lap) {
      let chosen = driver.frames[0] || {lap:1, position:driver.final_position, gap:0, time:0, compound:""};
      for (const frame of driver.frames) {
        if (frame.lap > lap) break;
        chosen = frame;
      }
      return chosen;
    }
    function renderRace(lap) {
      const drivers = replay.drivers.slice(0, 14).map((driver) => ({driver, frame: frameFor(driver, lap)}))
        .sort((a, b) => a.frame.position - b.frame.position);
      stage.innerHTML = drivers.map((item) => {
        const gap = Number(item.frame.gap || 0);
        const left = clamp(88 - (gap / Math.max(1, replay.max_gap)) * 74, 8, 90);
        const compound = item.frame.compound || "";
        return `<div class="race-row">
          <div><span class="driver-code">${esc(item.driver.code)}</span><br><span style="color:#9ca8bd;font-size:.72rem">P${esc(item.frame.position)}</span></div>
          <div class="track"><span class="car" style="left:${left}%;background:${esc(item.driver.colour)};color:${esc(item.driver.colour)}"></span></div>
          <div class="meta">${Number(item.frame.time || 0).toFixed(3)}s<br><span class="${item.frame.pit ? "pit" : ""}">${item.frame.pit ? "PIT · " : ""}${esc(compound)} ${gap ? "+" + gap.toFixed(1) + "s" : "Leader"}</span></div>
        </div>`;
      }).join("");
      note.textContent = "Race pace replay: car position is based on gap to the race leader for the selected lap. Pit laps are highlighted in yellow.";
    }
    function renderTyre(lap) {
      const tyre = replay.tyre;
      if (!tyre || !tyre.ages?.length) {
        stage.innerHTML = `<div class="note">Not enough clean same-compound laps for a stable tyre replay.</div>`;
        note.textContent = "Try another driver or compound-rich race.";
        return;
      }
      const shown = tyre.ages.map((age, index) => ({age, actual: tyre.actual[index], predicted: tyre.predicted[index]})).filter((p) => p.age <= lap);
      const points = shown.length ? shown : [{age:tyre.ages[0], actual:tyre.actual[0], predicted:tyre.predicted[0]}];
      const allY = [...tyre.actual, ...tyre.predicted].filter(Number.isFinite);
      const minAge = Math.min(...tyre.ages), maxAge = Math.max(...tyre.ages);
      const minY = Math.min(...allY) - .2, maxY = Math.max(...allY) + .2;
      const x = (age) => 60 + ((age - minAge) / Math.max(1, maxAge - minAge)) * 820;
      const y = (time) => 320 - ((time - minY) / Math.max(.1, maxY - minY)) * 260;
      const circles = points.map((p) => `<circle cx="${x(p.age)}" cy="${y(p.actual)}" r="5" fill="#00e5ff"><title>Age ${p.age} · ${Number(p.actual).toFixed(3)}s</title></circle>`).join("");
      const line = tyre.ages.map((age, index) => `${index ? "L" : "M"} ${x(age)} ${y(tyre.predicted[index])}`).join(" ");
      stage.innerHTML = `<svg viewBox="0 0 940 360" role="img" aria-label="Tyre degradation replay">
        <rect x="0" y="0" width="940" height="360" rx="18" fill="#090e18"/>
        <text x="60" y="34" fill="#f5f7fb" font-size="18" font-weight="900">${esc(tyre.driver)} · ${esc(tyre.compound)} tyre model</text>
        <text x="60" y="56" fill="#9ca8bd" font-size="13">RMSE ${Number(tyre.rmse).toFixed(3)}s · lower is faster</text>
        <path d="${line}" fill="none" stroke="#39ff8f" stroke-width="3"/>
        ${circles}
        <text x="60" y="342" fill="#9ca8bd" font-size="12">Tyre age</text>
        <text x="800" y="342" fill="#9ca8bd" font-size="12">Older tyre</text>
      </svg>`;
      note.textContent = tyre.interpretation || "Tyre replay shows clean lap observations against the fitted degradation curve.";
    }
    function renderPitTimeline(lap) {
      const drivers = replay.drivers.slice(0, 14);
      stage.innerHTML = drivers.map((driver) => {
        const stints = (driver.stints || []).map((stint) => {
          const colour = compoundColours[stint.compound] || driver.colour || "#00e5ff";
          return `<span class="stint" title="${esc(stint.compound)} L${stint.start_lap}-${stint.end_lap}" style="flex:${stint.laps || 1};background:${colour}"></span>`;
        }).join("");
        const cursorLeft = clamp((lap / Math.max(1, replay.total_laps)) * 100, 0, 100);
        const pits = (driver.pit_laps || []).filter((pitLap) => pitLap <= lap).join(", ") || "none yet";
        return `<div class="timeline-row">
          <div><span class="driver-code">${esc(driver.code)}</span><br><span style="color:#9ca8bd;font-size:.72rem">pits ${esc(pits)}</span></div>
          <div class="timeline">${stints}<span class="cursor" style="left:${cursorLeft}%"></span></div>
        </div>`;
      }).join("");
      note.textContent = "Pit timeline replay: tyre compound blocks reveal as the lap slider moves. The white marker is the current lap.";
    }
    function render(lap) {
      currentLap = clamp(Number(lap), 1, Number(replay.total_laps || 1));
      slider.value = currentLap;
      label.textContent = `Lap ${currentLap}`;
      statusChip.textContent = `${replay.race} · Lap ${currentLap}/${replay.total_laps}`;
      if (replay.type === "tyre_degradation") renderTyre(currentLap);
      else if (replay.type === "pit_timeline") renderPitTimeline(currentLap);
      else renderRace(currentLap);
    }
    function togglePlay() {
      playing = !playing;
      playButton.textContent = playing ? "Pause" : "Play";
      if (timer) clearInterval(timer);
      if (playing) {
        timer = setInterval(() => {
          const next = currentLap >= replay.total_laps ? 1 : currentLap + 1;
          render(next);
        }, 360);
      }
    }
    slider.addEventListener("input", () => render(slider.value));
    playButton.addEventListener("click", togglePlay);
    render(1);
  </script>
</body>
</html>
"""
        output_path.write_text(
            template
            .replace("__PAGE_TITLE__", html.escape(f"{title} | {race_name}"))
            .replace("__TITLE__", html.escape(title))
            .replace("__RACE__", html.escape(race_name))
            .replace("__TOTAL_LAPS__", str(total_laps))
            .replace("__DATA_JSON__", json.dumps(_jsonable(payload), ensure_ascii=False)),
            encoding="utf-8",
        )
        return output_path

    @staticmethod
    def _report_summary(key: str, race_name: str, comparison: dict[str, Any]) -> str:
        driver_a = comparison["driver_a"]["driver_code"]
        driver_b = comparison["driver_b"]["driver_code"]
        if key == "pdf":
            return f"PDF report for {race_name}: executive strategy summary, {driver_a} vs {driver_b} battle notes, full-grid ranking, and modelling assumptions."
        if key == "markdown":
            return f"Markdown report for {race_name}: GitHub-friendly post-race write-up with the full-grid table and driver battle verdict."
        if key == "csv":
            return f"CSV summary for {race_name}: all-driver metrics ready for spreadsheet filtering, sorting, or portfolio screenshots."
        return f"Complete report pack for {race_name}, including PDF, Markdown, and CSV outputs."

    def _summary_records(self, summary: pd.DataFrame) -> list[dict[str, Any]]:
        columns = [
            "final_position",
            "driver_code",
            "driver_name",
            "team",
            "average_clean_pace",
            "fastest_lap",
            "consistency_score",
            "tyre_management_score",
            "pit_stops",
            "race_engineer_score",
            "badge_earned",
            "rating",
        ]
        return summary[columns].to_dict(orient="records")

    def analyze(self, race_name: str, driver_code: str, comparison_code: str, season: int = 2026) -> dict[str, Any]:
        track_map = self._load_track_map(race_name, season)
        race = self._load_race(race_name, season)
        if not race["ok"]:
            race["track_map"] = track_map
            return race

        results = race["results"]
        race_laps = race["race_laps"]
        summary = race["summary"]
        driver_code = driver_code.upper()
        comparison_code = comparison_code.upper()
        if driver_code not in results:
            raise ValueError(f"Driver data not available for {driver_code}.")
        if comparison_code not in results:
            raise ValueError(f"Driver data not available for {comparison_code}.")

        comparison = compare_drivers(results, driver_code, comparison_code)
        tyre_fit = self._tyre_fit(race_laps, results, driver_code)
        selected = results[driver_code]
        return {
            "ok": True,
            "status": "completed",
            "race_name": race_name,
            "circuit": str(race_laps["circuit"].iloc[0]),
            "total_laps": int(race_laps["total_laps"].iloc[0]),
            "season": season,
            "track_map": track_map,
            "result": selected,
            "comparison": {
                "average_pace_difference_sec": comparison["average_pace_difference_sec"],
                "faster_driver": comparison["faster_driver"],
                "more_consistent_driver": comparison["more_consistent_driver"],
                "better_tyre_manager": comparison["better_tyre_manager"],
                "better_final_position": comparison["better_final_position"],
                "verdict": comparison["verdict"],
            },
            "tyre_fit": None if tyre_fit is None else {
                "driver_code": tyre_fit["driver_code"],
                "compound": tyre_fit["compound"],
                "base_pace": tyre_fit["base_pace"],
                "linear_degradation": tyre_fit["linear_degradation"],
                "quadratic_degradation": tyre_fit["quadratic_degradation"],
                "rmse": tyre_fit["rmse"],
                "interpretation": tyre_fit["interpretation"],
            },
            "summary": self._summary_records(summary),
            "traces": {
                driver_code: self._driver_trace(race_laps, driver_code),
                comparison_code: self._driver_trace(race_laps, comparison_code),
            },
            "strategy": self._strategy_rows(race_laps, results),
            "strategy_insights": self._strategy_insights(
                race_laps,
                results,
                comparison,
                driver_code,
                comparison_code,
            ),
        }

    def generate_plots(
        self,
        race_name: str,
        driver_code: str,
        comparison_code: str,
        season: int = 2026,
        plot_key: str = "all",
    ) -> dict[str, Any]:
        if not callable(generate_dashboard):
            return {
                "ok": False,
                "status": "error",
                "message": "Plot generation is unavailable in this runtime because Matplotlib is not installed.",
            }
        race = self._load_race(race_name, season)
        if not race["ok"]:
            return race
        results = race["results"]
        race_laps = race["race_laps"]
        summary = race["summary"]
        comparison = compare_drivers(results, driver_code.upper(), comparison_code.upper())
        tyre_fit = self._tyre_fit(race_laps, results, driver_code.upper())
        plots = generate_dashboard(summary, results, race_laps, comparison, tyre_fit, ROOT_DIR / "outputs" / "plots")
        payloads = []
        for path in plots:
            key = _plot_key_from_name(path.name)
            if plot_key != "all" and key != plot_key:
                continue
            payloads.append(self._file_payload(
                path,
                key,
                PLOT_CATALOG,
                self._plot_summary(key, summary, results, comparison, tyre_fit),
                "plot",
            ))
        return {
            "ok": True,
            "message": f"Generated {len(payloads)} Matplotlib plot output(s).",
            "files": payloads,
            "catalog": PLOT_CATALOG,
        }

    def generate_replays(
        self,
        race_name: str,
        driver_code: str,
        season: int = 2026,
        replay_key: str = "all",
    ) -> dict[str, Any]:
        race = self._load_race(race_name, season)
        if not race["ok"]:
            return race
        results = race["results"]
        race_laps = race["race_laps"]
        tyre_fit = self._tyre_fit(race_laps, results, driver_code.upper())
        requested = ["race_pace", "tyre_degradation", "pit_timeline"] if replay_key == "all" else [replay_key]
        requested = [key for key in requested if key in {"race_pace", "tyre_degradation", "pit_timeline"}]
        files = []
        messages = []
        for key in requested:
            path = self._write_browser_replay(key, race_name, driver_code.upper(), race_laps, results, tyre_fit)
            detail = "Generated lightweight browser-native replay for Render-friendly preview."
            payload = self._file_payload(
                path,
                key,
                REPLAY_CATALOG,
                self._replay_summary(key, race_name, driver_code.upper(), False, detail),
                "replay",
            )
            payload["used_fallback"] = False
            payload["detail"] = detail
            files.append(payload)
            messages.append(f"{REPLAY_CATALOG[key]['title']} ready")
        return {
            "ok": True,
            "message": "; ".join(messages),
            "files": files,
            "catalog": REPLAY_CATALOG,
        }

    def export_report(
        self,
        race_name: str,
        driver_code: str,
        comparison_code: str,
        season: int = 2026,
        report_key: str = "pdf",
    ) -> dict[str, Any]:
        race = self._load_race(race_name, season)
        if not race["ok"]:
            return race
        results = race["results"]
        race_laps = race["race_laps"]
        summary = race["summary"]
        comparison = compare_drivers(results, driver_code.upper(), comparison_code.upper())
        reports = write_reports(summary, results, comparison, self._tyre_fit(race_laps, results, driver_code.upper()), ROOT_DIR / "outputs" / "reports")
        files = []
        for path in reports.values():
            key = _report_key_from_name(path.name)
            if report_key != "all" and key != report_key:
                continue
            files.append(self._file_payload(
                path,
                key,
                REPORT_CATALOG,
                self._report_summary(key, race_name, comparison),
                "report",
            ))
        return {
            "ok": True,
            "message": f"Exported {len(files)} report file(s).",
            "files": files,
            "catalog": REPORT_CATALOG,
        }


WEB_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pit Wall Predictor Web</title>
  <style>
    :root {
      --bg: #f5f5f7;
      --panel: rgba(255, 255, 255, 0.86);
      --panel-solid: #ffffff;
      --line: rgba(15, 23, 42, 0.08);
      --text: #0f172a;
      --muted: #5b6475;
      --cyan: #0a84ff;
      --green: #1fbf75;
      --yellow: #c68a00;
      --red: #d92d20;
      --shadow: 0 22px 60px rgba(15, 23, 42, 0.08);
      color-scheme: light;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      overflow-x: hidden;
      background:
        linear-gradient(116deg, rgba(10, 132, 255, 0.08) 0 12%, transparent 12% 100%),
        repeating-linear-gradient(90deg, rgba(15, 23, 42, 0.032) 0 1px, transparent 1px 58px),
        repeating-linear-gradient(0deg, rgba(15, 23, 42, 0.025) 0 1px, transparent 1px 58px),
        linear-gradient(180deg, #f8f9fc 0%, #eff1f6 100%);
      color: var(--text);
    }

    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image:
        linear-gradient(45deg, rgba(15, 23, 42, 0.045) 25%, transparent 25%, transparent 75%, rgba(15, 23, 42, 0.045) 75%),
        linear-gradient(45deg, rgba(15, 23, 42, 0.045) 25%, transparent 25%, transparent 75%, rgba(15, 23, 42, 0.045) 75%);
      background-position: 0 0, 16px 16px;
      background-size: 32px 32px;
      mask-image: linear-gradient(to bottom, black, transparent 84%);
    }

    a { color: inherit; }

    .shell {
      width: min(1480px, calc(100vw - 28px));
      margin: 0 auto;
      padding: 18px 0 36px;
    }

    .site-header {
      position: sticky;
      top: 0;
      z-index: 80;
      padding: 10px 0 0;
      backdrop-filter: blur(18px);
    }

    .header-shell {
      position: relative;
      overflow: hidden;
      isolation: isolate;
      border: 1px solid var(--line);
      border-radius: 28px;
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(255, 255, 255, 0.82));
      box-shadow: var(--shadow);
      padding: 10px 16px 10px;
      display: grid;
      gap: 6px;
    }

    .header-shell > :not(.header-mark) {
      position: relative;
      z-index: 1;
    }

    .header-mark {
      position: absolute;
      right: 12px;
      top: 50%;
      transform: translateY(-50%);
      width: min(180px, 26vw);
      height: auto;
      z-index: 0;
      opacity: 0.16;
      color: #111827;
      pointer-events: none;
      user-select: none;
      filter: saturate(1.12) drop-shadow(0 10px 22px rgba(10, 132, 255, 0.12));
    }

    .header-top {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
    }

    .header-brand {
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      gap: 10px;
      min-width: 0;
    }

    .site-title {
      margin: 0;
      font-size: clamp(2rem, 3.4vw, 3.1rem);
      line-height: 0.9;
      letter-spacing: 0;
      font-weight: 950;
    }

    .header-actions {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      flex-wrap: wrap;
      gap: 10px;
    }

    .hero {
      border: 1px solid var(--line);
      border-radius: 32px;
      background:
        linear-gradient(112deg, rgba(10, 132, 255, 0.12) 0 18%, transparent 18% 100%),
        linear-gradient(180deg, rgba(255, 255, 255, 0.90), rgba(255, 255, 255, 0.78));
      box-shadow: var(--shadow);
      backdrop-filter: blur(24px);
      overflow: visible;
      position: relative;
      z-index: 12;
      margin-top: 8px;
      padding: 14px 18px 14px;
    }

    .hero::before {
      content: "";
      position: absolute;
      inset: auto 18px 0 18px;
      height: 10px;
      background-image:
        linear-gradient(45deg, rgba(15, 23, 42, 0.18) 25%, transparent 25%, transparent 75%, rgba(15, 23, 42, 0.18) 75%),
        linear-gradient(45deg, rgba(15, 23, 42, 0.18) 25%, transparent 25%, transparent 75%, rgba(15, 23, 42, 0.18) 75%);
      background-position: 0 0, 8px 8px;
      background-size: 16px 16px;
      opacity: 0.46;
      pointer-events: none;
    }

    .hero::after {
      content: "PIT WALL";
      position: absolute;
      right: -18px;
      top: -44px;
      font-size: clamp(4rem, 12vw, 11rem);
      font-weight: 950;
      letter-spacing: -0.08em;
      color: rgba(15, 23, 42, 0.035);
      pointer-events: none;
    }

    .eyebrow {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border: 1px solid rgba(10, 132, 255, 0.18);
      border-radius: 999px;
      background: rgba(10, 132, 255, 0.08);
      color: #0a84ff;
      font-size: 0.73rem;
      font-weight: 800;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }

    h1 {
      margin: 12px 0 8px;
      font-size: clamp(2.1rem, 4.8vw, 4.6rem);
      line-height: 0.9;
      letter-spacing: -0.075em;
    }

    .subtitle {
      max-width: 920px;
      color: var(--muted);
      font-size: 0.98rem;
      line-height: 1.55;
      margin: 0;
    }

    .hero-rail {
      display: grid;
      justify-items: end;
      gap: 12px;
    }

    .page-nav {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      justify-content: flex-end;
    }

    .page-link {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 10px 14px;
      border: 1px solid transparent;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.72);
      color: var(--muted);
      text-decoration: none;
      cursor: pointer;
      font-size: 0.82rem;
      font-weight: 800;
      letter-spacing: 0.04em;
      transition: transform 160ms ease, border-color 160ms ease, background 160ms ease, color 160ms ease;
    }

    .page-link:hover {
      transform: translateY(-1px);
      color: var(--text);
      border-color: var(--line);
      background: #ffffff;
    }

    body[data-page="overview"] .page-link[href="/overview"],
    body[data-page="analysis"] .page-link[href="/analysis"],
    body[data-page="strategy"] .page-link[href="/strategy"],
    body[data-page="exports"] .page-link[href="/exports"] {
      background: linear-gradient(135deg, #0a84ff, #0066d6);
      border-color: rgba(10, 132, 255, 0.42);
      color: #ffffff;
      box-shadow: 0 12px 28px rgba(10, 132, 255, 0.22);
    }

    .theme-toggle {
      width: auto;
      flex: 0 0 auto;
      min-width: 44px;
      padding: 10px 12px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-size: 1rem;
      line-height: 1;
    }

    .theme-toggle .theme-icon {
      font-size: 1.05rem;
      line-height: 1;
    }

    .status-chip {
      border: 1px solid rgba(57, 255, 143, 0.38);
      background: rgba(57, 255, 143, 0.12);
      color: #15803d;
      padding: 8px 12px;
      border-radius: 999px;
      font-weight: 900;
      letter-spacing: 0.08em;
      font-size: 0.72rem;
      text-transform: uppercase;
      white-space: nowrap;
    }

    .status-chip.warn {
      border-color: rgba(198, 138, 0, 0.28);
      background: rgba(198, 138, 0, 0.10);
      color: #9a6400;
    }

    .control-deck {
      display: grid;
      grid-template-columns: repeat(4, minmax(150px, 1fr));
      gap: 10px;
      padding: 12px 0 0;
      position: relative;
      z-index: 1;
      align-items: end;
    }

    .control-group {
      display: grid;
      gap: 5px;
      min-width: 0;
    }

    .race-picker {
      position: relative;
      min-width: 0;
      z-index: 22;
    }

    .race-picker--open {
      z-index: 120;
    }

    .race-toggle {
      display: flex;
      align-items: center;
      gap: 12px;
      width: 100%;
      min-height: 50px;
      padding: 10px 14px;
      border: 1px solid rgba(255, 255, 255, 0.10);
      border-radius: 16px;
      background: linear-gradient(180deg, rgba(17, 24, 39, 0.95), rgba(11, 16, 27, 0.92));
      color: #f5f7fb;
      font: inherit;
      appearance: none;
      -webkit-appearance: none;
      text-align: left;
      cursor: pointer;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08), 0 14px 30px rgba(15, 23, 42, 0.20);
    }

    .race-toggle:hover {
      transform: translateY(-1px);
      border-color: rgba(0, 229, 255, 0.30);
      background: linear-gradient(180deg, rgba(20, 29, 48, 0.98), rgba(11, 16, 27, 0.95));
    }

    .race-toggle:focus {
      border-color: rgba(10, 132, 255, 0.78);
      box-shadow: 0 0 0 4px rgba(10, 132, 255, 0.14);
    }

    .race-toggle-copy {
      min-width: 0;
      flex: 1 1 auto;
      display: grid;
    }

    .race-toggle-kicker {
      display: none;
      color: rgba(215, 223, 236, 0.76);
      font-size: 0.64rem;
      font-weight: 900;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .race-toggle-label {
      display: block;
      font-size: 0.95rem;
      font-weight: 850;
      line-height: 1.08;
      color: #f5f7fb;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .race-toggle-caret {
      flex: 0 0 auto;
      margin-left: auto;
      color: rgba(215, 223, 236, 0.72);
      font-size: 0.82rem;
      line-height: 1;
      opacity: 0.8;
    }

    .race-menu {
      position: absolute;
      left: 0;
      right: 0;
      top: calc(100% + 8px);
      z-index: 90;
      display: grid;
      gap: 6px;
      max-height: min(54vh, 500px);
      overflow: auto;
      overscroll-behavior: contain;
      padding: 8px;
      border: 1px solid rgba(255, 255, 255, 0.10);
      border-radius: 20px;
      background: rgba(11, 16, 27, 0.96);
      box-shadow: 0 24px 58px rgba(15, 23, 42, 0.34);
      backdrop-filter: blur(18px);
      color: #f5f7fb;
    }

    .race-menu[hidden] {
      display: none;
    }

    .race-menu-item {
      display: flex;
      align-items: center;
      gap: 10px;
      width: 100%;
      min-width: 0;
      padding: 10px 12px;
      border: 1px solid transparent;
      border-radius: 14px;
      background: transparent;
      color: #f5f7fb;
      font: inherit;
      appearance: none;
      -webkit-appearance: none;
      cursor: pointer;
      text-align: left;
      justify-content: flex-start;
    }

    .race-menu-item:hover {
      transform: none;
      border-color: rgba(0, 229, 255, 0.20);
      background: rgba(10, 132, 255, 0.12);
    }

    .race-menu-item[aria-selected="true"] {
      border-color: rgba(0, 229, 255, 0.26);
      background: linear-gradient(135deg, rgba(10, 132, 255, 0.22), rgba(255, 255, 255, 0.06));
      box-shadow: inset 0 0 0 1px rgba(0, 229, 255, 0.16);
    }

    .race-menu-flag {
      width: 34px;
      height: 34px;
      border-radius: 10px;
      display: grid;
      place-items: center;
      flex: 0 0 auto;
      background: rgba(15, 23, 42, 0.08);
      font-size: 1.05rem;
      line-height: 1;
    }

    .race-menu-flag--team {
      padding: 5px;
      border: 1px solid rgba(255, 255, 255, 0.12);
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.16);
    }

    .race-menu-copy {
      min-width: 0;
      flex: 1 1 auto;
      display: grid;
      gap: 2px;
    }

    .race-menu-copy strong {
      display: block;
      font-size: 0.86rem;
      line-height: 1.1;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .race-menu-copy span {
      color: rgba(215, 223, 236, 0.82);
      font-size: 0.72rem;
      line-height: 1.1;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .race-menu-status {
      flex: 0 0 auto;
      padding: 5px 8px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.08);
      color: #d7dfec;
      font-size: 0.64rem;
      font-weight: 900;
      letter-spacing: 0.10em;
      text-transform: uppercase;
      white-space: nowrap;
    }

    .select-shell {
      position: relative;
      border: 1px solid var(--line);
      border-radius: 16px;
      background: rgba(255, 255, 255, 0.88);
      overflow: hidden;
      min-height: 50px;
      display: flex;
      align-items: stretch;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.2);
    }

    .select-shell::before {
      content: "";
      position: absolute;
      inset: 0;
      background: linear-gradient(135deg, rgba(10, 132, 255, 0.07), transparent 42%);
      pointer-events: none;
    }

    .select-shell:focus-within {
      border-color: rgba(10, 132, 255, 0.72);
      box-shadow: 0 0 0 4px rgba(10, 132, 255, 0.12);
    }

    .select-icon {
      position: absolute;
      left: 12px;
      top: 50%;
      transform: translateY(-50%);
      width: 30px;
      height: 30px;
      border-radius: 10px;
      display: grid;
      place-items: center;
      overflow: hidden;
      z-index: 1;
      pointer-events: none;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.24);
    }

    .race-toggle .select-icon {
      position: static;
      transform: none;
      flex: 0 0 32px;
      width: 32px;
      height: 32px;
      z-index: auto;
      font-size: 0.72rem;
      font-weight: 950;
      letter-spacing: 0;
    }

    .select-icon img {
      width: 100%;
      height: 100%;
      object-fit: contain;
      display: block;
    }

    .select-icon--flag {
      font-size: 1.05rem;
      line-height: 1;
      background: linear-gradient(135deg, #0f172a, #1e293b);
      color: #ffffff;
    }

    .select-icon--team {
      padding: 4px;
      border: 1px solid rgba(255, 255, 255, 0.14);
    }

    .control-select {
      position: relative;
      z-index: 2;
      width: 100%;
      border: 0;
      background: transparent;
      padding: 11px 34px 11px 54px;
      appearance: none;
      -webkit-appearance: none;
      -moz-appearance: none;
      min-width: 0;
    }

    .control-select:focus {
      box-shadow: none;
      border-color: transparent;
    }

    .control-meta {
      min-height: 58px;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: rgba(255, 255, 255, 0.76);
      padding: 8px 10px;
      display: grid;
      align-content: center;
      gap: 7px;
      overflow: hidden;
    }

    .control-meta-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 10px;
      min-width: 0;
    }

    .control-meta-label {
      color: var(--muted);
      font-size: 0.62rem;
      font-weight: 900;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      white-space: nowrap;
    }

    .control-meta-number {
      flex: 0 0 auto;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 42px;
      padding: 5px 8px;
      border-radius: 999px;
      font-size: 0.72rem;
      font-weight: 950;
      letter-spacing: 0.08em;
    }

    .control-meta-body {
      display: flex;
      align-items: center;
      gap: 10px;
      min-width: 0;
    }

    .control-meta-logo {
      width: 44px;
      height: 20px;
      flex: 0 0 auto;
      filter: drop-shadow(0 8px 12px rgba(0, 0, 0, 0.15));
    }

    .control-meta-logo img,
    .race-menu-flag img,
    .select-icon img {
      width: 100%;
      height: 100%;
      object-fit: contain;
      display: block;
    }

    .control-meta-logo--fallback {
      display: grid;
      place-items: center;
      border-radius: 8px;
      font-size: 0.68rem;
      font-weight: 950;
      letter-spacing: 0.08em;
    }

    .control-meta-text {
      min-width: 0;
    }

    .control-meta-text strong {
      display: block;
      font-size: 0.82rem;
      line-height: 1.08;
      margin: 0;
      text-wrap: balance;
    }

    .control-meta-text span {
      display: block;
      margin-top: 2px;
      color: var(--muted);
      font-size: 0.72rem;
      line-height: 1.1;
    }

    label {
      display: block;
      color: var(--muted);
      font-size: 0.72rem;
      font-weight: 900;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      margin: 0;
    }

    select, button {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 16px;
      background: rgba(255, 255, 255, 0.88);
      color: var(--text);
      padding: 11px 14px;
      font: inherit;
      outline: none;
    }

    select:focus, button:focus {
      border-color: rgba(10, 132, 255, 0.72);
      box-shadow: 0 0 0 4px rgba(10, 132, 255, 0.12);
    }

    button {
      cursor: pointer;
      font-weight: 900;
      letter-spacing: 0.02em;
      transition: transform 160ms ease, border-color 160ms ease, background 160ms ease;
    }

    button:hover {
      transform: translateY(-1px);
      border-color: rgba(15, 23, 42, 0.16);
      background: rgba(15, 23, 42, 0.04);
    }

    .primary-button {
      border: 1px solid rgba(10, 132, 255, 0.58);
      background: linear-gradient(135deg, rgba(10, 132, 255, 0.08), rgba(10, 132, 255, 0.18));
      color: #ffffff;
      box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.10) inset, 0 18px 34px rgba(10, 132, 255, 0.16);
    }

    .primary-button:hover {
      border-color: rgba(10, 132, 255, 0.82);
      background: linear-gradient(135deg, rgba(10, 132, 255, 0.12), rgba(10, 132, 255, 0.26));
    }

    .main-grid {
      display: grid;
      grid-template-columns: minmax(300px, 0.9fr) minmax(300px, 0.9fr) minmax(380px, 1.4fr);
      gap: 14px;
      margin-top: 16px;
    }

    .panel {
      border: 1px solid var(--line);
      border-radius: 26px;
      background: var(--panel);
      box-shadow: var(--shadow);
      backdrop-filter: blur(18px);
      overflow: hidden;
    }

    .panel-header {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      padding: 18px 18px 0;
    }

    .panel-title {
      font-size: 0.86rem;
      font-weight: 950;
      letter-spacing: 0.16em;
      color: #0f172a;
      text-transform: uppercase;
    }

    .panel-body { padding: 18px; }

    .driver-panel-body {
      padding: 12px 12px 12px;
    }

    .source-link {
      color: #0a84ff;
      font-size: 0.75rem;
      font-weight: 900;
      letter-spacing: 0.08em;
      text-decoration: none;
      text-transform: uppercase;
    }

    .source-link:hover { color: #0066d6; }

    .page-module {
      margin-top: 8px;
    }

    .page-module--overview {
      display: block;
    }

    body[data-page="overview"] .page-module--analysis,
    body[data-page="overview"] .page-module--strategy,
    body[data-page="overview"] .page-module--exports {
      display: none;
    }

    body[data-page="analysis"] .page-module--overview,
    body[data-page="analysis"] .page-module--strategy,
    body[data-page="analysis"] .page-module--exports {
      display: none;
    }

    body[data-page="strategy"] .page-module--overview,
    body[data-page="strategy"] .page-module--analysis,
    body[data-page="strategy"] .page-module--exports {
      display: none;
    }

    body[data-page="exports"] .page-module--overview,
    body[data-page="exports"] .page-module--analysis,
    body[data-page="exports"] .page-module--strategy {
      display: none;
    }

    body[data-page="overview"] .main-grid,
    body[data-page="overview"] .wide-grid {
      display: none;
    }

    body[data-page="analysis"] .wide-grid {
      display: none;
    }

    body[data-page="strategy"] .overview-grid,
    body[data-page="strategy"] .main-grid {
      display: none;
    }

    body[data-page="strategy"] .wide-grid--secondary {
      grid-template-columns: 1fr;
    }

    body[data-page="strategy"] .wide-grid--secondary > section:last-child {
      display: none;
    }

    body[data-page="exports"] .overview-grid,
    body[data-page="exports"] .main-grid,
    body[data-page="exports"] .wide-grid {
      display: none;
    }

    .overview-grid {
      display: grid;
      grid-template-columns: minmax(0, 1.08fr) minmax(300px, 0.92fr);
      gap: 12px;
      align-items: stretch;
    }

    .overview-hero {
      grid-column: 1 / -1;
      padding: 0;
      min-height: 360px;
      display: grid;
      grid-template-columns: minmax(0, 1.05fr) minmax(340px, 0.95fr);
      gap: 0;
      position: relative;
      overflow: hidden;
    }

    .overview-hero::before {
      content: "";
      position: absolute;
      inset: 0;
      background:
        linear-gradient(118deg, transparent 0 66%, rgba(10, 132, 255, 0.10) 66% 67%, transparent 67% 100%),
        repeating-linear-gradient(135deg, rgba(15, 23, 42, 0.035) 0 1px, transparent 1px 18px);
      pointer-events: none;
    }

    .overview-hero-copy {
      position: relative;
      z-index: 1;
      padding: 24px;
      display: grid;
      align-content: center;
      gap: 14px;
    }

    .overview-headline {
      margin: 0;
      font-size: 3rem;
      line-height: 1.02;
      letter-spacing: 0;
      max-width: 13ch;
    }

    .overview-copy {
      color: var(--muted);
      line-height: 1.5;
      max-width: 56ch;
      margin: 0;
      font-size: 0.96rem;
    }

    .overview-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 2px;
    }

    .overview-button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 10px 14px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.86);
      color: var(--text);
      text-decoration: none;
      font-weight: 800;
      transition: transform 160ms ease, border-color 160ms ease, background 160ms ease;
    }

    .overview-button::after {
      content: ">";
      margin-left: 10px;
      color: #0a84ff;
      font-weight: 950;
    }

    .overview-button:hover {
      transform: translateY(-1px);
      border-color: rgba(10, 132, 255, 0.28);
      background: #ffffff;
    }

    .overview-quickline {
      border-left: 4px solid #0a84ff;
      padding: 10px 0 10px 14px;
      margin-top: 4px;
      background: linear-gradient(90deg, rgba(10, 132, 255, 0.08), transparent);
    }

    .race-visual {
      position: relative;
      min-height: 360px;
      overflow: hidden;
      border-left: 1px solid var(--line);
      background:
        linear-gradient(112deg, rgba(15, 23, 42, 0.08) 0 12%, transparent 12% 100%),
        repeating-linear-gradient(90deg, rgba(15, 23, 42, 0.045) 0 1px, transparent 1px 44px),
        linear-gradient(145deg, rgba(255, 255, 255, 0.34), rgba(255, 255, 255, 0.04));
    }

    .race-visual::before {
      content: "";
      position: absolute;
      top: 22px;
      right: 22px;
      width: 118px;
      height: 118px;
      border: 16px solid rgba(15, 23, 42, 0.10);
      border-right-color: rgba(10, 132, 255, 0.38);
      border-bottom-color: rgba(217, 45, 32, 0.28);
      border-radius: 50%;
    }

    .race-visual::after {
      content: "";
      position: absolute;
      inset: auto 0 0 0;
      height: 48px;
      background-image:
        linear-gradient(45deg, rgba(15, 23, 42, 0.18) 25%, transparent 25%, transparent 75%, rgba(15, 23, 42, 0.18) 75%),
        linear-gradient(45deg, rgba(15, 23, 42, 0.18) 25%, transparent 25%, transparent 75%, rgba(15, 23, 42, 0.18) 75%);
      background-position: 0 0, 14px 14px;
      background-size: 28px 28px;
      opacity: 0.35;
    }

    .mini-car {
      position: absolute;
      left: 44px;
      right: 34px;
      top: 88px;
      height: 118px;
      transform: skewX(-8deg);
    }

    .mini-car-body {
      position: absolute;
      left: 12%;
      right: 10%;
      top: 36px;
      height: 44px;
      border-radius: 18px 34px 16px 22px;
      background: linear-gradient(135deg, #d92d20, #0a84ff 70%, #061017);
      box-shadow: 0 20px 46px rgba(15, 23, 42, 0.20);
    }

    .mini-car-body::before {
      content: "";
      position: absolute;
      left: 34%;
      top: -22px;
      width: 108px;
      height: 34px;
      border-radius: 50% 50% 18px 18px;
      background: rgba(6, 16, 23, 0.86);
      border: 2px solid rgba(255, 255, 255, 0.72);
    }

    .mini-car-wing {
      position: absolute;
      left: 0;
      right: 0;
      height: 16px;
      border-radius: 999px;
      background: #061017;
      box-shadow: inset 0 0 0 2px rgba(255, 255, 255, 0.08);
    }

    .mini-car-wing.front { top: 18px; }
    .mini-car-wing.rear { bottom: 16px; }

    .mini-wheel {
      position: absolute;
      top: 20px;
      width: 44px;
      height: 78px;
      border-radius: 18px;
      background: #050811;
      border: 4px solid rgba(255, 255, 255, 0.88);
      box-shadow: inset 0 0 0 8px #1f2937;
    }

    .mini-wheel.front-left { left: 8%; }
    .mini-wheel.front-right { right: 8%; }
    .mini-wheel.rear-left { left: 26%; top: 64px; }
    .mini-wheel.rear-right { right: 26%; top: 64px; }

    .tyre-stack {
      position: absolute;
      right: 22px;
      bottom: 66px;
      display: grid;
      grid-template-columns: repeat(2, 42px);
      gap: 8px;
      z-index: 2;
    }

    .tyre {
      width: 42px;
      height: 42px;
      border-radius: 50%;
      border: 8px solid #061017;
      background: #f8fafc;
      box-shadow: inset 0 0 0 3px currentColor, 0 10px 20px rgba(15, 23, 42, 0.14);
    }

    .tyre-soft { color: #d92d20; }
    .tyre-medium { color: #c68a00; }
    .tyre-hard { color: #d1d5db; }
    .tyre-inter { color: #1fbf75; }

    .overview-feature-wall {
      border-left: 1px solid var(--line);
      background:
        linear-gradient(180deg, rgba(255, 255, 255, 0.72), rgba(255, 255, 255, 0.52)),
        linear-gradient(110deg, rgba(10, 132, 255, 0.06), transparent 38%),
        linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(255, 255, 255, 0.72));
      padding: 18px;
      display: grid;
      gap: 12px;
      align-content: start;
      position: relative;
      overflow: hidden;
    }

    .overview-feature-wall::before {
      content: "";
      position: absolute;
      inset: auto 14px 14px;
      height: 72px;
      border-radius: 20px;
      background:
        linear-gradient(90deg, rgba(10, 132, 255, 0.10), rgba(217, 45, 32, 0.08)),
        repeating-linear-gradient(90deg, rgba(15, 23, 42, 0.04) 0 1px, transparent 1px 18px);
      pointer-events: none;
    }

    .feature-strip {
      position: relative;
      z-index: 1;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }

    .brand-badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 48px;
      height: 32px;
      padding: 0 12px;
      border-radius: 12px;
      background: #0f172a;
      color: #ffffff;
      font-size: 0.78rem;
      font-weight: 950;
      letter-spacing: 0.14em;
      text-transform: uppercase;
    }

    .brand-logo {
      display: block;
      object-fit: contain;
      filter: drop-shadow(0 8px 14px rgba(0, 0, 0, 0.16));
    }

    .brand-logo--pirelli {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 94px;
      height: 32px;
      padding: 0 12px;
      border-radius: 12px;
      border: 1px solid rgba(255, 204, 0, 0.24);
      background: linear-gradient(135deg, rgba(255, 204, 0, 0.18), rgba(255, 255, 255, 0.72));
      color: #b06d00;
      font-size: 0.74rem;
      font-weight: 950;
      letter-spacing: 0.22em;
      text-transform: uppercase;
      object-fit: unset;
    }

    .flag-badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.74);
      padding: 8px 12px;
      color: var(--text);
      font-size: 0.76rem;
      font-weight: 900;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }

    .flag-badge span {
      font-size: 1rem;
      line-height: 1;
    }

    .race-card {
      position: relative;
      z-index: 1;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.78);
      padding: 14px;
      display: grid;
      gap: 8px;
      backdrop-filter: blur(14px);
    }

    .race-card small,
    .spec-card small,
    .overview-list small {
      display: block;
      color: var(--muted);
      font-size: 0.64rem;
      font-weight: 900;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }

    .race-card strong {
      font-size: 1.05rem;
      line-height: 1.05;
      letter-spacing: 0;
    }

    .race-card span {
      color: var(--muted);
      font-size: 0.82rem;
      line-height: 1.3;
    }

    .team-ribbon {
      position: relative;
      z-index: 1;
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }

    .team-chip {
      border: 1px solid var(--line);
      border-radius: 16px;
      background: rgba(255, 255, 255, 0.76);
      padding: 10px;
      display: grid;
      gap: 7px;
      align-content: center;
      min-width: 0;
    }

    .overview-specs {
      position: relative;
      z-index: 1;
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }

    .spec-card {
      border: 1px solid var(--line);
      border-radius: 14px;
      background: rgba(255, 255, 255, 0.78);
      padding: 10px;
      min-height: 78px;
      display: grid;
      align-content: space-between;
      gap: 6px;
      backdrop-filter: blur(14px);
    }

    .spec-card strong {
      font-size: 1.45rem;
      letter-spacing: 0;
      line-height: 1;
    }

    .overview-card {
      padding: 18px;
      display: grid;
      gap: 12px;
      align-content: start;
      position: relative;
    }

    .overview-card::before {
      content: "";
      position: absolute;
      left: 18px;
      right: 18px;
      top: 0;
      height: 4px;
      border-radius: 999px;
      background: linear-gradient(90deg, #d92d20, #0a84ff, #1fbf75);
    }

    .overview-card h3 {
      margin: 0;
      font-size: 1.2rem;
      letter-spacing: 0;
      line-height: 1.05;
    }

    .overview-card p {
      margin: 0;
      color: var(--muted);
      line-height: 1.6;
    }

    .overview-list {
      display: grid;
      gap: 8px;
      margin: 0;
      padding: 0;
      list-style: none;
    }

    .overview-list li {
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px;
      background: rgba(255, 255, 255, 0.72);
      display: grid;
      grid-template-columns: auto 1fr;
      gap: 10px;
      align-items: start;
    }

    .step-badge {
      width: 34px;
      height: 34px;
      border-radius: 50%;
      display: grid;
      place-items: center;
      background: #061017;
      color: #ffffff;
      font-size: 0.72rem;
      font-weight: 950;
    }

    .overview-list strong {
      display: block;
      margin-top: 4px;
      font-size: 0.96rem;
    }

    .page-map {
      display: grid;
      gap: 8px;
    }

    .page-map a {
      display: flex;
      justify-content: space-between;
      gap: 14px;
      align-items: center;
      text-decoration: none;
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px;
      background: rgba(255, 255, 255, 0.72);
      color: var(--text);
      transition: transform 160ms ease, border-color 160ms ease;
    }

    .page-map a:hover {
      transform: translateY(-1px);
      border-color: rgba(10, 132, 255, 0.28);
    }

    .page-map span {
      color: var(--muted);
      font-size: 0.82rem;
    }

    .site-credits {
      width: min(1480px, calc(100vw - 28px));
      margin: 18px auto 0;
      padding: 0 0 36px;
    }

    .credits-inner {
      border-top: 1px solid var(--line);
      display: flex;
      justify-content: space-between;
      gap: 18px;
      align-items: center;
      padding-top: 18px;
      color: var(--muted);
    }

    .credits-mark {
      display: grid;
      gap: 4px;
    }

    .credits-mark strong {
      color: var(--text);
      font-size: 0.94rem;
    }

    .credits-mark span {
      font-size: 0.82rem;
    }

    .credit-links {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      justify-content: flex-end;
    }

    .credit-link {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 9px 12px;
      background: rgba(255, 255, 255, 0.62);
      text-decoration: none;
      color: var(--text);
      font-size: 0.84rem;
      font-weight: 800;
    }

    .credit-icon {
      width: 22px;
      height: 22px;
      border-radius: 50%;
      display: grid;
      place-items: center;
      background: #0a84ff;
      color: #ffffff;
      font-size: 0.7rem;
      font-weight: 950;
      line-height: 1;
    }

    .media-layout {
      display: grid;
      grid-template-columns: minmax(230px, 0.72fr) minmax(320px, 1.28fr);
      gap: 18px;
      align-items: stretch;
    }

    .portrait-stage {
      min-height: 465px;
      border-radius: 26px;
      border: 1px solid var(--line);
      background:
        radial-gradient(circle at 50% 18%, rgba(255, 255, 255, 0.16), transparent 13rem),
        linear-gradient(160deg, rgba(255, 255, 255, 0.08), rgba(255, 255, 255, 0.025));
      display: grid;
      place-items: end center;
      position: relative;
      overflow: hidden;
    }

    .portrait-stage::after {
      content: "";
      position: absolute;
      inset: auto 20px 16px;
      height: 44px;
      border-radius: 50%;
      background: rgba(0, 0, 0, 0.36);
      filter: blur(18px);
    }

    .portrait-image {
      position: relative;
      z-index: 1;
      max-width: 96%;
      max-height: 452px;
      object-fit: contain;
      object-position: bottom center;
      filter: drop-shadow(0 22px 26px rgba(0, 0, 0, 0.42));
    }

    .portrait-fallback {
      width: 190px;
      height: 190px;
      border-radius: 50%;
      display: grid;
      place-items: center;
      margin: auto;
      position: relative;
      z-index: 1;
      border: 2px solid rgba(255, 255, 255, 0.78);
      box-shadow: inset 0 0 42px rgba(255, 255, 255, 0.10), 0 22px 54px rgba(0, 0, 0, 0.32);
      font-size: 2.9rem;
      font-weight: 950;
      letter-spacing: -0.08em;
    }

    .driver-copy {
      display: flex;
      flex-direction: column;
      justify-content: center;
      min-width: 0;
    }

    .driver-composite {
      position: relative;
      min-height: 280px;
      border-radius: 26px;
      overflow: hidden;
      border: 1px solid var(--line);
      background:
        radial-gradient(circle at 20% 18%, rgba(255, 255, 255, 0.14), transparent 12rem),
        radial-gradient(circle at 78% 50%, rgba(0, 229, 255, 0.10), transparent 14rem),
        linear-gradient(160deg, rgba(255, 255, 255, 0.08), rgba(255, 255, 255, 0.02));
      box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.02);
    }

    .driver-composite::after {
      content: "";
      position: absolute;
      left: 18%;
      right: 18%;
      bottom: 12px;
      height: 42px;
      border-radius: 50%;
      background: rgba(0, 0, 0, 0.30);
      filter: blur(16px);
    }

    .driver-portrait {
      position: absolute;
      left: 2%;
      bottom: 0;
      width: auto;
      height: 90%;
      max-height: 280px;
      object-fit: contain;
      object-position: left bottom;
      z-index: 3;
      filter: drop-shadow(0 20px 28px rgba(0, 0, 0, 0.42));
    }

    .driver-label-stack {
      position: absolute;
      right: 14px;
      top: 14px;
      z-index: 4;
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: 8px;
      max-width: 48%;
    }

    .driver-name {
      font-size: clamp(1.35rem, 2.8vw, 3rem);
      font-weight: 950;
      letter-spacing: -0.075em;
      line-height: 0.9;
      margin-top: 0;
      text-align: right;
      text-wrap: balance;
    }

    .driver-number-tag {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 7px 12px;
      border-radius: 999px;
      background: rgba(8, 11, 18, 0.72);
      border: 1px solid rgba(255, 255, 255, 0.16);
      color: var(--text);
      font-weight: 900;
      font-size: 0.78rem;
      letter-spacing: 0.16em;
      text-transform: uppercase;
    }

    .track-panel-body {
      padding: 12px 12px 12px;
    }

    .track-stage {
      position: relative;
      min-height: 320px;
      border-radius: 26px;
      overflow: hidden;
      border: 1px solid var(--line);
      background:
        radial-gradient(circle at 50% 20%, rgba(255, 255, 255, 0.12), transparent 12rem),
        radial-gradient(circle at 72% 50%, rgba(0, 229, 255, 0.14), transparent 14rem),
        linear-gradient(160deg, rgba(255, 255, 255, 0.09), rgba(255, 255, 255, 0.02));
    }

    .track-stage::before {
      content: "";
      position: absolute;
      inset: 0;
      background-image:
        linear-gradient(rgba(255, 255, 255, 0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
      background-size: 36px 36px;
      mask-image: linear-gradient(to bottom, rgba(0, 0, 0, 0.7), transparent 92%);
      pointer-events: none;
    }

    .track-meta {
      position: absolute;
      inset: 14px 14px auto 14px;
      z-index: 3;
      display: flex;
      justify-content: space-between;
      align-items: start;
      gap: 12px;
      pointer-events: none;
    }

    .track-race-name {
      font-size: clamp(1rem, 1.7vw, 1.45rem);
      font-weight: 950;
      letter-spacing: -0.05em;
      line-height: 1.0;
      margin: 0;
    }

    .track-circuit-name {
      margin-top: 5px;
      color: var(--muted);
      font-size: 0.82rem;
      line-height: 1.35;
      max-width: 220px;
    }

    .track-badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 34px;
      padding: 7px 11px;
      border-radius: 999px;
      border: 1px solid rgba(255, 255, 255, 0.18);
      background: rgba(8, 11, 18, 0.66);
      color: #f5f7fb;
      font-size: 0.72rem;
      font-weight: 900;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      white-space: nowrap;
    }

    .track-svg {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
    }

    .track-map-image {
      position: absolute;
      inset: 58px 24px 18px;
      width: calc(100% - 48px);
      height: calc(100% - 76px);
      object-fit: contain;
      object-position: center;
      opacity: 0.92;
      filter: invert(1) brightness(1.26) drop-shadow(0 0 22px rgba(0, 229, 255, 0.28));
      z-index: 1;
    }

    .track-map-image[hidden] {
      display: none;
    }

    .track-lane-glow {
      fill: none;
      stroke: rgba(0, 229, 255, 0.16);
      stroke-width: 58;
      stroke-linecap: round;
      stroke-linejoin: round;
      filter: blur(18px);
    }

    .track-lane-outline {
      fill: none;
      stroke: rgba(255, 255, 255, 0.88);
      stroke-width: 24;
      stroke-linecap: round;
      stroke-linejoin: round;
    }

    .track-lane-core {
      fill: none;
      stroke: rgba(5, 8, 15, 0.82);
      stroke-width: 12;
      stroke-linecap: round;
      stroke-linejoin: round;
    }

    .track-lane-spark {
      fill: none;
      stroke: rgba(0, 229, 255, 0.86);
      stroke-width: 4;
      stroke-linecap: round;
      stroke-dasharray: 14 16;
      opacity: 0.82;
    }

    .track-car-dot {
      filter: drop-shadow(0 0 14px rgba(0, 229, 255, 0.8));
    }

    .track-car-body {
      fill: url(#trackCarGradient);
      stroke: rgba(5, 8, 15, 0.92);
      stroke-width: 2;
    }

    .track-car-detail {
      fill: rgba(0, 229, 255, 0.92);
    }

    .track-marker {
      pointer-events: none;
      filter: drop-shadow(0 10px 18px rgba(0, 0, 0, 0.42));
    }

    .track-marker circle {
      stroke: rgba(6, 9, 16, 0.94);
      stroke-width: 2.2;
    }

    .track-marker text {
      fill: #061017;
      font-size: 9px;
      font-weight: 950;
      letter-spacing: 0.12em;
      text-anchor: middle;
      dominant-baseline: middle;
    }

    .track-marker-start circle {
      fill: #39ff8f;
    }

    .track-marker-end circle {
      fill: #ffd12e;
    }

    .car-photo-stage {
      width: 100%;
      margin-top: 18px;
      border-radius: 22px;
      border: 1px solid var(--line);
      background:
        radial-gradient(circle at 70% 45%, rgba(0, 229, 255, 0.12), transparent 16rem),
        linear-gradient(160deg, rgba(255, 255, 255, 0.08), rgba(255, 255, 255, 0.025));
      padding: 14px;
      position: relative;
      overflow: hidden;
      min-height: 170px;
    }

    .team-car-photo {
      position: absolute;
      left: 50%;
      bottom: -3%;
      transform: translateX(-50%);
      width: min(102%, 700px);
      height: 104%;
      min-height: 0;
      object-fit: contain;
      opacity: 0.98;
      z-index: 1;
      filter: drop-shadow(0 18px 22px rgba(0, 0, 0, 0.38));
    }

    .score-wrap {
      display: grid;
      grid-template-columns: auto 1fr;
      gap: 12px;
      align-items: center;
    }

    .score-ring {
      width: 126px;
      height: 126px;
      border-radius: 50%;
      display: grid;
      place-items: center;
      background: conic-gradient(var(--cyan) 0deg, rgba(255, 255, 255, 0.11) 0deg);
      box-shadow: 0 20px 48px rgba(0, 229, 255, 0.12);
    }

    .score-ring-inner {
      width: 94px;
      height: 94px;
      border-radius: 50%;
      background: #0b101d;
      display: grid;
      place-items: center;
      border: 1px solid var(--line);
      font-weight: 950;
      font-size: 1.18rem;
    }

    .rating {
      font-size: 1.12rem;
      font-weight: 950;
      letter-spacing: -0.03em;
    }

    .verdict {
      margin-top: 8px;
      color: var(--muted);
      line-height: 1.55;
    }

    .metrics {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin-top: 14px;
    }

    .metric {
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 12px;
      background: rgba(255, 255, 255, 0.045);
    }

    .metric small {
      display: block;
      color: var(--muted);
      font-weight: 900;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      font-size: 0.67rem;
      margin-bottom: 6px;
    }

    .metric strong {
      font-size: 1.05rem;
    }

    .badges {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 14px;
    }

    .badge {
      border-radius: 999px;
      background: rgba(255, 209, 46, 0.14);
      border: 1px solid rgba(255, 209, 46, 0.34);
      color: #ffe693;
      padding: 7px 10px;
      font-size: 0.75rem;
      font-weight: 950;
    }

    .radio {
      margin-top: 16px;
      border: 1px solid rgba(57, 255, 143, 0.28);
      border-radius: 24px;
      background: rgba(57, 255, 143, 0.08);
      padding: 14px;
      color: #d9ffe8;
      line-height: 1.55;
    }

    .radio-label {
      color: var(--green);
      font-weight: 950;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      font-size: 0.72rem;
      margin-bottom: 5px;
    }

    .wide-grid {
      display: grid;
      grid-template-columns: 1.25fr 1fr;
      gap: 16px;
      margin-top: 16px;
    }

    .strategy-command {
      margin-top: 16px;
      display: grid;
      grid-template-columns: minmax(0, 0.96fr) minmax(340px, 1.04fr);
      gap: 20px;
      align-items: center;
      overflow: hidden;
      position: relative;
      padding: 24px;
    }

    .strategy-command::before {
      content: "";
      position: absolute;
      inset: 0;
      background:
        radial-gradient(circle at 14% 20%, rgba(0, 229, 255, 0.13), transparent 16rem),
        linear-gradient(116deg, rgba(10, 132, 255, 0.10) 0 28%, transparent 28% 100%);
      pointer-events: none;
    }

    .strategy-command-copy,
    .strategy-cards {
      position: relative;
      z-index: 1;
      min-width: 0;
    }

    .strategy-headline {
      margin: 10px 0 12px;
      max-width: 23ch;
      font-size: clamp(2rem, 3.25vw, 3.25rem);
      line-height: 0.98;
      letter-spacing: -0.045em;
    }

    .strategy-intro {
      margin: 0;
      color: var(--muted);
      line-height: 1.55;
      max-width: 72ch;
      font-size: 0.96rem;
    }

    .strategy-cards {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
      align-self: center;
    }

    .strategy-card {
      border: 1px solid var(--line);
      border-radius: 22px;
      background: rgba(255, 255, 255, 0.06);
      padding: 14px;
      min-height: 112px;
      box-shadow: 0 16px 32px rgba(10, 132, 255, 0.08);
      display: flex;
      flex-direction: column;
      justify-content: center;
    }

    .strategy-card.is-selected {
      border-color: rgba(57, 255, 143, 0.38);
      background: linear-gradient(145deg, rgba(57, 255, 143, 0.12), rgba(255, 255, 255, 0.04));
    }

    .strategy-card.is-rival {
      border-color: rgba(0, 229, 255, 0.38);
      background: linear-gradient(145deg, rgba(0, 229, 255, 0.12), rgba(255, 255, 255, 0.04));
    }

    .strategy-card.is-neutral,
    .strategy-card.is-empty {
      border-style: dashed;
    }

    .strategy-card small {
      display: block;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.14em;
      font-size: 0.68rem;
      font-weight: 950;
      margin-bottom: 8px;
    }

    .strategy-card strong {
      display: block;
      font-size: 1.02rem;
      letter-spacing: -0.035em;
      margin-bottom: 6px;
    }

    .strategy-card span {
      color: var(--muted);
      line-height: 1.42;
      font-size: 0.84rem;
    }

    .strategy-radio {
      margin-top: 16px;
      padding-bottom: 18px;
    }

    .strategy-notes {
      display: grid;
      grid-template-columns: repeat(3, minmax(220px, 1fr));
      gap: 12px;
      padding: 16px 18px 0;
    }

    .strategy-notes .empty {
      grid-column: 1 / -1;
    }

    .strategy-note {
      border: 1px solid rgba(57, 255, 143, 0.20);
      border-radius: 18px;
      padding: 12px 14px;
      min-height: 88px;
      background: rgba(57, 255, 143, 0.06);
      color: var(--text);
      line-height: 1.45;
      position: relative;
      font-size: 0.86rem;
    }

    .strategy-note::before {
      content: "RADIO";
      display: block;
      color: var(--green);
      font-size: 0.65rem;
      font-weight: 950;
      letter-spacing: 0.14em;
      margin-bottom: 5px;
    }

    .panel-note {
      margin: 5px 0 0;
      color: var(--muted);
      font-size: 0.82rem;
      line-height: 1.45;
      font-weight: 650;
      letter-spacing: 0;
      text-transform: none;
    }

    .pace-canvas-wrap {
      position: relative;
    }

    canvas {
      width: 100%;
      min-height: 310px;
      border-radius: 20px;
      background: #090e18;
      border: 1px solid var(--line);
    }

    .pace-tooltip {
      position: absolute;
      z-index: 8;
      min-width: 154px;
      border: 1px solid rgba(0, 229, 255, 0.36);
      border-radius: 14px;
      background: rgba(7, 10, 18, 0.94);
      color: #f5f7fb;
      padding: 9px 10px;
      font-size: 0.78rem;
      line-height: 1.45;
      box-shadow: 0 16px 36px rgba(0, 0, 0, 0.34);
      pointer-events: none;
    }

    .pace-tooltip strong {
      display: block;
      font-size: 0.9rem;
      margin-bottom: 2px;
    }

    .chart-readout {
      margin-top: 9px;
      border: 1px solid rgba(0, 229, 255, 0.18);
      border-radius: 14px;
      padding: 9px 11px;
      color: var(--muted);
      background: rgba(0, 229, 255, 0.05);
      font-size: 0.84rem;
      line-height: 1.45;
    }

    .leaderboard {
      display: grid;
      gap: 7px;
    }

    .leader-row {
      display: grid;
      grid-template-columns: 46px 62px 1fr 66px;
      gap: 8px;
      align-items: center;
      font-size: 0.82rem;
      border: 1px solid transparent;
      border-radius: 13px;
      padding: 5px 6px;
    }

    .leader-row.is-focus {
      border-color: rgba(57, 255, 143, 0.28);
      background: rgba(57, 255, 143, 0.08);
    }

    .leader-row.is-rival {
      border-color: rgba(0, 229, 255, 0.28);
      background: rgba(0, 229, 255, 0.08);
    }

    .leader-meta {
      display: grid;
      gap: 3px;
      min-width: 0;
    }

    .leader-meta small {
      color: var(--muted);
      font-size: 0.66rem;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .bar-track {
      height: 10px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.08);
      overflow: hidden;
    }

    .bar-fill {
      height: 100%;
      border-radius: inherit;
      width: 0;
    }

    .strategy-list {
      max-height: 640px;
      overflow: auto;
      padding-right: 6px;
      display: grid;
      gap: 8px;
    }

    .strategy-row {
      display: grid;
      grid-template-columns: 104px minmax(0, 1fr);
      gap: 12px;
      align-items: center;
      border: 1px solid transparent;
      border-radius: 16px;
      padding: 9px;
    }

    .strategy-row.is-focus {
      border-color: rgba(57, 255, 143, 0.30);
      background: rgba(57, 255, 143, 0.07);
    }

    .strategy-row.is-rival {
      border-color: rgba(0, 229, 255, 0.30);
      background: rgba(0, 229, 255, 0.07);
    }

    .strategy-label {
      color: #dce7ff;
      font-size: 0.76rem;
      font-weight: 950;
    }

    .strategy-label small {
      display: block;
      color: var(--muted);
      font-size: 0.64rem;
      letter-spacing: 0.08em;
      margin-top: 2px;
      text-transform: uppercase;
    }

    .timeline-wrap {
      min-width: 0;
    }

    .timeline {
      position: relative;
      display: flex;
      height: 23px;
      border-radius: 999px;
      overflow: hidden;
      background: rgba(255, 255, 255, 0.06);
      border: 1px solid rgba(255, 255, 255, 0.08);
    }

    .stint {
      min-width: 5px;
    }

    .pit-marker {
      position: absolute;
      top: -2px;
      bottom: -2px;
      width: 3px;
      background: var(--cyan);
      box-shadow: 0 0 10px var(--cyan);
    }

    .strategy-meta {
      margin-top: 6px;
      color: var(--muted);
      font-size: 0.75rem;
      line-height: 1.35;
      white-space: normal;
    }

    .timeline-section-label {
      color: var(--muted);
      font-size: 0.68rem;
      font-weight: 950;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      margin: 8px 2px 2px;
    }

    .export-hero {
      margin-top: 16px;
      display: grid;
      grid-template-columns: minmax(0, 1.05fr) minmax(340px, 0.95fr);
      gap: 18px;
      padding: 22px;
      overflow: hidden;
      position: relative;
    }

    .export-hero::before {
      content: "";
      position: absolute;
      inset: 0;
      background:
        radial-gradient(circle at 82% 20%, rgba(255, 211, 96, 0.14), transparent 15rem),
        linear-gradient(118deg, rgba(10, 132, 255, 0.10) 0 34%, transparent 34% 100%);
      pointer-events: none;
    }

    .export-copy,
    .export-stack {
      position: relative;
      z-index: 1;
    }

    .export-headline {
      margin: 8px 0 10px;
      font-size: clamp(1.75rem, 3vw, 2.7rem);
      line-height: 1;
      letter-spacing: -0.045em;
      max-width: 13ch;
    }

    .export-intro {
      color: var(--muted);
      line-height: 1.48;
      margin: 0;
      max-width: 56ch;
    }

    .export-stack {
      display: grid;
      gap: 10px;
      align-content: start;
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }

    .export-mini-card {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: rgba(255, 255, 255, 0.055);
      display: grid;
      gap: 8px;
      align-content: start;
      min-height: 110px;
    }

    .export-mini-icon {
      width: 38px;
      height: 38px;
      border-radius: 8px;
      display: grid;
      place-items: center;
      background: linear-gradient(135deg, rgba(10, 132, 255, 0.18), rgba(0, 229, 255, 0.12));
      border: 1px solid rgba(0, 229, 255, 0.22);
      font-weight: 950;
    }

    .export-mini-card strong {
      display: block;
      margin-bottom: 2px;
      font-size: 0.96rem;
    }

    .export-mini-card span {
      color: var(--muted);
      font-size: 0.78rem;
      line-height: 1.34;
    }

    .export-studio-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 16px;
      margin-top: 16px;
    }

    .export-control {
      display: grid;
      gap: 12px;
      align-content: start;
      padding: 18px;
    }

    .export-control-header {
      display: flex;
      gap: 10px;
      align-items: center;
    }

    .export-control-header .export-mini-icon {
      width: 38px;
      height: 38px;
      border-radius: 8px;
    }

    .export-control-title {
      font-weight: 950;
      letter-spacing: -0.02em;
      font-size: 1.05rem;
    }

    .export-control p {
      margin: 0;
      color: var(--muted);
      line-height: 1.45;
      font-size: 0.84rem;
    }

    .export-select {
      min-height: 46px;
      background: rgba(255, 255, 255, 0.82);
    }

    .export-preview-panel {
      margin-top: 16px;
      padding: 18px;
    }

    .output-toolbar {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 14px;
    }

    .output-toolbar p {
      margin: 0;
      color: var(--muted);
      line-height: 1.45;
      max-width: 78ch;
    }

    .inline-preview {
      margin: 12px 0 14px;
      border: 1px solid rgba(0, 229, 255, 0.22);
      border-radius: 8px;
      background:
        radial-gradient(circle at 18% 0%, rgba(10, 132, 255, 0.08), transparent 22rem),
        rgba(255, 255, 255, 0.045);
      padding: 16px;
      overflow: hidden;
    }

    .inline-preview[hidden] {
      display: none;
    }

    .inline-preview-header {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: start;
      margin-bottom: 12px;
    }

    .inline-preview-title {
      font-weight: 950;
      font-size: 1.12rem;
      letter-spacing: -0.03em;
    }

    .inline-preview-summary {
      margin-top: 4px;
      color: var(--muted);
      line-height: 1.45;
    }

    .inline-preview-close {
      width: auto;
      min-width: 120px;
      padding: 9px 12px;
    }

    .inline-preview img,
    .inline-preview iframe {
      width: min(100%, 920px);
      display: block;
      margin: 0 auto;
      min-height: 360px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #070a12;
      object-fit: contain;
    }

    .inline-preview iframe.preview-frame--replay {
      width: min(100%, 760px);
      height: min(420px, 58vh);
      min-height: 0;
    }

    .inline-preview iframe.preview-frame--document {
      height: min(620px, 68vh);
    }

    .inline-preview img {
      display: block;
      height: auto;
      min-height: 0;
    }

    .actions {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
      margin-top: 16px;
    }

    .output-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      margin-top: 14px;
      align-items: start;
    }

    .output-column {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      background: rgba(255, 255, 255, 0.04);
      display: grid;
      gap: 10px;
      min-height: 120px;
    }

    .output-column--reports {
      grid-column: 1 / -1;
    }

    .output-column-title {
      font-size: 0.75rem;
      font-weight: 950;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: var(--cyan);
    }

    .output-column-note {
      color: var(--muted);
      font-size: 0.82rem;
      line-height: 1.45;
    }

    .output-card-grid {
      display: grid;
      gap: 10px;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    }

    .file-card {
      display: grid;
      gap: 7px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: rgba(255, 255, 255, 0.045);
      text-decoration: none;
      color: var(--text);
      min-height: 104px;
      text-align: left;
    }

    .file-card .file-name {
      margin-top: 2px;
    }

    .file-card:hover {
      border-color: rgba(0, 229, 255, 0.45);
    }

    .file-card img {
      display: block;
      width: 100%;
      aspect-ratio: 16 / 10;
      object-fit: cover;
      border-radius: 6px;
      margin-bottom: 7px;
      background: #070a12;
    }

    .file-name {
      font-weight: 850;
      font-size: 0.8rem;
      word-break: break-word;
    }

    .file-summary {
      color: var(--muted);
      line-height: 1.38;
      font-size: 0.75rem;
    }

    .file-kind {
      display: inline-flex;
      width: fit-content;
      border: 1px solid rgba(0, 229, 255, 0.22);
      border-radius: 999px;
      padding: 4px 8px;
      color: var(--cyan);
      background: rgba(0, 229, 255, 0.08);
      font-size: 0.64rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      font-weight: 950;
    }

    .modal-backdrop {
      position: fixed;
      inset: 0;
      z-index: 40;
      display: grid;
      place-items: center;
      padding: 24px;
      background: rgba(5, 8, 17, 0.72);
      backdrop-filter: blur(14px);
    }

    .modal-backdrop[hidden] {
      display: none;
    }

    .output-modal {
      width: min(1120px, 100%);
      max-height: min(88vh, 900px);
      border: 1px solid var(--line);
      border-radius: 28px;
      background: var(--panel-solid);
      box-shadow: var(--shadow);
      overflow: hidden;
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
    }

    .modal-header {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 12px;
      align-items: start;
      padding: 18px;
      border-bottom: 1px solid var(--line);
      position: relative;
      z-index: 2;
      background: var(--panel-solid);
    }

    .modal-title {
      font-size: 1.25rem;
      font-weight: 950;
      letter-spacing: -0.035em;
    }

    .modal-summary {
      margin-top: 6px;
      color: var(--muted);
      line-height: 1.45;
    }

    .modal-close {
      width: auto;
      min-width: 44px;
      padding: 9px 12px;
      position: relative;
      z-index: 3;
      pointer-events: auto;
    }

    .modal-body {
      padding: 18px;
      overflow: auto;
      background:
        radial-gradient(circle at 20% 0%, rgba(10, 132, 255, 0.08), transparent 22rem),
        var(--panel);
    }

    .modal-body img,
    .modal-body iframe {
      width: 100%;
      min-height: 560px;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: #070a12;
      object-fit: contain;
    }

    .modal-body img {
      display: block;
      height: auto;
      min-height: 0;
    }

    .modal-link-row {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 12px;
    }

    .modal-link-row a {
      color: var(--cyan);
      text-decoration: none;
      font-weight: 900;
    }

    .loading {
      opacity: 0.62;
      pointer-events: none;
    }

    .empty {
      color: var(--muted);
      line-height: 1.55;
      border: 1px dashed rgba(255, 255, 255, 0.16);
      border-radius: 8px;
      padding: 16px;
    }

    body[data-theme="dark"] {
      --bg: #050811;
      --panel: rgba(11, 16, 27, 0.84);
      --panel-solid: #0e1422;
      --line: rgba(255, 255, 255, 0.10);
      --text: #f5f7fb;
      --muted: #a7b1c4;
      --cyan: #61b8ff;
      --green: #39ff8f;
      --yellow: #ffd360;
      --red: #ff667a;
      --shadow: 0 24px 72px rgba(0, 0, 0, 0.42);
    }

    body[data-theme="dark"] {
      background:
        linear-gradient(116deg, rgba(10, 132, 255, 0.14) 0 12%, transparent 12% 100%),
        repeating-linear-gradient(90deg, rgba(255, 255, 255, 0.035) 0 1px, transparent 1px 58px),
        repeating-linear-gradient(0deg, rgba(255, 255, 255, 0.025) 0 1px, transparent 1px 58px),
        linear-gradient(180deg, #050811 0%, #090d16 100%);
    }

    body[data-theme="dark"]::before {
      background-image:
        linear-gradient(45deg, rgba(255, 255, 255, 0.045) 25%, transparent 25%, transparent 75%, rgba(255, 255, 255, 0.045) 75%),
        linear-gradient(45deg, rgba(255, 255, 255, 0.045) 25%, transparent 25%, transparent 75%, rgba(255, 255, 255, 0.045) 75%);
    }

    body[data-theme="dark"] .hero {
      background:
        linear-gradient(112deg, rgba(10, 132, 255, 0.15) 0 18%, transparent 18% 100%),
        linear-gradient(180deg, rgba(17, 24, 39, 0.92), rgba(11, 16, 27, 0.82));
    }

    body[data-theme="dark"] .site-header {
      background: linear-gradient(180deg, rgba(5, 8, 17, 0.88), rgba(5, 8, 17, 0.70));
    }

    body[data-theme="dark"] .header-shell {
      background: linear-gradient(180deg, rgba(11, 16, 27, 0.92), rgba(11, 16, 27, 0.84));
    }

    body[data-theme="dark"] .header-mark {
      opacity: 0.18;
      color: #f5f7fb;
      filter: brightness(1.08) saturate(1.16) drop-shadow(0 12px 24px rgba(10, 132, 255, 0.14));
    }

    body[data-theme="dark"] .hero::after {
      color: rgba(255, 255, 255, 0.03);
    }

    body[data-theme="dark"] .hero::before {
      background-image:
        linear-gradient(45deg, rgba(255, 255, 255, 0.16) 25%, transparent 25%, transparent 75%, rgba(255, 255, 255, 0.16) 75%),
        linear-gradient(45deg, rgba(255, 255, 255, 0.16) 25%, transparent 25%, transparent 75%, rgba(255, 255, 255, 0.16) 75%);
    }

    body[data-theme="dark"] .page-link {
      background: rgba(17, 24, 39, 0.80);
      color: #d7dfec;
    }

    body[data-theme="dark"] .page-link:hover {
      background: rgba(255, 255, 255, 0.08);
      color: #ffffff;
    }

    body[data-theme="dark"] .theme-toggle {
      background: rgba(17, 24, 39, 0.80);
      color: #d7dfec;
    }

    body[data-theme="dark"] .theme-toggle:hover {
      background: rgba(255, 255, 255, 0.08);
      color: #ffffff;
    }

    body[data-theme="dark"][data-page="overview"] .page-nav .page-link[href="/overview"],
    body[data-theme="dark"][data-page="analysis"] .page-nav .page-link[href="/analysis"],
    body[data-theme="dark"][data-page="strategy"] .page-nav .page-link[href="/strategy"],
    body[data-theme="dark"][data-page="exports"] .page-nav .page-link[href="/exports"] {
      background: linear-gradient(135deg, #0a84ff, #00e5ff);
      border-color: rgba(0, 229, 255, 0.42);
      color: #ffffff;
      box-shadow: 0 12px 30px rgba(10, 132, 255, 0.32);
    }

    body[data-theme="dark"] select,
    body[data-theme="dark"] button {
      background: rgba(17, 24, 39, 0.88);
      color: #f5f7fb;
    }

    body[data-theme="dark"] .select-shell {
      background: rgba(17, 24, 39, 0.84);
      border-color: rgba(255, 255, 255, 0.12);
    }

    body[data-theme="dark"] .select-shell::before {
      background: linear-gradient(135deg, rgba(10, 132, 255, 0.12), transparent 42%);
    }

    body[data-theme="dark"] .select-icon--flag {
      background: linear-gradient(135deg, rgba(10, 132, 255, 0.24), rgba(255, 255, 255, 0.08));
    }

    body[data-theme="dark"] .control-select {
      background: transparent;
      color: #f5f7fb;
    }

    body[data-theme="dark"] .race-toggle {
      background: rgba(17, 24, 39, 0.90);
      color: #f5f7fb;
      border-color: rgba(255, 255, 255, 0.12);
    }

    body[data-theme="dark"] .race-toggle:hover {
      background: rgba(17, 24, 39, 0.98);
      border-color: rgba(0, 229, 255, 0.30);
    }

    body[data-theme="dark"] .race-menu {
      background: rgba(11, 16, 27, 0.97);
      border-color: rgba(255, 255, 255, 0.10);
    }

    body[data-theme="dark"] .race-menu-item {
      color: #f5f7fb;
    }

    body[data-theme="dark"] .race-menu-item:hover {
      background: rgba(10, 132, 255, 0.14);
      border-color: rgba(0, 229, 255, 0.14);
    }

    body[data-theme="dark"] .race-menu-item[aria-selected="true"] {
      background: linear-gradient(135deg, rgba(10, 132, 255, 0.22), rgba(0, 229, 255, 0.08));
      border-color: rgba(0, 229, 255, 0.22);
    }

    body[data-theme="dark"] .race-menu-flag {
      background: rgba(255, 255, 255, 0.06);
    }

    body[data-theme="dark"] .race-menu-status {
      background: rgba(255, 255, 255, 0.06);
      color: #d7dfec;
    }

    body[data-theme="dark"] .primary-button {
      border-color: rgba(0, 229, 255, 0.62);
      background: linear-gradient(135deg, rgba(10, 132, 255, 0.16), rgba(0, 229, 255, 0.22));
      color: #ffffff;
      box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.08) inset, 0 18px 34px rgba(10, 132, 255, 0.20);
    }

    body[data-theme="dark"] .primary-button:hover {
      border-color: rgba(0, 229, 255, 0.84);
      background: linear-gradient(135deg, rgba(10, 132, 255, 0.20), rgba(0, 229, 255, 0.30));
    }

    body[data-theme="dark"] .primary-button {
      color: #ffffff;
    }

    body[data-theme="dark"] .overview-button,
    body[data-theme="dark"] .spec-card,
    body[data-theme="dark"] .overview-card li,
    body[data-theme="dark"] .page-map a,
    body[data-theme="dark"] .credit-link,
    body[data-theme="dark"] .export-mini-card,
    body[data-theme="dark"] .export-control,
    body[data-theme="dark"] .file-card {
      background: rgba(17, 24, 39, 0.76);
    }

    body[data-theme="dark"] .overview-button:hover,
    body[data-theme="dark"] .page-map a:hover,
    body[data-theme="dark"] .credit-link:hover,
    body[data-theme="dark"] .file-card:hover {
      background: rgba(255, 255, 255, 0.08);
    }

    body[data-theme="dark"] .export-select {
      background: rgba(17, 24, 39, 0.88);
      color: #f5f7fb;
    }

    body[data-theme="dark"] .output-modal {
      background: #0e1422;
    }

    body[data-theme="dark"] .panel-title {
      color: #f5f7fb;
    }

    body[data-theme="dark"] .credits-inner {
      border-top-color: rgba(255, 255, 255, 0.12);
    }

    body[data-theme="dark"] .control-meta,
    body[data-theme="dark"] .race-card,
    body[data-theme="dark"] .team-chip,
    body[data-theme="dark"] .flag-badge {
      background: rgba(17, 24, 39, 0.76);
      border-color: rgba(255, 255, 255, 0.12);
    }

    body[data-theme="dark"] .overview-feature-wall {
      background:
        linear-gradient(180deg, rgba(11, 16, 27, 0.90), rgba(11, 16, 27, 0.76)),
        linear-gradient(110deg, rgba(10, 132, 255, 0.10), transparent 38%);
      border-left-color: rgba(255, 255, 255, 0.10);
    }

    body[data-theme="dark"] .overview-feature-wall::before {
      background:
        linear-gradient(90deg, rgba(10, 132, 255, 0.14), rgba(217, 45, 32, 0.12)),
        repeating-linear-gradient(90deg, rgba(255, 255, 255, 0.04) 0 1px, transparent 1px 18px);
    }

    body[data-theme="dark"] .brand-badge {
      background: #f5f7fb;
      color: #0f172a;
    }

    body[data-theme="dark"] .flag-badge {
      color: #d7dfec;
    }

    body[data-theme="dark"] .control-meta-logo,
    body[data-theme="dark"] .team-chip-logo {
      filter: brightness(1.08) saturate(0.94) drop-shadow(0 8px 14px rgba(0, 0, 0, 0.18));
    }

    body[data-theme="dark"] .brand-logo--pirelli {
      background: linear-gradient(135deg, rgba(255, 204, 0, 0.22), rgba(255, 255, 255, 0.08));
      border-color: rgba(255, 204, 0, 0.24);
      color: #ffe27a;
      filter: drop-shadow(0 8px 14px rgba(0, 0, 0, 0.18));
    }

    body[data-theme="dark"] .control-meta-label,
    body[data-theme="dark"] .race-card small,
    body[data-theme="dark"] .spec-card small,
    body[data-theme="dark"] .overview-list small {
      color: #a7b1c4;
    }

    body[data-theme="dark"] .control-meta-text span,
    body[data-theme="dark"] .race-card span,
    body[data-theme="dark"] .team-chip-copy span {
      color: #a7b1c4;
    }

    body[data-theme="dark"] .overview-quickline {
      background: linear-gradient(90deg, rgba(10, 132, 255, 0.16), transparent);
    }

    body[data-theme="dark"] .panel,
    body[data-theme="dark"] .hero {
      box-shadow: 0 24px 72px rgba(0, 0, 0, 0.42);
    }

    body[data-theme="dark"] .driver-composite,
    body[data-theme="dark"] .portrait-stage,
    body[data-theme="dark"] .track-stage,
    body[data-theme="dark"] .car-photo-stage {
      background:
        radial-gradient(circle at 20% 18%, rgba(10, 132, 255, 0.14), transparent 12rem),
        radial-gradient(circle at 78% 50%, rgba(0, 229, 255, 0.10), transparent 14rem),
        linear-gradient(160deg, rgba(255, 255, 255, 0.06), rgba(255, 255, 255, 0.02));
    }

    body[data-theme="dark"] .score-ring-inner {
      background: #0b1018;
    }

    body[data-theme="dark"] .metric,
    body[data-theme="dark"] .strategy-list,
    body[data-theme="dark"] .strategy-card,
    body[data-theme="dark"] .strategy-note,
    body[data-theme="dark"] .leaderboard,
    body[data-theme="dark"] .radio,
    body[data-theme="dark"] .empty {
      color: var(--text);
    }

    body[data-theme="dark"] .metric {
      background: rgba(255, 255, 255, 0.04);
    }

    body[data-theme="dark"] .radio {
      border-color: rgba(57, 255, 143, 0.22);
      background: rgba(57, 255, 143, 0.10);
      color: #d9ffe8;
    }

    body[data-theme="dark"] .timeline {
      background: rgba(255, 255, 255, 0.06);
      border-color: rgba(255, 255, 255, 0.08);
    }

    body[data-theme="dark"] canvas {
      background: #090e18;
      border-color: rgba(255, 255, 255, 0.10);
    }

    body[data-theme="dark"] .empty {
      border-color: rgba(255, 255, 255, 0.14);
    }

    body[data-theme="dark"] .status-chip {
      border-color: rgba(57, 255, 143, 0.26);
      background: rgba(57, 255, 143, 0.12);
      color: #9fe9bf;
    }

    body[data-theme="dark"] .status-chip.warn {
      border-color: rgba(255, 211, 96, 0.30);
      background: rgba(255, 211, 96, 0.12);
      color: #ffe08a;
    }

    @media (max-width: 1180px) {
      .main-grid, .wide-grid, .overview-grid { grid-template-columns: 1fr; }
      .strategy-command { grid-template-columns: 1fr; }
      .export-hero, .export-studio-grid { grid-template-columns: 1fr; }
      .export-stack, .output-grid { grid-template-columns: 1fr; }
      .overview-hero {
        grid-column: auto;
        grid-template-columns: 1fr;
      }
      .overview-feature-wall {
        border-left: 0;
        border-top: 1px solid var(--line);
        padding-top: 16px;
      }
      .team-ribbon {
        grid-template-columns: 1fr;
      }
      .control-deck { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .driver-composite { min-height: 320px; }
      .track-stage { min-height: 280px; }
      .header-top { flex-direction: column; align-items: stretch; }
      .header-actions, .header-status { justify-content: flex-start; }
    }

    @media (max-width: 720px) {
      .control-deck, .actions, .metrics { grid-template-columns: 1fr; }
      .overview-grid { grid-template-columns: 1fr; }
      .strategy-cards, .strategy-notes { grid-template-columns: 1fr; }
      .export-stack, .output-grid, .output-card-grid { grid-template-columns: 1fr; }
      html, body { overflow-x: hidden; }
      .shell { width: min(100% - 14px, 1500px); padding: 10px 0 24px; }
      .site-header { padding-top: 8px; }
      .header-shell { padding: 12px; border-radius: 22px; gap: 10px; }
      .header-mark { width: 132px; opacity: 0.10; }
      .header-brand { gap: 6px; }
      .site-title { font-size: clamp(1.65rem, 10vw, 2.25rem); line-height: 0.96; }
      .header-brand .eyebrow { font-size: 0.62rem; line-height: 1.35; white-space: normal; }
      .header-actions { gap: 8px; }
      .page-nav {
        justify-content: flex-start;
        flex-wrap: nowrap;
        overflow-x: auto;
        max-width: 100%;
        padding-bottom: 2px;
        scrollbar-width: none;
      }
      .page-nav::-webkit-scrollbar { display: none; }
      .page-link { flex: 0 0 auto; padding: 10px 13px; font-size: 0.78rem; }
      .theme-button, .status-chip { padding: 9px 11px; }
      .hero { margin-top: 10px; padding: 12px; border-radius: 22px; }
      .control-deck { gap: 9px; padding-top: 9px; }
      .control-group label { font-size: 0.68rem; }
      .race-toggle { min-height: 46px; padding: 9px 11px; gap: 9px; }
      .race-toggle .select-icon { flex-basis: 30px; width: 30px; height: 30px; }
      .race-toggle-label {
        font-size: 0.86rem;
        white-space: normal;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
      }
      .race-picker {
        z-index: auto;
      }
      .race-picker--open {
        z-index: 40;
      }
      .race-menu {
        position: static;
        left: auto;
        right: auto;
        top: auto;
        bottom: auto;
        width: 100%;
        max-height: min(48vh, 390px);
        margin-top: 8px;
        border-radius: 22px;
        z-index: auto;
        box-shadow: 0 18px 42px rgba(15, 23, 42, 0.28);
      }
      .race-menu-item { padding: 11px 10px; }
      .race-menu-copy strong,
      .race-menu-copy span {
        white-space: normal;
      }
      .overview-hero-copy { padding: 18px; }
      .overview-headline { font-size: 2.15rem; max-width: 100%; }
      .overview-actions { display: grid; grid-template-columns: 1fr; }
      .overview-feature-wall { padding: 14px; }
      .overview-specs { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .team-ribbon { grid-template-columns: 1fr; }
      .credits-inner { align-items: flex-start; flex-direction: column; }
      .credit-links { justify-content: flex-start; }
      .driver-composite { min-height: 280px; }
      .driver-portrait { height: 92%; max-height: 270px; left: 2%; }
      .driver-label-stack { max-width: 56%; right: 14px; top: 14px; }
      .driver-name { font-size: clamp(1.3rem, 5vw, 2rem); }
      .track-stage { min-height: 250px; }
      .panel-header { align-items: flex-start; flex-direction: column; }
      .export-control, .export-preview-panel { padding: 14px; }
      .inline-preview { padding: 12px; }
      .inline-preview iframe.preview-frame--replay { height: min(360px, 58vh); }
    }

    @media (max-width: 480px) {
      .overview-specs { grid-template-columns: 1fr; }
      .driver-composite { min-height: 240px; }
      .driver-portrait { max-height: 230px; }
      .driver-label-stack { max-width: 60%; }
      .driver-name { font-size: 1.35rem; }
      .score-ring { width: 220px; height: 220px; }
      .leader-row { grid-template-columns: 40px 52px 1fr 54px; gap: 6px; }
      canvas { min-height: 260px; }
    }
  </style>
</head>
<body data-page="__PAGE__" data-theme="light">
  <header class="site-header">
    <div class="shell header-shell">
      <svg class="header-mark" viewBox="0 0 320 110" aria-hidden="true" focusable="false">
        <defs>
          <linearGradient id="header-mark-gradient" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stop-color="#d92d20"/>
            <stop offset="62%" stop-color="#ff4d4d"/>
            <stop offset="100%" stop-color="#0a84ff"/>
          </linearGradient>
        </defs>
        <g fill="none" fill-rule="evenodd">
          <path d="M14 74c18-29 48-43 90-43h66l-8 18H98c-25 0-48 10-60 25H14z" fill="url(#header-mark-gradient)"/>
          <path d="M154 25h42c12 0 22 10 22 22v4h-22v-4h-42z" fill="currentColor"/>
          <text x="18" y="77" font-family="system-ui, -apple-system, BlinkMacSystemFont, sans-serif" font-size="56" font-weight="950" letter-spacing="-4" fill="currentColor">F1</text>
        </g>
      </svg>
      <div class="header-top">
        <div class="header-brand">
          <h1 class="site-title">Pit Wall Predictor</h1>
          <span class="eyebrow">Molish Panneerselvam | Personal Project | Python Backend</span>
        </div>
        <div class="header-actions">
          <nav class="page-nav" aria-label="Application pages">
            <a class="page-link" href="/overview">Overview</a>
            <a class="page-link" href="/analysis">Analysis</a>
            <a class="page-link" href="/strategy">Strategy</a>
            <a class="page-link" href="/exports">Exports</a>
          </nav>
          <button id="themeToggle" class="page-link theme-toggle" type="button" aria-pressed="false" aria-label="Toggle theme" title="Toggle theme"><span class="theme-icon" aria-hidden="true">☾</span></button>
          <div id="statusChip" class="status-chip">Booting garage</div>
        </div>
      </div>
    </div>
  </header>

  <main class="shell">
    <section class="hero">
      <p class="subtitle">A browser-first Formula 1 strategy studio built with Python, NumPy, Pandas, SciPy, Matplotlib, and the standard library. Start on Overview, then move into Analysis, Strategy, or Exports once you have chosen a race and drivers.</p>
      <div class="control-deck">
        <div class="control-group">
          <label for="raceToggle">Race</label>
          <div id="racePicker" class="race-picker">
            <button id="raceToggle" class="race-toggle" type="button" aria-haspopup="listbox" aria-expanded="false" aria-controls="raceMenu">
              <span id="raceBadge" class="select-icon select-icon--flag" aria-hidden="true">🏁</span>
              <span class="race-toggle-copy">
                <span id="raceToggleMeta" class="race-toggle-kicker">Race</span>
                <strong id="raceToggleLabel" class="race-toggle-label">Barcelona-Catalunya Grand Prix</strong>
              </span>
              <span class="race-toggle-caret" aria-hidden="true">⌄</span>
            </button>
            <input type="hidden" id="raceSelect" value="Barcelona-Catalunya Grand Prix">
            <div id="raceMenu" class="race-menu" role="listbox" hidden></div>
          </div>
        </div>
        <div class="control-group">
          <label for="driverToggle">Driver</label>
          <div id="driverPicker" class="race-picker">
            <button id="driverToggle" class="race-toggle" type="button" aria-haspopup="listbox" aria-expanded="false" aria-controls="driverMenu">
              <span id="driverBadge" class="select-icon select-icon--team" aria-hidden="true"></span>
              <span class="race-toggle-copy">
                <span id="driverToggleMeta" class="race-toggle-kicker">Driver</span>
                <strong id="driverToggleLabel" class="race-toggle-label">Lewis Hamilton - Ferrari #44</strong>
              </span>
              <span class="race-toggle-caret" aria-hidden="true">⌄</span>
            </button>
            <input type="hidden" id="driverSelect" value="HAM">
            <div id="driverMenu" class="race-menu" role="listbox" hidden></div>
          </div>
        </div>
        <div class="control-group">
          <label for="compareToggle">Compare</label>
          <div id="comparePicker" class="race-picker">
            <button id="compareToggle" class="race-toggle" type="button" aria-haspopup="listbox" aria-expanded="false" aria-controls="compareMenu">
              <span id="compareBadge" class="select-icon select-icon--team" aria-hidden="true"></span>
              <span class="race-toggle-copy">
                <span id="compareToggleMeta" class="race-toggle-kicker">Compare</span>
                <strong id="compareToggleLabel" class="race-toggle-label">George Russell - Mercedes #63</strong>
              </span>
              <span class="race-toggle-caret" aria-hidden="true">⌄</span>
            </button>
            <input type="hidden" id="compareSelect" value="RUS">
            <div id="compareMenu" class="race-menu" role="listbox" hidden></div>
          </div>
        </div>
        <div class="control-group">
          <label>&nbsp;</label>
          <button id="analyzeButton" class="primary-button">Analyze Race</button>
        </div>
      </div>
    </section>

    <section class="page-module page-module--overview">
      <div class="overview-grid">
        <article class="panel overview-hero">
          <div class="overview-hero-copy">
            <div class="eyebrow">Race control | Overview</div>
            <h2 class="overview-headline">Strategy workbench for the pit wall.</h2>
            <p class="overview-copy">Choose a race, pick a driver, compare against a rival, and let the Python backend turn lap data into an engineer score, pace trace, strategy timeline, radio verdict, replay files, plots, and reports.</p>
            <div class="overview-actions">
              <a class="overview-button" href="/analysis">Open analysis</a>
              <a class="overview-button" href="/strategy">View strategy</a>
              <a class="overview-button" href="/exports">Generate outputs</a>
            </div>
            <p class="overview-copy overview-quickline"><strong>Quick start:</strong> choose a completed race, select the driver you want to study, pick a comparison driver, press Analyze Race, then review the score, track view, radio notes, and output files.</p>
          </div>
          <div class="overview-feature-wall">
            <div class="feature-strip">
              <span class="brand-badge">F1</span>
              <span class="brand-logo brand-logo--pirelli">Pirelli</span>
              <div class="flag-badge"><span>🏁</span><span id="overviewRaceFlag">Race flag</span></div>
            </div>
            <div class="race-card">
              <small>Selected race</small>
              <strong id="overviewRaceName">Barcelona-Catalunya Grand Prix</strong>
              <span id="overviewRaceCircuit">Circuit de Barcelona-Catalunya, Barcelona</span>
            </div>
            <div class="team-ribbon">
              <div id="overviewDriverCard" class="team-chip"></div>
              <div id="overviewCompareCard" class="team-chip"></div>
            </div>
            <div class="overview-specs">
              <div class="spec-card">
                <small>Completed races</small>
                <strong id="overviewRaceCount">--</strong>
              </div>
              <div class="spec-card">
                <small>Drivers</small>
                <strong id="overviewDriverCount">--</strong>
              </div>
              <div class="spec-card">
                <small>Teams</small>
                <strong id="overviewTeamCount">--</strong>
              </div>
              <div class="spec-card">
                <small>Season</small>
                <strong>2026</strong>
              </div>
            </div>
          </div>
        </article>

        <article class="panel overview-card">
          <div class="panel-title">How to use it</div>
          <ul class="overview-list">
            <li>
              <span class="step-badge">01</span>
              <span><small>Race</small><strong>Choose a completed race from the selector.</strong></span>
            </li>
            <li>
              <span class="step-badge">02</span>
              <span><small>Drivers</small><strong>Pick the driver you want to study and a comparison driver.</strong></span>
            </li>
            <li>
              <span class="step-badge">03</span>
              <span><small>Analyze</small><strong>Press Analyze Race, then read the score, pace, track, and radio verdict.</strong></span>
            </li>
            <li>
              <span class="step-badge">04</span>
              <span><small>Outputs</small><strong>Move to Strategy or Exports to see rankings, stints, plots, replays, and reports.</strong></span>
            </li>
          </ul>
        </article>

        <article class="panel overview-card">
          <div class="panel-title">Starter example</div>
          <ul class="overview-list">
            <li>
              <span class="step-badge">IN</span>
              <span><small>Example input</small><strong>Race: Barcelona-Catalunya Grand Prix - Driver: HAM - Compare: RUS</strong></span>
            </li>
            <li>
              <span class="step-badge">OUT</span>
              <span><small>Expected output</small><strong>Engineer score, bird's-eye track, pace trace, leaderboard, strategy timeline, plots, replay, and report.</strong></span>
            </li>
          </ul>
          <div class="page-map">
            <a href="/analysis"><span>Analysis</span><strong>Open the main dashboard</strong></a>
            <a href="/strategy"><span>Strategy</span><strong>Review pacing and stint flow</strong></a>
            <a href="/exports"><span>Exports</span><strong>Generate downloadable outputs</strong></a>
          </div>
        </article>
      </div>
    </section>

    <section class="page-module page-module--analysis">
      <section class="main-grid">
        <section class="panel">
          <div class="panel-header">
            <div class="panel-title">Driver + 2026 team car</div>
          </div>
          <div class="panel-body driver-panel-body">
            <div id="driverComposite" class="driver-composite">
              <img id="teamCarImage" class="team-car-photo" alt="Ferrari 2026 Formula 1 car side-view render">
              <img id="driverPortrait" class="driver-portrait" alt="Lewis Hamilton official 2026 race-suit portrait">
              <div class="driver-label-stack">
                <div id="driverName" class="driver-name">Lewis Hamilton</div>
                <div id="driverNumberTag" class="driver-number-tag">#44</div>
              </div>
            </div>
          </div>
        </section>

        <section class="panel">
          <div class="panel-header">
            <div class="panel-title">Bird's-eye track view</div>
          </div>
          <div class="panel-body track-panel-body">
            <div class="track-stage">
              <div class="track-meta">
                <div>
                  <div id="trackRaceName" class="track-race-name">Barcelona-Catalunya Grand Prix</div>
                  <div id="trackCircuitName" class="track-circuit-name">Circuit de Barcelona-Catalunya, Barcelona</div>
                </div>
                <div id="trackLapBadge" class="track-badge">LAPS 66</div>
              </div>
              <img id="trackMapImage" class="track-map-image" alt="" hidden>
              <svg id="trackSvg" class="track-svg" viewBox="0 0 1000 620" preserveAspectRatio="xMidYMid meet" aria-label="Bird's-eye circuit animation"></svg>
            </div>
          </div>
        </section>

        <section class="panel">
          <div class="panel-header">
            <div class="panel-title">Race engineer score</div>
          </div>
          <div class="panel-body">
            <div class="score-wrap">
              <div id="scoreRing" class="score-ring">
                <div id="scoreValue" class="score-ring-inner">--</div>
              </div>
              <div>
                <div id="rating" class="rating">Load a completed race</div>
                <div id="verdict" class="verdict">Radio will call the strategy verdict after analysis.</div>
              </div>
            </div>
            <div id="metrics" class="metrics"></div>
            <div id="badges" class="badges"></div>
            <div class="radio">
              <div class="radio-label">Race radio</div>
              <div id="radioText">Garage systems warming up...</div>
            </div>
          </div>
        </section>
      </section>
    </section>

    <section class="page-module page-module--strategy">
      <section class="strategy-command panel">
        <div class="strategy-command-copy">
          <div class="eyebrow">Strategy room | Driver battle</div>
          <h2 id="strategyHeadline" class="strategy-headline">Select a completed race to open the strategy room.</h2>
          <p id="strategyIntro" class="strategy-intro">This page compares the selected driver against the rival using clean pace, pit timing, tyre management, stint strength, and the final race-engineer score.</p>
        </div>
        <div id="strategyCards" class="strategy-cards">
          <div class="strategy-card is-empty">Strategy cards will appear after analysis.</div>
        </div>
      </section>
      <section class="strategy-radio panel">
        <div class="panel-header">
          <div class="panel-title">Pit wall strategy notes</div>
        </div>
        <div id="strategyNotes" class="strategy-notes">
          <div class="empty">Choose a completed race and press Analyze Race to see stint-by-stint strategy notes.</div>
        </div>
      </section>
    </section>

    <section class="page-module page-module--exports">
      <section class="export-hero panel">
        <div class="export-copy">
          <div class="eyebrow">Exports | Output studio</div>
          <h2 class="export-headline">Turn analysis into portfolio evidence.</h2>
          <p class="export-intro">Generate plots, replay animations, and reports directly from the selected race. Each output includes a short engineering summary so the graph is not just pretty; it explains what happened.</p>
        </div>
        <div class="export-stack">
          <div class="export-mini-card">
            <div class="export-mini-icon">PNG</div>
            <div><strong>Plots</strong><span>Matplotlib visuals for pace, consistency, tyres, team pace, strategy timeline, heatmap, and driver battle.</span></div>
          </div>
          <div class="export-mini-card">
            <div class="export-mini-icon">HTML</div>
            <div><strong>Replays</strong><span>Browser-previewable Matplotlib animations for race pace, tyre degradation, and pit-stop timeline.</span></div>
          </div>
          <div class="export-mini-card">
            <div class="export-mini-icon">PDF</div>
            <div><strong>Reports</strong><span>PDF, Markdown, and CSV exports for portfolio documentation and deeper review.</span></div>
          </div>
        </div>
      </section>

      <section class="export-studio-grid">
        <section class="panel export-control">
          <div class="export-control-header">
            <div class="export-mini-icon">01</div>
            <div class="export-control-title">Generate plots</div>
          </div>
          <p>Choose one chart or generate the whole plot pack. The selected output opens inside the website with a summary.</p>
          <select id="plotSelect" class="export-select" aria-label="Select plot output">
            <option value="pace">Full-grid race pace ranking</option>
            <option value="consistency">Full-grid consistency ranking</option>
            <option value="tyres">Full-grid tyre management ranking</option>
            <option value="team_pace">Team pace comparison</option>
            <option value="battle">Driver battle trace</option>
            <option value="timeline">Strategy timeline</option>
            <option value="heatmap">Race pace heatmap</option>
            <option value="degradation">Tyre degradation curve</option>
            <option value="all">Complete plot pack</option>
          </select>
          <button id="plotsButton" class="primary-button">Generate selected plot</button>
        </section>

        <section class="panel export-control">
          <div class="export-control-header">
            <div class="export-mini-icon">02</div>
            <div class="export-control-title">Run replays</div>
          </div>
          <p>Generate an animation and preview it inside the app. If animation export fails, the backend saves a final-frame fallback.</p>
          <select id="replaySelect" class="export-select" aria-label="Select replay output">
            <option value="race_pace">Race pace replay</option>
            <option value="tyre_degradation">Tyre degradation replay</option>
            <option value="pit_timeline">Pit stop timeline replay</option>
            <option value="all">Complete replay pack</option>
          </select>
          <button id="replaysButton" class="primary-button">Run selected replay</button>
        </section>

        <section class="panel export-control">
          <div class="export-control-header">
            <div class="export-mini-icon">03</div>
            <div class="export-control-title">Export report</div>
          </div>
          <p>Create a report from the same Python backend. PDF is the default because it is easiest to share in a portfolio.</p>
          <select id="reportSelect" class="export-select" aria-label="Select report output">
            <option value="pdf">PDF strategy report</option>
            <option value="markdown">Markdown race report</option>
            <option value="csv">CSV driver summary</option>
            <option value="all">Complete report pack</option>
          </select>
          <button id="reportButton" class="primary-button">Export selected report</button>
        </section>
      </section>

      <section class="panel export-preview-panel">
        <div class="panel-header output-toolbar">
          <div>
            <div class="panel-title">Generated output preview</div>
            <p id="outputHint">Pick a plot, replay, or report above. The file cards appear below, and you can click any card to open its preview inline.</p>
          </div>
        </div>
        <div id="outputInlinePreview" class="inline-preview" hidden></div>
        <div id="outputArea" class="output-grid">
          <div class="empty">No exports generated yet. Choose an output above to start.</div>
        </div>
      </section>
    </section>

    <section class="wide-grid wide-grid--primary">
      <section class="panel">
        <div class="panel-header">
          <div>
            <div class="panel-title">Clean-lap pace trace</div>
            <p class="panel-note">Lower is faster. Hover near a point to read the exact lap, compound, and lap time.</p>
          </div>
        </div>
        <div class="panel-body">
          <div class="pace-canvas-wrap">
            <canvas id="paceCanvas" height="330"></canvas>
            <div id="paceTooltip" class="pace-tooltip" hidden></div>
          </div>
          <div id="paceReadout" class="chart-readout">Move over the pace trace to inspect a clean lap.</div>
        </div>
      </section>

      <section class="panel">
        <div class="panel-header">
          <div>
            <div class="panel-title">Race engineer ranking</div>
            <p class="panel-note">Score = pace, consistency, tyre management, and stint execution. Your selected battle is highlighted.</p>
          </div>
        </div>
        <div class="panel-body">
          <div id="leaderboard" class="leaderboard"></div>
        </div>
      </section>
    </section>

    <section class="wide-grid wide-grid--secondary">
      <section class="panel">
        <div class="panel-header">
          <div>
            <div class="panel-title">Strategy timeline</div>
            <p class="panel-note">Each bar is a tyre stint. Cyan tick marks show pit laps. The selected driver and rival are pinned first.</p>
          </div>
        </div>
        <div class="panel-body">
          <div id="strategyList" class="strategy-list"></div>
        </div>
      </section>

      <section class="panel">
        <div class="panel-header">
          <div class="panel-title">Generate outputs</div>
        </div>
        <div class="panel-body">
          <div class="actions">
            <button id="legacyPlotsButton">Generate plots</button>
            <button id="legacyReplaysButton">Run replays</button>
            <button id="legacyReportButton">Export report</button>
          </div>
          <div id="legacyOutputArea" class="output-grid">
            <div class="empty">Generated plots, replay HTML files, and reports will appear here as browser links.</div>
          </div>
        </div>
      </section>
    </section>
  </main>
  <footer class="site-credits">
    <div class="credits-inner">
      <div class="credits-mark">
        <strong>Molish Panneerselvam</strong>
        <span>Mechanical Engineer · Formula 1 strategy and simulation project.</span>
      </div>
      <div class="credit-links" aria-label="Project contact links">
        <a class="credit-link" href="https://www.linkedin.com/in/molish-panneerselvam-22360721a/" target="_blank" rel="noreferrer noopener"><span class="credit-icon">in</span>LinkedIn</a>
        <a class="credit-link" href="mailto:pmolish@gmail.com"><span class="credit-icon">@</span>Email</a>
        <a class="credit-link" href="https://molish-personal.web.app/" target="_blank" rel="noreferrer noopener"><span class="credit-icon">W</span>Portfolio website</a>
      </div>
    </div>
  </footer>
  <div id="outputModalBackdrop" class="modal-backdrop" hidden>
    <div class="output-modal" role="dialog" aria-modal="true" aria-labelledby="outputModalTitle">
      <div class="modal-header">
        <div>
          <div id="outputModalTitle" class="modal-title">Generated output</div>
          <div id="outputModalSummary" class="modal-summary">Preview generated output here.</div>
        </div>
        <button id="outputModalClose" class="modal-close" type="button" aria-label="Close output preview" data-close-modal="true">×</button>
      </div>
      <div id="outputModalBody" class="modal-body"></div>
    </div>
  </div>
  <script>
    const state = {
      bootstrap: null,
      analysis: null,
      teamsByName: new Map(),
      driversByCode: new Map(),
      trackAnimationFrame: null,
      trackAnimationStart: 0,
      analysisRequestId: 0,
      paceChartPoints: []
    };

    const $ = (id) => document.getElementById(id);

    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      }[char]));
    }

    function contrastColour(hex) {
      const clean = String(hex || "#111827").replace("#", "");
      const red = parseInt(clean.slice(0, 2), 16);
      const green = parseInt(clean.slice(2, 4), 16);
      const blue = parseInt(clean.slice(4, 6), 16);
      const brightness = (red * 299 + green * 587 + blue * 114) / 1000;
      return brightness > 150 ? "#071017" : "#ffffff";
    }

    function selectedPayload() {
      return {
        race: $("raceSelect").value,
        driver: $("driverSelect").value,
        compare: $("compareSelect").value,
        season: 2026
      };
    }

    async function getJson(url) {
      const response = await fetch(url);
      const data = await response.json();
      if (!response.ok || data.ok === false && data.status === "error") {
        throw new Error(data.message || response.statusText);
      }
      return data;
    }

    async function postJson(url, payload) {
      const response = await fetch(url, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok || data.ok === false && data.status === "error") {
        throw new Error(data.message || response.statusText);
      }
      return data;
    }

    function setStatus(text, warn = false) {
      const chip = $("statusChip");
      if (!chip) return;
      chip.textContent = text;
      chip.classList.toggle("warn", warn);
    }

    function setRadio(text) {
      const radio = $("radioText");
      if (radio) radio.textContent = text;
    }

    function setAnalysisLoadingState() {
      const score = $("scoreValue");
      if (!score) return;
      score.textContent = "--";
      $("scoreRing").style.background = "conic-gradient(rgba(10, 132, 255, 0.42) 120deg, rgba(255,255,255,0.11) 0deg)";
      $("rating").textContent = "Loading race data";
      $("verdict").textContent = "Fetching the selected race from local lap data.";
      $("metrics").innerHTML = "";
      $("badges").innerHTML = "";
      renderStrategyInsights(null);
      hidePaceHover();
    }

    function readPreferredTheme() {
      try {
        const stored = localStorage.getItem("pitwall-theme");
        if (stored === "light" || stored === "dark") return stored;
      } catch (error) {
        void error;
      }
      return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }

    function syncThemeToggle(theme) {
      const toggle = $("themeToggle");
      if (!toggle) return;
      const icon = theme === "dark" ? "☀" : "☾";
      const label = "Toggle theme";
      toggle.innerHTML = `<span class="theme-icon" aria-hidden="true">${icon}</span>`;
      toggle.setAttribute("aria-label", label);
      toggle.setAttribute("title", label);
      toggle.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
    }

    function applyTheme(theme) {
      const resolved = theme === "dark" ? "dark" : "light";
      document.body.dataset.theme = resolved;
      syncThemeToggle(resolved);
      try {
        localStorage.setItem("pitwall-theme", resolved);
      } catch (error) {
        void error;
      }
    }

    function toggleTheme() {
      applyTheme(document.body.dataset.theme === "dark" ? "light" : "dark");
    }

    function pageName() {
      return document.body.dataset.page || "overview";
    }

    function syncActiveNav() {
      const activePath = `/${pageName()}`;
      document.querySelectorAll(".page-nav .page-link[href]").forEach((link) => {
        link.toggleAttribute("aria-current", link.getAttribute("href") === activePath);
      });
    }

    const COUNTRY_FLAGS = {
      Australia: "🇦🇺",
      China: "🇨🇳",
      Japan: "🇯🇵",
      "United States": "🇺🇸",
      Canada: "🇨🇦",
      Monaco: "🇲🇨",
      Spain: "🇪🇸",
      Austria: "🇦🇹",
      "Great Britain": "🇬🇧",
      Belgium: "🇧🇪",
      Hungary: "🇭🇺",
      Netherlands: "🇳🇱",
      Italy: "🇮🇹",
      Azerbaijan: "🇦🇿",
      Singapore: "🇸🇬",
      Mexico: "🇲🇽",
      Brazil: "🇧🇷",
      Qatar: "🇶🇦",
      "United Arab Emirates": "🇦🇪",
      France: "🇫🇷",
      Germany: "🇩🇪",
    };

    function countryFlagEmoji(country) {
      return COUNTRY_FLAGS[country] || "🏁";
    }

    function driverChoiceLabel(driver) {
      if (!driver) return "";
      const number = driver.official_number ?? driver.driver_number ?? "--";
      return `${driver.driver_name} - ${driver.team} #${number}`;
    }

    function teamMonogram(teamName) {
      return String(teamName || "??")
        .split(/\s+/)
        .filter(Boolean)
        .map((part) => part[0])
        .join("")
        .slice(0, 2)
        .toUpperCase();
    }

    function teamLogoMarkup(teamName, logoUrl) {
      const fallback = escapeHtml(teamMonogram(teamName));
      const safeTeam = escapeHtml(teamName || "Team");
      if (logoUrl) {
        return `<img src="${escapeHtml(logoUrl)}" alt="${safeTeam} logo" loading="lazy" onerror="this.hidden=true;this.nextElementSibling.hidden=false;"><span hidden>${fallback}</span>`;
      }
      return `<span>${fallback}</span>`;
    }

    function selectedRaceValue() {
      return $("raceSelect")?.value || state.bootstrap?.default_race || DEFAULT_RACE;
    }

    function renderRaceMenu() {
      if (!state.bootstrap) return;
      const menu = $("raceMenu");
      if (!menu) return;
      const races = Array.isArray(state.bootstrap.calendar) ? state.bootstrap.calendar : [];
      const current = selectedRaceValue();
      menu.innerHTML = races.map((race) => {
        const flag = countryFlagEmoji(race.country);
        const status = race.status === "completed" ? "Completed" : "Upcoming";
        return `
          <button type="button" class="race-menu-item" role="option" aria-selected="${race.race_name === current ? "true" : "false"}" data-race="${escapeHtml(race.race_name)}">
            <span class="race-menu-flag" aria-hidden="true">${escapeHtml(flag)}</span>
            <span class="race-menu-copy">
              <strong>${escapeHtml(race.race_name)}</strong>
              <span>${escapeHtml(race.circuit)}</span>
            </span>
            <span class="race-menu-status">${escapeHtml(status)}</span>
          </button>
        `;
      }).join("");
    }

    function syncRaceToggle() {
      const race = selectedRaceMeta() || state.bootstrap?.calendar?.find((item) => item.race_name === state.bootstrap?.default_race) || null;
      const labelNode = $("raceToggleLabel");
      const metaNode = $("raceToggleMeta");
      if (labelNode) labelNode.textContent = race?.race_name || "Select race";
      if (metaNode) metaNode.textContent = race ? `Race - ${race.country}` : "Race";
      const badge = $("raceBadge");
      if (badge) {
        badge.textContent = countryFlagEmoji(race?.country || "");
        badge.title = race ? `${race.country} flag` : "Race flag";
      }
      const menu = $("raceMenu");
      const current = selectedRaceValue();
      if (menu) {
        menu.querySelectorAll(".race-menu-item").forEach((item) => {
          item.setAttribute("aria-selected", item.dataset.race === current ? "true" : "false");
        });
      }
    }

    function openRaceMenu() {
      const menu = $("raceMenu");
      const toggle = $("raceToggle");
      if (!menu || !toggle) return;
      closeDropdown("driver");
      closeDropdown("compare");
      menu.hidden = false;
      menu.parentElement?.classList.add("race-picker--open");
      toggle.setAttribute("aria-expanded", "true");
    }

    function closeRaceMenu() {
      const menu = $("raceMenu");
      const toggle = $("raceToggle");
      if (!menu || !toggle) return;
      menu.hidden = true;
      menu.parentElement?.classList.remove("race-picker--open");
      toggle.setAttribute("aria-expanded", "false");
    }

    function closeAllDropdowns() {
      closeRaceMenu();
      closeDropdown("driver");
      closeDropdown("compare");
    }

    function toggleRaceMenu(force) {
      const menu = $("raceMenu");
      if (!menu) return;
      const shouldOpen = typeof force === "boolean" ? force : menu.hidden;
      if (shouldOpen) openRaceMenu();
      else closeRaceMenu();
    }

    function setRaceSelection(raceName) {
      const raceSelect = $("raceSelect");
      if (!raceSelect || !raceName) return;
      raceSelect.value = raceName;
      syncRaceToggle();
      renderOverview();
      if (pageName() !== "overview") {
        state.analysis = null;
        renderTrackView();
        setAnalysisLoadingState();
        setStatus("Loading race data", false);
      }
      analyze();
      closeAllDropdowns();
    }

    function selectedPersonValue(kind) {
      const hidden = $(`${kind}Select`);
      const defaultValue = kind === "driver"
        ? state.bootstrap?.default_driver
        : state.bootstrap?.default_compare;
      return hidden?.value || defaultValue || "";
    }

    function renderPersonMenu(kind) {
      if (!state.bootstrap) return;
      const menu = $(`${kind}Menu`);
      if (!menu) return;
      const drivers = Array.isArray(state.bootstrap.drivers) ? state.bootstrap.drivers : [];
      const current = selectedPersonValue(kind);
      menu.innerHTML = drivers.map((driver) => {
        const team = state.teamsByName.get(driver.team);
        const accent = team?.primary_colour || driver?.team_colour || "#0a84ff";
        const logoUrl = team?.logo_url || "";
        const number = driver?.official_number ?? driver?.driver_number ?? "--";
        const icon = teamLogoMarkup(driver?.team, logoUrl);
        return `
          <button type="button" class="race-menu-item" role="option" aria-selected="${driver.driver_code === current ? "true" : "false"}" data-driver="${escapeHtml(driver.driver_code)}">
            <span class="race-menu-flag race-menu-flag--team" aria-hidden="true" style="background:${escapeHtml(accent)};color:${escapeHtml(contrastColour(accent))};">${icon}</span>
            <span class="race-menu-copy">
              <strong>${escapeHtml(driver.driver_name)}</strong>
              <span>${escapeHtml(driver.team)}</span>
            </span>
            <span class="race-menu-status" style="background:${escapeHtml(accent)};color:${escapeHtml(contrastColour(accent))};">#${escapeHtml(number)}</span>
          </button>
        `;
      }).join("");
    }

    function syncPersonToggle(kind) {
      if (!state.bootstrap) return;
      const driverCode = selectedPersonValue(kind);
      const driver = state.driversByCode.get(driverCode);
      const team = state.teamsByName.get(driver?.team);
      const accent = team?.primary_colour || driver?.team_colour || "#0a84ff";
      const logoUrl = team?.logo_url || "";
      const labelNode = $(`${kind}ToggleLabel`);
      const metaNode = $(`${kind}ToggleMeta`);
      const badgeNode = $(`${kind}Badge`);
      const menu = $(`${kind}Menu`);
      const kindLabel = kind === "driver" ? "Driver" : "Compare";
      if (labelNode) labelNode.textContent = driver ? driverChoiceLabel(driver) : `Select ${kindLabel.toLowerCase()}`;
      if (metaNode) metaNode.textContent = kindLabel;
      if (badgeNode) {
        badgeNode.title = driver ? `${driver.driver_name} - ${driver.team}` : kindLabel;
        badgeNode.style.background = accent;
        badgeNode.style.color = contrastColour(accent);
        badgeNode.innerHTML = teamLogoMarkup(driver?.team, logoUrl);
      }
      if (menu) {
        menu.querySelectorAll(".race-menu-item").forEach((item) => {
          item.setAttribute("aria-selected", item.dataset.driver === driverCode ? "true" : "false");
        });
      }
    }

    function openDropdown(kind) {
      closeRaceMenu();
      if (kind !== "driver") closeDropdown("driver");
      if (kind !== "compare") closeDropdown("compare");
      const menu = $(`${kind}Menu`);
      const toggle = $(`${kind}Toggle`);
      if (!menu || !toggle) return;
      menu.hidden = false;
      menu.parentElement?.classList.add("race-picker--open");
      toggle.setAttribute("aria-expanded", "true");
    }

    function closeDropdown(kind) {
      const menu = $(`${kind}Menu`);
      const toggle = $(`${kind}Toggle`);
      if (!menu || !toggle) return;
      menu.hidden = true;
      menu.parentElement?.classList.remove("race-picker--open");
      toggle.setAttribute("aria-expanded", "false");
    }

    function toggleDropdown(kind, force) {
      const menu = $(`${kind}Menu`);
      if (!menu) return;
      const shouldOpen = typeof force === "boolean" ? force : menu.hidden;
      if (shouldOpen) openDropdown(kind);
      else closeDropdown(kind);
    }

    function setPersonSelection(kind, value) {
      const input = $(`${kind}Select`);
      if (!input || !value) return;
      input.value = value;
      syncPersonToggle(kind);
      renderOverview();
      analyze();
      closeAllDropdowns();
    }

    function driverSummaryMarkup(driverCode, label) {
      const driver = state.driversByCode.get(driverCode);
      const team = state.teamsByName.get(driver?.team);
      const accent = team?.primary_colour || driver?.team_colour || "#0a84ff";
      const teamName = team?.team || driver?.team || "Unknown team";
      const driverName = driver?.driver_name || driverCode || "Unknown driver";
      const number = driver?.official_number ?? driver?.driver_number ?? "--";
      const logoUrl = team?.logo_url || "";
      const logo = `
        <span class="control-meta-logo control-meta-logo--fallback" style="background:${escapeHtml(accent)};color:${escapeHtml(contrastColour(accent))};">
          ${teamLogoMarkup(teamName, logoUrl)}
        </span>`;
      return `
        <div class="control-meta-head">
          <span class="control-meta-label">${escapeHtml(label)}</span>
          <span class="control-meta-number" style="background:${escapeHtml(accent)};color:${escapeHtml(contrastColour(accent))};">#${escapeHtml(number)}</span>
        </div>
        <div class="control-meta-body">
          ${logo}
          <div class="control-meta-text">
            <strong>${escapeHtml(driverName)}</strong>
            <span>${escapeHtml(teamName)}</span>
          </div>
        </div>
      `;
    }

    function updateControlBadges() {
      if (!state.bootstrap) return;
      syncRaceToggle();

      const applyTeamBadge = (badgeNode, driverCode) => {
        if (!badgeNode) return;
        const driver = state.driversByCode.get(driverCode);
        const team = state.teamsByName.get(driver?.team);
        const accent = team?.primary_colour || driver?.team_colour || "#0a84ff";
        const logoUrl = team?.logo_url || "";
        badgeNode.title = driver ? `${driver.driver_name} · ${driver.team}` : "Driver";
        badgeNode.style.background = accent;
        badgeNode.title = driver ? `${driver.driver_name} - ${driver.team}` : "Driver";
        badgeNode.style.color = contrastColour(accent);
        badgeNode.innerHTML = teamLogoMarkup(driver?.team, logoUrl);
      };

      applyTeamBadge($("driverBadge"), $("driverSelect")?.value || state.bootstrap.default_driver);
      applyTeamBadge($("compareBadge"), $("compareSelect")?.value || state.bootstrap.default_compare);
    }

    function renderSelectionMeta() {
      if (!state.bootstrap) return;
      const driverCode = $("driverSelect")?.value || state.bootstrap.default_driver;
      const compareCode = $("compareSelect")?.value || state.bootstrap.default_compare;
      const overviewDriverCard = $("overviewDriverCard");
      const overviewCompareCard = $("overviewCompareCard");
      if (overviewDriverCard) overviewDriverCard.innerHTML = driverSummaryMarkup(driverCode, "Driver focus");
      if (overviewCompareCard) overviewCompareCard.innerHTML = driverSummaryMarkup(compareCode, "Rival focus");
      updateControlBadges();
    }

    function renderOverview() {
      if (!state.bootstrap) return;
      const races = Array.isArray(state.bootstrap.calendar) ? state.bootstrap.calendar : [];
      const drivers = Array.isArray(state.bootstrap.drivers) ? state.bootstrap.drivers : [];
      const teams = Array.isArray(state.bootstrap.teams) ? state.bootstrap.teams : [];
      const completedRaces = races.filter((race) => race.status === "completed");
      const raceNode = $("overviewRaceCount");
      const driverNode = $("overviewDriverCount");
      const teamNode = $("overviewTeamCount");
      const raceNameNode = $("overviewRaceName");
      const circuitNode = $("overviewRaceCircuit");
      const flagNode = $("overviewRaceFlag");
      const selectedRace = selectedRaceMeta();
      if (raceNode) raceNode.textContent = String(completedRaces.length);
      if (driverNode) driverNode.textContent = String(drivers.length);
      if (teamNode) teamNode.textContent = String(teams.length);
      if (selectedRace) {
        if (raceNameNode) raceNameNode.textContent = selectedRace.race_name;
        if (circuitNode) circuitNode.textContent = `${selectedRace.circuit}`;
        if (flagNode) flagNode.textContent = `${selectedRace.country}`;
      }
      renderSelectionMeta();
      if (pageName() === "overview") {
        setStatus("Overview ready", false);
        setRadio("Use the page tabs to open analysis, strategy, or exports.");
      }
    }

    function buildSelectors() {
      const {calendar, drivers, teams, default_race, default_driver, default_compare} = state.bootstrap;
      state.teamsByName = new Map(teams.map((team) => [team.team, team]));
      state.driversByCode = new Map(drivers.map((driver) => [driver.driver_code, driver]));

      const raceSelect = $("raceSelect");
      const driverSelect = $("driverSelect");
      const compareSelect = $("compareSelect");
      if (raceSelect) {
        raceSelect.value = default_race;
      }

      const driverOptions = drivers.map((driver) => (
        `<option value="${escapeHtml(driver.driver_code)}">${escapeHtml(driver.driver_code)} · ${escapeHtml(driver.driver_name)} · ${escapeHtml(driver.team)} #${escapeHtml(driver.official_number ?? driver.driver_number ?? "--")}</option>`
      )).join("");
      if (driverSelect) {
        driverSelect.innerHTML = driverOptions;
        driverSelect.value = default_driver;
      }
      if (compareSelect) {
        compareSelect.innerHTML = driverOptions;
        compareSelect.value = default_compare;
      }
      const normalizeDriverSelect = (select) => {
        if (!select) return;
        Array.from(select.options).forEach((option) => {
          const driver = state.driversByCode.get(option.value);
          if (driver) option.textContent = driverChoiceLabel(driver);
        });
      };
      normalizeDriverSelect(driverSelect);
      normalizeDriverSelect(compareSelect);
      renderRaceMenu();
      syncRaceToggle();
      updateControlBadges();
    }

    function syncRaceToggle() {
      const race = selectedRaceMeta() || state.bootstrap?.calendar?.find((item) => item.race_name === state.bootstrap?.default_race) || null;
      const labelNode = $("raceToggleLabel");
      const metaNode = $("raceToggleMeta");
      if (labelNode) labelNode.textContent = race?.race_name || "Select race";
      if (metaNode) {
        const status = race?.status === "completed" ? "Completed" : "Upcoming";
        metaNode.textContent = race ? `${status} - ${race.country}` : "Race";
      }
      const badge = $("raceBadge");
      if (badge) {
        badge.textContent = countryFlagEmoji(race?.country || "");
        badge.title = race ? `${race.country} flag` : "Race flag";
      }
      const menu = $("raceMenu");
      const current = selectedRaceValue();
      if (menu) {
        menu.querySelectorAll(".race-menu-item").forEach((item) => {
          item.setAttribute("aria-selected", item.dataset.race === current ? "true" : "false");
        });
      }
    }

    function updateControlBadges() {
      if (!state.bootstrap) return;
      syncRaceToggle();
      syncPersonToggle("driver");
      syncPersonToggle("compare");
    }

    function renderSelectionMeta() {
      if (!state.bootstrap) return;
      const driverCode = selectedPersonValue("driver");
      const compareCode = selectedPersonValue("compare");
      const overviewDriverCard = $("overviewDriverCard");
      const overviewCompareCard = $("overviewCompareCard");
      if (overviewDriverCard) overviewDriverCard.innerHTML = driverSummaryMarkup(driverCode, "Driver focus");
      if (overviewCompareCard) overviewCompareCard.innerHTML = driverSummaryMarkup(compareCode, "Rival focus");
      updateControlBadges();
    }

    function buildSelectors() {
      const {calendar, default_race, default_driver, default_compare} = state.bootstrap;
      const teams = Array.isArray(state.bootstrap.teams) ? state.bootstrap.teams : [];
      const drivers = Array.isArray(state.bootstrap.drivers) ? state.bootstrap.drivers : [];
      state.teamsByName = new Map(teams.map((team) => [team.team, team]));
      state.driversByCode = new Map(drivers.map((driver) => [driver.driver_code, driver]));

      const raceSelect = $("raceSelect");
      const driverSelect = $("driverSelect");
      const compareSelect = $("compareSelect");
      if (raceSelect) raceSelect.value = default_race;
      if (driverSelect) driverSelect.value = default_driver;
      if (compareSelect) compareSelect.value = default_compare;

      renderRaceMenu();
      renderPersonMenu("driver");
      renderPersonMenu("compare");
      syncRaceToggle();
      syncPersonToggle("driver");
      syncPersonToggle("compare");
      updateControlBadges();
    }

    function loadRemoteImage(image, url, altText) {
      image.hidden = true;
      image.alt = altText;
      image.onload = () => {
        image.hidden = false;
      };
      image.onerror = () => {
        image.hidden = true;
      };
      if (url) image.src = url;
      else image.removeAttribute("src");
    }

    function selectedRaceMeta() {
      const raceName = $("raceSelect").value;
      return state.bootstrap?.calendar?.find((race) => race.race_name === raceName) || null;
    }

    function activeTrackMap() {
      if (state.analysis && Object.prototype.hasOwnProperty.call(state.analysis, "track_map")) {
        return state.analysis.track_map;
      }
      return state.bootstrap?.track_map || null;
    }

    function placeTrackMarker(marker, point, neighbour, offset = 18, rotate = false) {
      if (!marker || !point || !neighbour) return;
      const dx = neighbour.x - point.x;
      const dy = neighbour.y - point.y;
      const distance = Math.max(Math.hypot(dx, dy), 1);
      const x = point.x + (-dy / distance) * offset;
      const y = point.y + (dx / distance) * offset;
      const angle = Math.atan2(dy, dx) * 180 / Math.PI;
      marker.setAttribute("transform", rotate
        ? `translate(${x.toFixed(2)} ${y.toFixed(2)}) rotate(${angle.toFixed(2)})`
        : `translate(${x.toFixed(2)} ${y.toFixed(2)})`);
    }

    function pointsBoundingBox(points) {
      if (!points.length) {
        return {minX: 0, minY: 0, maxX: 0, maxY: 0, width: 0, height: 0};
      }
      let minX = points[0].x;
      let minY = points[0].y;
      let maxX = points[0].x;
      let maxY = points[0].y;
      for (const point of points) {
        if (point.x < minX) minX = point.x;
        if (point.y < minY) minY = point.y;
        if (point.x > maxX) maxX = point.x;
        if (point.y > maxY) maxY = point.y;
      }
      return {minX, minY, maxX, maxY, width: Math.max(1, maxX - minX), height: Math.max(1, maxY - minY)};
    }

    function normalizeTrackPoints(points, targetWidth = 1000, targetHeight = 620, padding = 72) {
      const bounds = pointsBoundingBox(points);
      const innerWidth = Math.max(1, targetWidth - padding * 2);
      const innerHeight = Math.max(1, targetHeight - padding * 2);
      const scale = Math.min(innerWidth / bounds.width, innerHeight / bounds.height);
      const scaledWidth = bounds.width * scale;
      const scaledHeight = bounds.height * scale;
      const offsetX = (targetWidth - scaledWidth) / 2 - bounds.minX * scale;
      const offsetY = (targetHeight - scaledHeight) / 2 - bounds.minY * scale;
      return points.map((point) => ({
        x: point.x * scale + offsetX,
        y: point.y * scale + offsetY,
      }));
    }

    function pathDataFromPoints(points) {
      if (!points.length) return "";
      const segments = [`M ${points[0].x.toFixed(2)} ${points[0].y.toFixed(2)}`];
      for (let index = 1; index < points.length; index += 1) {
        segments.push(`L ${points[index].x.toFixed(2)} ${points[index].y.toFixed(2)}`);
      }
      return segments.join(" ");
    }

    function sampleTrackPoints(svg, trackMap, sampleCount = 320) {
      const namespace = "http://www.w3.org/2000/svg";
      const sourcePath = document.createElementNS(namespace, "path");
      sourcePath.setAttribute("d", trackMap.path_d);
      if (trackMap.path_transform) {
        sourcePath.setAttribute("transform", trackMap.path_transform);
      }
      sourcePath.setAttribute("fill", "none");
      sourcePath.setAttribute("stroke", "none");
      sourcePath.setAttribute("visibility", "hidden");
      sourcePath.setAttribute("aria-hidden", "true");
      svg.appendChild(sourcePath);
      const length = Math.max(0, sourcePath.getTotalLength());
      const points = [];
      const totalSamples = Math.max(2, sampleCount);
      for (let index = 0; index < totalSamples; index += 1) {
        const position = sourcePath.getPointAtLength(length * (index / (totalSamples - 1)));
        points.push({x: position.x, y: position.y});
      }
      sourcePath.remove();
      return {points, length};
    }

    function stopTrackAnimation() {
      if (state.trackAnimationFrame !== null) {
        cancelAnimationFrame(state.trackAnimationFrame);
        state.trackAnimationFrame = null;
      }
    }

    function animateTrack() {
      const svg = $("trackSvg");
      const path = svg?.querySelector("#trackRoute");
      const marker = svg?.querySelector("#trackCarIcon");
      if (!path || !marker) return;
      const length = path.getTotalLength();
      const elapsed = performance.now() - state.trackAnimationStart;
      const duration = Number(svg.dataset.duration || "9000");
      const progress = (elapsed % duration) / duration;
      const position = path.getPointAtLength(length * progress);
      const nextPoint = path.getPointAtLength(length * ((progress + 0.01) % 1));
      const angle = Math.atan2(nextPoint.y - position.y, nextPoint.x - position.x) * 180 / Math.PI;
      marker.setAttribute("transform", `translate(${position.x.toFixed(2)} ${position.y.toFixed(2)}) rotate(${angle.toFixed(2)})`);
      state.trackAnimationFrame = requestAnimationFrame(animateTrack);
    }

    function renderTrackView() {
      const race = selectedRaceMeta();
      if (!race) return;
      const svg = $("trackSvg");
      const trackImage = $("trackMapImage");
      const title = $("trackRaceName");
      const subtitle = $("trackCircuitName");
      const badge = $("trackLapBadge");
      const trackMap = activeTrackMap();
      const lapCount = Number(race.total_laps || 0);
      title.textContent = race.race_name;
      subtitle.textContent = race.circuit;
      badge.textContent = race.status === "completed" ? `LAPS ${lapCount}` : "UPCOMING";
      svg.dataset.duration = String(Math.max(6000, lapCount * 120));
      svg.setAttribute("viewBox", "0 0 1000 620");

      if (race.track_image_url) {
        stopTrackAnimation();
        svg.innerHTML = "";
        if (trackImage) {
          trackImage.hidden = false;
          trackImage.alt = `${race.race_name} circuit layout`;
          if (trackImage.getAttribute("src") !== race.track_image_url) {
            trackImage.src = race.track_image_url;
          }
        }
        return;
      }

      if (trackImage) {
        trackImage.hidden = true;
        trackImage.removeAttribute("src");
      }

      if (!trackMap?.path_d) {
        stopTrackAnimation();
        svg.innerHTML = `
          <text x="50%" y="50%" text-anchor="middle" fill="#9ca8bd" font-size="18" font-weight="700">Trusted circuit map loading…</text>
        `;
        return;
      }

      const sampleCount = Math.max(240, Math.min(520, Math.round((lapCount || 60) * 6)));
      svg.innerHTML = `
        <defs>
          <linearGradient id="trackCarGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#ffffff"/>
            <stop offset="100%" stop-color="#00e5ff"/>
          </linearGradient>
        </defs>
      `;

      const {points: rawPoints, length} = sampleTrackPoints(svg, trackMap, sampleCount);
      if (!rawPoints.length || length <= 0) {
        stopTrackAnimation();
        svg.innerHTML = `
          <text x="50%" y="50%" text-anchor="middle" fill="#9ca8bd" font-size="18" font-weight="700">Circuit map unavailable</text>
        `;
        return;
      }

      const points = normalizeTrackPoints(rawPoints, 1000, 620, 72);
      const trackPath = pathDataFromPoints(points);
      const closedGap = Math.hypot(points[0].x - points[points.length - 1].x, points[0].y - points[points.length - 1].y);
      const endIndex = closedGap < 18 ? Math.max(1, Math.floor(points.length * 0.96)) : points.length - 1;
      const startPoint = points[0];
      const startNext = points[Math.min(1, points.length - 1)];
      const endPoint = points[endIndex];
      const endPrev = points[Math.max(0, endIndex - 1)];

      svg.innerHTML = `
        <defs>
          <linearGradient id="trackCarGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#ffffff"/>
            <stop offset="100%" stop-color="#00e5ff"/>
          </linearGradient>
        </defs>
        <path id="trackGlowPath" class="track-lane-glow" d="${trackPath}"></path>
        <path id="trackRoute" class="track-lane-outline" d="${trackPath}"></path>
        <path class="track-lane-core" d="${trackPath}"></path>
        <path class="track-lane-spark" d="${trackPath}"></path>
        <g id="trackStartMarker" class="track-marker track-marker-start">
          <circle r="16"></circle>
          <text y="0.8">S</text>
        </g>
        <g id="trackEndMarker" class="track-marker track-marker-end">
          <circle r="16"></circle>
          <text y="0.8">F</text>
        </g>
        <g id="trackCarIcon" class="track-car-dot">
          <rect class="track-car-body" x="-14" y="-8" width="28" height="16" rx="8"></rect>
          <rect class="track-car-detail" x="-6" y="-4" width="12" height="8" rx="4"></rect>
        </g>
      `;

      const marker = svg.querySelector("#trackCarIcon");
      const route = svg.querySelector("#trackRoute");
      if (!marker || !route) return;
      placeTrackMarker(svg.querySelector("#trackStartMarker"), startPoint, startNext, 20, false);
      placeTrackMarker(svg.querySelector("#trackEndMarker"), endPoint, endPrev, 20, false);
      placeTrackMarker(marker, startPoint, startNext, 0, true);
      stopTrackAnimation();
      state.trackAnimationStart = performance.now();
      state.trackAnimationFrame = requestAnimationFrame(animateTrack);
    }

    function renderDriverIdentity(result) {
      const driver = state.driversByCode.get(result.driver_code);
      const team = state.teamsByName.get(result.team);
      const primary = team?.primary_colour || result.team_colour || "#00e5ff";
      const displayNumber = driver?.official_number || result.driver_number;
      $("driverComposite").style.background = `
        radial-gradient(circle at 20% 18%, ${primary}35, transparent 12rem),
        radial-gradient(circle at 78% 50%, rgba(0, 229, 255, 0.10), transparent 14rem),
        linear-gradient(160deg, rgba(255,255,255,0.08), rgba(255,255,255,0.02))
      `;
      $("driverPortrait").style.filter = `drop-shadow(0 20px 28px rgba(0, 0, 0, 0.42))`;
      $("driverName").textContent = result.driver_name;
      $("driverNumberTag").textContent = `#${displayNumber}`;
      loadRemoteImage($("driverPortrait"), driver?.photo_url, `${result.driver_name} official 2026 race-suit portrait`);
      loadRemoteImage($("teamCarImage"), team?.car_image_url, `${result.team} 2026 Formula 1 car side-view render`);
    }

    function renderStrategyInsights(insights) {
      const headline = $("strategyHeadline");
      const intro = $("strategyIntro");
      const cards = $("strategyCards");
      const notes = $("strategyNotes");
      if (!headline || !intro || !cards || !notes) return;

      if (!insights) {
        headline.textContent = "Select a completed race to open the strategy room.";
        intro.textContent = "This page compares the selected driver against the rival using clean pace, pit timing, tyre management, stint strength, and the final race-engineer score.";
        cards.innerHTML = `<div class="strategy-card is-empty">Strategy cards will appear after analysis.</div>`;
        notes.innerHTML = `<div class="empty">Choose a completed race and press Analyze Race to see stint-by-stint strategy notes.</div>`;
        return;
      }

      headline.textContent = insights.headline || "Strategy battle room";
      intro.textContent = insights.intro || "Strategy insights loaded.";
      cards.innerHTML = (insights.cards || []).map((card) => {
        const winnerClass = card.winner === "selected" ? "is-selected" : card.winner === "rival" ? "is-rival" : "is-neutral";
        return `<div class="strategy-card ${winnerClass}">
          <small>${escapeHtml(card.label)}</small>
          <strong>${escapeHtml(card.value)}</strong>
          <span>${escapeHtml(card.detail)}</span>
        </div>`;
      }).join("");
      notes.innerHTML = (insights.notes || []).map((note) => `<div class="strategy-note">${escapeHtml(note)}</div>`).join("");
    }

    function renderScore(result) {
      const score = Number(result.race_engineer_score || 0);
      const colour = score >= 85 ? "#39ff8f" : score >= 72 ? "#ffd12e" : "#ff4560";
      $("scoreRing").style.background = `conic-gradient(${colour} ${score * 3.6}deg, rgba(255,255,255,0.11) 0deg)`;
      $("scoreValue").textContent = `${score.toFixed(1)}`;
      $("rating").textContent = result.rating;
      $("verdict").textContent = result.race_engineer_verdict;

      const best = result.best_stint || {};
      const metrics = [
        ["Clean pace", `${Number(result.average_clean_pace).toFixed(3)} s`],
        ["Fastest lap", `${Number(result.fastest_lap).toFixed(3)} s`],
        ["Consistency", `${Number(result.consistency_score).toFixed(1)} / 100`],
        ["Tyre mgmt", `${Number(result.tyre_management_score).toFixed(1)} / 100`],
        ["Pit stops", `${result.pit_stops}`],
        ["Best stint", `${best.compound || "-"} · L${best.start_lap || "-"}-${best.end_lap || "-"}`]
      ];
      $("metrics").innerHTML = metrics.map(([label, value]) => (
        `<div class="metric"><small>${escapeHtml(label)}</small><strong>${escapeHtml(value)}</strong></div>`
      )).join("");

      const badges = Array.isArray(result.badges) ? result.badges : String(result.badge_earned || "").split(", ");
      $("badges").innerHTML = badges.filter(Boolean).map((badge) => `<span class="badge">${escapeHtml(badge)}</span>`).join("");
    }

    function renderLeaderboard(summary) {
      const maxScore = Math.max(...summary.map((row) => Number(row.race_engineer_score || 0)), 1);
      const focusCodes = state.analysis?.strategy_insights?.focus_codes || [];
      const selectedCode = focusCodes[0] || state.analysis?.result?.driver_code;
      const rivalCode = focusCodes[1];
      $("leaderboard").innerHTML = summary
        .slice()
        .sort((a, b) => Number(b.race_engineer_score) - Number(a.race_engineer_score))
        .map((row) => {
          const team = state.teamsByName.get(row.team);
          const colour = team?.primary_colour || "#00e5ff";
          const width = Number(row.race_engineer_score || 0) / maxScore * 100;
          const rowClass = row.driver_code === selectedCode ? "is-focus" : row.driver_code === rivalCode ? "is-rival" : "";
          return `<div class="leader-row ${rowClass}">
            <span>P${escapeHtml(row.final_position)}</span>
            <strong>${escapeHtml(row.driver_code)}</strong>
            <span class="leader-meta">
              <span class="bar-track"><span class="bar-fill" style="width:${width}%;background:${escapeHtml(colour)}"></span></span>
              <small>${escapeHtml(row.rating || "")}</small>
            </span>
            <span>${Number(row.race_engineer_score).toFixed(1)}</span>
          </div>`;
        }).join("");
    }

    function drawPaceChart(analysis) {
      const canvas = $("paceCanvas");
      const ctx = canvas.getContext("2d");
      const rect = canvas.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.max(600, Math.floor(rect.width * dpr));
      canvas.height = Math.floor(330 * dpr);
      ctx.scale(dpr, dpr);
      const width = canvas.width / dpr;
      const height = canvas.height / dpr;
      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = "#090e18";
      ctx.fillRect(0, 0, width, height);

      const entries = Object.entries(analysis.traces || {});
      const allPoints = entries.flatMap(([, points]) => points);
      state.paceChartPoints = [];
      if (!allPoints.length) return;

      const pad = {left: 56, right: 28, top: 34, bottom: 46};
      const lapMin = Math.min(...allPoints.map((p) => p.lap));
      const lapMax = Math.max(...allPoints.map((p) => p.lap));
      const timeMin = Math.min(...allPoints.map((p) => p.time)) - 0.3;
      const timeMax = Math.max(...allPoints.map((p) => p.time)) + 0.3;
      const x = (lap) => pad.left + (lap - lapMin) / Math.max(1, lapMax - lapMin) * (width - pad.left - pad.right);
      const y = (time) => pad.top + (time - timeMin) / Math.max(0.1, timeMax - timeMin) * (height - pad.top - pad.bottom);

      ctx.fillStyle = "#f5f7fb";
      ctx.font = "800 13px Segoe UI";
      ctx.fillText("Clean laps only · lower line = faster pace", pad.left, 20);

      ctx.strokeStyle = "rgba(255,255,255,0.10)";
      ctx.lineWidth = 1;
      ctx.fillStyle = "#9ca8bd";
      ctx.font = "12px Segoe UI";
      for (let i = 0; i < 5; i++) {
        const yy = pad.top + i / 4 * (height - pad.top - pad.bottom);
        ctx.beginPath();
        ctx.moveTo(pad.left, yy);
        ctx.lineTo(width - pad.right, yy);
        ctx.stroke();
        const value = timeMin + i / 4 * (timeMax - timeMin);
        ctx.fillText(`${value.toFixed(1)}s`, 12, yy + 4);
      }

      entries.forEach(([code, points], index) => {
        const result = analysis.summary.find((row) => row.driver_code === code);
        const colour = state.teamsByName.get(result?.team)?.primary_colour || (index ? "#ffd12e" : "#00e5ff");
        ctx.strokeStyle = colour;
        ctx.lineWidth = 2.4;
        ctx.beginPath();
        points.forEach((point, pointIndex) => {
          const xx = x(point.lap);
          const yy = y(point.time);
          state.paceChartPoints.push({
            x: xx,
            y: yy,
            code,
            lap: point.lap,
            time: point.time,
            compound: point.compound,
            colour
          });
          if (pointIndex === 0) ctx.moveTo(xx, yy);
          else ctx.lineTo(xx, yy);
        });
        ctx.stroke();
        ctx.fillStyle = colour;
        const best = points.reduce((current, point) => Number(point.time) < Number(current.time) ? point : current, points[0]);
        ctx.beginPath();
        ctx.arc(x(best.lap), y(best.time), 5, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = "#f5f7fb";
        ctx.font = "700 11px Segoe UI";
        ctx.fillText(`${code} best L${best.lap}`, x(best.lap) + 8, y(best.time) - 8);
        ctx.fillStyle = colour;
        const last = points[points.length - 1];
        ctx.beginPath();
        ctx.arc(x(last.lap), y(last.time), 4, 0, Math.PI * 2);
        ctx.fill();
        ctx.font = "800 13px Segoe UI";
        ctx.fillText(code, x(last.lap) - 34, y(last.time) - 8);
      });

      ctx.fillStyle = "#9ca8bd";
      ctx.font = "12px Segoe UI";
      ctx.fillText(`Lap ${lapMin}`, pad.left, height - 14);
      ctx.fillText(`Lap ${lapMax}`, width - pad.right - 48, height - 14);
    }

    function handlePaceHover(event) {
      const canvas = $("paceCanvas");
      const tooltip = $("paceTooltip");
      const readout = $("paceReadout");
      if (!canvas || !tooltip || !state.paceChartPoints.length) return;
      const rect = canvas.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      let nearest = null;
      let nearestDistance = Infinity;
      for (const point of state.paceChartPoints) {
        const distance = Math.hypot(point.x - x, point.y - y);
        if (distance < nearestDistance) {
          nearest = point;
          nearestDistance = distance;
        }
      }
      if (!nearest || nearestDistance > 24) {
        tooltip.hidden = true;
        if (readout) readout.textContent = "Move over the pace trace to inspect a clean lap.";
        return;
      }
      tooltip.hidden = false;
      tooltip.style.left = `${Math.min(rect.width - 168, Math.max(8, nearest.x + 12))}px`;
      tooltip.style.top = `${Math.max(8, nearest.y - 54)}px`;
      tooltip.innerHTML = `<strong style="color:${escapeHtml(nearest.colour)}">${escapeHtml(nearest.code)} · Lap ${escapeHtml(nearest.lap)}</strong>
        ${Number(nearest.time).toFixed(3)}s · ${escapeHtml(nearest.compound)} tyre`;
      if (readout) {
        readout.textContent = `${nearest.code} clean lap ${nearest.lap}: ${Number(nearest.time).toFixed(3)}s on ${nearest.compound}.`;
      }
    }

    function hidePaceHover() {
      const tooltip = $("paceTooltip");
      const readout = $("paceReadout");
      if (tooltip) tooltip.hidden = true;
      if (readout) readout.textContent = "Move over the pace trace to inspect a clean lap.";
    }

    function renderStrategy(strategy) {
      const insights = state.analysis?.strategy_insights || {};
      const focusCodes = insights.focus_codes || [];
      const selectedCode = focusCodes[0];
      const rivalCode = focusCodes[1];
      const orderedRows = [];
      const focusRows = strategy.filter((row) => focusCodes.includes(row.driver_code));
      const restRows = strategy.filter((row) => !focusCodes.includes(row.driver_code));
      if (focusRows.length) {
        orderedRows.push({section: "Selected battle"});
        orderedRows.push(...focusRows);
      }
      if (restRows.length) {
        orderedRows.push({section: "Rest of the grid"});
        orderedRows.push(...restRows);
      }

      $("strategyList").innerHTML = orderedRows.map((row) => {
        if (row.section) {
          return `<div class="timeline-section-label">${escapeHtml(row.section)}</div>`;
        }
        const stints = row.stints.map((stint) => (
          `<span class="stint" title="${escapeHtml(stint.compound)} L${stint.start}-${stint.end}" style="flex:${stint.laps};background:${escapeHtml(stint.colour)}"></span>`
        )).join("");
        const pits = row.pit_laps.map((lap) => {
          const left = ((lap - 0.5) / row.total_laps) * 100;
          return `<span class="pit-marker" title="Pit lap ${lap}" style="left:${left}%"></span>`;
        }).join("");
        const rowClass = row.driver_code === selectedCode ? "is-focus" : row.driver_code === rivalCode ? "is-rival" : "";
        const plan = row.stints.map((stint) => `${stint.compound} L${stint.start}-${stint.end}`).join(" → ");
        const pitText = row.pit_laps.length ? row.pit_laps.map((lap) => `L${lap}`).join(", ") : "No stops";
        const role = row.driver_code === selectedCode ? "Driver" : row.driver_code === rivalCode ? "Rival" : "Grid";
        return `<div class="strategy-row ${rowClass}">
          <div class="strategy-label">P${escapeHtml(row.position)} · ${escapeHtml(row.driver_code)}</div>
          <div class="timeline-wrap">
            <div class="timeline">${stints}${pits}</div>
            <div class="strategy-meta">${escapeHtml(plan)} · pits ${escapeHtml(pitText)} · ${escapeHtml(role)}</div>
          </div>
        </div>`;
      }).join("");
    }

    function renderAnalysis(data) {
      state.analysis = data;
      renderTrackView();
      if (!data.ok) {
        setStatus("Upcoming · no data", true);
        setRadio(data.message || "Race data not available yet.");
        renderStrategyInsights(null);
        hidePaceHover();
        $("metrics").innerHTML = "";
        $("badges").innerHTML = "";
        $("leaderboard").innerHTML = `<div class="empty">${escapeHtml(data.message || "No completed race data.")}</div>`;
        $("strategyList").innerHTML = `<div class="empty">${escapeHtml(data.message || "No completed race data.")}</div>`;
        return;
      }

      setStatus("Race data loaded", false);
      renderDriverIdentity(data.result);
      renderScore(data.result);
      renderStrategyInsights(data.strategy_insights);
      renderLeaderboard(data.summary);
      renderStrategy(data.strategy);
      drawPaceChart(data);
      const tyre = data.tyre_fit ? ` Tyre model RMSE: ${Number(data.tyre_fit.rmse).toFixed(3)}s.` : "";
      setRadio(`${data.comparison.verdict}${tyre}`);
    }

    async function analyze() {
      const payload = selectedPayload();
      const requestId = ++state.analysisRequestId;
      const params = new URLSearchParams(payload);
      document.body.classList.add("loading");
      try {
        const data = await getJson(`/api/analyze?${params.toString()}`);
        if (requestId !== state.analysisRequestId || data.race_name !== payload.race) return;
        renderAnalysis(data);
      } catch (error) {
        if (requestId !== state.analysisRequestId) return;
        setStatus("Analysis error", true);
        setRadio(error.message);
      } finally {
        if (requestId === state.analysisRequestId) {
          document.body.classList.remove("loading");
        }
      }
    }

    function selectedExportPayload(kind) {
      const payload = selectedPayload();
      if (kind === "plot") payload.plot_type = $("plotSelect")?.value || "all";
      if (kind === "replay") payload.replay_type = $("replaySelect")?.value || "all";
      if (kind === "report") payload.report_type = $("reportSelect")?.value || "pdf";
      return payload;
    }

    function outputPreviewMarkup(file) {
      const url = String(file.url || "");
      const lower = url.toLowerCase();
      const isReplay = file.kind === "replay" && lower.endsWith(".html");
      const link = `<div class="modal-link-row"><a href="${escapeHtml(url)}" target="_blank" rel="noreferrer">Open in new tab</a><a href="${escapeHtml(url)}" download>Download file</a></div>`;
      if (lower.endsWith(".png") || lower.endsWith(".jpg") || lower.endsWith(".jpeg") || lower.endsWith(".webp")) {
        return `<img src="${escapeHtml(url)}" alt="${escapeHtml(file.title || file.name)}">${link}`;
      }
      if (lower.endsWith(".html") || lower.endsWith(".pdf") || lower.endsWith(".md") || lower.endsWith(".csv")) {
        const frameClass = isReplay ? "preview-frame preview-frame--replay" : "preview-frame preview-frame--document";
        const replayFlag = isReplay ? ' data-compact-replay="true"' : "";
        return `<iframe class="${frameClass}" src="${escapeHtml(url)}" title="${escapeHtml(file.title || file.name)}"${replayFlag}></iframe>${link}`;
      }
      return `<div class="empty">Preview is not available for this file type, but you can open or download it.</div>${link}`;
    }

    function compactReplayFrame(frame) {
      if (!frame || frame.dataset.compacted === "true") return;
      try {
        const doc = frame.contentDocument || frame.contentWindow?.document;
        if (!doc || !doc.head) return;
        const style = doc.createElement("style");
        style.textContent = `
          html, body { margin: 0 !important; background: #070a12 !important; overflow: hidden !important; }
          .animation {
            width: 100% !important;
            max-width: 100% !important;
            display: flex !important;
            flex-direction: column !important;
            align-items: center !important;
            justify-content: flex-start !important;
            box-sizing: border-box !important;
            padding: 8px !important;
          }
          .animation > img {
            max-width: 100% !important;
            width: auto !important;
            height: min(300px, 48vh) !important;
            object-fit: contain !important;
          }
          .anim-controls {
            width: min(100%, 620px) !important;
            margin-top: 4px !important;
          }
          input[type=range].anim-slider {
            width: 100% !important;
            max-width: 100% !important;
          }
          .anim-buttons {
            display: flex !important;
            flex-wrap: wrap !important;
            justify-content: center !important;
            gap: 4px !important;
            margin: 4px 0 !important;
          }
          .anim-buttons button {
            width: 30px !important;
            height: 26px !important;
            padding: 0 !important;
            font-size: 12px !important;
          }
          .anim-state {
            margin: 2px 0 0 !important;
            font-size: 12px !important;
          }
        `;
        doc.head.appendChild(style);
        doc.documentElement.scrollTop = 0;
        doc.body.scrollTop = 0;
        frame.dataset.compacted = "true";
      } catch (error) {
        console.warn("Could not compact replay preview", error);
      }
    }

    function openOutputModal(file) {
      if (!file || !file.url) return;
      const inline = $("outputInlinePreview");
      if (inline) {
        inline.hidden = false;
        inline.innerHTML = `<div class="inline-preview-header">
          <div>
            <div class="inline-preview-title">${escapeHtml(file.title || file.name || "Generated output")}</div>
            <div class="inline-preview-summary">${escapeHtml(file.summary || file.description || "Generated from the selected race.")}</div>
          </div>
          <button class="inline-preview-close" type="button" data-close-modal="true">Close preview</button>
        </div>
        ${outputPreviewMarkup(file)}`;
        inline.querySelectorAll("[data-compact-replay]").forEach((frame) => {
          frame.addEventListener("load", () => compactReplayFrame(frame), {once: true});
        });
        inline.scrollIntoView({behavior: "smooth", block: "start"});
        return;
      }
      $("outputModalTitle").textContent = file.title || file.name || "Generated output";
      $("outputModalSummary").textContent = file.summary || file.description || "Generated from the selected race.";
      $("outputModalBody").innerHTML = outputPreviewMarkup(file);
      $("outputModalBody").querySelectorAll("[data-compact-replay]").forEach((frame) => {
        frame.addEventListener("load", () => compactReplayFrame(frame), {once: true});
      });
      $("outputModalBackdrop").hidden = false;
    }

    function closeOutputModal() {
      const backdrop = $("outputModalBackdrop");
      if (!backdrop) return;
      backdrop.hidden = true;
      $("outputModalBody").innerHTML = "";
      const inline = $("outputInlinePreview");
      if (inline) {
        inline.hidden = true;
        inline.innerHTML = "";
      }
    }

    function renderFiles(data) {
      const area = $("outputArea");
      const hint = $("outputHint");
      if (!area) return;
      if (!data.ok) {
        area.innerHTML = `<div class="empty">${escapeHtml(data.message || "No files generated.")}</div>`;
        if (hint) hint.textContent = data.message || "No files generated.";
        return;
      }
      const files = data.files || [];
      if (!files.length) {
        area.innerHTML = `<div class="empty">${escapeHtml(data.message || "No files were returned.")}</div>`;
        if (hint) hint.textContent = data.message || "No files were returned.";
        return;
      }
      const grouped = {
        plot: files.filter((file) => file.kind === "plot"),
        replay: files.filter((file) => file.kind === "replay"),
        report: files.filter((file) => file.kind === "report"),
        other: files.filter((file) => !["plot", "replay", "report"].includes(file.kind)),
      };
      const makeCards = (items, prefix) => items.map((file, index) => {
        const isImage = String(file.url || "").toLowerCase().endsWith(".png");
        const image = isImage ? `<img src="${escapeHtml(file.url)}" alt="${escapeHtml(file.name)}">` : "";
        return `<button class="file-card" type="button" data-output-kind="${escapeHtml(file.kind || "output")}" data-output-index="${prefix}-${index}">
          <span class="file-kind">${escapeHtml(file.kind || "output")}</span>
          ${image}
          <div class="file-name">${escapeHtml(file.title || file.name)}</div>
          <div class="file-summary">${escapeHtml(file.summary || file.description || file.name)}</div>
        </button>`;
      }).join("");
      const sections = [
        {
          key: "plot",
          title: "Plots",
          note: "Charts appear here. This column stays on the left so you can scan the figure without scrolling the whole page.",
          cls: "",
        },
        {
          key: "replay",
          title: "Replays",
          note: "Animation outputs appear here. This column stays on the right so it balances the plots.",
          cls: "",
        },
        {
          key: "report",
          title: "Reports",
          note: "PDF, Markdown, and CSV exports appear here across the full width.",
          cls: "output-column--reports",
        },
      ];
      area.innerHTML = sections.map((section) => {
        const items = grouped[section.key] || [];
        return `<section class="output-column ${section.cls}">
          <div class="output-column-title">${escapeHtml(section.title)}</div>
          <div class="output-column-note">${escapeHtml(section.note)}</div>
          <div class="output-card-grid">
            ${items.length ? makeCards(items, section.key) : '<div class="empty">No files yet.</div>'}
          </div>
        </section>`;
      }).join("");
      area.querySelectorAll("[data-output-kind][data-output-index]").forEach((button) => {
        const kind = button.getAttribute("data-output-kind") || "";
        const indexToken = button.getAttribute("data-output-index") || "";
        const [prefix, idx] = indexToken.split("-");
        const file = grouped[prefix]?.[Number(idx)];
        button.addEventListener("click", () => openOutputModal(file));
      });
      if (hint) hint.textContent = data.message || "Output generated.";
      setRadio(data.message || "Output generated.");
    }

    async function runAction(endpoint, label, kind) {
      const area = $("outputArea");
      const hint = $("outputHint");
      area.innerHTML = `<div class="empty">${escapeHtml(label)} in progress...</div>`;
      if (hint) hint.textContent = `${label} from the selected race and drivers.`;
      document.body.classList.add("loading");
      try {
        const data = await postJson(endpoint, selectedExportPayload(kind));
        renderFiles(data);
      } catch (error) {
        area.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
        if (hint) hint.textContent = error.message;
        setRadio(error.message);
      } finally {
        document.body.classList.remove("loading");
      }
    }

    async function init() {
      try {
        applyTheme(readPreferredTheme());
        syncActiveNav();
        state.bootstrap = await getJson("/api/bootstrap");
        buildSelectors();
        renderOverview();
        if (pageName() !== "overview") {
          await analyze();
        }
      } catch (error) {
        setStatus("Boot error", true);
        setRadio(error.message);
      }
    }

    $("raceToggle").addEventListener("click", () => toggleRaceMenu());
    $("raceMenu").addEventListener("click", (event) => {
      const item = event.target.closest(".race-menu-item");
      if (!item) return;
      setRaceSelection(item.dataset.race);
    });
    $("driverToggle").addEventListener("click", () => toggleDropdown("driver"));
    $("driverMenu").addEventListener("click", (event) => {
      const item = event.target.closest(".race-menu-item");
      if (!item) return;
      setPersonSelection("driver", item.dataset.driver);
    });
    $("compareToggle").addEventListener("click", () => toggleDropdown("compare"));
    $("compareMenu").addEventListener("click", (event) => {
      const item = event.target.closest(".race-menu-item");
      if (!item) return;
      setPersonSelection("compare", item.dataset.driver);
    });
    $("analyzeButton").addEventListener("click", analyze);
    $("themeToggle").addEventListener("click", toggleTheme);
    $("plotsButton").addEventListener("click", () => runAction("/api/generate-plots", "Generating selected plot", "plot"));
    $("replaysButton").addEventListener("click", () => runAction("/api/generate-replays", "Rendering selected replay", "replay"));
    $("reportButton").addEventListener("click", () => runAction("/api/export-report", "Exporting selected report", "report"));
    $("outputModalClose").addEventListener("click", closeOutputModal);
    $("outputModalBackdrop").addEventListener("click", (event) => {
      if (event.target === $("outputModalBackdrop")) closeOutputModal();
    });
    document.addEventListener("click", (event) => {
      if (event.target && event.target.closest && event.target.closest("[data-close-modal]")) {
        event.preventDefault();
        closeOutputModal();
      }
    }, true);
    $("paceCanvas").addEventListener("mousemove", handlePaceHover);
    $("paceCanvas").addEventListener("mouseleave", hidePaceHover);
    document.addEventListener("click", (event) => {
      const racePicker = $("racePicker");
      const driverPicker = $("driverPicker");
      const comparePicker = $("comparePicker");
      if (racePicker && !racePicker.contains(event.target)) closeRaceMenu();
      if (driverPicker && !driverPicker.contains(event.target)) closeDropdown("driver");
      if (comparePicker && !comparePicker.contains(event.target)) closeDropdown("compare");
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closeAllDropdowns();
        closeOutputModal();
      }
    });
    window.addEventListener("resize", () => state.analysis?.ok && drawPaceChart(state.analysis));
    init();
  </script>
</body>
</html>
"""


class PitWallRequestHandler(BaseHTTPRequestHandler):
    """HTTP handler bound to a PitWallWebService instance at runtime."""

    service: PitWallWebService

    def _send_bytes(self, content: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        no_store = content_type.startswith("application/json") or content_type.startswith("text/html")
        self.send_header("Cache-Control", "no-store" if no_store else "public, max-age=60")
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        content = json.dumps(_jsonable(payload), ensure_ascii=False).encode("utf-8")
        self._send_bytes(content, "application/json; charset=utf-8", status)

    def _send_error_json(self, message: str, status: int = 400) -> None:
        self._send_json({"ok": False, "status": "error", "message": message}, status)

    @staticmethod
    def _first(params: dict[str, list[str]] | dict[str, Any], key: str, default: Any = "") -> Any:
        value = params.get(key, default)
        if isinstance(value, list):
            return value[0] if value else default
        return value

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        content_type = self.headers.get("Content-Type", "").lower()
        if "application/x-www-form-urlencoded" in content_type:
            return parse_qs(raw)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            parsed = parse_qs(raw)
            if parsed:
                return parsed
            raise

    def _serve_project_file(self, raw_path: str, root_name: str) -> None:
        allowed_root = (ROOT_DIR / root_name).resolve()
        relative = unquote(raw_path).lstrip("/").replace("/", os.sep)
        requested = (ROOT_DIR / relative).resolve()
        try:
            requested.relative_to(allowed_root)
        except ValueError:
            self._send_error_json("File not found.", 404)
            return
        if not requested.is_file():
            self._send_error_json("File not found.", 404)
            return
        content_type = mimetypes.guess_type(str(requested))[0] or "application/octet-stream"
        self._send_bytes(requested.read_bytes(), content_type)

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler naming
        parsed = urlparse(self.path)
        try:
            page_map = {
                "/": "overview",
                "/index.html": "overview",
                "/overview": "overview",
                "/analysis": "analysis",
                "/strategy": "strategy",
                "/exports": "exports",
                "/outputs": "exports",
                "/output": "exports",
            }
            page = page_map.get(parsed.path)
            if page is not None:
                html = WEB_HTML.replace("__PAGE__", page)
                self._send_bytes(html.encode("utf-8"), "text/html; charset=utf-8")
                return
            if parsed.path == "/api/bootstrap":
                self._send_json(self.service.bootstrap())
                return
            if parsed.path == "/api/analyze":
                params = parse_qs(parsed.query)
                self._send_json(self.service.analyze(
                    race_name=self._first(params, "race", DEFAULT_RACE),
                    driver_code=self._first(params, "driver", DEFAULT_DRIVER),
                    comparison_code=self._first(params, "compare", DEFAULT_COMPARISON_DRIVER),
                    season=int(self._first(params, "season", 2026)),
                ))
                return
            if parsed.path.startswith("/outputs/"):
                self._serve_project_file(parsed.path, "outputs")
                return
            if parsed.path.startswith("/assets/"):
                self._serve_project_file(parsed.path, "assets")
                return
            self._send_error_json("Route not found.", 404)
        except Exception as error:
            self._send_error_json(str(error), 500)

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler naming
        parsed = urlparse(self.path)
        try:
            body = self._read_json_body()
            race = self._first(body, "race", DEFAULT_RACE)
            driver = self._first(body, "driver", DEFAULT_DRIVER)
            compare = self._first(body, "compare", DEFAULT_COMPARISON_DRIVER)
            season = int(self._first(body, "season", 2026))
            if parsed.path == "/api/generate-plots":
                self._send_json(self.service.generate_plots(
                    race,
                    driver,
                    compare,
                    season,
                    plot_key=str(self._first(body, "plot_type", "all")),
                ))
                return
            if parsed.path == "/api/generate-replays":
                self._send_json(self.service.generate_replays(
                    race,
                    driver,
                    season,
                    replay_key=str(self._first(body, "replay_type", "all")),
                ))
                return
            if parsed.path == "/api/export-report":
                self._send_json(self.service.export_report(
                    race,
                    driver,
                    compare,
                    season,
                    report_key=str(self._first(body, "report_type", "pdf")),
                ))
                return
            self._send_error_json("Route not found.", 404)
        except Exception as error:
            self._send_error_json(str(error), 500)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
        """Keep the VS Code terminal readable."""
        return


def run_web_app(host: str = "127.0.0.1", port: int = 8000, open_browser: bool = True) -> int:
    """Start the local browser UI."""
    service = PitWallWebService()

    class BoundPitWallRequestHandler(PitWallRequestHandler):
        pass

    BoundPitWallRequestHandler.service = service
    address = (host, port)
    try:
        server = ThreadingHTTPServer(address, BoundPitWallRequestHandler)
    except OSError as error:
        print(f"Pit Wall Predictor web app could not start on http://{host}:{port}: {error}")
        print("Try another port, for example: python main.py --web --port 8010")
        return 1

    url = f"http://{host}:{port}"
    print("=" * 72)
    print("PIT WALL PREDICTOR | LOCAL WEB UI")
    print("=" * 72)
    print(f"Open this in your browser: {url}")
    print("Press Ctrl+C in this terminal to stop the server.")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Pit Wall Predictor web app.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(run_web_app())
