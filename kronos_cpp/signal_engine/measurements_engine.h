#pragma once

#include <cstddef>
#include <vector>

namespace kronos::signal_engine {

struct MeasurementResult {
    double min_value = 0.0;
    double max_value = 0.0;
    double mean = 0.0;
    double rms = 0.0;
    double peak_to_peak = 0.0;
    double thd = 0.0;
    double snr = 0.0;
    double sinad = 0.0;
    double sfdr = 0.0;
};

class MeasurementsEngine {
public:
    static MeasurementResult compute(
        const std::vector<double>& signal,
        double fs,
        std::size_t roi_start = 0,
        std::size_t roi_end = 0
    );
};

} // namespace kronos::signal_engine
