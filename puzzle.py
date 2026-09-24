"""Futoshiki puzzle model and test-case file parser.

File format (rows/columns are 1-indexed):

    SIZE
    8
    GIVENS
    1,5,8            row,col,value
    INEQUALITIES
    1,2,<,1,3        cell(1,2) < cell(1,3)

Internally everything is 0-indexed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

Cell = Tuple[int, int]
Grid = List[List[int]]


class PuzzleFormatError(ValueError):
    """Raised when a puzzle file cannot be parsed."""


class SolveCancelled(Exception):
    """Raised from a solver's on_step callback when the user stops the solve."""


@dataclass
class Puzzle:
    size: int
    givens: Dict[Cell, int] = field(default_factory=dict)
    # Each pair is normalised so that value(first) < value(second).
    inequalities: List[Tuple[Cell, Cell]] = field(default_factory=list)

    def initial_grid(self) -> Grid:
        grid = [[0] * self.size for _ in range(self.size)]
        for (r, c), v in self.givens.items():
            grid[r][c] = v
        return grid

    def h_symbol(self, r: int, c: int) -> str:
        """Glyph between (r, c) and (r, c + 1): '<', '>' or ''."""
        left, right = (r, c), (r, c + 1)
        if (left, right) in self._pairs:
            return "<"
        if (right, left) in self._pairs:
            return ">"
        return ""

    def v_symbol(self, r: int, c: int) -> str:
        """Glyph between (r, c) and (r + 1, c): '^' (upper < lower), 'v' (upper > lower) or ''."""
        upper, lower = (r, c), (r + 1, c)
        if (upper, lower) in self._pairs:
            return "^"
        if (lower, upper) in self._pairs:
            return "v"
        return ""

    @property
    def _pairs(self) -> set:
        return set(self.inequalities)

    def is_solution(self, grid: Optional[Grid]) -> bool:
        n = self.size
        if grid is None or len(grid) != n or any(len(row) != n for row in grid):
            return False
        full = set(range(1, n + 1))
        if any(set(row) != full for row in grid):
            return False
        if any({grid[r][c] for r in range(n)} != full for c in range(n)):
            return False
        if any(grid[r][c] != v for (r, c), v in self.givens.items()):
            return False
        return all(grid[a[0]][a[1]] < grid[b[0]][b[1]] for a, b in self.inequalities)


def load_puzzle(path: str) -> Puzzle:
    with open(path, encoding="utf-8") as f:
        return parse_puzzle(f.read())


def parse_puzzle(text: str) -> Puzzle:
    size: Optional[int] = None
    section: Optional[str] = None
    givens: Dict[Cell, int] = {}
    inequalities: List[Tuple[Cell, Cell]] = []

    def fail(lineno: int, msg: str) -> PuzzleFormatError:
        return PuzzleFormatError(f"line {lineno}: {msg}")

    def parse_int(token: str, lineno: int, what: str) -> int:
        try:
            return int(token)
        except ValueError:
            raise fail(lineno, f"{what} must be an integer, got {token!r}") from None

    def parse_index(token: str, lineno: int, what: str) -> int:
        i = parse_int(token, lineno, what)
        if not 1 <= i <= size:
            raise fail(lineno, f"{what} {i} out of range 1..{size}")
        return i - 1

    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        header = line.upper()
        if header in ("SIZE", "GIVENS", "INEQUALITIES"):
            section = header
            continue

        if section is None:
            raise fail(lineno, f"expected a section header, got {line!r}")
        if section != "SIZE" and size is None:
            raise fail(lineno, "SIZE must come before GIVENS and INEQUALITIES")

        parts = [p.strip() for p in line.split(",")]
        if section == "SIZE":
            if size is not None:
                raise fail(lineno, "SIZE given more than once")
            size = parse_int(line, lineno, "SIZE")
            if not 2 <= size <= 9:
                raise fail(lineno, f"SIZE must be between 2 and 9, got {size}")
        elif section == "GIVENS":
            if len(parts) != 3:
                raise fail(lineno, f"expected row,col,value, got {line!r}")
            r = parse_index(parts[0], lineno, "row")
            c = parse_index(parts[1], lineno, "column")
            v = parse_int(parts[2], lineno, "value")
            if not 1 <= v <= size:
                raise fail(lineno, f"value {v} out of range 1..{size}")
            if (r, c) in givens:
                raise fail(lineno, f"cell ({r + 1},{c + 1}) given more than once")
            givens[(r, c)] = v
        else:  # INEQUALITIES
            if len(parts) != 5:
                raise fail(lineno, f"expected r1,c1,op,r2,c2, got {line!r}")
            a = (parse_index(parts[0], lineno, "row"), parse_index(parts[1], lineno, "column"))
            b = (parse_index(parts[3], lineno, "row"), parse_index(parts[4], lineno, "column"))
            op = parts[2]
            if op not in ("<", ">"):
                raise fail(lineno, f"operator must be '<' or '>', got {op!r}")
            if abs(a[0] - b[0]) + abs(a[1] - b[1]) != 1:
                raise fail(lineno, "inequality cells must be horizontally or vertically adjacent")
            pair = (a, b) if op == "<" else (b, a)
            if pair in inequalities or pair[::-1] in inequalities:
                raise fail(lineno, "duplicate or conflicting inequality")
            inequalities.append(pair)

    if size is None:
        raise PuzzleFormatError("missing SIZE section")
    return Puzzle(size=size, givens=givens, inequalities=inequalities)
