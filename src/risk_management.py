"""
Black Box Risk Management Module for Civil/Structural Software.

This module implements comprehensive checks to prevent common failures in
residential building projects due to "Black Box" software usage.

Based on industry reviews and failure case studies, this module addresses:
1. Input & Modeling Assumptions Risks
2. Load Modeling & Analysis Failures
3. Detailing & Constructibility Simplifications
4. Cost Estimation & Quantity Take-off Errors

DISCLAIMER: All designs must be verified by a licensed Structural Engineer
before construction.
"""

import math
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
from pydantic import BaseModel

from .grid_manager import GridManager, Column
from .framing_logic import StructuralMember
from .foundation_eng import Footing
from .logging_config import get_logger

logger = get_logger(__name__)


class RiskLevel(str, Enum):
    """Risk severity levels."""
    CRITICAL = "CRITICAL"  # Immediate safety concern
    HIGH = "HIGH"          # Significant design error
    MEDIUM = "MEDIUM"      # Potential issue
    LOW = "LOW"            # Informational
    PASS = "PASS"          # Check passed


class RiskCategory(str, Enum):
    """Categories of risks."""
    MODELING = "Modeling Assumptions"
    ANALYSIS = "Load Modeling & Analysis"
    DETAILING = "Detailing & Constructibility"
    COST = "Cost Estimation & Quantity"


@dataclass
class RiskCheckResult:
    """Result of a single risk check."""
    check_name: str
    category: RiskCategory
    risk_level: RiskLevel
    status: str  # "PASS", "FAIL", "WARN"
    message: str
    recommendation: str
    affected_members: List[str] = None  # Member IDs affected
    calculated_value: float = None
    limit_value: float = None
    discrepancy_percent: float = 0.0
    
    def __post_init__(self):
        if self.affected_members is None:
            self.affected_members = []


