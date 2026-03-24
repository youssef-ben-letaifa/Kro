"""Left dock panel with MATLAB-like navigation."""

from __future__ import annotations

import json
import os
from pathlib import Path

from PyQt6.QtCore import QByteArray, QMimeData, QPointF, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QDrag, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTabWidget,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from kronos.ui.theme.design_tokens import get_colors
from kronos.ui.theme.fluent_icons import icon_for


class ExplorerTree(QTreeWidget):
    """Project file explorer tree."""

    file_open_requested = pyqtSignal(str)

    def __init__(self, root_path: Path) -> None:
        super().__init__()
        self._root_path = root_path
        self._icon_cache: dict[str, QIcon] = {}
        self.setHeaderHidden(True)
        self.setIndentation(14)
        self.setUniformRowHeights(True)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._populate()

    def _populate(self) -> None:
        self.clear()
        root_item = QTreeWidgetItem([self._root_path.name])
        root_item.setData(0, Qt.ItemDataRole.UserRole, str(self._root_path))
        root_item.setIcon(0, self._folder_icon())
        self.addTopLevelItem(root_item)

        path_items: dict[Path, QTreeWidgetItem] = {self._root_path: root_item}
        for dirpath, dirnames, filenames in os.walk(self._root_path):
            dirnames[:] = [
                dirname for dirname in dirnames if not dirname.startswith(".") and dirname != "__pycache__"
            ]
            current_path = Path(dirpath)
            parent_item = path_items.get(current_path)
            if parent_item is None:
                continue

            for dirname in sorted(dirnames):
                child_path = current_path / dirname
                child_item = QTreeWidgetItem([dirname])
                child_item.setData(0, Qt.ItemDataRole.UserRole, str(child_path))
                child_item.setIcon(0, self._folder_icon())
                parent_item.addChild(child_item)
                path_items[child_path] = child_item

            for filename in sorted(filenames):
                file_path = current_path / filename
                file_item = QTreeWidgetItem([filename])
                file_item.setData(0, Qt.ItemDataRole.UserRole, str(file_path))
                file_item.setIcon(0, self._file_icon(filename))
                parent_item.addChild(file_item)

        root_item.setExpanded(True)

    def filter_items(self, text: str) -> None:
        """Filter tree items in real time."""
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

        for idx in range(self.topLevelItemCount()):
            _match(self.topLevelItem(idx))

    def _file_icon(self, filename: str) -> QIcon:
        ext = Path(filename).suffix.lower()
        if ext not in self._icon_cache:
            if ext == ".py":
                self._icon_cache[ext] = self._draw_file_icon("#1a6fff", "Py")
            elif ext == ".sim":
                self._icon_cache[ext] = self._draw_file_icon("#98c379", "Sm")
            elif ext == ".qc":
                self._icon_cache[ext] = self._draw_file_icon("#c678dd", "Qc")
            else:
                self._icon_cache[ext] = self._draw_file_icon("#6a7280", "--")
        return self._icon_cache[ext]

    @staticmethod
    def _draw_file_icon(color: str, text: str) -> QIcon:
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(QColor(color), 1.2))
        painter.setBrush(QColor("#13192a"))
        painter.drawRoundedRect(QRectF(1.5, 1.5, 13, 13), 2.2, 2.2)
        painter.setPen(QColor(color))
        painter.drawLine(10, 2, 14, 5)
        painter.drawLine(10, 2, 10, 5)
        painter.setPen(QColor("#c8ccd4"))
        painter.setFont(painter.font())
        painter.drawText(QRectF(2.0, 6.0, 12.0, 7.0), Qt.AlignmentFlag.AlignCenter, text)
        painter.end()
        return QIcon(pixmap)

    @staticmethod
    def _folder_icon() -> QIcon:
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(QColor("#8a784c"), 1.2))
        painter.setBrush(QColor("#3b3522"))
        path = QPainterPath()
        path.moveTo(1.5, 6.0)
        path.lineTo(5.8, 6.0)
        path.lineTo(7.4, 4.0)
        path.lineTo(14.5, 4.0)
        path.lineTo(14.5, 13.5)
        path.lineTo(1.5, 13.5)
        path.closeSubpath()
        painter.drawPath(path)
        painter.fillPath(path, QColor("#4a4128"))
        painter.end()
        return QIcon(pixmap)

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        del column
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(path, str) and path.endswith(".py"):
            self.file_open_requested.emit(path)


class WorkspacePreview(QTreeWidget):
    """Simple workspace list for left dock."""

    def __init__(self) -> None:
        super().__init__()
        self.setColumnCount(3)
        self.setHeaderLabels(["Name", "Type", "Value"])
        self.setAlternatingRowColors(True)
        self.setUniformRowHeights(True)

    def update_workspace(self, variables: dict) -> None:
        """Populate workspace table."""
        self.clear()
        for name, meta in sorted(variables.items()):
            row = QTreeWidgetItem([name, meta.get("type", ""), meta.get("value", "")])
            self.addTopLevelItem(row)


