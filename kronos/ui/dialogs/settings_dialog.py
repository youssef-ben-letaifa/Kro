"""Preferences dialog for Kronos IDE."""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontDatabase
from PyQt6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFontComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


class SettingsDialog(QDialog):
    """Preferences dialog with category list and stacked pages."""

    settings_changed = pyqtSignal(dict)

    def __init__(self, settings_manager, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.resize(780, 540)
        self._sm = settings_manager
        self._widgets: dict[str, Any] = {}

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._category_list = QListWidget()
        self._category_list.setFixedWidth(160)
        self._category_list.setSpacing(2)
        categories = ["Editor", "Appearance", "Simulation", "Console", "General", "About"]
        for name in categories:
            item = QListWidgetItem(name)
            item.setSizeHint(item.sizeHint().__class__(160, 36))
            self._category_list.addItem(item)
        self._category_list.setCurrentRow(0)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_editor_page())
        self._stack.addWidget(self._build_appearance_page())
        self._stack.addWidget(self._build_simulation_page())
        self._stack.addWidget(self._build_console_page())
        self._stack.addWidget(self._build_general_page())
        self._stack.addWidget(self._build_about_page())

        self._category_list.currentRowChanged.connect(self._stack.setCurrentIndex)

        splitter.addWidget(self._category_list)
        splitter.addWidget(self._stack)

        buttons = QHBoxLayout()
        restore_btn = QPushButton("Restore Defaults")
        cancel_btn = QPushButton("Cancel")
        apply_btn = QPushButton("Apply")
        ok_btn = QPushButton("OK")
        restore_btn.clicked.connect(self._restore_defaults)
        cancel_btn.clicked.connect(self.reject)
        apply_btn.clicked.connect(self._apply)
        ok_btn.clicked.connect(self._ok)
        buttons.addWidget(restore_btn)
        buttons.addStretch(1)
        buttons.addWidget(cancel_btn)
        buttons.addWidget(apply_btn)
        buttons.addWidget(ok_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(splitter, 1)
        layout.addLayout(buttons)

    # ── Page builders ──

    def _scrollable_form(self) -> tuple[QScrollArea, QFormLayout]:
        """Create a scroll area wrapping a form layout."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        form = QFormLayout(container)
        form.setContentsMargins(16, 12, 16, 12)
        form.setSpacing(10)
        scroll.setWidget(container)
        return scroll, form

    def _build_editor_page(self) -> QWidget:
        scroll, form = self._scrollable_form()
        font_combo = QFontComboBox()
        font_combo.setCurrentFont(QFont(self._sm.get("editor/font_family", "JetBrains Mono")))
        self._widgets["editor/font_family"] = font_combo
        form.addRow("Font Family:", font_combo)
        self._add_description(form, "Monospace font for the code editor")

        font_size = QSpinBox()
        font_size.setRange(8, 32)
        font_size.setValue(self._sm.get("editor/font_size", 13))
        self._widgets["editor/font_size"] = font_size
        form.addRow("Font Size:", font_size)

        tab_width = QSpinBox()
        tab_width.setRange(2, 8)
        tab_width.setValue(self._sm.get("editor/tab_width", 4))
        self._widgets["editor/tab_width"] = tab_width
        form.addRow("Tab Width:", tab_width)

        for key, label in [
            ("editor/auto_indent", "Auto Indent"),
            ("editor/line_numbers", "Show Line Numbers"),
            ("editor/highlight_line", "Highlight Current Line"),
            ("editor/autocomplete", "Enable Autocomplete"),
            ("editor/word_wrap", "Word Wrap"),
            ("editor/show_whitespace", "Show Whitespace"),
        ]:
            cb = QCheckBox()
            cb.setChecked(bool(self._sm.get(key, True)))
            self._widgets[key] = cb
            form.addRow(f"{label}:", cb)

        return scroll

    def _build_appearance_page(self) -> QWidget:
        scroll, form = self._scrollable_form()

        theme_combo = QComboBox()
        theme_combo.addItems(["catppuccin_mocha (dark)"])
        theme_combo.setCurrentText("catppuccin_mocha (dark)")
        theme_combo.setEnabled(False)
        self._widgets["appearance/theme"] = theme_combo
        form.addRow("Theme:", theme_combo)
        self._add_description(form, "Kronos now uses Catppuccin Mocha as the single global theme.")

        accent_btn = QPushButton()
        accent_color = self._sm.get("appearance/accent_color", "#89b4fa")
        accent_btn.setStyleSheet(
            f"background: {accent_color}; border: 1px solid #45475a; "
            f"border-radius: 4px; min-width: 60px; min-height: 24px;"
        )
        accent_btn.setProperty("color_value", accent_color)
        accent_btn.clicked.connect(lambda: self._pick_color(accent_btn))
        self._widgets["appearance/accent_color"] = accent_btn
        form.addRow("Accent Color:", accent_btn)
        self._add_description(form, "Primary accent color used across the UI")

        ui_font = QFontComboBox()
        ui_font.setCurrentFont(QFont(self._sm.get("appearance/font_ui", "Noto Sans")))
        self._widgets["appearance/font_ui"] = ui_font
        form.addRow("UI Font:", ui_font)

        ui_size = QSpinBox()
        ui_size.setRange(8, 20)
        ui_size.setValue(self._sm.get("appearance/font_ui_size", 12))
        self._widgets["appearance/font_ui_size"] = ui_size
        form.addRow("UI Font Size:", ui_size)

        return scroll

    def _build_simulation_page(self) -> QWidget:
        scroll, form = self._scrollable_form()

        t_end = QDoubleSpinBox()
        t_end.setRange(0.1, 1000.0)
        t_end.setValue(self._sm.get("simulation/default_t_end", 10.0))
        self._widgets["simulation/default_t_end"] = t_end
        form.addRow("Default t_end:", t_end)

        dt = QDoubleSpinBox()
        dt.setRange(0.001, 1.0)
        dt.setDecimals(3)
        dt.setValue(self._sm.get("simulation/default_dt", 0.01))
        self._widgets["simulation/default_dt"] = dt
        form.addRow("Default dt:", dt)

        auto_plot = QCheckBox()
        auto_plot.setChecked(bool(self._sm.get("simulation/auto_plot", True)))
        self._widgets["simulation/auto_plot"] = auto_plot
        form.addRow("Auto Plot:", auto_plot)

        max_time = QDoubleSpinBox()
        max_time.setRange(1.0, 3600.0)
        max_time.setValue(self._sm.get("simulation/max_sim_time", 300.0))
        self._widgets["simulation/max_sim_time"] = max_time
        form.addRow("Max Sim Time (s):", max_time)
        self._add_description(form, "Maximum allowed simulation duration")

        return scroll

    def _build_console_page(self) -> QWidget:
        scroll, form = self._scrollable_form()

        style_combo = QComboBox()
        style_combo.addItems(["monokai", "native", "fruity", "vim", "emacs"])
        style_combo.setCurrentText(self._sm.get("console/syntax_style", "monokai"))
        self._widgets["console/syntax_style"] = style_combo
        form.addRow("Syntax Style:", style_combo)

        font_size = QSpinBox()
        font_size.setRange(8, 24)
        font_size.setValue(self._sm.get("console/font_size", 12))
        self._widgets["console/font_size"] = font_size
        form.addRow("Font Size:", font_size)

        max_hist = QSpinBox()
        max_hist.setRange(100, 10000)
        max_hist.setValue(self._sm.get("console/max_history", 1000))
        self._widgets["console/max_history"] = max_hist
        form.addRow("Max History:", max_hist)

        return scroll

    def _build_general_page(self) -> QWidget:
        scroll, form = self._scrollable_form()

        autosave = QCheckBox()
        autosave.setChecked(bool(self._sm.get("general/autosave", True)))
        self._widgets["general/autosave"] = autosave
        form.addRow("Autosave:", autosave)

        interval = QSpinBox()
        interval.setRange(10, 600)
        interval.setSuffix(" sec")
        interval.setValue(self._sm.get("general/autosave_interval", 60))
        self._widgets["general/autosave_interval"] = interval
        form.addRow("Autosave Interval:", interval)

        restore = QCheckBox()
        restore.setChecked(bool(self._sm.get("general/restore_session", True)))
        self._widgets["general/restore_session"] = restore
        form.addRow("Restore Session:", restore)
        self._add_description(form, "Reopen files and layout from last session on startup")

        updates = QCheckBox()
        updates.setChecked(bool(self._sm.get("general/check_updates", True)))
        self._widgets["general/check_updates"] = updates
        form.addRow("Check for Updates:", updates)

        return scroll

    def _build_about_page(self) -> QWidget:
        scroll, form = self._scrollable_form()
        import sys
        from PyQt6.QtCore import PYQT_VERSION_STR

        info_lines = [
            ("Application:", "Kronos 2026.1"),
            ("Version:", "2026.1"),
            ("Author:", "Youssef Ben Letaifa"),
            ("Organization:", "Intelligent Systems"),
            ("License:", "MIT"),
            ("Python:", sys.version.split()[0]),
            ("PyQt6:", PYQT_VERSION_STR),
        ]
        for label_text, value in info_lines:
            form.addRow(label_text, QLabel(value))
        return scroll

    # ── Helpers ──

    @staticmethod
    def _add_description(form: QFormLayout, text: str) -> None:
        desc = QLabel(text)
        desc.setStyleSheet("color: #a6adc8; font-size: 10px;")
        form.addRow("", desc)

    @staticmethod
    def _pick_color(button: QPushButton) -> None:
        current = QColor(button.property("color_value") or "#89b4fa")
        color = QColorDialog.getColor(current, button, "Select Accent Color")
        if color.isValid():
            button.setProperty("color_value", color.name())
            button.setStyleSheet(
                f"background: {color.name()}; border: 1px solid #45475a; "
                f"border-radius: 4px; min-width: 60px; min-height: 24px;"
            )

    def _collect(self) -> dict[str, Any]:
        """Gather current widget values into a settings dict."""
        result: dict[str, Any] = {}
        for key, widget in self._widgets.items():
            if isinstance(widget, QCheckBox):
                result[key] = widget.isChecked()
            elif isinstance(widget, QSpinBox):
                result[key] = widget.value()
            elif isinstance(widget, QDoubleSpinBox):
                result[key] = widget.value()
            elif isinstance(widget, QComboBox):
                result[key] = widget.currentText()
            elif isinstance(widget, QFontComboBox):
                result[key] = widget.currentFont().family()
            elif isinstance(widget, QPushButton):
                result[key] = widget.property("color_value") or ""
        return result

    def _apply(self) -> None:
        values = self._collect()
        for key, value in values.items():
            self._sm.set(key, value)
        self.settings_changed.emit(values)

    def _ok(self) -> None:
        self._apply()
        self.accept()

    def _restore_defaults(self) -> None:
        self._sm.reset_to_defaults()
        self.settings_changed.emit({})
        self.accept()
