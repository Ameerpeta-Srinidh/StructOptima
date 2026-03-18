import math
from typing import List, Tuple, Literal, Optional
from pydantic import BaseModel, Field

# Using simple geometry classes/models 

class Point(BaseModel):
    x: float
    y: float
    
    def __hash__(self):
        return hash((self.x, self.y))
    
    def __eq__(self, other):
        return (self.x, self.y) == (other.x, other.y)

class MemberProperties(BaseModel):
    width_mm: float
    depth_mm: float
    
    @property
    def label(self) -> str:
        return f"{int(self.width_mm)}x{int(self.depth_mm)}"

class StructuralMember(BaseModel):
    id: str
    type: Literal["column", "beam"]
    start_point: Point
    end_point: Optional[Point] = None # Beam has end_point, Column is point location (start_point)
    properties: MemberProperties
    load_kn: float = 0.0 # Axial load for column, Distributed load for beam (simplification)
    tributary_area_m2: float = 0.0 # For columns
    
    # Analysis Results (Phase 16 - FEA)
    design_moment_knm: float = 0.0
    design_shear_kn: float = 0.0
    analysis_status: str = "PENDING"

class GridSystem(BaseModel):
    width_m: float
    length_m: float
    max_span_m: float = 6.0
    x_grid_lines: List[float] = []
    y_grid_lines: List[float] = []
    columns: List[StructuralMember] = []
    beams: List[StructuralMember] = []
    
    def generate_grid(self):
        """Generates grid lines based on max allowable span."""
        # Calculate number of bays
        num_bays_x = math.ceil(self.width_m / self.max_span_m)
        num_bays_y = math.ceil(self.length_m / self.max_span_m)
        
        # Ensure at least 1 bay (2 grid lines)
        num_bays_x = max(1, num_bays_x)
        num_bays_y = max(1, num_bays_y)
        
        span_x = self.width_m / num_bays_x
        span_y = self.length_m / num_bays_y
        
        self.x_grid_lines = [i * span_x for i in range(num_bays_x + 1)]
        self.y_grid_lines = [j * span_y for j in range(num_bays_y + 1)]
        
    def place_members(self):
        """Places columns at intersections and beams between them."""
        self.columns = []
        self.beams = []
        col_count = 0
        beam_count = 0
        
        # Place Columns
        for x in self.x_grid_lines:
            for y in self.y_grid_lines:
                col_count += 1
                # Default size 300x300 initially
                self.columns.append(StructuralMember(
                    id=f"C{col_count}",
                    type="column",
                    start_point=Point(x=x, y=y),
                    properties=MemberProperties(width_mm=300, depth_mm=300)
                ))
        
        # Place Beams (Horizontal)
        # Connect (x_i, y_j) to (x_i+1, y_j)
        for j, y in enumerate(self.y_grid_lines):
            for i in range(len(self.x_grid_lines) - 1):
                x1 = self.x_grid_lines[i]
                x2 = self.x_grid_lines[i+1]
                beam_count += 1
                self.beams.append(StructuralMember(
                    id=f"B_H_{beam_count}",
                    type="beam",
                    start_point=Point(x=x1, y=y),
                    end_point=Point(x=x2, y=y),
                    properties=MemberProperties(width_mm=300, depth_mm=600) # Default beam size
                ))
                
        # Place Beams (Vertical)
        # Connect (x_i, y_j) to (x_i, y_j+1)
        for i, x in enumerate(self.x_grid_lines):
            for j in range(len(self.y_grid_lines) - 1):
                y1 = self.y_grid_lines[j]
                y2 = self.y_grid_lines[j+1]
                beam_count += 1
                self.beams.append(StructuralMember(
                    id=f"B_V_{beam_count}",
                    type="beam",
                    start_point=Point(x=x, y=y1),
                    end_point=Point(x=x, y=y2),
                    properties=MemberProperties(width_mm=300, depth_mm=600)
                ))

    def calculate_tributary_loads(self, floor_load_kn_m2: float = 12.0):
        """
        Calculates tributary area for each column and corresponding load.
        Trib Area approx = (LeftSpan/2 + RightSpan/2) * (BotSpan/2 + TopSpan/2)
        """
        if not self.x_grid_lines or not self.y_grid_lines:
            return
            
        span_x = self.x_grid_lines[1] - self.x_grid_lines[0] # Uniform grid assumed
        span_y = self.y_grid_lines[1] - self.y_grid_lines[0]
        
        x_min, x_max = min(self.x_grid_lines), max(self.x_grid_lines)
        y_min, y_max = min(self.y_grid_lines), max(self.y_grid_lines)
        
        for col in self.columns:
            x, y = col.start_point.x, col.start_point.y
            
            # Determine Trib Width X
            if x == x_min or x == x_max:
                factor_x = 0.5 # Edge/Corner
            else:
                factor_x = 1.0 # Interior
            
            # Determine Trib Width Y
            if y == y_min or y == y_max:
                factor_y = 0.5
            else:
                factor_y = 1.0
                
            trib_area = (factor_x * span_x) * (factor_y * span_y)
            load = trib_area * floor_load_kn_m2
            
            col.tributary_area_m2 = trib_area
            col.load_kn = load
            
    def preliminary_sizing(self):
        """
        Sizing logic:
        If Load > 1500 kN -> 400x400
        Else -> 300x300
        """
        for col in self.columns:
            if col.load_kn > 1500:
                col.properties = MemberProperties(width_mm=400, depth_mm=400)
            else:
                col.properties = MemberProperties(width_mm=300, depth_mm=300)

    def get_visualization_data(self):
        """Returns simplified list for map."""
        cols = [(c.start_point.x, c.start_point.y, c.properties.label) for c in self.columns]
        beams = [((b.start_point.x, b.start_point.y), (b.end_point.x, b.end_point.y)) for b in self.beams]
        return cols, beams
