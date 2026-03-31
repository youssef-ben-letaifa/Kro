"""Custom ribbon widget for Signal Analyzer."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from kronos.ui.theme.fluent_icons import icon_for

_ACTION_ICON: Final[dict[str, str]] = {
    "new_session": "new",
    "open_session": "open",
    "save_session": "save",
    "display_grid": "layout",
    "toggle_signal_table": "workspace",
    "toggle_workspace": "workspace",
    "toggle_measurements": "analysis",
    "toggle_filter": "settings",
    "export_signal": "save",
    "duplicate_signal": "new",
    "delete_signal": "clear",
    "smooth": "plot",
    "quick_lowpass": "analysis",
    "quick_highpass": "analysis",
    "quick_bandpass": "analysis",
    "generate_script": "code",
    "generate_function": "code",
    "preferences": "settings",
    "clear_display": "clear",
    "legend_mode": "plot",
    "link_time": "analysis",
    "link_frequency": "analysis",
    "cursor_mode": "analysis",
    "snap_to_data": "analysis",
    "zoom_in": "analysis",
    "zoom_out": "analysis",
    "pan": "analysis",
    "reset_view": "undo",
    "view_time": "plot",
    "view_spectrum": "plot",
    "view_spectrogram": "plot",
    "view_scalogram": "plot",
    "view_persistence": "plot",
    "measure_set_roi": "analysis",
    "measure_clear_roi": "clear",
    "est_power": "plot",
    "est_psd": "plot",
    "est_specgram": "plot",
    "est_persistence": "plot",
    "display_db": "analysis",
    "display_norm": "analysis",
    "display_two_sided": "analysis",
    "find_peaks": "analysis",
    "label_peaks": "analysis",
    "measure_select_all": "analysis",
    "measure_deselect_all": "clear",
    "measure_export_csv": "save",
    "smooth_ma": "plot",
    "smooth_gaussian": "plot",
    "smooth_savgol": "plot",
    "smooth_lowess": "plot",
    "smooth_robust_lowess": "plot",
    "smooth_preview": "run",
    "smooth_apply": "run",
    "smooth_undo": "undo",
    "time_amplitude": "plot",
    "time_envelope": "plot",
    "time_inst_freq": "analysis",
    "time_inst_phase": "analysis",
    "trace_width": "settings",
    "trace_style": "settings",
    "trace_color": "settings",
}


def _icon_for_action(action_id: str):
    key = _ACTION_ICON.get(action_id)
    if key is None:
        return icon_for("analysis", size=20, color="#a6adc8")
    return icon_for(key, size=20, color="#cdd6f4")


class _RibbonSection(QFrame):
    """Word-like ribbon section with one hero command and compact actions."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ribbon_group")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 4)
        layout.setSpacing(2)

        self.grid = QGridLayout()
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(4)
        self.grid.setVerticalSpacing(4)
        layout.addLayout(self.grid, 1)
        self._has_primary = False
        self._secondary_index = 0
        self._max_col = 0

        footer = QLabel(title)
        footer.setObjectName("ribbon_group_title")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(footer)

    @staticmethod
    def _compactify(button: QToolButton) -> None:
        button.setObjectName("ribbon_action_compact")
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setIconSize(QSize(16, 16))
        button.setMinimumSize(116, 28)
        button.setMaximumHeight(28)

    def add_button(self, button: QToolButton) -> None:
        if button.objectName() == "ribbon_action_primary" and not self._has_primary:
            self.grid.addWidget(button, 0, 0, 2, 1)
            self._has_primary = True
            self._max_col = max(self._max_col, 0)
            return

        if button.objectName() == "ribbon_action_primary":
            self._compactify(button)

        start_col = 1 if self._has_primary else 0
        row = self._secondary_index % 2
        col = start_col + (self._secondary_index // 2)
        self.grid.addWidget(button, row, col)
        self._secondary_index += 1
        self._max_col = max(self._max_col, col)

    def finalize(self) -> None:
        self.grid.setColumnStretch(self._max_col + 1, 1)


class Ribbon(QWidget):
    """MATLAB-inspired ribbon with grouped icon actions."""

    action_triggered = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ribbon")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("ribbon_tabs")
        self.tabs.setDocumentMode(True)
        bar = self.tabs.tabBar()
        if bar is not None:
            bar.setExpanding(False)

        self._build_tabs()
        root.addWidget(self.tabs)

    def _build_tabs(self) -> None:
        self.tabs.addTab(self._build_analyzer_tab(), "ANALYZER")
        self.tabs.addTab(self._build_display_tab(), "DISPLAY")
        self.tabs.addTab(self._build_time_tab(), "TIME")
        self.tabs.addTab(self._build_spectrum_tab(), "SPECTRUM")
        self.tabs.addTab(self._build_measurements_tab(), "MEASUREMENTS")
        self.tabs.addTab(self._build_smooth_tab(), "SMOOTH")

    def _build_analyzer_tab(self) -> QWidget:
        sections = [
            ("FILE", [("New", "new_session"), ("Open", "open_session"), ("Save", "save_session")]),
            (
                "LAYOUT",
                [
                    ("Display Grid", "display_grid"),
                    ("Signal Table", "toggle_signal_table"),
                    ("Workspace Browser", "toggle_workspace"),
                    ("Measurements", "toggle_measurements"),
                    ("Filter Designer", "toggle_filter"),
                ],
            ),
            ("SIGNAL", [("Export", "export_signal"), ("Duplicate", "duplicate_signal"), ("Delete", "delete_signal")]),
            (
                "PREPROCESSING",
                [
                    ("Smooth", "smooth"),
                    ("Lowpass", "quick_lowpass"),
                    ("Highpass", "quick_highpass"),
                    ("Bandpass", "quick_bandpass"),
                ],
            ),
            ("OPTIONS", [("Generate Script", "generate_script"), ("Preferences", "preferences")]),
        ]
        return self._build_tab(sections)

    def _build_display_tab(self) -> QWidget:
        sections = [
            ("DISPLAY OPTIONS", [("Clear", "clear_display"), ("Legend", "legend_mode"), ("Link Time", "link_time")]),
            ("MEASURE", [("Data Cursors", "cursor_mode"), ("Snap", "snap_to_data")]),
            ("ZOOM & PAN", [("Zoom In", "zoom_in"), ("Zoom Out", "zoom_out"), ("Pan", "pan"), ("Reset", "reset_view")]),
            (
                "VIEWS",
                [
                    ("Time", "view_time"),
                    ("Spectrum", "view_spectrum"),
                    ("Spectrogram", "view_spectrogram"),
                    ("Scalogram", "view_scalogram"),
                    ("Persistence", "view_persistence"),
                ],
            ),
            ("ROI", [("Set ROI", "measure_set_roi"), ("Clear ROI", "measure_clear_roi")]),
        ]
        return self._build_tab(sections)

    def _build_time_tab(self) -> QWidget:
        sections = [
            ("SIGNAL", [("Amplitude", "time_amplitude"), ("Envelope", "time_envelope"), ("Inst. Freq", "time_inst_freq"), ("Inst. Phase", "time_inst_phase")]),
            ("TRACE", [("Line Width", "trace_width"), ("Style", "trace_style"), ("Color", "trace_color")]),
        ]
        return self._build_tab(sections)

    def _build_spectrum_tab(self) -> QWidget:
        sections = [
            ("ESTIMATION", [("Power Spectrum", "est_power"), ("PSD", "est_psd"), ("Spectrogram", "est_specgram"), ("Persistence", "est_persistence")]),
            ("DISPLAY", [("dB Scale", "display_db"), ("Normalized", "display_norm"), ("Two-sided", "display_two_sided")]),
            ("PEAK FINDER", [("Find Peaks", "find_peaks"), ("Label Peaks", "label_peaks")]),
        ]
        return self._build_tab(sections)

    def _build_measurements_tab(self) -> QWidget:
        sections = [
            ("STATISTICS", [("Select All", "measure_select_all"), ("Deselect", "measure_deselect_all")]),
            ("ROI", [("Set ROI", "measure_set_roi"), ("Clear ROI", "measure_clear_roi"), ("Export CSV", "measure_export_csv")]),
        ]
        return self._build_tab(sections)

    def _build_smooth_tab(self) -> QWidget:
        sections = [
            ("METHOD", [("Moving Avg", "smooth_ma"), ("Gaussian", "smooth_gaussian"), ("Savgol", "smooth_savgol"), ("Lowess", "smooth_lowess"), ("Robust", "smooth_robust_lowess")]),
            ("ACTION", [("Preview", "smooth_preview"), ("Apply", "smooth_apply"), ("Undo", "smooth_undo")]),
        ]
        return self._build_tab(sections)

    def _build_tab(self, sections: Iterable[tuple[str, list[tuple[str, str]]]]) -> QWidget:
        page = QWidget()
        page.setObjectName("ribbon_panel")
        sections_list = list(sections)

        row = QHBoxLayout(page)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(6)

        for idx_section, (section_name, buttons) in enumerate(sections_list):
            section = _RibbonSection(section_name, page)

            for idx, (label, action_id) in enumerate(buttons):
                btn = QToolButton()
                btn.setObjectName("ribbon_action_primary" if idx == 0 else "ribbon_action_compact")
                btn.setText(label)
                btn.setToolTip(label)
                btn.setToolButtonStyle(
                    Qt.ToolButtonStyle.ToolButtonTextUnderIcon if idx == 0 else Qt.ToolButtonStyle.ToolButtonTextBesideIcon
                )
                btn.setIcon(_icon_for_action(action_id))
                btn.setIconSize(QSize(22 if idx == 0 else 16, 22 if idx == 0 else 16))
                btn.setMinimumSize(52 if idx == 0 else 116, 56 if idx == 0 else 28)
                btn.clicked.connect(lambda _checked=False, aid=action_id: self.action_triggered.emit(aid))
                section.add_button(btn)

            section.finalize()
            row.addWidget(section)
            if idx_section < len(sections_list) - 1:
                sep = QFrame(page)
                sep.setObjectName("ribbon_divider")
                sep.setFrameShape(QFrame.Shape.VLine)
                sep.setFrameShadow(QFrame.Shadow.Plain)
                row.addWidget(sep)

        row.addStretch(1)
        return page
