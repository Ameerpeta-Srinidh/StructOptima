"""
Structural Checks Module - Edge Case Detection

Implements structural validation checks per IS 1893:2016 and IS 13920:2016:
- Soft Storey Detection
- Short/Captive Column Detection
- Cantilever Back-Span Verification
- Core/Shaft Handling (Stairwells, Lift Cores)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from enum import Enum
import math

from .logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class SoftStoreyResult:
    floor_level: int
    is_soft_storey: bool
    stiffness_ratio: float
    wall_density_ratio: float
    recommendation: str
    code_reference: str = "IS 1893:2016 Table 5"


@dataclass
class ShortColumnResult:
    column_id: str
    is_captive: bool
    clear_height_mm: float
    restrained_height_mm: float
    effective_slenderness: float
    recommendation: str
    code_reference: str = "IS 13920:2016 Clause 10"


@dataclass
class CantileverResult:
    beam_id: str
    cantilever_length_mm: float
    has_back_span: bool
    back_span_length_mm: float
    is_safe: bool
    recommendation: str


@dataclass
class CoreZone:
    zone_type: str
    center_x: float
    center_y: float
    width: float
    depth: float
    recommendation: str


class SoftStoreyChecker:
    SOFT_STOREY_STIFFNESS_RATIO = 0.7
    EXTREME_SOFT_STOREY_RATIO = 0.6
    
    def __init__(self):
        pass
    
    def check_soft_storey(
        self,
        floor_stiffnesses: List[float],
        floor_column_counts: List[int],
        floor_wall_lengths: List[float]
    ) -> List[SoftStoreyResult]:
        results = []
        
        if len(floor_stiffnesses) < 2:
            return results
        
        for i in range(len(floor_stiffnesses) - 1):
            lower_stiffness = floor_stiffnesses[i]
            upper_stiffness = floor_stiffnesses[i + 1]
            
            if upper_stiffness == 0:
                continue
            
            stiffness_ratio = lower_stiffness / upper_stiffness
            
            lower_cols = floor_column_counts[i] if i < len(floor_column_counts) else 0
            upper_cols = floor_column_counts[i + 1] if i + 1 < len(floor_column_counts) else 0
            col_ratio = lower_cols / max(upper_cols, 1)
            
            lower_walls = floor_wall_lengths[i] if i < len(floor_wall_lengths) else 0
            upper_walls = floor_wall_lengths[i + 1] if i + 1 < len(floor_wall_lengths) else 0
            wall_ratio = lower_walls / max(upper_walls, 1)
            
            is_soft = stiffness_ratio < self.SOFT_STOREY_STIFFNESS_RATIO
            is_extreme = stiffness_ratio < self.EXTREME_SOFT_STOREY_RATIO
            
            if is_soft:
                if is_extreme:
                    recommendation = (
                        f"CRITICAL: Floor {i} is an EXTREME SOFT STOREY. "
                        "Add shear walls or increase column sizes by 2.5x design forces. "
                        "Consider seismic isolation or energy dissipation devices."
                    )
                else:
                    recommendation = (
                        f"WARNING: Floor {i} is a SOFT STOREY. "
                        "Increase column stiffness or add infill walls. "
                        "Design for 2.5x seismic forces per IS 1893."
                    )
                
                results.append(SoftStoreyResult(
                    floor_level=i,
                    is_soft_storey=True,
                    stiffness_ratio=stiffness_ratio,
                    wall_density_ratio=wall_ratio,
                    recommendation=recommendation
                ))
                logger.warning(f"Soft storey detected at floor {i}: stiffness ratio = {stiffness_ratio:.2f}")
            
            if wall_ratio < 0.5 and col_ratio < 0.8:
                if not is_soft:
                    results.append(SoftStoreyResult(
                        floor_level=i,
                        is_soft_storey=False,
                        stiffness_ratio=stiffness_ratio,
                        wall_density_ratio=wall_ratio,
                        recommendation=(
                            f"INFO: Floor {i} has lower wall density ({wall_ratio:.1%}). "
                            "Verify this is intentional (e.g., parking floor)."
                        )
                    ))
        
        return results


class ShortColumnChecker:
    MIN_SLENDERNESS_FOR_SHORT = 4.0
    
    def __init__(self):
        pass
    
    def detect_short_columns(
        self,
        columns: List[Dict],
        intermediate_beams: List[Dict]
    ) -> List[ShortColumnResult]:
        results = []
        
        for col in columns:
            col_x = col.get('x', 0)
            col_y = col.get('y', 0)
            col_depth = col.get('depth', 300)
            full_height = col.get('height', 3000)
            
            restraining_beams = []
            for beam in intermediate_beams:
                beam_start = beam.get('start', (0, 0))
                beam_end = beam.get('end', (0, 0))
                beam_z = beam.get('z', 0)
                
                if beam_z > 0 and beam_z < full_height:
                    dist_to_start = math.hypot(col_x - beam_start[0], col_y - beam_start[1])
                    dist_to_end = math.hypot(col_x - beam_end[0], col_y - beam_end[1])
                    
                    if dist_to_start < 500 or dist_to_end < 500:
                        restraining_beams.append(beam_z)
            
            if restraining_beams:
                min_restrained_height = min(restraining_beams)
                clear_height = min_restrained_height
                slenderness = clear_height / col_depth
                
                is_captive = slenderness < self.MIN_SLENDERNESS_FOR_SHORT
                
                if is_captive:
                    recommendation = (
                        f"CAPTIVE COLUMN: {col.get('id', 'Unknown')} has clear height {clear_height:.0f}mm "
                        f"(slenderness {slenderness:.1f}). Provide special confining reinforcement "
                        "over FULL HEIGHT per IS 13920 Clause 10."
                    )
                else:
                    recommendation = (
                        f"Column {col.get('id', 'Unknown')} has intermediate restraint at {min_restrained_height:.0f}mm. "
                        "Check for short column effects in seismic design."
                    )
                
                results.append(ShortColumnResult(
                    column_id=col.get('id', 'Unknown'),
                    is_captive=is_captive,
                    clear_height_mm=clear_height,
                    restrained_height_mm=min_restrained_height,
                    effective_slenderness=slenderness,
                    recommendation=recommendation
                ))
                
                if is_captive:
                    logger.warning(f"Captive column detected: {col.get('id')}")
        
        return results


class CantileverChecker:
    MAX_SAFE_CANTILEVER_MM = 1500.0
    MIN_BACK_SPAN_RATIO = 2.0
    
    def __init__(self):
        pass
    
    def verify_cantilevers(
        self,
        beams: List[Dict],
        columns: List[Dict]
    ) -> List[CantileverResult]:
        results = []
        
        column_positions = set()
        for col in columns:
            column_positions.add((round(col.get('x', 0), 0), round(col.get('y', 0), 0)))
        
        for beam in beams:
            start = beam.get('start', (0, 0))
            end = beam.get('end', (0, 0))
            
            start_key = (round(start[0], 0), round(start[1], 0))
            end_key = (round(end[0], 0), round(end[1], 0))
            
            start_supported = start_key in column_positions
            end_supported = end_key in column_positions
            
            if start_supported and not end_supported:
                cantilever_length = math.hypot(end[0] - start[0], end[1] - start[1])
                back_beam = self._find_back_span(start, beam, beams, column_positions)
                
                is_safe = True
                back_span_length = 0.0
                
                if cantilever_length > self.MAX_SAFE_CANTILEVER_MM:
                    if back_beam:
                        back_span_length = back_beam.get('length', 0)
                        if back_span_length < cantilever_length * self.MIN_BACK_SPAN_RATIO:
                            is_safe = False
                    else:
                        is_safe = False
                
                recommendation = ""
                if not is_safe:
                    recommendation = (
                        f"CRITICAL: Cantilever beam {beam.get('id', 'Unknown')} ({cantilever_length:.0f}mm) "
                        f"needs back-span ≥ {cantilever_length * self.MIN_BACK_SPAN_RATIO:.0f}mm to interior column. "
                        "Risk of overturning."
                    )
                elif cantilever_length > self.MAX_SAFE_CANTILEVER_MM:
                    recommendation = (
                        f"INFO: Large cantilever ({cantilever_length:.0f}mm) at {beam.get('id', 'Unknown')}. "
                        "Verify deflection and vibration criteria."
                    )
                
                if recommendation:
                    results.append(CantileverResult(
                        beam_id=beam.get('id', 'Unknown'),
                        cantilever_length_mm=cantilever_length,
                        has_back_span=back_beam is not None,
                        back_span_length_mm=back_span_length,
                        is_safe=is_safe,
                        recommendation=recommendation
                    ))
        
        return results
    
    def _find_back_span(
        self,
        support_point: Tuple[float, float],
        cantilever_beam: Dict,
        all_beams: List[Dict],
        column_positions: set
    ) -> Optional[Dict]:
        for beam in all_beams:
            if beam.get('id') == cantilever_beam.get('id'):
                continue
            
            start = beam.get('start', (0, 0))
            end = beam.get('end', (0, 0))
            
            dist_to_start = math.hypot(support_point[0] - start[0], support_point[1] - start[1])
            dist_to_end = math.hypot(support_point[0] - end[0], support_point[1] - end[1])
            
            if dist_to_start < 500:
                end_key = (round(end[0], 0), round(end[1], 0))
                if end_key in column_positions:
                    length = math.hypot(end[0] - start[0], end[1] - start[1])
                    return {'id': beam.get('id'), 'length': length}
            elif dist_to_end < 500:
                start_key = (round(start[0], 0), round(start[1], 0))
                if start_key in column_positions:
                    length = math.hypot(end[0] - start[0], end[1] - start[1])
                    return {'id': beam.get('id'), 'length': length}
        
        return None


class CoreShaftHandler:
    STAIRWELL_MIN_WIDTH = 2400.0
    STAIRWELL_MAX_WIDTH = 4000.0
    LIFT_MIN_WIDTH = 1800.0
    LIFT_MAX_WIDTH = 2500.0
    
    def __init__(self):
        pass
    
    def detect_core_zones(
        self,
        enclosed_rectangles: List[Tuple[float, float, float, float]]
    ) -> List[CoreZone]:
        cores = []
        
        for (x, y, width, depth) in enclosed_rectangles:
            min_dim = min(width, depth)
            max_dim = max(width, depth)
            
            if self.STAIRWELL_MIN_WIDTH <= min_dim <= self.STAIRWELL_MAX_WIDTH:
                if max_dim <= 6000:
                    zone_type = "stairwell"
                    recommendation = (
                        f"Stairwell core detected at ({x:.0f}, {y:.0f}). "
                        "Replace corner columns with C-shape or Box shear wall for lateral stiffness."
                    )
                    cores.append(CoreZone(
                        zone_type=zone_type,
                        center_x=x,
                        center_y=y,
                        width=width,
                        depth=depth,
                        recommendation=recommendation
                    ))
            
            elif self.LIFT_MIN_WIDTH <= min_dim <= self.LIFT_MAX_WIDTH:
                if max_dim <= 3500:
                    zone_type = "lift"
                    recommendation = (
                        f"Lift core detected at ({x:.0f}, {y:.0f}). "
                        "Provide shear wall around lift pit. Do NOT place isolated columns at pit corners."
                    )
                    cores.append(CoreZone(
                        zone_type=zone_type,
                        center_x=x,
                        center_y=y,
                        width=width,
                        depth=depth,
                        recommendation=recommendation
                    ))
        
        return cores


def run_all_checks(
    columns: List[Dict],
    beams: List[Dict],
    floor_data: Optional[Dict] = None,
    intermediate_beams: Optional[List[Dict]] = None,
    enclosed_zones: Optional[List[Tuple]] = None
) -> Dict:
    results = {
        "soft_storey": [],
        "short_columns": [],
        "cantilevers": [],
        "core_zones": [],
        "summary": {
            "has_critical_issues": False,
            "critical_count": 0,
            "warning_count": 0
        }
    }
    
    if floor_data:
        checker = SoftStoreyChecker()
        soft_results = checker.check_soft_storey(
            floor_data.get('stiffnesses', []),
            floor_data.get('column_counts', []),
            floor_data.get('wall_lengths', [])
        )
        results["soft_storey"] = [r.__dict__ for r in soft_results]
        for r in soft_results:
            if r.is_soft_storey:
                results["summary"]["critical_count"] += 1
                results["summary"]["has_critical_issues"] = True
    
    if intermediate_beams:
        checker = ShortColumnChecker()
        short_results = checker.detect_short_columns(columns, intermediate_beams)
        results["short_columns"] = [r.__dict__ for r in short_results]
        for r in short_results:
            if r.is_captive:
                results["summary"]["critical_count"] += 1
                results["summary"]["has_critical_issues"] = True
    
    cantilever_checker = CantileverChecker()
    cantilever_results = cantilever_checker.verify_cantilevers(beams, columns)
    results["cantilevers"] = [r.__dict__ for r in cantilever_results]
    for r in cantilever_results:
        if not r.is_safe:
            results["summary"]["critical_count"] += 1
            results["summary"]["has_critical_issues"] = True
        else:
            results["summary"]["warning_count"] += 1
    
    if enclosed_zones:
        handler = CoreShaftHandler()
        core_results = handler.detect_core_zones(enclosed_zones)
        results["core_zones"] = [c.__dict__ for c in core_results]
    
    return results
