"""Custom ribbon widget for Signal Analyzer."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Final

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

_ICON_ROOT: Final[Path] = Path(__file__).resolve().parents[2] / "assets" / "icons" / "fluent"
_ICON_FILES: Final[dict[str, str]] = {
    "new": "ic_fluent_document_add_24_regular.svg",
    "open": "ic_fluent_folder_open_24_regular.svg",
    "save": "ic_fluent_save_24_regular.svg",
    "grid": "ic_fluent_grid_24_regular.svg",
    "workspace": "ic_fluent_table_simple_24_regular.svg",
    "settings": "ic_fluent_settings_24_regular.svg",
    "plot": "ic_fluent_chart_multiple_24_regular.svg",
    "signal": "ic_fluent_line_24_regular.svg",
    "analysis": "ic_fluent_data_bar_horizontal_24_regular.svg",
    "undo": "ic_fluent_arrow_undo_24_regular.svg",
    "clear": "ic_fluent_eraser_24_regular.svg",
    "run": "ic_fluent_play_24_regular.svg",
    "stop": "ic_fluent_stop_24_regular.svg",
    "code": "ic_fluent_code_24_regular.svg",
    "toolbox": "ic_fluent_library_24_regular.svg",
}

_ACTION_ICON: Final[dict[str, str]] = {
    "new_session": "new",
    "open_session": "open",
    "save_session": "save",
    "display_grid": "grid",
    "toggle_signal_table": "workspace",
    "toggle_workspace": "workspace",
    "toggle_measurements": "analysis",
    "toggle_filter": "settings",
    "export_signal": "save",
    "duplicate_signal": "new",
    "delete_signal": "clear",
    "smooth": "signal",
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
    "view_time": "signal",
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
    "smooth_ma": "signal",
    "smooth_gaussian": "signal",
    "smooth_savgol": "signal",
    "smooth_lowess": "signal",
    "smooth_robust_lowess": "signal",
    "smooth_preview": "run",
    "smooth_apply": "run",
    "smooth_undo": "undo",
    "time_amplitude": "signal",
    "time_envelope": "signal",
    "time_inst_freq": "analysis",
    "time_inst_phase": "analysis",
    "trace_width": "settings",
    "trace_style": "settings",
    "trace_color": "settings",
}


def _icon_for_action(action_id: str) -> QIcon:
    key = _ACTION_ICON.get(action_id)
    if key is None:
        return QIcon()
    filename = _ICON_FILES.get(key)
    if filename is None:
        return QIcon()
    path = _ICON_ROOT / filename
    if not path.exists():
        return QIcon()
    return QIcon(str(path))


class Ribbon(QWidget):
    """MATLAB-inspired ribbon with grouped icon actions."""

    action_triggered = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sa_ribbon")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("sa_ribbon_tabs")
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
        page.setObjectName("sa_ribbon_page")

        row = QHBoxLayout(page)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(8)

        for section_idx, (section_name, buttons) in enumerate(sections):
            if section_idx > 0:
                separator = QFrame()
                separator.setObjectName("sa_ribbon_separator")
                separator.setFrameShape(QFrame.Shape.VLine)
                separator.setFrameShadow(QFrame.Shadow.Plain)
                row.addWidget(separator)

            section = QFrame()
            section.setObjectName("sa_ribbon_section")
            section_layout = QVBoxLayout(section)
            section_layout.setContentsMargins(4, 2, 4, 2)
            section_layout.setSpacing(2)

            button_row = QHBoxLayout()
            button_row.setContentsMargins(0, 0, 0, 0)
            button_row.setSpacing(2)

            for label, action_id in buttons:
                btn = QToolButton()
                btn.setObjectName("sa_ribbon_button")
                btn.setText(label)
                btn.setToolTip(label)
                btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
                btn.setIcon(_icon_for_action(action_id))
                btn.setIconSize(QSize(20, 20))
                btn.setMinimumSize(78, 62)
                btn.clicked.connect(lambda _checked=False, aid=action_id: self.action_triggered.emit(aid))
                button_row.addWidget(btn)

            footer = QLabel(section_name)
            footer.setObjectName("sa_ribbon_section_label")
            footer.setAlignment(Qt.AlignmentFlag.AlignCenter)

            section_layout.addLayout(button_row)
            section_layout.addWidget(footer)
            row.addWidget(section)

        row.addStretch(1)
        return page
