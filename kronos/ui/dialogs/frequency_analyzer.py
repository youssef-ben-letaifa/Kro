"""Frequency/signal analysis dialog."""

from __future__ import annotations

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from kronos.native import create_waveform_view


class FrequencyAnalyzerDialog(QDialog):
    """FFT / PSD signal analysis dialog."""

    code_insert_requested = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Frequency Analyzer")
        self.resize(900, 600)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_controls())
        splitter.addWidget(self._build_plot())
        splitter.setSizes([280, 620])

        layout = QVBoxLayout(self)
        layout.addWidget(splitter)

    def _build_controls(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        sig_box = QGroupBox("Signal Generator")
        sig_form = QFormLayout(sig_box)

        self.sig_type = QComboBox()
        self.sig_type.addItems(["Composite Sine", "Chirp", "Square Wave", "Noise"])
        sig_form.addRow("Type:", self.sig_type)

        self.freq1 = QDoubleSpinBox()
        self.freq1.setRange(0.1, 500.0)
        self.freq1.setValue(5.0)
        self.freq1.setSuffix(" Hz")
        sig_form.addRow("Freq 1:", self.freq1)

        self.freq2 = QDoubleSpinBox()
        self.freq2.setRange(0.1, 500.0)
        self.freq2.setValue(50.0)
        self.freq2.setSuffix(" Hz")
        sig_form.addRow("Freq 2:", self.freq2)

        self.amp1 = QDoubleSpinBox()
        self.amp1.setRange(0.01, 100.0)
        self.amp1.setValue(1.0)
        sig_form.addRow("Amplitude 1:", self.amp1)

        self.amp2 = QDoubleSpinBox()
        self.amp2.setRange(0.0, 100.0)
        self.amp2.setValue(0.3)
        sig_form.addRow("Amplitude 2:", self.amp2)

        self.fs_spin = QDoubleSpinBox()
        self.fs_spin.setRange(10.0, 10000.0)
        self.fs_spin.setValue(1000.0)
        self.fs_spin.setSuffix(" Hz")
        sig_form.addRow("Sample Rate:", self.fs_spin)

        self.duration = QDoubleSpinBox()
        self.duration.setRange(0.1, 60.0)
        self.duration.setValue(2.0)
        self.duration.setSuffix(" s")
        sig_form.addRow("Duration:", self.duration)

        layout.addWidget(sig_box)

        filt_box = QGroupBox("Butterworth Filter")
        filt_form = QFormLayout(filt_box)

        self.filter_enable = QCheckBox("Apply filter")
        self.filter_enable.setChecked(False)
        filt_form.addRow(self.filter_enable)

        self.filter_type = QComboBox()
        self.filter_type.addItems(["lowpass", "highpass", "bandpass"])
        filt_form.addRow("Type:", self.filter_type)

        self.filter_order = QSpinBox()
        self.filter_order.setRange(1, 10)
        self.filter_order.setValue(4)
        filt_form.addRow("Order:", self.filter_order)

        self.filter_cutoff = QDoubleSpinBox()
        self.filter_cutoff.setRange(0.1, 5000.0)
        self.filter_cutoff.setValue(20.0)
        self.filter_cutoff.setSuffix(" Hz")
        filt_form.addRow("Cutoff:", self.filter_cutoff)

        self.filter_cutoff2 = QDoubleSpinBox()
        self.filter_cutoff2.setRange(0.1, 5000.0)
        self.filter_cutoff2.setValue(100.0)
        self.filter_cutoff2.setSuffix(" Hz")
        filt_form.addRow("Cutoff Hi:", self.filter_cutoff2)

        layout.addWidget(filt_box)

        display_box = QGroupBox("Display")
        disp_form = QFormLayout(display_box)
        self.show_psd = QCheckBox("Show PSD (Power)")
        self.show_psd.setChecked(False)
        disp_form.addRow(self.show_psd)
        self.log_freq = QCheckBox("Log frequency axis")
        self.log_freq.setChecked(False)
        disp_form.addRow(self.log_freq)
        self.peak_annotate = QCheckBox("Annotate peaks")
        self.peak_annotate.setChecked(True)
        disp_form.addRow(self.peak_annotate)
        layout.addWidget(display_box)

        analyze_btn = QPushButton("Analyze")
        insert_btn = QPushButton("Insert Code")
        analyze_btn.clicked.connect(self._analyze)
        insert_btn.clicked.connect(self._insert_code)
        layout.addWidget(analyze_btn)
        layout.addWidget(insert_btn)
        layout.addStretch(1)

        self._info = QLabel("")
        self._info.setWordWrap(True)
        self._info.setStyleSheet("color: #6a7280; font-size: 10px;")
        layout.addWidget(self._info)

        return panel

    def _build_plot(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        self._waveform_widget = create_waveform_view(container)
        if self._waveform_widget is not None:
            self._waveform_widget.setMinimumHeight(150)
            layout.addWidget(self._waveform_widget)
        self.figure = Figure(facecolor="#08090e")
        self.canvas = FigureCanvasQTAgg(self.figure)
        layout.addWidget(self.canvas)
        return container

    def _generate_signal(self):
        fs = self.fs_spin.value()
        dur = self.duration.value()
        t = np.arange(0, dur, 1.0 / fs)

        sig_type = self.sig_type.currentText()
        f1, f2 = self.freq1.value(), self.freq2.value()
        a1, a2 = self.amp1.value(), self.amp2.value()

        if sig_type == "Composite Sine":
            signal = a1 * np.sin(2 * np.pi * f1 * t) + a2 * np.sin(2 * np.pi * f2 * t)
        elif sig_type == "Chirp":
            from scipy.signal import chirp
            signal = a1 * chirp(t, f0=f1, t1=dur, f1=f2, method="linear")
        elif sig_type == "Square Wave":
            from scipy.signal import square
            signal = a1 * square(2 * np.pi * f1 * t)
        elif sig_type == "Noise":
            signal = a1 * np.random.randn(len(t))
        else:
            signal = np.sin(2 * np.pi * f1 * t)

        return t, signal, fs

    def _apply_filter(self, signal, fs):
        from scipy.signal import butter, filtfilt
        ftype = self.filter_type.currentText()
        order = self.filter_order.value()
        nyq = fs / 2.0
        low = self.filter_cutoff.value() / nyq
        high = self.filter_cutoff2.value() / nyq

        if ftype == "bandpass":
            b, a = butter(order, [low, high], btype="bandpass")
        elif ftype == "highpass":
            b, a = butter(order, low, btype="highpass")
        else:
            b, a = butter(order, low, btype="lowpass")

        return filtfilt(b, a, signal)

    def _analyze(self) -> None:
        try:
            t, signal, fs = self._generate_signal()
        except Exception as exc:
            QMessageBox.warning(self, "Signal Error", str(exc))
            return

        filtered = None
        if self.filter_enable.isChecked():
            try:
                filtered = self._apply_filter(signal, fs)
            except Exception as exc:
                QMessageBox.warning(self, "Filter Error", str(exc))
                return

        display_signal = filtered if filtered is not None else signal
        if self._waveform_widget is not None:
            native_view = getattr(self._waveform_widget, "_native_view", None)
            if native_view is not None:
                try:
                    native_view.set_data(t.tolist(), display_signal.tolist())
                except Exception:
                    pass

        # FFT
        n = len(display_signal)
        freqs = np.fft.rfftfreq(n, d=1.0 / fs)
        fft_vals = np.abs(np.fft.rfft(display_signal)) / n

        self.figure.clear()

        # Time domain
        ax1 = self.figure.add_subplot(211)
        ax1.set_facecolor("#08090e")
        ax1.plot(t, signal, color="#3a4050", linewidth=0.8, label="Raw")
        if filtered is not None:
            ax1.plot(t, filtered, color="#1a6fff", linewidth=1.2, label="Filtered")
        else:
            ax1.plot(t, display_signal, color="#1a6fff", linewidth=1.2)
        ax1.set_xlabel("Time (s)", color="#6a7280")
        ax1.set_ylabel("Amplitude", color="#6a7280")
        ax1.set_title("Time Domain", color="#c8ccd4", fontsize=10)
        if filtered is not None:
            ax1.legend(facecolor="#0e1117", edgecolor="#1e2128",
                       labelcolor="#c8ccd4", fontsize=8)

        # Frequency domain
        ax2 = self.figure.add_subplot(212)
        ax2.set_facecolor("#08090e")

        if self.show_psd.isChecked():
            psd = fft_vals ** 2
            ax2.plot(freqs[1:], psd[1:], color="#e5c07b", linewidth=1.2)
            ax2.set_ylabel("Power", color="#6a7280")
            ax2.set_title("Power Spectral Density", color="#c8ccd4", fontsize=10)
        else:
            ax2.plot(freqs[1:], fft_vals[1:], color="#98c379", linewidth=1.2)
            ax2.set_ylabel("|X(f)|", color="#6a7280")
            ax2.set_title("FFT Magnitude", color="#c8ccd4", fontsize=10)

        if self.log_freq.isChecked():
            ax2.set_xscale("log")
        ax2.set_xlabel("Frequency (Hz)", color="#6a7280")

        # Annotate peaks
        if self.peak_annotate.isChecked() and len(fft_vals) > 3:
            mag = fft_vals[1:]
            threshold = np.max(mag) * 0.3
            peak_indices = []
            for i in range(1, len(mag) - 1):
                if mag[i] > mag[i - 1] and mag[i] > mag[i + 1] and mag[i] > threshold:
                    peak_indices.append(i)
            for idx in peak_indices[:5]:
                f_peak = freqs[idx + 1]
                m_peak = mag[idx]
                ax2.annotate(
                    f"{f_peak:.1f} Hz",
                    xy=(f_peak, m_peak),
                    xytext=(f_peak, m_peak * 1.15),
                    color="#e5c07b",
                    fontsize=8,
                    ha="center",
                    arrowprops=dict(arrowstyle="-", color="#e5c07b", lw=0.5),
                )

        for ax in (ax1, ax2):
            ax.tick_params(colors="#3a4050")
            for spine in ax.spines.values():
                spine.set_color("#1e2128")
            ax.grid(True, color="#1a1f2a", linewidth=0.5)

        self.figure.tight_layout()
        self.canvas.draw()

        # Info
        peak_freqs = [f"{freqs[i + 1]:.1f}" for i in (peak_indices[:5] if self.peak_annotate.isChecked() and len(fft_vals) > 3 else [])]
        self._info.setText(f"Peaks: {', '.join(peak_freqs) if peak_freqs else '—'}")

    def _insert_code(self) -> None:
        fs = self.fs_spin.value()
        dur = self.duration.value()
        f1 = self.freq1.value()
        f2 = self.freq2.value()
        a1 = self.amp1.value()
        a2 = self.amp2.value()
        code = (
            "import numpy as np\n"
            "import matplotlib.pyplot as plt\n"
            f"fs = {fs}\n"
            f"t = np.arange(0, {dur}, 1.0/fs)\n"
            f"x = {a1}*np.sin(2*np.pi*{f1}*t) + {a2}*np.sin(2*np.pi*{f2}*t)\n"
            "freqs = np.fft.rfftfreq(len(x), d=1.0/fs)\n"
            "fft_mag = np.abs(np.fft.rfft(x)) / len(x)\n"
            "fig, (ax1, ax2) = plt.subplots(2, 1)\n"
            "ax1.plot(t, x)\n"
            "ax1.set_title('Time Domain')\n"
            "ax2.plot(freqs[1:], fft_mag[1:])\n"
            "ax2.set_title('FFT Magnitude')\n"
            "plt.tight_layout()\n"
            "plt.show()\n"
        )
        self.code_insert_requested.emit(code)
