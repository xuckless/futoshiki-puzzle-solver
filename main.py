"""Entry point: python3 main.py [puzzle-file]"""

import sys
import tkinter as tk

from ui import FutoshikiApp


def main() -> None:
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
