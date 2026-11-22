"""3ds Max 2026 selection, sub-object, and tool-mode context resolver."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .constants import (
    SAFE_COMMAND_MODES,
    TRIGGER_ALT_RMB,
    TRIGGER_CTRL_RMB,
    TRIGGER_CTRL_SHIFT_RMB,
    TRIGGER_RMB,
    TRIGGER_SHIFT_RMB,
    TRIGGER_SPACE_RMB,
)
from .logger import get_logger


@dataclass(frozen=True)
class MaxContext:
    """Snapshot of the active 3ds Max selection and editing state."""

    selection_count: int = 0
    object_category: str = "empty"  # empty | poly | spline | generic
    subobject_level: int = 0
    command_mode: str = "select"
    active_modifier: str = ""
    is_poly_editable: bool = False

    def is_safe_for_rmb_interception(self) -> bool:
        return self.command_mode.lower() in SAFE_COMMAND_MODES


def resolve_profile_id(trigger: str, ctx: MaxContext) -> str:
    """Choose the best radial menu profile ID for a trigger + Max context."""
    if trigger == TRIGGER_SPACE_RMB:
        return "space_rmb_maya"
    if trigger == TRIGGER_ALT_RMB:
        return "alt_rmb_viewport"
    if trigger == TRIGGER_CTRL_RMB:
        return "ctrl_rmb_select"
    if trigger == TRIGGER_CTRL_SHIFT_RMB:
        return "ctrl_shift_rmb_transform"

    if trigger == TRIGGER_SHIFT_RMB:
        if ctx.object_category == "spline" and ctx.selection_count > 0:
            if ctx.subobject_level == 1:
                return "shift_rmb_spline_vertex"
            if ctx.subobject_level == 2:
                return "shift_rmb_spline_segment"
            if ctx.subobject_level == 3:
                return "shift_rmb_spline_spline"
            return "shift_rmb_spline_object"
        if ctx.selection_count == 0 or not ctx.is_poly_editable or ctx.subobject_level == 0:
            return "shift_rmb_object"
        if ctx.subobject_level == 1:
            return "shift_rmb_vertex"
        if ctx.subobject_level == 2:
            return "shift_rmb_edge"
        if ctx.subobject_level == 3:
            return "shift_rmb_border"
        return "shift_rmb_poly"

    # Plain RMB (context-aware Maya style)
    if trigger == TRIGGER_RMB:
        if ctx.selection_count == 0:
            return "rmb_empty"
        if ctx.object_category == "spline":
            return "rmb_spline"
        return "rmb_poly"

    return "rmb_empty"


def _safe_str(value: Any) -> str:
    try:
        return str(value) if value is not None else ""
    except Exception:
        return ""


def query_max_context(rt: Any | None = None) -> MaxContext:
    """Query live 3ds Max 2026 state via pymxs.runtime safely."""
    if rt is None:
        try:
            from pymxs import runtime as rt  # type: ignore[import-not-found]
        except Exception:
            return MaxContext()

    try:
        sel_count = int(rt.selection.count)
    except Exception:
        sel_count = 0

    try:
        cmd_mode = _safe_str(rt.toolMode.commandMode).strip().lstrip("#").lower()
    except Exception:
        cmd_mode = "select"

    try:
        sub_level = int(rt.subObjectLevel) if rt.subObjectLevel is not None else 0
    except Exception:
        sub_level = 0

    if sel_count == 0:
        return MaxContext(
            selection_count=0,
            object_category="empty",
            subobject_level=0,
            command_mode=cmd_mode,
        )

    category = "generic"
    is_poly_editable = False
    active_mod_name = ""

    try:
        cur_obj = rt.modPanel.getCurrentObject()
        cur_cls = _safe_str(rt.classOf(cur_obj)).lower() if cur_obj is not None else ""
        active_mod_name = cur_cls

        if cur_cls in ("editable_poly", "edit_poly", "polymeshobject"):
            category = "poly"
            is_poly_editable = True
        elif cur_cls in ("editable_mesh", "edit_mesh"):
            category = "poly"
            is_poly_editable = True
        elif cur_cls in ("splineshape", "line", "edit_spline", "editable_spline") or "spline" in cur_cls:
            category = "spline"
        else:
            # Inspect primary selected node class/superclass
            node = rt.selection[0]
            super_cls = _safe_str(rt.superClassOf(node)).lower()
            node_cls = _safe_str(rt.classOf(node)).lower()
            if super_cls == "shape" or "spline" in node_cls:
                category = "spline"
            elif super_cls == "geometryclass":
                category = "poly"
                is_poly_editable = node_cls in ("editable_poly", "polymeshobject")
    except Exception as exc:
        get_logger().debug("Context inspection fallback: %s", exc)

    return MaxContext(
        selection_count=sel_count,
        object_category=category,
        subobject_level=sub_level,
        command_mode=cmd_mode,
        active_modifier=active_mod_name,
        is_poly_editable=is_poly_editable,
    )
