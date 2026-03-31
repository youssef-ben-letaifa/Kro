#pragma once

#include <cstddef>
#include <vector>

#include "signal_engine/fft_engine.h"

namespace kronos::signal_engine {

struct StftResult {
    std::vector<double> time_bins;
    std::vector<double> freq_bins;
    std::vector<std::vector<double>> magnitude_matrix;
};

class StftEngine {
public:
    static StftResult compute(
        const std::vector<double>& signal,
        double fs,
        std::size_t nperseg = 256,
        std::size_t noverlap = 128,
        std::size_t nfft = 0,
        WindowType window = WindowType::Hann,
        double kaiser_beta = 14.0
    );
};

} // namespace kronos::signal_engine
