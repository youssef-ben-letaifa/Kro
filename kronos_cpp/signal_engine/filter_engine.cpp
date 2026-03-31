#include "signal_engine/filter_engine.h"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstddef>
#include <numeric>
#include <stdexcept>
#include <string>
#include <vector>

namespace kronos::signal_engine {
namespace {

constexpr double kPi = 3.14159265358979323846264338327950288;

double sinc(double x) {
    if (std::abs(x) < 1e-12) {
        return 1.0;
    }
    return std::sin(kPi * x) / (kPi * x);
}

std::vector<double> convolve(const std::vector<double>& a, const std::vector<double>& b) {
    std::vector<double> out(a.size() + b.size() - 1, 0.0);
    for (std::size_t i = 0; i < a.size(); ++i) {
        for (std::size_t j = 0; j < b.size(); ++j) {
            out[i + j] += a[i] * b[j];
        }
    }
    return out;
}

std::vector<double> apply_df2t(
    const std::vector<double>& b,
    const std::vector<double>& a,
    const std::vector<double>& signal
) {
    if (signal.empty()) {
        return {};
    }
    if (b.empty() || a.empty() || std::abs(a[0]) < 1e-15) {
        return signal;
    }

    const std::size_t order = std::max(b.size(), a.size()) - 1U;
    std::vector<double> bb = b;
    std::vector<double> aa = a;
    bb.resize(order + 1U, 0.0);
    aa.resize(order + 1U, 0.0);

    const double a0 = aa[0];
    for (double& v : bb) {
        v /= a0;
    }
    for (double& v : aa) {
        v /= a0;
    }

    std::vector<double> z(order, 0.0);
    std::vector<double> y(signal.size(), 0.0);

    for (std::size_t n = 0; n < signal.size(); ++n) {
        const double in = signal[n];
        double out = bb[0] * in;
        if (order > 0) {
            out += z[0];
        }
        for (std::size_t i = 1; i < order; ++i) {
            z[i - 1] = z[i] + bb[i] * in - aa[i] * out;
        }
        if (order > 0) {
            z[order - 1] = bb[order] * in - aa[order] * out;
        }
        y[n] = out;
    }
    return y;
}

DigitalFilter biquad_lowpass(double fs, double fc, double q) {
    const double omega = 2.0 * kPi * fc / fs;
    const double cosw = std::cos(omega);
    const double alpha = std::sin(omega) / (2.0 * q);

    const double b0 = (1.0 - cosw) * 0.5;
    const double b1 = 1.0 - cosw;
    const double b2 = (1.0 - cosw) * 0.5;
    const double a0 = 1.0 + alpha;
    const double a1 = -2.0 * cosw;
    const double a2 = 1.0 - alpha;

    return {{b0 / a0, b1 / a0, b2 / a0}, {1.0, a1 / a0, a2 / a0}};
}

DigitalFilter biquad_highpass(double fs, double fc, double q) {
    const double omega = 2.0 * kPi * fc / fs;
    const double cosw = std::cos(omega);
    const double alpha = std::sin(omega) / (2.0 * q);

    const double b0 = (1.0 + cosw) * 0.5;
    const double b1 = -(1.0 + cosw);
    const double b2 = (1.0 + cosw) * 0.5;
    const double a0 = 1.0 + alpha;
    const double a1 = -2.0 * cosw;
    const double a2 = 1.0 - alpha;

    return {{b0 / a0, b1 / a0, b2 / a0}, {1.0, a1 / a0, a2 / a0}};
}

DigitalFilter biquad_bandpass(double fs, double fc1, double fc2, double q_scale) {
    const double center = std::max(1e-6, (fc1 + fc2) * 0.5);
    const double bw = std::max(1e-6, fc2 - fc1);
    const double q = std::max(0.2, (center / bw) * q_scale);

    const double omega = 2.0 * kPi * center / fs;
    const double alpha = std::sin(omega) / (2.0 * q);
    const double cosw = std::cos(omega);

    const double b0 = alpha;
    const double b1 = 0.0;
    const double b2 = -alpha;
    const double a0 = 1.0 + alpha;
    const double a1 = -2.0 * cosw;
    const double a2 = 1.0 - alpha;

    return {{b0 / a0, b1 / a0, b2 / a0}, {1.0, a1 / a0, a2 / a0}};
}

DigitalFilter cascade(const DigitalFilter& stage, std::size_t repeats) {
    DigitalFilter out{{1.0}, {1.0}};
    for (std::size_t i = 0; i < std::max<std::size_t>(1, repeats); ++i) {
        out.b = convolve(out.b, stage.b);
        out.a = convolve(out.a, stage.a);
    }
    return out;
}

std::vector<double> spectral_inversion(const std::vector<double>& taps) {
    std::vector<double> out = taps;
    const std::size_t m = out.size() / 2U;
    for (double& v : out) {
        v = -v;
    }
    out[m] += 1.0;
    return out;
}

bool solve_linear(std::vector<std::vector<double>> a, std::vector<double> b, std::vector<double>& x) {
    const std::size_t n = a.size();
    if (n == 0 || b.size() != n) {
        return false;
    }
    for (std::size_t i = 0; i < n; ++i) {
        std::size_t pivot = i;
        for (std::size_t r = i + 1; r < n; ++r) {
            if (std::abs(a[r][i]) > std::abs(a[pivot][i])) {
                pivot = r;
            }
        }
        if (std::abs(a[pivot][i]) < 1e-12) {
            return false;
        }
        if (pivot != i) {
            std::swap(a[pivot], a[i]);
            std::swap(b[pivot], b[i]);
        }
        const double diag = a[i][i];
        for (std::size_t c = i; c < n; ++c) {
            a[i][c] /= diag;
        }
        b[i] /= diag;
        for (std::size_t r = 0; r < n; ++r) {
            if (r == i) {
                continue;
            }
            const double factor = a[r][i];
            if (std::abs(factor) < 1e-16) {
                continue;
            }
            for (std::size_t c = i; c < n; ++c) {
                a[r][c] -= factor * a[i][c];
            }
            b[r] -= factor * b[i];
        }
    }
    x = std::move(b);
    return true;
}

} // namespace

DigitalFilter FilterEngine::design_fir_window(
    FilterKind kind,
    std::size_t order,
    double fs,
    double fc1,
    double fc2,
    WindowType window,
    double kaiser_beta
) {
    if (fs <= 0.0) {
        throw std::invalid_argument("Sample rate must be positive.");
    }

    std::size_t taps = std::max<std::size_t>(order + 1U, 3U);
    if (taps % 2U == 0U) {
        ++taps;
    }
    const std::size_t mid = taps / 2U;

    const double nyquist = fs * 0.5;
    const double w1 = std::clamp(fc1 / nyquist, 1e-6, 0.999);
    const double w2 = std::clamp(fc2 / nyquist, 1e-6, 0.999);

    std::vector<double> h(taps, 0.0);

    auto lowpass = [&](double wc) {
        std::vector<double> lp(taps, 0.0);
        for (std::size_t n = 0; n < taps; ++n) {
            const double k = static_cast<double>(n) - static_cast<double>(mid);
            lp[n] = wc * sinc(wc * k);
        }
        return lp;
    };

    switch (kind) {
    case FilterKind::Lowpass:
        h = lowpass(w1);
        break;
    case FilterKind::Highpass:
        h = spectral_inversion(lowpass(w1));
        break;
    case FilterKind::Bandpass: {
        const double lo = std::min(w1, w2);
        const double hi = std::max(w1, w2);
        const auto lp_hi = lowpass(hi);
        const auto lp_lo = lowpass(lo);
        for (std::size_t i = 0; i < taps; ++i) {
            h[i] = lp_hi[i] - lp_lo[i];
        }
        break;
    }
    case FilterKind::Bandstop: {
        const double lo = std::min(w1, w2);
        const double hi = std::max(w1, w2);
        const auto lp_hi = lowpass(hi);
        const auto lp_lo = lowpass(lo);
        for (std::size_t i = 0; i < taps; ++i) {
            h[i] = lp_lo[i] + (i == mid ? 1.0 : 0.0) - lp_hi[i];
        }
        break;
    }
    }

    const auto win = FftEngine::window_coefficients(taps, window, kaiser_beta);
    for (std::size_t i = 0; i < taps; ++i) {
        h[i] *= win[i];
    }

    if (kind == FilterKind::Lowpass || kind == FilterKind::Bandstop) {
        const double sum = std::accumulate(h.begin(), h.end(), 0.0);
        if (std::abs(sum) > 1e-12) {
            for (double& v : h) {
                v /= sum;
            }
        }
    }

    return {h, {1.0}};
}

DigitalFilter FilterEngine::design_iir(
    const std::string& method,
    FilterKind kind,
    std::size_t order,
    double fs,
    double fc1,
    double fc2,
    double ripple_db,
    double attenuation_db
) {
    (void)ripple_db;
    (void)attenuation_db;

    if (fs <= 0.0) {
        throw std::invalid_argument("Sample rate must be positive.");
    }

    const std::string lower = [&]() {
        std::string out;
        out.reserve(method.size());
        for (char c : method) {
            out.push_back(static_cast<char>(std::tolower(static_cast<unsigned char>(c))));
        }
        return out;
    }();

    double q_scale = 1.0;
    if (lower.find("cheby") != std::string::npos) {
        q_scale = 0.85;
    } else if (lower.find("ellip") != std::string::npos) {
        q_scale = 0.7;
    }

    DigitalFilter stage;
    const double q = std::sqrt(0.5) * q_scale;
    switch (kind) {
    case FilterKind::Lowpass:
        stage = biquad_lowpass(fs, fc1, q);
        break;
    case FilterKind::Highpass:
        stage = biquad_highpass(fs, fc1, q);
        break;
    case FilterKind::Bandpass:
        stage = biquad_bandpass(fs, std::min(fc1, fc2), std::max(fc1, fc2), q_scale);
        break;
    case FilterKind::Bandstop: {
        // Band-stop approximation: lowpass + highpass in parallel is expensive,
        // so we approximate by cascading lowpass then highpass around the edges.
        auto lp = biquad_lowpass(fs, std::min(fc1, fc2), q);
        auto hp = biquad_highpass(fs, std::max(fc1, fc2), q);
        stage = {
            convolve(lp.b, hp.b),
            convolve(lp.a, hp.a),
        };
        break;
    }
    }

    const std::size_t repeats = std::max<std::size_t>(1U, (order + 1U) / 2U);
    return cascade(stage, repeats);
}

std::vector<double> FilterEngine::apply_filter(
    const DigitalFilter& filter,
    const std::vector<double>& signal,
    bool zero_phase
) {
    if (!zero_phase) {
        return apply_df2t(filter.b, filter.a, signal);
    }

    auto y = apply_df2t(filter.b, filter.a, signal);
    std::reverse(y.begin(), y.end());
    y = apply_df2t(filter.b, filter.a, y);
    std::reverse(y.begin(), y.end());
    return y;
}

std::vector<double> FilterEngine::smooth_moving_average(
    const std::vector<double>& signal,
    std::size_t span
) {
    if (signal.empty() || span <= 1) {
        return signal;
    }
    const std::size_t win = std::max<std::size_t>(2, span);
    std::vector<double> out(signal.size(), 0.0);
    std::vector<double> prefix(signal.size() + 1U, 0.0);
    for (std::size_t i = 0; i < signal.size(); ++i) {
        prefix[i + 1U] = prefix[i] + signal[i];
    }
    const std::size_t half = win / 2U;
    for (std::size_t i = 0; i < signal.size(); ++i) {
        const std::size_t lo = (i > half) ? i - half : 0;
        const std::size_t hi = std::min(signal.size(), i + half + 1U);
        out[i] = (prefix[hi] - prefix[lo]) / static_cast<double>(hi - lo);
    }
    return out;
}

std::vector<double> FilterEngine::smooth_gaussian(
    const std::vector<double>& signal,
    double sigma,
    std::size_t radius
) {
    if (signal.empty() || sigma <= 0.0) {
        return signal;
    }
    if (radius == 0) {
        radius = static_cast<std::size_t>(std::max(1.0, std::ceil(3.0 * sigma)));
    }

    const std::size_t width = radius * 2U + 1U;
    std::vector<double> kernel(width, 0.0);
    double sum = 0.0;
    for (std::size_t i = 0; i < width; ++i) {
        const double x = static_cast<double>(i) - static_cast<double>(radius);
        const double v = std::exp(-(x * x) / (2.0 * sigma * sigma));
        kernel[i] = v;
        sum += v;
    }
    for (double& v : kernel) {
        v /= sum;
    }

    std::vector<double> out(signal.size(), 0.0);
    for (std::size_t i = 0; i < signal.size(); ++i) {
        double acc = 0.0;
        double norm = 0.0;
        for (std::size_t k = 0; k < width; ++k) {
            const long idx = static_cast<long>(i) + static_cast<long>(k) - static_cast<long>(radius);
            if (idx < 0 || idx >= static_cast<long>(signal.size())) {
                continue;
            }
            acc += signal[static_cast<std::size_t>(idx)] * kernel[k];
            norm += kernel[k];
        }
        out[i] = norm > 0.0 ? acc / norm : signal[i];
    }
    return out;
}

std::vector<double> FilterEngine::smooth_savgol(
    const std::vector<double>& signal,
    std::size_t window_length,
    std::size_t polyorder
) {
    if (signal.empty() || window_length < 3 || polyorder == 0) {
        return signal;
    }
    if (window_length % 2U == 0U) {
        ++window_length;
    }
    polyorder = std::min(polyorder, window_length - 1U);

    const std::size_t half = window_length / 2U;
    std::vector<double> out(signal.size(), 0.0);

    for (std::size_t idx = 0; idx < signal.size(); ++idx) {
        std::vector<double> y(window_length, 0.0);
        std::vector<double> x(window_length, 0.0);

        for (std::size_t k = 0; k < window_length; ++k) {
            const long pos = static_cast<long>(idx) + static_cast<long>(k) - static_cast<long>(half);
            const long clamped = std::clamp(pos, 0L, static_cast<long>(signal.size()) - 1L);
            y[k] = signal[static_cast<std::size_t>(clamped)];
            x[k] = static_cast<double>(static_cast<long>(k) - static_cast<long>(half));
        }

        const std::size_t m = polyorder + 1U;
        std::vector<std::vector<double>> ata(m, std::vector<double>(m, 0.0));
        std::vector<double> aty(m, 0.0);

        for (std::size_t r = 0; r < window_length; ++r) {
            std::vector<double> powers(m, 1.0);
            for (std::size_t p = 1; p < m; ++p) {
                powers[p] = powers[p - 1U] * x[r];
            }
            for (std::size_t i = 0; i < m; ++i) {
                aty[i] += powers[i] * y[r];
                for (std::size_t j = 0; j < m; ++j) {
                    ata[i][j] += powers[i] * powers[j];
                }
            }
        }

        std::vector<double> coeffs;
        if (!solve_linear(ata, aty, coeffs) || coeffs.empty()) {
            out[idx] = y[half];
            continue;
        }
        out[idx] = coeffs[0];
    }

    return out;
}

FilterKind FilterEngine::filter_kind_from_string(const std::string& name) {
    std::string key;
    key.reserve(name.size());
    for (const char c : name) {
        key.push_back(static_cast<char>(std::tolower(static_cast<unsigned char>(c))));
    }
    if (key.find("high") != std::string::npos) {
        return FilterKind::Highpass;
    }
    if (key.find("bandstop") != std::string::npos || key.find("notch") != std::string::npos) {
        return FilterKind::Bandstop;
    }
    if (key.find("band") != std::string::npos) {
        return FilterKind::Bandpass;
    }
    return FilterKind::Lowpass;
}

} // namespace kronos::signal_engine
