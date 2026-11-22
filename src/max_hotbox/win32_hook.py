"""Safe Win32 SetWindowSubclass manager for 3ds Max 2026 3D viewports."""

from __future__ import annotations

import ctypes
import time
import traceback
from ctypes import wintypes
from typing import Any, Callable

from .constants import (
    SUBCLASS_ID,
    TRIGGER_ALT_RMB,
    TRIGGER_CTRL_RMB,
    TRIGGER_CTRL_SHIFT_RMB,
    TRIGGER_RMB,
    TRIGGER_SHIFT_RMB,
    TRIGGER_SPACE_RMB,
    VK_BACK,
    VK_CONTROL,
    VK_ESCAPE,
    VK_LBUTTON,
    VK_MBUTTON,
    VK_MENU,
    VK_SHIFT,
    VK_SPACE,
    WM_CANCELMODE,
    WM_CAPTURECHANGED,
    WM_CONTEXTMENU,
    WM_KEYDOWN,
    WM_KEYUP,
    WM_KILLFOCUS,
    WM_LBUTTONDOWN,
    WM_NCDESTROY,
    WM_RBUTTONDOWN,
    WM_RBUTTONUP,
    WM_SYSKEYDOWN,
    WM_SYSKEYUP,
)
from .logger import get_logger

UINT_PTR = ctypes.c_size_t
LONG_PTR = ctypes.c_ssize_t

SUBCLASSPROC = ctypes.WINFUNCTYPE(
    LONG_PTR,
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
    UINT_PTR,
    UINT_PTR,
)


def _init_win32_apis() -> tuple[Any, Any]:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    comctl32 = ctypes.WinDLL("comctl32", use_last_error=True)

    comctl32.SetWindowSubclass.argtypes = [
        wintypes.HWND,
        SUBCLASSPROC,
        UINT_PTR,
        UINT_PTR,
    ]
    comctl32.SetWindowSubclass.restype = wintypes.BOOL

    comctl32.RemoveWindowSubclass.argtypes = [
        wintypes.HWND,
        SUBCLASSPROC,
        UINT_PTR,
    ]
    comctl32.RemoveWindowSubclass.restype = wintypes.BOOL

    comctl32.DefSubclassProc.argtypes = [
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]
    comctl32.DefSubclassProc.restype = LONG_PTR

    user32.GetKeyState.argtypes = [ctypes.c_int]
    user32.GetKeyState.restype = ctypes.c_short

    user32.SetCapture.argtypes = [wintypes.HWND]
    user32.SetCapture.restype = wintypes.HWND

    user32.GetCapture.argtypes = []
    user32.GetCapture.restype = wintypes.HWND

    user32.ReleaseCapture.argtypes = []
    user32.ReleaseCapture.restype = wintypes.BOOL

    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL

    return user32, comctl32


def discover_viewport_hwnds(rt: Any) -> set[int]:
    """Collect all valid 3D viewport HWNDs across all 3ds Max 2026 view panels."""
    hwnds: set[int] = set()
    if rt is None:
        return hwnds

    try:
        active = int(rt.viewport.getHWnd())
        if active > 0:
            hwnds.add(active)
    except Exception:
        pass

    try:
        num_views = int(rt.viewport.numViews)
        for idx in range(1, num_views + 1):
            try:
                h = int(rt.viewport.getHWnd(index=idx))
                if h > 0:
                    hwnds.add(h)
            except Exception:
                continue
    except Exception:
        pass

    try:
        vpm = getattr(rt, "ViewPanelManager", None)
        if vpm is not None:
            panel_count = int(vpm.GetViewPanelCount())
            for panel_idx in range(1, panel_count + 1):
                for view_idx in range(1, 5):
                    try:
                        h = int(rt.viewport.getHWnd(index=view_idx, viewPanelIndex=panel_idx))
                        if h > 0:
                            hwnds.add(h)
                    except Exception:
                        break
    except Exception:
        pass

    return hwnds


