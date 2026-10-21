"""
Rules every StructOptima design must satisfy, whatever the inputs (test helper, not a test module).

``design_violations(res, inputs)`` returns a list of "RULE-ID: what is wrong" strings; an empty list means the design
passed every rule. Each rule is either a code requirement the pipeline claims to apply, an equilibrium / consistency
relation between results, or a reporting rule (a failed check must reach the status list). The rules do not judge
whether a building is well designed - a FAIL design can satisfy every rule - they catch results that are wrong,
inconsistent or hidden.

Rule ids:
  G  global (status, text, finite numbers)       S  seismic (IS 1893)
  C  columns                                      B  beams
  L  slabs                                        F  footings
  D  durability, fire, drift reporting            Q  quantities
"""
import math
import re
from typing import Any, List

ORDER = {"PASS": 0, "WARN": 1, "FAIL": 2}
BAD_TEXT = re.compile(r"\b(nan|NaN|None|inf|Traceback|Exception)\b")
ZONE_Z = {"II": 0.10, "III": 0.16, "IV": 0.24, "V": 0.36}
RHO = {"II": 0.007, "III": 0.011, "IV": 0.016, "V": 0.024}
SPEC = {"I": (0.40, 1.00, 0.25), "II": (0.55, 1.36, 0.34), "III": (0.67, 1.67, 0.42)}
TOL = 1e-6


def _finite(prefix: str, obj: Any, out: List[str], depth: int = 0) -> None:
    """Every number reachable in a result object is finite."""
    if depth > 4:
        return
    if isinstance(obj, bool) or obj is None:
        return
    if isinstance(obj, (int, float)):
        if not math.isfinite(obj):
            out.append(f"G4: {prefix} = {obj}")
        return
    if hasattr(obj, "model_dump"):
        obj = obj.model_dump()
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("math_log",):
                continue
            _finite(f"{prefix}.{k}", v, out, depth + 1)
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj[:200]):
            _finite(f"{prefix}[{i}]", v, out, depth + 1)


def _spacings(desc: str) -> List[float]:
    return [float(x) for x in re.findall(r"@\s*(\d+(?:\.\d+)?)", desc or "")]


