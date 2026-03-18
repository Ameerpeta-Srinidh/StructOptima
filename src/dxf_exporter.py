
import ezdxf
from ezdxf import units
from typing import List
from .grid_manager import GridManager, Column
from .framing_logic import StructuralMember
from .logging_config import get_logger

logger = get_logger(__name__)

class StructuralDXFExporter:
    @staticmethod
    def export_structural_dxf(gm: GridManager, beams: List[StructuralMember], filename: str):
        """
        Exports the structural plan (Level 0/1) to a DXF file.
        Layers:
        - S-GRID: Grids (Dashed)
        - S-COL: Columns (Cyan, Rectangles)
        - S-BEAM: Beams (Yellow, Lines)
        - S-TEXT: Labels (White)
        """
        doc = ezdxf.new(dxfversion='R2010')
        doc.units = units.MM
        msp = doc.modelspace()
        
        # Setup Layers
        # ezdxf handles linetypes. 'DASHED' requires loading usually? 
        # Standard: continuous is default. 
        # For dashed, we might need to verify linetype table or just use continuous for now to mimic simple request.
        # User asked for Dashed lines.
        # Check if DASHED exists, else load it.
        if "DASHED" not in doc.linetypes:
            try:
                doc.linetypes.new("DASHED", dxfattribs={"description": "Dashed lines", "pattern": [12.7, -6.35]})
            except Exception as e:
                logger.warning("Could not create DASHED linetype: %s", e)
                pass  # Use default if fail
        
        doc.layers.add("S-GRID", color=252, linetype="DASHED") # Grey/Dashed
        doc.layers.add("S-COL", color=4) # Cyan
        doc.layers.add("S-BEAM", color=2) # Yellow
        doc.layers.add("S-TEXT", color=7) # White
        
        # 1. Grids
        # Draw X lines (Vertical lines at x coords)
        # Bounding box
        min_y = min(gm.y_grid_lines) - 2.0
        max_y = max(gm.y_grid_lines) + 2.0
        min_x = min(gm.x_grid_lines) - 2.0
        max_x = max(gm.x_grid_lines) + 2.0
        
        for x in gm.x_grid_lines:
            msp.add_line((x*1000, min_y*1000), (x*1000, max_y*1000), dxfattribs={'layer': 'S-GRID'})
            # Label
            msp.add_text(f"X={x:.1f}", dxfattribs={'layer': 'S-TEXT', 'height': 200}).set_placement((x*1000, max_y*1000 + 200))
            
        for y in gm.y_grid_lines:
            msp.add_line((min_x*1000, y*1000), (max_x*1000, y*1000), dxfattribs={'layer': 'S-GRID'})
            msp.add_text(f"Y={y:.1f}", dxfattribs={'layer': 'S-TEXT', 'height': 200}).set_placement((min_x*1000 - 600, y*1000))
            
        # 2. Columns
        # Filter Level 0 for Plan
        cols = [c for c in gm.columns if c.level == 0]
        for col in cols:
            cx, cy = col.x * 1000, col.y * 1000
            w, d = col.width_nb, col.depth_nb
            
            # Rect points (Centered)
            p1 = (cx - w/2, cy - d/2)
            p2 = (cx + w/2, cy - d/2)
            p3 = (cx + w/2, cy + d/2)
            p4 = (cx - w/2, cy + d/2)
            
            msp.add_lwpolyline([p1, p2, p3, p4, p1], dxfattribs={'layer': 'S-COL'})
            # Hatch? User didn't ask.
            
            # Label
            msp.add_text(col.id, dxfattribs={'layer': 'S-TEXT', 'height': 150}).set_placement((cx + w/2 + 50, cy))
            
        # 3. Beams
        # Filter for "beams" (These are usually objects. StructuralMember has 2D coords)
        # Use beams passed. Assuming they are generally representing the plan.
        # But if we have duplicates (3 stories), we just want unique plan beams.
        
        # Unique by ID or coords
        seen_beams = set()
        
        for beam in beams:
            # key based on rounded coords
            p_s = (round(beam.start_point.x, 3), round(beam.start_point.y, 3))
            p_e = (round(beam.end_point.x, 3), round(beam.end_point.y, 3))
            
            # Sort to ensure uniqueness regardless of direction
            key = tuple(sorted((p_s, p_e)))
            
            if key in seen_beams: continue
            seen_beams.add(key)
            
            start = (beam.start_point.x * 1000, beam.start_point.y * 1000)
            end = (beam.end_point.x * 1000, beam.end_point.y * 1000)
            
            msp.add_line(start, end, dxfattribs={'layer': 'S-BEAM', 'lineweight': 30})
            
            # Label
            mid = ((start[0]+end[0])/2, (start[1]+end[1])/2)
            if hasattr(beam, 'id'):
                msp.add_text(beam.id, dxfattribs={'layer': 'S-TEXT', 'height': 120}).set_placement((mid[0], mid[1]+100))
        
        doc.saveas(filename)
        logger.info("DXF Exported: %s", filename)
    
    @staticmethod
    def export_floor_dxf(gm: GridManager, beams: List[StructuralMember], level: int, filename: str):
        """
        Exports structural plan for a specific floor level to DXF.
        
        Args:
            gm: GridManager with columns
            beams: List of beam StructuralMember objects
            level: Floor level (0, 1, 2, etc.)
            filename: Output filename
        """
        doc = ezdxf.new(dxfversion='R2010')
        doc.units = units.MM
        msp = doc.modelspace()
        
        # Setup Layers
        if "DASHED" not in doc.linetypes:
            try:
                doc.linetypes.new("DASHED", dxfattribs={"description": "Dashed lines", "pattern": [12.7, -6.35]})
            except Exception as e:
                logger.warning("Could not create DASHED linetype: %s", e)
        
        doc.layers.add("S-GRID", color=252, linetype="DASHED")
        doc.layers.add("S-COL", color=4)
        doc.layers.add("S-BEAM", color=2)
        doc.layers.add("S-TEXT", color=7)
        doc.layers.add("S-TITLE", color=1)
        
        # Title
        title_text = f"STRUCTURAL PLAN - LEVEL {level}"
        msp.add_text(title_text, dxfattribs={'layer': 'S-TITLE', 'height': 400}).set_placement(
            (0, max(gm.y_grid_lines)*1000 + 1500)
        )
        
        # Grids
        min_y = min(gm.y_grid_lines) - 2.0
        max_y = max(gm.y_grid_lines) + 2.0
        min_x = min(gm.x_grid_lines) - 2.0
        max_x = max(gm.x_grid_lines) + 2.0
        
        for x in gm.x_grid_lines:
            msp.add_line((x*1000, min_y*1000), (x*1000, max_y*1000), dxfattribs={'layer': 'S-GRID'})
            msp.add_text(f"X={x:.1f}", dxfattribs={'layer': 'S-TEXT', 'height': 200}).set_placement((x*1000, max_y*1000 + 200))
            
        for y in gm.y_grid_lines:
            msp.add_line((min_x*1000, y*1000), (max_x*1000, y*1000), dxfattribs={'layer': 'S-GRID'})
            msp.add_text(f"Y={y:.1f}", dxfattribs={'layer': 'S-TEXT', 'height': 200}).set_placement((min_x*1000 - 600, y*1000))
        
        # Columns for this level
        cols = [c for c in gm.columns if c.level == level]
        for col in cols:
            cx, cy = col.x * 1000, col.y * 1000
            w, d = col.width_nb, col.depth_nb
            
            p1 = (cx - w/2, cy - d/2)
            p2 = (cx + w/2, cy - d/2)
            p3 = (cx + w/2, cy + d/2)
            p4 = (cx - w/2, cy + d/2)
            
            msp.add_lwpolyline([p1, p2, p3, p4, p1], dxfattribs={'layer': 'S-COL'})
            
            # Label with size
            label = f"{col.id}\\n{int(col.width_nb)}x{int(col.depth_nb)}"
            msp.add_text(col.id, dxfattribs={'layer': 'S-TEXT', 'height': 150}).set_placement((cx + w/2 + 50, cy))
        
        # Beams (unique only)
        seen_beams = set()
        for beam in beams:
            p_s = (round(beam.start_point.x, 3), round(beam.start_point.y, 3))
            p_e = (round(beam.end_point.x, 3), round(beam.end_point.y, 3))
            key = tuple(sorted((p_s, p_e)))
            
            if key in seen_beams:
                continue
            seen_beams.add(key)
            
            start = (beam.start_point.x * 1000, beam.start_point.y * 1000)
            end = (beam.end_point.x * 1000, beam.end_point.y * 1000)
            
            msp.add_line(start, end, dxfattribs={'layer': 'S-BEAM', 'lineweight': 30})
            
            mid = ((start[0]+end[0])/2, (start[1]+end[1])/2)
            if hasattr(beam, 'id'):
                msp.add_text(beam.id, dxfattribs={'layer': 'S-TEXT', 'height': 120}).set_placement((mid[0], mid[1]+100))
        
        doc.saveas(filename)
        logger.info("DXF Exported for Level %d: %s", level, filename)
