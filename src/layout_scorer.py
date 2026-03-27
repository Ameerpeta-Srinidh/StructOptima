"""
Layout Scorer — Dual-Objective Column Placement Scoring Engine

Scores column placements on two independent axes:
  1. Structural Score (0–100): IS 456 compliance, span safety, tributary balance
  2. Aesthetic Score (0–100): Wall concealability, room centroid avoidance, opening blockage

Used by LayoutOptimizer to find Pareto-optimal column arrangements.
"""

import math
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass, field
from .logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ColumnCandidate:
    """A proposed column position with size."""
    id: str
    x: float  # meters
    y: float  # meters
    width_mm: float = 300.0
    depth_mm: float = 300.0
    is_corner: bool = False
    is_edge: bool = False


@dataclass
class ScoredColumn:
    """A column with both structural and aesthetic scores."""
    column: ColumnCandidate
    structural_score: float = 0.0
    aesthetic_score: float = 0.0
    structural_details: Dict[str, float] = field(default_factory=dict)
    aesthetic_details: Dict[str, float] = field(default_factory=dict)

    @property
    def composite_score(self) -> float:
        return 0.5 * self.structural_score + 0.5 * self.aesthetic_score


@dataclass
class LayoutScore:
    """Aggregate scores for an entire column layout."""
    layout_id: str
    columns: List[ScoredColumn]
    structural_score: float = 0.0
    aesthetic_score: float = 0.0

    @property
    def composite_score(self) -> float:
        return 0.5 * self.structural_score + 0.5 * self.aesthetic_score

    def to_dict(self) -> dict:
        return {
            "layout_id": self.layout_id,
            "structural_score": round(self.structural_score, 1),
            "aesthetic_score": round(self.aesthetic_score, 1),
            "composite_score": round(self.composite_score, 1),
            "num_columns": len(self.columns),
        }


