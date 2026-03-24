"""Enhanced status bar for Kronos."""

from __future__ import annotations

import sys
from typing import Callable

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QStatusBar, QWidget

try:
    import psutil
except ImportError:
    psutil = None


class KernelIndicator(QWidget):
    """Kernel status indicator widget."""

    def __init__(self) -> None:
        super().__init__()
        self._dot = QLabel()
        self._text = QLabel("Kernel: offline")
        self._text.setStyleSheet("color: #6a7280;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self._dot)
        layout.addWidget(self._text)
        self.set_status(False)

    def set_status(self, online: bool) -> None:
        color = "#98c379" if online else "#e06c75"
        status = "ready" if online else "offline"
        self._dot.setPixmap(KronosStatusBar._make_dot(QColor(color)))
        self._text.setText(f"Kernel: {status}")


class KronosStatusBar(QStatusBar):
    """Status bar showing kernel, memory, cursor and Python version."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(24)
        self.setStyleSheet("QStatusBar { background: #080c14; border-top: 1px solid #1e2128; }")

        self._kernel_label = KernelIndicator()
        self._memory_label = QLabel()
        self._cursor_label = QLabel("Ln 1  Col 1")
        self._python_label = QLabel(f"Python {sys.version.split()[0]}")

        self._kernel_client_getter: Callable[[], object] | None = None
        self._kernel_online = False

        self._init_widgets()
        self._start_timers()

    def _init_widgets(self) -> None:
        self._memory_label.setText("RAM: -- MB")
        self._memory_label.setStyleSheet("color: #6a7280;")
        self._cursor_label.setStyleSheet("color: #6a7280;")
        self._python_label.setStyleSheet("color: #6a7280;")

        for widget in (
            self._kernel_label,
            self._separator(),
            self._memory_label,
            self._separator(),
            self._cursor_label,
            self._separator(),
            self._python_label,
        ):
            self.addPermanentWidget(widget)

    @staticmethod
    def _separator() -> QLabel:
        label = QLabel("  |  ")
        label.setStyleSheet("color: #3a4050;")
        return label

    def _start_timers(self) -> None:
        self._kernel_timer = QTimer(self)
        self._kernel_timer.timeout.connect(self._refresh_kernel)
        self._kernel_timer.start(2000)

        self._memory_timer = QTimer(self)
        self._memory_timer.timeout.connect(self._refresh_memory)
        self._memory_timer.start(5000)

    def set_kernel_client_getter(self, getter: Callable[[], object]) -> None:
        """Provide a callable to detect kernel availability."""
        self._kernel_client_getter = getter
        self._refresh_kernel()

    def _refresh_kernel(self) -> None:
        online = False
        if self._kernel_client_getter is not None:
            online = self._kernel_client_getter() is not None
        self.set_kernel_status(online)

    def _refresh_memory(self) -> None:
        if psutil is None:
            return
        process = psutil.Process()
        mem_mb = process.memory_info().rss / (1024 * 1024)
        self.set_memory(mem_mb)

    def set_kernel_status(self, online: bool) -> None:
        """Update kernel status indicator."""
        self._kernel_online = online
        color = "#98c379" if online else "#e06c75"
        status = "ready" if online else "offline"
        self._kernel_label.set_status(online)

    def set_memory(self, mb: float) -> None:
        """Update memory indicator."""
        self._memory_label.setText(f"RAM: {mb:.0f} MB")

    def update_cursor(self, line: int, col: int) -> None:
        """Update cursor indicator."""
        self._cursor_label.setText(f"Ln {line}  Col {col}")

    @staticmethod
    def _make_dot(color: QColor) -> QPixmap:
        pixmap = QPixmap(10, 10)
        pixmap.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pixmap)
        painter.setBrush(color)
        painter.setPen(color)
        painter.drawEllipse(1, 1, 8, 8)
        painter.end()
        return pixmap
