"""Pure geometric calculations for radial marking menus, option boxes, and 5-zone hotbox."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .constants import DIRECTIONS_4, DIRECTIONS_8


@dataclass(frozen=True)
class Point2D:
    x: float
    y: float


@dataclass(frozen=True)
class Rect2D:
    x: float
    y: float
    width: float
    height: float

    def contains(self, px: float, py: float, pad: float = 0.0) -> bool:
        return (
            self.x - pad <= px <= self.x + self.width + pad
            and self.y - pad <= py <= self.y + self.height + pad
        )


@dataclass(frozen=True)
class ItemButtonGeometry:
    """Full bounding rect plus optional split Maya-style right-side Option Box rect."""

    full_rect: Rect2D
    main_rect: Rect2D
    option_rect: Rect2D | None = None


@dataclass(frozen=True)
class RadialHitResult:
    """Result of hit-testing a cursor position relative to the menu origin."""

    kind: str  # "center" | "direction" | "extra" | "back"
    direction: str | None = None
    extra_index: int | None = None
    is_option_box: bool = False
    distance: float = 0.0
    angle_deg: float = 0.0


# Direction unit vectors (screen coordinates: +X right, +Y down)
_INV_SQRT2 = math.sqrt(0.5)
DIRECTION_VECTORS: dict[str, tuple[float, float]] = {
    "N": (0.0, -1.0),
    "NE": (_INV_SQRT2, -_INV_SQRT2),
    "E": (1.0, 0.0),
    "SE": (_INV_SQRT2, _INV_SQRT2),
    "S": (0.0, 1.0),
    "SW": (-_INV_SQRT2, _INV_SQRT2),
    "W": (-1.0, 0.0),
    "NW": (-_INV_SQRT2, -_INV_SQRT2),
}


def compute_angle_clockwise_from_north(dx: float, dy: float) -> float:
    """Compute angle in [0, 360) where 0 is North (0, -1) and 90 is East (1, 0)."""
    rad = math.atan2(dx, -dy)
    deg = math.degrees(rad)
    return deg % 360.0


def angle_to_direction(angle_deg: float, sector_count: int = 8) -> str:
    """Map a clockwise angle from North to an 8-way or 4-way direction."""
    if sector_count == 4:
        idx = int(((angle_deg + 45.0) % 360.0) // 90.0)
        return DIRECTIONS_4[idx]
    idx = int(((angle_deg + 22.5) % 360.0) // 45.0)
    return DIRECTIONS_8[idx]


def make_button_geometry(
    x: float,
    y: float,
    width: float,
    height: float,
    has_option_box: bool = False,
    option_width: float = 26.0,
) -> ItemButtonGeometry:
    """Create button geometry, splitting off a right-side Maya Option Box if present."""
    full = Rect2D(x, y, width, height)
    if not has_option_box:
        return ItemButtonGeometry(full_rect=full, main_rect=full, option_rect=None)

    opt_w = min(option_width, width * 0.32)
    main_w = max(10.0, width - opt_w)
    main = Rect2D(x, y, main_w, height)
    opt = Rect2D(x + main_w, y, opt_w, height)
    return ItemButtonGeometry(full_rect=full, main_rect=main, option_rect=opt)


def compute_direction_slot_centers(
    origin: Point2D,
    radius: float,
    directions: tuple[str, ...] = DIRECTIONS_8,
    horizontal_stretch: float = 1.32,
    vertical_stretch: float = 1.04,
) -> dict[str, Point2D]:
    """Return screen positions for radial button centers around `origin` without overlap."""
    centers: dict[str, Point2D] = {}
    for direction in directions:
        vx, vy = DIRECTION_VECTORS[direction]
        # Give diagonal slots slightly extra X clearance so N/NE/NW never collide
        x_mult = horizontal_stretch * (1.16 if direction in ("NE", "SE", "SW", "NW") else 1.0)
        y_mult = vertical_stretch * (0.94 if direction in ("NE", "SE", "SW", "NW") else 1.0)
        centers[direction] = Point2D(
            origin.x + vx * radius * x_mult,
            origin.y + vy * radius * y_mult,
        )
    return centers


def compute_radial_slot_geometries(
    origin: Point2D,
    radius: float,
    slot_option_flags: dict[str, bool],
    pill_width: float = 136.0,
    pill_height: float = 28.0,
    option_width: float = 26.0,
) -> dict[str, ItemButtonGeometry]:
    """Compute exact screen-space geometries for all populated radial slots."""
    centers = compute_direction_slot_centers(origin=origin, radius=radius)
    geoms: dict[str, ItemButtonGeometry] = {}
    for direction, has_opt in slot_option_flags.items():
        if direction not in centers:
            continue
        c = centers[direction]
        w = pill_width + (option_width * 0.45 if has_opt else 0.0)
        geoms[direction] = make_button_geometry(
            x=c.x - w * 0.5,
            y=c.y - pill_height * 0.5,
            width=w,
            height=pill_height,
            has_option_box=has_opt,
            option_width=option_width,
        )
    return geoms


def compute_extra_item_geometries(
    origin: Point2D,
    radius: float,
    extra_option_flags: list[bool],
    item_width: float = 188.0,
    item_height: float = 25.0,
    gap: float = 2.0,
    vertical_stretch: float = 1.04,
    top_padding: float = 28.0,
    option_width: float = 26.0,
) -> list[ItemButtonGeometry]:
    """Compute geometries for the Maya-style vertical stack below the South slot."""
    if not extra_option_flags:
        return []
    start_y = origin.y + radius * vertical_stretch + top_padding
    left_x = origin.x - item_width * 0.5
    geoms: list[ItemButtonGeometry] = []
    for idx, has_opt in enumerate(extra_option_flags):
        y = start_y + idx * (item_height + gap)
        geoms.append(
            make_button_geometry(
                x=left_x,
                y=y,
                width=item_width,
                height=item_height,
                has_option_box=has_opt,
                option_width=option_width,
            )
        )
    return geoms


def compute_extra_item_rects(
    origin: Point2D,
    radius: float,
    extra_count: int,
    item_width: float = 188.0,
    item_height: float = 25.0,
    gap: float = 2.0,
    vertical_stretch: float = 1.04,
    top_padding: float = 28.0,
) -> list[Rect2D]:
    """Convenience helper returning full Rect2D list for extra stack items."""
    geoms = compute_extra_item_geometries(
        origin=origin,
        radius=radius,
        extra_option_flags=[False] * extra_count,
        item_width=item_width,
        item_height=item_height,
        gap=gap,
        vertical_stretch=vertical_stretch,
        top_padding=top_padding,
    )
    return [g.full_rect for g in geoms]


def compute_back_button_rect(
    origin: Point2D,
    scale: float = 1.0,
) -> Rect2D:
    """Compute the non-overlapping mouse-hover '‹ 返回上级' button rect inside the inner ring."""
    w = 96.0 * scale
    h = 22.0 * scale
    return Rect2D(
        x=origin.x - w * 0.5,
        y=origin.y + 24.0 * scale,
        width=w,
        height=h,
    )


def hit_test_radial(
    origin: Point2D,
    cursor: Point2D,
    deadzone_radius: float = 28.0,
    sector_count: int = 8,
    available_directions: set[str] | None = None,
    slot_geoms: dict[str, ItemButtonGeometry] | None = None,
    extra_geoms: list[ItemButtonGeometry] | None = None,
    extra_rects: list[Rect2D] | None = None,
    back_rect: Rect2D | None = None,
) -> RadialHitResult:
    """Determine which radial slot, Option Box [□], extra item, or '‹ 返回上级' button is hit.

    Priority:
      0. Direct hit on '‹ 返回上级' button when inside a submenu.
      1. Direct hit on any radial slot's right-side Option Box [□] or main button rect.
      2. Direct hit on any extra vertical stack item (Option Box [□] or main rect).
      3. Center deadzone -> cancel.
      4. Fast Maya-style directional flick -> angle mapped to nearest radial sector.
    """
    dx = cursor.x - origin.x
    dy = cursor.y - origin.y
    dist = math.hypot(dx, dy)
    angle = compute_angle_clockwise_from_north(dx, dy) if dist > 0.0 else 0.0

    # 0. Mouse-only return to parent submenu button (inside inner ring, below center hub)
    if back_rect is not None and back_rect.contains(cursor.x, cursor.y, pad=2.0):
        return RadialHitResult(
            kind="back",
            distance=dist,
            angle_deg=angle,
        )

    # 1. Exact hit-test on radial slot buttons (enables hovering Option Box [□] accurately)
    if slot_geoms:
        for direction, geom in slot_geoms.items():
            if geom.option_rect is not None and geom.option_rect.contains(cursor.x, cursor.y, pad=2.0):
                return RadialHitResult(
                    kind="direction",
                    direction=direction,
                    is_option_box=True,
                    distance=dist,
                    angle_deg=angle,
                )
            if geom.main_rect.contains(cursor.x, cursor.y, pad=1.0):
                return RadialHitResult(
                    kind="direction",
                    direction=direction,
                    is_option_box=False,
                    distance=dist,
                    angle_deg=angle,
                )

    # 2. Exact hit-test on extra stack items below South
    if extra_geoms:
        for idx, geom in enumerate(extra_geoms):
            if geom.option_rect is not None and geom.option_rect.contains(cursor.x, cursor.y, pad=1.5):
                return RadialHitResult(
                    kind="extra",
                    extra_index=idx,
                    is_option_box=True,
                    distance=dist,
                    angle_deg=angle,
                )
            if geom.main_rect.contains(cursor.x, cursor.y, pad=1.5):
                return RadialHitResult(
                    kind="extra",
                    extra_index=idx,
                    is_option_box=False,
                    distance=dist,
                    angle_deg=angle,
                )
    elif extra_rects:
        for idx, rect in enumerate(extra_rects):
            if rect.contains(cursor.x, cursor.y, pad=1.5):
                return RadialHitResult(
                    kind="extra",
                    extra_index=idx,
                    is_option_box=False,
                    distance=dist,
                    angle_deg=angle,
                )

    # 3. Deadzone cancels cleanly
    if dist < deadzone_radius:
        return RadialHitResult(kind="center", distance=dist, angle_deg=0.0)

    # 4. Fast directional flick outside pills -> angular sector mapping
    direction = angle_to_direction(angle, sector_count=sector_count)
    if available_directions is not None and direction not in available_directions:
        best_dir: str | None = None
        best_delta = 46.0
        for candidate in available_directions:
            if candidate not in DIRECTIONS_8:
                continue
            cand_angle = DIRECTIONS_8.index(candidate) * 45.0
            diff = abs((angle - cand_angle + 180.0) % 360.0 - 180.0)
            if diff < best_delta:
                best_delta = diff
                best_dir = candidate
        if best_dir is None:
            return RadialHitResult(kind="center", distance=dist, angle_deg=angle)
        direction = best_dir

    return RadialHitResult(
        kind="direction",
        direction=direction,
        is_option_box=False,
        distance=dist,
        angle_deg=angle,
    )


def clamp_overlay_origin(
    origin: Point2D,
    overlay_width: float,
    overlay_height: float,
    screen_rect: Rect2D,
    margin: float = 8.0,
) -> Point2D:
    """Compute top-left corner for an overlay centered on `origin`, clamped to screen."""
    left = origin.x - overlay_width * 0.5
    top = origin.y - overlay_height * 0.5

    min_x = screen_rect.x + margin
    max_x = screen_rect.x + screen_rect.width - overlay_width - margin
    min_y = screen_rect.y + margin
    max_y = screen_rect.y + screen_rect.height - overlay_height - margin

    if max_x >= min_x:
        left = max(min_x, min(left, max_x))
    else:
        left = min_x

    if max_y >= min_y:
        top = max(min_y, min(top, max_y))
    else:
        top = min_y

    return Point2D(left, top)


def hit_test_hotbox_zone(
    origin: Point2D,
    cursor: Point2D,
    center_half_width: float = 82.0,
    center_half_height: float = 42.0,
) -> str:
    """Hit-test the 5-zone Maya Hotbox layout (CENTER, NORTH, SOUTH, WEST, EAST)."""
    dx = cursor.x - origin.x
    dy = cursor.y - origin.y

    if abs(dx) <= center_half_width and abs(dy) <= center_half_height:
        return "CENTER"

    norm_x = abs(dx) / max(center_half_width, 1.0)
    norm_y = abs(dy) / max(center_half_height, 1.0)

    if norm_y >= norm_x:
        return "SOUTH" if dy > 0 else "NORTH"
    return "EAST" if dx > 0 else "WEST"
