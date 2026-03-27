"""Native C++ physics backend with Python fallback."""

from __future__ import annotations

import importlib
from dataclasses import dataclass

from .common import VehicleState
from .dynamics import VehicleDynamicsModel


@dataclass
class PhysicsBackendInfo:
    native_available: bool
    native_active: bool
    backend_name: str


def _resolve_native_vehicle_class():
    """Resolve a native VehicleDynamics3D implementation if available.

    The standalone `kronos_physics` module is preferred because it is not linked
    against Qt, then we fall back to `kronos_native`.
    """
    for module_name in ("kronos.native.kronos_physics", "kronos.native.kronos_native"):
        try:
            module = importlib.import_module(module_name)
        except Exception:
            continue
        vehicle_cls = getattr(module, "VehicleDynamics3D", None)
        if vehicle_cls is not None:
            return vehicle_cls, module_name
    return None, None


class PhysicsBackend:
    """Use native `VehicleDynamics3D` when available, with Python fallback."""

    def __init__(self, model: VehicleDynamicsModel) -> None:
        self.model = model
        self._native = None
        self._native_cls = None
        self._module_name = None

        self._native_cls, self._module_name = _resolve_native_vehicle_class()
        if self._native_cls is not None:
            try:
                self._native = self._native_cls()
            except Exception:
                self._native = None

    @property
    def info(self) -> PhysicsBackendInfo:
        module_suffix = self._module_name.split(".")[-1] if self._module_name else ""
        backend_name = (
            f"native_cpp:{module_suffix}" if self._native is not None and module_suffix else "python_fallback"
        )
        return PhysicsBackendInfo(
            native_available=bool(self._native_cls is not None),
            native_active=self._native is not None,
            backend_name=backend_name,
        )

    def step_bicycle(self, state: VehicleState, accel_cmd: float, steer_cmd: float, dt: float) -> VehicleState:
        if self._native is None:
            return self.model.step(state, accel_cmd, steer_cmd, dt)

        vector = [
            float(state.x),
            float(state.y),
            float(state.yaw),
            float(state.speed),
            float(state.accel),
            float(state.steer),
        ]
        try:
            out = self._native.step_bicycle(
                vector,
                float(accel_cmd),
                float(steer_cmd),
                float(dt),
                float(state.wheelbase),
                float(self.model.max_steer),
                float(self.model.max_steer_rate),
                float(self.model.max_accel),
                float(self.model.max_decel),
                float(self.model.max_jerk),
                float(self.model.rolling_resistance),
                float(self.model.aero_drag),
            )
            next_state = state.copy()
            next_state.x = float(out[0])
            next_state.y = float(out[1])
            next_state.yaw = float(out[2])
            next_state.speed = float(out[3])
            next_state.accel = float(out[4])
            next_state.steer = float(out[5])
            return next_state
        except Exception:
            return self.model.step(state, accel_cmd, steer_cmd, dt)


__all__ = ["PhysicsBackend", "PhysicsBackendInfo"]
