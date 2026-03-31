"""Mini overview panner with ROI controls."""

from __future__ import annotations

import numpy as np
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSlider, QVBoxLayout, QWidget
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from .signal_model import SignalRecord


class PannerWidget(QWidget):
    """Overview waveform strip with ROI sliders and range display."""

    roi_changed = pyqtSignal(float, float)
    reset_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._record: SignalRecord | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._plot_frame = QFrame()
        frame_layout = QVBoxLayout(self._plot_frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)

        self.figure = Figure(figsize=(8.0, 1.2), dpi=100)
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvas(self.figure)
        frame_layout.addWidget(self.canvas)

        self._controls = QWidget()
        controls_layout = QHBoxLayout(self._controls)
        controls_layout.setContentsMargins(8, 2, 8, 2)

        self._start_slider = QSlider(Qt.Orientation.Horizontal)
        self._end_slider = QSlider(Qt.Orientation.Horizontal)
        for slider in (self._start_slider, self._end_slider):
            slider.setRange(0, 1000)
            slider.valueChanged.connect(self._on_slider_changed)

        self._range_label = QLabel("[0.00 s - 0.00 s]")
        self._range_label.setObjectName("sa_panner_range")

        controls_layout.addWidget(QLabel("ROI"))
        controls_layout.addWidget(self._start_slider, 1)
        controls_layout.addWidget(self._end_slider, 1)
        controls_layout.addWidget(self._range_label)

        root.addWidget(self._plot_frame, 1)
        root.addWidget(self._controls)

        self.apply_dark_theme()

    def apply_dark_theme(self) -> None:
        """Apply dark colors to panner figure."""
        self.figure.patch.set_facecolor("#0d0d1a")
        self.axes.set_facecolor("#0d0d1a")
        self.axes.tick_params(colors="#a0a0b0", labelsize=7)
        for spine in self.axes.spines.values():
            spine.set_color("#2a2a4a")

    def set_signal(self, record: SignalRecord | None) -> None:
        """Set signal used for panner overview."""
        self._record = record
        self._start_slider.blockSignals(True)
        self._end_slider.blockSignals(True)
        self._start_slider.setValue(0)
        self._end_slider.setValue(1000)
        self._start_slider.blockSignals(False)
        self._end_slider.blockSignals(False)
        self._draw_overview()
        self._emit_roi()

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[override]
        """Reset ROI to full range on double-click."""
        self._start_slider.setValue(0)
        self._end_slider.setValue(1000)
        self.reset_requested.emit()
        super().mouseDoubleClickEvent(event)

    def _on_slider_changed(self, _value: int) -> None:
        if self._start_slider.value() > self._end_slider.value():
            self._start_slider.blockSignals(True)
            self._start_slider.setValue(self._end_slider.value())
            self._start_slider.blockSignals(False)
        self._draw_overview()
        self._emit_roi()

    def _emit_roi(self) -> None:
        if self._record is None:
            return
        total = self._record.duration
        if total <= 0.0:
            return

        a = self._start_slider.value() / 1000.0
        b = self._end_slider.value() / 1000.0
        start = self._record.start_time + total * min(a, b)
        end = self._record.start_time + total * max(a, b)
        self._range_label.setText(f"[{start:.3f} s - {end:.3f} s]")
        self.roi_changed.emit(start, end)

    def _draw_overview(self) -> None:
        self.axes.clear()
        self.apply_dark_theme()

        if self._record is None or self._record.data.size == 0:
            self.axes.text(0.5, 0.5, "No Signal", transform=self.axes.transAxes, ha="center", va="center", color="#a0a0b0")
            self.canvas.draw_idle()
            return

        x = self._record.start_time + np.arange(self._record.data.size) / max(self._record.fs, 1e-9)
        y = self._record.data
        self.axes.plot(x, y, color=self._record.color.name(), linewidth=0.9)

        total = self._record.duration
        start = self._record.start_time + total * (self._start_slider.value() / 1000.0)
        end = self._record.start_time + total * (self._end_slider.value() / 1000.0)
        self.axes.axvspan(min(start, end), max(start, end), color="#4cc9f0", alpha=0.2)

        self.axes.set_xticks([])
        self.axes.set_yticks([])
        self.canvas.draw_idle()
