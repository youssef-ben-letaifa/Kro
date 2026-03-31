#pragma once

#include <cstddef>
#include <string>
#include <vector>

namespace kronos::signal_engine {

enum class WaveletType {
    Haar = 0,
    Db4,
    Sym8,
};

struct DwtResult {
    std::vector<double> approximation;
    std::vector<std::vector<double>> details;
};

class WaveletEngine {
public:
    static DwtResult dwt(
        const std::vector<double>& signal,
        WaveletType wavelet,
        std::size_t levels
    );

    static DwtResult modwt(
        const std::vector<double>& signal,
        WaveletType wavelet,
        std::size_t levels
    );

    static std::vector<double> passband_energy(
        const DwtResult& decomposition
    );

    static std::vector<double> reconstruct_selected(
        const DwtResult& decomposition,
        const std::vector<bool>& include_details,
        WaveletType wavelet
    );

    static WaveletType wavelet_from_string(const std::string& name);
    static std::string wavelet_to_string(WaveletType wavelet);
};

} // namespace kronos::signal_engine
