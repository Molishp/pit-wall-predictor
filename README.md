# Pit Wall Predictor 🏎️

Formula 1 post-race strategy analysis, built in Python.

Pit Wall Predictor is a browser-based race-engineering dashboard that turns completed Grand Prix lap data into clean pace analysis, driver battles, tyre strategy notes, replay animations, plots, and PDF reports.

It is designed as a personal portfolio project: part motorsport analytics, part Python backend, part interactive web dashboard.

> Status: 2026 completed-race dataset loaded through Round 8, Austrian Grand Prix.

## Why this project exists

Formula 1 strategy is not only about who sets the fastest lap. Race pace, pit timing, tyre degradation, consistency, traffic, and stint execution all matter.

This project takes raw race CSV data and turns it into a more readable “pit wall” view:

- Who had the stronger clean race pace?
- Which driver was more consistent?
- Where did the tyre drop-off appear?
- Did the final result match the underlying pace?
- What plots, replays, and reports can explain the race clearly?

## Main features

| Area | What it does |
| --- | --- |
| Race selector | Choose a completed 2026 Grand Prix. |
| Driver battle | Compare one driver against another. |
| Clean-lap model | Removes pit laps, in-laps, out-laps, safety-car laps, and extreme slow outliers. |
| Race engineer score | Combines pace, consistency, tyre management, and stint execution. |
| Strategy room | Summarizes stint plans, pit laps, tyre choices, and key race differences. |
| Visual analysis | Generates Matplotlib pace, consistency, tyre, team, timeline, heatmap, and battle plots. |
| Replay studio | Creates browser-previewable HTML race replays and tyre degradation animations. |
| Report export | Produces CSV, Markdown, and PDF reports for portfolio/interview evidence. |
| Local media assets | Uses local driver, car, team logo, and track map assets for a richer UI. |

## Tech stack

| Layer | Tools |
| --- | --- |
| Language | Python |
| Data | Pandas, NumPy |
| Modelling | SciPy |
| Plots/replays | Matplotlib |
| Web app | Python `http.server`, HTML, CSS, JavaScript |
| Desktop GUI | Tkinter |
| Reports | Custom CSV, Markdown, and dependency-light PDF generation |
| Hosting target | Render |

No Flask, FastAPI, Django, Streamlit, React, Plotly, or external web framework is required.

## How the analysis works

The app follows a transparent post-race workflow:

1. Load completed-race CSV data.
2. Filter out laps that do not represent normal race pace.
3. Calculate clean-lap metrics for each driver.
4. Break each driver’s race into tyre stints.
5. Estimate degradation trends from lap time versus tyre age.
6. Compare selected driver versus rival.
7. Convert the results into scores, badges, strategy notes, plots, replays, and reports.

Core formula used for tyre modelling:

```text
Lap Time = Base Pace + a * Tyre Age + b * Tyre Age^2
```

The race engineer score combines:

- clean pace
- consistency
- tyre management
- stint execution

The score is explanatory, not an official FIA/F1 performance rating.

## Current data coverage

The app currently uses an imported real-data bundle stored in `data/real/`.

Completed imported rounds:

1. Australian Grand Prix
2. Chinese Grand Prix
3. Japanese Grand Prix
4. Miami Grand Prix
5. Canadian Grand Prix
6. Monaco Grand Prix
7. Barcelona-Catalunya Grand Prix
8. Austrian Grand Prix

The data bundle includes:

- source manifest
- source hash index
- race calendar
- combined lap dataset
- per-race `laps.csv`
- per-race `results.csv`

This makes the data pipeline easier to audit and update as new races are completed.

## Run locally

Open PowerShell in the project folder:

```powershell
cd "M:\Upskill and Self Learn\Personal Projects\F1 Strategy Simulator"
```

Create a virtual environment:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\activate
```

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Launch the browser dashboard:

```powershell
python main.py --web
```

Open:

```text
http://127.0.0.1:8000
```

If port `8000` is busy:

```powershell
python main.py --web --port 8010
```

## Useful commands

Run the default CLI analysis:

```powershell
python main.py
```

Analyze a specific race and driver battle:

```powershell
python main.py --race "Barcelona-Catalunya Grand Prix" --driver HAM --compare RUS
```

Generate replay animations:

```powershell
python main.py --animations
```

Launch the Tkinter desktop GUI:

```powershell
python main.py --gui
```

## Updating race data

Each completed race should have a source CSV in:

```text
data/real/raw_sources/
```

After adding new race files, update:

```text
data/real/source_manifest.csv
```

Then rebuild the real-data bundle:

```powershell
python -m src.real_data_importer --manifest data\real\source_manifest.csv --overwrite
```

Once the imported bundle exists, the app automatically prefers it over the demo fallback dataset.

## Project structure

```text
main.py                         Main CLI, GUI, and web entry point
render.yaml                     Render deployment config
requirements.txt                Python dependencies

src/
  web_app.py                    Browser dashboard and API routes
  data_loader.py                Loads calendar, drivers, teams, and laps
  real_data_importer.py         Imports source-tracked race CSV files
  data_cleaning.py              Clean-lap filtering rules
  driver_analysis.py            Driver and grid calculations
  driver_comparison.py          Driver-vs-driver comparison
  scoring.py                    Scores, badges, and verdicts
  tyre_degradation.py           SciPy tyre degradation model
  visualizer.py                 Matplotlib plot generation
  animations.py                 HTML replay generation
  report_generator.py           CSV, Markdown, and PDF reports
  gui.py                        Optional Tkinter GUI

data/
  real/                         Imported real-data bundle
  driver_metadata.csv           Driver metadata
  team_metadata.csv             Team metadata
  race_calendar_2026.csv        Local calendar metadata

assets/
  drivers/                      Driver portraits
  cars/                         Team car images
  team_logos/                   Team logos
  track_maps/                   Track layout assets

outputs/
  plots/                        Generated plots
  animations/                   Generated HTML replays
  reports/                      Generated reports

docs/
  engineering_notes.md          Formula notes and assumptions

tools/
  export_fastf1_csv.py          Helper for FastF1 CSV export
  cache_web_assets.py           Helper for caching web assets
```

## Deployment

This project is prepared for Render.

Render build command:

```bash
pip install -r requirements.txt
```

Render start command:

```bash
python main.py --web --host 0.0.0.0 --no-browser
```

The app reads Render’s `PORT` environment variable automatically. Locally, it defaults to `8000`.

## Notes and limitations

- This is a post-race analyzer, not a live race predictor.
- The current deployment target is a free Render web service.
- Render free services may sleep after inactivity.
- Generated plots, replays, and reports are runtime files; on free hosting they may disappear after restart and can be regenerated from the app.
- The scoring model is intentionally transparent and educational, not an official F1 ranking system.

## Author

Molish Panneerselvam  
Mechanical Engineer  

- LinkedIn: <https://www.linkedin.com/in/molish-panneerselvam-22360721a/>
- Portfolio website: <https://molish-personal.web.app/>
- Email: <pmolish@gmail.com>
