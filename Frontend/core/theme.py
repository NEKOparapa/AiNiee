from qfluentwidgets import isDarkTheme


_LIGHT = {
    "surface": "#ffffff",
    "button_bg": "rgba(0,0,0,0.06)",
    "button_border": "rgba(0,0,0,0.18)",
    "button_hover": "rgba(0,0,0,0.10)",
    "button_checked": "rgba(0,0,0,0.16)",
    "text_on_button": "#202020",
    "list_border": "rgba(0,0,0,0.10)",
    "list_selected_bg": "rgba(98,160,234,0.22)",
}

_DARK = {
    "surface": "#2b2b2b",
    "button_bg": "#dddddd",
    "button_border": "rgba(255,255,255,0.28)",
    "button_hover": "rgba(255,255,255,0.22)",
    "button_checked": "rgba(255,255,255,0.30)",
    "text_on_button": "#202020",
    "list_border": "rgba(255,255,255,0.10)",
    "list_selected_bg": "rgba(98,160,234,0.32)",
}


def current_palette() -> dict:
    """Return the color dict matching the active theme."""
    return _DARK if isDarkTheme() else _LIGHT
