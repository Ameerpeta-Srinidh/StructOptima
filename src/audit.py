
import math
from typing import List, Dict, Optional
from pydantic import BaseModel
from .grid_manager import GridManager, Column
from .framing_logic import StructuralMember
from .foundation_eng import Footing
from .materials import Concrete
from .rebar_detailer import RebarResult

class AuditResult(BaseModel):
    member_id: str
    check_name: str
    design_value: float
    limit_value: float
    status: str # PASS, FAIL, WARN
    discrepancy_percent: float = 0.0
    notes: str = ""

class StructuralAuditor:
    def __init__(self, grid_mgr: GridManager, beams: List[StructuralMember], footings: List[Footing]):
        self.grid_mgr = grid_mgr
        self.beams = beams
        self.footings = footings
        self.audit_log: List[AuditResult] = []
        self.math_breakdown: List[str] = []
        
    def run_audit(self) -> List[AuditResult]:
        """
        Executes all independent checks.
        """
        self.audit_columns()
        self.audit_footings()
        self.audit_beams()
        return self.audit_log
        
    def audit_columns(self):
        """
        Independent check of column capacity P_u vs Load.
        Pu_limit = 0.4 fck Ag + 0.67 fy Asc
        """
        fck = 25.0 # M25
        fy = 415.0 # Fe415
        
        for col in self.grid_mgr.columns:
            # Independent Area Calc
            ag = col.width_nb * col.depth_nb
            
            # Rebar?
            asc = 0.0
            if col.id in self.grid_mgr.rebar_schedule:
                res = self.grid_mgr.rebar_schedule[col.id]
                asc = res.main_steel_area_mm2
                
            # Capacity Formula
            term1 = 0.4 * fck * ag
            term2 = 0.67 * fy * asc
            pu_cap_n = term1 + term2
            pu_cap_kn = pu_cap_n / 1000.0
            
            # Load
            load_kn = col.load_kn
            
            # Check
            ratio = load_kn / pu_cap_kn if pu_cap_kn > 0 else 999.0
            
            status = "PASS" if ratio <= 1.0 else "FAIL"
            
            self.audit_log.append(AuditResult(
                member_id=col.id,
                check_name="Column Axial Capacity",
                design_value=load_kn,
                limit_value=pu_cap_kn,
                status=status,
                discrepancy_percent=ratio*100,
                notes=f"Load: {load_kn:.1f} vs Cap: {pu_cap_kn:.1f} kN"
            ))
            
            # Math breakdown for sample
            if col.id in ["C1", "C5"]:
                self.math_breakdown.append(f"""
                --- Audit Math: {col.id} ---
                Size: {col.width_nb}x{col.depth_nb} mm
                Ag = {ag} mm2
                Asc (Provided) = {asc} mm2
                
                Capacity Formula: Pu = 0.4 * fck * Ag + 0.67 * fy * Asc
                Substitution: 0.4 * {fck} * {ag} + 0.67 * {fy} * {asc}
                Result: {term1/1000:.1f} + {term2/1000:.1f} = {pu_cap_kn:.1f} kN
                Applied Load: {load_kn:.1f} kN
                Status: {status}
                --------------------------
                """)

    def audit_footings(self):
        """
        Check Bearing Pressure and Punching Shear depth independent check.
        """
        sbc = 200.0 # kN/m2
        
        # Link footings to Level 0 columns
        level_0_cols = [c for c in self.grid_mgr.columns if getattr(c, 'level', 0) == 0]
        
        if len(level_0_cols) != len(self.footings):
             self.audit_log.append(AuditResult(
                 member_id="System",
                 check_name="Footing Count",
                 design_value=len(self.footings),
                 limit_value=len(level_0_cols),
                 status="FAIL",
                 notes="Footing count mismatch with L0 columns"
             ))
             return

        for i, col in enumerate(level_0_cols):
            ft = self.footings[i]
            
            # 1. Pressure Check
            # Load + 10% self weight assumed in design
            total_load = col.load_kn * 1.1
            area = ft.length_m * ft.width_m
            pressure = total_load / area
            
            status = "PASS" if pressure <= sbc else "FAIL"
            
            self.audit_log.append(AuditResult(
                member_id=f"F-{col.id}",
                check_name="Bearing Pressure",
                design_value=pressure,
                limit_value=sbc,
                status=status,
                notes=f"Press: {pressure:.1f} <= {sbc}"
            ))
            
            # 2. Punching Shear Check (Simplified)
            # Tau_v = Vu / (b0 * d)
            # b0 = 2*(c1+d + c2+d)
            # Tau_c = 0.25 * sqrt(fck) = 0.25 * 5 = 1.25 N/mm2
            
            tau_c = 0.25 * (25.0**0.5)
            
            d_mm = ft.thickness_mm - 75 # eff depth
            c1 = col.width_nb
            c2 = col.depth_nb
            
            perimeter = 2 * ((c1 + d_mm) + (c2 + d_mm))
            
            # Vu = P - (pressure * area_punching) ~ P typically
            vu_n = col.load_kn * 1000.0
            
            tau_v = vu_n / (perimeter * d_mm)
            
            status_shear = "PASS" if tau_v <= tau_c else "FAIL"
            
            self.audit_log.append(AuditResult(
                member_id=f"F-{col.id}",
                check_name="Punching Shear",
                design_value=tau_v,
                limit_value=tau_c,
                status=status_shear,
                notes=f"Shear Stress: {tau_v:.2f} <= {tau_c:.2f} N/mm2"
            ))


    def audit_beams(self):
        """
        Check Serviceability (Deflection).
        Delta = 5 w L^4 / 384 E I
        Limit = L / 250
        """
        # Assumptions
        fck = 25.0
        ec_mpa = 5000 * math.sqrt(fck) # 25000 MPa
        gamma_c = 25.0 # kN/m3
        
        # Access beams. Since main.py passes `all_beams` (logic copies), we iterate them.
        # But `all_beams` might be large.
        # Let's map unique beams by ID to avoid duplicate checks if passed multiple times.
        unique_beams = {b.id: b for b in self.beams}
        
        for bid, beam in unique_beams.items():
            # Geometry
            l_m = ((beam.end_point.x - beam.start_point.x)**2 + 
                   (beam.end_point.y - beam.start_point.y)**2)**0.5
            l_mm = l_m * 1000.0
            
            if l_mm < 1000.0: continue # Skip point beams or artifacts
            
            b_mm = beam.properties.width_mm
            d_mm = beam.properties.depth_mm
            
            # Inertia (Rectangle)
            # I = b * d^3 / 12
            I_mm4 = (b_mm * (d_mm**3)) / 12.0
            
            # Load (Simplified UDL assumption matched with detail_beams)
            # 20 kN/m imposed + SW
            sw_kn_m = (b_mm/1000) * (d_mm/1000) * gamma_c
            w_kn_m = 20.0 + sw_kn_m
            w_n_mm = w_kn_m / 1.0 # 1 kN/m = 1 N/mm
            
            # Deflection (Simply Supported - Conservative)
            # Delta = (5 * w * L^4) / (384 * E * I)
            
            numerator = 5 * w_n_mm * (l_mm**4)
            denominator = 384 * ec_mpa * I_mm4
            
            delta_actual = numerator / denominator if denominator > 0 else 0
            
            # Limit
            delta_limit = l_mm / 250.0
            
            status = "PASS" if delta_actual <= delta_limit else "FAIL"
            
            # Add to log
            self.audit_log.append(AuditResult(
                member_id=bid,
                check_name="Beam Deflection (Serviceability)",
                design_value=delta_actual,
                limit_value=delta_limit,
                status=status,
                notes=f"Defl: {delta_actual:.3f}mm vs Limit {delta_limit:.2f}mm"
            ))
