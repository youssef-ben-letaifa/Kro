"""LQR/LQG controller designer dialog."""

from __future__ import annotations

import ast

import control as ct
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class LQRDesignerDialog(QDialog):
    """LQR controller design wizard with step response preview."""

    code_insert_requested = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("LQR Controller Designer")
        self.resize(900, 620)

        layout = QHBoxLayout(self)
        layout.addWidget(self._build_controls(), 1)
        layout.addWidget(self._build_plot(), 2)
        layout.addWidget(self._build_results(), 1)

    def _build_controls(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        plant_box = QGroupBox("State-Space Plant")
        plant_form = QFormLayout(plant_box)
        self.a_edit = QLineEdit("[[0,1],[-2,-3]]")
        self.b_edit = QLineEdit("[[0],[1]]")
        self.c_edit = QLineEdit("[[1,0]]")
        self.d_edit = QLineEdit("[[0]]")
        plant_form.addRow("A:", self.a_edit)
        plant_form.addRow("B:", self.b_edit)
        plant_form.addRow("C:", self.c_edit)
        plant_form.addRow("D:", self.d_edit)
        layout.addWidget(plant_box)

        weight_box = QGroupBox("LQR Weights")
        weight_form = QFormLayout(weight_box)
        self.q_edit = QLineEdit("[[1,0],[0,1]]")
        self.r_edit = QLineEdit("[[1]]")
        weight_form.addRow("Q:", self.q_edit)
        weight_form.addRow("R:", self.r_edit)

        desc = QLabel("Q: state cost · R: control cost")
        desc.setStyleSheet("color: #6a7280; font-size: 10px;")
        weight_form.addRow("", desc)
        layout.addWidget(weight_box)

        compute_btn = QPushButton("Compute K & Simulate")
        insert_btn = QPushButton("Insert Code")
        compute_btn.clicked.connect(self._compute)
        insert_btn.clicked.connect(self._insert_code)
        layout.addWidget(compute_btn)
        layout.addWidget(insert_btn)
        layout.addStretch(1)
        return panel

    def _build_plot(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        self.figure = Figure(facecolor="#08090e")
        self.canvas = FigureCanvasQTAgg(self.figure)
        layout.addWidget(self.canvas)
        return container

    def _build_results(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        self._gain_label = QLabel("K = —")
        self._gain_label.setWordWrap(True)
        self._gain_label.setStyleSheet("font-size: 11px;")
        layout.addWidget(self._gain_label)

        self._poles_label = QLabel("CL Poles: —")
        self._poles_label.setWordWrap(True)
        self._poles_label.setStyleSheet("font-size: 10px; color: #8a92a2;")
        layout.addWidget(self._poles_label)

        self._cost_label = QLabel("J∞ = —")
        self._cost_label.setStyleSheet("font-size: 10px; color: #8a92a2;")
        layout.addWidget(self._cost_label)

        self._stable_label = QLabel("")
        self._stable_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._stable_label)

        layout.addStretch(1)
        return panel

    def _parse_matrices(self):
        A = np.array(ast.literal_eval(self.a_edit.text()), dtype=float)
        B = np.array(ast.literal_eval(self.b_edit.text()), dtype=float)
        C = np.array(ast.literal_eval(self.c_edit.text()), dtype=float)
        D = np.array(ast.literal_eval(self.d_edit.text()), dtype=float)
        Q = np.array(ast.literal_eval(self.q_edit.text()), dtype=float)
        R = np.array(ast.literal_eval(self.r_edit.text()), dtype=float)
        return A, B, C, D, Q, R

    def _compute(self) -> None:
        try:
            A, B, C, D, Q, R = self._parse_matrices()
        except (ValueError, SyntaxError) as exc:
            QMessageBox.warning(self, "Invalid matrix", str(exc))
            return

        try:
            K, S, E = ct.lqr(A, B, Q, R)
        except Exception as exc:
            QMessageBox.warning(self, "LQR failed", str(exc))
            return

        K = np.atleast_2d(K)

        # Display gains
        k_str = np.array2string(K, precision=4, separator=", ")
        self._gain_label.setText(f"K = {k_str}")

        # Display CL poles
        cl_poles = E
        pole_strs = [f"{p:.4f}" for p in cl_poles]
        self._poles_label.setText(f"CL Poles:\n{chr(10).join(pole_strs)}")

        # Stability check
        stable = all(p.real < 0 for p in cl_poles)
        if stable:
            self._stable_label.setText("✓ STABLE")
            self._stable_label.setStyleSheet(
                "color: #98c379; font-weight: bold; font-size: 14px;"
            )
        else:
            self._stable_label.setText("✗ UNSTABLE")
            self._stable_label.setStyleSheet(
                "color: #e06c75; font-weight: bold; font-size: 14px;"
            )

        # Simulate step response
        A_cl = A - B @ K
        sys_cl = ct.ss(A_cl, B, C, D)
        t = np.linspace(0, 10, 1000)
        t, y = ct.step_response(sys_cl, t)

        # Simulate open-loop for comparison
        sys_ol = ct.ss(A, B, C, D)
        try:
            t_ol, y_ol = ct.step_response(sys_ol, t)
            show_ol = True
        except Exception:
            show_ol = False

        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_facecolor("#08090e")
        if show_ol:
            ax.plot(t_ol, y_ol, color="#3a4050", linewidth=1.0,
                    linestyle="--", label="Open Loop")
        ax.plot(t, y, color="#1a6fff", linewidth=1.5, label="LQR Closed Loop")
        ax.axhline(1.0, color="#6a7280", linestyle="--", linewidth=0.8)
        ax.set_xlabel("Time (s)", color="#6a7280")
        ax.set_ylabel("Output", color="#6a7280")
        ax.set_title("Step Response Comparison", color="#c8ccd4", fontsize=11)
        ax.tick_params(colors="#3a4050")
        for spine in ax.spines.values():
            spine.set_color("#1e2128")
        ax.grid(True, color="#1a1f2a", linewidth=0.5)
        ax.legend(facecolor="#0e1117", edgecolor="#1e2128",
                  labelcolor="#c8ccd4", fontsize=8)
        self.canvas.draw()

    def _insert_code(self) -> None:
        code = (
            "import control as ct\n"
            "import numpy as np\n"
            f"A = np.array({self.a_edit.text()})\n"
            f"B = np.array({self.b_edit.text()})\n"
            f"C = np.array({self.c_edit.text()})\n"
            f"D = np.array({self.d_edit.text()})\n"
            f"Q = np.array({self.q_edit.text()})\n"
            f"R = np.array({self.r_edit.text()})\n"
            "K, S, E = ct.lqr(A, B, Q, R)\n"
            "print('LQR Gain K:', K)\n"
            "print('CL Poles:', E)\n"
            "sys_cl = ct.ss(A - B @ K, B, C, D)\n"
            "t, y = ct.step_response(sys_cl)\n"
            "import matplotlib.pyplot as plt\n"
            "plt.plot(t, y)\n"
            "plt.title('LQR Step Response')\n"
            "plt.show()\n"
        )
        self.code_insert_requested.emit(code)
