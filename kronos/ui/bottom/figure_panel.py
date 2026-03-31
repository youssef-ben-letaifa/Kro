"""Matplotlib figure panel."""

from __future__ import annotations

import os
from pathlib import Path

import matplotlib

from kronos.ui.theme.mpl_defaults import apply_mpl_defaults

try:
    import mpl_toolkits.mplot3d  # noqa: F401
except Exception:
    mpl_toolkits = None


def _ensure_matplotlib_config_dir() -> None:
    """Ensure Matplotlib uses a writable config/cache directory."""
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


_ensure_matplotlib_config_dir()
matplotlib.use("QtAgg")
apply_mpl_defaults()

import matplotlib.pyplot as plt  # noqa: F401
from matplotlib.figure import Figure

try:
    from matplotlib.backends.backend_qtagg import (
        FigureCanvasQTAgg as FigureCanvas,
        NavigationToolbar2QT as NavToolbar,
    )
except Exception as exc:
    raise RuntimeError(
        "Matplotlib QtAgg backend is required. Install matplotlib>=3.8.0."
    ) from exc

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class PlotThumbnail(QLabel):
    """Clickable thumbnail that selects a plot."""

    clicked = pyqtSignal(object, object, object)

    def __init__(
        self,
        fig_num: int | None,
        var_name: str | None,
        axes_index: int | None,
        pixmap: QPixmap,
        title: str,
    ) -> None:
        super().__init__()
        self._fig_num = fig_num
        self._var_name = var_name
        self._axes_index = axes_index
        self.setPixmap(pixmap)
        self.setToolTip(title)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event) -> None:
        self.clicked.emit(self._fig_num, self._axes_index, self._var_name)
        super().mousePressEvent(event)


class PlotGallery(QWidget):
    """Scrollable row of plot thumbnails."""

    plot_selected = pyqtSignal(object, object, object)

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._container = QWidget()
        self._row = QHBoxLayout(self._container)
        self._row.setContentsMargins(8, 6, 8, 6)
        self._row.setSpacing(8)
        self._scroll.setWidget(self._container)
        layout.addWidget(self._scroll)

    def clear_all(self) -> None:
        while self._row.count():
            item = self._row.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def set_items(self, items: list[dict]) -> None:
        self.clear_all()
        for item in items:
            pixmap = item.get("pixmap")
            if pixmap is None:
                continue
            thumb = PlotThumbnail(
                item.get("fig_num"),
                item.get("var_name"),
                item.get("axes_index"),
                pixmap,
                item.get("title", "Plot"),
            )
            thumb.clicked.connect(self.plot_selected.emit)
            self._row.addWidget(thumb)
        self._row.addStretch(1)


