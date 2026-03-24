"""# Kronos IDE — QSS stylesheet generator from design tokens."""

from __future__ import annotations

from PyQt6.QtWidgets import QApplication

from .design_tokens import FONTS, RADIUS, SPACING, get_colors


def build_stylesheet(theme: str = "dark") -> str:
    """Build the global application stylesheet from token values."""
    c = get_colors(theme)
    f = FONTS
    r = RADIUS
    s = SPACING

    return f"""
QMainWindow, QDialog, QWidget {{
    background: {c['bg_primary']};
    color: {c['text_primary']};
    font-family: "{f['ui']}";
    font-size: {f['size_sm']}pt;
}}

QMainWindow::separator {{
    background: {c['border']};
    width: 1px;
    height: 1px;
}}

QMenuBar {{
    background: {c['ribbon_bottom']};
    border-bottom: 1px solid {c['ribbon_tab_border']};
    padding: 2px {s}px;
}}

QMenuBar::item {{
    color: {c['text_primary']};
    spacing: {s}px;
    padding: 4px {s}px;
    border-radius: {r}px;
}}

QMenuBar::item:selected {{
    background: {c['bg_elevated']};
}}

QMenu {{
    background: {c['bg_secondary']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    padding: 4px;
}}

QMenu::item {{
    padding: 6px {s}px;
    border-radius: {r}px;
}}

QMenu::item:selected {{
    background: {c['bg_elevated']};
    color: {c['accent_hover']};
}}

QToolBar {{
    background: {c['toolbar_bg']};
    border: none;
    border-bottom: 1px solid {c['border']};
    spacing: 2px;
    padding: 2px {s}px;
}}

QToolButton {{
    background: transparent;
    color: {c['text_primary']};
    border: 1px solid transparent;
    border-radius: {r}px;
    padding: 4px;
}}

QToolButton:hover {{
    background: {c['bg_elevated']};
    border-color: {c['border']};
}}

QToolButton:pressed, QToolButton:checked {{
    background: {c['bg_elevated']};
    border-color: {c['accent']};
    color: {c['accent_hover']};
}}

QTabWidget::pane {{
    border: 1px solid {c['border']};
    border-radius: {r}px;
    background: {c['bg_secondary']};
    top: -1px;
}}

QTabWidget#ribbon_tabs {{
    background: {c['ribbon_bottom']};
}}

QTabBar::tab {{
    background: {c['ribbon_tab_inactive']};
    color: {c['text_secondary']};
    border: 1px solid {c['ribbon_tab_border']};
    border-bottom: none;
    border-top-left-radius: {r}px;
    border-top-right-radius: {r}px;
    padding: 6px {s + 2}px;
    margin-right: 2px;
}}

QTabWidget#ribbon_tabs QTabBar {{
    background: {c['ribbon_top']};
}}

QTabWidget#ribbon_tabs QTabBar::tab {{
    border-top-left-radius: 0px;
    border-top-right-radius: 0px;
    min-width: 96px;
    padding: 6px 12px;
    font-weight: 600;
}}

QTabBar::tab:selected {{
    color: {c['text_primary']};
    background: {c['ribbon_tab_active']};
    border-color: {c['accent']};
}}

QTabBar::tab:hover:!selected {{
    color: {c['accent_hover']};
    background: {c['ribbon_tab_active']};
}}

QDockWidget {{
    titlebar-close-icon: none;
    titlebar-normal-icon: none;
}}

QDockWidget::title {{
    background: {c['bg_secondary']};
    color: {c['text_primary']};
    text-align: left;
    padding: 4px {s}px;
    border-bottom: 1px solid {c['border']};
}}

QTreeView, QTreeWidget, QListWidget, QTableView, QTableWidget {{
    background: {c['bg_secondary']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    border-radius: {r}px;
    alternate-background-color: {c['bg_primary']};
    selection-background-color: {c['bg_elevated']};
    selection-color: {c['text_primary']};
    padding: 2px;
}}

QHeaderView::section {{
    background: {c['bg_elevated']};
    color: {c['text_secondary']};
    border: none;
    border-right: 1px solid {c['border']};
    border-bottom: 1px solid {c['border']};
    padding: 4px;
    font-weight: 600;
}}

QTextEdit, QPlainTextEdit {{
    background: {c['bg_secondary']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    border-radius: {r}px;
    selection-background-color: {c['accent']};
    selection-color: {c['bg_primary']};
    font-family: "{f['mono']}";
    font-size: {f['size_sm']}pt;
}}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background: {c['bg_elevated']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    border-radius: {r}px;
    padding: 4px 6px;
}}

QLineEdit#path_bar {{
    background: {c['path_bar']};
    color: {c['text_secondary']};
    border: 1px solid {c['border']};
    border-radius: {r}px;
    padding: 4px 8px;
}}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {c['border_focus']};
}}

QComboBox::drop-down {{
    width: 22px;
    border: none;
}}

QPushButton {{
    background: {c['bg_elevated']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    border-radius: {r}px;
    padding: 6px {s + 2}px;
}}

QPushButton:hover {{
    border-color: {c['accent']};
    color: {c['accent_hover']};
}}

QPushButton:pressed {{
    background: {c['bg_secondary']};
}}

QScrollBar:vertical, QScrollBar:horizontal {{
    background: {c['bg_primary']};
    border: none;
    margin: 0;
}}

QScrollBar:vertical {{
    width: 10px;
}}

QScrollBar:horizontal {{
    height: 10px;
}}

QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
    background: {c['bg_elevated']};
    border-radius: {r - 2}px;
    min-height: 18px;
    min-width: 18px;
}}

QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{
    background: {c['accent']};
}}

QScrollBar::add-line, QScrollBar::sub-line,
QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
    border: none;
}}

QSplitter::handle {{
    background: {c['border']};
    margin: 0;
}}

QStatusBar {{
    background: {c['bg_secondary']};
    color: {c['text_secondary']};
    border-top: 1px solid {c['border']};
}}

QLabel#panel_header {{
    color: {c['text_secondary']};
    font-size: {f['size_sm']}pt;
    font-weight: 600;
    padding: 4px 2px;
}}

QWidget#ribbon_title_row {{
    background: {c['bg_secondary']};
    border-bottom: 1px solid {c['border']};
}}

QLabel#ribbon_title {{
    color: {c['text_primary']};
    font-size: {f['size_lg']}pt;
    font-weight: 700;
}}

QLabel#ribbon_breadcrumb {{
    color: {c['text_secondary']};
    font-size: {f['size_sm']}pt;
}}

QFrame#ribbon_group {{
    background: {c['bg_secondary']};
    border: 1px solid {c['ribbon_tab_border']};
    border-radius: 2px;
}}

QLabel#ribbon_group_title {{
    color: {c['text_secondary']};
    font-size: {f['size_sm']}pt;
    font-weight: 600;
    text-transform: uppercase;
    padding-top: 1px;
}}

QToolButton#ribbon_action_primary {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: {r}px;
    padding: 3px;
}}

QToolButton#ribbon_action_primary:hover {{
    background: {c['bg_elevated']};
    border-color: {c['accent']};
}}

QToolButton#ribbon_action_secondary {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: {r}px;
    padding: 2px 6px;
}}

QToolButton#ribbon_action_secondary:hover {{
    background: {c['bg_elevated']};
    border-color: {c['border']};
}}

QWidget#ribbon_panel {{
    background: {c['ribbon_bottom']};
    border-bottom: 1px solid {c['ribbon_tab_border']};
}}

QWidget#ribbon_quick_row {{
    background: qlineargradient(
        x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 {c['ribbon_top']},
        stop: 1 {c['ribbon_bottom']}
    );
    border-bottom: 1px solid {c['ribbon_tab_border']};
}}

QWidget#ribbon_path_row {{
    background: {c['path_bar']};
    border-top: 1px solid {c['border']};
    border-bottom: 1px solid {c['border']};
}}

QLineEdit#ribbon_path {{
    background: {c['bg_secondary']};
    color: {c['text_secondary']};
    border: 1px solid {c['border']};
    border-radius: {r}px;
    padding: 4px 8px;
}}

QToolButton#ribbon_quick_button {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: {r}px;
    padding: 2px 4px;
}}

QToolButton#ribbon_quick_button:hover {{
    background: {c['bg_elevated']};
    border-color: {c['border']};
}}

QToolButton#ribbon_path_button {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 3px;
    padding: 2px;
}}

QToolButton#ribbon_path_button:hover {{
    background: {c['bg_elevated']};
    border-color: {c['border']};
}}

QWidget#left_toolbar {{
    background: {c['toolbar_bg']};
    border-right: 1px solid {c['border']};
}}

QToolButton#left_toolbar_button {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: {r}px;
    padding: 4px;
}}

QToolButton#left_toolbar_button:checked {{
    background: {c['bg_elevated']};
    border-color: {c['accent']};
}}

QToolButton#left_toolbar_button:hover {{
    background: {c['bg_elevated']};
    border-color: {c['border']};
}}
"""


def apply_stylesheet(app: QApplication | None = None, theme: str = "dark") -> None:
    """Apply the generated stylesheet to the given QApplication."""
    target = app or QApplication.instance()
    if target is None:
        return
    target.setStyleSheet(build_stylesheet(theme))
