"""# Kronos IDE — Fluent SVG icon loader with tinting support."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Final

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap

try:
    from PyQt6.QtSvg import QSvgRenderer
except Exception:  # pragma: no cover
    QSvgRenderer = None


ICON_ROOT: Final[Path] = (
    Path(__file__).resolve().parents[2] / "assets" / "icons" / "fluent"
)

ICON_FILES: Final[dict[str, str]] = {
    # Ribbon + quick access
    "new": "ic_fluent_document_add_24_regular.svg",
    "open": "ic_fluent_folder_open_24_regular.svg",
    "save": "ic_fluent_save_24_regular.svg",
    "undo": "ic_fluent_arrow_undo_24_regular.svg",
    "redo": "ic_fluent_arrow_redo_24_regular.svg",
    "search": "ic_fluent_search_24_regular.svg",
    "run": "ic_fluent_play_24_regular.svg",
    "stop": "ic_fluent_stop_24_regular.svg",
    "restart": "ic_fluent_arrow_clockwise_24_regular.svg",
    "run_time": "ic_fluent_timer_24_regular.svg",
    "run_section": "ic_fluent_play_circle_24_regular.svg",
    "clear": "ic_fluent_eraser_24_regular.svg",
    "settings": "ic_fluent_settings_24_regular.svg",
    "help": "ic_fluent_question_circle_24_regular.svg",
    "theme_dark": "ic_fluent_weather_moon_24_regular.svg",
    "theme_light": "ic_fluent_weather_sunny_24_regular.svg",
    # Analysis + tools
    "bode": "ic_fluent_chart_multiple_24_regular.svg",
    "step": "ic_fluent_line_24_regular.svg",
    "root": "ic_fluent_branch_24_regular.svg",
    "pid": "ic_fluent_settings_24_regular.svg",
    "lqr": "ic_fluent_math_formula_24_regular.svg",
    "math_formula": "ic_fluent_math_formula_24_regular.svg",
    "analysis": "ic_fluent_chart_multiple_24_regular.svg",
    "plot": "ic_fluent_line_24_regular.svg",
    "simulink": "ic_fluent_diagram_24_regular.svg",
    "apps": "ic_fluent_apps_24_regular.svg",
    "layout": "ic_fluent_grid_24_regular.svg",
    "console": "ic_fluent_prompt_24_regular.svg",
    # Left navigation
    "files": "ic_fluent_folder_24_regular.svg",
    "workspace": "ic_fluent_table_simple_24_regular.svg",
    "blocks": "ic_fluent_cube_24_regular.svg",
    "snippets": "ic_fluent_code_24_regular.svg",
    "database": "ic_fluent_database_24_regular.svg",
    # Simulink window extras
    "library": "ic_fluent_library_24_regular.svg",
    "log": "ic_fluent_list_24_regular.svg",
    "viewer": "ic_fluent_eye_24_regular.svg",
    "validate": "ic_fluent_checkmark_circle_24_regular.svg",
    "arrange": "ic_fluent_grid_24_regular.svg",
    "fit": "ic_fluent_full_screen_maximize_24_regular.svg",
    "data_inspector": "ic_fluent_data_bar_horizontal_24_regular.svg",
    "print": "ic_fluent_print_24_regular.svg",
    "back": "ic_fluent_arrow_left_20_regular.svg",
    "forward": "ic_fluent_arrow_right_20_regular.svg",
    "up": "ic_fluent_arrow_up_20_regular.svg",
    "home": "ic_fluent_home_20_regular.svg",
    "folder_up": "ic_fluent_folder_arrow_up_20_regular.svg",
}


def _load_svg(path: Path, size: int, color: str | None) -> QIcon:
    if QSvgRenderer is None:
        return QIcon(str(path))

    renderer = QSvgRenderer(str(path))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter, QRectF(0, 0, float(size), float(size)))

    if color:
        # PyQt6 enum location differs across builds.
        mode = getattr(QPainter, "CompositionMode_SourceIn", None)
        if mode is None:
            mode = QPainter.CompositionMode.CompositionMode_SourceIn
        painter.setCompositionMode(mode)
        painter.fillRect(pixmap.rect(), QColor(color))

    painter.end()
    return QIcon(pixmap)


@lru_cache(maxsize=512)
def icon_for(name: str, size: int = 24, color: str | None = None) -> QIcon:
    """Return a tinted Fluent SVG icon for the given name."""
    filename = ICON_FILES.get(name)
    if not filename:
        return QIcon()
    path = ICON_ROOT / filename
    if not path.exists():
        return QIcon()
    return _load_svg(path, size, color)


__all__ = ["ICON_FILES", "ICON_ROOT", "icon_for"]
