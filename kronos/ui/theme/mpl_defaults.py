"""Shared Matplotlib dark defaults for Kronos."""

from __future__ import annotations

import matplotlib as mpl


_MPL_DARK_DEFAULTS = {
    "figure.facecolor": "#0d0d1a",
    "axes.facecolor": "#0d0d1a",
    "savefig.facecolor": "#0d0d1a",
    "figure.edgecolor": "#0d0d1a",
    "axes.edgecolor": "#2a2a4a",
    "axes.labelcolor": "#6c7086",
    "xtick.color": "#6c7086",
    "ytick.color": "#6c7086",
    "grid.color": "#1e2a3a",
    "grid.alpha": 0.5,
    "grid.linestyle": "--",
    "axes.titlecolor": "#a0b0d0",
}


def apply_mpl_defaults() -> None:
    """Apply project-wide Matplotlib dark defaults before figure creation."""
    mpl.rcParams.update(_MPL_DARK_DEFAULTS)
