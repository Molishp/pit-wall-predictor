"""CSV and dependency-free Markdown/PDF reports for the CLI workflow."""

from __future__ import annotations

from pathlib import Path
import textwrap
from typing import Any

import pandas as pd

from src.real_data_importer import has_real_bundle


PDF_PAGE_WIDTH = 595.28
PDF_PAGE_HEIGHT = 841.89
PDF_MARGIN_X = 36
PDF_TOP_Y = 800
PDF_BOTTOM_Y = 42


def _slug(value: str) -> str:
    return "".join(character.lower() if character.isalnum() else "_" for character in value).strip("_").replace("__", "_")


def _markdown_table(frame: pd.DataFrame) -> str:
    """Render a compact table without depending on the external tabulate package."""
    columns = list(frame.columns)
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for _, row in frame.iterrows():
        lines.append("| " + " | ".join(str(row[column]).replace("|", "/") for column in columns) + " |")
    return "\n".join(lines)


def _wrapped_lines(text: str, width: int = 92) -> list[str]:
    """Wrap text for the PDF page renderer."""
    if not text:
        return [""]
    wrapped: list[str] = []
    for paragraph in str(text).splitlines() or [""]:
        wrapped.extend(textwrap.wrap(paragraph, width=width) or [""])
    return wrapped


def _pdf_escape(text: str) -> str:
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
        .replace("\r", "")
        .replace("\n", " ")
    )


def _new_pdf_page(title: str) -> dict[str, Any]:
    return {
        "title": title,
        "items": [
            {
                "text": title,
                "x": PDF_MARGIN_X,
                "y": PDF_TOP_Y,
                "size": 18,
                "color": (0.96, 0.97, 0.98),
                "bold": True,
            }
        ],
        "y": PDF_TOP_Y - 28,
    }


def _page_add(page: dict[str, Any], text: str, *, x: float, size: float, color: tuple[float, float, float], bold: bool = False, line_gap: float | None = None) -> None:
    page["items"].append(
        {
            "text": text,
            "x": x,
            "y": page["y"],
            "size": size,
            "color": color,
            "bold": bold,
        }
    )
    page["y"] -= line_gap if line_gap is not None else max(11.0, size + 4.0)


def _start_page(pages: list[dict[str, Any]], title: str) -> dict[str, Any]:
    page = _new_pdf_page(title)
    pages.append(page)
    return page


def _append_wrapped_lines(
    page: dict[str, Any],
    pages: list[dict[str, Any]],
    title: str,
    text: str,
    *,
    x: float,
    size: float,
    color: tuple[float, float, float],
    width: int = 92,
    bold: bool = False,
    line_gap: float | None = None,
) -> dict[str, Any]:
    current = page
    for wrapped in textwrap.wrap(text, width=width) or [""]:
        if current["y"] <= PDF_BOTTOM_Y:
            current = _start_page(pages, title)
        _page_add(current, wrapped, x=x, size=size, color=color, bold=bold, line_gap=line_gap)
    return current


def _write_minimal_pdf(pages: list[dict[str, Any]], output_path: Path) -> None:
    """Write a small valid PDF using only the standard library."""
    objects: list[str] = [""] * (3 + 2 * len(pages))
    objects[2] = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

    for index, page in enumerate(pages):
        content_lines = [
            "0.06 0.07 0.09 rg",
            f"0 0 {PDF_PAGE_WIDTH:.2f} {PDF_PAGE_HEIGHT:.2f} re f",
        ]
        for item in page["items"]:
            r, g, b = item["color"]
            font_name = "/F1"
            content_lines.extend(
                [
                    "BT",
                    f"{font_name} {item['size']:.1f} Tf",
                    f"{r:.3f} {g:.3f} {b:.3f} rg",
                    f"{item['x']:.2f} {item['y']:.2f} Td",
                    f"({_pdf_escape(item['text'])}) Tj",
                    "ET",
                ]
            )
        content = "\n".join(content_lines)
        content_bytes = content.encode("latin-1", "replace")
        content_id = 4 + index * 2
        page_id = 5 + index * 2
        objects[content_id - 1] = f"<< /Length {len(content_bytes)} >>\nstream\n{content}\nendstream"
        objects[page_id - 1] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PDF_PAGE_WIDTH:.2f} {PDF_PAGE_HEIGHT:.2f}] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>"
        )

    objects[1] = f"<< /Type /Pages /Count {len(pages)} /Kids [{' '.join(f'{5 + i * 2} 0 R' for i in range(len(pages)))}] >>"
    objects[0] = "<< /Type /Catalog /Pages 2 0 R >>"

    parts = [b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"]
    offsets: list[int] = []
    cursor = len(parts[0])
    for index, obj in enumerate(objects, start=1):
        encoded = f"{index} 0 obj\n{obj}\nendobj\n".encode("latin-1", "replace")
        offsets.append(cursor)
        parts.append(encoded)
        cursor += len(encoded)

    xref_start = cursor
    xref = [f"xref\n0 {len(objects) + 1}\n", "0000000000 65535 f \n"]
    xref.extend(f"{offset:010d} 00000 n \n" for offset in offsets)
    parts.append("".join(xref).encode("latin-1"))
    parts.append(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n"
        ).encode("latin-1")
    )
    output_path.write_bytes(b"".join(parts))


