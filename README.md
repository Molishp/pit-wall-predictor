# Pit Wall Predictor 🏎️

A Formula 1 post-race strategy dashboard built with Python.

Live site: https://pit-wall-predictor.onrender.com/

## Overview

Pit Wall Predictor converts completed Grand Prix lap data into a clean race-engineering dashboard. It helps compare drivers, review tyre stints, inspect clean race pace, generate strategy notes, and export plots, replays, and reports.

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

## Tech stack

- Python
- Pandas
- NumPy
- SciPy
- Matplotlib
- Tkinter
- HTML, CSS, JavaScript
- Python `http.server`
- Render

No Flask, FastAPI, Streamlit, React, or Plotly is used.

## Data

The app currently includes imported 2026 race data through:

```text
Round 8 - Austrian Grand Prix
```

Completed races are available for full analysis. Upcoming races are shown in the selector but safely marked as upcoming until data is imported.

## How it works

1. Load race lap CSV data.
2. Remove non-representative laps.
3. Calculate clean pace, consistency, tyre management, and stint metrics.
4. Compare the selected driver against a rival.
5. Generate readable strategy notes, plots, replays, and reports.

## Core formulas

The model is intentionally transparent. These are the main calculations used by the backend.

### Clean-lap filtering

```text
Clean Lap = not pit lap
          + not safety-car lap
          + not in-lap
          + not out-lap
          + lap time <= driver median lap time + 4.0 seconds
```

### Driver pace metrics

```text
Average Clean Pace = mean(clean lap times)
Fastest Clean Lap = min(clean lap times)
Slowest Clean Lap = max(clean lap times)
Lap Time Std Dev = sqrt(mean((lap time - average clean pace)^2))
```

### Stint and compound metrics

```text
Stint Average Pace = mean(clean lap times in that stint)
Compound Pace = mean(clean lap times on that compound)
Stint Degradation Rate = slope of clean lap time vs tyre age
```

The stint degradation rate uses a simple linear fit:

```text
Clean Lap Time = intercept + degradation_rate * tyre_age
```

### Driver comparison

```text
Pace Delta = Driver A average clean pace - Driver B average clean pace
```

Negative pace delta means Driver A was faster on average. Positive pace delta means Driver B was faster.

### Race engineer score

All component scores are clipped between 0 and 100.

```text
Pace Score = 100 - (driver average clean pace - fastest grid average clean pace) * 22

Consistency Score = 100 - lap time standard deviation * 30

Tyre Management Score = 100 - average positive stint degradation rate * 430

Stint Execution Score = 100 - (slowest stint average pace - fastest stint average pace) * 18
```

Fallback values are used when there is not enough data:

```text
Tyre Management Score = 70, if no usable degradation rates exist
Stint Execution Score = 75, if fewer than two usable stints exist
```

Final weighted score:

```text
Race Engineer Score =
  0.35 * Pace Score
+ 0.25 * Consistency Score
+ 0.25 * Tyre Management Score
+ 0.15 * Stint Execution Score
```

### Tyre degradation model

```text
Lap Time = Base Pace + a * Tyre Age + b * Tyre Age^2
```

The local degradation rate at a specific tyre age is:

```text
Degradation Rate = a + 2 * b * Tyre Age
```

Model error is measured with RMSE:

```text
RMSE = sqrt(mean((actual lap time - predicted lap time)^2))
```

### Replay positioning

The replay converts timing gaps into an approximate fractional lap position.

```text
Cumulative Driver Time = cumulative sum(driver lap times)
Gap To Leader = driver cumulative time - leader cumulative time
Replay Progress = current lap - gap to leader / leader lap time
```

The scores are explanatory and educational, not official Formula 1 ratings.

## Run locally

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

## Useful commands

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

## Project structure

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
Mechanical Engineer

- LinkedIn: https://www.linkedin.com/in/molish-panneerselvam-22360721a/
- Portfolio: https://molish-personal.web.app/
- Email: pmolish@gmail.com
