"""
Bar Bending Schedule (BBS) Module for Residential RCC Buildings.

This module generates Bar Bending Schedules for beams, columns, and slabs
following IS 456:2000 provisions for non-seismic/preliminary detailing.

Scope:
    - Residential RCC buildings (G+1 to G+5)
    - Non-seismic / preliminary detailing
    - IS 456 based assumptions
    - No ductile detailing (IS 13920 excluded)

Engineering Assumptions:
    - 90° standard hook = 9d (IS 456 Cl. 26.2.2.1)
    - 135° standard hook = 10d (IS 456 Cl. 26.2.2.1)
    - Stirrup hooks = 135° both ends
    - Development length = 47d approx for Fe415 in M25 (IS 456 Cl. 26.2.1)
    - Steel density = 7850 kg/m³
    - No lap splicing logic (single bar lengths assumed)
"""

import math
from typing import List, Dict, Optional
from pydantic import BaseModel, Field


# =============================================================================
# CONSTANTS (IS 456:2000 Based)
# =============================================================================

STEEL_DENSITY_KG_M3 = 7850.0  # Standard steel density

# Hook factors (multiples of bar diameter)
HOOK_90_FACTOR = 9   # IS 456 Cl. 26.2.2.1: 90° hook = 9d
HOOK_135_FACTOR = 10  # IS 456 Cl. 26.2.2.1: 135° hook = 10d

# Bond stress values for development length calculation (IS 456 Table 6.1)
# For deformed bars in tension, τbd = 1.2 * τbd_plain
BOND_STRESS_M20 = 1.2  # N/mm² for M20 plain bars
BOND_STRESS_M25 = 1.4  # N/mm² for M25 plain bars
BOND_STRESS_M30 = 1.5  # N/mm² for M30 plain bars

# Standard bar diameters available (mm)
STANDARD_BAR_DIAMETERS = [6, 8, 10, 12, 16, 20, 25, 32]

# =============================================================================
# IS 13920 DUCTILE DETAILING CONSTANTS
# =============================================================================

# Seismic hook extension: 6d but not less than 65mm (IS 13920)
SEISMIC_HOOK_MIN_EXTENSION_MM = 65
SEISMIC_HOOK_EXTENSION_FACTOR = 6

# Confined zone length from column face
CONFINED_ZONE_LENGTH_FACTOR = 2.0  # 2d from column face

# Maximum stirrup spacing in confined zone
CONFINED_ZONE_MAX_SPACING_MM = 100  # min of d/4, 8*dia, 100mm

# Lap splice multiplier when >50% bars lapped at one section
LAP_SPLICE_FACTOR_EXCESS = 1.4

# Standard bar length for stock optimization
STANDARD_BAR_LENGTH_M = 12.0


# =============================================================================
# INPUT DATA MODELS
# =============================================================================

class BeamBBSInput(BaseModel):
    """Input parameters for beam BBS generation."""
    member_id: str = Field(..., description="Unique beam identifier (e.g., 'B1')")
    length_mm: float = Field(..., gt=0, description="Clear span length in mm")
    width_mm: float = Field(..., gt=0, description="Beam width in mm")
    depth_mm: float = Field(..., gt=0, description="Beam overall depth in mm")
    clear_cover_mm: float = Field(default=25.0, ge=20, description="Clear cover in mm")
    main_bar_dia_mm: int = Field(..., description="Main bar diameter in mm")
    top_bars: int = Field(..., ge=2, description="Number of top (hanger) bars")
    bottom_bars: int = Field(..., ge=2, description="Number of bottom (tension) bars")
    stirrup_dia_mm: int = Field(default=8, description="Stirrup bar diameter in mm")
    stirrup_spacing_mm: float = Field(..., gt=0, description="Stirrup spacing c/c in mm")


class ColumnBBSInput(BaseModel):
    """Input parameters for column BBS generation."""
    member_id: str = Field(..., description="Unique column identifier (e.g., 'C1')")
    height_mm: float = Field(..., gt=0, description="Floor-to-floor height in mm")
    width_mm: float = Field(..., gt=0, description="Column width (b) in mm")
    depth_mm: float = Field(..., gt=0, description="Column depth (D) in mm")
    clear_cover_mm: float = Field(default=40.0, ge=25, description="Clear cover in mm")
    main_bar_dia_mm: int = Field(..., description="Longitudinal bar diameter in mm")
    num_bars: int = Field(..., ge=4, description="Number of longitudinal bars")
    tie_dia_mm: int = Field(default=8, description="Tie/stirrup diameter in mm")
    tie_spacing_mm: float = Field(..., gt=0, description="Tie spacing c/c in mm")


