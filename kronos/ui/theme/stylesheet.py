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
/* ---------- Global surfaces ---------- */
QWidget {{
    background-color: {c['bg_secondary']};
    color: {c['text_primary']};
    border: none;
    font-family: "{f['ui']}";
    font-size: {f['size_sm']}pt;
}}

QMainWindow, QDialog {{
    background-color: {c['bg_primary']};
}}

QMainWindow::separator {{
    background-color: {c['border']};
    width: 1px;
    height: 1px;
}}

QFrame {{
    background-color: {c['bg_secondary']};
    border: none;
}}

QGroupBox {{
    background-color: {c['bg_elevated']};
    border: none;
    border-radius: 8px;
    margin-top: 10px;
    padding: 24px 12px 10px 12px;
    font-weight: 600;
    color: {c['text_secondary']};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    top: 8px;
    padding: 0;
    color: {c['text_secondary']};
    font-size: {max(9, f['size_sm'] - 1)}pt;
    letter-spacing: 0.8px;
}}

QLabel {{
    background-color: transparent;
}}

QLabel#panel_header {{
    color: {c['text_secondary']};
    font-size: {f['size_sm']}pt;
    font-weight: 600;
    letter-spacing: 0.8px;
}}

/* ---------- Menu ---------- */
QMenuBar {{
    background-color: {c['bg_secondary']};
    border-bottom: 1px solid {c['border']};
    padding: 2px {s}px;
}}

QMenuBar::item {{
    color: {c['text_primary']};
    padding: 4px {s}px;
    border-radius: {r}px;
    background-color: transparent;
}}

QMenuBar::item:selected {{
    background-color: rgba(255, 255, 255, 0.06);
}}

QMenu {{
    background-color: {c['bg_secondary']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    padding: 4px;
    border-radius: 8px;
}}

QMenu::item {{
    padding: 6px 10px;
    border-radius: 6px;
    background-color: transparent;
}}

QMenu::item:selected {{
    background-color: rgba(255, 255, 255, 0.08);
    color: {c['text_primary']};
}}

/* ---------- Buttons ---------- */
QToolButton, QPushButton {{
    border-radius: 6px;
    padding: 6px 12px;
    background-color: transparent;
    border: none;
    font-weight: 500;
    min-width: 0;
    color: {c['text_primary']};
}}

QToolButton[flat="true"] {{
    background-color: transparent;
    border: none;
}}

QToolButton:hover, QPushButton:hover {{
    background-color: rgba(255, 255, 255, 0.06);
}}

QToolButton:pressed, QToolButton:checked,
QPushButton:pressed, QPushButton:checked {{
    background-color: rgba(255, 255, 255, 0.10);
}}

QToolButton:disabled, QPushButton:disabled {{
    color: {c['text_secondary']};
    background-color: transparent;
}}

/* ---------- Inputs ---------- */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit, QPlainTextEdit {{
    background-color: {c['path_bar']};
    border: 1px solid {c['border']};
    border-radius: 5px;
    padding: 4px 8px;
    color: {c['text_primary']};
    selection-background-color: {c['accent_hover']};
    selection-color: {c['text_primary']};
}}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QTextEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {c['border_focus']};
    background-color: #111827;
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    background-color: #111827;
    border-left: 1px solid {c['border']};
    border-top-right-radius: 5px;
    border-bottom-right-radius: 5px;
}}

QComboBox::down-arrow {{
    image: none;
    width: 8px;
    height: 8px;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 6px solid {c['text_secondary']};
    margin-right: 6px;
}}

QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    width: 16px;
    background-color: #111827;
    border-left: 1px solid {c['border']};
}}

QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
    background-color: {c['bg_hover']};
}}

/* ---------- Trees / tables ---------- */
QTreeView, QTreeWidget, QListWidget, QTableView, QTableWidget {{
    background-color: {c['path_bar']};
    alternate-background-color: #131928;
    gridline-color: #1e2a3a;
    border: none;
    border-radius: 8px;
    padding: 2px;
    color: {c['text_primary']};
    selection-background-color: rgba(122, 162, 247, 0.18);
    selection-color: #e0e7ff;
}}

