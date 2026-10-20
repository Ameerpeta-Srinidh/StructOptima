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
        self.load_warnings: List[str] = []
        self.placement_stats = {}
        self.placer = None          # Stored for Column Editor use
        self.placement_result = None # Stored for Column Editor use
        self.scale_factor = 1.0
        
    @staticmethod
    def _cluster(values: List[float], tol: float = 0.15) -> Tuple[List[float], float]:
        """Group sorted coordinates whose neighbours are within ``tol`` m; returns (cluster means rounded to mm,
        largest distance of a value from its cluster mean)."""
        out, spread, group = [], 0.0, []
        for v in sorted(values):
            if group and v - group[-1] > tol:
                m = sum(group) / len(group)
                out.append(round(m, 3))
                spread = max(spread, max(abs(g - m) for g in group))
                group = []
            group.append(v)
        if group:
            m = sum(group) / len(group)
            out.append(round(m, 3))
            spread = max(spread, max(abs(g - m) for g in group))
        return out, spread

    def _snap_to_grid(self, val: float, grid: List[float], tol: float = 0.1) -> float:
        """Nearest grid coordinate within ``tol``, else the value itself."""
        if not grid:
            return val
        g = min(grid, key=lambda v: abs(v - val))
        return g if abs(val - g) < tol else val

    def load_grid_manager(
        self, 
        auto_frame: bool = False,
        seismic_zone: str = "III",
        story_height_m: float = 3.0,
        num_stories: int = 1,
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
            
            # Graceful fallback: if no explicit columns found, auto-detect from walls
            if not raw_cols:
                logger.warning("No explicit column entities found. Falling back to Auto-Frame mode.")
                from .auto_framer import AutoFramer
                from .column_placer import ColumnPlacer
                
                self.framer = AutoFramer(self.parser)
                self.framer.identify_structural_nodes()
                
                if not self.framer.nodes:
                    raise ValueError(
                        "No columns or wall geometry found in the DXF file. "
                        "Ensure the file contains LINE/LWPOLYLINE entities on a named layer."
                    )
                
                placer = ColumnPlacer(
                    nodes=self.framer.nodes,
                    centerlines=self.framer.centerlines,
                    seismic_zone=seismic_zone
                )
                placement_result = placer.generate_placement()
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
                auto_frame = True  # Switch flag so beam conversion below uses struct path
                logger.info("Auto-Frame fallback: generated %d columns", len(raw_cols))
        
        if not raw_cols:
            raise ValueError(
                "No structural elements detected. Ensure your DXF has columns on a COLUMN layer "
                "or walls on a WALL/ARCH layer, then re-upload."
            )

        xs = [c['x'] for c in raw_cols]
        ys = [c['y'] for c in raw_cols]
        
        max_coord = max(max(abs(x) for x in xs), max(abs(y) for y in ys)) if xs and ys else 0
        unit_scale = self.parser.get_unit_scale()
        units_known = unit_scale is not None
        extent = max((max(xs) - min(xs)), (max(ys) - min(ys))) if xs and ys else 0.0
        if units_known and extent > 0 and not (1.0 <= extent * unit_scale <= 1000.0):
            # Declared unit contradicts the geometry (e.g. ezdxf default $INSUNITS=6 on a
            # millimetre drawing): fall back to the size heuristic and warn.
            self.load_warnings.append(
                f"DXF $INSUNITS gives a building extent of {extent * unit_scale:.1f} m, which is implausible; "
                f"units were inferred from coordinate size instead. Correct the drawing units.")
            units_known = False
            implausible = True
        else:
            implausible = False
        if units_known:
            self.scale_factor = unit_scale
        else:
            # Unitless drawing: legacy heuristic (|coord| > 500 -> mm), flagged (audit finding R17)
            self.scale_factor = 0.001 if max_coord > 500 else 1.0
        if not units_known and not implausible:
            self.load_warnings.append(
                f"DXF has no $INSUNITS: units guessed as {'millimetres' if self.scale_factor == 0.001 else 'metres'} "
                f"from coordinate size (max {max_coord:.0f}). Set drawing units in the CAD file to avoid scale errors.")
        if auto_frame and self.scale_factor != 0.001:
            self.load_warnings.append("Auto-frame column placement assumes a drawing in millimetres; results for other "
                                      "units are unreliable.")
        
        # Explicit column outlines are in drawing units: convert, then drop shapes that cannot be columns
        if not auto_frame:
            kept, odd = [], []
            for rc in raw_cols:
                w, d = rc['width'] * self.scale_factor, rc['depth'] * self.scale_factor
                (kept if 0.15 <= min(w, d) and max(w, d) <= 3.0 else odd).append(rc)
            if odd:
                self.load_warnings.append(
                    f"{len(odd)} closed outline(s) on column layers are smaller than 150 mm or larger than 3 m and "
                    f"were not used as columns (e.g. {odd[0]['width'] * self.scale_factor * 1000:.0f} x "
                    f"{odd[0]['depth'] * self.scale_factor * 1000:.0f} mm).")
            if not kept:
                raise ValueError("No columns of plausible size (150 mm to 3 m) found on the column layers. "
                                 "Check the drawing units.")
            raw_cols = kept

        # Grid lines: cluster column centres that are within 150 mm (drafting misalignment) onto one line, then move
        # the drawing so that the first grid intersection is the origin (survey / sheet coordinates)
        gx, spread_x = self._cluster([rc['x'] * self.scale_factor for rc in raw_cols])
        gy, spread_y = self._cluster([rc['y'] * self.scale_factor for rc in raw_cols])
        ox, oy = gx[0], gy[0]
        self.origin_m = (ox, oy)
        if math.hypot(ox, oy) > 1.0:
            self.load_warnings.append(f"Drawing coordinates were moved to the origin by ({-ox:.3f}, {-oy:.3f}) m "
                                      f"(the first grid intersection is now 0, 0).")
        unique_x = [round(v - ox, 3) for v in gx]
        unique_y = [round(v - oy, 3) for v in gy]
        spread = max(spread_x, spread_y)
        if spread > 0.005:
            self.load_warnings.append(f"Columns up to {spread * 1000:.0f} mm off a common grid line were aligned to "
                                      f"the grid (lines within 150 mm merged). Check the drawing if this is "
                                      f"not drafting tolerance.")

        width_m = unique_x[-1] - unique_x[0] if unique_x else 0
        length_m = unique_y[-1] - unique_y[0] if unique_y else 0
        
        gm = GridManager(width_m=width_m, length_m=length_m, num_stories=num_stories, story_height_m=story_height_m)
        gm.x_grid_lines = unique_x
        gm.y_grid_lines = unique_y
        
        gm.columns = []
        for rc in raw_cols:
            x_m = rc['x'] * self.scale_factor - ox
            y_m = rc['y'] * self.scale_factor - oy
            
            x_m = self._snap_to_grid(x_m, unique_x, tol=0.15)
            y_m = self._snap_to_grid(y_m, unique_y, tol=0.15)
            
            w_mm = rc.get('width', 300)
            d_mm = rc.get('depth', 300)

            if not auto_frame:
                # explicit column outlines are in drawing units
                w_mm *= self.scale_factor * 1000.0
                d_mm *= self.scale_factor * 1000.0
            elif w_mm < 5.0 and self.scale_factor == 1.0:
                w_mm *= 1000.0
                d_mm *= 1000.0
            
            col = Column(
                id=rc['id'],
                x=x_m,
                y=y_m,
                width_nb=w_mm,
                depth_nb=d_mm,
                level=0,
                z_top=story_height_m
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
                 p1 = Point(x=sb.start_point.x * self.scale_factor - ox, y=sb.start_point.y * self.scale_factor - oy)
                 p2 = Point(x=sb.end_point.x * self.scale_factor - ox, y=sb.end_point.y * self.scale_factor - oy)
                 
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
            # beam ends drawn at the column face (or slightly off) are moved to the column centre
            centres = [(c.x, c.y, max(c.width_nb, c.depth_nb) / 2000.0) for c in gm.columns]

            def snap(px, py):
                best = min(centres, key=lambda c: math.hypot(px - c[0], py - c[1]))
                if math.hypot(px - best[0], py - best[1]) <= best[2] + 0.15:
                    return best[0], best[1], True
                return px, py, False

            loose, seen = 0, set()
            for rb in raw_beams:
                start = rb['start']
                end = rb['end']
                sx, sy, ok1 = snap(start[0] * self.scale_factor - ox, start[1] * self.scale_factor - oy)
                ex, ey, ok2 = snap(end[0] * self.scale_factor - ox, end[1] * self.scale_factor - oy)
                loose += (not ok1) + (not ok2)
                key = tuple(sorted([(round(sx, 3), round(sy, 3)), (round(ex, 3), round(ey, 3))]))
                if key[0] == key[1] or key in seen:
                    continue
                seen.add(key)
                p1 = Point(x=sx, y=sy)
                p2 = Point(x=ex, y=ey)
                
                beams.append(StructuralMember(
                    id=rb['id'],
                    type="beam",
                    start_point=p1,
                    end_point=p2,
                    properties=MemberProperties(width_mm=300, depth_mm=600)
                ))
            
            if loose:
                self.load_warnings.append(f"{loose} beam end(s) in the drawing do not reach a column (beam-on-beam "
                                          f"or drafting gap): check the framing.")

        # ── Extract Walls from DXF and create Wall objects ──
        if self.parser:
            from .grid_manager import Wall
            raw_arch_walls = self.parser.extract_walls_normalized()
            raw_walls_for_thickness = self.parser.extract_walls()
            wall_thickness = self.parser.detect_wall_thickness(raw_walls_for_thickness, unit_m=self.scale_factor)
            
            # Clear height = storey - slab (125) - beam (400): same rule as GridManager.generate_walls
            wall_height = max(gm.story_height_m - 0.125 - 0.400, 0.5)
            
            for wi, wl in enumerate(raw_arch_walls):
                sx = wl[0][0] * self.scale_factor - ox
                sy = wl[0][1] * self.scale_factor - oy
                ex = wl[1][0] * self.scale_factor - ox
                ey = wl[1][1] * self.scale_factor - oy
                
                wall_len = math.hypot(ex - sx, ey - sy)
                if wall_len < 0.3:  # Skip very short segments (< 300mm)
                    continue
                
                gm.walls.append(Wall(
                    id=f"W{wi+1}",
                    start_x=round(sx, 3),
                    start_y=round(sy, 3),
                    end_x=round(ex, 3),
                    end_y=round(ey, 3),
                    thickness_mm=wall_thickness,
                    height_m=wall_height,
                    material="brick",
                    is_load_bearing=True,
                    level=0
                ))
            
            logger.info("Extracted %d wall segments (thickness=%.0fmm)", len(gm.walls), wall_thickness)
            self.load_warnings.extend(self.parser.warnings)

        if not beams:
            self.load_warnings.append("No beams found in the DXF (no BEAM layer): beams will be generated along "
                                      "all column grid lines.")
        
        return gm, beams
    
    def get_placement_json(self) -> str:
        """Returns JSON string of placement result with columns and warnings."""
        import json
        
        return json.dumps({
            "warnings": self.placement_warnings,
            "stats": self.placement_stats
        }, indent=2)

    def get_architectural_walls(self) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
        """Returns the raw architectural walls scaled to meters for visualization overlay."""
        if not self.parser:
            return []
        raw_walls = self.parser.extract_walls_normalized()
        scaled = []
        for w in raw_walls:
            scaled.append((
                (w[0][0] * self.scale_factor, w[0][1] * self.scale_factor),
                (w[1][0] * self.scale_factor, w[1][1] * self.scale_factor)
            ))
        return scaled