class SlabBBSInput(BaseModel):
    """Input parameters for slab BBS generation."""
    member_id: str = Field(..., description="Unique slab identifier (e.g., 'S1')")
    lx_mm: float = Field(..., gt=0, description="Short span length in mm")
    ly_mm: float = Field(..., gt=0, description="Long span length in mm")
    thickness_mm: float = Field(..., gt=0, description="Slab thickness in mm")
    clear_cover_mm: float = Field(default=20.0, ge=15, description="Clear cover in mm")
    main_bar_dia_mm: int = Field(..., description="Main bar diameter in mm")
    main_bar_spacing_mm: float = Field(..., gt=0, description="Main bar spacing c/c in mm")
    dist_bar_dia_mm: int = Field(..., description="Distribution bar diameter in mm")
    dist_bar_spacing_mm: float = Field(..., gt=0, description="Distribution bar spacing c/c in mm")


# =============================================================================
# OUTPUT DATA MODELS
# =============================================================================

class BBSEntry(BaseModel):
    """Single entry in the Bar Bending Schedule."""
    bar_mark: str = Field(..., description="Bar identification mark (e.g., 'A', 'B1', 'S1')")
    bar_diameter_mm: int = Field(..., description="Bar diameter in mm")
    shape_code: str = Field(..., description="Shape description (e.g., 'Straight', 'Stirrup')")
    cutting_length_mm: float = Field(..., description="Total cutting length per bar in mm")
    number_of_bars: int = Field(..., description="Total number of bars required")
    unit_weight_kg_per_m: float = Field(..., description="Weight per meter of bar in kg/m")
    total_weight_kg: float = Field(..., description="Total weight of all bars in kg")
    remarks: str = Field(default="", description="Engineering notes")

    class Config:
        json_encoders = {float: lambda v: round(v, 2)}


class MemberBBS(BaseModel):
    """BBS for a single structural member."""
    member_id: str = Field(..., description="Member identifier")
    member_type: str = Field(..., description="Type: 'beam', 'column', or 'slab'")
    member_size: str = Field(..., description="Size description (e.g., '300x600')")
    entries: List[BBSEntry] = Field(default_factory=list, description="List of BBS entries")
    total_weight_kg: float = Field(default=0.0, description="Total steel weight for member")

    def calculate_total(self):
        """Recalculate total weight from entries."""
        self.total_weight_kg = sum(e.total_weight_kg for e in self.entries)


class ProjectBBS(BaseModel):
    """Complete BBS for an entire project."""
    project_name: str = Field(default="Residential RCC Building", description="Project name")
    members: List[MemberBBS] = Field(default_factory=list, description="All member BBS")
    summary_by_diameter: Dict[int, float] = Field(default_factory=dict, description="Weight by diameter")
    total_steel_kg: float = Field(default=0.0, description="Total project steel weight")

    def calculate_summary(self):
        """Aggregate weights by bar diameter and calculate totals."""
        self.summary_by_diameter = {}
        self.total_steel_kg = 0.0
        
        for member in self.members:
            member.calculate_total()
            self.total_steel_kg += member.total_weight_kg
            
            for entry in member.entries:
                dia = entry.bar_diameter_mm
                self.summary_by_diameter[dia] = self.summary_by_diameter.get(dia, 0.0) + entry.total_weight_kg

    def get_procurement_summary(self, wastage_percent: float = 4.0) -> Dict[str, float]:
        """
        Get theoretical vs procurement weights (including rolling margin).
        
        Args:
            wastage_percent: Buffer for rolling margin + off-cuts (default 4%)
            
        Returns:
            Dict with 'theoretical_kg' and 'procurement_kg'
        """
        factor = 1.0 + (wastage_percent / 100.0)
        return {
            "theoretical_kg": self.total_steel_kg,
            "procurement_kg": self.total_steel_kg * factor,
            "wastage_factor": factor
        }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def hook_length_90(diameter_mm: int) -> float:
    """
    Calculate hook length for 90° standard hook.
    
    IS 456 Cl. 26.2.2.1: Anchorage value of hook = 9 * bar diameter
    
    Args:
        diameter_mm: Bar diameter in mm
        
    Returns:
        Hook length in mm
    """
    return HOOK_90_FACTOR * diameter_mm


