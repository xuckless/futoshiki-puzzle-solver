"""Tkinter UI for the Futoshiki solver.

Board layout mirrors goobix.com's Futoshiki table: bordered square cells with
inequality glyphs sitting in the gaps between them.

Live view: the selected solver runs in a background thread and reports every
assignment through on_step(row, col, value). on_step only writes to a shared
grid; the Tk thread polls that grid every POLL_MS and redraws cells that changed,
so rendering cost stays bounded no matter how many steps the solver takes.
"""

from __future__ import annotations

import copy
import importlib.util
import threading
import time
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Dict, Optional

from puzzle import (DEFAULT_TIMEOUT, Cell, Grid, Puzzle, PuzzleFormatError, SolveCancelled,
                    SolveTimeout, load_puzzle)

PROJECT_DIR = Path(__file__).resolve().parent
TESTS_DIR = PROJECT_DIR / "tests"

SOLVERS: Dict[str, Path] = {
    "Basic Backtracking": PROJECT_DIR / "basic-backtracking-solver.py",
    "AC-3 Enhanced": PROJECT_DIR / "ac3-enhanced-solver.py",
}

BOARD_SIDE = 568   # canvas side in px; every grid size is scaled to fit it
MARGIN = 15
MAX_CELL = 80      # cap so 2x2..4x4 boards don't balloon
GAP_RATIO = 0.45   # space between cells (where the inequality glyphs go), relative to cell side
POLL_MS = 30

BORDER_COLOR = "#808080"
BG_COLOR = "#ffffff"
HIGHLIGHT_COLOR = "#fff3b0"
GIVEN_COLOR = "#000000"
SOLVER_COLOR = "#1f5fbf"
GLYPH_COLOR = "#505050"
STATUS_COLOR = "#333333"
FONT_FAMILY = "Helvetica"
DIGIT_SCALE = 0.66   # digit point size relative to cell side
GLYPH_SCALE = 0.375  # inequality glyph point size relative to cell side


def format_time(seconds: float) -> str:
    if seconds < 1:
        return f"Time: {seconds * 1000:.3f} ms"
    return f"Time: {seconds:.3f} s"


def load_solver(path: Path) -> Callable:
    """Import a solver file (hyphenated names aren't importable normally) and return its solve()."""
    module_name = "solver_" + path.stem.replace("-", "_")
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, "solve")


class SolveRun:
    """One solver execution in a background thread, plus the state it shares with the UI."""

    def __init__(self, puzzle: Puzzle, solve_fn: Callable, timeout: float):
        self._puzzle = copy.deepcopy(puzzle)
        self._solve_fn = solve_fn
        self.timeout = timeout
        self.live_grid: Grid = puzzle.initial_grid()
        self.assignments = 0
        self.backtracks = 0
        self.last_cell: Optional[Cell] = None
        self.stop_event = threading.Event()
        self.result: Optional[Grid] = None
        self.error: Optional[BaseException] = None
        self.error_trace = ""
        self.start = 0.0
        self.elapsed: Optional[float] = None
        self.thread = threading.Thread(target=self._run, daemon=True)

    def on_step(self, row: int, col: int, value: int) -> None:
        """Called from the solver thread. Must never touch Tk."""
        if self.stop_event.is_set():
            raise SolveCancelled()
        self.live_grid[row][col] = value
        if value:
            self.assignments += 1
        else:
            self.backtracks += 1
        self.last_cell = (row, col)

    def begin(self) -> None:
        self.start = time.perf_counter()
        self.thread.start()

    def _run(self) -> None:
        try:
            self.result = self._solve_fn(self._puzzle, self.on_step, timeout=self.timeout)
        except Exception as e:
            self.error = e
            self.error_trace = traceback.format_exc()
        finally:
            self.elapsed = time.perf_counter() - self.start