class LayoutScorer:
    """
    Dual-objective scoring engine for column placements.

    Args:
        walls: List of wall centerline segments as ((x1,y1), (x2,y2)) in meters
        max_span_m: Maximum economical span (IS 456 recommendation)
        min_col_size_mm: Minimum column dimension per IS 13920
    """

    def __init__(
        self,
        walls: List[Tuple[Tuple[float, float], Tuple[float, float]]],
        max_span_m: float = 6.0,
        min_col_size_mm: float = 300.0,
    ):
        self.walls = walls
        self.max_span_m = max_span_m
        self.min_col_size_mm = min_col_size_mm
        self._room_polygons: Optional[List[List[Tuple[float, float]]]] = None

    # ------------------------------------------------------------------ #
    #  PUBLIC API                                                         #
    # ------------------------------------------------------------------ #

    def score_layout(self, columns: List[ColumnCandidate], layout_id: str = "L0") -> LayoutScore:
        """Score an entire column layout on both axes."""
        scored = [self._score_column(col, columns) for col in columns]

        struct_avg = sum(sc.structural_score for sc in scored) / max(len(scored), 1)
        aesth_avg = sum(sc.aesthetic_score for sc in scored) / max(len(scored), 1)

        # Global structural bonuses / penalties
        span_penalty = self._global_span_penalty(columns)
        corner_bonus = self._corner_coverage_bonus(columns)
        trib_balance = self._tributary_balance_bonus(columns)

        struct_final = max(0.0, min(100.0, struct_avg + span_penalty + corner_bonus + trib_balance))

        return LayoutScore(
            layout_id=layout_id,
            columns=scored,
            structural_score=round(struct_final, 1),
            aesthetic_score=round(aesth_avg, 1),
        )

    # ------------------------------------------------------------------ #
    #  PER-COLUMN SCORING                                                 #
    # ------------------------------------------------------------------ #

    def _score_column(self, col: ColumnCandidate, all_cols: List[ColumnCandidate]) -> ScoredColumn:
        s_details = {}
        a_details = {}

        # --- Structural sub-scores ---
        # 1. Min size compliance (IS 456 Cl. 25.1.1 / IS 13920)
        min_dim = min(col.width_mm, col.depth_mm)
        size_score = 100.0 if min_dim >= self.min_col_size_mm else (min_dim / self.min_col_size_mm) * 100.0
        s_details["size_compliance"] = round(size_score, 1)

        # 2. Nearest neighbour span check
        nearest_dist = self._nearest_column_dist(col, all_cols)
        if nearest_dist <= self.max_span_m:
            span_score = 100.0
        elif nearest_dist <= self.max_span_m * 1.5:
            span_score = max(0.0, 100.0 - ((nearest_dist - self.max_span_m) / (self.max_span_m * 0.5)) * 80.0)
        else:
            span_score = 0.0
        s_details["span_safety"] = round(span_score, 1)

        # 3. Position type bonus
        pos_score = 100.0 if col.is_corner else (80.0 if col.is_edge else 60.0)
        s_details["position_type"] = round(pos_score, 1)

        structural = 0.4 * size_score + 0.4 * span_score + 0.2 * pos_score

        # --- Aesthetic sub-scores ---
        # 1. Wall concealability (closer to wall = better)
        wall_dist = self._min_wall_distance(col)
        wall_threshold = 0.15  # 150mm — concealable inside 230mm wall
        if wall_dist <= wall_threshold:
            conceal_score = 100.0
        elif wall_dist <= 0.5:
            conceal_score = max(0.0, 100.0 - ((wall_dist - wall_threshold) / 0.35) * 70.0)
        else:
            conceal_score = max(0.0, 30.0 - (wall_dist - 0.5) * 20.0)
        a_details["wall_concealability"] = round(conceal_score, 1)

        # 2. Room centroid avoidance
        centroid_penalty = self._room_centroid_penalty(col)
        centroid_score = max(0.0, 100.0 - centroid_penalty)
        a_details["room_centroid_avoidance"] = round(centroid_score, 1)

        # 3. Opening blockage penalty
        opening_penalty = self._opening_blockage_penalty(col)
        opening_score = max(0.0, 100.0 - opening_penalty)
        a_details["opening_clearance"] = round(opening_score, 1)

        # 4. Grid regularity bonus
        reg_score = self._grid_regularity_score(col, all_cols)
        a_details["grid_regularity"] = round(reg_score, 1)

        aesthetic = 0.35 * conceal_score + 0.25 * centroid_score + 0.20 * opening_score + 0.20 * reg_score

        return ScoredColumn(
            column=col,
            structural_score=round(max(0, min(100, structural)), 1),
            aesthetic_score=round(max(0, min(100, aesthetic)), 1),
            structural_details=s_details,
            aesthetic_details=a_details,
        )

    # ------------------------------------------------------------------ #
    #  STRUCTURAL HELPERS                                                 #
    # ------------------------------------------------------------------ #

    def _nearest_column_dist(self, col: ColumnCandidate, all_cols: List[ColumnCandidate]) -> float:
        """Distance to nearest other column in meters."""
        min_d = float("inf")
        for other in all_cols:
            if other.id == col.id:
                continue
            d = math.hypot(col.x - other.x, col.y - other.y)
            if d < min_d:
                min_d = d
        return min_d

    def _global_span_penalty(self, columns: List[ColumnCandidate]) -> float:
        """Penalize if ANY pair of adjacent columns on the same axis exceeds max span."""
        if len(columns) < 2:
            return -30.0

        xs = sorted(set(round(c.x, 2) for c in columns))
        ys = sorted(set(round(c.y, 2) for c in columns))

        max_gap_x = max((xs[i + 1] - xs[i] for i in range(len(xs) - 1)), default=0)
        max_gap_y = max((ys[i + 1] - ys[i] for i in range(len(ys) - 1)), default=0)
        max_gap = max(max_gap_x, max_gap_y)

        if max_gap <= self.max_span_m:
            return 5.0
        elif max_gap <= self.max_span_m * 1.5:
            return -10.0
        else:
            return -25.0

    def _corner_coverage_bonus(self, columns: List[ColumnCandidate]) -> float:
        """Bonus if all 4 bounding-box corners have a column nearby."""
        if not columns:
            return -20.0

        xs = [c.x for c in columns]
        ys = [c.y for c in columns]
        corners = [
            (min(xs), min(ys)), (min(xs), max(ys)),
            (max(xs), min(ys)), (max(xs), max(ys)),
        ]

        covered = 0
        for cx, cy in corners:
            for c in columns:
                if math.hypot(c.x - cx, c.y - cy) < 0.5:
                    covered += 1
                    break

        return (covered / 4.0) * 10.0

    def _tributary_balance_bonus(self, columns: List[ColumnCandidate]) -> float:
        """Bonus for balanced tributary areas (low variance in nearest-neighbour distances)."""
        if len(columns) < 3:
            return 0.0

        dists = [self._nearest_column_dist(c, columns) for c in columns]
        mean_d = sum(dists) / len(dists)
        variance = sum((d - mean_d) ** 2 for d in dists) / len(dists)
        std_dev = math.sqrt(variance)

        # Lower std_dev = more balanced = more bonus
        if std_dev < 0.5:
            return 5.0
        elif std_dev < 1.5:
            return 2.0
        else:
            return -5.0

    # ------------------------------------------------------------------ #
    #  AESTHETIC HELPERS                                                    #
    # ------------------------------------------------------------------ #

    def _min_wall_distance(self, col: ColumnCandidate) -> float:
        """Minimum perpendicular distance from a column to any wall centerline (meters)."""
        min_d = float("inf")
        for (x1, y1), (x2, y2) in self.walls:
            d = self._point_to_segment_dist(col.x, col.y, x1, y1, x2, y2)
            if d < min_d:
                min_d = d
        return min_d if min_d != float("inf") else 1.0

    def _room_centroid_penalty(self, col: ColumnCandidate) -> float:
        """Penalty if column is near the centroid of any detected room polygon."""
        rooms = self._get_room_polygons()
        if not rooms:
            return 0.0  # No rooms detected → no penalty

        max_penalty = 0.0
        for room in rooms:
            cx, cy = self._polygon_centroid(room)
            dist = math.hypot(col.x - cx, col.y - cy)
            room_radius = self._polygon_radius(room)

            if room_radius < 0.5:
                continue

            # Closer to centroid = higher penalty
            ratio = dist / room_radius
            if ratio < 0.3:
                penalty = 80.0  # Column right in center of room
            elif ratio < 0.5:
                penalty = 50.0
            elif ratio < 0.7:
                penalty = 20.0
            else:
                penalty = 0.0

            max_penalty = max(max_penalty, penalty)

        return max_penalty

    def _opening_blockage_penalty(self, col: ColumnCandidate) -> float:
        """Penalty if column falls in a gap between wall endpoints (possible door/window)."""
        for i, ((x1, y1), (x2, y2)) in enumerate(self.walls):
            for j, ((x3, y3), (x4, y4)) in enumerate(self.walls):
                if j <= i:
                    continue

                # Check if two wall segments share an axis but have a gap (opening)
                # Horizontal walls at same Y
                if abs(y1 - y3) < 0.15 and abs(y2 - y4) < 0.15:
                    gap_start = min(max(x1, x2), max(x3, x4))
                    gap_end = max(min(x1, x2), min(x3, x4))
                    gap_y = (y1 + y3) / 2

                    if gap_end > gap_start:  # There IS a gap
                        gap_width = gap_end - gap_start
                        if 0.6 < gap_width < 2.5:  # Door/window sized
                            if gap_start <= col.x <= gap_end and abs(col.y - gap_y) < 0.3:
                                return 90.0  # Critical — column blocks a doorway

                # Vertical walls at same X
                if abs(x1 - x3) < 0.15 and abs(x2 - x4) < 0.15:
                    gap_start = min(max(y1, y2), max(y3, y4))
                    gap_end = max(min(y1, y2), min(y3, y4))
                    gap_x = (x1 + x3) / 2

                    if gap_end > gap_start:
                        gap_width = gap_end - gap_start
                        if 0.6 < gap_width < 2.5:
                            if gap_start <= col.y <= gap_end and abs(col.x - gap_x) < 0.3:
                                return 90.0

        return 0.0

    def _grid_regularity_score(self, col: ColumnCandidate, all_cols: List[ColumnCandidate]) -> float:
        """Score how well a column aligns with the dominant grid axes."""
        xs = sorted(set(round(c.x, 2) for c in all_cols))
        ys = sorted(set(round(c.y, 2) for c in all_cols))

        on_x_grid = any(abs(col.x - gx) < 0.1 for gx in xs if xs.count(gx) >= 1)
        on_y_grid = any(abs(col.y - gy) < 0.1 for gy in ys if ys.count(gy) >= 1)

        if on_x_grid and on_y_grid:
            return 100.0
        elif on_x_grid or on_y_grid:
            return 60.0
        else:
            return 20.0

    # ------------------------------------------------------------------ #
    #  GEOMETRY UTILITIES                                                  #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _point_to_segment_dist(px, py, x1, y1, x2, y2) -> float:
        """Perpendicular distance from point to line segment."""
        dx, dy = x2 - x1, y2 - y1
        if dx == 0 and dy == 0:
            return math.hypot(px - x1, py - y1)

        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        proj_x = x1 + t * dx
        proj_y = y1 + t * dy
        return math.hypot(px - proj_x, py - proj_y)

    def _get_room_polygons(self) -> List[List[Tuple[float, float]]]:
        """Extract approximate room polygons from wall segments (cached)."""
        if self._room_polygons is not None:
            return self._room_polygons

        self._room_polygons = self._detect_rooms()
        return self._room_polygons

    def _detect_rooms(self) -> List[List[Tuple[float, float]]]:
        """
        Simplified room detection:
        Find axis-aligned rectangular regions bounded by walls on all 4 sides.
        """
        if not self.walls:
            return []

        # Collect all unique X and Y coordinates from wall endpoints
        all_xs = set()
        all_ys = set()
        for (x1, y1), (x2, y2) in self.walls:
            all_xs.update([round(x1, 2), round(x2, 2)])
            all_ys.update([round(y1, 2), round(y2, 2)])

        xs = sorted(all_xs)
        ys = sorted(all_ys)

        rooms = []
        for i in range(len(xs) - 1):
            for j in range(len(ys) - 1):
                x_lo, x_hi = xs[i], xs[i + 1]
                y_lo, y_hi = ys[j], ys[j + 1]

                # Check if this rectangle is bounded by walls on at least 3 sides
                sides_covered = 0
                # Bottom
                if self._wall_covers_segment(x_lo, y_lo, x_hi, y_lo):
                    sides_covered += 1
                # Top
                if self._wall_covers_segment(x_lo, y_hi, x_hi, y_hi):
                    sides_covered += 1
                # Left
                if self._wall_covers_segment(x_lo, y_lo, x_lo, y_hi):
                    sides_covered += 1
                # Right
                if self._wall_covers_segment(x_hi, y_lo, x_hi, y_hi):
                    sides_covered += 1

                area = (x_hi - x_lo) * (y_hi - y_lo)
                if sides_covered >= 3 and area > 2.0:  # At least 2 sq.m
                    rooms.append([(x_lo, y_lo), (x_hi, y_lo), (x_hi, y_hi), (x_lo, y_hi)])

        logger.info("Detected %d room polygons from wall geometry", len(rooms))
        return rooms

    def _wall_covers_segment(self, x1, y1, x2, y2, tol=0.15) -> bool:
        """Check if any wall segment approximately covers the given line."""
        seg_len = math.hypot(x2 - x1, y2 - y1)
        if seg_len < 0.1:
            return False

        for (wx1, wy1), (wx2, wy2) in self.walls:
            # Check if wall is co-linear with segment
            mid_x, mid_y = (x1 + x2) / 2, (y1 + y2) / 2
            dist = self._point_to_segment_dist(mid_x, mid_y, wx1, wy1, wx2, wy2)
            if dist > tol:
                continue

            # Check overlap length
            wall_len = math.hypot(wx2 - wx1, wy2 - wy1)
            if wall_len >= seg_len * 0.5:  # Wall covers at least half the segment
                return True

        return False

    @staticmethod
    def _polygon_centroid(pts: List[Tuple[float, float]]) -> Tuple[float, float]:
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        return cx, cy

    @staticmethod
    def _polygon_radius(pts: List[Tuple[float, float]]) -> float:
        cx, cy = LayoutScorer._polygon_centroid(pts)
        return max(math.hypot(p[0] - cx, p[1] - cy) for p in pts)
