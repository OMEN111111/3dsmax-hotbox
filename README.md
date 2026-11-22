# MaxHotbox — Maya-Style Hotbox & Marking Menu for 3ds Max 2026

> **当前版本：`v0.1.0` (Beta 测试版)** · 适配 **Autodesk 3ds Max 2026 (Win64)** · 兼容中/英文界面

**MaxHotbox** 是一款为 **Autodesk 3ds Max 2026** 打造的 **Maya 风格热盒（Hotbox）与多级径向标记菜单（Marking Menu）** 插件。  
采用 **Win32 视口子类化 (`SetWindowSubclass`) + PySide6 (Qt 6.5) 悬浮渲染 + `pymxs`/MAXScript 解耦命令引擎 + Autodesk `.bundle` 标准打包**，在高度贴合 3ds Max 2026 原生深灰 UI 风格的同时，实现流畅的按住、划动、悬停展开、松开即执行的 Maya 式建模交互，并支持随时一键切换回原生四元菜单（Quad Menu）。

---

## 核心功能

### 1. 多级径向标记菜单（8 方向 + 悬停子菜单 `▸` + 下方扩展列表）
在任意 3D 视口内按住以下组合键并划动鼠标，松开即执行：
- **右键 (`RMB`)**：智能上下文菜单（根据选中的是多边形、样条线还是空白视口自动切换对象/子层级/创建菜单）。
- **`Shift + 右键`**：多边形建模菜单（按 Object / Vertex / Edge / Border / Polygon 子层级自动切换对应建模工具）。
- **`Ctrl + 右键`**：选择转换与扩展菜单（转顶点/边/面/元素、扩大/缩小、循环/环形边、软选择、反选）。
- **`Alt + 右键`**：视口与着色显示菜单（顶/前/左/右/透视/正交/相机视图、线框、边面、黏土着色、最大化视口）。
- **`Ctrl + Shift + 右键`**：坐标系、枢轴与捕捉菜单（局部/世界/视图/万向节坐标、仅影响轴、居中枢轴、Reset XForm）。
- **二级悬停子菜单 (`▸`)**：悬停在带 `▸` 的分类按钮（基础几何体、样条图形、相机与灯光、常用修改器、显示与孤立、视图切换、视口着色、枢轴与变换、切割与平面化、边选择扩展）上约 `180ms` 自动展开子菜单，按 `Backspace` 可返回上级。

### 2. Maya 风格右侧数值面板按钮（`□` Option Box）
针对高频建模与创建命令，按钮拆分为**主按钮**与**右侧 `□` 调整面板方块**：
- **划到主按钮松开**：直接进入 3ds Max 视口鼠标拖动交互（如直接拖动控制挤出长度、倒角、插入、切角、桥接、轮廓，或在视口拖动创建基础几何体）。
- **划到右侧 `□` 松开**：直接弹出对应功能的 **3ds Max 数值参数面板（Caddy / Dialog）** 进行精确数值调整（几何体为原点一键直出）。

### 3. 五区全局热盒（5-Zone Full Hotbox）
- 默认在视口内按住 `` ` ``（Tab 上方反引号键，可在设置面板中修改为 `Space` / `F8` / `F9` 或禁用）呼出中/北/南/西/东五区热盒，滑至目标命令松开即执行。
- 也可通过设置面板或 MacroScript 以点击模式呼出。

### 4. 原生 3ds Max 2026 UI 融合与一键切回四元菜单
- 默认采用 **3ds Max 2026 原生深灰主题**（提供 3 套主题、UI 缩放、半径、死区、透明度及自定义 JSON 菜单编辑器）。
- 启动后在 **3ds Max 2026 顶部菜单栏** 自动添加专属按钮 **`MaxHotbox [热盒]`**：
  - 点击即打开配置面板，顶部提供 **[Maya 热盒模式 (Hotbox)] / [3ds Max 原生四元菜单 (Quad)]** 一键切换。
  - 切回原生四元菜单后会立即卸载视口 Win32 钩子，零残留恢复原生四元菜单行为，按钮状态同步变为 `MaxHotbox [四元]`。
- 内置**安全工具模式保护**：按住左/中键取消操作或处于创建物体、Cut、Target Weld 等模态工具时自动放行右键。

---

## 安装方式（3ds Max 2026）

从 [Releases](https://github.com/OMEN111111/3dsmax-hotbox/releases) 页面下载最新测试版（`MaxHotbox_v0.1.0_Max2026.zip` 或 `MaxHotbox_v0.1.0_Max2026.mzp`）：

### 方式一：解压 ZIP 后双击 `install.bat`（推荐）
1. 解压 `MaxHotbox_v0.1.0_Max2026.zip`。
2. 双击运行 `install.bat`，按提示完成安装（自动部署到 `%APPDATA%\Autodesk\ApplicationPlugins\MaxHotbox.bundle`）。
3. **重启 3ds Max 2026** 即可自动加载；若 Max 已打开不想重启，可在顶部菜单点 **`脚本 (Scripting) -> 运行脚本 (Run Script)...`** 选择解压目录内的 `Load_MaxHotbox_Now.ms` 立即免重启激活。

### 方式二：使用 `.mzp` 单文件安装包
1. 打开 **3ds Max 2026**。
2. 将 `MaxHotbox_v0.1.0_Max2026.mzp` 直接拖拽到视口中（若 Max 以管理员身份运行导致 Windows 拦截拖拽，请改用 **`脚本 -> 运行脚本...`** 选择该 `.mzp` 文件）。
3. 安装脚本会自动部署并立即激活当前会话。

### 卸载方式
运行 `uninstall.bat`（或 `packaging/uninstall.ps1`）即可移除 `MaxHotbox.bundle`；附加 `-RemoveUserConfig` 参数可同时清理自定义配置文件与日志。

---

## 仓库目录结构

```text
3dsmax-hotbox/
├── README.md                  # 项目说明与使用指南
├── CHANGELOG.md               # 版本更新记录
├── src/
│   ├── max_hotbox/            # 插件 Python 核心包 (适配 Max 2026 Python 3.11 + PySide6)
│   └── maxscript/             # Max 2026 MacroScripts、启动引导与卸载辅助脚本
└── packaging/                 # Autodesk .bundle 清单、.mzp 与 Windows 安装/打包脚本
```

### 从源码自行打包
```powershell
python .\packaging\build_package.py
```
执行后会在本地 `dist/` 目录自动生成 `MaxHotbox.bundle/`、`MaxHotbox_v0.1.0_Max2026.zip`、`MaxHotbox_v0.1.0_Max2026.mzp` 与 SHA-256 校验文件。

---

## 配置与日志路径
- 用户配置：`%LOCALAPPDATA%\Autodesk\3dsMax\2026 - 64bit\<CHS|ENU>\userconfig\MaxHotbox\config.json`
- 运行日志：`%LOCALAPPDATA%\Autodesk\3dsMax\2026 - 64bit\<CHS|ENU>\userconfig\MaxHotbox\logs\max_hotbox.log`
