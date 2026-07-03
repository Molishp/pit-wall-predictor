# Barcelona-Catalunya Grand Prix - Post-Race Strategy Report

## Data note

This report uses the imported real-data bundle. Team pace assumptions and race events are derived from the loaded CSV source and demonstrate the Python analysis pipeline only.

## Full-grid summary

| final_position | driver_code | team | average_clean_pace | fastest_lap | consistency_score | tyre_management_score | pit_stops | race_engineer_score | badge_earned |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | HAM | Ferrari | 81.642 | 80.122 | 71.3 | 43.5 | 6 | 73.7 | Race Pace Beast |
| 2 | ANT | Mercedes | 82.303 | 80.704 | 71.3 | 63.9 | 4 | 75.0 | Clean Air King |
| 2 | RUS | Mercedes | 82.369 | 80.64 | 69.0 | 67.1 | 4 | 75.8 | Clean Air King |
| 3 | NOR | McLaren | 82.381 | 80.232 | 69.0 | 60.5 | 4 | 73.3 | Clean Air King |
| 4 | VER | Red Bull Racing | 82.225 | 80.23 | 70.6 | 46.3 | 6 | 69.6 | Tyre Cliff Victim |
| 5 | PIA | McLaren | 82.735 | 80.835 | 71.0 | 57.9 | 4 | 69.1 | Tyre Cliff Victim |
| 6 | HAD | Red Bull Racing | 83.264 | 80.15 | 63.4 | 64.2 | 6 | 62.8 | Tyre Cliff Victim |
| 6 | LEC | Ferrari | 82.544 | 80.379 | 70.1 | 54.9 | 5 | 69.4 | Smooth Operator |
| 7 | GAS | Alpine | 84.182 | 81.708 | 64.8 | 53.4 | 4 | 53.8 | Tyre Cliff Victim |
| 8 | COL | Alpine | 84.374 | 82.449 | 70.1 | 60.5 | 4 | 57.8 | Tyre Cliff Victim |
| 9 | LAW | Racing Bulls | 84.348 | 82.691 | 72.5 | 62.2 | 4 | 60.6 | Tyre Cliff Victim |
| 10 | LIN | Racing Bulls | 84.455 | 81.914 | 58.4 | 76.3 | 4 | 55.5 | Smooth Operator |
| 11 | BOR | Audi | 84.509 | 81.446 | 54.9 | 21.1 | 6 | 38.3 | Tyre Cliff Victim |
| 11 | ALB | Williams | 85.005 | 81.744 | 58.3 | 0.0 | 7 | 29.7 | Tyre Cliff Victim |
| 12 | SAI | Williams | 84.662 | 82.061 | 67.5 | 50.1 | 6 | 50.6 | Tyre Cliff Victim |
| 12 | HUL | Audi | 84.651 | 83.447 | 82.3 | 46.0 | 3 | 58.1 | Stint Monster |
| 13 | OCO | Haas F1 Team | 85.054 | 81.643 | 59.2 | 0.0 | 6 | 29.4 | Tyre Cliff Victim |
| 14 | PER | Cadillac | 85.778 | 82.82 | 60.1 | 24.4 | 6 | 35.3 | Tyre Cliff Victim |
| 15 | BEA | Haas F1 Team | 84.942 | 82.419 | 61.8 | 61.4 | 5 | 49.9 | Smooth Operator |
| 18 | ALO | Aston Martin | 86.621 | 85.366 | 74.3 | 65.4 | 3 | 46.7 | Smooth Operator |
| 21 | BOT | Cadillac | 87.223 | 85.745 | 68.3 | 0.0 | 2 | 28.3 | Tyre Cliff Victim |
| 22 | STR | Aston Martin | 86.212 | 85.904 | 93.3 | 72.3 | 1 | 52.6 | Consistency Champion |

## Driver battle: HAM vs RUS

HAM had the stronger average clean pace by 0.727s per lap. HAM was more consistent, while RUS managed degradation better. The finishing advantage went to HAM (P1).

- HAM: P1, 81.642s clean pace, 73.7/100, Race Pace Beast
- RUS: P2, 82.369s clean pace, 75.8/100, Clean Air King

## Selected driver engineer notes

### HAM - Lewis Hamilton

HAM showed strong clean-air pace and was reasonably consistent once non-representative laps were removed. The best phase was stint 4 on H tyres, while stint 1 was the slowest phase. The degradation trend suggests the tyres reached their limit too quickly.

- Clean laps: 56; fastest: 80.122s; standard deviation: 0.956s.
- Strategy: 6 pit stop(s); compounds used: S, H, M.
- Best stint: H L42-L66 (80.897s).

### RUS - George Russell

RUS showed steady clean-air pace and was reasonably consistent once non-representative laps were removed. The best phase was stint 3 on H tyres, while stint 1 was the slowest phase. Tyre management was acceptable, with room to smooth the long-run drop-off.

- Clean laps: 57; fastest: 80.640s; standard deviation: 1.035s.
- Strategy: 4 pit stop(s); compounds used: M, H.
- Best stint: H L37-L66 (81.831s).

## SciPy tyre model: HAM on M

Lap time = 80.7387 + -0.01034 x tyre age + 0.006693 x tyre age^2

RMSE: 0.1488s. The fitted degradation trend is steep, suggesting a tyre drop-off; RMSE of 0.15s indicates a close fit.
