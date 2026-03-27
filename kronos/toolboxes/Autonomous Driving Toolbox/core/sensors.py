"""LiDAR, Radar, and Camera simulation in 2D."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .common import CameraDetection, LidarDetection, RadarDetection, SensorConfig, VehicleState
from .road import RoadNetwork2D


@dataclass
class SensorSuite:
    config: SensorConfig

    def simulate(
        self,
        ego: VehicleState,
        vehicles: list[VehicleState],
        road: RoadNetwork2D,
        rng: np.random.Generator,
    ) -> tuple[list[LidarDetection], list[RadarDetection], list[CameraDetection]]:
        lidar = self._simulate_lidar(ego, vehicles, road, rng)
        radar = self._simulate_radar(ego, vehicles, road, rng)
        camera = self._simulate_camera(ego, vehicles, rng)
        return lidar, radar, camera

    def _simulate_lidar(
        self,
        ego: VehicleState,
        vehicles: list[VehicleState],
        road: RoadNetwork2D,
        rng: np.random.Generator,
    ) -> list[LidarDetection]:
        cfg = self.config
        points: list[LidarDetection] = []
        num = max(16, int(cfg.lidar_points_per_scan))
        fov = np.deg2rad(cfg.lidar_fov_deg)
        half = 0.5 * fov

        lane_segments = self._lane_segments(road)
        actor_segments = self._actor_segments([v for v in vehicles if v.actor_id != ego.actor_id])

        drop_beta = 1.0 - cfg.lidar_dropoff_zero_intensity
        drop_alpha = cfg.lidar_dropoff_zero_intensity / max(cfg.lidar_dropoff_intensity_limit, 1e-6)

        for i in range(num):
            if rng.random() < cfg.lidar_dropoff_general_rate:
                continue

            angle = -half + (i / max(1, num - 1)) * fov
            dir_global = np.array([
                np.cos(ego.yaw + angle),
                np.sin(ego.yaw + angle),
            ], dtype=float)
            origin = np.array([ego.x, ego.y], dtype=float)

            hit_distance = np.inf
            hit_point = None

            for seg in lane_segments:
                d = _ray_segment_distance(origin, dir_global, seg[0], seg[1], cfg.lidar_range)
                if d is not None and d < hit_distance:
                    hit_distance = d
                    hit_point = origin + d * dir_global

            for seg in actor_segments:
                d = _ray_segment_distance(origin, dir_global, seg[0], seg[1], cfg.lidar_range)
                if d is not None and d < hit_distance:
                    hit_distance = d
                    hit_point = origin + d * dir_global

            if hit_point is None or not np.isfinite(hit_distance):
                continue

            hit_distance = float(np.clip(hit_distance + rng.normal(0.0, cfg.lidar_noise_std), 0.0, cfg.lidar_range))
            hit_point = origin + hit_distance * dir_global

            intensity = float(np.exp(-cfg.lidar_attenuation * hit_distance))
            if intensity <= cfg.lidar_dropoff_intensity_limit:
                keep_prob = drop_alpha * intensity + drop_beta
                if rng.random() > keep_prob:
                    continue

            x_rel, y_rel = road.to_local_frame(ego.x, ego.y, ego.yaw, float(hit_point[0]), float(hit_point[1]))
            points.append(
                LidarDetection(
                    x_rel=float(x_rel),
                    y_rel=float(y_rel),
                    distance=float(hit_distance),
                    angle=float(np.arctan2(y_rel, max(1e-9, x_rel))),
                    intensity=float(np.clip(intensity, 0.0, 1.0)),
                )
            )

        return points

    def _simulate_radar(
        self,
        ego: VehicleState,
        vehicles: list[VehicleState],
        road: RoadNetwork2D,
        rng: np.random.Generator,
    ) -> list[RadarDetection]:
        cfg = self.config
        detections: list[RadarDetection] = []
        max_fov = np.deg2rad(cfg.radar_fov_deg) * 0.5

        ego_vel = np.array([ego.speed * np.cos(ego.yaw), ego.speed * np.sin(ego.yaw)], dtype=float)

        for veh in vehicles:
            if veh.actor_id == ego.actor_id:
                continue
            x_rel, y_rel = road.to_local_frame(ego.x, ego.y, ego.yaw, veh.x, veh.y)
            depth = float(np.hypot(x_rel, y_rel))
            if depth <= 0.5 or depth > cfg.radar_range:
                continue
            az = float(np.arctan2(y_rel, x_rel))
            if abs(az) > max_fov:
                continue

            target_vel = np.array([veh.speed * np.cos(veh.yaw), veh.speed * np.sin(veh.yaw)], dtype=float)
            los = np.array([x_rel, y_rel], dtype=float) / max(depth, 1e-6)
            rel_v = float(np.dot(target_vel - ego_vel, los))

            depth_noisy = depth + rng.normal(0.0, cfg.radar_noise_depth_std)
            vel_noisy = rel_v + rng.normal(0.0, cfg.radar_noise_vel_std)
            detections.append(
                RadarDetection(
                    depth=float(np.clip(depth_noisy, 0.0, cfg.radar_range)),
                    azimuth=az,
                    altitude=0.0,
                    velocity=vel_noisy,
                )
            )

        detections.sort(key=lambda d: d.depth)
        return detections

    def _simulate_camera(
        self,
        ego: VehicleState,
        vehicles: list[VehicleState],
        rng: np.random.Generator,
    ) -> list[CameraDetection]:
        cfg = self.config
        detections: list[CameraDetection] = []
        half_fov = np.deg2rad(cfg.camera_hfov_deg) * 0.5

        for veh in vehicles:
            if veh.actor_id == ego.actor_id:
                continue

            dx = veh.x - ego.x
            dy = veh.y - ego.y
            c = np.cos(ego.yaw)
            s = np.sin(ego.yaw)
            x_rel = c * dx + s * dy
            y_rel = -s * dx + c * dy
            if x_rel <= 0.5:
                continue

            dist = float(np.hypot(x_rel, y_rel))
            if dist > cfg.camera_range:
                continue
            az = float(np.arctan2(y_rel, x_rel))
            if abs(az) > half_fov:
                continue

            u_center = (0.5 + az / max(1e-6, 2.0 * half_fov)) * cfg.camera_width
            scale = 42.0 / max(dist, 1.0)
            bbox_w = float(np.clip(scale * veh.width * 16.0, 8.0, cfg.camera_width * 0.35))
            bbox_h = float(np.clip(scale * veh.length * 16.0, 8.0, cfg.camera_height * 0.70))
            v_center = float(cfg.camera_height * 0.62 - 0.015 * (dist - 20.0) * cfg.camera_height)

            conf = float(np.clip(0.98 - 0.004 * dist + rng.normal(0.0, 0.015), 0.30, 0.99))
            detections.append(
                CameraDetection(
                    actor_id=veh.actor_id,
                    x_rel=float(x_rel),
                    y_rel=float(y_rel),
                    distance=dist,
                    azimuth=az,
                    bbox_u=float(np.clip(u_center, 0.0, cfg.camera_width)),
                    bbox_v=float(np.clip(v_center, 0.0, cfg.camera_height)),
                    bbox_w=bbox_w,
                    bbox_h=bbox_h,
                    confidence=conf,
                )
            )

        detections.sort(key=lambda d: d.distance)
        return detections

    @staticmethod
    def _actor_segments(vehicles: list[VehicleState]) -> list[tuple[np.ndarray, np.ndarray]]:
        segments: list[tuple[np.ndarray, np.ndarray]] = []
        for veh in vehicles:
            corners = _vehicle_corners(veh)
            for i in range(4):
                p0 = corners[i]
                p1 = corners[(i + 1) % 4]
                segments.append((p0, p1))
        return segments

    @staticmethod
    def _lane_segments(road: RoadNetwork2D) -> list[tuple[np.ndarray, np.ndarray]]:
        segments: list[tuple[np.ndarray, np.ndarray]] = []
        xs = np.arange(0.0, road.config.road_length + 2.0, 2.0)
        if xs.size < 2:
            return segments

        first_markings = road.lane_markings(float(xs[0]))
        for mark_idx in range(len(first_markings)):
            prev = np.array([xs[0], first_markings[mark_idx]], dtype=float)
            for x in xs[1:]:
                marks = road.lane_markings(float(x))
                if mark_idx >= len(marks):
                    continue
                cur = np.array([x, marks[mark_idx]], dtype=float)
                segments.append((prev, cur))
                prev = cur
        return segments


def _vehicle_corners(veh: VehicleState) -> list[np.ndarray]:
    c = float(np.cos(veh.yaw))
    s = float(np.sin(veh.yaw))
    hl = 0.5 * float(veh.length)
    hw = 0.5 * float(veh.width)

    local = [
        np.array([hl, hw], dtype=float),
        np.array([hl, -hw], dtype=float),
        np.array([-hl, -hw], dtype=float),
        np.array([-hl, hw], dtype=float),
    ]

    corners: list[np.ndarray] = []
    for pt in local:
        x = veh.x + c * pt[0] - s * pt[1]
        y = veh.y + s * pt[0] + c * pt[1]
        corners.append(np.array([x, y], dtype=float))
    return corners


def _ray_segment_distance(
    origin: np.ndarray,
    direction: np.ndarray,
    p1: np.ndarray,
    p2: np.ndarray,
    max_range: float,
) -> float | None:
    """Distance from ray origin to first intersection with a segment."""
    v1 = origin - p1
    v2 = p2 - p1
    v3 = np.array([-direction[1], direction[0]], dtype=float)

    denom = float(np.dot(v2, v3))
    if abs(denom) < 1e-9:
        return None

    # 2D cross product scalar (z-component).
    cross_v2_v1 = float(v2[0] * v1[1] - v2[1] * v1[0])
    t1 = cross_v2_v1 / denom
    t2 = float(np.dot(v1, v3) / denom)

    if t1 < 0.0 or t1 > max_range:
        return None
    if t2 < 0.0 or t2 > 1.0:
        return None
    return t1
