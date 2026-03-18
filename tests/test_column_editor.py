"""
Tests for Column Editor Module

Tests cover:
- Removing a safe interior fill column
- Blocking removal of a corner column
- Detecting span violations after removal
- Adding a column on-grid
- Warning on off-grid or too-close column
- Full add-then-remove roundtrip
- Modification summary tracking
"""

import pytest
from src.column_placer import (
    ColumnPlacer, ColumnPlacement, PlacementResult,
    JunctionType, ReinforcementRule
)
from src.column_editor import (
    ColumnEditor, ModificationSeverity, ModificationResult
)


# ------------------------------------------------------------------ #
#  Fixtures                                                           
# ------------------------------------------------------------------ #

def _make_simple_house():
    """
    Simple 10m × 6m house with one internal wall at x=5000.
    Produces 6 nodes (4 corners + 2 intermediate).
    
    Layout:
        (0,0)-----(5000,0)-----(10000,0)
          |           |             |
          |           |             |
        (0,6000)---(5000,6000)---(10000,6000)
    """
    nodes = [
        (0, 0), (5000, 0), (10000, 0),
        (0, 6000), (5000, 6000), (10000, 6000)
    ]
    centerlines = [
        # Bottom wall
        ((0, 0), (5000, 0)),
        ((5000, 0), (10000, 0)),
        # Right wall
        ((10000, 0), (10000, 6000)),
        # Top wall
        ((10000, 6000), (5000, 6000)),
        ((5000, 6000), (0, 6000)),
        # Left wall
        ((0, 6000), (0, 0)),
        # Internal wall
        ((5000, 0), (5000, 6000))
    ]
    envelope = [(0, 0), (10000, 0), (10000, 6000), (0, 6000)]
    return nodes, centerlines, envelope


def _placement_with_editor(seismic_zone="III"):
    """Generate a placement and wrap it in a ColumnEditor."""
    nodes, centerlines, envelope = _make_simple_house()
    placer = ColumnPlacer(
        nodes=nodes,
        centerlines=centerlines,
        seismic_zone=seismic_zone,
        building_envelope=envelope
    )
    result = placer.generate_placement()
    
    editor = ColumnEditor(
        placement=result,
        centerlines=centerlines,
        building_envelope=envelope,
        seismic_zone=seismic_zone,
        primary_x=placer.primary_x,
        primary_y=placer.primary_y
    )
    return editor, result


# ------------------------------------------------------------------ #
#  Tests: Remove Column                                               
# ------------------------------------------------------------------ #

class TestRemoveColumn:

    def test_remove_nonexistent_column(self):
        """Removing a column that doesn't exist should fail with CRITICAL."""
        editor, _ = _placement_with_editor()
        result = editor.validate_remove_column("C999")
        assert not result.can_proceed
        assert result.has_critical

    def test_remove_corner_column_blocked(self):
        """Corner columns are mandatory — removal must be blocked."""
        editor, placement = _placement_with_editor()

        # Find a corner column
        corner_col = None
        for col in placement.columns:
            if col.junction_type == JunctionType.CORNER:
                corner_col = col
                break

        if corner_col is None:
            pytest.skip("No corner column found in simple house placement")

        result = editor.validate_remove_column(corner_col.id)
        assert not result.can_proceed
        assert result.has_critical
        assert any("corner" in w.message.lower() for w in result.warnings)

    def test_remove_interior_column_safe(self):
        """Removing an interior fill column should generally be safe."""
        editor, placement = _placement_with_editor()

        # Find an interior or edge column that isn't a corner
        target_col = None
        for col in placement.columns:
            if col.junction_type in (JunctionType.INTERIOR, JunctionType.EDGE):
                # Make sure it's not at a corner location
                if not editor._is_corner_location(col.x, col.y):
                    target_col = col
                    break

        if target_col is None:
            pytest.skip("No suitable interior/edge column found")

        result = editor.validate_remove_column(target_col.id)
        # Should either be safe (can_proceed=True) or have only warnings
        # The key check: no CRITICAL from corner protection
        assert not any(
            w.severity == ModificationSeverity.CRITICAL and "corner" in w.message.lower()
            for w in result.warnings
        )

    def test_remove_column_updates_count(self):
        """After removing a column, count decreases by 1."""
        editor, placement = _placement_with_editor()
        original_count = len(placement.columns)

        # Find a removable column
        for col in placement.columns:
            val_result = editor.validate_remove_column(col.id)
            if val_result.can_proceed:
                new_placement = editor.remove_column(col.id)
                assert len(new_placement.columns) == original_count - 1
                return

        pytest.skip("No removable column found in this layout")

    def test_remove_column_renumbers(self):
        """After removal, columns are re-numbered sequentially."""
        editor, placement = _placement_with_editor()

        # Find a removable column
        for col in placement.columns:
            val_result = editor.validate_remove_column(col.id)
            if val_result.can_proceed:
                new_placement = editor.remove_column(col.id)
                ids = [c.id for c in new_placement.columns]
                expected = [f"C{i+1}" for i in range(len(new_placement.columns))]
                assert ids == expected
                return

        pytest.skip("No removable column found")


# ------------------------------------------------------------------ #
#  Tests: Add Column                                                  
# ------------------------------------------------------------------ #

