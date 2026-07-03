# Engineering Notes — PitWall-Predictor

## Why post-race analysis comes first

Post-race analysis starts with observed lap data. That makes it a much more approachable engineering problem than prediction: the tool can measure the pace and tyre behaviour that occurred, separate obvious non-representative laps, and describe strategy trade-offs. A future what-if simulator can use these measured trends, but this first version does not claim to predict an official race result.

## Clean lap analysis

A clean lap is intended to represent normal green-flag running. The code removes pit laps, in-laps, out-laps, and safety-car laps before calculating pace. Those events change lap time for operational reasons rather than pure car-and-driver pace:

- A pit lap contains the pit-lane time loss.
- An in-lap usually includes preparation for a stop and may include traffic management.
- An out-lap is slower because tyres and brakes are being brought into a working window.
- A safety-car lap has a controlled speed and is not representative of race pace.

After those exclusions, a simple per-driver outlier rule removes laps more than four seconds slower than the driver's median candidate clean lap. It is intentionally transparent and easy to change in `src/data_cleaning.py`.

## Scores

Consistency is based on the standard deviation of clean lap times: lower scatter produces a higher score. The current formula is `100 - 30 × standard deviation`, clipped to 0-100.

Tyre management uses the average positive linear degradation rate measured inside each stint. Lower clean-lap time growth produces a higher score. The formula is `100 - 430 × mean positive degradation rate`, also clipped to 0-100.

The overall race engineer score weights pace (35%), consistency (25%), tyre management (25%), and stint execution (15%). These are educational dashboard scores, not a real F1 team metric.

## Tyre degradation model

For sufficiently long clean same-compound samples, SciPy fits:

`lap time = base pace + a × tyre age + b × tyre age²`

Tyre age matters because the tyre's grip changes after each racing lap. A quadratic term allows the rate of degradation to increase or decrease rather than assuming a perfectly straight line. The model is fitted after the race to explain the observed sample; it is not a pre-race tyre model.

Pit, safety-car, in-, and out-laps are removed before fitting because their time losses are not caused by ordinary tyre ageing. Root-mean-square error (RMSE) reports how closely the fitted curve follows the observed clean laps.

## Limitations

- The app can load an imported real-data CSV bundle when one is present; the checked-in
  demo dataset remains only as an offline fallback for development.
- The generator uses simplified pit strategies, tyre effects, safety cars, and position estimates.
- Traffic, weather, fuel burn, DRS, track evolution, yellow flags, damage, and undercuts are not individually modelled.
- A pooled compound fit can mix stints with different fuel loads or race conditions.
- Team performance tiers are fictional generator inputs only and make no claim about real 2026 performance.

## Animation notes

Version 5 uses `matplotlib.animation.FuncAnimation` and Matplotlib's built-in
`HTMLWriter` to create portable replay files. This avoids relying on a local
ffmpeg installation or adding Pillow. If the local writer cannot complete an
export, the program reports the problem and saves the final animation frame as
a static PNG instead.

## Extension path

The Version 6 Tkinter dashboard and Version 7 local browser dashboard both
reuse the offline loader, analysis, report, plot, and replay modules. The web
UI is served with Python's standard-library `http.server`, so it improves visual
presentation without rewriting the backend or adding a web framework.

The modular loader can later accept compatible real CSV files. Good next
additions are optional local metadata enrichment, a post-race what-if pit-stop
timing model, or a deployed Flask/FastAPI layer if the app needs to run beyond
localhost.
