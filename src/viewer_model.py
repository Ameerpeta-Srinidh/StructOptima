"""
Scene description for the browser 3D viewer / walkthrough (visuals phases 3-4).

``build_scene(gm, beams, footings)`` returns a JSON-serialisable dict of boxes
(one per column segment, beam per floor, slab panel per floor, wall per storey,
footing) in metres, Z up, with the same geometry conventions as
``ifc_exporter`` and the design data shown when a member is clicked.
``viewer_html(scene)`` returns a self-contained HTML page (the committed
three.js bundle ``components/viewer3d/dist/viewer.js`` inlined) for
``streamlit.components.v1.html``.
"""

from __future__ import annotations

import json
import math
import os
from typing import Dict, List, Optional

_BUNDLE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "components", "viewer3d", "dist", "viewer.js")


def _box(kind, name, storey, cx, cy, cz, sx, sy, sz, yaw, status, props):
    return {"kind": kind, "id": name, "storey": storey,
            "c": [round(cx, 4), round(cy, 4), round(cz, 4)],
            "s": [round(sx, 4), round(sy, 4), round(sz, 4)],
            "yaw": round(yaw, 6), "status": status or "",
            "props": {k: v for k, v in props.items() if v not in (None, "")}}


def build_scene(gm, beams, footings, marks=None) -> Dict:
    if marks is None:
        from .drawings import compute_marks
        marks = compute_marks(gm, beams, footings)
    n = gm.num_stories
    bottoms, tops = [], []
    for lvl in range(n):
        segs = [c for c in gm.columns if c.level == lvl]
        bottoms.append(min((c.z_bottom for c in segs), default=lvl * gm.story_height_m))
        tops.append(max((c.z_top for c in segs), default=(lvl + 1) * gm.story_height_m))
    storey_names = ["Ground storey" if i == 0 else f"Storey {i}" for i in range(n)]
    items: List[Dict] = []

    for c in gm.columns:
        r = gm.rebar_schedule.get(c.id)
        w, d = c.width_nb / 1000, c.depth_nb / 1000
        if abs((c.orientation_deg % 180.0) - 90.0) < 1.0:
            w, d = d, w
        h = c.z_top - c.z_bottom
        items.append(_box("column", c.id, min(c.level, n - 1), c.x, c.y, c.z_bottom + h / 2, w, d, h, 0.0,
                          r.status if r else "NOT DESIGNED",
                          {"Mark": marks.columns.get(c.id), "Size (mm)": f"{c.width_nb:.0f} x {c.depth_nb:.0f}",
                           "Main bars": r.main_bars_desc if r else None, "Ties": r.links_desc if r else None,
                           "Governing combination": r.governing_combo if r else None,
                           "Interaction ratio": round(float(r.interaction_ratio), 3) if r else None,
                           "Service load (kN)": round(float(c.load_kn), 1)}))

    panels = list(zip(gm.slab_panels(), gm.slab_schedule.items()))
    for lvl in range(1, n + 1):
        z = tops[lvl - 1]
        for b in beams:
            res = gm.get_beam_result(b.id)
            if res is None:
                continue
            dx, dy = b.end_point.x - b.start_point.x, b.end_point.y - b.start_point.y
            L = math.hypot(dx, dy)
            if L < 1e-6:
                continue
            D = res.depth_mm / 1000
            items.append(_box("beam", f"{b.id}_L{lvl - 1}", lvl - 1,
                              (b.start_point.x + b.end_point.x) / 2, (b.start_point.y + b.end_point.y) / 2, z - D / 2,
                              L, res.width_mm / 1000, D, math.atan2(dy, dx), res.status,
                              {"Mark": marks.beams.get(b.id), "Size (mm)": res.size_label, "Top bars": res.top_bars_desc,
                               "Bottom bars": res.bottom_bars_desc, "Stirrups": res.stirrups_desc,
                               "Governing combination": res.governing_combo,
                               "Mu sagging (kNm)": round(float(res.mu_sagging_knm), 1),
                               "Mu hogging (kNm)": round(float(res.mu_hogging_knm), 1),
                               "Vu (kN)": round(float(res.vu_kn), 1)}))
        for p, (sid, s) in panels:
            t = s.thickness_mm / 1000
            items.append(_box("slab", f"{sid}_L{lvl - 1}", lvl - 1, (p["x0"] + p["x1"]) / 2, (p["y0"] + p["y1"]) / 2,
                              z - t / 2, p["x1"] - p["x0"], p["y1"] - p["y0"], t, 0.0, s.status,
                              {"Mark": marks.slabs.get(sid), "Thickness (mm)": f"{s.thickness_mm:.0f}",
                               "Bottom (short span)": s.main_steel_desc, "Bottom (long span)": s.dist_steel_desc,
                               "Top": s.top_steel_desc}))

    for lvl in range(n):
        for w in gm.walls:
            dx, dy = w.end_x - w.start_x, w.end_y - w.start_y
            L = math.hypot(dx, dy)
            if L < 1e-6:
                continue
            items.append(_box("wall", f"{w.id}_L{lvl}", lvl, (w.start_x + w.end_x) / 2, (w.start_y + w.end_y) / 2,
                              bottoms[lvl] + w.height_m / 2, L, w.thickness_mm / 1000, w.height_m, math.atan2(dy, dx), "",
                              {"Thickness (mm)": f"{w.thickness_mm:.0f}", "Opening fraction": round(float(w.opening_fraction), 2),
                               "Line load (kN/m)": round(float(w.line_load_kn_m), 2)}))

    level0 = {c.id: c for c in gm.columns if c.level == 0}
    for ft in footings:
        c = level0.get(ft.id[2:])
        if c is None:
            continue
        t = ft.thickness_mm / 1000
        items.append(_box("footing", ft.id, 0, c.x, c.y, c.z_bottom - t / 2, ft.length_m, ft.width_m, t, 0.0, ft.status,
                          {"Mark": marks.footings.get(ft.id), "Size (mm)": f"{ft.length_m * 1000:.0f} x {ft.width_m * 1000:.0f}",
                           "Depth (mm)": f"{ft.thickness_mm:.0f}", "Bottom steel": ft.rebar_desc,
                           "Founding level": "NOT DESIGNED - shown directly below the column base"}))

    xs = [c.x for c in gm.columns] or [0.0]
    ys = [c.y for c in gm.columns] or [0.0]
    return {"storeys": [{"name": storey_names[i], "z0": bottoms[i], "z1": tops[i]} for i in range(n)],
            "bbox": [min(xs), min(ys), max(xs), max(ys), (tops[-1] if tops else 0.0)],
            "items": items}


def bundle_available() -> bool:
    return os.path.isfile(_BUNDLE)


def viewer_html(scene: Dict, height_px: int = 680) -> str:
    """Self-contained HTML (bundle + scene inlined). Raises FileNotFoundError without the bundle."""
    with open(_BUNDLE, encoding="utf-8") as fh:
        js = fh.read()
    data = json.dumps(scene, separators=(",", ":")).replace("</", "<\\/")
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>html,body{{margin:0;height:100%;'
            f'overflow:hidden;font:13px system-ui,sans-serif}}#app{{position:relative;width:100%;height:{height_px}px}}'
            f'</style></head><body><div id="app"></div><script>{js}</script>'
            f'<script>SOViewer.mount(document.getElementById("app"),{data});</script></body></html>')
