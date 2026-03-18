import math
from typing import Optional
from pydantic import BaseModel
from .materials import Concrete
from .logging_config import get_logger

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

def calculate_punching_shear_capacity(thickness_mm: float, fck: float) -> float:
    """
    Calculates allowable punching shear stress (Tau_c).
    Simplified limit state approx: 0.25 * sqrt(fck).
    Result in N/mm2 (MPa).
    """
    return 0.25 * math.sqrt(fck)

def design_footing(
    axial_load_kn: float, 
    sbc_kn_m2: float = 200.0, 
    column_width_mm: float = 300.0, 
    column_depth_mm: float = 300.0,
    concrete: Optional[Concrete] = None
) -> Footing:
    """
    Designs a square footing.
    1. Area = Load * 1.1 / SBC
    2. Thickness check for punching shear.
    """
    if concrete is None:
        # Fallback if not provided, assuming M25
        fck = 25.0
    else:
        fck = concrete.fck
    
    # Input validation - prevent crashes from edge cases
    if sbc_kn_m2 <= 0:
        logger.warning("SBC <= 0 provided, using default 200 kN/m²")
        sbc_kn_m2 = 200.0
    
    if axial_load_kn < 0:
        logger.warning("Negative load provided, using absolute value")
        axial_load_kn = abs(axial_load_kn)
    
    if axial_load_kn == 0:
        # Zero load - return minimum footing
        return Footing(
            length_m=1.0,
            width_m=1.0,
            thickness_mm=300.0,
            area_m2=1.0,
            concrete_vol_m3=0.3,
            excavation_vol_m3=1.5
        )

    # 1. Area Sizing
    # Load + 10% self weight
    design_load = axial_load_kn * 1.1
    required_area = design_load / sbc_kn_m2
    
    # Square footing
    side = math.sqrt(required_area)
    # Min size 1.0m
    if side < 1.0: side = 1.0
    
    # Max size 10m - beyond this, use pile foundation
    status = "PASS"
    if side > 10.0:
        logger.warning("Footing size %.1fm exceeds max 10m - consider pile foundation", side)
        side = 10.0
        status = "FAIL - SIZE EXCEEDED"
    
    # Round up to nearest 50mm (0.05m)
    side = math.ceil(side / 0.05) * 0.05
    
    provided_area = side * side
    
    # 2. Thickness / Punching Shear
    # Start thickness at 300mm
    thickness = 300.0
    
    # Allowable shear stress
    tau_allowable = calculate_punching_shear_capacity(thickness, fck) # MPa
    
    # Iterative check (50mm increments)
    while True:
        d = thickness - 50.0 # Effective depth approx (cover 50mm)
        if d <= 0:
            d = 0.5 * thickness # Fallback
            
        # Critical perimeter at d/2
        # Perimeter = 2 * (col_w + d) + 2 * (col_d + d)
        perimeter = 2 * (column_width_mm + d) + 2 * (column_depth_mm + d)
        
        # Shear Force (Punching) = Load - (Uplift on area inside perimeter)
        # Conservative: Pu (Factored load ideally, using axial_load_kn here as 'load')
        # Check: Is input load Factored or Service? Phase 2 used 'load' from trib area * 50kN/m2.
        # Assuming Factored Input Load.
        punching_load_kn = axial_load_kn # Simplifying -> Total load punches through
        
        # Shear Stress = Load / (Perimeter * d)
        # Convert kN to N, mm to mm2
        stress = (punching_load_kn * 1000.0) / (perimeter * d)
        
        if stress <= tau_allowable:
            # Phase 10: Safety Buffer for High Loads
            # If Load > 800kN and Stress is close to Limit (within 5%), add safety (50mm)
            limit_val = 800.0 # kN
            if punching_load_kn > limit_val:
                ratio = stress / tau_allowable
                if ratio > 0.95:
                    thickness += 50.0
            break
            
        thickness += 50.0
        if thickness > 2000: # Safety break
            break

    # Quantities
    # Excavation: Area * 1.5m (Assumption from plan)
    exc_depth = 1.5
    exc_vol = provided_area * exc_depth
    conc_vol = provided_area * (thickness / 1000.0)
    
    return Footing(
        length_m=side,
        width_m=side,
        thickness_mm=thickness,
        area_m2=provided_area,
        concrete_vol_m3=conc_vol,
        excavation_vol_m3=exc_vol,
        status=status
    )
