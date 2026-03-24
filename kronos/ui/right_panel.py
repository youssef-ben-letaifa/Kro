"""Right panel with workspace, analysis, and plots."""

from __future__ import annotations

import json
from typing import Callable

import control as ct
import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
try:
    import mpl_toolkits.mplot3d  # noqa: F401
except Exception:
    mpl_toolkits = None

from PyQt6.QtCore import QSortFilterProxyModel, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPixmap, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QLineEdit,
    QScrollArea,
    QStyledItemDelegate,
    QStyle,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTreeView,
    QVBoxLayout,
    QWidget,
)
from kronos.engine.kernel_message_router import KernelMessageRouter


class TypeBadgeDelegate(QStyledItemDelegate):
    """Draw variable types as colored pill badges."""

    def paint(self, painter: QPainter, option, index) -> None:  # type: ignore[override]
        if index.column() != 1:
            return super().paint(painter, option, index)
        text = str(index.data() or "")
        if not text:
            return super().paint(painter, option, index)

        lower = text.lower()
        if "ndarray" in lower:
            bg = QColor("#58A6FF")
        elif "dataframe" in lower:
            bg = QColor("#3FB950")
        elif lower in {"int", "float", "complex", "bool"}:
            bg = QColor("#8B949E")
        else:
            bg = QColor("#30363D")

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor("#21262D"))
        pill = option.rect.adjusted(6, 4, -6, -4)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(pill, 8, 8)
        painter.setPen(QColor("#0D1117"))
        painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()


class WorkspaceTree(QTreeView):
    """Tree view displaying workspace variables with filtering support."""

    variable_selected = pyqtSignal(str, dict)

    def __init__(self) -> None:
        super().__init__()
        self._vars: dict[str, dict] = {}
        self._model = QStandardItemModel(0, 4, self)
        self._model.setHorizontalHeaderLabels(["Name", "Type", "Size", "Value"])
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy.setFilterKeyColumn(-1)
        self.setModel(self._proxy)
        self.setRootIsDecorated(False)
        self.setUniformRowHeights(True)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTreeView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTreeView.SelectionMode.SingleSelection)
        self.setItemDelegateForColumn(1, TypeBadgeDelegate(self))
        self.doubleClicked.connect(self._on_activated)
        self.clicked.connect(self._on_activated)
        self.header().setStretchLastSection(True)
        self.setColumnWidth(0, 140)
        self.setColumnWidth(1, 120)
        self.setColumnWidth(2, 90)

    def set_filter_text(self, text: str) -> None:
        self._proxy.setFilterFixedString(text.strip())

    def update_workspace(self, variables: dict) -> None:
        self._vars = dict(variables)
        self._model.removeRows(0, self._model.rowCount())
        for name, meta in sorted(variables.items()):
            type_text = str(meta.get("type", ""))
            value_text = str(meta.get("value", ""))
            size_text = self._infer_size_text(type_text, value_text)
            row = [
                QStandardItem(name),
                QStandardItem(type_text),
                QStandardItem(size_text),
                QStandardItem(value_text),
            ]
            for item in row:
                item.setEditable(False)
            self._model.appendRow(row)

    @staticmethod
    def _infer_size_text(type_text: str, value_text: str) -> str:
        tokens = value_text.replace(",", " ").split()
        for token in tokens:
            if "x" in token and any(char.isdigit() for char in token):
                return token
        if "list" in type_text.lower() or "tuple" in type_text.lower():
            return "1-D"
        if "ndarray" in type_text.lower():
            return "array"
        return "—"

    def _on_activated(self, index) -> None:
        source = self._proxy.mapToSource(index)
        if not source.isValid():
            return
        name = str(self._model.item(source.row(), 0).text())
        meta = self._vars.get(name, {})
        self.variable_selected.emit(name, meta)


