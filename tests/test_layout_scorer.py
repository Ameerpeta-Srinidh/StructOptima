"""
Comprehensive tests for LayoutScorer and LayoutOptimizer.

Covers:
  - Structural scoring: size compliance, span safety, corner coverage, tributary balance
  - Aesthetic scoring: wall proximity, room centroid, opening blockage, grid regularity
  - Room polygon detection from wall geometry
  - Edge cases: empty inputs, single columns, zero walls
  - Optimizer: candidate generation, Pareto frontier, dominance logic
  - Integration: full pipeline from walls to scored layouts
"""

import pytest
import math
from src.layout_scorer import LayoutScorer, ColumnCandidate, ScoredColumn, LayoutScore
from src.layout_optimizer import LayoutOptimizer, OptimizationConfig


# ── Wall fixtures ────────────────────────────────────────────


@pytest.fixture
def simple_room():
    """A single 6m x 4m room with walls on all 4 sides (meters)."""
    return [
        ((0, 0), (6, 0)),   # bottom
        ((6, 0), (6, 4)),   # right
        ((6, 4), (0, 4)),   # top
        ((0, 4), (0, 0)),   # left
    ]


@pytest.fixture
def two_rooms():
    """Two rooms: 6x4 and 6x4, sharing a wall at x=6."""
    return [
        ((0, 0), (12, 0)),   # bottom
        ((12, 0), (12, 4)),  # right
        ((12, 4), (0, 4)),   # top
        ((0, 4), (0, 0)),    # left
        ((6, 0), (6, 4)),    # internal wall
    ]


@pytest.fixture
def room_with_opening():
    """A room with a doorway gap on the bottom wall (gap from x=2 to x=3.5)."""
    return [
        ((0, 0), (2, 0)),     # bottom-left
        ((3.5, 0), (6, 0)),   # bottom-right (gap = door)
        ((6, 0), (6, 4)),     # right
        ((6, 4), (0, 4)),     # top
        ((0, 4), (0, 0)),     # left
    ]


@pytest.fixture
def corner_columns():
    """4 columns at corners of 6x4 room."""
    return [
        ColumnCandidate(id="C1", x=0, y=0, is_corner=True),
        ColumnCandidate(id="C2", x=6, y=0, is_corner=True),
        ColumnCandidate(id="C3", x=6, y=4, is_corner=True),
        ColumnCandidate(id="C4", x=0, y=4, is_corner=True),
    ]


@pytest.fixture
def columns_with_center():
    """4 corner columns + 1 column in room center."""
    return [
        ColumnCandidate(id="C1", x=0, y=0, is_corner=True),
        ColumnCandidate(id="C2", x=6, y=0, is_corner=True),
        ColumnCandidate(id="C3", x=6, y=4, is_corner=True),
        ColumnCandidate(id="C4", x=0, y=4, is_corner=True),
        ColumnCandidate(id="C5", x=3, y=2),  # Dead center
    ]


@pytest.fixture
def columns_on_wall():
    """4 corner columns + 1 column on a wall centerline."""
    return [
        ColumnCandidate(id="C1", x=0, y=0, is_corner=True),
        ColumnCandidate(id="C2", x=6, y=0, is_corner=True),
        ColumnCandidate(id="C3", x=6, y=4, is_corner=True),
        ColumnCandidate(id="C4", x=0, y=4, is_corner=True),
        ColumnCandidate(id="C5", x=3, y=0, is_edge=True),  # On bottom wall
    ]


# ══════════════════════════════════════════════════════════════
#  STRUCTURAL SCORING TESTS
# ══════════════════════════════════════════════════════════════


