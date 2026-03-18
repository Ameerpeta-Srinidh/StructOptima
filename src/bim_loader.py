
import ifcopenshell
import ifcopenshell.util.element
import ifcopenshell.util.placement
import math
from typing import List, Tuple, Optional
from .grid_manager import GridManager, Column
from .framing_logic import StructuralMember, Point, MemberProperties
from .logging_config import get_logger

logger = get_logger(__name__)

class BIMLoader:
    """
    Parses Industry Foundation Classes (.ifc) files to extract structural data.
    """
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.model = ifcopenshell.open(file_path)
        self.gm = None
        self.beams = []
        
    def load_grid_manager(self) -> Tuple[GridManager, List[StructuralMember]]:
        """
        Main entry point. Returns GridManager and list of Beams.
        """
        logger.info("Loading IFC: %s", self.file_path)
        
        # 1. Analyze Vertical Structure
        stories = self.model.by_type("IfcBuildingStorey")
        # Sort by elevation
        stories.sort(key=lambda s: ifcopenshell.util.placement.get_local_placement(s.ObjectPlacement)[2, 3])
        
        num_stories = len(stories)
        if num_stories == 0:
             # Fallback if no stories defined properly
             num_stories = 1
             story_height = 3.0
        else:
             elevations = [ifcopenshell.util.placement.get_local_placement(s.ObjectPlacement)[2, 3] for s in stories]
             # Calc avg height
             if num_stories > 1:
                 story_height = (elevations[-1] - elevations[0]) / (num_stories - 1)
             else:
                 story_height = 3.0 # Default
                 
             if story_height < 1.0: story_height = 3.0 # Safety
             
        # Initialize GridManager
        # Dimensions are placeholder, will be updated by grid bounds
        self.gm = GridManager(width_m=20.0, length_m=20.0, num_stories=num_stories, story_height_m=story_height)
        self.gm.columns = [] 
        
        all_cols = []
        all_beams = []
        
        # 2. Extract Elements per Storey
        for i, storey in enumerate(stories):
            logger.debug("Parsing Storey %d: %s", i, storey.Name)
            
            # Get elements contained in storey
            # Uses IfcRelContainedInSpatialStructure
            elements = ifcopenshell.util.element.get_decomposition(storey)
            
            for elem in elements:
                if elem.is_a("IfcColumn"):
                    col = self._parse_column(elem, i, storey)
                    if col: 
                        all_cols.append(col)
                elif elem.is_a("IfcBeam"):
                    bm = self._parse_beam(elem, i, storey)
                    if bm:
                        all_beams.append(bm)
                        
        self.gm.columns = all_cols
        self.beams = all_beams
        
        logger.info("Extracted %d columns and %d beams.", len(self.gm.columns), len(self.beams))
        return self.gm, self.beams

    def _Get_Global_Matrix(self, elem):
         return ifcopenshell.util.placement.get_local_placement(elem.ObjectPlacement)

    def _parse_column(self, elem, level_idx, storey) -> Optional[Column]:
        # 1. Geometry (Global Coords)
        matrix = self._Get_Global_Matrix(elem)
        # 4th column is translation vector (x, y, z, 1)
        x = matrix[0, 3]
        y = matrix[1, 3]
        z_base = matrix[2, 3]
        
        # 2. Profile (Dimensions)
        width = 300.0
        depth = 300.0
        
        # Try to drill down Representation -> RepresentationMap -> MappedRepresentation -> Items -> IfcExtrudedAreaSolid -> ProfileDef
        # OR: ifcopenshell.util.element.get_psets(elem) might have dimensions? rarely reliable.
        # Let's inspect 'Representation'
        
        rep = elem.Representation
        if rep:
            for r in rep.Representations:
                for item in r.Items:
                    if item.is_a("IfcExtrudedAreaSolid"):
                        profile = item.SweptArea
                        if profile.is_a("IfcRectangleProfileDef"):
                            width = profile.XDim
                            depth = profile.YDim
        
        # Convert to mm if needed. IFC usually SI (m) or mm
        # Check Project Units? 
        # Heuristic: if width < 2.0, assumes meters => convert to mm
        if width < 2.0: width *= 1000.0
        if depth < 2.0: depth *= 1000.0
        
        # Rounding
        width = round(width / 10.0) * 10
        depth = round(depth / 10.0) * 10
        
        c = Column(
            id=f"C_IFC_{elem.GlobalId[:5]}",
            x=x,
            y=y,
            level=level_idx,
            width_nb=width,
            depth_nb=depth,
            height_m=self.gm.story_height_m # Default, or derive from extrusion depth calculation
        )
        c.z_bottom = z_base
        c.z_top = z_base + c.height_m
        return c

    def _parse_beam(self, elem, level_idx, storey) -> Optional[StructuralMember]:
        matrix = self._Get_Global_Matrix(elem)
        x_start = matrix[0, 3]
        y_start = matrix[1, 3]
        z_start = matrix[2, 3]
        
        # Need Length and Rotation to find End Point?
        # Beam Axis usually along local X (1,0,0) extruding along Length? 
        # Or Curve2D?
        
        # Simplification: Assume extrustion along local Z or X given profile alignment
        # Usually IfcBeam -> ExtrudedAreaSolid -> Depth (Length)
        length = 3.0 
        width_mm = 230.0
        depth_mm = 450.0
        
        rep = elem.Representation
        if rep:
            for r in rep.Representations:
                for item in r.Items:
                    if item.is_a("IfcExtrudedAreaSolid"):
                        length = item.Depth # Extrusion depth = Length of beam usually
                        
                        profile = item.SweptArea
                        if profile.is_a("IfcRectangleProfileDef"):
                            width_mm = profile.XDim
                            depth_mm = profile.YDim
                                
        # Units Heuristic
        if width_mm < 2.0: width_mm *= 1000.0
        if depth_mm < 2.0: depth_mm *= 1000.0
        
        # Transform End Point
        # Local X is direction of extrusion usually (IfcExtrudedAreaSolid direction? No, Extrusion is usually along Z of Position)
        # Actually ExtrudedAreaSolid: 'ExtrudedDirection'
        
        # Simplified: Use matrix rotation to find vector
        # Local Z axis is column 2 (0,0,1)?
        # For Beams, usually X axis is length.
        
        # Let's assume X axis of local placement is the beam axis.
        vec_x = matrix[0, 0] * length
        vec_y = matrix[1, 0] * length
        # vec_z = matrix[2, 0] * length
        
        x_end = x_start + vec_x
        y_end = y_start + vec_y
        
        bm = StructuralMember(
            start_point=Point(x=x_start, y=y_start),
            end_point=Point(x=x_end, y=y_end),
            id=f"B_IFC_{elem.GlobalId[:5]}"
        )
        bm.properties = MemberProperties(width_mm=width_mm, depth_mm=depth_mm)
        
        return bm
