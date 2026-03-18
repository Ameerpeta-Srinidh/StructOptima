"""
Beam Placement Module - IS 456:2000 & IS 13920:2016 Compliant

Implements realistic residential beam placement following structural engineering practices:
- Phase 1: Primary beams (column-to-column frame)
- Phase 2: Secondary beams (slab breaking, wall support)
- Phase 3: Cantilever detection and back-span verification
- Phase 4: IS-code sizing (L/d ratios)
- Phase 5: Validation checks (hierarchy, eccentricity, deep beams)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Set
from enum import Enum
import math
import json

from .logging_config import get_logger

logger = get_logger(__name__)


class BeamType(Enum):
    PRIMARY = "Primary"
    SECONDARY = "Secondary"
    CANTILEVER = "Cantilever"
    WALL_SUPPORT = "Wall_Support"


class SupportType(Enum):
    COLUMN_COLUMN = "Column-Column"
    BEAM_BEAM = "Beam-Beam"
    COLUMN_BEAM = "Column-Beam"
    CANTILEVER = "Cantilever"


class ReinforcementLogic(Enum):
    SINGLY_REINFORCED = "Singly_Reinforced"
    DOUBLY_REINFORCED = "Doubly_Reinforced"


@dataclass
class BeamPlacement:
    id: str
    beam_type: BeamType
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    span_mm: float
    width_mm: float = 230.0
    depth_mm: float = 450.0
    start_node: str = ""
    end_node: str = ""
    support_type: SupportType = SupportType.COLUMN_COLUMN
    is_cantilever: bool = False
    back_span_mm: float = 0.0
    supported_by: List[str] = field(default_factory=list)
    reinforcement_logic: ReinforcementLogic = ReinforcementLogic.SINGLY_REINFORCED
    warnings: List[str] = field(default_factory=list)
    is_hidden_in_wall: bool = True
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.beam_type.value,
            "start_node": self.start_node,
            "end_node": self.end_node,
            "span_mm": round(self.span_mm, 0),
            "section": {"width": int(self.width_mm), "depth": int(self.depth_mm)},
            "support_type": self.support_type.value,
            "is_cantilever": self.is_cantilever,
            "reinforcement_logic": self.reinforcement_logic.value,
            "is_hidden_in_wall": self.is_hidden_in_wall,
            "warnings": self.warnings
        }


@dataclass
class SlabPanel:
    id: str
    vertices: List[Tuple[float, float]]
    area_m2: float
    short_span_mm: float
    long_span_mm: float
    aspect_ratio: float
    bounding_beams: List[str]
    needs_secondary: bool = False


@dataclass
class PlacementResult:
    beams: List[BeamPlacement] = field(default_factory=list)
    slab_panels: List[SlabPanel] = field(default_factory=list)
    warnings: List[Dict] = field(default_factory=list)
    stats: Dict = field(default_factory=dict)
    
    def to_json(self) -> str:
        return json.dumps({
            "beams": [b.to_dict() for b in self.beams],
            "slab_panels": [{"id": p.id, "area_m2": p.area_m2, "needs_secondary": p.needs_secondary} 
                          for p in self.slab_panels],
            "warnings": self.warnings,
            "stats": self.stats
        }, indent=2)


class BeamPlacer:
    MAX_SLAB_SPAN_MM = 6000.0
    MAX_SLAB_AREA_M2 = 35.0
    MIN_BACK_SPAN_RATIO = 1.5
    MAX_CANTILEVER_MM = 2500.0  # Increased for balconies
    MIN_BEAM_WIDTH_MM = 200.0
    WALL_THICKNESS_MM = 230.0
    MIN_BD_RATIO = 0.3
    GRID_TOLERANCE_MM = 100.0
    PROXIMITY_TOLERANCE_MM = 500.0
    
    # Engineering Constants
    CRITICAL_SPAN_MM = 7000.0
    MIN_BEAM_DEPTH_MM = 400.0
    DEFAULT_SLAB_THICKNESS_MM = 125.0
    
    def __init__(
        self,
        columns: List[Dict],
        walls: List[Tuple[Tuple[float, float], Tuple[float, float]]],
        slab_boundary: Optional[List[Tuple[float, float]]] = None,
        seismic_zone: str = "III",
        floor_height_mm: float = 3000.0
    ):
        self.columns = columns
        self.walls = walls
        self.slab_boundary = slab_boundary
        self.seismic_zone = seismic_zone
        self.floor_height_mm = floor_height_mm
        self.is_seismic = seismic_zone in ["III", "IV", "V"]
        
        self.beams: List[BeamPlacement] = []
        self.primary_beams: List[BeamPlacement] = []
        self.secondary_beams: List[BeamPlacement] = []
        self.cantilever_beams: List[BeamPlacement] = []
        self.slab_panels: List[SlabPanel] = []
        self.warnings: List[Dict] = []
        
        self.column_positions = {(c.get('x', c.get('x')), c.get('y', c.get('y'))): c 
                                 for c in columns}
        self.column_ids = {(c.get('x'), c.get('y')): c.get('id', f"C{i}") 
                          for i, c in enumerate(columns)}
        
        self._compute_column_hull()
        self._compute_grid_lines()
    
    def _compute_column_hull(self):
        if not self.columns:
            self.column_hull = []
            return
        xs = [c.get('x', 0) for c in self.columns]
        ys = [c.get('y', 0) for c in self.columns]
        self.min_x, self.max_x = min(xs), max(xs)
        self.min_y, self.max_y = min(ys), max(ys)
        self.column_hull = [
            (self.min_x, self.min_y), (self.max_x, self.min_y),
            (self.max_x, self.max_y), (self.min_x, self.max_y)
        ]
    
    def _compute_grid_lines(self):
        xs = sorted(set(c.get('x', 0) for c in self.columns))
        ys = sorted(set(c.get('y', 0) for c in self.columns))
        
        self.x_grids = []
        for x in xs:
            group = [x]
            for other_x in xs:
                if x != other_x and abs(x - other_x) < self.GRID_TOLERANCE_MM:
                    group.append(other_x)
            self.x_grids.append(sum(group) / len(group))
        self.x_grids = sorted(set(self.x_grids))
        
        self.y_grids = []
        for y in ys:
            group = [y]
            for other_y in ys:
                if y != other_y and abs(y - other_y) < self.GRID_TOLERANCE_MM:
                    group.append(other_y)
            self.y_grids.append(sum(group) / len(group))
        self.y_grids = sorted(set(self.y_grids))
        
        logger.info(f"Grid lines: X={len(self.x_grids)}, Y={len(self.y_grids)}")
    
    def _is_close(self, p1: Tuple[float, float], p2: Tuple[float, float], tol: float = None) -> bool:
        if tol is None:
            tol = self.PROXIMITY_TOLERANCE_MM
        return math.hypot(p1[0] - p2[0], p1[1] - p2[1]) < tol
    
    def _get_column_at(self, x: float, y: float) -> Optional[Dict]:
        for col in self.columns:
            if self._is_close((x, y), (col.get('x'), col.get('y'))):
                return col
        return None
    
    def _get_column_id(self, x: float, y: float) -> str:
        for (cx, cy), cid in self.column_ids.items():
            if self._is_close((x, y), (cx, cy)):
                return cid
        return "Unknown"
    
    def _wall_exists_between(self, p1: Tuple[float, float], p2: Tuple[float, float]) -> bool:
        beam_len = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        if beam_len < 1:
            return False
        
        num_samples = max(3, int(beam_len / 1000))
        wall_tolerance = 500.0
        
        for start, end in self.walls:
            v_beam = (p2[0] - p1[0], p2[1] - p1[1])
            v_wall = (end[0] - start[0], end[1] - start[1])
            
            beam_mag = math.hypot(v_beam[0], v_beam[1])
            wall_mag = math.hypot(v_wall[0], v_wall[1])
            
            if wall_mag < 1:
                continue
            
            dot = (v_beam[0] * v_wall[0] + v_beam[1] * v_wall[1]) / (beam_mag * wall_mag)
            dot = max(-1.0, min(1.0, dot))
            angle = math.degrees(math.acos(abs(dot)))
            
            if angle > 15.0:
                continue
            
            points_near_wall = 0
            for i in range(num_samples):
                t = (i + 0.5) / num_samples
                sx = p1[0] + t * (p2[0] - p1[0])
                sy = p1[1] + t * (p2[1] - p1[1])
                dist = self._point_to_segment_dist((sx, sy), start, end)
                if dist < wall_tolerance:
                    points_near_wall += 1
            
            if points_near_wall >= num_samples * 0.5:
                return True
        
        return False
    
    def _point_to_segment_dist(self, p, a, b) -> float:
        px, py = p
        ax, ay = a
        bx, by = b
        
        l2 = (bx - ax) ** 2 + (by - ay) ** 2
        if l2 == 0:
            return math.hypot(px - ax, py - ay)
        
        t = ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / l2
        t = max(0, min(1, t))
        
        proj_x = ax + t * (bx - ax)
        proj_y = ay + t * (by - ay)
        
        return math.hypot(px - proj_x, py - proj_y)
    
    def _place_primary_beams(self):
        beam_count = 0
        placed_pairs: Set[Tuple[float, float, float, float]] = set()
        
        for x in self.x_grids:
            cols_on_line = [c for c in self.columns 
                           if abs(c.get('x', 0) - x) < self.GRID_TOLERANCE_MM]
            cols_on_line.sort(key=lambda c: c.get('y', 0))
            
            for i in range(len(cols_on_line) - 1):
                c1 = cols_on_line[i]
                c2 = cols_on_line[i + 1]
                
                x1, y1 = c1.get('x'), c1.get('y')
                x2, y2 = c2.get('x'), c2.get('y')
                span = math.hypot(x2 - x1, y2 - y1)
                
                pair_key = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
                if pair_key in placed_pairs:
                    continue
                placed_pairs.add(pair_key)
                
                has_wall = self._wall_exists_between((x1, y1), (x2, y2))
                
                beam_count += 1
                depth = self._calculate_depth(span, SupportType.COLUMN_COLUMN)
                width = self.WALL_THICKNESS_MM if has_wall else self.MIN_BEAM_WIDTH_MM
                
                beam = BeamPlacement(
                    id=f"B{beam_count}",
                    beam_type=BeamType.PRIMARY,
                    start_x=x1, start_y=y1,
                    end_x=x2, end_y=y2,
                    span_mm=span,
                    width_mm=width,
                    depth_mm=depth,
                    start_node=self._get_column_id(x1, y1),
                    end_node=self._get_column_id(x2, y2),
                    support_type=SupportType.COLUMN_COLUMN,
                    is_hidden_in_wall=has_wall
                )
                
                if not has_wall:
                    beam.warnings.append("Beam crosses open area - visible in ceiling")
                    self.warnings.append({
                        "severity": "INFO",
                        "message": f"Beam {beam.id} not hidden in wall - architectural review needed",
                        "beam_id": beam.id
                    })
                
                self.primary_beams.append(beam)
                logger.info(f"Primary beam {beam.id}: {beam.start_node} -> {beam.end_node} ({span:.0f}mm)")
        
        for y in self.y_grids:
            cols_on_line = [c for c in self.columns 
                           if abs(c.get('y', 0) - y) < self.GRID_TOLERANCE_MM]
            cols_on_line.sort(key=lambda c: c.get('x', 0))
            
            for i in range(len(cols_on_line) - 1):
                c1 = cols_on_line[i]
                c2 = cols_on_line[i + 1]
                
                x1, y1 = c1.get('x'), c1.get('y')
                x2, y2 = c2.get('x'), c2.get('y')
                span = math.hypot(x2 - x1, y2 - y1)
                
                pair_key = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
                if pair_key in placed_pairs:
                    continue
                placed_pairs.add(pair_key)
                
                has_wall = self._wall_exists_between((x1, y1), (x2, y2))
                
                beam_count += 1
                depth = self._calculate_depth(span, SupportType.COLUMN_COLUMN)
                width = self._calculate_width(has_wall)
                
                beam = BeamPlacement(
                    id=f"B{beam_count}",
                    beam_type=BeamType.PRIMARY,
                    start_x=x1, start_y=y1,
                    end_x=x2, end_y=y2,
                    span_mm=span,
                    width_mm=width,
                    depth_mm=depth,
                    start_node=self._get_column_id(x1, y1),
                    end_node=self._get_column_id(x2, y2),
                    support_type=SupportType.COLUMN_COLUMN,
                    is_hidden_in_wall=has_wall
                )
                
                if not has_wall:
                    beam.warnings.append("Beam crosses open area - visible in ceiling")
                
                self.primary_beams.append(beam)
                logger.info(f"Primary beam {beam.id}: {beam.start_node} -> {beam.end_node} ({span:.0f}mm)")

    def _check_long_spans(self):
        """Phase 2: Check for spans exceeding 7m limit"""
        for beam in self.primary_beams:
            if beam.span_mm > self.CRITICAL_SPAN_MM:
                beam.warnings.append(
                    f"CRITICAL: Span {beam.span_mm/1000:.1f}m > 7.0m limit. "
                    "Requires intermediate column or deep beam design."
                )
                self.warnings.append({
                    "severity": "CRITICAL",
                    "message": f"Beam {beam.id} span {beam.span_mm/1000:.1f}m exceeds 7m limit",
                    "beam_id": beam.id,
                    "code_reference": "IS 456 Deflection Control"
                })
    
    def _identify_slab_panels(self):
        # Improved Logic: Look for parallel primary beams enclosing a space
        # rather than just grid intersections (which might not have columns)
        
        self.slab_panels = []
        panel_count = 0
        
        # 1. Check Vertical Bays (defined by horiz beams at y1, y2)
        if len(self.y_grids) >= 2:
            for j in range(len(self.y_grids) - 1):
                y1, y2 = self.y_grids[j], self.y_grids[j + 1]
                height = abs(y2 - y1)
                
                # Check for beams on y1 and y2 within some x-range
                # We need to find common X ranges
                beams_y1 = [b for b in self.primary_beams 
                           if abs(b.start_y - y1) < 100 and abs(b.end_y - y1) < 100]
                beams_y2 = [b for b in self.primary_beams 
                           if abs(b.start_y - y2) < 100 and abs(b.end_y - y2) < 100]
                
                for b1 in beams_y1:
                    for b2 in beams_y2:
                        # Find overlap in X
                        start_x = max(min(b1.start_x, b1.end_x), min(b2.start_x, b2.end_x))
                        end_x = min(max(b1.start_x, b1.end_x), max(b2.start_x, b2.end_x))
                        
                        if end_x - start_x > 2000: # Min overlapping width 2m
                            # Found a "Bay"
                            width = end_x - start_x
                            area_m2 = (width / 1000) * (height / 1000)
                            
                            # Check if already covered (simple duplicate check)
                            xc, yc = (start_x+end_x)/2, (y1+y2)/2
                            if any(p.id for p in self.slab_panels if abs((p.vertices[0][0]+p.vertices[2][0])/2 - xc) < 100 and abs((p.vertices[0][1]+p.vertices[2][1])/2 - yc) < 100):
                                continue

                            panel_count += 1
                            needs_secondary = (width > self.MAX_SLAB_SPAN_MM or area_m2 > self.MAX_SLAB_AREA_M2)
                            
                            # Create a panel object
                            panel = SlabPanel(
                                id=f"S{panel_count}",
                                vertices=[(start_x, y1), (end_x, y1), (end_x, y2), (start_x, y2)],
                                area_m2=area_m2,
                                short_span_mm=min(width, height),
                                long_span_mm=max(width, height),
                                aspect_ratio=max(width, height)/min(width, height),
                                bounding_beams=[b1.id, b2.id],
                                needs_secondary=needs_secondary
                            )
                            self.slab_panels.append(panel)
                            
        # 2. Check Horizontal Bays (defined by vert beams at x1, x2)
        # Avoid duplicates with Vertical Bays
        if len(self.x_grids) >= 2:
            for i in range(len(self.x_grids) - 1):
                x1, x2 = self.x_grids[i], self.x_grids[i + 1]
                width = abs(x2 - x1)
                
                beams_x1 = [b for b in self.primary_beams 
                           if abs(b.start_x - x1) < 100 and abs(b.end_x - x1) < 100]
                beams_x2 = [b for b in self.primary_beams 
                           if abs(b.start_x - x2) < 100 and abs(b.end_x - x2) < 100]
                
                for b1 in beams_x1:
                    for b2 in beams_x2:
                        start_y = max(min(b1.start_y, b1.end_y), min(b2.start_y, b2.end_y))
                        end_y = min(max(b1.start_y, b1.end_y), max(b2.start_y, b2.end_y))
                        
                        if end_y - start_y > 2000:
                            height = end_y - start_y
                            area_m2 = (width/1000) * (height/1000)
                            
                            xc, yc = (x1+x2)/2, (start_y+end_y)/2
                            if any(p.id for p in self.slab_panels if abs((p.vertices[0][0]+p.vertices[2][0])/2 - xc) < 100 and abs((p.vertices[0][1]+p.vertices[2][1])/2 - yc) < 100):
                                continue

                            panel_count += 1
                            needs_secondary = (height > self.MAX_SLAB_SPAN_MM or area_m2 > self.MAX_SLAB_AREA_M2)
                            
                            panel = SlabPanel(
                                id=f"S{panel_count}",
                                vertices=[(x1, start_y), (x2, start_y), (x2, end_y), (x1, end_y)],
                                area_m2=area_m2,
                                short_span_mm=min(width, height),
                                long_span_mm=max(width, height),
                                aspect_ratio=max(width, height)/min(width, height),
                                bounding_beams=[b1.id, b2.id],
                                needs_secondary=needs_secondary
                            )
                            self.slab_panels.append(panel)

    
    def _place_secondary_beams(self):
        beam_count = len(self.primary_beams)
        
        for panel in self.slab_panels:
            if not panel.needs_secondary:
                continue
            
            x1 = min(v[0] for v in panel.vertices)
            x2 = max(v[0] for v in panel.vertices)
            y1 = min(v[1] for v in panel.vertices)
            y2 = max(v[1] for v in panel.vertices)
            
            width = x2 - x1
            height = y2 - y1
            
            if width > height:
                mid_x = (x1 + x2) / 2
                beam_count += 1
                span = height
                depth = self._calculate_depth(span, SupportType.BEAM_BEAM)
                
                beam = BeamPlacement(
                    id=f"B{beam_count}",
                    beam_type=BeamType.SECONDARY,
                    start_x=mid_x, start_y=y1,
                    end_x=mid_x, end_y=y2,
                    span_mm=span,
                    width_mm=self._calculate_width(True),
                    depth_mm=depth,
                    support_type=SupportType.BEAM_BEAM,
                    supported_by=[f"Primary beams at Y={y1:.0f} and Y={y2:.0f}"]
                )
                
                if self._wall_exists_between((mid_x, y1), (mid_x, y2)):
                    beam.is_hidden_in_wall = True
                else:
                    beam.is_hidden_in_wall = False
                    beam.warnings.append("Secondary beam visible - consider architectural treatment")
                
                # Check Hierarchy IMMEDIATELY
                # Find supporting primary beams
                for pb in self.primary_beams:
                    if (self._is_close((mid_x, y1), (pb.start_x, pb.start_y), 100) or 
                        self._is_close((mid_x, y1), (pb.end_x, pb.end_y), 100) or
                        (pb.start_y == pb.end_y and abs(pb.start_y - y1) < 100 and pb.start_x <= mid_x <= pb.end_x)):
                         # Only increase primary if needed
                         if pb.depth_mm < beam.depth_mm:
                             pb.depth_mm = beam.depth_mm
                             pb.warnings.append(f"Depth increased to {beam.depth_mm}mm to support Secondary B{beam_count}")
                    
                    if (self._is_close((mid_x, y2), (pb.start_x, pb.start_y), 100) or 
                        self._is_close((mid_x, y2), (pb.end_x, pb.end_y), 100) or
                        (pb.start_y == pb.end_y and abs(pb.start_y - y2) < 100 and pb.start_x <= mid_x <= pb.end_x)):
                         if pb.depth_mm < beam.depth_mm:
                             pb.depth_mm = beam.depth_mm
                             pb.warnings.append(f"Depth increased to {beam.depth_mm}mm to support Secondary B{beam_count}")

                self.secondary_beams.append(beam)
                logger.info(f"Secondary beam {beam.id} for panel {panel.id}: bisecting at X={mid_x:.0f}")
            else:
                mid_y = (y1 + y2) / 2
                beam_count += 1
                span = width
                depth = self._calculate_depth(span, SupportType.BEAM_BEAM)
                
                beam = BeamPlacement(
                    id=f"B{beam_count}",
                    beam_type=BeamType.SECONDARY,
                    start_x=x1, start_y=mid_y,
                    end_x=x2, end_y=mid_y,
                    span_mm=span,
                    width_mm=self._calculate_width(True),
                    depth_mm=depth,
                    support_type=SupportType.BEAM_BEAM,
                    supported_by=[f"Primary beams at X={x1:.0f} and X={x2:.0f}"]
                )
                
                if self._wall_exists_between((x1, mid_y), (x2, mid_y)):
                    beam.is_hidden_in_wall = True
                else:
                    beam.is_hidden_in_wall = False
                    beam.warnings.append("Secondary beam visible - consider architectural treatment")
                
                # Check Hierarchy IMMEDIATELY
                for pb in self.primary_beams:
                    if (self._is_close((x1, mid_y), (pb.start_x, pb.start_y), 100) or 
                        self._is_close((x1, mid_y), (pb.end_x, pb.end_y), 100) or
                        (pb.start_x == pb.end_x and abs(pb.start_x - x1) < 100 and pb.start_y <= mid_y <= pb.end_y)):
                         if pb.depth_mm < beam.depth_mm:
                             pb.depth_mm = beam.depth_mm
                             pb.warnings.append(f"Depth increased to {beam.depth_mm}mm to support Secondary B{beam_count}")
                    
                    if (self._is_close((x2, mid_y), (pb.start_x, pb.start_y), 100) or 
                        self._is_close((x2, mid_y), (pb.end_x, pb.end_y), 100) or
                        (pb.start_x == pb.end_x and abs(pb.start_x - x2) < 100 and pb.start_y <= mid_y <= pb.end_y)):
                         if pb.depth_mm < beam.depth_mm:
                             pb.depth_mm = beam.depth_mm
                             pb.warnings.append(f"Depth increased to {beam.depth_mm}mm to support Secondary B{beam_count}")

                self.secondary_beams.append(beam)
                logger.info(f"Secondary beam {beam.id} for panel {panel.id}: bisecting at Y={mid_y:.0f}")
    
    def _place_wall_support_beams(self):
        beam_count = len(self.primary_beams) + len(self.secondary_beams)
        
        for start, end in self.walls:
            wall_len = math.hypot(end[0] - start[0], end[1] - start[1])
            
            if wall_len < 1500:
                continue
            
            is_on_primary = False
            for pb in self.primary_beams:
                if (self._is_close((start[0], start[1]), (pb.start_x, pb.start_y)) and
                    self._is_close((end[0], end[1]), (pb.end_x, pb.end_y))):
                    is_on_primary = True
                    break
                if (self._is_close((start[0], start[1]), (pb.end_x, pb.end_y)) and
                    self._is_close((end[0], end[1]), (pb.start_x, pb.start_y))):
                    is_on_primary = True
                    break
            
            if is_on_primary:
                continue
            
            for sb in self.secondary_beams:
                if (self._is_close((start[0], start[1]), (sb.start_x, sb.start_y)) and
                    self._is_close((end[0], end[1]), (sb.end_x, sb.end_y))):
                    is_on_primary = True
                    break
            
            if is_on_primary:
                continue
    
    def _detect_cantilevers(self):
        """Phase 4: Detect and validate cantilevers (Balconies)"""
        if not self.slab_boundary:
            return
        
        beam_count = len(self.primary_beams) + len(self.secondary_beams) + len(self.cantilever_beams)
        
        # 1. Identify slab points outside the column hull
        # 2. Project from nearest edge column
        
        for edge_col in self.columns:
            cx, cy = edge_col.get('x'), edge_col.get('y')
            
            # Simplified check: is this column on the "edge" of hull?
            is_edge = (abs(cx - self.min_x) < self.GRID_TOLERANCE_MM or
                      abs(cx - self.max_x) < self.GRID_TOLERANCE_MM or
                      abs(cy - self.min_y) < self.GRID_TOLERANCE_MM or
                      abs(cy - self.max_y) < self.GRID_TOLERANCE_MM)
            
            if not is_edge:
                continue
            
            # Find nearest slab boundary point that is "outside" hull
            for sx, sy in self.slab_boundary:
                # Check if point is outside hull
                if (sx < self.min_x - 100 or sx > self.max_x + 100 or 
                    sy < self.min_y - 100 or sy > self.max_y + 100):
                    
                    dist = math.hypot(sx - cx, sy - cy)
                    if dist < 500 or dist > self.MAX_CANTILEVER_MM:
                        continue
                        
                    # Check alignment (must be orthogonal projection)
                    if abs(sx - cx) < 100 or abs(sy - cy) < 100:
                        # Candidate found
                        pass
                    else:
                        continue
                        
                    beam_count += 1
                    depth = self._calculate_depth(dist, SupportType.CANTILEVER)
                    width = self._calculate_width(True) # Cantilevers usually match wall/slab edge
                    
                    back_span = self._find_back_span(cx, cy, sx, sy) # Pass direction
                    
                    # Strictly 1.5x backspan required
                    is_safe = back_span >= dist * self.MIN_BACK_SPAN_RATIO
                    
                    beam = BeamPlacement(
                        id=f"B{beam_count}",
                        beam_type=BeamType.CANTILEVER,
                        start_x=cx, start_y=cy,
                        end_x=sx, end_y=sy,
                        span_mm=dist,
                        width_mm=width,
                        depth_mm=depth,
                        start_node=self._get_column_id(cx, cy),
                        end_node="Slab_Edge",
                        support_type=SupportType.CANTILEVER,
                        is_cantilever=True,
                        back_span_mm=back_span
                    )
                    
                    if not is_safe:
                        ratio = back_span / dist if dist > 0 else 0
                        beam.warnings.append(
                            f"CRITICAL: Back-span ratio {ratio:.2f} < 1.5. Unsafe cantilever."
                        )
                        self.warnings.append({
                            "severity": "CRITICAL",
                            "message": f"Cantilever {beam.id} unsafe. Back-span {back_span:.0f}mm vs overhang {dist:.0f}mm",
                            "beam_id": beam.id,
                            "code_reference": "IS 456 Stability"
                        })
                    
                    # Check if already exists (avoid duplicates)
                    exists = False
                    for existing in self.cantilever_beams:
                         if self._is_close((existing.end_x, existing.end_y), (sx, sy)):
                             exists = True
                             break
                    if not exists:
                        self.cantilever_beams.append(beam)

    def _find_back_span(self, cx: float, cy: float, tip_x: float, tip_y: float) -> float:
        """Find continuous beam span in the OPPOSITE direction of cantilever"""
        # Determine cantilever direction vector
        dx = tip_x - cx
        dy = tip_y - cy
        
        max_back_span = 0.0
        
        for beam in self.primary_beams:
            # Beam must start or end at (cx, cy)
            if self._is_close((cx, cy), (beam.start_x, beam.start_y)):
                bx, by = beam.end_x, beam.end_y
            elif self._is_close((cx, cy), (beam.end_x, beam.end_y)):
                bx, by = beam.start_x, beam.start_y
            else:
                continue
            
            # Vector of potential backspan beam
            bdx = bx - cx
            bdy = by - cy
            
            # Dot product to check if opposite direction (approx -1)
            # Normalize
            len_c = math.hypot(dx, dy)
            len_b = math.hypot(bdx, bdy)
            
            if len_c == 0 or len_b == 0: continue
            
            dot = (dx * bdx + dy * bdy) / (len_c * len_b)
            
            # If dot is near -1, it's opposite
            if dot < -0.9:
                max_back_span = max(max_back_span, beam.span_mm)
                
        return max_back_span
    
    def _calculate_depth(self, span_mm: float, support_type: SupportType) -> float:
        # IS 456 / Practical Rule: L/15 for general beams
        if support_type == SupportType.CANTILEVER:
            d = span_mm / 7.0
        else:
            d = span_mm / 15.0
            
        # Minimum depth checks (IS 456)
        min_depth = max(self.MIN_BEAM_DEPTH_MM, 3 * self.DEFAULT_SLAB_THICKNESS_MM)
        d = max(d, min_depth)
        
        # Round up to nearest 25mm
        d = math.ceil(d / 25) * 25
        
        if d > 750:
             self.warnings.append({
                "severity": "WARNING",
                "message": f"Beam depth {d:.0f}mm is large - check headroom",
                "code_reference": "Architectural Headroom"
            })
        
        return d
    
    def _calculate_width(self, has_wall: bool = True) -> float:
        if has_wall:
            # Match wall thickness but ensure min structural width
            return max(self.WALL_THICKNESS_MM, self.MIN_BEAM_WIDTH_MM)
        # If no wall, use minimum width (usually 200mm or 230mm)
        return max(self.MIN_BEAM_WIDTH_MM, 200.0)
    
    def _apply_seismic_checks(self):
        if not self.is_seismic:
            return
        
        all_beams = self.primary_beams + self.secondary_beams + self.cantilever_beams
        
        for beam in all_beams:
            bd_ratio = beam.width_mm / beam.depth_mm
            
            if bd_ratio < self.MIN_BD_RATIO:
                old_width = beam.width_mm
                beam.width_mm = max(beam.width_mm, beam.depth_mm * self.MIN_BD_RATIO)
                beam.width_mm = math.ceil(beam.width_mm / 25) * 25
                
                if beam.width_mm != old_width:
                    beam.warnings.append(
                        f"Width increased from {old_width:.0f}mm to {beam.width_mm:.0f}mm "
                        f"for b/D >= 0.3 (IS 13920)"
                    )
            
            if beam.width_mm < self.MIN_BEAM_WIDTH_MM:
                beam.width_mm = self.MIN_BEAM_WIDTH_MM
                beam.warnings.append(f"Width set to minimum {self.MIN_BEAM_WIDTH_MM:.0f}mm (IS 13920)")
    
    def _check_hierarchy(self):
        if not self.secondary_beams or not self.primary_beams:
            return
        
        max_primary_depth = max(b.depth_mm for b in self.primary_beams)
        
        for sb in self.secondary_beams:
            if sb.depth_mm > max_primary_depth:
                old_depth = sb.depth_mm
                sb.depth_mm = max_primary_depth - 50
                sb.warnings.append(
                    f"Depth reduced from {old_depth:.0f}mm to {sb.depth_mm:.0f}mm "
                    f"(must be <= primary beam depth)"
                )
                self.warnings.append({
                    "severity": "INFO",
                    "message": f"Secondary beam {sb.id} depth adjusted for hierarchy",
                    "code_reference": "Beam detailing - rebar clearance at supports"
                })
    
    def _check_deep_beams(self):
        all_beams = self.primary_beams + self.secondary_beams
        
        for beam in all_beams:
            if beam.depth_mm == 0:
                continue
            
            ld_ratio = beam.span_mm / beam.depth_mm
            
            if ld_ratio < 4.0:
                beam.warnings.append(f"DEEP BEAM: L/D = {ld_ratio:.2f} < 4.0 - use strut-and-tie")
                self.warnings.append({
                    "severity": "CRITICAL",
                    "message": f"Beam {beam.id} is a deep beam (L/D={ld_ratio:.2f}) - "
                              "requires strut-and-tie design",
                    "beam_id": beam.id,
                    "code_reference": "IS 456 Clause 29 - Deep Beams"
                })

    def _assign_reinforcement_logic(self):
        all_beams = self.primary_beams + self.secondary_beams + self.cantilever_beams
        
        for beam in all_beams:
            if beam.is_cantilever:
                beam.reinforcement_logic = ReinforcementLogic.DOUBLY_REINFORCED
            elif beam.support_type == SupportType.COLUMN_COLUMN:
                if beam.span_mm > 5000:
                    beam.reinforcement_logic = ReinforcementLogic.DOUBLY_REINFORCED
                else:
                    beam.reinforcement_logic = ReinforcementLogic.SINGLY_REINFORCED
            else:
                beam.reinforcement_logic = ReinforcementLogic.SINGLY_REINFORCED

    def generate_placement(self) -> PlacementResult:
        logger.info("Starting IS-code compliant beam placement")
        
        logger.info("Phase 1: Placing primary beams (column-to-column)")
        self._place_primary_beams()
        
        logger.info("Phase 2: Checking spans")
        self._check_long_spans()
        
        logger.info("Phase 3: Identify slab panels and place secondary beams")
        self._identify_slab_panels()
        self._place_secondary_beams()
        self._place_wall_support_beams()
        
        logger.info("Phase 4: Detecting cantilevers")
        self._detect_cantilevers()
        
        logger.info("Phase 5: Applying sizing and hierarchy checks")
        self._apply_seismic_checks()
        self._check_hierarchy()
        self._check_deep_beams()
        self._assign_reinforcement_logic()
        
        self.beams = self.primary_beams + self.secondary_beams + self.cantilever_beams
        
        stats = {
            "total_beams": len(self.beams),
            "primary": len(self.primary_beams),
            "secondary": len(self.secondary_beams),
            "cantilever": len(self.cantilever_beams),
            "slab_panels": len(self.slab_panels),
            "panels_needing_secondary": sum(1 for p in self.slab_panels if p.needs_secondary),
            "seismic_zone": self.seismic_zone,
            "warnings_count": len(self.warnings)
        }
        
        logger.info(f"Beam placement complete: {stats['total_beams']} beams, "
                   f"{stats['warnings_count']} warnings")
        
        return PlacementResult(
            beams=self.beams,
            slab_panels=self.slab_panels,
            warnings=self.warnings,
            stats=stats
        )