class TestStructuralScoring:

    def test_all_corners_covered_bonus(self, simple_room, corner_columns):
        """4/4 corners covered should yield a high corner bonus."""
        scorer = LayoutScorer(walls=simple_room)
        score = scorer.score_layout(corner_columns)
        assert score.structural_score > 50

    def test_undersized_column_penalty(self, simple_room):
        """Column smaller than min 300mm should be penalized."""
        cols = [
            ColumnCandidate(id="C1", x=0, y=0, width_mm=200, depth_mm=200, is_corner=True),
            ColumnCandidate(id="C2", x=6, y=0, is_corner=True),
            ColumnCandidate(id="C3", x=6, y=4, is_corner=True),
            ColumnCandidate(id="C4", x=0, y=4, is_corner=True),
        ]
        scorer = LayoutScorer(walls=simple_room)
        score = scorer.score_layout(cols)
        
        # Find C1's individual score
        c1_scored = [sc for sc in score.columns if sc.column.id == "C1"][0]
        assert c1_scored.structural_details["size_compliance"] < 100

    def test_excessive_span_penalty(self, simple_room):
        """Columns 10m apart should get severe span penalty."""
        cols = [
            ColumnCandidate(id="C1", x=0, y=0, is_corner=True),
            ColumnCandidate(id="C2", x=10, y=0, is_corner=True),
        ]
        scorer = LayoutScorer(walls=simple_room, max_span_m=6.0)
        score = scorer.score_layout(cols)
        # Score should be low due to span > 6m
        assert score.structural_score < 70

    def test_close_spacing_good_score(self, simple_room):
        """Columns 3m apart should get excellent span score."""
        cols = [
            ColumnCandidate(id="C1", x=0, y=0, is_corner=True),
            ColumnCandidate(id="C2", x=3, y=0, is_edge=True),
            ColumnCandidate(id="C3", x=6, y=0, is_corner=True),
            ColumnCandidate(id="C4", x=0, y=4, is_corner=True),
            ColumnCandidate(id="C5", x=3, y=4, is_edge=True),
            ColumnCandidate(id="C6", x=6, y=4, is_corner=True),
        ]
        scorer = LayoutScorer(walls=simple_room)
        score = scorer.score_layout(cols)
        assert score.structural_score > 60

    def test_tributary_balance_bonus(self, simple_room):
        """Evenly spaced columns should get tributary balance bonus."""
        cols = [
            ColumnCandidate(id="C1", x=0, y=0, is_corner=True),
            ColumnCandidate(id="C2", x=3, y=0, is_edge=True),
            ColumnCandidate(id="C3", x=6, y=0, is_corner=True),
            ColumnCandidate(id="C4", x=0, y=4, is_corner=True),
            ColumnCandidate(id="C5", x=3, y=4, is_edge=True),
            ColumnCandidate(id="C6", x=6, y=4, is_corner=True),
        ]
        scorer = LayoutScorer(walls=simple_room)
        bonus = scorer._tributary_balance_bonus(cols)
        # Evenly spaced -> should be positive bonus
        assert bonus >= 0

    def test_single_column_returns_valid_score(self, simple_room):
        """A single column should still produce a valid (low) score."""
        cols = [ColumnCandidate(id="C1", x=3, y=2)]
        scorer = LayoutScorer(walls=simple_room)
        score = scorer.score_layout(cols)
        assert 0 <= score.structural_score <= 100


# ══════════════════════════════════════════════════════════════
#  AESTHETIC SCORING TESTS
# ══════════════════════════════════════════════════════════════


