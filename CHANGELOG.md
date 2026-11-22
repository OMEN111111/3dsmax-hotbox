# Changelog

All notable changes to **MaxHotbox** will be documented in this file.

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