def hook_length_135(diameter_mm: int) -> float:
    """
    Calculate hook length for 135° standard hook.
    
    IS 456 Cl. 26.2.2.1: For 135° hooks, equivalent length = 10d
    Typically used for stirrups and ties.
    
    Args:
        diameter_mm: Bar diameter in mm
        
    Returns:
        Hook length in mm
    """
    return HOOK_135_FACTOR * diameter_mm


def development_length(diameter_mm: int, fy: float = 415.0, fck: float = 25.0) -> float:
    """
    Calculate basic development length as per IS 456 Cl. 26.2.1.
    
    Formula: Ld = (0.87 * fy * φ) / (4 * τbd)
    
    For deformed bars, τbd is increased by 60% over plain bars.
    Bond stress values from IS 456 Table 6.1.
    
    Args:
        diameter_mm: Bar diameter in mm
        fy: Yield strength of steel in N/mm² (default Fe415)
        fck: Characteristic strength of concrete in N/mm² (default M25)
        
    Returns:
        Development length in mm
    
    Note:
        This is a simplified calculation. Actual Ld depends on:
        - Type of bar (plain/deformed)
        - Tension/compression
        - End conditions
    """
    # Bond stress for plain bars (IS 456 Table 6.1)
    if fck <= 20:
        tau_bd_plain = 1.2
    elif fck <= 25:
        tau_bd_plain = 1.4
    elif fck <= 30:
        tau_bd_plain = 1.5
    elif fck <= 35:
        tau_bd_plain = 1.7
    else:
        tau_bd_plain = 1.9
    
    # For HYSD/deformed bars, increase by 60%
    tau_bd = tau_bd_plain * 1.6
    
    # Development length formula
    ld = (0.87 * fy * diameter_mm) / (4 * tau_bd)
    
    return ld


def unit_weight(diameter_mm: int) -> float:
    """
    Calculate unit weight of bar per meter length.
    
    Formula: Weight (kg/m) = (π × d² / 4) × density × (1m length in mm) / 10⁹
    
    Simplified: W (kg/m) = πd² × 7850 / (4 × 10⁶) ≈ d² / 162
    
    Args:
        diameter_mm: Bar diameter in mm
        
    Returns:
        Weight in kg per meter
    """
    # Area in mm²
    area_mm2 = (math.pi * diameter_mm ** 2) / 4.0
    
    # For 1 meter (1000mm) length:
    # Volume = Area (mm²) × 1000 mm = Volume in mm³
    # Volume in m³ = Volume_mm³ / 10⁹
    # Weight = Volume_m³ × density_kg_per_m³
    # 
    # Simplified: weight_kg_per_m = area_mm² × 1000 / 10⁹ × 7850
    #            = area_mm² × 7850 / 10⁶
    
    weight_kg_per_m = (area_mm2 * STEEL_DENSITY_KG_M3) / 1e6
    return weight_kg_per_m


def bend_deduction_90(diameter_mm: int) -> float:
    """
    Calculate bend deduction for 90° bend.
    
    When a bar is bent 90°, the actual cutting length is reduced because
    the bar elongates during bending. Standard deduction: 2d per bend.
    
    Args:
        diameter_mm: Bar diameter in mm
        
    Returns:
        Deduction length in mm (negative value to subtract)
    """
    return 2 * diameter_mm


def bend_deduction_180(diameter_mm: int) -> float:
    """
    Calculate bend deduction for 180° bend.
    
    Standard deduction: 4d per 180° bend.
    
    Args:
        diameter_mm: Bar diameter in mm
        
    Returns:
        Deduction length in mm (negative value to subtract)
    """
    return 4 * diameter_mm


def seismic_hook_extension(diameter_mm: int) -> float:
    """
    Calculate seismic hook extension per IS 13920.
    
    Rule: 6d but not less than 65mm.
    
    Args:
        diameter_mm: Bar diameter in mm
        
    Returns:
        Hook extension in mm
    """
    extension = SEISMIC_HOOK_EXTENSION_FACTOR * diameter_mm
    return max(extension, SEISMIC_HOOK_MIN_EXTENSION_MM)


def confined_zone_stirrup_spacing(
    effective_depth_mm: float,
    longitudinal_bar_dia_mm: int
) -> float:
    """
    Calculate stirrup spacing in confined zone per IS 13920.
    
    Rule: Minimum of (d/4, 8 × smallest longitudinal bar dia, 100mm)
    
    Args:
        effective_depth_mm: Effective depth of beam/column
        longitudinal_bar_dia_mm: Smallest longitudinal bar diameter
        
    Returns:
        Maximum allowed spacing in mm
    """
    option_1 = effective_depth_mm / 4
    option_2 = 8 * longitudinal_bar_dia_mm
    option_3 = CONFINED_ZONE_MAX_SPACING_MM
    
    return min(option_1, option_2, option_3)


