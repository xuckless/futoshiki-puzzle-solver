"""AC-3 enhanced backtracking Futoshiki solver."""

from puzzle import DEFAULT_TIMEOUT


def solve(puzzle, on_step=None, timeout=DEFAULT_TIMEOUT):
    """Solve `puzzle` (a puzzle.Puzzle) and return the solved grid, or None if unsolvable.

    Call on_step(row, col, value) every time a cell is assigned (value > 0) or
    cleared on backtrack (value = 0); indices are 0-based. The UI uses these
    calls for its live view, and on_step raises puzzle.SolveCancelled when the
    user presses Stop, so no cancel handling is needed here. Raise
    puzzle.SolveTimeout(timeout) if the search runs longer than `timeout` seconds.
    """
    raise NotImplementedError
