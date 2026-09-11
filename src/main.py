from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow(Path(__file__).resolve().parents[1])
    window.resize(1280, 800)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