class TestAestheticScoring:

    def test_column_on_wall_high_aesthetic(self, simple_room, columns_on_wall):
        """Column right on a wall should score high aesthetically."""
        scorer = LayoutScorer(walls=simple_room)
        score = scorer.score_layout(columns_on_wall)
        c5 = [sc for sc in score.columns if sc.column.id == "C5"][0]
        assert c5.aesthetic_details["wall_concealability"] == 100.0

    def test_column_in_center_low_aesthetic(self, simple_room, columns_with_center):
        """Column in room center should score low aesthetically."""
        scorer = LayoutScorer(walls=simple_room)
        score = scorer.score_layout(columns_with_center)
        c5 = [sc for sc in score.columns if sc.column.id == "C5"][0]
        # Should have lower wall concealability than on-wall
        assert c5.aesthetic_details["wall_concealability"] < 80

    def test_wall_vs_center_aesthetic_comparison(self, simple_room, columns_on_wall, columns_with_center):
        """On-wall layout should have higher aesthetic score than center layout."""
        scorer = LayoutScorer(walls=simple_room)
        wall_score = scorer.score_layout(columns_on_wall, "wall")
        center_score = scorer.score_layout(columns_with_center, "center")
        assert wall_score.aesthetic_score > center_score.aesthetic_score

    def test_opening_blockage_penalty(self, room_with_opening):
        """Column placed in a doorway opening should get severe penalty."""
        cols = [
            ColumnCandidate(id="C1", x=0, y=0, is_corner=True),
            ColumnCandidate(id="C2", x=6, y=0, is_corner=True),
            ColumnCandidate(id="C3", x=6, y=4, is_corner=True),
            ColumnCandidate(id="C4", x=0, y=4, is_corner=True),
            ColumnCandidate(id="C5", x=2.75, y=0),  # In the doorway!
        ]
        scorer = LayoutScorer(walls=room_with_opening)
        score = scorer.score_layout(cols)
        c5 = [sc for sc in score.columns if sc.column.id == "C5"][0]
        # Opening clearance should be low (blocked a door)
        assert c5.aesthetic_details["opening_clearance"] < 20

    def test_grid_regularity_bonus(self, simple_room):
        """Columns aligned on clean grid axes should score high regularity."""
        cols = [
            ColumnCandidate(id="C1", x=0, y=0, is_corner=True),
            ColumnCandidate(id="C2", x=3, y=0, is_edge=True),
            ColumnCandidate(id="C3", x=6, y=0, is_corner=True),
            ColumnCandidate(id="C4", x=0, y=4, is_corner=True),
            ColumnCandidate(id="C5", x=3, y=4, is_edge=True),
            ColumnCandidate(id="C6", x=6, y=4, is_corner=True),
        ]
        scorer = LayoutScorer(walls=simple_room)
        score = scorer.score_layout(cols)
        for sc in score.columns:
            assert sc.aesthetic_details["grid_regularity"] >= 60


# ══════════════════════════════════════════════════════════════
#  ROOM POLYGON DETECTION
# ══════════════════════════════════════════════════════════════


class TestRoomDetection:

    def test_single_room_detected(self, simple_room):
        """A rectangular 6x4 room should be detected."""
        scorer = LayoutScorer(walls=simple_room)
        rooms = scorer._get_room_polygons()
        assert len(rooms) >= 1

    def test_two_rooms_detected(self, two_rooms):
        """Two adjacent rooms should be detected."""
        scorer = LayoutScorer(walls=two_rooms)
        rooms = scorer._get_room_polygons()
        assert len(rooms) >= 2

    def test_no_walls_no_rooms(self):
        """Empty walls should produce no rooms."""
        scorer = LayoutScorer(walls=[])
        rooms = scorer._get_room_polygons()
        assert len(rooms) == 0

    def test_room_polygon_centroid(self):
        """Verify the centroid calculation."""
        pts = [(0, 0), (6, 0), (6, 4), (0, 4)]
        cx, cy = LayoutScorer._polygon_centroid(pts)
        assert cx == pytest.approx(3.0)
        assert cy == pytest.approx(2.0)

    def test_room_polygon_radius(self):
        """Verify the radius (max distance from centroid to vertex)."""
        pts = [(0, 0), (6, 0), (6, 4), (0, 4)]
        r = LayoutScorer._polygon_radius(pts)
        expected = math.hypot(3, 2)  # Distance from center (3,2) to corner (0,0)
        assert r == pytest.approx(expected, abs=0.01)


# ══════════════════════════════════════════════════════════════
#  LAYOUT SCORE MODEL
# ══════════════════════════════════════════════════════════════


class TestLayoutScoreModel:

    def test_composite_score_calculation(self):
        """Composite = 0.5 * structural + 0.5 * aesthetic."""
        ls = LayoutScore(layout_id="test", columns=[], structural_score=80, aesthetic_score=60)
        assert ls.composite_score == pytest.approx(70.0)

    def test_to_dict(self):
        """Verify dictionary output format."""
        ls = LayoutScore(layout_id="L1", columns=[], structural_score=75.5, aesthetic_score=82.3)
        d = ls.to_dict()
        assert d["layout_id"] == "L1"
        assert d["structural_score"] == 75.5
        assert d["aesthetic_score"] == 82.3
        assert d["num_columns"] == 0

    def test_scored_column_composite(self):
        """ScoredColumn composite should average structural and aesthetic."""
        sc = ScoredColumn(
            column=ColumnCandidate(id="C1", x=0, y=0),
            structural_score=90, aesthetic_score=70
        )
        assert sc.composite_score == pytest.approx(80.0)


