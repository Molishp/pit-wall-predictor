"""Colourful Tkinter front end for the existing PitWall-Predictor backend.

This module deliberately contains presentation and button wiring only.  Race
loading, scoring, reports, visualizations, and replays continue to use the
existing Version 1-5 modules without duplicating their calculations.
"""

from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from src.animations import generate_animations
from src.data_loader import get_race_laps, get_race_status, load_all_data
from src.driver_analysis import build_grid_summary
from src.driver_comparison import compare_drivers
from src.report_generator import write_reports
from src.tyre_degradation import fit_tyre_degradation
from src.visualizer import generate_dashboard


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKGROUND = "#0B0E14"
PANEL = "#161B25"
PANEL_ALT = "#202838"
TEXT = "#F2F5FA"
MUTED = "#AAB4C5"
GRID = "#3F4A5C"
ACCENT = "#00D2BE"
RADIO_GREEN = "#38E078"
WARNING = "#FFD12E"
ERROR = "#FF5A65"


class PitWallApp:
    """A responsive, backend-reusing pit-wall dashboard built with Tkinter."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("PitWall-Predictor | F1 2026 Post-Race Strategy Analyzer")
        self.root.geometry("1480x900")
        self.root.minsize(1160, 720)
        self.root.configure(bg=BACKGROUND)

        # Load all local CSV data once. The existing loader generates it if needed.
        self.calendar, self.drivers, self.teams, self.all_laps = load_all_data()
        self.race_laps = None
        self.summary = None
        self.results: dict[str, dict[str, Any]] = {}
        self.current_race_name: str | None = None
        self.avatar_image: tk.PhotoImage | None = None
        self.team_cards: dict[str, tk.Frame] = {}

        self.race_var = tk.StringVar(value="Barcelona-Catalunya Grand Prix")
        self.driver_var = tk.StringVar(value="HAM - Lewis Hamilton")
        self.comparison_var = tk.StringVar(value="RUS - George Russell")
        self.mode_var = tk.StringVar(value="Driver analysis")
        self.race_status_var = tk.StringVar(value="OFFLINE DATA READY")
        self.header_race_var = tk.StringVar(value="Barcelona-Catalunya Grand Prix")
        self.team_name_var = tk.StringVar(value="Ferrari")
        self.driver_name_var = tk.StringVar(value="Lewis Hamilton")
        self.driver_meta_var = tk.StringVar(value="#44 | HAM")
        self.score_var = tk.StringVar(value="--")
        self.rating_var = tk.StringVar(value="Load a completed race")

        self._configure_styles()
        self._build_layout()
        self.load_selected_race(show_message=False)

    def _configure_styles(self) -> None:
        """Use the built-in clam theme so the palette works on Windows/macOS/Linux."""
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("PitWall.TFrame", background=BACKGROUND)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("Title.TLabel", background=BACKGROUND, foreground=TEXT, font=("Segoe UI", 21, "bold"))
        style.configure("Subtitle.TLabel", background=BACKGROUND, foreground=MUTED, font=("Segoe UI", 10))
        style.configure("PanelTitle.TLabel", background=PANEL, foreground=TEXT, font=("Segoe UI", 13, "bold"))
        style.configure("Body.TLabel", background=PANEL, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=PANEL, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Dark.TCombobox", fieldbackground=PANEL_ALT, background=PANEL_ALT, foreground=TEXT, arrowcolor=TEXT)
        style.map("Dark.TCombobox", fieldbackground=[("readonly", PANEL_ALT)], foreground=[("readonly", TEXT)])
        style.configure("Accent.TButton", background=ACCENT, foreground="#07110F", font=("Segoe UI", 10, "bold"), padding=(10, 8), borderwidth=0)
        style.map("Accent.TButton", background=[("active", "#42E6D4")])
        style.configure("Action.TButton", background="#2D7DFF", foreground=TEXT, font=("Segoe UI", 10, "bold"), padding=(10, 8), borderwidth=0)
        style.map("Action.TButton", background=[("active", "#5598FF")])
        style.configure("Warning.TButton", background=WARNING, foreground="#161100", font=("Segoe UI", 10, "bold"), padding=(10, 8), borderwidth=0)
        style.map("Warning.TButton", background=[("active", "#FFE06A")])

    def _build_layout(self) -> None:
        """Create the pit-wall layout: setup, driver card, engineer result, radio."""
        self.root.grid_columnconfigure(0, weight=0, minsize=280)
        self.root.grid_columnconfigure(1, weight=1, minsize=390)
        self.root.grid_columnconfigure(2, weight=1, minsize=390)
        self.root.grid_rowconfigure(1, weight=1)

        self._build_top_bar()
        self._build_setup_panel()
        self._build_driver_card()
        self._build_result_panel()
        self._build_radio_panel()

    def _build_top_bar(self) -> None:
        top = tk.Frame(self.root, bg=BACKGROUND, padx=22, pady=15)
        top.grid(row=0, column=0, columnspan=3, sticky="ew")
        top.grid_columnconfigure(1, weight=1)
        tk.Label(top, text="PITWALL-PREDICTOR", bg=BACKGROUND, fg=TEXT, font=("Segoe UI", 22, "bold")).grid(row=0, column=0, sticky="w")
        tk.Label(top, text="F1 2026 Post-Race Strategy Analyzer", bg=BACKGROUND, fg=MUTED, font=("Segoe UI", 10)).grid(row=1, column=0, sticky="w", pady=(1, 0))
        self.header_race_label = tk.Label(top, textvariable=self.header_race_var, bg=PANEL_ALT, fg=TEXT, font=("Segoe UI", 10, "bold"), padx=14, pady=7)
        self.header_race_label.grid(row=0, column=1, rowspan=2, sticky="e", padx=(15, 12))
        self.status_label = tk.Label(top, textvariable=self.race_status_var, bg=RADIO_GREEN, fg="#07110F", font=("Segoe UI", 9, "bold"), padx=12, pady=7)
        self.status_label.grid(row=0, column=2, rowspan=2, sticky="e")

    def _build_setup_panel(self) -> None:
        panel = tk.Frame(self.root, bg=PANEL, padx=16, pady=16, highlightbackground=GRID, highlightthickness=1)
        panel.grid(row=1, column=0, sticky="nsew", padx=(18, 8), pady=(4, 10))
        panel.grid_columnconfigure(0, weight=1)
        tk.Label(panel, text="RACE SETUP", bg=PANEL, fg=TEXT, font=("Segoe UI", 14, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 13))

        self._combo_row(panel, "Season", tk.StringVar(value="2026"), ["2026"], 1)
        race_names = self.calendar["race_name"].tolist()
        self._combo_row(panel, "Race", self.race_var, race_names, 3, self._on_race_change)
        driver_values = [f"{row.driver_code} - {row.driver_name}" for row in self.drivers.itertuples()]
        self._combo_row(panel, "Driver", self.driver_var, driver_values, 5, self._on_driver_change)
        self._combo_row(panel, "Compare", self.comparison_var, driver_values, 7)
        self._combo_row(panel, "Mode", self.mode_var, ["Driver analysis", "Driver battle", "Full-grid dashboard"], 9)

        ttk.Button(panel, text="LOAD RACE", command=self.load_selected_race, style="Accent.TButton").grid(row=11, column=0, sticky="ew", pady=(12, 5))
        ttk.Button(panel, text="ANALYZE DRIVER", command=self.analyze_selected_driver, style="Action.TButton").grid(row=12, column=0, sticky="ew", pady=5)
        ttk.Button(panel, text="COMPARE DRIVERS", command=self.compare_selected_drivers, style="Action.TButton").grid(row=13, column=0, sticky="ew", pady=5)
        ttk.Button(panel, text="GENERATE PLOTS", command=self.generate_plots, style="Warning.TButton").grid(row=14, column=0, sticky="ew", pady=(12, 5))
        ttk.Button(panel, text="RUN REPLAY ANIMATIONS", command=self.generate_replays, style="Warning.TButton").grid(row=15, column=0, sticky="ew", pady=5)
        ttk.Button(panel, text="EXPORT REPORT", command=self.export_report, style="Accent.TButton").grid(row=16, column=0, sticky="ew", pady=5)

        tk.Label(panel, text="TEAM COLOUR CARDS", bg=PANEL, fg=MUTED, font=("Segoe UI", 9, "bold")).grid(row=17, column=0, sticky="w", pady=(18, 7))
        card_grid = tk.Frame(panel, bg=PANEL)
        card_grid.grid(row=18, column=0, sticky="ew")
        for index, team in enumerate(self.teams.itertuples()):
            card = tk.Frame(card_grid, bg=team.primary_colour, padx=5, pady=5, highlightthickness=1, highlightbackground=team.primary_colour)
            card.grid(row=index // 2, column=index % 2, sticky="ew", padx=(0, 5) if index % 2 == 0 else (0, 0), pady=2)
            card_grid.grid_columnconfigure(index % 2, weight=1)
            tk.Label(card, text=team.short_team_name, bg=team.primary_colour, fg=self._contrast_colour(team.primary_colour), font=("Segoe UI", 7, "bold"), wraplength=100).pack(fill="x")
            self.team_cards[team.team] = card

    def _combo_row(
        self,
        parent: tk.Frame,
        label: str,
        variable: tk.StringVar,
        values: list[str],
        row: int,
        callback: Any | None = None,
    ) -> None:
        tk.Label(parent, text=label.upper(), bg=PANEL, fg=MUTED, font=("Segoe UI", 8, "bold")).grid(row=row, column=0, sticky="w", pady=(4, 3))
        combo = ttk.Combobox(parent, textvariable=variable, values=values, state="readonly", style="Dark.TCombobox", font=("Segoe UI", 9))
        combo.grid(row=row + 1, column=0, sticky="ew", pady=(0, 4))
        if callback is not None:
            combo.bind("<<ComboboxSelected>>", callback)

    def _build_driver_card(self) -> None:
        panel = tk.Frame(self.root, bg=PANEL, padx=22, pady=18, highlightbackground=GRID, highlightthickness=1)
        panel.grid(row=1, column=1, sticky="nsew", padx=8, pady=(4, 10))
        panel.grid_columnconfigure(0, weight=1)
        tk.Label(panel, text="DRIVER CARD", bg=PANEL, fg=TEXT, font=("Segoe UI", 14, "bold")).grid(row=0, column=0, sticky="w")
        self.team_label = tk.Label(panel, textvariable=self.team_name_var, bg="#E8002D", fg=TEXT, font=("Segoe UI", 10, "bold"), padx=12, pady=5)
        self.team_label.grid(row=0, column=1, sticky="e")

        self.avatar_canvas = tk.Canvas(panel, width=190, height=190, bg=PANEL, highlightthickness=0)
        self.avatar_canvas.grid(row=1, column=0, columnspan=2, pady=(20, 8))
        tk.Label(panel, textvariable=self.driver_name_var, bg=PANEL, fg=TEXT, font=("Segoe UI", 20, "bold")).grid(row=2, column=0, columnspan=2, pady=(3, 0))
        tk.Label(panel, textvariable=self.driver_meta_var, bg=PANEL, fg=MUTED, font=("Segoe UI", 11)).grid(row=3, column=0, columnspan=2, pady=(4, 12))

        tk.Label(panel, text="STYLIZED TEAM CAR", bg=PANEL, fg=MUTED, font=("Segoe UI", 9, "bold")).grid(row=4, column=0, columnspan=2, pady=(7, 3))
        self.car_canvas = tk.Canvas(panel, width=330, height=150, bg=PANEL_ALT, highlightbackground=GRID, highlightthickness=1)
        self.car_canvas.grid(row=5, column=0, columnspan=2, pady=(0, 16))
        tk.Label(panel, text="Placeholder avatar and car art are generated locally; optional PNG avatars remain supported.", bg=PANEL, fg=MUTED, font=("Segoe UI", 8), wraplength=330, justify="center").grid(row=6, column=0, columnspan=2)

    def _build_result_panel(self) -> None:
        panel = tk.Frame(self.root, bg=PANEL, padx=20, pady=18, highlightbackground=GRID, highlightthickness=1)
        panel.grid(row=1, column=2, sticky="nsew", padx=(8, 18), pady=(4, 10))
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_columnconfigure(1, weight=1)
        tk.Label(panel, text="RACE ENGINEER RESULT", bg=PANEL, fg=TEXT, font=("Segoe UI", 14, "bold")).grid(row=0, column=0, sticky="w")
        tk.Label(panel, text="POST-RACE MODE", bg="#2D7DFF", fg=TEXT, font=("Segoe UI", 8, "bold"), padx=8, pady=5).grid(row=0, column=1, sticky="e")

        score_frame = tk.Frame(panel, bg=PANEL_ALT, padx=16, pady=12, highlightbackground=GRID, highlightthickness=1)
        score_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(16, 12))
        score_frame.grid_columnconfigure(1, weight=1)
        tk.Label(score_frame, text="RACE ENGINEER SCORE", bg=PANEL_ALT, fg=MUTED, font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w")
        tk.Label(score_frame, textvariable=self.score_var, bg=PANEL_ALT, fg=WARNING, font=("Segoe UI", 31, "bold")).grid(row=1, column=0, sticky="w")
        self.rating_label = tk.Label(score_frame, textvariable=self.rating_var, bg=PANEL_ALT, fg=TEXT, font=("Segoe UI", 11, "bold"), wraplength=205, justify="right")
        self.rating_label.grid(row=0, column=1, rowspan=2, sticky="e")

        self.metric_vars: dict[str, tk.StringVar] = {}
        metric_definitions = [
            ("Clean pace", "average_clean_pace"),
            ("Fastest lap", "fastest_lap"),
            ("Consistency", "consistency_score"),
            ("Tyre management", "tyre_management_score"),
            ("Pit stops", "pit_stops"),
            ("Best stint", "best_stint"),
        ]
        for index, (label, key) in enumerate(metric_definitions):
            variable = tk.StringVar(value="--")
            self.metric_vars[key] = variable
            card = tk.Frame(panel, bg=PANEL_ALT, padx=11, pady=10, highlightbackground=GRID, highlightthickness=1)
            card.grid(row=2 + index // 2, column=index % 2, sticky="nsew", padx=(0, 6) if index % 2 == 0 else (6, 0), pady=5)
            tk.Label(card, text=label.upper(), bg=PANEL_ALT, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w")
            tk.Label(card, textvariable=variable, bg=PANEL_ALT, fg=TEXT, font=("Segoe UI", 11, "bold"), wraplength=160, justify="left").pack(anchor="w", pady=(4, 0))

        tk.Label(panel, text="BADGES EARNED", bg=PANEL, fg=MUTED, font=("Segoe UI", 9, "bold")).grid(row=5, column=0, columnspan=2, sticky="w", pady=(15, 5))
        self.badges_frame = tk.Frame(panel, bg=PANEL)
        self.badges_frame.grid(row=6, column=0, columnspan=2, sticky="ew")

    def _build_radio_panel(self) -> None:
        panel = tk.Frame(self.root, bg=PANEL, padx=18, pady=13, highlightbackground=GRID, highlightthickness=1)
        panel.grid(row=2, column=0, columnspan=3, sticky="ew", padx=18, pady=(0, 16))
        panel.grid_columnconfigure(1, weight=1)
        tk.Label(panel, text="RADIO", bg=RADIO_GREEN, fg="#07110F", font=("Segoe UI", 10, "bold"), padx=10, pady=6).grid(row=0, column=0, sticky="nw", padx=(0, 12))
        self.radio_text = tk.Text(panel, height=3, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat", wrap="word", font=("Segoe UI", 10), padx=0, pady=0)
        self.radio_text.grid(row=0, column=1, sticky="ew")
        self._set_radio("Radio: Offline data ready. Load a completed race and the pit wall will do the rest.")

    @staticmethod
    def _contrast_colour(hex_colour: str) -> str:
        """Choose readable label text for one of the team colour cards."""
        hex_colour = hex_colour.lstrip("#")
        red, green, blue = (int(hex_colour[index:index + 2], 16) for index in (0, 2, 4))
        brightness = (red * 299 + green * 587 + blue * 114) / 1000
        return "#081018" if brightness > 155 else "#FFFFFF"

    @staticmethod
    def _driver_code(value: str) -> str:
        """Extract the code from a selector option such as 'HAM - Lewis Hamilton'."""
        return value.split(" - ", 1)[0].strip().upper()

    def _selected_driver_code(self) -> str:
        return self._driver_code(self.driver_var.get())

    def _selected_comparison_code(self) -> str:
        return self._driver_code(self.comparison_var.get())

    def _on_race_change(self, _event: Any = None) -> None:
        self.header_race_var.set(self.race_var.get())
        status = get_race_status(self.calendar, self.race_var.get())
        if status == "upcoming":
            self.race_status_var.set("UPCOMING - NO DATA")
            self.status_label.configure(bg=WARNING, fg="#161100")
        else:
            self.race_status_var.set("READY TO LOAD")
            self.status_label.configure(bg="#2D7DFF", fg=TEXT)

    def _on_driver_change(self, _event: Any = None) -> None:
        self._update_driver_card()
        if self.current_race_name == self.race_var.get() and self.results:
            self.analyze_selected_driver(quiet=True)

    def _set_radio(self, message: str) -> None:
        self.radio_text.configure(state="normal")
        self.radio_text.delete("1.0", "end")
        self.radio_text.insert("1.0", message)
        self.radio_text.configure(state="disabled")

    def _set_status(self, text: str, colour: str, foreground: str = TEXT) -> None:
        self.race_status_var.set(text)
        self.status_label.configure(bg=colour, fg=foreground)

    def _current_team_row(self) -> Any:
        driver = self.drivers.loc[self.drivers["driver_code"] == self._selected_driver_code()].iloc[0]
        return self.teams.loc[self.teams["team"] == driver["team"]].iloc[0]

    def _update_driver_card(self) -> None:
        """Redraw avatar and car when the driver selector changes."""
        code = self._selected_driver_code()
        driver = self.drivers.loc[self.drivers["driver_code"] == code].iloc[0]
        team = self._current_team_row()
        team_colour = str(team["primary_colour"])
        self.driver_name_var.set(str(driver["driver_name"]))
        self.driver_meta_var.set(f"#{int(driver['driver_number'])} | {code} | {driver['nationality']}")
        self.team_name_var.set(str(driver["team"]))
        self.team_label.configure(bg=team_colour, fg=self._contrast_colour(team_colour))
        self._draw_avatar(driver, team_colour)
        self._draw_car(int(driver["driver_number"]), team_colour, str(team["secondary_colour"]), code)
        for team_name, card in self.team_cards.items():
            is_selected = team_name == driver["team"]
            card.configure(highlightbackground=TEXT if is_selected else card.cget("bg"), highlightthickness=2 if is_selected else 1)

    def _draw_avatar(self, driver: Any, team_colour: str) -> None:
        """Use an optional local PNG, otherwise draw the requested circular placeholder."""
        canvas = self.avatar_canvas
        canvas.delete("all")
        self.avatar_image = None
        avatar_path = ROOT_DIR / str(driver["avatar_file"])
        if avatar_path.is_file():
            try:
                self.avatar_image = tk.PhotoImage(file=str(avatar_path))
                canvas.create_image(95, 95, image=self.avatar_image)
                return
            except tk.TclError:
                # Unsupported local image: retain a clean, project-owned placeholder.
                self.avatar_image = None
        canvas.create_oval(8, 8, 182, 182, fill=team_colour, outline="#FFFFFF", width=2)
        canvas.create_oval(24, 24, 166, 166, fill=PANEL_ALT, outline="", width=0)
        canvas.create_text(95, 78, text=str(driver["driver_code"]), fill=TEXT, font=("Segoe UI", 27, "bold"))
        canvas.create_text(95, 118, text=f"#{int(driver['driver_number'])}", fill=WARNING, font=("Segoe UI", 17, "bold"))
        initials = "".join(part[0] for part in str(driver["driver_name"]).split()[:2])
        canvas.create_text(95, 145, text=initials, fill=MUTED, font=("Segoe UI", 10, "bold"))

    def _draw_car(self, number: int, primary_colour: str, secondary_colour: str, code: str) -> None:
        """Draw a generic, non-official top-view race-car icon using Canvas shapes."""
        canvas = self.car_canvas
        canvas.delete("all")
        canvas.create_rectangle(0, 0, 330, 150, fill=PANEL_ALT, outline="")
        # Wheels and wings first, then a simple central body, so it reads as a car.
        for x, y in ((65, 28), (242, 28), (65, 95), (242, 95)):
            canvas.create_rectangle(x, y, x + 24, y + 31, fill="#06080C", outline="#3B4352", width=1)
        canvas.create_rectangle(102, 17, 228, 28, fill=secondary_colour, outline="#080A0E")
        canvas.create_rectangle(91, 117, 239, 130, fill=secondary_colour, outline="#080A0E")
        canvas.create_polygon(142, 28, 188, 28, 209, 67, 201, 112, 130, 112, 121, 67, fill=primary_colour, outline="#05070A", width=2)
        canvas.create_polygon(151, 35, 179, 35, 187, 62, 143, 62, fill=secondary_colour, outline="")
        canvas.create_oval(148, 62, 182, 96, fill="#101218", outline="#FFFFFF", width=1)
        canvas.create_text(165, 79, text=str(number), fill=TEXT, font=("Segoe UI", 14, "bold"))
        canvas.create_text(165, 140, text=f"{code} // PITWALL SPEC", fill=MUTED, font=("Segoe UI", 8, "bold"))

    def _reset_result_panel(self) -> None:
        self.score_var.set("--")
        self.rating_var.set("Load a completed race")
        for variable in self.metric_vars.values():
            variable.set("--")
        for widget in self.badges_frame.winfo_children():
            widget.destroy()

    def load_selected_race(self, show_message: bool = True) -> None:
        """Load a completed race via existing loader/analysis modules, never future data."""
        race_name = self.race_var.get()
        self.header_race_var.set(race_name)
        status = get_race_status(self.calendar, race_name)
        if status != "completed":
            self.race_laps = None
            self.summary = None
            self.results = {}
            self.current_race_name = None
            self._reset_result_panel()
            message = "Race data not available yet. This tool is currently a post-race analyzer."
            self._set_status("UPCOMING - NO DATA", WARNING, "#161100")
            self._set_radio(f"Radio: {message}")
            if show_message:
                messagebox.showinfo("Post-race analyzer", message, parent=self.root)
            return
        try:
            self._set_status("LOADING RACE", "#2D7DFF")
            self.root.update_idletasks()
            race_laps = get_race_laps(self.all_laps, race_name)
            if race_laps.empty:
                raise ValueError("The calendar marks this race completed, but no lap data was found.")
            self.summary, self.results = build_grid_summary(race_laps)
            self.race_laps = race_laps
            self.current_race_name = race_name
            self._set_status("RACE DATA LOADED", RADIO_GREEN, "#07110F")
            self._update_driver_card()
            self.analyze_selected_driver(quiet=True)
            if show_message:
                self._set_radio(f"Radio: {race_name} loaded. Green flag for post-race analysis of all 22 drivers.")
        except Exception as error:
            self._set_status("LOAD ERROR", ERROR)
            self._set_radio(f"Radio: Unable to load race data: {error}")
            if show_message:
                messagebox.showerror("Load race", str(error), parent=self.root)

    def _require_loaded_race(self) -> bool:
        if self.race_laps is not None and self.current_race_name == self.race_var.get() and self.results:
            return True
        self._set_radio("Radio: Load a completed race first. Upcoming races do not have analysis data yet.")
        return False

    def _selected_tyre_fit(self) -> dict[str, Any] | None:
        result = self.results[self._selected_driver_code()]
        compound = "M" if "M" in result["compound_usage"] else result["compound_usage"].split(", ")[0]
        return fit_tyre_degradation(self.race_laps, self._selected_driver_code(), compound)

    def analyze_selected_driver(self, quiet: bool = False) -> None:
        """Populate the driver card and result metrics from the already-built grid result."""
        if not self._require_loaded_race():
            return
        result = self.results[self._selected_driver_code()]
        self.score_var.set(f"{result['race_engineer_score']:.1f}/100")
        self.rating_var.set(result["rating"])
        self.metric_vars["average_clean_pace"].set(f"{result['average_clean_pace']:.3f} s")
        self.metric_vars["fastest_lap"].set(f"{result['fastest_lap']:.3f} s")
        self.metric_vars["consistency_score"].set(f"{result['consistency_score']:.1f}/100")
        self.metric_vars["tyre_management_score"].set(f"{result['tyre_management_score']:.1f}/100")
        self.metric_vars["pit_stops"].set(str(result["pit_stops"]))
        best = result["best_stint"]
        self.metric_vars["best_stint"].set(f"{best['compound']} | L{best['start_lap']}-L{best['end_lap']}")
        for widget in self.badges_frame.winfo_children():
            widget.destroy()
        for badge in result["badges"]:
            tk.Label(self.badges_frame, text=badge, bg=WARNING, fg="#171100", font=("Segoe UI", 8, "bold"), padx=8, pady=5).pack(side="left", padx=(0, 5), pady=2)
        if not quiet:
            self._set_radio(f"Radio: {result['race_engineer_verdict']}")

    def compare_selected_drivers(self) -> None:
        """Run the existing generic comparison and surface its verdict in race radio."""
        if not self._require_loaded_race():
            return
        try:
            comparison = compare_drivers(self.results, self._selected_driver_code(), self._selected_comparison_code())
            self._set_radio(f"Radio: {comparison['verdict']}")
        except Exception as error:
            self._set_radio(f"Radio: Comparison unavailable: {error}")

    def generate_plots(self) -> None:
        """Delegate the full-grid static dashboard to the existing visualizer module."""
        if not self._require_loaded_race():
            return
        try:
            self._set_status("GENERATING PLOTS", WARNING, "#161100")
            self._set_radio("Radio: Copy. Generating the full-grid Matplotlib dashboard...")
            self.root.update_idletasks()
            comparison = compare_drivers(self.results, self._selected_driver_code(), self._selected_comparison_code())
            plots = generate_dashboard(self.summary, self.results, self.race_laps, comparison, self._selected_tyre_fit(), ROOT_DIR / "outputs" / "plots")
            self._set_status("PLOTS READY", RADIO_GREEN, "#07110F")
            self._set_radio(f"Radio: Dashboard complete. {len(plots)} plots saved in outputs/plots.")
        except Exception as error:
            self._set_status("PLOT ERROR", ERROR)
            self._set_radio(f"Radio: Plot generation failed: {error}")

    def generate_replays(self) -> None:
        """Delegate Version 5 HTML replay generation to the existing animation module."""
        if not self._require_loaded_race():
            return
        try:
            self._set_status("RENDERING REPLAYS", WARNING, "#161100")
            self._set_radio("Radio: Stand by. Rendering Matplotlib replays; this can take a moment...")
            self.root.update_idletasks()
            exports = generate_animations(self.race_laps, self.results, self._selected_tyre_fit(), ROOT_DIR / "outputs" / "animations")
            messages = "; ".join(export.message for export in exports)
            self._set_status("REPLAYS READY", RADIO_GREEN, "#07110F")
            self._set_radio(f"Radio: {messages}")
        except Exception as error:
            self._set_status("REPLAY ERROR", ERROR)
            self._set_radio(f"Radio: Replay generation failed: {error}")

    def export_report(self) -> None:
        """Delegate CSV/Markdown export to the existing report generator."""
        if not self._require_loaded_race():
            return
        try:
            comparison = compare_drivers(self.results, self._selected_driver_code(), self._selected_comparison_code())
            reports = write_reports(self.summary, self.results, comparison, self._selected_tyre_fit(), ROOT_DIR / "outputs" / "reports")
            self._set_status("REPORT EXPORTED", RADIO_GREEN, "#07110F")
            self._set_radio(f"Radio: Report exported: {reports['summary_csv'].name} and {reports['markdown_report'].name}.")
        except Exception as error:
            self._set_status("REPORT ERROR", ERROR)
            self._set_radio(f"Radio: Report export failed: {error}")


def run_gui() -> int:
    """Start the desktop GUI and report a helpful message if Tk cannot open a window."""
    try:
        root = tk.Tk()
    except tk.TclError as error:
        print(f"PitWall-Predictor GUI could not start: {error}")
        print("Use the normal command-line mode, or run this project from a desktop Python installation with Tkinter.")
        return 1
    PitWallApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(run_gui())
