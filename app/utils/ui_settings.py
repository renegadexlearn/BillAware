from __future__ import annotations

import json
from pathlib import Path


SETTINGS_PATH = Path(__file__).resolve().parent.parent / "data" / "ui_settings.json"

DEFAULT_UI_SETTINGS = {
    "app_title": "BillAware",
    "logo_path": "images/logo.png",
    "navbar_bg": "#1E3A5F",
    "navbar_text": "#FFFFFF",
    "primary_bg": "#2F7D6D",
    "primary_hover": "#256659",
    "primary_text": "#FFFFFF",
    "accent_bg": "#E8F4F0",
    "surface_tint": "#F6FAFD",
}

THEME_PRESETS = {
    "billaware": {
        "label": "BillAware",
        "navbar_bg": "#1E3A5F",
        "navbar_text": "#FFFFFF",
        "primary_bg": "#2F7D6D",
        "primary_hover": "#256659",
        "primary_text": "#FFFFFF",
        "accent_bg": "#E8F4F0",
        "surface_tint": "#F6FAFD",
    },
    "ledger": {
        "label": "Ledger",
        "navbar_bg": "#25364A",
        "navbar_text": "#F8FAFC",
        "primary_bg": "#A84F1F",
        "primary_hover": "#8E4018",
        "primary_text": "#FFF8F3",
        "accent_bg": "#FFF1E6",
        "surface_tint": "#FAF7F2",
    },
    "mint": {
        "label": "Mint",
        "navbar_bg": "#1F5B56",
        "navbar_text": "#F5FFFD",
        "primary_bg": "#246F63",
        "primary_hover": "#1C5C52",
        "primary_text": "#F7FFFD",
        "accent_bg": "#E8FBF6",
        "surface_tint": "#F4FFFC",
    },
    "harbor": {
        "label": "Harbor",
        "navbar_bg": "#16324F",
        "navbar_text": "#F7FBFF",
        "primary_bg": "#D95F3A",
        "primary_hover": "#B94927",
        "primary_text": "#FFF8F4",
        "accent_bg": "#FFF0E8",
        "surface_tint": "#F5F9FD",
    },
    "graphite": {
        "label": "Graphite",
        "navbar_bg": "#2B303A",
        "navbar_text": "#F9FAFB",
        "primary_bg": "#2C6E91",
        "primary_hover": "#225975",
        "primary_text": "#F8FBFD",
        "accent_bg": "#EAF3F8",
        "surface_tint": "#F7F9FC",
    },
}


def get_ui_settings() -> dict:
    if not SETTINGS_PATH.exists():
        save_ui_settings(DEFAULT_UI_SETTINGS)
        return dict(DEFAULT_UI_SETTINGS)

    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_UI_SETTINGS)

    settings = dict(DEFAULT_UI_SETTINGS)
    settings.update({key: value for key, value in data.items() if key in DEFAULT_UI_SETTINGS})
    return settings


def save_ui_settings(settings: dict) -> dict:
    merged = dict(DEFAULT_UI_SETTINGS)
    merged.update({key: value for key, value in settings.items() if key in DEFAULT_UI_SETTINGS})
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    return merged
