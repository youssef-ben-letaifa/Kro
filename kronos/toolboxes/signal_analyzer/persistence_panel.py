"""Persistence spectrum panel."""

from __future__ import annotations

import numpy as np

from .plot_panel import PlotPanel
from .preprocessing_engine import PreprocessingEngine
from .signal_store import SignalStore


class PersistencePanel(PlotPanel):
    """Displays accumulated spectrum density over time."""

    def __init__(self, store: SignalStore, engine: PreprocessingEngine, parent=None) -> None:
        self._engine = engine
        super().__init__("Persistence", store, parent)

    def _draw_contents(self) -> None:
        record = self.selected_signal()
        if record is None:
            super()._draw_contents()
            return

        freq, mag_axis, density = self._engine.compute_persistence_spectrum(record.data, record.fs)
        if density.size == 0:
            super()._draw_contents()
            return

        extent = [float(freq[0]), float(freq[-1]), float(mag_axis[0]), float(mag_axis[-1])]
        image = self.axes.imshow(
            density,
            origin="lower",
            aspect="auto",
            extent=extent,
            cmap="hot",
        )
        self.figure.colorbar(image, ax=self.axes, pad=0.01)
        self.axes.set_title(f"Persistence Spectrum - {record.name}", color="#e0e0e0", fontsize=10)
        self.axes.set_xlabel("Frequency (Hz)", color="#a0a0b0")
        self.axes.set_ylabel("Magnitude", color="#a0a0b0")

        self.cursors.set_image(freq, mag_axis, density)