QTreeView::item:hover, QTreeWidget::item:hover,
QTableView::item:hover, QTableWidget::item:hover,
QListWidget::item:hover {{
    background-color: rgba(122, 162, 247, 0.08);
    border-radius: 4px;
}}

QTreeView::item:selected, QTreeWidget::item:selected,
QTableView::item:selected, QTableWidget::item:selected,
QListWidget::item:selected {{
    background-color: rgba(122, 162, 247, 0.18);
    color: #e0e7ff;
}}

QHeaderView::section {{
    background-color: {c['bg_elevated']};
    border: none;
    border-bottom: 1px solid {c['border']};
    padding: 5px 10px;
    font-weight: 600;
    font-size: 11px;
    letter-spacing: 0.5px;
    color: {c['text_secondary']};
}}

/* ---------- Tabs ---------- */
QTabWidget::pane {{
    border: none;
    background-color: {c['bg_secondary']};
}}

QTabBar::tab {{
    background-color: transparent;
    border: none;
    padding: 8px 16px;
    color: {c['text_secondary']};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.8px;
    border-bottom: 2px solid transparent;
}}

QTabBar::tab:selected {{
    color: {c['text_primary']};
    border-bottom: 2px solid {c['border_focus']};
}}

QTabBar::tab:hover {{
    color: #a0b0d0;
    background-color: rgba(255,255,255,0.03);
}}

/* ---------- Dock widgets ---------- */
QDockWidget {{
    background-color: {c['bg_secondary']};
    border: 1px solid {c['border']};
    border-radius: 8px;
    titlebar-close-icon: none;
    titlebar-normal-icon: none;
}}

QDockWidget::title {{
    background-color: {c['bg_elevated']};
    padding: 6px 12px;
    font-size: 11px;
    font-weight: 600;
    color: #8891aa;
    letter-spacing: 0.8px;
    border-bottom: 1px solid {c['border']};
}}

/* ---------- Scroll bars ---------- */
QScrollBar:vertical, QScrollBar:horizontal {{
    background: transparent;
    border: none;
}}

QScrollBar:vertical {{
    width: 6px;
}}

QScrollBar:horizontal {{
    height: 6px;
}}

QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
    background: {c['border']};
    border-radius: 3px;
    min-height: 30px;
    min-width: 30px;
}}

QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{
    background: #4a4a6a;
}}

QScrollBar::add-line, QScrollBar::sub-line,
QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
    border: none;
    width: 0;
    height: 0;
}}

/* ---------- Splitters / status ---------- */
QSplitter::handle {{
    background-color: {c['border']};
}}

QStatusBar {{
    background-color: {c['bg_secondary']};
    color: {c['text_secondary']};
    border-top: 1px solid {c['border']};
}}

/* ---------- Main ribbon ---------- */
QWidget#ribbon {{
    background-color: {c['bg_secondary']};
}}

QWidget#ribbon_panel {{
    background-color: {c['bg_secondary']};
}}

QWidget#ribbon_quick_row {{
    background-color: {c['bg_secondary']};
    border-bottom: 1px solid {c['border']};
}}

QWidget#ribbon_path_row {{
    background-color: {c['bg_elevated']};
    border-top: 1px solid {c['border']};
    border-bottom: 1px solid {c['border']};
}}

QLabel#ribbon_brand {{
    color: {c['text_primary']};
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.8px;
}}

QLineEdit#ribbon_path {{
    background-color: {c['path_bar']};
    border: 1px solid {c['border']};
    border-radius: 5px;
    padding: 4px 8px;
    color: {c['text_primary']};
}}

QTabWidget#ribbon_tabs {{
    background-color: {c['bg_secondary']};
}}

QTabWidget#ribbon_tabs::pane {{
    border: 1px solid {c['border']};
    border-top: none;
    background-color: {c['bg_secondary']};
}}

QFrame#ribbon_group {{
    background-color: {c['bg_elevated']};
    border: none;
    border-radius: 8px;
}}

QLabel#ribbon_group_title {{
    color: {c['text_secondary']};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.8px;
}}

QFrame#ribbon_divider {{
    background-color: {c['border']};
    min-width: 1px;
    max-width: 1px;
    margin: 8px 0;
}}

QToolButton#ribbon_action_primary,
QToolButton#ribbon_action {{
    background-color: transparent;
    border: none;
    border-radius: 6px;
    min-width: 52px;
    min-height: 56px;
    padding: 4px 4px;
}}

