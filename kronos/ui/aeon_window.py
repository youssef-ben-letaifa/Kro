"""Standalone Aeon-style window for Kronos – MATLAB 2025 UI."""

from __future__ import annotations

import json
from PyQt6.QtCore import QMimeData, QObject, QPointF, QRectF, QSize, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QDrag, QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from kronos.ui.center.aeon.block_param_dialog import BlockParamDialog
from kronos.ui.center.aeon.block_registry import (
    ALL_CATEGORIES,
    BlockDef,
    get_block_def,
)
from kronos.ui.center.aeon.canvas import AeonCanvas
from kronos.ui.center.aeon.simulator import DiagramSimulator
from kronos.ui.left_panel import BlockTreeWidget
from kronos.ui.theme.design_tokens import get_colors
from kronos.ui.theme.fluent_icons import icon_for


# ═══════════════════════════════════════════════════════════════════════════
# Ribbon helpers
# ═══════════════════════════════════════════════════════════════════════════

class _RibbonGroup(QFrame):
    """Group of buttons inside a ribbon tab (e.g. FILE, SIMULATE)."""

    def __init__(self, title: str) -> None:
        super().__init__()
        self.setObjectName("ribbon_group")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 2)
        layout.setSpacing(3)
        self.row = QHBoxLayout()
        self.row.setContentsMargins(0, 0, 0, 0)
        self.row.setSpacing(5)
        layout.addLayout(self.row, 1)
        label = QLabel(title)
        label.setObjectName("ribbon_group_title")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

    def add_widget(self, widget: QWidget) -> None:
        self.row.addWidget(widget)

    def finalize(self) -> None:
        self.row.addStretch(1)


def _sim_icon(name: str, color: str | None = None) -> QIcon:
    """Create a Fluent icon for the Aeon ribbon."""
    tint = color or get_colors("dark")["text_primary"]
    return icon_for(name, size=22, color=tint)


def _ribbon_button(
    text: str,
    tooltip: str,
    icon_name: str,
    icon_role: str = "text_secondary",
    *,
    checkable: bool = False,
) -> QToolButton:
    base_colors = get_colors("dark")
    icon_color = base_colors.get(icon_role, icon_role)
    btn = QToolButton()
    btn.setObjectName("ribbon_action")
    btn.setText(text)
    btn.setToolTip(tooltip)
    btn.setIcon(_sim_icon(icon_name, icon_color))
    btn.setIconSize(QSize(22, 22))
    btn.setMinimumSize(32, 32)
    btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
    btn.setCheckable(checkable)
    btn.setProperty("icon_name", icon_name)
    btn.setProperty("icon_role", icon_role)
    return btn


# ═══════════════════════════════════════════════════════════════════════════
# Library Browser
# ═══════════════════════════════════════════════════════════════════════════