# ══════════════════════════════════════════════════════════════
#  OPTIMIZER TESTS
# ══════════════════════════════════════════════════════════════


class TestOptimizerCandidateGeneration:

    def test_all_corners_no_candidates(self, simple_room):
        """If all columns are corners (immovable), no candidates should be generated."""
        cols = [
            ColumnCandidate(id="C1", x=0, y=0, is_corner=True),
            ColumnCandidate(id="C2", x=6, y=0, is_corner=True),
            ColumnCandidate(id="C3", x=6, y=4, is_corner=True),
            ColumnCandidate(id="C4", x=0, y=4, is_corner=True),
        ]
        scorer = LayoutScorer(walls=simple_room)
        optimizer = LayoutOptimizer(scorer, cols, OptimizationConfig(max_candidates=20))
        candidates = optimizer._generate_candidates()
        assert len(candidates) == 0

    def test_movable_column_generates_candidates(self, simple_room):
        """A non-corner column should yield perturbation candidates."""
        cols = [
            ColumnCandidate(id="C1", x=0, y=0, is_corner=True),
            ColumnCandidate(id="C2", x=6, y=0, is_corner=True),
            ColumnCandidate(id="C3", x=6, y=4, is_corner=True),
            ColumnCandidate(id="C4", x=0, y=4, is_corner=True),
            ColumnCandidate(id="C5", x=3, y=2),  # Movable
        ]
        scorer = LayoutScorer(walls=simple_room)
        optimizer = LayoutOptimizer(scorer, cols, OptimizationConfig(max_candidates=20))
        candidates = optimizer._generate_candidates()
        assert len(candidates) > 0
        assert len(candidates) <= 20

    def test_candidate_preserves_corners(self, simple_room):
        """Corner columns should not move in generated candidates."""
        cols = [
            ColumnCandidate(id="C1", x=0, y=0, is_corner=True),
            ColumnCandidate(id="C2", x=6, y=0, is_corner=True),
            ColumnCandidate(id="C3", x=6, y=4, is_corner=True),
            ColumnCandidate(id="C4", x=0, y=4, is_corner=True),
            ColumnCandidate(id="C5", x=3, y=2),
        ]
        scorer = LayoutScorer(walls=simple_room)
        optimizer = LayoutOptimizer(scorer, cols, OptimizationConfig(max_candidates=5))
        candidates = optimizer._generate_candidates()
        
        for candidate in candidates:
            for c in candidate:
                if c.is_corner:
                    # Corner positions should be unchanged
                    original = next(oc for oc in cols if oc.id == c.id)
                    assert c.x == original.x
                    assert c.y == original.y


class TestParetoFrontier:

    def test_dominated_solution_removed(self):
        """A dominated layout should not appear on the Pareto frontier."""
        scores = [
            LayoutScore("A", [], structural_score=90, aesthetic_score=80),
            LayoutScore("B", [], structural_score=70, aesthetic_score=60),  # Dominated by A
        ]
        frontier = LayoutOptimizer._pareto_frontier(scores)
        ids = {s.layout_id for s in frontier}
        assert "A" in ids
        assert "B" not in ids

    def test_non_dominated_solutions_kept(self):
        """Non-dominated layouts should all remain."""
        scores = [
            LayoutScore("A", [], structural_score=90, aesthetic_score=50),
            LayoutScore("B", [], structural_score=50, aesthetic_score=90),
        ]
        frontier = LayoutOptimizer._pareto_frontier(scores)
        assert len(frontier) == 2

    def test_identical_scores_both_kept(self):
        """Two layouts with identical scores are both non-dominated."""
        scores = [
            LayoutScore("A", [], structural_score=80, aesthetic_score=80),
            LayoutScore("B", [], structural_score=80, aesthetic_score=80),
        ]
        frontier = LayoutOptimizer._pareto_frontier(scores)
        assert len(frontier) == 2

    def test_empty_input_returns_empty(self):
        """Empty input produces empty frontier."""
        assert LayoutOptimizer._pareto_frontier([]) == []

    def test_single_input_returns_it(self):
        """Single layout is trivially on the frontier."""
        scores = [LayoutScore("A", [], structural_score=50, aesthetic_score=50)]
        frontier = LayoutOptimizer._pareto_frontier(scores)
        assert len(frontier) == 1

    def test_three_way_dominance_chain(self):
        """A dominates B dominates C — only A should remain."""
        scores = [
            LayoutScore("A", [], structural_score=90, aesthetic_score=90),
            LayoutScore("B", [], structural_score=80, aesthetic_score=80),
            LayoutScore("C", [], structural_score=70, aesthetic_score=70),
        ]
        frontier = LayoutOptimizer._pareto_frontier(scores)
        assert len(frontier) == 1
        assert frontier[0].layout_id == "A"


