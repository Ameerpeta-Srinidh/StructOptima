import plotly.graph_objects as go
import numpy as np
import math
from typing import List
from .grid_manager import GridManager, Column
from .foundation_eng import Footing
from .materials import Concrete
from .framing_logic import StructuralMember, Point

class Visualizer:
    def __init__(self):
        pass

    def get_color_by_stress(self, stress_ratio: float) -> str:
        """
        Returns color based on stress calculation.
        Green (0.0) -> Yellow (0.5) -> Red (1.0).
        """
        # Simple traffic light logic or gradients
        ratio = max(0.0, min(1.0, stress_ratio))
        # 0.0 -> Green (0, 255, 0)
        # 0.5 -> Yellow (255, 255, 0)
        # 1.0 -> Red (255, 0, 0)
        
        if ratio <= 0.5:
            # Green to Yellow
            # Ratio 0.0 -> Dark Green (0, 100, 0)
            # Ratio 0.5 -> Yellow (255, 255, 0)
            
            # Simple Linear Interpolation
            # R: 0 -> 255
            # G: 100 -> 255
            factor = ratio / 0.5
            r = int(255 * factor)
            g = int(100 + (155 * factor))
            b = 0
            return f'rgb({r},{g},{b})'
        else:
            # Yellow to Red
            # R: 255, G: 255 -> 0
            r = 255
            g = int(255 * (1.0 - (ratio - 0.5) / 0.5))
            b = 0
            return f'rgb({r},{g},{b})'

    def create_structure_figure(
        self, 
        grid_mgr: GridManager, 
        beams: List[StructuralMember], 
        footings: List[Footing], 
        concrete: Concrete,
        height_m: float = 3.0,
        view_mode: str = "Engineering" # "Engineering" or "Architectural"
    ) -> go.Figure:
        
        fig = go.Figure()
        
        # Design Strength
        fcd = 0.4 * concrete.fck
        
        # View Mode Logic
        # "Engineering": Standard heat map
        # "Architectural": Neutral
        # "Deflection": Exaggerated deformed shape
        # "Utilization": D/C Ratio heat map (same as Engineering but explicit)
        # "Load Path": Highlight load transfer elements

        deflection_scale = 100.0 if view_mode == "Deflection" else 0.0
        
        # 1. Beams (Horizontal Lines)
        num_stories = grid_mgr.num_stories if hasattr(grid_mgr, 'num_stories') else 1
        story_height = grid_mgr.story_height_m if hasattr(grid_mgr, 'story_height_m') else 3.0
        
        beam_x = []
        beam_y = []
        beam_z = []
        beam_hover = []
        beam_colors = []
        
        # Collect beam labels
        beam_labels_x = []
        beam_labels_y = []
        beam_labels_z = []
        beam_labels_text = []

        load_path_highlight_ids = []
        if view_mode == "Load Path":
            # Highlight main transfer beams or heavy beams?
            # For now, all connected beams participating in frame
            pass
        
        for level in range(num_stories):
            z_nominal = (level + 1) * story_height
            
            for beam in beams:
                # Calculate color based on mode
                color = 'darkorange'
                
                # Check utilization for color
                util_ratio = 0.0
                if hasattr(beam, 'analysis_result') and beam.analysis_result:
                     util_ratio = beam.analysis_result.get('usage_ratio', 0.5)
                elif hasattr(beam, 'properties'):
                     # Fake approximation based on length
                     length = ((beam.end_point.x - beam.start_point.x)**2 + (beam.end_point.y - beam.start_point.y)**2)**0.5
                     util_ratio = min(1.0, length / 7.0) # Heuristic for viz if analysis results are missing
                
                if view_mode in ["Engineering", "Utilization"]:
                     color = self.get_color_by_stress(util_ratio)
                elif view_mode == "Architectural":
                     color = 'grey'
                elif view_mode == "Load Path":
                     color = 'blue' # Default gravity
                
                # Calculate Deformed Shape (Parabolic approximation)
                x0, y0 = beam.start_point.x, beam.start_point.y
                x1, y1 = beam.end_point.x, beam.end_point.y
                
                # Base Z
                z0 = z_nominal
                z1 = z_nominal
                
                if view_mode == "Deflection":
                    # Simulate Sag: max at mid-span
                    # delta = L^2/scale * load_factor
                    L = ((x1-x0)**2 + (y1-y0)**2)**0.5
                    mid_sag = (L**2) * 0.002 * deflection_scale * -1 # Downward
                    
                    # Discretize beam into 5 segments for smooth curve
                    steps = 5
                    for i in range(steps):
                        t1 = i / steps
                        t2 = (i+1) / steps
                        
                        bx0 = x0 + (x1-x0)*t1
                        by0 = y0 + (y1-y0)*t1
                        bz0 = z0 + 4*mid_sag*t1*(1-t1) # Parabola
                        
                        bx1 = x0 + (x1-x0)*t2
                        by1 = y0 + (y1-y0)*t2
                        bz1 = z1 + 4*mid_sag*t2*(1-t2)
                        
                        beam_x.extend([bx0, bx1, None])
                        beam_y.extend([by0, by1, None])
                        beam_z.extend([bz0, bz1, None])
                        
                        # Fix Color array for line segments - easier to add seperate traces if colors vary
                        # For single trace, we can't easily vary line color per segment in plotly without line_color array
                        # We will use 'darkorange' global or split traces.
                        # Optimization: Use Mesh3d strip or just simple lines. 
                        # Simple: Just one color per trace.
                else:
                    # Straight Line
                    beam_x.extend([x0, x1, None])
                    beam_y.extend([y0, y1, None])
                    beam_z.extend([z0, z1, None])

                # Hover Text
                beam_id = getattr(beam, 'id', 'Beam')
                hover = f"ID: {beam_id}<br>Util: {util_ratio:.2f}"
                if view_mode == "Deflection":
                     hover += "<br>Deflection: Simulated"
                
                beam_hover.extend([hover, hover, None])
                
                # Label
                if level == 0 and view_mode != "Deflection":
                    mid_x = (x0 + x1) / 2
                    mid_y = (y0 + y1) / 2
                    beam_labels_x.append(mid_x)
                    beam_labels_y.append(mid_y)
                    beam_labels_z.append(z_nominal + 0.3)
                    beam_labels_text.append(beam_id)
            
        # Add Beams Trace
        # ISSUE: We calculated specific colors per beam, but trying to plot as one trace.
        # To support per-element coloring (Utilization), we must group by color OR rely on plotting individual lines (slow).
        # Compromise: For "Utilization", use `scatter3d` with `line=dict(color=array)` if supported, 
        # OR separate traces for High/Med/Low.
        
        # Let's split into 3 buckets for performance if Utilization mode
        if view_mode in ["Engineering", "Utilization"]:
             # Re-loop and group
             traces = {'Low': ([],[],[]), 'Med': ([],[],[]), 'High': ([],[],[])}
             colors = {'Low': 'green', 'Med': 'gold', 'High': 'red'}
             
             for level in range(num_stories):
                z_lev = (level+1) * story_height
                for beam in beams:
                     # Calculate utilization - match logic above line 100
                     u = 0.0
                     if hasattr(beam, 'analysis_result') and beam.analysis_result:
                         u = beam.analysis_result.get('usage_ratio', 0.5)
                     elif hasattr(beam, 'properties'):
                         length = ((beam.end_point.x - beam.start_point.x)**2 + (beam.end_point.y - beam.start_point.y)**2)**0.5
                         u = min(1.0, length / 7.0) # Increased threshold to 7m to match IS code max span better
                     
                     bucket = 'Low' if u < 0.5 else ('Med' if u < 0.9 else 'High')
                     
                     traces[bucket][0].extend([beam.start_point.x, beam.end_point.x, None])
                     traces[bucket][1].extend([beam.start_point.y, beam.end_point.y, None])
                     traces[bucket][2].extend([z_lev, z_lev, None])

             for b in ['Low', 'Med', 'High']:
                 if traces[b][0]:
                     fig.add_trace(go.Scatter3d(
                         x=traces[b][0], y=traces[b][1], z=traces[b][2],
                         mode='lines',
                         line=dict(color=colors[b], width=8),
                         name=f'Beam {b} Stress',
                         hoverinfo='skip'
                     ))
        else:
            # Standard single color trace (Deflection Mode or Architectural)
            line_color = 'darkorange' if view_mode != "Architectural" else 'grey'
            fig.add_trace(go.Scatter3d(
                x=beam_x, y=beam_y, z=beam_z,
                mode='lines',
                line=dict(color=line_color, width=8),
                name='Beams',
                hovertext=beam_hover,
                hoverinfo='text'
            ))

        # Add beam ID labels
        if beam_labels_text:
            fig.add_trace(go.Scatter3d(
                x=beam_labels_x, y=beam_labels_y, z=beam_labels_z,
                mode='text', text=beam_labels_text,
                textfont=dict(size=8, color='darkblue'),
                showlegend=False
            ))
        
        # 2. Columns
        # Apply similar deflection/color logic
        col_x, col_y, col_z = [], [], []
        
        for col in grid_mgr.columns:
            z_b = getattr(col, 'z_bottom', 0)
            z_t = getattr(col, 'z_top', height_m)
            
            # Utilization Color
            load_n = col.load_kn * 1000.0
            stress = load_n / col.area_mm2 if col.area_mm2 > 0 else 0
            ratio = stress / fcd
            
            c_color = 'lightgrey'
            if view_mode in ["Engineering", "Utilization"]:
                 c_color = self.get_color_by_stress(ratio)
                 col_width = 10
            elif view_mode == "Load Path":
                 # Highlight Vertical Load Path
                 if col.level <= 1: # Foundation/Ground columns
                     c_color = 'magenta' # Foundation transfer (Glowing)
                     col_width = 15
                 else:
                     c_color = 'blue'
                     col_width = 5
            else:
                 col_width = 10
                 
            # Deflection: Slight buckling curve? 
            # For simplicity, keep columns straight but color-coded.
            # 3D lines
            fig.add_trace(go.Scatter3d(
                x=[col.x, col.x], y=[col.y, col.y], z=[z_b, z_t],
                mode='lines',
                line=dict(color=c_color, width=col_width),
                name=f'{col.id}',
                showlegend=False,
                hovertext=f"ID: {col.id}<br>Util: {ratio:.2f}"
            ))

        # Animation Frames Logic for Deflection
        if view_mode == "Deflection":
            # Animate Camera Rotation to simulate dynamic inspection
            frames = []
            for k in range(36):
                theta = k * 10 * (3.14159 / 180)
                x_eye = 1.5 * math.cos(theta) - 1.5 * math.sin(theta)
                y_eye = 1.5 * math.sin(theta) + 1.5 * math.cos(theta)
                
                frames.append(go.Frame(layout=dict(scene=dict(camera=dict(eye=dict(x=x_eye, y=y_eye, z=1.5))))))
            
            fig.frames = frames
            
            fig.update_layout(
                updatemenus=[
                    dict(
                        type="buttons",
                        showactive=False,
                        x=0.1, y=0.9,
                        buttons=[dict(
                            label="▶️ Orbit View",
                            method="animate",
                            args=[None, dict(frame=dict(duration=100, redraw=True), fromcurrent=True, mode="immediate")]
                        )]
                    )
                ]
            )

        fig.update_layout(
            scene=dict(
                xaxis_title='Width (m)',
                yaxis_title='Length (m)',
                zaxis_title='Height (m)',
                aspectmode='data'
            ),
            margin=dict(r=0, l=0, b=0, t=0),
            title=f"Structural 3D View - {view_mode} Mode",
            legend=dict(x=0.7, y=0.9),
            # Camera default view
            scene_camera=dict(
                up=dict(x=0, y=0, z=1),
                center=dict(x=0, y=0, z=0),
                eye=dict(x=1.5, y=1.5, z=1.5)
            )
        )
        
        return fig

    def create_2d_plan(
        self,
        grid_mgr: GridManager,
        beams: List[StructuralMember],
        view_mode: str = "Engineering",
        level: int = 1
    ) -> go.Figure:
        """
        Creates a 2D Plan View of the structure at a specific level.
        """
        fig = go.Figure()

        # 1. Draw Grid Lines (Background)
        if hasattr(grid_mgr, 'x_grid_lines'):
            for x in grid_mgr.x_grid_lines:
                fig.add_trace(go.Scatter(
                    x=[x, x], 
                    y=[min(grid_mgr.y_grid_lines), max(grid_mgr.y_grid_lines)],
                    mode='lines',
                    line=dict(color='lightgrey', dash='dash', width=1),
                    hoverinfo='skip',
                    showlegend=False
                ))
        
        if hasattr(grid_mgr, 'y_grid_lines'):
            for y in grid_mgr.y_grid_lines:
                fig.add_trace(go.Scatter(
                    x=[min(grid_mgr.x_grid_lines), max(grid_mgr.x_grid_lines)],
                    y=[y, y],
                    mode='lines',
                    line=dict(color='lightgrey', dash='dash', width=1),
                    hoverinfo='skip',
                    showlegend=False
                ))

        # 2. Draw Columns (Rectangles)
        # Filter columns that exist at this level
        level_cols = [c for c in grid_mgr.columns if getattr(c, 'level', 0) == (level - 1)] 
        # Note: level arg is 1-based (Story 1), col.level is 0-based usually.
        # User usually wants "Story 1" (Ground to 1st Floor).
        # Columns supporting that slab are usually defined as level=0 (Ground->1st)
        
        for col in level_cols:
            # Color logic
            ratio = 0.0
            if col.load_kn > 0 and col.area_mm2 > 0:
                stress = (col.load_kn * 1000) / col.area_mm2
                fcd = 0.4 * 25 # Assume M25 default for color if not passed
                ratio = stress / fcd
                
            color = self.get_color_by_stress(ratio) if view_mode == "Engineering" else 'grey'
            
            # Draw as Shape (Rectangle)
            w_m = col.width_nb / 1000.0
            d_m = col.depth_nb / 1000.0
            
            x0 = col.x - w_m/2
            x1 = col.x + w_m/2
            y0 = col.y - d_m/2
            y1 = col.y + d_m/2
            
            fig.add_shape(
                type="rect",
                x0=x0, y0=y0, x1=x1, y1=y1,
                line=dict(color="black", width=1),
                fillcolor=color,
            )
            
            # Add Annotation for ID
            fig.add_annotation(
                x=col.x, y=col.y,
                text=col.id,
                showarrow=False,
                yshift=10,
                font=dict(size=8, color="black")
            )

        # 3. Draw Beams (Lines)
        # Filter beams
        # Since beams list is generic "StructuralMember", we assume they apply to this floor plan.
        for beam in beams:
            color = 'darkorange' if view_mode == "Engineering" else 'black'
            
            fig.add_trace(go.Scatter(
                x=[beam.start_point.x, beam.end_point.x],
                y=[beam.start_point.y, beam.end_point.y],
                mode='lines',
                line=dict(color=color, width=3),
                name='Beam',
                hovertext=f"Beam {getattr(beam, 'id', '')}<br>{getattr(beam, 'properties', '')}",
                showlegend=False
            ))

        fig.update_layout(
            title=f"2D Structural Plan - Level {level}",
            xaxis_title="Width (m)",
            yaxis_title="Length (m)",
            yaxis=dict(scaleanchor="x", scaleratio=1), # Maintain Aspect Ratio
            plot_bgcolor='white',
            hovermode='closest'
        )
        
        return fig
