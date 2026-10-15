"""
Post-design re-check ("audit") of the final member sizes.

These checks re-compute a few governing quantities with simple, separately
coded formulas.  They are a CONSISTENCY screen, not an independent
engineering verification (see docs/verification/verification-matrix.md).

Load convention (fixed in the 2026-10 remediation, audit finding R6):
``Column.load_kn`` is a SERVICE load; ultimate checks multiply by 1.5 or use
the factored combinations written by the analysis.
"""

import math
from typing import List, Optional

from pydantic import BaseModel

from .foundation_eng import Footing, calculate_punching_shear_capacity
from .framing_logic import StructuralMember
from .grid_manager import GridManager


class AuditResult(BaseModel):
    member_id: str
    check_name: str
    design_value: float
    limit_value: float
    status: str  # PASS, FAIL, WARN
    discrepancy_percent: float = 0.0
    notes: str = ""


class StructuralAuditor:
    def __init__(self, grid_mgr: GridManager, beams: List[StructuralMember], footings: List[Footing],
                 sbc_kn_m2: Optional[float] = None, fck: Optional[float] = None, fy: Optional[float] = None):
        self.grid_mgr = grid_mgr
        self.beams = beams
        self.footings = footings
        self.sbc = sbc_kn_m2 if sbc_kn_m2 is not None else 200.0
        self.fck = fck if fck is not None else getattr(grid_mgr, "fck", 25.0)
        self.fy = fy if fy is not None else getattr(grid_mgr, "fy", 415.0)
        self.audit_log: List[AuditResult] = []
        self.math_breakdown: List[str] = []

    def run_audit(self) -> List[AuditResult]:
        self.audit_columns()
        self.audit_footings()
        self.audit_beams()
        return self.audit_log

    # ------------------------------------------------------------ columns --
    def audit_columns(self):
        """Factored axial load vs 0.4 fck Ac + 0.67 fy Asc (IS 456 Cl 39.3
        form).  Pu = max over analysis combinations, or 1.5 x service load."""
        fck, fy = self.fck, self.fy
        for idx, col in enumerate(self.grid_mgr.columns):
            ag = col.width_nb * col.depth_nb
            res = self.grid_mgr.rebar_schedule.get(col.id)
            asc = res.main_steel_area_mm2 if res is not None else 0.0
            term1 = 0.4 * fck * (ag - asc)
            term2 = 0.67 * fy * asc
            cap_kn = (term1 + term2) / 1000.0
            pu = max([f[1] for f in col.design_forces], default=1.5 * col.load_kn)
            ratio = pu / cap_kn if cap_kn > 0 else 999.0
            emin = max((col.z_top - col.z_bottom) * 1000.0 / 500.0 + min(col.width_nb, col.depth_nb) / 30.0, 20.0)
            applicable = emin <= 0.05 * min(col.width_nb, col.depth_nb)
            status = "PASS" if ratio <= 1.0 else "FAIL"
            self.audit_log.append(AuditResult(
                member_id=col.id, check_name="Column Axial Capacity (factored)", design_value=pu,
                limit_value=cap_kn, status=status, discrepancy_percent=ratio * 100,
                notes=(f"Pu {pu:.1f} vs {cap_kn:.1f} kN (M{int(fck)}, Fe{int(fy)})"
                       + ("" if applicable else "; Cl 39.3 form not applicable (e_min > 0.05D) - "
                          "P-M interaction in the column schedule governs"))))
            if idx < 2:
                self.math_breakdown.append(
                    f"--- Audit Math: {col.id} ---\n"
                    f"Size: {col.width_nb:.0f}x{col.depth_nb:.0f} mm, Ag = {ag:.0f} mm2, Asc = {asc:.0f} mm2\n"
                    f"Capacity = 0.4 x {fck} x (Ag - Asc) + 0.67 x {fy} x Asc = {term1 / 1000:.1f} + {term2 / 1000:.1f} "
                    f"= {cap_kn:.1f} kN\nFactored Pu = {pu:.1f} kN (service {col.load_kn:.1f} kN)\nStatus: {status}\n")

    # ----------------------------------------------------------- footings --
    def audit_footings(self):
        level_0_cols = [c for c in self.grid_mgr.columns if getattr(c, "level", 0) == 0]
        if len(level_0_cols) != len(self.footings):
            self.audit_log.append(AuditResult(
                member_id="System", check_name="Footing Count", design_value=len(self.footings),
                limit_value=len(level_0_cols), status="FAIL", notes="Footing count mismatch with L0 columns"))
            return
        for col, ft in zip(level_0_cols, self.footings):
            service = col.load_kn + getattr(col, "plinth_load_kn", 0.0)
            area = ft.length_m * ft.width_m
            pressure = service * 1.1 / area
            self.audit_log.append(AuditResult(
                member_id=f"F-{col.id}", check_name="Bearing Pressure", design_value=pressure,
                limit_value=self.sbc, status="PASS" if pressure <= self.sbc + 1e-6 else "FAIL",
                notes=f"(P {service:.1f} kN x 1.1) / {area:.2f} m2 = {pressure:.1f} vs SBC {self.sbc:.0f} kN/m2"))

            pu = ft.factored_load_kn or 1.5 * service
            d = ft.thickness_mm - 50.0 - 12.0
            a1, a2 = col.width_nb + d, col.depth_nb + d
            qu = pu * 1000.0 / (ft.length_m * ft.width_m * 1e6)
            vu = pu * 1000.0 - qu * a1 * a2
            tau_v = vu / (2 * (a1 + a2) * d)
            beta = min(col.width_nb, col.depth_nb) / max(col.width_nb, col.depth_nb)
            tau_c = calculate_punching_shear_capacity(ft.thickness_mm, self.fck, beta)
            self.audit_log.append(AuditResult(
                member_id=f"F-{col.id}", check_name="Punching Shear", design_value=tau_v, limit_value=tau_c,
                status="PASS" if tau_v <= tau_c else "FAIL",
                notes=f"tau_v {tau_v:.2f} vs ks.0.25sqrt(fck) {tau_c:.2f} N/mm2 (Pu {pu:.0f} kN, d {d:.0f} mm)"))

    # -------------------------------------------------------------- beams --
    def audit_beams(self):
        """Short-term deflection, simply supported 5wL^4/384EI with
        Ieff = 0.5 Ig (approximation) under the analysed service line load,
        limit span/250.  Long-term creep/shrinkage effects not included."""
        ec = 5000.0 * math.sqrt(self.fck)
        unique = {}
        for b in self.beams:
            unique.setdefault(GridManager.base_member_id(b.id), b)
        for bid, beam in unique.items():
            l_mm = math.hypot(beam.end_point.x - beam.start_point.x, beam.end_point.y - beam.start_point.y) * 1000.0
            if l_mm < 1000.0:
                continue
            b_mm, d_mm = beam.properties.width_mm, beam.properties.depth_mm
            ieff = 0.5 * b_mm * d_mm ** 3 / 12.0
            w = beam.service_udl_kn_m or (20.0 + b_mm * d_mm / 1e6 * 25.0)
            delta = 5 * w * l_mm ** 4 / (384 * ec * ieff)
            limit = l_mm / 250.0
            self.audit_log.append(AuditResult(
                member_id=bid, check_name="Beam Deflection (Serviceability)", design_value=delta,
                limit_value=limit, status="PASS" if delta <= limit else "FAIL",
                notes=(f"Defl {delta:.2f} mm vs limit {limit:.2f} mm, w = {w:.1f} kN/m"
                       + ("" if beam.service_udl_kn_m else " (no analysis load - 20 kN/m assumed)"))))
