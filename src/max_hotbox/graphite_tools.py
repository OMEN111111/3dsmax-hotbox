"""Self-contained Graphite-style modeling & selection tools with native PySide6 parameter panels.

Provides pure-Python topological selection algorithms (unit-testable offline) plus
3ds Max 2026 PySide6 floating parameter dialogs with live viewport preview and
cancel-to-restore behavior — zero dependency on Ribbon UI controls.
"""

from __future__ import annotations

import math
import random
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable

from .logger import get_logger

# ------------------------------------------------------ Pure-Python Algorithms


def random_subset_indices(
    pool: list[int],
    ratio_percent: float,
    seed: int | None = None,
) -> list[int]:
    """Deterministically or randomly pick `ratio_percent`% of indices from `pool`."""
    if not pool:
        return []
    clamped = max(0.0, min(100.0, float(ratio_percent)))
    if clamped <= 0.0:
        return []
    if clamped >= 100.0:
        return sorted(pool)

    count = max(1, int(round(len(pool) * (clamped / 100.0))))
    count = min(count, len(pool))
    rng = random.Random(seed)
    return sorted(rng.sample(pool, count))


def filter_faces_by_sides(
    face_degrees: dict[int, int],
    operator: str,
    target_sides: int,
) -> list[int]:
    """Filter face indices by polygon vertex/edge count (`=`, `>`, `<`, `>=`, `<=`)."""
    ops: dict[str, Callable[[int, int], bool]] = {
        "=": lambda a, b: a == b,
        ">": lambda a, b: a > b,
        "<": lambda a, b: a < b,
        ">=": lambda a, b: a >= b,
        "<=": lambda a, b: a <= b,
    }
    fn = ops.get(operator, ops[">"])
    return sorted(fid for fid, deg in face_degrees.items() if fn(deg, target_sides))


def order_connected_chain(
    items: list[int],
    adjacency: dict[int, set[int]],
    seed_items: set[int] | None = None,
) -> list[list[int]]:
    """Order edge/face IDs into topological chains using an adjacency map."""
    remaining = set(items)
    chains: list[list[int]] = []
    seeds = set(seed_items or ())

    while remaining:
        # Prefer starting from an open endpoint or a seed item
        endpoints = [n for n in remaining if len(adjacency.get(n, set()) & remaining) <= 1]
        seed_candidates = [n for n in endpoints if n in seeds] or [n for n in remaining if n in seeds]
        start = seed_candidates[0] if seed_candidates else (endpoints[0] if endpoints else min(remaining))

        chain: list[int] = [start]
        remaining.remove(start)

        # Walk forward
        curr = start
        while True:
            nxt_list = sorted(adjacency.get(curr, set()) & remaining)
            if not nxt_list:
                break
            curr = nxt_list[0]
            chain.append(curr)
            remaining.remove(curr)

        # If started in the middle of an open chain, walk backward from start too
        curr = start
        prefix: list[int] = []
        while True:
            prev_list = sorted(adjacency.get(curr, set()) & remaining)
            if not prev_list:
                break
            curr = prev_list[0]
            prefix.append(curr)
            remaining.remove(curr)

        if prefix:
            prefix.reverse()
            chain = prefix + chain

        chains.append(chain)

    return chains


def compute_dot_step_indices(
    chains: list[list[int]],
    step: int = 2,
    offset: int = 0,
) -> list[int]:
    """Pick every `step`-th item along each ordered topological chain."""
    s = max(1, int(step))
    off = int(offset) % s
    picked: list[int] = []
    for chain in chains:
        for idx, item_id in enumerate(chain):
            if idx % s == off:
                picked.append(item_id)
    return sorted(set(picked))


def _angle_between_normals_deg(
    n1: tuple[float, float, float],
    n2: tuple[float, float, float],
) -> float:
    dot = n1[0] * n2[0] + n1[1] * n2[1] + n1[2] * n2[2]
    l1 = math.sqrt(n1[0] ** 2 + n1[1] ** 2 + n1[2] ** 2)
    l2 = math.sqrt(n2[0] ** 2 + n2[1] ** 2 + n2[2] ** 2)
    if l1 <= 1e-8 or l2 <= 1e-8:
        return 0.0
    cos_val = max(-1.0, min(1.0, dot / (l1 * l2)))
    return math.degrees(math.acos(cos_val))


def select_hard_edges_from_normals(
    edge_faces: dict[int, list[int]],
    face_normals: dict[int, tuple[float, float, float]],
    angle_threshold_deg: float = 30.0,
) -> list[int]:
    """Return edges whose two adjacent faces form a dihedral angle >= threshold."""
    hard: list[int] = []
    for eid, faces in edge_faces.items():
        if len(faces) != 2:
            continue
        n1 = face_normals.get(faces[0])
        n2 = face_normals.get(faces[1])
        if n1 is None or n2 is None:
            continue
        if _angle_between_normals_deg(n1, n2) >= angle_threshold_deg:
            hard.append(eid)
    return sorted(hard)


def flood_fill_faces_by_angle(
    seed_faces: list[int],
    face_adjacency: dict[int, set[int]],
    face_normals: dict[int, tuple[float, float, float]],
    max_angle_deg: float = 25.0,
) -> list[int]:
    """Flood-fill connected faces whose step-to-step normal angle <= `max_angle_deg`."""
    visited: set[int] = set(seed_faces)
    queue: deque[int] = deque(seed_faces)

    while queue:
        fid = queue.popleft()
        n1 = face_normals.get(fid)
        if n1 is None:
            continue
        for nb in face_adjacency.get(fid, set()):
            if nb in visited:
                continue
            n2 = face_normals.get(nb)
            if n2 is not None and _angle_between_normals_deg(n1, n2) <= max_angle_deg:
                visited.add(nb)
                queue.append(nb)

    return sorted(visited)


def select_similar_by_signature(
    seed_ids: list[int],
    all_signatures: dict[int, tuple[int, float]],
    tolerance_percent: float = 10.0,
    match_topology: bool = True,
    match_size: bool = True,
) -> list[int]:
    """Select all items whose (topology_count, geometric_size) matches any seed within tolerance.

    Used for Graphite-style Select Similar on Vertices (valence, 0.0), Edges (adj_faces, length),
    Polygons (side_count, area), and Scene Objects (face_count, bbox_diag).
    """
    if not seed_ids:
        return []
    tol = max(0.0, float(tolerance_percent)) / 100.0
    seed_sigs = [all_signatures[sid] for sid in seed_ids if sid in all_signatures]
    if not seed_sigs:
        return []

    matched: list[int] = []
    for item_id, (topo, size) in all_signatures.items():
        for s_topo, s_size in seed_sigs:
            if match_topology and topo != s_topo:
                continue
            if match_size and s_size > 1e-6:
                if abs(size - s_size) > s_size * tol + 1e-4:
                    continue
            matched.append(item_id)
            break
    return sorted(matched)


def toggle_smoothing_group_bit(mask: int, group_1_to_32: int, enable: bool | None = None) -> int:
    """Set, clear, or toggle bit `(group_1_to_32 - 1)` in a 32-bit 3ds Max smoothing group mask."""
    if not (1 <= group_1_to_32 <= 32):
        return mask
    bit = 1 << (group_1_to_32 - 1)
    if enable is None:
        return mask ^ bit
    return (mask | bit) if enable else (mask & ~bit)


