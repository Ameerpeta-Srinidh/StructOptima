"""
Member detailing for the production design path (IS 456:2000 limit state).

All moments, shears and axial loads passed to the ``detail_*`` functions are
FACTORED design values (kN, kNm) unless a parameter name says otherwise.
Section checks are delegated to :mod:`src.section_design`.

Each result carries an explicit ``status`` ("PASS" | "WARN" | "FAIL") and a
list of ``warnings`` so that downstream screens never have to infer success
(audit finding R5).
"""

import math
from typing import Dict, List, Optional, Sequence, Tuple

from pydantic import BaseModel

from . import section_design as sd
from .materials import Concrete

STEEL_DENSITY = 7850.0  # kg/m^3


def _kg_per_m(area_mm2: float) -> float:
    return area_mm2 / 1e6 * STEEL_DENSITY


def _worst(*statuses: str) -> str:
    order = {"PASS": 0, "WARN": 1, "FAIL": 2}
    return max(statuses, key=lambda s: order.get(s, 2)) if statuses else "PASS"


# ------------------------------------------------------------------ models --

BEYOND_CAPACITY = "beyond capacity (Pu outside the interaction diagram)"


def format_interaction_ratio(ratio, digits: int = 2) -> str:
    """Column interaction ratio for display. A ratio is infinite when the factored axial load lies outside the
    section's interaction diagram (no moment capacity at that load, IS 456 39.6): shown as text, never as a number
    (D-38; 'inf' crashed the IFC export and broke the 3D viewer JSON)."""
    if ratio is None:
        return "-"
    return f"{ratio:.{digits}f}" if math.isfinite(ratio) else BEYOND_CAPACITY


def interaction_ratio_value(ratio, digits: int = 2):
    """For tables and JSON: the rounded number when finite, otherwise the BEYOND_CAPACITY text (D-38)."""
    if ratio is None:
        return None
    return round(float(ratio), digits) if math.isfinite(ratio) else BEYOND_CAPACITY


class RebarResult(BaseModel):
    """Column detailing result."""
    main_bars_desc: str                 # e.g. "8-16#"
    links_desc: str                     # e.g. "8# @ 200 c/c"
    main_steel_area_mm2: float
    total_steel_weight_kg_per_m: float
    phi_main: int
    congestion_status: str = "PASS"
    weight_breakdown: Dict[int, float] = {}
    math_log: List[str] = []
    # Added by the 2026-10 remediation (R1/R5)
    status: str = "PASS"
    warnings: List[str] = []
    interaction_ratio: float = 0.0
    governing_combo: str = ""
    pu_design_kn: float = 0.0
    mux_design_knm: float = 0.0
    mux1_knm: float = 0.0               # uniaxial capacities at the governing Pu (lever along X / Y)
    muy1_knm: float = 0.0
    muy_design_knm: float = 0.0
    steel_percent: float = 0.0
    is_slender: bool = False
    hinge_zone_mm: float = 0.0
    hinge_spacing_mm: float = 0.0
    link_spacing_mm: float = 0.0


class StaircaseResult(BaseModel):
    waist_slab_thk_mm: float
    main_steel: str
    dist_steel: str
    concrete_vol_m3: float
    steel_weight_kg: float
    riser_mm: float
    tread_mm: float
    num_risers: int
    status: str = "PASS"
    warnings: List[str] = []
    mu_knm_per_m: float = 0.0
    effective_span_m: float = 0.0


class BeamRebarResult(BaseModel):
    top_bars_desc: str
    bottom_bars_desc: str
    stirrups_desc: str
    size_label: str
    weight_kg_per_m: float
    provided_steel_area_mm2: float      # top + bottom (congestion check)
    congestion_status: str = "PASS"
    weight_breakdown: Dict[int, float] = {}
    # Added by the 2026-10 remediation (R2/R4/R5/R13)
    status: str = "PASS"
    warnings: List[str] = []
    span_m: float = 0.0
    width_mm: float = 0.0
    depth_mm: float = 0.0
    mu_sagging_knm: float = 0.0
    mu_hogging_knm: float = 0.0
    vu_kn: float = 0.0
    ast_bottom_req_mm2: float = 0.0
    ast_top_req_mm2: float = 0.0
    ast_bottom_prov_mm2: float = 0.0
    ast_top_prov_mm2: float = 0.0
    doubly_reinforced: bool = False
    tau_v_Nmm2: float = 0.0
    tau_c_Nmm2: float = 0.0
    tau_c_max_Nmm2: float = 0.0
    span_depth_ratio: float = 0.0
    governing_combo: str = ""


