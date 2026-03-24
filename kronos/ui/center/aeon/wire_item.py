"""Graphics item representing a wire connection."""

from __future__ import annotations

import uuid

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import QGraphicsPathItem
from kronos.ui.theme.design_tokens import get_colors


class WireItem(QGraphicsPathItem):
    """Wire connecting two blocks."""

    _global_phase = 0.0

    def __init__(self, source_block_id: str, source_port: int,
                 dest_block_id: str, dest_port: int) -> None:
        super().__init__()
        self.source_block_id = source_block_id
        self.source_port = source_port
        self.dest_block_id = dest_block_id
        self.dest_port = dest_port
        self.wire_id = str(uuid.uuid4())[:8]
        self._start = QPointF()
        self._end = QPointF()
        self._hovered = False
        self._animated = False
        self._theme = "dark"
        self._colors = get_colors(self._theme)
        self._grid_spacing = 20
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemIsSelectable, True)

    def update_path(self, start: QPointF, end: QPointF) -> None:
        self._start = start
        self._end = end
        path = self.build_orthogonal_path(start, end, self._grid_spacing)
        self.setPath(path)
        self.update()

    @staticmethod
    def _snap(value: float, spacing: int) -> float:
        return round(value / spacing) * spacing

    @staticmethod
    def _compress_points(points: list[QPointF]) -> list[QPointF]:
        if not points:
            return []
        compact: list[QPointF] = [points[0]]
        for point in points[1:]:
            if (point - compact[-1]).manhattanLength() > 0.1:
                compact.append(point)
        if len(compact) <= 2:
            return compact
        out: list[QPointF] = [compact[0]]
        for idx in range(1, len(compact) - 1):
            prev_point = out[-1]
            curr_point = compact[idx]
            next_point = compact[idx + 1]
            same_x = abs(prev_point.x() - curr_point.x()) < 0.1 and abs(curr_point.x() - next_point.x()) < 0.1
            same_y = abs(prev_point.y() - curr_point.y()) < 0.1 and abs(curr_point.y() - next_point.y()) < 0.1
            if same_x or same_y:
                continue
            out.append(curr_point)
        out.append(compact[-1])
        return out

    @classmethod
    def build_orthogonal_path(cls, start: QPointF, end: QPointF, grid_spacing: int = 20) -> QPainterPath:
        grid = max(5, int(grid_spacing))
        stub = max(grid, 12)

        start_stub_x = start.x() + stub
        end_stub_x = end.x() - stub
        start_grid_y = cls._snap(start.y(), grid)
        end_grid_y = cls._snap(end.y(), grid)

        if end_stub_x >= start_stub_x + grid:
            lane_x = cls._snap((start_stub_x + end_stub_x) / 2.0, grid)
        else:
            lane_x = cls._snap(max(start_stub_x, end_stub_x) + 3 * grid, grid)

        points = [
            start,
            QPointF(start_stub_x, start.y()),
            QPointF(start_stub_x, start_grid_y),
            QPointF(lane_x, start_grid_y),
            QPointF(lane_x, end_grid_y),
            QPointF(end_stub_x, end_grid_y),
            QPointF(end_stub_x, end.y()),
            end,
        ]
        points = cls._compress_points(points)

        if not points:
            return QPainterPath()
        path = QPainterPath(points[0])
        for point in points[1:]:
            path.lineTo(point)
        return path

    def set_theme(self, theme: str) -> None:
        self._theme = theme if theme in {"dark", "light"} else "dark"
        self._colors = get_colors(self._theme)
        self.update()

    def set_grid_spacing(self, spacing: int) -> None:
        self._grid_spacing = max(5, int(spacing))
        if not self._start.isNull() or not self._end.isNull():
            self.update_path(self._start, self._end)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self.isSelected():
            color = QColor(self._colors["accent"])
        elif self._hovered:
            color = QColor(self._colors["accent_hover"])
        else:
            base = QColor(self._colors["accent"])
            color = base.darker(120) if self._theme == "light" else base.lighter(115)
        pen_width = 2.4 if self.isSelected() else 1.7
        pen = QPen(color, pen_width)
        painter.setPen(pen)
        painter.drawPath(self.path())
        if self._animated:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(self._colors["accent_hover"]))
            for idx in range(4):
                t = (self._global_phase + idx * 0.22) % 1.0
                point = self.path().pointAtPercent(t)
                painter.drawEllipse(point, 2.0, 2.0)
        direction = self.path().pointAtPercent(1.0) - self.path().pointAtPercent(0.95)
        self._draw_arrow(painter, self._end, direction, color)

    def hoverEnterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def _draw_arrow(self, painter: QPainter, end: QPointF, direction: QPointF, color: QColor) -> None:
        if direction.manhattanLength() == 0:
            return
        painter.setPen(color)
        painter.setBrush(color)
        length = (direction.x() ** 2 + direction.y() ** 2) ** 0.5 or 1.0
        norm = QPointF(direction.x() / length, direction.y() / length)
        right = QPointF(-norm.y(), norm.x())
        size = 6
        p1 = end
        p2 = end - norm * size + right * (size / 2)
        p3 = end - norm * size - right * (size / 2)
        painter.drawPolygon(QPolygonF([p1, p2, p3]))

    def set_animation_enabled(self, enabled: bool) -> None:
        self._animated = enabled
        self.update()

    @classmethod
    def set_global_phase(cls, phase: float) -> None:
        cls._global_phase = phase
