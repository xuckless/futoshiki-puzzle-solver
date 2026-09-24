import importlib.util
import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
PROJECT_DIR = TESTS_DIR.parent
sys.path.insert(0, str(PROJECT_DIR))

from puzzle import SolveTimeout, load_puzzle, parse_puzzle  # noqa: E402


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, PROJECT_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ac3 = _load("ac3_enhanced_solver", "ac3-enhanced-solver.py")
bt = _load("basic_backtracking_solver", "basic-backtracking-solver.py")

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

SOLVABLE_FIXTURES = ["4x4-easy.txt", "6x6-easy.txt", "6x6-hard.txt", "8x8-medium.txt", "8x8-hard.txt"]


class AC3SolverTest(unittest.TestCase):
    def test_solves_puzzle_with_givens_and_inequalities(self):
        p = parse_puzzle(SOLVABLE_5X5)
        self.assertTrue(p.is_solution(ac3.solve(p)))

    def test_solves_fixtures(self):
        # The two 8x8-easy files time out under basic backtracking but not here.
        for name in SOLVABLE_FIXTURES + ["8x8-easy.txt", "8x8-easy-2.txt"]:
            with self.subTest(name):
                p = load_puzzle(str(TESTS_DIR / name))
                self.assertTrue(p.is_solution(ac3.solve(p)))

    def test_unsolvable_returns_none(self):
        self.assertIsNone(ac3.solve(parse_puzzle(UNSAT_CHAIN)))
        self.assertIsNone(ac3.solve(load_puzzle(str(TESTS_DIR / "unsolvable-6x6.txt"))))

    def test_inconsistent_givens_return_none(self):
        dup_in_row = parse_puzzle("SIZE\n3\nGIVENS\n1,1,2\n1,3,2\n")
        self.assertIsNone(ac3.solve(dup_in_row))
        breaks_inequality = parse_puzzle("SIZE\n3\nGIVENS\n1,1,3\n1,2,1\nINEQUALITIES\n1,1,<,1,2\n")
        self.assertIsNone(ac3.solve(breaks_inequality))

    def test_revise_removes_unsupported_values(self):
        solver = ac3.AC3Solver(parse_puzzle("SIZE\n3\nINEQUALITIES\n1,1,<,1,2\n"))
        solver.domains = {cell: {1, 2, 3} for cell in solver.cells}
        solver.domains[(0, 1)] = {1, 2}
        self.assertTrue(solver.revise((0, 0), (0, 1)))
        self.assertEqual(solver.domains[(0, 0)], {1})
        self.assertFalse(solver.revise((0, 0), (0, 1)))

    def test_revise_all_different(self):
        solver = ac3.AC3Solver(parse_puzzle("SIZE\n3\n"))
        solver.domains = {cell: {1, 2, 3} for cell in solver.cells}
        solver.domains[(0, 1)] = {2}
        self.assertTrue(solver.revise((0, 0), (0, 1)))
        self.assertEqual(solver.domains[(0, 0)], {1, 3})

    def test_initial_ac3_prunes_domains(self):
        p = load_puzzle(str(TESTS_DIR / "4x4-easy.txt"))
        solver = ac3.AC3Solver(p)
        solver._deadline = float("inf")
        self.assertTrue(solver.initialize())
        self.assertTrue(all(solver.domains.values()))
        self.assertLess(sum(len(d) for d in solver.domains.values()), 16 * 4)
        for (r, c), v in p.givens.items():
            self.assertEqual(solver.domains[(r, c)], {v})
            for other in solver.neighbours[(r, c)]:
                self.assertNotIn(v, solver.domains[other])

    def test_initial_ac3_detects_unsat(self):
        solver = ac3.AC3Solver(parse_puzzle(UNSAT_CHAIN))
        solver._deadline = float("inf")
        self.assertFalse(solver.initialize())

    def test_failed_branch_restores_domains(self):
        p = parse_puzzle(SOLVABLE_5X5)
        solver = ac3.AC3Solver(p)
        solver._deadline = float("inf")
        solver.initialize()
        before = solver._snapshot()
        steps = []
        solver.on_step = lambda r, c, v: steps.append((r, c, v))
        # Force a failure below the first level by making the rest unsolvable
        # through a monkeypatched _backtrack after the first assignment.
        real = solver._backtrack
        depth = [0]

        def fail_below_top():
            depth[0] += 1
            try:
                return real() if depth[0] == 1 else False
            finally:
                depth[0] -= 1

        solver._backtrack = fail_below_top
        self.assertFalse(solver._backtrack())
        self.assertEqual(solver.domains, before)
        self.assertEqual(solver.assigned, p.givens)
        self.assertEqual(solver.assignments, solver.backtracks)

    def test_mrv_picks_smallest_domain_first(self):
        p = load_puzzle(str(TESTS_DIR / "8x8-hard.txt"))
        probe = ac3.AC3Solver(p)
        probe._deadline = float("inf")
        probe.initialize()
        smallest = min(len(d) for cell, d in probe.domains.items() if cell not in p.givens)

        steps = []
        ac3.solve(p, lambda r, c, v: steps.append((r, c, v)))
        r, c, _ = steps[0]
        self.assertEqual(len(probe.domains[(r, c)]), smallest)

    def test_mcv_breaks_mrv_ties(self):
        # All domains tie in size. With (0,0) assigned, cells in row 0 / col 0
        # have 3 unassigned neighbours and the rest have 4, so (1,1) wins over
        # the row-major first choice (0,1).
        solver = ac3.AC3Solver(parse_puzzle("SIZE\n3\n"))
        solver.domains = {cell: {1, 2, 3} for cell in solver.cells}
        solver.assigned = {(0, 0): 1}
        self.assertEqual(solver._select_variable(), (1, 1))

    def test_mrv_beats_degree(self):
        solver = ac3.AC3Solver(parse_puzzle("SIZE\n3\n"))
        solver.domains = {cell: {1, 2, 3} for cell in solver.cells}
        solver.assigned = {(0, 0): 1}
        solver.domains[(2, 2)] = {2, 3}
        self.assertEqual(solver._select_variable(), (2, 2))

    def test_lcv_orders_values(self):
        # (1,1) < (1,2): putting 1 in (1,1) leaves (1,2) the most options.
        solver = ac3.AC3Solver(parse_puzzle("SIZE\n3\nINEQUALITIES\n1,1,<,1,2\n"))
        solver._deadline = float("inf")
        solver.initialize()
        self.assertEqual(solver._order_values((0, 0)), [1, 2])

    def test_timeout(self):
        p = parse_puzzle(SOLVABLE_5X5)
        with self.assertRaises(SolveTimeout) as ctx:
            ac3.solve(p, timeout=0)
        self.assertEqual(ctx.exception.timeout, 0)

    def test_counters_match_callbacks(self):
        p = load_puzzle(str(TESTS_DIR / "8x8-hard.txt"))
        steps = []
        solver = ac3.AC3Solver(p, lambda r, c, v: steps.append(v))
        self.assertTrue(p.is_solution(solver.solve_with_ac3()))
        self.assertEqual(solver.assignments, sum(1 for v in steps if v))
        self.assertEqual(solver.backtracks, sum(1 for v in steps if not v))
        self.assertEqual(solver.assignments - solver.backtracks, 64 - len(p.givens))

    def test_fewer_nodes_than_basic_backtracking(self):
        for name in SOLVABLE_FIXTURES:
            with self.subTest(name):
                p = load_puzzle(str(TESTS_DIR / name))
                basic = bt.BacktrackingSolver(p)
                basic.solve_with_backtracking()
                mac = ac3.AC3Solver(p)
                mac.solve_with_ac3()
                self.assertLessEqual(mac.assignments, basic.assignments)


if __name__ == "__main__":
    unittest.main()
