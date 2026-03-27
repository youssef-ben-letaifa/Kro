"""Dynamic toolbox registry and loader."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

_TOOLBOX_ROOT = Path(__file__).resolve().parent


def list_available_toolboxes() -> list[str]:
    """Return toolboxes discovered under the toolbox root."""
    entries: list[str] = []
    for child in sorted(_TOOLBOX_ROOT.iterdir(), key=lambda p: p.name.lower()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if (child / "__init__.py").exists():
            entries.append(child.name)
    return entries


def _alias_for_toolbox(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return f"kronos_toolbox_{slug or 'toolbox'}"


def load_toolbox(name: str) -> ModuleType:
    """Load a toolbox package by display name from disk.

    This supports directory names with spaces (e.g. ``Autonomous Driving Toolbox``)
    by assigning a generated module alias at runtime.
    """
    toolbox_dir = _TOOLBOX_ROOT / name
    init_file = toolbox_dir / "__init__.py"
    if not toolbox_dir.is_dir() or not init_file.exists():
        raise FileNotFoundError(f"Toolbox not found: {name}")

    alias = _alias_for_toolbox(name)
    cached = sys.modules.get(alias)
    if cached is not None:
        return cached

    spec = importlib.util.spec_from_file_location(
        alias,
        init_file,
        submodule_search_locations=[str(toolbox_dir)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not create module spec for toolbox: {name}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[alias] = module
    spec.loader.exec_module(module)
    return module
