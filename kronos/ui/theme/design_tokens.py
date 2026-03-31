"""# Kronos IDE — Design tokens for the unified UI system."""

from __future__ import annotations

_CATPPUCCIN_MOCHA = {
    # Core surfaces
    "bg_primary": "#0d0d1a",
    "bg_secondary": "#1a1a2e",
    "bg_elevated": "#16213e",
    "bg_hover": "#1e2d4a",
    # Ribbon + bars
    "ribbon_top": "#1a1a2e",
    "ribbon_bottom": "#16213e",
    "ribbon_tab_active": "#16213e",
    "ribbon_tab_inactive": "#1a1a2e",
    "ribbon_tab_border": "#2a2a4a",
    "path_bar": "#0f1628",
    "toolbar_bg": "#1a1a2e",
    # Accents
    "accent": "#7aa2f7",
    "accent_hover": "#4361ee",
    "accent_teal": "#4cc9f0",
    "accent_violet": "#9d7de0",
    "accent_amber": "#f9e2af",
    "accent_rose": "#f38ba8",
    "accent_lime": "#a6e3a1",
    "success": "#a6e3a1",
    "warning": "#f9e2af",
    "error": "#f72585",
    # Text
    "text_primary": "#cdd6f4",
    "text_secondary": "#6c7086",
    # Borders
    "border": "#2a2a4a",
    "border_focus": "#7aa2f7",
    "shadow": "#0b0d15",
}

THEME_COLORS = {
    # Preferred explicit theme id.
    "catppuccin_mocha": dict(_CATPPUCCIN_MOCHA),
    # Backward compatible aliases.
    "dark": dict(_CATPPUCCIN_MOCHA),
    "light": dict(_CATPPUCCIN_MOCHA),
}


def get_colors(theme: str = "dark") -> dict[str, str]:
    """Return colors for a supported theme; fallback to Catppuccin Mocha."""
    key = (theme or "").strip().lower()
    if key in {"catppuccin", "catppuccin-mocha", "mocha"}:
        key = "catppuccin_mocha"
    return THEME_COLORS.get(key, THEME_COLORS["catppuccin_mocha"])


# Backward-compatible default for callers that do not pass a theme.
COLORS = get_colors("catppuccin_mocha")

FONTS = {
    "ui": "Segoe UI",
    "mono": "JetBrains Mono",
    "size_sm": 11,
    "size_md": 13,
    "size_lg": 15,
}

RADIUS = 6
SPACING = 8
