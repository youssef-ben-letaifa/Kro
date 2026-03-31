"""Toolbox integration utilities for Kronos."""

from .registry import list_available_toolboxes, load_toolbox

REGISTERED_BUILTIN_TOOLBOXES = (
    "Autonomous Driving Toolbox",
    "Signal Analyzer",
)

__all__ = ["REGISTERED_BUILTIN_TOOLBOXES", "list_available_toolboxes", "load_toolbox"]
