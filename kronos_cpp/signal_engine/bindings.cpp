#include <cstddef>
#include <string>
#include <vector>

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "signal_engine/fft_engine.h"
#include "signal_engine/filter_engine.h"
#include "signal_engine/measurements_engine.h"
#include "signal_engine/stft_engine.h"
#include "signal_engine/wavelet_engine.h"

namespace py = pybind11;
using namespace kronos::signal_engine;

PYBIND11_MODULE(kronos_signal_engine, m) {
    m.doc() =
        "Kronos Signal Analyzer native DSP engine. "
        "If this module is unavailable, Python fallbacks are used.";

    py::enum_<WindowType>(m, "WindowType")
        .value("RECTANGULAR", WindowType::Rectangular)
        .value("HANN", WindowType::Hann)
        .value("HAMMING", WindowType::Hamming)
        .value("BLACKMAN", WindowType::Blackman)
        .value("FLATTOP", WindowType::Flattop)
        .value("KAISER", WindowType::Kaiser);

    py::enum_<FilterKind>(m, "FilterKind")
        .value("LOWPASS", FilterKind::Lowpass)
        .value("HIGHPASS", FilterKind::Highpass)
        .value("BANDPASS", FilterKind::Bandpass)
        .value("BANDSTOP", FilterKind::Bandstop);

    py::enum_<WaveletType>(m, "WaveletType")
        .value("HAAR", WaveletType::Haar)
        .value("DB4", WaveletType::Db4)
        .value("SYM8", WaveletType::Sym8);

    py::class_<FftResult>(m, "FftResult")
        .def(py::init<>())
        .def_readwrite("frequencies", &FftResult::frequencies)
        .def_readwrite("magnitude", &FftResult::magnitude)
        .def_readwrite("power", &FftResult::power);

    py::class_<StftResult>(m, "StftResult")
        .def(py::init<>())
        .def_readwrite("time_bins", &StftResult::time_bins)
        .def_readwrite("freq_bins", &StftResult::freq_bins)
        .def_readwrite("magnitude_matrix", &StftResult::magnitude_matrix);

    py::class_<DigitalFilter>(m, "DigitalFilter")
        .def(py::init<>())
        .def_readwrite("b", &DigitalFilter::b)
        .def_readwrite("a", &DigitalFilter::a);

    py::class_<DwtResult>(m, "DwtResult")
        .def(py::init<>())
        .def_readwrite("approximation", &DwtResult::approximation)
        .def_readwrite("details", &DwtResult::details);

    py::class_<MeasurementResult>(m, "MeasurementResult")
        .def(py::init<>())
        .def_readwrite("min_value", &MeasurementResult::min_value)
        .def_readwrite("max_value", &MeasurementResult::max_value)
        .def_readwrite("mean", &MeasurementResult::mean)
        .def_readwrite("rms", &MeasurementResult::rms)
        .def_readwrite("peak_to_peak", &MeasurementResult::peak_to_peak)
        .def_readwrite("thd", &MeasurementResult::thd)
        .def_readwrite("snr", &MeasurementResult::snr)
        .def_readwrite("sinad", &MeasurementResult::sinad)
        .def_readwrite("sfdr", &MeasurementResult::sfdr);

    py::class_<PersistenceSpectrum>(m, "PersistenceSpectrum")
        .def(py::init<std::size_t, std::size_t, double, double>())
        .def("clear", &PersistenceSpectrum::clear)
        .def("accumulate", &PersistenceSpectrum::accumulate)
        .def("density", &PersistenceSpectrum::density)
        .def("freq_bins", &PersistenceSpectrum::freq_bins)
        .def("magnitude_bins", &PersistenceSpectrum::magnitude_bins);

    m.def(
        "compute_fft",
        [](const std::vector<double>& signal,
           double fs,
           const std::string& window,
           double kaiser_beta,
           std::size_t nfft) {
            return FftEngine::compute_fft(
                signal,
                fs,
                FftEngine::window_from_string(window),
                kaiser_beta,
                nfft
            );
        },
        py::arg("signal"),
        py::arg("fs"),
        py::arg("window") = "hann",
        py::arg("kaiser_beta") = 14.0,
        py::arg("nfft") = 0
    );

    m.def(
        "welch_psd",
        [](const std::vector<double>& signal,
           double fs,
           std::size_t nperseg,
           std::size_t noverlap,
           std::size_t nfft,
           const std::string& window,
           double kaiser_beta) {
            return FftEngine::welch_psd(
                signal,
                fs,
                nperseg,
                noverlap,
                nfft,
                FftEngine::window_from_string(window),
                kaiser_beta
            );
        },
        py::arg("signal"),
        py::arg("fs"),
        py::arg("nperseg") = 256,
        py::arg("noverlap") = 128,
        py::arg("nfft") = 0,
        py::arg("window") = "hann",
        py::arg("kaiser_beta") = 14.0
    );

    m.def(
        "stft",
        [](const std::vector<double>& signal,
           double fs,
           std::size_t nperseg,
           std::size_t noverlap,
           std::size_t nfft,
           const std::string& window,
           double kaiser_beta) {
            return StftEngine::compute(
                signal,
                fs,
                nperseg,
                noverlap,
                nfft,
                FftEngine::window_from_string(window),
                kaiser_beta
            );
        },
        py::arg("signal"),
        py::arg("fs"),
        py::arg("nperseg") = 256,
        py::arg("noverlap") = 128,
        py::arg("nfft") = 0,
        py::arg("window") = "hann",
        py::arg("kaiser_beta") = 14.0
    );

    m.def(
        "design_fir_window",
        [](const std::string& kind,
           std::size_t order,
           double fs,
           double fc1,
           double fc2,
           const std::string& window,
           double kaiser_beta) {
            return FilterEngine::design_fir_window(
                FilterEngine::filter_kind_from_string(kind),
                order,
                fs,
                fc1,
                fc2,
                FftEngine::window_from_string(window),
                kaiser_beta
            );
        },
        py::arg("kind"),
        py::arg("order"),
        py::arg("fs"),
        py::arg("fc1"),
        py::arg("fc2") = 0.0,
        py::arg("window") = "hann",
        py::arg("kaiser_beta") = 8.0
    );

    m.def(
        "design_iir",
        [](const std::string& method,
           const std::string& kind,
           std::size_t order,
           double fs,
           double fc1,
           double fc2,
           double ripple_db,
           double attenuation_db) {
            return FilterEngine::design_iir(
                method,
                FilterEngine::filter_kind_from_string(kind),
                order,
                fs,
                fc1,
                fc2,
                ripple_db,
                attenuation_db
            );
        },
        py::arg("method"),
        py::arg("kind"),
        py::arg("order"),
        py::arg("fs"),
        py::arg("fc1"),
        py::arg("fc2") = 0.0,
        py::arg("ripple_db") = 1.0,
        py::arg("attenuation_db") = 40.0
    );

    m.def(
        "apply_filter",
        &FilterEngine::apply_filter,
        py::arg("filter"),
        py::arg("signal"),
        py::arg("zero_phase") = false
    );

    m.def("smooth_moving_average", &FilterEngine::smooth_moving_average, py::arg("signal"), py::arg("span"));
    m.def("smooth_gaussian", &FilterEngine::smooth_gaussian, py::arg("signal"), py::arg("sigma"), py::arg("radius") = 0);
    m.def("smooth_savgol", &FilterEngine::smooth_savgol, py::arg("signal"), py::arg("window_length"), py::arg("polyorder"));

    m.def(
        "dwt",
        [](const std::vector<double>& signal, const std::string& wavelet, std::size_t levels) {
            return WaveletEngine::dwt(signal, WaveletEngine::wavelet_from_string(wavelet), levels);
        },
        py::arg("signal"),
        py::arg("wavelet") = "haar",
        py::arg("levels") = 4
    );

    m.def(
        "modwt",
        [](const std::vector<double>& signal, const std::string& wavelet, std::size_t levels) {
            return WaveletEngine::modwt(signal, WaveletEngine::wavelet_from_string(wavelet), levels);
        },
        py::arg("signal"),
        py::arg("wavelet") = "haar",
        py::arg("levels") = 4
    );

    m.def(
        "passband_energy",
        &WaveletEngine::passband_energy,
        py::arg("decomposition")
    );

    m.def(
        "reconstruct_selected",
        [](const DwtResult& decomposition, const std::vector<bool>& include_details, const std::string& wavelet) {
            return WaveletEngine::reconstruct_selected(
                decomposition,
                include_details,
                WaveletEngine::wavelet_from_string(wavelet)
            );
        },
        py::arg("decomposition"),
        py::arg("include_details"),
        py::arg("wavelet") = "haar"
    );

    m.def(
        "compute_measurements",
        &MeasurementsEngine::compute,
        py::arg("signal"),
        py::arg("fs"),
        py::arg("roi_start") = 0,
        py::arg("roi_end") = 0
    );
}
