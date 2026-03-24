"""Graphics item representing a Aeon block."""

from __future__ import annotations

import uuid

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QGraphicsObject, QGraphicsSceneMouseEvent, QStyleOptionGraphicsItem

from kronos.ui.center.aeon.block_registry import get_block_def, resolve_type
from kronos.ui.theme.design_tokens import get_colors


class BlockItem(QGraphicsObject):
    """Visual block on the Aeon canvas with improved port rendering."""

    position_changed = pyqtSignal(str)
    block_double_clicked = pyqtSignal(str, dict)

    BLOCK_W = 110
    BLOCK_H = 60
    PORT_SIZE = 5

    def __init__(
        self,
        block_type: str,
        params: dict | None = None,
        inputs: int | None = None,
        outputs: int | None = None,
        *,
        wire_update_callback=None,
    ) -> None:
        super().__init__()
        self.block_id = str(uuid.uuid4())[:8]
        self.block_type = block_type
        self.params = dict(params) if params else {}
        self._wire_update_callback = wire_update_callback
        self._theme = "dark"
        self._colors = get_colors(self._theme)
        self._rotation_deg = 0.0

        # Resolve from registry for defaults
        bdef = get_block_def(block_type)
        if inputs is not None:
            self.num_inputs = inputs
        elif bdef:
            self.num_inputs = bdef.inputs
        else:
            self.num_inputs = self._infer_port_counts(block_type)[0]

        if outputs is not None:
            self.num_outputs = outputs
        elif bdef:
            self.num_outputs = bdef.outputs
        else:
            self.num_outputs = self._infer_port_counts(block_type)[1]

        self._snap_enabled = True

        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setTransformOriginPoint(self.BLOCK_W / 2, self.BLOCK_H / 2)
        self._hovered = False

    def boundingRect(self) -> QRectF:
        return QRectF(-5, -5, self.BLOCK_W + 10, self.BLOCK_H + 10)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        color = self._get_color()
        is_dark = self._theme == "dark"
        fill = QColor(color)
        fill.setAlpha(40 if is_dark else 58)
        if self._hovered:
            fill.setAlpha(58 if is_dark else 84)

        # Block body
        if self.isSelected():
            pen = QPen(QColor(self._colors["accent"]), 2.0)
        elif self._hovered:
            edge = QColor(color).lighter(130) if is_dark else QColor(color).darker(125)
            pen = QPen(edge, 1.5)
        else:
            pen = QPen(QColor(color), 1.2)

        painter.setPen(pen)
        painter.setBrush(fill)
        body = QRectF(0, 0, self.BLOCK_W, self.BLOCK_H)
        painter.drawRoundedRect(body, 5, 5)

        # ── Input ports (inward triangles) ──
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#ffffff" if is_dark else "#1f2937"))
        for i in range(self.num_inputs):
            y = self._port_y(i, self.num_inputs)
            self._draw_port_triangle(painter, 0, y, "input")

        # ── Output ports (outward triangles) ──
        for i in range(self.num_outputs):
            y = self._port_y(i, self.num_outputs)
            self._draw_port_triangle(painter, self.BLOCK_W, y, "output")

        # ── Block symbol (center) ──
        bdef = get_block_def(self.block_type)
        symbol = bdef.symbol if bdef else ""
        if not symbol:
            symbol = self.block_type[:6]

        symbol_color = QColor(color).lighter(150) if is_dark else QColor(color).darker(170)
        painter.setPen(symbol_color)
        font = QFont("Noto Sans", 11)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(body.adjusted(8, 2, -8, -14), Qt.AlignmentFlag.AlignCenter, symbol)

        # ── Block label (bottom) ──
        display = self._display_text()
        painter.setPen(QColor(self._colors["text_secondary"]))
        font2 = QFont("Noto Sans", 7)
        painter.setFont(font2)
        label_rect = QRectF(4, self.BLOCK_H - 16, self.BLOCK_W - 8, 14)
        painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, display)

    def _draw_port_triangle(self, painter: QPainter, x: float, y: float, kind: str) -> None:
        s = self.PORT_SIZE
        path = QPainterPath()
        if kind == "input":
            path.moveTo(x - s, y - s / 1.5)
            path.lineTo(x + 1, y)
            path.lineTo(x - s, y + s / 1.5)
        else:
            path.moveTo(x - 1, y - s / 1.5)
            path.lineTo(x + s, y)
            path.lineTo(x - 1, y + s / 1.5)
        path.closeSubpath()
        painter.drawPath(path)

    def _port_y(self, index: int, count: int) -> float:
        if count <= 1:
            return self.BLOCK_H / 2
        margin = 12
        usable = self.BLOCK_H - 2 * margin
        return margin + index * usable / max(1, count - 1)

    def get_input_pos(self, port_index: int) -> QPointF:
        return self.mapToScene(QPointF(0, self._port_y(port_index, self.num_inputs)))

    def get_output_pos(self, port_index: int) -> QPointF:
        return self.mapToScene(QPointF(self.BLOCK_W, self._port_y(port_index, self.num_outputs)))

    def _get_color(self) -> str:
        bdef = get_block_def(self.block_type)
        if bdef:
            return bdef.color
        # Fallback colors for legacy types
        fallback = {
            "Sources": "#e5a100",
            "Math": "#90c8ff",
            "Control": "#98c379",
            "Nonlinear": "#e06c75",
            "Sinks": "#1a4080",
        }
        for cat, color in fallback.items():
            if cat.lower() in self.block_type.lower():
                return color
        return "#6a7280"

    def _display_text(self) -> str:
        bt = self.block_type
        p = self.params

        if bt == "Gain":
            return f"K={p.get('gain', 1.0)}"
        if bt in {"PID Controller", "PID"}:
            return f"P={p.get('Kp', 1)} I={p.get('Ki', 0)} D={p.get('Kd', 0)}"
        if bt in {"Transfer Fcn", "TransferFunction"}:
            return f"{p.get('numerator', '[1]')}/{p.get('denominator', '[1,1]')}"
        if bt == "Step":
            return f"A={p.get('amplitude', 1)} t={p.get('step_time', 0)}"
        if bt in {"Sine Wave", "Sine"}:
            return f"f={p.get('frequency', 1)} A={p.get('amplitude', 1)}"
        if bt == "Constant":
            return f"={p.get('value', 1.0)}"
        if bt == "Saturation":
            return f"[{p.get('lower', -1)},{p.get('upper', 1)}]"
        if bt in {"Dead Zone", "DeadZone"}:
            return f"DZ [{p.get('lower', -0.1)},{p.get('upper', 0.1)}]"
        if bt in {"To Workspace", "ToWorkspace"}:
            return f"→ {p.get('variable', 'y')}"
        if bt == "Scope":
            return p.get("variable", "y")
        if bt == "Sum":
            return p.get("signs", "++")
        if bt == "Transport Delay":
            return f"τ={p.get('delay', 1.0)}"
        if bt == "Unit Delay":
            return "z⁻¹"
        if bt == "Pulse Generator":
            return f"T={p.get('period', 1)}"
        return bt

    @staticmethod
    def _infer_port_counts(block_type: str) -> tuple[int, int]:
        """Fallback port inference for unknown types."""
        resolved = resolve_type(block_type)
        bdef = get_block_def(resolved)
        if bdef:
            return bdef.inputs, bdef.outputs
        return 1, 1

    def set_snap(self, enabled: bool) -> None:
        self._snap_enabled = enabled

    def set_theme(self, theme: str) -> None:
        self._theme = theme if theme in {"dark", "light"} else "dark"
        self._colors = get_colors(self._theme)
        self.update()

    @property
    def rotation_angle(self) -> float:
        return float(self._rotation_deg)

    def set_rotation(self, angle_deg: float) -> None:
        normalized = float(angle_deg) % 360.0
        self._rotation_deg = normalized
        self.setRotation(normalized)
        if self._wire_update_callback:
            self._wire_update_callback(self.block_id)
        self.update()

    def rotate_cw(self) -> None:
        self.set_rotation(self._rotation_deg + 90.0)

    def rotate_ccw(self) -> None:
        self.set_rotation(self._rotation_deg - 90.0)

    def reset_rotation(self) -> None:
        self.set_rotation(0.0)

    def itemChange(self, change, value):
        if change == QGraphicsObject.GraphicsItemChange.ItemPositionChange and self._snap_enabled:
            grid = 20
            new_pos = value
            snapped = QPointF(round(new_pos.x() / grid) * grid, round(new_pos.y() / grid) * grid)
            if self._wire_update_callback:
                self._wire_update_callback()
            return snapped
        if change == QGraphicsObject.GraphicsItemChange.ItemPositionHasChanged:
            if self._wire_update_callback:
                self._wire_update_callback()
            self.position_changed.emit(self.block_id)
        return super().itemChange(change, value)

    def hoverEnterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        self.block_double_clicked.emit(self.block_id, dict(self.params))
        super().mouseDoubleClickEvent(event)
