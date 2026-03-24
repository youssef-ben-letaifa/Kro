// Kronos IDE — pybind11 bindings for native Qt extensions

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <QBuffer>
#include <QByteArray>

#include "src/canvas_renderer.h"
#include "src/syntax_highlighter.h"
#include "src/waveform_renderer.h"

namespace py = pybind11;

PYBIND11_MODULE(kronos_native, m) {
    m.doc() = "Kronos native Qt extensions";

    py::class_<PythonHighlighter>(m, "PythonHighlighter")
        .def(py::init<std::uintptr_t>(), py::arg("document_ptr"));

    py::class_<WaveformView>(m, "WaveformView")
        .def(py::init<std::uintptr_t>(), py::arg("parent_ptr") = 0)
        .def("set_data", &WaveformView::setData, py::arg("x"), py::arg("y"))
        .def("clear", &WaveformView::clearData)
        .def("auto_scale", &WaveformView::autoScale)
        .def("set_grid_enabled", &WaveformView::setGridEnabled, py::arg("enabled"))
        .def("widget_ptr", &WaveformView::widgetPtr);

    py::class_<CanvasRenderer>(m, "CanvasRenderer")
        .def(py::init<>())
        .def("clear", &CanvasRenderer::clear)
        .def(
            "render_block",
            &CanvasRenderer::render_block,
            py::arg("id"),
            py::arg("x"),
            py::arg("y"),
            py::arg("w"),
            py::arg("h"),
            py::arg("label"),
            py::arg("color"))
        .def(
            "render_wire",
            &CanvasRenderer::render_wire,
            py::arg("x1"),
            py::arg("y1"),
            py::arg("x2"),
            py::arg("y2"),
            py::arg("animated"))
        .def("set_animation_phase", &CanvasRenderer::setAnimationPhase, py::arg("phase"))
        .def(
            "rasterize_png",
            [](const CanvasRenderer& renderer, int width, int height, const std::string& background) {
                const QImage image = renderer.rasterize(
                    width,
                    height,
                    QString::fromStdString(background));
                QByteArray bytes;
                QBuffer buffer(&bytes);
                buffer.open(QIODevice::WriteOnly);
                image.save(&buffer, "PNG");
                return py::bytes(bytes.constData(), bytes.size());
            },
            py::arg("width"),
            py::arg("height"),
            py::arg("background") = "#0D1117");
}
