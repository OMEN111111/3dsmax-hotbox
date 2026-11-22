"""Main lifecycle controller bridging 3ds Max 2026, Win32 viewport hooks, menu bar button, and PySide6 UI."""

from __future__ import annotations

import builtins
import time
from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets

from .actions import ActionExecutor
from .config import ConfigManager, HotboxConfig, MenuItem
from .constants import (
    HOLD_KEY_MAP,
    PLUGIN_DISPLAY_NAME,
    PLUGIN_NAME,
    PLUGIN_VERSION,
    TRIGGER_SPACE_RMB,
)
from .context import MaxContext, query_max_context
from .geometry import Point2D
from . import graphite_tools
from .logger import get_logger
from .state_machine import FullHotboxSessionState, HotboxStateMachine, RadialSessionState
from .ui_hotbox import FullHotboxOverlay
from .ui_overlay import RadialMenuOverlay
from .ui_settings import HotboxSettingsDialog
from .win32_hook import ViewportSubclassManager, discover_viewport_hwnds

_BUILTIN_SLOT = "_max_hotbox_controller"
_MAX_CALLBACK_ID = "MaxHotboxLifecycleCallbacks"
_MENUBAR_ACTION_OBJ_NAME = "MaxHotboxMenuBarDirectAction"


def _get_max_runtime() -> Any:
    from pymxs import runtime as rt  # type: ignore[import-not-found]

    return rt


def _get_max_main_window() -> QtWidgets.QWidget | None:
    try:
        import qtmax  # type: ignore[import-not-found]

        return qtmax.GetQMaxMainWindow()
    except Exception:
        return None


def _cursor_pos() -> Point2D:
    pt = QtGui.QCursor.pos()
    return Point2D(float(pt.x()), float(pt.y()))


