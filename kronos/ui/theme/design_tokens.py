"""# Kronos IDE — Design tokens for the unified UI system."""

from __future__ import annotations

THEME_COLORS = {
    "dark": {
        # Core surfaces
        "bg_primary": "#101214",
        "bg_secondary": "#1A1E22",
        "bg_elevated": "#23282E",
        # Ribbon + bars
        "ribbon_top": "#0B72E7",
        "ribbon_bottom": "#202327",
        "ribbon_tab_active": "#2A2E33",
        "ribbon_tab_inactive": "#0A67CF",
        "ribbon_tab_border": "#3E4650",
        "path_bar": "#14181C",
        "toolbar_bg": "#1B2025",
        # Accents
        "accent": "#4EA5FF",
        "accent_hover": "#79BEFF",
        "accent_teal": "#38C2C2",
        "accent_violet": "#A78BFA",
        "accent_amber": "#FFB347",
        "accent_rose": "#FF7FA3",
        "accent_lime": "#83D86D",
        "success": "#3FB950",
        "warning": "#D29922",
        "error": "#F85149",
        # Text
        "text_primary": "#E6E9ED",
        "text_secondary": "#A6AFBA",
        # Borders
        "border": "#2E343A",
        "border_focus": "#4EA5FF",
        "shadow": "#0B0D10",
    },
    "light": {
        # Core surfaces
        "bg_primary": "#F4F7FB",
        "bg_secondary": "#FFFFFF",
        "bg_elevated": "#EEF3FA",
        # Ribbon + bars
        "ribbon_top": "#1E88F4",
        "ribbon_bottom": "#EAF2FD",
        "ribbon_tab_active": "#FFFFFF",
        "ribbon_tab_inactive": "#1976D2",
        "ribbon_tab_border": "#BFD4EE",
        "path_bar": "#F7FAFE",
        "toolbar_bg": "#EEF4FC",
        # Accents
        "accent": "#1565C0",
        "accent_hover": "#2A7CDE",
        "accent_teal": "#008A8A",
        "accent_violet": "#6D55D8",
        "accent_amber": "#C97700",
        "accent_rose": "#C94C78",
        "accent_lime": "#4A8F2A",
        "success": "#2E9B43",
        "warning": "#A86F09",
        "error": "#C63B39",
        # Text
        "text_primary": "#0F1722",
        "text_secondary": "#475569",
        # Borders
        "border": "#C7D6E8",
        "border_focus": "#1565C0",
        "shadow": "#D5E2F2",
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
