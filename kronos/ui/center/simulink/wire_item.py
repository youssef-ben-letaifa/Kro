"""Graphics item representing a wire connection."""

from __future__ import annotations

import uuid

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import QGraphicsPathItem


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
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemIsSelectable, True)

    def update_path(self, start: QPointF, end: QPointF) -> None:
        self._start = start
        self._end = end
        path = QPainterPath(start)
        path.cubicTo(
            QPointF(start.x() + 60, start.y()),
            QPointF(end.x() - 60, end.y()),
            end,
        )
        self.setPath(path)
        self.update()

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self.isSelected():
            color = QColor("#1a6fff")
        elif self._hovered:
            color = QColor("#6a9acc")
        else:
            color = QColor("#4a7aaa")
        pen_width = 2.5 if self.isSelected() else 1.5
        pen = QPen(color, pen_width)
        painter.setPen(pen)
        painter.drawPath(self.path())
        if self._animated:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#79b8ff"))
            for idx in range(4):
                t = (self._global_phase + idx * 0.22) % 1.0
                point = self.path().pointAtPercent(t)
                painter.drawEllipse(point, 2.0, 2.0)
        direction = self.path().pointAtPercent(1.0) - self.path().pointAtPercent(0.95)
        self._draw_arrow(painter, self._end, direction)

    def hoverEnterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def _draw_arrow(self, painter: QPainter, end: QPointF, direction: QPointF) -> None:
        if direction.manhattanLength() == 0:
            return
        if self.isSelected():
            color = QColor("#1a6fff")
        elif self._hovered:
            color = QColor("#6a9acc")
        else:
            color = QColor("#4a7aaa")
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
