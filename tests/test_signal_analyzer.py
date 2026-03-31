from __future__ import annotations

import os
import unittest

import numpy as np
from PyQt6.QtWidgets import QApplication

from kronos.toolboxes.signal_analyzer.persistence_panel import PersistencePanel
from kronos.toolboxes.signal_analyzer.preprocessing_engine import PreprocessingEngine
from kronos.toolboxes.signal_analyzer.scalogram_panel import ScalogramPanel
from kronos.toolboxes.signal_analyzer.script_generator import ScriptGenerator, SessionExport
from kronos.toolboxes.signal_analyzer.signal_model import SignalRecord
from kronos.toolboxes.signal_analyzer.signal_store import SignalStore
from kronos.toolboxes.signal_analyzer.spectrogram_panel import SpectrogramPanel
from kronos.toolboxes.signal_analyzer.spectrum_panel import SpectrumPanel


class SignalAnalyzerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = PreprocessingEngine()

    def test_fft_sine_peak(self) -> None:
        fs = 1000.0
        t = np.arange(0.0, 2.0, 1.0 / fs)
        x = np.sin(2.0 * np.pi * 100.0 * t)

        spec = self.engine.compute_fft_spectrum(x, fs, window="hann", nfft=4096)
        idx = int(np.argmax(spec.magnitude[1:]) + 1)
        peak_hz = float(spec.freq[idx])
        self.assertAlmostEqual(peak_hz, 100.0, delta=1.0)

    def test_filter_lowpass_attenuation(self) -> None:
        fs = 2000.0
        t = np.arange(0.0, 2.0, 1.0 / fs)
        x = np.sin(2.0 * np.pi * 10.0 * t) + 0.8 * np.sin(2.0 * np.pi * 500.0 * t)

        filt = self.engine.design_filter(
            kind="lowpass",
            method="butterworth",
            order=8,
            fs=fs,
            fc1=100.0,
        )
        y = self.engine.apply_filter(x, filt, zero_phase=True)

        before = self.engine.compute_fft_spectrum(x, fs, nfft=4096)
        after = self.engine.compute_fft_spectrum(y, fs, nfft=4096)

        idx_500 = int(np.argmin(np.abs(before.freq - 500.0)))
        att_db = 20.0 * np.log10(max(after.magnitude[idx_500], 1e-12) / max(before.magnitude[idx_500], 1e-12))
        self.assertLess(att_db, -40.0)

    def test_stft_shape(self) -> None:
        fs = 1000.0
        x = np.random.default_rng(0).normal(size=4096)
        nperseg = 256
        noverlap = 128

        stft = self.engine.compute_stft(x, fs, nperseg=nperseg, noverlap=noverlap)
        self.assertGreater(stft.time_bins.size, 0)
        self.assertGreater(stft.freq_bins.size, 0)
        self.assertEqual(stft.magnitude.shape[0], stft.freq_bins.size)
        self.assertEqual(stft.magnitude.shape[1], stft.time_bins.size)

    def test_signal_store_add_remove(self) -> None:
        store = SignalStore()
        added: list[str] = []
        removed: list[str] = []

        store.signal_added.connect(lambda record: added.append(record.id))
        store.signal_removed.connect(lambda record_id: removed.append(record_id))

        record = SignalRecord.create(name="sig", data=np.arange(10, dtype=float), fs=1000.0)
        store.add_signal(record)
        self.assertEqual(len(store.list_signals()), 1)
        self.assertEqual(added, [record.id])

        store.remove_signal(record.id)
        self.assertEqual(len(store.list_signals()), 0)
        self.assertEqual(removed, [record.id])

    def test_measurements_rms(self) -> None:
        fs = 1000.0
        amp = 3.0
        t = np.arange(0.0, 1.0, 1.0 / fs)
        x = amp * np.sin(2.0 * np.pi * 20.0 * t)

        m = self.engine.compute_measurements(x, fs)
        expected = amp / np.sqrt(2.0)
        self.assertAlmostEqual(m.rms, expected, delta=0.01 * expected)

    def test_script_generator_output(self) -> None:
        record = SignalRecord.create(name="x", data=np.array([0.0, 1.0, 0.0]), fs=100.0)
        script = ScriptGenerator().generate_script(SessionExport([record]))

        compile(script, "generated_signal_analyzer.py", "exec")
        self.assertIn("import numpy as np", script)
        self.assertIn("from scipy import signal", script)

    def test_visual_panels_construct_and_refresh(self) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        app = QApplication.instance() or QApplication([])

        store = SignalStore()
        record = SignalRecord.create(
            name="demo",
            data=np.sin(2.0 * np.pi * 40.0 * np.arange(0.0, 1.0, 1.0 / 1000.0)),
            fs=1000.0,
        )
        store.add_signal(record)

        panels = [
            SpectrumPanel(store, self.engine),
            SpectrogramPanel(store, self.engine),
            ScalogramPanel(store, self.engine),
            PersistencePanel(store, self.engine),
        ]
        for panel in panels:
            panel.refresh()
            panel.deleteLater()
        app.processEvents()


if __name__ == "__main__":
    unittest.main()