class MaxHotboxController(QtCore.QObject):
    """Coordinates viewport hooks, gesture tracking, overlays, top menu bar button, and Max commands."""

    def __init__(self, config_manager: ConfigManager | None = None) -> None:
        super().__init__()
        self._logger = get_logger()
        self._config_manager = config_manager or ConfigManager()
        self._config: HotboxConfig = self._config_manager.load()

        self._executor = ActionExecutor(
            rt_provider=_get_max_runtime,
            ui_callbacks={
                "open_settings": self.open_settings,
                "open_full_hotbox": self.open_full_hotbox_interactive,
                "switch_to_quad_menu": lambda: self.set_enabled(False),
                # Graphite self-contained selection tools & custom PySide6 parameter panels
                "graphite_random_select": graphite_tools.run_random_select,
                "graphite_random_select_settings": graphite_tools.open_random_select_panel,
                "graphite_select_ngons": lambda: graphite_tools.run_select_by_sides(">", 4),
                "graphite_select_by_sides_settings": graphite_tools.open_select_by_sides_panel,
                "graphite_dot_loop": lambda: graphite_tools.run_dot_step("loop"),
                "graphite_dot_loop_settings": lambda: graphite_tools.open_dot_step_panel("loop"),
                "graphite_dot_ring": lambda: graphite_tools.run_dot_step("ring"),
                "graphite_dot_ring_settings": lambda: graphite_tools.open_dot_step_panel("ring"),
                "graphite_select_hard_edges": graphite_tools.run_select_hard_edges,
                "graphite_select_hard_edges_settings": lambda: graphite_tools.open_angle_select_panel("hard_edges"),
                "graphite_select_by_angle": graphite_tools.run_select_coplanar_faces,
                "graphite_select_by_angle_settings": lambda: graphite_tools.open_angle_select_panel("coplanar"),
            },
        )

        self._radial_overlay = RadialMenuOverlay()
        self._hotbox_overlay = FullHotboxOverlay(
            on_item_clicked=self._on_hotbox_interactive_item_clicked,
            on_cancel=self._on_hotbox_cancel,
        )
        self._settings_dialog: HotboxSettingsDialog | None = None
        self._menubar_action: QtGui.QAction | None = None
        self._hotbox_interactive_mode: bool = False

        # Submenu & Back-to-Parent hover dwell tracking
        self._submenu_hover_key: str | None = None
        self._submenu_hover_since: float = 0.0
        self._back_hover_since: float | None = None

        self._state = HotboxStateMachine(
            config_getter=lambda: self._config,
            context_getter=self._query_context,
            on_radial_update=self._on_radial_state_changed,
            on_hotbox_update=self._on_hotbox_state_changed,
            on_execute_item=self._schedule_item_execution,
        )

        self._hooks = ViewportSubclassManager(
            on_rmb_down=self._handle_rmb_down,
            on_rmb_up=self._handle_rmb_up,
            on_hold_key_down=self._handle_hold_key_down,
            on_hold_key_up=self._handle_hold_key_up,
            on_escape=self._handle_escape,
            on_backspace=self._handle_backspace,
            on_lmb_while_radial=self._handle_lmb_while_radial,
            on_abort=self._handle_abort,
            hold_vk_getter=self._current_hold_vk,
            is_radial_active=lambda: self._state.radial_state is not None,
            is_hotbox_active=lambda: self._state.hotbox_state is not None,
        )

        # High-frequency cursor tracking timer (active only while overlay is open)
        self._track_timer = QtCore.QTimer(self)
        self._track_timer.setInterval(12)
        self._track_timer.timeout.connect(self._on_track_tick)

        # Periodic viewport HWND synchronization timer
        self._sync_timer = QtCore.QTimer(self)
        self._sync_timer.setInterval(1000)
        self._sync_timer.timeout.connect(self.sync_viewports)

        self._started = False

    # -------------------------------------------------------------- Lifecycle
    def start(self) -> None:
        if self._started:
            self.sync_viewports()
            self._ensure_menubar_button()
            return

        self._started = True
        self.sync_viewports()
        self._sync_timer.start()
        QtCore.QTimer.singleShot(1500, self.sync_viewports)
        self._register_max_callbacks()
        self._ensure_menubar_button()

        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.stop)

        self._logger.info(
            "%s v%s started (enabled=%s, hooked_viewports=%d)",
            PLUGIN_NAME,
            PLUGIN_VERSION,
            self._config.settings.enabled,
            len(self._hooks.hooked_hwnds),
        )
        self._push_max_prompt(
            f"{PLUGIN_DISPLAY_NAME} v{PLUGIN_VERSION} 已就绪 "
            f"(已挂载 {len(self._hooks.hooked_hwnds)} 个视口)"
        )

    def stop(self) -> None:
        if not self._started:
            return
        self._started = False

        self._track_timer.stop()
        self._sync_timer.stop()
        self._state.cancel()
        self._unregister_max_callbacks()
        self._remove_menubar_button()
        ok = self._hooks.detach_all()

        if self._settings_dialog is not None:
            try:
                self._settings_dialog.close()
                self._settings_dialog.deleteLater()
            except Exception:
                pass
            self._settings_dialog = None

        try:
            self._radial_overlay.close()
            self._radial_overlay.deleteLater()
            self._hotbox_overlay.close()
            self._hotbox_overlay.deleteLater()
        except Exception:
            pass

        self._logger.info("%s stopped cleanly (all_detached=%s)", PLUGIN_NAME, ok)
        if getattr(builtins, _BUILTIN_SLOT, None) is self:
            setattr(builtins, _BUILTIN_SLOT, None)

    # ---------------------------------------------------- Menu Bar Button UI
    def _menubar_button_label(self) -> str:
        mode = "热盒" if self._config.settings.enabled else "四元"
        return f"MaxHotbox [{mode}]"

    def _ensure_menubar_button(self) -> None:
        """Install an exclusive clickable MaxHotbox settings button directly on Max 2026's menuBar."""
        try:
            main_win = _get_max_main_window()
            if main_win is None or not hasattr(main_win, "menuBar"):
                return
            menu_bar = main_win.menuBar()
            if menu_bar is None:
                return

            # Remove any stale action from a prior hot-reload
            for existing in list(menu_bar.actions()):
                if existing.objectName() == _MENUBAR_ACTION_OBJ_NAME:
                    if existing is self._menubar_action:
                        existing.setText(self._menubar_button_label())
                        return
                    menu_bar.removeAction(existing)

            action = QtGui.QAction(self._menubar_button_label(), menu_bar)
            action.setObjectName(_MENUBAR_ACTION_OBJ_NAME)
            action.setToolTip("点击打开 MaxHotbox 配置面板（可一键切换热盒 / 原生四元菜单模式）")
            action.triggered.connect(self.open_settings)
            menu_bar.addAction(action)
            self._menubar_action = action
            self._logger.info("Installed direct menuBar button on 3ds Max 2026")
        except Exception as exc:
            self._logger.warning("Could not install menuBar button: %s", exc)

    def _update_menubar_button(self) -> None:
        if self._menubar_action is not None:
            try:
                self._menubar_action.setText(self._menubar_button_label())
            except Exception:
                self._menubar_action = None
                self._ensure_menubar_button()
        else:
            self._ensure_menubar_button()

    def _remove_menubar_button(self) -> None:
        if self._menubar_action is None:
            return
        try:
            main_win = _get_max_main_window()
            if main_win is not None and hasattr(main_win, "menuBar"):
                menu_bar = main_win.menuBar()
                if menu_bar is not None:
                    menu_bar.removeAction(self._menubar_action)
        except Exception:
            pass
        self._menubar_action = None

    # ------------------------------------------------------------ Viewports
    def sync_viewports(self) -> str:
        """Discover all active 3ds Max 2026 viewports and ensure hooks are attached."""
        try:
            rt = _get_max_runtime()
            hwnds = discover_viewport_hwnds(rt)
            if self._config.settings.enabled:
                self._hooks.sync_hwnds(hwnds)
            else:
                if self._hooks.hooked_hwnds:
                    self._hooks.detach_all()
        except Exception as exc:
            self._logger.debug("sync_viewports skipped: %s", exc)
        return self.status_text()

    def status_text(self) -> str:
        if self._config.settings.enabled:
            return f"当前模式: Maya 热盒 · 视口挂钩: {len(self._hooks.hooked_hwnds)}"
        return "当前模式: 3ds Max 原生四元菜单"

    def is_enabled(self) -> bool:
        return bool(self._config.settings.enabled)

    def set_enabled(self, enabled: bool) -> bool:
        self._config.settings.enabled = bool(enabled)
        self._config_manager.save(self._config)
        if not enabled:
            self._state.cancel()
            self._track_timer.stop()
            self._hooks.detach_all()
            self._push_max_prompt(f"{PLUGIN_DISPLAY_NAME}: 已切换回 3ds Max 原生四元菜单模式")
        else:
            self.sync_viewports()
            self._push_max_prompt(
                f"{PLUGIN_DISPLAY_NAME}: 已切换为 Maya 热盒模式 (挂载 {len(self._hooks.hooked_hwnds)} 个视口)"
            )
        self._update_menubar_button()
        self._logger.info("set_enabled(%s)", enabled)
        return self._config.settings.enabled

    def toggle_enabled(self) -> bool:
        return self.set_enabled(not self._config.settings.enabled)

    def open_settings(self) -> None:
        if self._settings_dialog is not None:
            try:
                if self._settings_dialog.isVisible():
                    self._settings_dialog.raise_()
                    self._settings_dialog.activateWindow()
                    return
                self._settings_dialog.deleteLater()
            except Exception:
                pass
            self._settings_dialog = None

        parent = _get_max_main_window()
        dlg = HotboxSettingsDialog(
            config_manager=self._config_manager,
            on_config_applied=self._apply_config,
            on_mode_switched=self.set_enabled,
            status_provider=self.status_text,
            on_rescan_viewports=self.sync_viewports,
            parent=parent,
        )
        dlg.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self._settings_dialog = dlg
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def open_full_hotbox_interactive(self) -> None:
        """Open the 5-zone Full Hotbox at cursor in click-to-run mode."""
        if self._state.is_active:
            self._state.cancel()
        self._hotbox_interactive_mode = True
        if self._state.begin_hotbox(origin=_cursor_pos(), source_hwnd=0):
            self._track_timer.start()

    # --------------------------------------------------------- Config & State
    def _apply_config(self, config: HotboxConfig) -> None:
        self._config = config
        if not config.settings.enabled:
            self._state.cancel()
            self._track_timer.stop()
            self._hooks.detach_all()
        else:
            self.sync_viewports()
        self._update_menubar_button()

    def _current_hold_vk(self) -> int:
        if not self._config.settings.enabled:
            return 0
        return HOLD_KEY_MAP.get(self._config.settings.hold_hotbox_key, 0)

    def _query_context(self) -> MaxContext:
        try:
            return query_max_context(_get_max_runtime())
        except Exception:
            return MaxContext()

    # ---------------------------------------------------------- Hook Handlers
    def _handle_rmb_down(self, hwnd: int, trigger: str) -> bool:
        # If Space already opened the 5-zone Full Hotbox, seamlessly switch into Maya Space+RMB radial
        if trigger == TRIGGER_SPACE_RMB and self._state.hotbox_state is not None:
            self._hotbox_interactive_mode = False
            self._state.cancel()
        origin = _cursor_pos()
        self._submenu_hover_key = None
        self._back_hover_since = None
        if self._state.begin_radial(trigger=trigger, origin=origin, source_hwnd=hwnd):
            self._track_timer.start()
            return True
        return False

    def _handle_rmb_up(self, _hwnd: int) -> bool:
        self._track_timer.stop()
        self._submenu_hover_key = None
        self._back_hover_since = None
        self._state.end_radial(cursor=_cursor_pos(), execute=True)
        return True

    def _handle_hold_key_down(self, hwnd: int, _vk: int) -> bool:
        self._hotbox_interactive_mode = False
        if self._state.begin_hotbox(origin=_cursor_pos(), source_hwnd=hwnd):
            self._track_timer.start()
            return True
        return False

    def _handle_hold_key_up(self, _hwnd: int, _vk: int) -> bool:
        self._track_timer.stop()
        cursor = _cursor_pos()
        hovered_item, is_opt = self._hotbox_overlay.hit_test_item(cursor)
        self._state.end_hotbox(
            execute=True,
            explicit_item=hovered_item,
            explicit_is_option=is_opt,
        )
        return True

    def _handle_escape(self) -> bool:
        self._track_timer.stop()
        self._submenu_hover_key = None
        self._back_hover_since = None
        self._hotbox_interactive_mode = False
        self._state.cancel()
        return True

    def _handle_backspace(self) -> bool:
        self._submenu_hover_key = None
        self._back_hover_since = None
        return self._state.step_back_submenu()

    def _handle_lmb_while_radial(self) -> bool:
        """Maya-style LMB tap while holding RMB immediately returns to parent submenu."""
        self._submenu_hover_key = None
        self._back_hover_since = None
        if self._state.step_back_submenu():
            return True
        return False

    def _handle_abort(self, reason: str) -> None:
        self._logger.debug("Hotbox session aborted (%s)", reason)
        self._track_timer.stop()
        self._submenu_hover_key = None
        self._back_hover_since = None
        self._hotbox_interactive_mode = False
        self._state.cancel()

    # --------------------------------------------------------- Tracking & UI
    def _on_track_tick(self) -> None:
        cursor = _cursor_pos()
        if self._state.radial_state is not None:
            self._state.update_radial_cursor(cursor)
            self._check_back_dwell()
            self._check_submenu_dwell(cursor)
        elif self._state.hotbox_state is not None:
            hovered_item, is_opt = self._hotbox_overlay.hit_test_item(cursor)
            self._state.update_hotbox_cursor(
                cursor,
                hovered_item=hovered_item,
                hovered_is_option=is_opt,
            )
        else:
            self._track_timer.stop()

    def _check_back_dwell(self) -> None:
        rstate = self._state.radial_state
        if rstate is None or rstate.hit.kind != "back" or not rstate.profile_stack:
            if self._back_hover_since is not None:
                self._back_hover_since = None
                self._radial_overlay.set_back_dwell_progress(0.0)
            return

        dwell_sec = max(0.10, min(0.24, self._config.settings.submenu_dwell_ms / 1000.0 * 0.85))
        now = time.monotonic()
        if self._back_hover_since is None:
            self._back_hover_since = now
            self._radial_overlay.set_back_dwell_progress(0.08)
            return

        elapsed = now - self._back_hover_since
        if elapsed >= dwell_sec:
            self._back_hover_since = None
            self._submenu_hover_key = None
            self._radial_overlay.set_back_dwell_progress(0.0)
            self._state.step_back_submenu()
        else:
            self._radial_overlay.set_back_dwell_progress(elapsed / dwell_sec)

    def _check_submenu_dwell(self, cursor: Point2D) -> None:
        rstate = self._state.radial_state
        if rstate is None:
            return
        item = rstate.selected_item()
        if item is not None and item.command_type == "submenu" and item.submenu_id:
            dwell_sec = max(0.08, self._config.settings.submenu_dwell_ms / 1000.0)
            key = f"{rstate.profile.profile_id}:{rstate.hit.direction}:{item.submenu_id}"
            now = time.monotonic()
            if self._submenu_hover_key != key:
                self._submenu_hover_key = key
                self._submenu_hover_since = now
                self._radial_overlay.set_submenu_dwell_progress(0.05)
            else:
                elapsed = now - self._submenu_hover_since
                if elapsed >= dwell_sec:
                    self._submenu_hover_key = None
                    self._radial_overlay.set_submenu_dwell_progress(0.0)
                    self._state.enter_submenu_if_selected(new_origin=cursor)
                else:
                    self._radial_overlay.set_submenu_dwell_progress(elapsed / dwell_sec)
        else:
            if self._submenu_hover_key is not None:
                self._submenu_hover_key = None
                self._radial_overlay.set_submenu_dwell_progress(0.0)

    def _on_radial_state_changed(self, state: RadialSessionState | None) -> None:
        self._radial_overlay.sync_state(state, self._config.settings)

    def _on_hotbox_state_changed(self, state: FullHotboxSessionState | None) -> None:
        self._hotbox_overlay.sync_state(
            state=state,
            zones=self._config.hotbox_zones,
            settings=self._config.settings,
            interactive_click_mode=self._hotbox_interactive_mode,
        )

    def _on_hotbox_interactive_item_clicked(self, item: MenuItem, is_option: bool) -> None:
        self._track_timer.stop()
        self._hotbox_interactive_mode = False
        self._state.end_hotbox(
            execute=True,
            explicit_item=item,
            explicit_is_option=is_option,
        )

    def _on_hotbox_cancel(self) -> None:
        self._track_timer.stop()
        self._hotbox_interactive_mode = False
        self._state.cancel()

    def _schedule_item_execution(self, item: MenuItem, use_option_box: bool) -> None:
        """Defer command execution to the next Qt event-loop tick outside Win32 WndProc."""

        def _run() -> None:
            res = self._executor.execute(item, use_option_box=use_option_box)
            if res.ok:
                tag = " [□ 参数面板]" if use_option_box else ""
                self._push_max_prompt(f"{PLUGIN_DISPLAY_NAME}: {item.label}{tag}")
            else:
                self._logger.warning("Command '%s' failed: %s", item.label, res.message)
                self._push_max_prompt(f"{PLUGIN_DISPLAY_NAME} 执行提示: {res.message}")

        QtCore.QTimer.singleShot(0, _run)

    # --------------------------------------------------------- Max Callbacks
    def _register_max_callbacks(self) -> None:
        try:
            rt = _get_max_runtime()
            cb_id = rt.Name(_MAX_CALLBACK_ID)
            rt.callbacks.removeScripts(id=cb_id)
            rt.callbacks.addScript(
                rt.Name("viewportChange"),
                'python.execute "import max_hotbox; max_hotbox.sync_viewports()"',
                id=cb_id,
            )
            rt.callbacks.addScript(
                rt.Name("systemPostReset"),
                'python.execute "import max_hotbox; max_hotbox.sync_viewports()"',
                id=cb_id,
            )
            rt.callbacks.addScript(
                rt.Name("filePostOpen"),
                'python.execute "import max_hotbox; max_hotbox.sync_viewports()"',
                id=cb_id,
            )
            rt.callbacks.addScript(
                rt.Name("preSystemShutdown"),
                'python.execute "import max_hotbox; max_hotbox.shutdown()"',
                id=cb_id,
            )
        except Exception as exc:
            self._logger.warning("Failed to register 3ds Max callbacks: %s", exc)

    def _unregister_max_callbacks(self) -> None:
        try:
            rt = _get_max_runtime()
            rt.callbacks.removeScripts(id=rt.Name(_MAX_CALLBACK_ID))
        except Exception:
            pass

    @staticmethod
    def _push_max_prompt(message: str) -> None:
        try:
            rt = _get_max_runtime()
            rt.pushPrompt(message)
        except Exception:
            pass


