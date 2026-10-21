import plotly.graph_objects as go
import numpy as np
import math
from typing import List, Tuple, Optional
from .grid_manager import GridManager, Column
from .foundation_eng import Footing
from .materials import Concrete
from .framing_logic import StructuralMember, Point
from .rebar_detailer import format_interaction_ratio

def beam_utilisation(grid_mgr, beam_id: str):
    """(utilisation, status) of a designed beam: max of Ast,req / Ast,prov (top,
    bottom) and tau_v / tau_c,max; FAIL counts as >= 1.  (0.0, "") if not designed."""
    r = grid_mgr.get_beam_result(beam_id) if hasattr(grid_mgr, 'get_beam_result') else None
    if r is None:
        return 0.0, ""
    vals = []
    if r.ast_bottom_prov_mm2 > 0:
        vals.append(r.ast_bottom_req_mm2 / r.ast_bottom_prov_mm2)
    if r.ast_top_prov_mm2 > 0:
        vals.append(r.ast_top_req_mm2 / r.ast_top_prov_mm2)
    if r.tau_c_max_Nmm2 > 0:
        vals.append(r.tau_v_Nmm2 / r.tau_c_max_Nmm2)
    u = max(vals, default=0.0)
    if r.status == "FAIL":
        u = max(u, 1.0)
    return (0.0 if math.isnan(u) else u), r.status


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
        view_mode: str = "Engineering", # "Engineering" or "Architectural"
        arch_walls: Optional[List[Tuple[Tuple[float, float], Tuple[float, float]]]] = None
    ) -> go.Figure:
        
        try:
            fig = go.Figure()
            
        
            # View Mode Logic
            # "Engineering": Standard heat map
            # "Architectural": Neutral
            # "Utilization": D/C Ratio heat map (same as Engineering but explicit)
            # "Load Path": Highlight load transfer elements

        
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
                
                    # Utilisation from the beam design (N22): largest of required / provided
                    # steel (top, bottom) and tau_v / tau_c,max; a FAIL status shows red
                    util_ratio, b_status = beam_utilisation(grid_mgr, beam.id)

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
                
                    beam_x.extend([x0, x1, None])
                    beam_y.extend([y0, y1, None])
                    beam_z.extend([z0, z1, None])

                    # Hover Text
                    beam_id = getattr(beam, 'id', 'Beam')
                    hover = (f"ID: {beam_id}<br>Utilisation: {util_ratio:.2f}<br>Status: {b_status}"
                             if b_status else f"ID: {beam_id}<br>Not designed")
                
                    beam_hover.extend([hover, hover, None])
                
                    # Label
                    if level == 0:
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
                # Standard single colour trace (Architectural / Load Path)
                line_color = 'darkorange' if view_mode != "Architectural" else 'grey'
            
                # Filter None from hovertext to avoid Plotly JSON serialization issues in some versions
                clean_hover = [h if h is not None else "" for h in beam_hover]
            
                fig.add_trace(go.Scatter3d(
                    x=beam_x, y=beam_y, z=beam_z,
                    mode='lines',
                    line=dict(color=line_color, width=8),
                    name='Beams',
                    hovertext=clean_hover,
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
            
            # 1.5 Draw Architectural Trace Layers at Z=-0.05
            if arch_walls:
                w_x, w_y, w_z = [], [], []
                for (p1, p2) in arch_walls:
                    w_x.extend([p1[0], p2[0], None])
                    w_y.extend([p1[1], p2[1], None])
                    w_z.extend([-0.05, -0.05, None])
                
                fig.add_trace(go.Scatter3d(
                    x=w_x, y=w_y, z=w_z,
                    mode='lines',
                    line=dict(color='rgba(100, 149, 237, 0.4)', width=3), # Cornflower blue, transparent
                    name='Architectural Trace',
                    hoverinfo='skip',
                    showlegend=True
                ))
        
            # 2. Columns
            # Apply similar deflection/color logic
            col_x, col_y, col_z = [], [], []
        
            for col in grid_mgr.columns:
                z_b = getattr(col, 'z_bottom', 0)
                z_t = getattr(col, 'z_top', height_m)
            
                # Utilisation = P-M interaction ratio from the column design (N22)
                _cr = getattr(grid_mgr, 'rebar_schedule', {}).get(col.id)
                ratio = float(_cr.interaction_ratio) if _cr is not None else 0.0
                if _cr is not None and _cr.status == "FAIL":
                    ratio = max(ratio, 1.0)
            
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
                 
                # 3D lines
                fig.add_trace(go.Scatter3d(
                    x=[col.x, col.x], y=[col.y, col.y], z=[z_b, z_t],
                    mode='lines',
                    line=dict(color=c_color, width=col_width),
                    name=f'{col.id}',
                    showlegend=False,
                    hovertext=(f"ID: {col.id}<br>Interaction ratio: {format_interaction_ratio(_cr.interaction_ratio)}<br>Status: {_cr.status}"
                               if _cr is not None else f"ID: {col.id}<br>Not designed")
                ))

            
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
        except Exception as e:
            import traceback
            err_msg = traceback.format_exc()
            err_fig = go.Figure()
            err_fig.add_annotation(
                text=f"Visualizer Error: {str(e)}<br>{err_msg.replace(chr(10), '<br>')}",
                xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
                font=dict(color="red", size=10)
            )
            return err_fig

    def create_2d_plan(
        self,
        grid_mgr: GridManager,
        beams: List[StructuralMember],
        view_mode: str = "Engineering",
        level: int = 1,
        arch_walls: Optional[List[Tuple[Tuple[float, float], Tuple[float, float]]]] = None
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
        
        if hasattr(grid_mgr, 'y_grid_lines') and grid_mgr.y_grid_lines:
            for y in grid_mgr.y_grid_lines:
                fig.add_trace(go.Scatter(
                    x=[min(grid_mgr.x_grid_lines), max(grid_mgr.x_grid_lines)],
                    y=[y, y],
                    mode='lines',
                    line=dict(color='lightgrey', dash='dash', width=1),
                    hoverinfo='skip',
                    showlegend=False
                ))

        # Add Engineering Dimensions
        if hasattr(grid_mgr, 'x_grid_lines') and len(grid_mgr.x_grid_lines) > 1:
            x_grids = sorted(grid_mgr.x_grid_lines)
            y_dim = min(grid_mgr.y_grid_lines) - 1.5 # offset below
            for i in range(len(x_grids)-1):
                x_start = x_grids[i]
                x_end = x_grids[i+1]
                mid_x = (x_start + x_end) / 2
                dist = x_end - x_start
                if dist > 0.1:
                    fig.add_trace(go.Scatter(x=[x_start, x_end], y=[y_dim, y_dim], mode='lines+markers', marker=dict(symbol='line-ns', size=10), line=dict(color='black', width=1), showlegend=False))
                    fig.add_annotation(x=mid_x, y=y_dim-0.5, text=f"{dist:.2f}m", showarrow=False, font=dict(size=10, color="black"))

        if hasattr(grid_mgr, 'y_grid_lines') and len(grid_mgr.y_grid_lines) > 1:
            y_grids = sorted(grid_mgr.y_grid_lines)
            x_dim = min(grid_mgr.x_grid_lines) - 1.5 # offset left
            for i in range(len(y_grids)-1):
                y_start = y_grids[i]
                y_end = y_grids[i+1]
                mid_y = (y_start + y_end) / 2
                dist = y_end - y_start
                if dist > 0.1:
                    fig.add_trace(go.Scatter(x=[x_dim, x_dim], y=[y_start, y_end], mode='lines+markers', marker=dict(symbol='line-ew', size=10), line=dict(color='black', width=1), showlegend=False))
                    fig.add_annotation(x=x_dim-0.5, y=mid_y, text=f"{dist:.2f}m", textangle=-90, showarrow=False, font=dict(size=10, color="black"))

        # 1.5 Draw Architectural Traces / Masonry Walls
        if hasattr(grid_mgr, 'walls') and grid_mgr.walls:
            w_x, w_y = [], []
            for w in grid_mgr.walls:
                w_x.extend([w.start_x, w.end_x, None])
                w_y.extend([w.start_y, w.end_y, None])
            fig.add_trace(go.Scatter(
                x=w_x, y=w_y,
                mode='lines',
                line=dict(color='rgba(210, 105, 30, 0.8)', width=4, dash='solid'),
                name='Masonry Walls',
                hoverinfo='text',
                hovertext='Brick Wall',
                showlegend=True
            ))
        elif arch_walls and level == 1: # Usually we show foundation trace primarily
            w_x, w_y = [], []
            for (p1, p2) in arch_walls:
                w_x.extend([p1[0], p2[0], None])
                w_y.extend([p1[1], p2[1], None])
                
            fig.add_trace(go.Scatter(
                x=w_x, y=w_y,
                mode='lines',
                line=dict(color='rgba(100, 149, 237, 0.5)', width=2, dash='solid'),
                name='Architectural Blueprint',
                hoverinfo='skip',
                showlegend=True
            ))

        # 2. Draw Columns (Rectangles)
        # Filter columns that exist at this level
        level_cols = [c for c in grid_mgr.columns if getattr(c, 'level', 0) == (level - 1)] 
        # Note: level arg is 1-based (Story 1), col.level is 0-based usually.
        # User usually wants "Story 1" (Ground to 1st Floor).
        # Columns supporting that slab are usually defined as level=0 (Ground->1st)
        
        for col in level_cols:
            # Color logic
            # P-M interaction ratio from the column design (N22); FAIL shows red
            _cr = getattr(grid_mgr, 'rebar_schedule', {}).get(col.id)
            ratio = float(_cr.interaction_ratio) if _cr is not None else 0.0
            if _cr is not None and _cr.status == "FAIL":
                ratio = max(ratio, 1.0)
                
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
