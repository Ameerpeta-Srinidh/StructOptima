import ezdxf
from typing import Dict, List, Tuple, Optional
import math
import re
from .logging_config import get_logger

logger = get_logger(__name__)

# Layer-name tokens (split on any non-alphanumeric character). Matching whole tokens avoids look-alikes such as
# "COLOR-FILL" or "PROTOCOL"; annotation tokens exclude tag / dimension / hatch layers such as "S-COLS-IDEN".
COLUMN_TOKENS = {"COL", "COLS", "COLM", "COLMN", "COLUMN", "COLUMNS", "PILLAR", "PILLARS", "STANCHION", "STANCHIONS"}
BEAM_TOKENS = {"BEAM", "BEAMS", "BM", "BMS", "GIRDER", "GIRDERS"}
ANNOTATION_TOKENS = {"IDEN", "TEXT", "TXT", "TAG", "TAGS", "DIM", "DIMS", "ANNO", "NOTE", "NOTES", "LABEL", "LABELS",
                     "HATCH", "PATT", "SYMB", "MARK", "MARKS", "NUM", "SCHED", "TITLE"}
MAX_BLOCK_DEPTH = 8


def layer_tokens(name: str) -> List[str]:
    return [t for t in re.split(r"[^A-Z0-9]+", (name or "").upper()) if t]


def is_column_layer(name: str) -> bool:
    t = layer_tokens(name)
    return any(x in COLUMN_TOKENS for x in t) and not any(x in ANNOTATION_TOKENS for x in t)


def is_beam_layer(name: str) -> bool:
    t = layer_tokens(name)
    return any(x in BEAM_TOKENS for x in t) and not any(x in ANNOTATION_TOKENS for x in t)

class _Messages(list):
    """Warnings list that keeps each message once: the extractors are called more than once per load (raw extent
    check, rotation check, the load itself) and used to repeat their warnings."""

    def append(self, msg):
        if msg not in self:
            super().append(msg)