class FutoshikiApp(tk.Frame):
    def __init__(self, master: tk.Misc):
        super().__init__(master, bg=BG_COLOR)
        self.solvers: Dict[str, Path] = dict(SOLVERS)
        self.puzzle: Optional[Puzzle] = None
        self.displayed: Grid = []
        self.cell_rects: Dict[Cell, int] = {}
        self.cell_texts: Dict[Cell, int] = {}
        self.highlighted: Optional[Cell] = None
        self.cell = self.gap = self.offset = 0.0
        self.digit_font = self.given_font = self.glyph_font = (FONT_FAMILY, 1)
        self.active_run: Optional[SolveRun] = None

        self._build_top_bar()
        self.canvas = tk.Canvas(self, bg=BG_COLOR, highlightthickness=0,
                                width=BOARD_SIDE, height=BOARD_SIDE)
        self.canvas.pack(padx=10, pady=(5, 0))
        self.status_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self.status_var, bg=BG_COLOR, fg=STATUS_COLOR, anchor="center").pack(
            fill="x", padx=10, pady=(4, 10)
        )
        self._draw_placeholder()
        self.winfo_toplevel().protocol("WM_DELETE_WINDOW", self._on_close)

    # ----------------------------------------------------------------- layout

    def _build_top_bar(self) -> None:
        bar = ttk.Frame(self, padding=(10, 10, 10, 0))
        bar.pack(fill="x")

        self.load_button = ttk.Button(bar, text="Load puzzle…", command=self._choose_file)
        self.load_button.pack(side="left")
        self.file_var = tk.StringVar(value="No file loaded")
        ttk.Label(bar, textvariable=self.file_var, width=20, foreground="#666666").pack(
            side="left", padx=(6, 12)
        )

        ttk.Label(bar, text="Algorithm:").pack(side="left")
        self.algorithm_var = tk.StringVar(value=next(iter(self.solvers)))
        self.algorithm_box = ttk.Combobox(
            bar, textvariable=self.algorithm_var, values=list(self.solvers),
            state="readonly", width=18,
        )
        self.algorithm_box.pack(side="left", padx=(4, 12))

        ttk.Label(bar, text="Timeout (s):").pack(side="left")
        self.timeout_var = tk.StringVar(value=f"{DEFAULT_TIMEOUT:g}")
        self.timeout_box = ttk.Spinbox(bar, textvariable=self.timeout_var, from_=1, to=3600,
                                       increment=5, width=5)
        self.timeout_box.pack(side="left", padx=(4, 12))

        self.solve_button = ttk.Button(bar, text="Solve", command=self._solve_or_stop, state="disabled")
        self.solve_button.pack(side="left")

        self.timer_var = tk.StringVar(value=format_time(0))
        ttk.Label(bar, textvariable=self.timer_var, width=16, font=("Menlo", 12)).pack(
            side="left", padx=(12, 0)
        )

    def _draw_placeholder(self) -> None:
        self.canvas.delete("all")
        self.canvas.create_text(BOARD_SIDE / 2, BOARD_SIDE / 2, text="Load a puzzle to begin",
                                fill="#999999", font=(FONT_FAMILY, 16))

    def _layout(self, n: int) -> None:
        """Size cells, gaps and fonts so an n×n board fills the fixed canvas, centred."""
        self.cell = min(MAX_CELL, (BOARD_SIDE - 2 * MARGIN) / (n + (n - 1) * GAP_RATIO))
        self.gap = self.cell * GAP_RATIO
        self.offset = (BOARD_SIDE - (n * self.cell + (n - 1) * self.gap)) / 2
        digit_pt = round(self.cell * DIGIT_SCALE)
        self.digit_font = (FONT_FAMILY, digit_pt)
        self.given_font = (FONT_FAMILY, digit_pt, "bold")
        self.glyph_font = (FONT_FAMILY, round(self.cell * GLYPH_SCALE), "bold")

    def _cell_origin(self, r: int, c: int):
        step = self.cell + self.gap
        return self.offset + c * step, self.offset + r * step

    def _draw_board(self) -> None:
        p = self.puzzle
        n = p.size
        self._layout(n)
        cell, gap = self.cell, self.gap
        self.canvas.delete("all")
        self.cell_rects.clear()
        self.cell_texts.clear()
        self.highlighted = None
        self.displayed = [[0] * n for _ in range(n)]

        for r in range(n):
            for c in range(n):
                x, y = self._cell_origin(r, c)
                self.cell_rects[(r, c)] = self.canvas.create_rectangle(
                    x, y, x + cell, y + cell, outline=BORDER_COLOR, width=1, fill=BG_COLOR
                )
                self.cell_texts[(r, c)] = self.canvas.create_text(
                    x + cell / 2, y + cell / 2, text="", font=self.digit_font
                )
                glyph = p.h_symbol(r, c) if c < n - 1 else ""
                if glyph:
                    self.canvas.create_text(x + cell + gap / 2, y + cell / 2, text=glyph,
                                            font=self.glyph_font, fill=GLYPH_COLOR)
                glyph = p.v_symbol(r, c) if r < n - 1 else ""
                if glyph:
                    self.canvas.create_text(x + cell / 2, y + cell + gap / 2, text=glyph,
                                            font=self.glyph_font, fill=GLYPH_COLOR)

        self._sync_board(p.initial_grid(), None)

    def _sync_board(self, grid: Grid, last_cell: Optional[Cell]) -> None:
        """Redraw only the cells whose value differs from what's on screen."""
        givens = self.puzzle.givens
        for r, row in enumerate(grid):
            shown = self.displayed[r]
            for c, value in enumerate(row):
                if shown[c] == value:
                    continue
                shown[c] = value
                is_given = (r, c) in givens
                self.canvas.itemconfigure(
                    self.cell_texts[(r, c)],
                    text=str(value) if value else "",
                    fill=GIVEN_COLOR if is_given else SOLVER_COLOR,
                    font=self.given_font if is_given else self.digit_font,
                )
        self._set_highlight(last_cell)

    def _set_highlight(self, cell: Optional[Cell]) -> None:
        if cell == self.highlighted:
            return
        if self.highlighted is not None:
            self.canvas.itemconfigure(self.cell_rects[self.highlighted], fill=BG_COLOR)
        if cell is not None:
            self.canvas.itemconfigure(self.cell_rects[cell], fill=HIGHLIGHT_COLOR)
        self.highlighted = cell

    # ---------------------------------------------------------------- loading

    def _choose_file(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="Load Futoshiki puzzle",
            initialdir=str(TESTS_DIR if TESTS_DIR.is_dir() else PROJECT_DIR),
            filetypes=[("Text files", "*.txt"), ("All files", "*")],
        )
        if path:
            self.load_file(path)

    def load_file(self, path: str) -> bool:
        try:
            puzzle = load_puzzle(path)
        except (OSError, PuzzleFormatError) as e:
            messagebox.showerror("Could not load puzzle", f"{Path(path).name}: {e}", parent=self)
            return False
        self.puzzle = puzzle
        self.file_var.set(Path(path).name)
        self._draw_board()
        self.timer_var.set(format_time(0))
        self.status_var.set(f"{puzzle.size}×{puzzle.size} puzzle · {len(puzzle.givens)} givens · "
                            f"{len(puzzle.inequalities)} inequalities")
        self.solve_button.configure(state="normal")
        return True

    # ---------------------------------------------------------------- solving

    def _solve_or_stop(self) -> None:
        if self.active_run is not None:
            self.active_run.stop_event.set()
            self.solve_button.configure(state="disabled")
            return
        if self.puzzle is None:
            return

        algorithm = self.algorithm_var.get()
        try:
            timeout = float(self.timeout_var.get())
            if timeout <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid timeout", "Timeout must be a positive number of seconds.",
                                 parent=self)
            return
        try:
            solve_fn = load_solver(self.solvers[algorithm])
        except AttributeError:
            self.status_var.set(f"{algorithm} not implemented yet (no solve() function)")
            return
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Could not load solver", f"{algorithm}: {type(e).__name__}: {e}",
                                 parent=self)
            return

        self._sync_board(self.puzzle.initial_grid(), None)
        self.active_run = SolveRun(self.puzzle, solve_fn, timeout)
        self._set_running(True)
        self.status_var.set(f"{algorithm} · solving…")
        self.active_run.begin()
        self.after(POLL_MS, self._poll)

    def _set_running(self, running: bool) -> None:
        self.load_button.configure(state="disabled" if running else "normal")
        self.algorithm_box.configure(state="disabled" if running else "readonly")
        self.timeout_box.configure(state="disabled" if running else "normal")
        self.solve_button.configure(text="Stop" if running else "Solve", state="normal")

    def _poll(self) -> None:
        run = self.active_run
        if run is None:
            return
        self._sync_board(run.live_grid, run.last_cell)
        if run.thread.is_alive():
            self.timer_var.set(format_time(time.perf_counter() - run.start))
            self.status_var.set(f"{self.algorithm_var.get()} · solving… · {self._counts(run)}")
            self.after(POLL_MS, self._poll)
        else:
            self._finish(run)

    def _finish(self, run: SolveRun) -> None:
        self.active_run = None
        self._set_running(False)
        self.timer_var.set(format_time(run.elapsed))
        algorithm = self.algorithm_var.get()

        if isinstance(run.error, NotImplementedError):
            outcome = "not implemented yet"
        elif isinstance(run.error, SolveCancelled):
            outcome = "stopped"
        elif isinstance(run.error, SolveTimeout):
            outcome = str(run.error)
        elif run.error is not None:
            print(run.error_trace, end="")
            outcome = f"error: {type(run.error).__name__}: {run.error}"
        elif run.result is None:
            outcome = "no solution"
        elif self.puzzle.is_solution(run.result):
            self._sync_board(run.result, None)
            outcome = "solved ✓"
        else:
            outcome = "invalid solution returned ✗"
        self._set_highlight(None)
        self.status_var.set(f"{algorithm} · {outcome} · {self._counts(run)}")

    @staticmethod
    def _counts(run: SolveRun) -> str:
        return f"assignments: {run.assignments:,} · backtracks: {run.backtracks:,}"

    def _on_close(self) -> None:
        if self.active_run is not None:
            self.active_run.stop_event.set()
        self.winfo_toplevel().destroy()
