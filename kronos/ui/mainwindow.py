"""Main application window for Kronos."""

from __future__ import annotations

import json
import os
import pickle
from pathlib import Path

def _ensure_mpl_config_dir() -> None:
    """Ensure Matplotlib can write its config/cache files."""
    if os.environ.get("MPLCONFIGDIR"):
        return
    candidates = [Path.home() / ".cache" / "matplotlib", Path("/tmp") / "kronos-mpl"]
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            os.environ["MPLCONFIGDIR"] = str(candidate)
            return
        except OSError:
            continue


_ensure_mpl_config_dir()

from matplotlib.figure import Figure
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QDialog,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from kronos.engine.kernel_bridge import KernelBridge
from kronos.engine.kernel_message_router import KernelMessageRouter
from kronos.engine import plot_manager
from kronos.engine.settings_manager import SettingsManager
from kronos.engine.workspace_manager import WorkspaceManager
from kronos.ui.bottom.console_panel import ConsolePanel
from kronos.ui.bottom.figure_panel import FigurePanel
from kronos.ui.center.editor import CenterPanel
from kronos.ui.left_panel import LeftPanel
from kronos.ui.right_panel import RightPanel
from kronos.ui.ribbon import MatlabRibbon
from kronos.ui.statusbar import KronosStatusBar
from kronos.ui.aeon_window import AeonWindow
from kronos.ui.theme import apply_stylesheet