class TestAddColumn:

    def test_add_column_on_grid(self):
        """Adding a column on a grid intersection should succeed."""
        editor, _ = _placement_with_editor()

        # Use a grid coordinate — midpoint of a wall
        result = editor.validate_add_column(2500, 3000)
        # Should not have any CRITICAL warnings
        assert result.can_proceed
        assert not result.has_critical

    def test_add_column_too_close_warns(self):
        """Adding near an existing column produces a proximity warning."""
        editor, placement = _placement_with_editor()

        # Place very close to an existing column
        existing = placement.columns[0]
        result = editor.validate_add_column(existing.x + 200, existing.y + 200)
        
        assert result.has_warnings
        assert any("close" in w.message.lower() or "distance" in w.message.lower()
                    for w in result.warnings
                    if w.severity == ModificationSeverity.WARNING)

    def test_add_column_off_grid_warns(self):
        """Adding a column off-grid produces a warning."""
        editor, _ = _placement_with_editor()

        # Use a clearly off-grid coordinate
        result = editor.validate_add_column(1234, 1234)

        has_grid_warning = any(
            "grid" in w.message.lower()
            for w in result.warnings
            if w.severity == ModificationSeverity.WARNING
        )
        assert has_grid_warning

    def test_add_column_increases_count(self):
        """After adding a column, count increases by 1."""
        editor, placement = _placement_with_editor()
        original_count = len(placement.columns)

        new_placement = editor.add_column(2500, 3000)
        assert len(new_placement.columns) == original_count + 1

    def test_add_column_auto_sizes(self):
        """Added columns should be auto-sized per seismic zone."""
        editor, _ = _placement_with_editor(seismic_zone="IV")

        new_placement = editor.add_column(2500, 3000)
        new_col = new_placement.columns[-1]  # Last added

        assert new_col.width >= 300  # Seismic zone IV minimum
        assert new_col.depth >= 300


# ------------------------------------------------------------------ #
#  Tests: Roundtrip & Summary                                        
# ------------------------------------------------------------------ #

class TestRoundtripAndSummary:

    def test_add_then_remove_roundtrip(self):
        """Adding and then removing returns to original count."""
        editor, placement = _placement_with_editor()
        original_count = len(placement.columns)

        # Add
        new_placement = editor.add_column(2500, 3000)
        assert len(new_placement.columns) == original_count + 1

        # Remove the newly added column (it's the last one after re-numbering)
        new_id = new_placement.columns[-1].id
        final_placement = editor.remove_column(new_id)
        assert len(final_placement.columns) == original_count

    def test_modification_summary_tracks_actions(self):
        """Modification summary accurately tracks all changes."""
        editor, _ = _placement_with_editor()

        editor.add_column(2500, 3000)
        summary = editor.get_modification_summary()

        assert summary["total_modifications"] == 1
        assert summary["columns_added"] == 1
        assert summary["columns_removed"] == 0

    def test_modification_summary_after_remove(self):
        """Summary tracks removals correctly."""
        editor, placement = _placement_with_editor()

        # Add a column first so we have one that's safe to remove
        editor.add_column(2500, 3000)
        # The new column is the last one after re-numbering
        added_id = editor.columns[-1].id
        editor.remove_column(added_id)

        summary = editor.get_modification_summary()
        assert summary["columns_removed"] >= 1


# ------------------------------------------------------------------ #
#  Tests: Span Violation Detection                                    
# ------------------------------------------------------------------ #

class TestSpanViolations:

    def test_span_violation_on_long_layout(self):
        """
        On a long building, removing an intermediate column
        should trigger a span violation warning.
        """
        # 15m × 6m house — needs intermediate columns
        nodes = [
            (0, 0), (7500, 0), (15000, 0),
            (0, 6000), (7500, 6000), (15000, 6000)
        ]
        centerlines = [
            ((0, 0), (7500, 0)),
            ((7500, 0), (15000, 0)),
            ((15000, 0), (15000, 6000)),
            ((15000, 6000), (7500, 6000)),
            ((7500, 6000), (0, 6000)),
            ((0, 6000), (0, 0)),
            ((7500, 0), (7500, 6000))
        ]
        envelope = [(0, 0), (15000, 0), (15000, 6000), (0, 6000)]

        placer = ColumnPlacer(
            nodes=nodes,
            centerlines=centerlines,
            seismic_zone="III",
            building_envelope=envelope
        )
        result = placer.generate_placement()

        editor = ColumnEditor(
            placement=result,
            centerlines=centerlines,
            building_envelope=envelope,
            seismic_zone="III",
            primary_x=placer.primary_x,
            primary_y=placer.primary_y
        )

        # Try removing the middle column at x=7500
        mid_col = None
        for col in result.columns:
            if abs(col.x - 7500) < 500:
                mid_col = col
                break

        if mid_col is None:
            pytest.skip("No mid column found at x=7500")

        val_result = editor.validate_remove_column(mid_col.id)
        # Should have span violation or junction warning
        assert len(val_result.warnings) > 0


class TestRevalidate:

    def test_revalidate_preserves_columns(self):
        """Revalidate should preserve column count."""
        nodes, centerlines, envelope = _make_simple_house()
        placer = ColumnPlacer(
            nodes=nodes,
            centerlines=centerlines,
            seismic_zone="III",
            building_envelope=envelope
        )
        original = placer.generate_placement()

        revalidated = ColumnPlacer.revalidate(
            columns=original.columns,
            centerlines=centerlines,
            seismic_zone="III",
            building_envelope=envelope
        )

        assert len(revalidated.columns) == len(original.columns)
        assert revalidated.stats["total_columns"] == original.stats["total_columns"]
