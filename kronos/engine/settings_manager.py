"""Centralized settings management for Kronos IDE."""

from __future__ import annotations

import json
from typing import Any

from PyQt6.QtCore import QObject, QSettings, pyqtSignal


_DEFAULTS: dict[str, Any] = {
    # ── Editor ──
    "editor/font_family": "JetBrains Mono",
    "editor/font_size": 13,
    "editor/tab_width": 4,
    "editor/auto_indent": True,
    "editor/line_numbers": True,
    "editor/highlight_line": True,
    "editor/autocomplete": True,
    "editor/word_wrap": False,
    "editor/show_whitespace": False,
    # ── Appearance ──
    "appearance/theme": "light",
    "appearance/accent_color": "#1a6fff",
    "appearance/sidebar_width": 200,
    "appearance/panel_sizes": [200, 860, 220],
    "appearance/font_ui": "Noto Sans",
    "appearance/font_ui_size": 12,
    # ── Simulation ──
    "simulation/default_t_end": 10.0,
    "simulation/default_dt": 0.01,
    "simulation/auto_plot": True,
    "simulation/plot_style": "dark",
    "simulation/max_sim_time": 300.0,
    # ── Console ──
    "console/syntax_style": "monokai",
    "console/font_size": 12,
    "console/max_history": 1000,
    # ── General ──
    "general/autosave": True,
    "general/autosave_interval": 60,
    "general/restore_session": True,
    "general/last_project_path": "",
    "general/recent_files": [],
    "general/check_updates": True,
}


class SettingsManager(QObject):
    """Manage all user preferences via QSettings."""

    settings_changed = pyqtSignal(dict)

    def __init__(self) -> None:
        super().__init__()
        self._qsettings = QSettings(
            QSettings.Format.IniFormat,
            QSettings.Scope.UserScope,
            "IntelligentSystems",
            "Kronos",
        )

    def get(self, key: str, default: Any = None) -> Any:
        """Return the value for *key*, falling back to default or global default."""
        fallback = default if default is not None else _DEFAULTS.get(key)
        value = self._qsettings.value(key, fallback)
        # QSettings stores everything as strings; coerce back to expected type.
        expected = _DEFAULTS.get(key, default)
        if expected is not None and value is not None:
            value = self._coerce(value, expected)
        return value

    def set(self, key: str, value: Any) -> None:
        """Persist a setting and emit change notification."""
        if isinstance(value, (list, dict)):
            self._qsettings.setValue(key, json.dumps(value))
        else:
            self._qsettings.setValue(key, value)
        self._qsettings.sync()
        self.settings_changed.emit({key: value})

    def reset_to_defaults(self) -> None:
        """Clear all stored settings and emit change notification."""
        self._qsettings.clear()
        self._qsettings.sync()
        self.settings_changed.emit(dict(_DEFAULTS))

    # ── Recent files helpers ──

    def get_recent_files(self) -> list[str]:
        """Return the list of recently opened file paths."""
        raw = self.get("general/recent_files", [])
        if isinstance(raw, list):
            return raw
        return []

    def add_recent_file(self, path: str) -> None:
        """Prepend *path* to the recent-files list (max 10 entries)."""
        recent = self.get_recent_files()
        if path in recent:
            recent.remove(path)
        recent.insert(0, path)
        self.set("general/recent_files", recent[:10])

    def clear_recent_files(self) -> None:
        """Clear the recent files list."""
        self.set("general/recent_files", [])

    # ── Panel sizes helpers ──

    def save_panel_sizes(self, sizes: list[int]) -> None:
        """Persist splitter panel sizes."""
        self.set("appearance/panel_sizes", sizes)

    def load_panel_sizes(self) -> list[int]:
        """Load saved panel sizes."""
        raw = self.get("appearance/panel_sizes", [200, 860, 220])
        if isinstance(raw, list):
            return [int(v) for v in raw]
        return [200, 860, 220]

    # ── Session helpers ──

    def save_session(self, session: dict) -> None:
        """Save session state (open files, active tab, panel sizes)."""
        self.set("session/data", session)

    def load_session(self) -> dict:
        """Load saved session state."""
        raw = self.get("session/data", {})
        if isinstance(raw, dict):
            return raw
        return {}

    # ── Internal helpers ──

    @staticmethod
    def _coerce(value: Any, expected: Any) -> Any:
        """Convert QSettings string values back to their expected Python type."""
        if isinstance(expected, bool):
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ("true", "1", "yes")
            return bool(value)
        if isinstance(expected, int) and not isinstance(expected, bool):
            try:
                return int(value)
            except (ValueError, TypeError):
                return expected
        if isinstance(expected, float):
            try:
                return float(value)
            except (ValueError, TypeError):
                return expected
        if isinstance(expected, list):
            if isinstance(value, list):
                return value
            if isinstance(value, str):
                try:
                    parsed = json.loads(value)
                    return parsed if isinstance(parsed, list) else expected
                except json.JSONDecodeError:
                    return expected
            return expected
        if isinstance(expected, dict):
            if isinstance(value, dict):
                return value
            if isinstance(value, str):
                try:
                    parsed = json.loads(value)
                    return parsed if isinstance(parsed, dict) else expected
                except json.JSONDecodeError:
                    return expected
            return expected
        return value
