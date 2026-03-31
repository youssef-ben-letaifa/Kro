"""Embedded IPython console panel."""

from __future__ import annotations

import os
import re
from pathlib import Path
from html import escape

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


class ConsolePanel(QWidget):
    """Embedded IPython console panel."""

    transfer_figure_requested = pyqtSignal()
    problem_open_requested = pyqtSignal(str, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._is_dark_theme = True
        self._setup_ui()
        self._start_kernel()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        label = QLabel("Command Window")
        label.setObjectName("panel_header")
        header_layout.addWidget(label)
        header_layout.addStretch(1)

        self._transfer_button = QPushButton("Show Plot")
        self._transfer_button.setToolTip(
            "Choose a plot from Command Window and show it in Figures."
        )
        self._transfer_button.clicked.connect(self.transfer_figure_requested.emit)
        header_layout.addWidget(self._transfer_button)
        self._transfer_button.setVisible(False)

        layout.addWidget(header)
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)

        self._console_tab = QWidget()
        self._console_tab_layout = QVBoxLayout(self._console_tab)
        self._console_tab_layout.setContentsMargins(0, 0, 0, 0)
        self._widget_placeholder = QWidget()
        self._console_tab_layout.addWidget(self._widget_placeholder)

        self._output_tab = QTextEdit()
        self._output_tab.setReadOnly(True)
        self._output_tab.setObjectName("console_output")

        self._problems_tab = QTreeWidget()
        self._problems_tab.setHeaderLabels(["File", "Line", "Message"])
        self._problems_tab.itemActivated.connect(self._on_problem_activated)

        self._terminal_tab = QPlainTextEdit()
        self._terminal_tab.setReadOnly(True)
        self._terminal_tab.setPlainText("Integrated terminal is coming soon.")

        self._tabs.addTab(self._console_tab, "Console")
        self._tabs.addTab(self._output_tab, "Output")
        self._tabs.addTab(self._problems_tab, "Problems")
        self._tabs.addTab(self._terminal_tab, "Terminal")
        layout.addWidget(self._tabs, 1)

    def _start_kernel(self) -> None:
        try:
            self._prepare_runtime_dirs()
            from qtconsole.rich_jupyter_widget import RichJupyterWidget
            from qtconsole.manager import QtKernelManager

            km = QtKernelManager(kernel_name="python3")
            km.start_kernel()
            
            kc = km.client()
            kc.start_channels()

            self._console = RichJupyterWidget()
            self._console.kernel_manager = km
            self._console.kernel_client = kc
            self.set_theme(True)
            # Use external Matplotlib windows (Matlab-style) instead of inline/embedded.
            try:
                kc.execute("%matplotlib qt", silent=True, store_history=False)
            except Exception:
                pass
            # Install MATLAB-like plot tools (data cursor + point edit) on new figures.
            try:
                tools_code = r'''
import matplotlib.pyplot as plt
try:
    import mpl_toolkits.mplot3d  # noqa: F401
except Exception:
    pass

_KRONOS_THEMES = {
    "dark": {
        "fig": "#1e1e2e",
        "ax": "#1e1e2e",
        "text": "#cdd6f4",
        "tick": "#a6adc8",
        "spine": "#45475a",
        "grid": "#313244",
        "legend": "#cdd6f4",
        "accent": "#89b4fa",
    },
    "light": {
        "fig": "#ffffff",
        "ax": "#ffffff",
        "text": "#334155",
        "tick": "#475569",
        "spine": "#cbd5e1",
        "grid": "#e2e8f0",
        "legend": "#0f172a",
        "accent": "#89b4fa",
    },
}
_KRONOS_THEME_NAME = "dark"
_KRONOS_THEME = _KRONOS_THEMES[_KRONOS_THEME_NAME]

def __kronos_update_rcparams(theme):
    try:
        plt.rcParams.update({
            "figure.facecolor": theme["fig"],
            "axes.facecolor": theme["ax"],
            "savefig.facecolor": theme["fig"],
            "axes.edgecolor": theme["spine"],
            "axes.labelcolor": theme["text"],
            "xtick.color": theme["tick"],
            "ytick.color": theme["tick"],
            "grid.color": theme["grid"],
            "text.color": theme["text"],
            "legend.facecolor": theme["ax"],
            "legend.edgecolor": theme["spine"],
        })
    except Exception:
        pass

def __kronos_apply_theme(fig):
    theme = _KRONOS_THEME
    fig.set_facecolor(theme["fig"])
    for ax in fig.axes:
        ax.set_facecolor(theme["ax"])
        ax.title.set_color(theme["text"])
        ax.xaxis.label.set_color(theme["text"])
        ax.yaxis.label.set_color(theme["text"])
        ax.tick_params(colors=theme["tick"])
        for spine in ax.spines.values():
            spine.set_color(theme["spine"])
        if hasattr(ax, "zaxis"):
            ax.zaxis.label.set_color(theme["text"])
            ax.zaxis.set_tick_params(colors=theme["tick"])
            try:
                ax.xaxis.pane.set_facecolor(theme["ax"])
                ax.yaxis.pane.set_facecolor(theme["ax"])
                ax.zaxis.pane.set_facecolor(theme["ax"])
                ax.xaxis.pane.set_edgecolor(theme["spine"])
                ax.yaxis.pane.set_edgecolor(theme["spine"])
                ax.zaxis.pane.set_edgecolor(theme["spine"])
            except Exception:
                pass
        has_grid = any(
            gridline.get_visible()
            for gridline in (ax.get_xgridlines() + ax.get_ygridlines())
        )
        if has_grid:
            ax.grid(True, color=theme["grid"], linewidth=0.5)
        legend = ax.get_legend()
        if legend is not None:
            legend.get_frame().set_facecolor(theme["ax"])
            legend.get_frame().set_edgecolor(theme["spine"])
            for text in legend.get_texts():
                text.set_color(theme["legend"])

def __kronos_set_theme(theme_name="dark"):
    global _KRONOS_THEME_NAME, _KRONOS_THEME
    if theme_name not in _KRONOS_THEMES:
        theme_name = "dark"
    _KRONOS_THEME_NAME = theme_name
    _KRONOS_THEME = _KRONOS_THEMES[theme_name]
    __kronos_update_rcparams(_KRONOS_THEME)
    for num in plt.get_fignums():
        try:
            fig = plt.figure(num)
            __kronos_apply_theme(fig)
            fig.canvas.draw_idle()
        except Exception:
            pass

def __kronos_convert_axes_to_3d(fig):
    changed = False
    for ax in list(fig.axes):
        if hasattr(ax, "get_zlim"):
            continue
        lines = []
        for line in ax.lines:
            try:
                xdata = line.get_xdata(orig=False)
                ydata = line.get_ydata(orig=False)
            except Exception:
                continue
            lines.append({
                "x": xdata,
                "y": ydata,
                "color": line.get_color(),
                "linewidth": line.get_linewidth(),
                "linestyle": line.get_linestyle(),
                "marker": line.get_marker(),
                "markersize": line.get_markersize(),
                "alpha": line.get_alpha(),
                "label": line.get_label(),
            })
        if not lines:
            continue
        pos = ax.get_position()
        title = ax.get_title()
        xlabel = ax.get_xlabel()
        ylabel = ax.get_ylabel()
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        has_grid = any(
            gridline.get_visible()
            for gridline in (ax.get_xgridlines() + ax.get_ygridlines())
        )
        fig.delaxes(ax)
        ax3 = fig.add_axes(pos, projection="3d")
        for line in lines:
            ax3.plot(
                line["x"],
                line["y"],
                zs=0,
                zdir="z",
                color=line["color"],
                linewidth=line["linewidth"],
                linestyle=line["linestyle"],
                marker=line["marker"],
                markersize=line["markersize"],
                alpha=line["alpha"],
                label=line["label"],
            )
        ax3.set_title(title)
        ax3.set_xlabel(xlabel)
        ax3.set_ylabel(ylabel)
        ax3.set_xlim(xlim)
        ax3.set_ylim(ylim)
        if has_grid:
            ax3.grid(True)
        ax3.set_zlim(-1.0, 1.0)
        if any(
            line["label"] and not str(line["label"]).startswith("_")
            for line in lines
        ):
            ax3.legend()
        try:
            ax3.view_init(elev=25, azim=-60)
        except Exception:
            pass
        try:
            ax3.mouse_init()
        except Exception:
            pass
        changed = True
    if changed:
        __kronos_apply_theme(fig)
        fig.canvas.draw_idle()
    return changed

def __kronos_set_cursor(fig, cursor_name):
    try:
        from PyQt6.QtCore import Qt as __Qt
    except Exception:
        return
    try:
        cursor = getattr(__Qt.CursorShape, cursor_name, None)
        if cursor is None:
            return
        fig.canvas.setCursor(cursor)
    except Exception:
        pass

def __kronos_find_nearest(event, ax, max_dist=10):
    if event.x is None or event.y is None:
        return None
    ex, ey = event.x, event.y
    best = None
    best_dist = max_dist
    for line in ax.lines:
        xdata = line.get_xdata(orig=False)
        ydata = line.get_ydata(orig=False)
        if xdata is None or ydata is None:
            continue
        if len(xdata) == 0:
            continue
        try:
            pts = ax.transData.transform(list(zip(xdata, ydata)))
        except Exception:
            continue
        for idx, (px, py) in enumerate(pts):
            dist = ((px - ex) ** 2 + (py - ey) ** 2) ** 0.5
            if dist < best_dist:
                best_dist = dist
                best = (line, idx, xdata[idx], ydata[idx], ax)
    return best

def __kronos_set_point(line, idx, x, y):
    xdata = list(line.get_xdata(orig=False))
    ydata = list(line.get_ydata(orig=False))
    if idx < 0 or idx >= len(xdata):
        return
    xdata[idx] = x
    ydata[idx] = y
    line.set_data(xdata, ydata)

def __kronos_install_tools(fig):
    if getattr(fig, "_kronos_tools_installed", False):
        return
    mgr = getattr(fig.canvas, "manager", None)
    toolbar = getattr(mgr, "toolbar", None) if mgr else None
    if toolbar is None:
        return
    state = {"data_cursor": False, "edit_points": False, "drag": None, "ann": None}

    __kronos_apply_theme(fig)

    rotate_action = toolbar.addAction("3D Rotate")
    rotate_action.setCheckable(True)
    rotate_action.setToolTip("Convert 2D plots to 3D and rotate with mouse")

    data_action = toolbar.addAction("Data Cursor")
    data_action.setCheckable(True)
    data_action.setToolTip("Show data values on click")

    edit_action = toolbar.addAction("Edit Points")
    edit_action.setCheckable(True)
    edit_action.setToolTip("Drag points to edit line data")

    def toggle_data(checked):
        if checked:
            edit_action.setChecked(False)
            state["edit_points"] = False
        state["data_cursor"] = checked

    def toggle_edit(checked):
        if checked:
            data_action.setChecked(False)
            state["data_cursor"] = False
        state["edit_points"] = checked

    data_action.toggled.connect(toggle_data)
    edit_action.toggled.connect(toggle_edit)

    def toggle_rotate(checked):
        if checked:
            __kronos_convert_axes_to_3d(fig)
            __kronos_set_cursor(fig, "OpenHandCursor")
        else:
            __kronos_set_cursor(fig, "ArrowCursor")

    rotate_action.toggled.connect(toggle_rotate)

    def on_click(event):
        if not state["data_cursor"]:
            return
        if event.inaxes is None:
            return
        nearest = __kronos_find_nearest(event, event.inaxes)
        if nearest is None:
            return
        _line, _idx, x, y, ax = nearest
        text = f"x={x:.4g}\\ny={y:.4g}"
        ann = state.get("ann")
        if ann is None or ann.axes is not ax:
            ann = ax.annotate(
                text,
                xy=(x, y),
                xytext=(10, 10),
                textcoords="offset points",
                bbox=dict(
                    boxstyle="round",
                    fc=_KRONOS_THEME["spine"],
                    ec=_KRONOS_THEME["accent"],
                    alpha=0.85,
                ),
                color=_KRONOS_THEME["legend"],
            )
            state["ann"] = ann
        else:
            ann.xy = (x, y)
            ann.set_text(text)
        fig.canvas.draw_idle()

    def on_press(event):
        if not state["edit_points"]:
            return
        if event.inaxes is None:
            return
        nearest = __kronos_find_nearest(event, event.inaxes)
        if nearest is None:
            return
        line, idx, _x, _y, ax = nearest
        state["drag"] = (line, idx, ax)

    def on_motion(event):
        if not state["edit_points"]:
            return
        if state["drag"] is None:
            return
        if event.inaxes is None or event.xdata is None or event.ydata is None:
            return
        line, idx, ax = state["drag"]
        if event.inaxes is not ax:
            return
        __kronos_set_point(line, idx, event.xdata, event.ydata)
        try:
            ax.relim()
            ax.autoscale_view()
        except Exception:
            pass
        fig.canvas.draw_idle()

    def on_release(_event):
        state["drag"] = None

    fig.canvas.mpl_connect("button_press_event", on_press)
    fig.canvas.mpl_connect("motion_notify_event", on_motion)
    fig.canvas.mpl_connect("button_release_event", on_release)
    fig.canvas.mpl_connect("button_press_event", on_click)

    fig._kronos_tools_installed = True

def __kronos_patch_pyplot():
    if getattr(plt, "_kronos_patched", False):
        return
    _orig_figure = plt.figure

    def _figure(*args, **kwargs):
        fig = _orig_figure(*args, **kwargs)
        __kronos_install_tools(fig)
        return fig

    plt.figure = _figure
    _orig_subplots = plt.subplots

    def _subplots(*args, **kwargs):
        fig, axs = _orig_subplots(*args, **kwargs)
        __kronos_install_tools(fig)
        return fig, axs

    plt.subplots = _subplots
    plt._kronos_patched = True
    for num in plt.get_fignums():
        try:
            __kronos_install_tools(plt.figure(num))
        except Exception:
            pass

__kronos_patch_pyplot()
__kronos_set_theme(_KRONOS_THEME_NAME)
'''
                kc.execute(tools_code, silent=True, store_history=False)
            except Exception:
                pass

            layout = self.layout()
            self._console_tab_layout.replaceWidget(self._widget_placeholder, self._console)
            self._widget_placeholder.deleteLater()
            if hasattr(kc.iopub_channel, "message_received"):
                kc.iopub_channel.message_received.connect(self._on_iopub_message)

            self._km = km
            self._kc = kc
            self._sync_kernel_plot_theme(self._is_dark_theme)
        except Exception as exc:
            fallback = QPlainTextEdit()
            fallback.setReadOnly(True)
            fallback.setPlainText(
                f"Console failed to start:\n{exc}\n\n"
                "Install: pip install qtconsole ipykernel"
            )
            layout = self.layout()
            layout.replaceWidget(self._widget_placeholder, fallback)
            self._widget_placeholder.deleteLater()
            self._kc = None

    def _append_output(self, text: str) -> None:
        if not text:
            return
        body_color = "#E6EDF3" if self._is_dark_theme else "#111827"
        in_color = "#58A6FF" if self._is_dark_theme else "#1D4ED8"
        out_color = "#3FB950" if self._is_dark_theme else "#15803D"
        for raw_line in text.rstrip("\n").splitlines():
            line = raw_line.strip("\n")
            safe = escape(line)
            if line.startswith("In ["):
                html = f'<span style="color:{in_color};font-weight:600;">{safe}</span>'
            elif line.startswith("Out["):
                html = f'<span style="color:{out_color};font-weight:600;">{safe}</span>'
            else:
                html = f'<span style="color:{body_color};">{safe}</span>'
            self._output_tab.append(html)

    def _append_problem(self, traceback_text: str) -> None:
        lines = traceback_text.splitlines()
        file_path = ""
        line_no = 0
        message = lines[-1].strip() if lines else "Execution error"
        for line in lines:
            match = re.search(r'File "([^"]+)", line (\\d+)', line)
            if match:
                file_path = match.group(1)
                try:
                    line_no = int(match.group(2))
                except ValueError:
                    line_no = 0
        item = QTreeWidgetItem([file_path or "(unknown)", str(line_no or ""), message])
        item.setData(0, Qt.ItemDataRole.UserRole, file_path)
        item.setData(1, Qt.ItemDataRole.UserRole, line_no)
        self._problems_tab.addTopLevelItem(item)

    def _on_iopub_message(self, msg: dict) -> None:
        msg_type = msg.get("header", {}).get("msg_type")
        if msg_type == "stream":
            self._append_output(msg.get("content", {}).get("text", ""))
        elif msg_type == "execute_result":
            text = msg.get("content", {}).get("data", {}).get("text/plain", "")
            self._append_output(text)
        elif msg_type == "error":
            traceback_lines = msg.get("content", {}).get("traceback", [])
            traceback_text = "\n".join(traceback_lines)
            self._append_output(traceback_text)
            self._append_problem(traceback_text)

    def _on_problem_activated(self, item: QTreeWidgetItem, column: int) -> None:
        del column
        file_path = item.data(0, Qt.ItemDataRole.UserRole) or ""
        line_no = item.data(1, Qt.ItemDataRole.UserRole) or 0
        if isinstance(file_path, str) and file_path:
            try:
                line_no = int(line_no)
            except (TypeError, ValueError):
                line_no = 0
            self.problem_open_requested.emit(file_path, line_no)

    def _prepare_runtime_dirs(self) -> None:
        """Set writable runtime paths for IPython/Jupyter on locked systems."""
        base = Path(os.environ.get("KRONOS_RUNTIME_DIR", "/tmp/kronos-runtime"))
        dirs = {
            "IPYTHONDIR": base / "ipython",
            "JUPYTER_RUNTIME_DIR": base / "jupyter_runtime",
            "JUPYTER_DATA_DIR": base / "jupyter_data",
        }
        for env_name, path in dirs.items():
            if os.environ.get(env_name):
                continue
            path.mkdir(parents=True, exist_ok=True)
            os.environ[env_name] = str(path)

    def get_kernel_client(self):
        """Return the kernel client if available."""
        return getattr(self, "_kc", None)

    def set_theme(self, is_dark: bool) -> None:
        self._is_dark_theme = True
        if not hasattr(self, "_console"):
            return
        self._console.set_default_style("linux")
        self._console.syntax_style = "monokai"
        self._sync_kernel_plot_theme(True)

    def _sync_kernel_plot_theme(self, is_dark: bool) -> None:
        kc = self.get_kernel_client()
        if kc is None:
            return
        del is_dark
        theme_name = "dark"
        code = (
            "try:\n"
            f"    __kronos_set_theme({theme_name!r})\n"
            "except Exception:\n"
            "    pass\n"
        )
        try:
            kc.execute(code, silent=True, store_history=False)
        except Exception:
            pass

    def execute(self, code: str) -> None:
        """Execute code in the embedded console."""
        if hasattr(self, "_console"):
            self._console.execute(code)

    def clear_console(self) -> None:
        """Clear the console output."""
        if hasattr(self, "_console"):
            try:
                self._console.clear()
            except Exception:
                pass

    def interrupt_kernel(self) -> None:
        """Interrupt the running kernel."""
        if hasattr(self, "_km"):
            try:
                self._km.interrupt_kernel()
            except Exception:
                pass

    def restart_kernel(self) -> None:
        """Restart the running kernel and re-initialize plot tools."""
        if hasattr(self, "_km"):
            try:
                self._km.restart_kernel(now=True)
            except Exception:
                pass
            # The kernel needs a moment to come back up before we can inject code.
            from PyQt6.QtCore import QTimer

            QTimer.singleShot(1500, self._reinitialize_kernel)

    def _reinitialize_kernel(self) -> None:
        """Re-inject matplotlib backend and Kronos plot tools after kernel restart."""
        kc = self.get_kernel_client()
        if kc is None:
            return
        # Re-establish the external matplotlib backend.
        try:
            kc.execute("%matplotlib qt", silent=True, store_history=False)
        except Exception:
            pass
        # Re-inject the plot tools code.
        if hasattr(self, "_start_kernel"):
            # The tools code is the big block injected during _start_kernel.
            # We extract and re-run the same tools_code string.
            self._inject_plot_tools(kc)
        # Re-sync the current theme.
        self._sync_kernel_plot_theme(self._is_dark_theme)

    def _inject_plot_tools(self, kc) -> None:
        """Inject the Kronos plot tools into the kernel namespace."""
        tools_code = r'''
import matplotlib.pyplot as plt
try:
    import mpl_toolkits.mplot3d  # noqa: F401
except Exception:
    pass

_KRONOS_THEMES = {
    "dark": {
        "fig": "#1e1e2e",
        "ax": "#1e1e2e",
        "text": "#cdd6f4",
        "tick": "#a6adc8",
        "spine": "#45475a",
        "grid": "#313244",
        "legend": "#cdd6f4",
        "accent": "#89b4fa",
    },
    "light": {
        "fig": "#ffffff",
        "ax": "#ffffff",
        "text": "#334155",
        "tick": "#475569",
        "spine": "#cbd5e1",
        "grid": "#e2e8f0",
        "legend": "#0f172a",
        "accent": "#89b4fa",
    },
}
_KRONOS_THEME_NAME = "dark"
_KRONOS_THEME = _KRONOS_THEMES[_KRONOS_THEME_NAME]

def __kronos_update_rcparams(theme):
    try:
        plt.rcParams.update({
            "figure.facecolor": theme["fig"],
            "axes.facecolor": theme["ax"],
            "savefig.facecolor": theme["fig"],
            "axes.edgecolor": theme["spine"],
            "axes.labelcolor": theme["text"],
            "xtick.color": theme["tick"],
            "ytick.color": theme["tick"],
            "grid.color": theme["grid"],
            "text.color": theme["text"],
            "legend.facecolor": theme["ax"],
            "legend.edgecolor": theme["spine"],
        })
    except Exception:
        pass

def __kronos_apply_theme(fig):
    theme = _KRONOS_THEME
    fig.set_facecolor(theme["fig"])
    for ax in fig.axes:
        ax.set_facecolor(theme["ax"])
        ax.title.set_color(theme["text"])
        ax.xaxis.label.set_color(theme["text"])
        ax.yaxis.label.set_color(theme["text"])
        ax.tick_params(colors=theme["tick"])
        for spine in ax.spines.values():
            spine.set_color(theme["spine"])
        if hasattr(ax, "zaxis"):
            ax.zaxis.label.set_color(theme["text"])
            ax.zaxis.set_tick_params(colors=theme["tick"])
            try:
                ax.xaxis.pane.set_facecolor(theme["ax"])
                ax.yaxis.pane.set_facecolor(theme["ax"])
                ax.zaxis.pane.set_facecolor(theme["ax"])
                ax.xaxis.pane.set_edgecolor(theme["spine"])
                ax.yaxis.pane.set_edgecolor(theme["spine"])
                ax.zaxis.pane.set_edgecolor(theme["spine"])
            except Exception:
                pass
        has_grid = any(
            gridline.get_visible()
            for gridline in (ax.get_xgridlines() + ax.get_ygridlines())
        )
        if has_grid:
            ax.grid(True, color=theme["grid"], linewidth=0.5)
        legend = ax.get_legend()
        if legend is not None:
            legend.get_frame().set_facecolor(theme["ax"])
            legend.get_frame().set_edgecolor(theme["spine"])
            for text in legend.get_texts():
                text.set_color(theme["legend"])

def __kronos_set_theme(theme_name="dark"):
    global _KRONOS_THEME_NAME, _KRONOS_THEME
    if theme_name not in _KRONOS_THEMES:
        theme_name = "dark"
    _KRONOS_THEME_NAME = theme_name
    _KRONOS_THEME = _KRONOS_THEMES[theme_name]
    __kronos_update_rcparams(_KRONOS_THEME)
    for num in plt.get_fignums():
        try:
            fig = plt.figure(num)
            __kronos_apply_theme(fig)
            fig.canvas.draw_idle()
        except Exception:
            pass

def __kronos_find_nearest(event, ax, max_dist=10):
    if event.x is None or event.y is None:
        return None
    ex, ey = event.x, event.y
    best = None
    best_dist = max_dist
    for line in ax.lines:
        xdata = line.get_xdata(orig=False)
        ydata = line.get_ydata(orig=False)
        if xdata is None or ydata is None:
            continue
        if len(xdata) == 0:
            continue
        try:
            pts = ax.transData.transform(list(zip(xdata, ydata)))
        except Exception:
            continue
        for idx, (px, py) in enumerate(pts):
            dist = ((px - ex) ** 2 + (py - ey) ** 2) ** 0.5
            if dist < best_dist:
                best_dist = dist
                best = (line, idx, xdata[idx], ydata[idx], ax)
    return best

def __kronos_set_point(line, idx, x, y):
    xdata = list(line.get_xdata(orig=False))
    ydata = list(line.get_ydata(orig=False))
    if idx < 0 or idx >= len(xdata):
        return
    xdata[idx] = x
    ydata[idx] = y
    line.set_data(xdata, ydata)

def __kronos_install_tools(fig):
    if getattr(fig, "_kronos_tools_installed", False):
        return
    mgr = getattr(fig.canvas, "manager", None)
    toolbar = getattr(mgr, "toolbar", None) if mgr else None
    if toolbar is None:
        return
    state = {"data_cursor": False, "edit_points": False, "drag": None, "ann": None}

    __kronos_apply_theme(fig)

    data_action = toolbar.addAction("Data Cursor")
    data_action.setCheckable(True)
    data_action.setToolTip("Show data values on click")

    edit_action = toolbar.addAction("Edit Points")
    edit_action.setCheckable(True)
    edit_action.setToolTip("Drag points to edit line data")

    def toggle_data(checked):
        if checked:
            edit_action.setChecked(False)
            state["edit_points"] = False
        state["data_cursor"] = checked

    def toggle_edit(checked):
        if checked:
            data_action.setChecked(False)
            state["data_cursor"] = False
        state["edit_points"] = checked

    data_action.toggled.connect(toggle_data)
    edit_action.toggled.connect(toggle_edit)

    def on_click(event):
        if not state["data_cursor"]:
            return
        if event.inaxes is None:
            return
        nearest = __kronos_find_nearest(event, event.inaxes)
        if nearest is None:
            return
        _line, _idx, x, y, ax = nearest
        text = f"x={x:.4g}\\ny={y:.4g}"
        ann = state.get("ann")
        if ann is None or ann.axes is not ax:
            ann = ax.annotate(
                text,
                xy=(x, y),
                xytext=(10, 10),
                textcoords="offset points",
                bbox=dict(
                    boxstyle="round",
                    fc=_KRONOS_THEME["spine"],
                    ec=_KRONOS_THEME["accent"],
                    alpha=0.85,
                ),
                color=_KRONOS_THEME["legend"],
            )
            state["ann"] = ann
        else:
            ann.xy = (x, y)
            ann.set_text(text)
        fig.canvas.draw_idle()

    def on_press(event):
        if not state["edit_points"]:
            return
        if event.inaxes is None:
            return
        nearest = __kronos_find_nearest(event, event.inaxes)
        if nearest is None:
            return
        line, idx, _x, _y, ax = nearest
        state["drag"] = (line, idx, ax)

    def on_motion(event):
        if not state["edit_points"]:
            return
        if state["drag"] is None:
            return
        if event.inaxes is None or event.xdata is None or event.ydata is None:
            return
        line, idx, ax = state["drag"]
        if event.inaxes is not ax:
            return
        __kronos_set_point(line, idx, event.xdata, event.ydata)
        try:
            ax.relim()
            ax.autoscale_view()
        except Exception:
            pass
        fig.canvas.draw_idle()

    def on_release(_event):
        state["drag"] = None

    fig.canvas.mpl_connect("button_press_event", on_press)
    fig.canvas.mpl_connect("motion_notify_event", on_motion)
    fig.canvas.mpl_connect("button_release_event", on_release)
    fig.canvas.mpl_connect("button_press_event", on_click)

    fig._kronos_tools_installed = True

def __kronos_patch_pyplot():
    if getattr(plt, "_kronos_patched", False):
        return
    _orig_figure = plt.figure

    def _figure(*args, **kwargs):
        fig = _orig_figure(*args, **kwargs)
        __kronos_install_tools(fig)
        return fig

    plt.figure = _figure
    _orig_subplots = plt.subplots

    def _subplots(*args, **kwargs):
        fig, axs = _orig_subplots(*args, **kwargs)
        __kronos_install_tools(fig)
        return fig, axs

    plt.subplots = _subplots
    plt._kronos_patched = True
    for num in plt.get_fignums():
        try:
            __kronos_install_tools(plt.figure(num))
        except Exception:
            pass

__kronos_patch_pyplot()
__kronos_set_theme(_KRONOS_THEME_NAME)
'''
        try:
            kc.execute(tools_code, silent=True, store_history=False)
        except Exception:
            pass

    def shutdown(self) -> None:
        """Shutdown the kernel cleanly."""
        if hasattr(self, "_km"):
            try:
                self._km.shutdown_kernel(now=True)
            except Exception:
                pass
