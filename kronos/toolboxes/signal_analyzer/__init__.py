"""Signal Analyzer toolbox package for Kronos."""

from __future__ import annotations

from PyQt6.QtWidgets import QWidget

from .signal_analyzer_window import SignalAnalyzerWindow

TOOLBOX_NAME = "Signal Analyzer"


def launch(parent: QWidget | None = None) -> SignalAnalyzerWindow:
    """Create and return the Signal Analyzer toolbox window."""
    return SignalAnalyzerWindow(parent)


# Backward compatibility with existing Kronos toolbox loader that expects
# `AutonomousDrivingToolboxWindow` from toolbox modules.
AutonomousDrivingToolboxWindow = SignalAnalyzerWindow

__all__ = [
    "TOOLBOX_NAME",
    "SignalAnalyzerWindow",
    "AutonomousDrivingToolboxWindow",
    "launch",
]
