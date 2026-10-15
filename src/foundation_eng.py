"""
Isolated square pad footing design (IS 456:2000 Cl 34 with Cl 31.6 punching).

Load convention: ``axial_load_kn`` is the SERVICE (unfactored) column load at
the footing.  Factored design load = ``load_factor`` x service (1.5 default)
unless ``factored_load_kn`` is given.  Area sizing adds 10 % for footing
self-weight and backfill (project assumption, unchanged).
"""

import math
from typing import List, Optional

from pydantic import BaseModel

from . import section_design as sd
from .logging_config import get_logger
from .materials import Concrete

logger = get_logger(__name__)


class Footing(BaseModel):
    id: str = ""
    length_m: float
    width_m: float
    thickness_mm: float
    area_m2: float
    concrete_vol_m3: float
    excavation_vol_m3: float
    status: str = "PASS"
    one_way_shear_ok: bool = True
    bending_ok: bool = True
    # Added by the 2026-10 remediation (R16)
    punching_ok: bool = True
    bearing_ok: bool = True
    service_load_kn: float = 0.0
    factored_load_kn: float = 0.0
    bearing_pressure_kn_m2: float = 0.0
    sbc_kn_m2: float = 0.0
    effective_depth_mm: float = 0.0
    ast_per_m_mm2: float = 0.0
    rebar_desc: str = ""
    steel_weight_kg: float = 0.0
    warnings: List[str] = []


def calculate_punching_shear_capacity(thickness_mm: float, fck: float, beta_c: float = 1.0) -> float:
    """IS 456 Cl 31.6.3.1: ks * tau_c with tau_c = 0.25 sqrt(fck) and
    ks = 0.5 + beta_c <= 1 (beta_c = short/long column side)."""
    ks = min(1.0, 0.5 + beta_c)
    return ks * 0.25 * math.sqrt(fck)