# ------------------------------------------- Persistent In-Memory Tool Params


@dataclass
class GraphiteToolMemory:
    random_ratio: int = 30
    random_from_current: bool = False
    sides_operator: str = ">"
    sides_target: int = 4
    dot_gap: int = 1
    dot_cylinder_ends: bool = False
    dot_opposite: bool = False
    hard_edge_angle: float = 30.0
    coplanar_angle: float = 25.0
    similar_tolerance: int = 10
    similar_match_topo: bool = True
    similar_match_size: bool = True
    auto_smooth_angle: float = 45.0
    spline_divide_count: int = 2


_MEMORY = GraphiteToolMemory()


# -------------------------------------------------- 3ds Max 2026 Runtime Glue


def _get_rt() -> Any:
    from pymxs import runtime as rt  # type: ignore[import-not-found]

    return rt


def _to_bitarray(rt: Any, indices: list[int]) -> Any:
    ba = rt.BitArray()
    for idx in indices:
        if idx > 0:
            ba[int(idx)] = True
    return ba


def _from_bitarray(ba: Any) -> list[int]:
    if ba is None:
        return []
    return [int(i) for i in ba]


def _resolve_editable_poly(rt: Any) -> tuple[Any, Any, int] | None:
    """Return (node, current_obj, subobject_level) if an Editable_Poly is active."""
    try:
        if int(rt.selection.count) == 0:
            rt.pushPrompt("MaxHotbox 石墨工具: 请先选择一个可编辑多边形对象")
            return None
        node = rt.selection[0]
        cur = rt.modPanel.getCurrentObject()
        cls_name = str(rt.classOf(cur)).lower() if cur is not None else ""
        if cls_name != "editable_poly":
            node_cls = str(rt.classOf(node.baseObject)).lower()
            if node_cls == "editable_poly":
                cur = node.baseObject
            else:
                rt.pushPrompt("MaxHotbox 石墨工具: 当前对象不是 Editable Poly（请先转换为可编辑多边形）")
                return None
        sub = int(rt.subObjectLevel) if rt.subObjectLevel is not None else 0
        return node, cur, sub
    except Exception as exc:
        get_logger().warning("resolve_editable_poly failed: %s", exc)
        return None


def _subobj_sym(level: int) -> str:
    return {1: "Vertex", 2: "Edge", 3: "Border", 4: "Face", 5: "Element"}.get(level, "Face")


def _get_poly_sub_count(rt: Any, node: Any, level: int) -> int:
    if level == 1:
        return int(rt.polyop.getNumVerts(node))
    if level in (2, 3):
        return int(rt.polyop.getNumEdges(node))
    return int(rt.polyop.getNumFaces(node))


def _get_poly_selection(rt: Any, node: Any, level: int) -> list[int]:
    if level == 1:
        return _from_bitarray(rt.polyop.getVertSelection(node))
    if level in (2, 3):
        return _from_bitarray(rt.polyop.getEdgeSelection(node))
    return _from_bitarray(rt.polyop.getFaceSelection(node))


def _set_poly_selection(rt: Any, node: Any, level: int, indices: list[int]) -> None:
    ba = _to_bitarray(rt, indices)
    if level == 1:
        rt.polyop.setVertSelection(node, ba)
    elif level in (2, 3):
        rt.polyop.setEdgeSelection(node, ba)
    else:
        rt.polyop.setFaceSelection(node, ba)
    rt.redrawViews()


# -------------------------------------------------------- Quick Direct Actions


def run_random_select(ratio: int | None = None, from_current: bool | None = None) -> int:
    rt = _get_rt()
    ctx = _resolve_editable_poly(rt)
    if ctx is None:
        return 0
    node, _cur, sub = ctx
    if sub == 0:
        rt.setCommandPanelTaskMode(rt.Name("modify"))
        rt.subObjectLevel = 4
        sub = 4

    use_ratio = _MEMORY.random_ratio if ratio is None else int(ratio)
    use_curr = _MEMORY.random_from_current if from_current is None else bool(from_current)
    _MEMORY.random_ratio = use_ratio
    _MEMORY.random_from_current = use_curr

    if use_curr:
        pool = _get_poly_selection(rt, node, sub)
    else:
        total = _get_poly_sub_count(rt, node, sub)
        pool = list(range(1, total + 1))

    chosen = random_subset_indices(pool, use_ratio)
    _set_poly_selection(rt, node, sub, chosen)
    rt.pushPrompt(f"MaxHotbox 随机选择 ({use_ratio}%): 已选中 {len(chosen)} / {len(pool)}")
    return len(chosen)


def run_select_by_sides(operator: str = ">", target_sides: int = 4) -> int:
    rt = _get_rt()
    ctx = _resolve_editable_poly(rt)
    if ctx is None:
        return 0
    node, _cur, _sub = ctx
    rt.setCommandPanelTaskMode(rt.Name("modify"))
    rt.subObjectLevel = 4

    num_faces = int(rt.polyop.getNumFaces(node))
    degrees = {fid: int(rt.polyop.getFaceDeg(node, fid)) for fid in range(1, num_faces + 1)}
    chosen = filter_faces_by_sides(degrees, operator, target_sides)
    _set_poly_selection(rt, node, 4, chosen)
    rt.pushPrompt(f"MaxHotbox 按边数选择 ({operator} {target_sides}): 已选中 {len(chosen)} 个面")
    return len(chosen)


def _compute_dot_edge_chains(rt: Any, node: Any, cur: Any, mode: str) -> tuple[list[int], list[list[int]]]:
    """Expand seed edges to loop or ring via Max C++ then return (original_sel, ordered_chains)."""
    orig = _get_poly_selection(rt, node, 2)
    if not orig:
        rt.pushPrompt("MaxHotbox 点循环/点环形: 请先选中至少一条边")
        return [], []

    if mode == "ring":
        cur.SelectEdgeRing()
    else:
        cur.SelectEdgeLoop()

    expanded = _get_poly_selection(rt, node, 2)
    if not expanded:
        return orig, []

    expanded_set = set(expanded)
    adj: dict[int, set[int]] = {e: set() for e in expanded}

    if mode == "loop":
        # Two loop edges are adjacent if they share a vertex
        vert_to_edges: dict[int, list[int]] = {}
        for eid in expanded:
            verts = _from_bitarray(rt.polyop.getEdgeVerts(node, eid))
            for v in verts:
                vert_to_edges.setdefault(v, []).append(eid)
        for edges_at_v in vert_to_edges.values():
            for a in edges_at_v:
                for b in edges_at_v:
                    if a != b and b in expanded_set:
                        adj[a].add(b)
    else:
        # Two ring edges are adjacent if they belong to the same polygon face
        face_to_edges: dict[int, list[int]] = {}
        for eid in expanded:
            faces = _from_bitarray(rt.polyop.getEdgeFaces(node, eid))
            for f in faces:
                face_to_edges.setdefault(f, []).append(eid)
        for edges_in_f in face_to_edges.values():
            for a in edges_in_f:
                for b in edges_in_f:
                    if a != b and b in expanded_set:
                        adj[a].add(b)

    chains = order_connected_chain(expanded, adj, seed_items=set(orig))
    return orig, chains


