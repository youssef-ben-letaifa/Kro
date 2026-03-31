"""Kronos IDE application entry point."""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QElapsedTimer, QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication
from kronos.ui.theme import apply_stylesheet
from kronos.ui.theme.mpl_defaults import apply_mpl_defaults


def _load_stylesheet(app: QApplication, theme: str = "dark") -> None:
    """Load and apply the theme stylesheet."""
    apply_mpl_defaults()
    apply_stylesheet(app, theme)


def main() -> None:
    """Run the Kronos application."""
    app = QApplication(sys.argv)
    app.setApplicationName("Kronos 2026.1")

    base_dir = Path(__file__).parent.parent
    icon = QIcon()
    icon_small = base_dir / "icon.ico"
    icon_large = base_dir / "bigIcon.ico"
    icon_large_alt = base_dir / "BigIcon.ico"
    if icon_small.exists():
        icon.addFile(str(icon_small))
    if icon_large.exists():
        icon.addFile(str(icon_large))
    if icon_large_alt.exists():
        icon.addFile(str(icon_large_alt))
    if not icon.isNull():
        app.setWindowIcon(icon)

    # Show splash screen
    from kronos.ui.splash import KronosSplashScreen

    splash = KronosSplashScreen()
    splash.show()
    app.processEvents()
    splash_timer = QElapsedTimer()
    splash_timer.start()

    splash.set_progress(10, "Loading stylesheet…")
    app.processEvents()
    _load_stylesheet(app)

    splash.set_progress(30, "Initializing panels…")
    app.processEvents()

    from kronos.ui.mainwindow import MainWindow

    splash.set_progress(60, "Starting console kernel…")
    app.processEvents()

    window = MainWindow()
    if not icon.isNull():
        window.setWindowIcon(icon)

    splash.set_progress(90, "Preparing workspace…")
    app.processEvents()

    def show_main_window() -> None:
        window.show()
        splash.set_progress(100, "Ready")
        splash.finish(window)

    elapsed = splash_timer.elapsed()
    min_ms = 4500
    remaining = max(0, min_ms - elapsed)
    if remaining:
        QTimer.singleShot(remaining, show_main_window)
    else:
        show_main_window()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
