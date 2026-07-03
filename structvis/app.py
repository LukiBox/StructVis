"""StructVis application entry point."""
from __future__ import annotations

import sys


def main():
    from PySide6.QtWidgets import QApplication
    from structvis.ui import theme
    from structvis.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("StructVis")
    theme.apply(app)          # light or dark, from the saved setting

    win = MainWindow()
    win.show()
    win.show_welcome()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