class CADParser:
    """
    Parses DXF files to extract structural geometry.
    """
    def __init__(self, filepath: str, layer_map: Optional[Dict[str, str]] = None,
                 layer_roles: Optional[Dict[str, str]] = None):
        """
        Args:
            filepath: Path to the .dxf file.
            layer_map: Dictionary mapping element types to DXF layer names.
                       Default: {'columns': 'COLUMNS', 'beams': 'BEAMS', 'footings': 'FOOTINGS'}
            layer_roles: layer name -> "column" / "beam" / "wall" / "mixed" / "ignore" confirmed by the engineer;
                       layers not listed are ignored. None: roles suggested by ``dxf_layers.analyse_layers``.
        """
        self.filepath = filepath
        self.layer_roles = dict(layer_roles) if layer_roles is not None else None
        self._roles_cache: Optional[Dict[str, str]] = None
        self._mixed_cache = None
        self.layer_info = []      # dxf_layers.LayerInfo per layer when the roles are suggested
        self.doc = None
        self.msp = None
        self._flat_cache = None
        self.warnings: List[str] = _Messages()   # user-facing parsing warnings (audit finding R17)
        
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
        except (IOError, ezdxf.DXFError, UnicodeDecodeError, ValueError) as first:
            # damaged files: read with the recovery reader, as CAD programs do, and say so; a file that cannot be
            # recovered is an input error the user can fix (never a crash on the page)
            try:
                from ezdxf import recover
                self.doc, auditor = recover.readfile(self.filepath)
            except Exception as e:  # noqa: BLE001 - every reader failure becomes one input message
                logger.error("Unreadable DXF %s: %s / %s", self.filepath, first, e)
                raise ValueError(f"The file could not be read as a DXF drawing ({type(first).__name__}: {first}). "
                                 f"Save it again from the CAD program as DXF and upload it again.") from e
            self.warnings.append(f"The DXF file was damaged ({first}) and was repaired while reading "
                                 f"({len(auditor.fixes)} fix(es), {len(auditor.errors)} error(s)): check the preview "
                                 f"against the drawing.")
        self.msp = self.doc.modelspace()
        self._upright(self.msp)
        logger.info("Loaded %s", self.filepath)

    @staticmethod
    def _upright(entities) -> None:
        """Entities with an inverted extrusion (0, 0, -1) - mirrored blocks, MIRROR in some CAD programs - store
        their points in an object coordinate system whose x runs the other way; the readers use the stored
        coordinates as plan coordinates, so such columns were read mirrored about the origin (corpus seed 17).
        Rewritten as the equivalent entity with extrusion (0, 0, 1)."""
        from ezdxf.upright import upright
        for e in entities:
            ext = e.dxf.get("extrusion", None) if e.dxf.is_supported("extrusion") else None
            if ext is not None and ext[2] < 0:
                try:
                    upright(e)
                except Exception:  # noqa: BLE001 - unsupported type: left as is (not a column / beam / wall type)
                    pass

    # DXF $INSUNITS codes -> metres per drawing unit
    INSUNITS_TO_M = {1: 0.0254, 2: 0.3048, 4: 0.001, 5: 0.01, 6: 1.0}

    def get_unit_scale(self) -> Optional[float]:
        """Metres per drawing unit from the DXF header ($INSUNITS), or None if
        the drawing is unitless / uses an unsupported unit."""
        if not self.doc:
            return None
        try:
            code = int(self.doc.header.get('$INSUNITS', 0))
        except Exception:
            return None
        return self.INSUNITS_TO_M.get(code)

    # Layer-name keywords that never carry structural walls (Tier 2 exclusion)
    NON_WALL_KW = ['DIM', 'TEXT', 'ANNO', 'FURN', 'HATCH', 'TITLE', 'BORDER', 'GRID', 'AXIS', 'DEFPOINTS',
                   'SYMB', 'DOOR', 'WIND', 'LANDSCAPE', 'TREE', 'SANIT', 'ELEC', 'PLUMB', 'NOTE', 'TAG',
                   'LABEL', 'VIEWPORT', 'FIXTURE', 'FIX-']

    def _all_layer_names(self) -> List[str]:
        """Layers declared in the layer table plus layers referenced by
        model-space entities (valid DXFs need not declare every layer)."""
        names = [layer.dxf.name for layer in self.doc.layers]
        seen = set(names)
        for e in self._flat():
            lay = e.dxf.get("layer", "0")
            if lay not in seen:
                seen.add(lay)
                names.append(lay)
        return names

    def _flat(self) -> list:
        """Model-space entities with block references (INSERT) exploded recursively into world coordinates.
        Entities on layer "0" inside a block take the layer of the INSERT, as in AutoCAD. Unbound external
        references cannot be read and are reported."""
        if self._flat_cache is None:
            self._flat_cache = list(self._explode(self.msp, None, 0)) if self.msp is not None else []
        return self._flat_cache

    def _explode(self, entities, parent_layer, depth):
        for e in entities:
            layer = e.dxf.get("layer", "0")
            if layer == "0" and parent_layer:
                layer = parent_layer
            if e.dxftype() != "INSERT":
                if layer != e.dxf.get("layer", "0"):
                    e.dxf.layer = layer
                yield e
                continue
            name = e.dxf.get("name", "")
            block = self.doc.blocks.get(name)
            if block is None:
                self.warnings.append(f"Block '{name}' is referenced but not defined: its contents were not read.")
                continue
            if block.block is not None and (block.block.dxf.get("flags", 0) & 4):
                self.warnings.append(f"External reference '{name}' is not bound: bind the xref in CAD and re-export.")
                continue
            if depth >= MAX_BLOCK_DEPTH:
                self.warnings.append(f"Block '{name}' nested deeper than {MAX_BLOCK_DEPTH} levels: not read.")
                continue
            try:
                virtual = list(e.virtual_entities())
                self._upright(virtual)
            except Exception as ex:   # non-uniform scaling of some entity types etc.
                self.warnings.append(f"Block '{name}' could not be exploded ({ex}): its contents were not read.")
                continue
            yield from self._explode(virtual, layer, depth + 1)

    def roles(self) -> Dict[str, str]:
        """Role of every layer: the confirmed mapping, or the suggestion from names and drawn shapes."""
        if self.layer_roles is not None:
            return self.layer_roles
        if self._roles_cache is None:
            from .dxf_layers import analyse_layers
            self.layer_info = analyse_layers(self)
            self._roles_cache = {i.name: i.role for i in self.layer_info}
        return self._roles_cache

    def role_of(self, layer: str) -> str:
        return self.roles().get(layer, "ignore")

    def _mixed(self) -> Dict[str, list]:
        """Entities of "decide by shape" layers sorted by shape: column outlines, beam segments, wall segments
        (drawing units)."""
        if self._mixed_cache is not None:
            return self._mixed_cache
        out = {"columns": [], "circles": [], "beams": [], "walls": []}
        mixed = {n for n, r in self.roles().items() if r == "mixed"}
        if mixed:
            from .dxf_layers import _Geometry
            g = _Geometry(self)
            centres = []
            for n, d in g.by_layer.items():
                if n in mixed or self.role_of(n) == "column":
                    circles = d["circles"] if self.role_of(n) == "column" else g.framed_circles(d["circles"])
                    for o in [o for o in d["outlines"] if g.column_sized(o)] + circles:
                        centres.append((o["x"], o["y"], 0.5 * max(o["w"], o["d"]), min(o["w"], o["d"])))
            for n in mixed:
                d = g.by_layer.get(n)
                if not d:
                    continue
                out["columns"] += [o for o in d["outlines"] if g.column_sized(o)]
                out["circles"] += g.framed_circles(d["circles"])
                for o in d["outlines"]:
                    if not g.column_sized(o):
                        d["segs"] += list(zip(o["pts"], o["pts"][1:] + o["pts"][:1]))
                kinds = [g.classify_segment(sg, centres) for sg in d["segs"]]
                out["beams"] += [sg for sg, k in zip(d["segs"], kinds) if k == "beam"]
                rest = [sg for sg, k in zip(d["segs"], kinds) if k == "other"]
                paired, _ = g.paired_segments(rest, min_overlap_mm=500.0)   # guessing: ignore tag leaders, ticks
                out["walls"] += [rest[i] for i in sorted(paired)]
        self._mixed_cache = out
        return out

    def _by_type_and_layer(self, dxftype, layer_name):
        """Filter entities directly — avoids ezdxf's query()/pyparsing dependency entirely."""
        return [e for e in self._flat() if e.dxftype() == dxftype and e.dxf.layer == layer_name]

    def _outline(self, entity) -> Optional[List[Tuple[float, float]]]:
        """Vertices of a closed LWPOLYLINE / 2D POLYLINE, or None when the outline is open (leaders, tags)."""
        t = entity.dxftype()
        if t == "LWPOLYLINE":
            pts = [(float(x), float(y)) for x, y in self._lwpoly_xy(entity)]
            closed = bool(getattr(entity, "closed", False))
        elif t == "POLYLINE":
            pts = [(float(v.dxf.location.x), float(v.dxf.location.y)) for v in entity.vertices]
            closed = bool(getattr(entity, "is_closed", False))
        else:
            return None
        if len(pts) < 2:
            return None
        size = math.hypot(max(p[0] for p in pts) - min(p[0] for p in pts), max(p[1] for p in pts) - min(p[1] for p in pts))
        # first == last vertex closes the outline; tolerance relative to the outline (not the coordinates, which
        # can be survey values of millions of units)
        if len(pts) >= 4 and math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) <= 1e-6 * size:
            pts = pts[:-1]
            closed = True
        if not closed or len(pts) < 3:
            return None
        return pts

    @staticmethod
    def _lwpoly_xy(ply) -> List[Tuple[float, float]]:
        """Safe LWPOLYLINE point extractor compatible with ALL ezdxf versions.

        Never uses get_points() because the internal lambda that implements the 
        format filter is broken in several ezdxf builds on python 3.12+.
        Tries 4 progressively safer approaches instead.
        """
        pts = []
        
        # Method 1: direct iteration over the entity (supported in most ezdxf versions)
        try:
            pts = [(pt[0], pt[1]) for pt in ply]
            if pts: return pts
        except Exception:
            pass

        # Method 2: lwpoints stores raw tuples (newer ezdxf)
        try:
            pts = [(pt[0], pt[1]) for pt in ply.lwpoints]
            if pts: return pts
        except Exception:
            pass

        # Method 3: vertices() method (generator in some ezdxf versions)
        try:
            if callable(getattr(ply, 'vertices', None)):
                pts = list(ply.vertices())
                if pts: return pts
        except Exception:
            pass

        # Method 4: iterate vertices directly (very old ezdxf versions)
        try:
            pts = [(v.dxf.location.x, v.dxf.location.y) for v in ply.vertices]
            if pts: return pts
        except Exception:
            pass

        # Method 5: access dxf.points attribute fallback
        try:
            pts = [(p[0], p[1]) for p in ply.dxf.points]
            if pts: return pts
        except Exception:
            pass

        return pts

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
            points = self._lwpoly_xy(entity)
        elif entity.dxftype() == 'POLYLINE':
            points = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
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
            points = self._lwpoly_xy(entity)
         
         if not points:
             return (0.0, 0.0)
         
         xs = [p[0] for p in points]
         ys = [p[1] for p in points]
         
         width = max(xs) - min(xs)
         depth = max(ys) - min(ys)
         return (width, depth)

    def extract_columns(self) -> List[Dict]:
        """Columns on column layers (``is_column_layer``): closed LWPOLYLINE / POLYLINE outlines (directly or inside
        blocks) and circles. Open polylines (leaders) are ignored; duplicate outlines at the same place count once.
        Dimensions are in drawing units; circular columns are given the square of equal area (``shape``)."""
        if not self.msp or not self.doc:
            return []
        found = []
        for o in self._mixed()["columns"]:
            w, d, ang, cx, cy = self._rect_dims(o["pts"])
            found.append({"x": cx, "y": cy, "width": w, "depth": d, "orientation_deg": ang, "shape": "rect"})
        for c in self._mixed()["circles"]:              # circular columns on "decide by shape" layers (D-36)
            side = 0.886 * c["w"]
            found.append({"x": c["x"], "y": c["y"], "width": side, "depth": side, "orientation_deg": 0.0,
                          "shape": "circle", "diameter": c["w"]})
        for e in self._flat():
            if self.role_of(e.dxf.get("layer", "0")) != "column":
                continue
            t = e.dxftype()
            if t in ("LWPOLYLINE", "POLYLINE"):
                pts = self._outline(e)
                if pts is None:
                    continue
                w, d, ang, cx, cy = self._rect_dims(pts)
                found.append({"x": cx, "y": cy, "width": w, "depth": d, "orientation_deg": ang, "shape": "rect"})
            elif t == "CIRCLE":
                r = float(e.dxf.radius)
                side = 2 * r * math.sqrt(math.pi) / 2.0
                found.append({"x": float(e.dxf.center.x), "y": float(e.dxf.center.y), "width": side, "depth": side,
                              "orientation_deg": 0.0, "shape": "circle", "diameter": 2 * r})
        columns, dup = [], 0
        for c in found:
            tol = 0.25 * min(c["width"], c["depth"])
            if any(math.hypot(c["x"] - k["x"], c["y"] - k["y"]) <= tol for k in columns):
                dup += 1
                continue
            columns.append(c)
        if dup:
            self.warnings.append(f"{dup} duplicate column outline(s) at the same position were counted once.")
        n_circ = sum(1 for c in columns if c["shape"] == "circle")
        if n_circ:
            self.warnings.append(f"{n_circ} circular column(s): designed as squares of equal area "
                                 f"(side = 0.886 x diameter). Check circular columns separately.")
        skew = sum(1 for c in columns if abs(((c["orientation_deg"] + 45) % 90) - 45) > 1.0)
        if skew:
            self.warnings.append(f"{skew} column(s) are not parallel to the drawing axes: designed with their "
                                 f"plan dimensions on the main axes. Check the orientation.")
        for i, c in enumerate(columns):
            c["id"] = f"C{i + 1}"
        return columns

    @staticmethod
    def _rect_dims(pts) -> Tuple[float, float, float, float, float]:
        """(width along x, depth along y, orientation deg, centre x, centre y) of a column outline. Uses the frame
        of the longest edge so rotated rectangles give their true sides; at multiples of 90 degrees the sides map
        back to the drawing axes."""
        n = len(pts)
        edges = [(pts[i], pts[(i + 1) % n]) for i in range(n)]
        (x1, y1), (x2, y2) = max(edges, key=lambda e: math.hypot(e[1][0] - e[0][0], e[1][1] - e[0][1]))
        ang = math.atan2(y2 - y1, x2 - x1)
        ca, sa = math.cos(-ang), math.sin(-ang)
        rx = [x * ca - y * sa for x, y in pts]
        ry = [x * sa + y * ca for x, y in pts]
        a, b = max(rx) - min(rx), max(ry) - min(ry)
        mx, my = (max(rx) + min(rx)) / 2, (max(ry) + min(ry)) / 2
        cx, cy = mx * math.cos(ang) - my * math.sin(ang), mx * math.sin(ang) + my * math.cos(ang)
        deg = math.degrees(ang) % 180.0
        if abs(deg - 90.0) < 45.0:      # longest edge closer to the y axis
            return b, a, deg, cx, cy
        return a, b, deg, cx, cy

    def extract_beams(self) -> List[Dict]:
        """Beam centre lines on beam layers (``is_beam_layer``): LINE, and every segment of LWPOLYLINE / POLYLINE,
        directly or inside blocks. Coordinates in drawing units."""
        beams = []
        if not self.msp or not self.doc:
            return []
        for a, b in self._mixed()["beams"]:
            beams.append({"start": (float(a[0]), float(a[1])), "end": (float(b[0]), float(b[1])),
                          "id": f"B{len(beams) + 1}"})
        for e in self._flat():
            if self.role_of(e.dxf.get("layer", "0")) != "beam":
                continue
            t = e.dxftype()
            segs = []
            if t == "LINE":
                segs = [((e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y))]
            elif t in ("LWPOLYLINE", "POLYLINE"):
                if t == "LWPOLYLINE":
                    pts = [(float(x), float(y)) for x, y in self._lwpoly_xy(e)]
                    closed = bool(getattr(e, "closed", False))
                else:
                    pts = [(float(v.dxf.location.x), float(v.dxf.location.y)) for v in e.vertices]
                    closed = bool(getattr(e, "is_closed", False))
                segs = list(zip(pts, pts[1:])) + ([(pts[-1], pts[0])] if closed and len(pts) > 2 else [])
            for a, b in segs:
                if math.hypot(b[0] - a[0], b[1] - a[1]) > 0:
                    beams.append({"start": (float(a[0]), float(a[1])), "end": (float(b[0]), float(b[1])),
                                  "id": f"B{len(beams) + 1}"})
        return beams

    def extract_walls(self) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
        """
        Extracts wall lines using a 3-tier fallback strategy:
          Tier 1: Explicit keyword layer matching (WALL, STRUCT, etc.)
          Tier 2: Fuzzy scan of ALL layers for line geometry
          Tier 3: Geometric detection — find parallel line pairs (walls)
        """
        if not self.msp or not self.doc:
            return []
            
        layer_names = self._all_layer_names()
        wall_layers = [n for n in layer_names if self.role_of(n) == "wall"]
        
        def _get_lines_for_layers(layers_to_check):
            found = []
            for layer in layers_to_check:
                for line in self._by_type_and_layer('LINE', layer):
                    found.append(((line.dxf.start.x, line.dxf.start.y), (line.dxf.end.x, line.dxf.end.y)))
                for ply in self._by_type_and_layer('LWPOLYLINE', layer):
                    points = self._lwpoly_xy(ply)
                    for i in range(len(points) - 1): found.append((points[i], points[i+1]))
                    if ply.is_closed and len(points) > 2: found.append((points[-1], points[0]))
                for ply in self._by_type_and_layer('POLYLINE', layer):
                    points = [(v.dxf.location.x, v.dxf.location.y) for v in ply.vertices]
                    for i in range(len(points) - 1): found.append((points[i], points[i+1]))
                    if ply.is_closed and len(points) > 2: found.append((points[-1], points[0]))
            return found

        # Tier 1: layers read as walls (confirmed by the engineer, or suggested from names and shapes), plus the
        # wall faces of "decide by shape" layers
        walls = _get_lines_for_layers(wall_layers) + [tuple(map(tuple, w)) for w in self._mixed()["walls"]]
        guessed = [i.name for i in self.layer_info if i.role == "wall" and i.confidence == "low"]
        if guessed and walls:
            self.warnings.append(
                f"No layer was recognised as walls: {len(walls)} line segments from layers {sorted(guessed)[:8]} were "
                f"treated as walls. Check the layer list on the Setup page.")
        if walls or self.layer_roles is not None:
            logger.info("Tier 1 wall extraction: %d segments from %d layers", len(walls), len(wall_layers))
            return walls          # a confirmed mapping is used as given: no guessing from other layers
        if any(r in ("column", "mixed") for r in self.roles().values()):
            return walls          # a frame drawing without walls
        
        # Tier 2: scan the remaining layers, excluding annotation / furniture layers
        candidate = [n for n in layer_names if not any(kw in n.upper() for kw in self.NON_WALL_KW)]
        excluded = sorted(set(layer_names) - set(candidate))
        logger.warning("Tier 1 failed. Tier 2: scanning %d layers (excluded: %s).", len(candidate), excluded)
        walls = _get_lines_for_layers(candidate)
        if walls:
            self.warnings.append(
                f"No WALL-type layer found: {len(walls)} line segments from layers {sorted(candidate)[:8]} were treated "
                f"as walls. Check that no non-structural geometry is on these layers.")
            logger.info("Tier 2 wall extraction: %d segments", len(walls))
            return walls

        # Tier 3: Geometric detection — find ANY lines in modelspace
        logger.warning("Tier 2 failed. Tier 3: geometric entity scan.")
        
        # Detect scale
        max_coord = 0
        for entity in self.msp:
            if entity.dxftype() == 'LINE':
                max_coord = max(max_coord, abs(entity.dxf.start.x), abs(entity.dxf.end.x))
        is_mm = max_coord > 300
        min_len = 300.0 if is_mm else 0.3

        walls = []
        for entity in self.msp:
            if entity.dxftype() == 'LINE':
                s = (entity.dxf.start.x, entity.dxf.start.y)
                e = (entity.dxf.end.x, entity.dxf.end.y)
                length = math.hypot(e[0]-s[0], e[1]-s[1])
                if length > min_len:  # Ignore tiny lines (dimensions, hatches)
                    walls.append((s, e))
            elif entity.dxftype() in ('LWPOLYLINE', 'POLYLINE'):
                try:
                    if entity.dxftype() == 'LWPOLYLINE':
                        pts = self._lwpoly_xy(entity)
                    else:
                        pts = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
                    for i in range(len(pts)-1):
                        seg_len = math.hypot(pts[i+1][0]-pts[i][0], pts[i+1][1]-pts[i][1])
                        if seg_len > min_len:
                            walls.append((pts[i], pts[i+1]))
                except Exception:
                    pass

        logger.info("Tier 3 geometric extraction: %d segments", len(walls))
        if walls:
            self.warnings.append(f"Wall layers not identified: {len(walls)} model-space line segments used as walls "
                                 f"(geometric fallback) - verify the wall layout.")
        return walls

    def normalize_to_centerlines(
        self,
        walls: List[Tuple[Tuple[float, float], Tuple[float, float]]],
        thickness_range: Tuple[float, float] = (100.0, 400.0),
        angle_tol_deg: float = 8.0,
        unit_m: Optional[float] = None,
    ) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
        """
        Merges double-wall parallel line pairs into single centerlines.
        
        This is the key normalizer: whether an architect draws walls as
        single lines OR double lines (offset by wall thickness), the output
        is always a clean list of wall centerlines.

        Args:
            walls: Raw wall segments from extract_walls()
            thickness_range: (min, max) perpendicular distance to consider as wall pair (drawing units)
            angle_tol_deg: Max angle difference to treat lines as parallel
            unit_m: metres per drawing unit; None keeps the old guess (coordinates > 500 -> millimetres)
        
        Returns:
            List of centerline segments (merged where pairs found, passthrough for singles)
        """
        if not walls:
            return []

        n = len(walls)
        used = [False] * n
        centerlines = []

        # Precompute wall midpoints and directions
        wall_info = []
        for (sx, sy), (ex, ey) in walls:
            dx, dy = ex - sx, ey - sy
            length = math.hypot(dx, dy)
            mx, my = (sx+ex)/2, (sy+ey)/2
            wall_info.append({
                'dx': dx, 'dy': dy, 'length': length,
                'mx': mx, 'my': my,
            })

        if unit_m:
            min_length = 0.1 / unit_m                     # 100 mm in drawing units
        else:
            max_coord = max(max(abs(p) for seg in walls for pt in seg for p in pt), 1)
            # If coordinates are > 500, they are likely in mm. Otherwise they are in meters.
            min_length = 0.1 if max_coord < 500 else 100

        for i in range(n):
            if used[i]:
                continue
            
            w1 = walls[i]
            info1 = wall_info[i]
            if info1['length'] < min_length:
                used[i] = True
                continue

            best_j = -1
            best_dist = float('inf')
            best_dot = 1.0

            for j in range(i+1, n):
                if used[j]:
                    continue
                
                info2 = wall_info[j]
                if info2['length'] < min_length:
                    continue

                # Check parallelism via angle between direction vectors
                dot = (info1['dx']*info2['dx'] + info1['dy']*info2['dy'])
                denom = info1['length'] * info2['length']
                if denom < 1:
                    continue
                cos_angle = max(-1.0, min(1.0, abs(dot / denom)))
                angle_diff = math.degrees(math.acos(cos_angle))
                
                if angle_diff > angle_tol_deg:
                    continue

                # Check similar length (within 30%)
                len_ratio = min(info1['length'], info2['length']) / max(info1['length'], info2['length'])
                if len_ratio < 0.6:
                    continue

                # Check perpendicular distance between midpoints
                # Project midpoint2 onto the line through wall1
                perp_dist = self._point_to_line_dist(
                    info2['mx'], info2['my'],
                    w1[0][0], w1[0][1], w1[1][0], w1[1][1]
                )

                if thickness_range[0] <= perp_dist <= thickness_range[1]:
                    if perp_dist < best_dist:
                        best_dist = perp_dist
                        best_j = j
                        best_dot = dot

            if best_j >= 0:
                # Merge pair into centerline
                w2 = walls[best_j]
                if best_dot < 0:
                    w2 = (w2[1], w2[0])
                cx1 = (w1[0][0] + w2[0][0]) / 2
                cy1 = (w1[0][1] + w2[0][1]) / 2
                cx2 = (w1[1][0] + w2[1][0]) / 2
                cy2 = (w1[1][1] + w2[1][1]) / 2
                centerlines.append(((cx1, cy1), (cx2, cy2)))
                used[i] = True
                used[best_j] = True
                logger.debug("Merged wall pair (thickness=%.0fmm): [%d]+[%d]", best_dist, i, best_j)
            else:
                # Unpaired wall — treat as single-line centerline
                centerlines.append(w1)
                used[i] = True

        logger.info(
            "Wall normalization: %d raw segments -> %d centerlines (%d pairs merged)",
            n, len(centerlines), n - len(centerlines)
        )
        return centerlines

    def extract_walls_normalized(self) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
        """
        The universal entry point: extract walls and normalize to centerlines.
        
        Works with ANY DXF format:
          - Single-line walls -> passed through
          - Double-line walls -> merged into centerlines
          - Named layers -> detected by keyword
          - Unnamed layers -> detected by geometry
        """
        raw = self.extract_walls()
        if not raw:
            return []
            
        # wall faces 100-500 mm apart, in drawing units ($INSUNITS when plausible; a cm drawing paired nothing
        # under the old mm / m guess and counted every wall twice)
        from .dxf_layers import drawing_unit_m
        unit_m = drawing_unit_m(self)
        thickness = (0.1 / unit_m, 0.5 / unit_m)
        return self.normalize_to_centerlines(raw, thickness_range=thickness, unit_m=unit_m)

    @staticmethod
    def _point_to_line_dist(px, py, x1, y1, x2, y2) -> float:
        """Perpendicular distance from point to infinite line through (x1,y1)-(x2,y2)."""
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        if length < 1e-9:
            return math.hypot(px - x1, py - y1)
        return abs(dy * px - dx * py + x2 * y1 - y2 * x1) / length

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
            
            for line in self._by_type_and_layer('LINE', layer_name):
                start = (line.dxf.start.x, line.dxf.start.y)
                end = (line.dxf.end.x, line.dxf.end.y)
                result[wall_type].append((start, end))
            
            for ply in self._by_type_and_layer('LWPOLYLINE', layer_name):
                points = self._lwpoly_xy(ply)
                for i in range(len(points) - 1):
                    result[wall_type].append((points[i], points[i+1]))
                if ply.is_closed and len(points) > 2:
                    result[wall_type].append((points[-1], points[0]))
        
        return result

    def detect_wall_thickness(self, walls: List[Tuple], unit_m: float = 0.001) -> float:
        """Most frequent gap (mm) between pairs of parallel, overlapping wall lines, measured perpendicular to the
        lines. ``unit_m``: metres per drawing unit. Considers segments of at least 0.1 m and gaps of 75-500 mm
        (brick and block walls); returns 230 mm when no pair qualifies (reported by the loader)."""
        segs = []
        for (a, b) in walls or []:
            ax, ay, bx, by = a[0] * unit_m, a[1] * unit_m, b[0] * unit_m, b[1] * unit_m
            ln = math.hypot(bx - ax, by - ay)
            if ln >= 0.1:
                segs.append((ax, ay, bx, by, ln))
        gaps = []
        for i, (ax, ay, bx, by, ln) in enumerate(segs):
            ux, uy = (bx - ax) / ln, (by - ay) / ln
            for cx, cy, dx, dy, ln2 in segs[i + 1:]:
                if abs(ux * (dy - cy) - uy * (dx - cx)) / ln2 > math.sin(math.radians(2)):
                    continue                                   # not parallel
                gap = abs((cx - ax) * -uy + (cy - ay) * ux)    # perpendicular distance
                if not 0.075 <= gap <= 0.5:
                    continue
                t1, t2 = sorted(((cx - ax) * ux + (cy - ay) * uy, (dx - ax) * ux + (dy - ay) * uy))
                if min(t2, ln) - max(t1, 0.0) < 0.1:         # must overlap along the wall
                    continue
                gaps.append(round(gap * 1000.0 / 5.0) * 5.0)
        if not gaps:
            return 230.0
        return float(max(set(gaps), key=gaps.count))

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