class _BlockPreviewGrid(QScrollArea):
    """Right pane of the library browser showing block icons in a grid."""

    def __init__(self, theme: str = "dark") -> None:
        super().__init__()
        self._theme = theme if theme in {"dark", "light"} else "dark"
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._container = QWidget()
        self._grid = QGridLayout(self._container)
        self._grid.setSpacing(12)
        self._grid.setContentsMargins(12, 12, 12, 12)
        self.setWidget(self._container)
        self.set_theme(self._theme)

    def show_blocks(self, blocks: list[BlockDef]) -> None:
        # Clear existing
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        cols = 4
        for idx, bdef in enumerate(blocks):
            row, col = divmod(idx, cols)
            card = _DraggableBlockCard(bdef, self._theme)
            self._grid.addWidget(card, row, col)
        # Add stretch at bottom
        self._grid.setRowStretch(len(blocks) // cols + 1, 1)

    def set_theme(self, theme: str) -> None:
        self._theme = theme if theme in {"dark", "light"} else "dark"
        colors = get_colors(self._theme)
        self._container.setStyleSheet(f"background: {colors['bg_primary']};")
        self.setStyleSheet(f"QScrollArea {{ border: none; background: {colors['bg_primary']}; }}")
        for idx in range(self._grid.count()):
            item = self._grid.itemAt(idx)
            widget = item.widget()
            if isinstance(widget, _DraggableBlockCard):
                widget.set_theme(self._theme)


class _DraggableBlockCard(QWidget):
    """A card showing a block preview that can be dragged to the canvas."""

    def __init__(self, bdef: BlockDef, theme: str = "dark") -> None:
        super().__init__()
        self._bdef = bdef
        self._theme = theme if theme in {"dark", "light"} else "dark"
        self.setFixedSize(120, 90)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 6, 4, 4)
        layout.setSpacing(2)

        # Block icon preview
        self._icon_label = QLabel()
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._icon_label, 1)

        self._name = QLabel(bdef.type)
        self._name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name.setWordWrap(True)
        layout.addWidget(self._name)

        self.setToolTip(f"{bdef.type}\n{bdef.description}")
        self._drag_start_pos = None
        self.set_theme(self._theme)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        if self._drag_start_pos is None:
            return
        if (event.pos() - self._drag_start_pos).manhattanLength() < 5:
            return
            
        drag = QDrag(self)
        mime = QMimeData()
        payload = {
            "type": self._bdef.type,
            "category": self._bdef.category,
            "color": self._bdef.color,
            "inputs": self._bdef.inputs,
            "outputs": self._bdef.outputs,
            "params": dict(self._bdef.params),
        }
        encoded = json.dumps(payload).encode("utf-8")
        mime.setData("application/x-kronos-block", encoded)
        drag.setMimeData(mime)
        
        # Use a nice drag pixmap
        drag.setPixmap(self._block_preview_pixmap(self._bdef, self._theme))
        drag.setHotSpot(QPointF(40, 20).toPoint())  # Center of the 80x40 pixmap
        
        drag.exec(Qt.DropAction.CopyAction)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._drag_start_pos = None

    def set_theme(self, theme: str) -> None:
        self._theme = theme if theme in {"dark", "light"} else "dark"
        colors = get_colors(self._theme)
        if self._theme == "dark":
            card_bg = "#13192a"
            border = "#1e2128"
            text = "#c8ccd4"
        else:
            card_bg = "#ffffff"
            border = "#bfd4ee"
            text = "#334155"
        self.setStyleSheet(
            "QWidget {"
            f" background: {card_bg};"
            f" border: 1px solid {border};"
            " border-radius: 4px;"
            "}"
        )
        self._name.setStyleSheet(f"color: {text}; font-size: 9px; border: none;")
        self._icon_label.setPixmap(self._block_preview_pixmap(self._bdef, self._theme))

    @staticmethod
    def _block_preview_pixmap(bdef: BlockDef, theme: str = "dark") -> QPixmap:
        w, h = 80, 40
        pix = QPixmap(w, h)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        fill = QColor(bdef.color)
        fill.setAlpha(200 if theme == "dark" else 170)
        p.setPen(QPen(QColor(bdef.color), 1.2))
        p.setBrush(fill)
        p.drawRoundedRect(QRectF(4, 4, w - 8, h - 8), 4, 4)

        # Input ports
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#ffffff" if theme == "dark" else "#334155"))
        for i in range(bdef.inputs):
            y = h / 2 if bdef.inputs == 1 else 10 + i * (h - 20) / max(1, bdef.inputs - 1)
            _draw_port_triangle(p, 4, y, "input")

        # Output ports
        for i in range(bdef.outputs):
            y = h / 2 if bdef.outputs == 1 else 10 + i * (h - 20) / max(1, bdef.outputs - 1)
            _draw_port_triangle(p, w - 4, y, "output")

        # Block label
        p.setPen(QColor("#ffffff" if theme == "dark" else "#0f172a"))
        font = QFont("Noto Sans", 7)
        font.setBold(True)
        p.setFont(font)
        p.drawText(QRectF(4, 4, w - 8, h - 8), Qt.AlignmentFlag.AlignCenter,
                   bdef.symbol or bdef.type[:8])
        p.end()
        return pix


def _draw_port_triangle(p: QPainter, x: float, y: float, kind: str) -> None:
    """Draw a small directional triangle port."""
    s = 4.0
    path = QPainterPath()
    if kind == "input":
        path.moveTo(x - s, y - s / 2)
        path.lineTo(x, y)
        path.lineTo(x - s, y + s / 2)
    else:
        path.moveTo(x, y - s / 2)
        path.lineTo(x + s, y)
        path.lineTo(x, y + s / 2)
    path.closeSubpath()
    p.drawPath(path)


