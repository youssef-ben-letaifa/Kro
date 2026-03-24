"""Kronos toolbar with icon-only controls."""

from __future__ import annotations

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QFrame, QToolBar, QToolButton


class KronosToolBar(QToolBar):
    """Primary toolbar for Kronos."""

    run_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    restart_requested = pyqtSignal()
    new_requested = pyqtSignal()
    open_requested = pyqtSignal()
    save_requested = pyqtSignal()
    bode_requested = pyqtSignal()
    step_requested = pyqtSignal()
    rootlocus_requested = pyqtSignal()
    pid_requested = pyqtSignal()
    lqr_requested = pyqtSignal()
    theme_toggle_requested = pyqtSignal()
    simulink_requested = pyqtSignal()
    quantum_requested = pyqtSignal()
    symbolic_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__("KronosToolBar")
        self.setMovable(False)
        self.setFixedHeight(36)
        self.setIconSize(QSize(16, 16))
        self.setStyleSheet(
            "QToolBar { background: #080c14; border-bottom: 1px solid #1e2128; }"
            "QToolButton { background: transparent; border: none; }"
            "QToolButton:hover { background: #13192a; border-radius: 4px; }"
            "QToolButton:checked { background: #1a3a5c; color: #1a6fff; }"
        )

        self._control_buttons: list[QToolButton] = []

        self._add_exec_group()
        self._add_separator()
        self._add_file_group()
        self._add_separator()
        self._add_control_group()
        self._add_separator()
        self._add_view_group()
        self._add_separator()
        self._add_theme_group()

    def _add_separator(self) -> None:
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
        divider.setStyleSheet("QFrame { color: #1e2128; }")
        self.addWidget(divider)

    def _make_button(self, symbol: str, tooltip: str, color: QColor | None = None) -> QToolButton:
        button = QToolButton()
        button.setToolTip(tooltip)
        button.setAutoRaise(True)
        button.setFixedSize(28, 28)
        button.setIcon(self._make_icon(symbol, color or QColor("#c8ccd4")))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        return button

    @staticmethod
    def _make_icon(symbol: str, color: QColor) -> QIcon:
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setPen(color)
        painter.setFont(painter.font())
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, symbol)
        painter.end()
        return QIcon(pixmap)

    def _add_exec_group(self) -> None:
        run = self._make_button("▶", "Run (F5)", QColor("#98c379"))
        stop = self._make_button("■", "Stop Kernel", QColor("#e06c75"))
        restart = self._make_button("↺", "Restart Kernel", QColor("#e5c07b"))
        run.clicked.connect(self.run_requested)
        stop.clicked.connect(self.stop_requested)
        restart.clicked.connect(self.restart_requested)
        self.addWidget(run)
        self.addWidget(stop)
        self.addWidget(restart)

    def _add_file_group(self) -> None:
        new = self._make_button("📄", "New File (Ctrl+N)")
        open_btn = self._make_button("📂", "Open File (Ctrl+O)")
        save = self._make_button("💾", "Save (Ctrl+S)")
        new.clicked.connect(self.new_requested)
        open_btn.clicked.connect(self.open_requested)
        save.clicked.connect(self.save_requested)
        self.addWidget(new)
        self.addWidget(open_btn)
        self.addWidget(save)

    def _add_control_group(self) -> None:
        bode = self._make_button("〜", "Bode Plot Wizard")
        step = self._make_button("↗", "Step Response Wizard")
        root = self._make_button("⊙", "Root Locus Plot")
        pid = self._make_button("⚙", "PID Tuner")
        lqr = self._make_button("∑", "LQR Designer")
        bode.clicked.connect(self.bode_requested)
        step.clicked.connect(self.step_requested)
        root.clicked.connect(self.rootlocus_requested)
        pid.clicked.connect(self.pid_requested)
        lqr.clicked.connect(self.lqr_requested)
        self._control_buttons = [bode, step, root, pid, lqr]
        for btn in self._control_buttons:
            self.addWidget(btn)

    def _add_view_group(self) -> None:
        simulink = self._make_button("◫", "Switch to Simulink Canvas")
        quantum = self._make_button("⚛", "Switch to Quantum Circuit")
        symbolic = self._make_button("Σ", "Switch to Symbolic Math")
        simulink.clicked.connect(self.simulink_requested)
        quantum.clicked.connect(self.quantum_requested)
        symbolic.clicked.connect(self.symbolic_requested)
        self.addWidget(simulink)
        self.addWidget(quantum)
        self.addWidget(symbolic)

    def _add_theme_group(self) -> None:
        self._theme_button = self._make_button("🌙", "Toggle Dark/Light Theme")
        self._theme_button.clicked.connect(self.theme_toggle_requested)
        self.addWidget(self._theme_button)

    def set_control_tools_enabled(self, enabled: bool) -> None:
        """Enable or disable control tool buttons."""
        for btn in self._control_buttons:
            btn.setEnabled(enabled)

    def set_theme_icon(self, theme: str) -> None:
        """Update theme toggle icon based on current theme."""
        symbol = "🌙" if theme == "dark" else "☀"
        self._theme_button.setIcon(self._make_icon(symbol, QColor("#c8ccd4")))
