"""
Section-level reinforced concrete design routines (IS 456:2000 limit state).

This module is the single production implementation of section checks used by
``rebar_detailer`` (beams, columns, slabs, footings) and by the seismic /
optimizer modules.  It deliberately has no dependency on the building model.

Units: N, mm, N/mm^2 internally; public helpers state their units explicitly.

VERIFICATION NOTE
-----------------
Tabulated values (tau_c, tau_c_max, the Fe415/Fe500 design stress-strain points)
were transcribed by the development team and MUST be checked against the
printed standard / SP:16 before reliance.  See
docs/engineering/standards-register.md and docs/verification/verification-matrix.md.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

ES = 2.0e5          # N/mm^2, modulus of elasticity of steel
EPS_CU = 0.0035     # limiting concrete compressive strain in flexure
EPS_C0 = 0.002      # strain at peak of parabola / uniform compression

# IS 456 Table 19 (design shear strength of concrete, tau_c N/mm^2) by fck.
TAU_C_TABLES: Dict[int, List[Tuple[float, float]]] = {
    20: [(0.15, 0.28), (0.25, 0.36), (0.50, 0.48), (0.75, 0.56), (1.00, 0.62), (1.25, 0.67),
         (1.50, 0.72), (1.75, 0.75), (2.00, 0.79), (2.25, 0.81), (2.50, 0.82), (2.75, 0.82), (3.00, 0.82)],
    25: [(0.15, 0.29), (0.25, 0.36), (0.50, 0.49), (0.75, 0.57), (1.00, 0.64), (1.25, 0.70),
         (1.50, 0.74), (1.75, 0.78), (2.00, 0.82), (2.25, 0.85), (2.50, 0.88), (2.75, 0.90), (3.00, 0.92)],
    30: [(0.15, 0.29), (0.25, 0.37), (0.50, 0.50), (0.75, 0.59), (1.00, 0.66), (1.25, 0.71),
         (1.50, 0.76), (1.75, 0.80), (2.00, 0.84), (2.25, 0.88), (2.50, 0.91), (2.75, 0.94), (3.00, 0.96)],
    35: [(0.15, 0.29), (0.25, 0.37), (0.50, 0.50), (0.75, 0.59), (1.00, 0.67), (1.25, 0.73),
         (1.50, 0.78), (1.75, 0.82), (2.00, 0.86), (2.25, 0.90), (2.50, 0.93), (2.75, 0.96), (3.00, 0.99)],
    40: [(0.15, 0.30), (0.25, 0.38), (0.50, 0.51), (0.75, 0.60), (1.00, 0.68), (1.25, 0.74),
         (1.50, 0.79), (1.75, 0.84), (2.00, 0.88), (2.25, 0.92), (2.50, 0.95), (2.75, 0.98), (3.00, 1.01)],
}

# IS 456 Table 20 (maximum shear stress tau_c,max N/mm^2) by fck.
TAU_C_MAX = {20: 2.8, 25: 3.1, 30: 3.5, 35: 3.7, 40: 4.0}

# Design stress-strain points for cold-worked bars (IS 456 Fig. 23A / SP:16
# Table A): (stress as a fraction of 0.87 fy, inelastic strain).
_CW_POINTS = [(0.80, 0.0000), (0.85, 0.0001), (0.90, 0.0003), (0.95, 0.0007), (0.975, 0.0010), (1.00, 0.0020)]

BAR_AREAS = {d: math.pi * d * d / 4.0 for d in (8, 10, 12, 16, 20, 25, 32)}


def _grade_key(fck: float, table: Dict[int, object]) -> int:
    """Largest tabulated grade not exceeding fck (conservative)."""
    keys = sorted(table.keys())
    k = keys[0]
    for g in keys:
        if g <= fck + 1e-9:
            k = g
    return k


def tau_c(pt_percent: float, fck: float) -> float:
    """IS 456 Table 19 with linear interpolation (pt clamped to 0.15..3.0)."""
    pts = TAU_C_TABLES[_grade_key(fck, TAU_C_TABLES)]
    pt = max(pts[0][0], min(pt_percent, pts[-1][0]))
    for (p1, t1), (p2, t2) in zip(pts, pts[1:]):
        if p1 <= pt <= p2:
            return t1 + (t2 - t1) * (pt - p1) / (p2 - p1)
    return pts[-1][1]


def tau_c_max(fck: float) -> float:
    return TAU_C_MAX[_grade_key(fck, TAU_C_MAX)]


def xu_max_ratio(fy: float) -> float:
    """Limiting neutral-axis depth ratio xu,max/d for Fe250/Fe415/Fe500."""
    if fy <= 250:
        return 0.53
    if fy <= 415:
        return 0.48
    return 0.46


def steel_stress(strain, fy: float):
    """Design stress (N/mm^2, sign follows strain) for reinforcement.

    Fe250: elastic-perfectly plastic with fyd = 0.87 fy.
    Fe415/Fe500: cold-worked bar curve (IS 456 Fig. 23A) - see module note.
    Accepts scalars or numpy arrays.
    """
    eps = np.asarray(strain, dtype=float)
    a = np.abs(eps)
    fyd = 0.87 * fy
    if fy <= 250:
        s = np.minimum(a * ES, fyd)
    else:
        stresses = [0.0] + [r * fyd for r, _ in _CW_POINTS]
        strains = [0.0] + [r * fyd / ES + e for r, e in _CW_POINTS]
        s = np.interp(a, strains, stresses, right=fyd)
    out = np.sign(eps) * s
    return float(out) if out.ndim == 0 else out


def concrete_stress(strain, fck: float):
    """IS 456 Fig. 21 design stress block (compression positive, no tension)."""
    eps = np.clip(np.asarray(strain, dtype=float), 0.0, None)
    r = np.minimum(eps / EPS_C0, 1.0)
    s = 0.446 * fck * (2 * r - r * r)
    return float(s) if np.ndim(s) == 0 else s


# ---------------------------------------------------------------- flexure ----

def mu_lim_knm(b: float, d: float, fck: float, fy: float) -> float:
    k = xu_max_ratio(fy)
    return 0.36 * fck * b * d * d * k * (1 - 0.42 * k) / 1e6


def ast_singly(mu_knm: float, b: float, d: float, fck: float, fy: float) -> float:
    """Tension steel (mm^2) for a singly reinforced rectangular section with
    Mu <= Mu,lim (closed-form solution of the IS 456 Annex G expression)."""
    if mu_knm <= 0:
        return 0.0
    R = mu_knm * 1e6 / (b * d * d)
    disc = max(0.0, 1.0 - 4.598 * R / fck)
    pt = 50.0 * fck / fy * (1.0 - math.sqrt(disc))
    return pt * b * d / 100.0


@dataclass
class FlexureResult:
    mu_knm: float
    mu_lim_knm: float
    ast_req: float          # tension face steel required (mm^2)
    asc_req: float          # compression face steel required (mm^2)
    doubly: bool


def design_flexure(mu_knm: float, b: float, d: float, d_prime: float, fck: float, fy: float) -> FlexureResult:
    """Design a rectangular section for a (factored) moment magnitude."""
    mu = abs(mu_knm)
    mlim = mu_lim_knm(b, d, fck, fy)
    if mu <= mlim:
        return FlexureResult(mu, mlim, ast_singly(mu, b, d, fck, fy), 0.0, False)
    k = xu_max_ratio(fy)
    xu = k * d
    ast1 = 0.36 * fck * b * xu / (0.87 * fy)
    eps_sc = EPS_CU * (1.0 - d_prime / xu)
    fsc = steel_stress(eps_sc, fy)
    fcc = 0.446 * fck
    mu2 = (mu - mlim) * 1e6
    asc = mu2 / ((fsc - fcc) * (d - d_prime))
    ast2 = asc * (fsc - fcc) / (0.87 * fy)
    return FlexureResult(mu, mlim, ast1 + ast2, asc, True)


def min_tension_steel(b: float, d: float, fy: float) -> float:
    """IS 456 Cl 26.5.1.1(a): As/(b d) >= 0.85/fy."""
    return 0.85 * b * d / fy


# ------------------------------------------------------------------ shear ----

@dataclass
class ShearResult:
    vu_kn: float
    tau_v: float
    tau_c: float
    tau_c_max: float
    spacing_mm: float
    legs: int
    dia: int
    status: str
    note: str = ""


def design_shear(vu_kn: float, b: float, d: float, pt_percent: float, fck: float, fy: float,
                 stirrup_dia: int = 8, legs: int = 2) -> ShearResult:
    """Vertical stirrup design for a rectangular beam (IS 456 Cl 40)."""
    tv = abs(vu_kn) * 1000.0 / (b * d)
    tc = tau_c(pt_percent, fck)
    tcm = tau_c_max(fck)
    asv = legs * BAR_AREAS[stirrup_dia]
    fy_s = min(fy, 415.0)  # IS 456 Cl 40.4: fy of stirrups not taken > 415
    s_min_rule = 0.87 * fy_s * asv / (0.4 * b)          # minimum shear reinforcement
    s_max = min(0.75 * d, 300.0)
    if tv > tcm:
        return ShearResult(vu_kn, tv, tc, tcm, 0.0, legs, stirrup_dia, "FAIL",
                           f"tau_v={tv:.2f} > tau_c,max={tcm:.2f}: enlarge section")
    if tv <= tc:
        s = min(s_min_rule, s_max)
        note = "minimum shear reinforcement"
    else:
        vus = (tv - tc) * b * d  # N
        s = min(0.87 * fy_s * asv * d / vus, s_min_rule, s_max)
        note = "designed shear reinforcement"
    s = math.floor(s / 5.0) * 5.0
    status = "PASS"
    if s < 75.0:
        status = "FAIL"
        note += f"; required spacing {s:.0f} mm < 75 mm practical minimum - increase legs/diameter or section"
    return ShearResult(vu_kn, tv, tc, tcm, s, legs, stirrup_dia, status, note)


# ------------------------------------------------------------ bar choice ----

def choose_bars(area_req: float, width_avail: float, options: Sequence[int] = (12, 16, 20, 25),
                min_bars: int = 2, max_layers: int = 2, min_clear: float = 25.0) -> Tuple[int, int, int, float]:
    """Pick (n_bars, dia, layers, area_provided) for a beam face.

    Prefers the smallest diameter that fits in one layer; otherwise two
    layers.  Clear spacing >= max(dia, min_clear) (IS 456 Cl 26.3.2 uses
    aggregate size + 5 mm; 25 mm assumed for 20 mm aggregate).
    """
    best = None
    for layers in range(1, max_layers + 1):
        for dia in options:
            n = max(min_bars, math.ceil(area_req / BAR_AREAS[dia]))
            per_layer = math.ceil(n / layers)
            clear = max(dia, min_clear)
            fits = per_layer * dia + (per_layer - 1) * clear <= width_avail + 1e-6
            if fits:
                best = (n, dia, layers, n * BAR_AREAS[dia])
                break
        if best:
            break
    if best is None:
        dia = options[-1]
        n = max(min_bars, math.ceil(area_req / BAR_AREAS[dia]))
        best = (n, dia, max_layers + 1, n * BAR_AREAS[dia])  # does not fit -> caller flags FAIL
    return best


# --------------------------------------------------------------- columns ----

@dataclass
class ColumnSection:
    b: float                 # dimension along global X (mm)
    D: float                 # dimension along global Y (mm)
    bar_x: np.ndarray        # bar coordinates from centroid (mm)
    bar_y: np.ndarray
    bar_area: np.ndarray
    fck: float
    fy: float
    n_bars: int = 0
    dia: int = 0

    @property
    def As(self) -> float:
        return float(self.bar_area.sum())

    @property
    def Ag(self) -> float:
        return self.b * self.D


def column_section(b: float, D: float, n_bars: int, dia: int, fck: float, fy: float,
                   clear_cover: float = 40.0, tie_dia: int = 8) -> ColumnSection:
    """Rectangular column with ``n_bars`` (even, >= 4) distributed around the
    perimeter: 4 corner bars, remaining pairs shared between the faces in
    proportion to their lengths."""
    n_bars = max(4, n_bars + (n_bars % 2))
    edge = clear_cover + tie_dia + dia / 2.0
    xs, ys = b / 2.0 - edge, D / 2.0 - edge
    pts = [(-xs, -ys), (xs, -ys), (xs, ys), (-xs, ys)]
    pairs = (n_bars - 4) // 2
    px = int(round(pairs * b / (b + D)))  # pairs on faces parallel to X (top & bottom)
    py = pairs - px
    for i in range(1, px + 1):
        x = -xs + 2 * xs * i / (px + 1)
        pts += [(x, -ys), (x, ys)]
    for i in range(1, py + 1):
        y = -ys + 2 * ys * i / (py + 1)
        pts += [(-xs, y), (xs, y)]
    arr = np.array(pts)
    return ColumnSection(b, D, arr[:, 0], arr[:, 1], np.full(len(pts), BAR_AREAS[dia]), fck, fy, len(pts), dia)


def interaction_curve(sec: ColumnSection, direction: str = "x", n_fibres: int = 120) -> Tuple[np.ndarray, np.ndarray]:
    """Uniaxial P-M interaction (strain compatibility, IS 456 Cl 38.1/39.1).

    ``direction='x'`` bends the section so that the depth is measured along X
    (dimension b), i.e. the moment produced by sway in an X-direction frame.

    Strain profiles: neutral axis inside the section -> 0.0035 at the extreme
    fibre; neutral axis outside -> 0.002 at 3h/7 from the more compressed face
    (Cl 39.1(a)).  Concrete displaced by bars is deducted.  Pure tension and
    uniform 0.002 compression close the curve.

    Returns (P_kN, M_kNm) arrays sorted by increasing P, M >= 0.  Results are
    memoised per section definition (identical sections share one curve).
    """
    if direction == "x":
        h, w, pos = sec.b, sec.D, sec.bar_x
    else:
        h, w, pos = sec.D, sec.b, sec.bar_y
    key = (round(h, 3), round(w, 3), tuple(np.round(pos, 6)), tuple(float(a) for a in sec.bar_area),
           float(sec.fck), float(sec.fy), int(n_fibres))
    return _curve_cached(key)


@lru_cache(maxsize=4096)
def _curve_cached(key):
    h, w, pos, areas, fck, fy, n_fibres = key
    pos = np.asarray(pos, dtype=float)
    areas = np.asarray(areas, dtype=float)
    As = float(areas.sum())
    t_bar = h / 2.0 - pos                                   # bar depth from compression face
    dt = h / n_fibres
    t_f = (np.arange(n_fibres) + 0.5) * dt
    xus = np.concatenate([np.geomspace(1e-4 * h, 0.999 * h, 90), np.geomspace(1.001 * h, 60 * h, 40)])[:, None]
    inside = xus <= h
    denom = np.where(inside, xus, xus - 3.0 * h / 7.0)
    peak = np.where(inside, EPS_CU, EPS_C0)
    eps_f = peak * (xus - t_f[None, :]) / denom            # (n_xu, n_fibres)
    eps_s = peak * (xus - t_bar[None, :]) / denom          # (n_xu, n_bars)
    fc = concrete_stress(eps_f, fck) * w * dt               # N per fibre
    Fs = (steel_stress(eps_s, fy) - concrete_stress(eps_s, fck)) * areas[None, :]
    P = fc.sum(axis=1) + Fs.sum(axis=1)
    M = (fc * (h / 2.0 - t_f)[None, :]).sum(axis=1) + (Fs * (h / 2.0 - t_bar)[None, :]).sum(axis=1)
    p0 = 0.446 * fck * (h * w - As) + steel_stress(EPS_C0, fy) * As
    P = np.concatenate([[-0.87 * fy * As], P, [p0]]) / 1e3
    M = np.abs(np.concatenate([[0.0], M, [0.0]])) / 1e6
    order = np.argsort(P)
    P, M = P[order], M[order]
    P.flags.writeable = False
    M.flags.writeable = False
    return P, M


def moment_capacity_at(P_kN: float, curve: Tuple[np.ndarray, np.ndarray]) -> float:
    """Uniaxial moment capacity (kNm) at axial load P from an interaction curve;
    0 if P exceeds the axial capacity."""
    P, M = curve
    if P_kN > P[-1] or P_kN < P[0]:
        return 0.0
    return float(np.interp(P_kN, P, M))


def puz_kn(sec: ColumnSection) -> float:
    """IS 456 Cl 39.6: Puz = 0.45 fck Ac + 0.75 fy Asc."""
    return (0.45 * sec.fck * (sec.Ag - sec.As) + 0.75 * sec.fy * sec.As) / 1e3


def alpha_n(pu: float, puz: float) -> float:
    r = pu / puz if puz > 0 else 1.0
    if r <= 0.2:
        return 1.0
    if r >= 0.8:
        return 2.0
    return 1.0 + (r - 0.2) / 0.6


def e_min_mm(unsupported_length_mm: float, dim_mm: float) -> float:
    """IS 456 Cl 25.4 minimum eccentricity: l/500 + D/30, not less than 20 mm."""
    return max(unsupported_length_mm / 500.0 + dim_mm / 30.0, 20.0)


def additional_moment_knm(pu_kn: float, dim_mm: float, le_mm: float) -> float:
    """IS 456 Cl 39.7.1 additional moment for slender columns (reduction factor
    k taken as 1.0, conservative). Zero when le/D <= 12."""
    if dim_mm <= 0 or le_mm / dim_mm <= 12.0:
        return 0.0
    return pu_kn * dim_mm / 2000.0 * (le_mm / dim_mm) ** 2 / 1000.0


@dataclass
class ColumnCheck:
    pu_kn: float
    mux_kNm: float            # design moment, lever along X (dimension b), incl. e_min / slenderness
    muy_kNm: float            # design moment, lever along Y (dimension D)
    mux1_kNm: float
    muy1_kNm: float
    puz_kN: float
    alpha_n: float
    ratio: float              # governing interaction ratio (<= 1 passes)
    governing: str
    slender_x: bool
    slender_y: bool


def check_column(sec: ColumnSection, pu_kn: float, mx_kNm: float, my_kNm: float,
                 unsupported_length_mm: float, le_factor: float = 1.0,
                 curves: Optional[dict] = None) -> ColumnCheck:
    """Biaxial check (IS 456 Cl 39.6) including minimum eccentricity (applied
    about one axis at a time) and slenderness additional moments."""
    curves = curves or {"x": interaction_curve(sec, "x"), "y": interaction_curve(sec, "y")}
    pu = pu_kn                      # negative = net tension
    pa = abs(pu)
    le = le_factor * unsupported_length_mm
    ex, ey = e_min_mm(unsupported_length_mm, sec.b), e_min_mm(unsupported_length_mm, sec.D)
    max_x = additional_moment_knm(max(pu, 0.0), sec.b, le)
    max_y = additional_moment_knm(max(pu, 0.0), sec.D, le)
    puz = puz_kn(sec)
    an = alpha_n(max(pu, 0.0), puz)
    m1x, m1y = moment_capacity_at(pu, curves["x"]), moment_capacity_at(pu, curves["y"])
    cases = {
        "e_min about X-lever": (max(abs(mx_kNm), pa * ex / 1e3) + max_x, abs(my_kNm) + max_y),
        "e_min about Y-lever": (abs(mx_kNm) + max_x, max(abs(my_kNm), pa * ey / 1e3) + max_y),
    }
    worst = (-1.0, "", 0.0, 0.0)
    for name, (mx, my) in cases.items():
        if m1x <= 0 or m1y <= 0:
            r = float("inf")
        else:
            r = (mx / m1x) ** an + (my / m1y) ** an
        if r > worst[0]:
            worst = (r, name, mx, my)
    return ColumnCheck(pu, worst[2], worst[3], m1x, m1y, puz, an, worst[0], worst[1],
                       le / sec.b > 12.0, le / sec.D > 12.0)
