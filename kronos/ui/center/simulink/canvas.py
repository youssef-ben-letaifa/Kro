"""Simulink canvas implementation."""

from __future__ import annotations

import json
from collections import defaultdict, deque

from PyQt6.QtCore import QPointF, QRect, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QImage, QKeySequence, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QWidget,
)

from kronos.native import CanvasRenderer, native_available
from kronos.ui.center.simulink.block_item import BlockItem
from kronos.ui.center.simulink.block_param_dialog import BlockParamDialog
from kronos.ui.center.simulink.block_registry import SOURCE_TYPES, SINK_TYPES
from kronos.ui.center.simulink.wire_item import WireItem


class SimulinkCanvas(QGraphicsView):
    """Canvas for block diagram editing."""

    block_double_clicked = pyqtSignal(str, dict)
    simulation_requested = pyqtSignal(dict)
    diagram_changed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._scene = QGraphicsScene()
        self.setScene(self._scene)
        self._scene.setSceneRect(-2000, -2000, 4000, 4000)
        self._blocks: dict[str, BlockItem] = {}
        self._wires: dict[str, WireItem] = {}
        self._pending_wire: QGraphicsPathItem | None = None
        self._pending_start: dict | None = None
        self._scale_factor = 1.0
        self._connect_mode = True
        self._snap_to_grid = True
        self._grid_spacing = 20
        self._wire_animation_enabled = False
        self._flow_phase = 0.0
        self._native_renderer = CanvasRenderer()
        self._native_enabled = native_available()

        self.setAcceptDrops(True)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setBackgroundBrush(QBrush(QColor("#080c14")))
        self._flow_timer = QTimer(self)
        self._flow_timer.timeout.connect(self._on_flow_tick)
        self._build_overlay_widgets()

    def drawBackground(self, painter: QPainter, rect) -> None:  # noqa: N802
        painter.save()
        painter.setPen(QColor("#1a1f2a"))
        spacing = self._grid_spacing
        left = int(rect.left()) - (int(rect.left()) % spacing)
        top = int(rect.top()) - (int(rect.top()) % spacing)
        right = int(rect.right()) + spacing
        bottom = int(rect.bottom()) + spacing
        for x_pos in range(left, right, spacing):
            for y_pos in range(top, bottom, spacing):
                painter.drawPoint(x_pos, y_pos)
        self._draw_native_overlay(painter, rect)
        painter.restore()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        margin = 10
        if hasattr(self, "_zoom_widget"):
            zoom_w = self._zoom_widget.sizeHint().width()
            zoom_h = self._zoom_widget.sizeHint().height()
            self._zoom_widget.setGeometry(
                self.viewport().width() - zoom_w - margin,
                self.viewport().height() - zoom_h - 56,
                zoom_w,
                zoom_h,
            )
        if hasattr(self, "_status_widget"):
            self._status_widget.setGeometry(
                margin,
                self.viewport().height() - 36,
                max(220, self.viewport().width() - 2 * margin),
                26,
            )

    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            factor = 1.15 if delta > 0 else 0.87
            next_scale = self._scale_factor * factor
            if 0.1 <= next_scale <= 5.0:
                self.scale(factor, factor)
                self._scale_factor = next_scale
                if hasattr(self, "_zoom_label"):
                    self._zoom_label.setText(f"{int(self._scale_factor * 100)}%")
            return
        super().wheelEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            super().mousePressEvent(event)
            return

        if event.button() == Qt.MouseButton.LeftButton and self._connect_mode:
            scene_pos = self.mapToScene(event.position().toPoint())
            
            # Use self._scene.items to avoid being blocked by the pending wire
            items = self._scene.items(scene_pos, Qt.ItemSelectionMode.IntersectsItemShape, Qt.SortOrder.DescendingOrder, self.transform())
            for item in items:
                if isinstance(item, BlockItem):
                    port_info = self._port_at(item, scene_pos)
                    if port_info is not None:
                        port_type, port_index = port_info
                        if port_type == "output" and self._pending_start is None:
                            self._start_pending_wire(item, port_index)
                            return
                    break # Only check the topmost BlockItem
                    
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._pending_wire is not None and self._pending_start is not None:
            start = self._pending_start["pos"]
            end = self.mapToScene(event.position().toPoint())
            path = QPainterPath(start)
            path.cubicTo(
                QPointF(start.x() + 60, start.y()),
                QPointF(end.x() - 60, end.y()),
                end,
            )
            self._pending_wire.setPath(path)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            
        elif event.button() == Qt.MouseButton.LeftButton and self._connect_mode and self._pending_start is not None:
            scene_pos = self.mapToScene(event.position().toPoint())
            items = self._scene.items(scene_pos, Qt.ItemSelectionMode.IntersectsItemShape, Qt.SortOrder.DescendingOrder, self.transform())
            connected = False
            for item in items:
                if isinstance(item, BlockItem):
                    port_info = self._port_at(item, scene_pos)
                    if port_info is not None:
                        port_type, port_index = port_info
                        if port_type == "input":
                            self._finish_pending_wire(item, port_index)
                            connected = True
                            break
                    break # Only check the topmost BlockItem
            if not connected:
                self._clear_pending_wire()
                
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Delete:
            self._delete_selected()
            return
        if event.matches(QKeySequence.StandardKey.SelectAll):
            self._scene.clearSelection()
            for block in self._blocks.values():
                block.setSelected(True)
            for wire in self._wires.values():
                wire.setSelected(True)
            return
        if event.key() == Qt.Key.Key_L and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.auto_arrange_left_to_right()
            return
        if event.key() == Qt.Key.Key_Escape and self._pending_wire is not None:
            self._clear_pending_wire()
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event) -> None:
        scene_pos = self.mapToScene(event.pos())
        item = self._scene.itemAt(scene_pos, self.transform())
        if isinstance(item, BlockItem):
            menu = QMenu(self)
            edit_action = menu.addAction("Edit Parameters...")
            delete_action = menu.addAction("Delete Block")
            dup_action = menu.addAction("Duplicate")
            scope_action = menu.addAction("Branch to Scope")
            auto_action = menu.addAction("Auto Arrange")
            action = menu.exec(event.globalPos())
            if action == edit_action:
                self._open_param_dialog(item)
            elif action == delete_action:
                self.remove_block(item.block_id)
            elif action == dup_action:
                self._duplicate_block(item)
            elif action == scope_action:
                self._branch_scope(item)
            elif action == auto_action:
                self.auto_arrange_left_to_right()
            return
        super().contextMenuEvent(event)

    def _open_param_dialog(self, block: BlockItem) -> None:
        dialog = BlockParamDialog(block.block_type, block.params, self)
        if dialog.exec():
            block.params = dialog.get_params()
            block.update()
            self.diagram_changed.emit()

    def _duplicate_block(self, block: BlockItem) -> None:
        new_pos = block.scenePos() + QPointF(20, 20)
        self.add_block(
            block.block_type,
            dict(block.params),
            new_pos,
            input_count=block.num_inputs,
            output_count=block.num_outputs,
        )

    def _branch_scope(self, block: BlockItem) -> None:
        if block.num_outputs <= 0:
            return
        scope = self.add_block("Scope", {"variable": "y"}, block.scenePos() + QPointF(180, 100))
        self.add_wire(block.block_id, 0, scope.block_id, 0)

    # ─── Port detection ──────────────────────────────────────────

    @staticmethod
    def _port_at(block: BlockItem, scene_pos: QPointF) -> tuple[str, int] | None:
        """Detect if a scene position is near a port on the block."""
        hit_distance = 14.0
        for i in range(block.num_inputs):
            port_pos = block.get_input_pos(i)
            if (scene_pos - port_pos).manhattanLength() < hit_distance:
                return ("input", i)
        for i in range(block.num_outputs):
            port_pos = block.get_output_pos(i)
            if (scene_pos - port_pos).manhattanLength() < hit_distance:
                return ("output", i)
        return None

    def _start_pending_wire(self, block: BlockItem, port_index: int) -> None:
        start = block.get_output_pos(port_index)
        self._pending_start = {"block": block, "port": port_index, "pos": start}
        self._pending_wire = QGraphicsPathItem()
        self._pending_wire.setPen(QPen(QColor("#6a9acc"), 1.6))
        self._scene.addItem(self._pending_wire)

    def _finish_pending_wire(self, dest_block: BlockItem, dest_port: int) -> None:
        if self._pending_start is None:
            return
        source_block = self._pending_start["block"]
        source_port = int(self._pending_start["port"])
        if source_block.block_id == dest_block.block_id:
            self._clear_pending_wire()
            return
        self.add_wire(source_block.block_id, source_port, dest_block.block_id, dest_port)
        self._clear_pending_wire()

    def _clear_pending_wire(self) -> None:
        if self._pending_wire is not None:
            self._scene.removeItem(self._pending_wire)
        self._pending_wire = None
        self._pending_start = None

    def _build_overlay_widgets(self) -> None:
        self._zoom_widget = QFrame(self.viewport())
        self._zoom_widget.setObjectName("sim_zoom_controls")
        self._zoom_widget.setStyleSheet(
            "#sim_zoom_controls {"
            " background: rgba(22, 27, 34, 220);"
            " border: 1px solid #30363d;"
            " border-radius: 6px;"
            "}"
        )
        zoom_layout = QHBoxLayout(self._zoom_widget)
        zoom_layout.setContentsMargins(6, 4, 6, 4)
        zoom_layout.setSpacing(6)
        zoom_out = QPushButton("−")
        zoom_in = QPushButton("+")
        zoom_out.setFixedWidth(24)
        zoom_in.setFixedWidth(24)
        zoom_out.clicked.connect(self._zoom_out)
        zoom_in.clicked.connect(self._zoom_in)
        self._zoom_label = QLabel("100%")
        self._zoom_label.setMinimumWidth(48)
        self._zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        zoom_layout.addWidget(zoom_out)
        zoom_layout.addWidget(self._zoom_label)
        zoom_layout.addWidget(zoom_in)
        self._zoom_widget.show()

        self._status_widget = QFrame(self.viewport())
        self._status_widget.setObjectName("sim_runtime_status")
        self._status_widget.setStyleSheet(
            "#sim_runtime_status {"
            " background: rgba(13, 17, 23, 230);"
            " border: 1px solid #30363d;"
            " border-radius: 6px;"
            "}"
        )
        status_layout = QHBoxLayout(self._status_widget)
        status_layout.setContentsMargins(8, 2, 8, 2)
        status_layout.setSpacing(10)
        self._sim_time_label = QLabel("t: 0.000 s")
        self._sim_steps_label = QLabel("steps: 0")
        self._sim_errors_label = QLabel("errors: 0")
        self._sim_errors_label.setStyleSheet("color: #8b949e;")
        status_layout.addWidget(self._sim_time_label)
        status_layout.addWidget(self._sim_steps_label)
        status_layout.addWidget(self._sim_errors_label)
        status_layout.addStretch(1)
        self._status_widget.show()

    def _zoom_in(self) -> None:
        factor = 1.15
        next_scale = self._scale_factor * factor
        if 0.1 <= next_scale <= 5.0:
            self.scale(factor, factor)
            self._scale_factor = next_scale
            self._zoom_label.setText(f"{int(self._scale_factor * 100)}%")

    def _zoom_out(self) -> None:
        factor = 0.87
        next_scale = self._scale_factor * factor
        if 0.1 <= next_scale <= 5.0:
            self.scale(factor, factor)
            self._scale_factor = next_scale
            self._zoom_label.setText(f"{int(self._scale_factor * 100)}%")

    def set_runtime_status(self, sim_time: float, step_count: int, error_count: int = 0) -> None:
        self._sim_time_label.setText(f"t: {sim_time:.3f} s")
        self._sim_steps_label.setText(f"steps: {step_count}")
        if error_count > 0:
            self._sim_errors_label.setStyleSheet("color: #f85149;")
        else:
            self._sim_errors_label.setStyleSheet("color: #8b949e;")
        self._sim_errors_label.setText(f"errors: {error_count}")

    def set_wire_animation(self, enabled: bool) -> None:
        self._wire_animation_enabled = enabled
        if enabled:
            if not self._flow_timer.isActive():
                self._flow_timer.start(45)
        else:
            self._flow_timer.stop()
        for wire in self._wires.values():
            wire.set_animation_enabled(enabled)

    def _on_flow_tick(self) -> None:
        self._flow_phase = (self._flow_phase + 0.02) % 1.0
        WireItem.set_global_phase(self._flow_phase)
        if self._native_enabled:
            try:
                self._native_renderer.set_animation_phase(self._flow_phase)
            except Exception:
                pass
        for wire in self._wires.values():
            wire.update()

    def _draw_native_overlay(self, painter: QPainter, rect: QRect) -> None:
        if not self._native_enabled:
            return
        if not self._blocks and not self._wires:
            return
        try:
            self._native_renderer.clear()
            offset_x = float(rect.left())
            offset_y = float(rect.top())
            for wire in self._wires.values():
                source_block = self._blocks.get(wire.source_block_id)
                dest_block = self._blocks.get(wire.dest_block_id)
                if source_block is None or dest_block is None:
                    continue
                start = source_block.get_output_pos(wire.source_port)
                end = dest_block.get_input_pos(wire.dest_port)
                self._native_renderer.render_wire(
                    start.x() - offset_x,
                    start.y() - offset_y,
                    end.x() - offset_x,
                    end.y() - offset_y,
                    self._wire_animation_enabled,
                )
            for block in self._blocks.values():
                pos = block.scenePos()
                color = block._get_color() if hasattr(block, "_get_color") else "#58A6FF"
                self._native_renderer.render_block(
                    block.block_id,
                    pos.x() - offset_x,
                    pos.y() - offset_y,
                    float(block.BLOCK_W),
                    float(block.BLOCK_H),
                    block.block_type,
                    color,
                )
            png = self._native_renderer.rasterize_png(
                int(max(1, rect.width())),
                int(max(1, rect.height())),
                "#00000000",
            )
            if not png:
                return
            image = QImage.fromData(png, "PNG")
            if image.isNull():
                return
            painter.save()
            painter.setOpacity(0.2)
            painter.drawImage(QPointF(rect.left(), rect.top()), image)
            painter.restore()
        except Exception:
            # Native renderer is optional; keep canvas functional on failure.
            return

    # ─── Drag & Drop ─────────────────────────────────────────────

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasFormat("application/x-kronos-block"):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasFormat("application/x-kronos-block"):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        if not event.mimeData().hasFormat("application/x-kronos-block"):
            super().dropEvent(event)
            return
        data = event.mimeData().data("application/x-kronos-block")
        try:
            payload = json.loads(bytes(data).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return
        block_type = str(payload.get("type", "Block"))
        params = payload.get("params", {})
        input_count = int(payload.get("inputs", 1))
        output_count = int(payload.get("outputs", 1))
        pos = self.mapToScene(event.position().toPoint())
        self.add_block(block_type, params, pos, input_count=input_count, output_count=output_count)
        event.acceptProposedAction()

    # ─── Block & Wire Management ─────────────────────────────────

    def add_block(
        self,
        block_type: str,
        params: dict,
        pos: QPointF,
        input_count: int | None = None,
        output_count: int | None = None,
        block_id: str | None = None,
    ) -> BlockItem:
        block = BlockItem(
            block_type=block_type,
            params=params,
            inputs=input_count,
            outputs=output_count,
            wire_update_callback=lambda bid=None: self._update_wires_for_block(bid or block.block_id),
        )
        if block_id:
            block.block_id = block_id
        block.set_snap(self._snap_to_grid)
        block.setPos(pos)
        block.block_double_clicked.connect(self.block_double_clicked.emit)
        self._scene.addItem(block)
        self._blocks[block.block_id] = block
        self.diagram_changed.emit()
        return block

    def remove_block(self, block_id: str) -> None:
        block = self._blocks.pop(block_id, None)
        if block is None:
            return
        for wire_id in list(self._wires.keys()):
            wire = self._wires[wire_id]
            if wire.source_block_id == block_id or wire.dest_block_id == block_id:
                self.remove_wire(wire_id)
        self._scene.removeItem(block)
        self.diagram_changed.emit()

    def add_wire(self, source_id: str, source_port: int, dest_id: str, dest_port: int) -> WireItem | None:
        for wire in self._wires.values():
            if (
                wire.source_block_id == source_id
                and wire.source_port == source_port
                and wire.dest_block_id == dest_id
                and wire.dest_port == dest_port
            ):
                return None
        for wire_id, wire in list(self._wires.items()):
            if wire.dest_block_id == dest_id and wire.dest_port == dest_port:
                self.remove_wire(wire_id)

        wire = WireItem(source_id, source_port, dest_id, dest_port)
        wire.set_animation_enabled(self._wire_animation_enabled)
        self._scene.addItem(wire)
        self._wires[wire.wire_id] = wire
        self._update_wire_path(wire)
        self.diagram_changed.emit()
        return wire

    def remove_wire(self, wire_id: str) -> None:
        wire = self._wires.pop(wire_id, None)
        if wire is None:
            return
        self._scene.removeItem(wire)
        self.diagram_changed.emit()

    def _update_wire_path(self, wire: WireItem) -> None:
        source_block = self._blocks.get(wire.source_block_id)
        dest_block = self._blocks.get(wire.dest_block_id)
        if not source_block or not dest_block:
            return
        start = source_block.get_output_pos(wire.source_port)
        end = dest_block.get_input_pos(wire.dest_port)
        wire.update_path(start, end)

    def _update_wires_for_block(self, block_id: str) -> None:
        for wire in self._wires.values():
            if wire.source_block_id == block_id or wire.dest_block_id == block_id:
                self._update_wire_path(wire)

    def _delete_selected(self) -> None:
        for item in list(self._scene.selectedItems()):
            if isinstance(item, BlockItem):
                self.remove_block(item.block_id)
            elif isinstance(item, WireItem):
                self.remove_wire(item.wire_id)

    # ─── Serialization ───────────────────────────────────────────

    def get_diagram(self) -> dict:
        blocks = []
        for block in self._blocks.values():
            pos = block.scenePos()
            blocks.append(
                {
                    "id": block.block_id,
                    "type": block.block_type,
                    "params": dict(block.params),
                    "inputs": block.num_inputs,
                    "outputs": block.num_outputs,
                    "pos": [pos.x(), pos.y()],
                }
            )
        wires = []
        for wire in self._wires.values():
            wires.append(
                {
                    "id": wire.wire_id,
                    "source": wire.source_block_id,
                    "source_port": wire.source_port,
                    "dest": wire.dest_block_id,
                    "dest_port": wire.dest_port,
                }
            )
        return {"blocks": blocks, "wires": wires}

    def load_diagram(self, data: dict) -> None:
        self.clear_canvas()
        id_map: dict[str, str] = {}
        for block_data in data.get("blocks", []):
            pos_data = block_data.get("pos", [0, 0])
            pos = QPointF(float(pos_data[0]), float(pos_data[1]))
            original_id = str(block_data.get("id", ""))
            block = self.add_block(
                block_type=str(block_data.get("type", "Block")),
                params=dict(block_data.get("params", {})),
                pos=pos,
                input_count=int(block_data.get("inputs", 1)),
                output_count=int(block_data.get("outputs", 1)),
                block_id=original_id if original_id and original_id not in self._blocks else None,
            )
            if original_id:
                id_map[original_id] = block.block_id

        for wire_data in data.get("wires", []):
            src = id_map.get(str(wire_data.get("source", "")), str(wire_data.get("source", "")))
            dst = id_map.get(str(wire_data.get("dest", "")), str(wire_data.get("dest", "")))
            if src in self._blocks and dst in self._blocks:
                self.add_wire(
                    source_id=src,
                    source_port=int(wire_data.get("source_port", 0)),
                    dest_id=dst,
                    dest_port=int(wire_data.get("dest_port", 0)),
                )

    def clear_canvas(self) -> None:
        self.set_wire_animation(False)
        self._scene.clear()
        self._blocks.clear()
        self._wires.clear()
        self._pending_wire = None
        self._pending_start = None
        self.set_runtime_status(0.0, 0, 0)
        self.diagram_changed.emit()

    def set_connect_mode(self, enabled: bool) -> None:
        """Enable or disable click-to-connect mode."""
        self._connect_mode = enabled
        if not enabled:
            self._clear_pending_wire()

    def set_snap_to_grid(self, enabled: bool) -> None:
        """Enable or disable block snapping to grid."""
        self._snap_to_grid = enabled
        for block in self._blocks.values():
            block.set_snap(enabled)

    # ─── Validation ──────────────────────────────────────────────

    def validate_diagram(self) -> list[str]:
        """Return list of validation issues for current model."""
        issues: list[str] = []
        if not self._blocks:
            return ["Diagram has no blocks."]

        incoming: defaultdict[str, int] = defaultdict(int)
        outgoing: defaultdict[str, int] = defaultdict(int)
        dest_port_seen: set[tuple[str, int]] = set()
        for wire in self._wires.values():
            incoming[wire.dest_block_id] += 1
            outgoing[wire.source_block_id] += 1
            key = (wire.dest_block_id, wire.dest_port)
            if key in dest_port_seen:
                issues.append(f"Multiple wires connected to same input port on {wire.dest_block_id}.")
            dest_port_seen.add(key)

        for block in self._blocks.values():
            in_count = incoming.get(block.block_id, 0)
            out_count = outgoing.get(block.block_id, 0)
            if block.block_type not in SOURCE_TYPES and block.num_inputs > 0 and in_count == 0:
                issues.append(f"{block.block_type} [{block.block_id}] has no input.")
            if block.block_type not in SINK_TYPES and block.num_outputs > 0 and out_count == 0:
                issues.append(f"{block.block_type} [{block.block_id}] has no downstream connection.")
            if block.block_type in SINK_TYPES and in_count == 0:
                issues.append(f"{block.block_type} [{block.block_id}] has no signal connected.")

        return issues

    # ─── Auto Arrange ────────────────────────────────────────────

    def auto_arrange_left_to_right(self) -> None:
        """Arrange blocks in layers from sources to sinks."""
        indegree = {block_id: 0 for block_id in self._blocks}
        adjacency: defaultdict[str, list[str]] = defaultdict(list)
        for wire in self._wires.values():
            adjacency[wire.source_block_id].append(wire.dest_block_id)
            indegree[wire.dest_block_id] = indegree.get(wire.dest_block_id, 0) + 1

        queue_nodes = deque([node for node, degree in indegree.items() if degree == 0])
        order: list[str] = []
        while queue_nodes:
            node = queue_nodes.popleft()
            order.append(node)
            for target in adjacency[node]:
                indegree[target] -= 1
                if indegree[target] == 0:
                    queue_nodes.append(target)

        for node in self._blocks:
            if node not in order:
                order.append(node)

        level: dict[str, int] = {}
        for node in order:
            parents = [wire.source_block_id for wire in self._wires.values() if wire.dest_block_id == node]
            level[node] = 0 if not parents else max(level.get(parent, 0) + 1 for parent in parents)

        by_level: defaultdict[int, list[str]] = defaultdict(list)
        for node, node_level in level.items():
            by_level[node_level].append(node)

        for node_level, nodes in by_level.items():
            nodes.sort()
            for idx, node_id in enumerate(nodes):
                x_pos = 100 + node_level * 230
                y_pos = 110 + idx * 110
                self._blocks[node_id].setPos(QPointF(x_pos, y_pos))
                self._update_wires_for_block(node_id)

        self.diagram_changed.emit()

    # ─── Demo ────────────────────────────────────────────────────

    def load_demo_diagram(self) -> None:
        self.clear_canvas()
        step = self.add_block(
            "Step",
            {"amplitude": 1.0, "step_time": 0.0, "initial": 0.0},
            QPointF(100, 200),
            input_count=0,
            output_count=1,
        )
        pid = self.add_block(
            "PID Controller",
            {"Kp": 1.0, "Ki": 0.0, "Kd": 0.0},
            QPointF(320, 200),
            input_count=1,
            output_count=1,
        )
        tf = self.add_block(
            "Transfer Fcn",
            {"numerator": "[1]", "denominator": "[1, 1]"},
            QPointF(540, 200),
            input_count=1,
            output_count=1,
        )
        scope = self.add_block("Scope", {"variable": "y"}, QPointF(760, 140), input_count=1, output_count=0)
        ws = self.add_block(
            "To Workspace",
            {"variable": "sim_output"},
            QPointF(760, 280),
            input_count=1,
            output_count=0,
        )
        self.add_wire(step.block_id, 0, pid.block_id, 0)
        self.add_wire(pid.block_id, 0, tf.block_id, 0)
        self.add_wire(tf.block_id, 0, scope.block_id, 0)
        self.add_wire(tf.block_id, 0, ws.block_id, 0)
