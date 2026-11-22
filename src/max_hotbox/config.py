"""Configuration model, multi-level Maya-style marking menus with Option Boxes, and JSON persistence."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .constants import (
    ALL_RMB_TRIGGERS,
    CONFIG_SCHEMA_VERSION,
    DIRECTIONS_8,
    HOTBOX_ZONES,
    PLUGIN_VERSION,
    THEMES,
)
from .logger import get_logger, get_user_data_dir


@dataclass
class MenuItem:
    """Executable menu entry with optional Maya-style right-side Option Box [□]."""

    label: str
    command_type: str = "builtin"  # builtin | maxscript | python | action | submenu
    command: str = ""
    enabled: bool = True
    tooltip: str = ""
    submenu_id: str = ""
    option_command_type: str = ""  # e.g. "builtin" for numeric settings caddy
    option_command: str = ""
    option_tooltip: str = ""

    def has_option_box(self) -> bool:
        return bool(
            self.enabled
            and self.command_type != "submenu"
            and self.option_command.strip()
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "label": self.label,
            "command_type": self.command_type,
            "command": self.command,
            "enabled": self.enabled,
        }
        if self.tooltip:
            data["tooltip"] = self.tooltip
        if self.submenu_id:
            data["submenu_id"] = self.submenu_id
        if self.option_command:
            data["option_command_type"] = self.option_command_type or "builtin"
            data["option_command"] = self.option_command
            if self.option_tooltip:
                data["option_tooltip"] = self.option_tooltip
        return data

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> MenuItem:
        return cls(
            label=str(raw.get("label", "")),
            command_type=str(raw.get("command_type", "builtin")),
            command=str(raw.get("command", "")),
            enabled=bool(raw.get("enabled", True)),
            tooltip=str(raw.get("tooltip", "")),
            submenu_id=str(raw.get("submenu_id", "")),
            option_command_type=str(raw.get("option_command_type", "")),
            option_command=str(raw.get("option_command", "")),
            option_tooltip=str(raw.get("option_tooltip", "")),
        )


@dataclass
class RadialMenuProfile:
    """An 8-direction radial marking menu plus optional bottom extra list."""

    profile_id: str
    title: str
    subtitle: str = ""
    slots: dict[str, MenuItem] = field(default_factory=dict)
    extra_items: list[MenuItem] = field(default_factory=list)

    def enabled_directions(self) -> set[str]:
        return {
            direction
            for direction, item in self.slots.items()
            if direction in DIRECTIONS_8 and item.enabled and item.label
        }

    def enabled_extra_items(self) -> list[MenuItem]:
        return [item for item in self.extra_items if item.enabled and item.label]

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "title": self.title,
            "subtitle": self.subtitle,
            "slots": {
                direction: item.to_dict()
                for direction, item in self.slots.items()
                if direction in DIRECTIONS_8
            },
            "extra_items": [item.to_dict() for item in self.extra_items],
        }

    @classmethod
    def from_dict(cls, profile_id: str, raw: dict[str, Any]) -> RadialMenuProfile:
        slots_raw = raw.get("slots", {})
        slots: dict[str, MenuItem] = {}
        if isinstance(slots_raw, dict):
            for direction, item_raw in slots_raw.items():
                if direction in DIRECTIONS_8 and isinstance(item_raw, dict):
                    slots[direction] = MenuItem.from_dict(item_raw)
        extras_raw = raw.get("extra_items", [])
        extras: list[MenuItem] = []
        if isinstance(extras_raw, list):
            for item_raw in extras_raw:
                if isinstance(item_raw, dict):
                    extras.append(MenuItem.from_dict(item_raw))
        return cls(
            profile_id=profile_id,
            title=str(raw.get("title", profile_id)),
            subtitle=str(raw.get("subtitle", "")),
            slots=slots,
            extra_items=extras,
        )


@dataclass
class HotboxZoneProfile:
    """One zone of the 5-zone Maya-style full Hotbox."""

    zone_id: str
    title: str
    items: list[MenuItem] = field(default_factory=list)

    def enabled_items(self) -> list[MenuItem]:
        return [item for item in self.items if item.enabled and item.label]

    def to_dict(self) -> dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "title": self.title,
            "items": [item.to_dict() for item in self.items],
        }

    @classmethod
    def from_dict(cls, zone_id: str, raw: dict[str, Any]) -> HotboxZoneProfile:
        items_raw = raw.get("items", [])
        items = [
            MenuItem.from_dict(item_raw)
            for item_raw in items_raw
            if isinstance(item_raw, dict)
        ]
        return cls(
            zone_id=zone_id,
            title=str(raw.get("title", zone_id)),
            items=items,
        )


@dataclass
class HotboxSettings:
    """User-configurable behavior and visual settings."""

    enabled: bool = True
    theme: str = "max2026_native"
    deadzone_radius: int = 28
    menu_radius: int = 124
    submenu_dwell_ms: int = 180
    ui_scale: float = 1.0
    opacity: float = 0.96
    show_gesture_trail: bool = True
    safe_tool_mode_guard: bool = True
    hold_hotbox_key: str = "backtick"  # none | backtick | space | f8 | f9
    enabled_triggers: dict[str, bool] = field(
        default_factory=lambda: {trigger: True for trigger in ALL_RMB_TRIGGERS}
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "theme": self.theme,
            "deadzone_radius": self.deadzone_radius,
            "menu_radius": self.menu_radius,
            "submenu_dwell_ms": self.submenu_dwell_ms,
            "ui_scale": self.ui_scale,
            "opacity": self.opacity,
            "show_gesture_trail": self.show_gesture_trail,
            "safe_tool_mode_guard": self.safe_tool_mode_guard,
            "hold_hotbox_key": self.hold_hotbox_key,
            "enabled_triggers": dict(self.enabled_triggers),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> HotboxSettings:
        defaults = cls()
        theme = str(raw.get("theme", defaults.theme))
        if theme not in THEMES:
            theme = defaults.theme
        triggers = dict(defaults.enabled_triggers)
        raw_triggers = raw.get("enabled_triggers")
        if isinstance(raw_triggers, dict):
            for k in ALL_RMB_TRIGGERS:
                if k in raw_triggers:
                    triggers[k] = bool(raw_triggers[k])
        return cls(
            enabled=bool(raw.get("enabled", defaults.enabled)),
            theme=theme,
            deadzone_radius=max(12, min(80, int(raw.get("deadzone_radius", defaults.deadzone_radius)))),
            menu_radius=max(84, min(190, int(raw.get("menu_radius", defaults.menu_radius)))),
            submenu_dwell_ms=max(80, min(600, int(raw.get("submenu_dwell_ms", defaults.submenu_dwell_ms)))),
            ui_scale=max(0.75, min(1.5, float(raw.get("ui_scale", defaults.ui_scale)))),
            opacity=max(0.55, min(1.0, float(raw.get("opacity", defaults.opacity)))),
            show_gesture_trail=bool(raw.get("show_gesture_trail", defaults.show_gesture_trail)),
            safe_tool_mode_guard=bool(raw.get("safe_tool_mode_guard", defaults.safe_tool_mode_guard)),
            hold_hotbox_key=str(raw.get("hold_hotbox_key", defaults.hold_hotbox_key)),
            enabled_triggers=triggers,
        )


@dataclass
class HotboxConfig:
    """Complete MaxHotbox configuration tree."""

    schema_version: int = CONFIG_SCHEMA_VERSION
    plugin_version: str = PLUGIN_VERSION
    settings: HotboxSettings = field(default_factory=HotboxSettings)
    radial_profiles: dict[str, RadialMenuProfile] = field(default_factory=dict)
    hotbox_zones: dict[str, HotboxZoneProfile] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "plugin_version": self.plugin_version,
            "settings": self.settings.to_dict(),
            "radial_profiles": {
                pid: prof.to_dict() for pid, prof in self.radial_profiles.items()
            },
            "hotbox_zones": {
                zid: zone.to_dict() for zid, zone in self.hotbox_zones.items()
            },
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> HotboxConfig:
        base = create_default_config()
        if not isinstance(raw, dict):
            return base

        schema_ver = int(raw.get("schema_version", 1))
        if isinstance(raw.get("settings"), dict):
            base.settings = HotboxSettings.from_dict(raw["settings"])

        # Only override default menus if schema matches current version;
        # v1 configs automatically receive the upgraded v2 multi-level menus + Option Boxes
        if schema_ver >= CONFIG_SCHEMA_VERSION:
            raw_profiles = raw.get("radial_profiles")
            if isinstance(raw_profiles, dict):
                for pid, pdata in raw_profiles.items():
                    if isinstance(pdata, dict):
                        base.radial_profiles[pid] = RadialMenuProfile.from_dict(pid, pdata)

            raw_zones = raw.get("hotbox_zones")
            if isinstance(raw_zones, dict):
                for zid, zdata in raw_zones.items():
                    if zid in HOTBOX_ZONES and isinstance(zdata, dict):
                        base.hotbox_zones[zid] = HotboxZoneProfile.from_dict(zid, zdata)

        return base


def _b(
    label: str,
    cmd: str,
    tooltip: str = "",
    opt_cmd: str = "",
    opt_tip: str = "",
) -> MenuItem:
    return MenuItem(
        label=label,
        command_type="builtin",
        command=cmd,
        tooltip=tooltip,
        option_command_type="builtin" if opt_cmd else "",
        option_command=opt_cmd,
        option_tooltip=opt_tip,
    )


def _sub(label: str, submenu_id: str, tooltip: str = "") -> MenuItem:
    return MenuItem(
        label=label,
        command_type="submenu",
        command="",
        submenu_id=submenu_id,
        tooltip=tooltip,
    )


def create_default_radial_profiles() -> dict[str, RadialMenuProfile]:
    """Build complete multi-level Maya-style marking menus with Option Boxes [□]."""
    profiles: list[RadialMenuProfile] = [
        # ================================================= Primary Context RMB
        RadialMenuProfile(
            profile_id="rmb_poly",
            title="对象与子层级",
            subtitle="RMB · 多边形",
            slots={
                "N": _b("顶点 Vertex", "subobj_vertex", "进入顶点子层级 (1)"),
                "NE": _b("边界 Border", "subobj_border", "进入边界子层级 (3)"),
                "E": _b("边 Edge", "subobj_edge", "进入边子层级 (2)"),
                "SE": _b("元素 Element", "subobj_element", "进入元素子层级 (5)"),
                "S": _b("对象模式", "subobj_object", "返回对象层级 (0)"),
                "SW": _sub("常用修改器", "submenu_modifiers", "悬停展开常用与变形修改器"),
                "W": _b("多边形 Face", "subobj_polygon", "进入多边形子层级 (4)"),
                "NW": _sub("显示与孤立", "submenu_visibility", "悬停展开孤立/隐藏/冻结子菜单"),
            },
            extra_items=[
                _b("石墨: 快速循环 Swift Loop", "graphite_swift_loop"),
                _b("石墨: 随机选择 Random", "graphite_random_select", "快速随机选择", "graphite_random_select_settings", "随机选择比例面板"),
                _b("转换为可编辑多边形", "convert_to_poly"),
                _b("居中枢轴 Center Pivot", "center_pivot"),
                _b("重置变换 Reset XForm", "reset_xform"),
                _b("塌陷修改器栈 Collapse", "collapse_stack"),
                _b("热盒设置 / 切回四元菜单", "open_settings"),
            ],
        ),
        RadialMenuProfile(
            profile_id="rmb_spline",
            title="样条线层级",
            subtitle="RMB · 样条线",
            slots={
                "N": _b("顶点 Vertex", "subobj_vertex"),
                "NE": _b("优化 Refine", "spline_refine"),
                "E": _b("线段 Segment", "subobj_edge"),
                "SE": _b("焊接 Weld", "spline_weld"),
                "S": _b("对象模式", "subobj_object"),
                "SW": _b("转样条线", "convert_to_spline"),
                "W": _b("样条 Spline", "subobj_border"),
                "NW": _sub("显示与孤立", "submenu_visibility"),
            },
            extra_items=[
                _b("居中枢轴 Center Pivot", "center_pivot"),
                _b("添加挤出 Extrude", "mod_extrude"),
                _b("热盒设置 / 切回四元菜单", "open_settings"),
            ],
        ),
        RadialMenuProfile(
            profile_id="rmb_empty",
            title="场景与创建",
            subtitle="RMB · 空白视口",
            slots={
                "N": _sub("基础几何体", "submenu_create_geo", "悬停展开几何体创建菜单"),
                "NE": _sub("样条图形", "submenu_create_spline", "悬停展开样条线创建菜单"),
                "E": _sub("相机与灯光", "submenu_create_cam_light", "悬停展开相机/灯光/辅助物"),
                "SE": _sub("视口着色", "submenu_shading", "悬停展开线框/边面/黏土着色"),
                "S": _b("聚焦全部", "zoom_extents_all"),
                "SW": _sub("显示与冻结", "submenu_visibility"),
                "W": _sub("视图切换", "submenu_views", "悬停展开透视/顶/前/左/正交视图"),
                "NW": _b("切换网格", "toggle_grid"),
            },
            extra_items=[
                _b("全选 Select All", "select_all"),
                _b("打开五区全局热盒", "open_full_hotbox"),
                _b("热盒设置 / 切回四元菜单", "open_settings"),
            ],
        ),
        # ============================================ Shift+RMB Poly Modeling
        RadialMenuProfile(
            profile_id="shift_rmb_object",
            title="建模与修改器",
            subtitle="Shift+RMB · 对象",
            slots={
                "N": _sub("创建几何体", "submenu_create_geo"),
                "NE": _sub("常用修改器", "submenu_modifiers"),
                "E": _sub("变形与UV", "submenu_modifiers_deform"),
                "SE": _b("涡轮平滑", "mod_turbosmooth"),
                "S": _b("转可编辑多边形", "convert_to_poly"),
                "SW": _b("对称 Symmetry", "mod_symmetry"),
                "W": _sub("石墨工具", "submenu_graphite_modeling"),
                "NW": _sub("枢轴与变换", "submenu_pivot"),
            },
            extra_items=[
                _b("编辑多边形 Edit Poly", "mod_edit_poly"),
                _b("壳修改器 Shell", "mod_shell"),
                _b("展UV Unwrap UVW", "mod_unwrap_uvw"),
                _b("塌陷修改器栈 Collapse", "collapse_stack"),
                _b("克隆对象 Clone", "clone_object"),
            ],
        ),
        RadialMenuProfile(
            profile_id="shift_rmb_vertex",
            title="顶点建模",
            subtitle="Shift+RMB · 顶点",
            slots={
                "N": _b("目标焊接", "poly_weld", "交互目标焊接", "poly_weld_settings", "焊接数值面板"),
                "NE": _b("切角 Chamfer", "poly_chamfer", "鼠标拖动切角", "poly_chamfer_settings", "切角数值面板"),
                "E": _b("连接 Connect", "poly_connect"),
                "SE": _sub("石墨建模", "submenu_graphite_modeling"),
                "S": _b("移除 Remove", "poly_remove"),
                "SW": _b("断开 Break", "poly_break"),
                "W": _b("塌陷 Collapse", "poly_collapse"),
                "NW": _sub("切割与平面", "submenu_poly_cut"),
            },
            extra_items=[
                _b("石墨: 快速循环 Swift Loop", "graphite_swift_loop"),
                _b("石墨: 随机选择", "graphite_random_select", "随机选顶点", "graphite_random_select_settings", "随机选择比例面板"),
                _b("挤出 Extrude", "poly_extrude", "鼠标拖动挤出", "poly_extrude_settings", "挤出数值面板"),
                _b("松弛 Relax", "poly_relax", "快速松弛", "poly_relax_settings", "松弛数值面板"),
                _b("切换软选择 Soft Selection", "poly_soft_selection"),
            ],
        ),
        RadialMenuProfile(
            profile_id="shift_rmb_edge",
            title="边建模",
            subtitle="Shift+RMB · 边",
            slots={
                "N": _b("连接 Connect", "poly_connect", "快速连接边", "poly_connect_settings", "连接数值面板"),
                "NE": _b("切角 Chamfer", "poly_chamfer", "鼠标拖动切角", "poly_chamfer_settings", "切角数值面板"),
                "E": _b("桥接 Bridge", "poly_bridge", "交互桥接边", "poly_bridge_settings", "桥接数值面板"),
                "SE": _sub("石墨建模", "submenu_graphite_modeling"),
                "S": _b("移除 Remove", "poly_remove"),
                "SW": _sub("石墨选择", "submenu_graphite_select"),
                "W": _sub("切割与平面", "submenu_poly_cut"),
                "NW": _b("快速循环", "graphite_swift_loop", "石墨快速循环加线 (Swift Loop)"),
            },
            extra_items=[
                _b("石墨: 流连接 Flow Connect", "graphite_flow_connect"),
                _b("石墨: 设置流 Set Flow", "graphite_set_flow"),
                _b("清理边(含孤立顶点) Clean Remove", "poly_clean_remove"),
                _b("挤出 Extrude", "poly_extrude", "鼠标拖动挤出", "poly_extrude_settings", "挤出数值面板"),
                _b("创建图形 Create Shape", "poly_create_shape", "从边创建图形", "poly_create_shape_settings", "创建图形选项"),
                _b("塌陷 Collapse", "poly_collapse"),
            ],
        ),
        RadialMenuProfile(
            profile_id="shift_rmb_border",
            title="边界建模",
            subtitle="Shift+RMB · 边界",
            slots={
                "N": _b("封口 Cap", "poly_cap"),
                "NE": _b("桥接 Bridge", "poly_bridge", "交互桥接", "poly_bridge_settings", "桥接数值面板"),
                "E": _b("挤出 Extrude", "poly_extrude", "鼠标拖动挤出", "poly_extrude_settings", "挤出数值面板"),
                "SE": _b("切角 Chamfer", "poly_chamfer", "鼠标拖动切角", "poly_chamfer_settings", "切角数值面板"),
                "S": _b("塌陷 Collapse", "poly_collapse"),
                "SW": _b("几何体变圆", "graphite_geopoly", "石墨 GeoPoly 一键整圆"),
                "W": _b("创建图形", "poly_create_shape", "从边界创建图形", "poly_create_shape_settings", "创建图形选项"),
                "NW": _b("转边选择", "convert_sel_edge"),
            },
            extra_items=[
                _b("转多边形选择", "convert_sel_poly"),
                _b("对象模式 Object", "subobj_object"),
            ],
        ),
        RadialMenuProfile(
            profile_id="shift_rmb_poly",
            title="多边形建模",
            subtitle="Shift+RMB · 面",
            slots={
                "N": _b("挤出 Extrude", "poly_extrude", "鼠标拖动控制挤出长度", "poly_extrude_settings", "挤出数值面板"),
                "NE": _b("插入 Inset", "poly_inset", "鼠标拖动控制插入", "poly_inset_settings", "插入数值面板"),
                "E": _b("倒角 Bevel", "poly_bevel", "鼠标拖动控制倒角", "poly_bevel_settings", "倒角数值面板"),
                "SE": _sub("石墨建模", "submenu_graphite_modeling"),
                "S": _b("翻转法线", "poly_flip"),
                "SW": _b("分离 Detach", "poly_detach", "分离面", "poly_detach_settings", "分离选项面板"),
                "W": _b("轮廓 Outline", "poly_outline", "鼠标拖动控制轮廓", "poly_outline_settings", "轮廓数值面板"),
                "NW": _sub("切割与平面", "submenu_poly_cut"),
            },
            extra_items=[
                _b("桥接 Bridge", "poly_bridge", "交互桥接面", "poly_bridge_settings", "桥接数值面板"),
                _b("石墨: 几何体变圆 GeoPoly", "graphite_geopoly"),
                _b("石墨: 随机选择面", "graphite_random_select", "随机选面", "graphite_random_select_settings", "随机选择比例面板"),
                _b("自动平滑 Auto Smooth", "poly_autosmooth"),
                _b("塌陷 Collapse", "poly_collapse"),
            ],
        ),
        # ========================================== Ctrl / Alt / Ctrl+Shift / Space
        RadialMenuProfile(
            profile_id="ctrl_rmb_select",
            title="选择与转换",
            subtitle="Ctrl+RMB · 选择",
            slots={
                "N": _b("转为顶点", "convert_sel_vertex"),
                "NE": _b("扩大选择", "poly_grow"),
                "E": _b("转为边", "convert_sel_edge"),
                "SE": _b("缩小选择", "poly_shrink"),
                "S": _b("转为元素", "convert_sel_element"),
                "SW": _sub("石墨选择", "submenu_graphite_select"),
                "W": _b("转为多边形", "convert_sel_poly"),
                "NW": _b("环形边 Ring", "poly_ring"),
            },
            extra_items=[
                _b("循环边 Loop", "poly_loop"),
                _b("石墨: 随机选择", "graphite_random_select", "快速随机选择", "graphite_random_select_settings", "随机选择比例面板"),
                _b("石墨: 选择多边面 N-Gon", "graphite_select_ngons", "选 >4 边多边面", "graphite_select_by_sides_settings", "按边数选择面面板"),
                _b("切换软选择 Soft Selection", "poly_soft_selection"),
                _b("反选 Invert Selection", "select_invert"),
                _b("全选 Select All", "select_all"),
            ],
        ),
        RadialMenuProfile(
            profile_id="space_rmb_maya",
            title="Maya 视图热盒",
            subtitle="Space+RMB · 视图",
            slots={
                "N": _b("顶视图 Top", "view_top"),
                "NE": _b("透视图 Persp", "view_perspective"),
                "E": _b("右视图 Right", "view_right"),
                "SE": _sub("视口着色", "submenu_shading"),
                "S": _b("前视图 Front", "view_front"),
                "SW": _b("最大化视口", "toggle_maximize_viewport"),
                "W": _b("左视图 Left", "view_left"),
                "NW": _sub("更多视图", "submenu_views"),
            },
            extra_items=[
                _b("聚焦选中对象 (Z)", "zoom_extents_sel"),
                _b("线框 / 着色切换 (F3)", "toggle_wireframe"),
                _b("边面显示切换 (F4)", "toggle_edged_faces"),
                _b("孤立选择切换 (Isolate)", "toggle_isolate"),
                _b("打开五区全局热盒", "open_full_hotbox"),
                _b("热盒设置 / 切回四元菜单", "open_settings"),
            ],
        ),
        RadialMenuProfile(
            profile_id="alt_rmb_viewport",
            title="视口与显示",
            subtitle="Alt+RMB · 视口",
            slots={
                "N": _b("顶视图 Top", "view_top"),
                "NE": _b("透视图 Persp", "view_perspective"),
                "E": _b("右视图 Right", "view_right"),
                "SE": _sub("着色模式", "submenu_shading"),
                "S": _b("前视图 Front", "view_front"),
                "SW": _b("边面显示 F4", "toggle_edged_faces"),
                "W": _b("左视图 Left", "view_left"),
                "NW": _b("聚焦选中 Z", "zoom_extents_sel"),
            },
            extra_items=[
                _b("线框 / 着色切换 (F3)", "toggle_wireframe"),
                _b("最大化视口切换 (Alt+W)", "toggle_maximize_viewport"),
                _b("正交视图 Orthographic", "view_ortho"),
                _b("相机视图 Camera", "view_camera"),
            ],
        ),
        RadialMenuProfile(
            profile_id="ctrl_shift_rmb_transform",
            title="变换与枢轴",
            subtitle="Ctrl+Shift+RMB",
            slots={
                "N": _b("局部坐标", "coordsys_local"),
                "NE": _b("视图坐标", "coordsys_view"),
                "E": _b("世界坐标", "coordsys_world"),
                "SE": _b("角度捕捉", "toggle_angle_snap"),
                "S": _b("仅影响轴", "toggle_pivot_only"),
                "SW": _b("对象捕捉", "toggle_snap"),
                "W": _sub("枢轴工具", "submenu_pivot"),
                "NW": _b("重置变换", "reset_xform"),
            },
            extra_items=[
                _b("移动工具 Move", "tool_move"),
                _b("旋转工具 Rotate", "tool_rotate"),
                _b("缩放工具 Scale", "tool_scale"),
                _b("热盒设置 / 切回四元菜单", "open_settings"),
            ],
        ),
        # ============================================ Hover-Expand Submenus!
        RadialMenuProfile(
            profile_id="submenu_create_geo",
            title="基础几何体",
            subtitle="主按钮交互创建 · □ 原点直出",
            slots={
                "N": _b("长方体 Box", "create_box_interactive", "视口拖动创建", "create_box", "原点快速创建"),
                "NE": _b("球体 Sphere", "create_sphere_interactive", "视口拖动创建", "create_sphere", "原点快速创建"),
                "E": _b("圆柱 Cylinder", "create_cylinder_interactive", "视口拖动创建", "create_cylinder", "原点快速创建"),
                "SE": _b("平面 Plane", "create_plane_interactive", "视口拖动创建", "create_plane", "原点快速创建"),
                "S": _b("圆环 Torus", "create_torus_interactive", "视口拖动创建", "create_torus", "原点快速创建"),
                "SW": _b("圆锥 Cone", "create_cone_interactive", "视口拖动创建", "create_cone", "原点快速创建"),
                "W": _b("管状体 Tube", "create_tube_interactive", "视口拖动创建", "create_tube", "原点快速创建"),
                "NW": _b("几何球体", "create_geosphere_interactive", "视口拖动创建", "create_geosphere", "原点快速创建"),
            },
        ),
        RadialMenuProfile(
            profile_id="submenu_create_spline",
            title="样条图形",
            subtitle="子菜单 · Splines",
            slots={
                "N": _b("线 Line", "create_line"),
                "NE": _b("圆 Circle", "create_circle"),
                "E": _b("矩形 Rect", "create_rectangle"),
                "SE": _b("弧 Arc", "create_arc"),
                "S": _b("螺旋 Helix", "create_helix"),
                "SW": _b("星形 Star", "create_star"),
                "W": _b("多边形 NGon", "create_ngon"),
                "NW": _b("文本 Text", "create_text"),
            },
        ),
        RadialMenuProfile(
            profile_id="submenu_create_cam_light",
            title="相机与灯光",
            subtitle="子菜单 · Cam / Light",
            slots={
                "N": _b("视图相机", "camera_from_view"),
                "NE": _b("目标相机", "create_target_camera"),
                "E": _b("自由聚光灯", "create_free_light"),
                "SE": _b("目标聚光灯", "create_target_light"),
                "S": _b("辅助点 Point", "create_point_helper"),
                "SW": _b("虚拟体 Dummy", "create_dummy_helper"),
                "W": _b("辅助栅格", "create_grid_helper"),
                "NW": _b("聚焦全部", "zoom_extents_all"),
            },
        ),
        RadialMenuProfile(
            profile_id="submenu_modifiers",
            title="常用修改器",
            subtitle="子菜单 · Modifiers",
            slots={
                "N": _b("编辑多边形", "mod_edit_poly"),
                "NE": _b("涡轮平滑", "mod_turbosmooth"),
                "E": _b("对称 Symmetry", "mod_symmetry"),
                "SE": _b("壳 Shell", "mod_shell"),
                "S": _b("切角 Chamfer", "mod_chamfer"),
                "SW": _sub("变形与UV", "submenu_modifiers_deform"),
                "W": _b("加权法线", "mod_weighted_normals"),
                "NW": _b("OpenSubdiv", "mod_opensubdiv"),
            },
            extra_items=[
                _b("展UV Unwrap UVW", "mod_unwrap_uvw"),
                _b("贴图坐标 UVW Map", "mod_uvw_map"),
                _b("镜像 Mirror", "mod_mirror"),
                _b("减面优化 ProOptimizer", "mod_prooptimizer"),
                _b("平滑 Smooth", "mod_smooth"),
                _b("塌陷堆栈 Collapse Stack", "collapse_stack"),
            ],
        ),
        RadialMenuProfile(
            profile_id="submenu_modifiers_deform",
            title="变形与UV修改器",
            subtitle="子菜单 · Deform / UV",
            slots={
                "N": _b("FFD 3x3x3", "mod_ffd3"),
                "NE": _b("FFD 2x2x2", "mod_ffd2"),
                "E": _b("弯曲 Bend", "mod_bend"),
                "SE": _b("扭曲 Twist", "mod_twist"),
                "S": _b("锥化 Taper", "mod_taper"),
                "SW": _b("噪波 Noise", "mod_noise"),
                "W": _b("球形化 Spherify", "mod_spherify"),
                "NW": _b("FFD 4x4x4", "mod_ffd4"),
            },
            extra_items=[
                _b("推力 Push", "mod_push"),
                _b("车削 Lathe", "mod_lathe"),
                _b("扫描 Sweep", "mod_sweep"),
                _b("挤出修改器 Extrude", "mod_extrude"),
                _b("编辑法线 Edit Normals", "mod_edit_normals"),
            ],
        ),
        RadialMenuProfile(
            profile_id="submenu_graphite_modeling",
            title="石墨建模工具",
            subtitle="子菜单 · Graphite",
            slots={
                "N": _b("快速循环", "graphite_swift_loop", "石墨快速循环加线 (Swift Loop)"),
                "NE": _b("流连接", "graphite_flow_connect", "石墨按曲率流连接 (Flow Connect)"),
                "E": _b("设置流", "graphite_set_flow", "石墨顺滑曲率流 (Set Flow)"),
                "SE": _b("间距均分", "graphite_space_loop", "石墨循环边间距均分 (Space Loop)"),
                "S": _b("几何体变圆", "graphite_geopoly", "石墨 GeoPoly 一键整圆"),
                "SW": _sub("约束切换", "submenu_graphite_constrain"),
                "W": _b("全部四角化", "graphite_quadrify", "石墨 Quadrify All"),
                "NW": _sub("石墨选择", "submenu_graphite_select"),
            },
            extra_items=[
                _b("清理孤立顶点 Delete Iso Verts", "graphite_remove_iso_verts"),
                _b("松弛 Relax", "poly_relax", "快速松弛", "poly_relax_settings", "松弛数值面板"),
                _b("最佳平面化 Make Planar", "poly_make_planar"),
            ],
        ),
        RadialMenuProfile(
            profile_id="submenu_graphite_select",
            title="石墨选择工具",
            subtitle="主按钮快选 · □ 自建参数面板",
            slots={
                "N": _b("随机选择", "graphite_random_select", "按上次比例随机选", "graphite_random_select_settings", "随机选择比例面板"),
                "NE": _b("点循环", "graphite_dot_loop", "隔选循环边 (Dot Loop)", "graphite_dot_loop_settings", "点循环步长面板"),
                "E": _b("点环形", "graphite_dot_ring", "隔选环形边 (Dot Ring)", "graphite_dot_ring_settings", "点环形步长面板"),
                "SE": _b("选多边面", "graphite_select_ngons", "选 >4 边多边面", "graphite_select_by_sides_settings", "按边数选择面面板"),
                "S": _b("选择硬边", "graphite_select_hard_edges", "按角度选硬边", "graphite_select_hard_edges_settings", "硬边角度阈值面板"),
                "SW": _b("共面选择", "graphite_select_by_angle", "按角度泛洪选共面", "graphite_select_by_angle_settings", "共面角度阈值面板"),
                "W": _b("循环边 Loop", "poly_loop"),
                "NW": _b("环形边 Ring", "poly_ring"),
            },
            extra_items=[
                _b("扩大选择 Grow", "poly_grow"),
                _b("缩小选择 Shrink", "poly_shrink"),
                _b("边界转边 Border to Edge", "poly_border_to_edge"),
                _b("切换软选择 Soft Selection", "poly_soft_selection"),
            ],
        ),
        RadialMenuProfile(
            profile_id="submenu_graphite_constrain",
            title="石墨约束模式",
            subtitle="子菜单 · Constraints",
            slots={
                "N": _b("无约束 None", "graphite_constrain_none"),
                "E": _b("边约束 Edge", "graphite_constrain_edge"),
                "S": _b("面约束 Face", "graphite_constrain_face"),
                "W": _b("法线约束", "graphite_constrain_normal"),
            },
        ),
        RadialMenuProfile(
            profile_id="submenu_visibility",
            title="显示与孤立",
            subtitle="子菜单 · Visibility",
            slots={
                "N": _b("孤立选择", "toggle_isolate"),
                "NE": _b("隐藏选中", "hide_selected"),
                "E": _b("隐藏未选", "hide_unselected"),
                "SE": _b("取消隐藏全部", "unhide_all"),
                "S": _b("冻结选中", "freeze_selected"),
                "SW": _b("全部解冻", "unfreeze_all"),
                "W": _b("半透明 X-Ray", "toggle_xray"),
                "NW": _b("背面消隐", "toggle_backface_cull"),
            },
        ),
        RadialMenuProfile(
            profile_id="submenu_views",
            title="视图切换",
            subtitle="子菜单 · Views",
            slots={
                "N": _b("顶视图 Top", "view_top"),
                "NE": _b("透视图 Persp", "view_perspective"),
                "E": _b("右视图 Right", "view_right"),
                "SE": _b("底视图 Bottom", "view_bottom"),
                "S": _b("前视图 Front", "view_front"),
                "SW": _b("后视图 Back", "view_back"),
                "W": _b("左视图 Left", "view_left"),
                "NW": _b("正交 Ortho", "view_ortho"),
            },
            extra_items=[
                _b("相机视图 Camera", "view_camera"),
                _b("安全框切换 (Shift+F)", "toggle_safeframes"),
                _b("最大化视口 (Alt+W)", "toggle_maximize_viewport"),
                _b("聚焦选中 (Z)", "zoom_extents_sel"),
            ],
        ),
        RadialMenuProfile(
            profile_id="submenu_shading",
            title="视口着色",
            subtitle="子菜单 · Shading",
            slots={
                "N": _b("线框切换 F3", "toggle_wireframe"),
                "NE": _b("边面显示 F4", "toggle_edged_faces"),
                "E": _b("默认着色", "shading_default"),
                "SE": _b("黏土 Clay", "shading_clay"),
                "S": _b("面片 Facets", "shading_facets"),
                "SW": _b("半透明 X-Ray", "toggle_xray"),
                "W": _b("统计信息 7", "toggle_stats"),
                "NW": _b("网格切换 G", "toggle_grid"),
            },
        ),
        RadialMenuProfile(
            profile_id="submenu_pivot",
            title="枢轴与变换",
            subtitle="子菜单 · Pivot",
            slots={
                "N": _b("居中枢轴", "center_pivot"),
                "NE": _b("轴到底部", "pivot_to_bottom"),
                "E": _b("轴归零原点", "pivot_to_origin"),
                "SE": _b("仅影响轴", "toggle_pivot_only"),
                "S": _b("重置变换", "reset_xform"),
                "SW": _b("局部坐标", "coordsys_local"),
                "W": _b("世界坐标", "coordsys_world"),
                "NW": _b("万向节坐标", "coordsys_gimbal"),
            },
        ),
        RadialMenuProfile(
            profile_id="submenu_poly_cut",
            title="切割与平面化",
            subtitle="子菜单 · Cut / Planar",
            slots={
                "N": _b("切割 Cut", "poly_cut"),
                "NE": _b("快速切片", "poly_quickslice"),
                "E": _b("切片平面", "poly_slice_plane"),
                "SE": _b("最佳平面化", "poly_make_planar"),
                "S": _b("X 轴平面化", "poly_planar_x"),
                "SW": _b("Y 轴平面化", "poly_planar_y"),
                "W": _b("Z 轴平面化", "poly_planar_z"),
                "NW": _b("松弛 Relax", "poly_relax", "快速松弛", "poly_relax_settings", "松弛数值面板"),
            },
        ),
        RadialMenuProfile(
            profile_id="submenu_edge_select",
            title="边选择扩展",
            subtitle="子菜单 · Edge Select",
            slots={
                "N": _b("循环 Loop", "poly_loop"),
                "NE": _b("扩大选择", "poly_grow"),
                "E": _b("环形 Ring", "poly_ring"),
                "SE": _b("缩小选择", "poly_shrink"),
                "S": _b("边界转边", "poly_border_to_edge"),
                "SW": _b("转多边形", "convert_sel_poly"),
                "W": _b("转顶点", "convert_sel_vertex"),
                "NW": _b("软选择开关", "poly_soft_selection"),
            },
        ),
    ]
    return {p.profile_id: p for p in profiles}


def create_default_hotbox_zones() -> dict[str, HotboxZoneProfile]:
    """Build the 5-zone Maya-style Full Hotbox layout."""
    zones = [
        HotboxZoneProfile(
            zone_id="CENTER",
            title="视口与相机 · View",
            items=[
                _b("透视图 Perspective", "view_perspective"),
                _b("顶视图 Top", "view_top"),
                _b("前视图 Front", "view_front"),
                _b("左视图 Left", "view_left"),
                _b("正交视图 Ortho", "view_ortho"),
                _b("聚焦选中 Zoom Sel", "zoom_extents_sel"),
                _b("最大化视口 Alt+W", "toggle_maximize_viewport"),
            ],
        ),
        HotboxZoneProfile(
            zone_id="NORTH",
            title="显示与着色 · Display",
            items=[
                _b("线框 / 着色 (F3)", "toggle_wireframe"),
                _b("边面显示 (F4)", "toggle_edged_faces"),
                _b("孤立选择 Isolate", "toggle_isolate"),
                _b("黏土着色 Clay", "shading_clay"),
                _b("网格显示 (G)", "toggle_grid"),
                _b("统计信息 (7)", "toggle_stats"),
                _b("隐藏选中 Hide", "hide_selected"),
                _b("全部取消隐藏", "unhide_all"),
            ],
        ),
        HotboxZoneProfile(
            zone_id="SOUTH",
            title="层级与枢轴 · Pivot",
            items=[
                _b("对象模式 (0)", "subobj_object"),
                _b("顶点 Vertex (1)", "subobj_vertex"),
                _b("边 Edge (2)", "subobj_edge"),
                _b("多边形 Face (4)", "subobj_polygon"),
                _b("居中枢轴 Pivot", "center_pivot"),
                _b("轴到底部 Bottom", "pivot_to_bottom"),
                _b("重置变换 XForm", "reset_xform"),
                _b("切回原生四元菜单", "switch_to_quad_menu"),
            ],
        ),
        HotboxZoneProfile(
            zone_id="WEST",
            title="多边形建模 · Modeling",
            items=[
                _b("转可编辑多边形", "convert_to_poly"),
                _b("添加 Edit Poly", "mod_edit_poly"),
                _b("添加 TurboSmooth", "mod_turbosmooth"),
                _b("添加 Symmetry", "mod_symmetry"),
                _b("添加 Shell", "mod_shell"),
                _b("挤出 Extrude", "poly_extrude", "拖动挤出", "poly_extrude_settings", "挤出数值面板"),
                _b("切角 Chamfer", "poly_chamfer", "拖动切角", "poly_chamfer_settings", "切角数值面板"),
                _b("连接 Connect", "poly_connect", "快速连接", "poly_connect_settings", "连接数值面板"),
            ],
        ),
        HotboxZoneProfile(
            zone_id="EAST",
            title="创建与配置 · Create",
            items=[
                _b("长方体 Box", "create_box_interactive", "交互创建", "create_box", "原点直出"),
                _b("球体 Sphere", "create_sphere_interactive", "交互创建", "create_sphere", "原点直出"),
                _b("圆柱 Cylinder", "create_cylinder_interactive", "交互创建", "create_cylinder", "原点直出"),
                _b("平面 Plane", "create_plane_interactive", "交互创建", "create_plane", "原点直出"),
                _b("视图相机 Camera", "camera_from_view"),
                _b("克隆对象 Clone", "clone_object"),
                _b("热盒设置 Settings", "open_settings"),
            ],
        ),
    ]
    return {z.zone_id: z for z in zones}


def create_default_config() -> HotboxConfig:
    """Create a fresh default HotboxConfig instance."""
    return HotboxConfig(
        schema_version=CONFIG_SCHEMA_VERSION,
        plugin_version=PLUGIN_VERSION,
        settings=HotboxSettings(),
        radial_profiles=create_default_radial_profiles(),
        hotbox_zones=create_default_hotbox_zones(),
    )


class ConfigManager:
    """Loads, validates, and persists MaxHotbox configuration JSON."""

    def __init__(self, config_path: Path | None = None) -> None:
        self._path = config_path or (get_user_data_dir() / "config.json")
        self._config: HotboxConfig = create_default_config()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def config(self) -> HotboxConfig:
        return self._config

    def load(self) -> HotboxConfig:
        logger = get_logger()
        if not self._path.exists():
            self._config = create_default_config()
            return self._config
        try:
            raw_text = self._path.read_text(encoding="utf-8")
            raw_data = json.loads(raw_text)
            self._config = HotboxConfig.from_dict(raw_data)
            logger.info("Loaded config from %s", self._path)
        except Exception as exc:
            logger.warning("Failed to load config %s (%s); using defaults", self._path, exc)
            self._config = create_default_config()
        return self._config

    def save(self, config: HotboxConfig | None = None) -> Path:
        if config is not None:
            self._config = config
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self._config.to_dict(), ensure_ascii=False, indent=2)
        tmp_path = self._path.with_suffix(".json.tmp")
        tmp_path.write_text(payload, encoding="utf-8")
        tmp_path.replace(self._path)
        return self._path

    def reset_to_defaults(self, persist: bool = True) -> HotboxConfig:
        self._config = create_default_config()
        if persist:
            self.save()
        return self._config

    def export_to(self, target_path: Path) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self._config.to_dict(), ensure_ascii=False, indent=2)
        target_path.write_text(payload, encoding="utf-8")

    def import_from(self, source_path: Path, persist: bool = True) -> HotboxConfig:
        raw_data = json.loads(source_path.read_text(encoding="utf-8"))
        self._config = HotboxConfig.from_dict(raw_data)
        if persist:
            self.save()
        return self._config

    def clone_config(self) -> HotboxConfig:
        return copy.deepcopy(self._config)
