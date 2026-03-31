#include "signal_engine/measurements_engine.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <limits>
#include <numeric>
#include <vector>

#include "signal_engine/fft_engine.h"

namespace kronos::signal_engine {
namespace {

double safe_db(double num, double den) {
    if (num <= 0.0 || den <= 0.0) {
        return 0.0;
    }
    return 10.0 * std::log10(num / den);
}

} // namespace

MeasurementResult MeasurementsEngine::compute(
    const std::vector<double>& signal,
    double fs,
    std::size_t roi_start,
    std::size_t roi_end
) {
    MeasurementResult out;
    if (signal.empty()) {
        return out;
    }

    const std::size_t begin = std::min(roi_start, signal.size() - 1U);
    const std::size_t end =
        (roi_end == 0 || roi_end > signal.size()) ? signal.size() : std::max(roi_end, begin + 1U);

    const std::vector<double> x(signal.begin() + static_cast<long>(begin), signal.begin() + static_cast<long>(end));
    if (x.empty()) {
        return out;
    }

    auto [min_it, max_it] = std::minmax_element(x.begin(), x.end());
    out.min_value = *min_it;
    out.max_value = *max_it;
    out.peak_to_peak = out.max_value - out.min_value;

    const double sum = std::accumulate(x.begin(), x.end(), 0.0);
    out.mean = sum / static_cast<double>(x.size());

    double sq_sum = 0.0;
    for (double v : x) {
        sq_sum += v * v;
    }
    out.rms = std::sqrt(sq_sum / static_cast<double>(x.size()));

    std::vector<double> centered = x;
    for (double& v : centered) {
        v -= out.mean;
    }

    const auto fft = FftEngine::compute_fft(centered, fs > 0.0 ? fs : 1.0, WindowType::Hann, 8.0, 0);
    if (fft.power.size() < 3U) {
        return out;
    }

    std::size_t fundamental_idx = 1U;
    double fundamental_power = fft.power[1];
    for (std::size_t i = 2; i < fft.power.size(); ++i) {
        if (fft.power[i] > fundamental_power) {
            fundamental_power = fft.power[i];
            fundamental_idx = i;
        }
    }

    double harmonics_power = 0.0;
    for (std::size_t h = 2; h <= 8; ++h) {
        const std::size_t idx = fundamental_idx * h;
        if (idx >= fft.power.size()) {
            break;
        }
        harmonics_power += fft.power[idx];
    }

    double total_power = 0.0;
    for (std::size_t i = 1; i < fft.power.size(); ++i) {
        total_power += fft.power[i];
    }
    const double noise_power = std::max(1e-18, total_power - fundamental_power - harmonics_power);
    const double distortion_noise = std::max(1e-18, total_power - fundamental_power);

    out.thd = 100.0 * std::sqrt(std::max(0.0, harmonics_power)) / std::max(1e-12, std::sqrt(fundamental_power));
    out.snr = safe_db(fundamental_power, noise_power);
    out.sinad = safe_db(fundamental_power, distortion_noise);

    double spur = 0.0;
    for (std::size_t i = 1; i < fft.power.size(); ++i) {
        if (i == fundamental_idx) {
            continue;
        }
        spur = std::max(spur, fft.power[i]);
    }
    out.sfdr = 10.0 * std::log10(std::max(1e-18, fundamental_power) / std::max(1e-18, spur));

    return out;
}

} // namespace kronos::signal_engine
