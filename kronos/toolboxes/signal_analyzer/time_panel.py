"""Time-domain panel for Signal Analyzer."""

from __future__ import annotations

import numpy as np

from .plot_panel import PlotPanel
from .signal_store import SignalStore


class TimePanel(PlotPanel):
    """Plots visible signals in the time domain."""

    def __init__(self, store: SignalStore, parent=None) -> None:
        self._show_legend = True
        self._line_width = 1.5
        super().__init__("Time", store, parent)

    def set_show_legend(self, enabled: bool) -> None:
        """Toggle legend visibility."""
        self._show_legend = bool(enabled)
        self.refresh()

    def set_line_width(self, width: float) -> None:
        """Set trace linewidth for plotted signals."""
        self._line_width = max(0.6, float(width))
        self.refresh()

    def _draw_contents(self) -> None:
        visible = self._store.visible_signals()
        if not visible:
            super()._draw_contents()
            return

        series_map: dict[str, np.ndarray] = {}
        x_reference: np.ndarray | None = None

        for record in visible:
            x = record.start_time + np.arange(record.data.size, dtype=np.float64) / max(record.fs, 1e-9)
            self.axes.plot(
                x,
                record.data,
                color=record.color.name(),
                linewidth=self._line_width,
                label=record.name,
            )
            series_map[record.name] = record.data
            if x_reference is None or x.size > x_reference.size:
                x_reference = x

        self.axes.set_title("Time Domain", color="#e0e0e0", fontsize=10)
        self.axes.set_xlabel("Time (s)", color="#a0a0b0")
        self.axes.set_ylabel(visible[0].unit or "Amplitude", color="#a0a0b0")
        if self._show_legend:
            self.axes.legend(loc="upper right", fontsize=8, facecolor="#101827", edgecolor="#334155")

        roi = self._store.roi()
        if roi is not None:
            self.axes.axvspan(roi[0], roi[1], color="#4cc9f0", alpha=0.15)

        if x_reference is not None:
            self.cursors.set_series(x_reference, series_map)
