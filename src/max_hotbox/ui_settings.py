"""PySide6 Settings & Visual Menu Editor dialog styled for Autodesk 3ds Max 2026."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6 import QtCore, QtWidgets

from .actions import BUILTIN_COMMAND_CATALOG
from .config import ConfigManager, HotboxConfig, MenuItem
from .constants import (
    ALL_RMB_TRIGGERS,
    DIRECTION_LABELS_ZH,
    DIRECTIONS_8,
    HOLD_KEY_LABELS,
    HOTBOX_ZONES,
    PLUGIN_DISPLAY_NAME,
    PLUGIN_VERSION,
    TARGET_MAX_VERSION,
    THEMES,
)

# Native Autodesk 3ds Max 2026 Dark Neutral QSS
_DIALOG_QSS = """
QDialog {
    background-color: #323232;
    color: #E6E6E6;
    font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
    font-size: 12px;
}
QTabWidget::pane {
    border: 1px solid #525252;
    border-radius: 3px;
    background-color: #383838;
}
QTabBar::tab {
    background-color: #2B2B2B;
    color: #B0B0B0;
    padding: 7px 16px;
    border: 1px solid #4A4A4A;
    border-bottom: none;
    border-top-left-radius: 3px;
    border-top-right-radius: 3px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background-color: #383838;
    color: #FFFFFF;
    font-weight: bold;
    border-top: 2px solid #4A89CC;
}
QGroupBox {
    border: 1px solid #4E4E4E;
    border-radius: 3px;
    margin-top: 10px;
    padding-top: 10px;
    font-weight: bold;
    color: #DCDCDC;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTableWidget {
    background-color: #262626;
    color: #EDEDED;
    border: 1px solid #525252;
    border-radius: 2px;
    padding: 3px 6px;
}
QHeaderView::section {
    background-color: #2D2D2D;
    color: #DCDCDC;
    border: 1px solid #4A4A4A;
    padding: 4px;
}
QPushButton {
    background-color: #464646;
    color: #EEEEEE;
    border: 1px solid #5E5E5E;
    border-radius: 3px;
    padding: 5px 14px;
}
QPushButton:hover {
    background-color: #545454;
    border-color: #70A8E0;
}
QPushButton#primaryBtn {
    background-color: #3D75B3;
    border-color: #5894D4;
    color: #FFFFFF;
    font-weight: bold;
}
QPushButton#primaryBtn:hover {
    background-color: #4A89CC;
}
QPushButton#modeBtn {
    background-color: #2B2B2B;
    color: #B8B8B8;
    border: 1px solid #525252;
    border-radius: 3px;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: bold;
}
QPushButton#modeBtn:checked {
    background-color: #3D75B3;
    color: #FFFFFF;
    border: 1px solid #6BA7E5;
}
QCheckBox {
    spacing: 8px;
}
"""


class HotboxSettingsDialog(QtWidgets.QDialog):
    """Configuration manager, Hotbox/Quad mode switcher, and visual menu editor."""

    def __init__(
        self,
        config_manager: ConfigManager,
        on_config_applied: Callable[[HotboxConfig], None],
        on_mode_switched: Callable[[bool], None],
        status_provider: Callable[[], str],
        on_rescan_viewports: Callable[[], str],
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._config_manager = config_manager
        self._on_config_applied = on_config_applied
        self._on_mode_switched = on_mode_switched
        self._status_provider = status_provider
        self._on_rescan_viewports = on_rescan_viewports
        self._draft: HotboxConfig = config_manager.clone_config()

        self.setWindowTitle(
            f"{PLUGIN_DISPLAY_NAME} v{PLUGIN_VERSION} — 配置与菜单编辑器 (3ds Max {TARGET_MAX_VERSION})"
        )
        self.resize(960, 650)
        self.setStyleSheet(_DIALOG_QSS)

        self._build_ui()
        self._load_general_tab()
        self._load_radial_tab()
        self._load_hotbox_tab()

    def _build_ui(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # Prominent Work-Mode Switcher Banner (Hotbox vs Native Quad Menu)
        mode_frame = QtWidgets.QFrame()
        mode_frame.setStyleSheet(
            "QFrame { background-color: #292929; border: 1px solid #4A4A4A; border-radius: 3px; }"
        )
        mode_layout = QtWidgets.QHBoxLayout(mode_frame)
        mode_layout.setContentsMargins(12, 8, 12, 8)
        mode_layout.setSpacing(10)

        mode_title = QtWidgets.QLabel("<b>右键菜单工作模式:</b>")
        mode_title.setStyleSheet("border: none; color: #EAEAEA; font-size: 13px;")
        mode_layout.addWidget(mode_title)

        self._btn_mode_hotbox = QtWidgets.QPushButton("Maya 热盒模式 (Hotbox)")
        self._btn_mode_hotbox.setObjectName("modeBtn")
        self._btn_mode_hotbox.setCheckable(True)
        self._btn_mode_hotbox.clicked.connect(lambda: self._switch_work_mode(True))

        self._btn_mode_quad = QtWidgets.QPushButton("3ds Max 原生四元菜单 (Quad)")
        self._btn_mode_quad.setObjectName("modeBtn")
        self._btn_mode_quad.setCheckable(True)
        self._btn_mode_quad.clicked.connect(lambda: self._switch_work_mode(False))

        mode_layout.addWidget(self._btn_mode_hotbox)
        mode_layout.addWidget(self._btn_mode_quad)
        mode_layout.addStretch()

        self._status_lbl = QtWidgets.QLabel(self._status_provider())
        self._status_lbl.setStyleSheet("border: none; color: #A6A6A6;")
        mode_layout.addWidget(self._status_lbl)

        rescan_btn = QtWidgets.QPushButton("重新扫描视口")
        rescan_btn.clicked.connect(self._handle_rescan)
        mode_layout.addWidget(rescan_btn)
        root.addWidget(mode_frame)

        # Tabs
        self._tabs = QtWidgets.QTabWidget()
        self._tabs.addTab(self._create_general_tab(), "常规与交互设置")
        self._tabs.addTab(self._create_radial_tab(), "径向菜单与 □ 面板编辑")
        self._tabs.addTab(self._create_hotbox_tab(), "五区全局热盒编辑")
        root.addWidget(self._tabs, 1)

        # Footer buttons
        footer = QtWidgets.QHBoxLayout()
        import_btn = QtWidgets.QPushButton("导入配置...")
        import_btn.clicked.connect(self._handle_import)
        export_btn = QtWidgets.QPushButton("导出配置...")
        export_btn.clicked.connect(self._handle_export)
        reset_btn = QtWidgets.QPushButton("恢复默认")
        reset_btn.clicked.connect(self._handle_reset)

        footer.addWidget(import_btn)
        footer.addWidget(export_btn)
        footer.addWidget(reset_btn)
        footer.addStretch()

        apply_btn = QtWidgets.QPushButton("保存并应用")
        apply_btn.setObjectName("primaryBtn")
        apply_btn.clicked.connect(self._handle_save_apply)
        close_btn = QtWidgets.QPushButton("关闭")
        close_btn.clicked.connect(self.close)

        footer.addWidget(apply_btn)
        footer.addWidget(close_btn)
        root.addLayout(footer)

    def _sync_mode_buttons(self, enabled: bool) -> None:
        self._btn_mode_hotbox.setChecked(enabled)
        self._btn_mode_quad.setChecked(not enabled)
        if hasattr(self, "_chk_enabled"):
            self._chk_enabled.setChecked(enabled)

    def _switch_work_mode(self, hotbox_enabled: bool) -> None:
        self._draft.settings.enabled = hotbox_enabled
        self._sync_mode_buttons(hotbox_enabled)
        self._on_mode_switched(hotbox_enabled)
        self._status_lbl.setText(self._status_provider())

    # ------------------------------------------------------------------ Tab 1
    def _create_general_tab(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        grp_main = QtWidgets.QGroupBox("交互保护与反馈")
        g1 = QtWidgets.QVBoxLayout(grp_main)
        self._chk_enabled = QtWidgets.QCheckBox("启用 Maya 热盒模式（取消勾选则立即切回 3ds Max 原生四元菜单）")
        self._chk_enabled.toggled.connect(lambda checked: self._sync_mode_buttons(checked))
        self._chk_safe_guard = QtWidgets.QCheckBox(
            "安全工具模式保护（处于创建物体/Cut/Target Weld等模态工具或按住左/中键时自动放行右键）"
        )
        self._chk_trail = QtWidgets.QCheckBox("显示手势划动指引线")
        g1.addWidget(self._chk_enabled)
        g1.addWidget(self._chk_safe_guard)
        g1.addWidget(self._chk_trail)
        layout.addWidget(grp_main)

        grp_vis = QtWidgets.QGroupBox("外观与手势参数")
        form = QtWidgets.QFormLayout(grp_vis)

        self._cmb_theme = QtWidgets.QComboBox()
        for tid, tdata in THEMES.items():
            self._cmb_theme.addItem(tdata["name"], tid)
        form.addRow("界面主题:", self._cmb_theme)

        self._cmb_hold_key = QtWidgets.QComboBox()
        for key_id, label in HOLD_KEY_LABELS.items():
            self._cmb_hold_key.addItem(label, key_id)
        form.addRow("五区全局热盒按住键:", self._cmb_hold_key)

        self._spin_deadzone = QtWidgets.QSpinBox()
        self._spin_deadzone.setRange(12, 80)
        self._spin_deadzone.setSuffix(" px")
        form.addRow("中心取消死区半径:", self._spin_deadzone)

        self._spin_radius = QtWidgets.QSpinBox()
        self._spin_radius.setRange(84, 190)
        self._spin_radius.setSuffix(" px")
        form.addRow("径向按钮分布半径:", self._spin_radius)

        self._spin_dwell = QtWidgets.QSpinBox()
        self._spin_dwell.setRange(80, 600)
        self._spin_dwell.setSingleStep(20)
        self._spin_dwell.setSuffix(" ms")
        form.addRow("子菜单悬停展开延迟:", self._spin_dwell)

        self._spin_scale = QtWidgets.QDoubleSpinBox()
        self._spin_scale.setRange(0.75, 1.50)
        self._spin_scale.setSingleStep(0.05)
        form.addRow("UI 缩放倍率:", self._spin_scale)

        self._spin_opacity = QtWidgets.QDoubleSpinBox()
        self._spin_opacity.setRange(0.55, 1.00)
        self._spin_opacity.setSingleStep(0.02)
        form.addRow("悬浮层不透明度:", self._spin_opacity)
        layout.addWidget(grp_vis)

        grp_trig = QtWidgets.QGroupBox("启用的右键热盒组合（单个关闭即可让该组合回归原生四元菜单）")
        trig_layout = QtWidgets.QGridLayout(grp_trig)
        self._trigger_checks: dict[str, QtWidgets.QCheckBox] = {}
        labels = {
            "RMB": "右键 (RMB) — 上下文对象/子层级/创建菜单",
            "SHIFT+RMB": "Shift + 右键 — 多边形建模（含 □ 数值面板）",
            "CTRL+RMB": "Ctrl + 右键 — 选择转换/循环/环形菜单",
            "ALT+RMB": "Alt + 右键 — 视口切换与着色显示菜单",
            "CTRL+SHIFT+RMB": "Ctrl + Shift + 右键 — 坐标系/枢轴/捕捉菜单",
        }
        for idx, trigger in enumerate(ALL_RMB_TRIGGERS):
            chk = QtWidgets.QCheckBox(labels.get(trigger, trigger))
            self._trigger_checks[trigger] = chk
            trig_layout.addWidget(chk, idx // 2, idx % 2)
        layout.addWidget(grp_trig)
        layout.addStretch()
        return page

    def _load_general_tab(self) -> None:
        s = self._draft.settings
        self._sync_mode_buttons(s.enabled)
        self._chk_safe_guard.setChecked(s.safe_tool_mode_guard)
        self._chk_trail.setChecked(s.show_gesture_trail)
        idx = self._cmb_theme.findData(s.theme)
        if idx >= 0:
            self._cmb_theme.setCurrentIndex(idx)
        kidx = self._cmb_hold_key.findData(s.hold_hotbox_key)
        if kidx >= 0:
            self._cmb_hold_key.setCurrentIndex(kidx)
        self._spin_deadzone.setValue(s.deadzone_radius)
        self._spin_radius.setValue(s.menu_radius)
        self._spin_dwell.setValue(s.submenu_dwell_ms)
        self._spin_scale.setValue(s.ui_scale)
        self._spin_opacity.setValue(s.opacity)
        for trigger, chk in self._trigger_checks.items():
            chk.setChecked(s.enabled_triggers.get(trigger, True))

    def _collect_general_tab(self) -> None:
        s = self._draft.settings
        s.enabled = self._chk_enabled.isChecked()
        s.safe_tool_mode_guard = self._chk_safe_guard.isChecked()
        s.show_gesture_trail = self._chk_trail.isChecked()
        s.theme = str(self._cmb_theme.currentData() or "max2026_native")
        s.hold_hotbox_key = str(self._cmb_hold_key.currentData() or "backtick")
        s.deadzone_radius = int(self._spin_deadzone.value())
        s.menu_radius = int(self._spin_radius.value())
        s.submenu_dwell_ms = int(self._spin_dwell.value())
        s.ui_scale = float(self._spin_scale.value())
        s.opacity = float(self._spin_opacity.value())
        for trigger, chk in self._trigger_checks.items():
            s.enabled_triggers[trigger] = chk.isChecked()

    # ------------------------------------------------------------------ Tab 2
    def _create_radial_tab(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        top = QtWidgets.QHBoxLayout()
        top.addWidget(QtWidgets.QLabel("选择菜单或子菜单:"))
        self._cmb_profile = QtWidgets.QComboBox()
        self._cmb_profile.currentIndexChanged.connect(self._on_profile_changed)
        top.addWidget(self._cmb_profile, 1)
        layout.addLayout(top)

        self._radial_table = QtWidgets.QTableWidget(len(DIRECTIONS_8), 6)
        self._radial_table.setHorizontalHeaderLabels(
            ["方向", "启用", "显示名称", "命令类型", "主按钮命令 / 子菜单ID", "右侧 □ 调整面板命令"]
        )
        self._radial_table.horizontalHeader().setStretchLastSection(True)
        self._radial_table.verticalHeader().setVisible(False)
        self._radial_table.setColumnWidth(0, 82)
        self._radial_table.setColumnWidth(1, 46)
        self._radial_table.setColumnWidth(2, 130)
        self._radial_table.setColumnWidth(3, 95)
        self._radial_table.setColumnWidth(4, 210)
        layout.addWidget(self._radial_table, 1)

        hint = QtWidgets.QLabel(
            "说明: 主按钮为鼠标交互拖动操作（如 poly_extrude）；填写“右侧 □ 调整面板命令”（如 poly_extrude_settings）"
            "后，按钮右侧会自动显示 Maya 风格 □ 方块，划到 □ 上松开即打开数值参数面板。"
            "命令类型设为 submenu 并在命令栏填子菜单ID（如 submenu_modifiers）即可悬停展开二级菜单。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #A6A6A6; font-size: 11px;")
        layout.addWidget(hint)

        self._current_profile_id: str | None = None
        return page

    def _load_radial_tab(self) -> None:
        self._current_profile_id = None
        self._cmb_profile.blockSignals(True)
        self._cmb_profile.clear()
        for pid, prof in self._draft.radial_profiles.items():
            prefix = "[子菜单] " if pid.startswith("submenu_") else "[主菜单] "
            self._cmb_profile.addItem(f"{prefix}{prof.title} ({pid})", pid)
        self._cmb_profile.blockSignals(False)
        if self._cmb_profile.count() > 0:
            self._cmb_profile.setCurrentIndex(0)
            self._populate_radial_table(str(self._cmb_profile.currentData()))

    def _on_profile_changed(self, _index: int) -> None:
        if self._current_profile_id:
            self._save_radial_table(self._current_profile_id)
        pid = self._cmb_profile.currentData()
        if pid:
            self._populate_radial_table(str(pid))

    def _populate_radial_table(self, profile_id: str) -> None:
        self._current_profile_id = profile_id
        profile = self._draft.radial_profiles.get(profile_id)
        if profile is None:
            return

        builtin_keys = sorted(BUILTIN_COMMAND_CATALOG.keys())
        submenu_keys = sorted(k for k in self._draft.radial_profiles.keys() if k.startswith("submenu_"))

        for row, direction in enumerate(DIRECTIONS_8):
            item = profile.slots.get(direction, MenuItem(label="", command_type="builtin", command="", enabled=False))

            dir_cell = QtWidgets.QTableWidgetItem(DIRECTION_LABELS_ZH[direction])
            dir_cell.setFlags(dir_cell.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
            self._radial_table.setItem(row, 0, dir_cell)

            chk = QtWidgets.QCheckBox()
            chk.setChecked(item.enabled)
            chk_holder = QtWidgets.QWidget()
            hl = QtWidgets.QHBoxLayout(chk_holder)
            hl.addWidget(chk)
            hl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            hl.setContentsMargins(0, 0, 0, 0)
            self._radial_table.setCellWidget(row, 1, chk_holder)

            self._radial_table.setCellWidget(row, 2, QtWidgets.QLineEdit(item.label))

            type_cmb = QtWidgets.QComboBox()
            for t in ("builtin", "submenu", "maxscript", "python", "action"):
                type_cmb.addItem(t, t)
            tidx = type_cmb.findData(item.command_type)
            if tidx >= 0:
                type_cmb.setCurrentIndex(tidx)
            self._radial_table.setCellWidget(row, 3, type_cmb)

            cmd_cmb = QtWidgets.QComboBox()
            cmd_cmb.setEditable(True)
            for k in submenu_keys + builtin_keys:
                cmd_cmb.addItem(k)
            cmd_cmb.setCurrentText(item.submenu_id if item.command_type == "submenu" else item.command)
            self._radial_table.setCellWidget(row, 4, cmd_cmb)

            opt_cmb = QtWidgets.QComboBox()
            opt_cmb.setEditable(True)
            opt_cmb.addItem("")
            for k in builtin_keys:
                opt_cmb.addItem(k)
            opt_cmb.setCurrentText(item.option_command)
            self._radial_table.setCellWidget(row, 5, opt_cmb)

    def _save_radial_table(self, profile_id: str) -> None:
        profile = self._draft.radial_profiles.get(profile_id)
        if profile is None:
            return
        for row, direction in enumerate(DIRECTIONS_8):
            chk_holder = self._radial_table.cellWidget(row, 1)
            chk = chk_holder.findChild(QtWidgets.QCheckBox) if chk_holder else None
            lbl_edit = self._radial_table.cellWidget(row, 2)
            type_cmb = self._radial_table.cellWidget(row, 3)
            cmd_cmb = self._radial_table.cellWidget(row, 4)
            opt_cmb = self._radial_table.cellWidget(row, 5)

            enabled = bool(chk.isChecked()) if chk else False
            label = lbl_edit.text().strip() if isinstance(lbl_edit, QtWidgets.QLineEdit) else ""
            cmd_type = str(type_cmb.currentData() or "builtin") if isinstance(type_cmb, QtWidgets.QComboBox) else "builtin"
            cmd_text = cmd_cmb.currentText().strip() if isinstance(cmd_cmb, QtWidgets.QComboBox) else ""
            opt_text = opt_cmb.currentText().strip() if isinstance(opt_cmb, QtWidgets.QComboBox) else ""

            existing = profile.slots.get(direction)
            tooltip = existing.tooltip if existing else ""
            opt_tip = existing.option_tooltip if existing else ""
            if cmd_type == "submenu":
                profile.slots[direction] = MenuItem(
                    label=label,
                    command_type="submenu",
                    command="",
                    submenu_id=cmd_text,
                    enabled=enabled,
                    tooltip=tooltip,
                )
            else:
                profile.slots[direction] = MenuItem(
                    label=label,
                    command_type=cmd_type,
                    command=cmd_text,
                    enabled=enabled,
                    tooltip=tooltip,
                    option_command_type="builtin" if opt_text else "",
                    option_command=opt_text,
                    option_tooltip=opt_tip,
                )

    # ------------------------------------------------------------------ Tab 3
    def _create_hotbox_tab(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        top = QtWidgets.QHBoxLayout()
        top.addWidget(QtWidgets.QLabel("选择热盒区域:"))
        self._cmb_zone = QtWidgets.QComboBox()
        self._cmb_zone.currentIndexChanged.connect(self._on_zone_changed)
        top.addWidget(self._cmb_zone, 1)

        add_btn = QtWidgets.QPushButton("+ 添加命令")
        add_btn.clicked.connect(self._handle_add_zone_item)
        del_btn = QtWidgets.QPushButton("- 删除选中行")
        del_btn.clicked.connect(self._handle_del_zone_item)
        top.addWidget(add_btn)
        top.addWidget(del_btn)
        layout.addLayout(top)

        self._zone_table = QtWidgets.QTableWidget(0, 5)
        self._zone_table.setHorizontalHeaderLabels(
            ["启用", "显示名称", "命令类型", "主命令 / 内置ID", "右侧 □ 面板命令"]
        )
        self._zone_table.horizontalHeader().setStretchLastSection(True)
        self._zone_table.verticalHeader().setVisible(False)
        self._zone_table.setColumnWidth(0, 48)
        self._zone_table.setColumnWidth(1, 150)
        self._zone_table.setColumnWidth(2, 95)
        self._zone_table.setColumnWidth(3, 210)
        layout.addWidget(self._zone_table, 1)

        self._current_zone_id: str | None = None
        return page

    def _load_hotbox_tab(self) -> None:
        self._current_zone_id = None
        self._cmb_zone.blockSignals(True)
        self._cmb_zone.clear()
        for zid in HOTBOX_ZONES:
            zone = self._draft.hotbox_zones.get(zid)
            title = zone.title if zone else zid
            self._cmb_zone.addItem(f"{zid} — {title}", zid)
        self._cmb_zone.blockSignals(False)
        if self._cmb_zone.count() > 0:
            self._cmb_zone.setCurrentIndex(0)
            self._populate_zone_table(str(self._cmb_zone.currentData()))

    def _on_zone_changed(self, _index: int) -> None:
        if self._current_zone_id:
            self._save_zone_table(self._current_zone_id)
        zid = self._cmb_zone.currentData()
        if zid:
            self._populate_zone_table(str(zid))

    def _populate_zone_table(self, zone_id: str) -> None:
        self._current_zone_id = zone_id
        zone = self._draft.hotbox_zones.get(zone_id)
        self._zone_table.setRowCount(0)
        if zone is None:
            return
        for item in zone.items:
            self._append_zone_row(item)

    def _append_zone_row(self, item: MenuItem) -> None:
        row = self._zone_table.rowCount()
        self._zone_table.insertRow(row)

        chk = QtWidgets.QCheckBox()
        chk.setChecked(item.enabled)
        holder = QtWidgets.QWidget()
        hl = QtWidgets.QHBoxLayout(holder)
        hl.addWidget(chk)
        hl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        hl.setContentsMargins(0, 0, 0, 0)
        self._zone_table.setCellWidget(row, 0, holder)

        self._zone_table.setCellWidget(row, 1, QtWidgets.QLineEdit(item.label))

        type_cmb = QtWidgets.QComboBox()
        for t in ("builtin", "maxscript", "python", "action"):
            type_cmb.addItem(t, t)
        tidx = type_cmb.findData(item.command_type)
        if tidx >= 0:
            type_cmb.setCurrentIndex(tidx)
        self._zone_table.setCellWidget(row, 2, type_cmb)

        builtin_keys = sorted(BUILTIN_COMMAND_CATALOG.keys())
        cmd_cmb = QtWidgets.QComboBox()
        cmd_cmb.setEditable(True)
        for bk in builtin_keys:
            cmd_cmb.addItem(bk)
        cmd_cmb.setCurrentText(item.command)
        self._zone_table.setCellWidget(row, 3, cmd_cmb)

        opt_cmb = QtWidgets.QComboBox()
        opt_cmb.setEditable(True)
        opt_cmb.addItem("")
        for bk in builtin_keys:
            opt_cmb.addItem(bk)
        opt_cmb.setCurrentText(item.option_command)
        self._zone_table.setCellWidget(row, 4, opt_cmb)

    def _save_zone_table(self, zone_id: str) -> None:
        zone = self._draft.hotbox_zones.get(zone_id)
        if zone is None:
            return
        new_items: list[MenuItem] = []
        for row in range(self._zone_table.rowCount()):
            holder = self._zone_table.cellWidget(row, 0)
            chk = holder.findChild(QtWidgets.QCheckBox) if holder else None
            lbl_edit = self._zone_table.cellWidget(row, 1)
            type_cmb = self._zone_table.cellWidget(row, 2)
            cmd_cmb = self._zone_table.cellWidget(row, 3)
            opt_cmb = self._zone_table.cellWidget(row, 4)

            label = lbl_edit.text().strip() if isinstance(lbl_edit, QtWidgets.QLineEdit) else ""
            cmd_type = str(type_cmb.currentData() or "builtin") if isinstance(type_cmb, QtWidgets.QComboBox) else "builtin"
            cmd_text = cmd_cmb.currentText().strip() if isinstance(cmd_cmb, QtWidgets.QComboBox) else ""
            opt_text = opt_cmb.currentText().strip() if isinstance(opt_cmb, QtWidgets.QComboBox) else ""
            if not label and not cmd_text:
                continue
            new_items.append(
                MenuItem(
                    label=label or cmd_text,
                    command_type=cmd_type,
                    command=cmd_text,
                    enabled=bool(chk.isChecked()) if chk else True,
                    option_command_type="builtin" if opt_text else "",
                    option_command=opt_text,
                )
            )
        zone.items = new_items

    def _handle_add_zone_item(self) -> None:
        self._append_zone_row(MenuItem(label="新命令", command_type="builtin", command="toggle_grid", enabled=True))

    def _handle_del_zone_item(self) -> None:
        row = self._zone_table.currentRow()
        if row >= 0:
            self._zone_table.removeRow(row)

    # ------------------------------------------------------------------ Actions
    def _handle_rescan(self) -> None:
        status = self._on_rescan_viewports()
        self._status_lbl.setText(status)

    def _handle_save_apply(self) -> None:
        self._collect_general_tab()
        if self._current_profile_id:
            self._save_radial_table(self._current_profile_id)
        if self._current_zone_id:
            self._save_zone_table(self._current_zone_id)
        self._config_manager.save(self._draft)
        self._on_config_applied(self._config_manager.config)
        self._status_lbl.setText(self._status_provider())
        QtWidgets.QMessageBox.information(self, PLUGIN_DISPLAY_NAME, "配置已保存并立即生效。")

    def _handle_reset(self) -> None:
        reply = QtWidgets.QMessageBox.question(
            self,
            PLUGIN_DISPLAY_NAME,
            "确定要将所有热盒设置和自定义菜单恢复为出厂默认值吗？",
        )
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        self._config_manager.reset_to_defaults(persist=True)
        self._draft = self._config_manager.clone_config()
        self._load_general_tab()
        self._load_radial_tab()
        self._load_hotbox_tab()
        self._on_config_applied(self._config_manager.config)

    def _handle_export(self) -> None:
        path_str, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "导出 MaxHotbox 配置", "max_hotbox_preset.json", "JSON (*.json)"
        )
        if path_str:
            self._collect_general_tab()
            if self._current_profile_id:
                self._save_radial_table(self._current_profile_id)
            if self._current_zone_id:
                self._save_zone_table(self._current_zone_id)
            self._config_manager.save(self._draft)
            self._config_manager.export_to(Path(path_str))
            QtWidgets.QMessageBox.information(self, PLUGIN_DISPLAY_NAME, f"配置已导出至:\n{path_str}")

    def _handle_import(self) -> None:
        path_str, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "导入 MaxHotbox 配置", "", "JSON (*.json)"
        )
        if path_str:
            try:
                self._config_manager.import_from(Path(path_str), persist=True)
                self._draft = self._config_manager.clone_config()
                self._load_general_tab()
                self._load_radial_tab()
                self._load_hotbox_tab()
                self._on_config_applied(self._config_manager.config)
                QtWidgets.QMessageBox.information(self, PLUGIN_DISPLAY_NAME, "配置导入成功并已生效。")
            except Exception as exc:
                QtWidgets.QMessageBox.warning(self, PLUGIN_DISPLAY_NAME, f"导入失败: {exc}")
