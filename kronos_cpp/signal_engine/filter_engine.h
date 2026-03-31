#pragma once

#include <cstddef>
#include <string>
#include <vector>

#include "signal_engine/fft_engine.h"

namespace kronos::signal_engine {

enum class FilterKind {
    Lowpass = 0,
    Highpass,
    Bandpass,
    Bandstop,
};

struct DigitalFilter {
    std::vector<double> b;
    std::vector<double> a;
};

class FilterEngine {
public:
    static DigitalFilter design_fir_window(
        FilterKind kind,
        std::size_t order,
        double fs,
        double fc1,
        double fc2,
        WindowType window,
        double kaiser_beta = 8.0
    );

    static DigitalFilter design_iir(
        const std::string& method,
        FilterKind kind,
        std::size_t order,
        double fs,
        double fc1,
        double fc2,
        double ripple_db,
        double attenuation_db
    );

    static std::vector<double> apply_filter(
        const DigitalFilter& filter,
        const std::vector<double>& signal,
        bool zero_phase = false
    );

    static std::vector<double> smooth_moving_average(
        const std::vector<double>& signal,
        std::size_t span
    );

    static std::vector<double> smooth_gaussian(
        const std::vector<double>& signal,
        double sigma,
        std::size_t radius = 0
    );

    static std::vector<double> smooth_savgol(
        const std::vector<double>& signal,
        std::size_t window_length,
        std::size_t polyorder
    );

    static FilterKind filter_kind_from_string(const std::string& name);
};

} // namespace kronos::signal_engine
