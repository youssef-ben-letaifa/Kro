"""Step response analysis dialog."""

from __future__ import annotations

import ast

import control as ct
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class StepResponseDialog(QDialog):
    """Dialog for step response analysis."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Step Response Analyzer")
        self.resize(850, 580)
        layout = QVBoxLayout(self)

        main_layout = QHBoxLayout()
        main_layout.addWidget(self._build_controls(), 1)
        main_layout.addWidget(self._build_plot(), 2)
        layout.addLayout(main_layout)
        layout.addWidget(self._build_metrics_bar())

    def _build_controls(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        system_box = QGroupBox("System Input")
        system_layout = QFormLayout(system_box)
        self.num_edit = QLineEdit("[1]")
        self.den_edit = QLineEdit("[1, 2, 1]")
        system_layout.addRow("Numerator:", self.num_edit)
        system_layout.addRow("Denominator:", self.den_edit)
        layout.addWidget(system_box)

        step_box = QGroupBox("Step Options")
        step_layout = QFormLayout(step_box)
        self.amp_spin = QDoubleSpinBox()
        self.amp_spin.setValue(1.0)
        self.start_spin = QDoubleSpinBox()
        self.start_spin.setValue(0.0)
        self.end_spin = QDoubleSpinBox()
        self.end_spin.setValue(10.0)
        self.points_spin = QSpinBox()
        self.points_spin.setRange(100, 10000)
        self.points_spin.setValue(1000)
        step_layout.addRow("Amplitude:", self.amp_spin)
        step_layout.addRow("Start time:", self.start_spin)
        step_layout.addRow("End time:", self.end_spin)
        step_layout.addRow("Time points:", self.points_spin)
        layout.addWidget(step_box)

        options_box = QGroupBox("Display Options")
        options_layout = QVBoxLayout(options_box)
        self.annotate_check = QCheckBox("Show annotations")
        self.annotate_check.setChecked(True)
        self.grid_check = QCheckBox("Show grid")
        self.grid_check.setChecked(True)
        self.impulse_check = QCheckBox("Show impulse response")
        self.normalize_check = QCheckBox("Normalize to unit step")
        options_layout.addWidget(self.annotate_check)
        options_layout.addWidget(self.grid_check)
        options_layout.addWidget(self.impulse_check)
        options_layout.addWidget(self.normalize_check)
        layout.addWidget(options_box)

        compute_btn = QPushButton("Compute")
        compute_btn.clicked.connect(self._compute)
        layout.addWidget(compute_btn)
        layout.addStretch(1)
        return panel

    def _build_plot(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        self.figure = Figure(facecolor="#08090e")
        self.canvas = FigureCanvasQTAgg(self.figure)
        layout.addWidget(self.canvas)
        return panel

    def _build_metrics_bar(self) -> QWidget:
        bar = QWidget()
        layout = QHBoxLayout(bar)
        self.metric_labels = {
            "Rise": QLabel("Rise: —"),
            "Settle": QLabel("Settle: —"),
            "Overshoot": QLabel("Overshoot: —"),
            "SS Error": QLabel("SS Error: —"),
            "Bandwidth": QLabel("Bandwidth: —"),
        }
        for label in self.metric_labels.values():
            label.setStyleSheet("background: #13192a; border-radius: 8px; padding: 6px 10px;")
            layout.addWidget(label)
        layout.addStretch(1)
        return bar

    def _compute(self) -> None:
        try:
            num = ast.literal_eval(self.num_edit.text())
            den = ast.literal_eval(self.den_edit.text())
            sys = ct.tf(num, den)
        except (ValueError, SyntaxError):
            return

        amplitude = self.amp_spin.value()
        reference = 1.0 if self.normalize_check.isChecked() else amplitude
        if reference == 0:
            reference = 1.0
        t = np.linspace(self.start_spin.value(), self.end_spin.value(), self.points_spin.value())
        t, y = ct.step_response(sys, t)
        y = y * reference

        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.plot(t, y, color="#1a6fff", linewidth=1.5)
        if self.impulse_check.isChecked():
            t_i, y_i = ct.impulse_response(sys, t)
            ax.plot(t_i, y_i * reference, color="#e5c07b")
        if self.grid_check.isChecked():
            ax.grid(True, color="#1a1f2a", linewidth=0.5)
        ax.set_facecolor("#08090e")
        ax.tick_params(colors="#3a4050")
        for spine in ax.spines.values():
            spine.set_color("#1e2128")

        metrics = _compute_performance(t, y, reference, sys)
        if self.annotate_check.isChecked():
            ax.axvline(metrics["rise_time"], color="#98c379", linestyle="--")
            ax.axvline(metrics["settling_time"], color="#e5c07b", linestyle="--")
            ax.plot(metrics["peak_time"], metrics["peak_value"], "o", color="#e06c75")
            ax.axhline(reference, color="#6a7280", linestyle="--")

        self.metric_labels["Rise"].setText(f"Rise: {metrics['rise_time']:.2f}s")
        self.metric_labels["Settle"].setText(f"Settle: {metrics['settling_time']:.2f}s")
        self.metric_labels["Overshoot"].setText(f"Overshoot: {metrics['overshoot']:.2f}%")
        self.metric_labels["SS Error"].setText(f"SS Error: {metrics['ss_error']:.4f}")
        self.metric_labels["Bandwidth"].setText(f"Bandwidth: {metrics['bandwidth']:.2f}")
        self._apply_metric_colors(metrics)

        self.canvas.draw()

    def _apply_metric_colors(self, metrics: dict) -> None:
        _update_label_colors(self.metric_labels, metrics)


def _compute_performance(t: np.ndarray, y: np.ndarray, reference: float, sys) -> dict:
    if reference == 0:
        reference = 1.0
    rise_time = next((t[i] for i, val in enumerate(y) if val >= 0.9 * reference), t[-1])
    settle_idx = np.where(np.abs(y - reference) > 0.02 * reference)[0]
    settling_time = t[settle_idx[-1]] if len(settle_idx) else t[-1]
    overshoot = (np.max(y) - reference) / reference * 100.0
    ss_error = abs(y[-1] - reference)
    peak_idx = int(np.argmax(y))
    peak_time = float(t[peak_idx])
    peak_value = float(y[peak_idx])
    try:
        bandwidth_val = ct.bandwidth(sys)
        bandwidth = float(bandwidth_val) if bandwidth_val is not None else 0.0
    except Exception:
        bandwidth = 0.0
    return {
        "rise_time": float(rise_time),
        "settling_time": float(settling_time),
        "overshoot": float(overshoot),
        "ss_error": float(ss_error),
        "peak_time": peak_time,
        "peak_value": peak_value,
        "bandwidth": bandwidth,
    }


def _metric_color(value: float, good: float, warn: float) -> str:
    if value <= good:
        return "#98c379"
    if value <= warn:
        return "#e5c07b"
    return "#e06c75"


def _overshoot_color(value: float) -> str:
    if value < 5:
        return "#98c379"
    if value < 20:
        return "#e5c07b"
    return "#e06c75"


def _apply_label_style(label: QLabel, color: str) -> None:
    label.setStyleSheet(f"background: #13192a; border-radius: 8px; padding: 6px 10px; color: {color};")


def _update_label_colors(metric_labels: dict, metrics: dict) -> None:
    _apply_label_style(metric_labels["Overshoot"], _overshoot_color(metrics["overshoot"]))
    _apply_label_style(metric_labels["Settle"], _metric_color(metrics["settling_time"], 5.0, 10.0))
