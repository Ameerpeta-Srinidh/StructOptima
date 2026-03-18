import numpy as np
from typing import Literal, List, Tuple, Dict, Any
from pydantic import BaseModel, PositiveFloat, Field
from .sections import SectionProperties

# --- LOAD MODELS ---

class ComponentLoad(BaseModel):
    name: str
    value_kn_m: float = Field(..., description="Load value in kN/m (UDL) or kN (Point)")
    type: Literal["dead", "live", "superimposed"]

class AggregatedLoad(BaseModel):
    total_dead: float
    total_live: float
    total_superimposed: float
    total_factored: float

    @property
    def total_service(self) -> float:
        return self.total_dead + self.total_live + self.total_superimposed

def aggregate_loads(loads: List[ComponentLoad], dead_load_factor: float = 1.5, live_load_factor: float = 1.5) -> AggregatedLoad:
    """Aggregate loads and apply IS 456:2000 Table 18 load factors.
    
    Default factors: 1.5 DL + 1.5 LL (Limit State of Collapse, Combination 1).
    Superimposed dead loads are factored with the dead load factor.
    """
    d = sum(l.value_kn_m for l in loads if l.type == "dead")
    l = sum(l.value_kn_m for l in loads if l.type == "live")
    s = sum(l.value_kn_m for l in loads if l.type == "superimposed")
    
    # IS 456 Combinations usually 1.5(DL + LL)
    factored = (d + s) * dead_load_factor + l * live_load_factor
    
    return AggregatedLoad(
        total_dead=d,
        total_live=l,
        total_superimposed=s,
        total_factored=factored
    )

# --- BEAM ANALYSIS ---

class BeamAnalysisResult(BaseModel):
    max_bending_moment_kNm: float
    max_shear_force_kN: float
    max_deflection_mm: float
    span_mm: float
    is_safe_deflection: bool
    status_msg: str

def validate_sls(deflection_mm: float, span_mm: float, limit_ratio: float = 250.0) -> Tuple[bool, str]:
    """Check Serviceability Limit State (Deflection) per IS 456:2000 Cl. 23.2.
    
    Default limit: L/250 for total deflection (Cl. 23.2(a)).
    For deflection after erection of partitions/finishes, use L/350.
    """
    limit = span_mm / limit_ratio
    # deflection generally negative (downward), use abs
    if abs(deflection_mm) <= limit:
        return True, f"Pass: {abs(deflection_mm):.2f}mm <= {limit:.2f}mm (L/{limit_ratio})"
    return False, f"Fail: {abs(deflection_mm):.2f}mm > {limit:.2f}mm (L/{limit_ratio})"

def analyze_beam(
    span_mm: float,
    load_kn_m: float, # Factored load for Strength, Service load for Deflection ideally, but keeping simple for now
    section_props: SectionProperties,
    elastic_modulus_mpa: float,
    support_type: Literal["simply_supported", "continuous"] = "simply_supported"
) -> BeamAnalysisResult:
    """
    Analyse a beam under Uniformly Distributed Load (UDL).
    
    Formulae:
      Simply Supported: M = wL^2/8, V = wL/2 (IS 456 Cl. 22.2)
      Continuous:       M = wL^2/10, V = 0.6wL (IS 456 Cl. 22.5, Table 12/13)
      Deflection:       5wL^4/384EI (SS), wL^4/384EI (Continuous)
    
    Notation:
      w  = UDL in kN/m
      L  = clear span in m
      E  = modulus of elasticity in MPa
      I  = second moment of area in mm^4
    """
    L = span_mm / 1000.0 # convert to m for internal calc
    w = load_kn_m # kN/m
    
    # 1. Bending Moment & Shear Force (Using Factored Load ideally passed in w)
    if support_type == "simply_supported":
        # Max Moment M = wL^2 / 8
        m_max = (w * L**2) / 8.0 # kNm
        # Max Shear V = wL / 2
        v_max = (w * L) / 2.0 # kN
        # Deflection delta = 5wL^4 / 384EI (Note: this should use Unfactored technically)
        # We will assume w passed here is appropriate for the check or just calculate
        denom = (384 * elastic_modulus_mpa * section_props.ix) # E in MPa(N/mm2), I in mm4
        # w in N/mm -> w_kn_m = w N/mm
        # L in mm
        w_newton_mm = w # 1 kN/m = 1 N/mm
        
        deflection = (5 * w_newton_mm * (span_mm**4)) / denom # mm
        
    elif support_type == "continuous":
        # Simplified assumption for continuous beam (approximate mid-span positive or support negative)
        # Using IS 456 coefficients for interior span roughly wL^2/12 or wL^2/10 depending on position.
        # Taking conservative approximation wL^2/10 for support moment.
        m_max = (w * L**2) / 10.0
        v_max = (w * L) * 0.6 # Roughly 0.6 factor for shear redistribution
        
        # Deflection approximate: wL^4 / 384EI (Reduced due to continuity, often taken as 1/5th of simple)
        # Or standard approximation 1/384... let's use 1/384 coefficient for continuous approx
        w_newton_mm = w
        denom = (384 * elastic_modulus_mpa * section_props.ix)
        deflection = (1 * w_newton_mm * (span_mm**4)) / denom # significantly less than 5/384
        
    else:
        raise ValueError(f"Unknown support type: {support_type}")

    is_safe, msg = validate_sls(deflection, span_mm)
    
    return BeamAnalysisResult(
        max_bending_moment_kNm=m_max,
        max_shear_force_kN=v_max,
        max_deflection_mm=deflection,
        span_mm=span_mm,
        is_safe_deflection=is_safe,
        status_msg=msg
    )

