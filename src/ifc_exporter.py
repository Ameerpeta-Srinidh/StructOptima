"""
IFC4 export of the designed structure (visuals phase 2, decision D-15).

Exports, per storey: IfcColumn, IfcBeam, IfcSlab, IfcWall and, at the base,
IfcFooting - extruded rectangular solids in metres - each with a
``Pset_StructOptima`` property set (mark, size, reinforcement, status,
governing combination, utilisation) so a BIM viewer can show the design
data when a member is clicked.

Geometry conventions (consistent with ``bim_loader``):
  * columns: placement at (x, y, z_bottom), extruded +Z by the storey height;
  * one storey per column storey; beams/slabs at the top of a storey belong to it;
  * beams: top of beam at the floor level; local Z = beam axis, profile
    XDim = width (horizontal), YDim = depth (vertical);
  * slabs: one solid per panel, top at the floor level;
  * walls: per storey, on the storey floor, height = wall clear height;
  * footings: top at column base (z = 0) - the founding level is NOT designed.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional

import numpy as np


def _api():
    import ifcopenshell
    import ifcopenshell.api
    return ifcopenshell, ifcopenshell.api.run


def _matrix(origin, x_axis, z_axis) -> np.ndarray:
    x = np.asarray(x_axis, dtype=float)
    z = np.asarray(z_axis, dtype=float)
    x = x / np.linalg.norm(x)
    z = z / np.linalg.norm(z)
    y = np.cross(z, x)
    m = np.eye(4)
    m[:3, 0], m[:3, 1], m[:3, 2], m[:3, 3] = x, y, z, origin
    return m


def export_ifc(gm, beams, footings, project_name: str = "StructOptima model", marks=None) -> bytes:
    """Return the IFC4 file content (STEP text, UTF-8)."""
    ifcopenshell, run = _api()
    if marks is None:
        from .drawings import compute_marks
        marks = compute_marks(gm, beams, footings)

    f = ifcopenshell.file(schema="IFC4")
    project = run("root.create_entity", f, ifc_class="IfcProject", name=project_name)
    run("unit.assign_unit", f, units=[run("unit.add_si_unit", f, unit_type="LENGTHUNIT")])
    model = run("context.add_context", f, context_type="Model")
    body = run("context.add_context", f, context_type="Model", context_identifier="Body",
               target_view="MODEL_VIEW", parent=model)
    site = run("root.create_entity", f, ifc_class="IfcSite", name="Site")
    building = run("root.create_entity", f, ifc_class="IfcBuilding", name=project_name)
    run("aggregate.assign_object", f, relating_object=project, products=[site])
    run("aggregate.assign_object", f, relating_object=site, products=[building])

    concrete = run("material.add_material", f, name=f"Concrete M{gm.fck:.0f}")
    masonry = run("material.add_material", f, name="Brick masonry")

    # storeys at the bottom of each column storey
    n = gm.num_stories
    bottoms, tops = [], []
    for lvl in range(n):
        segs = [c for c in gm.columns if c.level == lvl]
        bottoms.append(min((c.z_bottom for c in segs), default=lvl * gm.story_height_m))
        tops.append(max((c.z_top for c in segs), default=(lvl + 1) * gm.story_height_m))
    # one IfcBuildingStorey per column storey; the beams and slabs at the top of
    # a storey belong to that storey (keeps the storey count on re-import)
    storeys = []
    for lvl in range(n):
        name = "Ground storey" if lvl == 0 else f"Storey {lvl}"
        st = run("root.create_entity", f, ifc_class="IfcBuildingStorey", name=name)
        st.Elevation = bottoms[lvl]
        run("aggregate.assign_object", f, relating_object=building, products=[st])
        m = np.eye(4)
        m[2, 3] = st.Elevation
        run("geometry.edit_object_placement", f, product=st, matrix=m, is_si=True)
        storeys.append(st)

    def solid(ifc_class, name, xdim, ydim, depth, matrix, storey, pset, material=concrete):
        el = run("root.create_entity", f, ifc_class=ifc_class, name=name)
        prof = f.create_entity("IfcRectangleProfileDef", ProfileType="AREA", XDim=float(xdim), YDim=float(ydim))
        rep = run("geometry.add_profile_representation", f, context=body, profile=prof, depth=float(depth))
        run("geometry.assign_representation", f, product=el, representation=rep)
        run("geometry.edit_object_placement", f, product=el, matrix=matrix, is_si=True)
        run("spatial.assign_container", f, relating_structure=storey, products=[el])
        run("material.assign_material", f, products=[el], material=material)
        ps = run("pset.add_pset", f, product=el, name="Pset_StructOptima")
        run("pset.edit_pset", f, pset=ps, properties={k: v for k, v in pset.items() if v is not None})
        return el

    # columns
    for c in gm.columns:
        r = gm.rebar_schedule.get(c.id)
        w, d = c.width_nb, c.depth_nb
        if abs((c.orientation_deg % 180.0) - 90.0) < 1.0:
            w, d = d, w
        solid("IfcColumn", c.id, w / 1000, d / 1000, c.z_top - c.z_bottom,
              _matrix((c.x, c.y, c.z_bottom), (1, 0, 0), (0, 0, 1)), storeys[min(c.level, n - 1)],
              {"Mark": marks.columns.get(c.id, ""), "Size": f"{c.width_nb:.0f}x{c.depth_nb:.0f}",
               "MainBars": r.main_bars_desc if r else "-", "Ties": r.links_desc if r else "-",
               "Status": r.status if r else "NOT DESIGNED", "GoverningCombination": r.governing_combo if r else "",
               "InteractionRatio": float(r.interaction_ratio) if r else 0.0,
               "ServiceLoad_kN": float(c.load_kn)})

    # beams and slabs on every floor (top of beam / slab at the floor level)
    panels = list(zip(gm.slab_panels(), gm.slab_schedule.items()))
    for lvl in range(1, n + 1):
        z = tops[lvl - 1]
        st = storeys[lvl - 1]
        for b in beams:
            res = gm.get_beam_result(b.id)
            if res is None:
                continue
            dx, dy = b.end_point.x - b.start_point.x, b.end_point.y - b.start_point.y
            L = math.hypot(dx, dy)
            if L < 1e-6:
                continue
            ux, uy = dx / L, dy / L
            D = res.depth_mm / 1000
            solid("IfcBeam", f"{b.id}_L{lvl - 1}", res.width_mm / 1000, D, L,
                  _matrix((b.start_point.x, b.start_point.y, z - D / 2), (-uy, ux, 0), (ux, uy, 0)), st,
                  {"Mark": marks.beams.get(b.id, ""), "Size": res.size_label, "Top": res.top_bars_desc,
                   "Bottom": res.bottom_bars_desc, "Stirrups": res.stirrups_desc, "Status": res.status,
                   "GoverningCombination": res.governing_combo, "MuSagging_kNm": float(res.mu_sagging_knm),
                   "MuHogging_kNm": float(res.mu_hogging_knm), "Vu_kN": float(res.vu_kn)})
        for p, (sid, s) in panels:
            t = s.thickness_mm / 1000
            solid("IfcSlab", f"{sid}_L{lvl - 1}", p["x1"] - p["x0"], p["y1"] - p["y0"], t,
                  _matrix(((p["x0"] + p["x1"]) / 2, (p["y0"] + p["y1"]) / 2, z - t), (1, 0, 0), (0, 0, 1)), st,
                  {"Mark": marks.slabs.get(sid, ""), "Thickness_mm": float(s.thickness_mm),
                   "BottomShortSpan": s.main_steel_desc, "BottomLongSpan": s.dist_steel_desc,
                   "Top": s.top_steel_desc, "Status": s.status})

    # walls on every storey
    for lvl in range(n):
        for w in gm.walls:
            dx, dy = w.end_x - w.start_x, w.end_y - w.start_y
            L = math.hypot(dx, dy)
            if L < 1e-6:
                continue
            ux, uy = dx / L, dy / L
            solid("IfcWall", f"{w.id}_L{lvl}", L, w.thickness_mm / 1000, w.height_m,
                  _matrix(((w.start_x + w.end_x) / 2, (w.start_y + w.end_y) / 2, bottoms[lvl]), (ux, uy, 0), (0, 0, 1)),
                  storeys[lvl], {"Thickness_mm": float(w.thickness_mm), "OpeningFraction": float(w.opening_fraction),
                                 "LineLoad_kN_m": float(w.line_load_kn_m)}, material=masonry)

    # footings below the ground-storey columns
    level0 = {c.id: c for c in gm.columns if c.level == 0}
    for ft in footings:
        c = level0.get(ft.id[2:])
        if c is None:
            continue
        t = ft.thickness_mm / 1000
        solid("IfcFooting", ft.id, ft.length_m, ft.width_m, t, _matrix((c.x, c.y, c.z_bottom - t), (1, 0, 0), (0, 0, 1)),
              storeys[0], {"Mark": marks.footings.get(ft.id, ""), "Size": f"{ft.length_m * 1000:.0f}x{ft.width_m * 1000:.0f}",
                           "Depth_mm": float(ft.thickness_mm), "BottomSteel": ft.rebar_desc, "Status": ft.status,
                           "FoundingLevel": "NOT DESIGNED - shown directly below the column base"})
    return f.to_string().encode("utf-8")
