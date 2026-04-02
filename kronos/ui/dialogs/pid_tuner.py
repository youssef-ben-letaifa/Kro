"""PID tuner dialog."""

from __future__ import annotations

import ast
import json

import control as ct
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QDoubleSpinBox,
    QVBoxLayout,
    QWidget,
    QTableWidget,
    QTableWidgetItem,
)
from kronos.engine.kernel_message_router import KernelMessageRouter


class PIDTunerDialog(QDialog):
    """Interactive PID tuning dialog."""

    code_insert_requested = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("PID Tuner")
        self.resize(900, 650)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._update_plot)
        self._kernel_client_getter = None
        self._message_router_getter = None

        layout = QHBoxLayout(self)
        layout.addWidget(self._build_controls(), 1)
        layout.addWidget(self._build_plot(), 2)
        layout.addWidget(self._build_metrics(), 1)
        self._update_plot()

    def _build_controls(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        plant_box = QGroupBox("Plant G(s)")
        plant_layout = QFormLayout(plant_box)
        self.num_edit = QLineEdit("[1]")
        self.den_edit = QLineEdit("[1, 2, 1]")
        self.load_btn = QPushButton("Load from workspace")
        self.load_btn.clicked.connect(self._load_from_workspace)
        plant_layout.addRow("Numerator:", self.num_edit)
        plant_layout.addRow("Denominator:", self.den_edit)
        plant_layout.addRow(self.load_btn)

        pid_box = QGroupBox("PID Gains")
        pid_layout = QFormLayout(pid_box)
        self.kp_slider, self.kp_spin = self._make_gain_controls(0.01, 20.0, 1.0)
        self.ki_slider, self.ki_spin = self._make_gain_controls(0.0, 10.0, 0.0)
        self.kd_slider, self.kd_spin = self._make_gain_controls(0.0, 5.0, 0.0)
        pid_layout.addRow("Kp:", self._wrap_slider_spin(self.kp_slider, self.kp_spin))
        pid_layout.addRow("Ki:", self._wrap_slider_spin(self.ki_slider, self.ki_spin))
        pid_layout.addRow("Kd:", self._wrap_slider_spin(self.kd_slider, self.kd_spin))

        sim_box = QGroupBox("Simulation")
        sim_layout = QFormLayout(sim_box)
        self.t_end = QDoubleSpinBox()
        self.t_end.setRange(1.0, 100.0)
        self.t_end.setValue(20.0)
        self.reference = QDoubleSpinBox()
        self.reference.setRange(0.1, 10.0)
        self.reference.setValue(1.0)
        self.t_end.valueChanged.connect(self._schedule_update)
        self.reference.valueChanged.connect(self._schedule_update)
        sim_layout.addRow("t_end:", self.t_end)
        sim_layout.addRow("Reference:", self.reference)

        auto_btn = QPushButton("Auto-Tune")
        reset_btn = QPushButton("Reset")
        auto_btn.clicked.connect(self._auto_tune)
        reset_btn.clicked.connect(self._reset_gains)

        layout.addWidget(plant_box)
        layout.addWidget(pid_box)
        layout.addWidget(sim_box)
        layout.addWidget(auto_btn)
        layout.addWidget(reset_btn)
        layout.addStretch(1)

        return panel

    def _build_plot(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        self.figure = Figure(facecolor="#08090e")
        self.canvas = FigureCanvasQTAgg(self.figure)
        layout.addWidget(self.canvas)
        return panel

    def _build_metrics(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        self.metrics = {
            "Rise time": QLabel("—"),
            "Settling time": QLabel("—"),
            "Overshoot": QLabel("—"),
            "SS error": QLabel("—"),
            "Peak time": QLabel("—"),
        }
        for name, label in self.metrics.items():
            row = QHBoxLayout()
            row.addWidget(QLabel(name))
            row.addStretch(1)
            row.addWidget(label)
            layout.addLayout(row)

        self.poles_label = QLabel("Closed-loop Poles")
        layout.addWidget(self.poles_label)
        self.poles_table = QTableWidget(0, 2)
        self.poles_table.setHorizontalHeaderLabels(["Pole", "Stable?"])
        layout.addWidget(self.poles_table)

        copy_btn = QPushButton("Copy gains to editor")
        copy_btn.clicked.connect(self._emit_code)
        layout.addWidget(copy_btn)
        layout.addStretch(1)
        return panel

    def set_kernel_client_getter(self, getter) -> None:
        """Attach kernel client getter for workspace loading."""
        self._kernel_client_getter = getter

    def set_message_router_getter(self, getter) -> None:
        """Attach kernel message router getter for workspace loading."""
        self._message_router_getter = getter

    def _load_from_workspace(self) -> None:
        kernel = self._kernel_client_getter() if self._kernel_client_getter else None
        if kernel is None:
            return
        router = self._message_router_getter() if self._message_router_getter else None
        if router is None or not isinstance(router, KernelMessageRouter):
            return
        code = (
            "import json, control as ct\n"
            "payload = {}\n"
            "for name, obj in globals().items():\n"
            "    if isinstance(obj, ct.TransferFunction):\n"
            "        num, den = ct.tfdata(obj)\n"
            "        payload = {'num': num[0][0].tolist(), 'den': den[0][0].tolist()}\n"
            "        break\n"
            "print(json.dumps(payload))\n"
        )
        data = router.request_json(kernel, code, timeout_ms=2000)
        if not isinstance(data, dict):
            return
        if "num" in data and "den" in data:
            self.num_edit.setText(str(data["num"]))
            self.den_edit.setText(str(data["den"]))
            self._schedule_update()

    @staticmethod
    def _wrap_slider_spin(slider: QSlider, spin: QDoubleSpinBox) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(slider)
        layout.addWidget(spin)
        return container

    def _make_gain_controls(self, min_val: float, max_val: float, default: float):
        slider = QSlider()
        slider.setOrientation(Qt.Orientation.Horizontal)
        slider.setRange(0, 200)
        spin = QDoubleSpinBox()
        spin.setRange(min_val, max_val)
        spin.setValue(default)

        def slider_to_value(val: int) -> float:
            return min_val + (max_val - min_val) * (val / 200.0)

        def value_to_slider(val: float) -> int:
            return int(200 * (val - min_val) / (max_val - min_val))

        def on_slider(val: int) -> None:
            spin.blockSignals(True)
            spin.setValue(slider_to_value(val))
            spin.blockSignals(False)
            self._schedule_update()

        def on_spin(val: float) -> None:
            slider.blockSignals(True)
            slider.setValue(value_to_slider(val))
            slider.blockSignals(False)
            self._schedule_update()

        slider.valueChanged.connect(on_slider)
        spin.valueChanged.connect(on_spin)
        slider.setValue(value_to_slider(default))
        return slider, spin

    def _schedule_update(self) -> None:
        self._debounce.start(150)

    def _parse_plant(self):
        num = ast.literal_eval(self.num_edit.text())
        den = ast.literal_eval(self.den_edit.text())
        return ct.tf(num, den)

    def _update_plot(self) -> None:
        try:
            plant = self._parse_plant()
        except (ValueError, SyntaxError):
            return

        kp = self.kp_spin.value()
        ki = self.ki_spin.value()
        kd = self.kd_spin.value()
        controller = ct.tf([kd, kp, ki], [1, 0.001])
        loop = controller * plant
        closed = ct.feedback(loop)

        t_end = self.t_end.value()
        t = np.linspace(0, t_end, 1000)
        t, y = ct.step_response(closed, t)
        ref = self.reference.value()
        y = y * ref
        error = ref - y
        _, u = ct.forced_response(controller, t, error)

        self.figure.clear()
        ax1 = self.figure.add_subplot(211)
        ax2 = self.figure.add_subplot(212)
        ax1.plot(t, y, color="#1a6fff", linewidth=1.5)
        ax1.axhline(ref, color="#6a7280", linestyle="--")
        ax2.plot(t, u, color="#e5c07b", linewidth=1.2)
        ax1.set_facecolor("#08090e")
        ax2.set_facecolor("#08090e")
        for ax in (ax1, ax2):
            ax.tick_params(colors="#3a4050")
            for spine in ax.spines.values():
                spine.set_color("#1e2128")
            ax.grid(True, color="#1a1f2a", linewidth=0.5)
        ax1.set_ylabel("Output")
        ax2.set_ylabel("Control effort")
        self.canvas.draw()

        metrics = _compute_performance(t, y, ref)
        self.metrics["Rise time"].setText(f"{metrics['rise_time']:.2f}s")
        self.metrics["Settling time"].setText(f"{metrics['settling_time']:.2f}s")
        self.metrics["Overshoot"].setText(f"{metrics['overshoot']:.2f}%")
        self.metrics["SS error"].setText(f"{metrics['ss_error']:.4f}")
        self.metrics["Peak time"].setText(f"{metrics['peak_time']:.2f}s")
        self._apply_metric_colors(metrics)

        poles = ct.poles(closed)
        self.poles_table.setRowCount(len(poles))
        for idx, pole in enumerate(poles):
            stable = pole.real < 0
            self.poles_table.setItem(idx, 0, QTableWidgetItem(f"{pole:.3f}"))
            item = QTableWidgetItem("Yes" if stable else "No")
            item.setForeground(QColor("#98c379") if stable else QColor("#e06c75"))
            self.poles_table.setItem(idx, 1, item)

    def _apply_metric_colors(self, metrics: dict) -> None:
        overshoot = metrics.get("overshoot", 0.0)
        settling = metrics.get("settling_time", 0.0)
        if overshoot < 5:
            self.metrics["Overshoot"].setStyleSheet("color: #98c379;")
        elif overshoot < 20:
            self.metrics["Overshoot"].setStyleSheet("color: #e5c07b;")
        else:
            self.metrics["Overshoot"].setStyleSheet("color: #e06c75;")

        if settling < 5:
            self.metrics["Settling time"].setStyleSheet("color: #98c379;")
        elif settling > 10:
            self.metrics["Settling time"].setStyleSheet("color: #e06c75;")
        else:
            self.metrics["Settling time"].setStyleSheet("color: #e5c07b;")

    def _auto_tune(self) -> None:
        try:
            plant = self._parse_plant()
            gm, pm, wg, wp = ct.margin(plant)
            ku = gm if gm and gm > 0 else 1.0
            tu = 2 * np.pi / wp if wp and wp > 0 else 1.0
            kp = 0.6 * ku
            ki = 1.2 * ku / tu
            kd = 0.075 * ku * tu
            self.kp_spin.setValue(kp)
            self.ki_spin.setValue(ki)
            self.kd_spin.setValue(kd)
        except (ValueError, SyntaxError):
            return

    def _reset_gains(self) -> None:
        self.kp_spin.setValue(1.0)
        self.ki_spin.setValue(0.0)
        self.kd_spin.setValue(0.0)

    def _emit_code(self) -> None:
        kp = self.kp_spin.value()
        ki = self.ki_spin.value()
        kd = self.kd_spin.value()
        code = (
            f"Kp, Ki, Kd = {kp:.3f}, {ki:.3f}, {kd:.3f}\n"
            f"C = ct.tf([{kd:.3f}, {kp:.3f}, {ki:.3f}], [1, 0.001])\n"
        )
        self.code_insert_requested.emit(code)


def _compute_performance(t: np.ndarray, y: np.ndarray, reference: float) -> dict:
    rise_time = next((t[i] for i, val in enumerate(y) if val >= 0.9 * reference), t[-1])
    settle_idx = np.where(np.abs(y - reference) > 0.02 * reference)[0]
    settling_time = t[settle_idx[-1]] if len(settle_idx) else t[-1]
    overshoot = (np.max(y) - reference) / reference * 100.0
    peak_time = t[np.argmax(y)]
    ss_error = abs(y[-1] - reference)
    return {
        "rise_time": float(rise_time),
        "settling_time": float(settling_time),
        "overshoot": float(overshoot),
        "ss_error": float(ss_error),
        "peak_time": float(peak_time),
    }
