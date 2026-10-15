"""
Member marks for drawings and schedules (decision D-13).

Identical members share one mark:
  * columns: whole stacks with the same size, bars and ties at every level -> C1, C2 ...
  * beams:   plan beams with the same size, bottom, top bars and stirrups   -> B1, B2 ...
  * footings: same plan size, depth and bottom steel                        -> F1, F2 ...
  * slabs:   same thickness and bottom/top steel                            -> S1, S2 ...
Marks are numbered in plan order (by x, then y) so they are stable for a
given design.  A member whose status is not PASS is still grouped by its
detailing; its status is carried in the mark information.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

_ORDER = {"PASS": 0, "WARN": 1, "FAIL": 2}


def _worst(statuses) -> str:
    return max(statuses, key=lambda s: _ORDER.get(s, 2)) if statuses else "PASS"


@dataclass
class MarkInfo:
    mark: str
    members: List[str] = field(default_factory=list)   # column stack ids / beam ids / footing ids / slab ids
    rows: List[dict] = field(default_factory=list)      # schedule rows (per level for columns)
    status: str = "PASS"

    @property
    def count(self) -> int:
        return len(self.members)


@dataclass
class Marks:
    columns: Dict[str, str] = field(default_factory=dict)        # column segment id -> mark
    column_info: Dict[str, MarkInfo] = field(default_factory=dict)
    beams: Dict[str, str] = field(default_factory=dict)          # plan beam id -> mark
    beam_info: Dict[str, MarkInfo] = field(default_factory=dict)
    footings: Dict[str, str] = field(default_factory=dict)       # footing id -> mark
    footing_info: Dict[str, MarkInfo] = field(default_factory=dict)
    slabs: Dict[str, str] = field(default_factory=dict)          # slab id -> mark
    slab_info: Dict[str, MarkInfo] = field(default_factory=dict)


def compute_marks(gm, beams, footings) -> Marks:
    m = Marks()

    # -- columns: group stacks ------------------------------------------
    stacks: Dict[Tuple[float, float], list] = {}
    for c in gm.columns:
        stacks.setdefault((round(c.x, 3), round(c.y, 3)), []).append(c)
    sig_to_mark: Dict[tuple, str] = {}
    for key in sorted(stacks):
        segs = sorted(stacks[key], key=lambda c: c.level)
        sig = []
        rows = []
        for c in segs:
            r = gm.rebar_schedule.get(c.id)
            bars = r.main_bars_desc if r else "-"
            links = r.links_desc if r else "-"
            sig.append((c.level, round(c.width_nb), round(c.depth_nb), bars, links))
            rows.append({"level": c.level, "size": f"{c.width_nb:.0f}x{c.depth_nb:.0f}", "bars": bars,
                         "links": links, "ratio": (r.interaction_ratio if r else 0.0),
                         "status": (r.status if r else "NOT DESIGNED")})
        sig = tuple(sig)
        if sig not in sig_to_mark:
            mk = f"C{len(sig_to_mark) + 1}"
            sig_to_mark[sig] = mk
            m.column_info[mk] = MarkInfo(mk, rows=rows)
        mk = sig_to_mark[sig]
        info = m.column_info[mk]
        info.members.append(segs[0].id.rsplit("_L", 1)[0])
        for i, row in enumerate(rows):            # keep the worst status/ratio per level
            if _ORDER.get(row["status"], 2) > _ORDER.get(info.rows[i]["status"], 2):
                info.rows[i]["status"] = row["status"]
            info.rows[i]["ratio"] = max(info.rows[i]["ratio"], row["ratio"])
        info.status = _worst([r["status"] for r in info.rows])
        for c in segs:
            m.columns[c.id] = mk

    # -- beams ------------------------------------------------------------
    sig_to_mark = {}
    for b in sorted(beams, key=lambda b: (round(min(b.start_point.x, b.end_point.x), 3),
                                          round(min(b.start_point.y, b.end_point.y), 3), b.id)):
        r = gm.get_beam_result(b.id)
        if r is None:
            continue
        sig = (round(r.width_mm), round(r.depth_mm), r.bottom_bars_desc, r.top_bars_desc, r.stirrups_desc)
        if sig not in sig_to_mark:
            mk = f"B{len(sig_to_mark) + 1}"
            sig_to_mark[sig] = mk
            m.beam_info[mk] = MarkInfo(mk, rows=[{"size": f"{r.width_mm:.0f}x{r.depth_mm:.0f}",
                                                  "bottom": r.bottom_bars_desc, "top": r.top_bars_desc,
                                                  "stirrups": r.stirrups_desc, "spans": []}])
        mk = sig_to_mark[sig]
        info = m.beam_info[mk]
        info.members.append(b.id)
        info.rows[0]["spans"].append(r.span_m)
        info.status = _worst([info.status, r.status])
        m.beams[b.id] = mk

    # -- footings ---------------------------------------------------------
    sig_to_mark = {}
    level0 = {c.id: c for c in gm.columns if c.level == 0}
    for ft in sorted(footings, key=lambda f: (round(level0[f.id[2:]].x, 3), round(level0[f.id[2:]].y, 3))
                     if f.id[2:] in level0 else (0, 0)):
        sig = (round(ft.length_m, 3), round(ft.width_m, 3), round(ft.thickness_mm), ft.rebar_desc)
        if sig not in sig_to_mark:
            mk = f"F{len(sig_to_mark) + 1}"
            sig_to_mark[sig] = mk
            m.footing_info[mk] = MarkInfo(mk, rows=[{"size": f"{ft.length_m * 1000:.0f}x{ft.width_m * 1000:.0f}",
                                                     "depth": f"{ft.thickness_mm:.0f}", "steel": ft.rebar_desc}])
        mk = sig_to_mark[sig]
        info = m.footing_info[mk]
        info.members.append(ft.id)
        info.status = _worst([info.status, ft.status])
        m.footings[ft.id] = mk

    # -- slabs ------------------------------------------------------------
    sig_to_mark = {}
    for sid, s in gm.slab_schedule.items():
        sig = (round(s.thickness_mm), s.main_steel_desc, s.dist_steel_desc, s.top_steel_desc)
        if sig not in sig_to_mark:
            mk = f"S{len(sig_to_mark) + 1}"
            sig_to_mark[sig] = mk
            m.slab_info[mk] = MarkInfo(mk, rows=[{"thk": f"{s.thickness_mm:.0f}", "main": s.main_steel_desc,
                                                  "dist": s.dist_steel_desc, "top": s.top_steel_desc}])
        mk = sig_to_mark[sig]
        info = m.slab_info[mk]
        info.members.append(sid)
        info.status = _worst([info.status, s.status])
        m.slabs[sid] = mk
    return m
