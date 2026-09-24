"""results.csv: one row per (Puzzle, Solver), replaced when that pair is run again."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Dict, List, Union

PROJECT_DIR = Path(__file__).resolve().parent
RESULTS_PATH = PROJECT_DIR / "results.csv"

COLUMNS = ["Puzzle", "N", "Difficulty", "Solver", "Status", "Time s", "Nodes visited", "Assignments",
           "Backtracks"]
KEY = ("Puzzle", "Solver")

DIFFICULTIES = ("trivial", "easy", "medium", "tricky", "hard", "extreme")
_HEADER_RE = re.compile(r"^\s*#.*\bdifficulty:\s*(\w+)", re.IGNORECASE)

Row = Dict[str, Union[str, int, float]]


def difficulty_of(path: Union[str, Path]) -> str:
    """The '# ... difficulty: X' comment in the file, else a DIFFICULTIES word in the filename, else ''."""
    path = Path(path)
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                if not line.lstrip().startswith("#"):
                    break
                match = _HEADER_RE.match(line)
                if match:
                    return match.group(1).lower()
    except OSError:
        pass
    words = re.split(r"[^a-z]+", path.stem.lower())
    return next((w for w in DIFFICULTIES if w in words), "")


def record(row: Row, path: Union[str, Path] = RESULTS_PATH) -> None:
    """Write `row` into the CSV, replacing any existing row with the same Puzzle and Solver."""
    path = Path(path)
    new = {col: str(row.get(col, "")) for col in COLUMNS}
    rows: List[Dict[str, str]] = []
    if path.exists():
        with open(path, newline="", encoding="utf-8") as f:
            rows = [{col: r.get(col) or "" for col in COLUMNS} for r in csv.DictReader(f)]
    key = tuple(new[k] for k in KEY)
    for i, existing in enumerate(rows):
        if tuple(existing[k] for k in KEY) == key:
            rows[i] = new
            break
    else:
        rows.append(new)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
