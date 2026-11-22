# Changelog

All notable changes to **MaxHotbox** will be documented in this file.

## [0.1.1] - 2026-11-22 (Beta Update)

### Added
- **Graphite Modeling & Selection Tools (石墨工具整合与自建参数面板)**:
  - Integrated Swift Loop (快速循环), Flow Connect (流连接), Set Flow (设置流), Space Loop (间距均分), GeoPoly (几何体变圆), Quadrify All (全部四角化), Delete Iso Verts (清理孤立顶点), and Poly Constraints (无/边/面/法线约束).
  - Built native 3ds Max 2026 dark-styled PySide6 live-preview parameter panels (`□`) with zero Ribbon UI dependency:
    - **Random Select (随机选择)** — ratio slider `1%–100%`, scope toggle (all vs current selection), re-seed button, and cancel-to-restore.
    - **Select by Sides (按边数选择面)** — quick presets (Triangles `=3`, Quads `=4`, N-Gons `>4`) + custom comparison rules.
    - **Dot Loop / Dot Ring (点循环 / 点环形隔选)** — topological chain tracing with live step (`2–20`) and offset controls.
    - **Angle Select (硬边选择 / 共面选择)** — dihedral & coplanar angle threshold slider (`1°–179°`) with live preview.
- **Expanded Modifiers**: Added `OpenSubdiv`, `Weighted Normals`, `Edit Normals`, `FFD 2x2x2`, `FFD 4x4x4`, `Bend`, `Twist`, `Taper`, `Noise`, `Spherify`, `Push`, `Smooth`, `Lathe`, `Sweep`, `UVW Map`, `ProOptimizer`, organized into `常用修改器` + `变形与UV修改器` submenus.
- **Maya `Space + RMB` Hotbox**: Hold `Space + RMB` in any 3D viewport to open the Maya-style Viewpoint & Quick Hotbox marking menu (automatically suppresses `Space` keyup so 3ds Max Selection Lock never toggles accidentally).
- **One-Click Install & Uninstall Scripts**: Added root-level `install.bat` and `uninstall.bat` (supports installing directly from a Git clone without prebuilt `dist/`, plus live 3ds Max process detection and interactive config cleanup).

### Fixed
- **Maya-Style Mouse Return to Parent Submenu**: Replaced unreliable `Backspace` keyboard return with 100% mouse-driven parent return — hover the non-overlapping `‹ 返回上级` pill below the submenu hub (with dwell progress bar) OR tap `LMB` while holding `RMB` to immediately return to the parent menu.

## [0.1.0] - 2026-11-22 (First Beta Release)

### Highlights
- **3ds Max 2026 Support**: First beta release built for Autodesk 3ds Max 2026 (Win64, Python 3.11, PySide6 / Qt 6.5, `#cuiRegisterMenus`), compatible with both Chinese (`CHS`) and English (`ENU`) interfaces.
- **Multi-Level Maya-Style Radial Marking Menus (`▸`)**:
  - Context-aware `RMB` (Editable Poly / Spline / Empty Scene), `Shift+RMB` (Object / Vertex / Edge / Border / Polygon), `Ctrl+RMB` (Selection & Convert), `Alt+RMB` (Viewport & Display), and `Ctrl+Shift+RMB` (Transform & Pivot).
  - 10 hover-expandable child radial submenus (Primitives, Splines, Cameras & Lights, Modifiers, Visibility, Views, Shading, Pivot, Cut & Planar, Edge Selection) with dwell progress indicator and `Backspace` parent return.
- **Maya-Style Right-Side Option Boxes (`□`)**:
  - Modeling & creation actions (Extrude, Inset, Bevel, Chamfer, Connect, Bridge, Weld, Outline, Relax, Detach, Create Shape, Box, Sphere, Cylinder, Plane, etc.) split into main viewport-interactive drag/create mode and right-side `□` numeric caddy / instant-create mode.
- **5-Zone Full Hotbox**:
  - Configurable hold-key trigger (default `` ` ``, customizable to `Space` / `F8` / `F9` / disabled) or click-to-run mode with Center / North / South / West / East zones.
- **Native 3ds Max 2026 Styling & Smooth Performance**:
  - Flat neutral dark gray theme (`max2026_native`), refined Autodesk blue highlight, zero-overlap 8-way layout, and lightweight in-place repainting for smooth cursor tracking.
- **Dedicated Menu Bar Button & 1-Click Native Quad Menu Switch**:
  - Adds `MaxHotbox [热盒]` / `MaxHotbox [四元]` directly to the 3ds Max 2026 menu bar; clicking opens the visual Settings & Menu Editor with instant 1-click switching back to 3ds Max's native Quad Menu.
- **Standard Packaging**:
  - Autodesk `.bundle` package (`PackageContents.xml`), drag-and-drop / Run Script `.mzp` installer, release `.zip`, Windows `install.bat` / `uninstall.bat`, and live hot-reload script `Load_MaxHotbox_Now.ms`.
