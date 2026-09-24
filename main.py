"""Entry point: python3 main.py [puzzle-file]"""

import os
import shutil
import subprocess
import sys
import tkinter as tk

from ui import FutoshikiApp

# macOS's bundled /usr/bin/python3 ships Tk 8.5, which opens blank windows on current macOS.
MIN_TK_VERSION = 8.6
CANDIDATE_PYTHONS = ("python3.13", "python3.12", "python3.11", "python3.10", "python3")
RELAUNCH_ENV = "FUTOSHIKI_RELAUNCHED"


def find_python_with_modern_tk():
    """Return the path of another Python on PATH whose Tk is >= MIN_TK_VERSION, or None."""
    probe = f"import sys, tkinter; sys.exit(0 if tkinter.TkVersion >= {MIN_TK_VERSION} else 1)"
    current = os.path.realpath(sys.executable)
    for name in CANDIDATE_PYTHONS:
        path = shutil.which(name)
        if not path or os.path.realpath(path) == current:
            continue
        try:
            ok = subprocess.run([path, "-c", probe], capture_output=True, timeout=15).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            continue
        if ok:
            return path
    return None


def ensure_modern_tk() -> None:
    """Re-run this script under a Python with a working Tk if the current one is too old."""
    if tk.TkVersion >= MIN_TK_VERSION or os.environ.get(RELAUNCH_ENV):
        return
    python = find_python_with_modern_tk()
    if python is None:
        sys.exit(
            f"This Python ({sys.executable}) has Tk {tk.TkVersion}, which renders blank windows.\n"
            "Install a Python with Tk 8.6+, e.g. `brew install python-tk@3.12`, then run:\n"
            "    python3.12 main.py"
        )
    print(f"Tk {tk.TkVersion} is too old; relaunching with {python}", file=sys.stderr)
    os.environ[RELAUNCH_ENV] = "1"
    os.execv(python, [python, os.path.abspath(__file__), *sys.argv[1:]])


def main() -> None:
    ensure_modern_tk()
    root = tk.Tk()
    root.title("Futoshiki Solver")
    root.configure(bg="#ffffff")
    root.resizable(False, False)
    app = FutoshikiApp(root)
    app.pack(fill="both", expand=True)
    if len(sys.argv) > 1:
        app.load_file(sys.argv[1])
    root.mainloop()


if __name__ == "__main__":
    main()
