#include "signal_engine/stft_engine.h"

#include <algorithm>
#include <cstddef>
#include <vector>

namespace kronos::signal_engine {

StftResult StftEngine::compute(
    const std::vector<double>& signal,
    double fs,
    std::size_t nperseg,
    std::size_t noverlap,
    std::size_t nfft,
    WindowType window,
    double kaiser_beta
) {
    StftResult out;
    if (signal.empty() || fs <= 0.0) {
        return out;
    }

    if (nperseg == 0) {
        nperseg = std::min<std::size_t>(256, signal.size());
    }
    nperseg = std::max<std::size_t>(8, std::min(nperseg, signal.size()));
    if (noverlap >= nperseg) {
        noverlap = nperseg / 2U;
    }

    const std::size_t hop = std::max<std::size_t>(1, nperseg - noverlap);
    const std::size_t actual_nfft = nfft == 0 ? nperseg : nfft;

    for (std::size_t start = 0; start + nperseg <= signal.size(); start += hop) {
        std::vector<double> frame(nperseg);
        for (std::size_t i = 0; i < nperseg; ++i) {
            frame[i] = signal[start + i];
        }

        const auto spec = FftEngine::compute_fft(frame, fs, window, kaiser_beta, actual_nfft);
        if (out.freq_bins.empty()) {
            out.freq_bins = spec.frequencies;
        }
        out.time_bins.push_back((static_cast<double>(start) + 0.5 * static_cast<double>(nperseg)) / fs);
        out.magnitude_matrix.push_back(spec.magnitude);
    }

    return out;
}

} // namespace kronos::signal_engine