class BlackBoxRiskManager:
    """
    Comprehensive risk management checker for structural software.
    
    Implements checks to prevent common "Black Box" software failures.
    """
    
    def __init__(
        self,
        grid_mgr: GridManager,
        beams: List[StructuralMember],
        footings: List[Footing],
        fck: float = 25.0,
        fy: float = 415.0,
        seismic_zone: str = "III",
        aggregate_size_mm: float = 20.0,
        subgrade_modulus_kn_m3: Optional[float] = None
    ):
        """
        Initialize risk manager.
        
        Args:
            grid_mgr: GridManager with columns and structure data
            beams: List of structural beams
            footings: List of footings
            fck: Concrete grade (N/mm²)
            fy: Steel yield strength (N/mm²)
            seismic_zone: Seismic zone (II, III, IV, V)
            aggregate_size_mm: Maximum aggregate size for congestion check
            subgrade_modulus_kn_m3: Soil spring stiffness (if None, assumes fixed)
        """
        self.grid_mgr = grid_mgr
        self.beams = beams
        self.footings = footings
        self.fck = fck
        self.fy = fy
        self.seismic_zone = seismic_zone
        self.aggregate_size_mm = aggregate_size_mm
        self.subgrade_modulus_kn_m3 = subgrade_modulus_kn_m3
        
        self.results: List[RiskCheckResult] = []
        
    def run_all_checks(self) -> List[RiskCheckResult]:
        """
        Run all risk management checks.
        
        Returns:
            List of RiskCheckResult objects
        """
        logger.info("Running Black Box Risk Management Checks...")
        
        # 0. NEW Safeguards (Audit)
        self.check_punching_shear_risk()
        self.check_deep_beam_action()
        self.check_short_column_risk()
        self.check_infill_wall_stiffness()

        # 1. Input & Modeling Assumptions Risks
        self.check_fixed_support_assumption()
        self.check_rigid_diaphragm_assumption()
        self.check_site_specific_geotechnics()
        
        # 2. Load Modeling & Analysis Failures
        self.check_pdelta_effects()
        self.check_pattern_loading()
        self.check_floating_columns()
        
        # 3. Detailing & Constructibility Simplifications
        self.check_bend_deductions()
        self.check_congestion_at_joints()
        self.check_seismic_hook_detailing()
        
        # 4. Cost Estimation & Quantity Take-off Errors
        self.check_opening_deductions()
        self.check_wastage_rolling_margin()
        
        # 5. Summary Checklist
        self.check_sanity_weight_vs_reaction()
        
        logger.info(f"Completed {len(self.results)} risk checks")
        return self.results
    
    # =========================================================================
    # 0. NEW CRITICAL CHECKS (Audit Safeguards)
    # =========================================================================

    def check_punching_shear_risk(self):
        """
        Check for Thin Slab / Punching Shear Risk (Audit Safeguard).
        
        Risk: Thin slabs (< 200mm) without beams (flat slabs) or with minimal beams
        failing in punching shear at columns.
        """
        check_name = "Punching Shear / Thin Slab Risk"
        
        if not hasattr(self.grid_mgr, 'slab_schedule') or not self.grid_mgr.slab_schedule:
             return 
            
        thin_slabs = []
        for slab_id, res in self.grid_mgr.slab_schedule.items():
            # Check thickness
            thk = getattr(res, 'thk_mm', 0)
            span_lx = getattr(res, 'span_lx_m', 0)
            span_ly = getattr(res, 'span_ly_m', 0)
            max_span = max(span_lx, span_ly)
            
            # Simple heuristic: If span > 5m and Thickness < 150mm, it's very risky for punching/deflection
            if max_span > 5.0 and thk < 150.0:
                 thin_slabs.append(f"{slab_id} (Thk={thk}mm, Span={max_span}m)")

        if thin_slabs:
            self.results.append(RiskCheckResult(
                check_name=check_name,
                category=RiskCategory.ANALYSIS,
                risk_level=RiskLevel.CRITICAL,
                status="FAIL",
                message=f"THIN SLAB / PUNCHING SHEAR RISK detected in {len(thin_slabs)} slabs.",
                recommendation="Found large span (>5m) slabs with thickness < 150mm. "
                             "This is highly vulnerable to PUNCHING SHEAR failure and long-term deflection creep. "
                             "Increase thickness to min 150-175mm or verify punching shear manually.",
                affected_members=thin_slabs
            ))

    def check_deep_beam_action(self):
        """
        Check for Deep Beam Action (Audit Safeguard).
        
        Risk: Member span-to-depth ratio < 4.0.
        Linear beam theory (Euler-Bernoulli) is INVALID. Needs Strut-and-Tie method.
        """
        check_name = "Deep Beam Action Check"
        
        deep_beams = []
        for beam in self.beams:
            # Calculate length
            L = math.sqrt((beam.end_point.x - beam.start_point.x)**2 + 
                          (beam.end_point.y - beam.start_point.y)**2)
            D = beam.properties.depth_mm / 1000.0
            
            if D > 0:
                ratio = L / D
                if ratio < 4.0:
                    deep_beams.append(f"{beam.id} (L/D={ratio:.1f})")
        
        if deep_beams:
            self.results.append(RiskCheckResult(
                check_name=check_name,
                category=RiskCategory.ANALYSIS,
                risk_level=RiskLevel.CRITICAL,
                status="FAIL",
                message=f"DEEP BEAMS detected: {len(deep_beams)} members with Span/Depth < 4.0.",
                recommendation="Standard flexural design is INVALID for deep beams. "
                             "Shear failure will dominate. Use Strut-and-Tie method or Deep Beam code provisions.",
                affected_members=deep_beams
            ))

    def check_short_column_risk(self):
        """
        Check for Short Column / Captive Column effect (Audit Safeguard).
        
        Risk: Low clear height due to mezzanines or partial infill walls.
        Attracts massive shear forces.
        """
        check_name = "Short Column Risk Check"
        
        short_cols = []
        
        # Check Story Height (Mezzanines)
        if self.grid_mgr.story_height_m < 2.5:
            self.results.append(RiskCheckResult(
                check_name=check_name,
                category=RiskCategory.MODELING,
                risk_level=RiskLevel.HIGH,
                status="WARN",
                message=f"Low Story Height ({self.grid_mgr.story_height_m}m) detected. "
                       "Columns may act as SHORT COLUMNS.",
                recommendation="Short columns attract high seismic shear forces because Stiffness ~ 1/L^3. "
                             "Ensure columns are designed for enhanced shear demand.",
                calculated_value=self.grid_mgr.story_height_m,
                limit_value=2.5
            ))
            
        # Helper: Check for partial infill settings (if we had them)
        # Assuming for now we check pure geometry

    def check_infill_wall_stiffness(self):
        """
        Check for Infill Wall Stiffness omission (Mixed System).
        (Audit Safeguard)
        """
        check_name = "Infill Wall Stiffness Check"
        
        # Heuristic: If we have wall loads but NO stiffness elements (struts)
        # Logic: We can't easily check for struts in this object model, 
        # but we can warn if "Bare Frame" is assumed for residential.
        
        # Simply warn for all frames in Seismic Zone III+ that infill stiffness matters.
        if hasattr(self, 'seismic_zone') and self.seismic_zone in ["III", "IV", "V"]:
             self.results.append(RiskCheckResult(
                check_name=check_name,
                category=RiskCategory.MODELING,
                risk_level=RiskLevel.MEDIUM,
                status="WARN",
                message="Masonry Infill Stiffness likely ignored (Bare Frame Analysis).",
                recommendation=f"Structure is in Seismic Zone {self.seismic_zone}. "
                             "Masonry walls increase stiffness and attract higher base shear. "
                             "Consider modeling Equivalent Diagonal Struts or check for Period Reduction.",
                affected_members=["Global Model"]
            ))


    
    def check_fixed_support_assumption(self):
        """
        Check for over-constrained supports (The "Fixed" Trap).
        
        Risk: Users frequently model column foundations as "Fixed" supports.
        In reality, isolated footings on standard soil allow for rotation.
        
        Consequence: Underestimates frame drift and column moments.
        """
        check_name = "Fixed Support Assumption Check"
        
        if self.subgrade_modulus_kn_m3 is None:
            # No soil spring defined - assume fixed (RISK)
            affected = [f.id for f in self.footings]
            
            self.results.append(RiskCheckResult(
                check_name=check_name,
                category=RiskCategory.MODELING,
                risk_level=RiskLevel.HIGH,
                status="WARN",
                message="Footings modeled as FIXED supports (no soil spring stiffness defined)",
                recommendation="Define subgrade modulus (k) for soil springs. "
                             "Typical values: 20,000-50,000 kN/m³ for medium soil. "
                             "Fixed assumption underestimates drift and moments. "
                             "Also CHECK CONSTRUCTION STAGE stability when fixed support is not yet achieved.",
                affected_members=affected
            ))
        else:
            # Soil spring defined - check if reasonable
            if self.subgrade_modulus_kn_m3 > 1e6:
                self.results.append(RiskCheckResult(
                    check_name=check_name,
                    category=RiskCategory.MODELING,
                    risk_level=RiskLevel.MEDIUM,
                    status="WARN",
                    message=f"Very high subgrade modulus ({self.subgrade_modulus_kn_m3:.0f} kN/m³) - "
                           "approaching rigid assumption",
                    recommendation="Verify soil properties. Values > 1,000,000 kN/m³ may be unrealistic.",
                    affected_members=[f.id for f in self.footings]
                ))
            else:
                self.results.append(RiskCheckResult(
                    check_name=check_name,
                    category=RiskCategory.MODELING,
                    risk_level=RiskLevel.PASS,
                    status="PASS",
                    message=f"Soil spring stiffness defined: {self.subgrade_modulus_kn_m3:.0f} kN/m³",
                    recommendation="Continue with current soil model."
                ))
    
    def check_rigid_diaphragm_assumption(self):
        """
        Check for rigid diaphragm fallacy.
        
        Risk: Software defaults to assuming floor slabs are infinitely rigid.
        In irregular shapes (L, C) or large openings, slab actually deforms.
        
        Consequence: Incorrect seismic force distribution.
        """
        check_name = "Rigid Diaphragm Assumption Check"
        
        if not self.grid_mgr:
            return
        
        # Calculate floor area
        floor_area = self.grid_mgr.width_m * self.grid_mgr.length_m
        
        # Check for irregular shapes (L, C, T)
        # Simple check: aspect ratio and re-entrant corners
        aspect_ratio = max(self.grid_mgr.width_m, self.grid_mgr.length_m) / \
                      min(self.grid_mgr.width_m, self.grid_mgr.length_m)
        
        # Check for large openings (stairwells, etc.)
        # This would require tracking openings - simplified check
        # Assume openings are tracked in grid_mgr or need to be passed
        
        # Check opening area (if available)
        opening_area = 0.0
        if hasattr(self.grid_mgr, 'void_zones') and self.grid_mgr.void_zones:
            # Calculate void area from grid
            for void in self.grid_mgr.void_zones:
                # Simplified: assume void is one bay
                span_x = self.grid_mgr.x_grid_lines[1] - self.grid_mgr.x_grid_lines[0] if len(self.grid_mgr.x_grid_lines) > 1 else 6.0
                span_y = self.grid_mgr.y_grid_lines[1] - self.grid_mgr.y_grid_lines[0] if len(self.grid_mgr.y_grid_lines) > 1 else 6.0
                opening_area += span_x * span_y
        
        opening_ratio = opening_area / floor_area if floor_area > 0 else 0.0
        
        # Risk criteria
        if opening_ratio > 0.30:
            self.results.append(RiskCheckResult(
                check_name=check_name,
                category=RiskCategory.MODELING,
                risk_level=RiskLevel.HIGH,
                status="FAIL",
                message=f"Large floor openings detected ({opening_ratio*100:.1f}% of floor area). "
                       f"Slab opening area > 30% threshold.",
                recommendation="Model as SEMI-RIGID or FLEXIBLE diaphragm. "
                             "Rigid assumption will incorrectly distribute seismic forces.",
                calculated_value=opening_ratio * 100,
                limit_value=30.0,
                discrepancy_percent=(opening_ratio * 100 - 30.0)
            ))
        elif opening_ratio > 0.15:
            self.results.append(RiskCheckResult(
                check_name=check_name,
                category=RiskCategory.MODELING,
                risk_level=RiskLevel.MEDIUM,
                status="WARN",
                message=f"Moderate floor openings ({opening_ratio*100:.1f}% of floor area)",
                recommendation="Verify diaphragm action is adequate. Consider semi-rigid analysis.",
                calculated_value=opening_ratio * 100,
                limit_value=30.0
            ))
        elif aspect_ratio > 3.0:
            self.results.append(RiskCheckResult(
                check_name=check_name,
                category=RiskCategory.MODELING,
                risk_level=RiskLevel.MEDIUM,
                status="WARN",
                message=f"High aspect ratio ({aspect_ratio:.2f}) - building may not act as rigid diaphragm",
                recommendation="Consider semi-rigid diaphragm analysis for accurate force distribution.",
                calculated_value=aspect_ratio,
                limit_value=3.0
            ))
        else:
            self.results.append(RiskCheckResult(
                check_name=check_name,
                category=RiskCategory.MODELING,
                risk_level=RiskLevel.PASS,
                status="PASS",
                message="Floor plan appears suitable for rigid diaphragm assumption",
                recommendation="Continue with rigid diaphragm analysis."
            ))
    
    def check_site_specific_geotechnics(self):
        """
        Check for site-specific geotechnical considerations.
        
        Risk: Applying standard bearing capacities without site-specific modification.
        """
        check_name = "Site-Specific Geotechnics Check"
        
        # Check if all footings use same SBC (potential issue)
        if not self.footings:
            return
        
        # This check would require SBC data per footing
        # Simplified: warn if no geotechnical variation considered
        self.results.append(RiskCheckResult(
            check_name=check_name,
            category=RiskCategory.MODELING,
            risk_level=RiskLevel.MEDIUM,
            status="WARN",
            message="Standard bearing capacity applied uniformly. No site-specific geotechnical variation considered.",
            recommendation="Consider: (1) Soil test reports, (2) Slope stability, "
                         "(3) Monsoon saturation effects (SBC reduction), (4) Differential settlement potential.",
            affected_members=[f"F-{i}" for i in range(len(self.footings))]
        ))
    
    # =========================================================================
    # 2. LOAD MODELING & ANALYSIS FAILURES
    # =========================================================================
    
    def check_pdelta_effects(self):
        """
        Check for P-Delta effects (Geometric Nonlinearity).
        
        Risk: Ignoring secondary moments from vertical load on laterally displaced structure.
        
        Consequence: Underestimation of storey drift and column moments (can be >10%).
        """
        check_name = "P-Delta Effects Check"
        
        if not self.grid_mgr:
            return
        
        num_stories = self.grid_mgr.num_stories
        
        # IS 16700: P-Delta mandatory for structures where stability index exceeds limits
        # Stability index: θ = P × Δ / (V × h)
        # For residential: P-Delta critical if > 3 stories or stability index > 0.1
        
        if num_stories >= 3:
            # Estimate total building weight
            total_weight_kn = sum(col.load_kn for col in self.grid_mgr.columns if col.level == 0)
            total_weight_kn *= num_stories  # Approximate
            
            # Check if P-Delta analysis was performed
            # This would require tracking analysis type - simplified warning
            self.results.append(RiskCheckResult(
                check_name=check_name,
                category=RiskCategory.ANALYSIS,
                risk_level=RiskLevel.HIGH,
                status="WARN",
                message=f"Structure has {num_stories} stories. P-Delta effects may be significant.",
                recommendation="As per IS 16700, perform P-Delta analysis if stability index > 0.1. "
                             "P-Delta can increase displacement by >10% in taller structures.",
                calculated_value=num_stories,
                limit_value=3.0
            ))
        else:
            self.results.append(RiskCheckResult(
                check_name=check_name,
                category=RiskCategory.ANALYSIS,
                risk_level=RiskLevel.LOW,
                status="PASS",
                message=f"Low-rise structure ({num_stories} stories). P-Delta effects typically negligible.",
                recommendation="P-Delta analysis not mandatory for low-rise structures."
            ))
    
    def check_pattern_loading(self):
        """
        Check for pattern loading omission.
        
        Risk: Applying live load across entire floor simultaneously.
        
        Consequence: IS 456 mandates pattern loading for continuous beams to find
        maximum hogging/sagging moments.
        """
        check_name = "Pattern Loading Check"
        
        if not self.beams:
            return
        
        # Check for continuous beams (beams with multiple spans)
        # Simplified: check if beams are part of continuous system
        continuous_beams = []
        
        # Group beams by grid line to identify continuous spans
        beam_groups = {}
        for beam in self.beams:
            # Check if beam aligns with grid
            key = None
            if abs(beam.start_point.y - beam.end_point.y) < 0.01:  # Horizontal beam
                key = f"Y={beam.start_point.y:.2f}"
            elif abs(beam.start_point.x - beam.end_point.x) < 0.01:  # Vertical beam
                key = f"X={beam.start_point.x:.2f}"
            
            if key:
                if key not in beam_groups:
                    beam_groups[key] = []
                beam_groups[key].append(beam)
        
        # Identify continuous beams (multiple beams on same line)
        for key, beams_in_line in beam_groups.items():
            if len(beams_in_line) >= 2:
                continuous_beams.extend([b.id for b in beams_in_line])
        
        if continuous_beams:
            self.results.append(RiskCheckResult(
                check_name=check_name,
                category=RiskCategory.ANALYSIS,
                risk_level=RiskLevel.HIGH,
                status="FAIL",
                message=f"Continuous beams detected but pattern loading not enforced. "
                       f"{len(continuous_beams)} continuous beam(s) identified.",
                recommendation="IS 456 mandates PATTERN LOADING (alternate spans loaded) "
                             "for continuous beams to find maximum moments. "
                             "Force pattern loading analysis.",
                affected_members=continuous_beams
            ))
        else:
            self.results.append(RiskCheckResult(
                check_name=check_name,
                category=RiskCategory.ANALYSIS,
                risk_level=RiskLevel.PASS,
                status="PASS",
                message="No continuous beam system detected or pattern loading applied.",
                recommendation="Continue with current loading pattern."
            ))
    
    def check_floating_columns(self):
        """
        Check for floating columns (discontinuous load paths).
        
        Risk: Columns resting on beams without flagging irregularity.
        
        Consequence: Vertical irregularity and stress concentration.
        """
        check_name = "Floating Columns Check"
        
        if not self.grid_mgr or not self.beams:
            return
        
        floating_cols = []
        
        # Check if any column at upper level doesn't have column below
        # (simplified check - would need full 3D model for accurate detection)
        columns_by_level = {}
        for col in self.grid_mgr.columns:
            if col.level not in columns_by_level:
                columns_by_level[col.level] = []
            columns_by_level[col.level].append(col)
        
        # Check columns above ground level
        for level in sorted(columns_by_level.keys()):
            if level == 0:
                continue
            
            for col in columns_by_level[level]:
                # Check if there's a column directly below at same (x, y)
                has_support_below = False
                for lower_col in columns_by_level.get(level - 1, []):
                    if abs(lower_col.x - col.x) < 0.01 and abs(lower_col.y - col.y) < 0.01:
                        has_support_below = True
                        break
                
                if not has_support_below:
                    floating_cols.append(col.id)
        
        if floating_cols:
            self.results.append(RiskCheckResult(
                check_name=check_name,
                category=RiskCategory.ANALYSIS,
                risk_level=RiskLevel.CRITICAL,
                status="FAIL",
                message=f"FLOATING COLUMNS detected: {len(floating_cols)} column(s) without direct vertical support.",
                recommendation="CRITICAL: Floating columns create vertical irregularity and stress concentration. "
                             "Missing lateral load paths are a major cause of failure. "
                             "Add transfer beams or redesign column layout.",
                affected_members=floating_cols
            ))
        else:
            self.results.append(RiskCheckResult(
                check_name=check_name,
                category=RiskCategory.ANALYSIS,
                risk_level=RiskLevel.PASS,
                status="PASS",
                message="All columns have continuous load path to foundation.",
                recommendation="Structure has continuous vertical load path."
            ))
    
    # =========================================================================
    # 3. DETAILING & CONSTRUCTIBILITY SIMPLIFICATIONS
    # =========================================================================
    
    def check_bend_deductions(self):
        """
        Check for bend deduction neglect in BBS.
        
        Risk: Calculating cutting lengths based on center-line dimensions
        without subtracting for steel elongation during bending.
        
        Consequence: Cut bars too long, don't fit in formwork.
        """
        check_name = "Bend Deduction Check"
        
        # Check if BBS module applies bend deductions
        # This would require checking BBS generation code
        # Simplified: always warn to verify
        
        self.results.append(RiskCheckResult(
            check_name=check_name,
            category=RiskCategory.DETAILING,
            risk_level=RiskLevel.HIGH,
            status="WARN",
            message="Verify that BBS cutting lengths include BEND DEDUCTIONS.",
            recommendation="Cutting length must account for bend allowances: "
                         "Deduct 2d for 90° bends, 4d for 180° bends. "
                         "Center-line dimensions overestimate actual cutting length.",
            affected_members=["All BBS entries"]
        ))
    
    def check_congestion_at_joints(self):
        """
        Check for congestion & concrete flow issues.
        
        Risk: Reinforcement spacing too close for aggregate to pass.
        
        Consequence: Honeycombing and weak joints.
        """
        check_name = "Congestion Check at Beam-Column Joints"
        
        if not self.grid_mgr or not self.beams:
            return
        
        congested_joints = []
        min_spacing_mm = self.aggregate_size_mm + 5.0  # IS 456 requirement
        
        # Check beam-column joints
        for col in self.grid_mgr.columns:
            if col.id not in self.grid_mgr.rebar_schedule:
                continue
            
            rebar_result = self.grid_mgr.rebar_schedule[col.id]
            
            # Get main steel area
            if hasattr(rebar_result, 'main_steel_area_mm2'):
                main_area = rebar_result.main_steel_area_mm2
                
                # Estimate number of bars (simplified)
                # Assume 16mm bars typically
                bar_dia = 16.0  # mm
                num_bars_est = int(main_area / (math.pi * (bar_dia/2)**2))
                
                # Check spacing
                # Simplified: check if bars fit with minimum spacing
                col_width = col.width_nb
                col_depth = col.depth_nb
                
                # Effective width/depth for bars (accounting for cover)
                cover = 40.0  # mm
                eff_width = col_width - 2 * cover
                eff_depth = col_depth - 2 * cover
                
                # Check if bars can fit with minimum spacing
                if num_bars_est > 0:
                    # Assume bars arranged in perimeter
                    # Simplified check: if too many bars for size
                    max_bars_width = int((eff_width + min_spacing_mm) / (bar_dia + min_spacing_mm))
                    max_bars_depth = int((eff_depth + min_spacing_mm) / (bar_dia + min_spacing_mm))
                    max_bars_total = max_bars_width * 2 + max_bars_depth * 2 - 4  # Perimeter
                    
                    if num_bars_est > max_bars_total * 0.8:  # 80% threshold
                        congested_joints.append(col.id)
        
        if congested_joints:
            self.results.append(RiskCheckResult(
                check_name=check_name,
                category=RiskCategory.DETAILING,
                risk_level=RiskLevel.HIGH,
                status="FAIL",
                message=f"CONGESTION detected at {len(congested_joints)} beam-column joint(s). "
                       f"Reinforcement spacing may be < {min_spacing_mm:.0f}mm (aggregate size + 5mm).",
                recommendation=f"Ensure reinforcement spacing > {min_spacing_mm:.0f}mm "
                             f"(aggregate size {self.aggregate_size_mm:.0f}mm + 5mm) for concrete flow. "
                             "Congestion causes honeycombing and weak joints.",
                affected_members=congested_joints,
                calculated_value=min_spacing_mm,
                limit_value=min_spacing_mm
            ))
        else:
            self.results.append(RiskCheckResult(
                check_name=check_name,
                category=RiskCategory.DETAILING,
                risk_level=RiskLevel.PASS,
                status="PASS",
                message=f"Reinforcement spacing appears adequate (> {min_spacing_mm:.0f}mm) at joints.",
                recommendation="Continue with current detailing."
            ))
    
    def check_seismic_hook_detailing(self):
        """
        Check for seismic hook detailing compliance.
        
        Risk: Defaulting to 90-degree hooks for stirrups.
        
        Consequence: In seismic zones (III, IV, V), IS 13920 mandates 135-degree hooks.
        """
        check_name = "Seismic Hook Detailing Check"
        
        # Check seismic zone
        zone_number = int(self.seismic_zone) if self.seismic_zone.isdigit() else 3
        
        if zone_number >= 3:
            # Seismic zones III, IV, V require 135° hooks per IS 13920
            self.results.append(RiskCheckResult(
                check_name=check_name,
                category=RiskCategory.DETAILING,
                risk_level=RiskLevel.CRITICAL,
                status="FAIL",
                message=f"Seismic Zone {self.seismic_zone} detected. Stirrups must use 135° hooks per IS 13920.",
                recommendation="CRITICAL: In seismic zones III, IV, V, all stirrups must have "
                             "135° hooks with extension length 6d or 65mm (whichever is greater). "
                             "90° hooks will open during earthquakes.",
                affected_members=["All stirrups in seismic zones"]
            ))
        else:
            self.results.append(RiskCheckResult(
                check_name=check_name,
                category=RiskCategory.DETAILING,
                risk_level=RiskLevel.PASS,
                status="PASS",
                message=f"Seismic Zone {self.seismic_zone} - 90° hooks acceptable per IS 456.",
                recommendation="Continue with standard hook detailing."
            ))
    
    # =========================================================================
    # 4. COST ESTIMATION & QUANTITY TAKE-OFF ERRORS
    # =========================================================================
    
    def check_opening_deductions(self):
        """
        Check for opening deduction logic per IS 1200.
        
        Risk: Automatically deducting all openings from masonry/concrete volumes.
        
        Consequence: IS 1200 specifies openings < 0.1m² are NOT deducted.
        """
        check_name = "Opening Deduction Logic Check (IS 1200)"
        
        # This check would require tracking opening sizes
        # Simplified warning
        
        self.results.append(RiskCheckResult(
            check_name=check_name,
            category=RiskCategory.COST,
            risk_level=RiskLevel.HIGH,
            status="WARN",
            message="Verify opening deduction logic follows IS 1200 rules.",
            recommendation="IS 1200: Openings < 0.1 m² are NOT deducted from masonry/concrete volumes. "
                         "Only openings ≥ 0.1 m² should be deducted. "
                         "Deducting all openings causes under-estimation of billable quantities.",
            affected_members=["All quantity take-offs"]
        ))
    
    def check_wastage_rolling_margin(self):
        """
        Check for wastage & rolling margin in steel estimation.
        
        Risk: Billing based on exact theoretical weight.
        
        Consequence: Real-world procurement must account for rolling margin and off-cut wastage.
        """
        check_name = "Wastage & Rolling Margin Check"
        
        self.results.append(RiskCheckResult(
            check_name=check_name,
            category=RiskCategory.COST,
            risk_level=RiskLevel.MEDIUM,
            status="WARN",
            message="Steel estimation may not account for wastage and rolling margin.",
            recommendation="Add 3-5% for rolling margin (variance in steel unit weight) "
                         "and 2-3% for off-cut wastage (cutting 4m bar from 12m stock). "
                         "Software estimates are often 3-5% lower than actual procurement needs.",
            affected_members=["All steel quantities"]
        ))
    
    # =========================================================================
    # 5. SUMMARY CHECKLIST
    # =========================================================================
    
    def check_sanity_weight_vs_reaction(self):
        """
        Sanity check: Total Building Weight vs Total Base Reaction.
        
        Risk: Discrepancy indicates modeling or load calculation error.
        """
        check_name = "Sanity Check: Building Weight vs Base Reaction"
        
        if not self.grid_mgr or not self.footings:
            return
        
        # Calculate total building weight
        # Sum all column loads at ground level
        total_weight_kn = sum(col.load_kn for col in self.grid_mgr.columns if col.level == 0)
        
        # Multiply by number of stories (approximate)
        total_weight_kn *= self.grid_mgr.num_stories
        
        # Add self-weight of structure (approximate)
        # Concrete volume estimate
        total_conc_vol = sum(f.concrete_vol_m3 for f in self.footings)
        # Add columns, beams, slabs (simplified)
        conc_density = 25.0  # kN/m³
        self_weight_kn = total_conc_vol * conc_density * 2.0  # Factor for columns/beams
        total_weight_kn += self_weight_kn
        
        # Calculate total base reaction (sum of footing reactions)
        total_reaction_kn = 0.0
        for footing in self.footings:
            # Estimate reaction from footing area and SBC
            # Simplified: assume SBC = 200 kN/m²
            sbc = 200.0  # kN/m²
            reaction = footing.area_m2 * sbc
            total_reaction_kn += reaction
        
        # Check discrepancy
        if total_reaction_kn > 0:
            discrepancy = abs(total_weight_kn - total_reaction_kn) / total_reaction_kn * 100
            
            if discrepancy > 20.0:
                self.results.append(RiskCheckResult(
                    check_name=check_name,
                    category=RiskCategory.ANALYSIS,
                    risk_level=RiskLevel.CRITICAL,
                    status="FAIL",
                    message=f"MAJOR DISCREPANCY: Total Weight ({total_weight_kn:.0f} kN) vs "
                           f"Base Reaction ({total_reaction_kn:.0f} kN) differs by {discrepancy:.1f}%.",
                    recommendation="CRITICAL: Check load calculations, footing design, and modeling assumptions. "
                                 "Discrepancy > 20% indicates potential error.",
                    calculated_value=total_weight_kn,
                    limit_value=total_reaction_kn,
                    discrepancy_percent=discrepancy
                ))
            elif discrepancy > 10.0:
                self.results.append(RiskCheckResult(
                    check_name=check_name,
                    category=RiskCategory.ANALYSIS,
                    risk_level=RiskLevel.HIGH,
                    status="WARN",
                    message=f"Discrepancy detected: Total Weight ({total_weight_kn:.0f} kN) vs "
                           f"Base Reaction ({total_reaction_kn:.0f} kN) differs by {discrepancy:.1f}%.",
                    recommendation="Review load calculations and footing reactions. "
                                 "Discrepancy > 10% should be investigated.",
                    calculated_value=total_weight_kn,
                    limit_value=total_reaction_kn,
                    discrepancy_percent=discrepancy
                ))
            else:
                self.results.append(RiskCheckResult(
                    check_name=check_name,
                    category=RiskCategory.ANALYSIS,
                    risk_level=RiskLevel.PASS,
                    status="PASS",
                    message=f"Total Weight ({total_weight_kn:.0f} kN) ≈ Base Reaction ({total_reaction_kn:.0f} kN). "
                           f"Discrepancy: {discrepancy:.1f}% (acceptable).",
                    recommendation="Weight and reaction balance is acceptable.",
                    calculated_value=total_weight_kn,
                    limit_value=total_reaction_kn,
                    discrepancy_percent=discrepancy
                ))
        else:
            self.results.append(RiskCheckResult(
                check_name=check_name,
                category=RiskCategory.ANALYSIS,
                risk_level=RiskLevel.MEDIUM,
                status="WARN",
                message="Cannot calculate base reaction - footing data incomplete.",
                recommendation="Ensure all footings have area and SBC data for sanity check."
            ))


