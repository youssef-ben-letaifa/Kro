"""Root locus plot wizard dialog."""

from __future__ import annotations

import ast

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
    QSplitter,
    QVBoxLayout,
    QWidget,
)


class RootLocusDialog(QDialog):
    """Interactive root locus plot wizard."""

    code_insert_requested = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Root Locus Plot")
        self.resize(850, 600)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_controls())
        splitter.addWidget(self._build_plot())
        splitter.setSizes([260, 590])

        layout = QVBoxLayout(self)
        layout.addWidget(splitter)

    def _build_controls(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        form = QFormLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Transfer Function", "State Space"])
        self.mode_combo.currentTextChanged.connect(self._update_mode)
        form.addRow("Mode:", self.mode_combo)

        self.num_edit = QLineEdit("[1]")
        self.den_edit = QLineEdit("[1, 3, 2]")
        self.a_edit = QLineEdit("[[0,1],[-2,-3]]")
        self.b_edit = QLineEdit("[[0],[1]]")
        self.c_edit = QLineEdit("[[1,0]]")
        self.d_edit = QLineEdit("[[0]]")
        form.addRow("Numerator:", self.num_edit)
        form.addRow("Denominator:", self.den_edit)
        form.addRow("A:", self.a_edit)
        form.addRow("B:", self.b_edit)
        form.addRow("C:", self.c_edit)
        form.addRow("D:", self.d_edit)
        layout.addLayout(form)

        self.grid_check = QCheckBox("Show grid")
        self.grid_check.setChecked(True)
        self.asymptote_check = QCheckBox("Show asymptotes")
        self.asymptote_check.setChecked(True)
        layout.addWidget(self.grid_check)
        layout.addWidget(self.asymptote_check)

        # Info panel
        self._info_label = QLabel("Click 'Generate' to compute root locus")
        self._info_label.setWordWrap(True)
        self._info_label.setStyleSheet("color: #6a7280; font-size: 10px;")
        layout.addWidget(self._info_label)

        generate_btn = QPushButton("Generate Plot")
        insert_btn = QPushButton("Insert Code")
        generate_btn.clicked.connect(self._generate)
        insert_btn.clicked.connect(self._insert_code)
        layout.addWidget(generate_btn)
        layout.addWidget(insert_btn)
        layout.addStretch(1)

        self._update_mode(self.mode_combo.currentText())
        return panel

    def _build_plot(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        self.figure = Figure(facecolor="#08090e")
        self.canvas = FigureCanvasQTAgg(self.figure)
        layout.addWidget(self.canvas)
        return container

    def _update_mode(self, mode: str) -> None:
        tf_mode = mode == "Transfer Function"
        for w in (self.num_edit, self.den_edit):
            w.setEnabled(tf_mode)
        for w in (self.a_edit, self.b_edit, self.c_edit, self.d_edit):
            w.setEnabled(not tf_mode)

    def _get_system(self):
        """Parse the current system from widgets."""
        if self.mode_combo.currentText() == "Transfer Function":
            num = ast.literal_eval(self.num_edit.text())
            den = ast.literal_eval(self.den_edit.text())
            return ct.tf(num, den)
        a = np.array(ast.literal_eval(self.a_edit.text()))
        b = np.array(ast.literal_eval(self.b_edit.text()))
        c = np.array(ast.literal_eval(self.c_edit.text()))
        d = np.array(ast.literal_eval(self.d_edit.text()))
        return ct.ss(a, b, c, d)

    def _generate(self) -> None:
        try:
            sys = self._get_system()
        except (ValueError, SyntaxError) as exc:
            QMessageBox.warning(self, "Invalid input", str(exc))
            return

        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_facecolor("#08090e")

        try:
            rlist, klist = ct.root_locus(sys, plot=False)
        except TypeError:
            rlist = ct.root_locus(sys, plot=False)
            klist = None

        # Plot the loci
        if isinstance(rlist, np.ndarray) and rlist.ndim == 2:
            for col in range(rlist.shape[1]):
                ax.plot(rlist[:, col].real, rlist[:, col].imag,
                        color="#1a6fff", linewidth=1.2)

        # Plot open-loop poles and zeros
        poles = ct.poles(sys)
        zeros = ct.zeros(sys)
        ax.plot(poles.real, poles.imag, "x", color="#e06c75",
                markersize=10, markeredgewidth=2, label="Poles")
        if len(zeros) > 0:
            ax.plot(zeros.real, zeros.imag, "o", color="#98c379",
                    markersize=8, markerfacecolor="none",
                    markeredgewidth=2, label="Zeros")

        # Show asymptotes
        if self.asymptote_check.isChecked():
            n_poles = len(poles)
            n_zeros = len(zeros)
            n_asym = n_poles - n_zeros
            if n_asym > 0:
                sigma_a = (sum(poles.real) - sum(zeros.real)) / n_asym
                for k in range(n_asym):
                    angle = (2 * k + 1) * 180.0 / n_asym
                    rad = np.deg2rad(angle)
                    length = 20
                    ax.plot(
                        [sigma_a, sigma_a + length * np.cos(rad)],
                        [0, length * np.sin(rad)],
                        "--", color="#4a5060", linewidth=0.8
                    )

        ax.axhline(0, color="#1e2128", linewidth=0.5)
        ax.axvline(0, color="#1e2128", linewidth=0.5)
        if self.grid_check.isChecked():
            ax.grid(True, color="#1a1f2a", linewidth=0.5)
        ax.set_xlabel("Real", color="#6a7280")
        ax.set_ylabel("Imaginary", color="#6a7280")
        ax.set_title("Root Locus", color="#c8ccd4", fontsize=11)
        ax.tick_params(colors="#3a4050")
        for spine in ax.spines.values():
            spine.set_color("#1e2128")
        ax.legend(facecolor="#0e1117", edgecolor="#1e2128",
                  labelcolor="#c8ccd4", fontsize=8)

        # Info text
        info_parts = [f"Poles: {len(poles)}", f"Zeros: {len(zeros)}"]
        pole_strs = [f"{p:.3f}" for p in poles]
        info_parts.append(f"OL Poles: {', '.join(pole_strs)}")
        self._info_label.setText(" | ".join(info_parts))

        self.canvas.draw()

    def _insert_code(self) -> None:
        if self.mode_combo.currentText() == "Transfer Function":
            code = (
                "import control as ct\n"
                "import matplotlib.pyplot as plt\n"
                f"num = {self.num_edit.text()}\n"
                f"den = {self.den_edit.text()}\n"
                "sys = ct.tf(num, den)\n"
                "ct.root_locus(sys)\n"
                "plt.show()\n"
            )
        else:
            code = (
                "import control as ct\n"
                "import numpy as np\n"
                "import matplotlib.pyplot as plt\n"
                f"A = np.array({self.a_edit.text()})\n"
                f"B = np.array({self.b_edit.text()})\n"
                f"C = np.array({self.c_edit.text()})\n"
                f"D = np.array({self.d_edit.text()})\n"
                "sys = ct.ss(A, B, C, D)\n"
                "ct.root_locus(sys)\n"
                "plt.show()\n"
            )
        self.code_insert_requested.emit(code)
