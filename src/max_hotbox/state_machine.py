"""Decoupled interaction state machine for multi-level radial marking menus & 5-zone hotbox."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .config import HotboxConfig, HotboxZoneProfile, MenuItem, RadialMenuProfile
from .context import MaxContext, resolve_profile_id
from .geometry import (
    ItemButtonGeometry,
    Point2D,
    RadialHitResult,
    Rect2D,
    compute_back_button_rect,
    compute_extra_item_geometries,
    compute_radial_slot_geometries,
    hit_test_hotbox_zone,
    hit_test_radial,
)


@dataclass
class RadialHistoryEntry:
    profile: RadialMenuProfile
    origin: Point2D
    entered_direction: str | None = None
    entered_submenu_id: str = ""


@dataclass
class RadialSessionState:
    """Live state of an active radial marking menu gesture."""

    trigger: str
    origin: Point2D
    cursor: Point2D
    profile: RadialMenuProfile
    profile_stack: list[RadialHistoryEntry] = field(default_factory=list)
    hit: RadialHitResult = field(default_factory=lambda: RadialHitResult(kind="center"))
    slot_geoms: dict[str, ItemButtonGeometry] = field(default_factory=dict)
    extra_geoms: list[ItemButtonGeometry] = field(default_factory=list)
    back_rect: Rect2D | None = None
    blocked_reenter_key: str | None = None
    layout_revision: int = 1
    source_hwnd: int = 0

    def current_submenu_key(self) -> str | None:
        item = self.selected_item()
        if item is not None and item.command_type == "submenu" and item.submenu_id:
            return f"{self.profile.profile_id}:{self.hit.direction}:{item.submenu_id}"
        return None

    def selected_item(self) -> MenuItem | None:
        if self.hit.kind == "direction" and self.hit.direction:
            item = self.profile.slots.get(self.hit.direction)
            if item and item.enabled and item.label:
                return item
        elif self.hit.kind == "extra" and self.hit.extra_index is not None:
            extras = self.profile.enabled_extra_items()
            if 0 <= self.hit.extra_index < len(extras):
                return extras[self.hit.extra_index]
        return None


@dataclass
class FullHotboxSessionState:
    """Live state of an active 5-zone Maya-style Hotbox."""

    origin: Point2D
    cursor: Point2D
    active_zone: str = "CENTER"
    hovered_item: MenuItem | None = None
    hovered_is_option: bool = False
    layout_revision: int = 1
    source_hwnd: int = 0


class HotboxStateMachine:
    """Pure-Python interaction state machine coordinating gestures, submenus, and Option Boxes."""

    def __init__(
        self,
        config_getter: Callable[[], HotboxConfig],
        context_getter: Callable[[], MaxContext],
        on_radial_update: Callable[[RadialSessionState | None], None] | None = None,
        on_hotbox_update: Callable[[FullHotboxSessionState | None], None] | None = None,
        on_execute_item: Callable[[MenuItem, bool], None] | None = None,
    ) -> None:
        self._get_config = config_getter
        self._get_context = context_getter
        self._on_radial_update = on_radial_update
        self._on_hotbox_update = on_hotbox_update
        self._on_execute_item = on_execute_item

        self._radial: RadialSessionState | None = None
        self._hotbox: FullHotboxSessionState | None = None
        self._rev_counter: int = 0

    @property
    def radial_state(self) -> RadialSessionState | None:
        return self._radial

    @property
    def hotbox_state(self) -> FullHotboxSessionState | None:
        return self._hotbox

    @property
    def is_active(self) -> bool:
        return self._radial is not None or self._hotbox is not None

    @property
    def active_mode(self) -> str | None:
        if self._radial is not None:
            return "radial"
        if self._hotbox is not None:
            return "hotbox"
        return None

    def _next_revision(self) -> int:
        self._rev_counter += 1
        return self._rev_counter

    def should_intercept_rmb(self, trigger: str) -> bool:
        """Check whether an RMB press with given modifier trigger should be intercepted."""
        cfg = self._get_config()
        if not cfg.settings.enabled:
            return False
        if not cfg.settings.enabled_triggers.get(trigger, False):
            return False
        if cfg.settings.safe_tool_mode_guard:
            ctx = self._get_context()
            if not ctx.is_safe_for_rmb_interception():
                return False
        return True

    def _build_radial_geoms(
        self,
        origin: Point2D,
        profile: RadialMenuProfile,
        cfg: HotboxConfig,
    ) -> tuple[dict[str, ItemButtonGeometry], list[ItemButtonGeometry]]:
        scale = cfg.settings.ui_scale
        radius = cfg.settings.menu_radius * scale

        slot_opt_flags = {
            direction: item.has_option_box()
            for direction, item in profile.slots.items()
            if item.enabled and item.label
        }
        slot_geoms = compute_radial_slot_geometries(
            origin=origin,
            radius=radius,
            slot_option_flags=slot_opt_flags,
            pill_width=136.0 * scale,
            pill_height=28.0 * scale,
            option_width=26.0 * scale,
        )

        extras = profile.enabled_extra_items()
        extra_geoms = compute_extra_item_geometries(
            origin=origin,
            radius=radius,
            extra_option_flags=[item.has_option_box() for item in extras],
            item_width=192.0 * scale,
            item_height=25.0 * scale,
            gap=2.0 * scale,
            top_padding=28.0 * scale,
            option_width=26.0 * scale,
        )
        return slot_geoms, extra_geoms

    def begin_radial(self, trigger: str, origin: Point2D, source_hwnd: int = 0) -> bool:
        """Start a radial marking menu session at `origin`."""
        if self.is_active:
            return False
        if not self.should_intercept_rmb(trigger):
            return False

        cfg = self._get_config()
        ctx = self._get_context()
        profile_id = resolve_profile_id(trigger, ctx)
        profile = cfg.radial_profiles.get(profile_id)
        if profile is None:
            profile = cfg.radial_profiles.get("rmb_empty")
        if profile is None:
            return False

        slot_geoms, extra_geoms = self._build_radial_geoms(origin, profile, cfg)
        self._radial = RadialSessionState(
            trigger=trigger,
            origin=origin,
            cursor=origin,
            profile=profile,
            slot_geoms=slot_geoms,
            extra_geoms=extra_geoms,
            layout_revision=self._next_revision(),
            source_hwnd=source_hwnd,
        )
        self._emit_radial()
        return True

    def update_radial_cursor(self, cursor: Point2D) -> RadialHitResult | None:
        """Update cursor position during a radial marking menu gesture."""
        if self._radial is None:
            return None

        # Skip redundant work if cursor didn't move at all
        if cursor.x == self._radial.cursor.x and cursor.y == self._radial.cursor.y:
            return self._radial.hit

        cfg = self._get_config()
        scale = cfg.settings.ui_scale
        hit = hit_test_radial(
            origin=self._radial.origin,
            cursor=cursor,
            deadzone_radius=cfg.settings.deadzone_radius * scale,
            sector_count=8,
            available_directions=self._radial.profile.enabled_directions(),
            slot_geoms=self._radial.slot_geoms,
            extra_geoms=self._radial.extra_geoms,
            back_rect=self._radial.back_rect,
        )
        self._radial.cursor = cursor
        self._radial.hit = hit
        # Clear submenu re-entry lock the moment the cursor leaves the just-exited submenu button
        if (
            self._radial.blocked_reenter_key is not None
            and self._radial.current_submenu_key() != self._radial.blocked_reenter_key
        ):
            self._radial.blocked_reenter_key = None
        self._emit_radial()
        return hit

    def enter_submenu_if_selected(self, new_origin: Point2D | None = None) -> bool:
        """If the currently hovered item is a submenu, pivot into it at `new_origin`."""
        if self._radial is None:
            return False
        cur_key = self._radial.current_submenu_key()
        if cur_key is None or cur_key == self._radial.blocked_reenter_key:
            return False
        item = self._radial.selected_item()
        if item is None or item.command_type != "submenu" or not item.submenu_id:
            return False
        cfg = self._get_config()
        sub_profile = cfg.radial_profiles.get(item.submenu_id)
        if sub_profile is None:
            return False

        # Anchor submenu cleanly at the cursor (just like Maya's hierarchical marking menu)
        origin = new_origin or self._radial.cursor
        self._radial.profile_stack.append(
            RadialHistoryEntry(
                profile=self._radial.profile,
                origin=self._radial.origin,
                entered_direction=self._radial.hit.direction,
                entered_submenu_id=item.submenu_id,
            )
        )
        slot_geoms, extra_geoms = self._build_radial_geoms(origin, sub_profile, cfg)
        self._radial.profile = sub_profile
        self._radial.origin = origin
        self._radial.cursor = origin
        self._radial.hit = RadialHitResult(kind="center")
        self._radial.slot_geoms = slot_geoms
        self._radial.extra_geoms = extra_geoms
        self._radial.back_rect = compute_back_button_rect(origin, scale=cfg.settings.ui_scale)
        self._radial.blocked_reenter_key = None
        self._radial.layout_revision = self._next_revision()
        self._emit_radial()
        return True

    def step_back_submenu(self) -> bool:
        """Return to the parent radial profile and lock re-entry on the exited slot until cursor leaves it."""
        if self._radial is None or not self._radial.profile_stack:
            return False
        cfg = self._get_config()
        parent = self._radial.profile_stack.pop()
        slot_geoms, extra_geoms = self._build_radial_geoms(parent.origin, parent.profile, cfg)
        self._radial.profile = parent.profile
        self._radial.origin = parent.origin
        self._radial.slot_geoms = slot_geoms
        self._radial.extra_geoms = extra_geoms
        self._radial.back_rect = (
            compute_back_button_rect(parent.origin, scale=cfg.settings.ui_scale)
            if self._radial.profile_stack
            else None
        )
        # Prevent immediate ping-pong re-expansion while cursor is still resting on the exited submenu button
        if parent.entered_direction and parent.entered_submenu_id:
            self._radial.blocked_reenter_key = (
                f"{parent.profile.profile_id}:{parent.entered_direction}:{parent.entered_submenu_id}"
            )
        else:
            self._radial.blocked_reenter_key = None
        # Re-evaluate hit immediately against the parent layout so highlight matches cursor accurately
        scale = cfg.settings.ui_scale
        self._radial.hit = hit_test_radial(
            origin=self._radial.origin,
            cursor=self._radial.cursor,
            deadzone_radius=cfg.settings.deadzone_radius * scale,
            sector_count=8,
            available_directions=self._radial.profile.enabled_directions(),
            slot_geoms=self._radial.slot_geoms,
            extra_geoms=self._radial.extra_geoms,
            back_rect=self._radial.back_rect,
        )
        self._radial.layout_revision = self._next_revision()
        self._emit_radial()
        return True

    def end_radial(self, cursor: Point2D | None = None, execute: bool = True) -> tuple[MenuItem | None, bool]:
        """Finish the active radial session, returning (selected_item, use_option_box)."""
        if self._radial is None:
            return None, False

        if cursor is not None:
            self.update_radial_cursor(cursor)

        selected = self._radial.selected_item()
        use_option = bool(self._radial.hit.is_option_box and selected is not None and selected.has_option_box())
        self._radial = None
        self._emit_radial()

        if execute and selected is not None and selected.command_type != "submenu":
            if self._on_execute_item is not None:
                self._on_execute_item(selected, use_option)
            return selected, use_option
        return None, False

    def begin_hotbox(self, origin: Point2D, source_hwnd: int = 0) -> bool:
        """Open the Maya-style 5-zone Full Hotbox at `origin`."""
        if self.is_active:
            return False
        cfg = self._get_config()
        if not cfg.settings.enabled:
            return False
        self._hotbox = FullHotboxSessionState(
            origin=origin,
            cursor=origin,
            active_zone="CENTER",
            hovered_item=None,
            hovered_is_option=False,
            layout_revision=self._next_revision(),
            source_hwnd=source_hwnd,
        )
        self._emit_hotbox()
        return True

    def update_hotbox_cursor(
        self,
        cursor: Point2D,
        hovered_item: MenuItem | None = None,
        hovered_is_option: bool = False,
    ) -> str | None:
        """Update cursor position and active zone for the 5-zone Hotbox."""
        if self._hotbox is None:
            return None
        if (
            cursor.x == self._hotbox.cursor.x
            and cursor.y == self._hotbox.cursor.y
            and hovered_item is self._hotbox.hovered_item
            and hovered_is_option == self._hotbox.hovered_is_option
        ):
            return self._hotbox.active_zone

        cfg = self._get_config()
        scale = cfg.settings.ui_scale
        zone = hit_test_hotbox_zone(
            origin=self._hotbox.origin,
            cursor=cursor,
            center_half_width=88.0 * scale,
            center_half_height=46.0 * scale,
        )
        self._hotbox.cursor = cursor
        self._hotbox.active_zone = zone
        self._hotbox.hovered_item = hovered_item
        self._hotbox.hovered_is_option = hovered_is_option
        self._emit_hotbox()
        return zone

    def end_hotbox(
        self,
        execute: bool = True,
        explicit_item: MenuItem | None = None,
        explicit_is_option: bool | None = None,
    ) -> tuple[MenuItem | None, bool]:
        """Close the 5-zone Hotbox and optionally execute the hovered/clicked item."""
        if self._hotbox is None:
            return None, False
        chosen = explicit_item if explicit_item is not None else self._hotbox.hovered_item
        use_option = (
            bool(explicit_is_option)
            if explicit_is_option is not None
            else self._hotbox.hovered_is_option
        )
        use_option = bool(use_option and chosen is not None and chosen.has_option_box())
        self._hotbox = None
        self._emit_hotbox()

        if execute and chosen is not None and chosen.enabled and chosen.command_type != "submenu":
            if self._on_execute_item is not None:
                self._on_execute_item(chosen, use_option)
            return chosen, use_option
        return None, False

    def cancel(self) -> None:
        """Cancel any active radial menu or full hotbox without executing commands."""
        if self._radial is not None:
            self._radial = None
            self._emit_radial()
        if self._hotbox is not None:
            self._hotbox = None
            self._emit_hotbox()

    def get_hotbox_zones(self) -> dict[str, HotboxZoneProfile]:
        return self._get_config().hotbox_zones

    def _emit_radial(self) -> None:
        if self._on_radial_update is not None:
            self._on_radial_update(self._radial)

    def _emit_hotbox(self) -> None:
        if self._on_hotbox_update is not None:
            self._on_hotbox_update(self._hotbox)