def _resolve_poly_any(rt: Any) -> tuple[Any, Any, int, bool] | None:
    """Return (node, current_obj, subobject_level, is_edit_poly_mod) for Editable_Poly OR Edit_Poly."""
    try:
        if int(rt.selection.count) == 0:
            rt.pushPrompt("MaxHotbox 石墨工具: 请先选择一个多边形对象")
            return None
        node = rt.selection[0]
        cur = rt.modPanel.getCurrentObject()
        cls_name = str(rt.classOf(cur)).lower() if cur is not None else ""
        if cls_name == "editable_poly":
            sub = int(rt.subObjectLevel) if rt.subObjectLevel is not None else 0
            return node, cur, sub, False
        if cls_name == "edit_poly":
            sub = int(rt.subObjectLevel) if rt.subObjectLevel is not None else 0
            return node, cur, sub, True
        node_cls = str(rt.classOf(node.baseObject)).lower()
        if node_cls == "editable_poly":
            sub = int(rt.subObjectLevel) if rt.subObjectLevel is not None else 0
            return node, node.baseObject, sub, False
        rt.pushPrompt("MaxHotbox 石墨工具: 当前对象不是 Editable Poly / Edit Poly")
        return None
    except Exception as exc:
        get_logger().warning("resolve_poly_any failed: %s", exc)
        return None


def _get_any_poly_selection(rt: Any, node: Any, cur: Any, level: int, is_mod: bool) -> list[int]:
    if not is_mod:
        return _get_poly_selection(rt, node, level)
    sym = rt.Name(_subobj_sym(level))
    try:
        return _from_bitarray(cur.GetSelection(sym))
    except Exception:
        return []


def _set_any_poly_selection(rt: Any, node: Any, cur: Any, level: int, indices: list[int], is_mod: bool) -> None:
    if not is_mod:
        _set_poly_selection(rt, node, level, indices)
        return
    sym = rt.Name(_subobj_sym(level))
    try:
        cur.SetSelection(sym, _to_bitarray(rt, indices))
        rt.redrawViews()
    except Exception:
        pass


def run_dot_step(
    mode: str = "loop",
    gap: int | None = None,
    cylinder_ends: bool | None = None,
    opposite: bool | None = None,
) -> int:
    """Run authentic native 3ds Max Graphite PolyToolsSelect.DotLoop / DotRing."""
    rt = _get_rt()
    ctx = _resolve_poly_any(rt)
    if ctx is None:
        return 0
    node, cur, sub, is_mod = ctx
    if sub not in (1, 2, 4):
        rt.setCommandPanelTaskMode(rt.Name("modify"))
        rt.subObjectLevel = 2
        sub = 2

    use_gap = _MEMORY.dot_gap if gap is None else max(1, int(gap))
    use_cyl = _MEMORY.dot_cylinder_ends if cylinder_ends is None else bool(cylinder_ends)
    use_opp = _MEMORY.dot_opposite if opposite is None else bool(opposite)
    _MEMORY.dot_gap = use_gap
    _MEMORY.dot_cylinder_ends = use_cyl
    _MEMORY.dot_opposite = use_opp

    seed_sel = _get_any_poly_selection(rt, node, cur, sub, is_mod)
    if not seed_sel:
        rt.pushPrompt("MaxHotbox 点循环/点环形: 请先选中至少一个起始子对象（顶点/边/面）")
        return 0

    try:
        if mode == "ring":
            rt.PolyToolsSelect.DotRing(use_gap)
        else:
            rt.PolyToolsSelect.DotLoop(use_gap, use_cyl, use_opp)
        rt.redrawViews()
    except Exception as exc:
        get_logger().warning("PolyToolsSelect dot_%s fallback: %s", mode, exc)
        if not is_mod and sub == 2:
            _orig, chains = _compute_dot_edge_chains(rt, node, cur, mode)
            chosen = compute_dot_step_indices(chains, step=use_gap + 1, offset=0)
            _set_poly_selection(rt, node, 2, chosen)

    final_sel = _get_any_poly_selection(rt, node, cur, sub, is_mod)
    label = "点环形 Dot Ring" if mode == "ring" else "点循环 Dot Loop"
    rt.pushPrompt(f"MaxHotbox {label} (间隔 {use_gap}): 已选中 {len(final_sel)} 项")
    return len(final_sel)


def _collect_face_normals(rt: Any, node: Any) -> dict[int, tuple[float, float, float]]:
    num_faces = int(rt.polyop.getNumFaces(node))
    normals: dict[int, tuple[float, float, float]] = {}
    for fid in range(1, num_faces + 1):
        n = rt.polyop.getFaceNormal(node, fid)
        normals[fid] = (float(n.x), float(n.y), float(n.z))
    return normals


def run_select_hard_edges(angle_deg: float | None = None) -> int:
    rt = _get_rt()
    ctx = _resolve_editable_poly(rt)
    if ctx is None:
        return 0
    node, _cur, _sub = ctx
    rt.setCommandPanelTaskMode(rt.Name("modify"))
    rt.subObjectLevel = 2

    thr = _MEMORY.hard_edge_angle if angle_deg is None else float(angle_deg)
    _MEMORY.hard_edge_angle = thr
    normals = _collect_face_normals(rt, node)
    num_edges = int(rt.polyop.getNumEdges(node))
    edge_faces = {eid: _from_bitarray(rt.polyop.getEdgeFaces(node, eid)) for eid in range(1, num_edges + 1)}
    chosen = select_hard_edges_from_normals(edge_faces, normals, angle_threshold_deg=thr)
    _set_poly_selection(rt, node, 2, chosen)
    rt.pushPrompt(f"MaxHotbox 硬边选择 (≥ {thr:.0f}°): 已选中 {len(chosen)} 条边")
    return len(chosen)


def run_select_coplanar_faces(max_angle_deg: float | None = None) -> int:
    rt = _get_rt()
    ctx = _resolve_editable_poly(rt)
    if ctx is None:
        return 0
    node, _cur, _sub = ctx
    rt.setCommandPanelTaskMode(rt.Name("modify"))
    rt.subObjectLevel = 4

    seeds = _get_poly_selection(rt, node, 4)
    if not seeds:
        rt.pushPrompt("MaxHotbox 按角度选面: 请先选中至少一个起始面")
        return 0

    thr = _MEMORY.coplanar_angle if max_angle_deg is None else float(max_angle_deg)
    _MEMORY.coplanar_angle = thr
    normals = _collect_face_normals(rt, node)
    num_edges = int(rt.polyop.getNumEdges(node))
    face_adj: dict[int, set[int]] = {}
    for eid in range(1, num_edges + 1):
        faces = _from_bitarray(rt.polyop.getEdgeFaces(node, eid))
        if len(faces) == 2:
            a, b = faces
            face_adj.setdefault(a, set()).add(b)
            face_adj.setdefault(b, set()).add(a)

    chosen = flood_fill_faces_by_angle(seeds, face_adj, normals, max_angle_deg=thr)
    _set_poly_selection(rt, node, 4, chosen)
    rt.pushPrompt(f"MaxHotbox 共面选择 (≤ {thr:.0f}°): 已选中 {len(chosen)} 个面")
    return len(chosen)


