import ezdxf
from typing import Dict, List, Tuple, Optional
import math
from .logging_config import get_logger

logger = get_logger(__name__)

class CADParser:
    """
    Parses DXF files to extract structural geometry.
    """
    def __init__(self, filepath: str, layer_map: Optional[Dict[str, str]] = None):
        """
        Args:
            filepath: Path to the .dxf file.
            layer_map: Dictionary mapping element types to DXF layer names.
                       Default: {'columns': 'COLUMNS', 'beams': 'BEAMS', 'footings': 'FOOTINGS'}
        """
        self.filepath = filepath
        self.doc = None
        self.msp = None
        
        # Default layer mapping
        self.layer_map = {
            'columns': 'COLUMNS',
            'beams': 'BEAMS',
            'footings': 'FOOTINGS'
        }
        if layer_map:
            self.layer_map.update(layer_map)

    def load(self):
        """Loads the DXF file."""
        try:
            self.doc = ezdxf.readfile(self.filepath)
            self.msp = self.doc.modelspace()
            logger.info("Successfully loaded %s", self.filepath)
        except IOError:
            logger.error("Not a DXF file or a generic I/O error: %s", self.filepath)
            raise
        except ezdxf.DXFStructureError:
            logger.error("Invalid or corrupted DXF file: %s", self.filepath)
            raise

    def get_layers(self) -> List[str]:
        """Returns a list of all layer names in the file."""
        if not self.doc:
            return []
        return [layer.dxf.name for layer in self.doc.layers]

    def _get_entity_center(self, entity) -> Tuple[float, float]:
        """Calculates the center (x, y) based on the bounding box."""
        # Use bounding box for more robust center finding of columns
        points = []
        if entity.dxftype() == 'LWPOLYLINE':
            points = entity.get_points(format='xy')
        elif entity.dxftype() == 'POLYLINE':
            points = [v.dxf.location[:2] for v in entity.vertices]
        else:
            return (0.0, 0.0)

        if not points:
            return (0.0, 0.0)

        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        
        return ((min_x + max_x) / 2.0, (min_y + max_y) / 2.0)

    
    def _get_dims(self, entity) -> Tuple[float, float]:
         """Approximates width and depth/height from bounding box."""
         # This is a simplification. Real extraction might need more complex geometry analysis.
         points = []
         if entity.dxftype() == 'LWPOLYLINE':
            points = entity.get_points(format='xy')
         
         if not points:
             return (0.0, 0.0)
         
         xs = [p[0] for p in points]
         ys = [p[1] for p in points]
         
         width = max(xs) - min(xs)
         depth = max(ys) - min(ys)
         return (width, depth)

    def extract_columns(self) -> List[Dict]:
        """Extracts column data from column layers."""
        columns = []
        if not self.msp or not self.doc:
            return []

        layer_names = [layer.dxf.name for layer in self.doc.layers]
        col_layers = [n for n in layer_names if any(kw in n.upper() for kw in ['COL', 'PILLAR', 'STANCHION'])]
        if not col_layers and self.layer_map['columns'] in layer_names:
            col_layers.append(self.layer_map['columns'])

        for layer in col_layers:
            for entity in self.msp.query(f'LWPOLYLINE[layer=="{layer}"]'):
                 cx, cy = self._get_entity_center(entity)
                 w, d = self._get_dims(entity)
                 columns.append({
                     'x': cx,
                     'y': cy,
                     'width': w,
                     'depth': d,
                     'id': f"C{len(columns)+1}"
                 })
                 
        return columns

    def extract_beams(self) -> List[Dict]:
        """Extracts beams, typically represented as lines or polylines."""
        beams = []
        if not self.msp or not self.doc:
             return []

        layer_names = [layer.dxf.name for layer in self.doc.layers]
        beam_layers = [n for n in layer_names if 'BEAM' in n.upper()]
        if not beam_layers and self.layer_map['beams'] in layer_names:
            beam_layers.append(self.layer_map['beams'])

        for layer in beam_layers:
            for entity in self.msp.query(f'LINE[layer=="{layer}"]'):
                start = entity.dxf.start
                end = entity.dxf.end
                beams.append({
                    'start': (start.x, start.y),
                    'end': (end.x, end.y),
                    'id': f"B{len(beams)+1}"
                })
            
        return beams

    def extract_walls(self) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
        """Extracts wall lines from LINE and POLYLINE entities."""
        if not self.msp or not self.doc:
            return []
            
        layer_names = [layer.dxf.name for layer in self.doc.layers]
        wall_layers = []
        for name in layer_names:
            upper = name.upper()
            if any(kw in upper for kw in ['WALL', 'STRUCT', 'LOAD', 'BEAR', 'MASONRY', 'BRICK']):
                wall_layers.append(name)
                
        def _get_lines_for_layers(layers_to_check):
            found_walls = []
            for layer in layers_to_check:
                for line in self.msp.query(f'LINE[layer=="{layer}"]'):
                    found_walls.append(((line.dxf.start.x, line.dxf.start.y), (line.dxf.end.x, line.dxf.end.y)))
                for ply in self.msp.query(f'LWPOLYLINE[layer=="{layer}"]'):
                    points = ply.get_points(format='xy')
                    for i in range(len(points) - 1): found_walls.append((points[i], points[i+1]))
                    if ply.is_closed and len(points) > 2: found_walls.append((points[-1], points[0]))
                for ply in self.msp.query(f'POLYLINE[layer=="{layer}"]'):
                    points = [v.dxf.location[:2] for v in ply.vertices]
                    for i in range(len(points) - 1): found_walls.append((points[i], points[i+1]))
                    if ply.is_closed and len(points) > 2: found_walls.append((points[-1], points[0]))
            return found_walls

        # First pass: try explicit matched layers
        walls = _get_lines_for_layers(wall_layers)
        
        # Deep Fallback: if STILL no lines found (e.g. wall layer exists but is empty/blocks), scan all layers
        if not walls:
            logger.warning("No line geometry found on explicit wall layers. Doing deep fallback to ALL layers.")
            walls = _get_lines_for_layers(layer_names)

        return walls

    def classify_layers(self) -> Dict[str, str]:
        """Classifies layers as load_bearing, partition, or boundary based on naming conventions."""
        if not self.doc:
            return {}
        
        classification = {}
        layer_names = [layer.dxf.name.upper() for layer in self.doc.layers]
        
        load_bearing_keywords = ['WALL', 'LOAD', 'STRUCT', 'BEARING', 'MAIN']
        partition_keywords = ['PARTITION', 'INTERNAL', 'NON-LOAD', 'NONLOAD']
        boundary_keywords = ['BOUNDARY', 'SLAB', 'EDGE', 'PERIMETER']
        
        for layer in self.doc.layers:
            name = layer.dxf.name.upper()
            
            if any(kw in name for kw in partition_keywords):
                classification[layer.dxf.name] = 'partition'
            elif any(kw in name for kw in boundary_keywords):
                classification[layer.dxf.name] = 'boundary'
            elif any(kw in name for kw in load_bearing_keywords):
                classification[layer.dxf.name] = 'load_bearing'
            elif name == 'WALLS':
                classification[layer.dxf.name] = 'load_bearing'
        
        return classification

    def extract_walls_by_type(self) -> Dict[str, List[Tuple]]:
        """Returns walls grouped by type (load_bearing, partition)."""
        classification = self.classify_layers()
        result = {
            'load_bearing': [],
            'partition': [],
            'boundary': []
        }
        
        if not self.msp:
            return result
        
        for layer in self.doc.layers:
            layer_name = layer.dxf.name
            wall_type = classification.get(layer_name, 'load_bearing')
            
            for line in self.msp.query(f'LINE[layer=="{layer_name}"]'):
                start = (line.dxf.start.x, line.dxf.start.y)
                end = (line.dxf.end.x, line.dxf.end.y)
                result[wall_type].append((start, end))
            
            for ply in self.msp.query(f'LWPOLYLINE[layer=="{layer_name}"]'):
                points = ply.get_points(format='xy')
                for i in range(len(points) - 1):
                    result[wall_type].append((points[i], points[i+1]))
                if ply.is_closed and len(points) > 2:
                    result[wall_type].append((points[-1], points[0]))
        
        return result

    def detect_wall_thickness(self, walls: List[Tuple]) -> float:
        """Detects wall thickness from parallel line pairs. Returns average thickness in mm."""
        if not walls or len(walls) < 2:
            return 230.0
        
        thicknesses = []
        used = [False] * len(walls)
        
        for i, w1 in enumerate(walls):
            if used[i]:
                continue
            
            v1 = (w1[1][0] - w1[0][0], w1[1][1] - w1[0][1])
            mag1 = math.hypot(v1[0], v1[1])
            if mag1 < 100:
                continue
            
            for j, w2 in enumerate(walls):
                if i == j or used[j]:
                    continue
                
                v2 = (w2[1][0] - w2[0][0], w2[1][1] - w2[0][1])
                mag2 = math.hypot(v2[0], v2[1])
                if mag2 < 100:
                    continue
                
                dot = (v1[0]*v2[0] + v1[1]*v2[1]) / (mag1 * mag2)
                angle = math.degrees(math.acos(max(-1, min(1, abs(dot)))))
                
                if angle < 5:
                    mx1 = (w1[0][0] + w1[1][0]) / 2
                    my1 = (w1[0][1] + w1[1][1]) / 2
                    mx2 = (w2[0][0] + w2[1][0]) / 2
                    my2 = (w2[0][1] + w2[1][1]) / 2
                    
                    dist = math.hypot(mx2 - mx1, my2 - my1)
                    
                    if 100 < dist < 500:
                        thicknesses.append(dist)
                        used[j] = True
        
        if thicknesses:
            return sum(thicknesses) / len(thicknesses)
        return 230.0

    def detect_enclosed_rectangles(self) -> List[Tuple[float, float, float, float]]:
        """Detects enclosed rectangular zones (potential stairwells/lift cores)."""
        walls = self.extract_walls()
        if not walls:
            return []
        
        rectangles = []
        
        horizontal = []
        vertical = []
        
        for start, end in walls:
            dx = abs(end[0] - start[0])
            dy = abs(end[1] - start[1])
            length = math.hypot(dx, dy)
            
            if length < 1000:
                continue
            
            if dx > dy * 3:
                horizontal.append((start, end))
            elif dy > dx * 3:
                vertical.append((start, end))
        
        for h1 in horizontal:
            for h2 in horizontal:
                if h1 == h2:
                    continue
                
                h1_y = (h1[0][1] + h1[1][1]) / 2
                h2_y = (h2[0][1] + h2[1][1]) / 2
                height = abs(h2_y - h1_y)
                
                if height < 1500 or height > 6000:
                    continue
                
                h1_x_min = min(h1[0][0], h1[1][0])
                h1_x_max = max(h1[0][0], h1[1][0])
                h2_x_min = min(h2[0][0], h2[1][0])
                h2_x_max = max(h2[0][0], h2[1][0])
                
                overlap_start = max(h1_x_min, h2_x_min)
                overlap_end = min(h1_x_max, h2_x_max)
                
                if overlap_end - overlap_start > 1500:
                    center_x = (overlap_start + overlap_end) / 2
                    center_y = (h1_y + h2_y) / 2
                    width = overlap_end - overlap_start
                    
                    rectangles.append((center_x, center_y, width, height))
        
        return rectangles