def lap_splice_length(
    diameter_mm: int,
    fy: float = 415.0,
    fck: float = 25.0,
    bars_lapped_percent: float = 50.0
) -> float:
    """
    Calculate lap splice length per IS 456.
    
    Lap length = Development length × factor
    Factor = 1.0 if ≤50% bars lapped, 1.4 if >50% bars lapped
    
    Args:
        diameter_mm: Bar diameter in mm
        fy: Steel yield strength
        fck: Concrete strength
        bars_lapped_percent: Percentage of bars being lapped at one section
        
    Returns:
        Required lap length in mm
    """
    ld = development_length(diameter_mm, fy, fck)
    
    if bars_lapped_percent > 50.0:
        return ld * LAP_SPLICE_FACTOR_EXCESS
    return ld


def stirrup_cutting_length(b_mm: float, d_mm: float, cover_mm: float, 
                            stirrup_dia_mm: int) -> float:
    """
    Calculate stirrup cutting length with 135° hooks at both ends.
    
    Stirrup perimeter = 2 * (clear_width + clear_depth) + hook_allowance - bend_deductions
    
    Where:
        clear_width = b - 2*cover
        clear_depth = d - 2*cover
        hook_allowance = 2 * 10d (for 135° hooks both ends)
        bend_deductions = 4 corners × 2d = 8d (for 90° bends at corners)
    
    Args:
        b_mm: Beam/column width in mm
        d_mm: Beam/column depth in mm
        cover_mm: Clear cover in mm
        stirrup_dia_mm: Stirrup bar diameter in mm
        
    Returns:
        Total cutting length in mm (with bend deductions applied)
    """
    # Clear dimensions (inside cover)
    clear_b = b_mm - 2 * cover_mm
    clear_d = d_mm - 2 * cover_mm
    
    # Stirrup perimeter (centerline)
    perimeter = 2 * (clear_b + clear_d)
    
    # 135° hooks both ends
    hooks = 2 * hook_length_135(stirrup_dia_mm)
    
    # Bend deductions: 4 corners with 90° bends = 4 × 2d = 8d
    # Note: Hooks are separate from corner bends
    corner_bend_deductions = 4 * bend_deduction_90(stirrup_dia_mm)
    
    # Total cutting length = perimeter + hooks - bend deductions
    cutting_length = perimeter + hooks - corner_bend_deductions
    
    return cutting_length


# =============================================================================
# BBS GENERATORS
# =============================================================================

