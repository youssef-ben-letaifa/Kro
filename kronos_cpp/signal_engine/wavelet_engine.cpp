#include "signal_engine/wavelet_engine.h"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstddef>
#include <numeric>
#include <string>
#include <vector>

namespace kronos::signal_engine {
namespace {

struct WaveletFilters {
    std::vector<double> lo_d;
    std::vector<double> hi_d;
    std::vector<double> lo_r;
    std::vector<double> hi_r;
};

WaveletFilters make_filters(WaveletType wavelet) {
    // Coefficients are standard orthogonal filter taps.
    switch (wavelet) {
    case WaveletType::Db4: {
        const std::vector<double> lo_d = {
            -0.010597401785069032,
            0.0328830116668852,
            0.030841381835560764,
            -0.18703481171888114,
            -0.027983769416859854,
            0.6308807679298587,
            0.7148465705529157,
            0.23037781330885523,
        };
        std::vector<double> hi_d(lo_d.size());
        for (std::size_t i = 0; i < lo_d.size(); ++i) {
            const std::size_t r = lo_d.size() - 1U - i;
            hi_d[i] = ((i % 2U) ? -1.0 : 1.0) * lo_d[r];
        }
        std::vector<double> lo_r(lo_d.rbegin(), lo_d.rend());
        std::vector<double> hi_r(hi_d.rbegin(), hi_d.rend());
        return {lo_d, hi_d, lo_r, hi_r};
    }
    case WaveletType::Sym8: {
        const std::vector<double> lo_d = {
            -0.003382415951359,
            -0.000542132331791,
            0.031695087811493,
            0.007607487324917,
            -0.143294238350809,
            -0.061273359067658,
            0.481359651258372,
            0.777185751700523,
            0.364441894835331,
            -0.051945838107875,
            -0.027219029917056,
            0.049137179673607,
            0.003808752013894,
            -0.014952258337048,
            -0.000302920514724,
            0.001889950332759,
        };
        std::vector<double> hi_d(lo_d.size());
        for (std::size_t i = 0; i < lo_d.size(); ++i) {
            const std::size_t r = lo_d.size() - 1U - i;
            hi_d[i] = ((i % 2U) ? -1.0 : 1.0) * lo_d[r];
        }
        std::vector<double> lo_r(lo_d.rbegin(), lo_d.rend());
        std::vector<double> hi_r(hi_d.rbegin(), hi_d.rend());
        return {lo_d, hi_d, lo_r, hi_r};
    }
    case WaveletType::Haar:
    default: {
        const double s = std::sqrt(0.5);
        return {{s, s}, {-s, s}, {s, s}, {s, -s}};
    }
    }
}

std::vector<double> periodic_convolve_downsample(
    const std::vector<double>& signal,
    const std::vector<double>& filter
) {
    const std::size_t n = signal.size();
    if (n == 0) {
        return {};
    }
    const std::size_t out_n = n / 2U;
    std::vector<double> out(out_n, 0.0);

    for (std::size_t i = 0; i < out_n; ++i) {
        double acc = 0.0;
        const std::size_t center = (2U * i) % n;
        for (std::size_t k = 0; k < filter.size(); ++k) {
            const std::size_t idx = (center + n - (k % n)) % n;
            acc += filter[k] * signal[idx];
        }
        out[i] = acc;
    }
    return out;
}

std::vector<double> periodic_convolve_upsample(
    const std::vector<double>& signal,
    const std::vector<double>& filter,
    std::size_t out_n
) {
    std::vector<double> up(out_n, 0.0);
    if (signal.empty() || out_n == 0) {
        return up;
    }

    for (std::size_t i = 0; i < signal.size(); ++i) {
        const std::size_t up_idx = (2U * i) % out_n;
        for (std::size_t k = 0; k < filter.size(); ++k) {
            const std::size_t idx = (up_idx + k) % out_n;
            up[idx] += signal[i] * filter[k];
        }
    }
    return up;
}

std::vector<double> periodic_convolve_stride(
    const std::vector<double>& signal,
    const std::vector<double>& filter,
    std::size_t stride
) {
    const std::size_t n = signal.size();
    std::vector<double> out(n, 0.0);
    if (n == 0) {
        return out;
    }

    for (std::size_t i = 0; i < n; ++i) {
        double acc = 0.0;
        for (std::size_t k = 0; k < filter.size(); ++k) {
            const std::size_t idx = (i + n - ((k * stride) % n)) % n;
            acc += filter[k] * signal[idx];
        }
        out[i] = acc;
    }
    return out;
}

} // namespace

DwtResult WaveletEngine::dwt(
    const std::vector<double>& signal,
    WaveletType wavelet,
    std::size_t levels
) {
    DwtResult out;
    if (signal.empty()) {
        return out;
    }

    const auto filters = make_filters(wavelet);
    out.approximation = signal;

    levels = std::max<std::size_t>(1, levels);
    for (std::size_t level = 0; level < levels; ++level) {
        if (out.approximation.size() < 4) {
            break;
        }
        auto approx_next = periodic_convolve_downsample(out.approximation, filters.lo_d);
        auto detail = periodic_convolve_downsample(out.approximation, filters.hi_d);
        out.details.push_back(detail);
        out.approximation = std::move(approx_next);
    }

    return out;
}

DwtResult WaveletEngine::modwt(
    const std::vector<double>& signal,
    WaveletType wavelet,
    std::size_t levels
) {
    DwtResult out;
    if (signal.empty()) {
        return out;
    }

    const auto filters = make_filters(wavelet);
    out.approximation = signal;
    levels = std::max<std::size_t>(1, levels);

    for (std::size_t level = 0; level < levels; ++level) {
        const std::size_t stride = 1U << level;
        auto detail = periodic_convolve_stride(out.approximation, filters.hi_d, stride);
        auto approx_next = periodic_convolve_stride(out.approximation, filters.lo_d, stride);
        out.details.push_back(detail);
        out.approximation = std::move(approx_next);
    }

    return out;
}

std::vector<double> WaveletEngine::passband_energy(const DwtResult& decomposition) {
    std::vector<double> energy;
    energy.reserve(decomposition.details.size() + 1U);

    for (const auto& level : decomposition.details) {
        const double e = std::inner_product(level.begin(), level.end(), level.begin(), 0.0);
        energy.push_back(e);
    }

    const double approx_energy = std::inner_product(
        decomposition.approximation.begin(),
        decomposition.approximation.end(),
        decomposition.approximation.begin(),
        0.0
    );
    energy.push_back(approx_energy);

    return energy;
}

std::vector<double> WaveletEngine::reconstruct_selected(
    const DwtResult& decomposition,
    const std::vector<bool>& include_details,
    WaveletType wavelet
) {
    if (decomposition.approximation.empty()) {
        return {};
    }

    const auto filters = make_filters(wavelet);
    std::vector<double> approx = decomposition.approximation;

    for (std::size_t level = decomposition.details.size(); level > 0; --level) {
        const auto& detail_level = decomposition.details[level - 1U];
        std::vector<double> detail = detail_level;
        const bool include = level - 1U < include_details.size() ? include_details[level - 1U] : true;
        if (!include) {
            std::fill(detail.begin(), detail.end(), 0.0);
        }

        const std::size_t out_n = std::max<std::size_t>(detail.size(), approx.size()) * 2U;
        auto a_up = periodic_convolve_upsample(approx, filters.lo_r, out_n);
        auto d_up = periodic_convolve_upsample(detail, filters.hi_r, out_n);
        approx.resize(out_n, 0.0);
        for (std::size_t i = 0; i < out_n; ++i) {
            approx[i] = a_up[i] + d_up[i];
        }
    }

    return approx;
}

WaveletType WaveletEngine::wavelet_from_string(const std::string& name) {
    std::string key;
    key.reserve(name.size());
    for (const char c : name) {
        key.push_back(static_cast<char>(std::tolower(static_cast<unsigned char>(c))));
    }
    if (key == "haar") {
        return WaveletType::Haar;
    }
    if (key == "db4") {
        return WaveletType::Db4;
    }
    if (key == "sym8") {
        return WaveletType::Sym8;
    }
    return WaveletType::Haar;
}

std::string WaveletEngine::wavelet_to_string(WaveletType wavelet) {
    switch (wavelet) {
    case WaveletType::Haar:
        return "haar";
    case WaveletType::Db4:
        return "db4";
    case WaveletType::Sym8:
        return "sym8";
    }
    return "haar";
}

} // namespace kronos::signal_engine
