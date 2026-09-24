# Futoshiki Puzzle Solver

A Tkinter desktop app that solves [Futoshiki](https://en.wikipedia.org/wiki/Futoshiki) puzzles with two
different algorithms, animates the search live on the board, and logs every run to `results.csv` so the
two approaches can be compared side by side.

A Futoshiki puzzle is an *N×N* grid (2 ≤ *N* ≤ 9). The goal is to fill every cell with a number from
1 to *N* so that:

- every row and every column holds each number exactly once (a Latin square),
- the pre-filled **givens** are kept, and
- every **inequality** sign between two adjacent cells (`<`, `>`, `^`, `v`) holds.

---

## Contents

1. [Requirements](#requirements)
2. [Quick start](#quick-start)
3. [Using the app](#using-the-app)
4. [Puzzle file format](#puzzle-file-format)
5. [The two algorithms](#the-two-algorithms)
6. [Results CSV](#results-csv)
7. [Project layout](#project-layout)

---

## Requirements

- **Python 3.10+** with **Tk 8.6 or newer**
- No third-party packages: everything uses the standard library (`requirements.txt` is empty).

> **macOS note:** Apple's bundled `/usr/bin/python3` ships Tk 8.5, which opens a blank window on current
> macOS. `main.py` detects this and relaunches itself with the first `python3.13` / `python3.12` /
> `python3.11` / `python3.10` it finds on your `PATH` that has a newer Tk. If none is found, install one:
>
> ```bash
> brew install python-tk@3.12
> ```

---

## Quick start

```bash
git clone <this-repo>
cd futoshiki-puzzle-solver

# Open the app with an empty board
python3.12 main.py

# …or open it with a puzzle already loaded
python3.12 main.py tests/6x6-tricky.txt
```

---

## Using the app

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ [Load puzzle…] 6x6-tricky.txt  Algorithm: [AC-3 Enhanced ▾]  Timeout (s): [60]  │
│                                                   [Solve]  Time: 14.669 ms      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│                        board with givens and < > ^ v signs                      │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│   AC-3 Enhanced · solved ✓ · assignments: 65 · backtracks: 29                   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

1. **Load a puzzle.** Click **Load puzzle…** (the dialog opens in `tests/`) or pass a path on the command
   line. The status bar shows the grid size and the number of givens and inequalities. A file that can't
   be parsed shows an error dialog naming the offending line.
2. **Pick an algorithm.** Choose **Basic Backtracking** or **AC-3 Enhanced** from the *Algorithm* drop-down.
3. **Set a timeout.** The *Timeout (s)* box defaults to **60 seconds**. A solve that runs longer is
   stopped and reported as *timed out*.
4. **Click Solve.** The solver runs in a background thread and the board updates live:
   - **black** digits are givens, **blue** digits are placed by the solver,
   - the **yellow** cell is the one the solver touched most recently,
   - the timer and the running assignment/backtrack counts update as it works.
5. **Stop at any time.** While a solve is running, the button reads **Stop**. A stopped run is *not*
   written to the results file.
6. **Read the outcome** in the status bar: `solved ✓`, `no solution`, `timed out after 60 s`, or an error.
   The finished solution is checked against every rule before it is accepted.

Every finished run (solved, unsolvable, timed out, or error) and every malformed file is recorded in
[`results.csv`](#results-csv).

---

## Puzzle file format

Puzzles are plain-text files with three sections. Rows and columns are **1-indexed**; `#` starts a comment.

```text
# 4x4 Futoshiki - difficulty: easy
# Unique solution. 1 given, 4 inequalities.
SIZE
4
GIVENS
4,1,2          # row 4, column 1 holds 2
INEQUALITIES
1,3,>,2,3      # cell (1,3) > cell (2,3)
2,1,<,2,2      # cell (2,1) < cell (2,2)
2,3,>,2,4
3,1,<,4,1
```

| Section        | Line format        | Rules                                                               |
|----------------|--------------------|---------------------------------------------------------------------|
| `SIZE`         | `N`                | Must come first; 2 ≤ N ≤ 9.                                         |
| `GIVENS`       | `row,col,value`    | 1 ≤ value ≤ N; each cell at most once.                              |
| `INEQUALITIES` | `r1,c1,op,r2,c2`   | `op` is `<` or `>`; the two cells must be horizontally or vertically adjacent; no duplicate or contradictory pairs. |

The optional `# … difficulty: <word>` comment on the first lines sets the *Difficulty* column in
`results.csv`. Without it, a difficulty word in the filename (`trivial`, `easy`, `medium`, `tricky`,
`hard`, `extreme`) is used instead.

### Bundled test puzzles (`tests/`)

| Size | Puzzles                                                           |
|------|-------------------------------------------------------------------|
| 4×4  | `4x4-trivial`, `4x4-easy`, `4x4-tricky`, `4x4-extreme`             |
| 6×6  | `6x6-trivial`, `6x6-easy`, `6x6-tricky`, `6x6-extreme`             |
| 8×8  | `8x8-trivial`, `8x8-easy`, `8x8-easy-2`, `8x8-tricky`, `8x8-extreme` |
| Edge cases | `unsolvable-6x6` (valid format, no solution), `malformed-4x4` (rejected by the parser) |

---

## The two algorithms

Both solvers expose the same entry point, `solve(puzzle, on_step, timeout)`, so the UI can swap them freely.
They count one **assignment** each time a value is placed on an empty cell, and one **backtrack** each
time a placement is undone.

### 1. Basic Backtracking — `basic-backtracking-solver.py`

The baseline: plain chronological depth-first search with **no** inference and **no** heuristics.

**How it works**

1. Check that the givens don't already clash (repeat in a row/column or break an inequality).
2. Walk the empty cells in **row-major order** (left to right, top to bottom).
3. For the current cell, try the values **1, 2, …, N** in ascending order.
4. Accept a value only if it doesn't repeat in its row or column, and satisfies every inequality whose
   *other* cell already holds a value.
5. If a value fits, move on to the next cell. If no value fits, undo the previous cell and try its next
   value (backtrack).

**Characteristics**

- Simple and easy to verify; row/column checks are O(1) set lookups.
- It only notices a dead end when it reaches the cell that can't be filled, so it may explore huge
  subtrees that were doomed from the start. The number of nodes grows exponentially with grid size.
- Very fast on tiny grids (little set-up cost), unusable on most 8×8 puzzles within 60 s.

### 2. AC-3 Enhanced — `ac3-enhanced-solver.py`

Backtracking that **Maintains Arc Consistency (MAC)**, plus the standard CSP ordering heuristics.

**The puzzle as a constraint-satisfaction problem**

- **Variables:** the N×N cells.
- **Domains:** `{given}` for a pre-filled cell, `{1..N}` otherwise.
- **Constraints:** every pair of cells in the same row or column must differ, and each inequality pair
  must satisfy `<`.

**How it works**

1. **Initial AC-3.** Run AC-3 over every arc `(Xi, Xj)`. `REVISE(Xi, Xj)` removes each value `x` from
   `Xi`'s domain that has no supporting value `y` in `Xj`'s domain. Whenever a domain shrinks, every
   arc pointing *into* that cell is queued again. An empty domain means the puzzle has no solution.
   On easy puzzles this step alone narrows most cells to a single value.
2. **Pick a variable** with **MRV** (Minimum Remaining Values: the smallest domain), breaking ties with
   **MCV / degree** (the most unassigned neighbours), then row-major order.
3. **Order its values** with **LCV** (Least Constraining Value): try first the value that removes the
   fewest options from neighbouring cells.
4. **Assign and propagate.** Fix the value, then run AC-3 on the arcs pointing at that cell, letting the
   removals ripple outward. If any domain becomes empty, the branch fails immediately.
5. **Backtrack cleanly.** Before each tentative assignment the solver snapshots every domain; if the
   branch fails, it restores that snapshot, undoing all of AC-3's removals in one step.

**Characteristics**

- Detects dead ends *before* committing to them, so the search tree is tiny. Most puzzles need only
  a few dozen assignments, and often zero backtracks.
- Each node is more expensive (propagation, heuristics, domain copies), so on a trivial 4×4 it can be a
  millisecond slower than basic backtracking. On anything bigger it wins by orders of magnitude.

### Side-by-side

| | Basic Backtracking | AC-3 Enhanced |
|---|---|---|
| Variable order | Fixed, row-major | MRV → MCV → row-major |
| Value order | 1…N ascending | LCV |
| Inference | None: checks only against already-filled cells | Full arc consistency before and during search |
| Dead-end detection | When a cell has no legal value | As soon as any domain becomes empty |
| Undo mechanism | Clear the cell | Restore a domain snapshot |
| Best for | Tiny grids, baseline comparisons | Everything else |

---

## Results CSV

`results.csv` is written automatically by the app (`results.py`). It holds **one row per
(Puzzle, Solver) pair**: re-running the same puzzle with the same solver **replaces** that row instead
of adding a duplicate. Stopped runs are not recorded.

### Columns

| Column | Meaning |
|---|---|
| `Puzzle` | Puzzle filename |
| `N` | Grid size |
| `Difficulty` | From the file's `difficulty:` comment or its filename; blank if neither |
| `Solver` | `Basic Backtracking` or `AC-3 Enhanced` |
| `Status` | `Solved`, `Unsolvable`, `Timed out`, `Error`, `Invalid solution`, or `Wrong format` |
| `Time s` | Wall-clock solve time in seconds (6 decimals) |
| `Nodes visited` | Search-tree nodes: one per value tried on an empty cell (equal to `Assignments`) |
| `Assignments` | Values placed by the solver (givens not counted) |
| `Backtracks` | Placements that were undone |

A malformed file produces a row with only `Puzzle` and `Status = Wrong format`.

### Current results

All runs used the default 60 s timeout.

| Puzzle | Basic: status | Basic: time | Basic: nodes | AC-3: status | AC-3: time | AC-3: nodes | AC-3: backtracks |
|---|---|---:|---:|---|---:|---:|---:|
| 4x4-trivial  | Solved | 0.22 ms | 13 | Solved | 1.49 ms | 11 | 0 |
| 4x4-easy     | Solved | 0.59 ms | 123 | Solved | 2.04 ms | 15 | 0 |
| 4x4-tricky   | Solved | 0.56 ms | 173 | Solved | 2.84 ms | 14 | 0 |
| 4x4-extreme  | Solved | 0.39 ms | 40 | Solved | 1.54 ms | 14 | 0 |
| 6x6-trivial  | Solved | 1.65 ms | 532 | Solved | 4.79 ms | 24 | 0 |
| 6x6-easy     | Solved | 160.3 ms | 128,939 | Solved | 7.51 ms | 32 | 0 |
| 6x6-tricky   | Solved | 82.1 ms | 60,040 | Solved | 14.67 ms | 65 | 29 |
| 6x6-extreme  | Solved | 181.2 ms | 143,169 | Solved | 10.48 ms | 47 | 14 |
| 8x8-trivial  | Solved | 50.2 ms | 30,982 | Solved | 9.43 ms | 40 | 1 |
| 8x8-easy     | **Timed out** | 60.0 s | 47,281,483 | Solved | 38.49 ms | 124 | 65 |
| 8x8-tricky   | not recorded | | | Solved | 24.81 ms | 83 | 24 |
| 8x8-extreme  | not recorded | | | Solved | 20.96 ms | 94 | 39 |
| unsolvable-6x6 | Unsolvable | 37.6 ms | 23,210 | not recorded | | | |
| malformed-4x4 | Wrong format | | | | | | |

### Highlights

- **AC-3 solves every recorded puzzle, all in under 40 ms.** No puzzle needed more than 124 nodes.
- **Basic backtracking breaks down at 8×8.** On `8x8-easy` it tried **47.3 million** assignments in
  60 s and still didn't finish. AC-3 solved the same puzzle in **38 ms with 124 nodes**, roughly
  380,000× fewer.
- **The search tree shrinks dramatically on 6×6.** On `6x6-easy`, basic backtracking needed
  **128,939** nodes, while AC-3 needed **32**, with zero backtracks, about 21× faster in wall-clock
  time.
- **Propagation often solves the puzzle outright.** On every 4×4 and on the trivial/easy 6×6 puzzles,
  AC-3 records **0 backtracks**: the initial AC-3 pass plus MRV leave a single choice at every step.
- **Overhead matters on tiny grids.** On all four 4×4 puzzles basic backtracking is 3–7× *faster*
  (0.2–0.6 ms vs 1.5–2.8 ms), because AC-3's set-up and per-node propagation cost more than the few
  hundred nodes the basic solver explores.
- **Difficulty labels don't map cleanly onto basic-backtracking effort.** `6x6-extreme` took about the
  same effort as `6x6-easy`, and `4x4-extreme` (40 nodes) was easier than `4x4-easy` (123). Row-major
  search is sensitive to *where* the constraints sit, not to how hard a human finds the puzzle.
- **Unsolvable puzzles are proven, not guessed.** Basic backtracking exhausted the whole search space of
  `unsolvable-6x6` in 23,210 assignments; every one was undone (assignments = backtracks).
- `8x8-easy-2` has not been run yet, and the gaps marked *not recorded* can be filled by running those
  puzzle/solver pairs in the app.

---

## Project layout

```
futoshiki-puzzle-solver/
├── main.py                        # Entry point; relaunches under a Python with Tk ≥ 8.6 if needed
├── ui.py                          # Tkinter app: board rendering, live view, threading, result logging
├── puzzle.py                      # Puzzle model, file parser, solution checker, timeout/cancel exceptions
├── basic-backtracking-solver.py   # Algorithm 1: plain backtracking
├── ac3-enhanced-solver.py         # Algorithm 2: MAC (AC-3) + MRV/MCV + LCV
├── results.py                     # Reads/writes results.csv (one row per puzzle+solver)
├── results.csv                    # Benchmark log produced by the app
├── requirements.txt               # Empty: standard library only
└── tests/                         # Puzzle files (4x4, 6x6, 8x8, unsolvable, malformed)
```

### Adding your own solver

Create a Python file that defines:

```python
def solve(puzzle, on_step=None, timeout=60.0):
    """Return a solved grid (list of lists, values 1..N) or None if unsolvable.
    Call on_step(row, col, value) on every placement (value 0 = undo).
    Raise puzzle.SolveTimeout when the timeout is exceeded."""
```

Then register it in the `SOLVERS` dictionary at the top of `ui.py`, and it appears in the *Algorithm*
drop-down.