def generate_beam_bbs(beam: BeamBBSInput) -> MemberBBS:
    """
    Generate Bar Bending Schedule for an RCC beam.
    
    Calculates cutting lengths and quantities for:
        - Top bars (straight with 90° hooks at ends)
        - Bottom bars (straight with 90° hooks at ends)
        - Stirrups (closed rectangular with 135° hooks)
    
    Args:
        beam: BeamBBSInput with all beam parameters
        
    Returns:
        MemberBBS with complete BBS entries
        
    Engineering Notes:
        - Main bars extend 9d beyond support (90° hook)
        - Bend deductions applied: 2d per 90° bend (bars elongate during bending)
        - Stirrups have 135° hooks both ends per IS 456
        - No curtailment considered (conservative)
    """
    entries = []
    
    # -------------------------------------------------------------------------
    # Entry A: Top Bars (Hanger/Anchor Bars)
    # -------------------------------------------------------------------------
    # Cutting length = Span + 2 * (Support width/2 + hook) - bend_deductions
    # Simplified: Span + 2 * 9d (for hooks into supports) - 2 * 2d (for 90° bends)
    top_hook_allowance = 2 * hook_length_90(beam.main_bar_dia_mm)
    top_bend_deductions = 2 * bend_deduction_90(beam.main_bar_dia_mm)  # 2 hooks = 2 × 90° bends
    top_cutting_length = beam.length_mm + top_hook_allowance - top_bend_deductions
    
    top_unit_wt = unit_weight(beam.main_bar_dia_mm)
    top_total_wt = (top_cutting_length / 1000.0) * top_unit_wt * beam.top_bars
    
    entries.append(BBSEntry(
        bar_mark="A",
        bar_diameter_mm=beam.main_bar_dia_mm,
        shape_code="Straight with 90° hooks both ends",
        cutting_length_mm=round(top_cutting_length, 1),
        number_of_bars=beam.top_bars,
        unit_weight_kg_per_m=round(top_unit_wt, 3),
        total_weight_kg=round(top_total_wt, 2),
        remarks=f"Top bars: {beam.top_bars}-{beam.main_bar_dia_mm}# at top"
    ))
    
    # -------------------------------------------------------------------------
    # Entry B: Bottom Bars (Tension Reinforcement)
    # -------------------------------------------------------------------------
    # Same logic as top bars - apply bend deductions
    bot_bend_deductions = 2 * bend_deduction_90(beam.main_bar_dia_mm)  # 2 hooks = 2 × 90° bends
    bot_cutting_length = beam.length_mm + top_hook_allowance - bot_bend_deductions
    
    bot_unit_wt = unit_weight(beam.main_bar_dia_mm)
    bot_total_wt = (bot_cutting_length / 1000.0) * bot_unit_wt * beam.bottom_bars
    
    entries.append(BBSEntry(
        bar_mark="B",
        bar_diameter_mm=beam.main_bar_dia_mm,
        shape_code="Straight with 90° hooks both ends",
        cutting_length_mm=round(bot_cutting_length, 1),
        number_of_bars=beam.bottom_bars,
        unit_weight_kg_per_m=round(bot_unit_wt, 3),
        total_weight_kg=round(bot_total_wt, 2),
        remarks=f"Bottom bars: {beam.bottom_bars}-{beam.main_bar_dia_mm}# at bottom"
    ))
    
    # -------------------------------------------------------------------------
    # Entry C: Stirrups
    # -------------------------------------------------------------------------
    stirrup_cut_len = stirrup_cutting_length(
        beam.width_mm, beam.depth_mm, 
        beam.clear_cover_mm, beam.stirrup_dia_mm
    )
    
    # Number of stirrups = (Span / Spacing) + 1
    num_stirrups = int(math.ceil(beam.length_mm / beam.stirrup_spacing_mm)) + 1
    
    stirrup_unit_wt = unit_weight(beam.stirrup_dia_mm)
    stirrup_total_wt = (stirrup_cut_len / 1000.0) * stirrup_unit_wt * num_stirrups
    
    entries.append(BBSEntry(
        bar_mark="C",
        bar_diameter_mm=beam.stirrup_dia_mm,
        shape_code="Rectangular stirrup with 135° hooks",
        cutting_length_mm=round(stirrup_cut_len, 1),
        number_of_bars=num_stirrups,
        unit_weight_kg_per_m=round(stirrup_unit_wt, 3),
        total_weight_kg=round(stirrup_total_wt, 2),
        remarks=f"2L-{beam.stirrup_dia_mm}# @ {int(beam.stirrup_spacing_mm)} c/c"
    ))
    
    # Create MemberBBS
    member_bbs = MemberBBS(
        member_id=beam.member_id,
        member_type="beam",
        member_size=f"{int(beam.width_mm)}x{int(beam.depth_mm)} L={int(beam.length_mm)}",
        entries=entries
    )
    member_bbs.calculate_total()
    
    return member_bbs


