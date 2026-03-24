"""# Kronos IDE — Design tokens for the unified UI system."""

from __future__ import annotations

THEME_COLORS = {
    "dark": {
        # Core surfaces
        "bg_primary": "#0D1024",
        "bg_secondary": "#141B37",
        "bg_elevated": "#1C2450",
        # Ribbon + bars
        "ribbon_top": "#5A70FF",
        "ribbon_bottom": "#1A2256",
        "ribbon_tab_active": "#2A3B92",
        "ribbon_tab_inactive": "#3F56E0",
        "ribbon_tab_border": "#5B6FD3",
        "path_bar": "#121A40",
        "toolbar_bg": "#18204B",
        # Accents
        "accent": "#5E73FF",
        "accent_hover": "#7F92FF",
        "accent_teal": "#38C2C2",
        "accent_violet": "#A78BFA",
        "accent_amber": "#FFB347",
        "accent_rose": "#FF7FA3",
        "accent_lime": "#83D86D",
        "success": "#3FB950",
        "warning": "#D29922",
        "error": "#F85149",
        # Text
        "text_primary": "#EAF0FF",
        "text_secondary": "#B7C4EA",
        # Borders
        "border": "#34407C",
        "border_focus": "#5E73FF",
        "shadow": "#090D23",
    },
    "light": {
        # Core surfaces
        "bg_primary": "#F3F6FF",
        "bg_secondary": "#FFFFFF",
        "bg_elevated": "#EAF0FF",
        # Ribbon + bars
        "ribbon_top": "#5E73FF",
        "ribbon_bottom": "#E6EDFF",
        "ribbon_tab_active": "#FFFFFF",
        "ribbon_tab_inactive": "#4760E8",
        "ribbon_tab_border": "#B8C6F5",
        "path_bar": "#EEF3FF",
        "toolbar_bg": "#E7EEFF",
        # Accents
        "accent": "#4F66F6",
        "accent_hover": "#6E83FF",
        "accent_teal": "#008A8A",
        "accent_violet": "#6D55D8",
        "accent_amber": "#C97700",
        "accent_rose": "#C94C78",
        "accent_lime": "#4A8F2A",
        "success": "#2E9B43",
        "warning": "#A86F09",
        "error": "#C63B39",
        # Text
        "text_primary": "#0E1B47",
        "text_secondary": "#4C5D8F",
        # Borders
        "border": "#C4D0F4",
        "border_focus": "#4F66F6",
        "shadow": "#D5DFFF",
    },
}


def get_colors(theme: str = "dark") -> dict[str, str]:
    """Return colors for a supported theme; fallback to dark."""
    return THEME_COLORS.get(theme, THEME_COLORS["dark"])


# Backward-compatible default for callers that do not pass a theme.
COLORS = get_colors("dark")

FONTS = {
    "ui": "Segoe UI",
    "mono": "JetBrains Mono",
    "size_sm": 11,
    "size_md": 13,
    "size_lg": 15,
}

RADIUS = 6
SPACING = 8