def design_violations(res, inputs) -> List[str]:
    v: List[str] = []
    gm = res.gm
    rows = res.failures

    # ---- G: status and text ----------------------------------------------------------------------------------
    if res.status not in ORDER:
        v.append(f"G1: status {res.status!r}")
    worst = max([ORDER.get(r["Status"], 9) for r in rows] + [0])
    if ORDER.get(res.status) != worst:
        v.append(f"G2: status {res.status} but the worst listed issue is "
                 f"{[k for k, o in ORDER.items() if o == worst]}")
    for r in rows:
        if set(r) != {"Member", "Type", "Status", "Issue"} or not all(str(r[k]).strip() for k in r):
            v.append(f"G3: malformed issue row {r}")
        elif BAD_TEXT.search(str(r["Issue"])) or BAD_TEXT.search(str(r["Member"])):
            v.append(f"G3: bad text in issue {r['Type']}: {r['Issue'][:120]}")
    for m in res.messages:
        if BAD_TEXT.search(m):
            v.append(f"G3: bad text in message: {m[:120]}")
    if not (math.isfinite(res.building_weight) and res.building_weight > 0):
        v.append(f"G4: building weight {res.building_weight}")
    for c in gm.columns:
        _finite(f"column {c.id}", c, v)
    for name, sched in (("column", gm.rebar_schedule), ("beam", gm.beam_schedule), ("slab", gm.slab_schedule)):
        for k, r in sched.items():
            if name == "column" and not math.isfinite(getattr(r, "interaction_ratio", 0.0)):
                # D-38: an infinite ratio means Pu outside the interaction diagram - allowed only as a FAIL that says so
                if r.interaction_ratio != math.inf or r.status != "FAIL" or \
                        not any("outside the interaction diagram" in w for w in r.warnings):
                    v.append(f"G4: column schedule {k}.interaction_ratio = {r.interaction_ratio} ({r.status})")
                r = r.model_copy(update={"interaction_ratio": 0.0})
            _finite(f"{name} schedule {k}", r, v)
    for f in res.footings:
        _finite(f"footing {f.id}", f, v)

    # ---- S: seismic ------------------------------------------------------------------------------------------
    sr = res.seismic_result
    zone, soil = inputs.seismic_zone, inputs.soil_type
    if sr is not None:
        p = sr.parameters
        h = sum(c.z_top - c.z_bottom for c in gm.columns if (c.x, c.y) == (gm.columns[0].x, gm.columns[0].y))
        d = max(gm.width_m, gm.length_m)
        ta = 0.075 * h ** 0.75
        if d > 0:
            ta = min(ta, 0.09 * h / math.sqrt(d))
        if abs(p.fundamental_period - ta) > 1e-3 * ta:
            v.append(f"S1: Ta {p.fundamental_period:.4f} s, IS 1893 7.6.2 gives {ta:.4f} s (h {h:.2f}, d {d:.2f})")
        t1, n, floor = SPEC[soil]
        sa = 2.5 if ta <= t1 else (n / ta if ta <= 4.0 else floor)
        r_fac = 5.0 if inputs.structural_system.upper() in ("SMRF", "SMF") else 3.0
        imp = p.importance_factor
        ah = ZONE_Z[zone] / 2 * imp / r_fac * sa
        vb = max(ah, RHO[zone]) * res.building_weight
        if abs(sr.base_shear_kn - vb) > 1e-6 * max(vb, 1.0):
            v.append(f"S2: VB {sr.base_shear_kn:.3f} kN, max(Ah, rho) W gives {vb:.3f} kN")
        if abs(sum(sr.storey_forces_kn) - sr.base_shear_kn) > 1e-6 * max(sr.base_shear_kn, 1.0):
            v.append("S3: storey forces do not sum to VB")
        if any(f < -TOL for f in sr.storey_forces_kn):
            v.append("S3: negative storey force")
        dyn = sr.dynamic if isinstance(getattr(sr, "dynamic", None), dict) else {}
        for dname in ("X", "Y"):
            dd = dyn.get(dname)
            if not dd:
                continue
            if dd["VB design (kN)"] < round(sr.base_shear_kn, 1) - 0.06:
                v.append(f"S4: dynamic design VB {dd['VB design (kN)']} < static {sr.base_shear_kn:.1f} ({dname})")
            if dd["Scale factor"] < 1.0 - 1e-3:
                v.append(f"S4: scale factor {dd['Scale factor']} < 1 ({dname})")
            if dd["Mass in those modes %"] < 90.0 - 1e-6:
                v.append(f"S4: modes reported for 90 % mass carry {dd['Mass in those modes %']} % ({dname})")
        if zone != "II" and inputs.structural_system.upper() == "OMRF" and \
                not any(r["Type"] == "Structural system" and r["Status"] == "FAIL" for r in rows):
            v.append(f"S5: OMRF in Zone {zone} not reported as FAIL (IS 1893 Table 9 Note 1)")

    # ---- C: columns --------------------------------------------------------------------------------------------
    ductile_zone = zone in ("III", "IV", "V") or inputs.structural_system.upper() in ("SMRF", "SMF")
    stacks = {}
    for c in gm.columns:
        stacks.setdefault((round(c.x, 3), round(c.y, 3)), []).append(c)
        if c.width_nb <= 0 or c.depth_nb <= 0:
            v.append(f"C1: {c.id} size {c.width_nb} x {c.depth_nb}")
        if ductile_zone and min(c.width_nb, c.depth_nb) < 300 - TOL:
            v.append(f"C2: {c.id} {c.width_nb:.0f} x {c.depth_nb:.0f} below 300 mm (IS 13920 7.1.1)")
        if c.wall_dir is not None:
            thin = c.depth_nb if c.wall_dir == "x" else c.width_nb
            if ductile_zone or abs(thin - 230) > TOL:
                v.append(f"C3: {c.id} wall column {c.width_nb:.0f} x {c.depth_nb:.0f} ({c.wall_dir}) in Zone {zone} "
                         f"{inputs.structural_system}")
        if c.id not in gm.rebar_schedule:
            v.append(f"C4: {c.id} not designed")
            continue
        r = gm.rebar_schedule[c.id]
        if r.status not in ORDER:
            v.append(f"C4: {c.id} status {r.status!r}")
        if r.status == "PASS":
            if r.interaction_ratio > 1.0 + 1e-6:
                v.append(f"C5: {c.id} PASS with interaction ratio {r.interaction_ratio:.3f}")
            if not 0.8 - 1e-3 <= r.steel_percent <= 4.0 + 1e-3:
                v.append(f"C5: {c.id} PASS with {r.steel_percent:.2f} % steel (IS 456 26.5.3.1)")
            pitch = r.link_spacing_mm
            if pitch and pitch > min(c.width_nb, c.depth_nb, 16 * r.phi_main, 300) + TOL:
                v.append(f"C6: {c.id} tie pitch {pitch} > min(b, D, 16 phi, 300) (IS 456 26.5.3.2)")
    for key, st in stacks.items():
        sizes = {(c.width_nb, c.depth_nb) for c in st}
        if len(sizes) > 1:
            v.append(f"C7: stack at {key} changes size {sorted(sizes)}")
        if len({c.wall_dir for c in st}) > 1:
            v.append(f"C7: stack at {key} mixes wall orientations")
    failing_cols = {c.id for c in gm.columns if gm.rebar_schedule.get(c.id) and gm.rebar_schedule[c.id].status == "FAIL"}
    listed = " ".join(r["Member"] for r in rows if r["Type"] == "Column")
    for cid in failing_cols:
        if cid not in listed:
            v.append(f"C8: failing column {cid} not in the issue list")

    # ---- B: beams ------------------------------------------------------------------------------------------------
    for b in res.beams:
        if b.end_point is None:
            continue
        r = gm.beam_schedule.get(b.id)
        if r is None:
            v.append(f"B1: {b.id} not designed")
            continue
        if r.status == "PASS":
            if r.ast_top_prov_mm2 < r.ast_top_req_mm2 * (1 - 1e-6) - 1e-6:
                v.append(f"B2: {b.id} top steel {r.ast_top_prov_mm2:.0f} < required {r.ast_top_req_mm2:.0f}")
            if r.ast_bottom_prov_mm2 < r.ast_bottom_req_mm2 * (1 - 1e-6) - 1e-6:
                v.append(f"B2: {b.id} bottom steel {r.ast_bottom_prov_mm2:.0f} < required {r.ast_bottom_req_mm2:.0f}")
            if r.tau_c_max_Nmm2 and r.tau_v_Nmm2 > r.tau_c_max_Nmm2 + 1e-9:
                v.append(f"B3: {b.id} PASS with tau_v {r.tau_v_Nmm2:.2f} > tau_c,max (IS 456 40.2.3)")
            sp = _spacings(r.stirrups_desc)
            if sp and max(sp) > 300 + TOL:
                v.append(f"B4: {b.id} stirrups {r.stirrups_desc} above 300 mm (IS 456 26.5.1.5)")
            for face, a in (("top", r.ast_top_prov_mm2), ("bottom", r.ast_bottom_prov_mm2)):
                if a > 0.04 * r.width_mm * r.depth_mm + 1:
                    v.append(f"B5: {b.id} {face} steel above 4 % bD (IS 456 26.5.1.1)")
        if r.status == "FAIL" and not any(x["Type"] == "Beam" and b.id in x["Member"] for x in rows):
            v.append(f"B6: failing beam {b.id} not in the issue list")
    base = {(round(c.x, 3), round(c.y, 3)): c for c in gm.columns if c.level == 0}
    wide_listed = {x["Member"] for x in rows if x["Type"] == "Beam wider than column"}
    for b in res.beams:
        if b.end_point is None:
            continue
        horiz = abs(b.end_point.y - b.start_point.y) < 1e-6
        for p_ in (b.start_point, b.end_point):
            c = base.get((round(p_.x, 3), round(p_.y, 3)))
            if c is None:
                continue
            across = c.depth_nb if horiz else c.width_nb
            if b.properties.width_mm > across + 1 and b.id not in wide_listed:
                v.append(f"B7: {b.id} ({b.properties.width_mm:.0f}) wider than {c.id} ({across:.0f}) and not reported")
                break

    # ---- L: slabs ------------------------------------------------------------------------------------------------
    for k, r in gm.slab_schedule.items():
        if r.thickness_mm < 125 - TOL:
            v.append(f"L1: slab {k} {r.thickness_mm} mm < 125")
        if r.status == "PASS":
            for s in _spacings(r.main_steel_desc) + _spacings(r.dist_steel_desc):
                if s > 450 + TOL:
                    v.append(f"L2: slab {k} bar spacing {s} mm")

    # ---- F: footings ---------------------------------------------------------------------------------------------
    by_id = {f.id: f for f in res.footings}
    for c in gm.columns:
        if c.level != 0:
            continue
        f = by_id.get(f"F-{c.id}")
        if f is None:
            v.append(f"F1: no footing under {c.id}")
            continue
        if abs(f.service_load_kn - (abs(c.load_kn) + c.plinth_load_kn)) > 1e-6 * max(abs(c.load_kn), 1.0) + 1e-6:
            v.append(f"F2: footing {f.id} service load {f.service_load_kn:.2f} != column {c.load_kn:.2f} + plinth "
                     f"{c.plinth_load_kn:.2f}")
        if f.status == "PASS" and f.bearing_pressure_kn_m2 > inputs.sbc_kn_m2 * (1 + 1e-6):
            v.append(f"F3: footing {f.id} PASS with {f.bearing_pressure_kn_m2:.1f} kN/m2 > SBC")
        if f.thickness_mm < 300 - TOL or f.length_m <= 0:
            v.append(f"F4: footing {f.id} {f.length_m} m x {f.thickness_mm} mm")

    # ---- D: durability, fire, drift reporting ----------------------------------------------------------------------
    from src.durability import requirements
    dreq = requirements(inputs.exposure, inputs.nbc_construction_type, float(inputs.conc_grade[1:]))
    for name in ("beam_cover_mm", "slab_cover_mm", "column_cover_mm", "footing_cover_mm"):
        if abs(getattr(gm, name) - getattr(dreq, name)) > TOL:
            v.append(f"D1: {name} {getattr(gm, name)} != IS 456 requirement {getattr(dreq, name)}")
    for chk in res.stab_checks or []:
        if not chk.is_fire_safe and not any(r["Type"] == "Fire resistance" and chk.member_id in r["Member"] or
                                             r["Type"] == "Fire resistance" and "+" in r["Member"] for r in rows):
            v.append(f"D2: fire failure of {chk.member_id} not reported")
        if not chk.is_stable and not any(r["Type"] == "Slenderness" and r["Member"] == chk.member_id for r in rows):
            v.append(f"D2: slenderness failure of {chk.member_id} not reported")
    drift_fail = any(d.get("Status") == "FAIL" for d in res.drift_results)
    if drift_fail != any(r["Type"] == "Storey drift" and r["Status"] == "FAIL" for r in rows):
        v.append("D3: storey drift FAIL rows and status list disagree")

    # ---- Q: quantities -------------------------------------------------------------------------------------------
    bom = res.bom
    if bom is not None:
        if not (bom.total_concrete_vol_m3 > 0 and math.isfinite(bom.total_concrete_vol_m3)):
            v.append(f"Q1: concrete {bom.total_concrete_vol_m3}")
        if not (bom.total_steel_weight_kg > 0 and math.isfinite(bom.total_steel_weight_kg)):
            v.append(f"Q1: steel {bom.total_steel_weight_kg}")
    return v
