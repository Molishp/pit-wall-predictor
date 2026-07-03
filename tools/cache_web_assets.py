"""Cache web visual assets used by the local Pit Wall Predictor UI.

The app can run with remote URLs, but cached local files make the interface more
stable during demos and keep the project folder organized.
"""

from __future__ import annotations

import csv
import json
import re
import sys
import time
from urllib.parse import quote, urlencode
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from src.web_app import (  # noqa: E402
    DRIVER_MEDIA,
    TEAM_MEDIA,
    TRACK_REQUEST_HEADERS,
    WIKIMEDIA_COMMONS_RAW_URL,
    _commons_raw_svg_url,
    _extract_track_map,
    _fetch_url_text,
    _load_track_map_from_page,
    _score_track_svg_filename,
    _search_wikipedia_titles,
    _track_candidate_titles,
)


ASSET_DIR = ROOT_DIR / "assets"
DRIVER_DIR = ASSET_DIR / "drivers"
CAR_DIR = ASSET_DIR / "cars"
TEAM_LOGO_DIR = ASSET_DIR / "team_logos"
TRACK_DIR = ASSET_DIR / "track_maps"
MANIFEST_PATH = ASSET_DIR / "asset_manifest.json"
COMMONS_API_URL = "https://commons.wikimedia.org/w/api.php"
TRACK_FILE_OVERRIDES = {
    "Miami Grand Prix": "2022 F1 CourseLayout Miami.svg",
    "Canadian Grand Prix": "2022 F1 CourseLayout Canada.svg",
    "Monaco Grand Prix": "Monte Carlo Formula 1 track map.svg",
    "Barcelona-Catalunya Grand Prix": "2023 F1 CourseLayout Spain.svg",
    "British Grand Prix": "2022 F1 CourseLayout Britain.svg",
    "Belgian Grand Prix": "Spa-Francorchamps of Belgium.svg",
    "Azerbaijan Grand Prix": "Baku Formula One circuit map.svg",
    "Qatar Grand Prix": "2023 F1 CourseLayout Qatar.svg",
}


def slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return re.sub(r"_+", "_", cleaned)


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def download(url: str, path: Path, binary: bool = True) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        return {"ok": True, "path": path.as_posix(), "source_url": url, "cached": True}
    request = urllib.request.Request(url, headers=TRACK_REQUEST_HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=35) as response:
            content = response.read()
    except (urllib.error.URLError, TimeoutError) as error:
        return {"ok": False, "path": path.as_posix(), "source_url": url, "error": str(error)}
    if not binary:
        content = content.decode("utf-8", errors="replace").encode("utf-8")
    path.write_bytes(content)
    time.sleep(0.08)
    return {"ok": True, "path": path.as_posix(), "source_url": url, "cached": False}


def commons_json(params: dict[str, Any]) -> dict[str, Any]:
    payload = dict(params)
    payload["format"] = "json"
    payload.setdefault("origin", "*")
    url = f"{COMMONS_API_URL}?{urlencode(payload)}"
    return json.loads(_fetch_url_text(url))


def commons_svg_candidates(query: str) -> list[str]:
    data = commons_json({
        "action": "query",
        "list": "search",
        "srnamespace": 6,
        "srlimit": 12,
        "srsearch": f"{query} circuit layout svg",
    })
    titles = [str(item.get("title", "")) for item in data.get("query", {}).get("search", [])]
    file_names = [title.split(":", 1)[1] for title in titles if title.lower().endswith(".svg") and ":" in title]
    file_names.sort(key=_score_track_svg_filename, reverse=True)
    return file_names


def commons_thumbnail_url(file_name: str, width: int = 1400) -> str | None:
    data = commons_json({
        "action": "query",
        "titles": f"File:{file_name}",
        "prop": "imageinfo",
        "iiprop": "url",
        "iiurlwidth": width,
    })
    pages = data.get("query", {}).get("pages", {})
    page = next(iter(pages.values()), {})
    image_info = page.get("imageinfo") or []
    if not image_info:
        return None
    return image_info[0].get("thumburl") or image_info[0].get("url")


def track_map_from_commons_search(race_name: str, circuit: str) -> dict[str, Any] | None:
    queries = [circuit, circuit.split(",", 1)[0], race_name.replace(" Grand Prix", "")]
    seen: set[str] = set()
    for query in queries:
        if not query.strip():
            continue
        try:
            file_names = commons_svg_candidates(query)
        except Exception:
            continue
        for file_name in file_names:
            if file_name in seen:
                continue
            seen.add(file_name)
            raw_url = _commons_raw_svg_url(file_name)
            try:
                svg_text = _fetch_url_text(raw_url)
            except Exception:
                continue
            track_map = _extract_track_map(svg_text)
            if not track_map:
                continue
            track_map.update({
                "source_page": "Wikimedia Commons search",
                "source_file": file_name,
                "source_url": f"https://commons.wikimedia.org/wiki/File:{quote(file_name.replace(' ', '_'))}",
                "raw_svg_url": raw_url,
                "race_name": race_name,
                "circuit_name": circuit,
            })
            return track_map
    return None


