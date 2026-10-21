"""
Rows for the schedule and status tables shown in the UI.

Every value comes from the production design results (``DesignResults``, ``GridManager`` schedules,
``Footing``); nothing is estimated or defaulted here. A missing result is shown as such
("NOT DESIGNED", "-"), never as a pass. Kept free of Streamlit so the rows can be unit tested
(tests/test_ui_tables.py).
"""
import re
from typing import Any, Dict, Iterable, List

from .rebar_detailer import interaction_ratio_value

STATUS_ORDER = {"FAIL": 0, "WARN": 1, "PASS": 2}

BBS_SCOPE = ("The bar bending schedule covers one typical floor: the beams and slab panels of one floor and the "
             "ground-storey columns. Upper-storey columns, footings, staircases and wastage are not included, so its "
             "total is not the building's steel quantity (the Overview total covers all floors).")


def natural_key(member_id: str):
    """Sort C2 before C10."""
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", member_id)]


def _ok(flag: bool) -> str:
    return "PASS" if flag else "FAIL"


def design_status_summary(res) -> Dict[str, Any]:
    """The design status and issue counts, taken only from ``res.status`` / ``res.failures``."""
    failures = list(getattr(res, "failures", None) or [])
    return {"status": res.status,
            "n_fail": sum(1 for f in failures if f["Status"] == "FAIL"),
            "n_warn": sum(1 for f in failures if f["Status"] == "WARN")}


def issue_rows(failures: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    """The pipeline failure list, FAIL first, then WARN, keeping the pipeline order within each group."""
    rows = list(failures or [])
    return sorted(rows, key=lambda f: STATUS_ORDER.get(f["Status"], 3))


def column_rows(gm, marks) -> List[Dict[str, Any]]:
    rows = []
    schedule = getattr(gm, "rebar_schedule", None) or {}
    for col in sorted(gm.columns, key=lambda c: (c.level, natural_key(c.id))):
        r = schedule.get(col.id)
        height = col.z_top - col.z_bottom
        rows.append({
            "ID": col.id,
            "Mark": marks.columns.get(col.id, ""),
            "Level": col.level,
            "Size (mm)": f"{col.width_nb:.0f} x {col.depth_nb:.0f}",
            "Service load (kN)": round(col.load_kn, 1),
            "P-M ratio": interaction_ratio_value(r.interaction_ratio) if r is not None else None,
            "Main bars": r.main_bars_desc if r is not None else "-",
            "Ties": r.links_desc if r is not None else "-",
            "Steel (kg)": round(r.total_steel_weight_kg_per_m * height, 1) if r is not None else None,
            "Governing combination": r.governing_combo if r is not None else "-",
            "Status": r.status if r is not None else "NOT DESIGNED",
        })
    return rows


def beam_rows(gm, marks) -> List[Dict[str, Any]]:
    rows = []
    schedule = getattr(gm, "beam_schedule", None) or {}
    for bid in sorted(schedule, key=natural_key):
        r = schedule[bid]
        rows.append({
            "Beam": bid,
            "Mark": marks.beams.get(bid, ""),
            "Size (mm)": f"{r.width_mm:.0f} x {r.depth_mm:.0f}",
            "Span (m)": round(r.span_m, 2),
            "Bottom bars": r.bottom_bars_desc,
            "Top bars": r.top_bars_desc,
            "Stirrups": r.stirrups_desc,
            "Mu+ (kNm)": round(r.mu_sagging_knm, 1),
            "Mu- (kNm)": round(r.mu_hogging_knm, 1),
            "Vu (kN)": round(r.vu_kn, 1),
            "Steel (kg)": round(r.weight_kg_per_m * r.span_m, 1),
            "Status": r.status,
        })
    return rows


def slab_rows(gm, marks) -> List[Dict[str, Any]]:
    rows = []
    schedule = getattr(gm, "slab_schedule", None) or {}
    for sid in sorted(schedule, key=natural_key):
        r = schedule[sid]
        rows.append({
            "Slab": sid,
            "Mark": marks.slabs.get(sid, ""),
            "lx x ly (m)": f"{r.lx_m:.2f} x {r.ly_m:.2f}",
            "Type": "Two-way" if r.is_two_way else "One-way",
            "Thickness (mm)": round(r.thickness_mm),
            "Area (m²)": round(r.area_m2, 2),
            "Main steel": r.main_steel_desc,
            "Distribution": r.dist_steel_desc,
            "Top steel": r.top_steel_desc or "-",
            "Steel (kg)": round(r.weight_kg_per_m2 * r.area_m2, 1),
            "Status": r.status,
        })
    return rows


def footing_rows(footings, marks) -> List[Dict[str, Any]]:
    rows = []
    for ft in footings or []:
        rows.append({
            "Footing": ft.id,
            "Mark": marks.footings.get(ft.id, ""),
            "Column": ft.id[2:] if ft.id.startswith("F-") else "-",
            "Size (m)": f"{ft.length_m:.2f} x {ft.width_m:.2f}",
            "Depth (mm)": round(ft.thickness_mm),
            "Pressure / SBC (kN/m²)": f"{ft.bearing_pressure_kn_m2:.0f} / {ft.sbc_kn_m2:.0f}",
            "Bearing": _ok(ft.bearing_ok),
            "Punching": _ok(ft.punching_ok),
            "One-way shear": _ok(ft.one_way_shear_ok),
            "Bending": _ok(ft.bending_ok),
            "Bars": ft.rebar_desc or "-",
            "Steel (kg)": round(ft.steel_weight_kg, 1),
            "Status": ft.status,
        })
    return rows