class SlabRebarResult(BaseModel):
    main_steel_desc: str
    dist_steel_desc: str
    thickness_mm: float
    weight_kg_per_m2: float
    weight_breakdown: Dict[int, float] = {}
    # Added by the 2026-10 remediation (R13/R20)
    status: str = "PASS"
    warnings: List[str] = []
    area_m2: float = 0.0
    lx_m: float = 0.0
    ly_m: float = 0.0
    is_two_way: bool = True
    table26_case: int = 0
    factored_load_kn_m2: float = 0.0
    mx_pos_knm: float = 0.0
    mx_neg_knm: float = 0.0
    my_pos_knm: float = 0.0
    my_neg_knm: float = 0.0
    top_steel_desc: str = ""


# IS 456 Table 26 bending-moment coefficients for rectangular panels supported
# on four sides with provision for torsion at corners.
# Transcribed by the development team - VERIFY AGAINST THE PRINTED STANDARD.
# {case: (short_neg[], short_pos[], long_neg, long_pos)}, ly/lx points below.
TABLE26_RATIOS = [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.75, 2.0]
TABLE26 = {
    1: ([0.032, 0.037, 0.043, 0.047, 0.051, 0.053, 0.060, 0.065], [0.024, 0.028, 0.032, 0.036, 0.039, 0.041, 0.045, 0.049], 0.032, 0.024),
    2: ([0.037, 0.043, 0.048, 0.051, 0.055, 0.057, 0.064, 0.068], [0.028, 0.032, 0.036, 0.039, 0.041, 0.044, 0.048, 0.052], 0.037, 0.028),
    3: ([0.037, 0.044, 0.052, 0.057, 0.063, 0.067, 0.077, 0.085], [0.028, 0.033, 0.039, 0.044, 0.047, 0.051, 0.059, 0.065], 0.037, 0.028),
    4: ([0.047, 0.053, 0.060, 0.065, 0.071, 0.075, 0.084, 0.091], [0.035, 0.040, 0.045, 0.049, 0.053, 0.056, 0.063, 0.069], 0.047, 0.035),  # long-span negative 0.047 (was 0.045, finding T1)
    5: ([0.045, 0.049, 0.052, 0.056, 0.059, 0.060, 0.065, 0.069], [0.035, 0.037, 0.040, 0.043, 0.044, 0.045, 0.049, 0.052], 0.0, 0.035),
    6: (None, [0.035, 0.043, 0.051, 0.057, 0.063, 0.068, 0.080, 0.088], 0.045, 0.035),
    7: ([0.057, 0.064, 0.071, 0.076, 0.080, 0.084, 0.091, 0.097], [0.043, 0.048, 0.053, 0.057, 0.060, 0.064, 0.069, 0.073], 0.0, 0.043),
    8: (None, [0.043, 0.051, 0.059, 0.065, 0.071, 0.076, 0.087, 0.096], 0.057, 0.043),
    9: (None, [0.056, 0.064, 0.072, 0.079, 0.085, 0.089, 0.100, 0.107], 0.0, 0.056),
}
# (number of discontinuous short edges, number of discontinuous long edges) -> case
TABLE26_CASE = {(0, 0): 1, (1, 0): 2, (0, 1): 3, (1, 1): 4, (2, 0): 5, (0, 2): 6, (2, 1): 7, (1, 2): 8, (2, 2): 9}


def table26_coefficients(ratio: float, disc_short: int, disc_long: int) -> Tuple[int, float, float, float, float]:
    """Return (case, ax_neg, ax_pos, ay_neg, ay_pos) for ly/lx = ratio (1..2)."""
    case = TABLE26_CASE[(min(disc_short, 2), min(disc_long, 2))]
    neg, pos, ly_neg, ly_pos = TABLE26[case]
    r = min(max(ratio, 1.0), 2.0)

    def interp(vals):
        if vals is None:
            return 0.0
        for (r1, v1), (r2, v2) in zip(zip(TABLE26_RATIOS, vals), zip(TABLE26_RATIOS[1:], vals[1:])):
            if r1 <= r <= r2:
                return v1 + (v2 - v1) * (r - r1) / (r2 - r1)
        return vals[-1]
    return case, interp(neg), interp(pos), ly_neg, ly_pos


