# Pit Wall Predictor

A Formula 1 post-race strategy dashboard built with Python.

Live site: https://pit-wall-predictor.onrender.com/

## Quick Start

```powershell
cd "M:\Upskill and Self Learn\Personal Projects\F1 Strategy Simulator"
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
python main.py --web
```

Open:

```text
http://127.0.0.1:8000
```

## What It Does

- Compares two drivers from a completed Grand Prix.
- Shows clean pace, consistency, tyre management, and race engineer score.
- Generates plots, browser replays, and PDF/Markdown reports.
- Uses a browser-based interface with a Python backend.

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

The full explanation for the maths and scoring model is kept in the project report, while the README stays short and practical.

## Data

Imported 2026 race data is currently loaded through:

```text
Round 8 - Austrian Grand Prix
```

Completed races are available for analysis. Upcoming races appear in the selector until their data is added.

## Useful Commands

```powershell
python main.py
python main.py --race "Barcelona-Catalunya Grand Prix" --driver HAM --compare RUS
python main.py --gui
```

## Project Structure

```text
main.py          CLI, GUI, and web entry point
src/             Analysis and web app modules
data/            Calendar, metadata, and race CSV data
assets/          Driver, car, logo, and track assets
outputs/         Generated plots, replays, and reports
docs/            Engineering notes
tools/           Helper scripts
render.yaml      Render deployment config
requirements.txt Python dependencies
```

## Author

Molish Panneerselvam  
Mechanical Engineer

- LinkedIn: https://www.linkedin.com/in/molish-panneerselvam-22360721a/
- Portfolio: https://molish-personal.web.app/
- Email: pmolish@gmail.com
