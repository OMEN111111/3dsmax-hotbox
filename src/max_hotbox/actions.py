"""3ds Max 2026 command execution engine for MaxHotbox (supports interactive & Option Box numeric modes)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .config import MenuItem
from .logger import get_logger

# Built-in command catalog (command_id -> Chinese/English description)
BUILTIN_COMMAND_CATALOG: dict[str, str] = {
    # Sub-object levels
    "subobj_object": "退出子对象层级 (Object Mode / 0)",
    "subobj_vertex": "顶点子层级 (Vertex / 1)",
    "subobj_edge": "边/线段子层级 (Edge / Segment / 2)",
    "subobj_border": "边界/样条子层级 (Border / Spline / 3)",
    "subobj_polygon": "多边形子层级 (Polygon / 4)",
    "subobj_element": "元素子层级 (Element / 5)",
    "subobj_spline_vertex": "样条线顶点层级 (Spline Vertex / 1)",
    "subobj_spline_segment": "样条线线段层级 (Spline Segment / 2)",
    "subobj_spline_spline": "样条线子层级 (Spline / 3)",
    # Convert & stack
    "convert_to_poly": "转换为可编辑多边形 (Convert to Editable Poly)",
    "convert_to_spline": "转换为可编辑样条线 (Convert to Editable Spline)",
    "collapse_stack": "塌陷修改器堆栈 (Collapse Stack)",
    "clone_object": "原位克隆对象 (Clone Selection)",
    # Modifiers — Core / UV / Deform / Topology / Spline
    "mod_edit_poly": "添加 Edit Poly 编辑多边形修改器",
    "mod_turbosmooth": "添加 TurboSmooth 涡轮平滑修改器",
    "mod_opensubdiv": "添加 OpenSubdiv 细分修改器",
    "mod_symmetry": "添加 Symmetry 对称修改器",
    "mod_shell": "添加 Shell 壳修改器",
    "mod_unwrap_uvw": "添加 Unwrap UVW 展UV修改器",
    "mod_uvw_map": "添加 UVW Map 贴图坐标修改器",
    "mod_uvw_clear": "添加 UVW Mapping Clear 清除UV修改器",
    "mod_uvw_xform": "添加 UVW XForm 变换UV修改器",
    "mod_uvw_add": "添加 UVW Mapping Add 添加UV通道修改器",
    "mod_projection": "添加 Projection 烘焙投影修改器",
    "mod_mapscaler": "添加 MapScaler 贴图缩放修改器",
    "mod_extrude": "添加 Extrude 挤出修改器",
    "mod_chamfer": "添加 Chamfer 切角修改器",
    "mod_weighted_normals": "添加 Weighted Normals 加权法线修改器",
    "mod_edit_normals": "添加 Edit Normals 编辑法线修改器",
    "mod_ffd2": "添加 FFD 2x2x2 自由变形修改器",
    "mod_ffd3": "添加 FFD 3x3x3 自由变形修改器",
    "mod_ffd4": "添加 FFD 4x4x4 自由变形修改器",
    "mod_bend": "添加 Bend 弯曲修改器",
    "mod_twist": "添加 Twist 扭曲修改器",
    "mod_taper": "添加 Taper 锥化修改器",
    "mod_noise": "添加 Noise 噪波修改器",
    "mod_relax": "添加 Relax 松弛修改器",
    "mod_spherify": "添加 Spherify 球形化修改器",
    "mod_push": "添加 Push 推力修改器",
    "mod_wave": "添加 Wave 波浪修改器",
    "mod_ripple": "添加 Ripple 涟漪修改器",
    "mod_stretch": "添加 Stretch 拉伸修改器",
    "mod_skew": "添加 Skew 倾斜修改器",
    "mod_displace": "添加 Displace 置换修改器",
    "mod_smooth": "添加 Smooth 平滑修改器",
    "mod_lathe": "添加 Lathe 车削修改器",
    "mod_sweep": "添加 Sweep 扫描修改器",
    "mod_prooptimizer": "添加 ProOptimizer 减面优化修改器",
    "mod_cap_holes": "添加 Cap Holes 补洞修改器",
    "mod_lattice": "添加 Lattice 晶格修改器",
    "mod_slice": "添加 Slice 切片修改器",
    "mod_quadify_mesh": "添加 Quadify Mesh 网格四角化修改器",
    "mod_turn_to_poly": "添加 Turn to Poly 转多边形修改器",
    "mod_delete_mesh": "添加 DeleteMesh 删除网格修改器",
    "mod_mirror": "添加 Mirror 镜像修改器",
    # Spline Modifiers (样条线修改器)
    "mod_normalize_spline": "添加 Normalize Spline 规格化样条线修改器",
    "mod_edit_spline": "添加 Edit Spline 编辑样条线修改器",
    "mod_bevel": "添加 Bevel 倒角修改器",
    "mod_bevel_profile": "添加 Bevel Profile 倒角剖面修改器",
    "mod_surface": "添加 Surface 曲面修改器",
    "mod_crosssection": "添加 CrossSection 横截面修改器",
    "mod_fillet_chamfer": "添加 Fillet/Chamfer 样条圆角切角修改器",
    "mod_spline_relax": "添加 Spline Relax 样条松弛修改器",
    "mod_renderable_spline": "添加 Renderable Spline 可渲染样条线修改器",
    "mod_garment_maker": "添加 Garment Maker 服装生成器修改器",
    "mod_spline_select": "添加 Spline Select 样条线选择修改器",
    # Graphite Modeling & Selection Tools (石墨工具 + 自建参数面板)
    "graphite_swift_loop": "石墨: 快速循环加线 (Swift Loop)",
    "graphite_step_loop": "石墨: 步骤循环 (Step Loop)",
    "graphite_flow_connect": "石墨: 流连接 (Flow Connect)",
    "graphite_set_flow": "石墨: 设置流 (Set Flow)",
    "graphite_space_loop": "石墨: 间距均分 (Space Loop)",
    "graphite_geopoly": "石墨: 几何体变圆 (GeoPoly)",
    "graphite_quadrify": "石墨: 全部四角化 (Quadrify All)",
    "graphite_remove_iso_verts": "石墨: 清理孤立顶点 (Delete Iso Verts)",
    "graphite_constrain_none": "石墨约束: 无约束 (None)",
    "graphite_constrain_edge": "石墨约束: 边约束 (Edge)",
    "graphite_constrain_face": "石墨约束: 面约束 (Face)",
    "graphite_constrain_normal": "石墨约束: 法线约束 (Normal)",
    "graphite_random_select": "石墨: 随机选择 (快速执行)",
    "graphite_random_select_settings": "石墨: 随机选择比例面板 (自建 □)",
    "graphite_select_ngons": "石墨: 选择多边面 N-Gon (>4边)",
    "graphite_select_by_sides_settings": "石墨: 按边数选择面面板 (自建 □)",
    "graphite_dot_loop": "石墨: 点循环隔选 (Dot Loop)",
    "graphite_dot_loop_settings": "石墨: 点循环步长面板 (自建 □)",
    "graphite_dot_ring": "石墨: 点环形隔选 (Dot Ring)",
    "graphite_dot_ring_settings": "石墨: 点环形步长面板 (自建 □)",
    "graphite_select_hard_edges": "石墨: 按角度选硬边 (Hard Edges)",
    "graphite_select_hard_edges_settings": "石墨: 硬边角度阈值面板 (自建 □)",
    "graphite_select_by_angle": "石墨: 按角度选共面 (Select by Angle)",
    "graphite_select_by_angle_settings": "石墨: 共面角度阈值面板 (自建 □)",
    "graphite_select_similar": "石墨: 选择相似 (Select Similar)",
    "graphite_select_similar_settings": "石墨: 选择相似容差面板 (自建 □)",
    # Poly modeling — Interactive viewport drag (main button)
    "poly_extrude": "挤出 - 视口鼠标拖动 (Interactive Extrude)",
    "poly_inset": "插入 - 视口鼠标拖动 (Interactive Inset)",
    "poly_bevel": "倒角 - 视口鼠标拖动 (Interactive Bevel)",
    "poly_outline": "轮廓 - 视口鼠标拖动 (Interactive Outline)",
    "poly_chamfer": "切角 - 视口鼠标拖动 (Interactive Chamfer)",
    "poly_connect": "连接 - 快速执行 (Quick Connect)",
    "poly_bridge": "桥接 - 视口交互 (Interactive Bridge)",
    "poly_weld": "目标焊接 - 视口交互 (Target Weld)",
    "poly_target_weld": "目标焊接 (Target Weld)",
    "poly_relax": "松弛 - 快速执行 (Quick Relax)",
    "poly_detach": "分离多边形 (Detach)",
    "poly_create_shape": "从边创建图形 (Create Shape)",
    # Poly modeling — Numeric settings panel (Option Box □)
    "poly_extrude_settings": "挤出数值面板 (Extrude Settings)",
    "poly_inset_settings": "插入数值面板 (Inset Settings)",
    "poly_bevel_settings": "倒角数值面板 (Bevel Settings)",
    "poly_outline_settings": "轮廓数值面板 (Outline Settings)",
    "poly_chamfer_settings": "切角数值面板 (Chamfer Settings)",
    "poly_connect_settings": "连接数值面板 (Connect Settings)",
    "poly_bridge_settings": "桥接数值面板 (Bridge Settings)",
    "poly_weld_settings": "焊接数值面板 (Weld Settings)",
    "poly_relax_settings": "松弛数值面板 (Relax Settings)",
    "poly_detach_settings": "分离选项面板 (Detach Settings)",
    "poly_create_shape_settings": "创建图形选项面板 (Create Shape Settings)",
    # Poly direct tools & cut/planar
    "poly_break": "断开顶点 (Break)",
    "poly_remove": "移除边/顶点 (Remove)",
    "poly_clean_remove": "清理边并删除孤立顶点 (Clean Remove)",
    "poly_split": "分割边 (Split)",
    "poly_collapse": "塌陷子对象 (Collapse)",
    "poly_cap": "边界封口 (Cap)",
    "poly_flip": "翻转法线 (Flip Normals)",
    "poly_attach": "附加对象 (Attach)",
    "poly_cut": "切割工具 (Cut)",
    "poly_quickslice": "快速切片 (QuickSlice)",
    "poly_slice_plane": "切片平面 (Slice Plane)",
    "poly_make_planar": "最佳平面化 (Make Planar)",
    "poly_planar_x": "X 轴平面化 (Make Planar X)",
    "poly_planar_y": "Y 轴平面化 (Make Planar Y)",
    "poly_planar_z": "Z 轴平面化 (Make Planar Z)",
    "poly_autosmooth": "自动平滑 (Auto Smooth)",
    "poly_autosmooth_settings": "平滑组与自动平滑设置面板 (自建 □)",
    "poly_clear_sg": "清除平滑组 (Clear Smoothing Groups)",
    "poly_soft_selection": "切换软选择 (Toggle Soft Selection)",
    "poly_loop": "循环边选择 (Edge Loop)",
    "poly_ring": "环形边选择 (Edge Ring)",
    "poly_grow": "扩大选择 (Grow Selection)",
    "poly_shrink": "缩小选择 (Shrink Selection)",
    "poly_border_to_edge": "边界转边选择 (Border to Edge)",
    # Selection conversion
    "convert_sel_vertex": "转换选择为顶点 (Convert to Vertex)",
    "convert_sel_edge": "转换选择为边 (Convert to Edge)",
    "convert_sel_poly": "转换选择为多边形 (Convert to Polygon)",
    "convert_sel_element": "转换选择为元素 (Convert to Element)",
    "select_invert": "反选 (Invert Selection)",
    "select_all": "全选 (Select All)",
    "select_none": "清除选择 (Select None)",
    # Spline operations (样条线三层级完整工具)
    "spline_refine": "样条: 优化加点 (Refine)",
    "spline_insert": "样条: 插入顶点 (Insert)",
    "spline_weld": "样条: 焊接顶点 (Weld)",
    "spline_fuse": "样条: 融合顶点 (Fuse)",
    "spline_break": "样条: 断开顶点 (Break)",
    "spline_fillet": "样条: 顶点圆角 (Fillet)",
    "spline_chamfer": "样条: 顶点切角 (Chamfer)",
    "spline_connect": "样条: 连接端点 (Connect)",
    "spline_cross_insert": "样条: 跨接插入 (Cross Insert)",
    "spline_make_first": "样条: 设为首顶点 (Make First)",
    "spline_cycle": "样条: 循环顶点 (Cycle)",
    "spline_knot_corner": "样条顶点类型: 角点 (Corner)",
    "spline_knot_smooth": "样条顶点类型: 平滑 (Smooth)",
    "spline_knot_bezier": "样条顶点类型: 贝塞尔 (Bezier)",
    "spline_knot_bezier_corner": "样条顶点类型: 贝塞尔角点 (Bezier Corner)",
    "spline_divide": "样条线段: 拆分 (Divide)",
    "spline_divide_settings": "样条线段: 拆分分段数面板 (自建 □)",
    "spline_detach": "样条: 分离 (Detach)",
    "spline_attach": "样条: 附加 (Attach)",
    "spline_seg_line": "样条线段: 转为直线 (Line)",
    "spline_seg_curve": "样条线段: 转为曲线 (Curve)",
    "spline_outline": "样条: 轮廓偏移 (Outline)",
    "spline_trim": "样条: 修剪 (Trim)",
    "spline_extend": "样条: 延伸 (Extend)",
    "spline_bool_union": "样条布尔: 并集 (Union)",
    "spline_bool_subtract": "样条布尔: 差集 (Subtract)",
    "spline_bool_intersect": "样条布尔: 交集 (Intersect)",
    "spline_reverse": "样条: 反转方向 (Reverse)",
    "spline_close": "样条: 闭合曲线 (Close)",
    "spline_explode": "样条: 炸开为独立对象 (Explode)",
    "spline_mirror_horiz": "样条: 水平镜像 (Mirror Horizontal)",
    # Scene visibility, shading & isolation
    "toggle_isolate": "切换孤立选择 (Isolate Selection)",
    "hide_selected": "隐藏选中对象 (Hide Selected)",
    "hide_unselected": "隐藏未选对象 (Hide Unselected)",
    "unhide_all": "全部取消隐藏 (Unhide All)",
    "freeze_selected": "冻结选中对象 (Freeze Selected)",
    "unfreeze_all": "全部解冻 (Unfreeze All)",
    "toggle_xray": "切换半透明 X-Ray (Alt+X)",
    "toggle_backface_cull": "切换背面消隐 (Backface Cull)",
    # Transform & Pivot
    "center_pivot": "轴居中到对象 (Center Pivot)",
    "pivot_to_bottom": "轴对齐到底部中心 (Pivot to Bottom)",
    "pivot_to_origin": "轴归零世界原点 (Pivot to World Origin)",
    "reset_xform": "重置变换并塌陷 (Reset XForm)",
    "toggle_pivot_only": "切换仅影响轴 (Affect Pivot Only)",
    "coordsys_local": "局部坐标系 (Local CoordSys)",
    "coordsys_world": "世界坐标系 (World CoordSys)",
    "coordsys_view": "视图坐标系 (View CoordSys)",
    "coordsys_gimbal": "万向节坐标系 (Gimbal CoordSys)",
    "gizmo_center_pivot": "变换中心: 使用轴点中心 (Use Pivot Point Center)",
    "gizmo_center_selection": "变换中心: 使用选择中心 (Use Selection Center)",
    "gizmo_center_transform": "变换中心: 使用变换坐标中心 (Use Transform Coord Center)",
    "toggle_snap": "切换捕捉 (Snap Toggle)",
    "toggle_angle_snap": "切换角度捕捉 (Angle Snap Toggle)",
    "tool_move": "移动工具 (Select and Move)",
    "tool_rotate": "旋转工具 (Select and Rotate)",
    "tool_scale": "缩放工具 (Select and Scale)",
    # Viewport & Display
    "view_perspective": "透视图 (Perspective)",
    "view_top": "顶视图 (Top)",
    "view_front": "前视图 (Front)",
    "view_left": "左视图 (Left)",
    "view_right": "右视图 (Right)",
    "view_back": "后视图 (Back)",
    "view_bottom": "底视图 (Bottom)",
    "view_ortho": "正交视图 (Orthographic)",
    "view_camera": "相机视图 (Camera View)",
    "toggle_safeframes": "切换安全框 (Safe Frames / Shift+F)",
    "zoom_extents_sel": "聚焦选中对象 (Zoom Extents Selected)",
    "zoom_extents_all": "最大化显示全部 (Zoom Extents All)",
    "toggle_wireframe": "切换线框/着色显示 (F3)",
    "toggle_edged_faces": "切换边面显示 (F4)",
    "shading_default": "默认明暗处理 (Default Shading)",
    "shading_clay": "黏土着色 (Clay Shading)",
    "shading_facets": "面片着色 (Facets Shading)",
    "toggle_maximize_viewport": "切换最大化视口 (Alt+W)",
    "toggle_grid": "切换视口网格 (G)",
    "toggle_stats": "切换视口统计信息 (7)",
    # Create Primitives — Interactive viewport draw vs instant origin creation
    "create_box_interactive": "交互创建长方体 (Interactive Box)",
    "create_box": "原点快速创建长方体 (Instant Box)",
    "create_sphere_interactive": "交互创建球体 (Interactive Sphere)",
    "create_sphere": "原点快速创建球体 (Instant Sphere)",
    "create_cylinder_interactive": "交互创建圆柱体 (Interactive Cylinder)",
    "create_cylinder": "原点快速创建圆柱体 (Instant Cylinder)",
    "create_plane_interactive": "交互创建平面 (Interactive Plane)",
    "create_plane": "原点快速创建平面 (Instant Plane)",
    "create_torus_interactive": "交互创建圆环 (Interactive Torus)",
    "create_torus": "原点快速创建圆环 (Instant Torus)",
    "create_cone_interactive": "交互创建圆锥 (Interactive Cone)",
    "create_cone": "原点快速创建圆锥 (Instant Cone)",
    "create_tube_interactive": "交互创建管状体 (Interactive Tube)",
    "create_tube": "原点快速创建管状体 (Instant Tube)",
    "create_geosphere_interactive": "交互创建几何球体 (Interactive GeoSphere)",
    "create_geosphere": "原点快速创建几何球体 (Instant GeoSphere)",
    # Create Splines
    "create_line": "交互创建线 (Line)",
    "create_circle": "交互创建圆 (Circle)",
    "create_rectangle": "交互创建矩形 (Rectangle)",
    "create_arc": "交互创建弧 (Arc)",
    "create_helix": "交互创建螺旋线 (Helix)",
    "create_star": "交互创建星形 (Star)",
    "create_text": "交互创建文本 (Text)",
    "create_ngon": "交互创建多边形 (NGon)",
    # Create Cameras, Lights & Helpers
    "camera_from_view": "从当前视图创建相机 (Camera from View)",
    "create_target_camera": "交互创建目标相机 (Target Camera)",
    "create_free_light": "交互创建自由聚光灯 (Free Spot)",
    "create_target_light": "交互创建目标聚光灯 (Target Spot)",
    "create_point_helper": "创建辅助点 (Point Helper)",
    "create_dummy_helper": "创建虚拟体 (Dummy Helper)",
    "create_grid_helper": "创建辅助栅格 (Grid Helper)",
    # Plugin UI actions
    "open_settings": "打开 MaxHotbox 设置与菜单编辑器",
    "open_full_hotbox": "打开五区全局热盒 (Full Hotbox)",
    "switch_to_quad_menu": "切换回 3ds Max 原生四元菜单",
}


# IMPORTANT: Every multi-statement MAXScript MUST be wrapped in outer `(...)`
# so `local` declarations are always valid inside `pymxs.runtime.execute(...)`.
_BUILTIN_MAXSCRIPTS: dict[str, str] = {
    # ------------------------------------------------------------ Sub-objects
    "subobj_object": "(subObjectLevel = 0; redrawViews())",
    "subobj_vertex": (
        "(if selection.count > 0 do ("
        "if (getCommandPanelTaskMode() != #modify) do (setCommandPanelTaskMode #modify);"
        "subObjectLevel = 1; redrawViews()))"
    ),
    "subobj_edge": (
        "(if selection.count > 0 do ("
        "if (getCommandPanelTaskMode() != #modify) do (setCommandPanelTaskMode #modify);"
        "subObjectLevel = 2; redrawViews()))"
    ),
    "subobj_border": (
        "(if selection.count > 0 do ("
        "if (getCommandPanelTaskMode() != #modify) do (setCommandPanelTaskMode #modify);"
        "subObjectLevel = 3; redrawViews()))"
    ),
    "subobj_polygon": (
        "(if selection.count > 0 do ("
        "if (getCommandPanelTaskMode() != #modify) do (setCommandPanelTaskMode #modify);"
        "subObjectLevel = 4; redrawViews()))"
    ),
    "subobj_element": (
        "(if selection.count > 0 do ("
        "if (getCommandPanelTaskMode() != #modify) do (setCommandPanelTaskMode #modify);"
        "subObjectLevel = 5; redrawViews()))"
    ),
    "subobj_spline_vertex": (
        "(if selection.count > 0 do ("
        "max modify mode;"
        "if (numSubObjectLevels > 0) then (subObjectLevel = 1; redrawViews()) "
        "else (pushPrompt \"MaxHotbox: 参数化图形无子层级，请先转换为可编辑样条线或添加 Edit Spline\")))"
    ),
    "subobj_spline_segment": (
        "(if selection.count > 0 do ("
        "max modify mode;"
        "if (numSubObjectLevels >= 2) then (subObjectLevel = 2; redrawViews()) "
        "else (pushPrompt \"MaxHotbox: 参数化图形无子层级，请先转换为可编辑样条线或添加 Edit Spline\")))"
    ),
    "subobj_spline_spline": (
        "(if selection.count > 0 do ("
        "max modify mode;"
        "if (numSubObjectLevels >= 3) then (subObjectLevel = 3; redrawViews()) "
        "else (pushPrompt \"MaxHotbox: 参数化图形无子层级，请先转换为可编辑样条线或添加 Edit Spline\")))"
    ),
    # -------------------------------------------------------- Convert & Stack
    "convert_to_poly": (
        '(undo "MaxHotbox: Convert to Poly" on ('
        "if selection.count > 0 do (subObjectLevel = 0; convertToPoly selection)))"
    ),
    "convert_to_spline": (
        '(undo "MaxHotbox: Convert to Spline" on ('
        "if selection.count > 0 do (subObjectLevel = 0; convertToSplineShape selection)))"
    ),
    "collapse_stack": (
        '(undo "MaxHotbox: Collapse Stack" on ('
        "if selection.count > 0 do (subObjectLevel = 0; for o in selection do collapseStack o)))"
    ),
    "clone_object": (
        '(undo "MaxHotbox: Clone" on ('
        "if selection.count > 0 do (local clones = #(); maxOps.cloneNodes (selection as array) cloneType:#copy newNodes:&clones; select clones)))"
    ),
    # -------------------------------------------------------------- Modifiers
    "mod_edit_poly": (
        '(undo "MaxHotbox: Add Edit Poly" on ('
        "if selection.count > 0 do (setCommandPanelTaskMode #modify; modPanel.addModToSelection (Edit_Poly()) ui:on)))"
    ),
    "mod_turbosmooth": (
        '(undo "MaxHotbox: Add TurboSmooth" on ('
        "if selection.count > 0 do (setCommandPanelTaskMode #modify; modPanel.addModToSelection (TurboSmooth iterations:1) ui:on)))"
    ),
    "mod_opensubdiv": (
        '(undo "MaxHotbox: Add OpenSubdiv" on ('
        "if selection.count > 0 do (setCommandPanelTaskMode #modify; modPanel.addModToSelection (OpenSubdiv iterations:1) ui:on)))"
    ),
    "mod_symmetry": (
        '(undo "MaxHotbox: Add Symmetry" on ('
        "if selection.count > 0 do (setCommandPanelTaskMode #modify; modPanel.addModToSelection (Symmetry()) ui:on)))"
    ),
    "mod_shell": (
        '(undo "MaxHotbox: Add Shell" on ('
        "if selection.count > 0 do (setCommandPanelTaskMode #modify; modPanel.addModToSelection (Shell outerAmount:2.0) ui:on)))"
    ),
    "mod_unwrap_uvw": (
        '(undo "MaxHotbox: Add Unwrap UVW" on ('
        "if selection.count > 0 do (setCommandPanelTaskMode #modify; modPanel.addModToSelection (Unwrap_UVW()) ui:on)))"
    ),
    "mod_uvw_map": (
        '(undo "MaxHotbox: Add UVW Map" on ('
        "if selection.count > 0 do (subObjectLevel = 0; setCommandPanelTaskMode #modify; try (modPanel.addModToSelection (Uvwmap maptype:4) ui:on) catch (for o in selection do addModifier o (Uvwmap maptype:4)))))"
    ),
    "mod_uvw_clear": (
        '(undo "MaxHotbox: UVW Mapping Clear" on ('
        "if selection.count > 0 do (subObjectLevel = 0; setCommandPanelTaskMode #modify; try (modPanel.addModToSelection (UVW_Mapping_Clear mapID:1) ui:on) catch (for o in selection do addModifier o (UVW_Mapping_Clear mapID:1)))))"
    ),
    "mod_uvw_xform": (
        '(undo "MaxHotbox: UVW XForm" on ('
        "if selection.count > 0 do (subObjectLevel = 0; setCommandPanelTaskMode #modify; try (modPanel.addModToSelection (UVW_Xform()) ui:on) catch (for o in selection do addModifier o (UVW_Xform())))))"
    ),
    "mod_uvw_add": (
        '(undo "MaxHotbox: UVW Mapping Add" on ('
        "if selection.count > 0 do (subObjectLevel = 0; setCommandPanelTaskMode #modify; try (modPanel.addModToSelection (UVW_Mapping_Add()) ui:on) catch (for o in selection do addModifier o (UVW_Mapping_Add())))))"
    ),
    "mod_projection": (
        '(undo "MaxHotbox: Projection" on ('
        "if selection.count > 0 do (subObjectLevel = 0; setCommandPanelTaskMode #modify; try (modPanel.addModToSelection (Projection()) ui:on) catch (for o in selection do addModifier o (Projection())))))"
    ),
    "mod_mapscaler": (
        '(undo "MaxHotbox: MapScaler" on ('
        "if selection.count > 0 do (subObjectLevel = 0; setCommandPanelTaskMode #modify; try (modPanel.addModToSelection (MapScaler()) ui:on) catch (for o in selection do addModifier o (MapScaler())))))"
    ),
    "mod_extrude": (
        '(undo "MaxHotbox: Add Extrude" on ('
        "if selection.count > 0 do (subObjectLevel = 0; setCommandPanelTaskMode #modify; try (modPanel.addModToSelection (Extrude amount:10.0) ui:on) catch (for o in selection do addModifier o (Extrude amount:10.0)))))"
    ),
    "mod_chamfer": (
        '(undo "MaxHotbox: Add Chamfer" on ('
        "if selection.count > 0 do (subObjectLevel = 0; setCommandPanelTaskMode #modify; try (modPanel.addModToSelection (Chamfer amount:1.0 segments:2) ui:on) catch (for o in selection do addModifier o (Chamfer amount:1.0 segments:2)))))"
    ),
    "mod_weighted_normals": (
        '(undo "MaxHotbox: Add Weighted Normals" on ('
        "if selection.count > 0 do (subObjectLevel = 0; setCommandPanelTaskMode #modify; try (modPanel.addModToSelection (Weighted_Normals()) ui:on) catch ())))"
    ),
    "mod_edit_normals": (
        '(undo "MaxHotbox: Add Edit Normals" on ('
        "if selection.count > 0 do (subObjectLevel = 0; setCommandPanelTaskMode #modify; modPanel.addModToSelection (Edit_Normals()) ui:on)))"
    ),
    "mod_ffd2": (
        '(undo "MaxHotbox: Add FFD 2x2x2" on ('
        "if selection.count > 0 do (subObjectLevel = 0; setCommandPanelTaskMode #modify; modPanel.addModToSelection (FFD_2x2x2()) ui:on)))"
    ),
    "mod_ffd3": (
        '(undo "MaxHotbox: Add FFD 3x3x3" on ('
        "if selection.count > 0 do (subObjectLevel = 0; setCommandPanelTaskMode #modify; modPanel.addModToSelection (FFD_3x3x3()) ui:on)))"
    ),
    "mod_ffd4": (
        '(undo "MaxHotbox: Add FFD 4x4x4" on ('
        "if selection.count > 0 do (subObjectLevel = 0; setCommandPanelTaskMode #modify; modPanel.addModToSelection (FFD_4x4x4()) ui:on)))"
    ),
    "mod_bend": (
        '(undo "MaxHotbox: Add Bend" on ('
        "if selection.count > 0 do (subObjectLevel = 0; setCommandPanelTaskMode #modify; modPanel.addModToSelection (Bend()) ui:on)))"
    ),
    "mod_twist": (
        '(undo "MaxHotbox: Add Twist" on ('
        "if selection.count > 0 do (subObjectLevel = 0; setCommandPanelTaskMode #modify; modPanel.addModToSelection (Twist()) ui:on)))"
    ),
    "mod_taper": (
        '(undo "MaxHotbox: Add Taper" on ('
        "if selection.count > 0 do (subObjectLevel = 0; setCommandPanelTaskMode #modify; modPanel.addModToSelection (Taper()) ui:on)))"
    ),
    "mod_noise": (
        '(undo "MaxHotbox: Add Noise" on ('
        "if selection.count > 0 do (subObjectLevel = 0; setCommandPanelTaskMode #modify; modPanel.addModToSelection (Noisemodifier scale:20.0 strength:[5,5,5]) ui:on)))"
    ),
    "mod_relax": (
        '(undo "MaxHotbox: Add Relax" on ('
        "if selection.count > 0 do (subObjectLevel = 0; setCommandPanelTaskMode #modify; modPanel.addModToSelection (Relax iterations:3 relax_value:0.5) ui:on)))"
    ),
    "mod_spherify": (
        '(undo "MaxHotbox: Add Spherify" on ('
        "if selection.count > 0 do (subObjectLevel = 0; setCommandPanelTaskMode #modify; modPanel.addModToSelection (Spherify()) ui:on)))"
    ),
    "mod_push": (
        '(undo "MaxHotbox: Add Push" on ('
        "if selection.count > 0 do (subObjectLevel = 0; setCommandPanelTaskMode #modify; modPanel.addModToSelection (Push()) ui:on)))"
    ),
    "mod_wave": (
        '(undo "MaxHotbox: Add Wave" on ('
        "if selection.count > 0 do (subObjectLevel = 0; setCommandPanelTaskMode #modify; modPanel.addModToSelection (Wave()) ui:on)))"
    ),
    "mod_ripple": (
        '(undo "MaxHotbox: Add Ripple" on ('
        "if selection.count > 0 do (subObjectLevel = 0; setCommandPanelTaskMode #modify; modPanel.addModToSelection (Ripple()) ui:on)))"
    ),
    "mod_stretch": (
        '(undo "MaxHotbox: Add Stretch" on ('
        "if selection.count > 0 do (subObjectLevel = 0; setCommandPanelTaskMode #modify; modPanel.addModToSelection (Stretch()) ui:on)))"
    ),
    "mod_skew": (
        '(undo "MaxHotbox: Add Skew" on ('
        "if selection.count > 0 do (subObjectLevel = 0; setCommandPanelTaskMode #modify; modPanel.addModToSelection (Skew()) ui:on)))"
    ),
    "mod_displace": (
        '(undo "MaxHotbox: Add Displace" on ('
        "if selection.count > 0 do (subObjectLevel = 0; setCommandPanelTaskMode #modify; modPanel.addModToSelection (Displace()) ui:on)))"
    ),
    "mod_smooth": (
        '(undo "MaxHotbox: Add Smooth" on ('
        "if selection.count > 0 do (subObjectLevel = 0; setCommandPanelTaskMode #modify; modPanel.addModToSelection (Smooth autosmooth:true) ui:on)))"
    ),
    "mod_lathe": (
        '(undo "MaxHotbox: Add Lathe" on ('
        "if selection.count > 0 do (subObjectLevel = 0; setCommandPanelTaskMode #modify; modPanel.addModToSelection (Lathe weldCore:true) ui:on)))"
    ),
    "mod_sweep": (
        '(undo "MaxHotbox: Add Sweep" on ('
        "if selection.count > 0 do (subObjectLevel = 0; setCommandPanelTaskMode #modify; modPanel.addModToSelection (Sweep()) ui:on)))"
    ),
    "mod_prooptimizer": (
        '(undo "MaxHotbox: Add ProOptimizer" on ('
        "if selection.count > 0 do (subObjectLevel = 0; setCommandPanelTaskMode #modify; modPanel.addModToSelection (ProOptimizer()) ui:on)))"
    ),
    "mod_cap_holes": (
        '(undo "MaxHotbox: Add Cap Holes" on ('
        "if selection.count > 0 do (subObjectLevel = 0; setCommandPanelTaskMode #modify; modPanel.addModToSelection (Cap_Holes()) ui:on)))"
    ),
    "mod_lattice": (
        '(undo "MaxHotbox: Add Lattice" on ('
        "if selection.count > 0 do (subObjectLevel = 0; setCommandPanelTaskMode #modify; modPanel.addModToSelection (Lattice()) ui:on)))"
    ),
    "mod_slice": (
        '(undo "MaxHotbox: Add Slice" on ('
        "if selection.count > 0 do (subObjectLevel = 0; setCommandPanelTaskMode #modify; modPanel.addModToSelection (SliceModifier()) ui:on)))"
    ),
    "mod_quadify_mesh": (
        '(undo "MaxHotbox: Add Quadify Mesh" on ('
        "if selection.count > 0 do (subObjectLevel = 0; setCommandPanelTaskMode #modify; modPanel.addModToSelection (Quadify_Mesh()) ui:on)))"
    ),
    "mod_turn_to_poly": (
        '(undo "MaxHotbox: Add Turn to Poly" on ('
        "if selection.count > 0 do (subObjectLevel = 0; setCommandPanelTaskMode #modify; modPanel.addModToSelection (Turn_to_Poly()) ui:on)))"
    ),
    "mod_delete_mesh": (
        '(undo "MaxHotbox: Add DeleteMesh" on ('
        "if selection.count > 0 do (subObjectLevel = 0; setCommandPanelTaskMode #modify; modPanel.addModToSelection (DeleteMesh()) ui:on)))"
    ),
    "mod_mirror": (
        '(undo "MaxHotbox: Add Mirror" on ('
        "if selection.count > 0 do (subObjectLevel = 0; setCommandPanelTaskMode #modify; modPanel.addModToSelection (Mirror()) ui:on)))"
    ),
    # ------------------------------------------------------ Spline Modifiers
    "mod_normalize_spline": (
        '(undo "MaxHotbox: Normalize Spline" on ('
        "if selection.count > 0 do ("
        "subObjectLevel = 0; setCommandPanelTaskMode #modify;"
        "local m = undefined;"
        "try (m = Normalize_Spline2()) catch ();"
        "if m == undefined do try (m = Normalize_Spl()) catch ();"
        "if m == undefined do try (m = Normalize_Spline()) catch ();"
        "if m != undefined do (try (modPanel.addModToSelection m ui:on) catch (for o in selection do addModifier o (copy m))))))"
    ),
    "mod_edit_spline": (
        '(undo "MaxHotbox: Edit Spline" on ('
        "if selection.count > 0 do (setCommandPanelTaskMode #modify; modPanel.addModToSelection (Edit_Spline()) ui:on)))"
    ),
    "mod_bevel": (
        '(undo "MaxHotbox: Add Bevel" on ('
        "if selection.count > 0 do (setCommandPanelTaskMode #modify; modPanel.addModToSelection (Bevel Level_1_Height:5.0) ui:on)))"
    ),
    "mod_bevel_profile": (
        '(undo "MaxHotbox: Bevel Profile" on ('
        "if selection.count > 0 do (setCommandPanelTaskMode #modify; modPanel.addModToSelection (Bevel_Profile()) ui:on)))"
    ),
    "mod_surface": (
        '(undo "MaxHotbox: Add Surface" on ('
        "if selection.count > 0 do (setCommandPanelTaskMode #modify; modPanel.addModToSelection (Surface()) ui:on)))"
    ),
    "mod_crosssection": (
        '(undo "MaxHotbox: CrossSection" on ('
        "if selection.count > 0 do (setCommandPanelTaskMode #modify; modPanel.addModToSelection (CrossSection()) ui:on)))"
    ),
    "mod_fillet_chamfer": (
        '(undo "MaxHotbox: Fillet/Chamfer" on ('
        "if selection.count > 0 do (setCommandPanelTaskMode #modify; modPanel.addModToSelection (Fillet_Chamfer()) ui:on)))"
    ),
    "mod_spline_relax": (
        '(undo "MaxHotbox: Spline Relax" on ('
        "if selection.count > 0 do (setCommandPanelTaskMode #modify; try (modPanel.addModToSelection (SplineRelax()) ui:on) catch ())))"
    ),
    "mod_renderable_spline": (
        '(undo "MaxHotbox: Renderable Spline" on ('
        "if selection.count > 0 do (setCommandPanelTaskMode #modify; modPanel.addModToSelection (Renderable_Spline()) ui:on)))"
    ),
    "mod_garment_maker": (
        '(undo "MaxHotbox: Garment Maker" on ('
        "if selection.count > 0 do (setCommandPanelTaskMode #modify; modPanel.addModToSelection (Garment_Maker()) ui:on)))"
    ),
    "mod_spline_select": (
        '(undo "MaxHotbox: Spline Select" on ('
        "if selection.count > 0 do (setCommandPanelTaskMode #modify; modPanel.addModToSelection (SplineSelect()) ui:on)))"
    ),
    # ---------------------------------------------- Graphite Modeling Tools
    "graphite_swift_loop": (
        "(try (macros.run \"PolyTools\" \"SwiftLoop\") catch (try (PolyToolsModeling.SwiftLoop()) catch ()))"
    ),
    "graphite_step_loop": (
        "(try (PolyToolsSelect.StepLoop false) catch ())"
    ),
    "graphite_flow_connect": (
        '(undo "MaxHotbox: Flow Connect" on (try (macros.run "PolyTools" "FlowConnect") catch (try (PolyToolsModeling.FlowConnect()) catch ())))'
    ),
    "graphite_set_flow": (
        '(undo "MaxHotbox: Set Flow" on (try (PolyToolsModeling.SetFlow false) catch (try (macros.run "PolyTools" "SetFlow") catch ())))'
    ),
    "graphite_space_loop": (
        '(undo "MaxHotbox: Space Loop" on (try (macros.run "PolyTools" "SpaceLoop") catch ()))'
    ),
    "graphite_geopoly": (
        '(undo "MaxHotbox: GeoPoly" on (try (macros.run "PolyTools" "GeoPoly") catch (try (PolyToolsModeling.GeoPoly()) catch ())))'
    ),
    "graphite_quadrify": (
        '(undo "MaxHotbox: Quadrify All" on (try (PolyToolsModeling.Quadrify false false) catch (try (macros.run "PolyTools" "QuadrifyAll") catch ())))'
    ),
    "graphite_remove_iso_verts": (
        '(undo "MaxHotbox: Delete Iso Verts" on ('
        "if selection.count > 0 and classOf selection[1] == Editable_Poly do polyop.deleteIsoVerts selection[1]))"
    ),
    "graphite_constrain_none": (
        "(local cur = modPanel.getCurrentObject(); if classOf cur == Editable_Poly or classOf cur == Edit_Poly do cur.constrainType = 0)"
    ),
    "graphite_constrain_edge": (
        "(local cur = modPanel.getCurrentObject(); if classOf cur == Editable_Poly or classOf cur == Edit_Poly do cur.constrainType = 1)"
    ),
    "graphite_constrain_face": (
        "(local cur = modPanel.getCurrentObject(); if classOf cur == Editable_Poly or classOf cur == Edit_Poly do cur.constrainType = 2)"
    ),
    "graphite_constrain_normal": (
        "(local cur = modPanel.getCurrentObject(); if classOf cur == Editable_Poly or classOf cur == Edit_Poly do cur.constrainType = 3)"
    ),
    # ---------------------- Poly Interactive Viewport Drag (Main Button Body)
    "poly_extrude": (
        "(local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly or classOf cur == Edit_Poly do ("
        "local modeSym = case subObjectLevel of (1: #ExtrudeVertex; 2: #ExtrudeEdge; 3: #ExtrudeEdge; default: #ExtrudeFace);"
        "try (cur.ToggleCommandMode modeSym) catch (try (cur.PopupDialog #Extrude) catch (cur.PopupDialog modeSym))))"
    ),
    "poly_inset": (
        "(local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly or classOf cur == Edit_Poly do ("
        "try (cur.ToggleCommandMode #InsetFace) catch (cur.PopupDialog #Inset)))"
    ),
    "poly_bevel": (
        "(local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly or classOf cur == Edit_Poly do ("
        "try (cur.ToggleCommandMode #Bevel) catch (cur.PopupDialog #Bevel)))"
    ),
    "poly_outline": (
        "(local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly or classOf cur == Edit_Poly do ("
        "try (cur.ToggleCommandMode #Outline) catch (cur.PopupDialog #Outline)))"
    ),
    "poly_chamfer": (
        "(local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly or classOf cur == Edit_Poly do ("
        "local modeSym = if subObjectLevel == 1 then #ChamferVertex else #ChamferEdge;"
        "try (cur.ToggleCommandMode modeSym) catch (try (cur.PopupDialog #Chamfer) catch (cur.PopupDialog modeSym))))"
    ),
    "poly_connect": (
        '(undo "MaxHotbox: Connect" on ('
        "local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly or classOf cur == Edit_Poly do ("
        "if subObjectLevel == 1 then cur.ButtonOp #ConnectVertices else cur.ButtonOp #ConnectEdges)))"
    ),
    "poly_bridge": (
        '(undo "MaxHotbox: Bridge" on ('
        "local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly or classOf cur == Edit_Poly do ("
        "local modeSym = case subObjectLevel of (2: #BridgeEdge; 3: #BridgeBorder; default: #BridgePolygon);"
        "local ok = false;"
        "try (ok = (cur.ButtonOp modeSym); if ok == undefined do ok = true) catch (ok = false);"
        "if not ok do try (cur.ToggleCommandMode modeSym) catch ())))"
    ),
    "poly_weld": (
        "(local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly or classOf cur == Edit_Poly do ("
        "local modeSym = if subObjectLevel == 2 then #TargetWeldEdge else #TargetWeldVertex;"
        "try (cur.ToggleCommandMode modeSym) catch (try (cur.PopupDialog #Weld) catch (cur.PopupDialog #WeldVertex))))"
    ),
    "poly_target_weld": (
        "(local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly or classOf cur == Edit_Poly do ("
        "local modeSym = if subObjectLevel == 2 then #TargetWeldEdge else #TargetWeldVertex;"
        "cur.ToggleCommandMode modeSym))"
    ),
    "poly_relax": (
        '(undo "MaxHotbox: Relax" on ('
        "local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly or classOf cur == Edit_Poly do cur.ButtonOp #Relax))"
    ),
    "poly_detach": (
        "(local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly then cur.ButtonOp #Detach "
        "else if classOf cur == Edit_Poly then cur.PopupDialog #DetachFace)"
    ),
    "poly_create_shape": (
        '(undo "MaxHotbox: Create Shape" on ('
        "local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly or classOf cur == Edit_Poly do ("
        "try (cur.ButtonOp #CreateShape) catch (cur.PopupDialog #CreateShape))))"
    ),
    # ---------------------- Poly Numeric Settings Panel (Option Box □)
    "poly_extrude_settings": (
        "(local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly then cur.PopupDialog #Extrude "
        "else if classOf cur == Edit_Poly then ("
        "case subObjectLevel of (1: cur.PopupDialog #ExtrudeVertex; 2: cur.PopupDialog #ExtrudeEdge; 3: cur.PopupDialog #ExtrudeEdge; default: cur.PopupDialog #ExtrudeFace)))"
    ),
    "poly_inset_settings": (
        "(local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly or classOf cur == Edit_Poly do cur.PopupDialog #Inset)"
    ),
    "poly_bevel_settings": (
        "(local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly or classOf cur == Edit_Poly do cur.PopupDialog #Bevel)"
    ),
    "poly_outline_settings": (
        "(local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly or classOf cur == Edit_Poly do cur.PopupDialog #Outline)"
    ),
    "poly_chamfer_settings": (
        "(local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly then cur.PopupDialog #Chamfer "
        "else if classOf cur == Edit_Poly then ("
        "if subObjectLevel == 1 then cur.PopupDialog #ChamferVertex else cur.PopupDialog #ChamferEdge))"
    ),
    "poly_connect_settings": (
        "(local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly or classOf cur == Edit_Poly do ("
        "if subObjectLevel == 1 then cur.ButtonOp #ConnectVertices else cur.PopupDialog #ConnectEdges))"
    ),
    "poly_bridge_settings": (
        "(local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly or classOf cur == Edit_Poly do ("
        "local modeSym = case subObjectLevel of (2: #BridgeEdge; 3: #BridgeBorder; default: #BridgePolygon);"
        "local ok = false;"
        "try (ok = (cur.PopupDialog modeSym); if ok == undefined do ok = true) catch (ok = false);"
        "if not ok do try (cur.PopupDialog #Bridge) catch ()))"
    ),
    "poly_weld_settings": (
        "(local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly then cur.PopupDialog #Weld "
        "else if classOf cur == Edit_Poly then ("
        "if subObjectLevel == 2 then cur.PopupDialog #WeldEdge else cur.PopupDialog #WeldVertex))"
    ),
    "poly_relax_settings": (
        "(local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly or classOf cur == Edit_Poly do cur.PopupDialog #Relax)"
    ),
    "poly_detach_settings": (
        "(local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly then cur.ButtonOp #Detach "
        "else if classOf cur == Edit_Poly then cur.PopupDialog #DetachFace)"
    ),
    "poly_create_shape_settings": (
        "(local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly or classOf cur == Edit_Poly do cur.PopupDialog #CreateShape)"
    ),
    # ---------------------------------------- Direct Poly Tools & Cut/Planar
    "poly_break": (
        '(undo "MaxHotbox: Break" on ('
        "local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly or classOf cur == Edit_Poly do cur.ButtonOp #BreakVertex))"
    ),
    "poly_remove": (
        '(undo "MaxHotbox: Remove" on ('
        "local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly then cur.ButtonOp #Remove "
        "else if classOf cur == Edit_Poly then ("
        "if subObjectLevel == 1 then cur.ButtonOp #RemoveVertex else cur.ButtonOp #RemoveEdge)))"
    ),
    "poly_clean_remove": (
        '(undo "MaxHotbox: Clean Remove Edge" on ('
        "local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly then (cur.ButtonOp #Remove; cur.ButtonOp #RemoveIsoVerts) "
        "else if classOf cur == Edit_Poly then cur.ButtonOp #RemoveEdgeRemoveVertices))"
    ),
    "poly_split": (
        '(undo "MaxHotbox: Split Edges" on ('
        "local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly then cur.ButtonOp #SplitEdges "
        "else if classOf cur == Edit_Poly then cur.ButtonOp #SplitEdges))"
    ),
    "poly_collapse": (
        '(undo "MaxHotbox: Collapse" on ('
        "local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly then cur.ButtonOp #Collapse "
        "else if classOf cur == Edit_Poly then ("
        "case subObjectLevel of (1: cur.ButtonOp #CollapseVertex; 2: cur.ButtonOp #CollapseEdge; default: cur.ButtonOp #CollapseFace))))"
    ),
    "poly_cap": (
        '(undo "MaxHotbox: Cap" on ('
        "local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly or classOf cur == Edit_Poly do cur.ButtonOp #Cap))"
    ),
    "poly_flip": (
        '(undo "MaxHotbox: Flip Normals" on ('
        "local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly or classOf cur == Edit_Poly do cur.ButtonOp #FlipNormals))"
    ),
    "poly_attach": (
        "(local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly or classOf cur == Edit_Poly do cur.ToggleCommandMode #Attach)"
    ),
    "poly_cut": (
        "(local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly or classOf cur == Edit_Poly do cur.ToggleCommandMode #Cut)"
    ),
    "poly_quickslice": (
        "(local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly or classOf cur == Edit_Poly do cur.ToggleCommandMode #QuickSlice)"
    ),
    "poly_slice_plane": (
        "(local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly or classOf cur == Edit_Poly do cur.ToggleCommandMode #SlicePlane)"
    ),
    "poly_make_planar": (
        '(undo "MaxHotbox: Make Planar" on ('
        "local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly or classOf cur == Edit_Poly do cur.ButtonOp #MakePlanar))"
    ),
    "poly_planar_x": (
        '(undo "MaxHotbox: Make Planar X" on ('
        "local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly then cur.MakePlanarIn #X "
        "else if classOf cur == Edit_Poly then cur.ButtonOp #MakePlanarInX))"
    ),
    "poly_planar_y": (
        '(undo "MaxHotbox: Make Planar Y" on ('
        "local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly then cur.MakePlanarIn #Y "
        "else if classOf cur == Edit_Poly then cur.ButtonOp #MakePlanarInY))"
    ),
    "poly_planar_z": (
        '(undo "MaxHotbox: Make Planar Z" on ('
        "local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly then cur.MakePlanarIn #Z "
        "else if classOf cur == Edit_Poly then cur.ButtonOp #MakePlanarInZ))"
    ),
    "poly_autosmooth": (
        '(undo "MaxHotbox: Auto Smooth" on ('
        "local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly then cur.ButtonOp #AutoSmooth "
        "else if classOf cur == Edit_Poly then cur.ButtonOp #Autosmooth))"
    ),
    "poly_clear_sg": (
        '(undo "MaxHotbox: Clear Smoothing Groups" on ('
        "local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly then (cur.SetSelection #Face (cur.GetSelection #Face); polyop.setFaceSmoothGroup $ (cur.GetSelection #Face) 0)))"
    ),
    "poly_soft_selection": (
        "(local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly or classOf cur == Edit_Poly do cur.useSoftSel = not cur.useSoftSel)"
    ),
    "poly_loop": (
        "(local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly then cur.SelectEdgeLoop() "
        "else if classOf cur == Edit_Poly then cur.ButtonOp #SelectEdgeLoop)"
    ),
    "poly_ring": (
        "(local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly then cur.SelectEdgeRing() "
        "else if classOf cur == Edit_Poly then cur.ButtonOp #SelectEdgeRing)"
    ),
    "poly_grow": (
        "(local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly then cur.GrowSelection() "
        "else if classOf cur == Edit_Poly then cur.ButtonOp #GrowSelection)"
    ),
    "poly_shrink": (
        "(local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly then cur.ShrinkSelection() "
        "else if classOf cur == Edit_Poly then cur.ButtonOp #ShrinkSelection)"
    ),
    "poly_border_to_edge": (
        "(local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly or classOf cur == Edit_Poly do ("
        "cur.ConvertSelection #Border #Edge; subObjectLevel = 2))"
    ),
    # --------------------------------------------------- Selection Conversion
    "convert_sel_vertex": (
        "(local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly or classOf cur == Edit_Poly do ("
        "cur.ConvertSelection #CurrentLevel #Vertex; subObjectLevel = 1))"
    ),
    "convert_sel_edge": (
        "(local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly or classOf cur == Edit_Poly do ("
        "cur.ConvertSelection #CurrentLevel #Edge; subObjectLevel = 2))"
    ),
    "convert_sel_poly": (
        "(local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly or classOf cur == Edit_Poly do ("
        "cur.ConvertSelection #CurrentLevel #Face; subObjectLevel = 4))"
    ),
    "convert_sel_element": (
        "(local cur = modPanel.getCurrentObject();"
        "if classOf cur == Editable_Poly or classOf cur == Edit_Poly do ("
        "cur.ConvertSelection #CurrentLevel #Element; subObjectLevel = 5))"
    ),
    "select_invert": "(max select invert)",
    "select_all": "(max select all)",
    "select_none": "(max select none)",
    # ------------------------------------------------------------ Spline Ops
    # NOTE: splineOps.* expects the scene node (selection[1]) for Editable_Spline/Line,
    # and the Edit_Spline modifier instance when editing an Edit_Spline modifier.
    "spline_refine": (
        "(max modify mode; local cur = modPanel.getCurrentObject();"
        "local tgt = if classOf cur == Edit_Spline then cur else (if selection.count > 0 then selection[1] else undefined);"
        "if tgt != undefined do (if subObjectLevel == 0 do subObjectLevel = 1; splineOps.startRefine tgt))"
    ),
    "spline_insert": (
        "(max modify mode; local cur = modPanel.getCurrentObject();"
        "local tgt = if classOf cur == Edit_Spline then cur else (if selection.count > 0 then selection[1] else undefined);"
        "if tgt != undefined do splineOps.startInsert tgt)"
    ),
    "spline_weld": (
        '(undo "MaxHotbox: Spline Weld" on (max modify mode; local cur = modPanel.getCurrentObject();'
        "local tgt = if classOf cur == Edit_Spline then cur else (if selection.count > 0 then selection[1] else undefined);"
        "if tgt != undefined do (if subObjectLevel != 1 do subObjectLevel = 1; splineOps.weld tgt)))"
    ),
    "spline_fuse": (
        '(undo "MaxHotbox: Spline Fuse" on (max modify mode; local cur = modPanel.getCurrentObject();'
        "local tgt = if classOf cur == Edit_Spline then cur else (if selection.count > 0 then selection[1] else undefined);"
        "if tgt != undefined do (if subObjectLevel != 1 do subObjectLevel = 1; splineOps.fuse tgt)))"
    ),
    "spline_break": (
        '(undo "MaxHotbox: Spline Break" on (max modify mode; local cur = modPanel.getCurrentObject();'
        "local tgt = if classOf cur == Edit_Spline then cur else (if selection.count > 0 then selection[1] else undefined);"
        "if tgt != undefined do (if subObjectLevel != 1 do subObjectLevel = 1; splineOps.startBreak tgt)))"
    ),
    "spline_fillet": (
        "(max modify mode; local cur = modPanel.getCurrentObject();"
        "local tgt = if classOf cur == Edit_Spline then cur else (if selection.count > 0 then selection[1] else undefined);"
        "if tgt != undefined do (if subObjectLevel != 1 do subObjectLevel = 1; splineOps.startFillet tgt))"
    ),
    "spline_chamfer": (
        "(max modify mode; local cur = modPanel.getCurrentObject();"
        "local tgt = if classOf cur == Edit_Spline then cur else (if selection.count > 0 then selection[1] else undefined);"
        "if tgt != undefined do (if subObjectLevel != 1 do subObjectLevel = 1; splineOps.startChamfer tgt))"
    ),
    "spline_connect": (
        "(max modify mode; local cur = modPanel.getCurrentObject();"
        "local tgt = if classOf cur == Edit_Spline then cur else (if selection.count > 0 then selection[1] else undefined);"
        "if tgt != undefined do (if subObjectLevel != 1 do subObjectLevel = 1; splineOps.startConnect tgt))"
    ),
    "spline_cross_insert": (
        "(max modify mode; local cur = modPanel.getCurrentObject();"
        "local tgt = if classOf cur == Edit_Spline then cur else (if selection.count > 0 then selection[1] else undefined);"
        "if tgt != undefined do (if subObjectLevel != 1 do subObjectLevel = 1; splineOps.startCrossInsert tgt))"
    ),
    "spline_make_first": (
        '(undo "MaxHotbox: Spline Make First" on (max modify mode; local cur = modPanel.getCurrentObject();'
        "local tgt = if classOf cur == Edit_Spline then cur else (if selection.count > 0 then selection[1] else undefined);"
        "if tgt != undefined do (if subObjectLevel != 1 do subObjectLevel = 1; splineOps.makeFirst tgt)))"
    ),
    "spline_cycle": (
        "(max modify mode; local cur = modPanel.getCurrentObject();"
        "local tgt = if classOf cur == Edit_Spline then cur else (if selection.count > 0 then selection[1] else undefined);"
        "if tgt != undefined do (if subObjectLevel != 1 do subObjectLevel = 1; splineOps.cycle tgt))"
    ),
    "spline_knot_corner": (
        '(undo "MaxHotbox: Knot Corner" on ('
        "if selection.count > 0 do (local sh = selection[1];"
        "if (classOf sh == SplineShape or classOf sh == line) do ("
        "for s = 1 to (numSplines sh) do (for k in (getKnotSelection sh s) do setKnotType sh s k #corner);"
        "updateShape sh))))"
    ),
    "spline_knot_smooth": (
        '(undo "MaxHotbox: Knot Smooth" on ('
        "if selection.count > 0 do (local sh = selection[1];"
        "if (classOf sh == SplineShape or classOf sh == line) do ("
        "for s = 1 to (numSplines sh) do (for k in (getKnotSelection sh s) do setKnotType sh s k #smooth);"
        "updateShape sh))))"
    ),
    "spline_knot_bezier": (
        '(undo "MaxHotbox: Knot Bezier" on ('
        "if selection.count > 0 do (local sh = selection[1];"
        "if (classOf sh == SplineShape or classOf sh == line) do ("
        "for s = 1 to (numSplines sh) do (for k in (getKnotSelection sh s) do setKnotType sh s k #bezier);"
        "updateShape sh))))"
    ),
    "spline_knot_bezier_corner": (
        '(undo "MaxHotbox: Knot Bezier Corner" on ('
        "if selection.count > 0 do (local sh = selection[1];"
        "if (classOf sh == SplineShape or classOf sh == line) do ("
        "for s = 1 to (numSplines sh) do (for k in (getKnotSelection sh s) do setKnotType sh s k #bezierCorner);"
        "updateShape sh))))"
    ),
    "spline_divide": (
        '(undo "MaxHotbox: Spline Divide" on (max modify mode; local cur = modPanel.getCurrentObject();'
        "local tgt = if classOf cur == Edit_Spline then cur else (if selection.count > 0 then selection[1] else undefined);"
        "if tgt != undefined do (if subObjectLevel != 2 do subObjectLevel = 2; splineOps.divide tgt)))"
    ),
    "spline_detach": (
        "(max modify mode; local cur = modPanel.getCurrentObject();"
        "local tgt = if classOf cur == Edit_Spline then cur else (if selection.count > 0 then selection[1] else undefined);"
        "if tgt != undefined do splineOps.detach tgt)"
    ),
    "spline_attach": (
        "(max modify mode; local cur = modPanel.getCurrentObject();"
        "local tgt = if classOf cur == Edit_Spline then cur else (if selection.count > 0 then selection[1] else undefined);"
        "if tgt != undefined do splineOps.startAttach tgt)"
    ),
    "spline_seg_line": (
        '(undo "MaxHotbox: Segment to Line" on ('
        "if selection.count > 0 do (local sh = selection[1];"
        "if (classOf sh == SplineShape or classOf sh == line) do ("
        "for s = 1 to (numSplines sh) do (for sg in (getSegSelection sh s) do setSegmentType sh s sg #line);"
        "updateShape sh))))"
    ),
    "spline_seg_curve": (
        '(undo "MaxHotbox: Segment to Curve" on ('
        "if selection.count > 0 do (local sh = selection[1];"
        "if (classOf sh == SplineShape or classOf sh == line) do ("
        "for s = 1 to (numSplines sh) do (for sg in (getSegSelection sh s) do setSegmentType sh s sg #curve);"
        "updateShape sh))))"
    ),
    "spline_outline": (
        "(max modify mode; local cur = modPanel.getCurrentObject();"
        "local tgt = if classOf cur == Edit_Spline then cur else (if selection.count > 0 then selection[1] else undefined);"
        "if tgt != undefined do (if subObjectLevel != 3 do subObjectLevel = 3; splineOps.startOutline tgt))"
    ),
    "spline_trim": (
        "(max modify mode; local cur = modPanel.getCurrentObject();"
        "local tgt = if classOf cur == Edit_Spline then cur else (if selection.count > 0 then selection[1] else undefined);"
        "if tgt != undefined do (if subObjectLevel != 3 do subObjectLevel = 3; splineOps.startTrim tgt))"
    ),
    "spline_extend": (
        "(max modify mode; local cur = modPanel.getCurrentObject();"
        "local tgt = if classOf cur == Edit_Spline then cur else (if selection.count > 0 then selection[1] else undefined);"
        "if tgt != undefined do (if subObjectLevel != 3 do subObjectLevel = 3; splineOps.startExtend tgt))"
    ),
    "spline_bool_union": (
        "(max modify mode; local cur = modPanel.getCurrentObject();"
        "local tgt = if classOf cur == Edit_Spline then cur else (if selection.count > 0 then selection[1] else undefined);"
        "if tgt != undefined do (if subObjectLevel != 3 do subObjectLevel = 3; splineOps.startUnion tgt))"
    ),
    "spline_bool_subtract": (
        "(max modify mode; local cur = modPanel.getCurrentObject();"
        "local tgt = if classOf cur == Edit_Spline then cur else (if selection.count > 0 then selection[1] else undefined);"
        "if tgt != undefined do (if subObjectLevel != 3 do subObjectLevel = 3; splineOps.startSubtract tgt))"
    ),
    "spline_bool_intersect": (
        "(max modify mode; local cur = modPanel.getCurrentObject();"
        "local tgt = if classOf cur == Edit_Spline then cur else (if selection.count > 0 then selection[1] else undefined);"
        "if tgt != undefined do (if subObjectLevel != 3 do subObjectLevel = 3; splineOps.startIntersect tgt))"
    ),
    "spline_reverse": (
        '(undo "MaxHotbox: Spline Reverse" on (max modify mode; local cur = modPanel.getCurrentObject();'
        "local tgt = if classOf cur == Edit_Spline then cur else (if selection.count > 0 then selection[1] else undefined);"
        "if tgt != undefined do (if subObjectLevel != 3 do subObjectLevel = 3; splineOps.reverse tgt)))"
    ),
    "spline_close": (
        '(undo "MaxHotbox: Spline Close" on (max modify mode; local cur = modPanel.getCurrentObject();'
        "local tgt = if classOf cur == Edit_Spline then cur else (if selection.count > 0 then selection[1] else undefined);"
        "if tgt != undefined do (if subObjectLevel != 3 do subObjectLevel = 3; splineOps.close tgt)))"
    ),
    "spline_explode": (
        '(undo "MaxHotbox: Spline Explode" on (max modify mode; local cur = modPanel.getCurrentObject();'
        "local tgt = if classOf cur == Edit_Spline then cur else (if selection.count > 0 then selection[1] else undefined);"
        "if tgt != undefined do (if subObjectLevel != 3 do subObjectLevel = 3; splineOps.explode tgt)))"
    ),
    "spline_mirror_horiz": (
        '(undo "MaxHotbox: Spline Mirror" on (max modify mode; local cur = modPanel.getCurrentObject();'
        "local tgt = if classOf cur == Edit_Spline then cur else (if selection.count > 0 then selection[1] else undefined);"
        "if tgt != undefined do (if subObjectLevel != 3 do subObjectLevel = 3; splineOps.mirrorHoriz tgt)))"
    ),
    # --------------------------------------------------- Visibility & Display
    "toggle_isolate": (
        "(if IsolateSelection.IsolateSelectionModeActive() then "
        "IsolateSelection.ExitIsolateSelectionMode() "
        "else if selection.count > 0 do IsolateSelection.EnterIsolateSelectionMode())"
    ),
    "hide_selected": '(undo "MaxHotbox: Hide Selected" on (if selection.count > 0 do hide selection))',
    "hide_unselected": '(undo "MaxHotbox: Hide Unselected" on (if selection.count > 0 do (local selArr = selection as array; for o in objects where (findItem selArr o == 0) do hide o)))',
    "unhide_all": '(undo "MaxHotbox: Unhide All" on (unhide objects))',
    "freeze_selected": '(undo "MaxHotbox: Freeze Selected" on (if selection.count > 0 do freeze selection))',
    "unfreeze_all": '(undo "MaxHotbox: Unfreeze All" on (unfreeze objects))',
    "toggle_xray": '(undo "MaxHotbox: Toggle X-Ray" on (for o in selection do o.xray = not o.xray))',
    "toggle_backface_cull": '(undo "MaxHotbox: Backface Cull" on (for o in selection do o.backfacecull = not o.backfacecull))',
    # ------------------------------------------------------ Transform & Pivot
    "center_pivot": '(undo "MaxHotbox: Center Pivot" on (if selection.count > 0 do CenterPivot selection))',
    "pivot_to_bottom": (
        '(undo "MaxHotbox: Pivot to Bottom" on ('
        "for o in selection do (o.pivot = [o.center.x, o.center.y, o.min.z])))"
    ),
    "pivot_to_origin": (
        '(undo "MaxHotbox: Pivot to Origin" on ('
        "for o in selection do (o.pivot = [0, 0, 0])))"
    ),
    "reset_xform": (
        '(undo "MaxHotbox: Reset XForm" on ('
        "if selection.count > 0 do (subObjectLevel = 0; ResetXForm selection; for o in selection do collapseStack o)))"
    ),
    "toggle_pivot_only": (
        "(if maxOps.pivotMode == #pivotOnly then maxOps.pivotMode = #none else maxOps.pivotMode = #pivotOnly)"
    ),
    "coordsys_local": "(toolMode.coordsys #local)",
    "coordsys_world": "(toolMode.coordsys #world)",
    "coordsys_view": "(toolMode.coordsys #view)",
    "coordsys_gimbal": "(toolMode.coordsys #gimbal)",
    "gizmo_center_pivot": "(toolMode.pivotCenter())",
    "gizmo_center_selection": "(toolMode.selectionCenter())",
    "gizmo_center_transform": "(toolMode.transformCenter())",
    "toggle_snap": "(snapMode.active = not snapMode.active)",
    "toggle_angle_snap": "(max angle snap toggle)",
    "tool_move": "(max move)",
    "tool_rotate": "(max rotate)",
    "tool_scale": "(max scale)",
    # ----------------------------------------------------- Viewport & Shading
    "view_perspective": "(viewport.setType #view_persp_user)",
    "view_top": "(viewport.setType #view_top)",
    "view_front": "(viewport.setType #view_front)",
    "view_left": "(viewport.setType #view_left)",
    "view_right": "(viewport.setType #view_right)",
    "view_back": "(viewport.setType #view_back)",
    "view_bottom": "(viewport.setType #view_bottom)",
    "view_ortho": "(viewport.setType #view_iso_user)",
    "view_camera": "(max vpt camera)",
    "toggle_safeframes": "(displaySafeFrames = not displaySafeFrames)",
    "zoom_extents_sel": "(max zoomext sel)",
    "zoom_extents_all": "(max zoomext sel all)",
    "toggle_wireframe": "(max wire smooth)",
    "toggle_edged_faces": "(max edged faces)",
    "shading_default": "(try (NitrousGraphicsManager.GetActiveViewportSetting()).VisualStyleMode = #Realistic catch (actionMan.executeAction 0 \"63566\"))",
    "shading_clay": "(try (NitrousGraphicsManager.GetActiveViewportSetting()).VisualStyleMode = #Clay catch ())",
    "shading_facets": "(try (NitrousGraphicsManager.GetActiveViewportSetting()).VisualStyleMode = #Facets catch ())",
    "toggle_maximize_viewport": "(max tool maximize)",
    "toggle_grid": "(max grid toggle)",
    "toggle_stats": "(max show statistics toggle)",
    # ------------------------------------------------------ Create Primitives
    "create_box_interactive": "(startObjectCreation Box)",
    "create_box": '(undo "MaxHotbox: Create Box" on (select (Box length:30 width:30 height:30 pos:[0,0,0])))',
    "create_sphere_interactive": "(startObjectCreation Sphere)",
    "create_sphere": '(undo "MaxHotbox: Create Sphere" on (select (Sphere radius:20 segments:24 pos:[0,0,20])))',
    "create_cylinder_interactive": "(startObjectCreation Cylinder)",
    "create_cylinder": '(undo "MaxHotbox: Create Cylinder" on (select (Cylinder radius:15 height:35 sides:24 pos:[0,0,0])))',
    "create_plane_interactive": "(startObjectCreation Plane)",
    "create_plane": '(undo "MaxHotbox: Create Plane" on (select (Plane length:60 width:60 lengthsegs:4 widthsegs:4 pos:[0,0,0])))',
    "create_torus_interactive": "(startObjectCreation Torus)",
    "create_torus": '(undo "MaxHotbox: Create Torus" on (select (Torus radius1:25 radius2:8 segs:24 sides:12 pos:[0,0,8])))',
    "create_cone_interactive": "(startObjectCreation Cone)",
    "create_cone": '(undo "MaxHotbox: Create Cone" on (select (Cone radius1:20 radius2:0 height:40 sides:24 pos:[0,0,0])))',
    "create_tube_interactive": "(startObjectCreation Tube)",
    "create_tube": '(undo "MaxHotbox: Create Tube" on (select (Tube radius1:20 radius2:14 height:35 sides:24 pos:[0,0,0])))',
    "create_geosphere_interactive": "(startObjectCreation GeoSphere)",
    "create_geosphere": '(undo "MaxHotbox: Create GeoSphere" on (select (GeoSphere radius:20 segs:3 pos:[0,0,20])))',
    # --------------------------------------------------------- Create Splines
    "create_line": "(startObjectCreation Line)",
    "create_circle": "(startObjectCreation Circle)",
    "create_rectangle": "(startObjectCreation Rectangle)",
    "create_arc": "(startObjectCreation Arc)",
    "create_helix": "(startObjectCreation Helix)",
    "create_star": "(startObjectCreation Star)",
    "create_text": "(startObjectCreation Text)",
    "create_ngon": "(startObjectCreation NGon)",
    # ---------------------------------------------- Cameras, Lights & Helpers
    "camera_from_view": '(undo "MaxHotbox: Camera from View" on (macros.run "Lights and Cameras" "StandardCamera_CreateFromView"))',
    "create_target_camera": "(startObjectCreation Targetcamera)",
    "create_free_light": "(startObjectCreation freeSpot)",
    "create_target_light": "(startObjectCreation targetSpot)",
    "create_point_helper": '(undo "MaxHotbox: Point Helper" on (select (Point size:20 cross:on box:on pos:[0,0,0])))',
    "create_dummy_helper": '(undo "MaxHotbox: Dummy Helper" on (select (Dummy boxsize:[20,20,20] pos:[0,0,0])))',
    "create_grid_helper": "(startObjectCreation Grid)",
}


@dataclass(frozen=True)
class ActionResult:
    ok: bool
    message: str = ""


class ActionExecutor:
    """Executes MenuItem main actions or Option Box [□] actions against 3ds Max 2026."""

    def __init__(
        self,
        rt_provider: Callable[[], Any] | None = None,
        ui_callbacks: dict[str, Callable[[], None]] | None = None,
    ) -> None:
        self._rt_provider = rt_provider or self._default_rt_provider
        self._ui_callbacks = dict(ui_callbacks or {})

    @staticmethod
    def _default_rt_provider() -> Any:
        from pymxs import runtime as rt  # type: ignore[import-not-found]

        return rt

    def register_ui_callback(self, command_id: str, callback: Callable[[], None]) -> None:
        self._ui_callbacks[command_id] = callback

    def execute(self, item: MenuItem, use_option_box: bool = False) -> ActionResult:
        """Execute either the main command or the right-side Option Box [□] command."""
        logger = get_logger()
        if not item.enabled:
            return ActionResult(ok=False, message="Item disabled")

        if use_option_box and item.has_option_box():
            cmd_type = (item.option_command_type or "builtin").strip().lower()
            cmd = (item.option_command or "").strip()
        else:
            cmd_type = (item.command_type or "builtin").strip().lower()
            cmd = (item.command or "").strip()

        if cmd_type == "submenu":
            return ActionResult(ok=True, message="Submenu handled by state machine")

        if not cmd:
            return ActionResult(ok=False, message=f"Empty command for '{item.label}'")

        try:
            if cmd_type == "builtin":
                if cmd in self._ui_callbacks:
                    self._ui_callbacks[cmd]()
                    return ActionResult(ok=True, message=f"UI callback '{cmd}' executed")
                script = _BUILTIN_MAXSCRIPTS.get(cmd)
                if script is None:
                    return ActionResult(ok=False, message=f"Unknown builtin command: {cmd}")
                rt = self._rt_provider()
                rt.execute(script)
                return ActionResult(ok=True, message=f"Builtin '{cmd}' executed")

            if cmd_type == "maxscript":
                rt = self._rt_provider()
                rt.execute(cmd)
                return ActionResult(ok=True, message="MAXScript executed")

            if cmd_type == "python":
                namespace: dict[str, Any] = {}
                try:
                    namespace["rt"] = self._rt_provider()
                except Exception:
                    pass
                exec(compile(cmd, "<max_hotbox_action>", "exec"), namespace)
                return ActionResult(ok=True, message="Python executed")

            if cmd_type == "action":
                if ":" not in cmd:
                    return ActionResult(
                        ok=False,
                        message="Action format must be '<tableId>:<actionId>'",
                    )
                table_str, action_id = cmd.split(":", 1)
                table_id = int(table_str.strip())
                rt = self._rt_provider()
                rt.actionMan.executeAction(table_id, action_id.strip())
                return ActionResult(ok=True, message=f"Action {table_id}:{action_id} executed")

            return ActionResult(ok=False, message=f"Unsupported command_type: {cmd_type}")
        except Exception as exc:
            logger.exception("Error executing item '%s' (%s:%s)", item.label, cmd_type, cmd)
            return ActionResult(ok=False, message=str(exc))
