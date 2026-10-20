"""
Seismic Design Module - IS 1893:2016 & IS 13920:2016

Implements:
- Seismic zone factors and response reduction
- Strong Column-Weak Beam (SCWB) verification
- Ductile detailing requirements (confining reinforcement)
- Floating column detection and warnings
- Irregularity checks

Reference:
- IS 1893 (Part 1): 2016 - Seismic Design Criteria
- IS 13920: 2016 - Ductile Detailing of RCC Structures

DISCLAIMER: All seismic designs must be verified by a licensed
Structural Engineer before construction.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from enum import Enum
import math


class SeismicZone(str, Enum):
    """Seismic zones of India per IS 1893:2016."""
    ZONE_II = "II"    # Low damage risk
    ZONE_III = "III"  # Moderate damage risk
    ZONE_IV = "IV"    # High damage risk
    ZONE_V = "V"      # Very high damage risk


class StructuralSystem(str, Enum):
    """Structural system types per IS 1893 Table 9."""
    ORDINARY_MOMENT_FRAME = "OMF"     # R = 3
    SPECIAL_MOMENT_FRAME = "SMF"      # R = 5
    DUAL_SYSTEM = "DUAL"              # R = 4
    SHEAR_WALL = "SW"                 # R = 4


@dataclass
class SeismicParameters:
    """Seismic design parameters per IS 1893:2016."""
    zone: SeismicZone
    zone_factor: float              # Z (Table 3)
    importance_factor: float        # I (Table 8)
    response_reduction: float       # R (Table 9)
    soil_type: str                  # I, II, or III
    
    # Calculated
    fundamental_period: float = 0.0   # Ta (sec)
    design_acceleration: float = 0.0  # Ah = (Z/2) × (I/R) × Sa/g
    base_shear_coefficient: float = 0.0
    
    # Requirements
    min_concrete_grade: int = 20
    ductile_detailing_required: bool = False
    scwb_required: bool = False


# IS 1893:2016 Table 3 - Zone Factors
ZONE_FACTORS = {
    SeismicZone.ZONE_II: 0.10,
    SeismicZone.ZONE_III: 0.16,
    SeismicZone.ZONE_IV: 0.24,
    SeismicZone.ZONE_V: 0.36,
}

# IS 1893 (Part 1):2016 Table 7 - minimum design lateral force (VB)min = rho W (7.2.2; checked 2026-10-20)
MIN_BASE_SHEAR_FRACTION = {
    SeismicZone.ZONE_II: 0.007,
    SeismicZone.ZONE_III: 0.011,
    SeismicZone.ZONE_IV: 0.016,
    SeismicZone.ZONE_V: 0.024,
}

# IS 1893:2016 Table 9 - Response Reduction Factors
RESPONSE_REDUCTION = {
    StructuralSystem.ORDINARY_MOMENT_FRAME: 3.0,
    StructuralSystem.SPECIAL_MOMENT_FRAME: 5.0,
    StructuralSystem.DUAL_SYSTEM: 4.0,
    StructuralSystem.SHEAR_WALL: 4.0,
}

# Importance Factors (IS 1893 Table 8) - keyword lookup (legacy)
IMPORTANCE_FACTORS = {
    "residential": 1.0,
    "commercial": 1.2,
    "school": 1.5,
    "hospital": 1.5,
    "emergency": 1.5,
    "institutional": 1.5,
    "assembly": 1.5,
}

# Default importance factor per StructOptima occupancy (building_types names).
# Conservative defaults chosen during the 2026-10 remediation (PROPOSED
# decision D-03) - verify against IS 1893 (Part 1):2016 Table 8 for the actual
# occupancy / number of occupants.
OCCUPANCY_IMPORTANCE = {
    "residential": 1.0,
    "commercial (office)": 1.2,
    "commercial (retail/shopping)": 1.5,
    "institutional": 1.5,
    "assembly hall": 1.5,
}


def importance_for_occupancy(name: str) -> float:
    key = (name or "").strip().lower()
    if key in OCCUPANCY_IMPORTANCE:
        return OCCUPANCY_IMPORTANCE[key]
    for k, v in IMPORTANCE_FACTORS.items():
        if k in key:
            return v
    return 1.0


def structural_system_from(value) -> "StructuralSystem":
    if isinstance(value, StructuralSystem):
        return value
    v = str(value or "OMRF").upper()
    if v in ("SMF", "SMRF"):
        return StructuralSystem.SPECIAL_MOMENT_FRAME
    if v == "DUAL":
        return StructuralSystem.DUAL_SYSTEM
    if v in ("SW", "SHEAR_WALL"):
        return StructuralSystem.SHEAR_WALL
    return StructuralSystem.ORDINARY_MOMENT_FRAME


@dataclass
class SCWBCheck:
    """Strong Column-Weak Beam check result."""
    joint_id: str
    column_moment_capacity_kNm: float
    beam_moment_capacity_kNm: float
    ratio: float  # Should be >= 1.4
    is_compliant: bool
    remarks: str


@dataclass
class DuctileDetailingCheck:
    """Ductile detailing check for plastic hinge zones."""
    member_id: str
    member_type: str  # column or beam
    
    # Plastic hinge zone
    hinge_zone_length_mm: float
    
    # Stirrup requirements
    max_stirrup_spacing_mm: float
    min_stirrup_dia_mm: int
    required_legs: int
    
    # Actual vs Required
    actual_spacing_mm: float
    is_compliant: bool
    remarks: str


@dataclass
class FloatingColumnCheck:
    """Check for floating columns (columns on beams)."""
    column_id: str
    is_floating: bool
    supporting_beam_id: Optional[str]
    transfer_load_kn: float
    warning: str


class IrregularityType(str, Enum):
    """Plan and vertical irregularity types per IS 1893 Tables 5 & 6."""
    # Plan irregularities (Table 5)
    TORSION = "Torsion"
    RE_ENTRANT_CORNER = "Re-entrant Corner"
    FLOOR_OPENING = "Floor Opening"
    OUT_OF_PLANE_OFFSET = "Out-of-Plane Offset"
    NON_PARALLEL_SYSTEM = "Non-Parallel System"
    # Vertical irregularities (Table 6)
    SOFT_STOREY = "Soft Storey"
    MASS_IRREGULARITY = "Mass Irregularity"
    VERTICAL_GEOMETRIC = "Vertical Geometric"
    IN_PLANE_DISCONTINUITY = "In-Plane Discontinuity"
    WEAK_STOREY = "Weak Storey"


class AnalysisMethod(str, Enum):
    """Seismic analysis methods per IS 1893."""
    EQUIVALENT_STATIC = "ESA"  # Equivalent Static Analysis
    RESPONSE_SPECTRUM = "RSA"  # Response Spectrum Analysis
    TIME_HISTORY = "THA"       # Time History Analysis


@dataclass
class IrregularityCheck:
    """Result of irregularity check."""
    irregularity_type: IrregularityType
    is_irregular: bool
    severity: str  # "None", "Moderate", "Severe"
    value: float   # Measured value (e.g., re-entrant corner percentage)
    limit: float   # Code limit
    recommendation: str


@dataclass
class SeismicWeightResult:
    """Seismic weight calculation per IS 1893."""
    total_dead_load_kn: float
    total_live_load_kn: float
    live_load_intensity_kn_m2: float
    ll_reduction_factor: float  # 0.25 or 0.50 per IS 1893 Cl. 7.4.3
    effective_live_load_kn: float
    seismic_weight_kn: float
    code_reference: str


@dataclass
class AnalysisMethodCheck:
    """Check for required analysis method."""
    required_method: AnalysisMethod
    irregularities_found: List[IrregularityType]
    static_allowed: bool
    reason: str


@dataclass
class SeismicAnalysisResult:
    """Complete seismic analysis result."""
    parameters: SeismicParameters
    
    # Seismic weight (with LL reduction)
    seismic_weight: Optional[SeismicWeightResult] = None
    
    # Base shear
    building_weight_kn: float = 0.0
    base_shear_kn: float = 0.0
    
    # Irregularity checks
    irregularity_checks: List[IrregularityCheck] = field(default_factory=list)
    analysis_method_check: Optional[AnalysisMethodCheck] = None
    
    # Checks
    scwb_checks: List[SCWBCheck] = field(default_factory=list)
    ductile_checks: List[DuctileDetailingCheck] = field(default_factory=list)
    floating_columns: List[FloatingColumnCheck] = field(default_factory=list)
    
    # Summary
    all_scwb_pass: bool = True
    all_ductile_pass: bool = True
    has_floating_columns: bool = False
    is_regular: bool = True
    static_analysis_allowed: bool = True
    system_permitted: bool = True             # IS 1893 Table 9 Note 1 (OMRF not allowed in Zones III-V)
    
    # Storey forces (equivalent static vertical distribution)
    height_m: float = 0.0
    storey_weights_kn: List[float] = field(default_factory=list)
    storey_heights_m: List[float] = field(default_factory=list)
    storey_forces_kn: List[float] = field(default_factory=list)

    # Design-based joint checks (filled by evaluate_joint_checks)
    scwb_details: List[dict] = field(default_factory=list)
    joint_details: List[dict] = field(default_factory=list)
    scwb_evaluated: bool = False
    ductile_verification: str = "NOT_EVALUATED"   # NOT_EVALUATED | PARTIAL_SPACING_ONLY | NOT_REQUIRED

    # Warnings
    warnings: List[str] = field(default_factory=list)


class SeismicDesignChecker:
    """
    IS 1893:2016 and IS 13920:2016 Seismic Design Checker.
    
    Performs:
    1. Seismic zone classification and design parameters
    2. Strong Column-Weak Beam verification
    3. Ductile detailing requirements
    4. Floating column detection
    """
    
    def __init__(
        self,
        zone: SeismicZone,
        building_type: str = "residential",
        structural_system: StructuralSystem = StructuralSystem.SPECIAL_MOMENT_FRAME,
        soil_type: str = "II",
        fck: float = 25.0,
        fy: float = 415.0,
        importance_factor: Optional[float] = None
    ):
        self.zone = zone
        self.building_type = building_type
        self.importance_override = importance_factor
        self.structural_system = structural_system_from(structural_system)
        self.soil_type = soil_type
        self.fck = fck
        self.fy = fy
        
        # Calculate parameters
        self.params = self._calculate_parameters()
    
    def _calculate_parameters(self) -> SeismicParameters:
        """Calculate seismic design parameters per IS 1893."""
        Z = ZONE_FACTORS[self.zone]
        I = self.importance_override if self.importance_override else importance_for_occupancy(self.building_type)
        R = RESPONSE_REDUCTION[self.structural_system]
        
        # Spectral acceleration coefficient (simplified for T < 0.55s)
        # For typical low-rise (G+5), assume Sa/g = 2.5 (rock/hard soil)
        Sa_g = 2.5
        
        # Design horizontal acceleration
        Ah = (Z / 2) * (I / R) * Sa_g
        
        # Requirements based on zone
        min_grade = 20
        ductile_required = False
        scwb_required = False
        
        if self.zone in [SeismicZone.ZONE_III, SeismicZone.ZONE_IV, SeismicZone.ZONE_V]:
            ductile_required = True
            scwb_required = True
            # minimum grade depends on height (IS 13920 5.2) - set in run_full_analysis
        
        return SeismicParameters(
            zone=self.zone,
            zone_factor=Z,
            importance_factor=I,
            response_reduction=R,
            soil_type=self.soil_type,
            design_acceleration=Ah,
            base_shear_coefficient=Ah,
            min_concrete_grade=min_grade,
            ductile_detailing_required=ductile_required,
            scwb_required=scwb_required,
            fundamental_period=0.0 # Will be refined with height
        )
    
    # Design spectrum for equivalent static analysis, IS 1893 (Part 1):2016
    # (transcribed - verify): soil type -> (plateau end T, numerator, floor)
    SPECTRUM = {"I": (0.40, 1.00, 0.25), "II": (0.55, 1.36, 0.34), "III": (0.67, 1.67, 0.42)}

    def get_spectral_acceleration(self, Ta: float, soil_type: Optional[str] = None, method: str = "static") -> float:
        """Sa/g, IS 1893 (Part 1):2016 6.4.2: (a) equivalent static method - 2.5 from T = 0 to the end of the
        plateau; (b) response spectrum method - rising branch 1 + 15 T below 0.10 s (finding S1: the static
        method used to take the rising branch, under-estimating Vb for stiff buildings)."""
        t_end, num, floor = self.SPECTRUM.get(str(soil_type or self.soil_type or "II").upper(), self.SPECTRUM["II"])
        if method == "response_spectrum" and Ta < 0.10:
            return 1.0 + 15.0 * Ta
        if Ta <= t_end:
            return 2.5
        if Ta <= 4.0:
            return num / Ta
        return floor
        
    def calculate_base_shear(self, building_weight_kn: float, height_m: float = 9.0,
                             base_dimension_m: Optional[float] = None, masonry_infill: bool = False) -> float:
        """
        Calculate design base shear per IS 1893.
        Updates internal params with actual Ta and Ah.
        
        Ta = 0.075 * h^0.75 (RC Moment Resisting Frame) // IS 1893 Cl 7.6.1
        Vb = Ah × W
        """
        # 1. Fundamental period: bare RC MRF 0.075 h^0.75; with masonry infill the
        # code also gives 0.09 h / sqrt(d).  The SHORTER period is used (Sa/g
        # equal or larger) - assumption A-SEI-02.
        ta = 0.075 * (height_m ** 0.75)
        if masonry_infill and base_dimension_m and base_dimension_m > 0:
            ta = min(ta, 0.09 * height_m / math.sqrt(base_dimension_m))
        self.params.fundamental_period = ta
        
        # 2. Get Sa/g
        sa_g = self.get_spectral_acceleration(self.params.fundamental_period)
        
        # 3. Recalculate Ah
        # Ah = (Z/2) * (I/R) * (Sa/g)
        Z = self.params.zone_factor
        I = self.params.importance_factor
        R = self.params.response_reduction
        
        self.params.design_acceleration = (Z / 2) * (I / R) * sa_g
        
        # 4. Base shear, not less than (VB)min = rho W (7.2.2, Table 7; finding S3)
        vb = self.params.design_acceleration * building_weight_kn
        vb_min = MIN_BASE_SHEAR_FRACTION[self.zone] * building_weight_kn
        self.minimum_base_shear_governs = vb_min > vb
        return max(vb, vb_min)
    
    def check_strong_column_weak_beam(
        self,
        column_moment_capacity_kNm: float,
        beam_moment_capacity_kNm: float,
        joint_id: str = "J1"
    ) -> SCWBCheck:
        """
        Check Strong Column-Weak Beam criterion per IS 13920.
        
        ΣMc ≥ 1.4 × ΣMb
        
        Args:
            column_moment_capacity_kNm: Sum of column capacities at joint
            beam_moment_capacity_kNm: Sum of beam capacities at joint
            joint_id: Joint identifier
            
        Returns:
            SCWBCheck result
        """
        if beam_moment_capacity_kNm <= 0:
            ratio = float('inf')
            is_compliant = True
            remarks = "No beams at joint"
        else:
            ratio = column_moment_capacity_kNm / beam_moment_capacity_kNm
            is_compliant = ratio >= 1.4
            
            if is_compliant:
                remarks = f"OK (≥1.4)"
            else:
                remarks = f"FAIL: Ratio {ratio:.2f} < 1.4. Increase column capacity or reduce beam."
        
        return SCWBCheck(
            joint_id=joint_id,
            column_moment_capacity_kNm=column_moment_capacity_kNm,
            beam_moment_capacity_kNm=beam_moment_capacity_kNm,
            ratio=ratio,
            is_compliant=is_compliant,
            remarks=remarks
        )
    
    def calculate_column_moment_capacity(
        self,
        width_mm: float,
        depth_mm: float,
        axial_load_kn: float,
        ast_mm2: float
    ) -> float:
        """
        Estimate column moment capacity (simplified).
        
        Mu ≈ 0.87 × fy × Ast × (d - 0.42*xu)
        
        For simplicity, use interaction curve point at ~0.4Pu.
        Note: This is a simplified approximation. Rigorous P-M interaction analysis is needed for final design.
        """
        d = depth_mm - 50  # Effective depth
        
        # Simplified: Mu ≈ 0.5 × Ast × fy × d × 10^-6
        Mu = 0.5 * ast_mm2 * self.fy * d * 1e-6  # kNm
        
        return Mu
    
    def calculate_beam_moment_capacity(
        self,
        width_mm: float,
        depth_mm: float,
        ast_mm2: float
    ) -> float:
        """
        Calculate beam moment capacity (simplified).
        
        Mu = 0.87 × fy × Ast × (d - 0.42*xu)
        For under-reinforced: Mu ≈ 0.87 × fy × Ast × 0.9d
        """
        d = depth_mm - 50
        
        Mu = 0.87 * self.fy * ast_mm2 * 0.9 * d * 1e-6  # kNm
        
        return Mu
    
    def get_ductile_detailing_requirements(
        self,
        member_type: str,
        depth_mm: float,
        width_mm: float
    ) -> DuctileDetailingCheck:
        """
        Get ductile detailing requirements per IS 13920.
        
        Plastic hinge zone = 2D from column face (beams)
        Stirrup spacing = min(d/4, 8×db, 100mm)
        
        Args:
            member_type: "column" or "beam"
            depth_mm: Member depth
            width_mm: Member width
            
        Returns:
            DuctileDetailingCheck with requirements
        """
        d = depth_mm - 50  # Effective depth
        
        if member_type == "column":
            # IS 13920 Cl 7.4 - Columns
            hinge_zone = max(depth_mm, width_mm, 450)  # lo
            max_spacing = min(width_mm / 4, 6 * 16, 100)  # Assuming 16mm bars
            min_dia = 8
            legs = max(2, int(width_mm / 150))
        else:
            # IS 13920 Cl 6.3 - Beams
            hinge_zone = 2 * depth_mm  # 2d from column face
            max_spacing = min(d / 4, 8 * 12, 100)  # Assuming 12mm bars
            min_dia = 8
            legs = 2
        
        return DuctileDetailingCheck(
            member_id="",
            member_type=member_type,
            hinge_zone_length_mm=hinge_zone,
            max_stirrup_spacing_mm=max_spacing,
            min_stirrup_dia_mm=min_dia,
            required_legs=legs,
            actual_spacing_mm=150,  # Will be updated
            is_compliant=True,  # Will be updated
            remarks=f"Plastic hinge zone: {hinge_zone:.0f}mm, max spacing: {max_spacing:.0f}mm"
        )
    
    def detect_floating_columns(
        self,
        columns: List,
        beams: List
    ) -> List[FloatingColumnCheck]:
        """
        Detect floating columns (columns that don't continue to foundation).
        
        A floating column is one that starts above ground level and
        is supported by a beam instead of the foundation.
        
        Args:
            columns: List of Column objects
            beams: List of beam objects
            
        Returns:
            List of FloatingColumnCheck results
        """
        results = []
        
        # Group columns by (x, y) location
        locations = {}
        for col in columns:
            key = (round(col.x, 2), round(col.y, 2))
            if key not in locations:
                locations[key] = []
            locations[key].append(col)
        
        # Check each location
        for loc_key, col_stack in locations.items():
            # Sort by level
            col_stack.sort(key=lambda c: c.level)
            
            # Check if ground level (0) column exists
            has_ground = any(c.level == 0 for c in col_stack)
            
            flagged = any(getattr(c, "is_floating", False) for c in col_stack)
            if (not has_ground or flagged) and len(col_stack) > 0:
                # This is a floating column stack
                first_col = col_stack[0]
                results.append(FloatingColumnCheck(
                    column_id=first_col.id,
                    is_floating=True,
                    supporting_beam_id="Unknown",
                    transfer_load_kn=first_col.load_kn,
                    warning=f"⚠️ FLOATING COLUMN at ({loc_key[0]}, {loc_key[1]}). "
                           f"Starts at Level {first_col.level}. "
                           f"Verify transfer beam capacity for {first_col.load_kn:.0f} kN."
                ))
        
        return results
    
    def calculate_seismic_weight(
        self,
        dead_load_kn: float,
        live_load_kn: float,
        live_load_intensity_kn_m2: float,
        is_roof_level: bool = False
    ) -> SeismicWeightResult:
        """
        Calculate seismic weight per IS 1893 Cl. 7.4.3.
        
        Seismic Weight W = Full DL + (Reduction Factor × LL)
        
        Live Load Reduction:
        - 0% for roof level
        - 25% of LL if live load intensity ≤ 3.0 kN/m²
        - 50% of LL if live load intensity > 3.0 kN/m²
        
        Args:
            dead_load_kn: Total dead load in kN
            live_load_kn: Total live load in kN
            live_load_intensity_kn_m2: Live load per unit area
            is_roof_level: Whether this calculation is for the roof
            
        Returns:
            SeismicWeightResult with calculation details
        """
        if is_roof_level:
            ll_factor = 0.0
            code_ref = "IS 1893 Table 10: Roof LL not included (0%)"
        elif live_load_intensity_kn_m2 <= 3.0:
            ll_factor = 0.25
            code_ref = "IS 1893 Cl. 7.4.3: 25% LL (intensity ≤ 3.0 kN/m²)"
        else:
            ll_factor = 0.50
            code_ref = "IS 1893 Cl. 7.4.3: 50% LL (intensity > 3.0 kN/m²)"
        
        effective_ll = live_load_kn * ll_factor
        seismic_weight = dead_load_kn + effective_ll
        
        return SeismicWeightResult(
            total_dead_load_kn=dead_load_kn,
            total_live_load_kn=live_load_kn,
            live_load_intensity_kn_m2=live_load_intensity_kn_m2,
            ll_reduction_factor=ll_factor,
            effective_live_load_kn=effective_ll,
            seismic_weight_kn=seismic_weight,
            code_reference=code_ref
        )
    
    def check_irregularities(
        self,
        floor_width_m: float,
        floor_length_m: float,
        opening_area_m2: float = 0.0,
        re_entrant_x_m: float = 0.0,
        re_entrant_y_m: float = 0.0,
        storey_stiffnesses: List[float] = None,
        storey_masses: List[float] = None
    ) -> List[IrregularityCheck]:
        """
        Check for plan and vertical irregularities per IS 1893 Tables 5 & 6.
        
        Args:
            floor_width_m: Floor plan width
            floor_length_m: Floor plan length
            opening_area_m2: Total floor opening area
            re_entrant_x_m: Re-entrant corner dimension in X
            re_entrant_y_m: Re-entrant corner dimension in Y
            storey_stiffnesses: List of storey stiffnesses (for soft storey)
            storey_masses: List of storey masses (for mass irregularity)
            
        Returns:
            List of IrregularityCheck results
        """
        results = []
        floor_area = floor_width_m * floor_length_m
        
        # 1. Re-entrant Corner Check (IS 1893 Table 5, Item 2)
        # Irregular if projection > 15% of plan dimension
        if re_entrant_x_m > 0 or re_entrant_y_m > 0:
            x_ratio = re_entrant_x_m / floor_width_m if floor_width_m > 0 else 0
            y_ratio = re_entrant_y_m / floor_length_m if floor_length_m > 0 else 0
            max_ratio = max(x_ratio, y_ratio) * 100
            
            is_irregular = max_ratio > 15.0
            severity = "Severe" if max_ratio > 25 else ("Moderate" if is_irregular else "None")
            
            results.append(IrregularityCheck(
                irregularity_type=IrregularityType.RE_ENTRANT_CORNER,
                is_irregular=is_irregular,
                severity=severity,
                value=max_ratio,
                limit=15.0,
                recommendation="Use Response Spectrum Analysis" if is_irregular else "OK"
            ))
        
        # 2. Floor Opening Check (IS 1893 Table 5, Item 3)
        # Irregular if opening > 50% of floor area
        if opening_area_m2 > 0:
            opening_ratio = (opening_area_m2 / floor_area) * 100 if floor_area > 0 else 0
            
            is_irregular = opening_ratio > 50.0
            severity = "Severe" if opening_ratio > 60 else ("Moderate" if is_irregular else "None")
            
            results.append(IrregularityCheck(
                irregularity_type=IrregularityType.FLOOR_OPENING,
                is_irregular=is_irregular,
                severity=severity,
                value=opening_ratio,
                limit=50.0,
                recommendation="Diaphragm flexibility analysis required" if is_irregular else "OK"
            ))
        
        # 3. Soft Storey Check (IS 1893 Table 6, Item 1)
        # Irregular if storey stiffness < that of the storey above (Table 6(i), Amendment 2)
        if storey_stiffnesses and len(storey_stiffnesses) > 1:
            for i in range(len(storey_stiffnesses) - 1):
                k_current = storey_stiffnesses[i]
                k_above = storey_stiffnesses[i + 1]
                
                if k_above > 0:
                    ratio = (k_current / k_above) * 100
                    is_irregular = ratio < 100.0  # IS 1893:2016 Table 6(i) as amended (Amd 2)
                    severity = "Severe" if ratio < 40 else ("Moderate" if is_irregular else "None")
                    
                    if is_irregular:
                        results.append(IrregularityCheck(
                            irregularity_type=IrregularityType.SOFT_STOREY,
                            is_irregular=True,
                            severity=severity,
                            value=ratio,
                            limit=100.0,
                            recommendation=f"Storey {i}: Increase stiffness or use 3D analysis"
                        ))
        
        # 4. Mass Irregularity Check (IS 1893 Table 6, Item 2)
        # Irregular if mass > 150% of adjacent storey
        if storey_masses and len(storey_masses) > 1:
            for i in range(1, len(storey_masses)):
                m_current = storey_masses[i]
                m_below = storey_masses[i - 1]
                
                if m_below > 0:
                    ratio = (m_current / m_below) * 100
                    if ratio > 150.0:
                        results.append(IrregularityCheck(
                            irregularity_type=IrregularityType.MASS_IRREGULARITY,
                            is_irregular=True,
                            severity="Moderate" if ratio < 200 else "Severe",
                            value=ratio,
                            limit=150.0,
                            recommendation=f"Storey {i}: Mass > 150% of storey below"
                        ))
        
        return results
    
    def check_analysis_method(
        self,
        irregularities: List[IrregularityCheck],
        num_stories: int,
        building_height_m: float
    ) -> AnalysisMethodCheck:
        """
        Determine required analysis method based on irregularities and building size.
        
        IS 1893 (Part 1):2016 7.6 and 7.7.1: the equivalent static method applies only to regular buildings
        lower than 15 m in Seismic Zone II; linear dynamic analysis is required for all other buildings
        (finding S4: the previous limits, 40 m in Zones II/III and 12 m in IV/V, were from the 2002 edition).
        
        Args:
            irregularities: List of irregularity check results
            num_stories: Number of stories
            building_height_m: Total building height
            
        Returns:
            AnalysisMethodCheck with required method and whether static is allowed
        """
        irregular_types = [ir.irregularity_type for ir in irregularities if ir.is_irregular]
        
        static_allowed = True
        reasons = []
        if self.zone != SeismicZone.ZONE_II:
            static_allowed = False
            reasons.append(f"Zone {self.zone.value}")
        if building_height_m >= 15.0:
            static_allowed = False
            reasons.append(f"height {building_height_m:.1f} m (not lower than 15 m)")
        if irregular_types:
            static_allowed = False
            reasons.append(f"irregular: {', '.join(ir.value for ir in irregular_types)}")

        if static_allowed:
            required_method = AnalysisMethod.EQUIVALENT_STATIC
            reason = "Equivalent static method permitted: regular building lower than 15 m in Zone II (IS 1893 7.7.1)"
        else:
            required_method = AnalysisMethod.RESPONSE_SPECTRUM
            reason = ("Dynamic analysis required by IS 1893 (Part 1):2016 7.7.1 (" + "; ".join(reasons) + "). The "
                      "equivalent static method is permitted only for regular buildings lower than 15 m in Zone II")
        
        return AnalysisMethodCheck(
            required_method=required_method,
            irregularities_found=irregular_types,
            static_allowed=static_allowed,
            reason=reason
        )


    def run_full_analysis(
        self,
        columns: List,
        beams: List,
        building_weight_kn: float,
        height_m: float = 9.0,
        storey_weights_kn: Optional[List[float]] = None,
        storey_heights_m: Optional[List[float]] = None,
        base_dimension_m: Optional[float] = None,
        masonry_infill: bool = False,
        plan_width_m: float = 0.0,
        plan_length_m: float = 0.0,
        plan_area_m2: Optional[float] = None,
    ) -> SeismicAnalysisResult:
        """Base shear, vertical distribution, regularity screening and
        floating-column detection.  Strong-column/weak-beam, joint shear and
        ductile detailing are evaluated from the designed members by
        :func:`evaluate_joint_checks` (placeholders before the 2026-10
        remediation, audit finding R15)."""
        base_shear = self.calculate_base_shear(building_weight_kn, height_m, base_dimension_m, masonry_infill)

        # Vertical distribution Qi = Vb Wi hi^2 / sum(Wj hj^2)
        forces: List[float] = []
        if storey_weights_kn and storey_heights_m:
            denom = sum(w * h * h for w, h in zip(storey_weights_kn, storey_heights_m))
            forces = [base_shear * w * h * h / denom if denom > 0 else 0.0
                      for w, h in zip(storey_weights_kn, storey_heights_m)]

        floating = self.detect_floating_columns(columns, beams)
        warnings: List[str] = []
        self.params.min_concrete_grade = min_concrete_grade(self.zone, height_m)
        if self.fck < self.params.min_concrete_grade:
            warnings.append(f"Concrete grade M{int(self.fck)} below minimum M{self.params.min_concrete_grade} "
                            f"for Zone {self.zone.value}")
        if floating:
            warnings.append(f"{len(floating)} floating column(s) detected. Verify transfer beam capacity.")
        if self.structural_system == StructuralSystem.SPECIAL_MOMENT_FRAME:
            warnings.append("R = 5 (SMRF) assumes full IS 13920 ductile detailing. StructOptima provides end-zone "
                            "tie/stirrup spacing only (confining steel Ash and capacity-design shear are NOT checked) - "
                            "an engineer must verify IS 13920 compliance before relying on R = 5.")
        system_permitted = not (self.structural_system == StructuralSystem.ORDINARY_MOMENT_FRAME
                                and self.zone != SeismicZone.ZONE_II)
        if not system_permitted:
            warnings.append(f"Ordinary moment frame (OMRF) is not allowed in Zone {self.zone.value}: RC structures in "
                            f"Zones III, IV and V shall be ductile (IS 1893 (Part 1):2016 Table 9, Note 1).")
        if getattr(self, "minimum_base_shear_governs", False):
            warnings.append(f"Minimum design lateral force governs: VB = {MIN_BASE_SHEAR_FRACTION[self.zone]:.1%} of W "
                            f"(IS 1893 7.2.2, Table 7).")

        irregularities: List[IrregularityCheck] = []
        if plan_width_m > 0 and plan_length_m > 0 and plan_area_m2 is not None:
            bbox = plan_width_m * plan_length_m
            if plan_area_m2 < 0.95 * bbox:
                proj = math.sqrt(max(bbox - plan_area_m2, 0.0))
                irregularities = self.check_irregularities(plan_width_m, plan_length_m,
                                                           re_entrant_x_m=proj, re_entrant_y_m=proj)
        # Table 6(ii): seismic weight of a floor > 150 % of the floor below (roof excluded: no floor above it
        # carries the comparison the other way; finding S6)
        if storey_weights_kn and len(storey_weights_kn) > 1:
            irregularities += self.check_irregularities(1.0, 1.0, storey_masses=list(storey_weights_kn))
        method = self.check_analysis_method(irregularities, len(storey_heights_m or []) or 1, height_m)
        if not method.static_allowed:
            warnings.append("Equivalent static method NOT permitted: " + method.reason +
                            ". StructOptima performs equivalent static analysis only - results are not valid for design.")

        return SeismicAnalysisResult(
            parameters=self.params,
            building_weight_kn=building_weight_kn,
            base_shear_kn=base_shear,
            irregularity_checks=irregularities,
            analysis_method_check=method,
            floating_columns=floating,
            has_floating_columns=len(floating) > 0,
            is_regular=not any(i.is_irregular for i in irregularities),
            static_analysis_allowed=method.static_allowed,
            system_permitted=system_permitted,
            height_m=height_m,
            storey_weights_kn=list(storey_weights_kn or []),
            storey_heights_m=list(storey_heights_m or []),
            storey_forces_kn=forces,
            warnings=warnings,
        )


def joint_confinement_factor(faces_with_beams: int) -> float:
    """IS 13920:2016 9.1.1 (Amendment 2): tau_jc = 1.5 sqrt(fck) for joints confined by beams on all four faces,
    1.2 sqrt(fck) on three faces, 1.0 sqrt(fck) for other joints (two opposite faces included; finding J1)."""
    return 1.5 if faces_with_beams >= 4 else (1.2 if faces_with_beams == 3 else 1.0)


def joint_effective_breadth(bb: float, bc: float, hc: float) -> float:
    """Effective breadth bj of a beam-column joint, IS 13920:2016 9.1.2(a) (Amendment 2).

    bc < bb: min[bb; bc + 0.5 hc] as printed. bc >= bb: the printed copy does not show this case in full; the
    mirror form min[bc; bb + 0.5 hc] is used (UNVERIFIED; more conservative than the previous bb + hc, finding J2).
    """
    if bc < bb:
        return min(bb, bc + 0.5 * hc)
    return min(bc, bb + 0.5 * hc)


def min_concrete_grade(zone: str, height_m: float) -> int:
    """IS 13920:2016 5.2: M20, but M25 for buildings more than 15 m in height in Zones III, IV and V (J4)."""
    z = zone.value if isinstance(zone, SeismicZone) else str(zone)
    return 25 if (z != "II" and height_m > 15.0) else 20


def _beam_capacity_knm(ast_mm2: float, b: float, d: float, fck: float, fy: float) -> float:
    """Flexural capacity of a singly reinforced rectangle from provided steel
    (xu limited to xu,max).  Slab steel and compression steel ignored."""
    from .section_design import xu_max_ratio
    if ast_mm2 <= 0 or d <= 0:
        return 0.0
    xu = min(0.87 * fy * ast_mm2 / (0.36 * fck * b), xu_max_ratio(fy) * d)
    return 0.36 * fck * b * xu * (d - 0.42 * xu) / 1e6


def evaluate_joint_checks(gm, beams, fck: float, fy: float, result: SeismicAnalysisResult) -> SeismicAnalysisResult:
    """Strong-column/weak-beam, joint shear and ductile tie spacing computed
    from the DESIGNED members (audit finding R15).

    * SCWB: sum Mc >= 1.4 sum Mb.  Mc = uniaxial capacity (strain
      compatibility) of the columns below and above the joint at the smallest
      factored axial load among their combinations.  Mb = beam capacities
      from provided steel for the worse sway sense (hogging on one side,
      sagging on the other).  Roof joints are checked in buildings of up to 4 storeys and waived above that
      (IS 13920 7.2.1.3; finding J3).
    * Joint shear: demand 1.25 fy (Ast_top + Ast_bot) of the framing beams with
      no deduction for column shear (conservative); capacity
      k sqrt(fck) Aj, k by ``joint_confinement_factor`` (9.1.1, Amd 2), Aj = bj x hc with bj by
      ``joint_effective_breadth`` (9.1.2(a), Amd 2).  Checked against the printed standard 2026-10-20.
    * Ductility: provided end-zone tie spacing vs min(b/4, 6 db, 100 mm);
      confining steel area (Ash) is NOT checked.
    """
    from . import section_design as sd
    TOLJ = 0.1
    cols_by_loc: Dict[Tuple[float, float], Dict[int, object]] = {}
    for c in gm.columns:
        cols_by_loc.setdefault((round(c.x, 2), round(c.y, 2)), {})[c.level] = c

    def beams_at(x, y, axis):
        out = []
        for bm in beams:
            if bm.end_point is None:
                continue
            p1, p2 = (bm.start_point.x, bm.start_point.y), (bm.end_point.x, bm.end_point.y)
            along_x = abs(p1[1] - p2[1]) < TOLJ
            if (axis == "x") != along_x:
                continue
            for p, q in ((p1, p2), (p2, p1)):
                if abs(p[0] - x) < TOLJ and abs(p[1] - y) < TOLJ:
                    side = 1 if ((q[0] > x) if axis == "x" else (q[1] > y)) else -1
                    out.append((bm, side))
        return out

    cap_cache: Dict[Tuple[str, str], float] = {}

    def col_capacity(col, axis):
        key = (col.id, axis)
        if key in cap_cache:
            return cap_cache[key]
        res = gm.rebar_schedule.get(col.id)
        val = 0.0
        if res is not None:
            n, dia = res.main_bars_desc.split("-")
            sec = sd.column_section(col.width_nb, col.depth_nb, int(n), int(dia.rstrip("#")), fck, fy)
            curve = sd.interaction_curve(sec, axis)
            pus = [f[1] for f in col.design_forces] or [col.load_kn * 1.5]
            val = min(sd.moment_capacity_at(p, curve) for p in pus)
        cap_cache[key] = val
        return val

    scwb, joints = [], []
    for (x, y), stack in cols_by_loc.items():
        top = gm.num_stories if gm.num_stories <= 4 else gm.num_stories - 1   # 7.2.1.3 roof waiver
        for lvl in range(1, top + 1):
            below, above = stack.get(lvl - 1), stack.get(lvl)
            if below is None:
                continue
            framing = {ax: beams_at(x, y, ax) for ax in ("x", "y")}
            n_faces = sum(len(v) for v in framing.values())
            k = joint_confinement_factor(n_faces)
            for ax in ("x", "y"):
                caps = []
                for bm, side in framing[ax]:
                    r = gm.get_beam_result(bm.id)
                    if r is None or not getattr(r, "width_mm", 0):
                        continue
                    d = r.depth_mm - getattr(gm, "beam_cover_mm", 25.0) - 8.0 - 8.0
                    caps.append((side, _beam_capacity_knm(r.ast_top_prov_mm2, r.width_mm, d, fck, fy),
                                 _beam_capacity_knm(r.ast_bottom_prov_mm2, r.width_mm, d, fck, fy), r))
                if not caps:
                    continue
                mc = col_capacity(below, ax) + (col_capacity(above, ax) if above is not None else 0.0)
                mb_a = sum(h for s, h, g, _ in caps if s > 0) + sum(g for s, h, g, _ in caps if s < 0)
                mb_b = sum(h for s, h, g, _ in caps if s < 0) + sum(g for s, h, g, _ in caps if s > 0)
                mb = max(mb_a, mb_b)
                ratio = mc / mb if mb > 0 else float("inf")
                jid = f"J_{below.id}_{ax.upper()}"
                scwb.append({"Joint": jid, "Level": lvl, "Direction": ax.upper(), "Sum Mc (kNm)": round(mc, 1),
                             "Sum Mb (kNm)": round(mb, 1), "Ratio": round(ratio, 2), "Required": 1.4,
                             "pass": ratio >= 1.4})
                tops = [r.ast_top_prov_mm2 for _, _, _, r in caps]
                bots = [r.ast_bottom_prov_mm2 for _, _, _, r in caps]
                ast_sum = max(tops) + (max(bots) if len(caps) > 1 else 0.0)
                vj = 1.25 * fy * ast_sum / 1000.0
                hc = below.width_nb if ax == "x" else below.depth_nb
                bc = below.depth_nb if ax == "x" else below.width_nb
                bb = max(r.width_mm for _, _, _, r in caps)
                aj = hc * joint_effective_breadth(bb, bc, hc)
                cap = k * math.sqrt(fck) * aj / 1000.0
                joints.append({"joint": jid, "level": lvl, "direction": ax.upper(), "confinement_factor": k,
                               "Vj_demand_kN": vj, "Vj_capacity_kN": cap,
                               "utilization": vj / cap if cap > 0 else float("inf"), "pass": vj <= cap})
    result.scwb_details = scwb
    result.joint_details = joints
    result.scwb_evaluated = True
    result.scwb_checks = [SCWBCheck(d["Joint"], d["Sum Mc (kNm)"], d["Sum Mb (kNm)"], d["Ratio"], d["pass"],
                                    "OK (>=1.4)" if d["pass"] else f"FAIL: ratio {d['Ratio']} < 1.4") for d in scwb]
    result.all_scwb_pass = all(d["pass"] for d in scwb) if scwb else True

    checks = []
    if result.parameters.ductile_detailing_required:
        for c in gm.columns:
            r = gm.rebar_schedule.get(c.id)
            if r is None:
                continue
            req_s = min(min(c.width_nb, c.depth_nb) / 4.0, 6 * r.phi_main, 100.0)
            lo = max(max(c.width_nb, c.depth_nb), (c.z_top - c.z_bottom) * 1000.0 / 6.0, 450.0)
            prov = r.hinge_spacing_mm if r.hinge_spacing_mm > 0 else r.link_spacing_mm
            checks.append(DuctileDetailingCheck(
                member_id=c.id, member_type="column", hinge_zone_length_mm=lo, max_stirrup_spacing_mm=req_s,
                min_stirrup_dia_mm=8, required_legs=max(2, int(min(c.width_nb, c.depth_nb) / 150)),
                actual_spacing_mm=prov, is_compliant=prov <= req_s + 1e-6,
                remarks="spacing check only - confining steel area (Ash) not verified"))
    result.ductile_checks = checks
    result.all_ductile_pass = all(c.is_compliant for c in checks) if checks else True
    result.ductile_verification = "PARTIAL_SPACING_ONLY" if checks else "NOT_REQUIRED"
    return result


def check_soft_storeys(storey_stiffnesses: List[float]) -> List["SoftStorey"]:
    """IS 1893 (Part 1):2016 Table 6(i) as amended (Amendment 2, 2020): a soft storey is a storey whose lateral
    stiffness is less than that of the storey above. ``storey_stiffnesses`` from the ground storey (index 0) up;
    finding S5 (the previous 70 % limit was from the 2002 edition)."""
    out = []
    for i in range(len(storey_stiffnesses) - 1):
        k, k_above = storey_stiffnesses[i], storey_stiffnesses[i + 1]
        if k_above > 0 and k < k_above * (1.0 - 1e-9):
            out.append(SoftStorey(storey=i, stiffness=k, stiffness_above=k_above))
    return out


@dataclass
class SoftStorey:
    storey: int                 # 0 = ground storey
    stiffness: float
    stiffness_above: float


def run_seismic_check(
    columns: List,
    beams: List,
    building_weight_kn: float,
    zone: str = "III",
    building_type: str = "residential",
    fck: float = 25.0,
    height_m: Optional[float] = None,
    soil_type: str = "II",
    structural_system="OMRF",
    importance_factor: Optional[float] = None,
    storey_weights_kn: Optional[List[float]] = None,
    storey_heights_m: Optional[List[float]] = None,
    base_dimension_m: Optional[float] = None,
    masonry_infill: bool = False,
    fy: float = 415.0,
    plan_width_m: float = 0.0,
    plan_length_m: float = 0.0,
    plan_area_m2: Optional[float] = None,
) -> SeismicAnalysisResult:
    """Equivalent static seismic analysis (IS 1893 Part 1:2016).

    ``height_m`` should always be supplied; when omitted it is derived from
    the highest column top (the old fixed 9 m default was audit finding R7)."""
    zone_map = {"II": SeismicZone.ZONE_II, "III": SeismicZone.ZONE_III,
                "IV": SeismicZone.ZONE_IV, "V": SeismicZone.ZONE_V}
    seismic_zone = zone_map.get(zone, SeismicZone.ZONE_III)
    if height_m is None:
        tops = [getattr(c, "z_top", 0.0) for c in columns]
        height_m = max(tops) if tops and max(tops) > 0 else 9.0
    checker = SeismicDesignChecker(zone=seismic_zone, building_type=building_type,
                                   structural_system=structural_system, soil_type=soil_type,
                                   fck=fck, fy=fy, importance_factor=importance_factor)
    return checker.run_full_analysis(columns, beams, building_weight_kn, height_m, storey_weights_kn,
                                     storey_heights_m, base_dimension_m, masonry_infill,
                                     plan_width_m, plan_length_m, plan_area_m2)


# Export zone list for UI
SEISMIC_ZONES = ["II", "III", "IV", "V"]
ZONE_DESCRIPTIONS = {
    "II": "Zone II - Low Seismic Risk",
    "III": "Zone III - Moderate Risk (Most of India)",
    "IV": "Zone IV - High Risk (Himalayan region)",
    "V": "Zone V - Very High Risk (NE India, Kashmir)",
}