class BlockTreeWidget(QTreeWidget):
    """Block palette with drag support."""

    block_drag_started = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setHeaderHidden(True)
        self.setDragEnabled(True)
        self.setIndentation(14)
        self.setUniformRowHeights(True)

    def startDrag(self, supported_actions: Qt.DropAction) -> None:
        del supported_actions
        item = self.currentItem()
        if item is None or item.parent() is None:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(data, dict):
            return
        mime = QMimeData()
        payload = json.dumps(data).encode("utf-8")
        mime.setData("application/x-kronos-block", QByteArray(payload))
        drag = QDrag(self)
        drag.setMimeData(mime)
        self.block_drag_started.emit(str(data.get("type", "")))
        drag.exec(Qt.DropAction.CopyAction)


class LeftPanel(QWidget):
    """MATLAB-like left dock with files/workspace and contextual tools."""

    file_open_requested = pyqtSignal(str)
    block_drag_started = pyqtSignal(str)
    snippet_insert_requested = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(False)
        if self.tabs.tabBar() is not None:
            self.tabs.tabBar().hide()
        self._nav_buttons: list[tuple[QToolButton, str]] = []
        self._is_dark_theme = True

        self.explorer = ExplorerTree(Path.cwd())
        self.blocks_tree = BlockTreeWidget()
        self.snippets_tree = QTreeWidget()
        self.snippets_tree.setHeaderHidden(True)
        self.snippets_tree.setIndentation(14)
        self.snippets_tree.setUniformRowHeights(True)

        self._build_blocks()
        self._build_snippets()
        self.tabs.addTab(self._build_files_workspace_tab(), "Files")
        self.tabs.addTab(self._build_blocks_tab(), "Blocks")
        self.tabs.addTab(self._build_snippets_tab(), "Snippets")

        self._nav_bar = self._build_nav_bar()
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._nav_bar)
        root_layout.addWidget(self.tabs, 1)

        self.explorer.file_open_requested.connect(self.file_open_requested)
        self.blocks_tree.block_drag_started.connect(self.block_drag_started)
        self.snippets_tree.itemDoubleClicked.connect(self._on_snippet_double_clicked)
        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _build_nav_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("left_toolbar")
        layout = QVBoxLayout(bar)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        self._add_nav_button(layout, "files", 0, "Files")
        self._add_nav_button(layout, "blocks", 1, "Blocks")
        self._add_nav_button(layout, "snippets", 2, "Snippets")

        layout.addStretch(1)
        self._sync_nav_icons()
        return bar

    def _add_nav_button(self, layout: QVBoxLayout, icon_name: str, index: int, tooltip: str) -> None:
        btn = QToolButton()
        btn.setObjectName("left_toolbar_button")
        btn.setToolTip(tooltip)
        btn.setCheckable(True)
        btn.setAutoExclusive(True)
        btn.setFixedSize(32, 32)
        btn.clicked.connect(lambda _checked=False, idx=index: self.tabs.setCurrentIndex(idx))
        btn.toggled.connect(self._sync_nav_icons)
        layout.addWidget(btn)
        self._nav_buttons.append((btn, icon_name))
        if index == 0:
            btn.setChecked(True)

    def _sync_nav_icons(self) -> None:
        colors = get_colors("dark" if self._is_dark_theme else "light")
        for btn, name in self._nav_buttons:
            color = colors["accent"] if btn.isChecked() else colors["text_secondary"]
            btn.setIcon(icon_for(name, size=20, color=color))
            btn.setIconSize(QSize(20, 20))

    def _on_tab_changed(self, index: int) -> None:
        if 0 <= index < len(self._nav_buttons):
            self._nav_buttons[index][0].setChecked(True)

    def set_theme(self, is_dark: bool) -> None:
        """Refresh icon tints on theme change."""
        self._is_dark_theme = is_dark
        self._sync_nav_icons()

    def _build_files_workspace_tab(self) -> QWidget:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(4, 4, 4, 4)
        page_layout.setSpacing(4)

        files = QWidget()
        files_layout = QVBoxLayout(files)
        files_layout.setContentsMargins(0, 0, 0, 0)
        files_layout.setSpacing(4)
        files_layout.addWidget(self._header("FILES"))

        path_bar = QLineEdit(str(self.explorer._root_path))
        path_bar.setReadOnly(True)
        path_bar.setObjectName("path_bar")
        files_layout.addWidget(path_bar)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search files...")
        self.search_bar.setClearButtonEnabled(True)
        self.search_bar.textChanged.connect(self.explorer.filter_items)
        files_layout.addWidget(self.search_bar)
        files_layout.addWidget(self.explorer, 1)
        page_layout.addWidget(files, 1)
        return page

    def _build_blocks_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        layout.addWidget(self._header("SIMULINK BLOCKS"))
        layout.addWidget(self.blocks_tree, 1)
        return page

    def _build_snippets_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        layout.addWidget(self._header("CODE SNIPPETS"))
        layout.addWidget(self.snippets_tree, 1)
        return page

    @staticmethod
    def _header(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("panel_header")
        return label

    def _build_blocks(self) -> None:
        from kronos.ui.center.simulink.block_registry import ALL_CATEGORIES

        for category, blocks in ALL_CATEGORIES:
            parent = QTreeWidgetItem([category])
            parent.setFlags(parent.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)
            self.blocks_tree.addTopLevelItem(parent)
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
                child.setIcon(0, self._block_icon(bdef.type, bdef.color))
                parent.addChild(child)
        self.blocks_tree.expandAll()

    @staticmethod
    def _block_icon(block_type: str, color: str) -> QIcon:
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(QColor(color), 1.1))
        fill = QColor(color)
        fill.setAlpha(190)
        painter.setBrush(fill)
        painter.drawRoundedRect(QRectF(2, 3, 12, 10), 2.0, 2.0)
        painter.setBrush(QColor("#ffffff"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(2.2, 8.0), 1.2, 1.2)
        painter.drawEllipse(QPointF(13.8, 8.0), 1.2, 1.2)
        painter.setPen(QPen(QColor("#e8eaf0"), 1.0))
        symbol = block_type.lower()
        if symbol == "step":
            painter.drawLine(5, 11, 5, 7)
            painter.drawLine(5, 7, 11, 7)
        elif symbol in {"transferfunction", "statespace"}:
            painter.drawLine(5, 11, 11, 5)
            painter.drawLine(5, 6, 11, 6)
        elif symbol == "pid":
            painter.drawLine(5, 8, 11, 8)
            painter.drawLine(8, 5, 8, 11)
        elif symbol in {"scope", "display"}:
            painter.drawLine(5, 11, 7, 8)
            painter.drawLine(7, 8, 9, 9)
            painter.drawLine(9, 9, 11, 6)
        else:
            painter.drawLine(5, 8, 11, 8)
        painter.end()
        return QIcon(pixmap)

    def _build_snippets(self) -> None:
        categories = {
            "Control Systems": {
                "Transfer Function": "G = ct.tf([1],[1,2,1])",
                "Closed Loop": "T = ct.feedback(C*G)",
                "Step Response": "t,y = ct.step_response(T)\nplt.plot(t,y)\nplt.show()",
                "Bode Plot": "ct.bode_plot(G, dB=True)\nplt.show()",
                "Root Locus": "ct.root_locus(G)\nplt.show()",
                "PID Controller": "C = ct.tf([Kd,Kp,Ki],[1,0])",
                "LQR Design": (
                    "A = np.array([[0,1],[-1,-2]])\n"
                    "B = np.array([[0],[1]])\n"
                    "Q = np.eye(2)\nR = np.array([[1]])\n"
                    "K, S, E = ct.lqr(A, B, Q, R)\n"
                ),
                "Kalman Filter": (
                    "A = np.array([[0,1],[-1,-2]])\n"
                    "B = np.array([[0],[1]])\n"
                    "C = np.array([[1,0]])\n"
                    "Qn = np.eye(2)\nRn = np.array([[1]])\n"
                    "L, P, E = ct.lqe(A, np.eye(2), C, Qn, Rn)\n"
                ),
            },
            "Signal Processing": {
                "FFT": "freq = np.fft.fftfreq(len(x), d=dt)\nX = np.fft.fft(x)\n",
                "Butterworth Filter": "b, a = signal.butter(4, 0.2)\ny = signal.filtfilt(b, a, x)\n",
                "Bode from scipy": "w, mag, phase = signal.bode(signal.TransferFunction(num, den))\n",
            },
            "Numpy / Math": {
                "Eigenvalues": "np.linalg.eigvals(A)\n",
                "Matrix Inverse": "np.linalg.inv(A)\n",
                "Linspace": "t = np.linspace(0, 10, 1000)\n",
            },
        }

        for category, snippets in categories.items():
            parent = QTreeWidgetItem([category])
            parent.setFlags(parent.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)
            self.snippets_tree.addTopLevelItem(parent)
            for name, code in snippets.items():
                child = QTreeWidgetItem([name])
                child.setData(0, Qt.ItemDataRole.UserRole, code)
                parent.addChild(child)
        self.snippets_tree.expandAll()

    def _on_snippet_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        del column
        if item.childCount() > 0:
            return
        code = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(code, str) and code:
            self.snippet_insert_requested.emit(code)

    def update_workspace(self, variables: dict) -> None:
        """Update workspace preview content."""
        del variables

    def show_workspace_section(self) -> None:
        """Show workspace emphasis within files tab."""
        self.tabs.setCurrentIndex(0)

    def show_files_section(self) -> None:
        """Show files emphasis within files tab."""
        self.tabs.setCurrentIndex(0)