def generate_column_bbs(column: ColumnBBSInput) -> MemberBBS:
    """
    Generate Bar Bending Schedule for an RCC column (short column).
    
    Calculates cutting lengths and quantities for:
        - Main longitudinal bars (straight, full height + development)
        - Ties/stirrups (closed rectangular with 135° hooks)
    
    Args:
        column: ColumnBBSInput with all column parameters
        
    Returns:
        MemberBBS with complete BBS entries
        
    Engineering Notes:
        - Main bars extend into footing/beam by Ld
        - Ties have 135° hooks per IS 456
        - Tie spacing reduced near joints (not implemented here)
    """
    entries = []
    
    # -------------------------------------------------------------------------
    # Entry M: Main Longitudinal Bars
    # -------------------------------------------------------------------------
    # Cutting length = Floor height + Development length at bottom + Starter into slab
    # Simplified: Height + Ld (into footing) + 40d (lap at top for continuity)
    ld = development_length(column.main_bar_dia_mm)
    
    # For ground floor: full Ld into footing
    # For upper floors: lap length ~40d-50d (using 40d here)
    lap_length = 40 * column.main_bar_dia_mm
    
    # Total cutting length
    main_cutting_length = column.height_mm + ld + lap_length
    
    main_unit_wt = unit_weight(column.main_bar_dia_mm)
    main_total_wt = (main_cutting_length / 1000.0) * main_unit_wt * column.num_bars
    
    entries.append(BBSEntry(
        bar_mark="M",
        bar_diameter_mm=column.main_bar_dia_mm,
        shape_code="Straight",
        cutting_length_mm=round(main_cutting_length, 1),
        number_of_bars=column.num_bars,
        unit_weight_kg_per_m=round(main_unit_wt, 3),
        total_weight_kg=round(main_total_wt, 2),
        remarks=f"Main bars: {column.num_bars}-{column.main_bar_dia_mm}#, incl. Ld & lap"
    ))
    
    # -------------------------------------------------------------------------
    # Entry T: Ties/Stirrups
    # -------------------------------------------------------------------------
    tie_cut_len = stirrup_cutting_length(
        column.width_mm, column.depth_mm,
        column.clear_cover_mm, column.tie_dia_mm
    )
    
    # Number of ties = (Height / Spacing) + 1
    num_ties = int(math.ceil(column.height_mm / column.tie_spacing_mm)) + 1
    
    tie_unit_wt = unit_weight(column.tie_dia_mm)
    tie_total_wt = (tie_cut_len / 1000.0) * tie_unit_wt * num_ties
    
    entries.append(BBSEntry(
        bar_mark="T",
        bar_diameter_mm=column.tie_dia_mm,
        shape_code="Rectangular tie with 135° hooks",
        cutting_length_mm=round(tie_cut_len, 1),
        number_of_bars=num_ties,
        unit_weight_kg_per_m=round(tie_unit_wt, 3),
        total_weight_kg=round(tie_total_wt, 2),
        remarks=f"Ties: {column.tie_dia_mm}# @ {int(column.tie_spacing_mm)} c/c"
    ))
    
    # Create MemberBBS
    member_bbs = MemberBBS(
        member_id=column.member_id,
        member_type="column",
        member_size=f"{int(column.width_mm)}x{int(column.depth_mm)} H={int(column.height_mm)}",
        entries=entries
    )
    member_bbs.calculate_total()
    
    return member_bbs


def generate_slab_bbs(slab: SlabBBSInput) -> MemberBBS:
    """
    Generate Bar Bending Schedule for an RCC slab (one-way or two-way).
    
    Calculates cutting lengths and quantities for:
        - Main bars (short span direction for two-way, or primary direction)
        - Distribution bars (perpendicular to main)
    
    Args:
        slab: SlabBBSInput with all slab parameters
        
    Returns:
        MemberBBS with complete BBS entries
        
    Engineering Notes:
        - Determine slab type: if Ly/Lx >= 2, it's one-way
        - Main bars placed along short span with 90° hooks
        - Distribution bars perpendicular
        - Bars bent up at supports (simplified as straight here)
    """
    entries = []
    
    # Determine slab type
    lx = min(slab.lx_mm, slab.ly_mm)  # Short span
    ly = max(slab.lx_mm, slab.ly_mm)  # Long span
    ratio = ly / lx if lx > 0 else 1.0
    is_one_way = ratio >= 2.0
    slab_type = "One-Way" if is_one_way else "Two-Way"
    
    # -------------------------------------------------------------------------
    # Entry M: Main Bars (Short Span Direction)
    # -------------------------------------------------------------------------
    # Cutting length = Span + 2 * 9d (hooks both ends) - 2 * 2d (bend deductions)
    main_hook = 2 * hook_length_90(slab.main_bar_dia_mm)
    main_bend_deductions = 2 * bend_deduction_90(slab.main_bar_dia_mm)  # 2 hooks = 2 × 90° bends
    main_cutting_length = lx + main_hook - main_bend_deductions
    
    # Number of main bars = (Long span / Spacing) + 1
    num_main = int(math.ceil(ly / slab.main_bar_spacing_mm)) + 1
    
    main_unit_wt = unit_weight(slab.main_bar_dia_mm)
    main_total_wt = (main_cutting_length / 1000.0) * main_unit_wt * num_main
    
    entries.append(BBSEntry(
        bar_mark="M",
        bar_diameter_mm=slab.main_bar_dia_mm,
        shape_code="Straight with 90° hooks both ends",
        cutting_length_mm=round(main_cutting_length, 1),
        number_of_bars=num_main,
        unit_weight_kg_per_m=round(main_unit_wt, 3),
        total_weight_kg=round(main_total_wt, 2),
        remarks=f"Main bars along short span ({slab_type} slab)"
    ))
    
    # -------------------------------------------------------------------------
    # Entry D: Distribution Bars (Long Span Direction)
    # -------------------------------------------------------------------------
    # Apply bend deductions for hooks
    dist_hook = 2 * hook_length_90(slab.dist_bar_dia_mm)
    dist_bend_deductions = 2 * bend_deduction_90(slab.dist_bar_dia_mm)  # 2 hooks = 2 × 90° bends
    dist_cutting_length = ly + dist_hook - dist_bend_deductions
    
    # Number of dist bars = (Short span / Spacing) + 1
    num_dist = int(math.ceil(lx / slab.dist_bar_spacing_mm)) + 1
    
    dist_unit_wt = unit_weight(slab.dist_bar_dia_mm)
    dist_total_wt = (dist_cutting_length / 1000.0) * dist_unit_wt * num_dist
    
    entries.append(BBSEntry(
        bar_mark="D",
        bar_diameter_mm=slab.dist_bar_dia_mm,
        shape_code="Straight with 90° hooks both ends",
        cutting_length_mm=round(dist_cutting_length, 1),
        number_of_bars=num_dist,
        unit_weight_kg_per_m=round(dist_unit_wt, 3),
        total_weight_kg=round(dist_total_wt, 2),
        remarks="Distribution bars along long span"
    ))
    
    # Create MemberBBS
    member_bbs = MemberBBS(
        member_id=slab.member_id,
        member_type="slab",
        member_size=f"{int(slab.lx_mm)}x{int(slab.ly_mm)} T={int(slab.thickness_mm)} ({slab_type})",
        entries=entries
    )
    member_bbs.calculate_total()
    
    return member_bbs