# ----------------------------------------- Native 3ds Max 2026 PySide6 Panels


_PANEL_QSS = """
QDialog {
    background-color: #323232;
    color: #EAEAEA;
    font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
    font-size: 12px;
}
QLabel { color: #DCDCDC; }
QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #262626;
    color: #F0F0F0;
    border: 1px solid #555555;
    border-radius: 2px;
    padding: 3px 6px;
}
QPushButton {
    background-color: #464646;
    color: #EEEEEE;
    border: 1px solid #5C5C5C;
    border-radius: 3px;
    padding: 5px 12px;
}
QPushButton:hover {
    background-color: #555555;
    border-color: #6BA7E5;
}
QPushButton#okBtn {
    background-color: #3D75B3;
    border-color: #5C98D6;
    color: #FFFFFF;
    font-weight: bold;
}
QSlider::groove:horizontal {
    height: 4px;
    background: #232323;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #4E8DD1;
    width: 12px;
    margin: -4px 0;
    border-radius: 2px;
}
"""

_ACTIVE_TOOL_DIALOG: Any = None


def _position_near_cursor(dialog: Any) -> None:
    from PySide6 import QtGui

    pos = QtGui.QCursor.pos()
    dialog.move(pos.x() + 18, pos.y() - 30)


def _get_max_parent() -> Any:
    try:
        import qtmax  # type: ignore[import-not-found]

        return qtmax.GetQMaxMainWindow()
    except Exception:
        return None


def _show_single_panel(dialog: Any) -> None:
    global _ACTIVE_TOOL_DIALOG
    if _ACTIVE_TOOL_DIALOG is not None:
        try:
            _ACTIVE_TOOL_DIALOG.close()
        except Exception:
            pass
    _ACTIVE_TOOL_DIALOG = dialog
    _position_near_cursor(dialog)
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()


def open_random_select_panel() -> None:
    """Open custom PySide6 live-preview Random Select parameter dialog."""
    from PySide6 import QtCore, QtWidgets

    rt = _get_rt()
    ctx = _resolve_editable_poly(rt)
    if ctx is None:
        return
    node, _cur, sub = ctx
    if sub == 0:
        rt.setCommandPanelTaskMode(rt.Name("modify"))
        rt.subObjectLevel = 4
        sub = 4

    orig_sel = _get_poly_selection(rt, node, sub)
    total = _get_poly_sub_count(rt, node, sub)
    all_pool = list(range(1, total + 1))

    dlg = QtWidgets.QDialog(_get_max_parent())
    dlg.setWindowTitle(f"随机选择 (Random Select · {_subobj_sym(sub)})")
    dlg.setStyleSheet(_PANEL_QSS)
    dlg.setFixedWidth(330)

    lay = QtWidgets.QVBoxLayout(dlg)
    lay.setSpacing(10)

    row_ratio = QtWidgets.QHBoxLayout()
    row_ratio.addWidget(QtWidgets.QLabel("选择比例:"))
    slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
    slider.setRange(1, 100)
    slider.setValue(_MEMORY.random_ratio)
    spin = QtWidgets.QSpinBox()
    spin.setRange(1, 100)
    spin.setSuffix(" %")
    spin.setValue(_MEMORY.random_ratio)
    row_ratio.addWidget(slider, 1)
    row_ratio.addWidget(spin)
    lay.addLayout(row_ratio)

    chk_curr = QtWidgets.QCheckBox(f"仅在当前已选子对象内随机筛选 ({len(orig_sel)} 个)")
    chk_curr.setChecked(_MEMORY.random_from_current and len(orig_sel) > 0)
    chk_curr.setEnabled(len(orig_sel) > 0)
    lay.addWidget(chk_curr)

    status_lbl = QtWidgets.QLabel("")
    status_lbl.setStyleSheet("color: #8FC0F0;")
    lay.addWidget(status_lbl)

    seed_box = {"seed": random.randint(1, 999999)}
    accepted = {"ok": False}

    def apply_preview() -> None:
        ratio = spin.value()
        from_curr = chk_curr.isChecked()
        _MEMORY.random_ratio = ratio
        _MEMORY.random_from_current = from_curr
        pool = orig_sel if from_curr else all_pool
        chosen = random_subset_indices(pool, ratio, seed=seed_box["seed"])
        _set_poly_selection(rt, node, sub, chosen)
        status_lbl.setText(f"实时预览: 已选中 {len(chosen)} / {len(pool)}")

    slider.valueChanged.connect(spin.setValue)
    spin.valueChanged.connect(slider.setValue)
    spin.valueChanged.connect(lambda _v: apply_preview())
    chk_curr.toggled.connect(lambda _c: apply_preview())

    btns = QtWidgets.QHBoxLayout()
    reseed_btn = QtWidgets.QPushButton("换一批")
    reseed_btn.clicked.connect(lambda: (seed_box.__setitem__("seed", random.randint(1, 999999)), apply_preview()))
    ok_btn = QtWidgets.QPushButton("确定")
    ok_btn.setObjectName("okBtn")
    cancel_btn = QtWidgets.QPushButton("取消")
    btns.addWidget(reseed_btn)
    btns.addStretch()
    btns.addWidget(ok_btn)
    btns.addWidget(cancel_btn)
    lay.addLayout(btns)

    def on_ok() -> None:
        accepted["ok"] = True
        dlg.accept()

    def on_reject() -> None:
        if not accepted["ok"]:
            _set_poly_selection(rt, node, sub, orig_sel)

    ok_btn.clicked.connect(on_ok)
    cancel_btn.clicked.connect(dlg.reject)
    dlg.finished.connect(lambda _r: on_reject())

    apply_preview()
    _show_single_panel(dlg)


