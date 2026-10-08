import trimesh
import math
import numpy as np
import base64
from typing import List, Tuple, Optional
from src.grid_manager import GridManager
from src.framing_logic import StructuralMember
from src.foundation_eng import Footing
from src.materials import Concrete

class GeometryExporter:
    @staticmethod
    def create_structure_scene(
        grid_mgr: GridManager,
        beams: List[StructuralMember],
        footings: List[Footing],
        view_mode: str = "Engineering",
        arch_walls: Optional[List[Tuple[Tuple[float, float], Tuple[float, float]]]] = None,
        height_m: float = 3.0,
        show_walls: bool = False,
    ) -> trimesh.Scene:
        scene = trimesh.Scene()
        
        # Helper colors
        col_color = [150, 150, 150, 255] # Grey
        beam_color = [200, 100, 50, 255] # Orange-ish
        footing_color = [100, 100, 100, 255] # Dark grey
        
        # Wall colors by material (semi-transparent so structure is visible)
        WALL_COLORS = {
            "brick":     [210, 105, 30, 160],   # Terracotta brick
            "aac_block": [200, 200, 200, 160],   # Light grey
            "rcc":       [150, 150, 150, 180],   # Concrete grey
        }
        DEFAULT_WALL_COLOR = [210, 105, 30, 160]
        
        # 1. Add Columns
        for col in grid_mgr.columns:
            w = getattr(col, 'width_nb', 300.0) / 1000.0
            d = getattr(col, 'depth_nb', 300.0) / 1000.0
            z_bot = getattr(col, 'z_bottom', 0.0)
            z_top = getattr(col, 'z_top', height_m)
            h = z_top - z_bot
            if h <= 0: h = height_m
            
            box = trimesh.creation.box(extents=[w, d, h])
            transform = np.eye(4)
            transform[0, 3] = col.x
            transform[1, 3] = col.y
            transform[2, 3] = z_bot + h/2.0
            box.apply_transform(transform)
            box.visual.face_colors = col_color
            scene.add_geometry(box)
            
        # 2. Add Footings
        level0_cols = [c for c in grid_mgr.columns if getattr(c, 'level', 0) == 0]
        for col, ftg in zip(level0_cols, footings):
            L = ftg.length_m
            B = ftg.width_m
            D = ftg.thickness_mm / 1000.0
            if L <= 0 or B <= 0 or D <= 0: continue
            
            box = trimesh.creation.box(extents=[L, B, D])
            transform = np.eye(4)
            transform[0, 3] = col.x
            transform[1, 3] = col.y
            transform[2, 3] = -D/2.0
            box.apply_transform(transform)
            box.visual.face_colors = footing_color
            scene.add_geometry(box)
            
        # 3. Add Beams
        story_height = getattr(grid_mgr, 'story_height_m', 3.0)
        for beam in beams:
            level = getattr(beam, 'level', 0)
            z_nominal = (level + 1) * story_height
            
            x0, y0 = beam.start_point.x, beam.start_point.y
            x1, y1 = beam.end_point.x, beam.end_point.y
            
            dx = x1 - x0
            dy = y1 - y0
            length = math.hypot(dx, dy)
            if length < 0.01: continue
            
            w = getattr(beam.properties, 'width_mm', 230.0) / 1000.0 if getattr(beam, 'properties', None) else 0.23
            d = getattr(beam.properties, 'depth_mm', 400.0) / 1000.0 if getattr(beam, 'properties', None) else 0.40
            
            box = trimesh.creation.box(extents=[length, w, d])
            
            angle = math.atan2(dy, dx)
            rot = trimesh.transformations.rotation_matrix(angle, [0, 0, 1])
            
            cx = (x0 + x1) / 2.0
            cy = (y0 + y1) / 2.0
            cz = z_nominal - (d / 2.0)
            
            trans = trimesh.transformations.translation_matrix([cx, cy, cz])
            transform = np.dot(trans, rot)
            box.apply_transform(transform)
            
            # Color by utilization if available
            util = 0.0
            if getattr(beam, 'analysis_result', None):
                util = beam.analysis_result.get('usage_ratio', 0.5) or 0.0
            if view_mode in ["Engineering", "Utilization"]:
                if util < 0.5: c = [0, 255, 0, 255]
                elif util < 0.9: c = [255, 215, 0, 255]
                else: c = [255, 0, 0, 255]
                box.visual.face_colors = c
            else:
                box.visual.face_colors = beam_color
                
            scene.add_geometry(box)
            
        # 4. Add Walls (from Wall model — proper multi-story rendering)
        if show_walls and hasattr(grid_mgr, 'walls') and grid_mgr.walls:
            num_stories = getattr(grid_mgr, 'num_stories', 1)
            
            for wall in grid_mgr.walls:
                x0 = wall.start_x
                y0 = wall.start_y
                x1 = wall.end_x
                y1 = wall.end_y
                
                dx = x1 - x0
                dy = y1 - y0
                wall_len = math.hypot(dx, dy)
                if wall_len < 0.01:
                    continue
                
                wall_th = wall.thickness_mm / 1000.0
                wall_h = wall.height_m
                
                material = getattr(wall, 'material', 'brick')
                wall_color = WALL_COLORS.get(material, DEFAULT_WALL_COLOR)
                
                angle = math.atan2(dy, dx)
                rot = trimesh.transformations.rotation_matrix(angle, [0, 0, 1])
                
                cx = (x0 + x1) / 2.0
                cy = (y0 + y1) / 2.0
                
                # Render wall at each story level
                for lvl in range(num_stories):
                    z_bot = lvl * story_height
                    cz = z_bot + wall_h / 2.0
                    
                    box = trimesh.creation.box(extents=[wall_len, wall_th, wall_h])
                    trans = trimesh.transformations.translation_matrix([cx, cy, cz])
                    tf = np.dot(trans, rot)
                    box.apply_transform(tf)
                    box.visual.face_colors = wall_color
                    scene.add_geometry(box)
        
        # 4b. Fallback — old arch_walls for CAD import backward compatibility
        elif show_walls and arch_walls:
            for (p1, p2) in arch_walls:
                x0, y0 = p1
                x1, y1 = p2
                dx = x1 - x0
                dy = y1 - y0
                length = math.hypot(dx, dy)
                if length < 0.01: continue
                
                wall_th = 0.20
                wall_h = height_m
                
                box = trimesh.creation.box(extents=[length, wall_th, wall_h])
                angle = math.atan2(dy, dx)
                rot = trimesh.transformations.rotation_matrix(angle, [0, 0, 1])
                
                cx = (x0 + x1) / 2.0
                cy = (y0 + y1) / 2.0
                cz = wall_h / 2.0
                
                trans = trimesh.transformations.translation_matrix([cx, cy, cz])
                transform = np.dot(trans, rot)
                box.apply_transform(transform)
                box.visual.face_colors = DEFAULT_WALL_COLOR
                scene.add_geometry(box)
                
        # Rot Z to Y for model-viewer (glTF uses Y up)
        rot_x = trimesh.transformations.rotation_matrix(-math.pi/2, [1, 0, 0])
        scene.apply_transform(rot_x)
        
        return scene

    @staticmethod
    def export_to_glb_base64(scene: trimesh.Scene) -> str:
        """Exports the scene to a GLB byte array and returns the base64 string."""
        glb_bytes = scene.export(file_type='glb')
        b64 = base64.b64encode(glb_bytes).decode('ascii')
        return f"data:model/gltf-binary;base64,{b64}"