class AeonLibrary(QWidget):
    """Two-pane library browser matching MATLAB Aeon Library Browser."""

    def __init__(self, theme: str = "dark") -> None:
        super().__init__()
        self._theme = theme if theme in {"dark", "light"} else "dark"
        self._colors = get_colors(self._theme)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title bar
        self._title_bar = QWidget()
        self._title_bar.setObjectName("panel_header")
        tb_layout = QHBoxLayout(self._title_bar)
        tb_layout.setContentsMargins(6, 4, 6, 4)
        self._title_lbl = QLabel("Aeon Library Browser")
        tb_layout.addWidget(self._title_lbl)
        tb_layout.addStretch(1)
        layout.addWidget(self._title_bar)

        # Search
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search blocks...")
        self._search.textChanged.connect(self._filter_items)
        layout.addWidget(self._search)

        # Two-pane splitter
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setChildrenCollapsible(False)

        # Left: category tree
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(14)
        self._tree.setMinimumWidth(160)

        # Right: block preview grid
        self._preview = _BlockPreviewGrid(self._theme)

        # Also keep block tree for drag-and-drop
        self.blocks_tree = BlockTreeWidget()
        self.blocks_tree.hide()

        self._splitter.addWidget(self._tree)
        self._splitter.addWidget(self._preview)
        self._splitter.setSizes([180, 300])
        layout.addWidget(self._splitter, 1)

        self._build_tree()
        self._tree.currentItemChanged.connect(self._on_category_selected)
        # Pre-select first category
        if self._tree.topLevelItemCount() > 0:
            self._tree.setCurrentItem(self._tree.topLevelItem(0))
        self.set_theme(self._theme)

    def _build_tree(self) -> None:
        """Populate the tree and hidden drag tree from registry."""
        for cat_name, blocks in ALL_CATEGORIES:
            # Category tree (visual)
            cat_item = QTreeWidgetItem([cat_name])
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)
            cat_item.setData(0, Qt.ItemDataRole.UserRole, cat_name)
            self._tree.addTopLevelItem(cat_item)

            for bdef in blocks:
                child = QTreeWidgetItem([bdef.type])
                child.setData(0, Qt.ItemDataRole.UserRole, bdef.type)
                child.setIcon(0, _block_tree_icon(bdef, self._theme))
                cat_item.addChild(child)

            # Drag-enabled tree (hidden, used for DnD onto canvas)
            parent_drag = QTreeWidgetItem([cat_name])
            parent_drag.setFlags(parent_drag.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)
            self.blocks_tree.addTopLevelItem(parent_drag)
            for bdef in blocks:
                payload = {
                    "type": bdef.type,
                    "category": bdef.category,
                    "color": bdef.color,
                    "inputs": bdef.inputs,
                    "outputs": bdef.outputs,
                    "params": dict(bdef.params),
                }
                child = QTreeWidgetItem([bdef.type])
                child.setData(0, Qt.ItemDataRole.UserRole, payload)
                child.setFlags(child.flags() | Qt.ItemFlag.ItemIsDragEnabled)
                child.setIcon(0, _block_tree_icon(bdef, self._theme))
                parent_drag.addChild(child)
        self.blocks_tree.expandAll()
        self._tree.expandAll()

    def _on_category_selected(self, current: QTreeWidgetItem | None, _prev=None) -> None:
        if current is None:
            return
        cat_name = current.data(0, Qt.ItemDataRole.UserRole)
        if cat_name is None:
            return

        # If a block (child) is selected, show its category's blocks
        parent = current.parent()
        if parent is not None:
            cat_name = parent.data(0, Qt.ItemDataRole.UserRole)

        # Find matching category
        for cname, blocks in ALL_CATEGORIES:
            if cname == cat_name:
                self._preview.show_blocks(blocks)
                return

    def _filter_items(self, text: str) -> None:
        term = text.lower().strip()

        def _match(item: QTreeWidgetItem) -> bool:
            own_match = term in item.text(0).lower() if term else True
            child_match = False
            for idx in range(item.childCount()):
                child = item.child(idx)
                if _match(child):
                    child_match = True
            item.setHidden(not (own_match or child_match))
            return own_match or child_match

        for idx in range(self._tree.topLevelItemCount()):
            _match(self._tree.topLevelItem(idx))

    def set_theme(self, theme: str) -> None:
        self._theme = theme if theme in {"dark", "light"} else "dark"
        self._colors = get_colors(self._theme)
        c = self._colors
        self._title_bar.setStyleSheet(
            f"background: {c['bg_secondary']};"
            f"border-bottom: 1px solid {c['border']};"
            "padding: 4px 8px;"
        )
        self._title_lbl.setStyleSheet(
            f"color: {c['text_primary']}; font-weight: 700; font-size: 11px;"
        )
        self._search.setStyleSheet(
            "QLineEdit {"
            f" background: {c['bg_elevated']};"
            f" color: {c['text_primary']};"
            f" border: 1px solid {c['border']};"
            " border-radius: 4px;"
            " padding: 4px 8px;"
            " margin: 4px 6px;"
            "}"
            "QLineEdit:focus {"
            f" border: 1px solid {c['border_focus']};"
            "}"
        )
        self._tree.setStyleSheet(
            "QTreeWidget {"
            f" background: {c['bg_secondary']};"
            f" color: {c['text_primary']};"
            f" border: 1px solid {c['border']};"
            "}"
            "QTreeWidget::item:selected {"
            f" background: {c['bg_elevated']};"
            f" color: {c['text_primary']};"
            "}"
        )
        self._splitter.setStyleSheet(
            "QSplitter::handle {"
            f" background: {c['border']};"
            "}"
        )
        self._preview.set_theme(self._theme)
        self._refresh_tree_icons()

    def _refresh_tree_icons(self) -> None:
        for idx in range(self._tree.topLevelItemCount()):
            parent = self._tree.topLevelItem(idx)
            for child_idx in range(parent.childCount()):
                child = parent.child(child_idx)
                bdef = get_block_def(child.text(0))
                if bdef is not None:
                    child.setIcon(0, _block_tree_icon(bdef, self._theme))
        for idx in range(self.blocks_tree.topLevelItemCount()):
            parent = self.blocks_tree.topLevelItem(idx)
            for child_idx in range(parent.childCount()):
                child = parent.child(child_idx)
                payload = child.data(0, Qt.ItemDataRole.UserRole)
                block_type = payload.get("type") if isinstance(payload, dict) else child.text(0)
                bdef = get_block_def(str(block_type))
                if bdef is not None:
                    child.setIcon(0, _block_tree_icon(bdef, self._theme))


