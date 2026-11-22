"""MaxHotbox — Maya-style Marking Menu & Hotbox plugin for Autodesk 3ds Max 2026."""

from __future__ import annotations

from .constants import PLUGIN_DISPLAY_NAME, PLUGIN_NAME, PLUGIN_VERSION, TARGET_MAX_VERSION

__all__ = [
    "PLUGIN_DISPLAY_NAME",
    "PLUGIN_NAME",
    "PLUGIN_VERSION",
    "TARGET_MAX_VERSION",
    "startup",
    "shutdown",
    "toggle",
    "is_enabled",
    "open_settings",
    "open_full_hotbox",
    "sync_viewports",
]


def startup():
    from .controller import startup as _startup

    return _startup()


def shutdown():
    from .controller import shutdown as _shutdown

    return _shutdown()


def toggle() -> bool:
    from .controller import toggle as _toggle

    return _toggle()


def is_enabled() -> bool:
    from .controller import is_enabled as _is_enabled

    return _is_enabled()


def open_settings() -> None:
    from .controller import open_settings as _open_settings

    _open_settings()


def open_full_hotbox() -> None:
    from .controller import open_full_hotbox as _open_full_hotbox

    _open_full_hotbox()


def sync_viewports() -> str:
    from .controller import sync_viewports as _sync_viewports

    return _sync_viewports()
