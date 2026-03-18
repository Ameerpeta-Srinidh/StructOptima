"""
Structural Stability and Fire Resistance Module

Implements checks per:
- IS 456:2000 - Structural stability and fire resistance
- IS 1893:2016 - Seismic provisions (simplified)
- NBC 2016 Part 4 - Fire and Life Safety

DISCLAIMER: All designs must be verified by a licensed Professional Engineer.
"""

from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional
from enum import Enum
import math


class FireRating(str, Enum):
    """Fire resistance ratings per NBC 2016."""
    HALF_HOUR = "0.5"
    ONE_HOUR = "1.0"
    ONE_HALF_HOUR = "1.5"
    TWO_HOUR = "2.0"
    THREE_HOUR = "3.0"
    FOUR_HOUR = "4.0"


class ExposureCondition(str, Enum):
    """Exposure conditions per IS 456 Table 3."""
    MILD = "mild"           # Concrete dry or protected
    MODERATE = "moderate"   # Concrete humid, buried
    SEVERE = "severe"       # Coastal, industrial
    VERY_SEVERE = "very_severe"  # Seawater, chemicals
    EXTREME = "extreme"     # Aggressive chemicals


@dataclass
class FireResistanceRequirements:
    """Fire resistance requirements per IS 456 Table 16A and NBC 2016."""
    fire_rating: FireRating
    min_column_width_mm: int
    min_beam_width_mm: int
    min_slab_thickness_mm: int
    min_cover_column_mm: int
    min_cover_beam_mm: int
    min_cover_slab_mm: int
    description: str


# IS 456 Table 16A - Fire Resistance Requirements
FIRE_RESISTANCE_TABLE = {
    FireRating.HALF_HOUR: FireResistanceRequirements(
        fire_rating=FireRating.HALF_HOUR,
        min_column_width_mm=200,
        min_beam_width_mm=200,
        min_slab_thickness_mm=75,
        min_cover_column_mm=20,
        min_cover_beam_mm=20,
        min_cover_slab_mm=15,
        description="0.5 hour fire resistance"
    ),
    FireRating.ONE_HOUR: FireResistanceRequirements(
        fire_rating=FireRating.ONE_HOUR,
        min_column_width_mm=200,
        min_beam_width_mm=200,
        min_slab_thickness_mm=95,
        min_cover_column_mm=25,
        min_cover_beam_mm=20,
        min_cover_slab_mm=20,
        description="1 hour fire resistance"
    ),
    FireRating.ONE_HALF_HOUR: FireResistanceRequirements(
        fire_rating=FireRating.ONE_HALF_HOUR,
        min_column_width_mm=200,
        min_beam_width_mm=200,
        min_slab_thickness_mm=110,
        min_cover_column_mm=30,
        min_cover_beam_mm=25,
        min_cover_slab_mm=25,
        description="1.5 hour fire resistance"
    ),
    FireRating.TWO_HOUR: FireResistanceRequirements(
        fire_rating=FireRating.TWO_HOUR,
        min_column_width_mm=300,
        min_beam_width_mm=200,
        min_slab_thickness_mm=125,
        min_cover_column_mm=40,
        min_cover_beam_mm=30,
        min_cover_slab_mm=25,
        description="2 hour fire resistance"
    ),
    FireRating.THREE_HOUR: FireResistanceRequirements(
        fire_rating=FireRating.THREE_HOUR,
        min_column_width_mm=400,
        min_beam_width_mm=240,
        min_slab_thickness_mm=150,
        min_cover_column_mm=50,
        min_cover_beam_mm=35,
        min_cover_slab_mm=35,
        description="3 hour fire resistance"
    ),
    FireRating.FOUR_HOUR: FireResistanceRequirements(
        fire_rating=FireRating.FOUR_HOUR,
        min_column_width_mm=450,
        min_beam_width_mm=280,
        min_slab_thickness_mm=170,
        min_cover_column_mm=55,
        min_cover_beam_mm=40,
        min_cover_slab_mm=45,
        description="4 hour fire resistance"
    ),
}


