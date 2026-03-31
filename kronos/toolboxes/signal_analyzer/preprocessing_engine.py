"""Signal preprocessing and DSP operations with native fallback support."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from scipy import signal

try:
    import pywt  # type: ignore
except Exception:  # pragma: no cover
    pywt = None

try:
    from kronos.native import kronos_signal_engine as _native  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    _native = None

WindowName = Literal["rectangular", "hann", "hamming", "blackman", "flattop", "kaiser"]
FilterKind = Literal["lowpass", "highpass", "bandpass", "bandstop"]
FilterMethod = Literal["butterworth", "cheby1", "cheby2", "ellip", "fir-window"]


@dataclass(slots=True)
class SpectrumData:
    """Container for spectrum data arrays."""

    freq: np.ndarray
    magnitude: np.ndarray
    power: np.ndarray


@dataclass(slots=True)
class StftData:
    """Container for STFT outputs."""

    time_bins: np.ndarray
    freq_bins: np.ndarray
    magnitude: np.ndarray


@dataclass(slots=True)
class Measurements:
    """Container for statistical and spectral measurements."""

    min_value: float
    max_value: float
    mean: float
    rms: float
    peak_to_peak: float
    thd: float
    snr: float
    sinad: float
    sfdr: float


@dataclass(slots=True)
class DesignedFilter:
    """Container for IIR/FIR coefficients."""

    b: np.ndarray
    a: np.ndarray


class PreprocessingEngine:
    """Computes all preprocessing, spectra, smoothing, and measurements."""

    def __init__(self) -> None:
        self._persistence_accumulator: np.ndarray | None = None

    @property
    def native_available(self) -> bool:
        """Return whether native module is available."""
        return _native is not None

    def compute_fft_spectrum(
        self,
        data: np.ndarray,
        fs: float,
        *,
        window: WindowName = "hann",
        nfft: int | None = None,
        kaiser_beta: float = 14.0,
    ) -> SpectrumData:
        """Compute one-sided FFT magnitude and power spectrum."""
        x = np.asarray(data, dtype=np.float64).reshape(-1)
        if x.size == 0:
            return SpectrumData(np.array([]), np.array([]), np.array([]))

        if self.native_available:
            result = _native.compute_fft(x.tolist(), float(fs), window, float(kaiser_beta), int(nfft or 0))
            return SpectrumData(
                np.asarray(result.frequencies, dtype=np.float64),
                np.asarray(result.magnitude, dtype=np.float64),
                np.asarray(result.power, dtype=np.float64),
            )

        n = int(nfft or x.size)
        if n <= 0:
            n = x.size
        n = int(2 ** np.ceil(np.log2(max(1, n))))

        window_arr = self._window_values(window, x.size, kaiser_beta)
        xw = x * window_arr
        spec = np.fft.rfft(xw, n=n)
        mag = np.abs(spec) / max(1, x.size)
        if mag.size > 2:
            mag[1:-1] *= 2.0
        power = mag**2
        freq = np.fft.rfftfreq(n, d=1.0 / fs)
        return SpectrumData(freq, mag, power)

    def compute_psd_welch(
        self,
        data: np.ndarray,
        fs: float,
        *,
        nperseg: int = 256,
        noverlap: int = 128,
        nfft: int | None = None,
        window: WindowName = "hann",
        kaiser_beta: float = 14.0,
    ) -> SpectrumData:
        """Compute power spectral density using Welch method."""
        x = np.asarray(data, dtype=np.float64).reshape(-1)
        if x.size == 0:
            return SpectrumData(np.array([]), np.array([]), np.array([]))

        if self.native_available:
            result = _native.welch_psd(
                x.tolist(),
                float(fs),
                int(nperseg),
                int(noverlap),
                int(nfft or 0),
                window,
                float(kaiser_beta),
            )
            return SpectrumData(
                np.asarray(result.frequencies, dtype=np.float64),
                np.asarray(result.magnitude, dtype=np.float64),
                np.asarray(result.power, dtype=np.float64),
            )

        win = ("kaiser", kaiser_beta) if window == "kaiser" else window
        freq, power = signal.welch(
            x,
            fs=fs,
            window=win,
            nperseg=min(max(8, int(nperseg)), x.size),
            noverlap=min(int(noverlap), max(0, int(nperseg) - 1)),
            nfft=nfft,
            scaling="density",
            return_onesided=True,
        )
        return SpectrumData(np.asarray(freq), np.sqrt(np.maximum(power, 0.0)), np.asarray(power))

    def compute_stft(
        self,
        data: np.ndarray,
        fs: float,
        *,
        nperseg: int = 256,
        noverlap: int = 128,
        nfft: int | None = None,
        window: WindowName = "hann",
        kaiser_beta: float = 14.0,
    ) -> StftData:
        """Compute short-time Fourier transform magnitude map."""
        x = np.asarray(data, dtype=np.float64).reshape(-1)
        if x.size == 0:
            return StftData(np.array([]), np.array([]), np.zeros((0, 0)))

        if self.native_available:
            result = _native.stft(
                x.tolist(),
                float(fs),
                int(nperseg),
                int(noverlap),
                int(nfft or 0),
                window,
                float(kaiser_beta),
            )
            matrix = np.asarray(result.magnitude_matrix, dtype=np.float64)
            return StftData(
                time_bins=np.asarray(result.time_bins, dtype=np.float64),
                freq_bins=np.asarray(result.freq_bins, dtype=np.float64),
                magnitude=matrix.T if matrix.ndim == 2 else matrix,
            )

        win = ("kaiser", kaiser_beta) if window == "kaiser" else window
        freq, times, zxx = signal.stft(
            x,
            fs=fs,
            window=win,
            nperseg=min(max(8, int(nperseg)), x.size),
            noverlap=min(int(noverlap), max(0, int(nperseg) - 1)),
            nfft=nfft,
            boundary=None,
        )
        return StftData(np.asarray(times), np.asarray(freq), np.abs(zxx))

    def compute_persistence_spectrum(
        self,
        data: np.ndarray,
        fs: float,
        *,
        bins_freq: int = 256,
        bins_mag: int = 128,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Compute/accumulate persistence spectrum density."""
        stft = self.compute_stft(data, fs, nperseg=256, noverlap=192)
        if stft.magnitude.size == 0:
            return np.array([]), np.array([]), np.zeros((0, 0))

        freq = stft.freq_bins
        mag = stft.magnitude
        max_mag = float(np.max(mag)) if mag.size else 1.0
        hist = np.zeros((bins_mag, bins_freq), dtype=np.float64)

        for col in range(mag.shape[1]):
            vals = mag[:, col]
            f_idx = np.clip(((freq / max(freq[-1], 1e-9)) * (bins_freq - 1)).astype(int), 0, bins_freq - 1)
            m_idx = np.clip(((vals / max(max_mag, 1e-12)) * (bins_mag - 1)).astype(int), 0, bins_mag - 1)
            hist[m_idx, f_idx] += 1.0

        if self._persistence_accumulator is None or self._persistence_accumulator.shape != hist.shape:
            self._persistence_accumulator = hist
        else:
            self._persistence_accumulator += hist

        density = self._persistence_accumulator / max(np.sum(self._persistence_accumulator), 1.0)
        mag_axis = np.linspace(0.0, max_mag, bins_mag)
        freq_axis = np.linspace(0.0, freq[-1], bins_freq)
        return freq_axis, mag_axis, density

    def design_filter(
        self,
        *,
        kind: FilterKind,
        method: FilterMethod,
        order: int,
        fs: float,
        fc1: float,
        fc2: float | None = None,
        ripple_db: float = 1.0,
        attenuation_db: float = 40.0,
        fir_window: WindowName = "hann",
    ) -> DesignedFilter:
        """Design FIR or IIR filter using native or SciPy backend."""
        if self.native_available and method == "fir-window":
            native_filter = _native.design_fir_window(
                kind,
                int(order),
                float(fs),
                float(fc1),
                float(fc2 or 0.0),
                fir_window,
                8.0,
            )
            return DesignedFilter(np.asarray(native_filter.b), np.asarray(native_filter.a))

        if self.native_available and method != "fir-window":
            native_filter = _native.design_iir(
                method,
                kind,
                int(order),
                float(fs),
                float(fc1),
                float(fc2 or 0.0),
                float(ripple_db),
                float(attenuation_db),
            )
            return DesignedFilter(np.asarray(native_filter.b), np.asarray(native_filter.a))

        nyq = fs * 0.5
        low = max(1e-9, min(fc1 / nyq, 0.999))
        high = max(1e-9, min((fc2 or fc1) / nyq, 0.999))

        if method == "fir-window":
            numtaps = max(3, int(order) + 1)
            if numtaps % 2 == 0:
                numtaps += 1
            pass_zero = {
                "lowpass": "lowpass",
                "highpass": "highpass",
                "bandpass": False,
                "bandstop": True,
            }[kind]
            cutoff = low if kind in {"lowpass", "highpass"} else sorted([low, high])
            b = signal.firwin(numtaps, cutoff=cutoff, window=fir_window, pass_zero=pass_zero)
            return DesignedFilter(b=np.asarray(b), a=np.asarray([1.0]))

        btype = {
            "lowpass": "lowpass",
            "highpass": "highpass",
            "bandpass": "bandpass",
            "bandstop": "bandstop",
        }[kind]
        wp = low if kind in {"lowpass", "highpass"} else sorted([low, high])

        if method == "cheby1":
            b, a = signal.cheby1(order, ripple_db, wp, btype=btype)
        elif method == "cheby2":
            b, a = signal.cheby2(order, attenuation_db, wp, btype=btype)
        elif method == "ellip":
            b, a = signal.ellip(order, ripple_db, attenuation_db, wp, btype=btype)
        else:
            b, a = signal.butter(order, wp, btype=btype)

        return DesignedFilter(np.asarray(b, dtype=np.float64), np.asarray(a, dtype=np.float64))

    def apply_filter(
        self,
        data: np.ndarray,
        filt: DesignedFilter,
        *,
        zero_phase: bool = False,
    ) -> np.ndarray:
        """Apply a digital filter with optional zero-phase mode."""
        x = np.asarray(data, dtype=np.float64).reshape(-1)
        b = np.asarray(filt.b, dtype=np.float64)
        a = np.asarray(filt.a, dtype=np.float64)

        if self.native_available:
            native_filter = type("Filter", (), {"b": b.tolist(), "a": a.tolist()})()
            y = _native.apply_filter(native_filter, x.tolist(), bool(zero_phase))
            return np.asarray(y, dtype=np.float64)

        if zero_phase:
            return signal.filtfilt(b, a, x, method="gust")
        return signal.lfilter(b, a, x)

    def smooth(self, data: np.ndarray, method: str, *, span: int = 9, order: int = 3) -> np.ndarray:
        """Smooth signal with selected method."""
        x = np.asarray(data, dtype=np.float64).reshape(-1)
        method_key = method.lower().strip()

        if method_key in {"moving average", "moving_average", "ma"}:
            if self.native_available:
                return np.asarray(_native.smooth_moving_average(x.tolist(), int(span)), dtype=np.float64)
            kernel = np.ones(max(2, int(span))) / max(2, int(span))
            return np.convolve(x, kernel, mode="same")

        if method_key in {"gaussian", "gauss"}:
            sigma = max(0.1, span / 3.0)
            if self.native_available:
                return np.asarray(_native.smooth_gaussian(x.tolist(), float(sigma), 0), dtype=np.float64)
            kernel = signal.windows.gaussian(max(7, int(6 * sigma) | 1), std=sigma)
            kernel = kernel / np.sum(kernel)
            return np.convolve(x, kernel, mode="same")

        if method_key in {"savitzky-golay", "savgol", "sg"}:
            w = max(5, int(span) | 1)
            p = max(1, min(int(order), w - 1))
            if self.native_available:
                return np.asarray(_native.smooth_savgol(x.tolist(), int(w), int(p)), dtype=np.float64)
            return signal.savgol_filter(x, window_length=w, polyorder=p, mode="interp")

        if method_key in {"lowess", "robust lowess", "robust_lowess"}:
            # Lightweight fallback: Gaussian smoothing approximation.
            sigma = max(0.25, span / 4.0)
            kernel = signal.windows.gaussian(max(7, int(6 * sigma) | 1), std=sigma)
            kernel = kernel / np.sum(kernel)
            return np.convolve(x, kernel, mode="same")

        return x

    def compute_scalogram(
        self,
        data: np.ndarray,
        fs: float,
        *,
        wavelet: str = "morl",
        scales: np.ndarray | None = None,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Compute CWT scalogram using PyWavelets (or SciPy fallback)."""
        x = np.asarray(data, dtype=np.float64).reshape(-1)
        if x.size == 0:
            return np.array([]), np.array([]), np.zeros((0, 0))

        if scales is None:
            scales = np.arange(1, 128, dtype=np.float64)

        if pywt is not None:
            coef, freqs = pywt.cwt(x, scales, wavelet, sampling_period=1.0 / fs)
            return np.arange(x.size) / fs, np.asarray(freqs), np.abs(coef)

        if hasattr(signal, "cwt") and hasattr(signal, "morlet2"):
            widths = scales
            cwt = signal.cwt(x, signal.morlet2, widths, w=5.0)
            pseudo_freq = fs / np.maximum(widths, 1e-9)
            return np.arange(x.size) / fs, pseudo_freq, np.abs(cwt)

        # SciPy compatibility fallback for builds where `signal.cwt` is absent.
        nperseg = min(max(32, int(scales.size * 2)), x.size)
        noverlap = max(0, nperseg // 2)
        freq, times, zxx = signal.stft(
            x,
            fs=fs,
            nperseg=nperseg,
            noverlap=noverlap,
            boundary=None,
        )
        return np.asarray(times), np.asarray(freq), np.abs(zxx)

    def compute_measurements(
        self,
        data: np.ndarray,
        fs: float,
        *,
        roi: tuple[float, float] | None = None,
    ) -> Measurements:
        """Compute measurements over optional ROI."""
        x = np.asarray(data, dtype=np.float64).reshape(-1)
        if x.size == 0:
            return Measurements(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

        i0 = 0
        i1 = x.size
        if roi is not None:
            i0 = int(max(0, np.floor(roi[0] * fs)))
            i1 = int(min(x.size, np.ceil(roi[1] * fs)))
            if i1 <= i0:
                i0, i1 = 0, x.size
        seg = x[i0:i1]

        if self.native_available:
            m = _native.compute_measurements(seg.tolist(), float(fs), 0, 0)
            return Measurements(
                min_value=float(m.min_value),
                max_value=float(m.max_value),
                mean=float(m.mean),
                rms=float(m.rms),
                peak_to_peak=float(m.peak_to_peak),
                thd=float(m.thd),
                snr=float(m.snr),
                sinad=float(m.sinad),
                sfdr=float(m.sfdr),
            )

        min_value = float(np.min(seg))
        max_value = float(np.max(seg))
        mean = float(np.mean(seg))
        rms = float(np.sqrt(np.mean(seg**2)))
        peak_to_peak = max_value - min_value

        centered = seg - mean
        spec = np.fft.rfft(centered)
        power = np.abs(spec) ** 2
        if power.size < 3:
            return Measurements(min_value, max_value, mean, rms, peak_to_peak, 0.0, 0.0, 0.0, 0.0)

        idx = int(np.argmax(power[1:]) + 1)
        fundamental = float(power[idx])
        harmonics = 0.0
        for h in range(2, 9):
            h_idx = idx * h
            if h_idx >= power.size:
                break
            harmonics += float(power[h_idx])

        total = float(np.sum(power[1:]))
        noise = max(1e-18, total - fundamental - harmonics)
        dist_noise = max(1e-18, total - fundamental)
        spur = float(np.max(np.delete(power[1:], idx - 1))) if power.size > 2 else 1e-18

        thd = 100.0 * np.sqrt(max(harmonics, 0.0)) / max(np.sqrt(fundamental), 1e-12)
        snr = 10.0 * np.log10(max(fundamental, 1e-18) / noise)
        sinad = 10.0 * np.log10(max(fundamental, 1e-18) / dist_noise)
        sfdr = 10.0 * np.log10(max(fundamental, 1e-18) / max(spur, 1e-18))

        return Measurements(min_value, max_value, mean, rms, peak_to_peak, float(thd), float(snr), float(sinad), float(sfdr))

    @staticmethod
    def _window_values(window: WindowName, n: int, kaiser_beta: float) -> np.ndarray:
        if n <= 1:
            return np.ones(max(1, n), dtype=np.float64)
        if window == "rectangular":
            return np.ones(n, dtype=np.float64)
        if window == "hann":
            return np.hanning(n)
        if window == "hamming":
            return np.hamming(n)
        if window == "blackman":
            return np.blackman(n)
        if window == "flattop":
            return signal.windows.flattop(n)
        if window == "kaiser":
            return np.kaiser(n, beta=kaiser_beta)
        return np.hanning(n)
