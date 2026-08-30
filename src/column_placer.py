"""
Column Placement Module - IS 456:2000 & IS 13920:2016 Compliant

Performs automated column placement from architectural DXF layouts following:
- Mandatory corner placement for frame stability
- Intersection prioritization (Degree 4 > Degree 3 > Degree 2)
- Span checks (max 7m economical span, intermediate columns at L/2)
- Seismic zone-aware sizing (min 300mm for Zones III/IV/V)
- Orientation optimization based on beam span directions
- Floating column detection for multi-floor buildings
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Set
from enum import Enum
import math
import json

from .logging_config import get_logger

logger = get_logger(__name__)


class JunctionType(Enum):
    CORNER = "corner"
    EDGE = "edge"
    T_JUNCTION = "t_junction"
    CROSS_JUNCTION = "cross_junction"
    INTERIOR = "interior"


class ReinforcementRule(Enum):
    IS_456_STANDARD = "IS_456_Standard"
    IS_13920_SPECIAL_CONFINING = "IS_13920_Special_Confining"
    IS_13920_FULL_HEIGHT_CONFINING = "IS_13920_Full_Height_Confining"


@dataclass
class ColumnPlacement:
    id: str
    x: float
    y: float
    z: float = 0.0
    width: float = 300.0
    depth: float = 300.0
    orientation_deg: float = 0.0
    column_type: str = "Rectangular"
    junction_type: JunctionType = JunctionType.INTERIOR
    degree: int = 0
    is_floating: bool = False
    reinforcement_rule: ReinforcementRule = ReinforcementRule.IS_456_STANDARD
    connected_spans: List[float] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "location": {"x": round(self.x, 1), "y": round(self.y, 1), "z": round(self.z, 1)},
            "size": {"width": int(self.width), "depth": int(self.depth)},
            "orientation": self.orientation_deg,
            "type": self.column_type,
            "junction_type": self.junction_type.value,
            "is_floating": self.is_floating,
            "reinforcement_rule": self.reinforcement_rule.value
        }


@dataclass
class PlacementWarning:
    severity: str
    message: str
    column_id: Optional[str] = None
    code_reference: Optional[str] = None
    
    def to_dict(self) -> Dict:
        result = {"severity": self.severity, "message": self.message}
        if self.column_id:
            result["column_id"] = self.column_id
        if self.code_reference:
            result["code_reference"] = self.code_reference
        return result


@dataclass
class PlacementResult:
    columns: List[ColumnPlacement] = field(default_factory=list)
    warnings: List[PlacementWarning] = field(default_factory=list)
    stats: Dict = field(default_factory=dict)
    
    def to_json(self) -> str:
        return json.dumps({
            "columns": [c.to_dict() for c in self.columns],
            "warnings": [w.to_dict() for w in self.warnings],
            "stats": self.stats
        }, indent=2)


class ColumnPlacer:
    SEISMIC_MIN_DIM_MM = 300.0
    NON_SEISMIC_MIN_DIM_MM = 230.0
    MIN_ASPECT_RATIO = 0.4
    PRIMARY_COVERAGE_THRESHOLD = 0.55
    SECONDARY_COVERAGE_THRESHOLD = 0.25
    
    def __init__(
        self,
        nodes: List[Tuple[float, float]],
        centerlines: List[Tuple[Tuple[float, float], Tuple[float, float]]],
        seismic_zone: str = "III",
        building_envelope: Optional[List[Tuple[float, float]]] = None
    ):
        self.nodes = nodes
        self.centerlines = centerlines
        self.seismic_zone = seismic_zone
        self.building_envelope = building_envelope or self._compute_envelope()
        
        self.is_seismic = seismic_zone in ["III", "IV", "V"]
        self.min_dim = self.SEISMIC_MIN_DIM_MM if self.is_seismic else self.NON_SEISMIC_MIN_DIM_MM
        
        self.columns: List[ColumnPlacement] = []
        self.warnings: List[PlacementWarning] = []
        self.node_degrees: Dict[Tuple[float, float], int] = {}
        self.node_junctions: Dict[Tuple[float, float], JunctionType] = {}
        
        self.primary_x: List[float] = []
        self.primary_y: List[float] = []
        
        self._compute_adaptive_params()
    
    def _compute_adaptive_params(self):
        env = self.building_envelope
        if not env or len(env) < 3:
            # FIX 5: cap at 5000mm (IS 456 Table 26 economical residential span)
            self.max_span = 5000.0
            self.min_span = 1500.0
            self.proximity_merge = 700.0
            self.bldg_width = 10000.0
            self.bldg_length = 10000.0
            return
        
        xs = [p[0] for p in env]
        ys = [p[1] for p in env]
        self.bldg_width = max(xs) - min(xs)
        self.bldg_length = max(ys) - min(ys)
        shorter = min(self.bldg_width, self.bldg_length)
        
        # FIX 5: Residential economical span per IS 456 Table 26 / SP 34:
        # Two-way slab with 125mm thickness works up to 5m span (L/d = 40).
        # Beyond 5m, slab becomes uneconomical (needs 150mm+ thickness).
        # Previous code allowed 7m — that is for industrial/commercial structures.
        self.max_span = min(5000.0, max(3000.0, shorter * 0.5))
        self.min_span = max(1000.0, shorter * 0.08)
        self.proximity_merge = max(600.0, shorter * 0.05)
        
    def _compute_envelope(self) -> List[Tuple[float, float]]:
        if not self.nodes:
            return []
        xs = [n[0] for n in self.nodes]
        ys = [n[1] for n in self.nodes]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        return [(min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y)]
    
    def _is_close(self, p1: Tuple[float, float], p2: Tuple[float, float], tol: float = 500.0) -> bool:
        return math.hypot(p1[0] - p2[0], p1[1] - p2[1]) < tol
    
    def _extract_structural_grid(self):
        """Extract primary and secondary structural gridlines from wall layout.
        
        A gridline is PRIMARY if walls along it cover >= PRIMARY_COVERAGE_THRESHOLD
        of the building dimension. Perimeter lines are always primary.
        This replaces hardcoded MIN_STRUCTURAL_WALL_MM with a proportional metric.
        """
        env = self.building_envelope
        if not env:
            return
        
        min_x = min(p[0] for p in env)
        max_x = max(p[0] for p in env)
        min_y = min(p[1] for p in env)
        max_y = max(p[1] for p in env)
        tol = 500.0
        
        # Gather unique X and Y coordinates from centerline endpoints
        raw_xs = set()
        raw_ys = set()
        for (x1, y1), (x2, y2) in self.centerlines:
            raw_xs.add(x1); raw_xs.add(x2)
            raw_ys.add(y1); raw_ys.add(y2)
        
        # Snap nearby coordinates to clean gridlines
        merge_tol = max(500.0, self.proximity_merge)
        def snap_coords(coords):
            sorted_c = sorted(coords)
            groups = [[sorted_c[0]]]
            for c in sorted_c[1:]:
                if abs(c - groups[-1][-1]) < merge_tol:
                    groups[-1].append(c)
                else:
                    groups.append([c])
            return [sum(g)/len(g) for g in groups]
        
        grid_xs = snap_coords(raw_xs)
        grid_ys = snap_coords(raw_ys)
        
        # Calculate wall coverage along each X gridline
        for gx in grid_xs:
            is_perimeter = abs(gx - min_x) < tol or abs(gx - max_x) < tol
            if is_perimeter:
                self.primary_x.append(gx)
                continue
            
            # Find all vertical walls near this X coordinate
            coverage = 0.0
            for (x1, y1), (x2, y2) in self.centerlines:
                if abs(x1 - gx) < tol and abs(x2 - gx) < tol:
                    coverage += abs(y2 - y1)
                elif abs(x1 - gx) < tol or abs(x2 - gx) < tol:
                    if abs(x2 - x1) < tol:
                        coverage += abs(y2 - y1)
            
            ratio = coverage / self.bldg_length if self.bldg_length > 0 else 0
            
            if ratio >= self.PRIMARY_COVERAGE_THRESHOLD:
                self.primary_x.append(gx)
            elif ratio >= self.SECONDARY_COVERAGE_THRESHOLD:
                self.primary_x.append(gx)
        
        # Calculate wall coverage along each Y gridline
        for gy in grid_ys:
            is_perimeter = abs(gy - min_y) < tol or abs(gy - max_y) < tol
            if is_perimeter:
                self.primary_y.append(gy)
                continue
            
            coverage = 0.0
            for (x1, y1), (x2, y2) in self.centerlines:
                if abs(y1 - gy) < tol and abs(y2 - gy) < tol:
                    coverage += abs(x2 - x1)
                elif abs(y1 - gy) < tol or abs(y2 - gy) < tol:
                    if abs(y2 - y1) < tol:
                        coverage += abs(x2 - x1)
            
            ratio = coverage / self.bldg_width if self.bldg_width > 0 else 0
            
            if ratio >= self.PRIMARY_COVERAGE_THRESHOLD:
                self.primary_y.append(gy)
            elif ratio >= self.SECONDARY_COVERAGE_THRESHOLD:
                self.primary_y.append(gy)
        
        self.primary_x = sorted(set(self.primary_x))
        self.primary_y = sorted(set(self.primary_y))
        
        # Remove interior gridlines that are shadowed by a perimeter line
        # (e.g., x=0 is redundant when x=-1500 is the perimeter)
        # Use 1200mm (standard cantilever) as threshold. 
        # 1.5m balconies should have their own gridline + core wall gridline.
        shadow_dist = 1200.0
        perim_xs = [gx for gx in self.primary_x 
                    if abs(gx - min_x) < tol or abs(gx - max_x) < tol]
        perim_ys = [gy for gy in self.primary_y 
                    if abs(gy - min_y) < tol or abs(gy - max_y) < tol]
        
        filtered_x = []
        for gx in self.primary_x:
            if abs(gx - min_x) < tol or abs(gx - max_x) < tol:
                filtered_x.append(gx)
                continue
            if any(0 < abs(gx - px) < shadow_dist for px in perim_xs):
                logger.info(f"Suppressed gridline x={gx:.0f} (shadowed by perimeter)")
                continue
            filtered_x.append(gx)
        
        filtered_y = []
        for gy in self.primary_y:
            if abs(gy - min_y) < tol or abs(gy - max_y) < tol:
                filtered_y.append(gy)
                continue
            if any(0 < abs(gy - py) < shadow_dist for py in perim_ys):
                logger.info(f"Suppressed gridline y={gy:.0f} (shadowed by perimeter)")
                continue
            filtered_y.append(gy)
        
        self.primary_x = filtered_x
        self.primary_y = filtered_y
        
        logger.info(f"Structural grid: X={[f'{x:.0f}' for x in self.primary_x]}, "
                     f"Y={[f'{y:.0f}' for y in self.primary_y]}")
    
    def _calculate_node_degrees(self):
        for node in self.nodes:
            degree = 0
            for start, end in self.centerlines:
                if self._is_close(node, start) or self._is_close(node, end):
                    degree += 1
            self.node_degrees[node] = degree
    
    def _classify_junctions(self):
        if not self.building_envelope:
            return
            
        min_x = min(p[0] for p in self.building_envelope)
        max_x = max(p[0] for p in self.building_envelope)
        min_y = min(p[1] for p in self.building_envelope)
        max_y = max(p[1] for p in self.building_envelope)
        
        edge_tol = 500.0
        
        for node in self.nodes:
            degree = self.node_degrees.get(node, 0)
            x, y = node
            
            on_x_edge = abs(x - min_x) < edge_tol or abs(x - max_x) < edge_tol
            on_y_edge = abs(y - min_y) < edge_tol or abs(y - max_y) < edge_tol
            
            if degree >= 4:
                self.node_junctions[node] = JunctionType.CROSS_JUNCTION
            elif degree == 3:
                self.node_junctions[node] = JunctionType.T_JUNCTION
            elif degree == 2 and on_x_edge and on_y_edge:
                self.node_junctions[node] = JunctionType.CORNER
            elif degree == 2 and (on_x_edge or on_y_edge):
                self.node_junctions[node] = JunctionType.EDGE
            elif degree == 2:
                self.node_junctions[node] = JunctionType.EDGE
            else:
                self.node_junctions[node] = JunctionType.INTERIOR
    
    def _is_on_perimeter(self, node: Tuple[float, float]) -> bool:
        if not self.building_envelope:
            return False
        min_x = min(p[0] for p in self.building_envelope)
        max_x = max(p[0] for p in self.building_envelope)
        min_y = min(p[1] for p in self.building_envelope)
        max_y = max(p[1] for p in self.building_envelope)
        
        tol = 500.0
        x, y = node
        return (abs(x - min_x) < tol or abs(x - max_x) < tol or
                abs(y - min_y) < tol or abs(y - max_y) < tol)
    
    def _place_mandatory_corners(self):
        corner_nodes = [n for n in self.nodes 
                       if self.node_junctions.get(n) == JunctionType.CORNER]
        
        if not corner_nodes and self.building_envelope:
            min_x = min(p[0] for p in self.building_envelope)
            max_x = max(p[0] for p in self.building_envelope)
            min_y = min(p[1] for p in self.building_envelope)
            max_y = max(p[1] for p in self.building_envelope)
            corner_nodes = [
                (min_x, min_y), (max_x, min_y),
                (max_x, max_y), (min_x, max_y)
            ]
        
        for i, node in enumerate(corner_nodes):
            col = ColumnPlacement(
                id=f"C{len(self.columns) + 1}",
                x=node[0],
                y=node[1],
                width=self.min_dim,
                depth=self.min_dim,
                junction_type=JunctionType.CORNER,
                degree=self.node_degrees.get(node, 2),
                reinforcement_rule=ReinforcementRule.IS_13920_SPECIAL_CONFINING if self.is_seismic else ReinforcementRule.IS_456_STANDARD
            )
            self.columns.append(col)
            logger.info(f"Placed corner column {col.id} at ({node[0]:.1f}, {node[1]:.1f})")
    
    def _place_at_intersections(self):
        placed_locations = set((c.x, c.y) for c in self.columns)
        
        cross_junctions = [(n, self.node_degrees.get(n, 0)) 
                          for n in self.nodes 
                          if self.node_junctions.get(n) == JunctionType.CROSS_JUNCTION]
        cross_junctions.sort(key=lambda x: -x[1])
        
        for node, degree in cross_junctions:
            if any(self._is_close(node, loc, self.proximity_merge) for loc in placed_locations):
                self.warnings.append(PlacementWarning(
                    severity="INFO",
                    message=f"Skipped cross-junction at ({node[0]:.0f}, {node[1]:.0f}) - too close to existing column"
                ))
                continue
            
            col = ColumnPlacement(
                id=f"C{len(self.columns) + 1}",
                x=node[0],
                y=node[1],
                width=self.min_dim,
                depth=self.min_dim + 100,
                junction_type=JunctionType.CROSS_JUNCTION,
                degree=degree,
                reinforcement_rule=ReinforcementRule.IS_13920_SPECIAL_CONFINING if self.is_seismic else ReinforcementRule.IS_456_STANDARD
            )
            self.columns.append(col)
            placed_locations.add((node[0], node[1]))
            logger.info(f"Placed cross-junction column {col.id}")
        
        t_junctions = [(n, self.node_degrees.get(n, 0)) 
                      for n in self.nodes 
                      if self.node_junctions.get(n) == JunctionType.T_JUNCTION]
        
        for node, degree in t_junctions:
            if any(self._is_close(node, loc, self.proximity_merge) for loc in placed_locations):
                continue
            
            col = ColumnPlacement(
                id=f"C{len(self.columns) + 1}",
                x=node[0],
                y=node[1],
                width=self.min_dim,
                depth=self.min_dim,
                junction_type=JunctionType.T_JUNCTION,
                degree=degree,
                reinforcement_rule=ReinforcementRule.IS_13920_SPECIAL_CONFINING if self.is_seismic else ReinforcementRule.IS_456_STANDARD
            )
            self.columns.append(col)
            placed_locations.add((node[0], node[1]))
            logger.info(f"Placed T-junction column {col.id}")
    
    def _place_at_grid_intersections(self):
        """Place columns at intersections of primary gridlines where a wall
        exists. This is exactly what a structural engineer does: identify the
        grid, then place columns at every grid intersection with a wall."""
        placed_locations = set((c.x, c.y) for c in self.columns)
        tol = 500.0
        
        for gx in self.primary_x:
            for gy in self.primary_y:
                if any(self._is_close((gx, gy), loc, self.proximity_merge) 
                       for loc in placed_locations):
                    continue
                
                # Check if a wall passes through or near this intersection
                has_wall = False
                for (x1, y1), (x2, y2) in self.centerlines:
                    # Vertical wall near gx, spanning across gy
                    if abs(x1 - gx) < tol and abs(x2 - gx) < tol:
                        y_lo, y_hi = min(y1, y2), max(y1, y2)
                        if y_lo - tol <= gy <= y_hi + tol:
                            has_wall = True
                            break
                    # Horizontal wall near gy, spanning across gx
                    if abs(y1 - gy) < tol and abs(y2 - gy) < tol:
                        x_lo, x_hi = min(x1, x2), max(x1, x2)
                        if x_lo - tol <= gx <= x_hi + tol:
                            has_wall = True
                            break
                
                if not has_wall:
                    continue
                
                # Determine junction type
                env = self.building_envelope
                is_perimeter = False
                if env:
                    min_x = min(p[0] for p in env)
                    max_x = max(p[0] for p in env)
                    min_y = min(p[1] for p in env)
                    max_y = max(p[1] for p in env)
                    is_perimeter = (abs(gx - min_x) < tol or abs(gx - max_x) < tol or
                                    abs(gy - min_y) < tol or abs(gy - max_y) < tol)
                
                jtype = JunctionType.EDGE if is_perimeter else JunctionType.INTERIOR
                col = ColumnPlacement(
                    id=f"C{len(self.columns) + 1}",
                    x=gx,
                    y=gy,
                    width=self.min_dim,
                    depth=self.min_dim,
                    junction_type=jtype
                )
                self.columns.append(col)
                placed_locations.add((gx, gy))
    
    def _fill_gaps(self):
        """Walk each primary gridline. For perimeter gridlines, always fill
        gaps > max_span. For interior gridlines, only fill if a wall runs
        along that segment. Real engineers don't fill open space."""
        new_columns = []
        placed_set = set((round(c.x, 0), round(c.y, 0)) for c in self.columns)
        tol = 500.0
        
        env = self.building_envelope
        min_x = min(p[0] for p in env) if env else 0
        max_x = max(p[0] for p in env) if env else 0
        min_y = min(p[1] for p in env) if env else 0
        max_y = max(p[1] for p in env) if env else 0
        
        def wall_exists_between(p1, p2):
            px_lo, px_hi = min(p1[0], p2[0]), max(p1[0], p2[0])
            py_lo, py_hi = min(p1[1], p2[1]), max(p1[1], p2[1])
            is_horizontal = abs(p1[1] - p2[1]) < tol
            for (x1, y1), (x2, y2) in self.centerlines:
                if is_horizontal:
                    if abs(y1 - p1[1]) < tol and abs(y2 - p1[1]) < tol:
                        wx_lo, wx_hi = min(x1, x2), max(x1, x2)
                        if wx_lo < px_hi and wx_hi > px_lo:
                            return True
                else:
                    if abs(x1 - p1[0]) < tol and abs(x2 - p1[0]) < tol:
                        wy_lo, wy_hi = min(y1, y2), max(y1, y2)
                        if wy_lo < py_hi and wy_hi > py_lo:
                            return True
            return False
        
        # Check vertical gridlines
        for gx in self.primary_x:
            is_perim_x = abs(gx - min_x) < tol or abs(gx - max_x) < tol
            cols_on_line = sorted(
                [c for c in self.columns if abs(c.x - gx) < tol],
                key=lambda c: c.y
            )
            for i in range(len(cols_on_line) - 1):
                c_lo, c_hi = cols_on_line[i], cols_on_line[i+1]
                gap = abs(c_hi.y - c_lo.y)
                if gap <= self.max_span:
                    continue
                if is_perim_x or wall_exists_between(
                        (c_lo.x, c_lo.y), (c_hi.x, c_hi.y)):
                    num_fills = math.ceil(gap / self.max_span) - 1
                    for k in range(1, num_fills + 1):
                        mid_y = c_lo.y + gap * k / (num_fills + 1)
                        key = (round(gx, 0), round(mid_y, 0))
                        if key not in placed_set:
                            new_columns.append(ColumnPlacement(
                                id=f"C{len(self.columns) + len(new_columns) + 1}",
                                x=gx, y=mid_y,
                                width=self.min_dim, depth=self.min_dim,
                                junction_type=JunctionType.EDGE
                            ))
                            placed_set.add(key)
        
        # Check horizontal gridlines
        for gy in self.primary_y:
            is_perim_y = abs(gy - min_y) < tol or abs(gy - max_y) < tol
            cols_on_line = sorted(
                [c for c in list(self.columns) + new_columns if abs(c.y - gy) < tol],
                key=lambda c: c.x
            )
            for i in range(len(cols_on_line) - 1):
                c_lo, c_hi = cols_on_line[i], cols_on_line[i+1]
                gap = abs(c_hi.x - c_lo.x)
                if gap <= self.max_span:
                    continue
                if is_perim_y or wall_exists_between(
                        (c_lo.x, c_lo.y), (c_hi.x, c_hi.y)):
                    num_fills = math.ceil(gap / self.max_span) - 1
                    for k in range(1, num_fills + 1):
                        mid_x = c_lo.x + gap * k / (num_fills + 1)
                        key = (round(mid_x, 0), round(gy, 0))
                        if key not in placed_set:
                            new_columns.append(ColumnPlacement(
                                id=f"C{len(self.columns) + len(new_columns) + 1}",
                                x=mid_x, y=gy,
                                width=self.min_dim, depth=self.min_dim,
                                junction_type=JunctionType.EDGE
                            ))
                            placed_set.add(key)
        
        self.columns.extend(new_columns)
    
    def _fill_long_spans(self):
        placed_set = set((round(c.x, 0), round(c.y, 0)) for c in self.columns)
        new_columns = []
        
        for start, end in self.centerlines:
            span = math.hypot(end[0] - start[0], end[1] - start[1])
            
            if span <= self.max_span:
                continue
            
            start_has_col = any(self._is_close(start, (c.x, c.y)) for c in self.columns)
            end_has_col = any(self._is_close(end, (c.x, c.y)) for c in self.columns)
            
            if not (start_has_col and end_has_col):
                continue
            
            num_segments = math.ceil(span / self.max_span)
            
            for i in range(1, num_segments):
                t = i / num_segments
                mid_x = start[0] + t * (end[0] - start[0])
                mid_y = start[1] + t * (end[1] - start[1])
                
                key = (round(mid_x, 0), round(mid_y, 0))
                if key in placed_set:
                    continue
                
                col = ColumnPlacement(
                    id=f"C{len(self.columns) + len(new_columns) + 1}",
                    x=mid_x,
                    y=mid_y,
                    width=self.min_dim,
                    depth=self.min_dim,
                    junction_type=JunctionType.INTERIOR
                )
                new_columns.append(col)
                placed_set.add(key)
                
                self.warnings.append(PlacementWarning(
                    severity="INFO",
                    message=f"Added intermediate column {col.id} for {span:.0f}mm span (exceeds 7m limit)",
                    column_id=col.id,
                    code_reference="IS 456 economical span recommendation"
                ))
        
        self.columns.extend(new_columns)
    
    def _check_short_spans(self):
        for i, c1 in enumerate(self.columns):
            for c2 in self.columns[i+1:]:
                dist = math.hypot(c1.x - c2.x, c1.y - c2.y)
                
                if dist < self.min_span and dist > 500:
                    on_same_wall = False
                    for start, end in self.centerlines:
                        if (self._is_close((c1.x, c1.y), start) or self._is_close((c1.x, c1.y), end)):
                            if (self._is_close((c2.x, c2.y), start) or self._is_close((c2.x, c2.y), end)):
                                on_same_wall = True
                                break
                    
                    if on_same_wall:
                        self.warnings.append(PlacementWarning(
                            severity="WARNING",
                            message=f"Short span ({dist:.0f}mm) between {c1.id} and {c2.id} - consider combined footing",
                            column_id=f"{c1.id},{c2.id}",
                            code_reference="IS 456 foundation design"
                        ))
    
    def _size_columns(self):
        """Apply IS 456 / IS 13920 / SP 34 minimum column sizes by junction type.
        
        Real-life practice (G+2/G+3 residential):
          - Corner   : 230×300mm (one face flush with wall = 230mm, other minimum 300mm)
          - Edge     : 230×300mm (same — one face in wall plane)
          - T-junction: 230×300mm to 300×300mm (depends on loads from both sides)
          - Cross-jct: 300×300mm (interior, loads from all 4 bays)
          - Interior : 300×300mm (max tributary area, govern size)
        
        Ref: IS 456:2000 Cl 26.5.3, IS 13920:2016 Cl 6.1.3, SP 34 Chapter 5
        """
        # Preferred sizes on-site (brick module + formwork standard)
        # 230, 300, 350, 380, 400, 450, 500, 600
        PREF_SIZES = [230, 300, 350, 380, 400, 450, 500, 600]
        
        def _snap_to_preferred(val: float) -> float:
            """Snap to nearest preferred column size ≥ val."""
            for s in PREF_SIZES:
                if s >= val:
                    return float(s)
            return float(math.ceil(val / 25) * 25)
        
        for col in self.columns:
            jt = col.junction_type
            
            if jt == JunctionType.CORNER:
                # Corner: IS 456 Cl 34.1.3 — 230mm face aligns with wall
                # Minimum 230×300 (one face in wall, other projects minimum 300mm)
                min_w = max(self.min_dim, 230.0)
                min_d = max(self.min_dim, 300.0)
            
            elif jt == JunctionType.EDGE:
                # Edge: Same as corner — face flush with wall
                min_w = max(self.min_dim, 230.0)
                min_d = max(self.min_dim, 300.0)
            
            elif jt == JunctionType.T_JUNCTION:
                # T-junction: One major beam direction → slightly larger
                # Practice: 230×300 or 300×300 depending on seismic zone
                min_w = max(self.min_dim, 230.0)
                min_d = max(self.min_dim, 300.0)
            
            elif jt == JunctionType.CROSS_JUNCTION:
                # Cross-junction (interior): Loads from all 4 bays → larger
                # IS 13920 Cl 6.1.3: min 300mm in seismic zones III/IV/V
                min_w = max(self.min_dim, 300.0)
                min_d = max(self.min_dim, 300.0)
            
            else:  # INTERIOR or any other
                min_w = max(self.min_dim, 300.0)
                min_d = max(self.min_dim, 300.0)
            
            # Apply minimums and snap to preferred size
            col.width = _snap_to_preferred(max(col.width, min_w))
            col.depth = _snap_to_preferred(max(col.depth, min_d))
            
            # Ensure aspect ratio ≥ 0.4 (IS 13920 Cl 7.1.2 — else it's a wall)
            aspect_ratio = min(col.width, col.depth) / max(col.width, col.depth)
            if aspect_ratio < self.MIN_ASPECT_RATIO:
                self.warnings.append(PlacementWarning(
                    severity="WARNING",
                    message=f"Column {col.id} has aspect ratio {aspect_ratio:.2f} < 0.4 - may be classified as structural wall (IS 13920 Cl 7.1.2)",
                    column_id=col.id,
                    code_reference="IS 13920 Clause 7.1.2"
                ))
    
    def _orient_columns(self):
        for col in self.columns:
            connected_walls = []
            for start, end in self.centerlines:
                if self._is_close((col.x, col.y), start) or self._is_close((col.x, col.y), end):
                    dx = abs(end[0] - start[0])
                    dy = abs(end[1] - start[1])
                    length = math.hypot(dx, dy)
                    is_horizontal = dx > dy
                    connected_walls.append((length, is_horizontal))
            
            if not connected_walls:
                continue
            
            h_spans = [l for l, h in connected_walls if h]
            v_spans = [l for l, h in connected_walls if not h]
            
            max_h = max(h_spans) if h_spans else 0
            max_v = max(v_spans) if v_spans else 0
            
            if max_h > max_v:
                col.orientation_deg = 0
            else:
                col.orientation_deg = 90
            
            col.connected_spans = [l for l, _ in connected_walls]
    
    def generate_placement(self) -> PlacementResult:
        logger.info("Starting IS-code compliant column placement")
        
        self._calculate_node_degrees()
        self._classify_junctions()
        self._extract_structural_grid()
        
        self._place_mandatory_corners()
        self._place_at_intersections()
        self._place_at_grid_intersections()
        self._fill_gaps()
        
        # FIX 7: Deduplicate using proximity_merge distance instead of 500mm buckets.
        # Old method: snap to 500mm grid — drops valid columns and keeps wrong ones.
        # New method: keep the HIGHER-DEGREE column when two are within proximity_merge.
        # Priority: CROSS > T > CORNER/EDGE > INTERIOR (higher degree = structural priority)
        _degree_priority = {
            JunctionType.CROSS_JUNCTION: 4,
            JunctionType.T_JUNCTION: 3,
            JunctionType.CORNER: 2,
            JunctionType.EDGE: 2,
            JunctionType.INTERIOR: 1,
        }
        deduped = []
        for col in self.columns:
            merged = False
            for existing in deduped:
                dist = math.hypot(col.x - existing.x, col.y - existing.y)
                if dist < self.proximity_merge:
                    # Keep the higher-priority junction type; upgrade if new is higher
                    if _degree_priority.get(col.junction_type, 0) > _degree_priority.get(existing.junction_type, 0):
                        existing.junction_type = col.junction_type
                        existing.degree = max(existing.degree, col.degree)
                    merged = True
                    break
            if not merged:
                deduped.append(col)
        self.columns = deduped
        
        # Re-number sequentially
        for i, col in enumerate(self.columns):
            col.id = f"C{i + 1}"
        
        self._check_short_spans()
        self._size_columns()
        self._orient_columns()
        
        stats = {
            "total_columns": len(self.columns),
            "corners": sum(1 for c in self.columns if c.junction_type == JunctionType.CORNER),
            "cross_junctions": sum(1 for c in self.columns if c.junction_type == JunctionType.CROSS_JUNCTION),
            "t_junctions": sum(1 for c in self.columns if c.junction_type == JunctionType.T_JUNCTION),
            "edge": sum(1 for c in self.columns if c.junction_type == JunctionType.EDGE),
            "interior": sum(1 for c in self.columns if c.junction_type == JunctionType.INTERIOR),
            "seismic_zone": self.seismic_zone,
            "warnings_count": len(self.warnings)
        }
        
        logger.info(f"Placement complete: {stats['total_columns']} columns, {stats['warnings_count']} warnings")
        
        return PlacementResult(
            columns=self.columns,
            warnings=self.warnings,
            stats=stats
        )
    
    @staticmethod
    def revalidate(
        columns: List[ColumnPlacement],
        centerlines: List[Tuple[Tuple[float, float], Tuple[float, float]]],
        seismic_zone: str = "III",
        building_envelope: Optional[List[Tuple[float, float]]] = None
    ) -> PlacementResult:
        """
        Re-validate a modified set of columns.

        Runs sizing, orientation, and span checks on an externally modified
        column list. Used by ColumnEditor after add/remove operations.
        """
        placer = ColumnPlacer(
            nodes=[(c.x, c.y) for c in columns],
            centerlines=centerlines,
            seismic_zone=seismic_zone,
            building_envelope=building_envelope
        )
        placer.columns = list(columns)

        # Re-run validation steps
        placer._check_short_spans()
        placer._size_columns()
        placer._orient_columns()

        stats = {
            "total_columns": len(placer.columns),
            "corners": sum(1 for c in placer.columns if c.junction_type == JunctionType.CORNER),
            "cross_junctions": sum(1 for c in placer.columns if c.junction_type == JunctionType.CROSS_JUNCTION),
            "t_junctions": sum(1 for c in placer.columns if c.junction_type == JunctionType.T_JUNCTION),
            "edge": sum(1 for c in placer.columns if c.junction_type == JunctionType.EDGE),
            "interior": sum(1 for c in placer.columns if c.junction_type == JunctionType.INTERIOR),
            "seismic_zone": seismic_zone,
            "warnings_count": len(placer.warnings)
        }

        return PlacementResult(
            columns=placer.columns,
            warnings=placer.warnings,
            stats=stats
        )

    def detect_floating_columns(
        self, 
        lower_floor_columns: List[Tuple[float, float]]
    ) -> List[PlacementWarning]:
        floating_warnings = []
        tol = 500.0
        
        for col in self.columns:
            has_support = any(
                math.hypot(col.x - lc[0], col.y - lc[1]) < tol
                for lc in lower_floor_columns
            )
            
            if not has_support:
                col.is_floating = True
                col.reinforcement_rule = ReinforcementRule.IS_13920_FULL_HEIGHT_CONFINING
                floating_warnings.append(PlacementWarning(
                    severity="CRITICAL",
                    message=f"Floating column detected: {col.id} at ({col.x:.0f}, {col.y:.0f}) has no support below",
                    column_id=col.id,
                    code_reference="IS 1893:2016 Vertical Irregularity - requires transfer girder"
                ))
        
        return floating_warnings
