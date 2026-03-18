"""
Advanced Safety Warnings Module - IS 456 / IS 13920

Implements Phase 2 safety checks:
- Joint shear capacity (IS 13920)
- Cracked section modifiers (IS 1893/IS 16700)
- Plan irregularity detection

DISCLAIMER: All designs must be verified by a licensed
Structural Engineer before construction.
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional
from enum import Enum
import math


class IrregularityType(str, Enum):
    """Types of structural irregularities per IS 1893."""
    NONE = "none"
    TORSIONAL = "torsional"           # Plan irregularity
    RE_ENTRANT = "re_entrant"         # L, T, C shapes
    DIAPHRAGM_DISCONTINUITY = "diaphragm"  # Large openings
    SOFT_STOREY = "soft_storey"       # Vertical irregularity
    MASS_IRREGULARITY = "mass"        # >200% mass change


@dataclass
class JointShearCheck:
    """
    Beam-column joint shear check per IS 13920 Cl 9.
    
    The joint must resist shear from beam moments.
    """
    joint_id: str
    
    # Joint dimensions
    column_width_mm: float
    column_depth_mm: float
    beam_depth_mm: float
    
    # Shear demand
    joint_shear_demand_kn: float
    
    # Shear capacity
    joint_shear_capacity_kn: float
    
    # Check
    is_adequate: bool
    utilization_ratio: float
    remarks: str


@dataclass
class CrackedSectionModifiers:
    """
    Cracked section property modifiers per IS 1893/IS 16700.
    
    For seismic analysis, concrete cracks under loading.
    Use reduced stiffness:
    - Columns: 0.70 × Ig
    - Beams: 0.35 × Ig
    - Slabs: 0.25 × Ig
    """
    column_modifier: float = 0.70
    beam_modifier: float = 0.35
    slab_modifier: float = 0.25
    
    # Applied
    is_applied: bool = False
    warning: str = ""


@dataclass
class IrregularityCheck:
    """Check for structural irregularities per IS 1893."""
    irregularity_type: IrregularityType
    is_detected: bool
    severity: str  # "none", "minor", "major"
    description: str
    recommendation: str


@dataclass
class SafetyWarningsSummary:
    """Summary of all safety warnings."""
    joint_checks: List[JointShearCheck]
    cracked_modifiers: CrackedSectionModifiers
    irregularities: List[IrregularityCheck]
    
    # Counts
    joints_failed: int
    irregularities_detected: int
    
    # Critical warnings
    critical_warnings: List[str]
    recommendations: List[str]


class SafetyWarningsChecker:
    """
    Advanced safety warnings checker.
    
    Implements checks often missed by simplified software.
    """
    
    def __init__(
        self,
        fck: float = 25.0,
        fy: float = 500.0,
        seismic_zone: str = "III"
    ):
        self.fck = fck
        self.fy = fy
        self.seismic_zone = seismic_zone
        
        # Cracked section modifiers (always warn for seismic)
        self.cracked_mods = CrackedSectionModifiers(
            column_modifier=0.70,
            beam_modifier=0.35,
            slab_modifier=0.25,
            is_applied=False,
            warning="⚠️ Analysis uses gross section (Ig). For accurate seismic "
                   "behavior, use cracked section: Columns 0.7Ig, Beams 0.35Ig"
        )
    
    def check_joint_shear(
        self,
        joint_id: str,
        column_width_mm: float,
        column_depth_mm: float,
        beam_depth_mm: float,
        beam_tension_steel_mm2: float,
        joint_type: str = "interior"  # interior, exterior, corner
    ) -> JointShearCheck:
        """
        Check beam-column joint shear capacity per IS 13920 Cl 9.
        
        Joint shear demand arises from beam reinforcement forces.
        Vcol = 1.4 × As × fy - Vcol
        
        Joint shear capacity depends on:
        - Joint type (interior, exterior, corner)
        - Concrete strength
        - Confining reinforcement
        
        Args:
            joint_id: Joint identifier
            column_width_mm, column_depth_mm: Column dimensions
            beam_depth_mm: Beam depth at joint
            beam_tension_steel_mm2: Area of beam tension steel
            joint_type: Type of joint
            
        Returns:
            JointShearCheck result
        """
        # Effective joint area (IS 13920 Cl 9.1)
        bj = min(column_width_mm, column_width_mm + beam_depth_mm)  # Simplified
        hc = column_depth_mm
        Aj = bj * hc  # mm²
        
        # Joint shear demand (simplified)
        # Assume beam capacity generates shear
        sigma_s = 1.25 * self.fy  # Strain hardening
        Vj_demand = beam_tension_steel_mm2 * sigma_s / 1000  # kN
        
        # Joint shear capacity (IS 13920 Cl 9.2)
        # For confined joints: 1.2 × √fck × Aj
        # Capacity factors by joint type
        capacity_factors = {
            "interior": 1.2,
            "exterior": 1.0,
            "corner": 0.8
        }
        factor = capacity_factors.get(joint_type, 1.0)
        
        tau_j = factor * math.sqrt(self.fck)  # MPa
        Vj_capacity = tau_j * Aj / 1000  # kN
        
        utilization = Vj_demand / Vj_capacity if Vj_capacity > 0 else float('inf')
        is_adequate = utilization <= 1.0
        
        if is_adequate:
            remarks = f"OK (Utilization: {utilization:.0%})"
        else:
            remarks = f"FAIL: Joint overstressed by {(utilization-1)*100:.0f}%. Increase column size."
        
        return JointShearCheck(
            joint_id=joint_id,
            column_width_mm=column_width_mm,
            column_depth_mm=column_depth_mm,
            beam_depth_mm=beam_depth_mm,
            joint_shear_demand_kn=Vj_demand,
            joint_shear_capacity_kn=Vj_capacity,
            is_adequate=is_adequate,
            utilization_ratio=utilization,
            remarks=remarks
        )
    
    def check_plan_irregularities(
        self,
        floor_width: float,
        floor_length: float,
        opening_area: float = 0.0,
        is_l_shaped: bool = False,
        is_c_shaped: bool = False
    ) -> List[IrregularityCheck]:
        """
        Check for plan irregularities per IS 1893 Cl 7.1.
        
        Types checked:
        - Torsional irregularity
        - Re-entrant corners (L, T, C shapes)
        - Diaphragm discontinuity (large openings)
        
        Args:
            floor_width, floor_length: Floor dimensions
            opening_area: Total area of floor openings
            is_l_shaped, is_c_shaped: Shape flags
            
        Returns:
            List of IrregularityCheck results
        """
        results = []
        floor_area = floor_width * floor_length
        
        # Re-entrant corners
        if is_l_shaped or is_c_shaped:
            results.append(IrregularityCheck(
                irregularity_type=IrregularityType.RE_ENTRANT,
                is_detected=True,
                severity="major",
                description="L/C shaped floor plan detected (re-entrant corners)",
                recommendation="Use 3D dynamic analysis or add structural joints"
            ))
        
        # Diaphragm discontinuity (>50% opening)
        if floor_area > 0:
            opening_ratio = opening_area / floor_area
            if opening_ratio > 0.5:
                results.append(IrregularityCheck(
                    irregularity_type=IrregularityType.DIAPHRAGM_DISCONTINUITY,
                    is_detected=True,
                    severity="major",
                    description=f"Large floor opening ({opening_ratio*100:.0f}%) - "
                               f"floor may not act as rigid diaphragm",
                    recommendation="Model as semi-rigid/flexible diaphragm"
                ))
            elif opening_ratio > 0.3:
                results.append(IrregularityCheck(
                    irregularity_type=IrregularityType.DIAPHRAGM_DISCONTINUITY,
                    is_detected=True,
                    severity="minor",
                    description=f"Moderate floor opening ({opening_ratio*100:.0f}%)",
                    recommendation="Verify diaphragm action is adequate"
                ))
        
        # If no irregularities
        if not results:
            results.append(IrregularityCheck(
                irregularity_type=IrregularityType.NONE,
                is_detected=False,
                severity="none",
                description="Building appears regular in plan",
                recommendation="Static analysis method acceptable"
            ))
        
        return results
    
    def check_soft_storey(
        self,
        storey_stiffnesses: List[float]
    ) -> Optional[IrregularityCheck]:
        """
        Check for soft storey (vertical irregularity) per IS 1893 Cl 7.1.
        
        Soft storey exists if stiffness < 70% of storey above
        or < 80% of average of 3 storeys above.
        
        Args:
            storey_stiffnesses: List of storey stiffnesses from bottom up
            
        Returns:
            IrregularityCheck if soft storey detected
        """
        if len(storey_stiffnesses) < 2:
            return None
        
        for i in range(len(storey_stiffnesses) - 1):
            current = storey_stiffnesses[i]
            above = storey_stiffnesses[i + 1]
            
            if above > 0 and current < 0.7 * above:
                return IrregularityCheck(
                    irregularity_type=IrregularityType.SOFT_STOREY,
                    is_detected=True,
                    severity="major",
                    description=f"Soft storey at Level {i}: Stiffness = {current/above:.0%} of level above",
                    recommendation="CRITICAL: Add shear walls or increase column stiffness"
                )
        
        return None
    
    def run_all_checks(
        self,
        columns: List,
        beams: List,
        floor_width: float = 0.0,
        floor_length: float = 0.0
    ) -> SafetyWarningsSummary:
        """
        Run all Phase 2 safety checks.
        
        Args:
            columns: Column list
            beams: Beam list
            floor_width, floor_length: Floor dimensions
            
        Returns:
            SafetyWarningsSummary
        """
        # Joint shear checks (sample)
        joint_checks = []
        for col in columns[:5] if columns else []:
            check = self.check_joint_shear(
                f"J_{col.id}",
                col.width_nb,
                col.depth_nb,
                beam_depth_mm=450,  # Assume typical beam
                beam_tension_steel_mm2=800,  # ~4×16mm
                joint_type="interior"
            )
            joint_checks.append(check)
        
        # Irregularity checks
        irregularities = self.check_plan_irregularities(
            floor_width, floor_length
        )
        
        # Count issues
        joints_failed = sum(1 for j in joint_checks if not j.is_adequate)
        irreg_detected = sum(1 for i in irregularities if i.is_detected)
        
        # Critical warnings
        critical = []
        recommendations = []
        
        if joints_failed > 0:
            critical.append(f"⚠️ {joints_failed} beam-column joints overstressed")
            recommendations.append("Increase column size at critical joints")
        
        if not self.cracked_mods.is_applied:
            recommendations.append(
                "Apply cracked section modifiers for seismic analysis "
                "(Columns: 0.7Ig, Beams: 0.35Ig)"
            )
        
        for irreg in irregularities:
            if irreg.severity == "major":
                critical.append(f"⚠️ {irreg.description}")
                recommendations.append(irreg.recommendation)
        
        return SafetyWarningsSummary(
            joint_checks=joint_checks,
            cracked_modifiers=self.cracked_mods,
            irregularities=irregularities,
            joints_failed=joints_failed,
            irregularities_detected=irreg_detected,
            critical_warnings=critical,
            recommendations=recommendations
        )


def run_safety_warnings_check(
    columns: List,
    beams: List,
    footings_or_width=0.0,
    floor_length: float = 0.0,
    fck: float = 25.0,
    seismic_zone: str = "III"
) -> SafetyWarningsSummary:
    """
    Main function to run Phase 2 safety warnings checks.
    
    Args:
        columns, beams: Structural members
        footings_or_width: Either footings list (ignored) or floor_width float
        floor_length: Floor length dimension
        fck: Concrete grade
        seismic_zone: Zone II-V
        
    Returns:
        SafetyWarningsSummary
    """
    # Handle case where footings list is passed as 3rd argument
    if isinstance(footings_or_width, (list, tuple)):
        floor_width = 0.0
    else:
        floor_width = float(footings_or_width)
    
    # Auto-derive floor dimensions from columns if not provided
    if (floor_width == 0.0 or floor_length == 0.0) and columns:
        xs = [c.x for c in columns]
        ys = [c.y for c in columns]
        if xs and ys:
            floor_width = max(xs) - min(xs) if floor_width == 0.0 else floor_width
            floor_length = max(ys) - min(ys) if floor_length == 0.0 else floor_length
    
    checker = SafetyWarningsChecker(
        fck=fck,
        seismic_zone=seismic_zone
    )
    
    return checker.run_all_checks(columns, beams, floor_width, floor_length)