def open_select_by_sides_panel() -> None:
    """Open custom PySide6 Select by Sides (Triangles / Quads / N-Gons) floating dialog."""
    from PySide6 import QtWidgets

    rt = _get_rt()
    ctx = _resolve_editable_poly(rt)
    if ctx is None:
        return
    node, _cur, _sub = ctx
    rt.setCommandPanelTaskMode(rt.Name("modify"))
    rt.subObjectLevel = 4

    orig_sel = _get_poly_selection(rt, node, 4)
    num_faces = int(rt.polyop.getNumFaces(node))
    degrees = {fid: int(rt.polyop.getFaceDeg(node, fid)) for fid in range(1, num_faces + 1)}

    dlg = QtWidgets.QDialog(_get_max_parent())
    dlg.setWindowTitle("按边数选择面 (Select by Sides)")
    dlg.setStyleSheet(_PANEL_QSS)
    dlg.setFixedWidth(340)

    lay = QtWidgets.QVBoxLayout(dlg)
    lay.setSpacing(10)

    presets = QtWidgets.QHBoxLayout()
    b_tri = QtWidgets.QPushButton("三角面 (=3)")
    b_quad = QtWidgets.QPushButton("四边面 (=4)")
    b_ngon = QtWidgets.QPushButton("多边面 (>4)")
    presets.addWidget(b_tri)
    presets.addWidget(b_quad)
    presets.addWidget(b_ngon)
    lay.addLayout(presets)

    row_rule = QtWidgets.QHBoxLayout()
    row_rule.addWidget(QtWidgets.QLabel("面边数条件:"))
    cmb_op = QtWidgets.QComboBox()
    for op in ("=", ">", "<", ">=", "<="):
        cmb_op.addItem(op, op)
    cmb_op.setCurrentText(_MEMORY.sides_operator)
    spin_sides = QtWidgets.QSpinBox()
    spin_sides.setRange(3, 64)
    spin_sides.setValue(_MEMORY.sides_target)
    row_rule.addWidget(cmb_op)
    row_rule.addWidget(spin_sides)
    row_rule.addStretch()
    lay.addLayout(row_rule)

    status_lbl = QtWidgets.QLabel("")
    status_lbl.setStyleSheet("color: #8FC0F0;")
    lay.addWidget(status_lbl)

    accepted = {"ok": False}

    def apply_preview() -> None:
        op = cmb_op.currentText()
        target = spin_sides.value()
        _MEMORY.sides_operator = op
        _MEMORY.sides_target = target
        chosen = filter_faces_by_sides(degrees, op, target)
        _set_poly_selection(rt, node, 4, chosen)
        status_lbl.setText(f"匹配面数: {len(chosen)} / {num_faces}")

    def set_rule(op: str, val: int) -> None:
        cmb_op.setCurrentText(op)
        spin_sides.setValue(val)
        apply_preview()

    b_tri.clicked.connect(lambda: set_rule("=", 3))
    b_quad.clicked.connect(lambda: set_rule("=", 4))
    b_ngon.clicked.connect(lambda: set_rule(">", 4))
    cmb_op.currentTextChanged.connect(lambda _t: apply_preview())
    spin_sides.valueChanged.connect(lambda _v: apply_preview())

    btns = QtWidgets.QHBoxLayout()
    btns.addStretch()
    ok_btn = QtWidgets.QPushButton("确定")
    ok_btn.setObjectName("okBtn")
    cancel_btn = QtWidgets.QPushButton("取消")
    btns.addWidget(ok_btn)
    btns.addWidget(cancel_btn)
    lay.addLayout(btns)

    ok_btn.clicked.connect(lambda: (accepted.__setitem__("ok", True), dlg.accept()))
    cancel_btn.clicked.connect(dlg.reject)
    dlg.finished.connect(lambda _r: _set_poly_selection(rt, node, 4, orig_sel) if not accepted["ok"] else None)

    apply_preview()
    _show_single_panel(dlg)


def open_dot_step_panel(initial_mode: str = "loop") -> None:
    """Open custom PySide6 panel driving native Graphite PolyToolsSelect.DotLoop / DotRing."""
    from PySide6 import QtCore, QtWidgets

    rt = _get_rt()
    ctx = _resolve_poly_any(rt)
    if ctx is None:
        return
    node, cur, sub, is_mod = ctx
    if sub not in (1, 2, 4):
        rt.setCommandPanelTaskMode(rt.Name("modify"))
        rt.subObjectLevel = 2
        sub = 2

    orig_sel = _get_any_poly_selection(rt, node, cur, sub, is_mod)
    if not orig_sel:
        rt.pushPrompt("MaxHotbox 点循环/点环形: 请先选中至少一个起始子对象（顶点/边/面）")
        return

    dlg = QtWidgets.QDialog(_get_max_parent())
    dlg.setWindowTitle(f"点循环 / 点环形 (原生石墨 · {_subobj_sym(sub)})")
    dlg.setStyleSheet(_PANEL_QSS)
    dlg.setFixedWidth(350)

    lay = QtWidgets.QVBoxLayout(dlg)
    lay.setSpacing(10)

    row_mode = QtWidgets.QHBoxLayout()
    row_mode.addWidget(QtWidgets.QLabel("隔选模式:"))
    cmb_mode = QtWidgets.QComboBox()
    cmb_mode.addItem("点循环 (Dot Loop)", "loop")
    cmb_mode.addItem("点环形 (Dot Ring)", "ring")
    cmb_mode.setCurrentIndex(1 if initial_mode == "ring" else 0)
    row_mode.addWidget(cmb_mode, 1)
    lay.addLayout(row_mode)

    row_gap = QtWidgets.QHBoxLayout()
    row_gap.addWidget(QtWidgets.QLabel("间隔跳过 (Gap):"))
    s_gap = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
    s_gap.setRange(1, 20)
    s_gap.setValue(max(1, _MEMORY.dot_gap))
    sp_gap = QtWidgets.QSpinBox()
    sp_gap.setRange(1, 20)
    sp_gap.setValue(max(1, _MEMORY.dot_gap))
    row_gap.addWidget(s_gap, 1)
    row_gap.addWidget(sp_gap)
    lay.addLayout(row_gap)

    chk_cyl = QtWidgets.QCheckBox("圆柱端面处理 (Cylinder Ends · 仅 Dot Loop)")
    chk_cyl.setChecked(_MEMORY.dot_cylinder_ends)
    chk_opp = QtWidgets.QCheckBox("反向偏移 (Opposite · 仅 Dot Loop)")
    chk_opp.setChecked(_MEMORY.dot_opposite)
    lay.addWidget(chk_cyl)
    lay.addWidget(chk_opp)

    status_lbl = QtWidgets.QLabel("")
    status_lbl.setStyleSheet("color: #8FC0F0;")
    lay.addWidget(status_lbl)

    accepted = {"ok": False}

    def apply_preview() -> None:
        mode = str(cmb_mode.currentData() or "loop")
        gap = sp_gap.value()
        cyl = chk_cyl.isChecked()
        opp = chk_opp.isChecked()
        _MEMORY.dot_gap = gap
        _MEMORY.dot_cylinder_ends = cyl
        _MEMORY.dot_opposite = opp

        is_loop = mode == "loop"
        chk_cyl.setEnabled(is_loop)
        chk_opp.setEnabled(is_loop)

        # Always reset back to initial seed selection before running native PolyToolsSelect
        _set_any_poly_selection(rt, node, cur, sub, orig_sel, is_mod)
        try:
            if mode == "ring":
                rt.PolyToolsSelect.DotRing(gap)
            else:
                rt.PolyToolsSelect.DotLoop(gap, cyl, opp)
            rt.redrawViews()
        except Exception as exc:
            status_lbl.setText(f"提示: {exc}")
            return

        now_sel = _get_any_poly_selection(rt, node, cur, sub, is_mod)
        status_lbl.setText(f"实时预览: 已选中 {len(now_sel)} 项 (间隔跳过 {gap})")

    s_gap.valueChanged.connect(sp_gap.setValue)
    sp_gap.valueChanged.connect(s_gap.setValue)
    sp_gap.valueChanged.connect(lambda _v: apply_preview())
    chk_cyl.toggled.connect(lambda _c: apply_preview())
    chk_opp.toggled.connect(lambda _c: apply_preview())
    cmb_mode.currentIndexChanged.connect(lambda _i: apply_preview())

    btns = QtWidgets.QHBoxLayout()
    btns.addStretch()
    ok_btn = QtWidgets.QPushButton("确定")
    ok_btn.setObjectName("okBtn")
    cancel_btn = QtWidgets.QPushButton("取消")
    btns.addWidget(ok_btn)
    btns.addWidget(cancel_btn)
    lay.addLayout(btns)

    ok_btn.clicked.connect(lambda: (accepted.__setitem__("ok", True), dlg.accept()))
    cancel_btn.clicked.connect(dlg.reject)
    dlg.finished.connect(
        lambda _r: _set_any_poly_selection(rt, node, cur, sub, orig_sel, is_mod)
        if not accepted["ok"]
        else None
    )

    apply_preview()
    _show_single_panel(dlg)


