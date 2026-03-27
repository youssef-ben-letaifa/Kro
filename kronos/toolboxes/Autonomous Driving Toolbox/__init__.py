"""Kronos Autonomous Driving Toolbox package."""

from .core import AutonomousDrivingSimulation

__all__ = ["AutonomousDrivingSimulation", "AutonomousDrivingToolboxWindow"]


def __getattr__(name: str):
    if name == "AutonomousDrivingToolboxWindow":
        from .window import AutonomousDrivingToolboxWindow

        return AutonomousDrivingToolboxWindow
    raise AttributeError(name)
