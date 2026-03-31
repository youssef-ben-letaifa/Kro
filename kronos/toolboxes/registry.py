"""Dynamic toolbox registry and loader."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

_TOOLBOX_ROOT = Path(__file__).resolve().parent


def _normalize_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def _display_name_from_dir(dirname: str) -> str:
    if dirname.lower() == "signal_analyzer":
        return "Signal Analyzer"
    if "_" in dirname and " " not in dirname:
        return dirname.replace("_", " ").title()
    return dirname


def _discover_toolboxes() -> dict[str, Path]:
    mapping: dict[str, Path] = {}
    for child in sorted(_TOOLBOX_ROOT.iterdir(), key=lambda p: p.name.lower()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if not (child / "__init__.py").exists():
            continue
        display = _display_name_from_dir(child.name)
        mapping[display] = child
    return mapping


def list_available_toolboxes() -> list[str]:
    """Return toolboxes discovered under the toolbox root."""
    return list(_discover_toolboxes().keys())


def _alias_for_toolbox(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return f"kronos_toolbox_{slug or 'toolbox'}"


def load_toolbox(name: str) -> ModuleType:
    """Load a toolbox package by display name from disk.

    This supports directory names with spaces (e.g. ``Autonomous Driving Toolbox``)
    by assigning a generated module alias at runtime.
    """
    discovered = _discover_toolboxes()
    toolbox_dir = discovered.get(name)
    if toolbox_dir is None:
        # Accept directory-name input and normalized lookup to support
        # underscores/spaces/title-case variants.
        direct = _TOOLBOX_ROOT / name
        if direct.is_dir() and (direct / "__init__.py").exists():
            toolbox_dir = direct
        else:
            wanted = _normalize_key(name)
            for display_name, path in discovered.items():
                if _normalize_key(display_name) == wanted or _normalize_key(path.name) == wanted:
                    toolbox_dir = path
                    break
    if toolbox_dir is None:
        raise FileNotFoundError(f"Toolbox not found: {name}")

    init_file = toolbox_dir / "__init__.py"
    alias = _alias_for_toolbox(toolbox_dir.name)
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