def open_spline_divide_panel() -> None:
    """Open custom PySide6 panel to subdivide selected Spline segments by exact count."""
    from PySide6 import QtCore, QtWidgets

    rt = _get_rt()
    try:
        if int(rt.selection.count) == 0:
            rt.pushPrompt("MaxHotbox 样条拆分: 请先选择一个样条线对象")
            return
        node = rt.selection[0]
        if str(rt.superClassOf(node)).lower() != "shape":
            rt.pushPrompt("MaxHotbox 样条拆分: 当前选中对象不是样条线")
            return
    except Exception:
        return

    dlg = QtWidgets.QDialog(_get_max_parent())
    dlg.setWindowTitle("拆分样条线段 (Divide Segments)")
    dlg.setStyleSheet(_PANEL_QSS)
    dlg.setFixedWidth(310)

    lay = QtWidgets.QVBoxLayout(dlg)
    lay.setSpacing(10)

    row = QtWidgets.QHBoxLayout()
    row.addWidget(QtWidgets.QLabel("每段新增顶点数:"))
    slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
    slider.setRange(1, 32)
    slider.setValue(_MEMORY.spline_divide_count)
    spin = QtWidgets.QSpinBox()
    spin.setRange(1, 32)
    spin.setValue(_MEMORY.spline_divide_count)
    row.addWidget(slider, 1)
    row.addWidget(spin)
    lay.addLayout(row)

    slider.valueChanged.connect(spin.setValue)
    spin.valueChanged.connect(slider.setValue)

    btns = QtWidgets.QHBoxLayout()
    btns.addStretch()
    ok_btn = QtWidgets.QPushButton("执行拆分")
    ok_btn.setObjectName("okBtn")
    cancel_btn = QtWidgets.QPushButton("取消")
    btns.addWidget(ok_btn)
    btns.addWidget(cancel_btn)
    lay.addLayout(btns)

    def do_divide() -> None:
        divs = spin.value()
        _MEMORY.spline_divide_count = divs
        ms = (
            '(undo "MaxHotbox: Spline Divide" on ('
            "if selection.count > 0 do ("
            "local sh = selection[1];"
            "if (classOf sh == SplineShape or classOf sh == line) do ("
            "for s = 1 to (numSplines sh) do ("
            "local segs = getSegSelection sh s;"
            "for idx = segs.count to 1 by -1 do ("
            f"subdivideSegment sh s segs[idx] {divs}));"
            "updateShape sh))))"
        )
        rt.execute(ms)
        rt.pushPrompt(f"MaxHotbox 样条拆分: 已对选中线段各插入 {divs} 个顶点")
        dlg.accept()

    ok_btn.clicked.connect(do_divide)
    cancel_btn.clicked.connect(dlg.reject)
    _show_single_panel(dlg)


# --------------------------------------------- Select Similar (FEAT-001)


def _collect_poly_similar_signatures(rt: Any, node: Any, sub: int) -> dict[int, tuple[int, float]]:
    """Build (topology_count, geometric_size) signatures for Vertex/Edge/Polygon."""
    sigs: dict[int, tuple[int, float]] = {}
    if sub == 1:
        num_v = int(rt.polyop.getNumVerts(node))
        for vid in range(1, num_v + 1):
            edges = _from_bitarray(rt.polyop.getEdgesUsingVert(node, vid))
            sigs[vid] = (len(edges), 0.0)
    elif sub in (2, 3):
        num_e = int(rt.polyop.getNumEdges(node))
        for eid in range(1, num_e + 1):
            verts = _from_bitarray(rt.polyop.getEdgeVerts(node, eid))
            faces = _from_bitarray(rt.polyop.getEdgeFaces(node, eid))
            length = 0.0
            if len(verts) == 2:
                p1 = rt.polyop.getVert(node, verts[0])
                p2 = rt.polyop.getVert(node, verts[1])
                length = math.sqrt(
                    (float(p2.x) - float(p1.x)) ** 2
                    + (float(p2.y) - float(p1.y)) ** 2
                    + (float(p2.z) - float(p1.z)) ** 2
                )
            sigs[eid] = (len(faces), length)
    else:
        num_f = int(rt.polyop.getNumFaces(node))
        for fid in range(1, num_f + 1):
            deg = int(rt.polyop.getFaceDeg(node, fid))
            area = float(rt.polyop.getFaceArea(node, fid))
            sigs[fid] = (deg, area)
    return sigs


def run_select_similar(
    tolerance_pct: int | None = None,
    match_topo: bool | None = None,
    match_size: bool | None = None,
) -> int:
    """Graphite-style Select Similar working across Object, Vertex, Edge, and Polygon levels."""
    rt = _get_rt()
    try:
        if int(rt.selection.count) == 0:
            rt.pushPrompt("MaxHotbox 选择相似: 请先选中参考对象或子对象")
            return 0
    except Exception:
        return 0

    sub = int(rt.subObjectLevel) if rt.subObjectLevel is not None else 0
    if sub == 0:
        # Object-level Select Similar via native 3ds Max command
        try:
            rt.execute('(actionMan.executeAction 0 "40099")')
        except Exception:
            try:
                rt.execute('(macros.run "Edit" "Select_Similar")')
            except Exception:
                pass
        cnt = int(rt.selection.count)
        rt.pushPrompt(f"MaxHotbox 选择相似对象: 已选中 {cnt} 个对象")
        return cnt

    ctx = _resolve_editable_poly(rt)
    if ctx is None:
        return 0
    node, _cur, sub = ctx
    seeds = _get_poly_selection(rt, node, sub)
    if not seeds:
        rt.pushPrompt("MaxHotbox 选择相似: 请先选中至少一个参考子对象（顶点/边/面）")
        return 0

    tol = _MEMORY.similar_tolerance if tolerance_pct is None else int(tolerance_pct)
    m_topo = _MEMORY.similar_match_topo if match_topo is None else bool(match_topo)
    m_size = _MEMORY.similar_match_size if match_size is None else bool(match_size)
    _MEMORY.similar_tolerance = tol
    _MEMORY.similar_match_topo = m_topo
    _MEMORY.similar_match_size = m_size

    sigs = _collect_poly_similar_signatures(rt, node, sub)
    chosen = select_similar_by_signature(
        seeds,
        sigs,
        tolerance_percent=float(tol),
        match_topology=m_topo,
        match_size=m_size,
    )
    _set_poly_selection(rt, node, sub, chosen)
    rt.pushPrompt(f"MaxHotbox 选择相似 (容差 {tol}%): 已选中 {len(chosen)} 项")
    return len(chosen)


