// Kronos IDE — Native vehicle physics backend
#pragma once

#include <vector>

class VehicleDynamics3D final {
public:
    VehicleDynamics3D() = default;

    std::vector<double> step_bicycle(
        const std::vector<double>& state,
        double accel_cmd,
        double steer_cmd,
        double dt,
        double wheelbase,
        double max_steer,
        double max_steer_rate,
        double max_accel,
        double max_decel,
        double max_jerk,
        double rolling_resistance,
        double aero_drag) const;

    std::vector<double> step_rigidbody(
        const std::vector<double>& state,
        double fx,
        double fy,
        double fz,
        double tx,
        double ty,
        double tz,
        double mass,
        double inertia_x,
        double inertia_y,
        double inertia_z,
        double dt) const;
};