class TestOptimizerFullPipeline:

    def test_optimize_returns_results(self, simple_room, columns_on_wall):
        """Full optimize() should return at least 1 result."""
        scorer = LayoutScorer(walls=simple_room)
        optimizer = LayoutOptimizer(
            scorer, columns_on_wall,
            OptimizationConfig(max_candidates=10, top_n=3)
        )
        results = optimizer.optimize()
        assert len(results) >= 1
        assert len(results) <= 3

    def test_optimize_scores_valid_range(self, simple_room, columns_on_wall):
        """All scores should be in [0, 100]."""
        scorer = LayoutScorer(walls=simple_room)
        optimizer = LayoutOptimizer(
            scorer, columns_on_wall,
            OptimizationConfig(max_candidates=10, top_n=3)
        )
        results = optimizer.optimize()
        for r in results:
            assert 0 <= r.structural_score <= 100
            assert 0 <= r.aesthetic_score <= 100
            assert 0 <= r.composite_score <= 100

    def test_optimize_sorted_by_composite(self, simple_room, columns_on_wall):
        """Results should be sorted by composite score (descending)."""
        scorer = LayoutScorer(walls=simple_room)
        optimizer = LayoutOptimizer(
            scorer, columns_on_wall,
            OptimizationConfig(max_candidates=15, top_n=3)
        )
        results = optimizer.optimize()
        for i in range(len(results) - 1):
            assert results[i].composite_score >= results[i+1].composite_score

    def test_baseline_always_included(self, simple_room, corner_columns):
        """The baseline layout should always be in the results."""
        scorer = LayoutScorer(walls=simple_room)
        optimizer = LayoutOptimizer(
            scorer, corner_columns,
            OptimizationConfig(max_candidates=5, top_n=3)
        )
        results = optimizer.optimize()
        ids = {r.layout_id for r in results}
        assert "Baseline" in ids


# ══════════════════════════════════════════════════════════════
#  EDGE CASES
# ══════════════════════════════════════════════════════════════


class TestEdgeCases:

    def test_score_empty_layout(self):
        """Scoring zero columns should not crash."""
        scorer = LayoutScorer(walls=[((0,0),(6,0))])
        score = scorer.score_layout([], "empty")
        assert score.structural_score >= 0
        assert score.aesthetic_score >= 0
        assert score.layout_id == "empty"

    def test_score_no_walls(self):
        """Scoring with no walls should still work (wall proximity defaults)."""
        scorer = LayoutScorer(walls=[])
        cols = [ColumnCandidate(id="C1", x=0, y=0)]
        score = scorer.score_layout(cols)
        assert 0 <= score.structural_score <= 100

    def test_nearest_column_dist_single_column(self):
        """Single-column layout should have infinite nearest distance."""
        scorer = LayoutScorer(walls=[])
        cols = [ColumnCandidate(id="C1", x=0, y=0)]
        d = scorer._nearest_column_dist(cols[0], cols)
        assert d == float("inf")

    def test_min_wall_distance_no_walls(self):
        """No walls should return default 1.0m distance."""
        scorer = LayoutScorer(walls=[])
        col = ColumnCandidate(id="C1", x=3, y=2)
        d = scorer._min_wall_distance(col)
        assert d == 1.0
