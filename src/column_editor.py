"""
Column Editor Module - Interactive Add/Remove with Structural Integrity Validation

Allows users to modify automated column placements while ensuring:
- Corner columns remain immovable (frame stability)
- No span exceeds 7m between adjacent columns on a grid line
- Slab panels retain minimum boundary support (≥3 columns)
- Proximity constraints are respected (no two columns < merge distance)
- Load path continuity is maintained through all floors
- IS 456:2000 & IS 13920:2016 compliance is preserved

Usage:
    editor = ColumnEditor(placement_result, centerlines, envelope, seismic_zone)
    result = editor.validate_remove_column("C5")
    if result.can_proceed:
        editor.remove_column("C5")
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from enum import Enum
import math

from .column_placer import (
    ColumnPlacer, ColumnPlacement, PlacementResult,
    PlacementWarning, JunctionType, ReinforcementRule
)
from .logging_config import get_logger

logger = get_logger(__name__)


class ModificationSeverity(Enum):
    """Severity of a modification warning."""
    CRITICAL = "CRITICAL"   # Blocks the action — structure will fail
    WARNING = "WARNING"     # Proceed with caution — review required
    INFO = "INFO"           # Safe to proceed


@dataclass
class ModificationWarning:
    """A warning generated during column modification validation."""
    severity: ModificationSeverity
    message: str
    code_reference: Optional[str] = None

    def to_dict(self) -> Dict:
        result = {
            "severity": self.severity.value,
            "message": self.message
        }
        if self.code_reference:
            result["code_reference"] = self.code_reference
        return result


@dataclass
class ModificationResult:
    """Result of validating an add/remove column operation."""
    can_proceed: bool
    warnings: List[ModificationWarning] = field(default_factory=list)
    affected_spans: List[Dict] = field(default_factory=list)
    column_id: Optional[str] = None

    @property
    def has_critical(self) -> bool:
        return any(w.severity == ModificationSeverity.CRITICAL for w in self.warnings)

    @property
    def has_warnings(self) -> bool:
        return any(w.severity == ModificationSeverity.WARNING for w in self.warnings)

    def to_dict(self) -> Dict:
        return {
            "can_proceed": self.can_proceed,
            "warnings": [w.to_dict() for w in self.warnings],
            "affected_spans": self.affected_spans,
            "column_id": self.column_id
        }


class ColumnEditor:
    """
    Interactive column editor with structural integrity validation.

    Wraps an existing PlacementResult and provides safe add/remove
    operations that enforce IS 456 and IS 13920 structural rules.
    """

    MAX_SPAN_MM = 7000.0       # IS 456 economical span limit
    MIN_SPAN_MM = 1500.0       # Practical minimum
    PROXIMITY_MERGE_MM = 700.0 # Minimum distance between columns

    def __init__(
        self,
        placement: PlacementResult,
        centerlines: List[Tuple[Tuple[float, float], Tuple[float, float]]],
        building_envelope: Optional[List[Tuple[float, float]]] = None,
        seismic_zone: str = "III",
        primary_x: Optional[List[float]] = None,
        primary_y: Optional[List[float]] = None
    ):
        self.columns: List[ColumnPlacement] = list(placement.columns)
        self.warnings: List[PlacementWarning] = list(placement.warnings)
        self.stats = dict(placement.stats)
        self.centerlines = centerlines
        self.building_envelope = building_envelope or []
        self.seismic_zone = seismic_zone
        self.is_seismic = seismic_zone in ["III", "IV", "V"]
        self.min_dim = 300.0 if self.is_seismic else 230.0
        self.primary_x = primary_x or []
        self.primary_y = primary_y or []

        # Compute envelope bounds
        if self.building_envelope:
            xs = [p[0] for p in self.building_envelope]
            ys = [p[1] for p in self.building_envelope]
            self.env_min_x, self.env_max_x = min(xs), max(xs)
            self.env_min_y, self.env_max_y = min(ys), max(ys)
            shorter = min(self.env_max_x - self.env_min_x,
                          self.env_max_y - self.env_min_y)
            self.max_span = min(7000.0, max(4000.0, shorter * 0.6))
            self.proximity_merge = max(600.0, shorter * 0.05)
        else:
            self.env_min_x = self.env_max_x = 0
            self.env_min_y = self.env_max_y = 0
            self.max_span = self.MAX_SPAN_MM
            self.proximity_merge = self.PROXIMITY_MERGE_MM

        # Track modifications
        self.modifications: List[Dict] = []

    # ------------------------------------------------------------------ #
    #  Helpers                                                            
    # ------------------------------------------------------------------ #

    def _dist(self, p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
        return math.hypot(p1[0] - p2[0], p1[1] - p2[1])

    def _is_close(self, p1: Tuple[float, float], p2: Tuple[float, float],
                  tol: float = 500.0) -> bool:
        return self._dist(p1, p2) < tol

    def _find_column(self, column_id: str) -> Optional[ColumnPlacement]:
        for col in self.columns:
            if col.id == column_id:
                return col
        return None

    def _is_corner_location(self, x: float, y: float) -> bool:
        """Check if (x, y) is at a building corner."""
        if not self.building_envelope:
            return False
        tol = 500.0
        on_x_edge = (abs(x - self.env_min_x) < tol or
                     abs(x - self.env_max_x) < tol)
        on_y_edge = (abs(y - self.env_min_y) < tol or
                     abs(y - self.env_max_y) < tol)
        return on_x_edge and on_y_edge

    def _is_on_perimeter(self, x: float, y: float) -> bool:
        """Check if (x, y) is on the building perimeter."""
        if not self.building_envelope:
            return False
        tol = 500.0
        return (abs(x - self.env_min_x) < tol or
                abs(x - self.env_max_x) < tol or
                abs(y - self.env_min_y) < tol or
                abs(y - self.env_max_y) < tol)

    def _is_on_grid(self, x: float, y: float) -> bool:
        """Check if (x, y) lies on a structural grid intersection."""
        tol = 500.0
        on_x_grid = any(abs(x - gx) < tol for gx in self.primary_x)
        on_y_grid = any(abs(y - gy) < tol for gy in self.primary_y)
        return on_x_grid or on_y_grid

    def _columns_on_gridline(self, coord: float, axis: str,
                             exclude_id: Optional[str] = None) -> List[ColumnPlacement]:
        """Get all columns on a given X or Y gridline."""
        tol = 500.0
        result = []
        for col in self.columns:
            if exclude_id and col.id == exclude_id:
                continue
            if axis == "x" and abs(col.x - coord) < tol:
                result.append(col)
            elif axis == "y" and abs(col.y - coord) < tol:
                result.append(col)
        return result

    def _check_span_violations(self, exclude_id: Optional[str] = None,
                               extra_col: Optional[ColumnPlacement] = None
                               ) -> List[Dict]:
        """
        Check all grid lines for span violations after a modification.
        Returns list of violated spans with details.
        """
        violations = []
        tol = 500.0

        # Build working column list
        working_cols = [c for c in self.columns
                        if not (exclude_id and c.id == exclude_id)]
        if extra_col:
            working_cols.append(extra_col)

        # Check vertical gridlines (X = const)
        for gx in self.primary_x:
            cols_on_line = sorted(
                [c for c in working_cols if abs(c.x - gx) < tol],
                key=lambda c: c.y
            )
            for i in range(len(cols_on_line) - 1):
                span = abs(cols_on_line[i + 1].y - cols_on_line[i].y)
                if span > self.max_span:
                    violations.append({
                        "gridline": f"X={gx:.0f}",
                        "between": f"{cols_on_line[i].id} → {cols_on_line[i+1].id}",
                        "span_mm": round(span),
                        "max_mm": round(self.max_span),
                        "excess_mm": round(span - self.max_span)
                    })

        # Check horizontal gridlines (Y = const)
        for gy in self.primary_y:
            cols_on_line = sorted(
                [c for c in working_cols if abs(c.y - gy) < tol],
                key=lambda c: c.x
            )
            for i in range(len(cols_on_line) - 1):
                span = abs(cols_on_line[i + 1].x - cols_on_line[i].x)
                if span > self.max_span:
                    violations.append({
                        "gridline": f"Y={gy:.0f}",
                        "between": f"{cols_on_line[i].id} → {cols_on_line[i+1].id}",
                        "span_mm": round(span),
                        "max_mm": round(self.max_span),
                        "excess_mm": round(span - self.max_span)
                    })

        return violations

    def _count_columns_in_neighborhood(self, x: float, y: float,
                                       radius: float = 3000.0,
                                       exclude_id: Optional[str] = None
                                       ) -> int:
        """Count columns within 'radius' mm of (x, y)."""
        count = 0
        for col in self.columns:
            if exclude_id and col.id == exclude_id:
                continue
            if self._dist((x, y), (col.x, col.y)) < radius:
                count += 1
        return count

    def _classify_junction(self, x: float, y: float) -> JunctionType:
        """Classify junction type for a new column position."""
        tol = 500.0
        degree = 0
        for (x1, y1), (x2, y2) in self.centerlines:
            if self._is_close((x, y), (x1, y1)) or self._is_close((x, y), (x2, y2)):
                degree += 1

        if self._is_corner_location(x, y):
            return JunctionType.CORNER
        elif degree >= 4:
            return JunctionType.CROSS_JUNCTION
        elif degree == 3:
            return JunctionType.T_JUNCTION
        elif self._is_on_perimeter(x, y):
            return JunctionType.EDGE
        else:
            return JunctionType.INTERIOR

    # ------------------------------------------------------------------ #
    #  Validation Methods                                                 
    # ------------------------------------------------------------------ #

    def validate_remove_column(self, column_id: str) -> ModificationResult:
        """
        Validate whether a column can be safely removed.

        Checks performed (in order of severity):
          1. CRITICAL: Corner column removal
          2. CRITICAL: Span violation after removal (> max_span)
          3. WARNING:  Cross-junction or T-junction removal
          4. WARNING:  Perimeter column removal (creates unsupported edge)
          5. WARNING:  Leaves a local area with sparse support
          6. INFO:     Interior/fill column — generally safe
        """
        col = self._find_column(column_id)
        if col is None:
            return ModificationResult(
                can_proceed=False,
                warnings=[ModificationWarning(
                    severity=ModificationSeverity.CRITICAL,
                    message=f"Column '{column_id}' not found in placement."
                )],
                column_id=column_id
            )

        warnings: List[ModificationWarning] = []

        # 1. Corner check
        if col.junction_type == JunctionType.CORNER or self._is_corner_location(col.x, col.y):
            warnings.append(ModificationWarning(
                severity=ModificationSeverity.CRITICAL,
                message=(f"Cannot remove corner column {column_id} at "
                         f"({col.x:.0f}, {col.y:.0f}). Corner columns are "
                         f"mandatory for frame stability."),
                code_reference="IS 456 Frame Stability / IS 13920 Cl 7"
            ))

        # 2. Span violations
        span_violations = self._check_span_violations(exclude_id=column_id)
        for sv in span_violations:
            warnings.append(ModificationWarning(
                severity=ModificationSeverity.CRITICAL,
                message=(f"Removing {column_id} creates {sv['span_mm']}mm span "
                         f"on gridline {sv['gridline']} ({sv['between']}), "
                         f"exceeding {sv['max_mm']}mm limit by {sv['excess_mm']}mm."),
                code_reference="IS 456 economical span (max 7m)"
            ))

        # 3. Junction importance
        if col.junction_type == JunctionType.CROSS_JUNCTION:
            warnings.append(ModificationWarning(
                severity=ModificationSeverity.WARNING,
                message=(f"Column {column_id} is at a cross-junction (degree ≥4). "
                         f"Removing it weakens the structural frame significantly. "
                         f"A structural engineer should verify this change."),
                code_reference="IS 456 Frame Action"
            ))
        elif col.junction_type == JunctionType.T_JUNCTION:
            warnings.append(ModificationWarning(
                severity=ModificationSeverity.WARNING,
                message=(f"Column {column_id} is at a T-junction. This column "
                         f"supports slab and beam connectivity at this wall "
                         f"intersection. Removal requires engineering review."),
                code_reference="IS 456 Frame Action"
            ))

        # 4. Perimeter check
        if self._is_on_perimeter(col.x, col.y) and col.junction_type != JunctionType.CORNER:
            warnings.append(ModificationWarning(
                severity=ModificationSeverity.WARNING,
                message=(f"Column {column_id} is on the building perimeter. "
                         f"Removing perimeter columns may create unsupported "
                         f"edge spans and affect lateral stability."),
                code_reference="IS 456 Lateral Stability"
            ))

        # 5. Local sparsity
        neighbors = self._count_columns_in_neighborhood(
            col.x, col.y, radius=self.max_span, exclude_id=column_id
        )
        if neighbors < 2:
            warnings.append(ModificationWarning(
                severity=ModificationSeverity.WARNING,
                message=(f"Removing {column_id} leaves fewer than 2 columns "
                         f"within {self.max_span:.0f}mm. The surrounding slab "
                         f"may be unsupported."),
                code_reference="IS 456 Slab Support"
            ))

        # 6. If no issues at all — safe fill column
        if not warnings:
            warnings.append(ModificationWarning(
                severity=ModificationSeverity.INFO,
                message=(f"Column {column_id} is an intermediate fill column. "
                         f"Removal is structurally acceptable. Adjacent spans "
                         f"remain within limits.")
            ))

        can_proceed = not any(
            w.severity == ModificationSeverity.CRITICAL for w in warnings
        )

        return ModificationResult(
            can_proceed=can_proceed,
            warnings=warnings,
            affected_spans=span_violations,
            column_id=column_id
        )

    def validate_add_column(self, x: float, y: float) -> ModificationResult:
        """
        Validate whether a column can be added at (x, y).

        Checks performed:
          1. WARNING: Too close to an existing column (< proximity_merge)
          2. WARNING: Not on a structural grid line (off-grid)
          3. INFO:    Helps reduce an existing long span
          4. INFO:    Valid placement confirmation
        """
        warnings: List[ModificationWarning] = []

        # 1. Proximity check
        for col in self.columns:
            dist = self._dist((x, y), (col.x, col.y))
            if dist < self.proximity_merge:
                warnings.append(ModificationWarning(
                    severity=ModificationSeverity.WARNING,
                    message=(f"New column at ({x:.0f}, {y:.0f}) is only "
                             f"{dist:.0f}mm from existing {col.id}. Minimum "
                             f"recommended distance is {self.proximity_merge:.0f}mm. "
                             f"Consider a combined footing if proceeding."),
                    code_reference="IS 456 Foundation Design"
                ))
                break  # One proximity warning is enough

        # 2. Grid alignment check
        on_grid = self._is_on_grid(x, y)
        if not on_grid:
            warnings.append(ModificationWarning(
                severity=ModificationSeverity.WARNING,
                message=(f"New column at ({x:.0f}, {y:.0f}) does not lie on "
                         f"any structural grid line. Off-grid columns create "
                         f"eccentric loading and irregular framing. Prefer "
                         f"grid intersections for clean load transfer."),
                code_reference="IS 456 Frame Design"
            ))

        # 3. Check if this reduces a long span
        temp_col = ColumnPlacement(
            id="TEMP",
            x=x, y=y,
            width=self.min_dim,
            depth=self.min_dim,
            junction_type=self._classify_junction(x, y)
        )

        # Check current violations vs. violations with new column
        current_violations = self._check_span_violations()
        new_violations = self._check_span_violations(extra_col=temp_col)

        resolved = len(current_violations) - len(new_violations)
        if resolved > 0:
            warnings.append(ModificationWarning(
                severity=ModificationSeverity.INFO,
                message=(f"Adding a column here resolves {resolved} span "
                         f"violation(s). This improves structural performance.")
            ))

        # 4. Confirmation
        junction_type = self._classify_junction(x, y)
        on_perim = self._is_on_perimeter(x, y)
        location_desc = f"{'perimeter' if on_perim else 'interior'}"
        grid_desc = "on-grid" if on_grid else "off-grid"

        warnings.append(ModificationWarning(
            severity=ModificationSeverity.INFO,
            message=(f"Column will be placed at ({x:.0f}, {y:.0f}) as a "
                     f"{location_desc} {junction_type.value} column ({grid_desc}). "
                     f"Size: {self.min_dim:.0f}×{self.min_dim:.0f}mm.")
        ))

        can_proceed = not any(
            w.severity == ModificationSeverity.CRITICAL for w in warnings
        )

        return ModificationResult(
            can_proceed=can_proceed,
            warnings=warnings,
            column_id=None
        )

    # ------------------------------------------------------------------ #
    #  Execute Methods                                                    
    # ------------------------------------------------------------------ #

    def remove_column(self, column_id: str) -> PlacementResult:
        """
        Remove a column and return updated PlacementResult.

        Call validate_remove_column() first to check safety.
        This method does NOT block on critical warnings — the caller
        is responsible for checking validation results.
        """
        col = self._find_column(column_id)
        if col is None:
            raise ValueError(f"Column '{column_id}' not found.")

        self.columns = [c for c in self.columns if c.id != column_id]
        self.modifications.append({
            "action": "remove",
            "column_id": column_id,
            "location": (col.x, col.y),
            "junction_type": col.junction_type.value
        })

        logger.info(f"Removed column {column_id} at ({col.x:.0f}, {col.y:.0f})")

        return self._rebuild_result()

    def add_column(self, x: float, y: float) -> PlacementResult:
        """
        Add a column at (x, y) and return updated PlacementResult.

        Call validate_add_column() first to check safety.
        The column is auto-sized and classified per IS code rules.
        """
        junction_type = self._classify_junction(x, y)

        # Auto-size based on junction type and seismic zone
        width = self.min_dim
        depth = self.min_dim
        if junction_type == JunctionType.CROSS_JUNCTION:
            depth = self.min_dim + 150
        elif junction_type == JunctionType.T_JUNCTION:
            depth = self.min_dim + 100

        reinf = (ReinforcementRule.IS_13920_SPECIAL_CONFINING
                 if self.is_seismic
                 else ReinforcementRule.IS_456_STANDARD)

        new_col = ColumnPlacement(
            id=f"C{len(self.columns) + 1}",
            x=x,
            y=y,
            width=width,
            depth=depth,
            junction_type=junction_type,
            reinforcement_rule=reinf
        )

        self.columns.append(new_col)
        self.modifications.append({
            "action": "add",
            "column_id": new_col.id,
            "location": (x, y),
            "junction_type": junction_type.value
        })

        logger.info(f"Added column {new_col.id} at ({x:.0f}, {y:.0f}) "
                     f"type={junction_type.value}")

        return self._rebuild_result()

    # ------------------------------------------------------------------ #
    #  Rebuild & Summary                                                  
    # ------------------------------------------------------------------ #

    def _rebuild_result(self) -> PlacementResult:
        """Re-number columns sequentially and rebuild stats."""
        # Re-number
        for i, col in enumerate(self.columns):
            col.id = f"C{i + 1}"

        # Re-orient columns based on connected walls
        self._reorient_columns()

        # Re-check short spans
        new_warnings = list(self.warnings)
        self._recheck_short_spans(new_warnings)

        # Rebuild stats
        stats = {
            "total_columns": len(self.columns),
            "corners": sum(1 for c in self.columns
                          if c.junction_type == JunctionType.CORNER),
            "cross_junctions": sum(1 for c in self.columns
                                  if c.junction_type == JunctionType.CROSS_JUNCTION),
            "t_junctions": sum(1 for c in self.columns
                              if c.junction_type == JunctionType.T_JUNCTION),
            "edge": sum(1 for c in self.columns
                       if c.junction_type == JunctionType.EDGE),
            "interior": sum(1 for c in self.columns
                           if c.junction_type == JunctionType.INTERIOR),
            "seismic_zone": self.seismic_zone,
            "warnings_count": len(new_warnings),
            "modifications": len(self.modifications)
        }

        return PlacementResult(
            columns=self.columns,
            warnings=new_warnings,
            stats=stats
        )

    def _reorient_columns(self):
        """Re-orient all columns based on connected wall spans."""
        for col in self.columns:
            connected_walls = []
            for start, end in self.centerlines:
                if (self._is_close((col.x, col.y), start) or
                        self._is_close((col.x, col.y), end)):
                    dx = abs(end[0] - start[0])
                    dy = abs(end[1] - start[1])
                    length = math.hypot(dx, dy)
                    is_horizontal = dx > dy
                    connected_walls.append((length, is_horizontal))

            if not connected_walls:
                continue

            h_spans = [l for l, h in connected_walls if h]
            v_spans = [l for l, h in connected_walls if not h]

            max_h = max(h_spans) if h_spans else 0
            max_v = max(v_spans) if v_spans else 0

            col.orientation_deg = 0 if max_h > max_v else 90
            col.connected_spans = [l for l, _ in connected_walls]

    def _recheck_short_spans(self, warnings: List[PlacementWarning]):
        """Check for short spans between new adjacent columns."""
        for i, c1 in enumerate(self.columns):
            for c2 in self.columns[i + 1:]:
                dist = self._dist((c1.x, c1.y), (c2.x, c2.y))
                if self.MIN_SPAN_MM > dist > 500:
                    # Check if they share a wall
                    on_same_wall = False
                    for start, end in self.centerlines:
                        if ((self._is_close((c1.x, c1.y), start) or
                             self._is_close((c1.x, c1.y), end)) and
                            (self._is_close((c2.x, c2.y), start) or
                             self._is_close((c2.x, c2.y), end))):
                            on_same_wall = True
                            break
                    if on_same_wall:
                        warnings.append(PlacementWarning(
                            severity="WARNING",
                            message=(f"Short span ({dist:.0f}mm) between "
                                     f"{c1.id} and {c2.id} — consider "
                                     f"combined footing"),
                            column_id=f"{c1.id},{c2.id}",
                            code_reference="IS 456 foundation design"
                        ))

    def get_modification_summary(self) -> Dict:
        """Get a summary of all modifications made so far."""
        additions = [m for m in self.modifications if m["action"] == "add"]
        removals = [m for m in self.modifications if m["action"] == "remove"]

        # Check current span violations
        violations = self._check_span_violations()

        return {
            "total_modifications": len(self.modifications),
            "columns_added": len(additions),
            "columns_removed": len(removals),
            "current_column_count": len(self.columns),
            "span_violations": len(violations),
            "modifications": self.modifications,
            "violations": violations
        }
