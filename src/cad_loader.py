from typing import List, Tuple, Dict, Optional
import math
import re
from .cad_parser import CADParser
from .grid_manager import GridManager, Column, MAX_PLAN_EXTENT_M, check_plan_geometry
from .framing_logic import StructuralMember, Point, MemberProperties
from .logging_config import get_logger

logger = get_logger(__name__)

class CADLoader:
    def __init__(self, dxf_path: str, layer_roles: Optional[Dict[str, str]] = None):
        self.parser = CADParser(dxf_path, layer_roles=layer_roles)
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
        self._check_raw_extent()
        self._align_to_axes()

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
        
        unit_scale = self.parser.get_unit_scale()
        units_known = unit_scale is not None
        extent = max((max(xs) - min(xs)), (max(ys) - min(ys))) if xs and ys else 0.0
        if units_known and extent > 0 and not (1.0 <= extent * unit_scale <= MAX_PLAN_EXTENT_M):
            # Declared unit contradicts the geometry (e.g. ezdxf default $INSUNITS=6 on a
            # millimetre drawing): fall back to the size heuristic and warn.
            self.load_warnings.append(
                f"DXF $INSUNITS gives a building extent of {extent * unit_scale:.1f} m, which is implausible; "
                f"units were inferred from the drawing instead. Correct the drawing units.")
            units_known = False
            implausible = True
        else:
            implausible = False
        if units_known:
            self.scale_factor = unit_scale
        else:
            # Unitless or implausible: the unit under which the drawing looks like a building (D-35, one rule shared
            # with the layer analysis in dxf_layers.drawing_unit_m)
            from .dxf_layers import drawing_unit_m
            self.scale_factor = drawing_unit_m(self.parser)
        if not units_known:
            self.load_warnings.append(
                f"Drawing units taken as {getattr(self.parser, 'unit_reason', 'guessed')}. Check the dimensions in the "
                f"preview, and set the drawing units ($INSUNITS) in the CAD file to avoid scale errors.")
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
            if not auto_frame:
                gm.drawn_column_sizes_mm[f"{x_m:.3f},{y_m:.3f}"] = (round(w_mm), round(d_mm))
            
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

            loose, seen, split = 0, set(), 0
            for rb in raw_beams:
                start = rb['start']
                end = rb['end']
                sx, sy, ok1 = snap(start[0] * self.scale_factor - ox, start[1] * self.scale_factor - oy)
                ex, ey, ok2 = snap(end[0] * self.scale_factor - ox, end[1] * self.scale_factor - oy)
                loose += (not ok1) + (not ok2)
                pieces = self._split_at_columns((sx, sy), (ex, ey), centres)
                if len(pieces) > 1:
                    split += 1
                for n, ((ax, ay), (bx, by)) in enumerate(pieces):
                    key = tuple(sorted([(round(ax, 3), round(ay, 3)), (round(bx, 3), round(by, 3))]))
                    if key[0] == key[1] or key in seen:
                        continue
                    seen.add(key)
                    beams.append(StructuralMember(
                        id=rb['id'] if len(pieces) == 1 else f"{rb['id']}-{n + 1}",
                        type="beam",
                        start_point=Point(x=ax, y=ay),
                        end_point=Point(x=bx, y=by),
                        properties=MemberProperties(width_mm=300, depth_mm=600)
                    ))
            if split:
                self.load_warnings.append(f"{split} beam line(s) drawn through intermediate columns were divided into "
                                          f"one beam per span (at the columns they pass through).")
            
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
            self.load_warnings.extend(w for w in self.parser.warnings if w not in self.load_warnings)
            hidden = self.parser.hidden_layer_warning()
            if hidden:
                self.load_warnings.append(hidden)

        if not beams:
            self.load_warnings.append("No beams found in the DXF (no BEAM layer): beams will be generated along "
                                      "all column grid lines.")
        self.load_warnings.extend(self._labels_outside_structure(gm, beams, ox, oy))
        check_plan_geometry(gm, beams)

        return gm, beams

    @staticmethod
    def _split_at_columns(a, b, centres, tol: float = 0.15):
        """A beam line drawn through intermediate columns (one line along a whole grid line) is one beam per span:
        pieces between the column centres lying on it, more than half a column + ``tol`` from its ends (N62: it
        was designed as a single member spanning several bays)."""
        (x1, y1), (x2, y2) = a, b
        ln = math.hypot(x2 - x1, y2 - y1)
        if ln <= 0:
            return [(a, b)]
        ux, uy = (x2 - x1) / ln, (y2 - y1) / ln
        cuts = sorted({round((cx - x1) * ux + (cy - y1) * uy, 6): (cx, cy) for cx, cy, half in centres
                       if abs((cx - x1) * -uy + (cy - y1) * ux) <= tol
                       and half + tol < (cx - x1) * ux + (cy - y1) * uy < ln - half - tol}.items())
        pts = [a] + [c for _, c in cuts] + [b]
        return list(zip(pts, pts[1:]))

    # a plan rotated by less than this is left as drawn (drafting noise; grid clustering absorbs it)
    MIN_ROTATION_DEG = 0.05

    def _non_finite_structural(self) -> int:
        """Entities on column / beam / wall / mixed layers with a NaN or infinite coordinate (the extractors drop a
        NaN line silently: hypot(nan) > 0 is false)."""
        p, n = self.parser, 0
        for e in p._flat():
            if p.role_of(e.dxf.get("layer", "0")) not in ("column", "beam", "wall", "mixed"):
                continue
            t = e.dxftype()
            if t == "LINE":
                vals = [*e.dxf.start, *e.dxf.end]
            elif t == "CIRCLE":
                vals = [*e.dxf.center, e.dxf.radius]
            elif t == "LWPOLYLINE":
                vals = [v for pt in p._lwpoly_xy(e) for v in pt[:2]]
            elif t == "POLYLINE":
                vals = [v for q in e.vertices for v in (q.dxf.location.x, q.dxf.location.y)]
            else:
                continue
            n += not all(math.isfinite(v) for v in vals)
        return n

    def _align_to_axes(self) -> None:
        """A plan drawn rotated (every column outline, or every beam / wall line, at the same angle to the drawing
        axes, other than a multiple of 90 degrees) is rotated back so that its grid runs along X and Y (D-34). The
        frames, grid lines and member orientations of the design assume an orthogonal grid; read as drawn, a rotated
        plan gave every column its own grid line and diagonal beams outside every frame. Plans whose members run in
        several unrelated directions are not rotated (warned by the parser)."""
        theta = self._plan_rotation_deg()
        if theta is None or abs(theta) < self.MIN_ROTATION_DEG:
            return
        from ezdxf.math import Matrix44
        m = Matrix44.z_rotate(math.radians(-theta))
        failed = []
        for e in self.parser.msp:
            try:
                e.transform(m)
            except Exception:  # noqa: BLE001 - entity types without a transformation (proxies) are reported
                failed.append(e)
        self.parser._flat_cache = None
        self.parser._mixed_cache = None
        structural = [e for e in failed if self.parser.role_of(e.dxf.get("layer", "0")) in ("column", "beam", "wall")]
        if structural:
            raise ValueError(f"The drawing is rotated by {theta:.2f} degrees and {len(structural)} structural "
                             f"entit(y/ies) ({structural[0].dxftype()}) could not be rotated back to the axes. "
                             f"Explode them or draw the plan parallel to the axes.")
        self.load_warnings.append(
            f"The plan is drawn rotated by {theta:.2f} degrees: it was rotated back so that the grid runs along X and "
            f"Y. Coordinates, grid lines and directions in the results refer to the rotated plan.")

    def _plan_rotation_deg(self):
        """Common angle (degrees, -45 .. 45) of the structure to the drawing axes, or None without a consensus.
        Column outlines decide when there are at least two rectangular ones (75 % within 0.5 degrees of their
        median); otherwise beam lines, then wall lines (length-weighted mean of 4 x angle, resultant >= 0.95)."""
        p = self.parser
        n_warn = len(p.warnings)
        try:
            cols = [c for c in p.extract_columns() if c.get("shape") == "rect"]
            if len(cols) >= 2:
                a = sorted(((c["orientation_deg"] + 45.0) % 90.0) - 45.0 for c in cols)
                med = a[len(a) // 2]
                near = sum(1 for v in a if abs(((v - med + 45.0) % 90.0) - 45.0) <= 0.5)
                return med if near >= 0.75 * len(a) else None
            segs = [(b["start"], b["end"]) for b in p.extract_beams()] or list(p.extract_walls())
        finally:
            del p.warnings[n_warn:]                      # re-read after the rotation; keep no stale warnings
        sx = sy = w = 0.0
        for (x1, y1), (x2, y2) in segs:
            ln = math.hypot(x2 - x1, y2 - y1)
            if ln <= 0:
                continue
            t = 4.0 * math.atan2(y2 - y1, x2 - x1)
            sx, sy, w = sx + ln * math.cos(t), sy + ln * math.sin(t), w + ln
        if w <= 0 or math.hypot(sx, sy) / w < 0.95:
            return None
        return math.degrees(math.atan2(sy, sx)) / 4.0

    # smallest length unit a drawing is read in (millimetres, CADParser.INSUNITS_TO_M / the size heuristic)
    MIN_UNIT_M = 0.001

    def _check_raw_extent(self) -> None:
        """Before any framing: every column / beam / wall coordinate is finite, and the geometry spans no more than
        MAX_PLAN_EXTENT_M even if the drawing is in millimetres (the units are not known yet). The auto-framer puts a
        node every 5 m along each wall: a stray line 10^11 units long made 3 x 10^8 nodes and exhausted the memory."""
        p = self.parser
        n_warn = len(p.warnings)
        try:
            pts = [(c["x"], c["y"]) for c in p.extract_columns()]
            pts += [pt for b in p.extract_beams() for pt in (b["start"], b["end"])]
            pts += [tuple(pt) for seg in p.extract_walls() for pt in seg]
        finally:
            del p.warnings[n_warn:]                      # the load reads them again (after any rotation)
        bad = self._non_finite_structural()
        if bad:
            raise ValueError(f"The drawing has {bad} column, beam or wall entit{'y' if bad == 1 else 'ies'} with an "
                             f"invalid (infinite or undefined) coordinate: the file is damaged. Save it again from the "
                             f"CAD program.")
        if not pts:
            return
        if not all(math.isfinite(v) for pt in pts for v in pt[:2]):
            raise ValueError("The drawing has a column, beam or wall with an invalid (infinite or undefined) "
                             "coordinate: the file is damaged. Save it again from the CAD program.")
        extent = max(max(pt[i] for pt in pts) - min(pt[i] for pt in pts) for i in (0, 1))
        if extent * self.MIN_UNIT_M > MAX_PLAN_EXTENT_M:
            raise ValueError(
                f"The columns, beams and walls in the drawing span {extent:.3g} drawing units: more than "
                f"{MAX_PLAN_EXTENT_M:.0f} m even if the drawing is in millimetres. A line is probably drawn far "
                f"from the building (or has a damaged coordinate): zoom to the drawing extents in the CAD program, "
                f"remove it and upload the drawing again.")

    ROOM_LABEL = re.compile(r"^(?=(?:.*[A-Za-z]){3})[A-Za-z][A-Za-z0-9 .&/'()-]*$")
    COLUMN_MARK = re.compile(r"^(C|COL|P)[-_ ]?\d+[A-Z]?$", re.I)

    def _labels_outside_structure(self, gm, beams, ox, oy) -> List[str]:
        """Room names inside the plan extent but in no slab panel: the area is drawn and named, but no structure
        was read around it (its columns / beams may be on a layer that was not read)."""
        from .dxf_layers import entity_text
        cols = [c for c in gm.columns if c.level == 0]
        if len(cols) < 3:
            return []
        x0, x1 = min(c.x for c in cols), max(c.x for c in cols)
        y0, y1 = min(c.y for c in cols), max(c.y for c in cols)
        saved = gm.boundary_segments
        gm.boundary_segments = [((b.start_point.x, b.start_point.y), (b.end_point.x, b.end_point.y)) for b in beams]
        try:
            panels = gm.slab_panels(include_voids=True)
        finally:
            gm.boundary_segments = saved
        out = []
        for e in self.parser._flat():
            txt = entity_text(e)
            if not txt or not self.ROOM_LABEL.match(txt) or self.COLUMN_MARK.match(txt):
                continue
            try:
                p = e.dxf.insert
            except AttributeError:
                continue
            x, y = p.x * self.scale_factor - ox, p.y * self.scale_factor - oy
            if not (x0 + 0.3 < x < x1 - 0.3 and y0 + 0.3 < y < y1 - 0.3):
                continue                      # title block, entry notes, labels outside the plan
            if any(pn["x0"] <= x <= pn["x1"] and pn["y0"] <= y <= pn["y1"] for pn in panels):
                continue
            out.append(f"Text '{txt}' at ({x:.2f}, {y:.2f}) m is inside the plan but outside the structure read "
                       f"from the drawing (no slab panel there). If that area is part of the building, its columns "
                       f"or beams are on a layer that was not read: check the layer list.")
        return out

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
