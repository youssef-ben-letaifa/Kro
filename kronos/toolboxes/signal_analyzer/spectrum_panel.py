"""Frequency spectrum panel for Signal Analyzer."""

from __future__ import annotations

import numpy as np

from .plot_panel import PlotPanel
from .preprocessing_engine import PreprocessingEngine
from .signal_store import SignalStore


class SpectrumPanel(PlotPanel):
    """Displays one-sided FFT or PSD spectrum for selected signal."""

    def __init__(self, store: SignalStore, engine: PreprocessingEngine, parent=None) -> None:
        self._engine = engine
        self._use_db = True
        self._show_psd = False
        super().__init__("Spectrum", store, parent)

    def set_db_scale(self, enabled: bool) -> None:
        """Toggle dB amplitude scale."""
        self._use_db = bool(enabled)
        self.refresh()

    def set_psd_mode(self, enabled: bool) -> None:
        """Toggle PSD mode versus FFT magnitude mode."""
        self._show_psd = bool(enabled)
        self.refresh()

    def _draw_contents(self) -> None:
        record = self.selected_signal()
        if record is None:
            super()._draw_contents()
            return

        if self._show_psd:
            spec = self._engine.compute_psd_welch(record.data, record.fs)
            y = np.asarray(spec.power, dtype=np.float64)
            label = "PSD"
        else:
            spec = self._engine.compute_fft_spectrum(record.data, record.fs)
            y = np.asarray(spec.magnitude, dtype=np.float64)
            label = "Magnitude"

        x = np.asarray(spec.freq, dtype=np.float64)
        if x.size == 0 or y.size == 0:
            super()._draw_contents()
            return

        if self._use_db:
            y_plot = 20.0 * np.log10(np.maximum(y, 1e-12))
            ylabel = f"{label} (dB)"
        else:
            y_plot = y
            ylabel = label

        self.axes.plot(x, y_plot, color=record.color.name(), linewidth=1.4)
        self.axes.set_title(f"Spectrum - {record.name}", color="#cdd6f4", fontsize=10)
        self.axes.set_xlabel("Frequency (Hz)", color="#a6adc8")
        self.axes.set_ylabel(ylabel, color="#a6adc8")

        self.cursors.set_series(x, {record.name: y_plot})
