"""Splash screen for Kronos IDE startup."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QProgressBar, QSplashScreen, QVBoxLayout, QWidget


class KronosSplashScreen(QSplashScreen):
    """Startup splash screen with loading progress."""

    def __init__(self) -> None:
        pixmap = self._render_splash()
        super().__init__(pixmap)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        overlay = QWidget(self)
        overlay.setGeometry(0, pixmap.height() - 40, pixmap.width(), 40)
        overlay.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(overlay)
        layout.setContentsMargins(40, 0, 40, 12)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(4)
        self._progress.setStyleSheet(
            "QProgressBar { background: #1a1f2a; border: none; border-radius: 2px; }"
            "QProgressBar::chunk { background: #1a6fff; border-radius: 2px; }"
        )
        layout.addWidget(self._progress)

    def set_progress(self, value: int, message: str) -> None:
        """Update progress bar and message text."""
        self._progress.setValue(value)
        self.showMessage(
            message,
            int(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter),
            QColor("#6a7280"),
        )

    @staticmethod
    def _render_splash() -> QPixmap:
        """Render the splash screen pixmap."""
        base_dir = Path(__file__).resolve().parents[2]
        for name in ("loading.png", "loading.pjg", "loading.jpg", "loading.jpeg"):
            custom = base_dir / name
            if custom.exists():
                pixmap = QPixmap(str(custom))
                if not pixmap.isNull():
                    max_w, max_h = 1000, 600
                    if pixmap.width() > max_w or pixmap.height() > max_h:
                        pixmap = pixmap.scaled(
                            max_w,
                            max_h,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    return pixmap

        width, height = 480, 280
        pixmap = QPixmap(width, height)
        pixmap.fill(QColor("#080c14"))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Logo box
        logo_size = 64
        cx = width // 2
        cy = 90
        painter.setPen(QPen(QColor("#1a6fff"), 2))
        painter.setBrush(QColor("#0d2340"))
        painter.drawRoundedRect(
            cx - logo_size // 2, cy - logo_size // 2,
            logo_size, logo_size, 12, 12
        )

        # K letter
        font = QFont("Segoe UI", 32, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#1a6fff"))
        from PyQt6.QtCore import QRectF
        painter.drawText(
            QRectF(cx - logo_size // 2, cy - logo_size // 2, logo_size, logo_size),
            Qt.AlignmentFlag.AlignCenter,
            "K",
        )

        # Title
        title_font = QFont("Noto Sans", 20, QFont.Weight.Bold)
        painter.setFont(title_font)
        painter.setPen(QColor("#c8ccd4"))
        painter.drawText(
            QRectF(0, cy + 40, width, 30),
            Qt.AlignmentFlag.AlignCenter,
            "Kronos 2026.1",
        )

        # Tagline
        tag_font = QFont("Noto Sans", 10)
        painter.setFont(tag_font)
        painter.setPen(QColor("#4a5060"))
        painter.drawText(
            QRectF(0, cy + 72, width, 20),
            Qt.AlignmentFlag.AlignCenter,
            "Open science. No license fees.",
        )

        # Version
        ver_font = QFont("Noto Sans", 8)
        painter.setFont(ver_font)
        painter.setPen(QColor("#3a4050"))
        painter.drawText(
            QRectF(0, height - 54, width, 16),
            Qt.AlignmentFlag.AlignCenter,
            "2026.1",
        )

        painter.end()
        return pixmap
