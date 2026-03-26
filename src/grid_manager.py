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

class GridManager(BaseModel):
    width_m: float
    length_m: float
    num_stories: int = 1
    story_height_m: float = 3.0
    max_span_m: float = 6.0
    
    # Cantilever Config (Phase 9)
    cantilever_dirs: List[str] = [] # "top","bottom","left","right"
    cantilever_len_m: float = 1.5
    
    x_grid_lines: List[float] = []
    y_grid_lines: List[float] = []
    columns: List[Column] = []
    footings: List[Any] = [] # Using Any to avoid circular import issues with Footing
    
    # Void Zones for Opening Deductions (List of (x_idx, y_idx) tuples for bays)
    void_zones: List[Tuple[int, int]] = []
    
    # Store detailed rebar info per column ID
    rebar_schedule: dict = {} # {col_id: RebarResult}
    beam_schedule: dict = {} # {beam_id: BeamRebarResult}
    slab_schedule: dict = {} # {slab_id: SlabRebarResult}
    staircase_schedule: dict = {} # {stair_id: StaircaseResult}
    
    def _estimate_initial_column_size(self, col_type: str, trib_area_est: float) -> tuple:
        """Estimate column size based on story count, position, and IS 456 Cl 39.3."""
        fck = 25.0
        fy = 415.0
        floor_load = 12.0  # kN/m2 typical residential
        pu_kn = trib_area_est * floor_load * self.num_stories * 1.5  # Factored
        pu_n = pu_kn * 1000.0
        
        width = 230.0
        depth = 230.0
        while True:
            ag = width * depth
            asc = 0.008 * ag
            ac = ag - asc
            p_cap_n = (0.4 * fck * ac) + (0.67 * fy * asc)
            if p_cap_n >= pu_n:
                break
            width += 50.0
            depth += 50.0
            if width > 1500:
                break
        
        # Min 300mm for seismic zones (IS 13920)
        width = max(width, 300.0)
        depth = max(depth, 300.0)
        # Round to 25mm
        width = math.ceil(width / 25.0) * 25.0
        depth = math.ceil(depth / 25.0) * 25.0
        return width, depth

    def generate_grid(self):
        """Generates uniform grid with multi-story columns."""
        num_bays_x = math.ceil(self.width_m / self.max_span_m)
        num_bays_y = math.ceil(self.length_m / self.max_span_m)
        
        num_bays_x = max(1, num_bays_x)
        num_bays_y = max(1, num_bays_y)
        
        span_x = self.width_m / num_bays_x
        span_y = self.length_m / num_bays_y
        
        self.x_grid_lines = [i * span_x for i in range(num_bays_x + 1)]
        self.y_grid_lines = [j * span_y for j in range(num_bays_y + 1)]
        
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
                    col_type = "edge"
                    fx = span_x / 2 if is_edge_x else span_x
                    fy = span_y / 2 if is_edge_y else span_y
                    trib_est = fx * fy
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
        Wall Load: Added to each level based on beam framing.
        """
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
                    
                wall_load = beam_len * wall_load_kn_m
                total_level_load = level_load + wall_load
                
                # Phase 10: Add Staircase Load if present
                if hasattr(col, 'staircase_add_load'):
                    total_level_load += getattr(col, 'staircase_add_load')
                
                cumulative_load += total_level_load
                col.load_kn = cumulative_load

    def optimize_column_sizes(self, concrete: Concrete, fy: float = 415.0):
        """
        Iterative sizing per column segment based on IS 456:2000 Cl 39.3.
        Pu = 0.4 fck Ac + 0.67 fy Asc
        Assumption: Min steel 0.8% (Asc = 0.008 Ag).
        """
        fck = concrete.fck
        
        for col in self.columns:
            # Factored Load Input? The engine usually works with factored load.
            # Assuming col.load_kn is Pu.
            pu_n = col.load_kn * 1000.0 # Convert kN to N
            
            # Start small, e.g. 230x230 (Min code requirement)
            width = 230.0
            depth = 230.0
            
            while True:
                ag = width * depth
                asc = 0.008 * ag
                ac = ag - asc
                
                # Capacity Check
                p_cap_n = (0.4 * fck * ac) + (0.67 * fy * asc)
                
                if p_cap_n >= pu_n:
                    col.width_nb = width
                    col.depth_nb = depth
                    break
                
                # Increase size in 50mm increments
                width += 50.0
                depth += 50.0
                
                if width > 2000: # Safety break
                    col.width_nb = width
                    col.depth_nb = depth
                    break
                    
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
                sw = 0.23 * (b.properties.depth_mm/1000.0) * (b.properties.width_mm/1000.0) * 25.0 # Corrected SW volume
                # Note: Previous code hardcoded 0.23 width. Now dynamic.
                total_load = 20.0 + sw
                
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
                min_thk = short_span_mm / 26.0
                # Round to 5mm
                thk_mm = math.ceil(min_thk / 5.0) * 5.0
                thk_mm = max(thk_mm, 125.0) # Min 125mm
                
                sid = f"S{count}"
                res = RebarDetailer.detail_slab(lx, ly, slab_thk_mm=thk_mm)
                self.slab_schedule[sid] = res

    def detail_columns(self, concrete: Concrete, fy: float = 415.0):
        """Populate rebar_schedule using RebarDetailer."""
        from .rebar_detailer import RebarDetailer
        self.rebar_schedule = {}
        
        for col in self.columns:
            res = RebarDetailer.detail_column(
                b_mm=col.width_nb,
                d_mm=col.depth_nb,
                pu_kn=col.load_kn,
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

