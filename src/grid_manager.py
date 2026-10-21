import math
import re
from typing import Dict, List, Literal, Tuple, Optional, Any
from pydantic import BaseModel, PositiveFloat

from .materials import Concrete
from .logging_config import get_logger

logger = get_logger(__name__)

# Largest plan dimension StructOptima handles, the same plausibility bound used to accept DXF $INSUNITS
# (cad_loader / dxf_layers): geometry beyond it is a drawing or unit error, not a building
MAX_PLAN_EXTENT_M = 1000.0


class InvalidStructureError(ValueError):
    """The geometry is not a structure StructOptima designs (an input the user can fix, not a calculation error)."""


def check_plan_geometry(gm: "GridManager", beams: list) -> None:
    """Raise ``ValueError`` (an input error the user can fix) when the columns, beams and walls have a non-finite
    coordinate or span more than ``MAX_PLAN_EXTENT_M``: nothing is designed from such geometry (a stray line far
    from the building made beams and walls kilometres long and the building weight absurd)."""
    pts = [("column " + c.id, c.x, c.y) for c in gm.columns]
    for b in beams:
        for p in (b.start_point, b.end_point):
            if p is not None:
                pts.append(("beam " + b.id, p.x, p.y))
    for w in gm.walls:
        pts += [("wall " + w.id, w.start_x, w.start_y), ("wall " + w.id, w.end_x, w.end_y)]
    for name, x, y in pts:
        if not (math.isfinite(x) and math.isfinite(y)):
            raise InvalidStructureError(f"The {name} has an invalid coordinate ({x}, {y}): the drawing or model is damaged. "
                             f"Correct it and load it again.")
    if not pts:
        return
    base = [c for c in gm.columns if c.level == 0] or gm.columns
    if base and (len({round(c.x, 3) for c in base}) < 2 or len({round(c.y, 3) for c in base}) < 2):
        # D-33: StructOptima designs frames carrying floor slabs; columns on one line enclose no slab panel (and
        # give a floor without rotational mass: the 3D dynamic model has no solution)
        raise InvalidStructureError(f"The {len(base)} column(s) read all lie on one line, so they enclose no floor slab. "
                         f"StructOptima designs frame buildings with slabs: at least one bay needs columns on two grid "
                         f"lines in each direction. Check that every column is on a column layer.")
    for axis in (1, 2):
        lo, hi = min(pts, key=lambda p: p[axis]), max(pts, key=lambda p: p[axis])
        if hi[axis] - lo[axis] > MAX_PLAN_EXTENT_M:
            raise InvalidStructureError(
                f"The structure spans {hi[axis] - lo[axis]:,.0f} m in {'XY'[axis - 1]} (from the {lo[0]} to the "
                f"{hi[0]}); StructOptima handles plans up to {MAX_PLAN_EXTENT_M:.0f} m. A line is probably drawn far "
                f"from the building or the drawing units are wrong: check the drawing extents and units.")


class Column(BaseModel):
    id: str
    x: float
    y: float
    level: int = 0
    z_bottom: float = 0.0
    z_top: float = 3.0
    type: Literal["corner", "edge", "interior"] = "interior"
    trib_area_m2: float = 0.0
    load_kn: float = 0.0
    width_nb: float = 300.0
    depth_nb: float = 300.0
    staircase_add_load: float = 0.0
    junction_type: str = "interior"
    is_floating: bool = False
    reinforcement_rule: str = "IS_456_Standard"
    orientation_deg: float = 0.0
    # "x" / "y": the column stands in a wall line along that axis with its side across the wall equal to the wall
    # (IS 456 Fig. 1 "50 % exposed"); None: free-standing (D-29)
    wall_dir: Optional[str] = None
    # SERVICE load split from calculate_loads (load_kn = load_dl_kn + load_ll_kn)
    load_dl_kn: float = 0.0
    load_ll_kn: float = 0.0
    plinth_load_kn: float = 0.0      # ground-storey wall load carried by plinth beams (level 0 only)
    # Factored design actions from analysis_integration: (combo, Pu kN, Mx kNm, My kNm)
    # Mx = moment with lever arm along X (width_nb), My = lever arm along Y (depth_nb)
    design_forces: List[Tuple[str, float, float, float]] = []
    
    @property
    def label(self) -> str:
        return f"{int(self.width_nb)}x{int(self.depth_nb)}"
    
    @property
    def area_mm2(self) -> float:
        return self.width_nb * self.depth_nb

class Wall(BaseModel):
    """Masonry/RCC wall element for dead load calculation and BOM.
    
    Material densities per IS 875 (Part 1):1987 Table 1:
      - Burnt clay brick: 19.2 kN/m³
      - AAC block: 7.5 kN/m³
      - RCC shear wall: 25.0 kN/m³
    """
    id: str
    start_x: float  # meters
    start_y: float  # meters
    end_x: float    # meters
    end_y: float    # meters
    thickness_mm: float = 230.0  # Standard 9-inch brick wall
    height_m: float = 3.0  # Wall height (story height minus beam depth)
    material: Literal["brick", "aac_block", "rcc"] = "brick"
    is_load_bearing: bool = True
    level: int = 0
    opening_fraction: float = 0.33  # 1/3 deducted for doors/windows (practical estimate)
    col_start_id: str = ""   # Column at start of wall
    col_end_id: str = ""     # Column at end of wall
    is_exterior: bool = True # True for perimeter walls, False for interior partitions
    
    @property
    def length_m(self) -> float:
        import math as _m
        return _m.hypot(self.end_x - self.start_x, self.end_y - self.start_y)
    
    @property
    def density_kn_m3(self) -> float:
        """IS 875 (Part 1):1987 Table 1"""
        densities = {"brick": 19.2, "aac_block": 7.5, "rcc": 25.0}
        return densities.get(self.material, 19.2)
    
    @property
    def line_load_kn_m(self) -> float:
        """Dead load per meter run of wall (kN/m), with opening deduction."""
        thickness_m = self.thickness_mm / 1000.0
        effective_height = self.height_m * (1.0 - self.opening_fraction)
        return thickness_m * effective_height * self.density_kn_m3

