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


# ------------------------------------------- Persistent In-Memory Tool Params


@dataclass
class GraphiteToolMemory:
    random_ratio: int = 30
    random_from_current: bool = False
    sides_operator: str = ">"
    sides_target: int = 4
    dot_step: int = 2
    dot_offset: int = 0
    hard_edge_angle: float = 30.0
    coplanar_angle: float = 25.0


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


def run_dot_step(mode: str = "loop", step: int | None = None, offset: int | None = None) -> int:
    rt = _get_rt()
    ctx = _resolve_editable_poly(rt)
    if ctx is None:
        return 0
    node, cur, _sub = ctx
    rt.setCommandPanelTaskMode(rt.Name("modify"))
    rt.subObjectLevel = 2

    use_step = _MEMORY.dot_step if step is None else int(step)
    use_off = _MEMORY.dot_offset if offset is None else int(offset)
    _MEMORY.dot_step = use_step
    _MEMORY.dot_offset = use_off

    _orig, chains = _compute_dot_edge_chains(rt, node, cur, mode)
    if not chains:
        return 0
    chosen = compute_dot_step_indices(chains, step=use_step, offset=use_off)
    _set_poly_selection(rt, node, 2, chosen)
    label = "点环形 Dot Ring" if mode == "ring" else "点循环 Dot Loop"
    rt.pushPrompt(f"MaxHotbox {label} (步长 {use_step}): 已选中 {len(chosen)} 条边")
    return len(chosen)


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
    """Open custom PySide6 Dot Loop / Dot Ring step & offset live-preview panel."""
    from PySide6 import QtCore, QtWidgets

    rt = _get_rt()
    ctx = _resolve_editable_poly(rt)
    if ctx is None:
        return
    node, cur, _sub = ctx
    rt.setCommandPanelTaskMode(rt.Name("modify"))
    rt.subObjectLevel = 2

    orig_sel = _get_poly_selection(rt, node, 2)
    if not orig_sel:
        rt.pushPrompt("MaxHotbox 点循环/点环形: 请先选中至少一条边")
        return

    cached_chains: dict[str, list[list[int]]] = {}

    def get_chains(mode: str) -> list[list[int]]:
        if mode not in cached_chains:
            _set_poly_selection(rt, node, 2, orig_sel)
            _, chains = _compute_dot_edge_chains(rt, node, cur, mode)
            cached_chains[mode] = chains
        return cached_chains[mode]

    dlg = QtWidgets.QDialog(_get_max_parent())
    dlg.setWindowTitle("点循环 / 点环形间距 (Dot Loop & Ring)")
    dlg.setStyleSheet(_PANEL_QSS)
    dlg.setFixedWidth(340)

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

    row_step = QtWidgets.QHBoxLayout()
    row_step.addWidget(QtWidgets.QLabel("间隔步长:"))
    s_step = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
    s_step.setRange(2, 20)
    s_step.setValue(max(2, _MEMORY.dot_step))
    sp_step = QtWidgets.QSpinBox()
    sp_step.setRange(2, 20)
    sp_step.setValue(max(2, _MEMORY.dot_step))
    row_step.addWidget(s_step, 1)
    row_step.addWidget(sp_step)
    lay.addLayout(row_step)

    row_off = QtWidgets.QHBoxLayout()
    row_off.addWidget(QtWidgets.QLabel("起始偏移:"))
    sp_off = QtWidgets.QSpinBox()
    sp_off.setRange(0, 19)
    sp_off.setValue(_MEMORY.dot_offset)
    row_off.addWidget(sp_off)
    row_off.addStretch()
    lay.addLayout(row_off)

    status_lbl = QtWidgets.QLabel("")
    status_lbl.setStyleSheet("color: #8FC0F0;")
    lay.addWidget(status_lbl)

    accepted = {"ok": False}

    def apply_preview() -> None:
        mode = str(cmb_mode.currentData() or "loop")
        step = sp_step.value()
        off = sp_off.value()
        _MEMORY.dot_step = step
        _MEMORY.dot_offset = off
        chains = get_chains(mode)
        chosen = compute_dot_step_indices(chains, step=step, offset=off)
        _set_poly_selection(rt, node, 2, chosen)
        status_lbl.setText(f"实时预览: 选中 {len(chosen)} 条边 (每 {step} 条选 1 条)")

    s_step.valueChanged.connect(sp_step.setValue)
    sp_step.valueChanged.connect(s_step.setValue)
    sp_step.valueChanged.connect(lambda _v: apply_preview())
    sp_off.valueChanged.connect(lambda _v: apply_preview())
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
    dlg.finished.connect(lambda _r: _set_poly_selection(rt, node, 2, orig_sel) if not accepted["ok"] else None)

    apply_preview()
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
