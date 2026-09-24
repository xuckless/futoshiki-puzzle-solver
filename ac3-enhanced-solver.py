"""AC-3 enhanced backtracking Futoshiki solver.

Backtracking search that maintains arc consistency (MAC):

* Variables are the n*n cells; each domain starts as {given} or {1..n}.
* Binary constraints link every pair of cells sharing a row or column
  (values differ), plus the puzzle's inequalities between adjacent cells.
* AC-3 runs over every arc before search begins. AC-3 alone does not always
  solve a puzzle, so search continues from the reduced domains.
* The next variable is chosen by Minimum Remaining Values, with ties broken
  by the Most Constraining Variable (most unassigned neighbours) and then by
  row-major order. Values are tried in Least Constraining Value order.
* After each tentative assignment, AC-3 runs on the arcs pointing at the
  assigned cell, and propagates from there. An empty domain fails the branch.

Domain state during backtracking (copy / restore):
    Before each tentative assignment, the solver copies the whole domain map
    with _snapshot(): a new dict of copied sets, at most 81 sets of at most 9
    ints. The assignment and the AC-3 run after it change self.domains in
    place. When the branch fails, the solver puts the snapshot back. Nothing
    ever changes the snapshot, so one copy per recursion level restores the
    exact state before the assignment, however far AC-3 spread its removals.

Measurement: one node is counted (self.assignments, and one on_step call with
value > 0) every time the search tries a value on an unassigned cell. Givens
are not counted.

AI Disclousure: The algorithm was taught to me by AI, also binding it to display
on the UI and refactoring job was left to AI. Verified by implementing correct 
solutions and read real articles. 
"""

from __future__ import annotations

import time
from collections import deque
from typing import Callable, Dict, Iterable, List, Optional, Set, Tuple

from puzzle import DEFAULT_TIMEOUT, Cell, Grid, Puzzle, SolveTimeout

StepCallback = Optional[Callable[[int, int, int], None]]
Domains = Dict[Cell, Set[int]]
Arc = Tuple[Cell, Cell]