# --- COLUMN SIZING ---

class ColumnCheckResult(BaseModel):
    axial_capacity_kN: float
    load_applied_kN: float
    is_safe: bool
    slenderness_ratio: float
    status_msg: str

def check_column_capacity(
    load_kN: float,
    section_props: SectionProperties,
    effective_length_mm: float,
    fck: float,
    fy: float,
    gross_area_mm2: float
) -> ColumnCheckResult:
    """
    Check column axial capacity per IS 456:2000 Cl. 39.3.
    
    Formula (Short Axially Loaded Members):
      Pu = 0.4 fck Ac + 0.67 fy Asc
    
    Where:
      Ac  = net area of concrete = Ag - Asc
      Asc = area of longitudinal steel (assumed 0.8% Ag minimum per Cl. 26.5.3.1)
      fck = characteristic compressive strength of concrete (MPa)
      fy  = yield strength of steel (MPa)
    
    Slenderness check: Lambda = Le / r_min. Short column if Lambda <= 12.
    """
    
    # Assumption: Minimum steel 0.8%, let's check with 0.8% for conservative estimate if exact reinforcement unspecified
    # Asc = 0.008 * Ag
    # Ac = Ag - Asc = 0.992 * Ag
    
    asc = 0.008 * gross_area_mm2
    ac = gross_area_mm2 - asc
    
    # IS 456 formula for Pu
    p_u = (0.4 * fck * ac + 0.67 * fy * asc) / 1000.0 # Convert N to kN
    
    # Slenderness check
    # Lambda = Le / r_min
    # r_min = sqrt(I_min / A)
    i_min = min(section_props.ix, section_props.iy)
    r_min = np.sqrt(i_min / gross_area_mm2)
    slenderness = effective_length_mm / r_min
    
    msg = []
    is_safe = True
    
    # Check slenderness (Limit 12 for short column simplified check usually, but IS 456 allows up to 60 before fail)
    # If > 12, it's a long column and needs reduction coefficients (Cr). 
    # For Phase 1 simplified, we will warn if > 12.
    if slenderness > 12:
        msg.append(f"Warning: Slenderness {slenderness:.2f} > 12 (Long Column functionality not fully implemented).")
        
    if load_kN > p_u:
        is_safe = False
        msg.append(f"Fail: Load {load_kN} kN > Capacity {p_u:.2f} kN")
    else:
        msg.append(f"Pass: Capacity {p_u:.2f} kN >= Load {load_kN} kN")
        
    return ColumnCheckResult(
        axial_capacity_kN=p_u,
        load_applied_kN=load_kN,
        is_safe=is_safe,
        slenderness_ratio=slenderness,
        status_msg="; ".join(msg)
    )
