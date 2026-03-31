#pragma once

#include <cstddef>
#include <complex>
#include <cstdint>
#include <string>
#include <vector>

namespace kronos::signal_engine {

enum class WindowType {
    Rectangular = 0,
    Hann,
    Hamming,
    Blackman,
    Flattop,
    Kaiser,
};

struct FftResult {
    std::vector<double> frequencies;
    std::vector<double> magnitude;
    std::vector<double> power;
};

class FftEngine {
public:
    static std::vector<double> window_coefficients(
        std::size_t n,
        WindowType window,
        double kaiser_beta = 14.0
    );

    static FftResult compute_fft(
        const std::vector<double>& signal,
        double fs,
        WindowType window = WindowType::Hann,
        double kaiser_beta = 14.0,
        std::size_t nfft = 0
    );

    static FftResult welch_psd(
        const std::vector<double>& signal,
        double fs,
        std::size_t nperseg = 256,
        std::size_t noverlap = 128,
        std::size_t nfft = 0,
        WindowType window = WindowType::Hann,
        double kaiser_beta = 14.0
    );

    static WindowType window_from_string(const std::string& name);
    static std::string window_to_string(WindowType window);
};

class PersistenceSpectrum {
public:
    PersistenceSpectrum(
        std::size_t freq_bins,
        std::size_t magnitude_bins,
        double max_frequency,
        double max_magnitude
    );

    void clear();

    void accumulate(
        const std::vector<double>& frequencies,
        const std::vector<double>& magnitudes
    );

    [[nodiscard]] std::vector<double> density() const;
    [[nodiscard]] std::size_t freq_bins() const { return freq_bins_; }
    [[nodiscard]] std::size_t magnitude_bins() const { return magnitude_bins_; }

private:
    std::size_t freq_bins_;
    std::size_t magnitude_bins_;
    double max_frequency_;
    double max_magnitude_;
    std::vector<std::uint64_t> counts_;
    std::uint64_t samples_;
};

} // namespace kronos::signal_engine
