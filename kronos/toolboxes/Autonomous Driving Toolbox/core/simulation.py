"""Autonomous driving simulation orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .adas import ADASController
from .common import (
    ADASConfig,
    PlannerConfig,
    SensorConfig,
    SimulationFrame,
    VehicleState,
    WorldConfig,
)
from .dynamics import LaneFollowingController, PID1D, VehicleDynamicsModel
from .fusion import SensorFusionEngine
from .hd_map import build_lane_profiles, load_hd_map
from .perception import PerceptionPipeline
from .physics_backend import PhysicsBackend
from .planning import PathPlanner
from .road import RoadNetwork2D
from .sensors import SensorSuite


@dataclass
class FeatureFlags:
    lidar: bool = True
    radar: bool = True
    camera: bool = True
    lane_keeping_assist: bool = True
    collision_warning: bool = True


class AutonomousDrivingSimulation:
    """End-to-end AD simulation with dynamics, sensing, fusion, and ADAS."""

    def __init__(
        self,
        *,
        world_config: WorldConfig | None = None,
        sensor_config: SensorConfig | None = None,
        planner_config: PlannerConfig | None = None,
        adas_config: ADASConfig | None = None,
        seed: int = 7,
    ) -> None:
        self.world_config = world_config or WorldConfig()
        self.sensor_config = sensor_config or SensorConfig()
        self.planner_config = planner_config or PlannerConfig()
        self.adas_config = adas_config or ADASConfig()

        self.flags = FeatureFlags()
        self.rng = np.random.default_rng(seed)

        self.road = RoadNetwork2D(self.world_config)
        self.path_planner = PathPlanner(self.road, self.planner_config)
        self.sensor_suite = SensorSuite(self.sensor_config)
        self.perception = PerceptionPipeline()
        self.fusion = SensorFusionEngine()

        self.dynamics_model = VehicleDynamicsModel()
        self.physics = PhysicsBackend(self.dynamics_model)

        self.controller = LaneFollowingController(
            speed_pid=PID1D(kp=0.35, ki=0.08, kd=0.02, min_output=-1.0, max_output=1.0),
            lateral_gain=1.25,
            heading_gain=1.0,
        )
        self.adas = ADASController(self.adas_config, self.road)

        self.time = 0.0
        self._step_index = 0
        self.ego = VehicleState("ego", 0.0, 0.0, 0.0, 0.0, is_ego=True)
        self.traffic: list[VehicleState] = []
        self.goal_lane = 0
        self.goal_x = self.road.config.road_length - 20.0
        self.global_path: list[tuple[float, float]] = []
        self.trajectory: list[tuple[float, float]] = []
        self.hd_map_path: str | None = None

        self.reset()

    @property
    def dt(self) -> float:
        return float(self.world_config.dt)

    def set_feature_flags(
        self,
        *,
        lidar: bool | None = None,
        radar: bool | None = None,
        camera: bool | None = None,
        lane_keeping_assist: bool | None = None,
        collision_warning: bool | None = None,
    ) -> None:
        if lidar is not None:
            self.flags.lidar = bool(lidar)
        if radar is not None:
            self.flags.radar = bool(radar)
        if camera is not None:
            self.flags.camera = bool(camera)
        if lane_keeping_assist is not None:
            self.flags.lane_keeping_assist = bool(lane_keeping_assist)
        if collision_warning is not None:
            self.flags.collision_warning = bool(collision_warning)

    def load_hd_map(self, path: str | Path) -> dict[str, str | float | int]:
        """Load and activate an OpenDRIVE or Lanelet2 map for this simulation."""
        hd_map = load_hd_map(path)
        profiles = build_lane_profiles(hd_map)
        if len(profiles) < 1:
            raise ValueError("No usable lanes found in HD map.")

        self.road.apply_hd_map_profiles(profiles)
        self.hd_map_path = str(path)
        self.goal_x = max(80.0, self.road.config.road_length - 20.0)
        self.reset()
        return {
            "format": hd_map.source_format,
            "lanes": len(profiles),
            "road_length": float(self.road.config.road_length),
            "source": str(path),
        }

    def reset(self) -> SimulationFrame:
        """Reset simulation to a lane-following traffic scenario."""
        self.time = 0.0
        self._step_index = 0
        self.perception = PerceptionPipeline()
        self.controller.reset()

        start_lane = min(max(0, self.road.config.lane_count // 2), self.road.config.lane_count - 1)
        self.goal_lane = start_lane

        self.ego = VehicleState(
            actor_id="ego",
            x=10.0,
            y=self.road.lane_center(start_lane, 10.0),
            yaw=0.0,
            speed=13.5,
            accel=0.0,
            steer=0.0,
            desired_speed=20.0,
            lane_index=start_lane,
            is_ego=True,
            z=0.0,
            roll=0.0,
            pitch=0.0,
        )

        lane_m1 = max(0, start_lane - 1)
        lane_p1 = min(self.road.config.lane_count - 1, start_lane + 1)

        self.traffic = [
            VehicleState(
                actor_id="veh_front_slow",
                x=58.0,
                y=self.road.lane_center(start_lane, 58.0),
                yaw=0.0,
                speed=9.0,
                desired_speed=9.0,
                lane_index=start_lane,
            ),
            VehicleState(
                actor_id="veh_adj_fast",
                x=42.0,
                y=self.road.lane_center(lane_p1, 42.0),
                yaw=0.0,
                speed=17.0,
                desired_speed=17.0,
                lane_index=lane_p1,
            ),
            VehicleState(
                actor_id="veh_adj_mid",
                x=110.0,
                y=self.road.lane_center(lane_p1, 110.0),
                yaw=0.0,
                speed=13.0,
                desired_speed=13.0,
                lane_index=lane_p1,
            ),
            VehicleState(
                actor_id="veh_left_far",
                x=132.0,
                y=self.road.lane_center(lane_m1, 132.0),
                yaw=0.0,
                speed=12.0,
                desired_speed=12.0,
                lane_index=lane_m1,
            ),
            VehicleState(
                actor_id="veh_rear",
                x=-8.0,
                y=self.road.lane_center(start_lane, -8.0),
                yaw=0.0,
                speed=15.0,
                desired_speed=15.0,
                lane_index=start_lane,
            ),
        ]

        self.global_path = self.path_planner.plan_global_path(
            self.ego.x,
            self.ego.lane_index,
            self.goal_x,
            self.goal_lane,
        )
        self.trajectory = self.path_planner.build_local_trajectory(self.ego, self.global_path, self.dt)

        return self._build_frame(
            lidar_points=[],
            radar_detections=[],
            camera_detections=[],
            fused_objects=[],
            adas={},
        )

    def force_collision_case(self, distance: float = 12.0, lead_speed: float = 4.0) -> None:
        """Testing hook: place a slow lead vehicle directly ahead of ego."""
        if not self.traffic:
            return
        lane_center = self.road.lane_center(self.ego.lane_index, self.ego.x + distance)
        self.traffic[0].x = self.ego.x + max(4.0, distance)
        self.traffic[0].y = lane_center
        self.traffic[0].speed = max(0.0, lead_speed)
        self.traffic[0].desired_speed = max(0.0, lead_speed)
        self.traffic[0].lane_index = self.ego.lane_index

    def replan(self) -> None:
        """Refresh global route according to current lane utility."""
        self.goal_lane = self._select_goal_lane()
        self.global_path = self.path_planner.plan_global_path(
            self.ego.x,
            self.ego.lane_index,
            self.goal_x,
            self.goal_lane,
        )

    def step(self) -> SimulationFrame:
        dt = self.dt
        self._step_index += 1

        self._update_traffic(dt)

        # Re-plan globally once per second to allow lane change decisions.
        if self._step_index % max(1, int(round(1.0 / dt))) == 0:
            self.replan()

        self.trajectory = self.path_planner.build_local_trajectory(self.ego, self.global_path, dt)
        target_point, target_heading = self.path_planner.target_from_trajectory(self.trajectory)

        accel_cmd, steer_cmd = self.controller.control(
            self.ego,
            self.ego.desired_speed,
            target_point,
            target_heading,
            dt,
        )

        # Physical lead-vehicle moderation before perception/ADAS loop.
        gt_lead_distance, gt_lead_speed = self._ground_truth_lead()
        if gt_lead_distance is not None and gt_lead_speed is not None:
            desired_gap = max(8.0, 1.3 * self.ego.speed)
            speed_ref = gt_lead_speed + 0.40 * (gt_lead_distance - desired_gap)
            accel_cmd = min(accel_cmd, 0.9 * (speed_ref - self.ego.speed))

        vehicles_all = [self.ego] + self.traffic
        lidar_points, radar_detections, camera_detections = self.sensor_suite.simulate(
            self.ego,
            vehicles_all,
            self.road,
            self.rng,
        )

        if not self.flags.lidar:
            lidar_points = []
        if not self.flags.radar:
            radar_detections = []
        if not self.flags.camera:
            camera_detections = []

        lidar_h, radar_h, cam_h = self.perception.detect(
            self.ego,
            lidar_points,
            radar_detections,
            camera_detections,
        )
        fused_h = self.fusion.fuse(lidar_h, radar_h, cam_h)
        tracks = self.perception.track(fused_h, dt)

        adas_decision = self.adas.evaluate(
            self.ego,
            tracks,
            target_heading,
            enable_lka=self.flags.lane_keeping_assist,
            enable_collision_warning=self.flags.collision_warning,
        )

        steer_cmd += float(adas_decision.lane_keeping_steer)
        speed_error = adas_decision.recommended_speed - self.ego.speed
        accel_cmd = min(accel_cmd, 0.95 * speed_error)

        if adas_decision.collision_warning:
            accel_cmd = min(accel_cmd, -2.5)
        if adas_decision.emergency_brake:
            accel_cmd = min(accel_cmd, -6.5)

        self.ego = self.physics.step_bicycle(self.ego, accel_cmd, steer_cmd, dt)
        self.ego.y = self.road.clamp_to_road(self.ego.y, self.ego.x)
        self.ego.lane_index = self.road.nearest_lane_index(self.ego.y, self.ego.x)

        if self.ego.x > self.road.config.road_length - 5.0:
            # Keep simulation ongoing with a wrap-around road section.
            self.ego.x -= self.road.config.road_length * 0.65

        self.time += dt

        return self._build_frame(
            lidar_points=lidar_points,
            radar_detections=radar_detections,
            camera_detections=camera_detections,
            fused_objects=tracks,
            adas=adas_decision.to_dict(),
        )

    def _build_frame(
        self,
        *,
        lidar_points,
        radar_detections,
        camera_detections,
        fused_objects,
        adas,
    ) -> SimulationFrame:
        lane_center = self.road.lane_center(self.ego.lane_index, self.ego.x)
        backend = self.physics.info
        return SimulationFrame(
            time=float(self.time),
            ego=self.ego.copy(),
            vehicles=[v.copy() for v in self.traffic],
            global_path=list(self.global_path),
            trajectory=list(self.trajectory),
            lidar_points=list(lidar_points),
            radar_detections=list(radar_detections),
            camera_detections=list(camera_detections),
            fused_objects=list(fused_objects),
            adas=dict(adas),
            metrics={
                "speed": float(self.ego.speed),
                "lane_offset": float(self.ego.y - lane_center),
                "target_lane": float(self.goal_lane),
                "backend_native_active": float(1 if backend.native_active else 0),
            },
        )

    def _select_goal_lane(self) -> int:
        current_lane = self.road.nearest_lane_index(self.ego.y, self.ego.x)
        current_gap = self._lane_front_gap(current_lane)

        best_lane = current_lane
        best_score = self._lane_score(current_lane)
        for lane in range(self.road.config.lane_count):
            score = self._lane_score(lane)
            if score > best_score:
                best_lane = lane
                best_score = score

        # Avoid unnecessary lane changes unless current lane is constrained.
        if current_gap > 48.0:
            return current_lane
        if best_lane != current_lane and self._lane_front_gap(best_lane) > current_gap + 9.0:
            return best_lane
        return current_lane

    def _lane_score(self, lane_index: int) -> float:
        gap = self._lane_front_gap(lane_index)
        lane_penalty = 5.5 * abs(lane_index - self.road.nearest_lane_index(self.ego.y, self.ego.x))
        return gap - lane_penalty

    def _lane_front_gap(self, lane_index: int) -> float:
        gap = 1e3
        lane_half = 0.5 * self.road.lane_width(lane_index)
        for veh in self.traffic:
            lane_center = self.road.lane_center(lane_index, veh.x)
            if abs(veh.y - lane_center) > lane_half + 0.4:
                continue
            rel = veh.x - self.ego.x
            if rel > 0.0:
                gap = min(gap, rel)
        return float(gap)

    def _ground_truth_lead(self) -> tuple[float | None, float | None]:
        lead_distance: float | None = None
        lead_speed: float | None = None
        lane_index = self.road.nearest_lane_index(self.ego.y, self.ego.x)
        lane_half = 0.5 * self.road.lane_width(lane_index)

        for veh in self.traffic:
            lane_center = self.road.lane_center(lane_index, veh.x)
            if abs(veh.y - lane_center) > lane_half + 0.4:
                continue
            rel = veh.x - self.ego.x
            if rel <= 0.0:
                continue
            if lead_distance is None or rel < lead_distance:
                lead_distance = float(rel)
                lead_speed = float(veh.speed)

        return lead_distance, lead_speed

    def _update_traffic(self, dt: float) -> None:
        for idx, veh in enumerate(self.traffic):
            desired_speed = veh.desired_speed + 0.35 * np.sin(0.11 * self.time + 0.7 * idx)
            accel = 0.75 * (desired_speed - veh.speed)

            lead = self._vehicle_lead_for_actor(veh)
            if lead is not None:
                lead_gap = max(1.0, lead.x - veh.x - 0.5 * (lead.length + veh.length))
                dv = max(0.0, veh.speed - lead.speed)
                desired_gap = 6.0 + 1.25 * veh.speed + 0.6 * dv
                accel -= 2.3 * (desired_gap / lead_gap) ** 2

            accel = float(np.clip(accel, -4.5, 2.2))
            updated = self.physics.step_bicycle(veh, accel, 0.0, dt)

            lane_center = self.road.lane_center(veh.lane_index, updated.x)
            lateral_error = lane_center - updated.y
            updated.y += float(np.clip(0.35 * lateral_error * dt, -0.08, 0.08))
            updated.yaw = float(np.clip(np.arctan2(updated.y - veh.y, max(1e-3, updated.x - veh.x)), -0.08, 0.08))
            updated.lane_index = self.road.nearest_lane_index(updated.y, updated.x)

            if updated.x > self.road.config.road_length + 25.0:
                updated.x -= self.road.config.road_length + 145.0
            self.traffic[idx] = updated

    def _vehicle_lead_for_actor(self, actor: VehicleState) -> VehicleState | None:
        lead = None
        min_gap = np.inf
        lane_half = 0.5 * self.road.lane_width(actor.lane_index)
        for other in self.traffic:
            if other.actor_id == actor.actor_id:
                continue
            lane_center = self.road.lane_center(actor.lane_index, other.x)
            if abs(other.y - lane_center) > lane_half + 0.4:
                continue
            gap = other.x - actor.x
            if 0.0 < gap < min_gap:
                min_gap = gap
                lead = other
        return lead


__all__ = ["AutonomousDrivingSimulation", "FeatureFlags"]
