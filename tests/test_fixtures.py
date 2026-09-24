"""The labelled puzzle files in tests/ load and behave as their names claim."""

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
PROJECT_DIR = TESTS_DIR.parent
sys.path.insert(0, str(PROJECT_DIR))

from puzzle import PuzzleFormatError, load_puzzle  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "basic_backtracking_solver", PROJECT_DIR / "basic-backtracking-solver.py"
)
bt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bt)

# file -> (size, difficulty)
SOLVABLE = {
    "4x4-easy.txt": (4, "easy"),
    "6x6-easy.txt": (6, "easy"),
    "6x6-hard.txt": (6, "hard"),
    "8x8-medium.txt": (8, "medium"),
    "8x8-hard.txt": (8, "hard"),
}


class FixtureTest(unittest.TestCase):
    def test_solvable_puzzles(self):
        for name, (size, _) in SOLVABLE.items():
            with self.subTest(name):
                p = load_puzzle(str(TESTS_DIR / name))
                self.assertEqual(p.size, size)
                self.assertTrue(p.is_solution(bt.solve(p)))

    def test_difficulty_orders_backtracking_effort(self):
        def effort(name):
            solver = bt.BacktrackingSolver(load_puzzle(str(TESTS_DIR / name)))
            solver.solve_with_backtracking()
            return solver.assignments

        self.assertLess(effort("6x6-easy.txt"), effort("6x6-hard.txt"))
        self.assertLess(effort("8x8-medium.txt"), effort("8x8-hard.txt"))

    def test_unsolvable_is_well_formed_but_has_no_solution(self):
        p = load_puzzle(str(TESTS_DIR / "unsolvable-6x6.txt"))
        self.assertEqual(p.size, 6)
        self.assertIsNone(bt.solve(p))

    def test_malformed_is_rejected(self):
        with self.assertRaises(PuzzleFormatError):
            load_puzzle(str(TESTS_DIR / "malformed-4x4.txt"))

    def test_binary_file_is_rejected(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"\xff\xfe\x00SIZE")
        try:
            with self.assertRaises(PuzzleFormatError):
                load_puzzle(f.name)
        finally:
            Path(f.name).unlink()


if __name__ == "__main__":
    unittest.main()
