// Kronos IDE — standalone native physics bindings (no Qt dependencies)

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "vehicle_physics.h"

namespace py = pybind11;

PYBIND11_MODULE(kronos_physics, m) {
    m.doc() = "Kronos native vehicle physics backend";

    py::class_<VehicleDynamics3D>(m, "VehicleDynamics3D")
        .def(py::init<>())
        .def(
            "step_bicycle",
            &VehicleDynamics3D::step_bicycle,
            py::arg("state"),
            py::arg("accel_cmd"),
            py::arg("steer_cmd"),
            py::arg("dt"),
            py::arg("wheelbase"),
            py::arg("max_steer"),
            py::arg("max_steer_rate"),
            py::arg("max_accel"),
            py::arg("max_decel"),
            py::arg("max_jerk"),
            py::arg("rolling_resistance"),
            py::arg("aero_drag"))
        .def(
            "step_rigidbody",
            &VehicleDynamics3D::step_rigidbody,
            py::arg("state"),
            py::arg("fx"),
            py::arg("fy"),
            py::arg("fz"),
            py::arg("tx"),
            py::arg("ty"),
            py::arg("tz"),
            py::arg("mass"),
            py::arg("inertia_x"),
            py::arg("inertia_y"),
            py::arg("inertia_z"),
            py::arg("dt"));
}
