import importlib.util
import sys
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from puzzle import SolveTimeout, parse_puzzle  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "basic_backtracking_solver", PROJECT_DIR / "basic-backtracking-solver.py"
)
bt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bt)

SOLVABLE_5X5 = """SIZE
5
GIVENS
1,1,1
3,3,4
INEQUALITIES
1,2,<,1,3
2,4,>,3,4
4,1,<,4,2
5,5,>,5,4
"""

# 1 < a < b < c < d forces a 3x3 value of at least 5: no solution.
UNSAT_CHAIN = """SIZE
3
INEQUALITIES
1,1,<,1,2
1,2,<,1,3
1,3,<,2,3
2,3,<,3,3
"""


class BacktrackingTest(unittest.TestCase):
    def test_solves_puzzle_with_givens_and_inequalities(self):
        p = parse_puzzle(SOLVABLE_5X5)
        grid = bt.solve(p)
        self.assertTrue(p.is_solution(grid))

    def test_row_major_ascending_order(self):
        p = parse_puzzle("SIZE\n3\n")
        steps = []
        grid = bt.solve(p, lambda r, c, v: steps.append((r, c, v)))
        self.assertEqual(grid, [[1, 2, 3], [2, 3, 1], [3, 1, 2]])
        self.assertEqual(steps[:3], [(0, 0, 1), (0, 1, 2), (0, 2, 3)])

    def test_skips_givens_in_row_major_walk(self):
        p = parse_puzzle("SIZE\n3\nGIVENS\n1,1,3\n")
        steps = []
        bt.solve(p, lambda r, c, v: steps.append((r, c, v)))
        self.assertEqual(steps[0], (0, 1, 1))
        self.assertNotIn((0, 0), {(r, c) for r, c, _ in steps})

    def test_unsatisfiable_returns_none(self):
        self.assertIsNone(bt.solve(parse_puzzle(UNSAT_CHAIN)))

    def test_inconsistent_givens_return_none(self):
        dup_in_row = parse_puzzle("SIZE\n3\nGIVENS\n1,1,2\n1,3,2\n")
        self.assertIsNone(bt.solve(dup_in_row))
        breaks_inequality = parse_puzzle("SIZE\n3\nGIVENS\n1,1,3\n1,2,1\nINEQUALITIES\n1,1,<,1,2\n")
        self.assertIsNone(bt.solve(breaks_inequality))

    def test_inequality_respected_against_known_neighbour(self):
        # (1,1) < (1,2) with (1,2)=1 given is impossible, even though the rest is free.
        p = parse_puzzle("SIZE\n3\nGIVENS\n1,2,1\nINEQUALITIES\n1,1,<,1,2\n")
        self.assertIsNone(bt.solve(p))

    def test_timeout(self):
        p = parse_puzzle(SOLVABLE_5X5)
        with self.assertRaises(SolveTimeout) as ctx:
            bt.solve(p, timeout=0)
        self.assertEqual(ctx.exception.timeout, 0)

    def test_default_timeout_is_60s(self):
        solver = bt.BacktrackingSolver(parse_puzzle("SIZE\n3\n"))
        self.assertEqual(solver.timeout, 60.0)

    def test_counters_match_callbacks(self):
        p = parse_puzzle(SOLVABLE_5X5)
        steps = []
        solver = bt.BacktrackingSolver(p, lambda r, c, v: steps.append(v))
        self.assertTrue(p.is_solution(solver.solve_with_backtracking()))
        self.assertEqual(solver.assignments, sum(1 for v in steps if v))
        self.assertEqual(solver.backtracks, sum(1 for v in steps if not v))
        # every unfilled cell ends up assigned: assignments - backtracks == number of empty cells
        self.assertEqual(solver.assignments - solver.backtracks, 25 - len(p.givens))


if __name__ == "__main__":
    unittest.main()
