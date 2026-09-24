import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from puzzle import Puzzle, PuzzleFormatError, load_puzzle, parse_puzzle  # noqa: E402

SAMPLE = Path(__file__).resolve().parent / "sample-ques.txt"


class SampleFileTest(unittest.TestCase):
    def setUp(self):
        self.p = load_puzzle(str(SAMPLE))

    def test_counts(self):
        self.assertEqual(self.p.size, 8)
        self.assertEqual(len(self.p.givens), 5)
        self.assertEqual(len(self.p.inequalities), 28)

    def test_givens_are_zero_indexed(self):
        self.assertEqual(self.p.givens[(0, 4)], 8)
        self.assertEqual(self.p.givens[(7, 7)], 6)
        grid = self.p.initial_grid()
        self.assertEqual(grid[2][3], 7)
        self.assertEqual(sum(v != 0 for row in grid for v in row), 5)

    def test_glyphs_match_goobix_layout(self):
        # Horizontal: arrow_l0 -> '<', arrow_r0 -> '>'
        self.assertEqual(self.p.h_symbol(0, 1), "<")
        self.assertEqual(self.p.h_symbol(1, 4), ">")
        self.assertEqual(self.p.h_symbol(7, 5), ">")
        self.assertEqual(self.p.h_symbol(0, 0), "")
        # Vertical: arrow_d0 -> 'v' (upper > lower), arrow_u0 -> '^' (upper < lower)
        self.assertEqual(self.p.v_symbol(0, 1), "v")
        self.assertEqual(self.p.v_symbol(0, 5), "^")
        self.assertEqual(self.p.v_symbol(6, 0), "v")
        self.assertEqual(self.p.v_symbol(0, 0), "")


class ParseErrorTest(unittest.TestCase):
    def assertFormatError(self, text):
        with self.assertRaises(PuzzleFormatError):
            parse_puzzle(text)

    def test_missing_size(self):
        self.assertFormatError("GIVENS\n")

    def test_givens_before_size(self):
        self.assertFormatError("GIVENS\n1,1,1\nSIZE\n4\n")

    def test_out_of_range(self):
        self.assertFormatError("SIZE\n4\nGIVENS\n5,1,1\n")
        self.assertFormatError("SIZE\n4\nGIVENS\n1,1,5\n")

    def test_bad_operator(self):
        self.assertFormatError("SIZE\n4\nINEQUALITIES\n1,1,=,1,2\n")

    def test_non_adjacent(self):
        self.assertFormatError("SIZE\n4\nINEQUALITIES\n1,1,<,1,3\n")
        self.assertFormatError("SIZE\n4\nINEQUALITIES\n1,1,<,2,2\n")

    def test_duplicate_given(self):
        self.assertFormatError("SIZE\n4\nGIVENS\n1,1,1\n1,1,2\n")

    def test_comments_and_blank_lines(self):
        p = parse_puzzle("# demo\nsize\n\n4\ngivens\n1,1,2  # corner\n")
        self.assertEqual(p.givens, {(0, 0): 2})


class IsSolutionTest(unittest.TestCase):
    def setUp(self):
        self.p = parse_puzzle("SIZE\n4\nGIVENS\n1,1,1\nINEQUALITIES\n1,2,<,1,3\n1,4,>,2,4\n")
        self.solved = [[1, 2, 3, 4],
                       [2, 1, 4, 3],
                       [3, 4, 1, 2],
                       [4, 3, 2, 1]]

    def test_valid(self):
        self.assertTrue(self.p.is_solution(self.solved))

    def test_violates_inequality(self):
        # swap columns 2 and 3 -> row 1 becomes 1,3,2,4 (breaks col-2 < col-3)
        bad = [[row[0], row[2], row[1], row[3]] for row in self.solved]
        self.assertFalse(self.p.is_solution(bad))

    def test_violates_given_and_shape(self):
        self.assertFalse(self.p.is_solution([row[::-1] for row in self.solved]))
        self.assertFalse(self.p.is_solution(None))
        self.assertFalse(self.p.is_solution([[1]]))

    def test_not_latin(self):
        bad = [row[:] for row in self.solved]
        bad[3] = [4, 3, 2, 2]
        self.assertFalse(self.p.is_solution(bad))


if __name__ == "__main__":
    unittest.main()