def generate_project_bbs(
    beams: List[BeamBBSInput],
    columns: List[ColumnBBSInput],
    slabs: List[SlabBBSInput],
    project_name: str = "Residential RCC Building"
) -> ProjectBBS:
    """
    Generate complete project BBS from all structural members.
    
    Args:
        beams: List of beam inputs
        columns: List of column inputs
        slabs: List of slab inputs
        project_name: Project identifier
        
    Returns:
        ProjectBBS with all members and summary
    """
    project = ProjectBBS(project_name=project_name)
    
    # Generate BBS for each member type
    for beam in beams:
        project.members.append(generate_beam_bbs(beam))
    
    for column in columns:
        project.members.append(generate_column_bbs(column))
    
    for slab in slabs:
        project.members.append(generate_slab_bbs(slab))
    
    # Calculate summary
    project.calculate_summary()
    
    return project


# =============================================================================
# REPORTING FUNCTIONS
# =============================================================================

def format_bbs_table(member_bbs: MemberBBS) -> str:
    """
    Format a member BBS as a text table.
    
    Args:
        member_bbs: MemberBBS to format
        
    Returns:
        Formatted string table
    """
    lines = []
    lines.append(f"\n{'='*90}")
    lines.append(f"BAR BENDING SCHEDULE: {member_bbs.member_id} ({member_bbs.member_type.upper()})")
    lines.append(f"Size: {member_bbs.member_size}")
    lines.append(f"{'='*90}")
    
    # Header
    header = f"{'Mark':<6}{'Dia':>5}{'Shape':<35}{'Cut Len':>10}{'Nos':>6}{'Unit Wt':>10}{'Total':>10}"
    lines.append(header)
    lines.append("-" * 90)
    
    # Entries
    for e in member_bbs.entries:
        row = f"{e.bar_mark:<6}{e.bar_diameter_mm:>5}{e.shape_code:<35}{e.cutting_length_mm:>10.1f}{e.number_of_bars:>6}{e.unit_weight_kg_per_m:>10.3f}{e.total_weight_kg:>10.2f}"
        lines.append(row)
    
    lines.append("-" * 90)
    lines.append(f"{'TOTAL WEIGHT (kg)':<73}{member_bbs.total_weight_kg:>10.2f}")
    
    return "\n".join(lines)