class VariableDetailDialog(QDialog):
    """Dialog showing variable details."""

    def __init__(self, name: str, meta: dict, details: dict | None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Variable: {name}")
        layout = QFormLayout(self)
        layout.addRow("Name:", QLabel(name))
        layout.addRow("Type:", QLabel(meta.get("type", "")))
        layout.addRow("Value:", QLabel(meta.get("value", "")))
        detail_text = self._format_details(details or {})
        detail_label = QLabel(detail_text)
        detail_label.setWordWrap(True)
        layout.addRow("Details:", detail_label)

    @staticmethod
    def _format_details(details: dict) -> str:
        if not details:
            return "—"
        if details.get("kind") == "ndarray":
            shape = details.get("shape", "")
            preview = details.get("preview", [])
            return f"Shape: {shape}\nPreview: {preview}"
        if details.get("kind") == "tf":
            num = details.get("numerator", [])
            den = details.get("denominator", [])
            return f"Numerator: {num}\nDenominator: {den}"
        if details.get("kind") == "ss":
            return "State-space system"
        return details.get("repr", "—")


class SystemAnalysisPanel(QWidget):
    """System analysis panel with control metrics."""

    def __init__(self) -> None:
        super().__init__()
        self._kernel_client_getter: Callable[[], object] | None = None
        self._workspace_provider: Callable[[], dict] | None = None
        self._sys_fetch_buffer = ""
        self._pending_sys_fetch = None

        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        self._title = QLabel("System Analysis")
        self._analyze_btn = QPushButton("Analyze")
        header.addWidget(self._title)
        header.addStretch(1)
        header.addWidget(self._analyze_btn)
        layout.addLayout(header)

        self._system_label = QLabel("No control system found in workspace")
        layout.addWidget(self._system_label)

        self._stability_title = QLabel("STABILITY")
        self._stability_title.setStyleSheet("color: #6a7280; font-weight: bold;")
        layout.addWidget(self._stability_title)

        self._poles_table = QTableWidget(0, 4)
        self._poles_table.setHorizontalHeaderLabels(["Real", "Imag", "Magnitude", "Stable?"])
        layout.addWidget(self._poles_table)

        self._verdict = QLabel("")
        self._verdict.setStyleSheet("font-weight: bold;")
        layout.addWidget(self._verdict)

        self._margins_title = QLabel("MARGINS")
        self._margins_title.setStyleSheet("color: #6a7280; font-weight: bold;")
        layout.addWidget(self._margins_title)
        self._gm_label = QLabel("Gain Margin: —")
        self._gm_bar = QProgressBar()
        self._gm_bar.setRange(0, 100)
        self._pm_label = QLabel("Phase Margin: —")
        self._pm_bar = QProgressBar()
        self._pm_bar.setRange(0, 100)
        self._crossover_label = QLabel("Gain crossover: — | Phase crossover: —")
        self._rule_label = QLabel("")
        layout.addWidget(self._gm_label)
        layout.addWidget(self._gm_bar)
        layout.addWidget(self._pm_label)
        layout.addWidget(self._pm_bar)
        layout.addWidget(self._crossover_label)
        layout.addWidget(self._rule_label)

        self._performance_title = QLabel("PERFORMANCE")
        self._performance_title.setStyleSheet("color: #6a7280; font-weight: bold;")
        layout.addWidget(self._performance_title)
        self._performance = QLabel("")
        layout.addWidget(self._performance)

        self._analyze_btn.clicked.connect(self._analyze)

    def set_kernel_client_getter(self, getter: Callable[[], object]) -> None:
        """Attach kernel client accessor."""
        self._kernel_client_getter = getter
        kc = self._kernel_client_getter()
        if kc and hasattr(kc.iopub_channel, "message_received"):
            kc.iopub_channel.message_received.connect(self._on_iopub_msg)

    def set_workspace_provider(self, provider: Callable[[], dict]) -> None:
        """Attach workspace variables provider."""
        self._workspace_provider = provider

    def _analyze(self) -> None:
        kernel_client = self._kernel_client_getter() if self._kernel_client_getter else None
        if kernel_client is None:
            return
            
        self._analyze_btn.setEnabled(False)
        self._analyze_btn.setText("Working...")
        
        code = (
            "import json, control as ct\n"
            "data = {}\n"
            "for name, obj in globals().items():\n"
            "    try:\n"
            "        if isinstance(obj, ct.TransferFunction):\n"
            "            num, den = ct.tfdata(obj)\n"
            "            data[name] = {'type': 'tf', 'num': num[0][0].tolist(), 'den': den[0][0].tolist()}\n"
            "        elif isinstance(obj, ct.StateSpace):\n"
            "            data[name] = {'type': 'ss', 'A': obj.A.tolist(), 'B': obj.B.tolist(), 'C': obj.C.tolist(), 'D': obj.D.tolist()}\n"
            "    except Exception:\n"
            "        pass\n"
            "print(json.dumps(data))\n"
        )
        self._sys_fetch_buffer = ""
        self._pending_sys_fetch = kernel_client.execute(code, silent=False, store_history=False)

    def _on_iopub_msg(self, msg: dict) -> None:
        if not getattr(self, "_pending_sys_fetch", None):
            return
        if msg.get("parent_header", {}).get("msg_id") != self._pending_sys_fetch:
            return
            
        msg_type = msg.get("header", {}).get("msg_type")
        if msg_type == "stream":
            self._sys_fetch_buffer += msg["content"].get("text", "")
        elif msg_type == "status" and msg["content"].get("execution_state") == "idle":
            self._pending_sys_fetch = None
            self._analyze_btn.setEnabled(True)
            self._analyze_btn.setText("Analyze")
            
            try:
                data = json.loads(self._sys_fetch_buffer.strip())
                systems = []
                for name, entry in data.items():
                    if entry["type"] == "tf":
                        sys = ct.tf(entry["num"], entry["den"])
                    else:
                        sys = ct.ss(entry["A"], entry["B"], entry["C"], entry["D"])
                    systems.append((name, sys))
                self._process_analysis(systems)
            except Exception:
                self._process_analysis([])

    def _process_analysis(self, systems: list[tuple[str, object]]) -> None:
        if not systems:
            self._system_label.setText("No control system found in workspace")
            self._poles_table.setRowCount(0)
            self._verdict.setText("")
            self._gm_label.setText("Gain Margin: —")
            self._pm_label.setText("Phase Margin: —")
            self._crossover_label.setText("Gain crossover: — | Phase crossover: —")
            self._gm_bar.setValue(0)
            self._pm_bar.setValue(0)
            self._rule_label.setText("")
            self._performance.setText("")
            return

        name, sys = systems[0]
        self._system_label.setText(f"System: {name}")
        poles = ct.pole(sys)
        self._poles_table.setRowCount(len(poles))
        stable = True
        marginal = False
        tol = 1e-6
        for idx, pole in enumerate(poles):
            real = pole.real
            imag = pole.imag
            mag = abs(pole)
            if real > tol:
                stable = False
            if abs(real) <= tol:
                marginal = True
            is_stable = real < -tol
            self._poles_table.setItem(idx, 0, QTableWidgetItem(f"{real:.3f}"))
            self._poles_table.setItem(idx, 1, QTableWidgetItem(f"{imag:.3f}"))
            self._poles_table.setItem(idx, 2, QTableWidgetItem(f"{mag:.3f}"))
            if is_stable:
                status_item = QTableWidgetItem("Yes")
                status_item.setForeground(QColor("#98c379"))
            elif abs(real) <= tol:
                status_item = QTableWidgetItem("~")
                status_item.setForeground(QColor("#e5c07b"))
            else:
                status_item = QTableWidgetItem("No")
                status_item.setForeground(QColor("#e06c75"))
            self._poles_table.setItem(idx, 3, status_item)

        gm, pm, wg, wp = ct.margin(sys)
        gm_db = 20 * np.log10(gm) if gm and gm > 0 else float("inf")
        pm_val = float(pm) if pm is not None else 0.0
        pm_status = "Good" if pm_val > 45 else "Acceptable" if pm_val > 20 else "Poor"
        gm_text = "∞" if not np.isfinite(gm_db) else f"{gm_db:.2f} dB"
        self._gm_label.setText(f"Gain Margin: {gm_text}")
        self._pm_label.setText(f"Phase Margin: {pm_val:.1f}°")
        self._crossover_label.setText(
            f"Gain crossover: {wg:.3g} rad/s | Phase crossover: {wp:.3g} rad/s"
            if wg and wp
            else "Gain crossover: — | Phase crossover: —"
        )
        self._gm_bar.setValue(100 if not np.isfinite(gm_db) else max(0, min(100, int(gm_db * 3))))
        self._pm_bar.setValue(max(0, min(100, int(pm_val))))
        rule_color = "#98c379" if pm_status == "Good" else "#e5c07b" if pm_status == "Acceptable" else "#e06c75"
        self._rule_label.setText(f"PM status: {pm_status}")
        self._rule_label.setStyleSheet(f"color: {rule_color}; font-weight: bold;")

        t, y = ct.step_response(sys)
        reference = 1.0
        metrics = _compute_performance(t, y, reference)
        try:
            bandwidth = ct.bandwidth(sys)
        except Exception:
            bandwidth = None
        base_text = (
            f"Rise: {metrics['rise_time']:.2f}s | "
            f"Settling: {metrics['settling_time']:.2f}s | "
            f"Overshoot: {metrics['overshoot']:.2f}% | "
            f"SS Error: {metrics['ss_error']:.4f}"
        )
        if bandwidth is not None:
            base_text += f" | Bandwidth: {bandwidth:.3g}"
        self._performance.setText(base_text)

        if stable and not marginal:
            self._verdict.setText("✓ STABLE")
            self._verdict.setStyleSheet("color: #98c379; font-weight: bold;")
        elif not stable:
            self._verdict.setText("✗ UNSTABLE")
            self._verdict.setStyleSheet("color: #e06c75; font-weight: bold;")
        else:
            self._verdict.setText("~ MARGINAL")
            self._verdict.setStyleSheet("color: #e5c07b; font-weight: bold;")



class PlotThumbnail(QLabel):
    """Clickable thumbnail for plots."""

    clicked = pyqtSignal(Figure)

    def __init__(self, fig: Figure, pixmap: QPixmap) -> None:
        super().__init__()
        self._fig = fig
        self.setPixmap(pixmap)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event) -> None:
        self.clicked.emit(self._fig)
        super().mousePressEvent(event)