def cache_track(row: dict[str, str]) -> dict[str, Any]:
    race_name = row["race_name"]
    circuit = row["circuit"]
    round_no = int(row["round"])
    path = TRACK_DIR / f"{round_no:02d}_{slug(race_name)}.svg"
    existing_png = TRACK_DIR / f"{round_no:02d}_{slug(race_name)}.png"
    if path.exists() and path.stat().st_size > 0:
        return {"ok": True, "path": path.as_posix(), "race_name": race_name, "circuit": circuit, "cached": True}
    if existing_png.exists() and existing_png.stat().st_size > 0:
        return {"ok": True, "path": existing_png.as_posix(), "race_name": race_name, "circuit": circuit, "cached": True}
    override_file = TRACK_FILE_OVERRIDES.get(race_name)
    if override_file:
        raw_url = _commons_raw_svg_url(override_file)
        saved = download(raw_url, path, binary=False)
        if not saved.get("ok") and "429" in str(saved.get("error", "")):
            thumbnail_path = TRACK_DIR / f"{round_no:02d}_{slug(race_name)}.png"
            thumbnail_url = f"https://commons.wikimedia.org/wiki/Special:Redirect/file/{quote(override_file.replace(' ', '_'))}?width=1400"
            saved = download(thumbnail_url, thumbnail_path, binary=True)
        if not saved.get("ok") and "429" in str(saved.get("error", "")):
            thumbnail_url = commons_thumbnail_url(override_file)
            if thumbnail_url:
                thumbnail_path = TRACK_DIR / f"{round_no:02d}_{slug(race_name)}.png"
                saved = download(thumbnail_url, thumbnail_path, binary=True)
        saved.update({
            "race_name": race_name,
            "circuit": circuit,
            "source_page": "Wikimedia Commons override",
            "source_file": override_file,
            "source_url": f"https://commons.wikimedia.org/wiki/File:{quote(override_file.replace(' ', '_'))}",
        })
        return saved
    result: dict[str, Any] | None = None
    candidates = _track_candidate_titles(race_name, circuit)
    for page_title in candidates:
        try:
            result = _load_track_map_from_page(page_title, race_name, circuit)
        except Exception:
            result = None
        if result:
            break
    if not result:
        fallback_titles: list[str] = []
        for query in (circuit, race_name):
            try:
                fallback_titles.extend(_search_wikipedia_titles(query))
            except Exception:
                continue
        for page_title in fallback_titles:
            try:
                result = _load_track_map_from_page(page_title, race_name, circuit)
            except Exception:
                result = None
            if result:
                break
    if not result:
        result = track_map_from_commons_search(race_name, circuit)
    if not result or not result.get("raw_svg_url"):
        return {
            "ok": False,
            "race_name": race_name,
            "path": path.as_posix(),
            "error": "No trusted SVG track candidate found.",
        }
    saved = download(str(result["raw_svg_url"]), path, binary=False)
    saved.update({
        "race_name": race_name,
        "circuit": circuit,
        "source_page": result.get("source_page"),
        "source_file": result.get("source_file"),
        "source_url": result.get("source_url"),
    })
    return saved


def main() -> int:
    for directory in (DRIVER_DIR, CAR_DIR, TEAM_LOGO_DIR, TRACK_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    calendar = load_csv(ROOT_DIR / "data" / "race_calendar_2026.csv")
    drivers = load_csv(ROOT_DIR / "data" / "driver_metadata.csv")
    teams = load_csv(ROOT_DIR / "data" / "team_metadata.csv")

    manifest: dict[str, Any] = {
        "generated_by": "tools/cache_web_assets.py",
        "drivers": {},
        "cars": {},
        "team_logos": {},
        "track_maps": {},
    }

    for driver in drivers:
        code = driver["driver_code"]
        url = DRIVER_MEDIA.get(code, {}).get("photo")
        if url:
            manifest["drivers"][code] = download(url, DRIVER_DIR / f"{code}.webp")

    for team in teams:
        team_name = team["team"]
        key = slug(team_name)
        media = TEAM_MEDIA.get(team_name, {})
        if media.get("car"):
            manifest["cars"][team_name] = download(media["car"], CAR_DIR / f"{key}.webp")
        if media.get("logo"):
            manifest["team_logos"][team_name] = download(media["logo"], TEAM_LOGO_DIR / f"{key}.webp")

    for row in calendar:
        manifest["track_maps"][row["race_name"]] = cache_track(row)

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    ok_count = sum(
        1
        for section in ("drivers", "cars", "team_logos", "track_maps")
        for item in manifest[section].values()
        if item.get("ok")
    )
    print(f"Cached asset manifest: {MANIFEST_PATH}")
    print(f"Successful assets: {ok_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