QToolButton#ribbon_action_compact {{
    background-color: transparent;
    border: none;
    border-radius: 6px;
    min-height: 28px;
    padding: 2px 6px;
    text-align: left;
}}

QToolButton#ribbon_quick_button,
QToolButton#ribbon_path_button,
QToolButton#ribbon_action_primary,
QToolButton#ribbon_action,
QToolButton#ribbon_action_compact {{
    color: {c['text_primary']};
}}

QToolButton#ribbon_quick_button:hover,
QToolButton#ribbon_path_button:hover,
QToolButton#ribbon_action_primary:hover,
QToolButton#ribbon_action:hover,
QToolButton#ribbon_action_compact:hover {{
    background-color: rgba(255,255,255,0.06);
}}

QToolButton#ribbon_quick_button:pressed,
QToolButton#ribbon_path_button:pressed,
QToolButton#ribbon_action_primary:pressed,
QToolButton#ribbon_action:pressed,
QToolButton#ribbon_action_compact:pressed {{
    background-color: rgba(255,255,255,0.10);
}}

/* ---------- Signal analyzer ribbon ---------- */
QWidget#sa_ribbon {{
    background-color: {c['bg_secondary']};
    border-bottom: 1px solid {c['border']};
}}

QTabWidget#sa_ribbon_tabs::pane {{
    border: 1px solid {c['border']};
    border-top: none;
    background-color: {c['bg_secondary']};
}}

QWidget#sa_ribbon_page {{
    background-color: {c['bg_secondary']};
}}

QFrame#sa_ribbon_section {{
    background-color: {c['bg_elevated']};
    border-radius: 8px;
}}

QFrame#sa_ribbon_separator {{
    background-color: {c['border']};
    min-width: 1px;
    max-width: 1px;
    margin: 8px 0;
}}

QLabel#sa_ribbon_section_label {{
    color: {c['text_secondary']};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.8px;
}}

QToolButton#sa_ribbon_button_primary {{
    background-color: transparent;
    border: none;
    border-radius: 6px;
    min-width: 52px;
    min-height: 56px;
    padding: 4px;
    color: {c['text_primary']};
}}

QToolButton#sa_ribbon_button_compact {{
    background-color: transparent;
    border: none;
    border-radius: 6px;
    min-height: 28px;
    padding: 2px 6px;
    color: {c['text_primary']};
    text-align: left;
}}

QToolButton#sa_ribbon_button_primary:hover,
QToolButton#sa_ribbon_button_compact:hover {{
    background-color: rgba(255,255,255,0.06);
}}

QToolButton#sa_ribbon_button_primary:pressed,
QToolButton#sa_ribbon_button_compact:pressed {{
    background-color: rgba(255,255,255,0.10);
}}

/* ---------- Signal analyzer panel headers ---------- */
QFrame#sa_panel_header {{
    min-height: 32px;
    background-color: {c['bg_elevated']};
    border-bottom: 1px solid {c['border']};
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
}}

QLabel#sa_panel_title {{
    color: #8891aa;
    font-size: 12px;
    font-weight: 600;
}}

QToolButton#sa_panel_icon_button {{
    background-color: transparent;
    border: none;
    border-radius: 6px;
    min-width: 24px;
    max-width: 24px;
    min-height: 24px;
    max-height: 24px;
    padding: 0;
}}

QToolButton#sa_panel_icon_button:hover {{
    background-color: {c['bg_hover']};
}}

/***** Left nav compact toolbar *****/
QWidget#left_toolbar {{
    background-color: {c['toolbar_bg']};
    border-right: 1px solid {c['border']};
}}

QToolButton#left_toolbar_button {{
    background-color: transparent;
    border: none;
    border-radius: 6px;
    padding: 4px;
}}

QToolButton#left_toolbar_button:checked,
QToolButton#left_toolbar_button:hover {{
    background-color: rgba(255,255,255,0.06);
}}
"""


def apply_stylesheet(app: QApplication | None = None, theme: str = "dark") -> None:
    """Apply the generated stylesheet to the given QApplication."""
    target = app or QApplication.instance()
    if target is None:
        return
    target.setStyleSheet(build_stylesheet(theme))