def format_risk_report(results: List[RiskCheckResult]) -> str:
    """
    Format risk check results as a readable report.
    
    Args:
        results: List of RiskCheckResult objects
        
    Returns:
        Formatted report string
    """
    lines = []
    lines.append("\n" + "="*100)
    lines.append("BLACK BOX RISK MANAGEMENT REPORT")
    lines.append("="*100)
    
    # Group by category
    by_category = {}
    for result in results:
        if result.category not in by_category:
            by_category[result.category] = []
        by_category[result.category].append(result)
    
    # Summary statistics
    critical = sum(1 for r in results if r.risk_level == RiskLevel.CRITICAL)
    high = sum(1 for r in results if r.risk_level == RiskLevel.HIGH)
    medium = sum(1 for r in results if r.risk_level == RiskLevel.MEDIUM)
    passed = sum(1 for r in results if r.risk_level == RiskLevel.PASS)
    
    lines.append(f"\nSUMMARY:")
    lines.append(f"  Critical Issues: {critical}")
    lines.append(f"  High Risk: {high}")
    lines.append(f"  Medium Risk: {medium}")
    lines.append(f"  Passed: {passed}")
    lines.append(f"  Total Checks: {len(results)}")
    
    # Detailed results by category
    for category in RiskCategory:
        if category not in by_category:
            continue
        
        lines.append(f"\n{'='*100}")
        lines.append(f"{category.value.upper()}")
        lines.append(f"{'='*100}")
        
        for result in by_category[category]:
            status_symbol = {
                "PASS": "✓",
                "WARN": "⚠",
                "FAIL": "✗"
            }.get(result.status, "?")
            
            lines.append(f"\n[{status_symbol}] {result.check_name} - {result.risk_level.value}")
            lines.append(f"   Status: {result.status}")
            lines.append(f"   Message: {result.message}")
            
            if result.affected_members:
                lines.append(f"   Affected Members: {', '.join(result.affected_members[:10])}")
                if len(result.affected_members) > 10:
                    lines.append(f"   ... and {len(result.affected_members) - 10} more")
            
            if result.calculated_value is not None and result.limit_value is not None:
                lines.append(f"   Calculated: {result.calculated_value:.2f} | Limit: {result.limit_value:.2f}")
                if result.discrepancy_percent > 0:
                    lines.append(f"   Discrepancy: {result.discrepancy_percent:.1f}%")
            
            lines.append(f"   Recommendation: {result.recommendation}")
    
    lines.append("\n" + "="*100)
    lines.append("END OF RISK MANAGEMENT REPORT")
    lines.append("="*100 + "\n")
    
    return "\n".join(lines)


# Convenience function
def run_risk_checks(
    grid_mgr: GridManager,
    beams: List[StructuralMember],
    footings: List[Footing],
    **kwargs
) -> Tuple[List[RiskCheckResult], str]:
    """
    Run all risk checks and return results with formatted report.
    
    Args:
        grid_mgr: GridManager instance
        beams: List of beams
        footings: List of footings
        **kwargs: Additional parameters for BlackBoxRiskManager
        
    Returns:
        Tuple of (results list, formatted report string)
    """
    manager = BlackBoxRiskManager(grid_mgr, beams, footings, **kwargs)
    results = manager.run_all_checks()
    report = format_risk_report(results)
    
    return results, report
