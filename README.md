# Pit Wall Predictor 🏎️

A Formula 1 post-race strategy dashboard built with Python.

Live site: https://pit-wall-predictor.onrender.com/

## Overview

Pit Wall Predictor converts completed Formula 1 Grand Prix lap data into a clean race-engineering dashboard. It helps compare drivers, review tyre stints, inspect clean race pace, generate strategy notes, and export plots, replays, and reports.

The project is designed as a portfolio piece combining Python data analysis, backend logic, and a custom browser UI.

## Features

| Feature | Description |
| --- | --- |
| Race and driver selection | Choose a completed race, driver, and comparison driver. |
| Clean-lap analysis | Filters pit laps, in-laps, out-laps, safety-car laps, and major slow-lap outliers. |
| Driver comparison | Compares clean pace, consistency, tyre management, and final result. |
| Race engineer score | Produces an easy-to-read score from pace, consistency, tyres, and stint execution. |
| Strategy room | Summarizes pit stops, tyre choices, and race-defining strategy differences. |
| Exports | Generates plots, browser replays, CSV summaries, Markdown notes, and PDF reports. |
| Deployment | Hosted live on Render as a Python web service. |

## Tech Stack

- Python
- Pandas
- NumPy
- SciPy
- Matplotlib
- Tkinter
- HTML, CSS, JavaScript
- Python `http.server`
- Render

## Data

The app currently includes imported 2026 race data.

Completed races are available for full analysis. Upcoming races are shown in the selector but safely marked as upcoming until data is imported.

## Limitations

- The project currently focuses only on the 2026 Formula 1 season.
- The analysis covers main Grand Prix race sessions only, not sprint races, qualifying, practice, or live race prediction.
- The live website is hosted on Render, so it may go inactive after a period of no traffic. If the page loads slowly, wait a short time and refresh once the service wakes up.

## How It Works

1. Load race lap CSV data.
2. Remove non-representative laps.
3. Calculate clean pace, consistency, tyre management, and stint metrics.
4. Compare the selected driver against a rival.
5. Generate readable strategy notes, plots, replays, and reports.

## Core Formulas

```text
Clean Lap = not pit lap
          + not safety-car lap
          + not in-lap
          + not out-lap
          + lap time <= driver median lap time + 4.0 seconds

Race Engineer Score =
  0.35 * Pace Score
+ 0.25 * Consistency Score
+ 0.25 * Tyre Management Score
+ 0.15 * Stint Execution Score

Lap Time = Base Pace + a * Tyre Age + b * Tyre Age^2
```

The scores are explanatory and educational, not official Formula 1 ratings.

## Run Locally

```powershell
cd "F1 Strategy Simulator"
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
python main.py --web
```

Open:

```text
http://127.0.0.1:8000
```

## Useful Commands

Run the default analysis:

```powershell
python main.py
```

Run a specific driver battle:

```powershell
python main.py --race "Barcelona-Catalunya Grand Prix" --driver HAM --compare RUS
```

Launch the Tkinter GUI:

```powershell
python main.py --gui
```

## Project Structure

```text
main.py                  Main CLI, GUI, and web entry point
src/                     Backend analysis and web app modules
data/                    Calendar, metadata, and race CSV data
assets/                  Driver, car, logo, and track assets
outputs/                 Generated plots, replays, and reports
docs/                    Engineering notes
tools/                   Helper scripts
render.yaml              Render deployment config
requirements.txt         Python dependencies
```

## Author

Molish Panneerselvam  
Mechanical Engineer | Motorsport and Aerospace design

- LinkedIn: https://www.linkedin.com/in/molish-panneerselvam-22360721a/
- Portfolio: https://molish-personal.web.app/
- Email: pmolish@gmail.com