def open_select_similar_panel() -> None:
    """Open custom PySide6 live-preview Select Similar panel for Vertex/Edge/Polygon."""
    from PySide6 import QtCore, QtWidgets

    rt = _get_rt()
    sub = int(rt.subObjectLevel) if rt.subObjectLevel is not None else 0
    if sub == 0:
        run_select_similar()
        return

    ctx = _resolve_editable_poly(rt)
    if ctx is None:
        return
    node, _cur, sub = ctx
    orig_sel = _get_poly_selection(rt, node, sub)
    if not orig_sel:
        rt.pushPrompt("MaxHotbox 选择相似: 请先选中至少一个参考子对象")
        return

    sigs = _collect_poly_similar_signatures(rt, node, sub)

    dlg = QtWidgets.QDialog(_get_max_parent())
    dlg.setWindowTitle(f"选择相似 (Select Similar · {_subobj_sym(sub)})")
    dlg.setStyleSheet(_PANEL_QSS)
    dlg.setFixedWidth(340)

    lay = QtWidgets.QVBoxLayout(dlg)
    lay.setSpacing(10)

    row_tol = QtWidgets.QHBoxLayout()
    row_tol.addWidget(QtWidgets.QLabel("尺寸容差:"))
    slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
    slider.setRange(0, 50)
    slider.setValue(_MEMORY.similar_tolerance)
    spin = QtWidgets.QSpinBox()
    spin.setRange(0, 50)
    spin.setSuffix(" %")
    spin.setValue(_MEMORY.similar_tolerance)
    row_tol.addWidget(slider, 1)
    row_tol.addWidget(spin)
    lay.addLayout(row_tol)

    chk_topo = QtWidgets.QCheckBox("匹配拓扑结构（顶点数 / 边数 / 邻接数）")
    chk_topo.setChecked(_MEMORY.similar_match_topo)
    chk_size = QtWidgets.QCheckBox("匹配几何尺寸（边长 / 面积）")
    chk_size.setChecked(_MEMORY.similar_match_size and sub != 1)
    chk_size.setEnabled(sub != 1)
    lay.addWidget(chk_topo)
    lay.addWidget(chk_size)

    status_lbl = QtWidgets.QLabel("")
    status_lbl.setStyleSheet("color: #8FC0F0;")
    lay.addWidget(status_lbl)

    accepted = {"ok": False}

    def apply_preview() -> None:
        tol = spin.value()
        m_topo = chk_topo.isChecked()
        m_size = chk_size.isChecked()
        _MEMORY.similar_tolerance = tol
        _MEMORY.similar_match_topo = m_topo
        _MEMORY.similar_match_size = m_size
        chosen = select_similar_by_signature(
            orig_sel,
            sigs,
            tolerance_percent=float(tol),
            match_topology=m_topo,
            match_size=m_size,
        )
        _set_poly_selection(rt, node, sub, chosen)
        status_lbl.setText(f"实时预览: 匹配到 {len(chosen)} / {len(sigs)} 项")

    slider.valueChanged.connect(spin.setValue)
    spin.valueChanged.connect(slider.setValue)
    spin.valueChanged.connect(lambda _v: apply_preview())
    chk_topo.toggled.connect(lambda _c: apply_preview())
    chk_size.toggled.connect(lambda _c: apply_preview())

    btns = QtWidgets.QHBoxLayout()
    btns.addStretch()
    ok_btn = QtWidgets.QPushButton("确定")
    ok_btn.setObjectName("okBtn")
    cancel_btn = QtWidgets.QPushButton("取消")
    btns.addWidget(ok_btn)
    btns.addWidget(cancel_btn)
    lay.addLayout(btns)

    ok_btn.clicked.connect(lambda: (accepted.__setitem__("ok", True), dlg.accept()))
    cancel_btn.clicked.connect(dlg.reject)
    dlg.finished.connect(
        lambda _r: _set_poly_selection(rt, node, sub, orig_sel) if not accepted["ok"] else None
    )

    apply_preview()
    _show_single_panel(dlg)


# ------------------------------------ Smoothing Groups & Auto Smooth (FEAT-002)


