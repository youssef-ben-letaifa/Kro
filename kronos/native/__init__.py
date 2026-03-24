"""# Kronos IDE — Native extension bridge and graceful fallbacks."""

from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import QWidget

try:
    from PyQt6 import sip
except Exception:  # pragma: no cover
    sip = None

try:
    from . import kronos_native  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    kronos_native = None


def native_available() -> bool:
    """Return whether the compiled native extension is available."""
    return kronos_native is not None and sip is not None


def _unwrap_ptr(obj: Any) -> int:
    if sip is None or obj is None:
        return 0
    return int(sip.unwrapinstance(obj))


def create_python_highlighter(document: Any):
    """Create a native Python highlighter bound to a QTextDocument."""
    if not native_available() or document is None:
        return None
    try:
        return kronos_native.PythonHighlighter(_unwrap_ptr(document))
    except Exception:
        return None


def create_waveform_view(parent: QWidget | None = None) -> QWidget | None:
    """Create and wrap a native WaveformView as a QWidget."""
    if not native_available():
        return None
    try:
        native_view = kronos_native.WaveformView(_unwrap_ptr(parent))
        wrapped = sip.wrapinstance(int(native_view.widget_ptr()), QWidget)
        setattr(wrapped, "_native_view", native_view)
        return wrapped
    except Exception:
        return None


class _CanvasRendererFallback:
    """Minimal fallback matching the native renderer API."""

    def clear(self) -> None:
        pass

    def render_block(
        self,
        block_id: str,
        x: float,
        y: float,
        w: float,
        h: float,
        label: str,
        color: str,
    ) -> None:
        del block_id, x, y, w, h, label, color

    def render_wire(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        animated: bool,
    ) -> None:
        del x1, y1, x2, y2, animated

    def set_animation_phase(self, phase: float) -> None:
        del phase

    def rasterize_png(self, width: int, height: int, background: str = "#0D1117") -> bytes:
        del width, height, background
        return b""


CanvasRenderer = (
    kronos_native.CanvasRenderer if native_available() else _CanvasRendererFallback
)

__all__ = [
    "CanvasRenderer",
    "create_python_highlighter",
    "create_waveform_view",
    "kronos_native",
    "native_available",
]