def _build_pdf_pages(
    race_name: str,
    summary: pd.DataFrame,
    comparison: dict[str, Any],
    tyre_fit: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    driver_a, driver_b = comparison["driver_a"], comparison["driver_b"]
    data_label = "imported real-data bundle" if has_real_bundle() else "reproducible synthetic demo data"
    pages: list[dict[str, Any]] = []
    page = _start_page(pages, f"{race_name} - Post-Race Strategy Report")

    sections: list[tuple[str, list[str]]] = [
        (
            "Executive summary",
            _wrapped_lines(
                f"This PDF is generated locally by the Python backend from the selected {data_label}. It is designed as a portfolio-friendly export: readable, compact, and focused on the engineering story.",
                92,
            ),
        ),
        ("Driver battle", _wrapped_lines(comparison["verdict"], 92)),
        (
            "Selected-driver notes",
            _wrapped_lines(driver_a["race_engineer_verdict"], 92),
        ),
        (
            "Rival notes",
            _wrapped_lines(driver_b["race_engineer_verdict"], 92),
        ),
        (
            "Full-grid race engineer ranking",
            [
                "Pos  Driver  Team                 Pace(s)  Consistency  Tyres  Score",
                *(
                    f"P{int(row['final_position']):<2}  {row['driver_code']:<6}  {str(row['team'])[:19]:<19}  "
                    f"{float(row['average_clean_pace']):>7.3f}  {float(row['consistency_score']):>10.1f}  "
                    f"{float(row['tyre_management_score']):>5.1f}  {float(row['race_engineer_score']):>5.1f}"
                    for _, row in summary.sort_values("race_engineer_score", ascending=False).iterrows()
                ),
            ],
        ),
        (
            "Data and modelling note",
            _wrapped_lines(
                f"The project currently uses the {data_label} when available. Pit laps, in-laps, out-laps, safety-car laps, and extreme outliers are removed from clean-lap calculations.",
                92,
            ),
        ),
    ]

    if tyre_fit is not None:
        sections.append(
            (
                "SciPy tyre degradation model",
                _wrapped_lines(
                    f"{tyre_fit['driver_code']} on {tyre_fit['compound']}: base {tyre_fit['base_pace']:.4f}s, linear {tyre_fit['linear_degradation']:.5f}, quadratic {tyre_fit['quadratic_degradation']:.6f}.",
                    92,
                )
                + [f"RMSE: {tyre_fit['rmse']:.4f}s."]
                + _wrapped_lines(tyre_fit["interpretation"], 92),
            )
        )

    title = page["title"]
    for header, lines in sections:
        if page["y"] <= PDF_BOTTOM_Y + 40:
            page = _start_page(pages, title)
            title = page["title"]

        if page["y"] <= PDF_BOTTOM_Y:
            page = _start_page(pages, title)

        _page_add(page, header, x=PDF_MARGIN_X, size=12.5, color=(0.0, 0.9, 1.0), bold=True, line_gap=18)
        for line in lines:
            if page["y"] <= PDF_BOTTOM_Y:
                page = _start_page(pages, title)
            if line.startswith("- "):
                page = _append_wrapped_lines(
                    page,
                    pages,
                    title,
                    line,
                    x=PDF_MARGIN_X + 10,
                    size=9.2,
                    color=(0.84, 0.87, 0.93),
                    width=98,
                    line_gap=13,
                )
            else:
                page = _append_wrapped_lines(
                    page,
                    pages,
                    title,
                    line,
                    x=PDF_MARGIN_X,
                    size=9.4,
                    color=(0.84, 0.87, 0.93),
                    width=100,
                    line_gap=13,
                )
        page["y"] -= 6

    return pages


def _write_pdf_report(
    summary: pd.DataFrame,
    comparison: dict[str, Any],
    tyre_fit: dict[str, Any] | None,
    output_path: Path,
) -> Path:
    """Write a compact PDF report without optional third-party dependencies."""
    race_name = str(summary.iloc[0]["race_name"]) if "race_name" in summary.columns else comparison["driver_a"]["race_name"]
    pages = _build_pdf_pages(race_name, summary, comparison, tyre_fit)
    _write_minimal_pdf(pages, output_path)
    return output_path


def write_reports(
    summary: pd.DataFrame,
    results: dict[str, dict[str, Any]],
    comparison: dict[str, Any],
    tyre_fit: dict[str, Any] | None,
    output_dir: Path,
) -> dict[str, Path]:
    """Save the required all-driver CSV and a readable full post-race Markdown report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    race_name = str(summary.iloc[0]["race_name"]) if "race_name" in summary.columns else next(iter(results.values()))["race_name"]
    stem = _slug(race_name)
    csv_path = output_dir / f"{stem}_all_driver_summary.csv"
    markdown_path = output_dir / f"{stem}_post_race_report.md"
    pdf_path = output_dir / f"{stem}_post_race_report.pdf"
    data_label = "imported real-data bundle" if has_real_bundle() else "reproducible synthetic demo data"
    summary.to_csv(csv_path, index=False)

    display_columns = [
        "final_position",
        "driver_code",
        "team",
        "average_clean_pace",
        "fastest_lap",
        "consistency_score",
        "tyre_management_score",
        "pit_stops",
        "race_engineer_score",
        "badge_earned",
    ]
    driver_a, driver_b = comparison["driver_a"], comparison["driver_b"]
    lines = [
        f"# {race_name} - Post-Race Strategy Report",
        "",
        "## Data note",
        "",
        f"This report uses the {data_label}. Team pace assumptions and race events are derived from the loaded CSV source and demonstrate the Python analysis pipeline only.",
        "",
        "## Full-grid summary",
        "",
        _markdown_table(summary[display_columns]),
        "",
        f"## Driver battle: {driver_a['driver_code']} vs {driver_b['driver_code']}",
        "",
        comparison["verdict"],
        "",
        f"- {driver_a['driver_code']}: P{driver_a['final_position']}, {driver_a['average_clean_pace']:.3f}s clean pace, {driver_a['race_engineer_score']:.1f}/100, {driver_a['badge_earned']}",
        f"- {driver_b['driver_code']}: P{driver_b['final_position']}, {driver_b['average_clean_pace']:.3f}s clean pace, {driver_b['race_engineer_score']:.1f}/100, {driver_b['badge_earned']}",
        "",
        "## Selected driver engineer notes",
        "",
    ]
    for result in (driver_a, driver_b):
        lines.extend(
            [
                f"### {result['driver_code']} - {result['driver_name']}",
                "",
                result["race_engineer_verdict"],
                "",
                f"- Clean laps: {result['number_clean_laps']}; fastest: {result['fastest_lap']:.3f}s; standard deviation: {result['lap_time_std']:.3f}s.",
                f"- Strategy: {result['pit_stops']} pit stop(s); compounds used: {result['compound_usage']}.",
                f"- Best stint: {result['best_stint']['compound']} L{result['best_stint']['start_lap']}-L{result['best_stint']['end_lap']} ({result['best_stint']['average_clean_pace']:.3f}s).",
                "",
            ]
        )
    if tyre_fit is not None:
        lines.extend(
            [
                f"## SciPy tyre model: {tyre_fit['driver_code']} on {tyre_fit['compound']}",
                "",
                f"Lap time = {tyre_fit['base_pace']:.4f} + {tyre_fit['linear_degradation']:.5f} x tyre age + {tyre_fit['quadratic_degradation']:.6f} x tyre age^2",
                "",
                f"RMSE: {tyre_fit['rmse']:.4f}s. {tyre_fit['interpretation']}",
                "",
            ]
        )
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    _write_pdf_report(summary, comparison, tyre_fit, pdf_path)
    return {"summary_csv": csv_path, "markdown_report": markdown_path, "pdf_report": pdf_path}