def _block_tree_icon(bdef: BlockDef, theme: str = "dark") -> QIcon:
    """16×16 icon for the library tree."""
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    color = QColor(bdef.color)
    p.setPen(QPen(color, 1.1))
    fill = QColor(color)
    fill.setAlpha(190 if theme == "dark" else 170)
    p.setBrush(fill)
    p.drawRoundedRect(QRectF(2, 3, 12, 10), 2.0, 2.0)

    # Input/output port dots
    p.setBrush(QColor("#ffffff" if theme == "dark" else "#334155"))
    p.setPen(Qt.PenStyle.NoPen)
    if bdef.inputs > 0:
        p.drawEllipse(QPointF(2.2, 8.0), 1.2, 1.2)
    if bdef.outputs > 0:
        p.drawEllipse(QPointF(13.8, 8.0), 1.2, 1.2)

    # Center symbol
    p.setPen(QPen(QColor("#e8eaf0" if theme == "dark" else "#0f172a"), 1.0))
    sym = bdef.symbol[:3] if bdef.symbol else bdef.type[:3]
    font = QFont("Noto Sans", 5)
    p.setFont(font)
    p.drawText(QRectF(2, 3, 12, 10), Qt.AlignmentFlag.AlignCenter, sym)
    p.end()
    return QIcon(pixmap)


# ═══════════════════════════════════════════════════════════════════════════
# Main Aeon Window
# ═══════════════════════════════════════════════════════════════════════════

