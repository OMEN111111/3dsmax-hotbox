# MaxHotbox — Maya-Style Hotbox & Marking Menu for 3ds Max 2026

> **当前版本：`v0.1.1` (Beta 测试版)** · 适配 **Autodesk 3ds Max 2026 (Win64)** · 兼容中/英文界面

**MaxHotbox** 是一款为 **Autodesk 3ds Max 2026** 打造的 **Maya 风格热盒（Hotbox）与多级径向标记菜单（Marking Menu）** 插件。  
采用 **Win32 视口子类化 (`SetWindowSubclass`) + PySide6 (Qt 6.5) 悬浮渲染 + `pymxs`/MAXScript 解耦命令引擎 + Autodesk `.bundle` 标准打包**，在高度贴合 3ds Max 2026 原生深灰 UI 风格的同时，实现流畅的按住、划动、悬停展开、松开即执行的 Maya 式建模交互，并支持随时一键切换回原生四元菜单（Quad Menu）。

---

## 核心功能

### 1. 多级径向标记菜单（8 方向 + 悬停子菜单 `▸` + Maya 鼠标返回上级）
在任意 3D 视口内按住以下组合键并划动鼠标，松开即执行：
- **右键 (`RMB`)**：智能上下文菜单（根据选中的是多边形、样条线还是空白视口自动切换对象/子层级/创建菜单）。
- **`Shift + 右键`**：多边形建模菜单（按 Object / Vertex / Edge / Border / Polygon 子层级自动切换，整合石墨建模、切割平面化与多边形工具）。
- **`Ctrl + 右键`**：选择转换与石墨选择菜单（转顶点/边/面/元素、随机选择、点循环/点环形、选多边面、硬边与共面选择）。
- **`Alt + 右键`**：视口与着色显示菜单（顶/前/左/右/后/底/透视/正交/相机视图、线框、边面、黏土着色、最大化视口）。
- **`Ctrl + Shift + 右键`**：坐标系、枢轴与捕捉菜单（局部/世界/视图/万向节坐标、仅影响轴、居中枢轴、轴到底部、Reset XForm）。
- **`Space + 右键`（Maya 空格热盒）**：参考 Maya 按住空格+右键唤出视图与快捷热盒，自动屏蔽空格松开避免误触 3ds Max 选择锁定。
- **二级悬停子菜单 (`▸`) 与纯鼠标返回上级**：悬停在带 `▸` 按钮上约 `180ms` 自动展开子菜单；展开后**悬停中心下方的 `‹ 返回上级` 按钮**或**按住右键同时轻点左键**即可立即返回上一级菜单，无需键盘按键。

### 2. 石墨工具整合 & 自建 PySide6 实时预览参数面板（`□` Option Box）
不依赖 Ribbon 原界面按钮，内置高频石墨工具并重构了原生 3ds Max 2026 风格实时预览悬浮面板（点击按钮右侧 `□` 唤出，取消自动还原原始选择）：
- **随机选择 (`Random Select`)**：主按钮按上次比例快选；`□` 面板支持 `1%~100%` 比例滑块、全部/当前选集范围切换与“换一批”实时预览。
- **按边数选择面 (`Select by Sides`)**：主按钮一键选多边面 `N-Gon (>4)`；`□` 面板支持三角面/四边面/多边面预设及自定义边数条件。
- **点循环 / 点环形 (`Dot Loop` / `Dot Ring`)**：基于纯 `polyop` 拓扑链路追踪，`□` 面板支持步长 (`2~20`) 与偏移实时预览。
- **硬边选择 / 共面选择 (`Angle Select`)**：基于面法线夹角算法，`□` 面板支持 `1°~179°` 角度阈值实时预览。
- **更多石墨建模与常用修改器**：整合快速循环 (`Swift Loop`)、流连接 (`Flow Connect`)、设置流 (`Set Flow`)、间距均分 (`Space Loop`)、几何体变圆 (`GeoPoly`)、全部四角化 (`Quadrify All`)、约束切换（无/边/面/法线），以及 25+ 常用建模/变形/UV/法线修改器。
- **建模交互 vs 数值面板 (`□`)**：挤出、插入、倒角、切角、连接、桥接、焊接、轮廓及基础几何体等，主按钮进入视口交互拖动/绘制，右侧 `□` 打开对应 3ds Max 数值参数面板（几何体为原点直出）。

### 3. 五区全局热盒 & 一键切回原生四元菜单
- 默认在视口内按住 `` ` ``（Tab 上方反引号键，可在设置面板改为 `Space` / `F8` / `F9` 或禁用）呼出中/北/南/西/东五区热盒。
- 启动后在 **3ds Max 2026 顶部菜单栏** 自动添加专属按钮 **`MaxHotbox [热盒]`**，点击即打开配置面板，顶部提供 **[Maya 热盒模式] / [3ds Max 原生四元菜单]** 一键切换，切回四元菜单后立即卸载视口钩子。

---

## 一键安装与一键卸载（3ds Max 2026）

从 [Releases](https://github.com/OMEN111111/3dsmax-hotbox/releases) 下载 `MaxHotbox_v0.1.1_Max2026.zip`（或直接克隆本仓库）：

### 方式一：一键安装脚本（最推荐）
1. 双击根目录下的 **`install.bat`**（支持直接从压缩包或源码仓库一键组装并部署到 `%APPDATA%\Autodesk\ApplicationPlugins\MaxHotbox.bundle`）。
2. 重启 **3ds Max 2026** 自动生效；若 Max 已打开不想重启，点击顶部菜单 **`脚本 (Scripting) -> 运行脚本 (Run Script)...`** 选择 `Load_MaxHotbox_Now.ms` 立即热重载激活。

### 方式二：`.mzp` 单文件安装
打开 **3ds Max 2026**，将 `MaxHotbox_v0.1.1_Max2026.mzp` 拖入视口（若管理员权限拦截拖拽，改用 **`脚本 -> 运行脚本...`** 选择该 `.mzp` 文件）即可一键安装并立即激活。

### 一键卸载
双击根目录下的 **`uninstall.bat`** 即可移除插件包，并可选择是否同时清理个人配置与日志。

---

## 仓库目录结构

```text
3dsmax-hotbox/
├── install.bat                # Windows 一键安装脚本
├── uninstall.bat              # Windows 一键卸载脚本
├── README.md                  # 项目说明与使用指南
├── CHANGELOG.md               # 版本更新记录
├── src/
│   ├── max_hotbox/            # 插件 Python 核心包 (适配 Max 2026 Python 3.11 + PySide6)
│   └── maxscript/             # Max 2026 MacroScripts、启动引导与卸载辅助脚本
└── packaging/                 # Autodesk .bundle 清单、.mzp 与安装/打包脚本
```

### 从源码自行打包
```powershell
python .\packaging\build_package.py
```
执行后会在本地 `dist/` 目录自动生成 `MaxHotbox.bundle/`、`MaxHotbox_v0.1.1_Max2026.zip`、`MaxHotbox_v0.1.1_Max2026.mzp`、`install.bat`、`uninstall.bat`、`Load_MaxHotbox_Now.ms` 与 SHA-256 校验文件。
