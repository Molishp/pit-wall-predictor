# Pit Wall Predictor

A Python-powered Formula 1 post-race strategy dashboard for the 2026 season.

Pit Wall Predictor turns completed-race lap-time CSV data into an interactive race-engineering review: clean-lap pace, tyre stints, degradation trends, driver battles, full-grid scoring, strategy notes, plots, replays, and PDF reports.

This is a post-race analysis project. It does not predict future races unless completed race data has been imported.

## What the app does

- Loads completed 2026 race data from local CSV files.
- Lets you choose a race, a main driver, and a comparison driver.
- Removes non-representative laps such as pit laps, in-laps, out-laps, safety-car laps, and extreme slow outliers.
- Calculates clean race pace, consistency, tyre management, stint execution, and a race engineer score.
- Compares two drivers with readable strategy-room notes.
- Generates Matplotlib plots, HTML replay animations, and PDF/Markdown/CSV reports.
- Provides a custom browser dashboard built with Python's standard `http.server`, HTML, CSS, and JavaScript.

## Tech stack

- Python
- NumPy
- Pandas
- SciPy
- Matplotlib
- Tkinter, for the optional desktop GUI
- Python standard library HTTP server
- Plain HTML/CSS/JavaScript for the browser UI

No Flask, FastAPI, Django, Streamlit, React, Plotly, or external web framework is required.

## Quick start on your computer

Open PowerShell inside this project folder:

```powershell
cd "M:\Upskill and Self Learn\Personal Projects\F1 Strategy Simulator"
```

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Launch the local browser app:

```powershell
python main.py --web
```

Then open:

```text
http://127.0.0.1:8000
```

If port `8000` is busy:

```powershell
python main.py --web --port 8010
```

## Command-line examples

Run the default analysis:

```powershell
python main.py
```

Analyze another completed race and driver battle:

```powershell
python main.py --race "Monaco Grand Prix" --driver HAM --compare RUS
```

Generate replay animations:

```powershell
python main.py --animations
```

Launch the optional Tkinter GUI:

```powershell
python main.py --gui
```

## Current real-data bundle

The app currently loads the imported real-data bundle in `data/real/`.

Completed imported rounds:

1. Australian Grand Prix
2. Chinese Grand Prix
3. Japanese Grand Prix
4. Miami Grand Prix
5. Canadian Grand Prix
6. Monaco Grand Prix
7. Barcelona-Catalunya Grand Prix
8. Austrian Grand Prix

Source tracking files:

- `data/real/source_manifest.csv`
- `data/real/source_index.json`
- `data/real/2026_real_race_laps.csv`
- `data/real/race_calendar_2026.csv`
- `data/real/raw_sources/<race_folder>/laps.csv`
- `data/real/raw_sources/<race_folder>/results.csv`

## Real-data import workflow

Each completed race should have a `laps.csv` file inside its race folder under:

```text
data/real/raw_sources/
```

After adding new race CSVs, update:

```text
data/real/source_manifest.csv
```

Then run:

```powershell
python -m src.real_data_importer --manifest data\real\source_manifest.csv --overwrite
```

The app will automatically prefer the imported real-data bundle when it exists.

## Engineering assumptions

- Pit laps, safety-car laps, in-laps, and out-laps are excluded from clean-lap pace.
- Laps more than 4 seconds slower than the driver's median representative lap are treated as outliers.
- Average clean pace is the mean of clean lap times.
- Consistency rewards lower clean-lap standard deviation.
- Tyre management is estimated from clean-lap degradation slopes by stint.
- The SciPy tyre model fits:

```text
Lap Time = Base Pace + a * Tyre Age + b * Tyre Age^2
```

- Race engineer score combines pace, consistency, tyre management, and stint execution.

For more detail, see:

```text
docs/engineering_notes.md
```

## Project structure

```text
main.py                         Main CLI, GUI, and web entry point
render.yaml                     Render deployment recipe
requirements.txt                Python dependencies

src/
  data_loader.py                Loads calendar, drivers, teams, and lap data
  real_data_importer.py         Imports source-tracked real race CSVs
  data_cleaning.py              Clean-lap filtering rules
  driver_analysis.py            Driver and full-grid calculations
  driver_comparison.py          Driver-vs-driver comparison logic
  scoring.py                    Race engineer score and badges
  tyre_degradation.py           SciPy tyre degradation model
  visualizer.py                 Matplotlib plot generation
  animations.py                 HTML replay animation generation
  report_generator.py           CSV, Markdown, and PDF reports
  gui.py                        Optional Tkinter GUI
  web_app.py                    Browser dashboard

data/
  real/                         Imported real-data bundle and source CSVs
  driver_metadata.csv           Driver metadata
  team_metadata.csv             Team metadata
  race_calendar_2026.csv        Local calendar metadata

assets/
  drivers/                      Local driver image assets
  cars/                         Local team car image assets
  team_logos/                   Local team logo assets
  track_maps/                   Local track map assets

outputs/
  plots/                        Generated plots
  animations/                   Generated HTML replays
  reports/                      Generated CSV, Markdown, PDF reports

docs/
  engineering_notes.md          Formula and design notes

tools/
  export_fastf1_csv.py          Helper to export race CSVs from FastF1
  cache_web_assets.py           Helper to cache web assets locally
```

## Hosting on Render

This project is prepared for Render as a Python web service.

Render start command:

```bash
python main.py --web --host 0.0.0.0 --no-browser
```

The app reads Render's `PORT` environment variable automatically. Locally, it still defaults to port `8000`.

## Important hosting note

Render's free web service filesystem is temporary. Generated plots, reports, and replays may disappear when the service restarts or redeploys. That is fine for a portfolio demo because users can regenerate outputs from the app.

If this later becomes a production project, generated outputs should be moved to persistent storage.