class PlotPickerDialog(QDialog):
    """Dialog to pick which plot to show in Figures."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._mapping: list[tuple[int, int | None]] = []

        self.setWindowTitle("Show Plot")
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_row_changed)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)

        layout.addWidget(self._list, 1)
        layout.addWidget(close_btn)

    def set_items(
        self,
        labels: list[str],
        mapping: list[tuple[int | None, int | None, str | None]],
        selection_callback,
    ) -> None:
        self._mapping = mapping
        self._selection_callback = selection_callback
        self._list.clear()
        for label in labels:
            self._list.addItem(label)
        if labels:
            self._list.setCurrentRow(0)

    def _on_row_changed(self, row: int) -> None:
        if row < 0 or row >= len(self._mapping):
            return
        fig_num, axes_index, var_name = self._mapping[row]
        if self._selection_callback is not None:
            self._selection_callback(fig_num, axes_index, var_name)


class MainWindow(QMainWindow):
    """Main window for the Kronos IDE."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Kronos 2026.1")
        self.setMinimumSize(1280, 800)
        self.settings_manager = SettingsManager()
        self._current_theme = self.settings_manager.get("appearance/theme", "light")
        apply_stylesheet(QApplication.instance(), self._current_theme)
        # MATLAB-style external figure windows (disable integrated figures panel).
        self._integrated_figures_enabled = False

        self.left_panel = LeftPanel()
        self.center_panel = CenterPanel()
        self.right_panel = RightPanel()
        self.console_panel = ConsolePanel()
        self.figure_panel = FigurePanel()
        self.left_panel.setMinimumWidth(250)
        self.right_panel.setMinimumWidth(240)
        self.center_panel.setMinimumWidth(500)
        self.kernel_bridge = KernelBridge(self.console_panel.get_kernel_client())
        self.kernel_message_router = KernelMessageRouter(
            self.console_panel.get_kernel_client(), self
        )
        self.workspace_manager = WorkspaceManager()
        runtime_dir = Path(os.environ.get("KRONOS_RUNTIME_DIR", "/tmp/kronos-runtime"))
        self._figure_transfer_path = runtime_dir / "latest_console_plot.pkl"
        self._figure_transfer_status_path = runtime_dir / "latest_console_plot.json"
        self._figure_list_path = runtime_dir / "latest_console_figures.json"
        self._plots_manifest_path = runtime_dir / "plots_manifest.json"
        self._plots_dir = runtime_dir / "plots"
        self._figure_transfer_pending = False
        self._suppress_workspace_update = False
        self._suppress_plot_refresh = False
        self._plot_refresh_pending = False
        self._selected_axes_index: int | None = None
        self._selected_figure_num: int | None = None
        self._selected_figure_var: str | None = None
        self._queued_selection: tuple[int | None, int | None, str | None] | None = None
        self._plot_picker: PlotPickerDialog | None = None
        self._aeon_window: AeonWindow | None = None

        self._build_menubar()
        self._build_ribbon()
        self.ribbon.set_theme_icon(self._current_theme)
        self.ribbon.set_breadcrumb(os.getcwd())
        self._build_statusbar()
        self._build_layout()
        self._plot_refresh_timer = QTimer(self)
        self._plot_refresh_timer.setSingleShot(True)
        self._plot_refresh_timer.timeout.connect(self._refresh_plots_from_kernel)
        self._hide_figure_panel_initial()
        self._connect_signals()
        self._center_on_screen()
        self._sync_panel_themes()

    def _sync_panel_themes(self) -> None:
        """Propagate current UI theme down to embedded tool kernels."""
        is_dark = self._current_theme == "dark"
        self.center_panel.set_theme(is_dark)
        self.console_panel.set_theme(is_dark)
        self.figure_panel.set_theme(is_dark)
        if hasattr(self.left_panel, "set_theme"):
            self.left_panel.set_theme(is_dark)

    def _center_on_screen(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geometry = screen.geometry()
        width, height = 1280, 800
        self.setGeometry(
            (geometry.width() - width) // 2,
            (geometry.height() - height) // 2,
            width,
            height,
        )

    def _build_layout(self) -> None:
        outer_splitter = QSplitter(Qt.Orientation.Vertical)
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._main_splitter = main_splitter
        self._bottom_splitter = bottom_splitter
        self._outer_splitter = outer_splitter

        main_splitter.addWidget(self.left_panel)
        main_splitter.addWidget(self.center_panel)
        main_splitter.addWidget(self.right_panel)
        main_splitter.setChildrenCollapsible(False)
        main_splitter.setSizes([250, 780, 250])
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setStretchFactor(2, 0)

        bottom_splitter.addWidget(self.console_panel)
        bottom_splitter.addWidget(self.figure_panel)
        bottom_splitter.setChildrenCollapsible(False)
        bottom_splitter.setSizes([630, 650])

        outer_splitter.addWidget(main_splitter)
        outer_splitter.addWidget(bottom_splitter)
        outer_splitter.setChildrenCollapsible(False)
        outer_splitter.setSizes([640, 160])
        outer_splitter.setStretchFactor(0, 1)
        outer_splitter.setStretchFactor(1, 0)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.ribbon)
        layout.addWidget(outer_splitter, 1)
        self.setCentralWidget(container)

    def _build_menubar(self) -> None:
        menubar = self.menuBar()
        menubar.setVisible(False)

        file_menu = menubar.addMenu("File")
        self.menu_new = file_menu.addAction("New")
        self.menu_open = file_menu.addAction("Open")
        self.menu_save = file_menu.addAction("Save")
        self.menu_save_as = file_menu.addAction("Save As")
        file_menu.addSeparator()
        self._recent_menu = file_menu.addMenu("Recent Files")
        self._rebuild_recent_menu()
        file_menu.addSeparator()
        self.menu_exit = file_menu.addAction("Exit")

        edit_menu = menubar.addMenu("Edit")
        self.menu_undo = edit_menu.addAction("Undo")
        self.menu_redo = edit_menu.addAction("Redo")
        edit_menu.addSeparator()
        self.menu_find = edit_menu.addAction("Find")
        self.menu_replace = edit_menu.addAction("Replace")

        run_menu = menubar.addMenu("Run")
        self.menu_run_file = run_menu.addAction("Run File")
        self.menu_run_file.setShortcut("F5")
        self.menu_stop_kernel = run_menu.addAction("Stop Kernel")
        self.menu_restart_kernel = run_menu.addAction("Restart Kernel")

        tools_menu = menubar.addMenu("Tools")
        self.menu_bode = tools_menu.addAction("Bode Wizard")
        self.menu_step = tools_menu.addAction("Step Response")
        self.menu_rootlocus = tools_menu.addAction("Root Locus")
        self.menu_pid = tools_menu.addAction("PID Tuner")
        self.menu_lqr = tools_menu.addAction("LQR Designer")
        self.menu_freq = tools_menu.addAction("Frequency Analyzer")
        tools_menu.addSeparator()
        self.menu_preferences = tools_menu.addAction("Preferences")

        help_menu = menubar.addMenu("Help")
        self.menu_docs = help_menu.addAction("Documentation")
        self.menu_about = help_menu.addAction("About Kronos")

    def _build_ribbon(self) -> None:
        self.ribbon = MatlabRibbon(self)

    def _build_statusbar(self) -> None:
        self.status = KronosStatusBar(self)
        self.setStatusBar(self.status)
        self.status.set_kernel_client_getter(self.console_panel.get_kernel_client)

    def _connect_signals(self) -> None:
        self.ribbon.run_requested.connect(self._on_run)
        self.ribbon.stop_requested.connect(self._on_stop)
        self.ribbon.restart_requested.connect(self._on_restart_kernel)
        self.ribbon.save_requested.connect(self._on_save)
        self.ribbon.open_requested.connect(self._on_open)
        self.ribbon.new_requested.connect(self._on_new)
        self.ribbon.bode_requested.connect(self._open_bode_wizard)
        self.ribbon.step_requested.connect(self._open_step_response)
        self.ribbon.rootlocus_requested.connect(self._open_root_locus)
        self.ribbon.pid_requested.connect(self._open_pid_tuner)
        self.ribbon.lqr_requested.connect(self._open_lqr_designer)
        self.ribbon.theme_toggle_requested.connect(self._toggle_theme)
        self.ribbon.aeon_requested.connect(self._open_aeon_window)
        self.ribbon.action_requested.connect(self._on_ribbon_action)

        self.menu_run_file.triggered.connect(self._on_run)
        self.menu_stop_kernel.triggered.connect(self._on_stop)
        self.menu_restart_kernel.triggered.connect(self._on_restart_kernel)
        self.menu_open.triggered.connect(self._on_open)
        self.menu_save.triggered.connect(self._on_save)
        self.menu_new.triggered.connect(self._on_new)
        self.menu_exit.triggered.connect(self.close)
        self.menu_bode.triggered.connect(self._open_bode_wizard)
        self.menu_step.triggered.connect(self._open_step_response)
        self.menu_rootlocus.triggered.connect(self._open_root_locus)
        self.menu_pid.triggered.connect(self._open_pid_tuner)
        self.menu_lqr.triggered.connect(self._open_lqr_designer)
        self.menu_freq.triggered.connect(self._open_frequency_analyzer)
        self.menu_preferences.triggered.connect(self._open_preferences)
        self.menu_about.triggered.connect(self._open_about)

        self.left_panel.file_open_requested.connect(self._on_open_file)
        self.left_panel.snippet_insert_requested.connect(self.center_panel.insert_snippet)
        self.center_panel.simulation_complete.connect(self._on_simulation_complete)
        self.console_panel.transfer_figure_requested.connect(self._on_transfer_console_plot)
        self.console_panel.problem_open_requested.connect(self._on_problem_open_requested)
        self.center_panel.tabs.currentChanged.connect(self._on_tab_changed)
        self.center_panel.editor_cursor_changed.connect(self._on_cursor_changed)
        self._on_tab_changed(self.center_panel.tabs.currentIndex())

        self.kernel_bridge.execution_finished.connect(self._on_kernel_execution_finished)
        self.kernel_bridge.error_occurred.connect(self._on_kernel_error)
        self.workspace_manager.workspace_changed.connect(self.right_panel.update_workspace)
        self.workspace_manager.workspace_changed.connect(self.left_panel.update_workspace)
        self.right_panel.clear_workspace_requested.connect(self.workspace_manager.clear)
        self.right_panel.update_analysis_sources(
            self.console_panel.get_kernel_client,
            self.workspace_manager.get_variables,
            lambda: self.kernel_message_router,
        )
        self.figure_panel.plot_requested.connect(self._on_plot_thumbnail_selected)

    def _on_tab_changed(self, index: int) -> None:
        self.ribbon.set_control_tools_enabled(index >= 0)

    def _on_cursor_changed(self, *args) -> None:
        line, col = self.center_panel.editor.get_cursor_position()
        self.status.update_cursor(line + 1, col + 1)

    def _on_open_file(self, path: str) -> None:
        try:
            code = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(self, "Open failed", str(exc))
            return
        self.center_panel.open_document(path, code)
        self.ribbon.set_breadcrumb(str(Path(path).parent))

    def _on_problem_open_requested(self, path: str, line_no: int) -> None:
        self._on_open_file(path)
        target_line = max(1, line_no) - 1
        editor = self.center_panel.editor
        if hasattr(editor, "setCursorPosition"):
            try:
                editor.setCursorPosition(target_line, 0)
            except Exception:
                pass
        elif hasattr(editor, "textCursor"):
            try:
                cursor = editor.textCursor()
                cursor.movePosition(cursor.MoveOperation.Start)
                cursor.movePosition(cursor.MoveOperation.Down, cursor.MoveMode.MoveAnchor, target_line)
                editor.setTextCursor(cursor)
            except Exception:
                pass

    def _on_kernel_error(self, traceback_text: str) -> None:
        QMessageBox.critical(self, "Execution Error", traceback_text)

    def _on_kernel_execution_finished(self, status: str) -> None:
        if not self._suppress_workspace_update:
            self.workspace_manager.update_from_kernel(
                self.console_panel.get_kernel_client()
            )
        if (
            self._integrated_figures_enabled
            and status == "ok"
            and not self._suppress_plot_refresh
        ):
            self._schedule_plot_refresh()

    def _schedule_plot_refresh(self) -> None:
        if self._plot_refresh_timer.isActive():
            self._plot_refresh_timer.stop()
        self._plot_refresh_timer.start(400)

    def _on_run(self) -> None:
        code = self.center_panel.get_current_code()
        self.kernel_bridge.execute_file_or_code(code)

    def _on_stop(self) -> None:
        self.console_panel.interrupt_kernel()
        self.status.set_kernel_status(False)

    def _on_restart_kernel(self) -> None:
        self.console_panel.restart_kernel()
        QTimer.singleShot(
            250,
            lambda: self.kernel_message_router.attach(
                self.console_panel.get_kernel_client()
            ),
        )
        self.status.set_kernel_status(True)

    def _on_save(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save File", os.getcwd(), "Python Files (*.py)"
        )
        if not path:
            return
        try:
            Path(path).write_text(self.center_panel.get_current_code(), encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(self, "Save failed", str(exc))

    def _on_open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open File", os.getcwd(), "Python Files (*.py)"
        )
        if path:
            self._on_open_file(path)
            self.settings_manager.add_recent_file(path)
            self._rebuild_recent_menu()

    def _on_new(self) -> None:
        self.center_panel.new_file()

    def _hide_figure_panel_initial(self) -> None:
        self.figure_panel.hide()
        bottom_sizes = self._bottom_splitter.sizes()
        if len(bottom_sizes) == 2:
            total = max(sum(bottom_sizes), 2)
            self._bottom_splitter.setSizes([total, 0])

    def _on_transfer_console_plot(self) -> None:
        if self._integrated_figures_enabled:
            self._schedule_plot_refresh()

    def _refresh_plots_from_kernel(self) -> None:
        if not self._integrated_figures_enabled:
            return
        if self._plot_refresh_pending:
            return
        if self.console_panel.get_kernel_client() is None:
            return
        self._plot_refresh_pending = True
        self._suppress_workspace_update = True
        self._suppress_plot_refresh = True
        self.kernel_bridge.execute_code(
            self._build_plot_export_all_code(),
            on_finished=self._on_plot_export_ready,
            silent=True,
            store_history=False,
        )

    def _build_plot_export_all_code(self) -> str:
        return plot_manager.build_plot_export_all_code(
            self._plots_manifest_path, self._plots_dir
        )

    def _on_plot_export_ready(self, status: str) -> None:
        self._plot_refresh_pending = False
        self._suppress_workspace_update = False
        self._suppress_plot_refresh = False
        if status != "ok":
            return

        plot_items = plot_manager.parse_plot_manifest(self._plots_manifest_path)
        self.figure_panel.set_plot_items(plot_items)
        if plot_items:
            self._ensure_figure_panel_visible()

    def _on_plot_thumbnail_selected(
        self, fig_num: int | None, axes_index: int | None, var_name: str | None
    ) -> None:
        if not self._integrated_figures_enabled:
            return
        if self._figure_transfer_pending:
            self._queued_selection = (fig_num, axes_index, var_name)
            return
        self.figure_panel.preview_selection(fig_num, axes_index, var_name)
        self._selected_axes_index = axes_index
        self._selected_figure_num = fig_num
        self._selected_figure_var = var_name
        self._export_selected_console_figure(fig_num, var_name)

    def _build_console_figure_list_code(self) -> str:
        return plot_manager.build_console_figure_list_code(self._figure_list_path)

    def _on_console_figure_list_ready(self, status: str) -> None:
        self._figure_transfer_pending = False
        if status != "ok":
            self._suppress_workspace_update = False
            self.status.showMessage("Could not list plots due to kernel error.", 3500)
            return

        try:
            payload_text = self._figure_list_path.read_text(encoding="utf-8")
            payload = json.loads(payload_text)
        except (OSError, ValueError) as exc:
            self._suppress_workspace_update = False
            self.status.showMessage(f"Could not read plot list: {exc}", 4000)
            return

        if not payload.get("ok"):
            self._suppress_workspace_update = False
            reason = str(payload.get("reason", "No figure list found."))
            first_line = reason.strip().splitlines()[0] if reason.strip() else "No figures found."
            self.status.showMessage(first_line, 4000)
            return

        figures = payload.get("figures", [])
        if not figures:
            self._suppress_workspace_update = False
            self.status.showMessage("No Matplotlib figures found in Command Window.", 4000)
            return

        raw_labels: list[str] = []
        mapping: list[tuple[int | None, int | None, str | None]] = []
        for fig in figures:
            num = fig.get("num")
            var_name = fig.get("var")
            fig_title = str(fig.get("title") or "").strip()
            axes = fig.get("axes", [])
            if not isinstance(axes, list):
                axes = []
            if not axes:
                if fig_title:
                    label = fig_title
                elif var_name:
                    label = f"{var_name}"
                elif num is not None:
                    label = f"Figure {num}"
                else:
                    label = "Figure"
                raw_labels.append(label)
                mapping.append((int(num) if num is not None else None, None, var_name))
                continue
            for axis in axes:
                idx = axis.get("index")
                axis_title = str(axis.get("title") or "").strip()
                if axis_title:
                    label = axis_title
                elif fig_title:
                    label = fig_title
                elif var_name:
                    label = f"{var_name}"
                elif num is not None:
                    label = f"Figure {num}"
                else:
                    label = "Figure"
                raw_labels.append(label)
                mapping.append(
                    (int(num) if num is not None else None, int(idx) if idx is not None else None, var_name)
                )

        label_counts: dict[str, int] = {}
        for label in raw_labels:
            label_counts[label] = label_counts.get(label, 0) + 1
        choices: list[str] = []
        for raw_label, (fig_num, _axes_index, var_name) in zip(raw_labels, mapping):
            if label_counts.get(raw_label, 0) > 1:
                suffix = f"Figure {fig_num}" if fig_num is not None else (var_name or "Figure")
                choices.append(f"{raw_label} ({suffix})")
            else:
                choices.append(raw_label)

        if self._plot_picker is None:
            self._plot_picker = PlotPickerDialog(self)
        self._plot_picker.set_items(choices, mapping, self._on_plot_picker_selected)
        self._plot_picker.show()
        self._plot_picker.raise_()
        self._plot_picker.activateWindow()
        self._suppress_workspace_update = False

    def _on_plot_picker_selected(self, fig_num: int | None, axes_index: int | None, var_name: str | None) -> None:
        if self._figure_transfer_pending:
            self._queued_selection = (fig_num, axes_index, var_name)
            return
        self._selected_figure_num = fig_num
        self._selected_axes_index = axes_index
        self._selected_figure_var = var_name
        self._export_selected_console_figure(fig_num, var_name)

    def _export_selected_console_figure(self, fig_num: int | None, var_name: str | None) -> None:
        self._figure_transfer_pending = True
        self._suppress_workspace_update = True
        self._suppress_plot_refresh = True
        try:
            self._figure_transfer_path.unlink(missing_ok=True)
        except OSError:
            pass
        try:
            self._figure_transfer_status_path.unlink(missing_ok=True)
        except OSError:
            pass

        self.status.showMessage("Showing selected plot...", 1500)
        self.kernel_bridge.execute_code(
            self._build_console_figure_export_code(fig_num, var_name),
            on_finished=self._on_console_figure_export_finished,
            silent=True,
            store_history=False,
        )

    def _build_console_figure_export_code(self, fig_num: int | None, var_name: str | None) -> str:
        return plot_manager.build_console_figure_export_code(
            fig_num, var_name,
            self._figure_transfer_path,
            self._figure_transfer_status_path,
        )

    def _on_console_figure_export_finished(self, status: str) -> None:
        QTimer.singleShot(0, lambda: self._apply_console_figure_export(status))

    def _apply_console_figure_export(self, status: str) -> None:
        self._figure_transfer_pending = False
        self._suppress_workspace_update = False
        self._suppress_plot_refresh = False
        if status != "ok":
            self.status.showMessage("Figure transfer failed due to kernel error.", 3500)
            return

        try:
            payload_text = self._figure_transfer_status_path.read_text(encoding="utf-8")
            payload = json.loads(payload_text)
        except (OSError, ValueError):
            payload = {"ok": False, "reason": "No figure metadata found."}

        if not payload.get("ok"):
            if not self.figure_panel.has_preview():
                self.figure_panel.clear_figure()
            reason = str(payload.get("reason", "No figure found in Command Window."))
            first_line = reason.strip().splitlines()[0] if reason.strip() else "No figure found."
            self.status.showMessage(first_line, 4000)
            return

        try:
            with self._figure_transfer_path.open("rb") as handle:
                fig = pickle.load(handle)
        except Exception as exc:
            if not self.figure_panel.has_preview():
                self.figure_panel.clear_figure()
            self.status.showMessage(f"Could not load figure data: {exc}", 4000)
            return

        if not isinstance(fig, Figure):
            if not self.figure_panel.has_preview():
                self.figure_panel.clear_figure()
            self.status.showMessage("Captured object is not a Matplotlib figure.", 4000)
            return

        self.figure_panel.show_selected_figure(fig, self._selected_axes_index)
        self._selected_axes_index = None
        self._selected_figure_num = None
        self._selected_figure_var = None
        self._ensure_figure_panel_visible()
        self.status.showMessage("Plot updated in Figures panel.", 2000)

        if self._queued_selection is not None:
            next_fig, next_axes, next_var = self._queued_selection
            self._queued_selection = None
            self._selected_figure_num = next_fig
            self._selected_axes_index = next_axes
            self._selected_figure_var = next_var
            self._export_selected_console_figure(next_fig, next_var)

    def _ensure_figure_panel_visible(self) -> None:
        if not self._integrated_figures_enabled:
            return
        self.figure_panel.show()
        bottom_sizes = self._bottom_splitter.sizes()
        if len(bottom_sizes) == 2 and bottom_sizes[1] == 0:
            total = max(sum(bottom_sizes), 2)
            self._bottom_splitter.setSizes([int(total * 0.55), total - int(total * 0.55)])

        outer_sizes = self._outer_splitter.sizes()
        if len(outer_sizes) == 2 and outer_sizes[1] == 0:
            total = max(sum(outer_sizes), 2)
            self._outer_splitter.setSizes([int(total * 0.75), total - int(total * 0.75)])

    def _toggle_theme(self) -> None:
        self._current_theme = "light" if self._current_theme == "dark" else "dark"
        self.settings_manager.set("appearance/theme", self._current_theme)
        apply_stylesheet(QApplication.instance(), self._current_theme)
        self.ribbon.set_theme_icon(self._current_theme)
        self.ribbon.refresh_theme()
        self._sync_panel_themes()

    def _reset_layout(self) -> None:
        self._main_splitter.setSizes([250, 780, 250])
        if self._integrated_figures_enabled:
            self._bottom_splitter.setSizes([630, 650])
        else:
            self._bottom_splitter.setSizes([1280, 0])
        self._outer_splitter.setSizes([640, 160])

    def _on_ribbon_action(self, action_id: str) -> None:
        """Dispatch ribbon actions via a lookup table."""
        dispatch: dict[str, tuple] = {
            "clear_workspace":  (lambda: (self.workspace_manager.clear(), self.status.showMessage("Workspace cleared", 2000)),),
            "clear_commands":   (lambda: (self.console_panel.clear_console(), self.status.showMessage("Command window cleared", 2000)),),
            "layout_reset":     (lambda: (self._reset_layout(), self.status.showMessage("Layout reset", 2000)),),
            "show_workspace":   (lambda: (self.left_panel.show_workspace_section(), self.right_panel.tabs.setCurrentIndex(0)),),
            "show_analysis":    (lambda: self.right_panel.tabs.setCurrentIndex(1),),
            "show_plots":       (lambda: self.right_panel.tabs.setCurrentIndex(2),),
            "show_console":     (lambda: self.console_panel.setFocus(),),
            "show_files":       (lambda: self.left_panel.show_files_section(),),
            "show_blocks":      (lambda: self.left_panel.tabs.setCurrentIndex(1),),
            "show_snippets":    (lambda: self.left_panel.tabs.setCurrentIndex(2),),
            "run_time":         (lambda: (self._on_run(), self.status.showMessage("Running with timing (basic)", 2000)),),
            "run_section":      (lambda: self._on_run(),),
            "preferences":      (lambda: self._open_preferences(),),
            "find_files":       (lambda: self.left_panel.show_files_section(),),
            "about":            (lambda: self._open_about(),),
        }
        entry = dispatch.get(action_id)
        if entry:
            entry[0]()
        else:
            self.status.showMessage(f"{action_id.replace('_', ' ').title()} is not available yet", 3000)

    def _open_bode_wizard(self) -> None:
        from kronos.ui.dialogs.bode_wizard import BodeWizardDialog

        dlg = BodeWizardDialog(self)
        dlg.set_workspace_vars(self.workspace_manager.get_variables())
        dlg.set_kernel_client_getter(self.console_panel.get_kernel_client)
        dlg.set_message_router_getter(lambda: self.kernel_message_router)
        dlg.code_insert_requested.connect(self.center_panel.insert_snippet)
        dlg.exec()

    def _open_pid_tuner(self) -> None:
        from kronos.ui.dialogs.pid_tuner import PIDTunerDialog

        dlg = PIDTunerDialog(self)
        dlg.set_kernel_client_getter(self.console_panel.get_kernel_client)
        dlg.set_message_router_getter(lambda: self.kernel_message_router)
        dlg.code_insert_requested.connect(self.center_panel.insert_snippet)
        dlg.exec()

    def _open_step_response(self) -> None:
        from kronos.ui.dialogs.step_response_dialog import StepResponseDialog

        dlg = StepResponseDialog(self)
        dlg.exec()

    def _open_root_locus(self) -> None:
        from kronos.ui.dialogs.root_locus_dialog import RootLocusDialog

        dlg = RootLocusDialog(self)
        dlg.code_insert_requested.connect(self.center_panel.insert_snippet)
        dlg.exec()

    def _open_lqr_designer(self) -> None:
        from kronos.ui.dialogs.lqr_designer import LQRDesignerDialog

        dlg = LQRDesignerDialog(self)
        dlg.code_insert_requested.connect(self.center_panel.insert_snippet)
        dlg.exec()

    def _open_frequency_analyzer(self) -> None:
        from kronos.ui.dialogs.frequency_analyzer import FrequencyAnalyzerDialog

        dlg = FrequencyAnalyzerDialog(self)
        dlg.code_insert_requested.connect(self.center_panel.insert_snippet)
        dlg.exec()

    def _open_aeon_window(self) -> None:
        if self._aeon_window is None:
            self._aeon_window = AeonWindow(self)
            self._aeon_window.simulation_complete.connect(self._on_simulation_complete)
            self._aeon_window.closed.connect(self._on_aeon_closed)
            try:
                self._aeon_window.setWindowIcon(self.windowIcon())
            except Exception:
                pass
        self._aeon_window.show()
        self._aeon_window.raise_()
        self._aeon_window.activateWindow()

    def _on_aeon_closed(self) -> None:
        self._aeon_window = None

    def _open_preferences(self) -> None:
        from kronos.ui.dialogs.settings_dialog import SettingsDialog

        dlg = SettingsDialog(self.settings_manager, self)
        dlg.settings_changed.connect(self._on_settings_changed)
        dlg.exec()

    def _open_about(self) -> None:
        from kronos.ui.dialogs.about_dialog import AboutDialog

        dlg = AboutDialog(self)
        dlg.exec()

    def _on_settings_changed(self, changes: dict) -> None:
        if "appearance/theme" in changes:
            new_theme = changes["appearance/theme"]
            if new_theme != self._current_theme:
                self._current_theme = new_theme
                apply_stylesheet(QApplication.instance(), self._current_theme)
                self.ribbon.set_theme_icon(self._current_theme)
                self.ribbon.refresh_theme()
                self._sync_panel_themes()
        self.status.showMessage("Settings applied", 2000)

    def _rebuild_recent_menu(self) -> None:
        self._recent_menu.clear()
        recent = self.settings_manager.get_recent_files()
        if not recent:
            action = self._recent_menu.addAction("(No recent files)")
            action.setEnabled(False)
            return
        for filepath in recent:
            action = self._recent_menu.addAction(Path(filepath).name)
            action.setToolTip(filepath)
            action.triggered.connect(
                lambda _checked=False, p=filepath: self._on_open_file(p)
            )
        self._recent_menu.addSeparator()
        clear_action = self._recent_menu.addAction("Clear Recent Files")
        clear_action.triggered.connect(self._clear_recent_files)

    def _clear_recent_files(self) -> None:
        self.settings_manager.clear_recent_files()
        self._rebuild_recent_menu()

    def _on_simulation_complete(self, result: dict) -> None:
        is_dark = self._current_theme == "dark"
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

        for scope_id, signal in result["outputs"].items():
            fig = Figure(facecolor=fig_face)
            ax = fig.add_subplot(111)
            ax.plot(result["time"], signal, color=line_color, linewidth=1.5)
            ax.set_facecolor(ax_face)
            ax.tick_params(colors=tick_color)
            for spine in ax.spines.values():
                spine.set_color(spine_color)
            ax.grid(True, color=grid_color, linewidth=0.5)
            title = f"Scope: {scope_id}"
            ax.set_title(title, color=title_color, fontsize=10)
            self.right_panel.plots_tab.add_figure(fig, title)
            if self._integrated_figures_enabled:
                self.figure_panel.update_figure(fig)
            else:
                try:
                    fig.show()
                except Exception:
                    pass

        for var_name, value in result["variables"].items():
            self.console_panel.execute(f"{var_name} = {repr(value)}")

    def closeEvent(self, event) -> None:  # type: ignore[override]
        # Save settings.
        try:
            self.settings_manager.set("appearance/theme", self._current_theme)
            self.settings_manager.save_panel_sizes(
                self._main_splitter.sizes()
            )
        except Exception:
            pass
        # Close Aeon window if open.
        if self._aeon_window is not None:
            try:
                self._aeon_window.close()
            except Exception:
                pass
            self._aeon_window = None
        # Shutdown the kernel.
        try:
            self.console_panel.shutdown()
        except Exception:
            pass
        event.accept()