class AC3Solver:
    def __init__(self, puzzle: Puzzle, on_step: StepCallback = None, timeout: float = DEFAULT_TIMEOUT):
        self.puzzle = puzzle
        self.n = puzzle.size
        self.on_step = on_step
        self.timeout = timeout
        self.cells: List[Cell] = [(r, c) for r in range(self.n) for c in range(self.n)]
        # Every other cell in the same row or column. Inequality cells are
        # adjacent, so they are already neighbours.
        self.neighbours: Dict[Cell, List[Cell]] = {
            (r, c): [(r, k) for k in range(self.n) if k != c] + [(k, c) for k in range(self.n) if k != r]
            for r, c in self.cells
        }
        # (smaller, larger) pairs: value(smaller) < value(larger)
        self.less: Set[Arc] = set(puzzle.inequalities)
        self.domains: Domains = {}
        self.assigned: Dict[Cell, int] = dict(puzzle.givens)
        self.assignments = 0
        self.backtracks = 0
        self._deadline = 0.0

    def solve_with_ac3(self) -> Optional[Grid]:
        """Return a solved grid, or None if no solution exists.

        Raises SolveTimeout if the search runs longer than self.timeout seconds.
        """
        self._deadline = time.perf_counter() + self.timeout
        if not self.initialize():
            return None
        if self._backtrack():
            return [[self.assigned[(r, c)] for c in range(self.n)] for r in range(self.n)]
        return None

    def initialize(self) -> bool:
        """Set up the starting domains and run AC-3 on every arc; False if a domain empties."""
        self.domains = {
            cell: {self.puzzle.givens[cell]} if cell in self.puzzle.givens else set(range(1, self.n + 1))
            for cell in self.cells
        }
        return self.ac3((xi, xj) for xi in self.cells for xj in self.neighbours[xi])

    # ------------------------------------------------------------ propagation

    def _satisfies(self, xi: Cell, x: int, xj: Cell, y: int) -> bool:
        """True if xi = x and xj = y together satisfy the constraint between xi and xj."""
        if x == y:
            return False
        if (xi, xj) in self.less:
            return x < y
        if (xj, xi) in self.less:
            return x > y
        return True

    def revise(self, xi: Cell, xj: Cell) -> bool:
        """REVISE(Xi, Xj): drop each x in Di with no supporting y in Dj; True if Di changed."""
        di, dj = self.domains[xi], self.domains[xj]
        revised = False
        for x in list(di):
            if not any(self._satisfies(xi, x, xj, y) for y in dj):
                di.discard(x)
                revised = True
        return revised

    def ac3(self, arcs: Iterable[Arc]) -> bool:
        """Make the given arcs, and every arc they affect, consistent. False if a domain empties."""
        queue = deque(arcs)
        queued = set(queue)
        while queue:
            if time.perf_counter() > self._deadline:
                raise SolveTimeout(self.timeout)
            xi, xj = queue.popleft()
            queued.discard((xi, xj))
            if not self.revise(xi, xj):
                continue
            if not self.domains[xi]:
                return False
            # Di shrank, so every other arc (Xk, Xi) needs checking again.
            for xk in self.neighbours[xi]:
                if xk != xj and (xk, xi) not in queued:
                    queue.append((xk, xi))
                    queued.add((xk, xi))
        return True

    def _snapshot(self) -> Domains:
        """Copy the domains so a failed branch can restore them exactly (see module docstring)."""
        return {cell: d.copy() for cell, d in self.domains.items()}

    # ----------------------------------------------------------------- search

    def _backtrack(self) -> bool:
        if len(self.assigned) == len(self.cells):
            return True
        if time.perf_counter() > self._deadline:
            raise SolveTimeout(self.timeout)

        var = self._select_variable()
        for value in self._order_values(var):
            saved = self._snapshot()
            self._assign(var, value)
            if self.ac3((xk, var) for xk in self.neighbours[var]) and self._backtrack():
                return True
            self._unassign(var)
            self.domains = saved
        return False

    def _unassigned_degree(self, cell: Cell) -> int:
        return sum(1 for xk in self.neighbours[cell] if xk not in self.assigned)

    def _select_variable(self) -> Cell:
        """MRV, ties broken by Most Constraining Variable, then row-major order."""
        return min(
            (cell for cell in self.cells if cell not in self.assigned),
            key=lambda cell: (len(self.domains[cell]), -self._unassigned_degree(cell), cell),
        )

    def _order_values(self, var: Cell) -> List[int]:
        """LCV: values that remove the fewest options from unassigned neighbours come first."""
        values = sorted(self.domains[var])
        if len(values) == 1:
            return values
        others = [xk for xk in self.neighbours[var] if xk not in self.assigned]

        def ruled_out(x: int) -> int:
            return sum(1 for xk in others for y in self.domains[xk] if not self._satisfies(var, x, xk, y))

        return sorted(values, key=lambda x: (ruled_out(x), x))

    def _assign(self, cell: Cell, value: int) -> None:
        self.domains[cell] = {value}
        self.assigned[cell] = value
        self.assignments += 1
        if self.on_step:
            self.on_step(cell[0], cell[1], value)

    def _unassign(self, cell: Cell) -> None:
        del self.assigned[cell]
        self.backtracks += 1
        if self.on_step:
            self.on_step(cell[0], cell[1], 0)


def solve(puzzle: Puzzle, on_step: StepCallback = None, timeout: float = DEFAULT_TIMEOUT) -> Optional[Grid]:
    """UI entry point: return the solved grid or None; raises SolveTimeout on time-out.

    on_step(row, col, value) is called on every assignment (value > 0) and every
    backtrack (value = 0); indices are 0-based.
    """
    return AC3Solver(puzzle, on_step, timeout).solve_with_ac3()
