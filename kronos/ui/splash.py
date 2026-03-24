"""# Kronos IDE — Animated splash screen and startup transitions."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QGraphicsOpacityEffect,
    QProgressBar,
    QSplashScreen,
    QVBoxLayout,
    QWidget,
)


class KronosSplashScreen(QSplashScreen):
    """Startup splash with animated progress and fade-out."""

    def __init__(self) -> None:
        pixmap = self._render_splash()
        super().__init__(pixmap)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity)
        self._fade_anim: QPropertyAnimation | None = None
        self._progress_anim: QPropertyAnimation | None = None

        overlay = QWidget(self)
        overlay.setGeometry(0, pixmap.height() - 56, pixmap.width(), 56)
        overlay.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(overlay)
        layout.setContentsMargins(40, 4, 40, 10)
        layout.setSpacing(6)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(6)
        self._progress.setStyleSheet(
            "QProgressBar { background: #161B22; border: 1px solid #30363D; border-radius: 3px; }"
            "QProgressBar::chunk { background: #58A6FF; border-radius: 3px; }"
        )
        layout.addWidget(self._progress)

    def set_progress(self, value: int, message: str) -> None:
        """Update progress value with animation and message."""
        value = max(0, min(100, int(value)))
        if self._progress_anim is not None:
            self._progress_anim.stop()
        self._progress_anim = QPropertyAnimation(self._progress, b"value", self)
        self._progress_anim.setDuration(220)
        self._progress_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._progress_anim.setStartValue(self._progress.value())
        self._progress_anim.setEndValue(value)
        self._progress_anim.start()

        self.showMessage(
            message,
            int(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter),
            QColor("#8B949E"),
        )

    def finish(self, widget) -> None:  # type: ignore[override]
        """Fade out before closing splash."""
        if self._fade_anim is not None:
            self._fade_anim.stop()
        self._fade_anim = QPropertyAnimation(self._opacity, b"opacity", self)
        self._fade_anim.setDuration(280)
        self._fade_anim.setStartValue(1.0)
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.finished.connect(lambda: super(KronosSplashScreen, self).finish(widget))
        self._fade_anim.start()

    @staticmethod
    def _render_splash() -> QPixmap:
        base_dir = Path(__file__).resolve().parents[2]
        for name in ("loading.png", "loading.jpg", "loading.jpeg"):
            custom = base_dir / name
            if custom.exists():
                pixmap = QPixmap(str(custom))
                if not pixmap.isNull():
                    max_w, max_h = 1100, 640
                    if pixmap.width() > max_w or pixmap.height() > max_h:
                        pixmap = pixmap.scaled(
                            max_w,
                            max_h,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    return pixmap

        width, height = 560, 320
        pixmap = QPixmap(width, height)
        pixmap.fill(QColor("#0D1117"))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        logo_size = 72
        cx = width // 2
        cy = 104
        painter.setPen(QPen(QColor("#58A6FF"), 2))
        painter.setBrush(QColor("#161B22"))
        painter.drawRoundedRect(cx - logo_size // 2, cy - logo_size // 2, logo_size, logo_size, 14, 14)

        font = QFont("Segoe UI", 34, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#58A6FF"))
        from PyQt6.QtCore import QRectF

        painter.drawText(
            QRectF(cx - logo_size // 2, cy - logo_size // 2, logo_size, logo_size),
            Qt.AlignmentFlag.AlignCenter,
            "K",
        )

        title_font = QFont("Inter", 22, QFont.Weight.DemiBold)
        painter.setFont(title_font)
        painter.setPen(QColor("#E6EDF3"))
        painter.drawText(QRectF(0, cy + 48, width, 34), Qt.AlignmentFlag.AlignCenter, "Kronos IDE")

        tag_font = QFont("Inter", 10)
        painter.setFont(tag_font)
        painter.setPen(QColor("#8B949E"))
        painter.drawText(
            QRectF(0, cy + 82, width, 24),
            Qt.AlignmentFlag.AlignCenter,
            "Loading engine... Starting kernel... Preparing workspace...",
        )

        painter.end()
        return pixmap
