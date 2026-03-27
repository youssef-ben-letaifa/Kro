"""Sensor-level fusion for autonomous-driving perception."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .perception import ObjectHypothesis


@dataclass
class SensorFusionConfig:
    """Configuration for multi-sensor object fusion."""

    association_distance: float = 4.0
    lidar_weight: float = 1.0
    radar_weight: float = 1.25
    camera_weight: float = 0.95


class SensorFusionEngine:
    """Fuse LiDAR, Radar, and Camera hypotheses into unified objects."""

    def __init__(self, config: SensorFusionConfig | None = None) -> None:
        self.config = config or SensorFusionConfig()

    def fuse(
        self,
        lidar: list[ObjectHypothesis],
        radar: list[ObjectHypothesis],
        camera: list[ObjectHypothesis],
    ) -> list[ObjectHypothesis]:
        hypotheses = list(lidar) + list(radar) + list(camera)
        if not hypotheses:
            return []

        clusters = self._cluster_hypotheses(hypotheses)
        fused: list[ObjectHypothesis] = []

        for cluster in clusters:
            members = [hypotheses[idx] for idx in cluster]
            source_weights = np.array([self._source_weight(m.source) for m in members], dtype=float)
            conf = np.array([np.clip(m.confidence, 0.05, 1.0) for m in members], dtype=float)
            weights = source_weights * conf
            weights = weights / max(float(np.sum(weights)), 1e-6)

            positions = np.array([[m.x, m.y] for m in members], dtype=float)
            x, y = np.sum(positions * weights[:, None], axis=0)

            # Prefer radar for velocity when available, then blend with others.
            radar_members = [m for m in members if m.source == "radar"]
            if radar_members:
                vweights = np.array(
                    [self._source_weight(m.source) * np.clip(m.confidence, 0.05, 1.0) for m in radar_members],
                    dtype=float,
                )
                vweights = vweights / max(float(np.sum(vweights)), 1e-6)
                rv = np.array([[m.vx, m.vy] for m in radar_members], dtype=float)
                vx, vy = np.sum(rv * vweights[:, None], axis=0)
            else:
                velocities = np.array([[m.vx, m.vy] for m in members], dtype=float)
                vx, vy = np.sum(velocities * weights[:, None], axis=0)

            actor_id = None
            actor_candidates = [m for m in members if m.actor_id]
            if actor_candidates:
                actor_candidates.sort(key=lambda m: m.confidence, reverse=True)
                actor_id = actor_candidates[0].actor_id

            # Probabilistic confidence merge: 1 - product(1 - p_i * w_i_norm)
            p = np.clip(conf * source_weights / max(float(np.max(source_weights)), 1e-6), 0.0, 0.999)
            fused_conf = float(1.0 - np.prod(1.0 - p))
            fused_conf = float(np.clip(fused_conf, 0.05, 0.995))

            source_label = "+".join(sorted({m.source for m in members}))
            fused.append(
                ObjectHypothesis(
                    source=source_label,
                    x=float(x),
                    y=float(y),
                    vx=float(vx),
                    vy=float(vy),
                    confidence=fused_conf,
                    actor_id=actor_id,
                )
            )

        fused.sort(key=lambda h: (h.x, h.y))
        return fused

    def _cluster_hypotheses(self, hypotheses: list[ObjectHypothesis]) -> list[list[int]]:
        """Cluster detections by Euclidean proximity with BFS expansion."""
        threshold = float(max(0.5, self.config.association_distance))
        coords = np.array([[h.x, h.y] for h in hypotheses], dtype=float)
        n = coords.shape[0]

        unvisited = set(range(n))
        clusters: list[list[int]] = []

        while unvisited:
            root = min(unvisited)
            unvisited.remove(root)
            queue = [root]
            cluster = {root}

            while queue:
                idx = queue.pop()
                dist = np.linalg.norm(coords - coords[idx], axis=1)
                neighbors = [j for j in list(unvisited) if dist[j] <= threshold]
                for j in neighbors:
                    unvisited.remove(j)
                    cluster.add(j)
                    queue.append(j)

            clusters.append(sorted(cluster))

        return clusters

    def _source_weight(self, source: str) -> float:
        if source == "lidar":
            return self.config.lidar_weight
        if source == "radar":
            return self.config.radar_weight
        if source == "camera":
            return self.config.camera_weight
        # Already-fused hypotheses or mixed labels.
        if "radar" in source:
            return self.config.radar_weight
        if "lidar" in source:
            return self.config.lidar_weight
        if "camera" in source:
            return self.config.camera_weight
        return 1.0


__all__ = ["SensorFusionConfig", "SensorFusionEngine"]