class PlotGallery(QWidget):
    """Grid of plot thumbnails."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._grid_container = QWidget()
        self._grid = QGridLayout(self._grid_container)
        self._grid.setSpacing(8)
        self._scroll.setWidget(self._grid_container)
        layout.addWidget(self._scroll)
        self._row = 0
        self._col = 0

    def add_figure(self, fig: Figure, title: str) -> None:
        canvas = FigureCanvasAgg(fig)
        canvas.draw()
        width, height = fig.get_size_inches() * fig.get_dpi()
        image = QImage(
            canvas.buffer_rgba(),
            int(width),
            int(height),
            QImage.Format.Format_RGBA8888,
        )
        pixmap = QPixmap.fromImage(image).scaled(
            120, 90, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        thumb = PlotThumbnail(fig, pixmap)
        thumb.setToolTip(title)
        thumb.clicked.connect(self._open_fullscreen)
        self._grid.addWidget(thumb, self._row, self._col)
        self._col += 1
        if self._col >= 2:
            self._col = 0
            self._row += 1

    def clear_all(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._row = 0
        self._col = 0

    def _open_fullscreen(self, fig: Figure) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Plot")
        layout = QVBoxLayout(dialog)
        canvas = FigureCanvasQTAgg(fig)
        _enable_3d_navigation(fig)
        layout.addWidget(canvas)
        dialog.showMaximized()
        dialog.exec()


class RightPanel(QWidget):
    """Right panel with workspace, analysis, and plots."""

    clear_workspace_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(False)
        self._kernel_client_getter: Callable[[], object] | None = None
        self._message_router_getter: Callable[[], KernelMessageRouter | None] | None = None

        self.workspace_tree = WorkspaceTree()
        self.workspace_tree.variable_selected.connect(self._show_variable_dialog)
        workspace_tab = QWidget()
        ws_layout = QVBoxLayout(workspace_tab)
        self.workspace_search = QLineEdit()
        self.workspace_search.setPlaceholderText("Filter workspace variables...")
        self.workspace_search.textChanged.connect(self.workspace_tree.set_filter_text)
        ws_layout.addWidget(self.workspace_search)
        ws_layout.addWidget(self.workspace_tree, 1)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear_workspace_requested)
        ws_layout.addWidget(clear_btn)

        self.analysis_tab = SystemAnalysisPanel()
        analysis_tab = QWidget()
        analysis_layout = QVBoxLayout(analysis_tab)
        analysis_layout.addWidget(self.analysis_tab)

        self.plots_tab = PlotGallery()
        plots_tab = QWidget()
        plots_layout = QVBoxLayout(plots_tab)
        plots_layout.addWidget(self.plots_tab, 1)
        clear_plots = QPushButton("Clear All")
        clear_plots.clicked.connect(self.plots_tab.clear_all)
        plots_layout.addWidget(clear_plots)

        self.tabs.addTab(workspace_tab, "Workspace")
        self.tabs.addTab(analysis_tab, "Analysis")
        self.tabs.addTab(plots_tab, "Plots")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tabs)

    def update_workspace(self, variables: dict) -> None:
        self.workspace_tree.update_workspace(variables)

    def update_analysis_sources(
        self,
        kernel_client_getter,
        workspace_provider,
        message_router_getter: Callable[[], KernelMessageRouter | None] | None = None,
    ) -> None:
        self._kernel_client_getter = kernel_client_getter
        self._message_router_getter = message_router_getter
        self.analysis_tab.set_kernel_client_getter(kernel_client_getter)
        self.analysis_tab.set_workspace_provider(workspace_provider)

    def _show_variable_dialog(self, name: str, meta: dict) -> None:
        details = self._fetch_variable_details(name)
        dialog = VariableDetailDialog(name, meta, details, self)
        dialog.exec()

    def _fetch_variable_details(self, name: str) -> dict:
        kernel = self._kernel_client_getter() if self._kernel_client_getter else None
        if kernel is None:
            return {}
        router = self._message_router_getter() if self._message_router_getter else None
        if router is None:
            return {}
        code = (
            "import json, numpy as np\n"
            "try:\n"
            "    import control as ct\n"
            "except ImportError:\n"
            "    ct = None\n"
            f"obj = globals().get({name!r})\n"
            "payload = {}\n"
            "if isinstance(obj, np.ndarray):\n"
            "    payload = {'kind':'ndarray','shape':list(obj.shape),'preview':obj.flatten()[:5].tolist()}\n"
            "elif ct is not None and isinstance(obj, ct.TransferFunction):\n"
            "    num, den = ct.tfdata(obj)\n"
            "    payload = {'kind':'tf','numerator':num[0][0].tolist(),'denominator':den[0][0].tolist()}\n"
            "elif ct is not None and isinstance(obj, ct.StateSpace):\n"
            "    payload = {'kind':'ss'}\n"
            "else:\n"
            "    try:\n"
            "        payload = {'kind':'repr','repr':repr(obj)}\n"
            "    except Exception:\n"
            "        payload = {'kind':'repr','repr':str(obj)}\n"
            "print(json.dumps(payload))\n"
        )
        payload = router.request_json(kernel, code, timeout_ms=2000)
        if isinstance(payload, dict):
            return payload
        return {}


def _compute_performance(t: np.ndarray, y: np.ndarray, reference: float) -> dict:
    """Compute basic performance metrics."""
    rise_time = next((t[i] for i, val in enumerate(y) if val >= 0.9 * reference), t[-1])
    settle_idx = np.where(np.abs(y - reference) > 0.02 * reference)[0]
    settling_time = t[settle_idx[-1]] if len(settle_idx) else t[-1]
    overshoot = (np.max(y) - reference) / reference * 100.0
    ss_error = abs(y[-1] - reference)
    return {
        "rise_time": float(rise_time),
        "settling_time": float(settling_time),
        "overshoot": float(overshoot),
        "ss_error": float(ss_error),
    }


def _enable_3d_navigation(fig: Figure) -> None:
    """Rebind 3D mouse interactions after moving figures across canvases."""
    for ax in fig.axes:
        if not hasattr(ax, "get_zlim"):
            continue
        try:
            ax.mouse_init()
        except Exception:
            pass
