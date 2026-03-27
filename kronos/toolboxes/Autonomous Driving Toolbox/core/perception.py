"""Perception: detection extraction and multi-target tracking."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .common import CameraDetection, FusedObject, LidarDetection, RadarDetection, VehicleState


@dataclass
class ObjectHypothesis:
    source: str
    x: float
    y: float
    vx: float
    vy: float
    confidence: float
    actor_id: str | None = None


@dataclass
class _Track:
    track_id: int
    state: np.ndarray  # [x, y, vx, vy]
    cov: np.ndarray
    age: int = 0
    missed: int = 0
    actor_id: str | None = None
    confidence: float = 0.5


class PerceptionPipeline:
    """Extract object hypotheses from LiDAR, Radar, and Camera streams."""

    def __init__(self) -> None:
        self._next_track_id = 1
        self._tracks: dict[int, _Track] = {}

    @staticmethod
    def _to_global(ego: VehicleState, x_rel: float, y_rel: float) -> tuple[float, float]:
        c = float(np.cos(ego.yaw))
        s = float(np.sin(ego.yaw))
        x = ego.x + c * x_rel - s * y_rel
        y = ego.y + s * x_rel + c * y_rel
        return float(x), float(y)

    def detect(
        self,
        ego: VehicleState,
        lidar: list[LidarDetection],
        radar: list[RadarDetection],
        camera: list[CameraDetection],
    ) -> tuple[list[ObjectHypothesis], list[ObjectHypothesis], list[ObjectHypothesis]]:
        lidar_h = self._detect_from_lidar(ego, lidar)
        radar_h = self._detect_from_radar(ego, radar)
        cam_h = self._detect_from_camera(ego, camera)
        return lidar_h, radar_h, cam_h

    def _detect_from_lidar(self, ego: VehicleState, points: list[LidarDetection]) -> list[ObjectHypothesis]:
        if not points:
            return []
        pts = np.array([[p.x_rel, p.y_rel] for p in points], dtype=float)
        clusters = _euclidean_clusters(pts, eps=1.7, min_points=4)
        out: list[ObjectHypothesis] = []
        for idxs in clusters:
            cluster = pts[idxs]
            centroid = np.mean(cluster, axis=0)
            spread = np.max(np.linalg.norm(cluster - centroid, axis=1)) if len(cluster) > 1 else 0.0
            if spread < 0.2:
                continue
            gx, gy = self._to_global(ego, float(centroid[0]), float(centroid[1]))
            conf = float(np.clip(0.60 + 0.02 * len(cluster), 0.60, 0.98))
            out.append(
                ObjectHypothesis(
                    source="lidar",
                    x=gx,
                    y=gy,
                    vx=0.0,
                    vy=0.0,
                    confidence=conf,
                )
            )
        return out

    def _detect_from_radar(self, ego: VehicleState, detections: list[RadarDetection]) -> list[ObjectHypothesis]:
        out: list[ObjectHypothesis] = []
        for det in detections:
            x_rel = det.depth * float(np.cos(det.azimuth))
            y_rel = det.depth * float(np.sin(det.azimuth))
            gx, gy = self._to_global(ego, x_rel, y_rel)

            # Convert radial velocity to world components under LOS assumption.
            los_global = np.array([
                np.cos(ego.yaw + det.azimuth),
                np.sin(ego.yaw + det.azimuth),
            ], dtype=float)
            vx = float(det.velocity * los_global[0])
            vy = float(det.velocity * los_global[1])

            out.append(
                ObjectHypothesis(
                    source="radar",
                    x=gx,
                    y=gy,
                    vx=vx,
                    vy=vy,
                    confidence=0.72,
                )
            )
        return out

    def _detect_from_camera(self, ego: VehicleState, detections: list[CameraDetection]) -> list[ObjectHypothesis]:
        out: list[ObjectHypothesis] = []
        for det in detections:
            gx, gy = self._to_global(ego, det.x_rel, det.y_rel)
            out.append(
                ObjectHypothesis(
                    source="camera",
                    x=gx,
                    y=gy,
                    vx=0.0,
                    vy=0.0,
                    confidence=float(det.confidence),
                    actor_id=det.actor_id,
                )
            )
        return out

    def track(self, fused_objects: list[ObjectHypothesis], dt: float) -> list[FusedObject]:
        """Track fused detections with constant-velocity Kalman filters."""
        dt = max(float(dt), 1e-3)
        self._predict_tracks(dt)

        unmatched_tracks = set(self._tracks.keys())
        unmatched_meas = set(range(len(fused_objects)))
        pairs: list[tuple[int, int, float]] = []

        for tid, track in self._tracks.items():
            tx, ty = track.state[0], track.state[1]
            for mi, meas in enumerate(fused_objects):
                dist = float(np.hypot(meas.x - tx, meas.y - ty))
                if dist < 7.5:
                    pairs.append((tid, mi, dist))

        pairs.sort(key=lambda p: p[2])
        assignments: list[tuple[int, int]] = []
        used_tracks: set[int] = set()
        used_meas: set[int] = set()
        for tid, mi, _ in pairs:
            if tid in used_tracks or mi in used_meas:
                continue
            used_tracks.add(tid)
            used_meas.add(mi)
            assignments.append((tid, mi))

        for tid, mi in assignments:
            meas = fused_objects[mi]
            self._update_track(self._tracks[tid], meas)
            self._tracks[tid].missed = 0
            self._tracks[tid].age += 1
            self._tracks[tid].actor_id = meas.actor_id or self._tracks[tid].actor_id
            self._tracks[tid].confidence = float(np.clip(0.7 * self._tracks[tid].confidence + 0.3 * meas.confidence, 0.1, 0.99))
            unmatched_tracks.discard(tid)
            unmatched_meas.discard(mi)

        for tid in list(unmatched_tracks):
            self._tracks[tid].missed += 1
            self._tracks[tid].age += 1
            self._tracks[tid].confidence = max(0.05, self._tracks[tid].confidence * 0.93)

        for mi in unmatched_meas:
            meas = fused_objects[mi]
            self._spawn_track(meas)

        # Prune stale tracks.
        for tid in list(self._tracks.keys()):
            tr = self._tracks[tid]
            if tr.missed > 12 or tr.confidence < 0.08:
                self._tracks.pop(tid, None)

        result: list[FusedObject] = []
        for tid, tr in self._tracks.items():
            result.append(
                FusedObject(
                    track_id=tid,
                    actor_id=tr.actor_id,
                    x=float(tr.state[0]),
                    y=float(tr.state[1]),
                    vx=float(tr.state[2]),
                    vy=float(tr.state[3]),
                    confidence=float(np.clip(tr.confidence, 0.0, 1.0)),
                    source_count=1,
                )
            )
        result.sort(key=lambda t: t.track_id)
        return result

    def _predict_tracks(self, dt: float) -> None:
        f = np.array(
            [
                [1.0, 0.0, dt, 0.0],
                [0.0, 1.0, 0.0, dt],
                [0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ],
            dtype=float,
        )
        q = np.diag([0.4, 0.4, 1.2, 1.2]) * dt
        for tr in self._tracks.values():
            tr.state = f @ tr.state
            tr.cov = f @ tr.cov @ f.T + q

    @staticmethod
    def _update_track(track: _Track, meas: ObjectHypothesis) -> None:
        z = np.array([meas.x, meas.y], dtype=float)
        h = np.array(
            [
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0],
            ],
            dtype=float,
        )
        r = np.diag([1.3, 1.3])
        y = z - h @ track.state
        s = h @ track.cov @ h.T + r
        k = track.cov @ h.T @ np.linalg.inv(s)
        track.state = track.state + k @ y
        i = np.eye(4)
        track.cov = (i - k @ h) @ track.cov
        # Fold radar velocity hints in softly.
        if abs(meas.vx) + abs(meas.vy) > 0.05:
            track.state[2] = 0.7 * track.state[2] + 0.3 * meas.vx
            track.state[3] = 0.7 * track.state[3] + 0.3 * meas.vy

    def _spawn_track(self, meas: ObjectHypothesis) -> None:
        tid = self._next_track_id
        self._next_track_id += 1
        self._tracks[tid] = _Track(
            track_id=tid,
            state=np.array([meas.x, meas.y, meas.vx, meas.vy], dtype=float),
            cov=np.diag([3.0, 3.0, 4.0, 4.0]),
            age=1,
            missed=0,
            actor_id=meas.actor_id,
            confidence=float(np.clip(meas.confidence, 0.1, 0.99)),
        )


def _euclidean_clusters(points: np.ndarray, eps: float, min_points: int) -> list[np.ndarray]:
    """Lightweight Euclidean clustering without sklearn dependency."""
    n = int(points.shape[0])
    if n == 0:
        return []
    visited = np.zeros(n, dtype=bool)
    clusters: list[np.ndarray] = []

    for idx in range(n):
        if visited[idx]:
            continue
        visited[idx] = True
        neighbors = np.where(np.linalg.norm(points - points[idx], axis=1) <= eps)[0]
        if len(neighbors) < min_points:
            continue
        queue = list(neighbors)
        cluster_idx: set[int] = set(neighbors.tolist())
        while queue:
            cur = queue.pop()
            if not visited[cur]:
                visited[cur] = True
                cur_neighbors = np.where(np.linalg.norm(points - points[cur], axis=1) <= eps)[0]
                if len(cur_neighbors) >= min_points:
                    for nidx in cur_neighbors:
                        if nidx not in cluster_idx:
                            cluster_idx.add(int(nidx))
                            queue.append(int(nidx))
        clusters.append(np.array(sorted(cluster_idx), dtype=int))

    return clusters