class RebarDetailer:
    """Detailing logic for structural members based on IS 456:2000."""

    @staticmethod
    def check_congestion(ag_mm2: float, ast_mm2: float, element_type: str = "column") -> str:
        """Practical congestion limit of 4 % of gross area (IS 456 permits 6 %
        for columns and 4 % per face for beams)."""
        if ag_mm2 <= 0:
            return "FAIL"
        return "FAIL" if ast_mm2 / ag_mm2 * 100.0 > 4.0 else "PASS"

    # ------------------------------------------------------------ columns --
    @staticmethod
    def detail_column(
        b_mm: float,
        d_mm: float,
        pu_kn: float,
        concrete: Concrete,
        level: int = 0,
        fy: float = 415.0,
        mux_knm: float = 0.0,
        muy_knm: float = 0.0,
        unsupported_length_m: float = 3.0,
        le_factor: float = 1.0,
        combos: Optional[Sequence[Tuple[str, float, float, float]]] = None,
        clear_cover_mm: float = 40.0,
        ductile: bool = False,
        column_id: str = "",
        min_bars: int = 8,
        min_dia: int = 16,
    ) -> RebarResult:
        """Design a rectangular column for factored axial load and biaxial moments.

        ``b_mm`` is the dimension along global X, ``d_mm`` along global Y.
        ``mux_knm`` is the moment whose lever arm is along X (sway in the X
        direction), ``muy_knm`` the moment with lever arm along Y.
        ``combos`` (name, Pu, Mx, My) overrides the single (pu, mux, muy) set.
        """
        fck = concrete.fck
        combos = list(combos) if combos else [("design", pu_kn, mux_knm, muy_knm)]
        L_mm = unsupported_length_m * 1000.0
        ag = b_mm * d_mm
        warnings: List[str] = []

        candidates = []
        for dia in (12, 16, 20, 25, 32):
            if dia < min_dia:
                continue
            for n in range(max(4, min_bars), 41, 2):
                area = n * sd.BAR_AREAS[dia]
                if area < 0.008 * ag - 1e-6:
                    continue
                sec = sd.column_section(b_mm, d_mm, n, dia, fck, fy, clear_cover_mm)
                # perimeter spacing checks (centre-to-centre <= 300 mm, clear >= max(dia, 25))
                edge = clear_cover_mm + 8 + dia / 2.0
                pairs = (n - 4) // 2
                px = int(round(pairs * b_mm / (b_mm + d_mm)))
                py = pairs - px
                sx = (b_mm - 2 * edge) / (px + 1)
                sy = (d_mm - 2 * edge) / (py + 1)
                if min(sx, sy) - dia < max(dia, 25.0) or max(sx, sy) > 300.0:
                    continue
                candidates.append((area, n, dia, sec))
        candidates.sort(key=lambda c: c[0])

        chosen = None
        best_fail = None
        for area, n, dia, sec in candidates:
            if area > 0.04 * ag + 1e-6:
                break
            curves = {"x": sd.interaction_curve(sec, "x"), "y": sd.interaction_curve(sec, "y")}
            worst = None
            for name, pu, mx, my in combos:
                chk = sd.check_column(sec, pu, mx, my, L_mm, le_factor, curves)
                if worst is None or chk.ratio > worst[1].ratio:
                    worst = (name, chk)
            if best_fail is None or worst[1].ratio < best_fail[2][1].ratio:
                best_fail = (n, dia, worst, sec)
            if worst[1].ratio <= 1.0:
                chosen = (n, dia, worst, sec)
                break

        status = "PASS"
        if chosen is None:
            status = "FAIL"
            if best_fail is None:
                # Section too small for any compliant bar arrangement
                n, dia = max(min_bars, 4), max(min_dia, 16)
                sec = sd.column_section(b_mm, d_mm, n, dia, fck, fy, clear_cover_mm)
                curves = {"x": sd.interaction_curve(sec, "x"), "y": sd.interaction_curve(sec, "y")}
                name, pu, mx, my = max(combos, key=lambda c: c[1])
                chosen = (n, dia, (name, sd.check_column(sec, pu, mx, my, L_mm, le_factor, curves)), sec)
                warnings.append("No bar arrangement satisfies spacing rules for this section size")
            else:
                chosen = best_fail
            chk = chosen[2][1]
            if math.isinf(chk.ratio):       # no moment capacity at this axial load (IS 456 39.6 curve ends)
                warnings.append(
                    f"Factored axial load {chk.pu_kn:.0f} kN is outside the interaction diagram of the section "
                    f"(Puz = {chk.puz_kN:.0f} kN) with up to 4% steel: increase column size")
            else:
                warnings.append(
                    f"Interaction ratio {chk.ratio:.2f} > 1.0 with up to 4% steel: increase column size")
        n, dia, (gname, chk), sec = chosen
        provided = sec.As
        pct = provided / ag * 100.0
        congestion = RebarDetailer.check_congestion(ag, provided, "column")
        if chk.slender_x or chk.slender_y:
            warnings.append("Slender column (le/D > 12): additional moments included (k = 1.0)")
        warnings.append("Effective length taken as {:.2f} x unsupported length - confirm per IS 456 Annex E".format(le_factor))

        # Lateral ties (IS 456 Cl 26.5.3.2(c))
        pitch = min(b_mm, d_mm, 16 * dia, 300.0)
        if level == 0:
            pitch = min(pitch, 150.0)  # project rule retained from previous versions
        pitch = math.floor(pitch / 25.0) * 25.0
        link_dia = max(dia / 4.0, 6.0)
        link_dia = 8 if link_dia <= 8 else (10 if link_dia <= 10 else 12)
        hinge_zone = hinge_s = 0.0
        links_desc = f"{link_dia}# @ {int(pitch)} c/c"
        if ductile:
            hinge_zone = max(max(b_mm, d_mm), L_mm / 6.0, 450.0)
            hinge_s = math.floor(min(min(b_mm, d_mm) / 4.0, 6 * dia, 100.0) / 5.0) * 5.0
            links_desc += f" (end zones {int(hinge_zone)} mm: @ {int(hinge_s)} c/c)"
            warnings.append("Ductile end-zone spacing provided; confining steel area (Ash) NOT checked")

        weights = {dia: _kg_per_m(provided)}
        p_link = 2 * ((b_mm - 2 * clear_cover_mm) + (d_mm - 2 * clear_cover_mm)) + 24 * link_dia
        w_links = (1000.0 / pitch) * max(p_link, 0) / 1000.0 * _kg_per_m(sd.BAR_AREAS[link_dia])
        weights[link_dia] = weights.get(link_dia, 0.0) + w_links

        logs = [
            f"Column Design (ID: {column_id or 'N/A'}, Size: {int(b_mm)}x{int(d_mm)}, M{int(fck)}, Fe{int(fy)})",
            f"1. Governing combination: {gname}",
            f"2. Pu = {chk.pu_kn:.1f} kN; design Mx = {chk.mux_kNm:.1f} kNm (lever along X), "
            f"My = {chk.muy_kNm:.1f} kNm (lever along Y) incl. e_min / slenderness",
            f"3. Uniaxial capacities at Pu (strain compatibility): Mux1 = {chk.mux1_kNm:.1f} kNm, Muy1 = {chk.muy1_kNm:.1f} kNm",
            f"4. Puz = {chk.puz_kN:.0f} kN, alpha_n = {chk.alpha_n:.2f}",
            f"5. Interaction (Mx/Mux1)^an + (My/Muy1)^an = {format_interaction_ratio(chk.ratio, 3)} ({chk.governing})",
            f"6. Reinforcement: {n}-{dia}# = {provided:.0f} mm2 ({pct:.2f}%)",
            f"7. Result: {status}",
        ]
        return RebarResult(
            main_bars_desc=f"{n}-{dia}#",
            links_desc=links_desc,
            main_steel_area_mm2=provided,
            total_steel_weight_kg_per_m=sum(weights.values()),
            phi_main=dia,
            congestion_status=congestion,
            weight_breakdown=weights,
            math_log=logs,
            status=_worst(status, "FAIL" if congestion == "FAIL" else "PASS"),
            warnings=warnings,
            interaction_ratio=chk.ratio,
            governing_combo=gname,
            pu_design_kn=chk.pu_kn,
            mux_design_knm=chk.mux_kNm,
            muy_design_knm=chk.muy_kNm,
            mux1_knm=chk.mux1_kNm,
            muy1_knm=chk.muy1_kNm,
            steel_percent=pct,
            is_slender=chk.slender_x or chk.slender_y,
            hinge_zone_mm=hinge_zone,
            hinge_spacing_mm=hinge_s,
            link_spacing_mm=pitch,
        )

    # -------------------------------------------------------------- beams --
    @staticmethod
    def detail_beam(
        b_mm: float,
        d_mm: float,
        span_m: float,
        load_kn_m: float = 0.0,
        design_moment_knm: float = 0.0,
        design_shear_kn: float = 0.0,
        fck: float = 25.0,
        mu_sagging_knm: Optional[float] = None,
        mu_hogging_knm: Optional[float] = None,
        vu_kn: Optional[float] = None,
        fy: float = 415.0,
        clear_cover_mm: float = 25.0,
        stirrup_dia: int = 8,
        ductile: bool = False,
        continuous: Optional[bool] = None,
        governing_combo: str = "",
    ) -> BeamRebarResult:
        """Design a rectangular beam of overall depth ``d_mm``.

        Preferred inputs are the factored envelope values ``mu_sagging_knm``,
        ``mu_hogging_knm`` and ``vu_kn``.  Legacy inputs: ``design_moment_knm``
        (applied to BOTH faces, conservative) or a factored ``load_kn_m``
        (wL^2/8 to both faces, wL/2 shear).
        """
        D = d_mm
        warnings: List[str] = []
        if mu_sagging_knm is None and mu_hogging_knm is None:
            if design_moment_knm > 0:
                m = design_moment_knm
                v = design_shear_kn
            else:
                m = load_kn_m * span_m ** 2 / 8.0
                v = load_kn_m * span_m / 2.0
            mu_sag, mu_hog = m, m
            vu = v if vu_kn is None else vu_kn
            warnings.append("Legacy input: single moment applied to both faces")
        else:
            mu_sag = abs(mu_sagging_knm or 0.0)
            mu_hog = abs(mu_hogging_knm or 0.0)
            vu = abs(vu_kn if vu_kn is not None else design_shear_kn)
        if continuous is None:
            continuous = mu_hog > 0.05 * max(mu_sag, 1e-6)

        width_avail = b_mm - 2 * clear_cover_mm - 2 * stirrup_dia

        def eff_depth(dia: int, layers: int) -> float:
            base = D - clear_cover_mm - stirrup_dia
            return base - dia / 2.0 if layers == 1 else base - dia - 12.5

        d_prime = clear_cover_mm + stirrup_dia + 8.0
        # Iterate once on bar size / layers
        dia_b = dia_t = 16
        lay_b = lay_t = 1
        for _ in range(3):
            d_b = eff_depth(dia_b, lay_b)
            d_t = eff_depth(dia_t, lay_t)
            f_sag = sd.design_flexure(mu_sag, b_mm, d_b, d_prime, fck, fy)
            f_hog = sd.design_flexure(mu_hog, b_mm, d_t, d_prime, fck, fy)
            ast_bot = max(f_sag.ast_req, f_hog.asc_req, sd.min_tension_steel(b_mm, d_b, fy) if mu_sag > 0 else 0.0)
            ast_top = max(f_hog.ast_req, f_sag.asc_req, sd.min_tension_steel(b_mm, d_t, fy) if mu_hog > 0 else 0.0,
                          2 * sd.BAR_AREAS[12])
            nb, dia_b_new, lay_b_new, prov_b = sd.choose_bars(ast_bot, width_avail)
            nt, dia_t_new, lay_t_new, prov_t = sd.choose_bars(ast_top, width_avail)
            if (dia_b_new, lay_b_new, dia_t_new, lay_t_new) == (dia_b, lay_b, dia_t, lay_t):
                break
            dia_b, lay_b, dia_t, lay_t = dia_b_new, lay_b_new, dia_t_new, lay_t_new

        statuses = []
        if lay_b > 2 or lay_t > 2:
            statuses.append("FAIL")
            warnings.append("Required bars do not fit in two layers: increase width")
        for face, prov in (("bottom", prov_b), ("top", prov_t)):
            if prov > 0.04 * b_mm * D:
                statuses.append("FAIL")
                warnings.append(f"{face} steel exceeds 4% of bD (IS 456 Cl 26.5.1.1(b))")
        if f_sag.doubly or f_hog.doubly:
            warnings.append("Doubly reinforced section (Mu > Mu,lim): compression steel provided")

        # Shear: use the smaller tension-steel ratio (conservative)
        d_s = min(d_b, d_t)
        pt = min(prov_b, prov_t) * 100.0 / (b_mm * d_s)
        sh = sd.design_shear(vu, b_mm, d_s, pt, fck, fy, stirrup_dia)
        statuses.append(sh.status)
        if sh.status == "FAIL":
            warnings.append(sh.note)
        stirrup_desc = f"2L-{stirrup_dia}# @ {int(sh.spacing_mm)} c/c" if sh.spacing_mm > 0 else "FAIL"
        if ductile and sh.spacing_mm > 0:
            # IS 13920 6.3.5 as amended (Amd 1): d/4, 6 x smallest longitudinal bar, 100 mm (J9; was 8 x)
            hs = math.floor(min(d_s / 4.0, 6 * min(dia_b, dia_t), 100.0, sh.spacing_mm) / 5.0) * 5.0
            stirrup_desc += f" (ends {int(2 * D)} mm: @ {int(hs)} c/c)"
            warnings.append("Ductile end-zone stirrup spacing provided; other IS 13920 beam provisions not checked")

        # Serviceability: basic span/effective-depth ratio (IS 456 Cl 23.2.1)
        ld = span_m * 1000.0 / d_s if d_s > 0 else 0.0
        basic = 26.0 if continuous else 20.0
        if ld > basic:
            statuses.append("WARN")
            warnings.append(f"span/d = {ld:.1f} > basic {basic:.0f}; modification factors not evaluated")

        congestion = "FAIL" if (lay_b > 2 or lay_t > 2 or max(prov_b, prov_t) > 0.04 * b_mm * D) else "PASS"

        weights: Dict[int, float] = {}
        weights[dia_b] = weights.get(dia_b, 0.0) + _kg_per_m(prov_b)
        weights[dia_t] = weights.get(dia_t, 0.0) + _kg_per_m(prov_t)
        perim = 2 * ((b_mm - 2 * clear_cover_mm) + (D - 2 * clear_cover_mm)) + 24 * stirrup_dia
        s_eff = sh.spacing_mm if sh.spacing_mm > 0 else 75.0
        weights[stirrup_dia] = weights.get(stirrup_dia, 0.0) + (1000.0 / s_eff) * perim / 1000.0 * _kg_per_m(sd.BAR_AREAS[stirrup_dia])

        return BeamRebarResult(
            top_bars_desc=f"{nt}-{dia_t}#" + (" (2 layers)" if lay_t == 2 else ""),
            bottom_bars_desc=f"{nb}-{dia_b}#" + (" (2 layers)" if lay_b == 2 else ""),
            stirrups_desc=stirrup_desc,
            size_label=f"{int(b_mm)}x{int(D)}",
            weight_kg_per_m=sum(weights.values()),
            provided_steel_area_mm2=prov_b + prov_t,
            congestion_status=congestion,
            weight_breakdown=weights,
            status=_worst(*statuses) if statuses else "PASS",
            warnings=warnings,
            span_m=span_m,
            width_mm=b_mm,
            depth_mm=D,
            mu_sagging_knm=mu_sag,
            mu_hogging_knm=mu_hog,
            vu_kn=vu,
            ast_bottom_req_mm2=ast_bot,
            ast_top_req_mm2=ast_top,
            ast_bottom_prov_mm2=prov_b,
            ast_top_prov_mm2=prov_t,
            doubly_reinforced=f_sag.doubly or f_hog.doubly,
            tau_v_Nmm2=sh.tau_v,
            tau_c_Nmm2=sh.tau_c,
            tau_c_max_Nmm2=sh.tau_c_max,
            span_depth_ratio=ld,
            governing_combo=governing_combo,
        )

    # ---------------------------------------------------------- staircase --
    @staticmethod
    def detail_staircase(
        floor_height_m: float,
        flight_width_m: float = 1.2,
        fy: float = 415.0,
        fck: float = 25.0,
        live_load_kn_m2: float = 3.0,
        floor_finish_kn_m2: float = 1.0,
    ) -> StaircaseResult:
        """Dog-legged staircase, one flight designed as a simply supported
        waist slab spanning the going plus two 1.2 m landings (assumption)."""
        flight_height = floor_height_m / 2.0
        num_risers = max(1, round(flight_height * 1000 / 150.0))
        riser = flight_height * 1000 / num_risers
        tread = 250.0 if riser > 160 else 300.0
        num_treads = num_risers - 1
        eff_span = num_treads * tread / 1000.0 + 1.2 + 1.2
        waist = max(math.ceil(eff_span * 1000 / 25.0 / 10.0) * 10.0, 150.0)
        slope = math.hypot(riser, tread) / tread
        warnings: List[str] = []
        status = "PASS"
        main_dia, spacing = 10, 0.0
        for _ in range(40):
            d = waist - 20.0 - 6.0
            w = 25.0 * waist / 1000.0 * slope + 25.0 * riser / 1000.0 / 2.0 + live_load_kn_m2 + floor_finish_kn_m2
            mu = 1.5 * w * eff_span ** 2 / 8.0
            if mu <= sd.mu_lim_knm(1000.0, d, fck, fy):
                ast = max(sd.ast_singly(mu, 1000.0, d, fck, fy), 0.0012 * 1000.0 * waist)
                for dia in (10, 12, 16):
                    s_try = math.floor(sd.BAR_AREAS[dia] * 1000.0 / ast / 10.0) * 10.0
                    if s_try >= 100.0:
                        main_dia, spacing = dia, min(s_try, 300.0, math.floor(3 * d / 10.0) * 10.0)
                        break
                if spacing > 0:
                    break
            waist += 10.0
        else:
            status = "FAIL"
            warnings.append("Waist slab could not be designed within 550 mm")
            ast = 0.0
        dist_ast = 0.0012 * 1000.0 * waist
        spacing_d = min(math.floor(sd.BAR_AREAS[8] * 1000.0 / dist_ast / 10.0) * 10.0, 300.0, 5 * d)
        slope_len = num_treads * tread * slope / 1000.0
        vol = slope_len * flight_width_m * waist / 1000.0 + num_risers * (riser / 1000.0 * tread / 1000.0 / 2.0) * flight_width_m
        warnings.append("Steel quantity estimated at 100 kg/m3 of stair concrete")
        return StaircaseResult(
            waist_slab_thk_mm=waist, main_steel=f"{main_dia}mm @ {int(spacing)}mm c/c", dist_steel=f"8mm @ {int(spacing_d)}mm c/c",
            concrete_vol_m3=vol, steel_weight_kg=vol * 100.0, riser_mm=riser, tread_mm=tread, num_risers=num_risers,
            status=status, warnings=warnings, mu_knm_per_m=mu, effective_span_m=eff_span,
        )

    # -------------------------------------------------------------- slabs --
    @staticmethod
    def detail_slab(
        lx_m: float,
        ly_m: float,
        slab_thk_mm: float = 125.0,
        load_kn_m2: float = 5.0,
        fck: float = 25.0,
        factored_load_kn_m2: Optional[float] = None,
        fy: float = 415.0,
        disc_short_edges: int = 2,
        disc_long_edges: int = 2,
        clear_cover_mm: float = 20.0,
    ) -> SlabRebarResult:
        """Slab panel design.

        Two-way panels (ly/lx <= 2) use IS 456 Table 26 coefficients selected
        from the number of discontinuous short/long edges (default: all four
        edges discontinuous, case 9).  One-way panels use wL^2/8 for both span
        and support moments (conservative simplification).

        ``load_kn_m2`` is a SERVICE load (factored x1.5) kept for backward
        compatibility; ``factored_load_kn_m2`` overrides it.
        """
        lx, ly = min(lx_m, ly_m), max(lx_m, ly_m)
        w = factored_load_kn_m2 if factored_load_kn_m2 is not None else 1.5 * load_kn_m2
        warnings: List[str] = []
        statuses: List[str] = []
        ratio = ly / lx
        two_way = ratio <= 2.0
        dx = slab_thk_mm - clear_cover_mm - 5.0
        dy = dx - 10.0
        case = 0
        if two_way:
            case, axn, axp, ayn, ayp = table26_coefficients(ratio, disc_short_edges, disc_long_edges)
            mxp, mxn = axp * w * lx ** 2, axn * w * lx ** 2
            myp, myn = ayp * w * lx ** 2, ayn * w * lx ** 2
            warnings.append(f"IS 456 Table 26 case {case}; corner torsion reinforcement not detailed")
        else:
            mxp = mxn = w * lx ** 2 / 8.0
            myp = myn = 0.0
            warnings.append("One-way slab: wL^2/8 used for span and support moments")
        min_ast = 0.0012 * 1000.0 * slab_thk_mm

        def bars(m, d, distribution=False):
            ast = max(sd.ast_singly(m, 1000.0, d, fck, fy), min_ast)
            smax = min(5 * d, 450.0) if distribution else min(3 * d, 300.0)
            for dia in (8, 10, 12):
                s = math.floor(sd.BAR_AREAS[dia] * 1000.0 / ast / 10.0) * 10.0
                if s >= 100:
                    s = min(s, math.floor(smax / 10.0) * 10.0)
                    return dia, s, ast
            statuses.append("FAIL")
            warnings.append(f"Moment {m:.1f} kNm/m needs 12 mm bars at < 100 mm: increase thickness")
            return 12, 100.0, ast

        for m, d in ((mxp, dx), (mxn, dx), (myp, dy), (myn, dy)):
            if m > sd.mu_lim_knm(1000.0, d, fck, fy):
                statuses.append("FAIL")
                warnings.append(f"Slab moment {m:.1f} kNm/m exceeds Mu,lim: increase thickness")
        dm, sm, _ = bars(mxp, dx)
        if two_way:
            dd, sdist, _ = bars(myp, dy)
        else:
            dd, sdist, _ = bars(0.0, dy, distribution=True)
        top_parts = []
        if mxn > 0:
            dt, st, _ = bars(mxn, dx)
            top_parts.append(f"short span {dt}# @ {int(st)}")
        if myn > 0:
            dt2, st2, _ = bars(myn, dy)
            top_parts.append(f"long span {dt2}# @ {int(st2)}")
        basic = 20.0 if case in (9, 0) and not (mxn > 0) else 26.0
        if lx * 1000.0 / dx > basic:
            statuses.append("WARN")
            warnings.append(f"lx/d = {lx * 1000 / dx:.1f} > basic {basic:.0f}; modification factor not evaluated")

        weights: Dict[int, float] = {}
        weights[dm] = weights.get(dm, 0.0) + (1000.0 / sm) * _kg_per_m(sd.BAR_AREAS[dm])
        weights[dd] = weights.get(dd, 0.0) + (1000.0 / sdist) * _kg_per_m(sd.BAR_AREAS[dd])
        # top steel: assumed to extend 0.3 lx from each continuous edge
        if mxn > 0:
            weights[dt] = weights.get(dt, 0.0) + (1000.0 / st) * _kg_per_m(sd.BAR_AREAS[dt]) * min(1.0, 0.6 * (2 - disc_long_edges) / 2)
        if myn > 0:
            weights[dt2] = weights.get(dt2, 0.0) + (1000.0 / st2) * _kg_per_m(sd.BAR_AREAS[dt2]) * min(1.0, 0.6 * (2 - disc_short_edges) / 2)

        return SlabRebarResult(
            main_steel_desc=f"{dm}# @ {int(sm)} c/c",
            dist_steel_desc=f"{dd}# @ {int(sdist)} c/c",
            thickness_mm=slab_thk_mm,
            weight_kg_per_m2=sum(weights.values()),
            weight_breakdown=weights,
            status=_worst(*statuses) if statuses else "PASS",
            warnings=warnings,
            area_m2=lx_m * ly_m,
            lx_m=lx,
            ly_m=ly,
            is_two_way=two_way,
            table26_case=case,
            factored_load_kn_m2=w,
            mx_pos_knm=mxp,
            mx_neg_knm=mxn,
            my_pos_knm=myp,
            my_neg_knm=myn,
            top_steel_desc="; ".join(top_parts) if top_parts else "nominal",
        )
