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
def _fire_table() -> Dict["FireRating", FireResistanceRequirements]:
    """IS 456 Fig. 1 (minimum dimensions; columns fully exposed) and Table 16A (covers; beams continuous, slabs
    simply supported, columns 40 mm) - built from src/durability.py, checked against the printed standard on
    2026-10-20 (the previous transcription had column covers of 20-30 mm and a 200 mm column at 1.5 h)."""
    from .durability import FIG1_MIN, TABLE16A
    out = {}
    for rating in FireRating:
        h = float(rating.value)
        b, d, col, _, _ = FIG1_MIN[h]
        _bss, bcont, sss, _scont, ccol = TABLE16A[h]
        out[rating] = FireResistanceRequirements(
            fire_rating=rating, min_column_width_mm=col, min_beam_width_mm=b, min_slab_thickness_mm=d,
            min_cover_column_mm=ccol, min_cover_beam_mm=bcont, min_cover_slab_mm=sss,
            description=f"{rating.value} hour fire resistance (IS 456 Fig. 1, Table 16A)")
    return out


FIRE_RESISTANCE_TABLE = _fire_table()


def rating_for_hours(h: float) -> "FireRating":
    return {0.5: FireRating.HALF_HOUR, 1.0: FireRating.ONE_HOUR, 1.5: FireRating.ONE_HALF_HOUR,
            2.0: FireRating.TWO_HOUR, 3.0: FireRating.THREE_HOUR, 4.0: FireRating.FOUR_HOUR}[h]


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
        fire_rating: Optional[FireRating] = None,
        requirements=None,
    ):
        """Fire ratings per element come from NBC 2016 Part 4 Table 1 for the type of construction
        (``requirements``: src.durability.DurabilityRequirements). The previous rule by number of floors and
        height is not in NBC and was removed (2026-10-20). ``fire_rating`` forces one rating for every member."""
        from .durability import requirements as _requirements
        self.num_floors = num_floors
        self.building_height_m = building_height_m
        self.exposure = exposure
        self.req = requirements or _requirements("Moderate", 2)
        self.forced_rating = fire_rating
        self.fire_rating = fire_rating or rating_for_hours(self.req.column_fire_h)
        self.fire_req = FIRE_RESISTANCE_TABLE[self.fire_rating]

    def _rating(self, hours_: float) -> FireRating:
        return self.forced_rating or rating_for_hours(hours_)
    
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
        if width_mm <= 0 or depth_mm <= 0:
            raise ValueError("Invalid member dimensions (zero or negative)")
            
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
        if width_mm <= 0 or depth_mm <= 0:
            raise ValueError("Invalid member dimensions (zero or negative)")
            
        L_by_b = span_mm / width_mm
        limit1 = 60.0
        limit2 = 250 * width_mm / depth_mm
        max_allowed = min(limit1, limit2)
        
        return L_by_b, max_allowed, L_by_b <= max_allowed
    
    def check_fire_resistance_column(
        self,
        width_mm: float,
        depth_mm: float,
        cover_mm: float = 40,
        rating: Optional[FireRating] = None,
        wall_dir: Optional[str] = None,
    ) -> Tuple[bool, bool, str]:
        """
        Check column fire resistance per IS 456 Fig. 1 and Table 16A. Free-standing columns: "fully exposed", least
        dimension. Columns built into a wall line (``wall_dir`` "x" / "y"): "50 % exposed", the dimension along
        the wall (Fig. 1 sketch).

        Returns:
            (dimension_ok, cover_ok, remarks)
        """
        fr = FIRE_RESISTANCE_TABLE[rating or self.fire_rating]
        min_dim = min(width_mm, depth_mm)
        req_dim = fr.min_column_width_mm
        if wall_dir in ("x", "y"):
            from .durability import FIG1_MIN
            min_dim = width_mm if wall_dir == "x" else depth_mm
            req_dim = FIG1_MIN[float(fr.fire_rating.value)][3]
        req_cover = fr.min_cover_column_mm
        
        dim_ok = min_dim >= req_dim
        cover_ok = cover_mm >= req_cover
        
        remarks = []
        if not dim_ok:
            where = "along the wall, 50 % exposed" if wall_dir in ("x", "y") else "fully exposed"
            remarks.append(f"Min width {req_dim}mm ({where}) required for {fr.fire_rating.value}hr rating (IS 456 Fig. 1)")
        if not cover_ok:
            remarks.append(f"Min cover {req_cover}mm required for {fr.fire_rating.value}hr rating (IS 456 Table 16A)")
        
        return dim_ok, cover_ok, "; ".join(remarks) if remarks else "OK"
    
    def check_fire_resistance_beam(
        self,
        width_mm: float,
        cover_mm: float = 30,
        rating: Optional[FireRating] = None,
    ) -> Tuple[bool, bool, str]:
        """Check beam fire resistance per IS 456 Fig. 1 and Table 16A (continuous beam)."""
        fr = FIRE_RESISTANCE_TABLE[rating or self.fire_rating]
        req_width = fr.min_beam_width_mm
        req_cover = fr.min_cover_beam_mm
        
        width_ok = width_mm >= req_width
        cover_ok = cover_mm >= req_cover
        
        remarks = []
        if not width_ok:
            remarks.append(f"Min width {req_width}mm required for {fr.fire_rating.value}hr rating (IS 456 Fig. 1)")
        if not cover_ok:
            remarks.append(f"Min cover {req_cover}mm required")
        
        return width_ok, cover_ok, "; ".join(remarks) if remarks else "OK"
    
    def check_fire_resistance_slab(
        self,
        thickness_mm: float,
        cover_mm: float = 20,
        rating: Optional[FireRating] = None,
    ) -> Tuple[bool, bool, str]:
        """Check slab fire resistance per IS 456 Fig. 1 and Table 16A (simply supported slab, conservative)."""
        fr = FIRE_RESISTANCE_TABLE[rating or self.fire_rating]
        req_thick = fr.min_slab_thickness_mm
        req_cover = fr.min_cover_slab_mm
        
        thick_ok = thickness_mm >= req_thick
        cover_ok = cover_mm >= req_cover
        
        remarks = []
        if not thick_ok:
            remarks.append(f"Min thickness {req_thick}mm required for {fr.fire_rating.value}hr rating (IS 456 Fig. 1)")
        if not cover_ok:
            remarks.append(f"Min cover {req_cover}mm required")
        
        return thick_ok, cover_ok, "; ".join(remarks) if remarks else "OK"
    
    def check_column(
        self,
        col_id: str,
        width_mm: float,
        depth_mm: float,
        height_mm: float,
        cover_mm: float = 40,
        rating: Optional[FireRating] = None,
        wall_dir: Optional[str] = None,
    ) -> StabilityCheck:
        """Full stability and fire check for a column."""
        rating = rating or self.fire_rating
        fr = FIRE_RESISTANCE_TABLE[rating]
        # Slenderness
        slend, max_slend, slend_ok = self.check_column_slenderness(
            width_mm, depth_mm, height_mm
        )
        
        # Fire
        dim_ok, cover_ok, remarks = self.check_fire_resistance_column(
            width_mm, depth_mm, cover_mm, rating, wall_dir=wall_dir
        )
        
        return StabilityCheck(
            member_id=col_id,
            member_type="column",
            slenderness_ratio=slend,
            max_slenderness=max_slend,
            slenderness_ok=slend_ok,
            fire_rating_required=rating,
            min_dimension_required_mm=fr.min_column_width_mm,
            actual_dimension_mm=int(min(width_mm, depth_mm)),
            dimension_ok=dim_ok,
            min_cover_required_mm=fr.min_cover_column_mm,
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
        cover_mm: float = 30,
        rating: Optional[FireRating] = None,
    ) -> StabilityCheck:
        """Full stability and fire check for a beam."""
        rating = rating or self.fire_rating
        fr = FIRE_RESISTANCE_TABLE[rating]
        # Slenderness
        slend, max_slend, slend_ok = self.check_beam_slenderness(
            width_mm, depth_mm, span_mm
        )
        
        # Fire
        dim_ok, cover_ok, remarks = self.check_fire_resistance_beam(
            width_mm, cover_mm, rating
        )
        
        return StabilityCheck(
            member_id=beam_id,
            member_type="beam",
            slenderness_ratio=slend,
            max_slenderness=max_slend,
            slenderness_ok=slend_ok,
            fire_rating_required=rating,
            min_dimension_required_mm=fr.min_beam_width_mm,
            actual_dimension_mm=int(width_mm),
            dimension_ok=dim_ok,
            min_cover_required_mm=fr.min_cover_beam_mm,
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
        story_height_m: float,
        column_cover_mm: float = 40.0,
        beam_cover_mm: float = 25.0,
        slabs: Optional[List[Tuple[str, float]]] = None,
        slab_cover_mm: float = 20.0,
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
            # NBC Table 1: columns below the top storey support more than one floor; top-storey columns the roof only
            more_than_one = getattr(col, "level", 0) < self.num_floors - 1
            check = self.check_column(
                col.id,
                col.width_nb,
                col.depth_nb,
                height_mm,
                cover_mm=column_cover_mm,  # clear cover used by rebar_detailer
                rating=self._rating(self.req.column_fire_hours(more_than_one)),
                wall_dir=getattr(col, "wall_dir", None),
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
                cover_mm=beam_cover_mm,  # clear cover used by rebar_detailer
                rating=self._rating(self.req.beam_fire_h),
            )
            results.append(check)
            if not (check.is_stable and check.is_fire_safe):
                failed.append(beam.id)

        # Slabs: NBC Table 1 floor construction; IS 456 Fig. 1 thickness and Table 16A cover
        for sid, thk in slabs or []:
            rating = self._rating(self.req.slab_fire_h)
            fr = FIRE_RESISTANCE_TABLE[rating]
            thick_ok, cover_ok, remarks = self.check_fire_resistance_slab(thk, slab_cover_mm, rating)
            results.append(StabilityCheck(
                member_id=sid, member_type="slab", slenderness_ratio=0.0, max_slenderness=0.0, slenderness_ok=True,
                fire_rating_required=rating, min_dimension_required_mm=fr.min_slab_thickness_mm,
                actual_dimension_mm=int(thk), dimension_ok=thick_ok, min_cover_required_mm=fr.min_cover_slab_mm,
                actual_cover_mm=int(slab_cover_mm), cover_ok=cover_ok, is_stable=True,
                is_fire_safe=thick_ok and cover_ok, remarks=remarks))
            if not (thick_ok and cover_ok):
                failed.append(sid)
        
        # Summary
        passed_stab = sum(1 for r in results if r.is_stable)
        passed_fire = sum(1 for r in results if r.is_fire_safe)
        
        recommendations = sorted({f"{r.member_type.title()} {r.member_id}: {r.remarks}" for r in results
                                  if not r.is_fire_safe})[:20]
        
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
    fire_rating: Optional[FireRating] = None,
    column_cover_mm: float = 40.0,
    beam_cover_mm: float = 25.0,
    requirements=None,
    slabs: Optional[List[Tuple[str, float]]] = None,
    slab_cover_mm: float = 20.0,
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
        fire_rating=fire_rating,
        requirements=requirements,
    )
    
    return checker.check_all_members(columns, beams, story_height_m, column_cover_mm, beam_cover_mm, slabs,
                                     slab_cover_mm)