def design_footing(
    axial_load_kn: float,
    sbc_kn_m2: float = 200.0,
    column_width_mm: float = 300.0,
    column_depth_mm: float = 300.0,
    concrete: Optional[Concrete] = None,
    fy: float = 415.0,
    factored_load_kn: Optional[float] = None,
    load_factor: float = 1.5,
    base_moment_knm: float = 0.0,
    clear_cover_mm: float = 50.0,
    bar_dia_mm: int = 12,
) -> Footing:
    fck = 25.0 if concrete is None else concrete.fck
    warnings: List[str] = []

    if sbc_kn_m2 <= 0:
        logger.warning("SBC <= 0 provided, using default 200 kN/m2")
        warnings.append("Invalid SBC replaced by 200 kN/m2")
        sbc_kn_m2 = 200.0
    if axial_load_kn < 0:
        logger.warning("Negative (tension) column load: footing designed for |P| - uplift not checked")
        warnings.append("Net tension at column base: uplift resistance NOT checked")
        axial_load_kn = abs(axial_load_kn)
    if axial_load_kn == 0:
        return Footing(length_m=1.0, width_m=1.0, thickness_mm=300.0, area_m2=1.0, concrete_vol_m3=0.3,
                       excavation_vol_m3=1.5, sbc_kn_m2=sbc_kn_m2, warnings=["Zero load: nominal footing"])

    pu = factored_load_kn if factored_load_kn is not None else load_factor * axial_load_kn

    # 1. Plan size from bearing (service load + 10 % self weight)
    side = math.sqrt(axial_load_kn * 1.1 / sbc_kn_m2)
    side = max(side, 1.5 if axial_load_kn <= 400 else 2.0)    # project minimums (retained)
    status = "PASS"
    if side > 10.0:
        warnings.append(f"Required side {side:.1f} m exceeds 10 m: isolated footing not feasible - consider raft/piles")
        status = "FAIL"
    side = math.ceil(side / 0.05) * 0.05
    area = side * side
    pressure = axial_load_kn * 1.1 / area
    bearing_ok = pressure <= sbc_kn_m2 + 1e-6
    if base_moment_knm:
        e = abs(base_moment_knm) / axial_load_kn
        q_max = axial_load_kn * 1.1 / area * (1 + 6 * e / side)
        if e > side / 6.0:
            warnings.append(f"Base eccentricity {e:.2f} m > B/6: partial uplift - footing sizing ignores moment")
            status = "FAIL" if status == "FAIL" else "WARN"
        elif q_max > sbc_kn_m2:
            warnings.append(f"Edge pressure {q_max:.0f} kN/m2 > SBC with base moment (sizing used axial load only)")
            status = "FAIL" if status == "FAIL" else "WARN"

    # 2. Thickness from punching, one-way shear and flexure
    c_min = min(column_width_mm, column_depth_mm)
    beta = c_min / max(column_width_mm, column_depth_mm)
    tau_p = calculate_punching_shear_capacity(0, fck, beta)
    thickness = 300.0 if axial_load_kn <= 400 else 350.0
    side_mm = side * 1000.0
    qu = pu * 1000.0 / (side_mm * side_mm)            # N/mm^2 net factored pressure
    cant = (side_mm - c_min) / 2.0                    # governing cantilever (smaller column side)
    punching_ok = one_way_ok = bending_ok = False
    ast = 0.0
    d = thickness - clear_cover_mm - bar_dia_mm
    while thickness <= 2000.0:
        d = thickness - clear_cover_mm - bar_dia_mm   # mean of the two layers
        # punching (critical perimeter at d/2 from column faces)
        a1, a2 = column_width_mm + d, column_depth_mm + d
        v_p = pu * 1000.0 - qu * min(a1 * a2, side_mm * side_mm)
        punching_ok = v_p / (2 * (a1 + a2) * d) <= tau_p
        # flexure at the column face, per metre width
        mu = qu * cant ** 2 / 2.0 * 1000.0 / 1e6     # kNm per metre
        bending_ok = mu <= sd.mu_lim_knm(1000.0, d, fck, fy)
        ast = max(sd.ast_singly(mu, 1000.0, d, fck, fy), 0.0012 * 1000.0 * thickness)
        # one-way shear at d from the column face with tau_c from provided steel
        proj = cant - d
        if proj > 0:
            tv = qu * proj * 1000.0 / (1000.0 * d)
            one_way_ok = tv <= sd.tau_c(ast * 100.0 / (1000.0 * d), fck)
        else:
            one_way_ok = True
        if punching_ok and bending_ok and one_way_ok:
            break
        thickness += 50.0
    if not (punching_ok and bending_ok and one_way_ok):
        status = "FAIL"
        warnings.append("Footing thickness exceeded 2000 mm without satisfying shear/flexure")

    spacing = math.floor(sd.BAR_AREAS[bar_dia_mm] * 1000.0 / ast / 10.0) * 10.0
    dia = bar_dia_mm
    if spacing < 100:
        dia = 16
        spacing = math.floor(sd.BAR_AREAS[16] * 1000.0 / ast / 10.0) * 10.0
    spacing = min(spacing, 300.0, math.floor(3 * d / 10.0) * 10.0)
    if spacing < 75.0:
        status = "FAIL"
        warnings.append(f"Bottom steel {ast:.0f} mm2/m needs bars closer than 75 mm: footing not feasible as designed")
        spacing = 75.0
    n_bars = math.floor((side_mm - 2 * clear_cover_mm) / spacing) + 1
    bar_len = (side_mm - 2 * clear_cover_mm) / 1000.0
    steel_kg = 2 * n_bars * bar_len * sd.BAR_AREAS[dia] / 1e6 * 7850.0

    conc_vol = area * thickness / 1000.0
    return Footing(
        length_m=side, width_m=side, thickness_mm=thickness, area_m2=area, concrete_vol_m3=conc_vol,
        excavation_vol_m3=area * 1.5, status=status if bearing_ok else "FAIL",
        one_way_shear_ok=one_way_ok, bending_ok=bending_ok, punching_ok=punching_ok, bearing_ok=bearing_ok,
        service_load_kn=axial_load_kn, factored_load_kn=pu, bearing_pressure_kn_m2=pressure, sbc_kn_m2=sbc_kn_m2,
        effective_depth_mm=d, ast_per_m_mm2=ast, rebar_desc=f"{dia}# @ {int(spacing)} c/c both ways (bottom)",
        steel_weight_kg=steel_kg, warnings=warnings,
    )


def check_footing_overlaps(columns, footings) -> List[str]:
    """Warn where adjacent square footings would overlap (combined footing needed)."""
    msgs = []
    for i in range(len(columns)):
        for j in range(i + 1, len(columns)):
            ci, cj, fi, fj = columns[i], columns[j], footings[i], footings[j]
            gap_x = abs(ci.x - cj.x) - (fi.length_m + fj.length_m) / 2.0
            gap_y = abs(ci.y - cj.y) - (fi.width_m + fj.width_m) / 2.0
            if gap_x < 0 and gap_y < 0:
                msgs.append(f"Footings of {ci.id} and {cj.id} overlap - consider a combined footing")
    return msgs
