"""Global and local planning modules."""

from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush

import numpy as np

from .common import PlannerConfig, VehicleState
from .road import RoadNetwork2D


@dataclass
class RouteNode:
    x_idx: int
    lane_idx: int


class PathPlanner:
    """Lane-lattice global planner + trajectory sampler."""

    def __init__(self, road: RoadNetwork2D, config: PlannerConfig) -> None:
        self.road = road
        self.config = config
        self.segment_step = max(2.0, config.lattice_step)
        self.node_count = int(np.floor(self.road.config.road_length / self.segment_step)) + 1

    def _neighbors(self, node: RouteNode) -> list[tuple[RouteNode, float]]:
        out: list[tuple[RouteNode, float]] = []
        # Longitudinal progression.
        if node.x_idx + 1 < self.node_count:
            out.append((RouteNode(node.x_idx + 1, node.lane_idx), self.segment_step * self.config.longitudinal_weight))
        # Adjacent lane changes with a fixed penalty.
        for dl in (-1, 1):
            lane_next = node.lane_idx + dl
            if 0 <= lane_next < self.road.config.lane_count:
                out.append((RouteNode(node.x_idx, lane_next), self.config.lane_change_cost))
        return out

    def _heuristic(self, node: RouteNode, goal: RouteNode) -> float:
        dx = max(0, goal.x_idx - node.x_idx) * self.segment_step
        dl = abs(goal.lane_idx - node.lane_idx)
        return dx + dl * self.config.lane_change_cost

    def plan_global_path(
        self,
        start_x: float,
        start_lane: int,
        goal_x: float,
        goal_lane: int,
    ) -> list[tuple[float, float]]:
        """A* path in x/lane lattice, then convert to world points."""
        start = RouteNode(int(np.clip(start_x / self.segment_step, 0, self.node_count - 1)), start_lane)
        goal = RouteNode(int(np.clip(goal_x / self.segment_step, 0, self.node_count - 1)), goal_lane)

        frontier: list[tuple[float, int, RouteNode]] = []
        counter = 0
        heappush(frontier, (0.0, counter, start))

        came_from: dict[tuple[int, int], tuple[int, int] | None] = {(start.x_idx, start.lane_idx): None}
        cost_so_far: dict[tuple[int, int], float] = {(start.x_idx, start.lane_idx): 0.0}

        while frontier:
            _, _, current = heappop(frontier)
            key = (current.x_idx, current.lane_idx)
            if key == (goal.x_idx, goal.lane_idx):
                break
            for neighbor, edge_cost in self._neighbors(current):
                nkey = (neighbor.x_idx, neighbor.lane_idx)
                new_cost = cost_so_far[key] + edge_cost
                if nkey not in cost_so_far or new_cost < cost_so_far[nkey]:
                    cost_so_far[nkey] = new_cost
                    counter += 1
                    priority = new_cost + self._heuristic(neighbor, goal)
                    heappush(frontier, (priority, counter, neighbor))
                    came_from[nkey] = key

        goal_key = (goal.x_idx, goal.lane_idx)
        if goal_key not in came_from:
            # Fallback to straightforward lane-follow path.
            xs = np.arange(start_x, max(start_x + 40.0, goal_x), self.segment_step)
            return [(float(x), self.road.lane_center(start_lane, float(x))) for x in xs]

        # Reconstruct route in lattice nodes.
        route_nodes: list[tuple[int, int]] = []
        cur = goal_key
        while cur is not None:
            route_nodes.append(cur)
            cur = came_from.get(cur)
        route_nodes.reverse()

        # Convert lattice route to smooth world path.
        points: list[tuple[float, float]] = []
        for x_idx, lane_idx in route_nodes:
            x = x_idx * self.segment_step
            points.append((x, self.road.lane_center(lane_idx, x)))
        return self._smooth_lane_changes(points)

    @staticmethod
    def _smooth_lane_changes(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
        if len(points) < 3:
            return points
        xs = np.array([p[0] for p in points], dtype=float)
        ys = np.array([p[1] for p in points], dtype=float)
        xq = np.linspace(xs[0], xs[-1], max(40, len(points) * 6))
        yq = np.interp(xq, xs, ys)
        kernel = np.array([1.0, 2.0, 3.0, 2.0, 1.0], dtype=float)
        kernel /= np.sum(kernel)
        y_smooth = np.convolve(yq, kernel, mode="same")
        # Preserve exact lane anchors at route boundaries.
        y_smooth[0] = ys[0]
        y_smooth[-1] = ys[-1]
        return [(float(x), float(y)) for x, y in zip(xq, y_smooth)]

    def build_local_trajectory(
        self,
        ego: VehicleState,
        global_path: list[tuple[float, float]],
        dt: float,
    ) -> list[tuple[float, float]]:
        """Generate finite-horizon trajectory from global path and ego speed."""
        if not global_path:
            return [(ego.x, ego.y)]

        points = np.asarray(global_path, dtype=float)
        distances = np.sqrt(np.sum((points - np.array([ego.x, ego.y])) ** 2, axis=1))
        nearest_idx = int(np.argmin(distances))

        horizon_dist = max(25.0, ego.speed * self.config.lookahead_time * 4.0)
        selected: list[tuple[float, float]] = []
        accum = 0.0
        last = points[nearest_idx]
        for idx in range(nearest_idx, len(points)):
            p = points[idx]
            step = float(np.linalg.norm(p - last))
            accum += step
            selected.append((float(p[0]), float(p[1])))
            last = p
            if accum >= horizon_dist:
                break

        if len(selected) < 2:
            selected.append((ego.x + 20.0, selected[-1][1]))

        # Uniformly resample the selected piece for controller consumption.
        samples = max(20, int(self.config.lookahead_time / max(dt, 1e-3)) * 8)
        selected_arr = np.asarray(selected, dtype=float)
        seg = np.sqrt(np.sum(np.diff(selected_arr, axis=0) ** 2, axis=1))
        s = np.concatenate(([0.0], np.cumsum(seg)))
        if s[-1] < 1e-6:
            return selected
        sq = np.linspace(0.0, s[-1], samples)
        xq = np.interp(sq, s, selected_arr[:, 0])
        yq = np.interp(sq, s, selected_arr[:, 1])
        return [(float(x), float(y)) for x, y in zip(xq, yq)]

    @staticmethod
    def target_from_trajectory(trajectory: list[tuple[float, float]], lookahead_idx: int = 6) -> tuple[tuple[float, float], float]:
        """Return target point and heading from trajectory."""
        if len(trajectory) < 2:
            return trajectory[0], 0.0
        idx = int(np.clip(lookahead_idx, 1, len(trajectory) - 1))
        p0 = np.asarray(trajectory[idx - 1], dtype=float)
        p1 = np.asarray(trajectory[idx], dtype=float)
        heading = float(np.arctan2(p1[1] - p0[1], p1[0] - p0[0]))
        return (float(p1[0]), float(p1[1])), heading
