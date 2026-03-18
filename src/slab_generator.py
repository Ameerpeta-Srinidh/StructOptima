"""
Slab Generation Module - IS 456:2000 Compliant

Implements slab detection and load mapping from beam grid:
- Phase 1: Closed loop detection (minimum cycles in beam graph)
- Phase 2: Slab classification (One-way vs Two-way)
- Phase 3: Thickness calculation and load computation
- Phase 4: Wall load mapping to beams
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Set
from enum import Enum
import math
import json

from .logging_config import get_logger

logger = get_logger(__name__)


class SlabType(Enum):
    ONE_WAY = "One_Way"
    TWO_WAY = "Two_Way"


class SlabZoneType(Enum):
    REGULAR = "Regular"
    STAIRCASE = "Staircase"
    LIFT_SHAFT = "Lift_Shaft"
    VOID = "Void"
    SERVICE_SHAFT = "Service_Shaft"


class LoadType(Enum):
    DEAD = "Dead"
    LIVE = "Live"
    SUPERIMPOSED = "Superimposed"
    WALL = "Wall"


@dataclass
class SlabLoad:
    load_type: LoadType
    value_kn_m2: float
    description: str
    source: str = ""


@dataclass
class SlabElement:
    id: str
    boundary_beams: List[str]
    vertices: List[Tuple[float, float]]
    slab_type: SlabType
    Lx_mm: float
    Ly_mm: float
    aspect_ratio: float
    thickness_mm: float
    area_m2: float
    zone_type: SlabZoneType = SlabZoneType.REGULAR
    loads: List[SlabLoad] = field(default_factory=list)
    total_dead_kn_m2: float = 0.0
    total_live_kn_m2: float = 0.0
    total_factored_kn_m2: float = 0.0
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "boundary_beams": self.boundary_beams,
            "type": self.slab_type.value,
            "dimensions": {
                "Lx": round(self.Lx_mm / 1000, 2),
                "Ly": round(self.Ly_mm / 1000, 2)
            },
            "thickness": int(self.thickness_mm),
            "area_m2": round(self.area_m2, 2),
            "zone_type": self.zone_type.value,
            "loads": {
                "dead_kn_m2": round(self.total_dead_kn_m2, 2),
                "live_kn_m2": round(self.total_live_kn_m2, 2),
                "factored_kn_m2": round(self.total_factored_kn_m2, 2)
            },
            "warnings": self.warnings
        }


@dataclass
class WallLoad:
    beam_id: str
    load_kn_m: float
    wall_height_mm: float
    wall_thickness_mm: float
    wall_length_mm: float
    source: str
    
    def to_dict(self) -> Dict:
        return {
            "beam_id": self.beam_id,
            "type": "Wall_Load",
            "value_kn_m": round(self.load_kn_m, 2),
            "source": self.source
        }


@dataclass 
class SlabGenerationResult:
    slabs: List[SlabElement] = field(default_factory=list)
    wall_loads: List[WallLoad] = field(default_factory=list)
    warnings: List[Dict] = field(default_factory=list)
    stats: Dict = field(default_factory=dict)
    
    def to_json(self) -> str:
        return json.dumps({
            "slabs": [s.to_dict() for s in self.slabs],
            "loads_on_beams": [w.to_dict() for w in self.wall_loads],
            "warnings": self.warnings,
            "stats": self.stats
        }, indent=2)


class SlabGenerator:
    MIN_SLAB_AREA_M2 = 1.0
    MAX_SLAB_AREA_M2 = 35.0
    MIN_THICKNESS_MM = 125.0
    CONCRETE_DENSITY_KN_M3 = 25.0
    BRICK_DENSITY_KN_M3 = 20.0
    BLOCK_DENSITY_KN_M3 = 24.0
    FLOOR_FINISH_KN_M2 = 1.0
    RESIDENTIAL_LIVE_LOAD_KN_M2 = 2.0
    PARTITION_ALLOWANCE_KN_M2 = 1.0
    DEAD_LOAD_FACTOR = 1.5
    LIVE_LOAD_FACTOR = 1.5
    
    def __init__(
        self,
        beams: List[Dict],
        columns: List[Dict],
        walls: List[Tuple[Tuple[float, float], Tuple[float, float]]],
        text_annotations: Optional[List[Dict]] = None,
        storey_height_mm: float = 3000.0,
        beam_depth_mm: float = 450.0,
        steel_grade: str = "Fe415"
    ):
        self.beams = beams
        self.columns = columns
        self.walls = walls
        self.text_annotations = text_annotations or []
        self.storey_height_mm = storey_height_mm
        self.beam_depth_mm = beam_depth_mm
        self.steel_grade = steel_grade
        
        self.slabs: List[SlabElement] = []
        self.wall_loads: List[WallLoad] = []
        self.warnings: List[Dict] = []
        
        self._compute_grid()
    
    def _compute_grid(self):
        xs = sorted(set(c.get('x', 0) for c in self.columns))
        ys = sorted(set(c.get('y', 0) for c in self.columns))
        self.x_grids = xs
        self.y_grids = ys
        self.column_positions = {(c.get('x'), c.get('y')): c for c in self.columns}
    
    def _is_close(self, p1: Tuple[float, float], p2: Tuple[float, float], 
                  tol: float = 500.0) -> bool:
        return math.hypot(p1[0] - p2[0], p1[1] - p2[1]) < tol
    
    def _get_column_at(self, x: float, y: float) -> Optional[Dict]:
        for (cx, cy), col in self.column_positions.items():
            if self._is_close((x, y), (cx, cy)):
                return col
        return None
    
    def _find_closed_loops(self) -> List[List[Tuple[float, float]]]:
        loops = []
        
        if len(self.x_grids) < 2 or len(self.y_grids) < 2:
            return loops
        
        for i in range(len(self.x_grids) - 1):
            for j in range(len(self.y_grids) - 1):
                x1, x2 = self.x_grids[i], self.x_grids[i + 1]
                y1, y2 = self.y_grids[j], self.y_grids[j + 1]
                
                corners = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
                
                has_all_corners = all(
                    self._get_column_at(cx, cy) is not None
                    for cx, cy in corners
                )
                
                if has_all_corners:
                    loops.append(corners)
        
        logger.info(f"Found {len(loops)} closed loops from beam grid")
        return loops
    
    def _filter_valid_panels(self, loops: List[List[Tuple[float, float]]]) -> List[List[Tuple[float, float]]]:
        valid = []
        
        for loop in loops:
            x_coords = [p[0] for p in loop]
            y_coords = [p[1] for p in loop]
            width = max(x_coords) - min(x_coords)
            height = max(y_coords) - min(y_coords)
            area_m2 = (width / 1000) * (height / 1000)
            
            if area_m2 < self.MIN_SLAB_AREA_M2:
                logger.info(f"Filtering loop as void/shaft: area={area_m2:.2f}m² < 1m²")
                continue
            
            valid.append(loop)
        
        return valid
    
    def _check_special_zone(self, loop: List[Tuple[float, float]]) -> SlabZoneType:
        if not self.text_annotations:
            return SlabZoneType.REGULAR
        
        x_coords = [p[0] for p in loop]
        y_coords = [p[1] for p in loop]
        min_x, max_x = min(x_coords), max(x_coords)
        min_y, max_y = min(y_coords), max(y_coords)
        
        for annotation in self.text_annotations:
            text = annotation.get('text', '').upper()
            ax = annotation.get('x', 0)
            ay = annotation.get('y', 0)
            
            if min_x <= ax <= max_x and min_y <= ay <= max_y:
                if 'STAIR' in text:
                    return SlabZoneType.STAIRCASE
                elif 'LIFT' in text or 'ELEVATOR' in text:
                    return SlabZoneType.LIFT_SHAFT
                elif 'VOID' in text or 'OPEN' in text:
                    return SlabZoneType.VOID
                elif 'SHAFT' in text or 'DUCT' in text:
                    return SlabZoneType.SERVICE_SHAFT
        
        return SlabZoneType.REGULAR
    
    def _classify_slab(self, Lx_mm: float, Ly_mm: float) -> SlabType:
        if Ly_mm <= 0 or Lx_mm <= 0:
            return SlabType.TWO_WAY
        
        ratio = Ly_mm / Lx_mm
        
        if ratio > 2.0:
            return SlabType.ONE_WAY
        else:
            return SlabType.TWO_WAY
    
    def _calculate_thickness(self, Lx_mm: float, slab_type: SlabType) -> float:
        if slab_type == SlabType.ONE_WAY:
            if self.steel_grade == "Fe250":
                t = Lx_mm / 25
            else:
                t = Lx_mm / 28
        else:
            if self.steel_grade == "Fe250":
                t = Lx_mm / 30
            else:
                t = Lx_mm / 35
        
        t = math.ceil(t / 5) * 5
        t = max(t, self.MIN_THICKNESS_MM)
        
        return t
    
    def _calculate_loads(self, slab: SlabElement):
        self_weight = (slab.thickness_mm / 1000) * self.CONCRETE_DENSITY_KN_M3
        slab.loads.append(SlabLoad(
            load_type=LoadType.DEAD,
            value_kn_m2=self_weight,
            description="Self weight",
            source=f"{slab.thickness_mm}mm slab × 25 kN/m³"
        ))
        
        slab.loads.append(SlabLoad(
            load_type=LoadType.SUPERIMPOSED,
            value_kn_m2=self.FLOOR_FINISH_KN_M2,
            description="Floor finish",
            source="IS 875 Part 1"
        ))
        
        slab.loads.append(SlabLoad(
            load_type=LoadType.LIVE,
            value_kn_m2=self.RESIDENTIAL_LIVE_LOAD_KN_M2,
            description="Residential live load",
            source="IS 875 Part 2 - Residential"
        ))
        
        slab.total_dead_kn_m2 = self_weight + self.FLOOR_FINISH_KN_M2
        slab.total_live_kn_m2 = self.RESIDENTIAL_LIVE_LOAD_KN_M2
        
        slab.total_factored_kn_m2 = (
            self.DEAD_LOAD_FACTOR * slab.total_dead_kn_m2 +
            self.LIVE_LOAD_FACTOR * slab.total_live_kn_m2
        )
    
    def _generate_slabs(self):
        loops = self._find_closed_loops()
        valid_loops = self._filter_valid_panels(loops)
        
        slab_count = 0
        for loop in valid_loops:
            x_coords = [p[0] for p in loop]
            y_coords = [p[1] for p in loop]
            
            width = max(x_coords) - min(x_coords)
            height = max(y_coords) - min(y_coords)
            
            Lx = min(width, height)
            Ly = max(width, height)
            area_m2 = (width / 1000) * (height / 1000)
            aspect_ratio = Ly / Lx if Lx > 0 else 1.0
            
            zone_type = self._check_special_zone(loop)
            
            if zone_type in [SlabZoneType.VOID, SlabZoneType.SERVICE_SHAFT]:
                logger.info(f"Skipping slab for {zone_type.value} zone")
                continue
            
            slab_type = self._classify_slab(Lx, Ly)
            thickness = self._calculate_thickness(Lx, slab_type)
            
            slab_count += 1
            slab = SlabElement(
                id=f"S{slab_count}",
                boundary_beams=[],
                vertices=loop,
                slab_type=slab_type,
                Lx_mm=Lx,
                Ly_mm=Ly,
                aspect_ratio=aspect_ratio,
                thickness_mm=thickness,
                area_m2=area_m2,
                zone_type=zone_type
            )
            
            if zone_type == SlabZoneType.STAIRCASE:
                slab.warnings.append("Staircase zone - use waist slab design")
                slab.boundary_beams.append("STAIR_SUPPORT")
            
            if area_m2 > self.MAX_SLAB_AREA_M2:
                slab.warnings.append(f"Panel area {area_m2:.1f}m² > 35m² - deflection risk")
                self.warnings.append({
                    "severity": "WARNING",
                    "message": f"Slab {slab.id} area {area_m2:.1f}m² exceeds 35m² - consider adding beam",
                    "slab_id": slab.id,
                    "code_reference": "IS 456 deflection limits"
                })
            
            self._calculate_loads(slab)
            
            self.slabs.append(slab)
            logger.info(f"Slab {slab.id}: {slab_type.value}, {Lx:.0f}×{Ly:.0f}mm, "
                       f"t={thickness:.0f}mm, {area_m2:.1f}m²")
    
    def _map_wall_loads(self):
        wall_height = self.storey_height_mm - self.beam_depth_mm
        
        for start, end in self.walls:
            wall_length = math.hypot(end[0] - start[0], end[1] - start[1])
            
            if wall_length < 500:
                continue
            
            matching_beam = None
            for beam in self.beams:
                bx1, by1 = beam.get('start_x', 0), beam.get('start_y', 0)
                bx2, by2 = beam.get('end_x', 0), beam.get('end_y', 0)
                
                if (self._is_close(start, (bx1, by1)) and self._is_close(end, (bx2, by2))) or \
                   (self._is_close(start, (bx2, by2)) and self._is_close(end, (bx1, by1))):
                    matching_beam = beam
                    break
                
                wall_vec = (end[0] - start[0], end[1] - start[1])
                beam_vec = (bx2 - bx1, by2 - by1)
                
                wall_mag = math.hypot(wall_vec[0], wall_vec[1])
                beam_mag = math.hypot(beam_vec[0], beam_vec[1])
                
                if wall_mag < 1 or beam_mag < 1:
                    continue
                
                dot = abs(wall_vec[0] * beam_vec[0] + wall_vec[1] * beam_vec[1]) / (wall_mag * beam_mag)
                if dot > 0.95:
                    mid_wall = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
                    mid_beam = ((bx1 + bx2) / 2, (by1 + by2) / 2)
                    if self._is_close(mid_wall, mid_beam, 1000):
                        matching_beam = beam
                        break
            
            if matching_beam:
                wall_thickness = 230.0
                load_kn_m = (wall_thickness / 1000) * (wall_height / 1000) * self.BRICK_DENSITY_KN_M3
                
                wall_load = WallLoad(
                    beam_id=matching_beam.get('id', 'Unknown'),
                    load_kn_m=load_kn_m,
                    wall_height_mm=wall_height,
                    wall_thickness_mm=wall_thickness,
                    wall_length_mm=wall_length,
                    source=f"{int(wall_thickness)}mm Brick Wall"
                )
                
                self.wall_loads.append(wall_load)
                logger.info(f"Wall load on {wall_load.beam_id}: {load_kn_m:.2f} kN/m")
    
    def _add_partition_allowance(self):
        for slab in self.slabs:
            if slab.zone_type == SlabZoneType.REGULAR:
                slab.loads.append(SlabLoad(
                    load_type=LoadType.SUPERIMPOSED,
                    value_kn_m2=self.PARTITION_ALLOWANCE_KN_M2,
                    description="Partition wall allowance",
                    source="IS 875 - movable partitions"
                ))
                slab.total_dead_kn_m2 += self.PARTITION_ALLOWANCE_KN_M2
                slab.total_factored_kn_m2 += self.DEAD_LOAD_FACTOR * self.PARTITION_ALLOWANCE_KN_M2
    
    def generate(self) -> SlabGenerationResult:
        logger.info("Starting slab generation")
        
        logger.info("Phase 1: Finding closed loops")
        self._generate_slabs()
        
        logger.info("Phase 2: Mapping wall loads")
        self._map_wall_loads()
        
        logger.info("Phase 3: Adding partition allowances")
        self._add_partition_allowance()
        
        one_way_count = sum(1 for s in self.slabs if s.slab_type == SlabType.ONE_WAY)
        two_way_count = sum(1 for s in self.slabs if s.slab_type == SlabType.TWO_WAY)
        
        stats = {
            "total_slabs": len(self.slabs),
            "one_way_slabs": one_way_count,
            "two_way_slabs": two_way_count,
            "total_wall_loads": len(self.wall_loads),
            "warnings_count": len(self.warnings),
            "total_slab_area_m2": sum(s.area_m2 for s in self.slabs)
        }
        
        logger.info(f"Slab generation complete: {stats['total_slabs']} slabs, "
                   f"{stats['total_wall_loads']} wall loads")
        
        return SlabGenerationResult(
            slabs=self.slabs,
            wall_loads=self.wall_loads,
            warnings=self.warnings,
            stats=stats
        )