class AeonWindow(QMainWindow):
    """Independent Aeon-style window with MATLAB-style ribbon."""

    simulation_complete = pyqtSignal(dict)
    closed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Aeon — Kronos 2026.1")
        self.setMinimumSize(1200, 720)
        parent_theme = getattr(parent, "_current_theme", "light")
        self._theme = parent_theme if parent_theme in {"dark", "light"} else "light"
        self._colors = get_colors(self._theme)

        self._simulator = DiagramSimulator()
        self._sim_thread: QThread | None = None

        self.aeon_canvas = AeonCanvas()
        self.aeon_canvas.set_theme(self._theme)
        self.aeon_canvas.load_demo_diagram()

        self._library = AeonLibrary(self._theme)

        self._build_ui()
        self._connect_signals()
        self.set_theme(self._theme)

    # ---------------------------------------------------------------
    # UI Construction
    # ---------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Ribbon ──
        layout.addWidget(self._build_ribbon())

        # ── Model name bar ──
        self._name_bar = QWidget()
        self._name_bar.setObjectName("aeon_model_bar")
        nb_layout = QHBoxLayout(self._name_bar)
        nb_layout.setContentsMargins(10, 2, 10, 2)
        self._model_name = QLabel("untitled")
        self._model_name.setObjectName("aeon_model_name")
        nb_layout.addWidget(self._model_name)
        nb_layout.addStretch(1)
        layout.addWidget(self._name_bar)

        # ── Main content: library + canvas ──
        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._main_splitter.setChildrenCollapsible(False)
        self._main_splitter.addWidget(self._library)
        self._main_splitter.addWidget(self.aeon_canvas)
        self._main_splitter.setSizes([280, 920])
        layout.addWidget(self._main_splitter, 1)

        # ── Status bar ──
        self._status_bar = QWidget()
        self._status_bar.setObjectName("aeon_status_bar")
        self._status_bar.setFixedHeight(24)
        sb_layout = QHBoxLayout(self._status_bar)
        sb_layout.setContentsMargins(10, 0, 10, 0)
        self._status = QLabel("Ready")
        self._status.setObjectName("aeon_status_text")
        sb_layout.addWidget(self._status)
        sb_layout.addStretch(1)
        self._zoom_label = QLabel("100%")
        self._zoom_label.setObjectName("aeon_status_text")
        sb_layout.addWidget(self._zoom_label)
        sb_layout.addWidget(self._sep())
        self._solver_label = QLabel("VariableStepAuto")
        self._solver_label.setObjectName("aeon_status_text")
        sb_layout.addWidget(self._solver_label)
        layout.addWidget(self._status_bar)

        self.setCentralWidget(root)

    def _build_ribbon(self) -> QWidget:
        ribbon = QWidget()
        ribbon.setObjectName("ribbon")
        ribbon.setMinimumHeight(130)
        ribbon.setMaximumHeight(140)
        rl = QVBoxLayout(ribbon)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)

        tabs = QTabWidget()
        tabs.setObjectName("ribbon_tabs")
        tabs.setDocumentMode(True)
        tabs.addTab(self._build_simulation_tab(), "SIMULATION")
        tabs.addTab(self._build_modeling_tab(), "MODELING")
        tabs.addTab(self._build_format_tab(), "FORMAT")
        tabs.addTab(self._build_apps_tab(), "APPS")
        rl.addWidget(tabs, 1)
        return ribbon

    def _build_simulation_tab(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("ribbon_panel")
        row = QHBoxLayout(panel)
        row.setContentsMargins(8, 4, 8, 4)
        row.setSpacing(6)

        # FILE group
        g_file = _RibbonGroup("FILE")
        g_file.add_widget(_ribbon_button("New", "New Model", "new"))
        self._open_btn = _ribbon_button("Open", "Open Model", "open")
        g_file.add_widget(self._open_btn)
        self._save_btn = _ribbon_button("Save", "Save Model", "save")
        g_file.add_widget(self._save_btn)
        g_file.finalize()
        row.addWidget(g_file)
        row.addWidget(self._vdiv())

        # LIBRARY group
        g_lib = _RibbonGroup("LIBRARY")
        g_lib.add_widget(_ribbon_button("Library\nBrowser", "Open Library", "library"))
        g_lib.add_widget(_ribbon_button("Log\nSignals", "Log Signals", "log"))
        g_lib.add_widget(_ribbon_button("Add\nViewer", "Add Signal Viewer", "viewer"))
        g_lib.finalize()
        row.addWidget(g_lib)
        row.addWidget(self._vdiv())

        # SIMULATE group
        g_sim = _RibbonGroup("SIMULATE")
        # Stop Time
        time_w = QWidget()
        time_l = QVBoxLayout(time_w)
        time_l.setContentsMargins(0, 0, 0, 0)
        time_l.setSpacing(2)
        st_lbl = QLabel("Stop Time")
        st_lbl.setObjectName("aeon_small_label")
        st_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._t_end_spin = QDoubleSpinBox()
        self._t_end_spin.setRange(0.0, 10000.0)
        self._t_end_spin.setValue(10.0)
        self._t_end_spin.setSingleStep(0.5)
        self._t_end_spin.setFixedWidth(70)
        time_l.addWidget(st_lbl)
        time_l.addWidget(self._t_end_spin)
        g_sim.add_widget(time_w)

        # Solver combo
        solver_w = QWidget()
        solver_l = QVBoxLayout(solver_w)
        solver_l.setContentsMargins(0, 0, 0, 0)
        solver_l.setSpacing(2)
        sv_lbl = QLabel("Solver")
        sv_lbl.setObjectName("aeon_small_label")
        sv_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._solver_combo = QComboBox()
        self._solver_combo.addItems(["Normal", "Accelerator", "Rapid Accelerator"])
        self._solver_combo.setFixedWidth(100)
        solver_l.addWidget(sv_lbl)
        solver_l.addWidget(self._solver_combo)
        g_sim.add_widget(solver_w)

        # dt
        dt_w = QWidget()
        dt_l = QVBoxLayout(dt_w)
        dt_l.setContentsMargins(0, 0, 0, 0)
        dt_l.setSpacing(2)
        dt_lbl = QLabel("dt")
        dt_lbl.setObjectName("aeon_small_label")
        dt_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._dt_spin = QDoubleSpinBox()
        self._dt_spin.setRange(0.001, 1.0)
        self._dt_spin.setDecimals(3)
        self._dt_spin.setValue(0.01)
        self._dt_spin.setSingleStep(0.001)
        self._dt_spin.setFixedWidth(70)
        dt_l.addWidget(dt_lbl)
        dt_l.addWidget(self._dt_spin)
        g_sim.add_widget(dt_w)

        # Simulation buttons
        self._run_btn = _ribbon_button("Run", "Run Simulation (F5)", "run", "success")
        self._stop_btn = _ribbon_button("Stop", "Stop Simulation", "stop", "error")
        g_sim.add_widget(self._run_btn)
        g_sim.add_widget(self._stop_btn)
        g_sim.finalize()
        row.addWidget(g_sim)
        row.addWidget(self._vdiv())

        # TOOLS group
        g_tools = _RibbonGroup("TOOLS")
        self._validate_btn = _ribbon_button("Validate", "Validate Model", "validate")
        self._arrange_btn = _ribbon_button("Arrange", "Auto Arrange", "arrange")
        self._fit_btn = _ribbon_button("Fit View", "Fit View", "fit")
        self._clear_btn = _ribbon_button("Clear", "Clear Canvas", "clear", "error")
        g_tools.add_widget(self._validate_btn)
        g_tools.add_widget(self._arrange_btn)
        g_tools.add_widget(self._fit_btn)
        g_tools.add_widget(self._clear_btn)
        g_tools.finalize()
        row.addWidget(g_tools)
        row.addWidget(self._vdiv())

        # REVIEW RESULTS group
        g_review = _RibbonGroup("REVIEW RESULTS")
        g_review.add_widget(_ribbon_button("Data\nInspector", "Data Inspector", "data_inspector"))
        g_review.finalize()
        row.addWidget(g_review)

        row.addStretch(1)
        return panel

    def _build_modeling_tab(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("ribbon_panel")
        row = QHBoxLayout(panel)
        row.setContentsMargins(8, 4, 8, 4)
        row.setSpacing(6)
        g = _RibbonGroup("MODEL")
        g.add_widget(_ribbon_button("Undo", "Undo", "undo"))
        g.add_widget(_ribbon_button("Redo", "Redo", "redo"))
        g.finalize()
        row.addWidget(g)

        g2 = _RibbonGroup("INSERT")
        self._connect_mode = QCheckBox("Connect Mode")
        self._connect_mode.setChecked(True)
        self._snap_mode = QCheckBox("Snap to Grid")
        self._snap_mode.setChecked(True)
        g2.add_widget(self._connect_mode)
        g2.add_widget(self._snap_mode)
        g2.finalize()
        row.addWidget(g2)
        row.addStretch(1)
        return panel

    def _build_format_tab(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("ribbon_panel")
        row = QHBoxLayout(panel)
        row.setContentsMargins(8, 4, 8, 4)
        lbl = QLabel("Format tools — coming soon")
        lbl.setObjectName("aeon_muted_text")
        row.addWidget(lbl)
        row.addStretch(1)
        return panel

    def _build_apps_tab(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("ribbon_panel")
        row = QHBoxLayout(panel)
        row.setContentsMargins(8, 4, 8, 4)
        lbl = QLabel("Apps — coming soon")
        lbl.setObjectName("aeon_muted_text")
        row.addWidget(lbl)
        row.addStretch(1)
        return panel

    @staticmethod
    def _vdiv() -> QFrame:
        d = QFrame()
        d.setFrameShape(QFrame.Shape.VLine)
        d.setObjectName("ribbon_divider")
        return d

    @staticmethod
    def _sep() -> QLabel:
        lbl = QLabel("  |  ")
        lbl.setObjectName("aeon_sep")
        return lbl

    def set_theme(self, theme: str) -> None:
        self._theme = theme if theme in {"dark", "light"} else "dark"
        self._colors = get_colors(self._theme)
        c = self._colors
        self._name_bar.setStyleSheet(
            f"background: {c['bg_secondary']};"
            f"border-bottom: 1px solid {c['border']};"
            "padding: 2px 10px;"
        )
        self._status_bar.setStyleSheet(
            f"background: {c['bg_secondary']};"
            f"border-top: 1px solid {c['border']};"
        )
        self._main_splitter.setStyleSheet(
            "QSplitter::handle {"
            f" background: {c['border']};"
            "}"
        )
        self.setStyleSheet(
            "QLabel#aeon_model_name {"
            f" color: {c['text_primary']};"
            " font-size: 12px;"
            " font-weight: 600;"
            "}"
            "QLabel#aeon_status_text {"
            f" color: {c['text_secondary']};"
            " font-size: 10px;"
            "}"
            "QLabel#aeon_sep {"
            f" color: {c['text_secondary']};"
            "}"
            "QLabel#aeon_muted_text {"
            f" color: {c['text_secondary']};"
            "}"
            "QLabel#aeon_small_label {"
            f" color: {c['text_secondary']};"
            " font-size: 9px;"
            "}"
            "QFrame#ribbon_divider {"
            f" background: {c['ribbon_tab_border']};"
            "}"
            "QToolButton#ribbon_action {"
            f" color: {c['text_primary']};"
            "}"
        )
        self._library.set_theme(self._theme)
        self.aeon_canvas.set_theme(self._theme)
        self._refresh_ribbon_icons()

    def _resolve_icon_tint(self, icon_role: str | None) -> str:
        if not icon_role:
            return self._colors["text_secondary"]
        return self._colors.get(icon_role, icon_role)

    def _refresh_ribbon_icons(self) -> None:
        for btn in self.findChildren(QToolButton):
            if btn.objectName() != "ribbon_action":
                continue
            icon_name = btn.property("icon_name")
            if not isinstance(icon_name, str) or not icon_name:
                continue
            icon_role = btn.property("icon_role")
            role_name = icon_role if isinstance(icon_role, str) else "text_secondary"
            btn.setIcon(_sim_icon(icon_name, self._resolve_icon_tint(role_name)))

    # ---------------------------------------------------------------
    # Signal connections
    # ---------------------------------------------------------------

    def _connect_signals(self) -> None:
        self._run_btn.clicked.connect(self._simulate_diagram)
        self._stop_btn.clicked.connect(self._stop_simulation)
        self._validate_btn.clicked.connect(self._validate_diagram)
        self._arrange_btn.clicked.connect(self._auto_arrange)
        self._clear_btn.clicked.connect(self.aeon_canvas.clear_canvas)
        self._save_btn.clicked.connect(self._save_diagram)
        self._open_btn.clicked.connect(self._load_diagram)
        self._fit_btn.clicked.connect(self._fit_view)
        self._connect_mode.toggled.connect(self.aeon_canvas.set_connect_mode)
        self._snap_mode.toggled.connect(self.aeon_canvas.set_snap_to_grid)
        self.aeon_canvas.diagram_changed.connect(
            lambda: self._status.setText("Modified")
        )
        self.aeon_canvas.block_double_clicked.connect(
            self._on_block_double_clicked
        )

    # ---------------------------------------------------------------
    # Simulation
    # ---------------------------------------------------------------

    def _simulate_diagram(self) -> None:
        if self._sim_thread is not None and self._sim_thread.isRunning():
            self._status.setText("Simulation already running")
            return
        issues = self.aeon_canvas.validate_diagram()
        if issues:
            preview = "\n".join(f"• {issue}" for issue in issues[:6])
            if len(issues) > 6:
                preview += "\n• ..."
            answer = QMessageBox.question(
                self,
                "Model validation",
                f"Model has validation warnings:\n\n{preview}\n\nContinue anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                self._status.setText("Validation failed")
                return
        diagram = self.aeon_canvas.get_diagram()
        t_end = float(self._t_end_spin.value())
        dt = float(self._dt_spin.value())
        self._status.setText("Running simulation…")
        self.aeon_canvas.set_wire_animation(True)
        self.aeon_canvas.set_runtime_status(0.0, 0, 0)

        worker = _SimulationWorker(self._simulator, diagram, t_end, dt)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_simulation_result)
        worker.error.connect(self._on_simulation_error)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.error.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: setattr(self, "_sim_thread", None))
        
        self._sim_worker = worker
        self._sim_thread = thread
        thread.start()

    def _stop_simulation(self) -> None:
        if self._sim_thread is not None and self._sim_thread.isRunning():
            self._sim_thread.requestInterruption()
            self._status.setText("Stop requested")
            self.aeon_canvas.set_wire_animation(False)

    # ---------------------------------------------------------------
    # File I/O
    # ---------------------------------------------------------------

    def _save_diagram(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Diagram", "", "Aeon Files (*.sim)"
        )
        if not path:
            return
        data = self.aeon_canvas.get_diagram()
        try:
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2)
        except OSError as exc:
            QMessageBox.warning(self, "Save failed", str(exc))
            return
        self._model_name.setText(path.rsplit("/", 1)[-1].replace(".sim", ""))
        self._status.setText("Saved")

    def _load_diagram(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Diagram", "", "Aeon Files (*.sim)"
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            self.aeon_canvas.load_diagram(data)
            self._model_name.setText(path.rsplit("/", 1)[-1].replace(".sim", ""))
            self._status.setText("Loaded")
        except (OSError, json.JSONDecodeError) as exc:
            QMessageBox.warning(self, "Load failed", str(exc))

    # ---------------------------------------------------------------
    # Actions
    # ---------------------------------------------------------------

    def _validate_diagram(self) -> None:
        issues = self.aeon_canvas.validate_diagram()
        if not issues:
            self._status.setText("Model valid ✓")
            QMessageBox.information(self, "Validation", "No issues found.")
            return
        self._status.setText(f"{len(issues)} issue(s)")
        QMessageBox.warning(self, "Validation issues", "\n".join(issues))

    def _auto_arrange(self) -> None:
        self.aeon_canvas.auto_arrange_left_to_right()
        self._status.setText("Auto-arranged")

    def _fit_view(self) -> None:
        items_rect = self.aeon_canvas.scene().itemsBoundingRect()
        if not items_rect.isNull():
            self.aeon_canvas.fitInView(
                items_rect.adjusted(-40, -40, 40, 40),
                Qt.AspectRatioMode.KeepAspectRatio,
            )
        else:
            self.aeon_canvas.fitInView(
                self.aeon_canvas.sceneRect(),
                Qt.AspectRatioMode.KeepAspectRatio,
            )

    def _on_simulation_result(self, result: dict) -> None:
        self.aeon_canvas.set_wire_animation(False)
        if result.get("success"):
            self._status.setText("Simulation complete ✓")
            sim_time = float(result.get("time", [0.0])[-1]) if result.get("time") else 0.0
            self.aeon_canvas.set_runtime_status(
                sim_time=sim_time,
                step_count=max(0, len(result.get("time", [])) - 1),
                error_count=0,
            )
            
            # Show popup scopes for standalone window
            outputs = result.get("outputs", {})
            if outputs:
                import matplotlib.pyplot as plt
                current_theme = self._theme
                is_dark = current_theme == "dark"
                if is_dark:
                    fig_face = "#08090e"
                    ax_face = "#08090e"
                    line_color = "#1a6fff"
                    tick_color = "#3a4050"
                    spine_color = "#1e2128"
                    grid_color = "#1a1f2a"
                    title_color = "#6a7280"
                else:
                    fig_face = "#ffffff"
                    ax_face = "#ffffff"
                    line_color = "#1a6fff"
                    tick_color = "#475569"
                    spine_color = "#cbd5e1"
                    grid_color = "#e2e8f0"
                    title_color = "#334155"
                for scope_id, signal in outputs.items():
                    fig = plt.figure(f"Scope: {scope_id}", facecolor=fig_face)
                    fig.clear()
                    ax = fig.add_subplot(111)
                    ax.plot(result["time"], signal, color=line_color, linewidth=1.5)
                    ax.set_facecolor(ax_face)
                    ax.tick_params(colors=tick_color)
                    for spine in ax.spines.values():
                        spine.set_color(spine_color)
                    ax.grid(True, color=grid_color, linewidth=0.5)
                    ax.set_title(f"Scope: {scope_id}", color=title_color, fontsize=10)
                    plt.show(block=False)
                    
            self.simulation_complete.emit(result)
        else:
            self._status.setText("Simulation failed")
            self.aeon_canvas.set_runtime_status(0.0, 0, 1)
            QMessageBox.warning(
                self, "Simulation Error", result.get("error", "Unknown error")
            )

    def _on_simulation_error(self, error: str) -> None:
        self._status.setText("Simulation error")
        self.aeon_canvas.set_wire_animation(False)
        self.aeon_canvas.set_runtime_status(0.0, 0, 1)
        QMessageBox.warning(self, "Simulation Error", error)

    def _on_block_double_clicked(self, block_id: str, params: dict) -> None:
        block = self.aeon_canvas._blocks.get(block_id)
        if block is None:
            return
        dlg = BlockParamDialog(block.block_type, params, self)
        if dlg.exec() == dlg.DialogCode.Accepted:
            block.params = dlg.get_params()
            block.update()
            self.aeon_canvas.diagram_changed.emit()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.closed.emit()
        super().closeEvent(event)


# ═══════════════════════════════════════════════════════════════════════════
# Simulation Worker
# ═══════════════════════════════════════════════════════════════════════════

class _SimulationWorker(QObject):
    """Worker object to run simulations off the UI thread."""

    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(
        self,
        simulator: DiagramSimulator,
        diagram: dict,
        t_end: float,
        dt: float,
    ) -> None:
        super().__init__()
        self._simulator = simulator
        self._diagram = diagram
        self._t_end = t_end
        self._dt = dt

    def run(self) -> None:
        try:
            result = self._simulator.simulate(self._diagram, self._t_end, self._dt)
            if result.get("success"):
                self.finished.emit(result)
            else:
                self.error.emit(result.get("error", "Simulation failed"))
        except (ValueError, RuntimeError) as exc:
            self.error.emit(str(exc))
