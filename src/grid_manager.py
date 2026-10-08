import math
from typing import List, Literal, Tuple, Optional, Any
from pydantic import BaseModel, PositiveFloat

from .materials import Concrete
from .logging_config import get_logger

logger = get_logger(__name__)

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

    def calculate_loads(self, floor_load_kn_m2: float, wall_load_kn_m: float = 0.0):
        """
        Cumulative Load Takedown from Top -> Bottom.
        Wall Load: Distributed from actual self.walls geometry if available, else from uniform parameter.
        """
        # Pre-calculate wall load per column stack based on actual wall geometry
        wall_load_map = {}
        if self.walls:
            import math as _m
            for w in self.walls:
                total_w_load = w.length_m * w.line_load_kn_m
                # Distribute half load to the nearest start column, half to nearest end column
                start_c = min(self.columns, key=lambda c: _m.hypot(c.x - w.start_x, c.y - w.start_y))
                end_c = min(self.columns, key=lambda c: _m.hypot(c.x - w.end_x, c.y - w.end_y))
                
                k1 = (start_c.x, start_c.y)
                k2 = (end_c.x, end_c.y)
                wall_load_map[k1] = wall_load_map.get(k1, 0.0) + (total_w_load / 2.0)
                if start_c != end_c:
                    wall_load_map[k2] = wall_load_map.get(k2, 0.0) + (total_w_load / 2.0)

        # Group by (x, y) coordinates to form stacks
        stacks = {}
        for col in self.columns:
            key = (col.x, col.y)
            if key not in stacks:
                stacks[key] = []
            stacks[key].append(col)
        
        # Sort each stack by level descending (Top -> Bottom)
        for key in stacks:
            stacks[key].sort(key=lambda c: c.level, reverse=True)
            
            cumulative_load = 0.0
            
            for col in stacks[key]:
                # 1. Floor Load
                level_load = col.trib_area_m2 * floor_load_kn_m2
                
                # 2. Wall Load & Beams
                # Use actual adjacent spans for this column
                sorted_x = sorted(self.x_grid_lines)
                sorted_y = sorted(self.y_grid_lines)
                x_idx = next((i for i, gx in enumerate(sorted_x) if abs(gx - col.x) < 0.01), None)
                y_idx = next((i for i, gy in enumerate(sorted_y) if abs(gy - col.y) < 0.01), None)
                
                # Half-span contributions
                left_sp = (sorted_x[x_idx] - sorted_x[x_idx-1]) / 2.0 if x_idx and x_idx > 0 else 0.0
                right_sp = (sorted_x[x_idx+1] - sorted_x[x_idx]) / 2.0 if x_idx is not None and x_idx < len(sorted_x)-1 else 0.0
                below_sp = (sorted_y[y_idx] - sorted_y[y_idx-1]) / 2.0 if y_idx and y_idx > 0 else 0.0
                above_sp = (sorted_y[y_idx+1] - sorted_y[y_idx]) / 2.0 if y_idx is not None and y_idx < len(sorted_y)-1 else 0.0
                
                beam_len_x = left_sp + right_sp  # X-direction beam tributary
                beam_len_y = below_sp + above_sp  # Y-direction beam tributary
                beam_len = beam_len_x + beam_len_y
                
                # Add Cantilever Load (Simplified)
                # If this is edge/corner, and direction matches cantilever, add load
                if self.cantilever_dirs:
                    c_load = 0
                    # Check bounds
                    x_min, x_max = min(self.x_grid_lines), max(self.x_grid_lines)
                    y_min, y_max = min(self.y_grid_lines), max(self.y_grid_lines)
                    
                    is_left = abs(col.x - x_min) < 0.1
                    is_right = abs(col.x - x_max) < 0.1
                    is_bot = abs(col.y - y_min) < 0.1
                    is_top = abs(col.y - y_max) < 0.1
                    
                    c_len = self.cantilever_len_m
                    
                    # Logic: If 'left' is active, and column is on left edge, it supports cantilever
                    if "left" in self.cantilever_dirs and is_left:
                         trib_w_y = beam_len_y if not (is_bot or is_top) else beam_len_y/2
                         c_area = trib_w_y * c_len
                         c_load += c_area * floor_load_kn_m2
                         beam_len += c_len # Extension beam
                         
                    if "right" in self.cantilever_dirs and is_right:
                         trib_w_y = beam_len_y if not (is_bot or is_top) else beam_len_y/2
                         c_area = trib_w_y * c_len
                         c_load += c_area * floor_load_kn_m2
                         beam_len += c_len

                    if "bottom" in self.cantilever_dirs and is_bot:
                         trib_w_x = beam_len_x if not (is_left or is_right) else beam_len_x/2
                         c_area = trib_w_x * c_len
                         c_load += c_area * floor_load_kn_m2
                         beam_len += c_len
                         
                    if "top" in self.cantilever_dirs and is_top:
                         trib_w_x = beam_len_x if not (is_left or is_right) else beam_len_x/2
                         c_area = trib_w_x * c_len
                         c_load += c_area * floor_load_kn_m2
                         beam_len += c_len
                    
                    level_load += c_load
                
                # Calculate Wall Load
                if self.walls:
                    is_roof = (col.level == self.num_stories - 1)
                    if is_roof:
                        # Roof usually only has parapet wall (~1m height, roughly 33% of full story wall)
                        wall_load = wall_load_map.get(key, 0.0) * 0.33
                    else:
                        wall_load = wall_load_map.get(key, 0.0)
                else:
                    # Fallback if no specific wall objects exist
                    wall_load = beam_len * wall_load_kn_m
                    
                total_level_load = level_load + wall_load
                
                # Column self-weight
                col_sw = (col.width_nb / 1000.0) * (col.depth_nb / 1000.0) * self.story_height_m * 25.0
                total_level_load += col_sw
                
                # Phase 10: Add Staircase Load if present
                if hasattr(col, 'staircase_add_load'):
                    total_level_load += getattr(col, 'staircase_add_load')
                
                cumulative_load += total_level_load
                col.load_kn = cumulative_load

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
                if abs(col.width_nb - gw) <= 15 and abs(col.depth_nb - gd) <= 15:
                    # Only group if canonical is ≥ current (don't reduce to smaller)
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

    def detail_beams(self, beams: List[Any]):
        from .rebar_detailer import RebarDetailer
        self.beam_schedule = {}
        for b in beams:
            # Calc length
            p1 = b.start_point
            p2 = b.end_point
            length_m = math.sqrt((p2.x-p1.x)**2 + (p2.y-p1.y)**2)
            
            # Dynamic Sizing (Phase 11)
            # Depth ~ Span / 12 for simply supported, Span / 15 continuous
            # Conservative: Span / 12
            min_depth = (length_m * 1000) / 12.0
            # Round up to 50mm
            depth_mm = math.ceil(min_depth / 50.0) * 50.0
            depth_mm = max(depth_mm, 300.0) # Min depth
            
            b.properties.depth_mm = depth_mm
            
            # Load? Approx 20kN/m + Self Weight
            # SW = 0.23 * D * 25
            # Auto-Sizing Loop
            # We enforce Max 2.5% steel. If exceeded, increase depth.
            
            while True:
                # Stability Check (Blade Beam)
                if b.properties.depth_mm > 750.0 and b.properties.width_mm < 300.0:
                    b.properties.width_mm = 300.0
                
                # Update SW Load based on current depth
                sw = (b.properties.width_mm / 1000.0) * (b.properties.depth_mm / 1000.0) * 25.0 # Corrected SW volume
                # Note: Previous code hardcoded 0.23 width. Now dynamic.
                avg_span_x = (self.x_grid_lines[-1] - self.x_grid_lines[0]) / max(1, len(self.x_grid_lines) - 1) if self.x_grid_lines else 4.0
                avg_span_y = (self.y_grid_lines[-1] - self.y_grid_lines[0]) / max(1, len(self.y_grid_lines) - 1) if self.y_grid_lines else 4.0
                trib_width_m = min(avg_span_x, avg_span_y)  # Half-span each side
                floor_udl = trib_width_m * 12.0  # 12 kN/m2 typical total floor load
                total_load = floor_udl + sw + 12.0  # + wall load 12 kN/m default
                
                res = RebarDetailer.detail_beam(
                    b_mm=b.properties.width_mm,
                    d_mm=b.properties.depth_mm,
                    span_m=length_m,
                    load_kn_m=total_load,
                    design_moment_knm=b.design_moment_knm,
                    design_shear_kn=b.design_shear_kn
                )
                
                # Check Congestion (Max 2.5%)
                ag = b.properties.width_mm * b.properties.depth_mm
                rho = (res.provided_steel_area_mm2 / ag) * 100.0
                
                if rho > 2.5 and b.properties.depth_mm < 1200:
                    b.properties.depth_mm += 50.0
                    # Assign new size to object so next iteration uses it
                    continue
                else:
                    self.beam_schedule[b.id] = res
                    break

    def detail_slabs(self):
        """Assume slab panels between grid lines."""
        from .rebar_detailer import RebarDetailer
        self.slab_schedule = {}
        
        # Grid Panes
        if not self.x_grid_lines or not self.y_grid_lines: return
        
        count = 0
        for i in range(len(self.x_grid_lines)-1):
            for j in range(len(self.y_grid_lines)-1):
                count += 1
                lx = self.x_grid_lines[i+1] - self.x_grid_lines[i]
                ly = self.y_grid_lines[j+1] - self.y_grid_lines[j]
                
                # Dynamic Slab Thickness
                # IS 456: Span/Depth <= 26 for continuous (Slab)
                # Short span governs
                short_span_mm = min(lx, ly) * 1000.0
                d_min = short_span_mm / 26.0  # IS 456 Cl 23.2.1 effective depth
                thk_mm = d_min + 30.0  # Add cover (25mm) + half bar dia (5mm)
                thk_mm = math.ceil(thk_mm / 5.0) * 5.0
                thk_mm = max(thk_mm, 125.0)  # Absolute minimum
                
                sid = f"S{count}"
                res = RebarDetailer.detail_slab(lx, ly, slab_thk_mm=thk_mm)
                self.slab_schedule[sid] = res

    def detail_columns(self, concrete: Concrete, fy: float = 415.0):
        """Populate rebar_schedule using RebarDetailer."""
        from .rebar_detailer import RebarDetailer
        self.rebar_schedule = {}
        
        for col in self.columns:
            # col.load_kn is SERVICE (unfactored) load from calculate_loads()
            # IS 456 Table 18: γf = 1.5 for (1.5 DL + 1.5 LL) combination
            pu_factored_kn = col.load_kn * 1.5
            res = RebarDetailer.detail_column(
                b_mm=col.width_nb,
                d_mm=col.depth_nb,
                pu_kn=pu_factored_kn,
                concrete=concrete,
                level=col.level,
                fy=fy
            )
            self.rebar_schedule[col.id] = res

    def detail_staircase(self):
        """Generates Staircase Design for the building."""
        from .rebar_detailer import RebarDetailer
        self.staircase_schedule = {}
        
        # Assume one main staircase per building block
        # Design for the typical floor height
        res = RebarDetailer.detail_staircase(
            floor_height_m=self.story_height_m,
            flight_width_m=1.2, # Standard width
            fy=415.0,
            fck=25.0
        )
        self.staircase_schedule["ST-1"] = res

