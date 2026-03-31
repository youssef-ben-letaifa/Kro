#include "signal_engine/fft_engine.h"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <complex>
#include <cstddef>
#include <limits>
#include <numeric>
#include <stdexcept>

#ifdef KRONOS_USE_FFTW
#include <fftw3.h>
#endif

namespace kronos::signal_engine {
namespace {

constexpr double kPi = 3.14159265358979323846264338327950288;

std::size_t next_pow2(std::size_t value) {
    if (value == 0) {
        return 1;
    }
    std::size_t n = 1;
    while (n < value) {
        n <<= 1U;
    }
    return n;
}

bool is_pow2(std::size_t value) {
    return value != 0 && (value & (value - 1U)) == 0;
}

double bessel_i0(double x) {
    double sum = 1.0;
    double term = 1.0;
    const double half = x * 0.5;
    for (int k = 1; k < 32; ++k) {
        term *= (half * half) / (static_cast<double>(k) * static_cast<double>(k));
        sum += term;
        if (term < 1e-14 * sum) {
            break;
        }
    }
    return sum;
}

void fft_radix2_inplace(std::vector<std::complex<double>>& values) {
    const std::size_t n = values.size();
    if (!is_pow2(n)) {
        throw std::invalid_argument("FFT length must be power of two.");
    }

    std::size_t j = 0;
    for (std::size_t i = 1; i < n; ++i) {
        std::size_t bit = n >> 1U;
        while ((j & bit) != 0U) {
            j ^= bit;
            bit >>= 1U;
        }
        j ^= bit;
        if (i < j) {
            std::swap(values[i], values[j]);
        }
    }

    for (std::size_t len = 2; len <= n; len <<= 1U) {
        const double angle = -2.0 * kPi / static_cast<double>(len);
        const std::complex<double> wlen(std::cos(angle), std::sin(angle));
        for (std::size_t i = 0; i < n; i += len) {
            std::complex<double> w(1.0, 0.0);
            const std::size_t half = len >> 1U;
            for (std::size_t k = 0; k < half; ++k) {
                const std::complex<double> u = values[i + k];
                const std::complex<double> v = values[i + k + half] * w;
                values[i + k] = u + v;
                values[i + k + half] = u - v;
                w *= wlen;
            }
        }
    }
}

std::vector<std::complex<double>> fft_execute(std::vector<std::complex<double>> values) {
#ifdef KRONOS_USE_FFTW
    const int n = static_cast<int>(values.size());
    std::vector<std::complex<double>> out(values.size());
    fftw_plan plan = fftw_plan_dft_1d(
        n,
        reinterpret_cast<fftw_complex*>(values.data()),
        reinterpret_cast<fftw_complex*>(out.data()),
        FFTW_FORWARD,
        FFTW_ESTIMATE
    );
    if (plan == nullptr) {
        throw std::runtime_error("FFTW plan creation failed.");
    }
    fftw_execute(plan);
    fftw_destroy_plan(plan);
    return out;
#else
    fft_radix2_inplace(values);
    return values;
#endif
}

} // namespace

std::vector<double> FftEngine::window_coefficients(
    std::size_t n,
    WindowType window,
    double kaiser_beta
) {
    if (n == 0) {
        return {};
    }
    if (n == 1) {
        return {1.0};
    }

    std::vector<double> coeffs(n, 1.0);
    const double denom = static_cast<double>(n - 1);

    for (std::size_t i = 0; i < n; ++i) {
        const double x = static_cast<double>(i) / denom;
        const double phase = 2.0 * kPi * x;
        switch (window) {
        case WindowType::Rectangular:
            coeffs[i] = 1.0;
            break;
        case WindowType::Hann:
            coeffs[i] = 0.5 - 0.5 * std::cos(phase);
            break;
        case WindowType::Hamming:
            coeffs[i] = 0.54 - 0.46 * std::cos(phase);
            break;
        case WindowType::Blackman:
            coeffs[i] =
                0.42
                - 0.5 * std::cos(phase)
                + 0.08 * std::cos(2.0 * phase);
            break;
        case WindowType::Flattop:
            coeffs[i] =
                1.0
                - 1.93 * std::cos(phase)
                + 1.29 * std::cos(2.0 * phase)
                - 0.388 * std::cos(3.0 * phase)
                + 0.032 * std::cos(4.0 * phase);
            break;
        case WindowType::Kaiser: {
            const double r = 2.0 * x - 1.0;
            const double inside = std::max(0.0, 1.0 - r * r);
            coeffs[i] = bessel_i0(kaiser_beta * std::sqrt(inside)) / bessel_i0(kaiser_beta);
            break;
        }
        }
    }
    return coeffs;
}

FftResult FftEngine::compute_fft(
    const std::vector<double>& signal,
    double fs,
    WindowType window,
    double kaiser_beta,
    std::size_t nfft
) {
    if (signal.empty() || fs <= 0.0) {
        return {};
    }

    const std::size_t requested_n = nfft == 0 ? signal.size() : nfft;
    const std::size_t fft_n = next_pow2(requested_n);
    std::vector<std::complex<double>> x(fft_n, {0.0, 0.0});

    const std::size_t copy_n = std::min(signal.size(), fft_n);
    const auto window_vals = window_coefficients(copy_n, window, kaiser_beta);
    for (std::size_t i = 0; i < copy_n; ++i) {
        x[i] = std::complex<double>(signal[i] * window_vals[i], 0.0);
    }

    const auto spectrum = fft_execute(std::move(x));

    const std::size_t half = fft_n / 2U + 1U;
    FftResult result;
    result.frequencies.resize(half);
    result.magnitude.resize(half);
    result.power.resize(half);

    const double scale = 1.0 / static_cast<double>(copy_n);
    for (std::size_t i = 0; i < half; ++i) {
        const double freq = static_cast<double>(i) * fs / static_cast<double>(fft_n);
        double mag = std::abs(spectrum[i]) * scale;
        if (i != 0 && i != half - 1) {
            mag *= 2.0;
        }
        result.frequencies[i] = freq;
        result.magnitude[i] = mag;
        result.power[i] = mag * mag;
    }

    return result;
}

FftResult FftEngine::welch_psd(
    const std::vector<double>& signal,
    double fs,
    std::size_t nperseg,
    std::size_t noverlap,
    std::size_t nfft,
    WindowType window,
    double kaiser_beta
) {
    if (signal.empty() || fs <= 0.0) {
        return {};
    }
    if (nperseg == 0) {
        nperseg = std::min<std::size_t>(256, signal.size());
    }
    nperseg = std::min(nperseg, signal.size());
    if (nperseg < 8) {
        return compute_fft(signal, fs, window, kaiser_beta, nfft);
    }

    if (noverlap >= nperseg) {
        noverlap = nperseg / 2U;
    }
    const std::size_t step = std::max<std::size_t>(1, nperseg - noverlap);
    const std::size_t fft_n = next_pow2(nfft == 0 ? nperseg : nfft);

    const auto w = window_coefficients(nperseg, window, kaiser_beta);
    const double u = std::accumulate(
        w.begin(),
        w.end(),
        0.0,
        [](double acc, double v) { return acc + v * v; }
    );
    const double norm = (u > 0.0) ? (1.0 / (fs * u)) : 1.0;

    const std::size_t half = fft_n / 2U + 1U;
    std::vector<double> psd(half, 0.0);
    std::size_t segments = 0;

    for (std::size_t start = 0; start + nperseg <= signal.size(); start += step) {
        std::vector<double> segment(nperseg);
        for (std::size_t i = 0; i < nperseg; ++i) {
            segment[i] = signal[start + i] * w[i];
        }
        const auto frame = compute_fft(segment, fs, WindowType::Rectangular, 0.0, fft_n);
        for (std::size_t i = 0; i < half; ++i) {
            psd[i] += frame.power[i] * norm;
        }
        ++segments;
    }

    if (segments == 0) {
        return {};
    }

    FftResult result;
    result.frequencies.resize(half);
    result.magnitude.resize(half);
    result.power.resize(half);
    for (std::size_t i = 0; i < half; ++i) {
        result.frequencies[i] = static_cast<double>(i) * fs / static_cast<double>(fft_n);
        result.power[i] = psd[i] / static_cast<double>(segments);
        result.magnitude[i] = std::sqrt(std::max(0.0, result.power[i]));
    }
    return result;
}

WindowType FftEngine::window_from_string(const std::string& name) {
    std::string key;
    key.reserve(name.size());
    for (const char c : name) {
        key.push_back(static_cast<char>(std::tolower(static_cast<unsigned char>(c))));
    }
    if (key == "rect" || key == "rectangular") {
        return WindowType::Rectangular;
    }
    if (key == "hann" || key == "hanning") {
        return WindowType::Hann;
    }
    if (key == "hamming") {
        return WindowType::Hamming;
    }
    if (key == "blackman") {
        return WindowType::Blackman;
    }
    if (key == "flattop" || key == "flat-top") {
        return WindowType::Flattop;
    }
    if (key == "kaiser") {
        return WindowType::Kaiser;
    }
    return WindowType::Hann;
}

std::string FftEngine::window_to_string(WindowType window) {
    switch (window) {
    case WindowType::Rectangular:
        return "rectangular";
    case WindowType::Hann:
        return "hann";
    case WindowType::Hamming:
        return "hamming";
    case WindowType::Blackman:
        return "blackman";
    case WindowType::Flattop:
        return "flattop";
    case WindowType::Kaiser:
        return "kaiser";
    }
    return "hann";
}

PersistenceSpectrum::PersistenceSpectrum(
    std::size_t freq_bins,
    std::size_t magnitude_bins,
    double max_frequency,
    double max_magnitude
)
    : freq_bins_(std::max<std::size_t>(freq_bins, 2)),
      magnitude_bins_(std::max<std::size_t>(magnitude_bins, 2)),
      max_frequency_(std::max(1e-9, max_frequency)),
      max_magnitude_(std::max(1e-12, max_magnitude)),
      counts_(freq_bins_ * magnitude_bins_, 0),
      samples_(0) {
}

void PersistenceSpectrum::clear() {
    std::fill(counts_.begin(), counts_.end(), 0);
    samples_ = 0;
}

void PersistenceSpectrum::accumulate(
    const std::vector<double>& frequencies,
    const std::vector<double>& magnitudes
) {
    const std::size_t n = std::min(frequencies.size(), magnitudes.size());
    if (n == 0) {
        return;
    }
    for (std::size_t i = 0; i < n; ++i) {
        const double fn = std::clamp(frequencies[i] / max_frequency_, 0.0, 1.0);
        const double mn = std::clamp(magnitudes[i] / max_magnitude_, 0.0, 1.0);
        const std::size_t fx = std::min(freq_bins_ - 1, static_cast<std::size_t>(fn * static_cast<double>(freq_bins_ - 1)));
        const std::size_t my = std::min(magnitude_bins_ - 1, static_cast<std::size_t>(mn * static_cast<double>(magnitude_bins_ - 1)));
        counts_[my * freq_bins_ + fx] += 1;
    }
    samples_ += static_cast<std::uint64_t>(n);
}

std::vector<double> PersistenceSpectrum::density() const {
    std::vector<double> out(counts_.size(), 0.0);
    if (samples_ == 0) {
        return out;
    }
    const double inv = 1.0 / static_cast<double>(samples_);
    for (std::size_t i = 0; i < counts_.size(); ++i) {
        out[i] = static_cast<double>(counts_[i]) * inv;
    }
    return out;
}

} // namespace kronos::signal_engine
