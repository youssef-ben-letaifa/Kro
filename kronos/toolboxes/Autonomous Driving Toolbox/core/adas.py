"""ADAS logic: lane keeping assist and collision warning."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .common import ADASConfig, FusedObject, VehicleState
from .dynamics import wrap_angle
from .road import RoadNetwork2D


@dataclass
class ADASDecision:
    lane_index: int
    lane_center: float
    lane_offset: float
    heading_error: float
    lane_keeping_steer: float
    nearest_object_distance: float | None
    nearest_object_speed: float | None
    min_ttc: float | None
    collision_warning: bool
    emergency_brake: bool
    recommended_speed: float

    def to_dict(self) -> dict[str, float | bool | int | None]:
        return {
            "lane_index": self.lane_index,
            "lane_center": self.lane_center,
            "lane_offset": self.lane_offset,
            "heading_error": self.heading_error,
            "lane_keeping_steer": self.lane_keeping_steer,
            "nearest_object_distance": self.nearest_object_distance,
            "nearest_object_speed": self.nearest_object_speed,
            "min_ttc": self.min_ttc,
            "collision_warning": self.collision_warning,
            "emergency_brake": self.emergency_brake,
            "recommended_speed": self.recommended_speed,
        }


class ADASController:
    """Implements LKA and forward collision warning logic."""

    def __init__(self, config: ADASConfig, road: RoadNetwork2D) -> None:
        self.config = config
        self.road = road

    def evaluate(
        self,
        ego: VehicleState,
        objects: list[FusedObject],
        path_heading: float,
        *,
        enable_lka: bool = True,
        enable_collision_warning: bool = True,
    ) -> ADASDecision:
        lane_index = self.road.nearest_lane_index(ego.y, ego.x)
        lane_center = self.road.lane_center(lane_index, ego.x)
        lane_offset = float(ego.y - lane_center)
        heading_error = float(wrap_angle(path_heading - ego.yaw))

        lane_keep_cmd = 0.0
        if enable_lka:
            lane_keep_cmd = -(
                self.config.lane_keeping_gain * lane_offset
                + self.config.lane_heading_gain * heading_error
            )
            lane_keep_cmd = float(np.clip(lane_keep_cmd, -0.38, 0.38))

        nearest_dist: float | None = None
        nearest_speed: float | None = None
        min_ttc = np.inf
        heading = np.array([np.cos(ego.yaw), np.sin(ego.yaw)], dtype=float)

        for obj in objects:
            x_rel, y_rel = self.road.to_local_frame(ego.x, ego.y, ego.yaw, obj.x, obj.y)
            if x_rel <= 0.5:
                continue
            # Same-lane corridor with a small margin.
            lane_half = 0.5 * self.road.lane_width(lane_index)
            if abs(y_rel) > lane_half + 0.8:
                continue

            obj_speed_long = float(np.dot(np.array([obj.vx, obj.vy], dtype=float), heading))
            relative_speed = float(max(0.0, ego.speed - obj_speed_long))
            ttc = x_rel / max(relative_speed, 1e-4) if relative_speed > 0.05 else np.inf

            if nearest_dist is None or x_rel < nearest_dist:
                nearest_dist = float(x_rel)
                nearest_speed = obj_speed_long
            min_ttc = min(min_ttc, ttc)

        warning = bool(enable_collision_warning and min_ttc <= self.config.collision_ttc_warning_s)
        emergency = bool(enable_collision_warning and min_ttc <= self.config.collision_ttc_emergency_s)

        recommended_speed = float(ego.desired_speed)
        if nearest_dist is not None and nearest_speed is not None:
            # Time-gap based advisory speed control.
            desired_gap = max(8.0, 1.4 * max(ego.speed, 0.0))
            gap_error = nearest_dist - desired_gap
            speed_advice = nearest_speed + 0.45 * gap_error
            recommended_speed = float(min(recommended_speed, max(0.0, speed_advice)))

        if warning:
            recommended_speed = float(min(recommended_speed, max(0.0, ego.speed - 2.5)))
        if emergency:
            recommended_speed = 0.0

        return ADASDecision(
            lane_index=int(lane_index),
            lane_center=float(lane_center),
            lane_offset=lane_offset,
            heading_error=heading_error,
            lane_keeping_steer=float(lane_keep_cmd),
            nearest_object_distance=nearest_dist,
            nearest_object_speed=nearest_speed,
            min_ttc=None if not np.isfinite(min_ttc) else float(min_ttc),
            collision_warning=warning,
            emergency_brake=emergency,
            recommended_speed=float(np.clip(recommended_speed, 0.0, 45.0)),
        )


__all__ = ["ADASController", "ADASDecision"]