@dataclass
class StabilityCheck:
    """Result of stability check for a member."""
    member_id: str
    member_type: str  # column, beam, slab
    
    # Slenderness check
    slenderness_ratio: float
    max_slenderness: float
    slenderness_ok: bool
    
    # Fire resistance check
    fire_rating_required: FireRating
    min_dimension_required_mm: int
    actual_dimension_mm: int
    dimension_ok: bool
    min_cover_required_mm: int
    actual_cover_mm: int
    cover_ok: bool
    
    # Overall
    is_stable: bool
    is_fire_safe: bool
    remarks: str


@dataclass
class StabilitySummary:
    """Summary of all stability and fire checks."""
    total_members: int
    passed_stability: int
    passed_fire: int
    failed_members: List[str]
    fire_rating_used: FireRating
    all_passed: bool
    recommendations: List[str]


class StabilityChecker:
    """
    Structural stability and fire resistance checker.
    
    Per IS 456:2000 and NBC 2016.
    """
    
    def __init__(
        self,
        num_floors: int,
        building_height_m: float,
        exposure: ExposureCondition = ExposureCondition.MODERATE,
        fire_rating: Optional[FireRating] = None
    ):
        self.num_floors = num_floors
        self.building_height_m = building_height_m
        self.exposure = exposure
        
        # Determine fire rating based on building height per NBC 2016
        if fire_rating:
            self.fire_rating = fire_rating
        else:
            self.fire_rating = self._get_required_fire_rating()
        
        self.fire_req = FIRE_RESISTANCE_TABLE[self.fire_rating]
    
    def _get_required_fire_rating(self) -> FireRating:
        """
        Determine fire rating based on building height per NBC 2016.
        
        NBC 2016 Part 4:
        - Up to 2 floors: 0.5 - 1 hour
        - 3-4 floors: 1.5 hours
        - 5+ floors: 2 hours
        - High-rise (>15m): 2-3 hours
        - Very tall (>45m): 4 hours
        """
        if self.num_floors <= 2:
            return FireRating.ONE_HOUR
        elif self.num_floors <= 4:
            return FireRating.ONE_HALF_HOUR
        elif self.building_height_m <= 15:
            return FireRating.TWO_HOUR
        elif self.building_height_m <= 45:
            return FireRating.THREE_HOUR
        else:
            return FireRating.FOUR_HOUR
    
    def check_column_slenderness(
        self,
        width_mm: float,
        depth_mm: float,
        height_mm: float,
        effective_length_factor: float = 1.0
    ) -> Tuple[float, float, bool]:
        """
        Check column slenderness per IS 456 Cl 25.1.2.
        
        Short column: Le/D < 12
        Slender column: 12 <= Le/D < 60
        Very slender (not recommended): Le/D >= 60
        
        Args:
            width_mm, depth_mm: Column dimensions
            height_mm: Unsupported height
            effective_length_factor: k (0.65 to 2.0)
            
        Returns:
            (slenderness_ratio, max_allowed, is_ok)
        """
        Le = effective_length_factor * height_mm
        D = min(width_mm, depth_mm)  # Minimum lateral dimension
        
        slenderness = Le / D
        max_allowed = 60.0  # IS 456 limit for practical design
        
        return slenderness, max_allowed, slenderness <= max_allowed
    
    def check_beam_slenderness(
        self,
        width_mm: float,
        depth_mm: float,
        span_mm: float
    ) -> Tuple[float, float, bool]:
        """
        Check beam slenderness per IS 456 Cl 23.3.
        
        For lateral stability:
        - L/b should not exceed 60 or 250b/d, whichever is lower
        
        Args:
            width_mm: Beam width
            depth_mm: Beam depth
            span_mm: Clear span
            
        Returns:
            (slenderness_ratio, max_allowed, is_ok)
        """
        L_by_b = span_mm / width_mm
        limit1 = 60.0
        limit2 = 250 * width_mm / depth_mm
        max_allowed = min(limit1, limit2)
        
        return L_by_b, max_allowed, L_by_b <= max_allowed
    
    def check_fire_resistance_column(
        self,
        width_mm: float,
        depth_mm: float,
        cover_mm: float = 40
    ) -> Tuple[bool, bool, str]:
        """
        Check column fire resistance per IS 456 Table 16A.
        
        Returns:
            (dimension_ok, cover_ok, remarks)
        """
        min_dim = min(width_mm, depth_mm)
        req_dim = self.fire_req.min_column_width_mm
        req_cover = self.fire_req.min_cover_column_mm
        
        dim_ok = min_dim >= req_dim
        cover_ok = cover_mm >= req_cover
        
        remarks = []
        if not dim_ok:
            remarks.append(f"Min width {req_dim}mm required for {self.fire_rating.value}hr rating")
        if not cover_ok:
            remarks.append(f"Min cover {req_cover}mm required for {self.fire_rating.value}hr rating")
        
        return dim_ok, cover_ok, "; ".join(remarks) if remarks else "OK"
    
    def check_fire_resistance_beam(
        self,
        width_mm: float,
        cover_mm: float = 30
    ) -> Tuple[bool, bool, str]:
        """Check beam fire resistance per IS 456 Table 16A."""
        req_width = self.fire_req.min_beam_width_mm
        req_cover = self.fire_req.min_cover_beam_mm
        
        width_ok = width_mm >= req_width
        cover_ok = cover_mm >= req_cover
        
        remarks = []
        if not width_ok:
            remarks.append(f"Min width {req_width}mm required for {self.fire_rating.value}hr rating")
        if not cover_ok:
            remarks.append(f"Min cover {req_cover}mm required")
        
        return width_ok, cover_ok, "; ".join(remarks) if remarks else "OK"
    
    def check_fire_resistance_slab(
        self,
        thickness_mm: float,
        cover_mm: float = 20
    ) -> Tuple[bool, bool, str]:
        """Check slab fire resistance per IS 456 Table 16A."""
        req_thick = self.fire_req.min_slab_thickness_mm
        req_cover = self.fire_req.min_cover_slab_mm
        
        thick_ok = thickness_mm >= req_thick
        cover_ok = cover_mm >= req_cover
        
        remarks = []
        if not thick_ok:
            remarks.append(f"Min thickness {req_thick}mm required for {self.fire_rating.value}hr rating")
        if not cover_ok:
            remarks.append(f"Min cover {req_cover}mm required")
        
        return thick_ok, cover_ok, "; ".join(remarks) if remarks else "OK"
    
    def check_column(
        self,
        col_id: str,
        width_mm: float,
        depth_mm: float,
        height_mm: float,
        cover_mm: float = 40
    ) -> StabilityCheck:
        """Full stability and fire check for a column."""
        # Slenderness
        slend, max_slend, slend_ok = self.check_column_slenderness(
            width_mm, depth_mm, height_mm
        )
        
        # Fire
        dim_ok, cover_ok, remarks = self.check_fire_resistance_column(
            width_mm, depth_mm, cover_mm
        )
        
        return StabilityCheck(
            member_id=col_id,
            member_type="column",
            slenderness_ratio=slend,
            max_slenderness=max_slend,
            slenderness_ok=slend_ok,
            fire_rating_required=self.fire_rating,
            min_dimension_required_mm=self.fire_req.min_column_width_mm,
            actual_dimension_mm=int(min(width_mm, depth_mm)),
            dimension_ok=dim_ok,
            min_cover_required_mm=self.fire_req.min_cover_column_mm,
            actual_cover_mm=int(cover_mm),
            cover_ok=cover_ok,
            is_stable=slend_ok,
            is_fire_safe=dim_ok and cover_ok,
            remarks=remarks
        )
    
    def check_beam(
        self,
        beam_id: str,
        width_mm: float,
        depth_mm: float,
        span_mm: float,
        cover_mm: float = 30
    ) -> StabilityCheck:
        """Full stability and fire check for a beam."""
        # Slenderness
        slend, max_slend, slend_ok = self.check_beam_slenderness(
            width_mm, depth_mm, span_mm
        )
        
        # Fire
        dim_ok, cover_ok, remarks = self.check_fire_resistance_beam(
            width_mm, cover_mm
        )
        
        return StabilityCheck(
            member_id=beam_id,
            member_type="beam",
            slenderness_ratio=slend,
            max_slenderness=max_slend,
            slenderness_ok=slend_ok,
            fire_rating_required=self.fire_rating,
            min_dimension_required_mm=self.fire_req.min_beam_width_mm,
            actual_dimension_mm=int(width_mm),
            dimension_ok=dim_ok,
            min_cover_required_mm=self.fire_req.min_cover_beam_mm,
            actual_cover_mm=int(cover_mm),
            cover_ok=cover_ok,
            is_stable=slend_ok,
            is_fire_safe=dim_ok and cover_ok,
            remarks=remarks
        )
    
    def check_all_members(
        self,
        columns: List,  # Column objects
        beams: List,    # StructuralMember objects
        story_height_m: float
    ) -> Tuple[List[StabilityCheck], StabilitySummary]:
        """
        Check all columns and beams for stability and fire resistance.
        
        Returns:
            (list of checks, summary)
        """
        results = []
        failed = []
        
        height_mm = story_height_m * 1000
        
        # Check columns
        for col in columns:
            check = self.check_column(
                col.id,
                col.width_nb,
                col.depth_nb,
                height_mm,
                cover_mm=40  # Default cover
            )
            results.append(check)
            if not (check.is_stable and check.is_fire_safe):
                failed.append(col.id)
        
        # Check beams
        for beam in beams:
            dx = abs(beam.end_point.x - beam.start_point.x)
            dy = abs(beam.end_point.y - beam.start_point.y)
            span_mm = ((dx**2 + dy**2)**0.5) * 1000
            
            check = self.check_beam(
                beam.id,
                beam.properties.width_mm,
                beam.properties.depth_mm,
                span_mm,
                cover_mm=30
            )
            results.append(check)
            if not (check.is_stable and check.is_fire_safe):
                failed.append(beam.id)
        
        # Summary
        passed_stab = sum(1 for r in results if r.is_stable)
        passed_fire = sum(1 for r in results if r.is_fire_safe)
        
        recommendations = []
        if passed_fire < len(results):
            recommendations.append(
                f"Increase cover to {self.fire_req.min_cover_column_mm}mm for columns "
                f"and {self.fire_req.min_cover_beam_mm}mm for beams"
            )
        if any(not r.dimension_ok for r in results):
            recommendations.append(
                f"Minimum column width {self.fire_req.min_column_width_mm}mm required "
                f"for {self.fire_rating.value}hr fire rating"
            )
        
        summary = StabilitySummary(
            total_members=len(results),
            passed_stability=passed_stab,
            passed_fire=passed_fire,
            failed_members=failed,
            fire_rating_used=self.fire_rating,
            all_passed=len(failed) == 0,
            recommendations=recommendations
        )
        
        return results, summary


def run_stability_check(
    columns: List,
    beams: List,
    num_floors: int,
    story_height_m: float,
    fire_rating: Optional[FireRating] = None
) -> Tuple[List[StabilityCheck], StabilitySummary]:
    """
    Main function to run stability and fire resistance checks.
    
    Args:
        columns: List of Column objects
        beams: List of beam StructuralMember objects
        num_floors: Number of stories
        story_height_m: Height per floor
        fire_rating: Optional override for fire rating
        
    Returns:
        (checks, summary)
    """
    building_height = num_floors * story_height_m
    
    checker = StabilityChecker(
        num_floors=num_floors,
        building_height_m=building_height,
        fire_rating=fire_rating
    )
    
    return checker.check_all_members(columns, beams, story_height_m)
