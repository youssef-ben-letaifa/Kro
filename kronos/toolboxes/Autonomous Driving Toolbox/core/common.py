"""Shared data structures for autonomous driving simulation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class VehicleState:
    """Vehicle state in a planar frame."""

    actor_id: str
    x: float
    y: float
    yaw: float
    speed: float
    accel: float = 0.0
    steer: float = 0.0
    length: float = 4.6
    width: float = 1.9
    wheelbase: float = 2.8
    desired_speed: float = 16.0
    lane_index: int = 0
    is_ego: bool = False
    z: float = 0.0
    roll: float = 0.0
    pitch: float = 0.0

    def position(self) -> np.ndarray:
        return np.array([self.x, self.y], dtype=float)

    def copy(self) -> "VehicleState":
        return VehicleState(
            actor_id=self.actor_id,
            x=float(self.x),
            y=float(self.y),
            yaw=float(self.yaw),
            speed=float(self.speed),
            accel=float(self.accel),
            steer=float(self.steer),
            length=float(self.length),
            width=float(self.width),
            wheelbase=float(self.wheelbase),
            desired_speed=float(self.desired_speed),
            lane_index=int(self.lane_index),
            is_ego=bool(self.is_ego),
            z=float(self.z),
            roll=float(self.roll),
            pitch=float(self.pitch),
        )


@dataclass
class LidarDetection:
    x_rel: float
    y_rel: float
    distance: float
    angle: float
    intensity: float


@dataclass
class RadarDetection:
    depth: float
    azimuth: float
    altitude: float
    velocity: float


@dataclass
class CameraDetection:
    actor_id: str
    x_rel: float
    y_rel: float
    distance: float
    azimuth: float
    bbox_u: float
    bbox_v: float
    bbox_w: float
    bbox_h: float
    confidence: float


@dataclass
class FusedObject:
    track_id: int
    actor_id: str | None
    x: float
    y: float
    vx: float
    vy: float
    confidence: float
    source_count: int


@dataclass
class SimulationFrame:
    time: float
    ego: VehicleState
    vehicles: list[VehicleState]
    global_path: list[tuple[float, float]]
    trajectory: list[tuple[float, float]]
    lidar_points: list[LidarDetection]
    radar_detections: list[RadarDetection]
    camera_detections: list[CameraDetection]
    fused_objects: list[FusedObject]
    adas: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)


@dataclass
class WorldConfig:
    lane_width: float = 3.6
    lane_count: int = 4
    road_length: float = 900.0
    dt: float = 0.05


@dataclass
class SensorConfig:
    lidar_range: float = 85.0
    lidar_points_per_scan: int = 360
    lidar_fov_deg: float = 220.0
    lidar_noise_std: float = 0.05
    lidar_attenuation: float = 0.004
    lidar_dropoff_zero_intensity: float = 0.4
    lidar_dropoff_intensity_limit: float = 0.8
    lidar_dropoff_general_rate: float = 0.12

    radar_range: float = 120.0
    radar_fov_deg: float = 35.0
    radar_noise_depth_std: float = 0.15
    radar_noise_vel_std: float = 0.25

    camera_range: float = 95.0
    camera_hfov_deg: float = 90.0
    camera_width: int = 640
    camera_height: int = 360


@dataclass
class PlannerConfig:
    lattice_step: float = 10.0
    lookahead_time: float = 2.2
    lane_change_cost: float = 12.0
    longitudinal_weight: float = 1.0


@dataclass
class ADASConfig:
    lane_keeping_gain: float = 0.55
    lane_heading_gain: float = 0.9
    collision_ttc_warning_s: float = 3.0
    collision_ttc_emergency_s: float = 1.3
    min_lane_center_margin_m: float = 0.25
