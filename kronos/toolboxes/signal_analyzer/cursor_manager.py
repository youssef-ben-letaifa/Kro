"""Reusable matplotlib cursor interactions for analyzer panels."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from matplotlib.axes import Axes
from matplotlib.lines import Line2D

CursorMode = Literal["none", "single", "double", "track", "crosshair"]


@dataclass
class _CursorVisual:
    line_v: Line2D | None = None
    line_h: Line2D | None = None
    text_artist: object | None = None


class CursorManager:
    """Manages one or more data cursors attached to a matplotlib axes."""

    def __init__(self) -> None:
        self._mode: CursorMode = "none"
        self._ax: Axes | None = None
        self._cid_click: int | None = None
        self._cid_move: int | None = None
        self._series_x: np.ndarray | None = None
        self._series_map: dict[str, np.ndarray] = {}
        self._image: np.ndarray | None = None
        self._image_x: np.ndarray | None = None
        self._image_y: np.ndarray | None = None
        self._cursor_a = _CursorVisual()
        self._cursor_b = _CursorVisual()
        self._active_drag: str | None = None

    def attach(self, ax: Axes) -> None:
        """Attach cursor manager to an axes and subscribe to events."""
        self.detach()
        self._ax = ax
        canvas = ax.figure.canvas
        self._cid_click = canvas.mpl_connect("button_press_event", self._on_click)
        self._cid_move = canvas.mpl_connect("motion_notify_event", self._on_move)

    def detach(self) -> None:
        """Detach from current axes and remove event handlers."""
        if self._ax is None:
            return
        canvas = self._ax.figure.canvas
        if self._cid_click is not None:
            canvas.mpl_disconnect(self._cid_click)
        if self._cid_move is not None:
            canvas.mpl_disconnect(self._cid_move)
        self._cid_click = None
        self._cid_move = None
        self._ax = None
        self._clear_visual(self._cursor_a)
        self._clear_visual(self._cursor_b)

    def set_mode(self, mode: CursorMode) -> None:
        """Set cursor interaction mode."""
        self._mode = mode
        self._active_drag = None
        self._clear_visual(self._cursor_a)
        self._clear_visual(self._cursor_b)
        self._redraw()

    def set_series(self, x: np.ndarray, series: dict[str, np.ndarray]) -> None:
        """Provide time-domain or spectrum data for cursor readout."""
        self._series_x = np.asarray(x, dtype=np.float64)
        self._series_map = {name: np.asarray(values, dtype=np.float64) for name, values in series.items()}

    def set_image(self, x: np.ndarray, y: np.ndarray, z: np.ndarray) -> None:
        """Provide image-style data (spectrogram/scalogram) for crosshair mode."""
        self._image_x = np.asarray(x, dtype=np.float64)
        self._image_y = np.asarray(y, dtype=np.float64)
        self._image = np.asarray(z, dtype=np.float64)

    def _on_click(self, event) -> None:
        if self._ax is None or event.inaxes != self._ax:
            return
        if self._mode == "none":
            return
        x = float(event.xdata if event.xdata is not None else 0.0)
        y = float(event.ydata if event.ydata is not None else 0.0)

        if self._mode in {"single", "track", "crosshair"}:
            self._update_cursor(self._cursor_a, x, y, label="A")
            self._active_drag = "A"
        elif self._mode == "double":
            if self._cursor_a.line_v is None:
                self._update_cursor(self._cursor_a, x, y, label="A")
                self._active_drag = "A"
            else:
                self._update_cursor(self._cursor_b, x, y, label="B")
                self._active_drag = "B"
            self._update_delta()

    def _on_move(self, event) -> None:
        if self._ax is None or event.inaxes != self._ax:
            return
        if self._mode == "none":
            return
        if event.xdata is None or event.ydata is None:
            return

        x = float(event.xdata)
        y = float(event.ydata)

        if self._mode == "track":
            x, y = self._nearest_point(x)
            self._update_cursor(self._cursor_a, x, y, label="Track")
            return

        if self._mode == "crosshair":
            self._update_cursor(self._cursor_a, x, y, label="TF", with_horizontal=True)
            return

        if self._active_drag == "A":
            self._update_cursor(self._cursor_a, x, y, label="A")
            self._update_delta()
        elif self._active_drag == "B":
            self._update_cursor(self._cursor_b, x, y, label="B")
            self._update_delta()

    def _nearest_point(self, x_value: float) -> tuple[float, float]:
        if self._series_x is None or self._series_x.size == 0 or not self._series_map:
            return x_value, 0.0
        idx = int(np.argmin(np.abs(self._series_x - x_value)))
        first_series = next(iter(self._series_map.values()))
        return float(self._series_x[idx]), float(first_series[min(idx, first_series.size - 1)])

    def _update_cursor(
        self,
        cursor: _CursorVisual,
        x: float,
        y: float,
        *,
        label: str,
        with_horizontal: bool = False,
    ) -> None:
        if self._ax is None:
            return

        if cursor.line_v is None:
            (cursor.line_v,) = self._ax.plot([x, x], self._ax.get_ylim(), linestyle="--", color="#cdd6f4", alpha=0.88, lw=1.0)
        else:
            cursor.line_v.set_xdata([x, x])
            cursor.line_v.set_ydata(self._ax.get_ylim())

        if with_horizontal:
            if cursor.line_h is None:
                (cursor.line_h,) = self._ax.plot(self._ax.get_xlim(), [y, y], linestyle="--", color="#cdd6f4", alpha=0.78, lw=1.0)
            else:
                cursor.line_h.set_xdata(self._ax.get_xlim())
                cursor.line_h.set_ydata([y, y])
        elif cursor.line_h is not None:
            cursor.line_h.remove()
            cursor.line_h = None

        text = self._format_label(label, x, y)
        if cursor.text_artist is None:
            cursor.text_artist = self._ax.text(
                x,
                y,
                text,
                fontsize=8,
                color="#cdd6f4",
                bbox={"boxstyle": "round,pad=0.25", "facecolor": "#181825", "edgecolor": "#89b4fa", "alpha": 0.92},
            )
        else:
            cursor.text_artist.set_position((x, y))
            cursor.text_artist.set_text(text)

        self._redraw()

    def _format_label(self, prefix: str, x: float, y: float) -> str:
        if self._mode == "crosshair" and self._image is not None and self._image_x is not None and self._image_y is not None:
            x_idx = int(np.argmin(np.abs(self._image_x - x)))
            y_idx = int(np.argmin(np.abs(self._image_y - y)))
            mag = float(self._image[y_idx, x_idx]) if self._image.ndim == 2 else 0.0
            return f"{prefix}: t={x:.4g}, f={y:.4g}, |X|={mag:.4g}"

        values: list[str] = []
        if self._series_x is not None and self._series_x.size > 0:
            idx = int(np.argmin(np.abs(self._series_x - x)))
            for name, arr in self._series_map.items():
                if arr.size == 0:
                    continue
                values.append(f"{name}: {float(arr[min(idx, arr.size - 1)]):.4g}")
        suffix = " | ".join(values[:3])
        return f"{prefix}: x={x:.4g} y={y:.4g}" + (f"\n{suffix}" if suffix else "")

    def _update_delta(self) -> None:
        if self._cursor_a.line_v is None or self._cursor_b.line_v is None:
            return
        if self._cursor_a.text_artist is None:
            return
        xa = float(self._cursor_a.line_v.get_xdata()[0])
        xb = float(self._cursor_b.line_v.get_xdata()[0])
        dt = abs(xb - xa)
        self._cursor_a.text_artist.set_text(f"A-B: dx={dt:.4g}")
        self._redraw()

    def _clear_visual(self, cursor: _CursorVisual) -> None:
        if cursor.line_v is not None:
            try:
                cursor.line_v.remove()
            except Exception:
                pass
        if cursor.line_h is not None:
            try:
                cursor.line_h.remove()
            except Exception:
                pass
        if cursor.text_artist is not None:
            try:
                cursor.text_artist.remove()
            except Exception:
                pass
        cursor.line_v = None
        cursor.line_h = None
        cursor.text_artist = None

    def _redraw(self) -> None:
        if self._ax is None:
            return
        self._ax.figure.canvas.draw_idle()
