"""Basic backtracking Futoshiki solver (baseline).

Plain chronological backtracking: no AC-3, forward checking, MRV, MCV or LCV.
Unfilled cells are assigned in row-major order and values are tried in
ascending order. A value is committed only if it is consistent with every row,
column, fixed-value and inequality constraint whose other cells already hold a
value; otherwise the next value is tried, and when none fit the solver
backtracks immediately.


AI Disclousure: The algorithm was bounded to the display using help of Claude Code
and refactoring job was left to AI agent. Verified by implementing correct
solutions and read real articles. Code read and verified by me.
"""

from __future__ import annotations

import time
from typing import Callable, Dict, List, Optional, Set, Tuple

from puzzle import DEFAULT_TIMEOUT, Cell, Grid, Puzzle, SolveTimeout

StepCallback = Optional[Callable[[int, int, int], None]]


class BacktrackingSolver:
    def __init__(self, puzzle: Puzzle, on_step: StepCallback = None, timeout: float = DEFAULT_TIMEOUT):
        self.puzzle = puzzle
        self.n = puzzle.size
        self.on_step = on_step
        self.timeout = timeout
        self.grid: Grid = puzzle.initial_grid()
        self.unfilled: List[Cell] = [
            (r, c) for r in range(self.n) for c in range(self.n) if self.grid[r][c] == 0
        ]
        # Values currently placed in each row/column (givens included), so the
        # "no repeats" check against known values is a set lookup.
        self.row_used: List[Set[int]] = [set() for _ in range(self.n)]
        self.col_used: List[Set[int]] = [set() for _ in range(self.n)]
        # cell -> [(other cell, True if cell must be less than other)]
        self.ineq: Dict[Cell, List[Tuple[Cell, bool]]] = {}
        for smaller, larger in puzzle.inequalities:
            self.ineq.setdefault(smaller, []).append((larger, True))
            self.ineq.setdefault(larger, []).append((smaller, False))
        self.assignments = 0
        self.backtracks = 0
        self._deadline = 0.0

    def solve_with_backtracking(self) -> Optional[Grid]:
        """Return a solved grid, or None if no solution exists.

        Raises SolveTimeout if the search runs longer than self.timeout seconds.
        """
        self._deadline = time.perf_counter() + self.timeout
        if not self._givens_consistent():
            return None
        if self._backtrack(0):
            return [row[:] for row in self.grid]
        return None

    def _givens_consistent(self) -> bool:
        """Fixed values must not repeat in a row/column or break an inequality between them."""
        for (r, c), v in self.puzzle.givens.items():
            if v in self.row_used[r] or v in self.col_used[c]:
                return False
            self.row_used[r].add(v)
            self.col_used[c].add(v)
        for (r1, c1), (r2, c2) in self.puzzle.inequalities:
            a, b = self.grid[r1][c1], self.grid[r2][c2]
            if a and b and not a < b:
                return False
        return True

    def _backtrack(self, index: int) -> bool:
        if index == len(self.unfilled):
            return True
        if time.perf_counter() > self._deadline:
            raise SolveTimeout(self.timeout)

        r, c = self.unfilled[index]
        for value in range(1, self.n + 1):
            if not self._is_consistent(r, c, value):
                continue
            self._assign(r, c, value)
            if self._backtrack(index + 1):
                return True
            self._unassign(r, c, value)
        return False

    def _is_consistent(self, r: int, c: int, value: int) -> bool:
        if value in self.row_used[r] or value in self.col_used[c]:
            return False
        for (orow, ocol), must_be_less in self.ineq.get((r, c), ()):
            other = self.grid[orow][ocol]
            if other == 0:
                continue  # not known yet; checked when that cell is assigned
            if must_be_less and not value < other:
                return False
            if not must_be_less and not value > other:
                return False
        return True

    def _assign(self, r: int, c: int, value: int) -> None:
        self.grid[r][c] = value
        self.row_used[r].add(value)
        self.col_used[c].add(value)
        self.assignments += 1
        if self.on_step:
            self.on_step(r, c, value)

    def _unassign(self, r: int, c: int, value: int) -> None:
        self.grid[r][c] = 0
        self.row_used[r].discard(value)
        self.col_used[c].discard(value)
        self.backtracks += 1
        if self.on_step:
            self.on_step(r, c, 0)


def solve(puzzle: Puzzle, on_step: StepCallback = None, timeout: float = DEFAULT_TIMEOUT) -> Optional[Grid]:
    """UI entry point: return the solved grid or None; raises SolveTimeout on time-out.

    on_step(row, col, value) is called on every assignment (value > 0) and every
    backtrack (value = 0); indices are 0-based.
    """
    return BacktrackingSolver(puzzle, on_step, timeout).solve_with_backtracking()
