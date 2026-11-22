"""PySide6 Maya-style radial marking menu overlay styled for Autodesk 3ds Max 2026."""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from .config import HotboxSettings, MenuItem
from .constants import DIRECTIONS_8, THEMES
from .geometry import (
    ItemButtonGeometry,
    Point2D,
    Rect2D,
    clamp_overlay_origin,
)
from .state_machine import RadialSessionState


def _hex_color(hex_str: str, alpha: int = 255) -> QtGui.QColor:
    c = QtGui.QColor(hex_str)
    c.setAlpha(max(0, min(255, alpha)))
    return c


class RadialMenuOverlay(QtWidgets.QWidget):
    """High-FPS, click-through PySide6 overlay matching 3ds Max 2026 native UI."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        flags = (
            QtCore.Qt.WindowType.Tool
            | QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowDoesNotAcceptFocus
            | QtCore.Qt.WindowType.WindowTransparentForInput
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
        )
        super().__init__(parent, flags)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._state: RadialSessionState | None = None
        self._settings: HotboxSettings = HotboxSettings()
        self._top_left: Point2D = Point2D(0.0, 0.0)
        self._last_layout_revision: int = -1
        self._submenu_dwell_progress: float = 0.0

    def set_submenu_dwell_progress(self, progress: float) -> None:
        clamped = max(0.0, min(1.0, progress))
        if abs(clamped - self._submenu_dwell_progress) >= 0.04:
            self._submenu_dwell_progress = clamped
            if self.isVisible():
                self.update()

    def sync_state(
        self,
        state: RadialSessionState | None,
        settings: HotboxSettings,
    ) -> None:
        """Reposition ONLY when layout_revision changes; otherwise repaint in-place for 60fps+."""
        self._state = state
        self._settings = settings

        if state is None:
            self._last_layout_revision = -1
            self._submenu_dwell_progress = 0.0
            if self.isVisible():
                self.hide()
            return

        # Recompute & move the Win32 layered window ONLY on session start or submenu transition!
        if state.layout_revision != self._last_layout_revision or not self.isVisible():
            self._last_layout_revision = state.layout_revision
            self._submenu_dwell_progress = 0.0
            self._relayout_window(state, settings)

        self.update()

    def _relayout_window(self, state: RadialSessionState, settings: HotboxSettings) -> None:
        scale = settings.ui_scale
        # Compute tight bounding box covering origin, all radial slots, and extra items
        min_x = state.origin.x - 140.0 * scale
        max_x = state.origin.x + 140.0 * scale
        min_y = state.origin.y - 100.0 * scale
        max_y = state.origin.y + 100.0 * scale

        for geom in list(state.slot_geoms.values()) + list(state.extra_geoms):
            r = geom.full_rect
            min_x = min(min_x, r.x)
            max_x = max(max_x, r.x + r.width)
            min_y = min(min_y, r.y)
            max_y = max(max_y, r.y + r.height)

        pad = 36.0 * scale
        min_x -= pad
        max_x += pad
        min_y -= pad
        max_y += pad

        width = max(420, int(max_x - min_x))
        height = max(340, int(max_y - min_y))

        screen = QtGui.QGuiApplication.screenAt(
            QtCore.QPoint(int(state.origin.x), int(state.origin.y))
        ) or QtGui.QGuiApplication.primaryScreen()

        if screen is not None:
            avail = screen.availableGeometry()
            screen_rect = Rect2D(
                float(avail.x()),
                float(avail.y()),
                float(avail.width()),
                float(avail.height()),
            )
        else:
            screen_rect = Rect2D(0.0, 0.0, 1920.0, 1080.0)

        center_pt = Point2D((min_x + max_x) * 0.5, (min_y + max_y) * 0.5)
        clamped = clamp_overlay_origin(
            origin=center_pt,
            overlay_width=float(width),
            overlay_height=float(height),
            screen_rect=screen_rect,
        )
        self._top_left = clamped
        self.setGeometry(int(clamped.x), int(clamped.y), width, height)
        self.setWindowOpacity(settings.opacity)
        if not self.isVisible():
            self.show()

    def _to_local(self, pt: Point2D) -> QtCore.QPointF:
        return QtCore.QPointF(pt.x - self._top_left.x, pt.y - self._top_left.y)

    def _rect_to_local(self, rect: Rect2D) -> QtCore.QRectF:
        return QtCore.QRectF(
            rect.x - self._top_left.x,
            rect.y - self._top_left.y,
            rect.width,
            rect.height,
        )

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        if self._state is None:
            return

        state = self._state
        settings = self._settings
        palette = THEMES.get(settings.theme, THEMES["max2026_native"])
        scale = settings.ui_scale
        bg_alpha = int(palette.get("bg_alpha", "240"))

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)

        origin_pt = self._to_local(state.origin)
        cursor_pt = self._to_local(state.cursor)

        # 1. Subtle deadzone circle & crisp Maya/Max vector gesture line
        deadzone = settings.deadzone_radius * scale
        painter.setPen(QtGui.QPen(_hex_color(palette["border"], 120), 1.0))
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        painter.drawEllipse(origin_pt, deadzone, deadzone)

        if settings.show_gesture_trail and state.hit.distance > 4.0:
            # Clamp endpoint visually inside overlay bounds so trail never clips abruptly
            line_pen = QtGui.QPen(_hex_color(palette["trail"], 215), 1.6 * scale)
            line_pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
            painter.setPen(line_pen)
            painter.drawLine(origin_pt, cursor_pt)

            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(_hex_color(palette["trail"], 235))
            painter.drawEllipse(cursor_pt, 3.2 * scale, 3.2 * scale)

        # 2. Radial 8-direction buttons (with optional right-side Option Box [□] or Submenu ▸)
        item_font = QtGui.QFont("Microsoft YaHei UI", max(8, int(9 * scale)))
        painter.setFont(item_font)

        for direction in DIRECTIONS_8:
            item = state.profile.slots.get(direction)
            geom = state.slot_geoms.get(direction)
            if item is None or geom is None or not item.enabled or not item.label:
                continue
            is_selected = state.hit.kind == "direction" and state.hit.direction == direction
            is_opt_hover = is_selected and state.hit.is_option_box
            self._draw_item_button(
                painter=painter,
                geom=geom,
                item=item,
                is_main_hover=is_selected and not is_opt_hover,
                is_opt_hover=is_opt_hover,
                palette=palette,
                bg_alpha=bg_alpha,
                scale=scale,
                dwell_progress=self._submenu_dwell_progress if (is_selected and item.command_type == "submenu") else 0.0,
            )

        # 3. Center Hub (flat 3ds Max 2026 style)
        hub_w = 118.0 * scale
        hub_h = 40.0 * scale
        hub_rect = QtCore.QRectF(
            origin_pt.x() - hub_w * 0.5,
            origin_pt.y() - hub_h * 0.5,
            hub_w,
            hub_h,
        )
        is_center = state.hit.kind == "center"
        painter.setBrush(_hex_color(palette["hub_bg"], min(252, bg_alpha + 8)))
        painter.setPen(
            QtGui.QPen(
                _hex_color(palette["accent"] if is_center else palette["border"], 235),
                1.2,
            )
        )
        painter.drawRoundedRect(hub_rect, 3.0 * scale, 3.0 * scale)

        hub_title_font = QtGui.QFont("Microsoft YaHei UI", max(8, int(8.5 * scale)))
        hub_title_font.setWeight(QtGui.QFont.Weight.DemiBold)
        painter.setFont(hub_title_font)
        painter.setPen(_hex_color(palette["text"], 250))
        title_prefix = "‹ " if state.profile_stack else ""
        painter.drawText(
            QtCore.QRectF(hub_rect.x() + 4, hub_rect.y() + 3 * scale, hub_rect.width() - 8, 18 * scale),
            QtCore.Qt.AlignmentFlag.AlignCenter,
            f"{title_prefix}{state.profile.title}",
        )

        sub_font = QtGui.QFont("Microsoft YaHei UI", max(7, int(7.5 * scale)))
        painter.setFont(sub_font)
        painter.setPen(_hex_color(palette["text_muted"], 225))
        sub_text = self._compute_status_hint(state)
        painter.drawText(
            QtCore.QRectF(hub_rect.x() + 4, hub_rect.y() + 20 * scale, hub_rect.width() - 8, 16 * scale),
            QtCore.Qt.AlignmentFlag.AlignCenter,
            sub_text,
        )

        # 4. Extra vertical stack below South
        extras = state.profile.enabled_extra_items()
        if extras and state.extra_geoms:
            # Subtle container frame around the extra stack (Max Quad/Menu feel)
            first_r = self._rect_to_local(state.extra_geoms[0].full_rect)
            last_r = self._rect_to_local(state.extra_geoms[-1].full_rect)
            stack_frame = QtCore.QRectF(
                first_r.x() - 3 * scale,
                first_r.y() - 3 * scale,
                first_r.width() + 6 * scale,
                (last_r.bottom() - first_r.top()) + 6 * scale,
            )
            painter.setBrush(_hex_color(palette["bg"], bg_alpha))
            painter.setPen(QtGui.QPen(_hex_color(palette["border_outer"], 220), 1.0))
            painter.drawRoundedRect(stack_frame, 3.0 * scale, 3.0 * scale)

            painter.setFont(item_font)
            for idx, (item, geom) in enumerate(zip(extras, state.extra_geoms)):
                is_selected = state.hit.kind == "extra" and state.hit.extra_index == idx
                is_opt_hover = is_selected and state.hit.is_option_box
                self._draw_item_button(
                    painter=painter,
                    geom=geom,
                    item=item,
                    is_main_hover=is_selected and not is_opt_hover,
                    is_opt_hover=is_opt_hover,
                    palette=palette,
                    bg_alpha=bg_alpha,
                    scale=scale,
                    dwell_progress=0.0,
                )

        painter.end()

    @staticmethod
    def _compute_status_hint(state: RadialSessionState) -> str:
        sel = state.selected_item()
        if sel is not None:
            if state.hit.is_option_box and sel.has_option_box():
                return sel.option_tooltip or "□ 数值参数面板"
            if sel.command_type == "submenu":
                return "悬停展开子菜单 ▸"
            if sel.tooltip:
                return sel.tooltip
        if state.profile_stack:
            return "Backspace 返回上级"
        return state.profile.subtitle or state.trigger

    def _draw_item_button(
        self,
        painter: QtGui.QPainter,
        geom: ItemButtonGeometry,
        item: MenuItem,
        is_main_hover: bool,
        is_opt_hover: bool,
        palette: dict[str, str],
        bg_alpha: int,
        scale: float,
        dwell_progress: float,
    ) -> None:
        radius = 3.0 * scale
        full_rect = self._rect_to_local(geom.full_rect)
        main_rect = self._rect_to_local(geom.main_rect)
        any_hover = is_main_hover or is_opt_hover

        # Outer dark crisp border (native Max 2026 look)
        painter.setPen(QtGui.QPen(_hex_color(palette["border_outer"], 235), 1.0))
        painter.setBrush(_hex_color(palette["panel"], bg_alpha))
        painter.drawRoundedRect(full_rect, radius, radius)

        # Main button area
        if is_main_hover:
            painter.setBrush(_hex_color(palette["panel_hover"], 248))
            painter.setPen(QtGui.QPen(_hex_color(palette["border_hover"], 255), 1.1))
        else:
            painter.setBrush(_hex_color(palette["panel"], bg_alpha))
            painter.setPen(QtGui.QPen(_hex_color(palette["border"], 215), 1.0))
        painter.drawRoundedRect(main_rect, radius, radius)

        # Submenu dwell progress accent bar along bottom of main button
        if dwell_progress > 0.01:
            bar_w = (main_rect.width() - 4.0) * dwell_progress
            bar_rect = QtCore.QRectF(main_rect.x() + 2.0, main_rect.bottom() - 2.5 * scale, bar_w, 2.0 * scale)
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(_hex_color(palette["border_hover"], 255))
            painter.drawRect(bar_rect)

        # Main label text
        text_color = "#FFFFFF" if is_main_hover else palette["text"]
        painter.setPen(_hex_color(text_color, 255))
        if item.command_type == "submenu":
            text_rect = main_rect.adjusted(8 * scale, 0, -18 * scale, 0)
            painter.drawText(text_rect, QtCore.Qt.AlignmentFlag.AlignCenter, item.label)
            # Crisp right-side submenu triangle ▸
            tri_x = main_rect.right() - 10 * scale
            tri_y = main_rect.center().y()
            tri = QtGui.QPolygonF(
                [
                    QtCore.QPointF(tri_x - 3 * scale, tri_y - 4 * scale),
                    QtCore.QPointF(tri_x + 3 * scale, tri_y),
                    QtCore.QPointF(tri_x - 3 * scale, tri_y + 4 * scale),
                ]
            )
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(_hex_color("#FFFFFF" if is_main_hover else palette["submenu_tag"], 235))
            painter.drawPolygon(tri)
        else:
            painter.drawText(
                main_rect.adjusted(6 * scale, 0, -6 * scale, 0),
                QtCore.Qt.AlignmentFlag.AlignCenter,
                item.label,
            )

        # Right-side Maya Option Box [□]
        if geom.option_rect is not None:
            opt_rect = self._rect_to_local(geom.option_rect)
            if is_opt_hover:
                painter.setBrush(_hex_color(palette["option_hover"], 250))
                painter.setPen(QtGui.QPen(_hex_color(palette["border_hover"], 255), 1.2))
            else:
                painter.setBrush(_hex_color(palette["option_bg"], bg_alpha))
                painter.setPen(QtGui.QPen(_hex_color(palette["border"], 220), 1.0))
            painter.drawRoundedRect(opt_rect, radius, radius)

            # Crisp Maya-style Option Box square icon [□]
            sq = 8.0 * scale
            cx = opt_rect.center().x()
            cy = opt_rect.center().y()
            sq_rect = QtCore.QRectF(cx - sq * 0.5, cy - sq * 0.5, sq, sq)
            icon_color = "#FFFFFF" if (is_opt_hover or any_hover) else palette["text_muted"]
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            painter.setPen(QtGui.QPen(_hex_color(icon_color, 240), 1.25 * scale))
            painter.drawRect(sq_rect)
