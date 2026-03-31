"""Display grid manager for plot panels."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtWidgets import QGridLayout, QWidget

from .persistence_panel import PersistencePanel
from .preprocessing_engine import PreprocessingEngine
from .scalogram_panel import ScalogramPanel
from .signal_store import SignalStore
from .spectrogram_panel import SpectrogramPanel
from .spectrum_panel import SpectrumPanel
from .time_panel import TimePanel


@dataclass(slots=True)
class GridShape:
    """Represents rows and columns for panel layout."""

    rows: int
    cols: int


class DisplayManager(QWidget):
    """Owns panel instances and arranges them in a configurable grid."""

    def __init__(self, store: SignalStore, engine: PreprocessingEngine, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._store = store
        self._engine = engine

        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)

        self._grid_shape = GridShape(1, 1)
        self._panels: list[QWidget] = []

        self.set_grid(1, 1)
        self.set_views(["time"])

    def set_grid(self, rows: int, cols: int) -> None:
        """Set grid dimensions for panel arrangement."""
        self._grid_shape = GridShape(max(1, rows), max(1, cols))
        self._relayout()

    def set_views(self, views: list[str]) -> None:
        """Rebuild panel list with requested view types."""
        self.clear()
        for view in views:
            panel = self._create_panel(view)
            self._panels.append(panel)
        self._relayout()

    def clear(self) -> None:
        """Remove and delete all panel widgets."""
        for panel in self._panels:
            panel.setParent(None)
            panel.deleteLater()
        self._panels.clear()

    def panels(self) -> list[QWidget]:
        """Return current panel widgets."""
        return list(self._panels)

    def _create_panel(self, view: str) -> QWidget:
        key = view.strip().lower()
        if key == "time":
            return TimePanel(self._store, self)
        if key == "spectrum":
            return SpectrumPanel(self._store, self._engine, self)
        if key in {"time-frequency", "spectrogram"}:
            return SpectrogramPanel(self._store, self._engine, self)
        if key == "persistence":
            return PersistencePanel(self._store, self._engine, self)
        if key == "scalogram":
            return ScalogramPanel(self._store, self._engine, self)
        return TimePanel(self._store, self)

    def _relayout(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

        if not self._panels:
            return

        max_cells = self._grid_shape.rows * self._grid_shape.cols
        panels = self._panels[:max_cells]

        for idx, panel in enumerate(panels):
            row = idx // self._grid_shape.cols
            col = idx % self._grid_shape.cols
            self._layout.addWidget(panel, row, col)

        for row in range(self._grid_shape.rows):
            self._layout.setRowStretch(row, 1)
        for col in range(self._grid_shape.cols):
            self._layout.setColumnStretch(col, 1)
