"""OpenGL-based 3D viewport for the Autonomous Driving Toolbox."""

from __future__ import annotations

import numpy as np

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QPainter, QPen, QPolygonF
from PyQt6.QtOpenGLWidgets import QOpenGLWidget

from kronos.ui.theme.design_tokens import get_colors


class OpenGLHighwayView(QOpenGLWidget):
    """Lightweight OpenGL scene renderer with perspective projection."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._theme = "dark"
        self._frame = None
        self._road = None
        self._colors = get_colors(self._theme)
        self._gl_ready = False

    def set_theme(self, theme: str) -> None:
        del theme
        self._theme = "dark"
        self._colors = get_colors(self._theme)
        self.update()

    def update_scene(self, frame, road) -> None:
        self._frame = frame
        self._road = road
        self.update()

    def initializeGL(self) -> None:
        # Some PyQt6 builds do not expose QOpenGLContext.functions().
        # Keep initialization non-fatal and render with QPainter fallback.
        self._gl_ready = self.context() is not None

    def paintGL(self) -> None:
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.fillRect(self.rect(), QColor(self._colors["bg_primary"]))

            if not self._gl_ready:
                painter.setPen(QColor(self._colors["text_secondary"]))
                painter.drawText(
                    self.rect(),
                    Qt.AlignmentFlag.AlignCenter,
                    "OpenGL context unavailable",
                )
                return

            if self._frame is None or self._road is None:
                painter.setPen(QColor(self._colors["text_secondary"]))
                painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "3D scene unavailable")
                return

            self._draw_scene(painter)
        finally:
            painter.end()

    def _draw_scene(self, painter: QPainter) -> None:
        frame = self._frame
        road = self._road
        ego = frame.ego

        eye = np.array([ego.x - 28.0, ego.y + 15.0, 16.0], dtype=float)
        target = np.array([ego.x + 36.0, ego.y, 1.5], dtype=float)
        up = np.array([0.0, 0.0, 1.0], dtype=float)

        aspect = max(1.0, float(self.width()) / max(1.0, float(self.height())))
        view = _look_at(eye, target, up)
        proj = _perspective(np.deg2rad(55.0), aspect, 0.1, 1000.0)
        vp = proj @ view

        x_min = max(0.0, ego.x - 20.0)
        x_max = ego.x + 90.0
        xs = np.linspace(x_min, x_max, 80)

        self._draw_road_surface(painter, road, xs, vp)
        self._draw_trajectory(painter, frame.trajectory, vp)

        for veh in frame.vehicles:
            self._draw_vehicle_box(painter, veh, QColor("#cf6f6f"), vp)
        self._draw_vehicle_box(painter, frame.ego, QColor("#4f87ff"), vp)

        for obj in frame.fused_objects:
            pt = self._project_point(vp, obj.x, obj.y, 1.2)
            if pt is None:
                continue
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#8fe7a5"))
            painter.drawEllipse(pt, 3.2, 3.2)

    def _draw_road_surface(self, painter: QPainter, road, xs: np.ndarray, vp: np.ndarray) -> None:
        lane_count = len(road.lane_centers)
        if lane_count == 0:
            return

        lane_fill_a = QColor("#1e1e2e")
        lane_fill_b = QColor("#181825")

        for lane_idx in range(lane_count):
            width = road.lane_width(lane_idx)
            lower_pts: list[QPointF] = []
            upper_pts: list[QPointF] = []
            for x in xs:
                yc = road.lane_center(lane_idx, float(x))
                p_lo = self._project_point(vp, float(x), float(yc - 0.5 * width), 0.0)
                p_hi = self._project_point(vp, float(x), float(yc + 0.5 * width), 0.0)
                if p_lo is not None:
                    lower_pts.append(p_lo)
                if p_hi is not None:
                    upper_pts.append(p_hi)

            if len(lower_pts) > 2 and len(upper_pts) > 2:
                poly = QPolygonF(lower_pts + list(reversed(upper_pts)))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(lane_fill_a if lane_idx % 2 == 0 else lane_fill_b)
                painter.drawPolygon(poly)

        first_marks = road.lane_markings(float(xs[0]))
        line_color = QColor("#f9e2af")
        for mark_idx in range(len(first_marks)):
            pts: list[QPointF] = []
            for x in xs:
                marks = road.lane_markings(float(x))
                if mark_idx >= len(marks):
                    continue
                p = self._project_point(vp, float(x), float(marks[mark_idx]), 0.04)
                if p is not None:
                    pts.append(p)
            if len(pts) < 2:
                continue
            pen = QPen(line_color, 1.5 if mark_idx in {0, len(first_marks) - 1} else 1.0)
            if mark_idx not in {0, len(first_marks) - 1}:
                pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            for i in range(len(pts) - 1):
                painter.drawLine(pts[i], pts[i + 1])

    def _draw_trajectory(self, painter: QPainter, trajectory: list[tuple[float, float]], vp: np.ndarray) -> None:
        if len(trajectory) < 2:
            return
        points: list[QPointF] = []
        for x, y in trajectory:
            p = self._project_point(vp, float(x), float(y), 0.12)
            if p is not None:
                points.append(p)
        if len(points) < 2:
            return
        painter.setPen(QPen(QColor("#6fbcff"), 2.0))
        for i in range(len(points) - 1):
            painter.drawLine(points[i], points[i + 1])

    def _draw_vehicle_box(self, painter: QPainter, vehicle, color: QColor, vp: np.ndarray) -> None:
        corners = _vehicle_corners(vehicle)
        bottom = np.column_stack([corners, np.full(4, float(vehicle.z))])
        top = np.column_stack([corners, np.full(4, float(vehicle.z + 1.45))])

        painter.setPen(QPen(color, 1.4))
        for i in range(4):
            j = (i + 1) % 4
            b0 = self._project_vec(vp, bottom[i])
            b1 = self._project_vec(vp, bottom[j])
            t0 = self._project_vec(vp, top[i])
            t1 = self._project_vec(vp, top[j])
            if b0 is not None and b1 is not None:
                painter.drawLine(b0, b1)
            if t0 is not None and t1 is not None:
                painter.drawLine(t0, t1)
            if b0 is not None and t0 is not None:
                painter.drawLine(b0, t0)

    def _project_point(self, vp: np.ndarray, x: float, y: float, z: float) -> QPointF | None:
        vec = np.array([x, y, z, 1.0], dtype=float)
        clip = vp @ vec
        w = float(clip[3])
        if w <= 1e-6:
            return None
        ndc = clip[:3] / w
        if ndc[0] < -1.2 or ndc[0] > 1.2 or ndc[1] < -1.2 or ndc[1] > 1.2:
            return None
        sx = (float(ndc[0]) * 0.5 + 0.5) * self.width()
        sy = (1.0 - (float(ndc[1]) * 0.5 + 0.5)) * self.height()
        return QPointF(sx, sy)

    def _project_vec(self, vp: np.ndarray, xyz: np.ndarray) -> QPointF | None:
        return self._project_point(vp, float(xyz[0]), float(xyz[1]), float(xyz[2]))


def _look_at(eye: np.ndarray, target: np.ndarray, up: np.ndarray) -> np.ndarray:
    f = target - eye
    f = f / max(np.linalg.norm(f), 1e-8)
    u = up / max(np.linalg.norm(up), 1e-8)
    s = np.cross(f, u)
    s = s / max(np.linalg.norm(s), 1e-8)
    u = np.cross(s, f)

    m = np.eye(4, dtype=float)
    m[0, :3] = s
    m[1, :3] = u
    m[2, :3] = -f
    m[0, 3] = -np.dot(s, eye)
    m[1, 3] = -np.dot(u, eye)
    m[2, 3] = np.dot(f, eye)
    return m


def _perspective(fov_y_rad: float, aspect: float, near: float, far: float) -> np.ndarray:
    f = 1.0 / np.tan(0.5 * fov_y_rad)
    m = np.zeros((4, 4), dtype=float)
    m[0, 0] = f / max(aspect, 1e-6)
    m[1, 1] = f
    m[2, 2] = (far + near) / (near - far)
    m[2, 3] = (2.0 * far * near) / (near - far)
    m[3, 2] = -1.0
    return m


def _vehicle_corners(vehicle) -> np.ndarray:
    c = float(np.cos(vehicle.yaw))
    s = float(np.sin(vehicle.yaw))
    hl = 0.5 * float(vehicle.length)
    hw = 0.5 * float(vehicle.width)
    local = np.array(
        [
            [hl, hw],
            [hl, -hw],
            [-hl, -hw],
            [-hl, hw],
        ],
        dtype=float,
    )
    rot = np.array([[c, -s], [s, c]], dtype=float)
    return local @ rot.T + np.array([vehicle.x, vehicle.y], dtype=float)


__all__ = ["OpenGLHighwayView"]