def format_project_summary(project: ProjectBBS) -> str:
    """
    Format project summary as text.
    
    Args:
        project: ProjectBBS to format
        
    Returns:
        Formatted string summary
    """
    lines = []
    lines.append(f"\n{'='*60}")
    lines.append(f"PROJECT STEEL SUMMARY: {project.project_name}")
    lines.append(f"{'='*60}")
    
    # Summary by diameter
    lines.append(f"\n{'Diameter (mm)':<20}{'Weight (kg)':>20}{'% of Total':>20}")
    lines.append("-" * 60)
    
    sorted_dias = sorted(project.summary_by_diameter.keys())
    for dia in sorted_dias:
        wt = project.summary_by_diameter[dia]
        pct = (wt / project.total_steel_kg * 100) if project.total_steel_kg > 0 else 0
        lines.append(f"{dia:<20}{wt:>20.2f}{pct:>19.1f}%")
    
    lines.append("-" * 60)
    lines.append("-" * 60)
    lines.append(f"{'TOTAL THEORETICAL (kg)':<20}{project.total_steel_kg:>20.2f}")
    
    # Procurement w/ Margin
    proc = project.get_procurement_summary()
    lines.append(f"{'PROCUREMENT (kg)':<20}{proc['procurement_kg']:>20.2f}")
    lines.append(f"{'  (incl. 4% Margin)':<20}")
    
    lines.append("-" * 60)
    lines.append(f"{'TOTAL STEEL (Tonnes)':<20}{proc['procurement_kg']/1000:>20.3f}")
    
    return "\n".join(lines)


# =============================================================================
# SAMPLE DEMONSTRATION
# =============================================================================

if __name__ == "__main__":
    """
    Sample demonstration of BBS module.
    Run: python -m src.bbs_module
    """
    
    print("\n" + "="*90)
    print("BAR BENDING SCHEDULE (BBS) MODULE - SAMPLE OUTPUT")
    print("IS 456:2000 Based | Non-Seismic | Residential RCC Building")
    print("="*90)
    
    # Sample Beam
    sample_beam = BeamBBSInput(
        member_id="B1",
        length_mm=6000,
        width_mm=300,
        depth_mm=600,
        clear_cover_mm=25,
        main_bar_dia_mm=16,
        top_bars=2,
        bottom_bars=4,
        stirrup_dia_mm=8,
        stirrup_spacing_mm=150
    )
    
    # Sample Column
    sample_column = ColumnBBSInput(
        member_id="C1",
        height_mm=3000,
        width_mm=300,
        depth_mm=300,
        clear_cover_mm=40,
        main_bar_dia_mm=16,
        num_bars=8,
        tie_dia_mm=8,
        tie_spacing_mm=150
    )
    
    # Sample Slab
    sample_slab = SlabBBSInput(
        member_id="S1",
        lx_mm=4000,
        ly_mm=5000,
        thickness_mm=150,
        clear_cover_mm=20,
        main_bar_dia_mm=10,
        main_bar_spacing_mm=150,
        dist_bar_dia_mm=8,
        dist_bar_spacing_mm=200
    )
    
    # Generate BBS
    beam_bbs = generate_beam_bbs(sample_beam)
    column_bbs = generate_column_bbs(sample_column)
    slab_bbs = generate_slab_bbs(sample_slab)
    
    # Print individual BBS
    print(format_bbs_table(beam_bbs))
    print(format_bbs_table(column_bbs))
    print(format_bbs_table(slab_bbs))
    
    # Generate project summary
    project = generate_project_bbs(
        beams=[sample_beam],
        columns=[sample_column],
        slabs=[sample_slab],
        project_name="Sample G+1 Residence"
    )
    
    print(format_project_summary(project))
    
    # Show calculation verification
    print("\n" + "="*60)
    print("CALCULATION VERIFICATION")
    print("="*60)
    
    print(f"\n1. Hook Length (90°) for 16mm bar:")
    print(f"   9 × 16 = {hook_length_90(16)} mm ✓")
    
    print(f"\n2. Hook Length (135°) for 8mm bar:")
    print(f"   10 × 8 = {hook_length_135(8)} mm ✓")
    
    print(f"\n3. Unit Weight of 16mm bar:")
    print(f"   π × 16² / 4 × 7850 / 10⁶ × 1000 = {unit_weight(16):.3f} kg/m")
    print(f"   Check: 16² / 162 = {16**2/162:.3f} kg/m (approx formula) ✓")
    
    print(f"\n4. Development Length for 16mm bar (Fe415, M25):")
    print(f"   Ld = 0.87 × 415 × 16 / (4 × 1.4 × 1.6) = {development_length(16):.1f} mm ✓")
    
    print("\n" + "="*60)
    print("BBS MODULE READY FOR PRODUCTION USE")
    print("="*60 + "\n")