def open_smoothing_groups_panel() -> None:
    """Open custom 3ds Max 2026 PySide6 Smoothing Groups (1–32) & Auto Smooth Threshold dialog."""
    from PySide6 import QtCore, QtWidgets

    rt = _get_rt()
    ctx = _resolve_poly_any(rt)
    if ctx is None:
        return
    node, cur, sub, is_mod = ctx
    if sub not in (4, 5):
        rt.setCommandPanelTaskMode(rt.Name("modify"))
        rt.subObjectLevel = 4

    try:
        current_thr = float(getattr(cur, "autoSmoothThreshold", _MEMORY.auto_smooth_angle))
    except Exception:
        current_thr = _MEMORY.auto_smooth_angle

    dlg = QtWidgets.QDialog(_get_max_parent())
    dlg.setWindowTitle("平滑组与自动平滑 (Smoothing Groups & Auto Smooth)")
    dlg.setStyleSheet(
        _PANEL_QSS
        + """
        QPushButton#sgBtn {
            min-width: 30px; min-height: 26px; padding: 2px;
            background-color: #2B2B2B; color: #CCCCCC; border: 1px solid #4E4E4E;
        }
        QPushButton#sgBtn:checked {
            background-color: #3D75B3; color: #FFFFFF; border: 1px solid #70A8E0; font-weight: bold;
        }
        """
    )
    dlg.setFixedWidth(360)

    lay = QtWidgets.QVBoxLayout(dlg)
    lay.setSpacing(10)

    # Auto Smooth section
    row_as = QtWidgets.QHBoxLayout()
    row_as.addWidget(QtWidgets.QLabel("自动平滑阈值:"))
    slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
    slider.setRange(0, 180)
    slider.setValue(int(round(current_thr)))
    spin = QtWidgets.QDoubleSpinBox()
    spin.setRange(0.0, 180.0)
    spin.setDecimals(1)
    spin.setSuffix(" °")
    spin.setValue(current_thr)
    row_as.addWidget(slider, 1)
    row_as.addWidget(spin)
    lay.addLayout(row_as)

    slider.valueChanged.connect(lambda v: spin.setValue(float(v)))
    spin.valueChanged.connect(lambda v: slider.setValue(int(round(v))))

    row_as_btns = QtWidgets.QHBoxLayout()
    btn_auto = QtWidgets.QPushButton("执行自动平滑 (Auto Smooth)")
    btn_auto.setObjectName("okBtn")
    btn_clear = QtWidgets.QPushButton("清除全部平滑组")
    row_as_btns.addWidget(btn_auto, 1)
    row_as_btns.addWidget(btn_clear)
    lay.addLayout(row_as_btns)

    # 8x4 Smoothing Groups Matrix (1..32)
    lay.addWidget(QtWidgets.QLabel("手动平滑组 (1 - 32，点击切换选中面的平滑组):"))
    grid = QtWidgets.QGridLayout()
    grid.setSpacing(3)
    sg_buttons: dict[int, Any] = {}

    def read_common_mask() -> int:
        if is_mod:
            return 0
        sel_faces = _get_poly_selection(rt, node, 4)
        if not sel_faces:
            return 0
        mask = 0
        for fid in sel_faces[:500]:
            mask |= int(rt.polyop.getFaceSmoothGroup(node, fid))
        return mask

    def refresh_grid() -> None:
        mask = read_common_mask()
        for g in range(1, 33):
            b = sg_buttons[g]
            b.blockSignals(True)
            b.setChecked(bool(mask & (1 << (g - 1))))
            b.blockSignals(False)

    def on_sg_clicked(group_idx: int, checked: bool) -> None:
        if is_mod:
            rt.pushPrompt("MaxHotbox 平滑组: 手动 1-32 矩阵仅支持 Editable Poly（Edit Poly 请使用上方自动平滑）")
            return
        sel_faces = _get_poly_selection(rt, node, 4)
        if not sel_faces:
            rt.pushPrompt("MaxHotbox 平滑组: 请先选中至少一个多边形面")
            refresh_grid()
            return
        for fid in sel_faces:
            old_m = int(rt.polyop.getFaceSmoothGroup(node, fid))
            new_m = toggle_smoothing_group_bit(old_m, group_idx, enable=checked)
            rt.polyop.setFaceSmoothGroup(node, fid, new_m, False)
        rt.redrawViews()

    for g in range(1, 33):
        btn = QtWidgets.QPushButton(str(g))
        btn.setObjectName("sgBtn")
        btn.setCheckable(True)
        btn.setEnabled(not is_mod)
        btn.clicked.connect(lambda checked, idx=g: on_sg_clicked(idx, checked))
        sg_buttons[g] = btn
        grid.addWidget(btn, (g - 1) // 8, (g - 1) % 8)
    lay.addLayout(grid)

    def do_auto_smooth() -> None:
        angle = float(spin.value())
        _MEMORY.auto_smooth_angle = angle
        try:
            cur.autoSmoothThreshold = angle
        except Exception:
            pass
        try:
            if not is_mod:
                cur.ButtonOp(rt.Name("AutoSmooth"))
            else:
                cur.ButtonOp(rt.Name("Autosmooth"))
            rt.redrawViews()
            rt.pushPrompt(f"MaxHotbox 自动平滑: 已按 {angle:.1f}° 执行")
        except Exception as exc:
            rt.pushPrompt(f"MaxHotbox 自动平滑失败: {exc}")
        refresh_grid()

    def do_clear_sg() -> None:
        if not is_mod:
            sel_faces = _get_poly_selection(rt, node, 4)
            if sel_faces:
                rt.polyop.setFaceSmoothGroup(node, _to_bitarray(rt, sel_faces), 0, False)
                rt.redrawViews()
                rt.pushPrompt("MaxHotbox: 已清除选中面的所有平滑组")
        else:
            try:
                cur.SetOperation(rt.Name("ClearAll"))
            except Exception:
                pass
        refresh_grid()

    btn_auto.clicked.connect(do_auto_smooth)
    btn_clear.clicked.connect(do_clear_sg)

    footer = QtWidgets.QHBoxLayout()
    footer.addStretch()
    close_btn = QtWidgets.QPushButton("关闭")
    close_btn.clicked.connect(dlg.accept)
    footer.addWidget(close_btn)
    lay.addLayout(footer)

    refresh_grid()
    _show_single_panel(dlg)


def open_angle_select_panel(mode: str = "hard_edges") -> None:
    """Open custom PySide6 Angle Threshold dialog for Hard Edges or Coplanar Faces."""
    from PySide6 import QtCore, QtWidgets

    rt = _get_rt()
    ctx = _resolve_editable_poly(rt)
    if ctx is None:
        return
    node, _cur, _sub = ctx
    rt.setCommandPanelTaskMode(rt.Name("modify"))

    is_edges = mode == "hard_edges"
    sub_level = 2 if is_edges else 4
    rt.subObjectLevel = sub_level
    orig_sel = _get_poly_selection(rt, node, sub_level)

    if not is_edges and not orig_sel:
        rt.pushPrompt("MaxHotbox 按角度选面: 请先选中至少一个起始面")
        return

    normals = _collect_face_normals(rt, node)
    num_edges = int(rt.polyop.getNumEdges(node))
    edge_faces = {eid: _from_bitarray(rt.polyop.getEdgeFaces(node, eid)) for eid in range(1, num_edges + 1)}
    face_adj: dict[int, set[int]] = {}
    if not is_edges:
        for faces in edge_faces.values():
            if len(faces) == 2:
                a, b = faces
                face_adj.setdefault(a, set()).add(b)
                face_adj.setdefault(b, set()).add(a)

    dlg = QtWidgets.QDialog(_get_max_parent())
    dlg.setWindowTitle("选择硬边 (Hard Edges)" if is_edges else "按角度选共面 (Select by Angle)")
    dlg.setStyleSheet(_PANEL_QSS)
    dlg.setFixedWidth(340)

    lay = QtWidgets.QVBoxLayout(dlg)
    lay.setSpacing(10)

    init_val = int(round(_MEMORY.hard_edge_angle if is_edges else _MEMORY.coplanar_angle))
    row_ang = QtWidgets.QHBoxLayout()
    row_ang.addWidget(QtWidgets.QLabel("角度阈值:"))
    slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
    slider.setRange(1, 179)
    slider.setValue(init_val)
    spin = QtWidgets.QSpinBox()
    spin.setRange(1, 179)
    spin.setSuffix(" °")
    spin.setValue(init_val)
    row_ang.addWidget(slider, 1)
    row_ang.addWidget(spin)
    lay.addLayout(row_ang)

    status_lbl = QtWidgets.QLabel("")
    status_lbl.setStyleSheet("color: #8FC0F0;")
    lay.addWidget(status_lbl)

    accepted = {"ok": False}

    def apply_preview() -> None:
        ang = float(spin.value())
        if is_edges:
            _MEMORY.hard_edge_angle = ang
            chosen = select_hard_edges_from_normals(edge_faces, normals, angle_threshold_deg=ang)
            _set_poly_selection(rt, node, 2, chosen)
            status_lbl.setText(f"硬边 (≥ {ang:.0f}°): 选中 {len(chosen)} 条边")
        else:
            _MEMORY.coplanar_angle = ang
            chosen = flood_fill_faces_by_angle(orig_sel, face_adj, normals, max_angle_deg=ang)
            _set_poly_selection(rt, node, 4, chosen)
            status_lbl.setText(f"共面 (≤ {ang:.0f}°): 选中 {len(chosen)} 个面")

    slider.valueChanged.connect(spin.setValue)
    spin.valueChanged.connect(slider.setValue)
    spin.valueChanged.connect(lambda _v: apply_preview())

    btns = QtWidgets.QHBoxLayout()
    btns.addStretch()
    ok_btn = QtWidgets.QPushButton("确定")
    ok_btn.setObjectName("okBtn")
    cancel_btn = QtWidgets.QPushButton("取消")
    btns.addWidget(ok_btn)
    btns.addWidget(cancel_btn)
    lay.addLayout(btns)

    ok_btn.clicked.connect(lambda: (accepted.__setitem__("ok", True), dlg.accept()))
    cancel_btn.clicked.connect(dlg.reject)
    dlg.finished.connect(
        lambda _r: _set_poly_selection(rt, node, sub_level, orig_sel) if not accepted["ok"] else None
    )

    apply_preview()
    _show_single_panel(dlg)
