"""Build an interview-ready PDF report for the Pit Wall Predictor project."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import json

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
REAL_DIR = DATA_DIR / "real"
OUTPUT_DIR = ROOT / "outputs" / "reports"
PDF_PATH = OUTPUT_DIR / "pit_wall_predictor_interview_report.pdf"


def p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(text, style)


def t(rows: list[list[str]], widths: list[float], styles: dict[str, ParagraphStyle], *, header_fill: str = "#DCE6F1") -> Table:
    data = []
    for row_index, row in enumerate(rows):
        current = []
        for col_index, value in enumerate(row):
            current.append(p(value, styles["table_head"] if row_index == 0 else styles["table_body"]))
        data.append(current)
    table = Table(data, colWidths=[w * inch for w in widths], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_fill)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1A1A1A")),
                ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#B7C6D8")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def build_pdf() -> Path:
    calendar = pd.read_csv(REAL_DIR / "race_calendar_2026.csv")
    laps = pd.read_csv(REAL_DIR / "2026_real_race_laps.csv")
    source_index = json.loads((REAL_DIR / "source_index.json").read_text(encoding="utf-8"))
    summary = pd.read_csv(ROOT / "outputs" / "reports" / "barcelona_catalunya_grand_prix_all_driver_summary.csv")
    summary_sorted = summary.sort_values("race_engineer_score", ascending=False).head(5)
    race_counts = (
        laps.groupby("race_name", as_index=False)
        .agg(rows=("lap_number", "size"), drivers=("driver_code", "nunique"))
        .merge(calendar[["race_name", "round", "status", "total_laps"]], on="race_name", how="left")
        .sort_values("round")
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        "TitleBig",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=30,
        leading=34,
        alignment=TA_CENTER,
        textColor=colors.black,
        spaceAfter=12,
    ))
    styles.add(ParagraphStyle(
        "Subtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=13.5,
        leading=17,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#444444"),
        spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        "CoverSummary",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=10.5,
        leading=14,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#444444"),
        spaceAfter=14,
    ))
    styles.add(ParagraphStyle(
        "H1",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=19,
        textColor=colors.HexColor("#2E74B5"),
        spaceBefore=8,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#2E74B5"),
        spaceBefore=6,
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        "H3",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=11.5,
        leading=14,
        textColor=colors.HexColor("#1F4D78"),
        spaceBefore=4,
        spaceAfter=3,
    ))
    styles.add(ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#1A1A1A"),
        spaceAfter=7,
    ))
    styles.add(ParagraphStyle(
        "BodyCenter",
        parent=styles["Body"],
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        "TableHead",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=10,
        textColor=colors.HexColor("#1A1A1A"),
    ))
    styles.add(ParagraphStyle(
        "TableBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.2,
        leading=10,
        textColor=colors.HexColor("#1A1A1A"),
    ))
    styles_map = {"table_head": styles["TableHead"], "table_body": styles["TableBody"]}

    doc = SimpleDocTemplate(
        str(PDF_PATH),
        pagesize=letter,
        leftMargin=1.0 * inch,
        rightMargin=1.0 * inch,
        topMargin=0.85 * inch,
        bottomMargin=0.85 * inch,
    )

    story: list[object] = []

    story.append(Spacer(1, 0.55 * inch))
    story.append(p("Pit Wall Predictor", styles["TitleBig"]))
    story.append(p("Interview report - real-data Formula 1 strategy analysis system", styles["Subtitle"]))
    story.append(p(
        "A transparent offline Python project that turns completed-race CSV files into engineering-style race pace, tyre, strategy, and reporting outputs.",
        styles["CoverSummary"],
    ))

    cover_rows = [
        ["Project snapshot", "Value"],
        ["Purpose", "Post-race Formula 1 strategy analysis with transparent formulas and reusable CLI, GUI, and browser front ends."],
        ["Runtime", "Python, NumPy, Pandas, SciPy, Matplotlib, Tkinter, and the standard library."],
        ["Verified data", "8 completed races, 9,215 laps, 22 drivers, 11 teams, imported from local official race CSV files."],
        ["Outputs", "CSV summaries, Markdown reports, PDF reports, PNG plots, and HTML replays."],
        ["Modes", "CLI, colourful Tkinter dashboard, and localhost browser dashboard."],
    ]
    story.append(t(cover_rows, [1.55, 4.95], styles_map))
    story.append(Spacer(1, 0.08 * inch))
    story.append(p(
        f"Verified on {date.today().isoformat()}, the current imported bundle contains {len(calendar)} completed races and {len(laps)} lap rows. The analysis layer now loads that real bundle automatically whenever it is present.",
        styles["BodyCenter"],
    ))
    story.append(p(
        "The main design goal is clarity: every score, plot, and replay is generated from explicit rules that can be explained in a technical interview without relying on black-box machine learning.",
        styles["BodyCenter"],
    ))

    story.append(PageBreak())

    story.append(p("1. What the project is", styles["H1"]))
    story.append(p(
        "Pit Wall Predictor is a post-race analysis tool, not a live prediction engine. It reads completed-race lap CSV files, cleans the laps, compares drivers, scores race execution, fits a simple tyre-degradation curve, and then exposes the same backend through three surfaces: command line, Tkinter desktop UI, and a local web UI.",
        styles["Body"],
    ))
    story.append(p(
        "That makes the project useful as a portfolio piece because it shows data loading, data cleaning, transparent scoring, plotting, animation, local web serving, and report generation in one coherent codebase.",
        styles["Body"],
    ))

    story.append(p("2. How to use it", styles["H1"]))
    use_rows = [
        ["Mode / command", "What it does", "When to use it"],
        ["python main.py", "Runs the default CLI analysis for the default race and driver pair.", "Fastest way to smoke-test the backend."],
        ["python main.py --race \"Monaco Grand Prix\" --driver VER --compare NOR", "Chooses a race plus two driver codes.", "When you want a specific post-race comparison."],
        ["python main.py --gui", "Launches the colourful Tkinter dashboard.", "When you want a desktop front end."],
        ["python main.py --web", "Starts the localhost browser interface.", "When you want the more polished web UI."],
        ["python main.py --animations", "Exports the HTML replay animations.", "When you need replay artefacts for a presentation."],
    ]
    story.append(t(use_rows, [2.2, 2.5, 1.8], styles_map))

    story.append(p("3. What you can input", styles["H1"]))
    input_rows = [
        ["Input", "Example", "Where it is used"],
        ["Race name", "Barcelona-Catalunya Grand Prix", "Selects the completed race from the calendar."],
        ["Primary driver code", "HAM", "Drives the main analysis summary and tyre fit."],
        ["Comparison driver code", "RUS", "Builds the driver-battle verdict and pace plot."],
        ["Season", "2026", "Matches the calendar and imported data bundle."],
        ["UI flag", "--gui or --web", "Chooses the desktop or browser surface."],
        ["Replay flag", "--animations", "Creates the HTML replay exports."],
        ["Real-data manifest", "data/real/source_manifest.csv", "Tells the importer where the official CSV files live."],
    ]
    story.append(t(input_rows, [1.4, 2.2, 2.9], styles_map))

    story.append(p("4. What comes out", styles["H1"]))
    output_rows = [
        ["Output family", "Example file or surface", "Why it matters"],
        ["Grid summary", "outputs/reports/*_all_driver_summary.csv", "Gives one row per driver with pace, consistency, tyre, and total race-engineer score."],
        ["Readable report", "outputs/reports/*_post_race_report.md and .pdf", "Turns the analysis into a portfolio-friendly narrative."],
        ["Dashboard plots", "outputs/plots/*.png", "Provides the visual evidence behind the scores."],
        ["Replays", "outputs/animations/*.html", "Shows the race, tyre, and pit-stop stories in motion."],
        ["Browser UI", "http://127.0.0.1:8000", "Lets a user explore the project in a local web interface."],
        ["Tkinter UI", "main.py --gui", "Provides the desktop variant without a browser."],
    ]
    story.append(t(output_rows, [1.5, 2.4, 2.6], styles_map))

    story.append(p("5. How the analysis works", styles["H1"]))
    story.append(p("5.1 Data loading and validation", styles["H2"]))
    story.append(p(
        "The loader prefers the imported real-data bundle in data/real/ whenever it exists. If that bundle is missing, the project falls back to the deterministic sample dataset so the app still opens during development. The import pipeline stores the bundle in a local calendar file, a consolidated lap file, a manifest copy, and a source index that tracks the original CSV source for each race.",
        styles["Body"],
    ))
    story.append(p(
        f"The current validated bundle contains {len(calendar)} completed races, {int(laps['driver_code'].nunique())} drivers across the bundle, and {len(laps)} lap rows. The verified completed rounds are: {', '.join(calendar['race_name'].tolist())}.",
        styles["Body"],
    ))

    story.append(p("5.2 Clean-lap filtering", styles["H2"]))
    story.append(p(
        "Clean pace is the foundation of the project. The cleaning rule removes pit laps, safety-car laps, in-laps, out-laps, and then drops any remaining lap that is more than 4.0 seconds slower than the driver's median clean lap. That keeps the pace comparison focused on representative racing pace rather than traffic, pit cycles, or extreme anomalies.",
        styles["Body"],
    ))

    story.append(p("5.3 Driver analysis", styles["H2"]))
    story.append(p(
        "For each driver, the backend calculates average clean pace, fastest clean lap, slowest clean lap, standard deviation, pit-stop count, compound usage, and stint-level summaries. Each stint also gets a simple linear degradation estimate so the report can say where pace held up and where it dropped away.",
        styles["Body"],
    ))

    story.append(p("5.4 Scoring model", styles["H2"]))
    story.append(p(
        "The gamified score is intentionally transparent. It combines pace, consistency, tyre management, and stint execution with fixed weights, then converts the result into an easy-to-read rating and badge. Because the weights are explicit, the interview story is straightforward: the score is an explanation layer, not a hidden AI model.",
        styles["Body"],
    ))

    story.append(p("5.5 Tyre degradation model", styles["H2"]))
    story.append(p(
        "The tyre model uses SciPy's curve_fit on clean laps from a single driver and compound. The fitted form is Lap Time = Base Pace + a x Tyre Age + b x Tyre Age^2. The project reports the fitted coefficients and the RMSE so a reader can see both the trend and the quality of the fit.",
        styles["Body"],
    ))

    story.append(p("6. Formula cheat sheet", styles["H1"]))
    formula_rows = [
        ["Metric", "Formula or rule", "Interpretation"],
        ["Clean pace", "Mean of clean laps after filtering", "Core pace metric for the driver and the grid."],
        ["Consistency score", "clip(100 - lap_time_std x 30)", "Lower lap-time scatter is rewarded."],
        ["Tyre management score", "clip(100 - avg_positive_degradation x 430)", "Punishes steep stint degradation."],
        ["Pace score", "clip(100 - pace_deficit x 22)", "Converts clean pace deficit into a 0-100 scale."],
        ["Stint execution score", "clip(100 - stint_pace_spread x 18)", "Rewards a balanced stint profile."],
        ["Race engineer score", "0.35 pace + 0.25 consistency + 0.25 tyre + 0.15 stint", "Final gamified score used in the ranking."],
        ["Badge logic", "Threshold checks on pace, consistency, tyres, stints, and position", "Produces a human-readable achievement label."],
    ]
    story.append(t(formula_rows, [1.5, 2.7, 2.3], styles_map))
    story.append(p(
        "The key design decision is that every formula is simple enough to explain live in an interview. There is no opaque model tuning step and no hidden training set - just fixed rules, visible assumptions, and stable outputs.",
        styles["Body"],
    ))

    story.append(p("7. Example output from the verified Barcelona-Catalunya run", styles["H1"]))
    example_rows = [["Rank", "Driver", "Team", "Clean pace (s)", "Score", "Badge"]]
    for rank, (_, row) in enumerate(summary.sort_values("race_engineer_score", ascending=False).head(5).iterrows(), start=1):
        example_rows.append([
            str(rank),
            str(row["driver_code"]),
            str(row["team"]),
            f"{float(row['average_clean_pace']):.3f}",
            f"{float(row['race_engineer_score']):.1f}",
            str(row["badge_earned"]),
        ])
    story.append(t(example_rows, [0.6, 0.8, 1.35, 1.1, 0.8, 1.85], styles_map, header_fill="#DCE6F1"))
    story.append(p(
        "On this verified run, Hamilton leads the sample summary and the report generator turns that result into a compact project artefact. That makes the project easy to demo: the same backend can support a short summary, a detailed explanation, and a visual dashboard from the same race data.",
        styles["Body"],
    ))

    story.append(p("8. Plot and replay catalogue", styles["H1"]))
    plot_rows = [
        ["Artifact", "What it shows"],
        ["full_grid_pace_ranking.png", "Average clean pace by driver; lower is faster."],
        ["full_grid_consistency_ranking.png", "Lap-time stability across the grid."],
        ["full_grid_tyre_management_ranking.png", "Who preserved tyre life best."],
        ["team_pace_comparison.png", "Average pace by team."],
        ["driver_battle_HAM_vs_RUS.png", "Lap-by-lap clean pace comparison."],
        ["full_grid_strategy_timeline.png", "Tyre stints and pit laps across the whole field."],
        ["race_pace_heatmap.png", "Relative clean-lap pace trace by driver and lap."],
        ["tyre_degradation_HAM_M.png", "SciPy tyre-age curve fit for the selected driver."],
        ["race_pace_replay.html", "Animated race-progress replay."],
        ["tyre_degradation_replay_HAM_M.html", "Animated tyre-fit reveal."],
        ["pit_stop_timeline_replay.html", "Animated stint and pit-stop timeline."],
    ]
    story.append(t(plot_rows, [2.5, 3.8], styles_map))

    story.append(p("9. Real-data import pipeline and verification", styles["H1"]))
    story.append(p(
        "The project now reads local FastF1-style CSV exports through a manifest-driven importer. The manifest preserves the source path for each completed race, the importer normalizes the lap schema into the project's standard columns, and the loaded bundle is then used by the CLI, GUI, browser UI, and report generation.",
        styles["Body"],
    ))
    ver_rows = [["Round", "Race", "Laps in bundle", "Drivers", "Status"]]
    race_counts = (
        laps.groupby("race_name", as_index=False)
        .agg(rows=("lap_number", "size"), drivers=("driver_code", "nunique"))
        .merge(calendar[["race_name", "round", "status", "total_laps"]], on="race_name", how="left")
        .sort_values("round")
    )
    for _, row in race_counts.iterrows():
        ver_rows.append([
            str(int(row["round"])),
            str(row["race_name"]),
            str(int(row["rows"])),
            str(int(row["drivers"])),
            str(row["status"]),
        ])
    story.append(t(ver_rows, [0.6, 2.7, 1.2, 0.9, 1.0], styles_map))
    story.append(p(
        "The validation pass confirmed that all eight supplied completed rounds are visible to the app. That matters for an interview because it shows the project is not only functional in isolation, but also wired to a source-tracked, reproducible data path.",
        styles["Body"],
    ))

    story.append(p("10. Project structure", styles["H1"]))
    module_rows = [
        ["Module", "Responsibility", "Notes"],
        ["main.py", "CLI entry point for demo, GUI, web, and animation modes.", "Routes to the right surface."],
        ["src/real_data_importer.py", "Imports and normalizes real race CSV files.", "Tracks source files and builds the local bundle."],
        ["src/data_loader.py", "Loads real or sample data depending on what is present.", "Keeps the rest of the app simple."],
        ["src/data_cleaning.py", "Applies the clean-lap rules.", "Removes pits, safety-car laps, and outliers."],
        ["src/driver_analysis.py", "Builds per-driver and full-grid analysis.", "Produces the summary table."],
        ["src/scoring.py", "Applies the visible scoring and badge rules.", "Turns metrics into a gamified rating."],
        ["src/tyre_degradation.py", "Fits the quadratic tyre-age model.", "Uses SciPy curve fitting and RMSE."],
        ["src/visualizer.py", "Creates the PNG dashboard plots.", "Matplotlib output only."],
        ["src/animations.py", "Creates HTML replays and static fallbacks.", "Kept dependency-light."],
        ["src/web_app.py", "Serves the local browser dashboard.", "Reuses the same backend calculations."],
        ["src/gui.py", "Tkinter desktop dashboard.", "Alternate offline front end."],
        ["src/report_generator.py", "Writes CSV, Markdown, and PDF report artefacts.", "Used for portfolio exports."],
    ]
    story.append(t(module_rows, [1.6, 3.35, 1.55], styles_map))

    story.append(p("11. Interview talking points", styles["H1"]))
    story.append(p(
        "If you want a crisp spoken summary, describe the project as an offline Formula 1 post-race engineering dashboard that turns source-tracked lap CSVs into pace, consistency, tyre, strategy, and replay outputs. Emphasize that the value is in transparency: every number comes from a visible rule or model, and the same backend powers the CLI, GUI, browser UI, plots, animations, and report export.",
        styles["Body"],
    ))
    story.append(p(
        "That framing makes it easy to talk about software engineering, data handling, analysis, and product thinking in one story, which is exactly what an interview panel usually wants to hear.",
        styles["Body"],
    ))

    def on_first_page(canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawCentredString(4.25 * inch, 0.45 * inch, "Pit Wall Predictor interview report")
        canvas.restoreState()

    def on_later_pages(canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawCentredString(4.25 * inch, 0.45 * inch, f"Pit Wall Predictor interview report - Page {doc.page}")
        canvas.restoreState()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    doc.build(story, onFirstPage=on_first_page, onLaterPages=on_later_pages)
    return PDF_PATH


if __name__ == "__main__":
    print(build_pdf())
