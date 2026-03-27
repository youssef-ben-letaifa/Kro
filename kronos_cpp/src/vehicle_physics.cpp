// Kronos IDE — Native vehicle physics backend

#include "vehicle_physics.h"

#include <algorithm>
#include <cmath>

namespace {

double clamp_value(double v, double lo, double hi) {
    return std::max(lo, std::min(hi, v));
}

double wrap_angle(double angle) {
    constexpr double kPi = 3.14159265358979323846;
    constexpr double kTwoPi = 6.28318530717958647692;
    while (angle > kPi) {
        angle -= kTwoPi;
    }
    while (angle < -kPi) {
        angle += kTwoPi;
    }
    return angle;
}

}  // namespace

std::vector<double> VehicleDynamics3D::step_bicycle(
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
    double aero_drag) const {
    const double x = state.size() > 0 ? state[0] : 0.0;
    const double y = state.size() > 1 ? state[1] : 0.0;
    const double yaw = state.size() > 2 ? state[2] : 0.0;
    const double speed = state.size() > 3 ? state[3] : 0.0;
    const double accel = state.size() > 4 ? state[4] : 0.0;
    const double steer = state.size() > 5 ? state[5] : 0.0;

    const double h = std::max(dt, 1e-4);

    const double steer_target = clamp_value(steer_cmd, -max_steer, max_steer);
    const double steer_delta = clamp_value(steer_target - steer, -max_steer_rate * h, max_steer_rate * h);
    const double steer_next = clamp_value(steer + steer_delta, -max_steer, max_steer);

    const double accel_target = clamp_value(accel_cmd, -max_decel, max_accel);
    const double accel_delta = clamp_value(accel_target - accel, -max_jerk * h, max_jerk * h);
    const double accel_applied = accel + accel_delta;

    const double resistive = rolling_resistance * speed + aero_drag * speed * std::abs(speed);
    const double net_accel = accel_applied - resistive;

    const double lf = std::max(0.8, 0.5 * wheelbase);
    const double lr = std::max(0.8, wheelbase - lf);
    const double beta = std::atan2(lr * std::tan(steer_next), std::max(1e-6, lf + lr));

    const double speed_next = std::max(0.0, speed + net_accel * h);
    const double yaw_rate = speed_next * std::sin(beta) / std::max(1e-6, lr);
    const double yaw_next = wrap_angle(yaw + yaw_rate * h);

    const double vx = speed_next * std::cos(yaw + beta);
    const double vy = speed_next * std::sin(yaw + beta);
    const double x_next = x + vx * h;
    const double y_next = y + vy * h;

    return {x_next, y_next, yaw_next, speed_next, accel_applied, steer_next};
}

std::vector<double> VehicleDynamics3D::step_rigidbody(
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
    double dt) const {
    double x = state.size() > 0 ? state[0] : 0.0;
    double y = state.size() > 1 ? state[1] : 0.0;
    double z = state.size() > 2 ? state[2] : 0.0;
    double roll = state.size() > 3 ? state[3] : 0.0;
    double pitch = state.size() > 4 ? state[4] : 0.0;
    double yaw = state.size() > 5 ? state[5] : 0.0;
    double vx = state.size() > 6 ? state[6] : 0.0;
    double vy = state.size() > 7 ? state[7] : 0.0;
    double vz = state.size() > 8 ? state[8] : 0.0;
    double wx = state.size() > 9 ? state[9] : 0.0;
    double wy = state.size() > 10 ? state[10] : 0.0;
    double wz = state.size() > 11 ? state[11] : 0.0;

    const double h = std::max(dt, 1e-4);
    const double m = std::max(1e-6, mass);

    const double ax = fx / m;
    const double ay = fy / m;
    const double az = fz / m;

    const double alphax = tx / std::max(1e-6, inertia_x);
    const double alphay = ty / std::max(1e-6, inertia_y);
    const double alphaz = tz / std::max(1e-6, inertia_z);

    vx += ax * h;
    vy += ay * h;
    vz += az * h;

    wx += alphax * h;
    wy += alphay * h;
    wz += alphaz * h;

    // Mild damping to keep unconstrained integration bounded.
    const double linear_damping = clamp_value(1.0 - 0.02 * h, 0.0, 1.0);
    const double angular_damping = clamp_value(1.0 - 0.03 * h, 0.0, 1.0);
    vx *= linear_damping;
    vy *= linear_damping;
    vz *= linear_damping;
    wx *= angular_damping;
    wy *= angular_damping;
    wz *= angular_damping;

    x += vx * h;
    y += vy * h;
    z += vz * h;

    roll = wrap_angle(roll + wx * h);
    pitch = wrap_angle(pitch + wy * h);
    yaw = wrap_angle(yaw + wz * h);

    return {x, y, z, roll, pitch, yaw, vx, vy, vz, wx, wy, wz};
}