class FigurePanel(QWidget):
    """Embedded Matplotlib canvas panel."""

    plot_requested = pyqtSignal(object, object, object)

    def __init__(self) -> None:
        super().__init__()
        self._is_dark = True
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setStyleSheet("border-radius: 6px; border: 1px solid #2a2a4a; background: #0d0d1a;")
        self.toolbar = NavToolbar(self.canvas, self)
        self._rotate_3d_action = self.toolbar.addAction("3D Rotate")
        self._rotate_3d_action.setCheckable(True)
        self._rotate_3d_action.setToolTip(
            "Convert 2D plots to 3D and rotate with the mouse"
        )
        self._rotate_3d_action.toggled.connect(self._on_rotate_3d_toggled)
        self._preview_source: QPixmap | None = None
        self._plot_index: dict[tuple[object, object, object], dict] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel("Figures")
        label.setObjectName("panel_header")
        layout.addWidget(label)

        self._gallery = PlotGallery()
        self._gallery.plot_selected.connect(self.plot_requested.emit)
        self._gallery.setMaximumHeight(140)
        layout.addWidget(self._gallery)

        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas, 1)

        self._preview_label = QLabel()
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.hide()
        layout.addWidget(self._preview_label, 1)

        self._empty_hint = QLabel(
            "No figure yet.\nRun a plot to see previews here."
        )
        self._empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._empty_hint, 1)

        self.clear_figure()
        self.set_theme(True)

    def set_theme(self, is_dark: bool) -> None:
        self._is_dark = True
        self._empty_hint.setStyleSheet("color: #6c7086; padding: 12px;")
        self.toolbar.setStyleSheet(
            "QToolBar { background: #1a1a2e; border: none; }"
            "QToolButton { background: transparent; border: none; border-radius: 6px; color: #cdd6f4; }"
            "QToolButton:hover { background: rgba(255,255,255,0.06); }"
            "QToolButton:pressed { background: rgba(255,255,255,0.10); }"
        )
        self._apply_theme_to_figure()
        self.canvas.draw_idle()

    def update_figure(self, fig: Figure) -> None:
        """Replace the current figure."""
        self.figure = fig
        self.canvas.figure = fig
        if self._rotate_3d_action.isChecked():
            self._rotate_3d_action.setChecked(False)
        self.canvas.setCursor(Qt.CursorShape.ArrowCursor)
        self._enable_3d_navigation()
        self._apply_theme_to_figure()
        self.toolbar.show()
        self.canvas.show()
        self._preview_label.hide()
        self._preview_source = None
        self._empty_hint.hide()
        self.canvas.draw_idle()

    def clear_figure(self) -> None:
        """Reset panel to an empty hidden-canvas state."""
        self.figure.clear()
        if self._rotate_3d_action.isChecked():
            self._rotate_3d_action.setChecked(False)
        self.canvas.setCursor(Qt.CursorShape.ArrowCursor)
        self.toolbar.hide()
        self.canvas.hide()
        self._preview_label.hide()
        self._preview_source = None
        self._empty_hint.show()
        self.canvas.draw_idle()

    def set_plot_items(self, items: list[dict]) -> None:
        """Populate thumbnail gallery with plot items."""
        if not items:
            self._plot_index = {}
            self._gallery.clear_all()
            self.clear_figure()
            self.hide()
            return

        self.show()
        self.toolbar.hide()
        self.canvas.hide()
        self._preview_label.hide()
        self._preview_source = None
        self._empty_hint.setText("Select a preview to view it here.")
        self._empty_hint.show()
        gallery_items = []
        self._plot_index = {}
        for item in items:
            png_path = item.get("png_path")
            axes_bbox = item.get("axes_bbox")
            fig_num = item.get("fig_num")
            var_name = item.get("var_name")
            axes_index = item.get("axes_index")
            title = item.get("title", "Plot")
            if png_path is None:
                continue
            pixmap = self._render_thumbnail_from_png(png_path, axes_bbox)
            if pixmap is None:
                continue
            self._plot_index[(fig_num, axes_index, var_name)] = {
                "png_path": png_path,
                "axes_bbox": axes_bbox,
                "title": title,
            }
            gallery_items.append(
                {
                    "fig_num": fig_num,
                    "var_name": var_name,
                    "axes_index": axes_index,
                    "title": title,
                    "pixmap": pixmap,
                }
            )
        self._gallery.set_items(gallery_items)

    def show_selected_figure(self, fig: Figure, axes_index: int | None) -> None:
        """Display a selected plot in the main viewer."""
        if isinstance(fig, Figure) and axes_index is not None:
            axes = list(fig.axes)
            if 0 <= axes_index < len(axes):
                keep = axes[axes_index]
                for ax in axes:
                    if ax is not keep:
                        fig.delaxes(ax)
                keep.set_position([0.12, 0.12, 0.82, 0.8])
        self.update_figure(fig)
        self._empty_hint.hide()

    def preview_selection(
        self, fig_num: object, axes_index: object, var_name: object
    ) -> bool:
        """Show a quick PNG preview for the selected plot."""
        info = self._plot_index.get((fig_num, axes_index, var_name))
        if info is None:
            info = self._plot_index.get((fig_num, axes_index, None))
        if info is None and var_name is not None:
            info = self._plot_index.get((None, axes_index, var_name))
        if info is None:
            return False
        image = self._load_png_crop(info.get("png_path"), info.get("axes_bbox"))
        if image is None:
            return False
        self._preview_source = QPixmap.fromImage(image)
        self._update_preview_pixmap()
        self.toolbar.hide()
        self.canvas.hide()
        self._empty_hint.hide()
        self._preview_label.show()
        return True

    def has_preview(self) -> bool:
        return self._preview_source is not None

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        self._update_preview_pixmap()
        super().resizeEvent(event)

    def _update_preview_pixmap(self) -> None:
        if self._preview_source is None:
            return
        target = self._preview_label.size()
        if target.width() <= 0 or target.height() <= 0:
            return
        scaled = self._preview_source.scaled(
            target,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview_label.setPixmap(scaled)

    def _render_thumbnail_from_png(
        self,
        png_path: str,
        axes_bbox: list[float] | None,
    ) -> QPixmap | None:
        image = self._load_png_crop(png_path, axes_bbox)
        if image is None:
            return None
        pixmap = QPixmap.fromImage(image).scaled(
            160,
            120,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        return pixmap

    def _load_png_crop(
        self, png_path: str, axes_bbox: list[float] | None
    ) -> QImage | None:
        image = QImage(png_path)
        if image.isNull():
            return None
        width = image.width()
        height = image.height()
        if axes_bbox and len(axes_bbox) == 4:
            left = int(axes_bbox[0] * width)
            right = int(axes_bbox[2] * width)
            top = int((1 - axes_bbox[3]) * height)
            bottom = int((1 - axes_bbox[1]) * height)
            pad = 6
            left = max(left - pad, 0)
            right = min(right + pad, width)
            top = max(top - pad, 0)
            bottom = min(bottom + pad, height)
            if right > left and bottom > top:
                image = image.copy(left, top, right - left, bottom - top)
        return image

    def _on_rotate_3d_toggled(self, checked: bool) -> None:
        if not checked:
            self.canvas.setCursor(Qt.CursorShape.ArrowCursor)
            return
        if not self.figure.axes:
            self._rotate_3d_action.setChecked(False)
            return
        converted = self._convert_axes_to_3d(self.figure)
        if converted:
            self._apply_theme_to_figure()
        self._enable_3d_navigation()
        self.canvas.setCursor(Qt.CursorShape.OpenHandCursor)
        self.canvas.draw_idle()

    def _convert_axes_to_3d(self, fig: Figure) -> bool:
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
                lines.append(
                    {
                        "x": xdata,
                        "y": ydata,
                        "color": line.get_color(),
                        "linewidth": line.get_linewidth(),
                        "linestyle": line.get_linestyle(),
                        "marker": line.get_marker(),
                        "markersize": line.get_markersize(),
                        "alpha": line.get_alpha(),
                        "label": line.get_label(),
                    }
                )
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
            changed = True
        return changed

    def _apply_theme_to_figure(self) -> None:
        """Apply panel theme colors to the loaded Matplotlib figure."""
        face_color = "#0d0d1a"
        axis_color = "#0d0d1a"
        text_color = "#a0b0d0"
        tick_color = "#6c7086"
        spine_color = "#2a2a4a"
        grid_color = "#1e2a3a"
        legend_face = "#16213e"
        legend_text = "#cdd6f4"

        self.figure.set_facecolor(face_color)
        for ax in self.figure.axes:
            ax.set_facecolor(axis_color)
            ax.title.set_color(text_color)
            ax.title.set_fontsize(10)
            ax.title.set_fontweight("normal")
            ax.xaxis.label.set_color(text_color)
            ax.yaxis.label.set_color(text_color)
            ax.tick_params(colors=tick_color, labelsize=9)
            for spine in ax.spines.values():
                spine.set_color(spine_color)

            if hasattr(ax, "zaxis"):
                ax.zaxis.label.set_color(text_color)
                ax.zaxis.set_tick_params(colors=tick_color)
                try:
                    ax.xaxis.pane.set_facecolor(axis_color)
                    ax.yaxis.pane.set_facecolor(axis_color)
                    ax.zaxis.pane.set_facecolor(axis_color)
                    ax.xaxis.pane.set_edgecolor(spine_color)
                    ax.yaxis.pane.set_edgecolor(spine_color)
                    ax.zaxis.pane.set_edgecolor(spine_color)
                except Exception:
                    pass

            has_visible_grid = any(
                gridline.get_visible()
                for gridline in (ax.get_xgridlines() + ax.get_ygridlines())
            )
            if has_visible_grid:
                ax.grid(True, color=grid_color, linewidth=0.5)

            legend = ax.get_legend()
            if legend is not None:
                legend.get_frame().set_facecolor(legend_face)
                legend.get_frame().set_edgecolor(spine_color)
                for text in legend.get_texts():
                    text.set_color(legend_text)
                    text.set_fontsize(9)

    def _enable_3d_navigation(self) -> None:
        """Rebind 3D mouse interactions after moving figures across canvases."""
        for ax in self.figure.axes:
            if not hasattr(ax, "get_zlim"):
                continue
            try:
                ax.mouse_init()
            except Exception:
                pass
