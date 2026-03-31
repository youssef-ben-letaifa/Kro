"""Spectrogram (time-frequency) panel."""

from __future__ import annotations

import numpy as np

from .plot_panel import PlotPanel
from .preprocessing_engine import PreprocessingEngine
from .signal_store import SignalStore


class SpectrogramPanel(PlotPanel):
    """Displays STFT heatmap for selected signal."""

    def __init__(self, store: SignalStore, engine: PreprocessingEngine, parent=None) -> None:
        self._engine = engine
        self._colormap = "viridis"
        self._nperseg = 256
        self._noverlap = 192
        super().__init__("Spectrogram", store, parent)

    def set_colormap(self, cmap: str) -> None:
        """Set matplotlib colormap for spectrogram."""
        self._colormap = cmap
        self.refresh()

    def _draw_contents(self) -> None:
        record = self.selected_signal()
        if record is None:
            super()._draw_contents()
            return

        stft = self._engine.compute_stft(
            record.data,
            record.fs,
            nperseg=self._nperseg,
            noverlap=self._noverlap,
        )
        z = np.asarray(stft.magnitude, dtype=np.float64)
        if z.size == 0:
            super()._draw_contents()
            return

        t = np.asarray(stft.time_bins, dtype=np.float64)
        f = np.asarray(stft.freq_bins, dtype=np.float64)
        z_db = 20.0 * np.log10(np.maximum(z, 1e-12))

        extent = [float(t[0]) if t.size else 0.0, float(t[-1]) if t.size else 1.0, float(f[0]), float(f[-1])]
        image = self.axes.imshow(
            z_db,
            origin="lower",
            aspect="auto",
            extent=extent,
            cmap=self._colormap,
        )
        self.figure.colorbar(image, ax=self.axes, pad=0.01)

        self.axes.set_title(f"Spectrogram - {record.name}", color="#cdd6f4", fontsize=10)
        self.axes.set_xlabel("Time (s)", color="#a6adc8")
        self.axes.set_ylabel("Frequency (Hz)", color="#a6adc8")

        self.cursors.set_image(t, f, z_db)
