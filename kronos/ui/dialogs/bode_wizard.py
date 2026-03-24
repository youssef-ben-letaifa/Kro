"""Bode plot wizard dialog."""

from __future__ import annotations

import ast
import json
from typing import Callable

import control as ct
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
    QDoubleSpinBox,
)
from kronos.engine.kernel_message_router import KernelMessageRouter


class BodeWizardDialog(QDialog):
    """Dialog for generating Bode plots."""

    code_insert_requested = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Bode Plot Wizard")
        self.resize(800, 600)
        self._kernel_client_getter: Callable[[], object] | None = None
        self._message_router_getter: Callable[[], KernelMessageRouter | None] | None = None
        self._workspace_vars: dict = {}

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_controls())
        splitter.addWidget(self._build_plot())
        splitter.setSizes([250, 550])

        layout = QVBoxLayout(self)
        layout.addWidget(splitter)

    def _build_controls(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        form = QFormLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Transfer Function", "State Space", "From Workspace"])
        self.mode_combo.currentTextChanged.connect(self._update_mode_fields)
        form.addRow("Mode:", self.mode_combo)

        self.num_edit = QLineEdit("[1]")
        self.den_edit = QLineEdit("[1, 2, 1]")
        self.a_edit = QLineEdit("[[0,1],[-1,-2]]")
        self.b_edit = QLineEdit("[[0],[1]]")
        self.c_edit = QLineEdit("[[1,0]]")
        self.d_edit = QLineEdit("[[0]]")
        self.workspace_combo = QComboBox()

        form.addRow("Numerator:", self.num_edit)
        form.addRow("Denominator:", self.den_edit)
        form.addRow("A:", self.a_edit)
        form.addRow("B:", self.b_edit)
        form.addRow("C:", self.c_edit)
        form.addRow("D:", self.d_edit)
        form.addRow("Workspace:", self.workspace_combo)
        layout.addLayout(form)

        freq_layout = QFormLayout()
        self.start_exp = QDoubleSpinBox()
        self.start_exp.setRange(-3.0, 0.0)
        self.start_exp.setValue(-2.0)
        self.end_exp = QDoubleSpinBox()
        self.end_exp.setRange(0.0, 6.0)
        self.end_exp.setValue(3.0)
        self.points = QSpinBox()
        self.points.setRange(10, 10000)
        self.points.setValue(500)
        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["rad/s", "Hz"])
        freq_layout.addRow("Start (10^x):", self.start_exp)
        freq_layout.addRow("End (10^x):", self.end_exp)
        freq_layout.addRow("Points:", self.points)
        freq_layout.addRow("Unit:", self.unit_combo)
        layout.addLayout(freq_layout)

        self.db_check = QCheckBox("dB scale")
        self.db_check.setChecked(True)
        self.unwrap_check = QCheckBox("Phase unwrap")
        self.unwrap_check.setChecked(True)
        self.grid_check = QCheckBox("Grid")
        self.grid_check.setChecked(True)
        self.margins_check = QCheckBox("Show margins")
        self.margins_check.setChecked(True)
        layout.addWidget(self.db_check)
        layout.addWidget(self.unwrap_check)
        layout.addWidget(self.grid_check)
        layout.addWidget(self.margins_check)

        generate_btn = QPushButton("Generate Plot")
        export_btn = QPushButton("Export PNG")
        insert_btn = QPushButton("Insert Code")
        generate_btn.clicked.connect(self.generate_plot)
        export_btn.clicked.connect(self._export_png)
        insert_btn.clicked.connect(self._insert_code)
        layout.addWidget(generate_btn)
        layout.addWidget(export_btn)
        layout.addWidget(insert_btn)
        layout.addStretch(1)
        self._update_mode_fields(self.mode_combo.currentText())
        return panel

    def _build_plot(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        self.figure = Figure(facecolor="#08090e")
        self.canvas = FigureCanvasQTAgg(self.figure)
        layout.addWidget(self.canvas)
        return container

    def set_workspace_vars(self, vars_dict: dict) -> None:
        self._workspace_vars = vars_dict
        self.workspace_combo.clear()
        for name, meta in vars_dict.items():
            var_type = meta.get("type", "")
            if "TransferFunction" in var_type or "StateSpace" in var_type:
                self.workspace_combo.addItem(name)

    def set_kernel_client_getter(self, getter: Callable[[], object]) -> None:
        self._kernel_client_getter = getter

    def set_message_router_getter(
        self, getter: Callable[[], KernelMessageRouter | None]
    ) -> None:
        self._message_router_getter = getter

    def _update_mode_fields(self, mode: str) -> None:
        tf_enabled = mode == "Transfer Function"
        ss_enabled = mode == "State Space"
        ws_enabled = mode == "From Workspace"
        for widget in (self.num_edit, self.den_edit):
            widget.setEnabled(tf_enabled)
        for widget in (self.a_edit, self.b_edit, self.c_edit, self.d_edit):
            widget.setEnabled(ss_enabled)
        self.workspace_combo.setEnabled(ws_enabled)

    def _get_system(self):
        mode = self.mode_combo.currentText()
        if mode == "Transfer Function":
            num = ast.literal_eval(self.num_edit.text())
            den = ast.literal_eval(self.den_edit.text())
            return ct.tf(num, den)
        if mode == "State Space":
            a = np.array(ast.literal_eval(self.a_edit.text()))
            b = np.array(ast.literal_eval(self.b_edit.text()))
            c = np.array(ast.literal_eval(self.c_edit.text()))
            d = np.array(ast.literal_eval(self.d_edit.text()))
            return ct.ss(a, b, c, d)
        name = self.workspace_combo.currentText()
        return self._fetch_from_kernel(name)

    def _fetch_from_kernel(self, name: str):
        if not self._kernel_client_getter:
            raise ValueError("Kernel not available")
        kernel = self._kernel_client_getter()
        router = self._message_router_getter() if self._message_router_getter else None
        if router is None:
            raise ValueError("Kernel message router is not available")
        code = (
            "import json, control as ct\n"
            f"obj = globals().get({name!r})\n"
            "payload = {}\n"
            "if isinstance(obj, ct.TransferFunction):\n"
            "    num, den = ct.tfdata(obj)\n"
            "    payload = {'type':'tf','num':num[0][0].tolist(),'den':den[0][0].tolist()}\n"
            "elif isinstance(obj, ct.StateSpace):\n"
            "    payload = {'type':'ss','A':obj.A.tolist(),'B':obj.B.tolist(),'C':obj.C.tolist(),'D':obj.D.tolist()}\n"
            "print(json.dumps(payload))\n"
        )
        data = router.request_json(kernel, code, timeout_ms=2000)
        if not isinstance(data, dict):
            raise ValueError("Failed to parse workspace system")
        if data.get("type") == "tf":
            return ct.tf(data["num"], data["den"])
        if data.get("type") == "ss":
            return ct.ss(data["A"], data["B"], data["C"], data["D"])
        raise ValueError("No control system found in workspace")

    def generate_plot(self) -> None:
        try:
            sys = self._get_system()
        except (ValueError, SyntaxError) as exc:
            QMessageBox.warning(self, "Invalid input", str(exc))
            return

        start_exp = self.start_exp.value()
        end_exp = self.end_exp.value()
        points = self.points.value()
        freq = np.logspace(start_exp, end_exp, points)
        omega = 2 * np.pi * freq if self.unit_combo.currentText() == "Hz" else freq
        mag, phase, omega = ct.bode_data(sys, omega)
        mag = np.squeeze(mag)
        phase = np.squeeze(phase)
        phase = np.unwrap(phase) if self.unwrap_check.isChecked() else phase
        mag_vals = 20 * np.log10(mag) if self.db_check.isChecked() else mag
        phase_deg = np.degrees(phase)
        x_vals = omega if self.unit_combo.currentText() == "rad/s" else freq

        self.figure.clear()
        ax1 = self.figure.add_subplot(211)
        ax2 = self.figure.add_subplot(212)
        ax1.plot(x_vals, mag_vals, color="#1a6fff")
        ax2.plot(x_vals, phase_deg, color="#e5c07b")
        ax1.set_xscale("log")
        ax2.set_xscale("log")
        ax1.set_ylabel("Magnitude (dB)" if self.db_check.isChecked() else "Magnitude")
        ax2.set_ylabel("Phase (deg)")
        ax2.set_xlabel(f"Frequency ({self.unit_combo.currentText()})")
        for ax in (ax1, ax2):
            ax.set_facecolor("#08090e")
            ax.tick_params(colors="#3a4050")
            for spine in ax.spines.values():
                spine.set_color("#1e2128")
        if self.grid_check.isChecked():
            ax1.grid(True, color="#1a1f2a", linewidth=0.5)
            ax2.grid(True, color="#1a1f2a", linewidth=0.5)

        if self.margins_check.isChecked():
            gm, pm, wg, wp = ct.margin(sys)
            if wg and np.isfinite(wg):
                x_g = wg if self.unit_combo.currentText() == "rad/s" else wg / (2 * np.pi)
                ax1.axvline(x_g, color="#98c379", linestyle="--")
            if wp and np.isfinite(wp):
                x_p = wp if self.unit_combo.currentText() == "rad/s" else wp / (2 * np.pi)
                ax2.axvline(x_p, color="#98c379", linestyle="--")
                ax2.annotate(f"PM={pm:.1f}°", xy=(x_p, 0), color="#98c379")

        self.canvas.draw()

    def _export_png(self) -> None:
        path = "bode_plot.png"
        self.figure.savefig(path, dpi=150)
        QMessageBox.information(self, "Saved", f"Saved to {path}")

    def _insert_code(self) -> None:
        mode = self.mode_combo.currentText()
        db_flag = "True" if self.db_check.isChecked() else "False"
        if mode == "Transfer Function":
            code = (
                "import control as ct\n"
                "import matplotlib.pyplot as plt\n"
                f"num = {self.num_edit.text()}\n"
                f"den = {self.den_edit.text()}\n"
                "sys = ct.tf(num, den)\n"
                f"ct.bode_plot(sys, dB={db_flag})\n"
                "plt.show()\n"
            )
        elif mode == "State Space":
            code = (
                "import control as ct\n"
                "import matplotlib.pyplot as plt\n"
                f"A = {self.a_edit.text()}\n"
                f"B = {self.b_edit.text()}\n"
                f"C = {self.c_edit.text()}\n"
                f"D = {self.d_edit.text()}\n"
                "sys = ct.ss(A, B, C, D)\n"
                f"ct.bode_plot(sys, dB={db_flag})\n"
                "plt.show()\n"
            )
        else:
            name = self.workspace_combo.currentText()
            code = (
                "import control as ct\n"
                "import matplotlib.pyplot as plt\n"
                f"sys = {name}\n"
                f"ct.bode_plot(sys, dB={db_flag})\n"
                "plt.show()\n"
            )
        self.code_insert_requested.emit(code)
