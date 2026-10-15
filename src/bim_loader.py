"""
IFC import (IfcBuildingStorey / IfcColumn / IfcBeam with IfcExtrudedAreaSolid
and IfcRectangleProfileDef).

Rewritten in the 2026-10 remediation (audit finding R14).  Behaviour:
  * Length unit scale read from the IFC project (ifcopenshell.util.unit).
  * Column base = object placement origin; height = extrusion depth.
  * Beam axis = object placement x extrusion position x extruded direction.
  * Plan coordinates shifted so the minimum column x / y is 0.
  * Beams are de-duplicated by plan position: the design pipeline assumes the
    same beam layout on every storey (limitation).
  * Non-rectangular profiles fall back to 300 x 300 mm columns / 230 x 450 mm
    beams with a warning.
"""

import math
from typing import List, Optional, Tuple

import numpy as np
import ifcopenshell
import ifcopenshell.util.element
import ifcopenshell.util.placement
import ifcopenshell.util.unit

from .framing_logic import MemberProperties, Point, StructuralMember
from .grid_manager import Column, GridManager
from .logging_config import get_logger

logger = get_logger(__name__)


class BIMLoader:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.model = ifcopenshell.open(file_path)
        self.gm: Optional[GridManager] = None
        self.beams: List[StructuralMember] = []
        self.warnings: List[str] = []
        try:
            self.unit = float(ifcopenshell.util.unit.calculate_unit_scale(self.model))  # metres per file unit
        except Exception:
            self.unit = 1.0
            self.warnings.append("IFC length unit could not be read - metres assumed")

    # ---------------------------------------------------------- helpers --
    def _placement(self, elem) -> np.ndarray:
        return ifcopenshell.util.placement.get_local_placement(elem.ObjectPlacement)

    def _solid(self, elem):
        rep = getattr(elem, "Representation", None)
        if not rep:
            return None
        for r in rep.Representations:
            for item in r.Items:
                if item.is_a("IfcExtrudedAreaSolid"):
                    return item
                if item.is_a("IfcMappedItem"):
                    for sub in item.MappingSource.MappedRepresentation.Items:
                        if sub.is_a("IfcExtrudedAreaSolid"):
                            return sub
        return None

    def _profile_mm(self, solid, default: Tuple[float, float], kind: str, name: str) -> Tuple[float, float]:
        if solid is not None and solid.SweptArea.is_a("IfcRectangleProfileDef"):
            p = solid.SweptArea
            return round(p.XDim * self.unit * 1000.0 / 5.0) * 5.0, round(p.YDim * self.unit * 1000.0 / 5.0) * 5.0
        self.warnings.append(f"{kind} {name}: non-rectangular or missing profile - {default[0]:.0f}x{default[1]:.0f} mm assumed")
        return default

    def _axis(self, elem, solid) -> Tuple[np.ndarray, np.ndarray, float]:
        """(start point m, unit direction, length m) of the extrusion in world coordinates."""
        M = self._placement(elem)
        if solid is None:
            return M[:3, 3] * self.unit, M[:3, 2], 0.0
        P = ifcopenshell.util.placement.get_axis2placement(solid.Position) if solid.Position else np.eye(4)
        W = M @ P
        d = np.array(solid.ExtrudedDirection.DirectionRatios, dtype=float)
        direction = W[:3, :3] @ d
        direction = direction / (np.linalg.norm(direction) or 1.0)
        return W[:3, 3] * self.unit, direction, float(solid.Depth) * self.unit

    # ------------------------------------------------------------- main --
    def load_grid_manager(self) -> Tuple[GridManager, List[StructuralMember]]:
        logger.info("Loading IFC: %s", self.file_path)
        storeys = self.model.by_type("IfcBuildingStorey")
        storeys.sort(key=lambda s: self._placement(s)[2, 3])
        elev = [self._placement(s)[2, 3] * self.unit for s in storeys]
        n = max(len(storeys), 1)
        if len(storeys) > 1:
            h = (elev[-1] - elev[0]) / (len(storeys) - 1)
        else:
            h = 3.0
        if h < 1.0:
            self.warnings.append(f"Derived storey height {h:.2f} m implausible - 3.0 m used")
            h = 3.0

        raw_cols, raw_beams = [], []
        for i, storey in enumerate(storeys):
            for elem in ifcopenshell.util.element.get_decomposition(storey):
                if elem.is_a("IfcColumn"):
                    solid = self._solid(elem)
                    origin, direction, depth = self._axis(elem, solid)
                    base = self._placement(elem)[:3, 3] * self.unit
                    w, d = self._profile_mm(solid, (300.0, 300.0), "Column", elem.GlobalId[:8])
                    raw_cols.append((elem, i, base, depth if depth > 0 else h, w, d))
                elif elem.is_a("IfcBeam"):
                    solid = self._solid(elem)
                    origin, direction, length = self._axis(elem, solid)
                    if length <= 0:
                        self.warnings.append(f"Beam {elem.GlobalId[:8]}: no extruded body - skipped")
                        continue
                    if abs(direction[2]) > 0.2:
                        self.warnings.append(f"Beam {elem.GlobalId[:8]}: inclined member skipped")
                        continue
                    w, d = self._profile_mm(solid, (230.0, 450.0), "Beam", elem.GlobalId[:8])
                    raw_beams.append((elem, origin, origin + direction * length, w, d))

        if not raw_cols:
            raise ValueError("No IfcColumn elements found in IFC storeys")
        x0 = min(c[2][0] for c in raw_cols)
        y0 = min(c[2][1] for c in raw_cols)
        z0 = min(c[2][2] for c in raw_cols)

        cols: List[Column] = []
        for elem, lvl, base, height, w, d in raw_cols:
            zb = base[2] - z0
            cols.append(Column(id=f"C_IFC_{elem.GlobalId[:6]}_L{lvl}", x=round(base[0] - x0, 3), y=round(base[1] - y0, 3),
                               level=lvl, z_bottom=zb, z_top=zb + height, width_nb=w, depth_nb=d))
        xs = sorted({round(c.x, 2) for c in cols})
        ys = sorted({round(c.y, 2) for c in cols})
        gm = GridManager(width_m=max(xs[-1] - xs[0], 0.1), length_m=max(ys[-1] - ys[0], 0.1),
                         num_stories=n, story_height_m=h)
        gm.x_grid_lines, gm.y_grid_lines = xs, ys
        gm.columns = cols

        plan = {}
        for elem, p1, p2, w, d in raw_beams:
            a = (round(p1[0] - x0, 2), round(p1[1] - y0, 2))
            b = (round(p2[0] - x0, 2), round(p2[1] - y0, 2))
            key = tuple(sorted([a, b]))
            if key in plan or a == b:
                continue
            plan[key] = StructuralMember(id=f"B_IFC_{elem.GlobalId[:6]}", type="beam",
                                         start_point=Point(x=key[0][0], y=key[0][1]),
                                         end_point=Point(x=key[1][0], y=key[1][1]),
                                         properties=MemberProperties(width_mm=w, depth_mm=d))
        beams = list(plan.values())
        if raw_beams and len(beams) < len(raw_beams):
            self.warnings.append("Beams de-duplicated by plan position: the same beam layout is assumed on every storey")
        self.gm, self.beams = gm, beams
        logger.info("Extracted %d columns and %d plan beams (unit scale %.4f m).", len(cols), len(beams), self.unit)
        return gm, beams
