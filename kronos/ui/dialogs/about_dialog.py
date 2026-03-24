"""About dialog for Kronos IDE."""

from __future__ import annotations

import platform
import sys

from PyQt6.QtCore import PYQT_VERSION_STR, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class AboutDialog(QDialog):
    """Modal dialog showing Kronos version and credits."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("About Kronos")
        self.setFixedSize(480, 320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(10)

        # Logo
        logo = QLabel()
        logo.setPixmap(self._draw_logo())
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo)

        # Title
        title = QLabel("Kronos 2026.1")
        title.setFont(QFont("Noto Sans", 18, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Version
        version = QLabel("Version 2026.1")
        version.setStyleSheet("color: #6a7280;")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)

        # Tagline
        tagline = QLabel("Open science. No license fees.")
        tagline.setStyleSheet("color: #8a92a2; font-style: italic;")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(tagline)

        layout.addSpacing(8)

        # Info block
        info_text = (
            f"Author: Youssef Ben Letaifa\n"
            f"Organization: Intelligent Systems\n"
            f"License: MIT\n"
            f"Python {sys.version.split()[0]} · PyQt6 {PYQT_VERSION_STR} · "
            f"{platform.system()} {platform.release()}"
        )
        info = QLabel(info_text)
        info.setStyleSheet("color: #8a92a2; font-size: 11px;")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addStretch(1)

        # Close button
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

    @staticmethod
    def _draw_logo() -> QPixmap:
        """Draw a simple Kronos 'K' logo."""
        size = 64
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # Blue square
        painter.setPen(QPen(QColor("#1a6fff"), 2))
        painter.setBrush(QColor("#0d2340"))
        painter.drawRoundedRect(4, 4, size - 8, size - 8, 10, 10)
        # K letter
        font = QFont("Segoe UI", 32, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#1a6fff"))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "K")
        painter.end()
        return pixmap