class ViewportSubclassManager:
    """Manages Win32 SetWindowSubclass hooks across all 3ds Max 2026 viewports."""

    def __init__(
        self,
        on_rmb_down: Callable[[int, str], bool],
        on_rmb_up: Callable[[int], bool],
        on_hold_key_down: Callable[[int, int], bool],
        on_hold_key_up: Callable[[int, int], bool],
        on_escape: Callable[[], bool],
        on_abort: Callable[[str], None],
        hold_vk_getter: Callable[[], int],
        is_radial_active: Callable[[], bool],
        is_hotbox_active: Callable[[], bool],
        on_backspace: Callable[[], bool] | None = None,
        on_lmb_while_radial: Callable[[], bool] | None = None,
        win32_apis: tuple[Any, Any] | None = None,
    ) -> None:
        self._user32, self._comctl32 = win32_apis if win32_apis is not None else _init_win32_apis()
        self._on_rmb_down = on_rmb_down
        self._on_rmb_up = on_rmb_up
        self._on_hold_key_down = on_hold_key_down
        self._on_hold_key_up = on_hold_key_up
        self._on_escape = on_escape
        self._on_backspace = on_backspace
        self._on_lmb_while_radial = on_lmb_while_radial
        self._on_abort = on_abort
        self._hold_vk_getter = hold_vk_getter
        self._is_radial_active = is_radial_active
        self._is_hotbox_active = is_hotbox_active

        # Map hwnd -> SUBCLASSPROC (kept alive while attached!)
        self._hooks: dict[int, Any] = {}
        self._leaked_callbacks: list[Any] = []
        self._capture_hwnd: int = 0
        self._releasing_capture: bool = False
        self._suppress_context_menu_until: float = 0.0
        self._active_hold_vk: int = 0
        self._space_used_with_rmb: bool = False

    @property
    def hooked_hwnds(self) -> tuple[int, ...]:
        return tuple(sorted(self._hooks.keys()))

    def is_key_down(self, vk: int) -> bool:
        return bool(self._user32.GetKeyState(vk) & 0x8000)

    def current_rmb_trigger(self) -> str:
        space = self.is_key_down(VK_SPACE)
        shift = self.is_key_down(VK_SHIFT)
        ctrl = self.is_key_down(VK_CONTROL)
        alt = self.is_key_down(VK_MENU)

        if space and not ctrl and not alt:
            return TRIGGER_SPACE_RMB
        if ctrl and shift and not alt:
            return TRIGGER_CTRL_SHIFT_RMB
        if alt and not ctrl and not shift:
            return TRIGGER_ALT_RMB
        if ctrl and not shift and not alt:
            return TRIGGER_CTRL_RMB
        if shift and not ctrl and not alt:
            return TRIGGER_SHIFT_RMB
        if not shift and not ctrl and not alt:
            return TRIGGER_RMB
        return "UNHANDLED"

    def attach_hwnd(self, hwnd: int) -> bool:
        if hwnd <= 0 or hwnd in self._hooks:
            return hwnd in self._hooks
        if not self._user32.IsWindow(hwnd):
            return False

        cb = SUBCLASSPROC(self._wnd_proc)
        ok = bool(self._comctl32.SetWindowSubclass(hwnd, cb, SUBCLASS_ID, 0))
        if ok:
            self._hooks[hwnd] = cb
            get_logger().info("Attached viewport subclass hwnd=%s", hwnd)
        else:
            err = ctypes.get_last_error()
            get_logger().warning("SetWindowSubclass failed for hwnd=%s err=%s", hwnd, err)
        return ok

    def detach_hwnd(self, hwnd: int) -> bool:
        cb = self._hooks.get(hwnd)
        if cb is None:
            return True

        if self._capture_hwnd == hwnd:
            self.release_capture()

        if not self._user32.IsWindow(hwnd):
            self._hooks.pop(hwnd, None)
            return True

        ok = bool(self._comctl32.RemoveWindowSubclass(hwnd, cb, SUBCLASS_ID))
        if ok:
            self._hooks.pop(hwnd, None)
            get_logger().info("Detached viewport subclass hwnd=%s", hwnd)
        else:
            err = ctypes.get_last_error()
            get_logger().error(
                "RemoveWindowSubclass failed for hwnd=%s err=%s; retaining callback reference",
                hwnd,
                err,
            )
            self._hooks.pop(hwnd, None)
            self._leaked_callbacks.append(cb)
        return ok

    def sync_hwnds(self, target_hwnds: set[int]) -> tuple[int, int]:
        """Attach to any new viewport HWNDs and prune invalid/removed ones."""
        attached = 0
        detached = 0

        for existing in list(self._hooks.keys()):
            if not self._user32.IsWindow(existing) or (target_hwnds and existing not in target_hwnds):
                if self.detach_hwnd(existing):
                    detached += 1

        for hwnd in target_hwnds:
            if hwnd not in self._hooks and self._user32.IsWindow(hwnd):
                if self.attach_hwnd(hwnd):
                    attached += 1

        return attached, detached

    def detach_all(self) -> bool:
        self.release_capture()
        all_ok = True
        for hwnd in list(self._hooks.keys()):
            if not self.detach_hwnd(hwnd):
                all_ok = False
        return all_ok

    def set_capture(self, hwnd: int) -> None:
        if hwnd > 0 and self._user32.IsWindow(hwnd):
            self._user32.SetCapture(hwnd)
            self._capture_hwnd = hwnd

    def release_capture(self) -> None:
        """Release Win32 mouse capture without triggering a false capture-lost abort.

        Windows synchronously dispatches WM_CAPTURECHANGED from inside ReleaseCapture();
        guarding with `_releasing_capture` ensures our own release never cancels the
        completing gesture before `_on_rmb_up` executes the chosen command.
        """
        if self._capture_hwnd:
            hwnd = self._capture_hwnd
            self._capture_hwnd = 0
            self._releasing_capture = True
            try:
                if self._user32.GetCapture() == hwnd:
                    self._user32.ReleaseCapture()
            finally:
                self._releasing_capture = False

    def _wnd_proc(
        self,
        hwnd: int,
        msg: int,
        wparam: int,
        lparam: int,
        subclass_id: int,
        ref_data: int,
    ) -> int:
        try:
            # Always self-remove subclass before window destruction
            if msg == WM_NCDESTROY:
                if self._capture_hwnd == hwnd:
                    self._capture_hwnd = 0
                cb = self._hooks.pop(hwnd, None)
                if cb is not None:
                    self._comctl32.RemoveWindowSubclass(hwnd, cb, subclass_id)
                return self._comctl32.DefSubclassProc(hwnd, msg, wparam, lparam)

            # Right mouse button down -> Radial Marking Menu (including Maya Space+RMB)
            if msg == WM_RBUTTONDOWN and not self._is_radial_active():
                if not self.is_key_down(VK_LBUTTON) and not self.is_key_down(VK_MBUTTON):
                    trigger = self.current_rmb_trigger()
                    # Allow Space+RMB even if Space already opened the 5-zone Full Hotbox
                    if not self._is_hotbox_active() or trigger == TRIGGER_SPACE_RMB:
                        if trigger != "UNHANDLED" and self._on_rmb_down(hwnd, trigger):
                            if trigger == TRIGGER_SPACE_RMB:
                                self._space_used_with_rmb = True
                                self._active_hold_vk = 0
                            self.set_capture(hwnd)
                            self._suppress_context_menu_until = time.monotonic() + 0.5
                            return 0

            # Left-click tap while holding RMB inside a submenu -> Maya-style instant return to parent
            if msg == WM_LBUTTONDOWN and self._is_radial_active():
                if self._on_lmb_while_radial and self._on_lmb_while_radial():
                    return 0

            # Right mouse button up -> Complete Radial Marking Menu and execute!
            if msg == WM_RBUTTONUP and self._is_radial_active():
                self._suppress_context_menu_until = time.monotonic() + 0.15
                self.release_capture()
                self._on_rmb_up(hwnd)
                return 0

            # Suppress Space auto-repeat & Space release after Space+RMB so Max Selection Lock never toggles
            if msg == WM_KEYDOWN and wparam == VK_SPACE and self._space_used_with_rmb:
                return 0
            if msg == WM_KEYUP and wparam == VK_SPACE and self._space_used_with_rmb:
                self._space_used_with_rmb = False
                return 0

            # Suppress native context menu / Quad menu while radial is active or just released
            if msg == WM_CONTEXTMENU:
                if self._is_radial_active() or time.monotonic() < self._suppress_context_menu_until:
                    return 0

            # Escape cancels active radial or full hotbox; Backspace returns to parent submenu
            if msg == WM_KEYDOWN and wparam == VK_ESCAPE:
                if self._is_radial_active() or self._is_hotbox_active():
                    self.release_capture()
                    self._active_hold_vk = 0
                    self._on_escape()
                    return 0

            if msg == WM_KEYDOWN and wparam == VK_BACK and self._is_radial_active():
                if self._on_backspace and self._on_backspace():
                    return 0

            # Configurable Hold-Key Full Hotbox
            hold_vk = self._hold_vk_getter()
            if hold_vk > 0:
                if msg in (WM_KEYDOWN, WM_SYSKEYDOWN) and wparam == hold_vk:
                    is_repeat = bool(lparam & 0x40000000)
                    if self._active_hold_vk == hold_vk and self._is_hotbox_active():
                        return 0
                    if (
                        not is_repeat
                        and not self._is_radial_active()
                        and not self._is_hotbox_active()
                        and not self.is_key_down(VK_CONTROL)
                        and not self.is_key_down(VK_MENU)
                    ):
                        if self._on_hold_key_down(hwnd, hold_vk):
                            self._active_hold_vk = hold_vk
                            return 0

                if msg in (WM_KEYUP, WM_SYSKEYUP) and wparam == hold_vk and self._active_hold_vk == hold_vk:
                    self._active_hold_vk = 0
                    if self._is_hotbox_active():
                        self._on_hold_key_up(hwnd, hold_vk)
                        return 0

            # Abort cleanly ONLY if capture was stolen externally (not by our own release_capture)
            if msg in (WM_CAPTURECHANGED, WM_CANCELMODE) and self._is_radial_active():
                if not self._releasing_capture:
                    self._capture_hwnd = 0
                    self._on_abort("capture_lost")

            if msg == WM_KILLFOCUS and (self._is_radial_active() or self._is_hotbox_active()):
                self.release_capture()
                self._active_hold_vk = 0
                self._on_abort("kill_focus")

        except BaseException:
            get_logger().error(
                "Win32 subclass callback error:\n%s", traceback.format_exc()
            )

        return self._comctl32.DefSubclassProc(hwnd, msg, wparam, lparam)
