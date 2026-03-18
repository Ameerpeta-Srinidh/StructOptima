import sys
import os
import plotly.graph_objects as go

# Add root to path (optional, as script is in root)
sys.path.append(os.path.dirname(__file__))

from src.cad_loader import CADLoader
from src.visualizer import Visualizer
from src.materials import Concrete
from src.foundation_eng import design_footing
from main import generate_beams_for_grid

def visualize_autoframing(dxf_path: str, output_html: str):
    print(f"Visualizing Auto-Framing for: {dxf_path}")
    
    # 1. Load & Auto-Frame
    loader = CADLoader(dxf_path)
    # Note: We need to access the parser to get walls later, so we keep loader instance
    gm, beams = loader.load_grid_manager(auto_frame=True)
    
    beams = generate_beams_for_grid(gm) # Generate beams connecting the columns
    
    # 2. Design (Required for Footing Viz and Col Stress Color)
    print("Performing Design Checks...")
    gm.calculate_trib_areas()
    gm.calculate_loads(floor_load_kn_m2=50.0) 
    
    m25 = Concrete.from_grade("M25")
    gm.optimize_column_sizes(concrete=m25)
    
    footings = []
    for col in gm.columns:
        ft = design_footing(
            axial_load_kn=col.load_kn,
            sbc_kn_m2=200.0,
            column_width_mm=col.width_nb,
            column_depth_mm=col.depth_nb,
            concrete=m25
        )
        footings.append(ft)
        
    # 3. Basic Structure Visualization
    viz = Visualizer()
    fig = viz.create_structure_figure(
        grid_mgr=gm,
        beams=beams,
        footings=footings,
        concrete=m25
    )
    
    # 4. Overlay Architectural Walls
    print("Overlaying Architectural Walls...")
    walls = loader.parser.extract_walls()
    
    wall_x = []
    wall_y = []
    wall_z = []
    
    # Scale correction (loader detects scale, but parser returns raw)
    # We need to replicate the scale logic from CADLoader
    # Helper to check scale
    raw_cols = loader.parser.extract_columns() # These are raw
    # Logic from CADLoader:
    xs = [c['x'] for c in raw_cols] if raw_cols else []
    ys = [c['y'] for c in raw_cols] if raw_cols else []
    
    # If raw_cols is empty (auto-framer used generator), checking scale is tricky.
    # AutoFramer returns generated columns which might be scaled? No, AutoFramer consumes parser (raw).
    # Let's peek at the first wall coord
    scale_factor = 1.0
    if walls:
         x1 = walls[0][0][0]
         if x1 > 500: scale_factor = 0.001
    
    for start, end in walls:
        # Draw wall at Z=0 (Ground Plan) and maybe Z=3 (Ceiling Plan)?
        # Let's draw at Z=0 for context
        wx = [start[0]*scale_factor, end[0]*scale_factor, None]
        wy = [start[1]*scale_factor, end[1]*scale_factor, None]
        
        wall_x.extend(wx)
        wall_y.extend(wy)
        wall_z.extend([0, 0, None])
        
    fig.add_trace(go.Scatter3d(
        x=wall_x, y=wall_y, z=wall_z,
        mode='lines',
        line=dict(color='grey', width=2),
        name='Architectural Walls (Base)',
        hoverinfo='skip'
    ))

    # Update Layout
    fig.update_layout(
        title=f"Auto-Framing Result: {os.path.basename(dxf_path)}",
        scene_camera=dict(eye=dict(x=1.5, y=1.5, z=1.5))
    )
    
    fig.write_html(output_html)
    print(f"Visualization saved to: {output_html}")
    
if __name__ == "__main__":
    visualize_autoframing("sample_arch_only.dxf", "auto_frame_viz.html")