# ----------------------------------------------------------- Public Singleton
def get_controller() -> MaxHotboxController | None:
    return getattr(builtins, _BUILTIN_SLOT, None)


def startup() -> MaxHotboxController:
    """Start (or reload) the singleton MaxHotboxController in 3ds Max 2026."""
    existing = get_controller()
    if existing is not None:
        existing.stop()
    controller = MaxHotboxController()
    setattr(builtins, _BUILTIN_SLOT, controller)
    controller.start()
    return controller


def shutdown() -> None:
    """Cleanly stop MaxHotbox and restore native 3ds Max viewport behavior."""
    existing = get_controller()
    if existing is not None:
        existing.stop()


def toggle() -> bool:
    ctrl = get_controller()
    if ctrl is None:
        ctrl = startup()
        return ctrl.is_enabled()
    return ctrl.toggle_enabled()


def is_enabled() -> bool:
    ctrl = get_controller()
    return bool(ctrl and ctrl.is_enabled())


def open_settings() -> None:
    ctrl = get_controller() or startup()
    ctrl.open_settings()


def open_full_hotbox() -> None:
    ctrl = get_controller() or startup()
    ctrl.open_full_hotbox_interactive()


def sync_viewports() -> str:
    ctrl = get_controller()
    if ctrl is not None:
        return ctrl.sync_viewports()
    return "未启动"
