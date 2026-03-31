"""Base plot panel widget used by all Signal Analyzer views."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from .cursor_manager import CursorManager
from .signal_store import SignalStore


class PlotPanel(QWidget):
    """Base class that provides panel header, canvas, and store subscriptions."""

    request_close = pyqtSignal(QWidget)
    request_split = pyqtSignal(QWidget)

    def __init__(self, view_name: str, store: SignalStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_name = view_name
        self._store = store

        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(0, 0, 0, 0)
        self._root.setSpacing(0)

        self._header = QFrame()
        self._header.setObjectName("sa_panel_header")
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(8, 4, 8, 4)
        header_layout.setSpacing(6)

        self._title = QLabel(view_name)
        self._title.setObjectName("sa_panel_title")

        self._signal_combo = QComboBox()
        self._signal_combo.setMinimumWidth(140)
        self._signal_combo.currentIndexChanged.connect(self.refresh)

        self._btn_split = QPushButton("⊞")
        self._btn_split.setToolTip("Split panel")
        self._btn_split.setFixedWidth(28)
        self._btn_split.clicked.connect(lambda: self.request_split.emit(self))

        self._btn_close = QPushButton("✕")
        self._btn_close.setToolTip("Close panel")
        self._btn_close.setFixedWidth(28)
        self._btn_close.clicked.connect(lambda: self.request_close.emit(self))

        header_layout.addWidget(self._title)
        header_layout.addStretch(1)
        header_layout.addWidget(self._signal_combo)
        header_layout.addWidget(self._btn_split)
        header_layout.addWidget(self._btn_close)

        self.figure = Figure(figsize=(5.0, 3.0), dpi=100)
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvas(self.figure)

        self._root.addWidget(self._header)
        self._root.addWidget(self.canvas, 1)

        self.cursors = CursorManager()
        self.cursors.attach(self.axes)

        self._store.signal_added.connect(self._rebuild_signal_combo)
        self._store.signal_removed.connect(self._rebuild_signal_combo)
        self._store.signal_updated.connect(lambda _rec: self.refresh())
        self._store.selection_changed.connect(lambda _sid: self.refresh())
        self._store.roi_changed.connect(lambda _a, _b: self.refresh())

        self._rebuild_signal_combo()
        self.apply_dark_theme()

    def view_name(self) -> str:
        """Return panel view type name."""
        return self._view_name

    def selected_signal_id(self) -> str | None:
        """Return selected signal id from panel combo."""
        item_data = self._signal_combo.currentData()
        return str(item_data) if item_data else None

    def selected_signal(self):
        """Return selected signal record or store-selected fallback."""
        sid = self.selected_signal_id()
        if sid:
            record = self._store.get_signal(sid)
            if record is not None:
                return record
        return self._store.selected_signal()

    def apply_dark_theme(self) -> None:
        """Apply panel-local dark plotting style."""
        self.figure.patch.set_facecolor("#0d0d1a")
        self.axes.set_facecolor("#0d0d1a")
        self.axes.tick_params(colors="#a0a0b0")
        for spine in self.axes.spines.values():
            spine.set_color("#2a2a4a")
        self.axes.grid(True, color="#1e1e3a", alpha=0.5, linestyle="--", linewidth=0.7)

    def refresh(self) -> None:
        """Redraw panel contents."""
        self.axes.clear()
        self.apply_dark_theme()
        self._draw_contents()
        self.canvas.draw_idle()

    def _draw_contents(self) -> None:
        """Override in subclasses to render panel content."""
        self.axes.text(
            0.5,
            0.5,
            f"{self._view_name}\n(no data)",
            transform=self.axes.transAxes,
            ha="center",
            va="center",
            color="#a0a0b0",
        )

    def _rebuild_signal_combo(self, *_args) -> None:
        current = self.selected_signal_id()
        self._signal_combo.blockSignals(True)
        self._signal_combo.clear()
        for record in self._store.list_signals():
            self._signal_combo.addItem(record.name, record.id)
        if current is not None:
            idx = self._signal_combo.findData(current)
            if idx >= 0:
                self._signal_combo.setCurrentIndex(idx)
        self._signal_combo.blockSignals(False)
        self.refresh()
