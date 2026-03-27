"""Tests for the Layout Scorer and Optimizer modules."""

import pytest
import math
from src.layout_scorer import LayoutScorer, ColumnCandidate, LayoutScore
from src.layout_optimizer import LayoutOptimizer, OptimizationConfig


# ── Fixtures ─────────────────────────────────────────────


@pytest.fixture
def simple_walls():
    """A 6m x 4m rectangular room with walls on all 4 sides."""
    return [
        ((0, 0), (6, 0)),  # bottom
        ((6, 0), (6, 4)),  # right
        ((6, 4), (0, 4)),  # top
        ((0, 4), (0, 0)),  # left
    ]


@pytest.fixture
def columns_on_walls():
    """Columns placed right on the wall corners/edges (high aesthetic score)."""
    return [
        ColumnCandidate(id="C1", x=0, y=0, is_corner=True),
        ColumnCandidate(id="C2", x=6, y=0, is_corner=True),
        ColumnCandidate(id="C3", x=6, y=4, is_corner=True),
        ColumnCandidate(id="C4", x=0, y=4, is_corner=True),
        ColumnCandidate(id="C5", x=3, y=0, is_edge=True),
    ]


@pytest.fixture
def column_in_center():
    """A column placed right in the center of the room (low aesthetic score)."""
    return [
        ColumnCandidate(id="C1", x=0, y=0, is_corner=True),
        ColumnCandidate(id="C2", x=6, y=0, is_corner=True),
        ColumnCandidate(id="C3", x=6, y=4, is_corner=True),
        ColumnCandidate(id="C4", x=0, y=4, is_corner=True),
        ColumnCandidate(id="C5", x=3, y=2),  # Dead center of room
    ]


# ── Test 1: Structural scoring basics ────────────────────


def test_structural_scoring_valid_layout(simple_walls, columns_on_walls):
    """Columns on corners with valid spans should get high structural scores."""
    scorer = LayoutScorer(walls=simple_walls)
    result = scorer.score_layout(columns_on_walls, "test")

    assert result.structural_score > 50.0, f"Expected >50, got {result.structural_score}"
    assert result.structural_score <= 100.0


# ── Test 2: Aesthetic scoring — wall vs center ───────────


def test_aesthetic_wall_vs_center(simple_walls, columns_on_walls, column_in_center):
    """Columns on walls should score higher aesthetically than columns in room center."""
    scorer = LayoutScorer(walls=simple_walls)

    score_on_walls = scorer.score_layout(columns_on_walls, "on_walls")
    score_in_center = scorer.score_layout(column_in_center, "in_center")

    assert score_on_walls.aesthetic_score > score_in_center.aesthetic_score, (
        f"Wall layout aesthetic ({score_on_walls.aesthetic_score}) should beat "
        f"center layout ({score_in_center.aesthetic_score})"
    )


# ── Test 3: Pareto frontier returns non-dominated ────────


def test_pareto_frontier():
    """Verify the Pareto frontier only contains non-dominated solutions."""
    # Create mock scores
    s1 = LayoutScore(layout_id="A", columns=[], structural_score=80, aesthetic_score=60)
    s2 = LayoutScore(layout_id="B", columns=[], structural_score=70, aesthetic_score=90)
    s3 = LayoutScore(layout_id="C", columns=[], structural_score=60, aesthetic_score=50)  # Dominated by A
    s4 = LayoutScore(layout_id="D", columns=[], structural_score=90, aesthetic_score=40)

    frontier = LayoutOptimizer._pareto_frontier([s1, s2, s3, s4])

    frontier_ids = {s.layout_id for s in frontier}
    assert "C" not in frontier_ids, "C is dominated by A and should not be on frontier"
    assert "A" in frontier_ids
    assert "B" in frontier_ids
    assert "D" in frontier_ids


# ── Test 4: Optimizer generates valid candidates ─────────


def test_optimizer_generates_candidates(simple_walls, columns_on_walls):
    """The optimizer should produce valid layouts with scores."""
    scorer = LayoutScorer(walls=simple_walls)
    optimizer = LayoutOptimizer(
        scorer=scorer,
        baseline_columns=columns_on_walls,
        config=OptimizationConfig(max_candidates=10, top_n=3),
    )

    results = optimizer.optimize()

    assert len(results) > 0, "Optimizer should return at least one layout"
    assert len(results) <= 3, "Should return at most top 3"

    for result in results:
        assert result.structural_score >= 0
        assert result.aesthetic_score >= 0
        assert result.composite_score >= 0
