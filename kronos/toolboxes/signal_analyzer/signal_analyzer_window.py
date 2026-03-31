"""Top-level Signal Analyzer toolbox window."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QColorDialog,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from scipy import signal as sp_signal

from .cursor_manager import CursorMode
from .display_manager import DisplayManager
from .export_manager import ExportManager
from .filter_designer_panel import FilterDesignerPanel, FilterRequest
from .measurements_widget import MeasurementsWidget
from .multiresolution_window import MultiResolutionWindow
from .panner_widget import PannerWidget
from .preprocessing_engine import PreprocessingEngine
from .ribbon import Ribbon
from .script_generator import ScriptGenerator, SessionExport
from .settings_dialog import AnalyzerSettings, SettingsDialog
from .signal_loader import SignalLoader
from .signal_model import DEFAULT_SIGNAL_COLORS, SignalRecord
from .signal_store import SignalStore
from .spectrum_panel import SpectrumPanel
from .time_panel import TimePanel
from .workspace_bridge import WorkspaceBridge


class SignalAnalyzerWindow(QMainWindow):
    """Main desktop window for Kronos Signal Analyzer toolbox."""

    closed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Signal Analyzer")
        self.resize(1600, 900)

        self.store = SignalStore(self)
        self.engine = PreprocessingEngine()
        self.loader = SignalLoader()
        self.workspace_bridge = WorkspaceBridge(self)
        self.exporter = ExportManager()
        self.script_generator = ScriptGenerator()
        self.settings = AnalyzerSettings()
        self._multi_window: MultiResolutionWindow | None = None

        self._legend_enabled = True
        self._spectrum_use_db = True
        self._spectrum_use_psd = False
        self._cursor_modes: tuple[CursorMode, ...] = ("none", "single", "double", "track", "crosshair")
        self._cursor_mode_index = 1
        self._smooth_method = "moving average"
        self._smooth_span = 9
        self._smooth_order = 3
        self._time_line_width = 1.5

        self._color_index = 0
        self._build_ui()
        self._connect_signals()
        self._apply_style()
        self._apply_panel_defaults()

        self._workspace_timer = QTimer(self)
        self._workspace_timer.timeout.connect(self.refresh_workspace)
        self._workspace_timer.start(self.settings.workspace_refresh_interval_ms)

    def set_theme(self, theme: str = "dark") -> None:
        """Keep compatibility with Kronos toolbox host theme hooks."""
        del theme
        self._apply_style()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.closed.emit()
        super().closeEvent(event)

    def _build_ui(self) -> None:
        container = QWidget()
        root = QVBoxLayout(container)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.ribbon = Ribbon(self)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.left_panel = self._build_left_panel()
        self.center_panel = self._build_center_panel()

        splitter.addWidget(self.left_panel)
        splitter.addWidget(self.center_panel)
        splitter.setSizes([340, 1260])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)

        root.addWidget(self.ribbon)
        root.addWidget(splitter, 1)
        self.setCentralWidget(container)

        self.filter_dock = QDockWidget("Filter Designer", self)
        self.filter_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        self.filter_panel = FilterDesignerPanel(self.store, self.engine, self)
        self.filter_dock.setWidget(self.filter_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.filter_dock)

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("sa_left_panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.signal_toolbar = QWidget()
        top_row = QHBoxLayout(self.signal_toolbar)
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(6)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter signals...")
        self.import_btn = QPushButton("+")
        self.import_btn.setFixedWidth(30)
        top_row.addWidget(self.search_edit, 1)
        top_row.addWidget(self.import_btn)

        self.signal_tree = QTreeWidget()
        self.signal_tree.setHeaderLabels(["Name", "Info", "Fs", "Start Time"])
        self.signal_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.signal_tree.setAlternatingRowColors(True)

        self.workspace_label = QLabel("Workspace Browser")
        self.workspace_label.setObjectName("sa_workspace_label")
        self.workspace_table = QTableWidget(0, 3)
        self.workspace_table.setHorizontalHeaderLabels(["Name", "Size", "Class"])
        self.workspace_table.verticalHeader().setVisible(False)
        self.workspace_table.setAlternatingRowColors(True)

        layout.addWidget(self.signal_toolbar)
        layout.addWidget(self.signal_tree, 3)
        layout.addWidget(self.workspace_label)
        layout.addWidget(self.workspace_table, 2)
        return panel

    def _build_center_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("sa_center_panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.display = DisplayManager(self.store, self.engine, self)
        self.panner = PannerWidget(self)
        self.measurements = MeasurementsWidget(self.store, self.engine, self)

        layout.addWidget(self.display, 6)
        layout.addWidget(self.panner, 1)
        layout.addWidget(self.measurements, 3)
        return panel

    def _connect_signals(self) -> None:
        self.import_btn.clicked.connect(self.import_signal)
        self.search_edit.textChanged.connect(self._filter_signal_tree)

        self.signal_tree.itemSelectionChanged.connect(self._on_tree_selection_changed)
        self.signal_tree.itemChanged.connect(self._on_tree_item_changed)
        self.signal_tree.customContextMenuRequested.connect(self._show_signal_context_menu)

        self.workspace_table.itemDoubleClicked.connect(self._import_workspace_item)

        self.panner.roi_changed.connect(self.store.set_roi)
        self.panner.reset_requested.connect(self._on_panner_reset)

        self.store.signal_added.connect(lambda _rec: self._rebuild_signal_tree())
        self.store.signal_removed.connect(lambda _sid: self._rebuild_signal_tree())
        self.store.signal_updated.connect(lambda _rec: self._rebuild_signal_tree())
        self.store.selection_changed.connect(lambda _sid: self._sync_panner_signal())

        self.filter_panel.apply_to_selected_requested.connect(self._apply_filter_selected)
        self.filter_panel.apply_to_visible_requested.connect(self._apply_filter_visible)

        self.ribbon.action_triggered.connect(self._on_ribbon_action)

    def set_kernel_client(self, kernel_client) -> None:
        """Attach kernel client for workspace browsing integration."""
        self.workspace_bridge.set_kernel_client(kernel_client)
        self.refresh_workspace()

    def refresh_workspace(self) -> None:
        """Refresh workspace browser table from kernel."""
        rows = self.workspace_bridge.list_array_variables(timeout_ms=900)
        self.workspace_table.setRowCount(len(rows))
        for row, item in enumerate(rows):
            self.workspace_table.setItem(row, 0, QTableWidgetItem(item.get("name", "")))
            self.workspace_table.setItem(row, 1, QTableWidgetItem(item.get("size", "")))
            self.workspace_table.setItem(row, 2, QTableWidgetItem(item.get("class", "")))

    def import_signal(self) -> None:
        """Open file picker and import one or more signals."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Signal",
            str(Path.cwd()),
            "Signals (*.wav *.csv *.txt *.npy *.mat *.ksa)",
        )
        if not path:
            return
        try:
            records = self.loader.load_file(path)
        except Exception as exc:
            QMessageBox.warning(self, "Import Error", str(exc))
            return

        for record in records:
            self._assign_color(record)
            self.store.add_signal(record)

        self.statusBar().showMessage(f"Imported {len(records)} signal(s)", 2500)

    def _assign_color(self, record: SignalRecord) -> None:
        color = DEFAULT_SIGNAL_COLORS[self._color_index % len(DEFAULT_SIGNAL_COLORS)]
        self._color_index += 1
        record.color.setNamedColor(color)

    def _rebuild_signal_tree(self) -> None:
        self.signal_tree.blockSignals(True)
        self.signal_tree.clear()

        index: dict[str, QTreeWidgetItem] = {}
        for record in self.store.list_signals():
            item = QTreeWidgetItem([record.name, "i" if record.preprocessing_log else "", f"{record.fs:.4g}", f"{record.start_time:.4g}"])
            item.setData(0, Qt.ItemDataRole.UserRole, record.id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEditable)
            item.setCheckState(0, Qt.CheckState.Checked if record.visible else Qt.CheckState.Unchecked)
            item.setForeground(0, record.color)
            index[record.id] = item

        for record in self.store.list_signals():
            item = index[record.id]
            if record.parent_id and record.parent_id in index:
                index[record.parent_id].addChild(item)
            else:
                self.signal_tree.addTopLevelItem(item)

        self.signal_tree.expandAll()
        self.signal_tree.blockSignals(False)
        self._filter_signal_tree(self.search_edit.text())

    def _filter_signal_tree(self, text: str) -> None:
        needle = text.strip().lower()

        def visit(item: QTreeWidgetItem) -> bool:
            visible = needle in item.text(0).lower() if needle else True
            child_visible = False
            for i in range(item.childCount()):
                child_visible = visit(item.child(i)) or child_visible
            final = visible or child_visible
            item.setHidden(not final)
            return final

        for i in range(self.signal_tree.topLevelItemCount()):
            visit(self.signal_tree.topLevelItem(i))

    def _on_tree_selection_changed(self) -> None:
        selected = self.signal_tree.selectedItems()
        if not selected:
            return
        signal_id = selected[0].data(0, Qt.ItemDataRole.UserRole)
        if signal_id:
            self.store.set_selected(str(signal_id))

    def _on_tree_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        signal_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not signal_id:
            return
        record = self.store.get_signal(str(signal_id))
        if record is None:
            return

        if column == 0:
            record.visible = item.checkState(0) == Qt.CheckState.Checked
            record.name = item.text(0)
        self.store.update_signal(record)

    def _show_signal_context_menu(self, pos) -> None:
        item = self.signal_tree.itemAt(pos)
        if item is None:
            return
        signal_id = item.data(0, Qt.ItemDataRole.UserRole)
        record = self.store.get_signal(str(signal_id)) if signal_id else None
        if record is None:
            return

        menu = QMenu(self)
        rename_action = QAction("Rename", self)
        duplicate_action = QAction("Duplicate", self)
        delete_action = QAction("Delete", self)
        send_workspace = QAction("Send to Workspace", self)
        export_action = QAction("Export", self)
        multi_action = QAction("Open Multiresolution Analyzer", self)

        rename_action.triggered.connect(lambda: self._rename_record(record.id))
        duplicate_action.triggered.connect(lambda: self._duplicate_record(record.id))
        delete_action.triggered.connect(lambda: self.store.remove_signal(record.id))
        send_workspace.triggered.connect(lambda: self._copy_record_to_workspace(record.id))
        export_action.triggered.connect(lambda: self._export_record(record.id))
        multi_action.triggered.connect(self._open_multiresolution)

        menu.addAction(rename_action)
        menu.addAction(duplicate_action)
        menu.addAction(delete_action)
        menu.addSeparator()
        menu.addAction(send_workspace)
        menu.addAction(export_action)
        menu.addSeparator()
        menu.addAction(multi_action)
        menu.exec(self.signal_tree.viewport().mapToGlobal(pos))

    def _rename_record(self, signal_id: str) -> None:
        record = self.store.get_signal(signal_id)
        if record is None:
            return
        new_name, ok = QInputDialog.getText(self, "Rename Signal", "Name", text=record.name)
        if not ok or not new_name.strip():
            return
        record.name = new_name.strip()
        self.store.update_signal(record)

    def _duplicate_record(self, signal_id: str) -> None:
        record = self.store.get_signal(signal_id)
        if record is None:
            return
        clone = record.copy_with(name=f"{record.name}_copy", source="derived", parent_id=record.id)
        self._assign_color(clone)
        self.store.add_signal(clone)

    def _copy_record_to_workspace(self, signal_id: str) -> None:
        record = self.store.get_signal(signal_id)
        if record is None:
            return
        QMessageBox.information(
            self,
            "Workspace Export",
            "Use Kronos kernel integration hook to inject arrays into workspace.\n"
            "(This build keeps a local-only implementation.)",
        )

    def _export_record(self, signal_id: str) -> None:
        record = self.store.get_signal(signal_id)
        if record is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Signal",
            f"{record.name}.csv",
            "Signal Files (*.csv *.txt *.npy *.wav *.mat)",
        )
        if not path:
            return
        try:
            self.exporter.export_signal(record, path)
        except Exception as exc:
            QMessageBox.warning(self, "Export Error", str(exc))

    def _on_panner_reset(self) -> None:
        selected = self.store.selected_signal()
        if selected is None:
            return
        self.store.set_roi(selected.start_time, selected.end_time)

    def _sync_panner_signal(self) -> None:
        self.panner.set_signal(self.store.selected_signal())

    def _import_workspace_item(self, item: QTableWidgetItem) -> None:
        row = item.row()
        name_item = self.workspace_table.item(row, 0)
        if name_item is None:
            return
        record = self.workspace_bridge.fetch_signal(name_item.text())
        if record is None:
            QMessageBox.information(self, "Workspace", "Could not import workspace variable as 1D signal.")
            return
        self._assign_color(record)
        self.store.add_signal(record)

    def _apply_filter_selected(self, request: FilterRequest) -> None:
        record = self.store.selected_signal()
        if record is None:
            self.statusBar().showMessage("Select a signal first", 1800)
            return
        derived = self._create_filtered_record(record, request)
        if derived is not None:
            self._assign_color(derived)
            self.store.add_signal(derived)

    def _apply_filter_visible(self, request: FilterRequest) -> None:
        applied = 0
        for record in self.store.visible_signals():
            derived = self._create_filtered_record(record, request)
            if derived is None:
                continue
            self._assign_color(derived)
            self.store.add_signal(derived)
            applied += 1
        self.statusBar().showMessage(f"Applied filter to {applied} signal(s)", 2200)

    def _create_filtered_record(self, record: SignalRecord, request: FilterRequest) -> SignalRecord | None:
        try:
            filtered = self.engine.apply_filter(
                record.data,
                request.designed_filter,
                zero_phase=request.zero_phase,
            )
        except Exception as exc:
            QMessageBox.warning(self, "Filter Error", str(exc))
            return None

        return record.copy_with(
            name=f"{record.name}_filtered",
            data=filtered,
            source="derived",
            parent_id=record.id,
            append_log=f"filter({self.filter_panel.kind_combo.currentText()}, {self.filter_panel.method_combo.currentText()})",
        )

    def _on_ribbon_action(self, action_id: str) -> None:
        dispatch = {
            "new_session": self._new_session,
            "open_session": self._open_session,
            "save_session": self._save_session,
            "display_grid": self._choose_grid,
            "toggle_signal_table": self._toggle_signal_table,
            "toggle_workspace": self._toggle_workspace_panel,
            "toggle_measurements": self._toggle_measurements_panel,
            "toggle_filter": self._toggle_filter_dock,
            "export_signal": self._export_selected_signal,
            "duplicate_signal": self._duplicate_selected_signal,
            "delete_signal": self._delete_selected_signal,
            "smooth": self._smooth_selected,
            "quick_lowpass": lambda: self._apply_quick_filter("lowpass"),
            "quick_highpass": lambda: self._apply_quick_filter("highpass"),
            "quick_bandpass": lambda: self._apply_quick_filter("bandpass"),
            "generate_script": self._generate_script,
            "preferences": self._open_preferences,
            "clear_display": self._clear_display,
            "legend_mode": self._toggle_legend,
            "link_time": lambda: self.statusBar().showMessage("Panels are linked through shared ROI", 2000),
            "cursor_mode": self._cycle_cursor_mode,
            "snap_to_data": self._enable_track_cursor,
            "zoom_in": lambda: self._zoom_all(0.8),
            "zoom_out": lambda: self._zoom_all(1.25),
            "pan": lambda: self.statusBar().showMessage("Drag inside plots to inspect with cursors", 1800),
            "reset_view": self._reset_all_views,
            "view_time": lambda: self._set_views(["time"]),
            "view_spectrum": lambda: self._set_views(["spectrum"]),
            "view_spectrogram": lambda: self._set_views(["spectrogram"]),
            "view_scalogram": lambda: self._set_views(["scalogram"]),
            "view_persistence": lambda: self._set_views(["persistence"]),
            "est_power": self._set_spectrum_power,
            "est_psd": self._set_spectrum_psd,
            "est_specgram": lambda: self._set_views(["spectrogram"]),
            "est_persistence": lambda: self._set_views(["persistence"]),
            "display_db": self._toggle_spectrum_db,
            "display_norm": lambda: self.statusBar().showMessage("Normalized frequency axis coming soon", 2000),
            "display_two_sided": lambda: self.statusBar().showMessage("Two-sided spectrum mode coming soon", 2000),
            "find_peaks": lambda: self.statusBar().showMessage("Peak finder UI update coming soon", 2000),
            "label_peaks": lambda: self.statusBar().showMessage("Peak labels UI update coming soon", 2000),
            "measure_set_roi": self._set_roi_from_selected,
            "measure_clear_roi": self._clear_roi,
            "measure_select_all": self._select_all_signals,
            "measure_deselect_all": self._deselect_all_signals,
            "smooth_ma": lambda: self._select_smoothing_method("moving average"),
            "smooth_gaussian": lambda: self._select_smoothing_method("gaussian"),
            "smooth_savgol": lambda: self._select_smoothing_method("savitzky-golay"),
            "smooth_lowess": lambda: self._select_smoothing_method("lowess"),
            "smooth_robust_lowess": lambda: self._select_smoothing_method("robust lowess"),
            "smooth_preview": lambda: self._smooth_selected(preview=True),
            "smooth_apply": lambda: self._smooth_selected(preview=False),
            "smooth_undo": self._undo_smoothing,
            "trace_width": self._set_trace_width,
            "time_amplitude": lambda: self._set_views(["time"]),
            "time_envelope": self._add_envelope_signal,
            "time_inst_freq": self._add_instantaneous_frequency_signal,
            "time_inst_phase": self._add_instantaneous_phase_signal,
            "trace_style": lambda: self.statusBar().showMessage("Trace style presets coming soon", 2000),
            "trace_color": self._change_selected_signal_color,
            "measure_export_csv": self.measurements._export_csv,
        }
        handler = dispatch.get(action_id)
        if handler is None:
            self.statusBar().showMessage(f"{action_id} is not wired yet", 1800)
            return
        try:
            handler()
        except Exception as exc:
            QMessageBox.critical(self, "Signal Analyzer", f"Action '{action_id}' failed:\n{exc}")
            self.statusBar().showMessage(f"{action_id} failed", 2500)

    def _set_views(self, views: list[str]) -> None:
        self.display.set_views(views)
        self._apply_panel_defaults()

    def _apply_panel_defaults(self) -> None:
        mode = self._cursor_modes[self._cursor_mode_index]
        for panel in self.display.panels():
            if hasattr(panel, "cursors"):
                panel.cursors.set_mode(mode)
            if isinstance(panel, TimePanel):
                panel.set_show_legend(self._legend_enabled)
                panel.set_line_width(self._time_line_width)
            if isinstance(panel, SpectrumPanel):
                panel.set_db_scale(self._spectrum_use_db)
                panel.set_psd_mode(self._spectrum_use_psd)

    def _toggle_signal_table(self) -> None:
        visible = not self.signal_tree.isVisible()
        self.signal_toolbar.setVisible(visible)
        self.signal_tree.setVisible(visible)
        self.statusBar().showMessage(f"Signal table {'shown' if visible else 'hidden'}", 1800)

    def _toggle_workspace_panel(self) -> None:
        visible = not self.workspace_table.isVisible()
        self.workspace_label.setVisible(visible)
        self.workspace_table.setVisible(visible)
        self.statusBar().showMessage(f"Workspace browser {'shown' if visible else 'hidden'}", 1800)

    def _toggle_measurements_panel(self) -> None:
        visible = not self.measurements.isVisible()
        self.measurements.setVisible(visible)
        self.statusBar().showMessage(f"Measurements {'shown' if visible else 'hidden'}", 1800)

    def _selected_signal_id(self) -> str | None:
        selected = self.store.selected_signal()
        return selected.id if selected is not None else None

    def _export_selected_signal(self) -> None:
        signal_id = self._selected_signal_id()
        if signal_id is None:
            self.statusBar().showMessage("Select a signal to export", 2000)
            return
        self._export_record(signal_id)

    def _duplicate_selected_signal(self) -> None:
        signal_id = self._selected_signal_id()
        if signal_id is None:
            self.statusBar().showMessage("Select a signal to duplicate", 2000)
            return
        self._duplicate_record(signal_id)

    def _delete_selected_signal(self) -> None:
        signal_id = self._selected_signal_id()
        if signal_id is None:
            self.statusBar().showMessage("Select a signal to delete", 2000)
            return
        self.store.remove_signal(signal_id)

    def _apply_quick_filter(self, kind: str) -> None:
        record = self.store.selected_signal()
        if record is None:
            self.statusBar().showMessage("Select a signal before filtering", 2000)
            return

        fs = max(record.fs, 1.0)
        fc1 = max(1.0, fs * 0.08)
        fc2 = max(fc1 + 1.0, fs * 0.28)

        designed = self.engine.design_filter(
            kind=kind,  # type: ignore[arg-type]
            method="butterworth",
            order=6,
            fs=fs,
            fc1=fc1,
            fc2=fc2,
        )
        request = FilterRequest(designed_filter=designed, zero_phase=True)
        derived = self._create_filtered_record(record, request)
        if derived is None:
            return
        self._assign_color(derived)
        self.store.add_signal(derived)
        self.statusBar().showMessage(f"Applied quick {kind} filter", 2200)

    def _clear_display(self) -> None:
        self._set_views(["time"])
        self.statusBar().showMessage("Display reset to Time view", 1800)

    def _toggle_legend(self) -> None:
        self._legend_enabled = not self._legend_enabled
        for panel in self.display.panels():
            if isinstance(panel, TimePanel):
                panel.set_show_legend(self._legend_enabled)
        self.statusBar().showMessage(f"Legend {'on' if self._legend_enabled else 'off'}", 1800)

    def _cycle_cursor_mode(self) -> None:
        self._cursor_mode_index = (self._cursor_mode_index + 1) % len(self._cursor_modes)
        mode = self._cursor_modes[self._cursor_mode_index]
        for panel in self.display.panels():
            if hasattr(panel, "cursors"):
                panel.cursors.set_mode(mode)
        self.statusBar().showMessage(f"Cursor mode: {mode}", 1800)

    def _enable_track_cursor(self) -> None:
        self._cursor_mode_index = self._cursor_modes.index("track")
        for panel in self.display.panels():
            if hasattr(panel, "cursors"):
                panel.cursors.set_mode("track")
        self.statusBar().showMessage("Snap to data enabled (track cursor)", 1800)

    def _zoom_all(self, scale: float) -> None:
        for panel in self.display.panels():
            if not hasattr(panel, "axes"):
                continue
            axes = panel.axes
            x0, x1 = axes.get_xlim()
            y0, y1 = axes.get_ylim()
            xc = (x0 + x1) * 0.5
            yc = (y0 + y1) * 0.5
            xr = max(abs(x1 - x0) * 0.5 * scale, 1e-12)
            yr = max(abs(y1 - y0) * 0.5 * scale, 1e-12)
            axes.set_xlim(xc - xr, xc + xr)
            axes.set_ylim(yc - yr, yc + yr)
            panel.canvas.draw_idle()

    def _reset_all_views(self) -> None:
        for panel in self.display.panels():
            if hasattr(panel, "refresh"):
                panel.refresh()
        self.statusBar().showMessage("Reset view", 1600)

    def _set_spectrum_psd(self) -> None:
        self._spectrum_use_psd = True
        self._set_views(["spectrum"])
        self.statusBar().showMessage("Spectrum mode: PSD", 1800)

    def _set_spectrum_power(self) -> None:
        self._spectrum_use_psd = False
        self._set_views(["spectrum"])
        self.statusBar().showMessage("Spectrum mode: Power Spectrum", 1800)

    def _toggle_spectrum_db(self) -> None:
        self._spectrum_use_db = not self._spectrum_use_db
        for panel in self.display.panels():
            if isinstance(panel, SpectrumPanel):
                panel.set_db_scale(self._spectrum_use_db)
        self.statusBar().showMessage(f"Spectrum dB {'on' if self._spectrum_use_db else 'off'}", 1800)

    def _set_roi_from_selected(self) -> None:
        selected = self.store.selected_signal()
        if selected is None:
            self.statusBar().showMessage("Select a signal first", 1800)
            return
        self.store.set_roi(selected.start_time, selected.end_time)
        self.statusBar().showMessage("ROI set to full selected signal", 1800)

    def _clear_roi(self) -> None:
        selected = self.store.selected_signal()
        if selected is None:
            return
        self.store.set_roi(selected.start_time, selected.end_time)
        self.panner.set_signal(selected)
        self.statusBar().showMessage("ROI cleared", 1800)

    def _select_all_signals(self) -> None:
        for record in self.store.list_signals():
            if not record.visible:
                record.visible = True
                self.store.update_signal(record)
        self.statusBar().showMessage("All signals selected", 1800)

    def _deselect_all_signals(self) -> None:
        for record in self.store.list_signals():
            if record.visible:
                record.visible = False
                self.store.update_signal(record)
        self.statusBar().showMessage("All signals hidden", 1800)

    def _select_smoothing_method(self, method: str) -> None:
        self._smooth_method = method
        self.statusBar().showMessage(f"Smoothing method: {method}", 1800)

    def _set_trace_width(self) -> None:
        width, ok = QInputDialog.getDouble(
            self,
            "Trace Width",
            "Line width",
            1.5,
            0.5,
            6.0,
            1,
        )
        if not ok:
            return
        self._time_line_width = float(width)
        for panel in self.display.panels():
            if isinstance(panel, TimePanel):
                panel.set_line_width(self._time_line_width)

    def _undo_smoothing(self) -> None:
        selected = self.store.selected_signal()
        if selected is None:
            return
        candidates = [
            record
            for record in self.store.list_signals()
            if record.parent_id == selected.id and record.name.endswith("_smooth")
        ]
        if not candidates and selected.name.endswith("_smooth") and selected.parent_id is not None:
            self.store.remove_signal(selected.id)
            return
        if not candidates:
            self.statusBar().showMessage("No smoothing result to undo for selected signal", 2000)
            return
        self.store.remove_signal(candidates[-1].id)
        self.statusBar().showMessage("Removed latest smoothing result", 1800)

    def _change_selected_signal_color(self) -> None:
        record = self.store.selected_signal()
        if record is None:
            self.statusBar().showMessage("Select a signal first", 1800)
            return
        color = QColorDialog.getColor(record.color, self, "Select Signal Color")
        if not color.isValid():
            return
        record.color = color
        self.store.update_signal(record)

    def _add_envelope_signal(self) -> None:
        record = self.store.selected_signal()
        if record is None:
            self.statusBar().showMessage("Select a signal first", 1800)
            return
        analytic = sp_signal.hilbert(np.asarray(record.data, dtype=np.float64))
        envelope = np.abs(analytic)
        derived = record.copy_with(
            name=f"{record.name}_envelope",
            data=envelope,
            source="derived",
            parent_id=record.id,
            append_log="envelope(hilbert)",
        )
        self._assign_color(derived)
        self.store.add_signal(derived)

    def _add_instantaneous_phase_signal(self) -> None:
        record = self.store.selected_signal()
        if record is None:
            self.statusBar().showMessage("Select a signal first", 1800)
            return
        analytic = sp_signal.hilbert(np.asarray(record.data, dtype=np.float64))
        phase = np.unwrap(np.angle(analytic))
        derived = record.copy_with(
            name=f"{record.name}_phase",
            data=phase,
            source="derived",
            parent_id=record.id,
            append_log="instantaneous_phase(hilbert)",
        )
        self._assign_color(derived)
        self.store.add_signal(derived)

    def _add_instantaneous_frequency_signal(self) -> None:
        record = self.store.selected_signal()
        if record is None:
            self.statusBar().showMessage("Select a signal first", 1800)
            return
        analytic = sp_signal.hilbert(np.asarray(record.data, dtype=np.float64))
        phase = np.unwrap(np.angle(analytic))
        dphase = np.diff(phase, prepend=phase[0])
        inst_freq = dphase * (record.fs / (2.0 * np.pi))
        derived = record.copy_with(
            name=f"{record.name}_inst_freq",
            data=inst_freq,
            source="derived",
            parent_id=record.id,
            append_log="instantaneous_frequency(hilbert)",
        )
        self._assign_color(derived)
        self.store.add_signal(derived)

    def _new_session(self) -> None:
        self.store.clear()
        self._set_views(["time"])
        self.statusBar().showMessage("New Signal Analyzer session", 1800)

    def _open_session(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open Session", str(Path.cwd()), "Kronos Session (*.ksa)")
        if not path:
            return
        self._new_session()
        try:
            records = self.loader.load_file(path)
        except Exception as exc:
            QMessageBox.warning(self, "Open Session", str(exc))
            return
        for record in records:
            self._assign_color(record)
            self.store.add_signal(record)

    def _save_session(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save Session", "session.ksa", "Kronos Session (*.ksa)")
        if not path:
            return
        try:
            self.exporter.save_session(self.store.list_signals(), path)
        except Exception as exc:
            QMessageBox.warning(self, "Save Session", str(exc))

    def _choose_grid(self) -> None:
        options = ["1x1", "1x2", "2x1", "2x2", "2x3", "3x2", "4x2"]
        value, ok = QInputDialog.getItem(self, "Display Grid", "Layout", options, editable=False)
        if not ok:
            return
        rows, cols = [int(v) for v in value.split("x")]
        self.display.set_grid(rows, cols)

        # Keep current first view and add spectrum placeholders.
        base = [panel.view_name().lower() for panel in self.display.panels() if hasattr(panel, "view_name")]
        if not base:
            base = ["time"]
        target_count = rows * cols
        while len(base) < target_count:
            base.append("spectrum")
        self._set_views(base[:target_count])

    def _toggle_filter_dock(self) -> None:
        self.filter_dock.setVisible(not self.filter_dock.isVisible())

    def _generate_script(self) -> None:
        script = self.script_generator.generate_script(SessionExport(self.store.list_signals()))
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Generated Script")
        dialog.setText("Generated script preview is available below.")
        preview = QPlainTextEdit()
        preview.setPlainText(script)
        preview.setReadOnly(True)
        preview.setMinimumSize(900, 520)
        dialog.layout().addWidget(preview, 1, 0, 1, dialog.layout().columnCount())
        dialog.exec()

    def _open_preferences(self) -> None:
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        self.settings = dialog.values()
        if self.settings.workspace_auto_refresh:
            self._workspace_timer.start(self.settings.workspace_refresh_interval_ms)
        else:
            self._workspace_timer.stop()

    def _smooth_selected(self, *, preview: bool = False) -> None:
        record = self.store.selected_signal()
        if record is None:
            self.statusBar().showMessage("Select a signal first", 1800)
            return
        method = self._smooth_method
        smoothed = self.engine.smooth(record.data, method, span=self._smooth_span, order=self._smooth_order)
        suffix = "_preview" if preview else "_smooth"
        derived = record.copy_with(
            name=f"{record.name}{suffix}",
            data=smoothed,
            source="derived",
            parent_id=record.id,
            append_log=f"smooth({method})",
        )
        self._assign_color(derived)
        self.store.add_signal(derived)
        self.statusBar().showMessage(
            f"{'Previewed' if preview else 'Applied'} smoothing ({method})",
            2200,
        )

    def _open_multiresolution(self) -> None:
        if self._multi_window is None:
            self._multi_window = MultiResolutionWindow(self.store, self.engine, self)
            self._multi_window.destroyed.connect(lambda *_args: self._clear_multi_window())
        self._multi_window.show()
        self._multi_window.raise_()
        self._multi_window.activateWindow()

    def _clear_multi_window(self) -> None:
        self._multi_window = None

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: #e7ebf1;
                color: #1f2937;
            }
            QWidget {
                color: #1f2937;
                background: #e7ebf1;
                font-size: 9pt;
            }

            QWidget#sa_ribbon {
                background: #d9dee7;
                border-bottom: 1px solid #9aa6b8;
            }

            QTabWidget#sa_ribbon_tabs::pane {
                border: 1px solid #8c9aad;
                border-top: 0;
                background: #d9dee7;
            }

            QTabBar::tab {
                background: #0b4477;
                color: #cde2ff;
                padding: 7px 16px;
                border: 0;
                min-width: 86px;
                min-height: 24px;
            }
            QTabBar::tab:selected {
                background: #185f97;
                color: #ffffff;
                border-bottom: 3px solid #86e1ff;
            }

            QWidget#sa_ribbon_page {
                background: #d9dee7;
            }
            QFrame#sa_ribbon_section {
                background: #d9dee7;
                border: none;
            }
            QFrame#sa_ribbon_separator {
                background: #aab4c4;
                min-width: 1px;
                max-width: 1px;
                margin-top: 8px;
                margin-bottom: 14px;
            }
            QLabel#sa_ribbon_section_label {
                color: #4b5563;
                font-size: 8pt;
                letter-spacing: 0.5px;
            }
            QToolButton#sa_ribbon_button {
                background: transparent;
                border: 1px solid transparent;
                border-radius: 6px;
                padding: 4px 4px;
                color: #1f2937;
                font-size: 8.5pt;
            }
            QToolButton#sa_ribbon_button:hover {
                background: #ecf2fb;
                border: 1px solid #9fb7d6;
            }
            QToolButton#sa_ribbon_button:pressed {
                background: #cde0f8;
                border: 1px solid #6f97c5;
            }

            QFrame#sa_panel_header {
                background: #23364f;
                border: 1px solid #3b4f6d;
                border-radius: 6px;
            }
            QLabel#sa_panel_title {
                color: #e5edf8;
                font-weight: 600;
            }

            QPushButton {
                background: #f6f8fb;
                border: 1px solid #b2bfd2;
                border-radius: 5px;
                padding: 5px 10px;
                color: #1f2937;
            }
            QPushButton:hover {
                background: #e7eef8;
            }
            QPushButton:pressed {
                background: #d6e4f6;
            }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit {
                background: #ffffff;
                border: 1px solid #a8b4c5;
                border-radius: 4px;
                padding: 4px;
                color: #111827;
            }
            QTreeWidget, QTableWidget {
                background: #f8fafc;
                alternate-background-color: #edf2f9;
                gridline-color: #c4cedd;
                border: 1px solid #b9c6d8;
                color: #1f2937;
            }
            QTreeWidget::item:selected, QTableWidget::item:selected {
                background: #2f5f94;
                color: #ffffff;
            }
            QHeaderView::section {
                background: #dde3ec;
                border: 1px solid #b9c6d8;
                padding: 4px;
                color: #334155;
            }

            QWidget#sa_left_panel {
                background: #e4e9f1;
                border: 1px solid #bcc7d8;
                border-radius: 8px;
            }
            QWidget#sa_center_panel {
                background: #e7ebf1;
            }
            QLabel#sa_workspace_label {
                color: #334155;
                font-weight: 600;
            }
            """
        )
