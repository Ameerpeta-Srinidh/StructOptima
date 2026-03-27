
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


class ProfessionalDXFExporter:
    """
    Exports high-fidelity 2D structural plans (Foundation, Framing)
    matching standard IS-code/architectural drafting styles.
    """
    def __init__(self, grid_manager: GridManager, beams: List[StructuralMember], design_data: dict, drawing_type: str = "FOUNDATION"):
        self.gm = grid_manager
        self.beams = beams
        self.design = design_data
        self.type = drawing_type
        
        self.doc = ezdxf.new(dxfversion='R2010')
        self.doc.units = units.MM
        self.msp = self.doc.modelspace()
        self._setup_document()
        
    def export(self, filepath: str) -> str:
        self._draw_grid()
        self._draw_footings()
        self._draw_columns()
        self._draw_beams()
        self._draw_dimensions()
        
        if self.type == "FOUNDATION":
            self._draw_slab_annotation()
            self._draw_stairs()
            
        self._draw_north_arrow()
        self._draw_scale_bar()
        self._draw_title_block()
        
        self.doc.saveas(filepath)
        logger.info("Professional DXF Exported: %s", filepath)
        return filepath

    def _setup_document(self):
        if "DASHED" not in self.doc.linetypes:
            self.doc.linetypes.new("DASHED", dxfattribs={"description": "Dashed lines", "pattern": [15.0, -5.0]})
            
        # Standard layer setup per requirements
        self.doc.layers.add("GRID", color=8, linetype="CONTINUOUS", lineweight=18)
        self.doc.layers.add("GRID_BUBBLE", color=8, linetype="CONTINUOUS", lineweight=25)
        self.doc.layers.add("DIMENSIONS", color=2, linetype="CONTINUOUS", lineweight=18)
        self.doc.layers.add("COLUMNS", color=1, linetype="CONTINUOUS", lineweight=50)
        self.doc.layers.add("BEAMS", color=3, linetype="DASHED", lineweight=35)
        self.doc.layers.add("FOOTINGS", color=5, linetype="DASHED", lineweight=25)
        self.doc.layers.add("SLAB_HATCH", color=8, linetype="CONTINUOUS", lineweight=13)
        self.doc.layers.add("SLAB_NOTES", color=7, linetype="CONTINUOUS", lineweight=18)
        self.doc.layers.add("STAIRS", color=6, linetype="CONTINUOUS", lineweight=25)
        self.doc.layers.add("TITLE_BLOCK", color=7, linetype="CONTINUOUS", lineweight=50)
        self.doc.layers.add("NORTH_ARROW", color=7, linetype="CONTINUOUS", lineweight=25)
        self.doc.layers.add("SCALE_BAR", color=7, linetype="CONTINUOUS", lineweight=18)

    def _draw_grid(self):
        ext = 1200.0  
        bubble_r = 200.0
        
        # Vertical grid lines (X geometry, Label 1, 2, 3...)
        min_y = (min(self.gm.y_grid_lines) if self.gm.y_grid_lines else 0) * 1000 - ext
        max_y = (max(self.gm.y_grid_lines) if self.gm.y_grid_lines else 0) * 1000 + ext
        
        for i, x_m in enumerate(self.gm.x_grid_lines):
            x = x_m * 1000
            self.msp.add_line((x, min_y), (x, max_y), dxfattribs={'layer': 'GRID'})
            self.msp.add_circle((x, max_y + bubble_r), bubble_r, dxfattribs={'layer': 'GRID_BUBBLE'})
            self.msp.add_text(str(i+1), dxfattribs={'layer': 'GRID_BUBBLE', 'height': 150}).set_placement(
                (x, max_y + bubble_r), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
            self.msp.add_circle((x, min_y - bubble_r), bubble_r, dxfattribs={'layer': 'GRID_BUBBLE'})
            self.msp.add_text(str(i+1), dxfattribs={'layer': 'GRID_BUBBLE', 'height': 150}).set_placement(
                (x, min_y - bubble_r), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)

        # Horizontal grid lines (Y geometry, Label A, B, C...)
        min_x = (min(self.gm.x_grid_lines) if self.gm.x_grid_lines else 0) * 1000 - ext
        max_x = (max(self.gm.x_grid_lines) if self.gm.x_grid_lines else 0) * 1000 + ext
        
        y_sorted_desc = sorted(self.gm.y_grid_lines, reverse=True)
        for i, y_m in enumerate(y_sorted_desc):
            label = chr(65 + i)
            y = y_m * 1000
            self.msp.add_line((min_x, y), (max_x, y), dxfattribs={'layer': 'GRID'})
            self.msp.add_circle((min_x - bubble_r, y), bubble_r, dxfattribs={'layer': 'GRID_BUBBLE'})
            self.msp.add_text(label, dxfattribs={'layer': 'GRID_BUBBLE', 'height': 150}).set_placement(
                (min_x - bubble_r, y), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
            self.msp.add_circle((max_x + bubble_r, y), bubble_r, dxfattribs={'layer': 'GRID_BUBBLE'})
            self.msp.add_text(label, dxfattribs={'layer': 'GRID_BUBBLE', 'height': 150}).set_placement(
                (max_x + bubble_r, y), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)

    def _draw_dimensions(self):
        dimstyle = self.doc.dimstyles.new("ARCH_DIM")
        dimstyle.dxf.dimtxt = 150.0  
        dimstyle.dxf.dimclrt = 2  
        dimstyle.dxf.dimclrd = 2  
        dimstyle.dxf.dimclre = 2  
        dimstyle.dxf.dimdec = 2   
        
        ext, bubble_r = 1200.0, 200.0
        offset_1, offset_2 = 400.0, 1000.0 
        
        if not self.gm.x_grid_lines or not self.gm.y_grid_lines: return
        max_y = max(self.gm.y_grid_lines) * 1000 + ext + bubble_r*2
        max_x = max(self.gm.x_grid_lines) * 1000 + ext + bubble_r*2
        x_lines = sorted(self.gm.x_grid_lines)
        y_lines = sorted(self.gm.y_grid_lines, reverse=True)
        
        if len(x_lines) > 1:
            base_y = max_y + offset_1
            for i in range(len(x_lines)-1):
                x1, x2 = x_lines[i]*1000, x_lines[i+1]*1000
                dim = self.msp.add_linear_dim(base=(x1, base_y), p1=(x1, max_y), p2=(x2, max_y), 
                                         dimstyle="ARCH_DIM", text=f"{(x2-x1)/1000.0:.2f}", dxfattribs={'layer': 'DIMENSIONS'})
                dim.render()
            dim = self.msp.add_linear_dim(base=(x_lines[0]*1000, base_y + offset_2), 
                                     p1=(x_lines[0]*1000, max_y), p2=(x_lines[-1]*1000, max_y),
                                     dimstyle="ARCH_DIM", text=f"{(x_lines[-1]-x_lines[0])/1000.0:.2f}", dxfattribs={'layer': 'DIMENSIONS'})
            dim.render()

        if len(y_lines) > 1:
            base_x = max_x + offset_1
            for i in range(len(y_lines)-1):
                y1, y2 = y_lines[i]*1000, y_lines[i+1]*1000
                dim = self.msp.add_linear_dim(base=(base_x, y1), p1=(max_x, y1), p2=(max_x, y2), 
                                         angle=90, dimstyle="ARCH_DIM", text=f"{abs(y1-y2)/1000.0:.2f}", dxfattribs={'layer': 'DIMENSIONS'})
                dim.render()
            dim = self.msp.add_linear_dim(base=(base_x + offset_2, y_lines[0]*1000), 
                                     p1=(max_x, y_lines[0]*1000), p2=(max_x, y_lines[-1]*1000), 
                                     angle=90, dimstyle="ARCH_DIM", text=f"{abs(y_lines[0]-y_lines[-1])/1000.0:.2f}", dxfattribs={'layer': 'DIMENSIONS'})
            dim.render()

    def _draw_columns(self):
        cols = [c for c in self.gm.columns if c.level == 0]
        for col in cols:
            cx, cy = col.x * 1000, col.y * 1000
            w, d = col.width_nb, col.depth_nb
            points = [(cx - w/2, cy - d/2), (cx + w/2, cy - d/2), (cx + w/2, cy + d/2), (cx - w/2, cy + d/2), (cx - w/2, cy - d/2)]
            
            hatch = self.msp.add_hatch(color=1, dxfattribs={'layer': 'COLUMNS'})
            hatch.paths.add_polyline_path(points)
            self.msp.add_lwpolyline(points, dxfattribs={'layer': 'COLUMNS'})
            
            self.msp.add_text(f"{col.id}-F1", dxfattribs={'layer': 'COLUMNS', 'height': 150}).set_placement((cx + w/2 + 50, cy + d/2 + 50))

    def _draw_footings(self):
        cols = [c for c in self.gm.columns if c.level == 0]
        fw, fd = 1200.0, 1200.0
        for col in cols:
            cx, cy = col.x * 1000, col.y * 1000
            p1, p2, p3, p4 = (cx - fw/2, cy - fd/2), (cx + fw/2, cy - fd/2), (cx + fw/2, cy + fd/2), (cx - fw/2, cy + fd/2)
            self.msp.add_lwpolyline([p1, p2, p3, p4, p1], dxfattribs={'layer': 'FOOTINGS'})

    def _draw_beams(self):
        seen_beams = set()
        for beam in self.beams:
            p_s = (round(beam.start_point.x, 3), round(beam.start_point.y, 3))
            p_e = (round(beam.end_point.x, 3), round(beam.end_point.y, 3))
            key = tuple(sorted((p_s, p_e)))
            if key in seen_beams: continue
            seen_beams.add(key)
            
            start = (beam.start_point.x * 1000, beam.start_point.y * 1000)
            end = (beam.end_point.x * 1000, beam.end_point.y * 1000)
            
            self.msp.add_line(start, end, dxfattribs={'layer': 'BEAMS', 'lineweight': 35})
            
            mid = ((start[0]+end[0])/2, (start[1]+end[1])/2)
            # Wall footing or Foundation tie beam
            lbl = "WF" if hasattr(beam, 'id') and "WF" in beam.id else "FTB"
            self.msp.add_text(lbl, dxfattribs={'layer': 'BEAMS', 'height': 120}).set_placement((mid[0], mid[1]+100))

    def _draw_slab_annotation(self):
        if not self.gm.x_grid_lines or not self.gm.y_grid_lines: return
        x1, x2 = min(self.gm.x_grid_lines)*1000, max(self.gm.x_grid_lines)*1000
        y1, y2 = min(self.gm.y_grid_lines)*1000, max(self.gm.y_grid_lines)*1000
        
        # Diagonal ANSI31 hatch over entire slab envelope for visual pop
        hatch = self.msp.add_hatch(color=8, dxfattribs={'layer': 'SLAB_HATCH'})
        hatch.set_pattern_fill('ANSI31', scale=500.0)
        hatch.paths.add_polyline_path([(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)])
        
        # Center multiline text
        cx, cy = (x1+x2)/2, (y1+y2)/2
        txt = "100mm THICK SLAB\\nWITH 10mm Ø TEMP.BARS\\n@300mm O.C.B.W."
        self.msp.add_text("100mm THICK SLAB", dxfattribs={'layer': 'SLAB_NOTES', 'height': 150}).set_placement((cx, cy + 200), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
        self.msp.add_text("WITH 10mm Ø TEMP.BARS", dxfattribs={'layer': 'SLAB_NOTES', 'height': 150}).set_placement((cx, cy), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
        self.msp.add_text("@300mm O.C.B.W.", dxfattribs={'layer': 'SLAB_NOTES', 'height': 150}).set_placement((cx, cy - 200), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)

    def _draw_stairs(self):
        # Placeholder for stair symbol detection
        pass

    def _draw_north_arrow(self):
        if not self.gm.x_grid_lines or not self.gm.y_grid_lines: return
        nx = max(self.gm.x_grid_lines)*1000 + 3000
        ny = max(self.gm.y_grid_lines)*1000 + 3000
        self.msp.add_circle((nx, ny), 300, dxfattribs={'layer': 'NORTH_ARROW'})
        self.msp.add_line((nx, ny-300), (nx, ny+500), dxfattribs={'layer': 'NORTH_ARROW'})
        self.msp.add_line((nx, ny+500), (nx-150, ny+200), dxfattribs={'layer': 'NORTH_ARROW'})
        self.msp.add_line((nx, ny+500), (nx+150, ny+200), dxfattribs={'layer': 'NORTH_ARROW'})
        self.msp.add_text("N", dxfattribs={'layer': 'NORTH_ARROW', 'height': 200}).set_placement((nx, ny+600), align=ezdxf.enums.TextEntityAlignment.BOTTOM_CENTER)

    def _draw_scale_bar(self):
        if not self.gm.x_grid_lines or not self.gm.y_grid_lines: return
        sx = min(self.gm.x_grid_lines)*1000
        sy = min(self.gm.y_grid_lines)*1000 - 3000
        for i in range(3):
            self.msp.add_line((sx + i*1000, sy), (sx + i*1000, sy+100), dxfattribs={'layer': 'SCALE_BAR'})
            self.msp.add_text(f"{i}m", dxfattribs={'layer': 'SCALE_BAR', 'height': 120}).set_placement((sx + i*1000, sy+150), align=ezdxf.enums.TextEntityAlignment.BOTTOM_CENTER)
        self.msp.add_line((sx, sy), (sx + 2000, sy), dxfattribs={'layer': 'SCALE_BAR'})

    def _draw_title_block(self):
        if not self.gm.x_grid_lines or not self.gm.y_grid_lines: return
        min_x = min(self.gm.x_grid_lines)*1000 - 2500
        max_x = max(self.gm.x_grid_lines)*1000 + 4000
        min_y = min(self.gm.y_grid_lines)*1000 - 5000
        
        # Main border
        self.msp.add_lwpolyline([(min_x, min_y), (max_x, min_y), (max_x, min_y+1500), (min_x, min_y+1500), (min_x, min_y)], dxfattribs={'layer': 'TITLE_BLOCK'})
        
        # Separators
        w = max_x - min_x
        self.msp.add_line((min_x + w*0.3, min_y), (min_x + w*0.3, min_y+1500), dxfattribs={'layer': 'TITLE_BLOCK'})
        self.msp.add_line((min_x + w*0.6, min_y), (min_x + w*0.6, min_y+1500), dxfattribs={'layer': 'TITLE_BLOCK'})
        self.msp.add_line((min_x + w*0.8, min_y), (min_x + w*0.8, min_y+1500), dxfattribs={'layer': 'TITLE_BLOCK'})
        
        # Texts
        p_name = self.design.get("project_name", "PROPOSED BUILDING")
        eng = self.design.get("engineer", "STRUCTURAL ENGINEER")
        title = "FOUNDATION PLAN" if self.type == "FOUNDATION" else "STRUCTURAL FRAMING PLAN"
        date = self.design.get("date", "2026")
        scale = self.design.get("scale", "1:100")
        sheet = self.design.get("sheet", "S-1")
        
        self.msp.add_text(p_name, dxfattribs={'layer': 'TITLE_BLOCK', 'height': 200}).set_placement((min_x + w*0.15, min_y+750), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
        self.msp.add_text(title, dxfattribs={'layer': 'TITLE_BLOCK', 'height': 250}).set_placement((min_x + w*0.45, min_y+750), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
        self.msp.add_text(f"DATE: {date}\\nSCALE: {scale}", dxfattribs={'layer': 'TITLE_BLOCK', 'height': 150}).set_placement((min_x + w*0.7, min_y+750), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
        self.msp.add_text(sheet, dxfattribs={'layer': 'TITLE_BLOCK', 'height': 400}).set_placement((min_x + w*0.9, min_y+750), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)

    def export_beam_schedule_table(self, filepath: str) -> str:
        doc = ezdxf.new(dxfversion='R2010')
        doc.units = units.MM
        msp = doc.modelspace()
        doc.layers.add("TABLE", color=7, linetype="CONTINUOUS", lineweight=25)
        
        # Base table parameters
        cx, cy = 0, 0
        w_sec, w_end, w_mid, w_space = 2000, 4000, 4000, 3000
        h_head = 800
        h_row = 1500
        
        # Header
        tot_w = w_sec + w_end + w_mid + w_space
        msp.add_lwpolyline([(cx, cy), (cx+tot_w, cy), (cx+tot_w, cy-h_head), (cx, cy-h_head), (cx, cy)], dxfattribs={'layer': 'TABLE'})
        msp.add_line((cx+w_sec, cy), (cx+w_sec, cy-h_head), dxfattribs={'layer': 'TABLE'})
        msp.add_line((cx+w_sec+w_end, cy), (cx+w_sec+w_end, cy-h_head), dxfattribs={'layer': 'TABLE'})
        msp.add_line((cx+w_sec+w_end+w_mid, cy), (cx+w_sec+w_end+w_mid, cy-h_head), dxfattribs={'layer': 'TABLE'})
        
        msp.add_text("SECTION", dxfattribs={'layer': 'TABLE', 'height': 150}).set_placement((cx+w_sec/2, cy-h_head/2), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
        msp.add_text("END-SECT REBARS", dxfattribs={'layer': 'TABLE', 'height': 150}).set_placement((cx+w_sec+w_end/2, cy-h_head/2), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
        msp.add_text("MID-SECT REBARS", dxfattribs={'layer': 'TABLE', 'height': 150}).set_placement((cx+w_sec+w_end+w_mid/2, cy-h_head/2), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
        msp.add_text("SPACING OF STIRRUPS", dxfattribs={'layer': 'TABLE', 'height': 150}).set_placement((cx+tot_w-w_space/2, cy-h_head/2), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)

        # Rows
        sections = ["B1", "B2", "RB", "FTB"]
        for i, sec in enumerate(sections):
            ry = cy - h_head - i*h_row
            msp.add_lwpolyline([(cx, ry), (cx+tot_w, ry), (cx+tot_w, ry-h_row), (cx, ry-h_row), (cx, ry)], dxfattribs={'layer': 'TABLE'})
            msp.add_line((cx+w_sec, ry), (cx+w_sec, ry-h_row), dxfattribs={'layer': 'TABLE'})
            msp.add_line((cx+w_sec+w_end, ry), (cx+w_sec+w_end, ry-h_row), dxfattribs={'layer': 'TABLE'})
            msp.add_line((cx+w_sec+w_end+w_mid, ry), (cx+w_sec+w_end+w_mid, ry-h_row), dxfattribs={'layer': 'TABLE'})
            
            msp.add_text(sec, dxfattribs={'layer': 'TABLE', 'height': 200}).set_placement((cx+w_sec/2, ry-h_row/2), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
            
            # Draw tiny cross-section sketch in END and MID
            def draw_sect_sketch(px, py):
                msp.add_lwpolyline([(px-150, py-250), (px+150, py-250), (px+150, py+250), (px-150, py+250), (px-150, py-250)], dxfattribs={'layer': 'TABLE'})
                msp.add_circle((px-100, py+200), 25, dxfattribs={'layer': 'TABLE'}) # rebars
                msp.add_circle((px+100, py+200), 25, dxfattribs={'layer': 'TABLE'})
            
            draw_sect_sketch(cx+w_sec+w_end/4, ry-h_row/2)
            msp.add_text("2-16mm Ø TOP BARS", dxfattribs={'layer': 'TABLE', 'height': 120}).set_placement((cx+w_sec+w_end/2 + 200, ry-h_row/3))
            msp.add_text("2-12mm Ø MID BARS", dxfattribs={'layer': 'TABLE', 'height': 120}).set_placement((cx+w_sec+w_end/2 + 200, ry-h_row/2))
            msp.add_text("2-16mm Ø BOT BARS", dxfattribs={'layer': 'TABLE', 'height': 120}).set_placement((cx+w_sec+w_end/2 + 200, ry-h_row*2/3))

            draw_sect_sketch(cx+w_sec+w_end+w_mid/4, ry-h_row/2)
            msp.add_text("2-16mm Ø TOP BARS", dxfattribs={'layer': 'TABLE', 'height': 120}).set_placement((cx+w_sec+w_end+w_mid/2 + 200, ry-h_row/3))
            msp.add_text("2-12mm Ø MID BARS", dxfattribs={'layer': 'TABLE', 'height': 120}).set_placement((cx+w_sec+w_end+w_mid/2 + 200, ry-h_row/2))
            msp.add_text("2-16mm Ø BOT BARS", dxfattribs={'layer': 'TABLE', 'height': 120}).set_placement((cx+w_sec+w_end+w_mid/2 + 200, ry-h_row*2/3))
            
            msp.add_text("A, B, C, D", dxfattribs={'layer': 'TABLE', 'height': 150}).set_placement((cx+tot_w-w_space/2, ry-h_row/2), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
            
        doc.saveas(filepath)
        logger.info("Beam Schedule DXF Exported: %s", filepath)
        return filepath
