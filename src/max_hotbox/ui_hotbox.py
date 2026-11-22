"""PySide6 Maya-style 5-zone Full Hotbox overlay styled for Autodesk 3ds Max 2026."""

from __future__ import annotations

from typing import Callable

from PySide6 import QtCore, QtGui, QtWidgets

from .config import HotboxSettings, HotboxZoneProfile, MenuItem
from .constants import THEMES
from .geometry import (
    ItemButtonGeometry,
    Point2D,
    Rect2D,
    clamp_overlay_origin,
    make_button_geometry,
)
from .state_machine import FullHotboxSessionState


def _hex_color(hex_str: str, alpha: int = 255) -> QtGui.QColor:
    c = QtGui.QColor(hex_str)
    c.setAlpha(max(0, min(255, alpha)))
    return c


class FullHotboxOverlay(QtWidgets.QWidget):
    """Native-styled 5-zone Hotbox supporting hold-and-release, click-to-run, and Option Boxes [□]."""

    def __init__(
        self,
        on_item_clicked: Callable[[MenuItem, bool], None] | None = None,
        on_cancel: Callable[[], None] | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        flags = (
            QtCore.Qt.WindowType.Tool
            | QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
        )
        super().__init__(parent, flags)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

        self._on_item_clicked = on_item_clicked
        self._on_cancel = on_cancel

        self._state: FullHotboxSessionState | None = None
        self._zones: dict[str, HotboxZoneProfile] = {}
        self._settings: HotboxSettings = HotboxSettings()
        self._top_left: Point2D = Point2D(0.0, 0.0)
        self._interactive_click_mode: bool = False
        self._last_layout_revision: int = -1

        # (ItemButtonGeometry in global coords, zone_id, MenuItem)
        self._item_hitboxes: list[tuple[ItemButtonGeometry, str, MenuItem]] = []
        self._zone_rects_local: dict[str, QtCore.QRectF] = {}

    def sync_state(
        self,
        state: FullHotboxSessionState | None,
        zones: dict[str, HotboxZoneProfile],
        settings: HotboxSettings,
        interactive_click_mode: bool = False,
    ) -> None:
        self._state = state
        self._zones = zones
        self._settings = settings
        self._interactive_click_mode = interactive_click_mode

        if state is None:
            self._last_layout_revision = -1
            self._item_hitboxes.clear()
            if self.isVisible():
                self.hide()
            return

        if state.layout_revision != self._last_layout_revision or not self.isVisible():
            self._last_layout_revision = state.layout_revision
            self.setAttribute(
                QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents,
                not interactive_click_mode,
            )

            scale = settings.ui_scale
            width = int(680 * scale)
            height = int(530 * scale)

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

            clamped = clamp_overlay_origin(
                origin=state.origin,
                overlay_width=float(width),
                overlay_height=float(height),
                screen_rect=screen_rect,
            )
            self._top_left = clamped
            self.setGeometry(int(clamped.x), int(clamped.y), width, height)
            self._rebuild_layout(width, height, scale)
            self.setWindowOpacity(settings.opacity)

            if not self.isVisible():
                self.show()
                if interactive_click_mode:
                    self.activateWindow()

        self.update()

    def hit_test_item(self, global_cursor: Point2D) -> tuple[MenuItem | None, bool]:
        """Return (MenuItem, is_option_box) under `global_cursor`."""
        for geom, _zone_id, item in self._item_hitboxes:
            if geom.option_rect is not None and geom.option_rect.contains(global_cursor.x, global_cursor.y):
                return item, True
            if geom.main_rect.contains(global_cursor.x, global_cursor.y):
                return item, False
        return None, False

    def _rebuild_layout(self, width: int, height: int, scale: float) -> None:
        self._item_hitboxes.clear()
        self._zone_rects_local.clear()

        pad = 8.0 * scale
        col_w = 204.0 * scale
        center_w = 224.0 * scale
        top_h = 148.0 * scale
        bottom_h = 148.0 * scale
        mid_h = height - top_h - bottom_h - pad * 4

        cx = (width - center_w) * 0.5
        cy = top_h + pad * 2

        self._zone_rects_local = {
            "NORTH": QtCore.QRectF(cx - 60 * scale, pad, center_w + 120 * scale, top_h),
            "SOUTH": QtCore.QRectF(cx - 60 * scale, height - bottom_h - pad, center_w + 120 * scale, bottom_h),
            "WEST": QtCore.QRectF(pad, cy - 28 * scale, col_w, mid_h + 56 * scale),
            "EAST": QtCore.QRectF(width - col_w - pad, cy - 28 * scale, col_w, mid_h + 56 * scale),
            "CENTER": QtCore.QRectF(cx, cy, center_w, mid_h),
        }

        header_h = 24.0 * scale
        btn_h = 24.0 * scale
        gap = 3.0 * scale
        opt_w = 24.0 * scale

        for zone_id, zrect in self._zone_rects_local.items():
            zone = self._zones.get(zone_id)
            if zone is None:
                continue
            items = zone.enabled_items()
            if not items:
                continue

            cols = 2 if zone_id in ("NORTH", "SOUTH") else 1
            inner_x = zrect.x() + 7.0 * scale
            inner_y = zrect.y() + header_h + 4.0 * scale
            inner_w = zrect.width() - 14.0 * scale
            cell_w = (inner_w - gap * (cols - 1)) / cols

            for idx, item in enumerate(items):
                row = idx // cols
                col = idx % cols
                bx = inner_x + col * (cell_w + gap)
                by = inner_y + row * (btn_h + gap)
                if by + btn_h > zrect.bottom() - 5.0 * scale:
                    break
                geom = make_button_geometry(
                    x=self._top_left.x + bx,
                    y=self._top_left.y + by,
                    width=cell_w,
                    height=btn_h,
                    has_option_box=item.has_option_box(),
                    option_width=opt_w,
                )
                self._item_hitboxes.append((geom, zone_id, item))

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._interactive_click_mode and self._state is not None:
            gp = event.globalPosition()
            cursor = Point2D(float(gp.x()), float(gp.y()))
            item, is_opt = self.hit_test_item(cursor)
            self._state.cursor = cursor
            self._state.hovered_item = item
            self._state.hovered_is_option = is_opt
            self.update()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._interactive_click_mode:
            if event.button() == QtCore.Qt.MouseButton.RightButton:
                if self._on_cancel:
                    self._on_cancel()
                return
            if event.button() == QtCore.Qt.MouseButton.LeftButton:
                gp = event.globalPosition()
                item, is_opt = self.hit_test_item(Point2D(float(gp.x()), float(gp.y())))
                if item is not None and self._on_item_clicked:
                    self._on_item_clicked(item, is_opt)
                elif self._on_cancel:
                    self._on_cancel()
                return
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.key() == QtCore.Qt.Key.Key_Escape and self._on_cancel:
            self._on_cancel()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        if self._state is None:
            return

        palette = THEMES.get(self._settings.theme, THEMES["max2026_native"])
        scale = self._settings.ui_scale
        bg_alpha = int(palette.get("bg_alpha", "240"))

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)

        # Subtle Maya quadrant guide lines
        diag_pen = QtGui.QPen(_hex_color(palette["border"], 90), 1.0)
        diag_pen.setStyle(QtCore.Qt.PenStyle.DotLine)
        painter.setPen(diag_pen)
        painter.drawLine(0, 0, self.width(), self.height())
        painter.drawLine(self.width(), 0, 0, self.height())

        header_font = QtGui.QFont("Microsoft YaHei UI", max(8, int(8.5 * scale)))
        header_font.setWeight(QtGui.QFont.Weight.DemiBold)
        item_font = QtGui.QFont("Microsoft YaHei UI", max(8, int(8.5 * scale)))

        for zone_id, zrect in self._zone_rects_local.items():
            zone = self._zones.get(zone_id)
            is_active_zone = self._state.active_zone == zone_id
            panel_bg = palette["hub_bg"] if zone_id == "CENTER" else palette["bg"]

            painter.setBrush(_hex_color(panel_bg, bg_alpha))
            painter.setPen(
                QtGui.QPen(
                    _hex_color(palette["accent"] if is_active_zone else palette["border"], 225),
                    1.3 if is_active_zone else 1.0,
                )
            )
            painter.drawRoundedRect(zrect, 4.0 * scale, 4.0 * scale)

            painter.setFont(header_font)
            painter.setPen(_hex_color(palette["accent"] if is_active_zone else palette["text_muted"], 245))
            title = zone.title if zone else zone_id
            painter.drawText(
                QtCore.QRectF(zrect.x() + 8 * scale, zrect.y() + 3 * scale, zrect.width() - 16 * scale, 20 * scale),
                QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft,
                title,
            )

        painter.setFont(item_font)
        hovered = self._state.hovered_item
        hovered_opt = self._state.hovered_is_option
        radius = 2.5 * scale

        for geom, _zone_id, item in self._item_hitboxes:
            main_r = QtCore.QRectF(
                geom.main_rect.x - self._top_left.x,
                geom.main_rect.y - self._top_left.y,
                geom.main_rect.width,
                geom.main_rect.height,
            )
            is_main_hover = hovered is item and not hovered_opt
            is_opt_hover = hovered is item and hovered_opt

            painter.setBrush(_hex_color(palette["panel_hover"] if is_main_hover else palette["panel"], 240))
            painter.setPen(QtGui.QPen(_hex_color(palette["border_hover"] if is_main_hover else palette["border"], 215), 1.0))
            painter.drawRoundedRect(main_r, radius, radius)

            painter.setPen(_hex_color("#FFFFFF" if is_main_hover else palette["text"], 255))
            painter.drawText(main_r.adjusted(6, 0, -6, 0), QtCore.Qt.AlignmentFlag.AlignCenter, item.label)

            if geom.option_rect is not None:
                opt_r = QtCore.QRectF(
                    geom.option_rect.x - self._top_left.x,
                    geom.option_rect.y - self._top_left.y,
                    geom.option_rect.width,
                    geom.option_rect.height,
                )
                painter.setBrush(_hex_color(palette["option_hover"] if is_opt_hover else palette["option_bg"], 240))
                painter.setPen(QtGui.QPen(_hex_color(palette["border_hover"] if is_opt_hover else palette["border"], 215), 1.0))
                painter.drawRoundedRect(opt_r, radius, radius)

                sq = 7.5 * scale
                sq_rect = QtCore.QRectF(opt_r.center().x() - sq * 0.5, opt_r.center().y() - sq * 0.5, sq, sq)
                painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
                painter.setPen(QtGui.QPen(_hex_color("#FFFFFF" if is_opt_hover else palette["text_muted"], 235), 1.2 * scale))
                painter.drawRect(sq_rect)

        painter.end()
