"""Core constants and identifiers for MaxHotbox (3ds Max 2026)."""

from __future__ import annotations

PLUGIN_NAME = "MaxHotbox"
PLUGIN_DISPLAY_NAME = "MaxHotbox"
PLUGIN_VERSION = "0.1.3"
TARGET_MAX_VERSION = 2026
CONFIG_SCHEMA_VERSION = 5

# Subclass ID used with comctl32.SetWindowSubclass (unique 32-bit magic id)
SUBCLASS_ID = 0x4D484258  # 'MHBX'

# Win32 window messages
WM_NCDESTROY = 0x0082
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_CONTEXTMENU = 0x007B
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_CAPTURECHANGED = 0x0215
WM_CANCELMODE = 0x001F
WM_KILLFOCUS = 0x0008

# Win32 virtual key codes
VK_LBUTTON = 0x01
VK_RBUTTON = 0x02
VK_MBUTTON = 0x04
VK_BACK = 0x08
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt
VK_ESCAPE = 0x1B
VK_SPACE = 0x20
VK_F8 = 0x77
VK_F9 = 0x78
VK_OEM_3 = 0xC0  # Backtick / Tilde (` ~)

HOLD_KEY_MAP: dict[str, int] = {
    "none": 0,
    "backtick": VK_OEM_3,
    "space": VK_SPACE,
    "f8": VK_F8,
    "f9": VK_F9,
}

HOLD_KEY_LABELS: dict[str, str] = {
    "none": "禁用 (仅使用右键热盒)",
    "backtick": "` / ~ (Tab上方反引号键)",
    "space": "Spacebar (Maya 空格风格)",
    "f8": "F8",
    "f9": "F9",
}

# 8 radial directions ordered clockwise starting from North (up)
DIRECTIONS_8: tuple[str, ...] = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
DIRECTIONS_4: tuple[str, ...] = ("N", "E", "S", "W")

DIRECTION_LABELS_ZH: dict[str, str] = {
    "N": "上 (N)",
    "NE": "右上 (NE)",
    "E": "右 (E)",
    "SE": "右下 (SE)",
    "S": "下 (S)",
    "SW": "左下 (SW)",
    "W": "左 (W)",
    "NW": "左上 (NW)",
}

# Modifier trigger keys
TRIGGER_RMB = "RMB"
TRIGGER_SHIFT_RMB = "SHIFT+RMB"
TRIGGER_CTRL_RMB = "CTRL+RMB"
TRIGGER_ALT_RMB = "ALT+RMB"
TRIGGER_CTRL_SHIFT_RMB = "CTRL+SHIFT+RMB"
TRIGGER_SPACE_RMB = "SPACE+RMB"
TRIGGER_HOTBOX_KEY = "HOTBOX_KEY"

ALL_RMB_TRIGGERS: tuple[str, ...] = (
    TRIGGER_RMB,
    TRIGGER_SHIFT_RMB,
    TRIGGER_CTRL_RMB,
    TRIGGER_ALT_RMB,
    TRIGGER_CTRL_SHIFT_RMB,
    TRIGGER_SPACE_RMB,
)

# 5-zone full hotbox identifiers
HOTBOX_ZONES: tuple[str, ...] = ("CENTER", "NORTH", "SOUTH", "WEST", "EAST")

# Safe 3ds Max tool modes where RMB interception won't block active primitive creation/modal tools
SAFE_COMMAND_MODES: frozenset[str] = frozenset(
    {
        "select",
        "move",
        "rotate",
        "uscale",
        "nuscale",
        "squash",
        "place",
        "selectandmove",
        "selectandrotate",
        "selectandscale",
        "none",
        "",
    }
)

# Theme palettes — Default closely matches Autodesk 3ds Max 2026 Dark UI
THEMES: dict[str, dict[str, str]] = {
    "max2026_native": {
        "name": "3ds Max 2026 原生深灰 (默认)",
        "bg": "#323232",
        "bg_alpha": "240",
        "panel": "#3D3D3D",
        "panel_hover": "#3D75B3",
        "option_bg": "#484848",
        "option_hover": "#4E8DD1",
        "border": "#585858",
        "border_outer": "#1E1E1E",
        "border_hover": "#7BB4EE",
        "text": "#EAEAEA",
        "text_muted": "#A6A6A6",
        "accent": "#5294E2",
        "hub_bg": "#2B2B2B",
        "trail": "#6BA7E5",
        "submenu_tag": "#D9D9D9",
    },
    "maya_dark": {
        "name": "Maya 经典灰蓝",
        "bg": "#36383D",
        "bg_alpha": "240",
        "panel": "#44474E",
        "panel_hover": "#5285A6",
        "option_bg": "#4F535B",
        "option_hover": "#629BC0",
        "border": "#60646D",
        "border_outer": "#222428",
        "border_hover": "#8EC5E8",
        "text": "#EDEDED",
        "text_muted": "#AFAFAF",
        "accent": "#66A3CC",
        "hub_bg": "#2E3035",
        "trail": "#7CB4D8",
        "submenu_tag": "#E0E0E0",
    },
    "max_light": {
        "name": "3ds Max 浅灰亮色",
        "bg": "#D6D6D6",
        "bg_alpha": "244",
        "panel": "#E6E6E6",
        "panel_hover": "#3D75B3",
        "option_bg": "#D8D8D8",
        "option_hover": "#4E8DD1",
        "border": "#9E9E9E",
        "border_outer": "#7A7A7A",
        "border_hover": "#2A5B94",
        "text": "#1F1F1F",
        "text_muted": "#555555",
        "accent": "#3D75B3",
        "hub_bg": "#CCCCCC",
        "trail": "#3D75B3",
        "submenu_tag": "#333333",
    },
}
