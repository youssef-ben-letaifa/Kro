"""MATLAB-inspired ribbon with a modern three-row layout."""

from __future__ import annotations

import os

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from kronos.ui.theme.design_tokens import get_colors
from kronos.ui.theme.fluent_icons import icon_for

_UNAVAILABLE_ACTION_IDS = {
    "import_data",
    "new_variable",
    "analyze_code",
    "add_ons",
    "plot_line",
    "plot_scatter",
    "plot_bar",
    "plot_hist",
    "plot_surf",
    "plot_mesh",
    "plot_contour",
    "plot_box",
    "plot_errorbar",
    "plot_matrix",
    "plot_polar",
    "plot_compass",
    "app_signal",
    "app_stats",
    "app_ml",
    "app_deep",
    "publish",
    "go_to",
    "find",
    "format",
    "run_selection",
    "bp_toggle",
    "bp_clear",
    "profiler",
    "live_insert_text",
    "live_insert_eq",
    "live_insert_ctrl",
    "live_heading",
    "live_list",
    "live_view_inline",
    "live_hide_code",
    "debug_step",
    "debug_step_in",
    "debug_continue",
    "debug_quit",
    "bp_conditional",
    "bp_error",
    "debug_stack",
}


class _RibbonGroup(QFrame):
    """Ribbon group container with section label."""

    def __init__(self, title: str) -> None:
        super().__init__()
        self.setObjectName("ribbon_group")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 4)
        layout.setSpacing(2)

        self.grid = QGridLayout()
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(4)
        self.grid.setVerticalSpacing(4)
        layout.addLayout(self.grid, 1)
        self._has_primary = False
        self._secondary_index = 0
        self._max_col = 0

        label = QLabel(title)
        label.setObjectName("ribbon_group_title")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

    @staticmethod
    def _compactify(button: QToolButton) -> None:
        button.setObjectName("ribbon_action_compact")
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setIconSize(QSize(16, 16))
        button.setMinimumSize(116, 28)
        button.setMaximumHeight(28)

    def add_button(self, button: QToolButton) -> None:
        if button.objectName() == "ribbon_action_primary" and not self._has_primary:
            self.grid.addWidget(button, 0, 0, 2, 1)
            self._has_primary = True
            self._max_col = max(self._max_col, 0)
            return

        if button.objectName() == "ribbon_action_primary":
            self._compactify(button)

        start_col = 1 if self._has_primary else 0
        row = self._secondary_index % 2
        col = start_col + (self._secondary_index // 2)
        self.grid.addWidget(button, row, col)
        self._secondary_index += 1
        self._max_col = max(self._max_col, col)

    def finalize(self) -> None:
        self.grid.setColumnStretch(self._max_col + 1, 1)


class MatlabRibbon(QWidget):
    """Three-row ribbon with dedicated command tabs."""

    run_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    restart_requested = pyqtSignal()
    new_requested = pyqtSignal()
    open_requested = pyqtSignal()
    save_requested = pyqtSignal()
    bode_requested = pyqtSignal()
    step_requested = pyqtSignal()
    rootlocus_requested = pyqtSignal()
    pid_requested = pyqtSignal()
    lqr_requested = pyqtSignal()
    aeon_requested = pyqtSignal()
    theme_toggle_requested = pyqtSignal()
    action_requested = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ribbon")
        self.setMinimumHeight(216)
        self.setMaximumHeight(272)
        self._control_buttons: list[QToolButton] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_quick_row())

        self.tabs = QTabWidget()
        self.tabs.setObjectName("ribbon_tabs")
        self.tabs.setDocumentMode(True)
        if self.tabs.tabBar() is not None:
            self.tabs.tabBar().setExpanding(False)

        self.tabs.addTab(self._build_home_tab(), "HOME")
        self.tabs.addTab(self._build_plots_tab(), "PLOTS")
        self.tabs.addTab(self._build_apps_tab(), "APPS")
        self.tabs.addTab(self._build_editor_tab(), "EDITOR")
        self.tabs.addTab(self._build_live_editor_tab(), "LIVE EDITOR")
        self.tabs.addTab(self._build_debug_tab(), "DEBUG")
        self.tabs.addTab(self._build_quantum_tab(), "QUANTUM")
        self.tabs.addTab(self._build_symbolic_tab(), "SYMBOLIC")
        self._disable_unavailable_actions()

        root.addWidget(self.tabs, 1)
        root.addWidget(self._build_path_row())
        self._disable_unavailable_actions()

    def _build_quick_row(self) -> QWidget:
        row = QWidget()
        row.setObjectName("ribbon_quick_row")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        brand = QLabel("KRONOS")
        brand.setObjectName("ribbon_brand")
        layout.addWidget(brand)
        layout.addSpacing(4)

        layout.addWidget(
            self._quick_button("New", "New script", "new", signal=self.new_requested)
        )
        layout.addWidget(
            self._quick_button("Open", "Open file", "open", signal=self.open_requested)
        )
        layout.addWidget(
            self._quick_button("Save", "Save file", "save", signal=self.save_requested)
        )
        layout.addWidget(
            self._quick_button("Undo", "Undo", "undo", action_id="undo")
        )
        layout.addWidget(
            self._quick_button("Redo", "Redo", "redo", action_id="redo")
        )

        layout.addStretch(1)

        self._help_button = self._quick_button(
            "Help", "About Kronos", "help", action_id="about"
        )
        layout.addWidget(self._help_button)

        self._theme_button = self._quick_button(
            "Theme",
            "Catppuccin Mocha (dark-only theme)",
            "theme_dark",
            signal=self.theme_toggle_requested,
        )
        self._theme_button.setEnabled(False)
        layout.addWidget(self._theme_button)
        return row

    def _build_path_row(self) -> QWidget:
        row = QWidget()
        row.setObjectName("ribbon_path_row")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        for name, tip in (
            ("back", "Back"),
            ("forward", "Forward"),
            ("up", "Up"),
            ("folder_up", "Parent"),
            ("home", "Home"),
        ):
            layout.addWidget(self._path_button(name, tip))

        label = QLabel("Path:")
        label.setObjectName("ribbon_breadcrumb")
        layout.addWidget(label)

        self._path_bar = QLineEdit(os.getcwd())
        self._path_bar.setReadOnly(True)
        self._path_bar.setObjectName("ribbon_path")
        layout.addWidget(self._path_bar, 1)
        return row

    def _build_home_tab(self) -> QWidget:
        panel = self._panel()
        row = panel.layout()

        files = _RibbonGroup("FILE")
        files.add_button(self._action_button("New", "New script", "new", signal=self.new_requested))
        files.add_button(self._action_button("Open", "Open file", "open", signal=self.open_requested))
        files.add_button(self._action_button("Save", "Save file", "save", signal=self.save_requested))
        files.add_button(self._action_button("Find Files", "Find files", "search", action_id="find_files"))
        files.add_button(self._action_button("Import", "Import data", "open", action_id="import_data"))
        files.finalize()
        row.addWidget(files)

        variable = _RibbonGroup("VARIABLE")
        variable.add_button(self._action_button("New Var", "Create variable", "new", action_id="new_variable"))
        variable.add_button(
            self._action_button("Workspace", "Show workspace", "workspace", action_id="show_workspace")
        )
        variable.add_button(
            self._action_button("Clear", "Clear workspace", "database", action_id="clear_workspace")
        )
        variable.finalize()
        row.addWidget(variable)

        code = _RibbonGroup("CODE")
        code.add_button(self._action_button("Analyze", "Analyze code", "analysis", action_id="analyze_code"))
        code.add_button(
            self._action_button("Run+Time", "Run with timing", "run_time", action_id="run_time")
        )
        code.add_button(
            self._action_button("Clear Cmd", "Clear command window", "clear", action_id="clear_commands")
        )
        code.finalize()
        row.addWidget(code)

        sim = _RibbonGroup("AEON")
        sim.add_button(
            self._action_button("Aeon", "Open Aeon window", "aeon", signal=self.aeon_requested)
        )
        sim.finalize()
        row.addWidget(sim)

        environment = _RibbonGroup("ENVIRONMENT")
        environment.add_button(
            self._action_button("ToolBox", "Toolbox browser", "toolbox", action_id="toolboxes")
        )
        environment.add_button(
            self._action_button("Prefs", "Preferences", "settings", action_id="preferences")
        )
        environment.add_button(
            self._action_button("Add-Ons", "Add-ons", "apps", action_id="add_ons")
        )
        environment.add_button(
            self._action_button("Help", "Documentation", "help", action_id="about")
        )
        environment.finalize()
        row.addWidget(environment)

        layout_group = _RibbonGroup("LAYOUT")
        layout_group.add_button(
            self._action_button("Reset", "Reset layout", "layout", action_id="layout_reset")
        )
        layout_group.finalize()
        row.addWidget(layout_group)

        row.addStretch(1)
        return panel

    def _build_plots_tab(self) -> QWidget:
        panel = self._panel()
        row = panel.layout()

        plot2d = _RibbonGroup("2D")
        plot2d.add_button(self._action_button("Line", "Line plot", "plot", action_id="plot_line"))
        plot2d.add_button(self._action_button("Scatter", "Scatter plot", "plot", action_id="plot_scatter"))
        plot2d.add_button(self._action_button("Bar", "Bar plot", "plot", action_id="plot_bar"))
        plot2d.add_button(self._action_button("Hist", "Histogram", "analysis", action_id="plot_hist"))
        plot2d.finalize()
        row.addWidget(plot2d)

        plot3d = _RibbonGroup("SURFACE/3D")
        plot3d.add_button(self._action_button("Surf", "Surface plot", "analysis", action_id="plot_surf"))
        plot3d.add_button(self._action_button("Mesh", "Mesh plot", "analysis", action_id="plot_mesh"))
        plot3d.add_button(self._action_button("Contour", "Contour plot", "analysis", action_id="plot_contour"))
        plot3d.finalize()
        row.addWidget(plot3d)

        stats = _RibbonGroup("STATISTICS")
        stats.add_button(self._action_button("Box", "Box plot", "analysis", action_id="plot_box"))
        stats.add_button(self._action_button("Error", "Error bars", "analysis", action_id="plot_errorbar"))
        stats.add_button(self._action_button("Matrix", "Plot matrix", "analysis", action_id="plot_matrix"))
        stats.finalize()
        row.addWidget(stats)

        polar = _RibbonGroup("POLAR")
        polar.add_button(self._action_button("Polar", "Polar plot", "plot", action_id="plot_polar"))
        polar.add_button(self._action_button("Compass", "Compass plot", "plot", action_id="plot_compass"))
        polar.finalize()
        row.addWidget(polar)

        row.addStretch(1)
        return panel

    def _build_apps_tab(self) -> QWidget:
        panel = self._panel()
        row = panel.layout()

        control = _RibbonGroup("CONTROL")
        control.add_button(self._control_button("Bode", "Bode plot wizard", "bode", self.bode_requested))
        control.add_button(self._control_button("PID", "PID tuner", "pid", self.pid_requested))
        control.add_button(self._control_button("LQR", "LQR designer", "lqr", self.lqr_requested))
        control.finalize()
        row.addWidget(control)

        signal = _RibbonGroup("SIGNAL/STATS")
        signal.add_button(self._action_button("Signal", "Signal analyzer", "analysis", action_id="app_signal"))
        signal.add_button(self._action_button("Stats", "Statistics app", "analysis", action_id="app_stats"))
        signal.finalize()
        row.addWidget(signal)

        ml = _RibbonGroup("ML/AI")
        ml.add_button(self._action_button("ML", "Machine learning app", "analysis", action_id="app_ml"))
        ml.add_button(self._action_button("Deep", "Deep network designer", "apps", action_id="app_deep"))
        ml.finalize()
        row.addWidget(ml)

        aeon = _RibbonGroup("AEON")
        aeon.add_button(
            self._action_button("Aeon", "Open Aeon", "aeon", signal=self.aeon_requested)
        )
        aeon.add_button(
            self._action_button("Blocks", "Show block browser", "blocks", action_id="show_blocks")
        )
        aeon.finalize()
        row.addWidget(aeon)

        row.addStretch(1)
        return panel

    def _build_editor_tab(self) -> QWidget:
        panel = self._panel()
        row = panel.layout()

        file_group = _RibbonGroup("FILE")
        file_group.add_button(self._action_button("Open", "Open file", "open", signal=self.open_requested))
        file_group.add_button(self._action_button("Save", "Save file", "save", signal=self.save_requested))
        file_group.add_button(self._action_button("Publish", "Publish document", "print", action_id="publish"))
        file_group.finalize()
        row.addWidget(file_group)

        navigate = _RibbonGroup("NAVIGATE")
        navigate.add_button(self._action_button("Go To", "Go to line/symbol", "search", action_id="go_to"))
        navigate.add_button(self._action_button("Find", "Find/replace", "search", action_id="find"))
        navigate.finalize()
        row.addWidget(navigate)

        edit_group = _RibbonGroup("EDIT")
        edit_group.add_button(self._action_button("Undo", "Undo", "undo", action_id="undo"))
        edit_group.add_button(self._action_button("Redo", "Redo", "redo", action_id="redo"))
        edit_group.add_button(self._action_button("Format", "Format code", "settings", action_id="format"))
        edit_group.finalize()
        row.addWidget(edit_group)

        run_group = _RibbonGroup("RUN")
        run_group.add_button(self._action_button("Run", "Run script", "run", signal=self.run_requested))
        run_group.add_button(self._action_button("Section", "Run section", "run_section", action_id="run_section"))
        run_group.add_button(self._action_button("Selection", "Run selection", "run_time", action_id="run_selection"))
        run_group.finalize()
        row.addWidget(run_group)

        breakpoints = _RibbonGroup("BREAKPOINTS")
        breakpoints.add_button(self._action_button("Toggle", "Toggle breakpoint", "stop", action_id="bp_toggle"))
        breakpoints.add_button(self._action_button("Clear", "Clear breakpoints", "clear", action_id="bp_clear"))
        breakpoints.finalize()
        row.addWidget(breakpoints)

        analyze = _RibbonGroup("ANALYZE")
        analyze.add_button(self._action_button("Code", "Code analyzer", "analysis", action_id="analyze_code"))
        analyze.add_button(self._action_button("Profiler", "Run profiler", "analysis", action_id="profiler"))
        analyze.finalize()
        row.addWidget(analyze)

        row.addStretch(1)
        return panel

    def _build_live_editor_tab(self) -> QWidget:
        panel = self._panel()
        row = panel.layout()

        insert = _RibbonGroup("INSERT")
        insert.add_button(self._action_button("Text", "Insert text", "files", action_id="live_insert_text"))
        insert.add_button(self._action_button("Equation", "Insert equation", "math_formula", action_id="live_insert_eq"))
        insert.add_button(self._action_button("Control", "Insert control", "apps", action_id="live_insert_ctrl"))
        insert.finalize()
        row.addWidget(insert)

        text_group = _RibbonGroup("TEXT FORMAT")
        text_group.add_button(self._action_button("Heading", "Heading style", "files", action_id="live_heading"))
        text_group.add_button(self._action_button("List", "Bulleted list", "files", action_id="live_list"))
        text_group.finalize()
        row.addWidget(text_group)

        view_group = _RibbonGroup("VIEW")
        view_group.add_button(self._action_button("Inline", "Inline output", "layout", action_id="live_view_inline"))
        view_group.add_button(self._action_button("Hide Code", "Hide code", "layout", action_id="live_hide_code"))
        view_group.finalize()
        row.addWidget(view_group)

        run_group = _RibbonGroup("RUN")
        run_group.add_button(
            self._action_button("Run", "Run script", "run", signal=self.run_requested)
        )
        run_group.add_button(
            self._action_button("Run+Time", "Run with timing", "run_time", action_id="run_time")
        )
        run_group.add_button(
            self._action_button("Clear", "Clear command window", "clear", action_id="clear_commands")
        )
        run_group.finalize()
        row.addWidget(run_group)

        row.addStretch(1)
        return panel

    def _build_debug_tab(self) -> QWidget:
        panel = self._panel()
        row = panel.layout()

        step_controls = _RibbonGroup("STEP CONTROLS")
        step_controls.add_button(
            self._action_button("Step", "Step over", "run_section", action_id="debug_step")
        )
        step_controls.add_button(
            self._action_button("Step In", "Step in", "run", action_id="debug_step_in")
        )
        step_controls.add_button(
            self._action_button("Continue", "Continue execution", "restart", action_id="debug_continue")
        )
        step_controls.add_button(
            self._action_button("Quit", "Quit debug", "stop", action_id="debug_quit")
        )
        step_controls.finalize()
        row.addWidget(step_controls)

        breakpoints = _RibbonGroup("BREAKPOINTS")
        breakpoints.add_button(
            self._action_button("Toggle", "Toggle breakpoint", "stop", action_id="bp_toggle")
        )
        breakpoints.add_button(
            self._action_button("Conditional", "Conditional breakpoint", "settings", action_id="bp_conditional")
        )
        breakpoints.add_button(
            self._action_button("Error BP", "Break on errors", "analysis", action_id="bp_error")
        )
        breakpoints.finalize()
        row.addWidget(breakpoints)

        stack = _RibbonGroup("STACK")
        stack.add_button(
            self._action_button("Call Stack", "Show call stack", "files", action_id="debug_stack")
        )
        stack.finalize()
        row.addWidget(stack)

        row.addStretch(1)
        return panel

    def _build_quantum_tab(self) -> QWidget:
        panel = self._panel()
        row = panel.layout()
        group = _RibbonGroup("QUANTUM")
        button = self._action_button("Coming Soon", "Quantum tools are coming soon", "apps")
        self._mark_coming_soon(button)
        group.add_button(button)
        group.finalize()
        row.addWidget(group)
        row.addStretch(1)
        return panel

    def _build_symbolic_tab(self) -> QWidget:
        panel = self._panel()
        row = panel.layout()
        group = _RibbonGroup("SYMBOLIC")
        button = self._action_button("Coming Soon", "Symbolic tools are coming soon", "math_formula")
        self._mark_coming_soon(button)
        group.add_button(button)
        group.finalize()
        row.addWidget(group)
        row.addStretch(1)
        return panel

    def _panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("ribbon_panel")
        row = QHBoxLayout(panel)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(6)
        return panel

    def _quick_button(
        self,
        text: str,
        tooltip: str,
        icon_name: str,
        signal: pyqtSignal | None = None,
        action_id: str | None = None,
    ) -> QToolButton:
        button = QToolButton()
        button.setObjectName("ribbon_quick_button")
        button.setProperty("icon_name", icon_name)
        button.setProperty("action_id", action_id or "")
        button.setToolTip(tooltip)
        button.setIcon(self._build_icon(icon_name, size=22))
        button.setIconSize(QSize(22, 22))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        button.setFixedSize(34, 34)
        if signal is not None:
            button.clicked.connect(signal.emit)
        elif action_id is not None:
            button.clicked.connect(lambda _checked=False, aid=action_id: self.action_requested.emit(aid))
        return button

    def _path_button(self, icon_name: str, tooltip: str) -> QToolButton:
        button = QToolButton()
        button.setObjectName("ribbon_path_button")
        button.setToolTip(tooltip)
        button.setIcon(self._build_icon(icon_name, size=16))
        button.setIconSize(QSize(16, 16))
        button.setFixedSize(24, 24)
        self._mark_coming_soon(button)
        return button

    def _action_button(
        self,
        text: str,
        tooltip: str,
        icon_name: str,
        signal: pyqtSignal | None = None,
        action_id: str | None = None,
        *,
        primary: bool = True,
    ) -> QToolButton:
        button = QToolButton()
        button.setObjectName("ribbon_action_primary" if primary else "ribbon_action_compact")
        button.setProperty("icon_name", icon_name)
        button.setProperty("action_id", action_id or "")
        button.setText(text)
        button.setToolTip(tooltip)
        icon_size = 22 if primary else 16
        button.setIcon(self._build_icon(icon_name, size=icon_size))
        button.setIconSize(QSize(icon_size, icon_size))
        button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextUnderIcon if primary else Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        button.setMinimumSize(52 if primary else 116, 56 if primary else 28)
        if signal is not None:
            button.clicked.connect(signal.emit)
        elif action_id is not None:
            button.clicked.connect(lambda _checked=False, aid=action_id: self.action_requested.emit(aid))
        return button

    @staticmethod
    def _mark_coming_soon(button: QToolButton) -> None:
        tooltip = button.toolTip().strip()
        if "coming soon" not in tooltip.lower():
            tooltip = f"{tooltip} (Coming soon)"
        button.setToolTip(tooltip)
        button.setEnabled(False)

    def _disable_unavailable_actions(self) -> None:
        for button in self.findChildren(QToolButton):
            action_id = button.property("action_id")
            if isinstance(action_id, str) and action_id in _UNAVAILABLE_ACTION_IDS:
                self._mark_coming_soon(button)

    def _control_button(
        self, text: str, tooltip: str, icon_name: str, signal: pyqtSignal
    ) -> QToolButton:
        button = self._action_button(text, tooltip, icon_name, signal=signal, primary=True)
        self._control_buttons.append(button)
        return button

    def _build_icon(self, name: str, size: int = 24) -> QIcon:
        current_theme = getattr(self.window(), "_current_theme", "dark")
        colors = get_colors(current_theme)
        base_color = colors["text_primary"]
        color_overrides = {
            "run": colors["success"],
            "stop": colors["error"],
            "restart": colors["warning"],
            "bode": colors["accent_teal"],
            "step": colors["accent_teal"],
            "root": colors["accent_teal"],
            "pid": colors["accent_lime"],
            "lqr": colors["accent_lime"],
            "plot": colors["accent_teal"],
            "analysis": colors["accent_violet"],
            "workspace": colors["accent_amber"],
            "apps": colors["accent_violet"],
            "aeon": colors["accent_amber"],
            "database": colors["accent_amber"],
            "new": colors["accent"],
            "open": colors["accent_amber"],
            "save": colors["accent_teal"],
            "search": colors["accent_violet"],
            "settings": colors["accent_violet"],
            "help": colors["accent_rose"],
            "undo": colors["accent_amber"],
            "redo": colors["accent_amber"],
            "clear": colors["accent_rose"],
            "run_time": colors["accent_teal"],
            "run_section": colors["accent_teal"],
            "theme_dark": colors["accent"],
            "theme_light": colors["warning"],
        }
        color = color_overrides.get(name, base_color)
        return icon_for(name, size=size, color=color)

    @staticmethod
    def _divider() -> QFrame:
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setObjectName("ribbon_divider")
        return divider

    def set_control_tools_enabled(self, enabled: bool) -> None:
        for button in self._control_buttons:
            button.setEnabled(enabled)

    def set_theme_icon(self, theme: str) -> None:
        del theme
        icon_name = "theme_dark"
        self._theme_button.setIcon(self._build_icon(icon_name, size=22))
        self._theme_button.setProperty("icon_name", icon_name)

    def refresh_theme(self) -> None:
        for btn in self.findChildren(QToolButton):
            name = btn.property("icon_name")
            if name:
                if btn.objectName() == "ribbon_quick_button":
                    size = 22
                elif btn.objectName() == "ribbon_path_button":
                    size = 16
                elif btn.objectName() == "ribbon_action_primary":
                    size = 30
                else:
                    size = 16
                btn.setIcon(self._build_icon(name, size=size))

    def set_breadcrumb(self, path_text: str) -> None:
        self._path_bar.setText(path_text)
