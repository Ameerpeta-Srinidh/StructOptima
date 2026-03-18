from typing import List, Tuple, Dict, Optional
import math
from .cad_parser import CADParser
from .grid_manager import GridManager, Column
from .framing_logic import StructuralMember, Point, MemberProperties
from .logging_config import get_logger

logger = get_logger(__name__)

class CADLoader:
    def __init__(self, dxf_path: str):
        self.parser = CADParser(dxf_path)
        self.parser.load()
        self.placement_warnings = []
        self.placement_stats = {}
        self.placer = None          # Stored for Column Editor use
        self.placement_result = None # Stored for Column Editor use
        
    def _snap_to_grid(self, val: float, grid: List[float], tol: float = 0.1) -> float:
        for g in grid:
            if abs(val - g) < tol:
                return g
        return val

    def load_grid_manager(
        self, 
        auto_frame: bool = False,
        seismic_zone: str = "III"
    ) -> Tuple[GridManager, List[StructuralMember]]:
        """
        Creates a GridManager and Beam list from the CAD file.
        Infers grid lines from column positions.
        
        Args:
            auto_frame: If True, use IS-code compliant ColumnPlacer for automatic placement
            seismic_zone: Seismic zone for IS 13920 sizing (II, III, IV, V)
        """
        raw_cols = []
        raw_beams = []
        placement_result = None
        
        if auto_frame:
            from .auto_framer import AutoFramer
            from .column_placer import ColumnPlacer
            
            self.framer = AutoFramer(self.parser)
            self.framer.identify_structural_nodes()
            
            placer = ColumnPlacer(
                nodes=self.framer.nodes,
                centerlines=self.framer.centerlines,
                seismic_zone=seismic_zone
            )
            placement_result = placer.generate_placement()
            
            # Store for Column Editor access
            self.placer = placer
            self.placement_result = placement_result
            
            raw_cols = [
                {
                    'id': col.id,
                    'x': col.x,
                    'y': col.y,
                    'width': col.width,
                    'depth': col.depth,
                    'junction_type': col.junction_type.value,
                    'is_floating': col.is_floating,
                    'reinforcement_rule': col.reinforcement_rule.value,
                    'orientation_deg': col.orientation_deg
                }
                for col in placement_result.columns
            ]
            
            self.placement_warnings = [w.to_dict() for w in placement_result.warnings]
            self.placement_stats = placement_result.stats
            
            raw_beams_struct = self.framer.generate_beams()
            logger.info("IS-Code Column Placer: Generated %d columns with %d warnings", 
                       len(raw_cols), len(self.placement_warnings))
        else:
            raw_cols = self.parser.extract_columns()
            raw_beams = self.parser.extract_beams()
        
        if not raw_cols:
             if auto_frame:
                 raise ValueError("Auto-Framer could not find any valid column locations (walls/corners missing?)")
             else:
                 raise ValueError("No columns found in CAD file. Check layer names or use --auto-frame")

        xs = [c['x'] for c in raw_cols]
        ys = [c['y'] for c in raw_cols]
        
        max_coord = max(max(xs), max(ys)) if xs and ys else 0
        scale_factor = 1.0
        if max_coord > 500:
            scale_factor = 0.001
            logger.debug("Detected large coordinates (max %s), assuming mm. Converting to meters.", max_coord)
        
        unique_x = sorted(list(set([round(x * scale_factor, 2) for x in xs])))
        unique_y = sorted(list(set([round(y * scale_factor, 2) for y in ys])))
        
        width_m = unique_x[-1] - unique_x[0] if unique_x else 0
        length_m = unique_y[-1] - unique_y[0] if unique_y else 0
        
        gm = GridManager(width_m=width_m, length_m=length_m)
        gm.x_grid_lines = unique_x
        gm.y_grid_lines = unique_y
        
        gm.columns = []
        for rc in raw_cols:
            x_m = rc['x'] * scale_factor
            y_m = rc['y'] * scale_factor
            
            x_m = self._snap_to_grid(x_m, unique_x)
            y_m = self._snap_to_grid(y_m, unique_y)
            
            w_mm = rc.get('width', 300)
            d_mm = rc.get('depth', 300)
            
            if w_mm < 5.0 and scale_factor == 1.0: 
                w_mm *= 1000.0
                d_mm *= 1000.0
            
            col = Column(
                id=rc['id'],
                x=x_m,
                y=y_m,
                width_nb=w_mm,
                depth_nb=d_mm,
                level=0, 
                z_top=3.0
            )
            
            if auto_frame:
                col.junction_type = rc.get('junction_type', 'interior')
                col.is_floating = rc.get('is_floating', False)
                col.reinforcement_rule = rc.get('reinforcement_rule', 'IS_456_Standard')
                col.orientation_deg = rc.get('orientation_deg', 0.0)
            
            gm.columns.append(col)
            
        beams = []
        
        if auto_frame and 'raw_beams_struct' in locals():
             for sb in raw_beams_struct:
                 p1 = Point(x=sb.start_point.x * scale_factor, y=sb.start_point.y * scale_factor)
                 p2 = Point(x=sb.end_point.x * scale_factor, y=sb.end_point.y * scale_factor)
                 
                 p1.x = self._snap_to_grid(p1.x, unique_x)
                 p1.y = self._snap_to_grid(p1.y, unique_y)
                 p2.x = self._snap_to_grid(p2.x, unique_x)
                 p2.y = self._snap_to_grid(p2.y, unique_y)
                 
                 beams.append(StructuralMember(
                    id=sb.id,
                    type="beam",
                    start_point=p1,
                    end_point=p2,
                    properties=sb.properties
                 ))
        else:
            for rb in raw_beams:
                start = rb['start']
                end = rb['end']
                
                p1 = Point(x=start[0]*scale_factor, y=start[1]*scale_factor)
                p2 = Point(x=end[0]*scale_factor, y=end[1]*scale_factor)
                
                beams.append(StructuralMember(
                    id=rb['id'],
                    type="beam",
                    start_point=p1,
                    end_point=p2,
                    properties=MemberProperties(width_mm=300, depth_mm=600)
                ))
            
        return gm, beams
    
    def get_placement_json(self) -> str:
        """Returns JSON string of placement result with columns and warnings."""
        import json
        
        return json.dumps({
            "warnings": self.placement_warnings,
            "stats": self.placement_stats
        }, indent=2)
