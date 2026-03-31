"""Wavelet scalogram panel."""

from __future__ import annotations

import numpy as np

from .plot_panel import PlotPanel
from .preprocessing_engine import PreprocessingEngine
from .signal_store import SignalStore


class ScalogramPanel(PlotPanel):
    """Displays wavelet magnitude map for selected signal."""

    def __init__(self, store: SignalStore, engine: PreprocessingEngine, parent=None) -> None:
        self._engine = engine
        self._wavelet = "morl"
        self._cmap = "viridis"
        super().__init__("Scalogram", store, parent)

    def set_wavelet(self, wavelet: str) -> None:
        """Set wavelet name for CWT."""
        self._wavelet = wavelet
        self.refresh()

    def _draw_contents(self) -> None:
        record = self.selected_signal()
        if record is None:
            super()._draw_contents()
            return

        time_axis, freq_axis, mag = self._engine.compute_scalogram(
            record.data,
            record.fs,
            wavelet=self._wavelet,
        )
        if mag.size == 0:
            super()._draw_contents()
            return

        extent = [float(time_axis[0]), float(time_axis[-1]), float(freq_axis[-1]), float(freq_axis[0])]
        image = self.axes.imshow(
            np.abs(mag),
            origin="upper",
            aspect="auto",
            extent=extent,
            cmap=self._cmap,
        )
        self.figure.colorbar(image, ax=self.axes, pad=0.01)
        self.axes.set_title(f"Scalogram - {record.name}", color="#e0e0e0", fontsize=10)
        self.axes.set_xlabel("Time (s)", color="#a0a0b0")
        self.axes.set_ylabel("Pseudo-Frequency (Hz)", color="#a0a0b0")

        self.cursors.set_image(time_axis, freq_axis, np.abs(mag))
