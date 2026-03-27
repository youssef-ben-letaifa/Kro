"""Road and lane geometry helpers."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .common import WorldConfig
from .hd_map import LaneProfile


@dataclass
class LaneSegment:
    lane_index: int
    x0: float
    x1: float
    y: float


class RoadNetwork2D:
    """Lane geometry with optional HD-map-derived lane profiles."""

    def __init__(self, config: WorldConfig) -> None:
        self.config = config
        self.lane_centers = self._build_lane_centers(config.lane_count, config.lane_width)
        self._lane_profiles: dict[int, LaneProfile] = {}
        self._lane_widths: dict[int, float] = {}
        self._hd_enabled = False

    @property
    def hd_enabled(self) -> bool:
        return self._hd_enabled

    def apply_hd_map_profiles(self, profiles: list[LaneProfile]) -> None:
        """Activate lane geometry from ingested HD map profiles."""
        if not profiles:
            return

        self._lane_profiles.clear()
        self._lane_widths.clear()

        ordered = sorted(profiles, key=lambda p: p.lane_index)
        lane_centers: list[float] = []
        widths: list[float] = []
        max_x = 0.0

        for idx, profile in enumerate(ordered):
            xs = np.asarray(profile.xs, dtype=float)
            ys = np.asarray(profile.ys, dtype=float)
            if xs.size < 2 or ys.size < 2:
                continue
            self._lane_profiles[idx] = LaneProfile(
                lane_id=profile.lane_id,
                lane_index=idx,
                xs=xs,
                ys=ys,
                width=float(max(2.2, profile.width)),
            )
            self._lane_widths[idx] = float(max(2.2, profile.width))
            lane_centers.append(float(np.mean(ys)))
            widths.append(float(max(2.2, profile.width)))
            max_x = max(max_x, float(xs[-1]))

        if not self._lane_profiles:
            return

        self._hd_enabled = True
        self.lane_centers = lane_centers
        self.config.lane_count = len(self.lane_centers)
        if widths:
            self.config.lane_width = float(np.mean(widths))
        if max_x > 30.0:
            self.config.road_length = float(max_x)

    @staticmethod
    def _build_lane_centers(lane_count: int, lane_width: float) -> list[float]:
        half = (lane_count - 1) * 0.5
        return [(-half + idx) * lane_width for idx in range(lane_count)]

    def lane_width(self, lane_index: int) -> float:
        idx = int(np.clip(lane_index, 0, max(0, len(self.lane_centers) - 1)))
        if self._hd_enabled and idx in self._lane_widths:
            return self._lane_widths[idx]
        return float(self.config.lane_width)

    def lane_center(self, lane_index: int, x: float | None = None) -> float:
        idx = int(np.clip(lane_index, 0, max(0, len(self.lane_centers) - 1)))
        if self._hd_enabled and x is not None and idx in self._lane_profiles:
            profile = self._lane_profiles[idx]
            xq = float(np.clip(x, profile.xs[0], profile.xs[-1]))
            return float(np.interp(xq, profile.xs, profile.ys))
        return self.lane_centers[idx]

    def lane_bounds(self, x: float | None = None) -> list[tuple[float, float]]:
        bounds: list[tuple[float, float]] = []
        for lane_idx in range(len(self.lane_centers)):
            center = self.lane_center(lane_idx, x)
            half = 0.5 * self.lane_width(lane_idx)
            bounds.append((center - half, center + half))
        return bounds

    def nearest_lane_index(self, y: float, x: float | None = None) -> int:
        distances = [abs(y - self.lane_center(i, x)) for i in range(len(self.lane_centers))]
        return int(np.argmin(distances))

    def clamp_to_road(self, y: float, x: float | None = None) -> float:
        bounds = self.lane_bounds(x)
        lower = min(b[0] for b in bounds)
        upper = max(b[1] for b in bounds)
        return float(np.clip(y, lower, upper))

    def lane_markings(self, x: float | None = None) -> list[float]:
        bounds = self.lane_bounds(x)
        markings = [bounds[0][0]]
        markings.extend(bound[1] for bound in bounds)
        return markings

    def centerline_points(self, lane_index: int, x_start: float, x_end: float, step: float = 4.0) -> list[tuple[float, float]]:
        x0 = min(x_start, x_end)
        x1 = max(x_start, x_end)
        xs = np.arange(x0, x1 + 1e-6, max(0.5, step))
        out: list[tuple[float, float]] = []
        for x in xs:
            out.append((float(x), self.lane_center(lane_index, float(x))))
        return out

    def lane_segments(self, step: float = 10.0) -> list[LaneSegment]:
        segments: list[LaneSegment] = []
        xs = np.arange(0.0, self.config.road_length + step, step)
        for lane_idx in range(len(self.lane_centers)):
            for i in range(len(xs) - 1):
                xm = 0.5 * (xs[i] + xs[i + 1])
                segments.append(
                    LaneSegment(
                        lane_index=lane_idx,
                        x0=float(xs[i]),
                        x1=float(xs[i + 1]),
                        y=self.lane_center(lane_idx, float(xm)),
                    )
                )
        return segments

    def to_local_frame(self, ref_x: float, ref_y: float, ref_yaw: float, x: float, y: float) -> tuple[float, float]:
        dx = x - ref_x
        dy = y - ref_y
        c = float(np.cos(ref_yaw))
        s = float(np.sin(ref_yaw))
        x_rel = c * dx + s * dy
        y_rel = -s * dx + c * dy
        return x_rel, y_rel

    def to_global_frame(self, ref_x: float, ref_y: float, ref_yaw: float, x_rel: float, y_rel: float) -> tuple[float, float]:
        c = float(np.cos(ref_yaw))
        s = float(np.sin(ref_yaw))
        x = ref_x + c * x_rel - s * y_rel
        y = ref_y + s * x_rel + c * y_rel
        return float(x), float(y)
