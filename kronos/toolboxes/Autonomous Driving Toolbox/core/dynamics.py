"""Vehicle dynamics and low-level control models."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .common import VehicleState


def wrap_angle(angle: float) -> float:
    """Wrap angle to [-pi, pi]."""
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


@dataclass
class PID1D:
    """Simple PID controller with anti-windup."""

    kp: float
    ki: float
    kd: float
    min_output: float = -1.0
    max_output: float = 1.0
    integral: float = 0.0
    prev_error: float = 0.0

    def reset(self) -> None:
        self.integral = 0.0
        self.prev_error = 0.0

    def step(self, target: float, measurement: float, dt: float) -> float:
        error = float(target - measurement)
        self.integral += error * dt
        self.integral = float(np.clip(self.integral, self.min_output, self.max_output))
        derivative = (error - self.prev_error) / max(dt, 1e-6)
        output = self.kp * error + self.ki * self.integral + self.kd * derivative
        output = float(np.clip(output, self.min_output, self.max_output))
        self.prev_error = error
        return output


@dataclass
class VehicleDynamicsModel:
    """Bicycle-model dynamics with steering and jerk constraints."""

    max_steer: float = np.deg2rad(35.0)
    max_steer_rate: float = np.deg2rad(90.0)
    max_accel: float = 3.0
    max_decel: float = 8.0
    max_jerk: float = 8.0
    rolling_resistance: float = 0.05
    aero_drag: float = 0.015

    def step(self, state: VehicleState, accel_cmd: float, steer_cmd: float, dt: float) -> VehicleState:
        """Advance one integration step."""
        dt = max(float(dt), 1e-4)
        next_state = state.copy()

        # Steering first-order dynamics with rate limit.
        steer_cmd = float(np.clip(steer_cmd, -self.max_steer, self.max_steer))
        steer_delta = np.clip(steer_cmd - state.steer, -self.max_steer_rate * dt, self.max_steer_rate * dt)
        next_state.steer = float(np.clip(state.steer + steer_delta, -self.max_steer, self.max_steer))

        # Acceleration command with jerk and physical limits.
        accel_cmd = float(np.clip(accel_cmd, -self.max_decel, self.max_accel))
        accel_delta = np.clip(accel_cmd - state.accel, -self.max_jerk * dt, self.max_jerk * dt)
        applied_accel = state.accel + accel_delta

        # Resistive forces (rolling + aerodynamic). Use signed speed for stability.
        v = float(state.speed)
        resistive = self.rolling_resistance * v + self.aero_drag * v * abs(v)
        net_accel = applied_accel - resistive

        # Kinematic bicycle update.
        lf = max(0.8, 0.5 * state.wheelbase)
        lr = max(0.8, state.wheelbase - lf)
        beta = float(np.arctan2(lr * np.tan(next_state.steer), max(1e-6, lf + lr)))

        next_state.speed = float(max(0.0, v + net_accel * dt))
        yaw_rate = 0.0
        if state.wheelbase > 1e-6:
            yaw_rate = next_state.speed * np.sin(beta) / max(1e-6, lr)
        next_state.yaw = wrap_angle(state.yaw + yaw_rate * dt)

        vx = next_state.speed * np.cos(state.yaw + beta)
        vy = next_state.speed * np.sin(state.yaw + beta)
        next_state.x = float(state.x + vx * dt)
        next_state.y = float(state.y + vy * dt)
        next_state.accel = float(applied_accel)

        return next_state


@dataclass
class LaneFollowingController:
    """Speed PID + Stanley-style lateral lane controller."""

    speed_pid: PID1D
    lateral_gain: float = 1.4
    heading_gain: float = 1.0

    def reset(self) -> None:
        self.speed_pid.reset()

    def control(
        self,
        state: VehicleState,
        target_speed: float,
        path_point: tuple[float, float],
        path_heading: float,
        dt: float,
    ) -> tuple[float, float]:
        px, py = path_point
        dx = px - state.x
        dy = py - state.y

        # Signed cross-track error in vehicle frame.
        c = np.cos(state.yaw)
        s = np.sin(state.yaw)
        cte = -s * dx + c * dy

        heading_error = wrap_angle(path_heading - state.yaw)
        stanley_term = np.arctan2(self.lateral_gain * cte, max(0.8, state.speed))
        steer_cmd = self.heading_gain * heading_error + stanley_term

        accel_cmd = self.speed_pid.step(target_speed, state.speed, dt)
        # Map normalized PID output to physical acceleration command.
        accel_cmd = 3.0 * accel_cmd if accel_cmd >= 0 else 8.0 * accel_cmd

        return float(accel_cmd), float(steer_cmd)