class GridManager(BaseModel):
    width_m: float
    length_m: float
    num_stories: int = 1
    story_height_m: float = 3.0
    max_span_m: float = 6.0  # IS 456 Table 26: economical residential slab span ≤ 5-6m
    
    # Cantilever Config (Phase 9)
    cantilever_dirs: List[str] = [] # "top","bottom","left","right"
    cantilever_len_m: float = 1.5
    
    x_grid_lines: List[float] = []
    y_grid_lines: List[float] = []
    columns: List[Column] = []
    footings: List[Any] = [] # Using Any to avoid circular import issues with Footing
    walls: List[Wall] = []   # Architectural/structural walls from DXF
    
    # Void Zones for Opening Deductions (List of (x_idx, y_idx) tuples for bays)
    void_zones: List[Tuple[int, int]] = []
    
    # Store detailed rebar info per column ID
    rebar_schedule: dict = {} # {col_id: RebarResult}
    beam_schedule: dict = {} # {beam_id: BeamRebarResult}
    slab_schedule: dict = {} # {slab_id: SlabRebarResult}
    staircase_schedule: dict = {} # {stair_id: StaircaseResult}

    # Material and load context (set by design_pipeline / calculate_loads)
    fck: float = 25.0
    fy: float = 415.0
    slab_thickness_mm: float = 125.0
    # Nominal covers (mm) used by the detailing; set from the exposure condition and fire rating by the design
    # pipeline (src/durability.py: IS 456 Tables 16 and 16A, 26.4.2.1, 26.4.2.2)
    beam_cover_mm: float = 25.0
    slab_cover_mm: float = 20.0
    column_cover_mm: float = 40.0
    footing_cover_mm: float = 50.0
    dead_load_kn_m2: float = 0.0          # floor dead load incl. slab self-weight (service)
    live_load_kn_m2: float = 0.0          # floor live load (service)
    roof_dead_kn_m2: float = 0.0
    roof_live_kn_m2: float = 0.0
    superimposed_dead_kn_m2: float = 0.0  # finishes + partitions + services (for slab design)
    fallback_wall_load_kn_m: float = 0.0
    load_split_known: bool = False
    void_bays: List[Tuple[int, int]] = []  # bays without slab (staircase / voids)
    # Plan line segments ((x1, y1), (x2, y2)) in m bounding the floor (walls and
    # beams); used to decide whether a bay lies inside the building.
    boundary_segments: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
    # column sizes as drawn in the DXF, mm, keyed "x,y" (m, 3 decimals): reported when the design differs
    drawn_column_sizes_mm: Dict[str, Tuple[float, float]] = {}
    
    def _estimate_initial_column_size(self, col_type: str, trib_area_est: float) -> tuple:
        """Estimate column size based on story count, position, and IS 456 Cl 39.3.
        
        Floor load per IS 875:
          - Dead load (125mm slab + finish + partitions): ~4.5 kN/m²
          - Live load (residential IS 875 Pt2):            ~2.0 kN/m²
          - Self-weight of beams (approx):                ~1.5 kN/m²
          - Total service load:                           ~8.0 kN/m²
        """
        fck = 25.0
        fy = 415.0
        floor_load = 8.0  # FIX 3: kN/m² per IS 875 Part 1 & 2 (was 12.0 — too high)
        pu_kn = trib_area_est * floor_load * self.num_stories * 1.5  # Factored per IS 456 Table 18
        pu_n = pu_kn * 1000.0
        
        # Per IS 456 Cl 34.1.3: minimum column dimension = 200mm; practice = 230mm (brick module)
        # Per IS 13920 Cl 6.1.3: min 300mm for seismic zones III/IV/V
        width = 230.0
        depth = 230.0
        while True:
            ag = width * depth
            asc = 0.008 * ag  # IS 456 Cl 26.5.3.1: min 0.8% steel
            ac = ag - asc
            # IS 456 Cl 39.3: Pu = 0.4*fck*Ac + 0.67*fy*Asc
            p_cap_n = (0.4 * fck * ac) + (0.67 * fy * asc)
            if p_cap_n >= pu_n:
                break
            # Increment by 50mm (standard size increment on site)
            width += 50.0
            depth += 50.0
            if width > 1500:
                break
        
        # Min sizes per IS 456 / IS 13920 / practice
        # Corner/edge: 230×300 min; interior: 300×300 min
        if col_type == "corner":
            width = max(width, 230.0)
            depth = max(depth, 300.0)
        elif col_type == "edge":
            width = max(width, 230.0)
            depth = max(depth, 300.0)
        else:  # interior
            width = max(width, 300.0)
            depth = max(depth, 300.0)
        # Round to nearest 25mm module (standard formwork sizes)
        width = math.ceil(width / 25.0) * 25.0
        depth = math.ceil(depth / 25.0) * 25.0
        return width, depth

    def _choose_bay_count(self, dimension_m: float) -> int:
        """Choose number of bays such that each span falls in 3–5m range.
        
        Per IS 456 / SP 34 / NBC 2016:
          - Preferred residential RCC slab span: 3.0–5.0m (two-way action, 125mm slab)
          - Beyond 5m, slab thickness rises uneconomically (L/d = 40 → 125mm @ 5m)
          - Below 3m, column count is excessive and uneconomical
        """
        MIN_SPAN = 3.0  # metres
        MAX_SPAN = 5.0  # metres (IS 456 Table 26 economical limit for residential)
        
        # Find the minimum number of bays that gives span ≤ MAX_SPAN
        n = max(1, math.ceil(dimension_m / MAX_SPAN))
        span = dimension_m / n
        
        # If span is already ≥ MIN_SPAN, we're in the sweet spot — done
        if span >= MIN_SPAN:
            return n
        
        # Span is < MIN_SPAN with n bays — try fewer bays (larger spans)
        # This can happen for very small buildings (< 6m)
        while n > 1 and (dimension_m / (n - 1)) <= MAX_SPAN:
            n -= 1
        return n

    def generate_grid(self):
        """Generates IS 456-compliant column grid with preferred 3–5m bay spacing.
        
        FIX 4: Bay sizing now chooses spans in the 3–5m economical range
        (IS 456 Table 26 + SP 34) rather than raw division by max_span.
        FIX 2: Edge column type and tributary area are no longer overwritten.
        """
        # FIX 4: Use economical bay sizing (3–5m) per IS 456
        num_bays_x = self._choose_bay_count(self.width_m)
        num_bays_y = self._choose_bay_count(self.length_m)
        
        num_bays_x = max(1, num_bays_x)
        num_bays_y = max(1, num_bays_y)
        
        span_x = self.width_m / num_bays_x
        span_y = self.length_m / num_bays_y
        
        self.x_grid_lines = [round(i * span_x, 4) for i in range(num_bays_x + 1)]
        self.y_grid_lines = [round(j * span_y, 4) for j in range(num_bays_y + 1)]
        
        self.columns = []
        
        num_x = len(self.x_grid_lines)
        num_y = len(self.y_grid_lines)
        
        for i_x, x in enumerate(self.x_grid_lines):
            for i_y, y in enumerate(self.y_grid_lines):
                col_index = i_x * num_y + i_y + 1
                
                # Determine column type for initial sizing
                is_edge_x = (i_x == 0 or i_x == num_x - 1)
                is_edge_y = (i_y == 0 or i_y == num_y - 1)
                if is_edge_x and is_edge_y:
                    col_type = "corner"
                    trib_est = (span_x / 2) * (span_y / 2)
                elif is_edge_x or is_edge_y:
                    # FIX 2: Keep "edge" type — do NOT overwrite with "interior"
                    col_type = "edge"
                    fx = span_x / 2 if is_edge_x else span_x
                    fy_val = span_y / 2 if is_edge_y else span_y
                    trib_est = fx * fy_val
                else:
                    col_type = "interior"
                    trib_est = span_x * span_y
                
                w, d = self._estimate_initial_column_size(col_type, trib_est)
                
                # Create a base column to pass into stack_columns
                base_col = Column(
                    id=f"C{col_index}",
                    x=x, 
                    y=y,
                    type=col_type,
                    width_nb=w,
                    depth_nb=d
                )
                self.columns.append(base_col)
                
        # Stack all base columns
        self.columns = self.stack_columns(self.columns, self.num_stories, self.story_height_m)
        
    def stack_columns(self, base_cols: List[Column], num_stories: int, story_height_m: float) -> List[Column]:
        """Utility to stack a list of 2D plan columns into 3D multi-story columns."""
        stacked = []
        for level in range(num_stories):
            z_bot = level * story_height_m
            z_top = (level + 1) * story_height_m
            for base_c in base_cols:
                new_c = base_c.model_copy()
                # If it already has _L[level], just use it, else append
                if "_L" not in new_c.id:
                    new_c.id = f"{base_c.id}_L{level}"
                new_c.level = level
                new_c.z_bottom = z_bot
                new_c.z_top = z_top
                stacked.append(new_c)
        return stacked

    def calculate_trib_areas(self, staircase_bay: Optional[Tuple[int, int]] = None, void_zones: List[Tuple[int, int]] = None):
        """
        Calculates influence area.
        staircase_bay: Optional (x_idx, y_idx) of bay to be voided.
        void_zones: List of (x,y) bay indices to void.
        """
        if not self.x_grid_lines or not self.y_grid_lines:
            return

        # ── FIX: Ensure ALL column positions exist in grid lines ──
        # Intermediate columns placed by AutoFramer may not be in the original grid.
        # Without their coordinates in the grid, trib_area will be zero.
        GRID_TOL = 0.01  # 10mm tolerance for matching
        for col in self.columns:
            # Check X
            if not any(abs(gx - col.x) < GRID_TOL for gx in self.x_grid_lines):
                self.x_grid_lines.append(round(col.x, 4))
                self.x_grid_lines.sort()
            # Check Y
            if not any(abs(gy - col.y) < GRID_TOL for gy in self.y_grid_lines):
                self.y_grid_lines.append(round(col.y, 4))
                self.y_grid_lines.sort()

        x_min, x_max = min(self.x_grid_lines), max(self.x_grid_lines)
        y_min, y_max = min(self.y_grid_lines), max(self.y_grid_lines)
        
        if len(self.x_grid_lines) < 2 or len(self.y_grid_lines) < 2:
             logger.warning("Insufficient grid lines for tributary area calculation.")
             return

        # Combine legacy and new voids
        all_voids = []
        if staircase_bay:
            all_voids.append(staircase_bay)
        if void_zones:
            all_voids.extend(void_zones)
        if self.void_zones:
            all_voids.extend(v for v in self.void_zones if v not in all_voids)
        self.void_bays = list(all_voids)
            
        # Coordinates of void corners
        void_corners = []
        for vx_idx, vy_idx in all_voids:
            if 0 <= vx_idx < len(self.x_grid_lines)-1 and 0 <= vy_idx < len(self.y_grid_lines)-1:
                x0, x1 = self.x_grid_lines[vx_idx], self.x_grid_lines[vx_idx+1]
                y0, y1 = self.y_grid_lines[vy_idx], self.y_grid_lines[vy_idx+1]
                void_corners.append( (x0, y0, x1, y1) )

        sorted_x = sorted(self.x_grid_lines)
        sorted_y = sorted(self.y_grid_lines)

        for col in self.columns:
            col.staircase_add_load = 0.0
        for col in self.columns:
            # Find adjacent grid lines for THIS column (non-uniform safe)
            x_idx = None
            for idx, gx in enumerate(sorted_x):
                if abs(gx - col.x) < 0.01:
                    x_idx = idx
                    break
            y_idx = None
            for idx, gy in enumerate(sorted_y):
                if abs(gy - col.y) < 0.01:
                    y_idx = idx
                    break
            
            if x_idx is None or y_idx is None:
                col.trib_area_m2 = 0.0
                continue
            
            # Tributary width X: half-span to left + half-span to right
            left_x = (sorted_x[x_idx] - sorted_x[x_idx - 1]) / 2.0 if x_idx > 0 else 0.0
            right_x = (sorted_x[x_idx + 1] - sorted_x[x_idx]) / 2.0 if x_idx < len(sorted_x) - 1 else 0.0
            width_x = left_x + right_x
            
            # Tributary width Y
            below_y = (sorted_y[y_idx] - sorted_y[y_idx - 1]) / 2.0 if y_idx > 0 else 0.0
            above_y = (sorted_y[y_idx + 1] - sorted_y[y_idx]) / 2.0 if y_idx < len(sorted_y) - 1 else 0.0
            width_y = below_y + above_y
            
            is_edge_x = (x_idx == 0 or x_idx == len(sorted_x) - 1)
            is_edge_y = (y_idx == 0 or y_idx == len(sorted_y) - 1)
            
            # Categorize
            if is_edge_x and is_edge_y:
                col.type = "corner"
            elif is_edge_x or is_edge_y:
                col.type = "edge"
            else:
                col.type = "interior"
            
            # Base Area
            col.trib_area_m2 = width_x * width_y
            
            # Check proximity to voids
            # Simple check: If column is ONE of the corners of the void rects, reduce area.
            # A column contributes area to 1, 2, or 4 bays.
            # If a bay it touches is void, reduce area by (SpanX/2 * SpanY/2).
            
            for (v_x0, v_y0, v_x1, v_y1) in void_corners:
                # Is column a corner of this void?
                if (abs(col.x - v_x0) < 0.1 or abs(col.x - v_x1) < 0.1) and \
                   (abs(col.y - v_y0) < 0.1 or abs(col.y - v_y1) < 0.1):
                    # It touches this void bay. Remove 25% contribution.
                    v_span_x = abs(v_x1 - v_x0)
                    v_span_y = abs(v_y1 - v_y0)
                    reduction = (v_span_x/2.0) * (v_span_y/2.0)
                    col.trib_area_m2 = max(0.0, col.trib_area_m2 - reduction)
                    
                    # Phase 10: Staircase Load (Point Load Conversion)
                    # Void area ~ 25% of bay for this column corner
                    # Load = Area * 15 kN/m2 (Dl+LL for stairs)
                    s_area = reduction
                    s_load = s_area * 15.0
                    
                    # Store as attribute to be picked up in calculate_loads
                    # If it already exists (from another void), add to it
                    current_s = getattr(col, 'staircase_add_load', 0.0)
                    setattr(col, 'staircase_add_load', current_s + s_load)

    # ------------------------------------------------------------------
    # Load takedown
    # ------------------------------------------------------------------
    def set_load_intensities(self, dead_kn_m2: float, live_kn_m2: float,
                             roof_dead_kn_m2: Optional[float] = None, roof_live_kn_m2: Optional[float] = None):
        """Record SERVICE area loads (kN/m2, slab self-weight included in dead)."""
        self.dead_load_kn_m2 = dead_kn_m2
        self.live_load_kn_m2 = live_kn_m2
        self.roof_dead_kn_m2 = dead_kn_m2 if roof_dead_kn_m2 is None else roof_dead_kn_m2
        self.roof_live_kn_m2 = live_kn_m2 if roof_live_kn_m2 is None else roof_live_kn_m2

    def _wall_load_map(self) -> dict:
        """Wall line loads lumped to the nearest columns (half to each end), per
        plan location {(x, y): kN} for ONE storey of walls."""
        wall_load_map = {}
        if not self.walls or not self.columns:
            return wall_load_map
        for w in self.walls:
            total_w_load = w.length_m * w.line_load_kn_m
            start_c = min(self.columns, key=lambda c: math.hypot(c.x - w.start_x, c.y - w.start_y))
            end_c = min(self.columns, key=lambda c: math.hypot(c.x - w.end_x, c.y - w.end_y))
            k1, k2 = (start_c.x, start_c.y), (end_c.x, end_c.y)
            if k1 == k2:
                wall_load_map[k1] = wall_load_map.get(k1, 0.0) + total_w_load
            else:
                wall_load_map[k1] = wall_load_map.get(k1, 0.0) + total_w_load / 2.0
                wall_load_map[k2] = wall_load_map.get(k2, 0.0) + total_w_load / 2.0
        return wall_load_map

    def _beam_self_weight_map(self, beams: Optional[List[Any]]) -> dict:
        """Half of each framing beam's web self-weight lumped to each end
        column, {(x, y): kN} per floor.  Web depth = D - slab thickness, less the half beam width of each adjacent
        panel designed thicker than that slab (already in the tributary slab load, finding N46)."""
        from .analysis_integration import beam_slab_coefficients, web_self_weight_kn_m   # (circular at import time)
        out = {}
        t = self.slab_thickness_mm / 1000.0
        if beams:
            valid = [b for b in beams if b.end_point is not None]
            over = beam_slab_coefficients(self, valid, return_extra=True)[2] if valid else {}
            for b in valid:
                L = math.hypot(b.end_point.x - b.start_point.x, b.end_point.y - b.start_point.y)
                sw = web_self_weight_kn_m(b, t, over.get(b.id, 0.0)) * L
                for p in (b.start_point, b.end_point):
                    c = min(self.columns, key=lambda c: math.hypot(c.x - p.x, c.y - p.y)) if self.columns else None
                    if c is not None and math.hypot(c.x - p.x, c.y - p.y) < 0.3:
                        out[(c.x, c.y)] = out.get((c.x, c.y), 0.0) + sw / 2.0
                    # beam ends that do not land on a column (secondary beams)
                    # are distributed by the slab tributary logic - not lumped here
        return out

    def calculate_loads(self, floor_load_kn_m2: Optional[float] = None, wall_load_kn_m: float = 0.0,
                        dead_load_kn_m2: Optional[float] = None, live_load_kn_m2: Optional[float] = None,
                        roof_dead_kn_m2: Optional[float] = None, roof_live_kn_m2: Optional[float] = None,
                        beams: Optional[List[Any]] = None):
        """Cumulative SERVICE load takedown, top to bottom.

        Preferred call: ``dead_load_kn_m2`` (slab self-weight + finishes +
        partitions + services) and ``live_load_kn_m2`` with optional roof
        values.  Legacy call: ``floor_load_kn_m2`` alone is treated entirely as
        dead load (conservative for seismic mass, identical for 1.5DL+1.5LL).

        Per column and storey: slab load (tributary area x roof or floor
        intensity) + cantilever slab share + wall load (actual Wall objects, or
        ``wall_load_kn_m`` x half spans when no walls exist) + framing beam web
        self-weight (from ``beams`` when given, otherwise 230x(450-t) estimate)
        + column self-weight + staircase allowance.

        Results: ``load_dl_kn``, ``load_ll_kn``, ``load_kn`` (sum, SERVICE).
        Ground-storey walls are carried by plinth beams and stored as
        ``plinth_load_kn`` on level-0 columns (added at the footing).
        """
        if dead_load_kn_m2 is None and live_load_kn_m2 is None:
            if floor_load_kn_m2 is None:
                raise ValueError("calculate_loads needs floor_load_kn_m2 or dead/live intensities")
            self.set_load_intensities(floor_load_kn_m2, 0.0, roof_dead_kn_m2, roof_live_kn_m2)
            self.load_split_known = False
        else:
            self.set_load_intensities(dead_load_kn_m2 or 0.0, live_load_kn_m2 or 0.0, roof_dead_kn_m2, roof_live_kn_m2)
            self.load_split_known = True
        self.fallback_wall_load_kn_m = wall_load_kn_m

        wall_load_map = self._wall_load_map()
        beam_sw_map = self._beam_self_weight_map(beams)
        panel_extra = self.panel_extra_dead_kn_m2()   # N13: designed slab thickness
        sorted_x = sorted(self.x_grid_lines)
        sorted_y = sorted(self.y_grid_lines)
        t = self.slab_thickness_mm / 1000.0

        stacks = {}
        for col in self.columns:
            stacks.setdefault((col.x, col.y), []).append(col)

        for key, stack in stacks.items():
            stack.sort(key=lambda c: c.level, reverse=True)
            cum_dl = cum_ll = 0.0
            for col in stack:
                is_roof = col.level >= self.num_stories - 1
                q_dl = self.roof_dead_kn_m2 if is_roof else self.dead_load_kn_m2
                q_ll = self.roof_live_kn_m2 if is_roof else self.live_load_kn_m2
                dl = col.trib_area_m2 * q_dl
                ll = col.trib_area_m2 * q_ll

                x_idx = next((i for i, gx in enumerate(sorted_x) if abs(gx - col.x) < 0.01), None)
                y_idx = next((i for i, gy in enumerate(sorted_y) if abs(gy - col.y) < 0.01), None)
                left = (sorted_x[x_idx] - sorted_x[x_idx - 1]) / 2.0 if x_idx else 0.0
                right = (sorted_x[x_idx + 1] - sorted_x[x_idx]) / 2.0 if x_idx is not None and x_idx < len(sorted_x) - 1 else 0.0
                below = (sorted_y[y_idx] - sorted_y[y_idx - 1]) / 2.0 if y_idx else 0.0
                above = (sorted_y[y_idx + 1] - sorted_y[y_idx]) / 2.0 if y_idx is not None and y_idx < len(sorted_y) - 1 else 0.0
                bl_x, bl_y = left + right, below + above
                beam_len = bl_x + bl_y

                # N13: extra dead load of panels designed thicker than the occupancy slab,
                # from the quarter of each adjacent panel inside the tributary area
                if panel_extra and x_idx is not None and y_idx is not None:
                    for (ii, hx) in ((x_idx - 1, left), (x_idx, right)):
                        for (jj, hy) in ((y_idx - 1, below), (y_idx, above)):
                            dl += panel_extra.get((ii, jj), 0.0) * hx * hy

                if self.cantilever_dirs and sorted_x and sorted_y:
                    is_left, is_right = abs(col.x - sorted_x[0]) < 0.1, abs(col.x - sorted_x[-1]) < 0.1
                    is_bot, is_top = abs(col.y - sorted_y[0]) < 0.1, abs(col.y - sorted_y[-1]) < 0.1
                    c_len = self.cantilever_len_m
                    c_area = 0.0
                    if "left" in self.cantilever_dirs and is_left:
                        c_area += (bl_y if not (is_bot or is_top) else bl_y / 2) * c_len; beam_len += c_len
                    if "right" in self.cantilever_dirs and is_right:
                        c_area += (bl_y if not (is_bot or is_top) else bl_y / 2) * c_len; beam_len += c_len
                    if "bottom" in self.cantilever_dirs and is_bot:
                        c_area += (bl_x if not (is_left or is_right) else bl_x / 2) * c_len; beam_len += c_len
                    if "top" in self.cantilever_dirs and is_top:
                        c_area += (bl_x if not (is_left or is_right) else bl_x / 2) * c_len; beam_len += c_len
                    dl += c_area * q_dl
                    ll += c_area * q_ll

                if self.walls:
                    # Roof: parapet assumed 1/3 of a storey wall (project assumption)
                    wall = wall_load_map.get(key, 0.0) * (0.33 if is_roof else 1.0)
                else:
                    wall = beam_len * wall_load_kn_m
                dl += wall

                if beams:
                    dl += beam_sw_map.get(key, 0.0)
                else:
                    dl += beam_len * 0.23 * max(0.45 - t, 0.0) * 25.0

                dl += (col.width_nb / 1000.0) * (col.depth_nb / 1000.0) * self.story_height_m * 25.0
                if col.staircase_add_load:
                    # 15 kN/m2 stair allowance split 12 DL + 3 LL (project assumption)
                    dl += col.staircase_add_load * 0.8
                    ll += col.staircase_add_load * 0.2

                cum_dl += dl
                cum_ll += ll
                col.load_dl_kn = cum_dl
                col.load_ll_kn = cum_ll
                col.load_kn = cum_dl + cum_ll
                col.plinth_load_kn = wall_load_map.get(key, 0.0) if (col.level == 0 and self.walls) else 0.0

    def optimize_column_sizes(self, concrete: Concrete, fy: float = 415.0,
                              wall_thickness_mm: float = 230.0,
                              align_to_wall: bool = False,
                              seismic_zone: str = "III"):
        """
        Iterative sizing per column segment based on IS 456:2000 Cl 39.3.
        Pu = 0.4 fck Ac + 0.67 fy Asc
        Assumption: Min steel 0.8% (Asc = 0.008 Ag).
        
        After individual sizing:
          - Enforces IS 13920 Cl 6.1.3 minimum 300mm for seismic zones III/IV/V
          - Enforces per-type practice minimums (corner/edge 230×300, interior 300×300)
          - Optionally aligns one face to wall thickness (Change 5)
          - Locks each XY stack to its maximum size (Change 7)
          - Groups similar sizes within ±15mm to standardize schedule (Change 6)
        """
        fck = concrete.fck
        is_seismic = seismic_zone in ("III", "IV", "V")
        
        # Preferred sizes for snap-to (brick module + formwork standards)
        PREF = [230, 300, 350, 380, 400, 450, 500, 550, 600, 650, 700, 750, 800]
        
        def snap_pref(val: float) -> float:
            for p in PREF:
                if p >= val:
                    return float(p)
            return float(math.ceil(val / 25.0) * 25.0)
        
        for col in self.columns:
            # col.load_kn contains SERVICE (unfactored) cumulative loads from calculate_loads()
            pu_n = col.load_kn * 1.5 * 1000.0  # Factored load in Newtons (IS 456 Table 18)
            
            # Start at minimum per IS 456 Cl 34.1 (230mm)
            width = 230.0
            depth = 230.0
            
            while True:
                ag = width * depth
                asc = 0.008 * ag  # Min 0.8% steel per IS 456 Cl 26.5.3.1
                ac = ag - asc
                
                # IS 456:2000 Cl 39.3: Pu = 0.4*fck*Ac + 0.67*fy*Asc
                p_cap_n = (0.4 * fck * ac) + (0.67 * fy * asc)
                
                if p_cap_n >= pu_n:
                    col.width_nb = width
                    col.depth_nb = depth
                    break
                
                width += 50.0
                depth += 50.0
                
                if width > 2000:  # Safety break
                    col.width_nb = width
                    col.depth_nb = depth
                    break
            
            # ── IS 13920 Cl 6.1.3: Minimum 300mm in seismic zones III/IV/V ──
            if is_seismic:
                col.width_nb = max(col.width_nb, 300.0)
                col.depth_nb = max(col.depth_nb, 300.0)
            
            # ── Per-type practice minimums (SP 34 Ch5 / IS 456 practice) ────
            # User requirement: Min 300x450 for ALL columns
            # Increase to 400x600 for interior columns with >400kN load
            col.width_nb = max(col.width_nb, 300.0)
            col.depth_nb = max(col.depth_nb, 450.0)
            
            if col.type == "interior" and col.load_kn > 400:
                col.width_nb = max(col.width_nb, 400.0)
                col.depth_nb = max(col.depth_nb, 600.0)
            
            # Snap to preferred size (round up to nearest standard size)
            col.width_nb = snap_pref(col.width_nb)
            col.depth_nb = snap_pref(col.depth_nb)
            
            # Change 5: Align one face to wall thickness for architectural alignment
            # Per IS 456 Cl 34.1 & IS SP:24 commentary: column face should align with wall
            if align_to_wall:
                # Keep the load-governed dimension, align the SMALLER face to wall
                if col.width_nb <= col.depth_nb:
                    col.width_nb = max(col.width_nb, wall_thickness_mm)
                    col.width_nb = snap_pref(col.width_nb)
                else:
                    col.depth_nb = max(col.depth_nb, wall_thickness_mm)
                    col.depth_nb = snap_pref(col.depth_nb)
        
        # Change 7: Lock each XY stack to its maximum computed size
        # Columns must not change size mid-stack (constructability + IS 456)
        stacks = {}
        for col in self.columns:
            key = (round(col.x, 2), round(col.y, 2))
            if key not in stacks:
                stacks[key] = []
            stacks[key].append(col)
        
        for key, stack in stacks.items():
            max_w = max(c.width_nb for c in stack)
            max_d = max(c.depth_nb for c in stack)
            for c in stack:
                c.width_nb = max_w
                c.depth_nb = max_d
        
        # Change 6: Group columns by similar size (within ±15mm tolerance)
        # Canonical size = FIRST encountered in that group (which is the largest due to stack locking)
        # ±15mm prevents merging 280 → 300 or 300 → 280 incorrectly
        unique_sizes = []
        for col in self.columns:
            found = False
            for (gw, gd) in unique_sizes:
                # Only group UPWARD (canonical >= current, within 15 mm) - audit finding R26
                if 0 <= gw - col.width_nb <= 15 and 0 <= gd - col.depth_nb <= 15:
                    col.width_nb = gw
                    col.depth_nb = gd
                    found = True
                    break
            if not found:
                unique_sizes.append((col.width_nb, col.depth_nb))
        
        logger.info(f"Column grouping complete: {len(unique_sizes)} unique size groups")
                    
    # ... (Keep existing methods)
        
    def generate_beams(self):
        """Generates beams based on grid."""
        # This mirrors the logic in main.py but keeps it centralized
        from .framing_logic import StructuralMember, Point, MemberProperties
        beams = []
        beam_count = 0
        
        start_x = self.x_grid_lines[0]
        end_x = self.x_grid_lines[-1]
        start_y = self.y_grid_lines[0]
        end_y = self.y_grid_lines[-1]
        
        cant_len = self.cantilever_len_m
        dirs = self.cantilever_dirs
        
        # Horizontal Beams
        for y in self.y_grid_lines:
            beam_start_x = start_x
            beam_end_x = end_x
            
            # Cantilever Left
            if "left" in dirs: beam_start_x -= cant_len
            if "right" in dirs: beam_end_x += cant_len
                
            for i in range(len(self.x_grid_lines) - 1):
                x1 = self.x_grid_lines[i]
                x2 = self.x_grid_lines[i+1]
                span_m = abs(x2 - x1)
                depth_mm = max(300.0, math.ceil((span_m * 1000) / 12.0 / 50.0) * 50.0)
                width_mm = 230.0 if depth_mm <= 600 else 300.0
                beam_count += 1
                beams.append(StructuralMember(id=f"B_H_{beam_count}", type="beam",
                    start_point=Point(x=x1, y=y), end_point=Point(x=x2, y=y),
                    properties=MemberProperties(width_mm=width_mm, depth_mm=depth_mm)))
                    
            # Cantilever Segments Implicit or Explicit? explicit for schedule
            if "left" in dirs: 
                beam_count+=1
                beams.append(StructuralMember(id=f"BC_L_{beam_count}", type="beam",
                    start_point=Point(x=start_x-cant_len, y=y), end_point=Point(x=start_x, y=y),
                    properties=MemberProperties(width_mm=230, depth_mm=450)))
            if "right" in dirs: 
                beam_count+=1
                beams.append(StructuralMember(id=f"BC_R_{beam_count}", type="beam",
                    start_point=Point(x=end_x, y=y), end_point=Point(x=end_x+cant_len, y=y),
                    properties=MemberProperties(width_mm=230, depth_mm=450)))

        # Vertical Beams
        for x in self.x_grid_lines:
            for i in range(len(self.y_grid_lines) - 1):
                y1 = self.y_grid_lines[i]
                y2 = self.y_grid_lines[i+1]
                span_m = abs(y2 - y1)
                depth_mm = max(300.0, math.ceil((span_m * 1000) / 12.0 / 50.0) * 50.0)
                width_mm = 230.0 if depth_mm <= 600 else 300.0
                beam_count += 1
                beams.append(StructuralMember(id=f"B_V_{beam_count}", type="beam",
                    start_point=Point(x=x, y=y1), end_point=Point(x=x, y=y2),
                    properties=MemberProperties(width_mm=width_mm, depth_mm=depth_mm)))
            
            if "bottom" in dirs:
                 beam_count+=1
                 beams.append(StructuralMember(id=f"BC_B_{beam_count}", type="beam",
                    start_point=Point(x=x, y=start_y-cant_len), end_point=Point(x=x, y=start_y),
                    properties=MemberProperties(width_mm=230, depth_mm=450)))
            if "top" in dirs:
                 beam_count+=1
                 beams.append(StructuralMember(id=f"BC_T_{beam_count}", type="beam",
                    start_point=Point(x=x, y=end_y), end_point=Point(x=x, y=end_y+cant_len),
                    properties=MemberProperties(width_mm=230, depth_mm=450)))
                    
        return beams

    def generate_walls(
        self,
        wall_thickness_mm: float = 200.0,
        opening_fraction: float = 0.33,
        include_interior: bool = False,
        beam_depth_mm: float = 400.0,
        slab_thickness_mm: float = 125.0,
    ):
        """Generate Wall objects between adjacent columns.
        
        Creates walls along the building perimeter (exterior walls).
        Optionally creates interior partition walls along all interior beam lines.
        
        Wall clear height = story_height - slab_thickness - beam_depth
        
        Args:
            wall_thickness_mm: Core brick thickness (200mm = full brick, 100mm = half brick).
            opening_fraction: Fraction of wall area deducted for doors/windows (0-0.5).
            include_interior: If True, also create interior partition walls.
            beam_depth_mm: Beam depth for clear height calculation.
            slab_thickness_mm: Slab thickness for clear height calculation.
        """
        self.walls = []
        wall_count = 0
        
        if not self.x_grid_lines or not self.y_grid_lines:
            return
        
        num_x = len(self.x_grid_lines)
        num_y = len(self.y_grid_lines)
        
        # Clear wall height: Hv = Hf - ts - Db
        clear_height = self.story_height_m - (slab_thickness_mm / 1000.0) - (beam_depth_mm / 1000.0)
        clear_height = max(clear_height, 0.5)
        
        # Get level-0 columns for coordinate lookup
        base_cols = [c for c in self.columns if c.level == 0]
        
        def find_col_at(x: float, y: float) -> str:
            """Find column ID nearest to (x, y)."""
            best_id = ""
            best_dist = float('inf')
            for c in base_cols:
                d = math.hypot(c.x - x, c.y - y)
                if d < best_dist:
                    best_dist = d
                    best_id = c.id
            return best_id
        
        # --- Horizontal wall segments (along X axis) ---
        for j, y in enumerate(self.y_grid_lines):
            is_perimeter_y = (j == 0 or j == num_y - 1)
            if not is_perimeter_y and not include_interior:
                continue
            
            for i in range(num_x - 1):
                x1 = self.x_grid_lines[i]
                x2 = self.x_grid_lines[i + 1]
                wall_count += 1
                
                col_s = find_col_at(x1, y)
                col_e = find_col_at(x2, y)
                
                self.walls.append(Wall(
                    id=f"W_H{wall_count}",
                    start_x=x1,
                    start_y=y,
                    end_x=x2,
                    end_y=y,
                    thickness_mm=wall_thickness_mm,
                    height_m=clear_height,
                    material="brick",
                    is_load_bearing=True,
                    opening_fraction=opening_fraction,
                    col_start_id=col_s,
                    col_end_id=col_e,
                    is_exterior=is_perimeter_y,
                ))
        
        # --- Vertical wall segments (along Y axis) ---
        for i, x in enumerate(self.x_grid_lines):
            is_perimeter_x = (i == 0 or i == num_x - 1)
            if not is_perimeter_x and not include_interior:
                continue
            
            for j in range(num_y - 1):
                y1 = self.y_grid_lines[j]
                y2 = self.y_grid_lines[j + 1]
                wall_count += 1
                
                col_s = find_col_at(x, y1)
                col_e = find_col_at(x, y2)
                
                self.walls.append(Wall(
                    id=f"W_V{wall_count}",
                    start_x=x,
                    start_y=y1,
                    end_x=x,
                    end_y=y2,
                    thickness_mm=wall_thickness_mm,
                    height_m=clear_height,
                    material="brick",
                    is_load_bearing=True,
                    opening_fraction=opening_fraction,
                    col_start_id=col_s,
                    col_end_id=col_e,
                    is_exterior=is_perimeter_x,
                ))
        
        logger.info(f"Generated {len(self.walls)} walls (exterior perimeter"
                     f"{' + interior' if include_interior else ''}).")

    # ------------------------------------------------------------------
    # Slab panels (shared by analysis and slab design)
    # ------------------------------------------------------------------
    def slab_panels(self, include_voids: bool = False) -> List[dict]:
        """Rectangular grid bays treated as slab panels.

        A bay is a panel when it is not a void (staircase / void_zones) and
        either all 4 corners carry a level-0 column, or its
        centre is enclosed on all four sides by wall / beam lines (4-ray test on
        ``walls`` + ``boundary_segments``).  The ray test keeps interior bays of
        CAD plans that have no corner columns while leaving the notch of an
        L-shaped plan outside (assumption A-GEO-01).  Each dict: i, j, x0, x1, y0, y1, lx, ly,
        two_way, disc_short, disc_long, neighbours {'left','right','bottom','top'}.
        """
        xs, ys = sorted(self.x_grid_lines), sorted(self.y_grid_lines)
        if len(xs) < 2 or len(ys) < 2:
            return []
        base = {(round(c.x, 2), round(c.y, 2)) for c in self.columns if c.level == 0} or \
               {(round(c.x, 2), round(c.y, 2)) for c in self.columns}
        voids = set() if include_voids else set(tuple(v) for v in (self.void_bays or []))
        segs = [((w.start_x, w.start_y), (w.end_x, w.end_y)) for w in self.walls] + list(self.boundary_segments or [])

        def enclosed(cx, cy):
            if not segs:
                return False
            hit = {"+x": False, "-x": False, "+y": False, "-y": False}
            for (x1, y1), (x2, y2) in segs:
                if min(y1, y2) - 1e-6 <= cy <= max(y1, y2) + 1e-6 and abs(y2 - y1) > 1e-9:
                    xi = x1 + (cy - y1) * (x2 - x1) / (y2 - y1)
                    hit["+x" if xi > cx else "-x"] = True
                if min(x1, x2) - 1e-6 <= cx <= max(x1, x2) + 1e-6 and abs(x2 - x1) > 1e-9:
                    yi = y1 + (cx - x1) * (y2 - y1) / (x2 - x1)
                    hit["+y" if yi > cy else "-y"] = True
            return all(hit.values())

        exists = {}
        for i in range(len(xs) - 1):
            for j in range(len(ys) - 1):
                corners = [(xs[i], ys[j]), (xs[i + 1], ys[j]), (xs[i], ys[j + 1]), (xs[i + 1], ys[j + 1])]
                n = sum((round(x, 2), round(y, 2)) in base for x, y in corners)
                inside = n == 4 or enclosed((xs[i] + xs[i + 1]) / 2.0, (ys[j] + ys[j + 1]) / 2.0)
                exists[(i, j)] = inside and (i, j) not in voids
        panels = []
        for (i, j), ok in exists.items():
            if not ok:
                continue
            sx, sy = xs[i + 1] - xs[i], ys[j + 1] - ys[j]
            if sx <= 1e-6 or sy <= 1e-6:
                continue
            nb = {"left": exists.get((i - 1, j), False), "right": exists.get((i + 1, j), False),
                  "bottom": exists.get((i, j - 1), False), "top": exists.get((i, j + 1), False)}
            # short edges are the edges whose length is lx (the shorter span)
            if sx <= sy:
                lx, ly = sx, sy
                short_edges, long_edges = ("bottom", "top"), ("left", "right")
            else:
                lx, ly = sy, sx
                short_edges, long_edges = ("left", "right"), ("bottom", "top")
            panels.append({
                "i": i, "j": j, "x0": xs[i], "x1": xs[i + 1], "y0": ys[j], "y1": ys[j + 1],
                "lx": lx, "ly": ly, "two_way": ly / lx <= 2.0,
                "disc_short": sum(not nb[e] for e in short_edges),
                "disc_long": sum(not nb[e] for e in long_edges),
                "neighbours": nb,
            })
        return panels

    def panel_slab_thickness_mm(self, panel: dict) -> float:
        """Designed slab thickness for a panel (single rule, finding N13):
        t = max(ceil((lx/26 + c) / 5) x 5, 125, occupancy slab thickness) mm.
        lx/26 is the basic span/effective-depth ratio; c = max(30, slab cover + 10) mm for cover and
        half a bar (project rule; c follows the exposure cover since 2026-10-20)."""
        d_min = panel["lx"] * 1000.0 / 26.0
        c = max(30.0, self.slab_cover_mm + 10.0)
        return max(math.ceil((d_min + c) / 5.0) * 5.0, 125.0, self.slab_thickness_mm)

    def panel_extra_dead_kn_m2(self) -> dict:
        """{(i, j): extra dead load kN/m2} = 25 x (designed - occupancy thickness).
        The recorded dead-load intensities include the occupancy slab
        (``slab_thickness_mm``); this adds the difference for thicker panels."""
        return {(p["i"], p["j"]): 25.0 * (self.panel_slab_thickness_mm(p) - self.slab_thickness_mm) / 1000.0
                for p in self.slab_panels()}

    def footprint_area_m2(self) -> float:
        """Plan area of all framed bays including voids (used for regularity screening)."""
        return sum((p["x1"] - p["x0"]) * (p["y1"] - p["y0"]) for p in self.slab_panels(include_voids=True))

    @staticmethod
    def base_member_id(member_id: str) -> str:
        """Strip the per-level suffix (``B_H_1_L0`` -> ``B_H_1``)."""
        return re.sub(r"_L\d+$", "", member_id)

    def get_beam_result(self, beam_id: str):
        """Beam schedule lookup that accepts per-level ids (audit finding R13)."""
        return self.beam_schedule.get(beam_id) or self.beam_schedule.get(self.base_member_id(beam_id))

    # ------------------------------------------------------------------
    # Member detailing
    # ------------------------------------------------------------------
    def detail_beams(self, beams: List[Any], fck: Optional[float] = None, fy: Optional[float] = None,
                     ductile: bool = False, max_depth_mm: float = 1200.0):
        """Design every plan beam.

        Uses the factored envelope written by ``analysis_integration``
        (``mu_sagging_knm``, ``mu_hogging_knm``, ``vu_kn``).  If a beam has no
        analysis result, a simplified factored UDL is built from the recorded
        load intensities and the beam is flagged WARN.

        Depth starts at max(current depth, span/12 rounded up to 50 mm, 300 mm)
        and is increased in 50 mm steps while the section FAILS (never
        reduced, so repeated analysis/design iterations converge).
        """
        from .rebar_detailer import RebarDetailer
        fck = fck or self.fck
        fy = fy or self.fy
        self.beam_schedule = {}
        avg_x = (self.x_grid_lines[-1] - self.x_grid_lines[0]) / max(1, len(self.x_grid_lines) - 1) if len(self.x_grid_lines) > 1 else 4.0
        avg_y = (self.y_grid_lines[-1] - self.y_grid_lines[0]) / max(1, len(self.y_grid_lines) - 1) if len(self.y_grid_lines) > 1 else 4.0
        for b in beams:
            length_m = math.hypot(b.end_point.x - b.start_point.x, b.end_point.y - b.start_point.y)
            span_depth = max(math.ceil(length_m * 1000.0 / 12.0 / 50.0) * 50.0, 300.0)
            b.properties.depth_mm = max(b.properties.depth_mm, span_depth)
            has_analysis = b.analysis_status != "PENDING" and (b.mu_sagging_knm > 0 or b.mu_hogging_knm > 0)
            is_fallback = b.analysis_status.startswith("FALLBACK")
            while True:
                if b.properties.depth_mm > 750.0 and b.properties.width_mm < 300.0:
                    b.properties.width_mm = 300.0
                if has_analysis:
                    res = RebarDetailer.detail_beam(
                        b.properties.width_mm, b.properties.depth_mm, length_m, fck=fck, fy=fy,
                        mu_sagging_knm=b.mu_sagging_knm, mu_hogging_knm=b.mu_hogging_knm, vu_kn=b.vu_kn,
                        ductile=ductile, governing_combo=b.governing_combo, clear_cover_mm=self.beam_cover_mm)
                    if is_fallback:
                        res.warnings.append(f"Analysis fallback ({b.analysis_status}): simply supported moments on both faces")
                        if res.status == "PASS":
                            res.status = "WARN"
                else:
                    trib = min(avg_x, avg_y)  # half panel each side
                    sw = b.properties.width_mm / 1000.0 * b.properties.depth_mm / 1000.0 * 25.0
                    q = (self.dead_load_kn_m2 + self.live_load_kn_m2) or 8.0
                    wu = 1.5 * (q * trib + sw + (self.fallback_wall_load_kn_m or 0.0))
                    res = RebarDetailer.detail_beam(
                        b.properties.width_mm, b.properties.depth_mm, length_m, fck=fck, fy=fy,
                        mu_sagging_knm=wu * length_m ** 2 / 8.0, mu_hogging_knm=wu * length_m ** 2 / 8.0,
                        vu_kn=wu * length_m / 2.0, ductile=ductile, governing_combo="simplified 1.5(DL+LL)",
                        clear_cover_mm=self.beam_cover_mm)
                    res.warnings.append("No frame analysis result: simplified tributary UDL used (wL^2/8 both faces)")
                    if res.status == "PASS":
                        res.status = "WARN"
                rho = res.provided_steel_area_mm2 / (b.properties.width_mm * b.properties.depth_mm) * 100.0
                failing = res.status == "FAIL" or rho > 2.5
                if failing and b.properties.depth_mm < max_depth_mm:
                    b.properties.depth_mm += 50.0
                    continue
                self.beam_schedule[b.id] = res
                break

    def detail_slabs(self, fck: Optional[float] = None, fy: Optional[float] = None):
        """Design each slab panel with its own thickness, factored load
        1.5 x (slab self-weight + superimposed dead + live) and IS 456
        Table 26 coefficients chosen from the panel's edge continuity."""
        from .rebar_detailer import RebarDetailer
        fck = fck or self.fck
        fy = fy or self.fy
        self.slab_schedule = {}
        sdl = self.superimposed_dead_kn_m2
        ll = self.live_load_kn_m2
        if sdl <= 0 and ll <= 0:
            sdl, ll = 3.0, 2.0   # residential defaults when no intensities were recorded
        count = 0
        for p in self.slab_panels():
            count += 1
            thk = self.panel_slab_thickness_mm(p)
            wu = 1.5 * (25.0 * thk / 1000.0 + sdl + ll)
            res = RebarDetailer.detail_slab(p["x1"] - p["x0"], p["y1"] - p["y0"], slab_thk_mm=thk, fck=fck, fy=fy,
                                           factored_load_kn_m2=wu, disc_short_edges=p["disc_short"],
                                           disc_long_edges=p["disc_long"], clear_cover_mm=self.slab_cover_mm)
            self.slab_schedule[f"S{count}"] = res

    def detail_columns(self, concrete: Concrete, fy: float = 415.0, ductile: bool = False, le_factor: float = 1.0):
        """Design every column segment for all factored combinations written by
        the analysis (``design_forces``); without analysis results the
        1.5(DL+LL) axial load with minimum eccentricity is used."""
        from .rebar_detailer import RebarDetailer
        self.rebar_schedule = {}
        for col in self.columns:
            combos = col.design_forces or [("1.5(DL+LL) axial only", col.load_kn * 1.5, 0.0, 0.0)]
            res = RebarDetailer.detail_column(
                b_mm=col.width_nb, d_mm=col.depth_nb, pu_kn=combos[0][1], concrete=concrete, level=col.level,
                fy=fy, combos=combos, unsupported_length_m=max(col.z_top - col.z_bottom, 0.1) or self.story_height_m,
                le_factor=le_factor, ductile=ductile, column_id=col.id, clear_cover_mm=self.column_cover_mm)
            if not col.design_forces:
                res.warnings.append("No frame analysis result: axial load with minimum eccentricity only")
                if res.status == "PASS":
                    res.status = "WARN"
            self.rebar_schedule[col.id] = res

    def detail_staircase(self, fck: Optional[float] = None, fy: Optional[float] = None, live_load_kn_m2: float = 3.0):
        """Design the typical dog-legged flight for the storey height."""
        from .rebar_detailer import RebarDetailer
        self.staircase_schedule = {
            "ST-1": RebarDetailer.detail_staircase(floor_height_m=self.story_height_m, flight_width_m=1.2,
                                                   fy=fy or self.fy, fck=fck or self.fck, live_load_kn_m2=live_load_kn_m2)
        }
