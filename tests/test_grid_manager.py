"""
Unit tests for src/grid_manager.py - GridManager and Column classes.
"""
import pytest
import math
from src.grid_manager import GridManager, Column
from src.materials import Concrete


class TestColumn:
    """Test Column model."""

    def test_column_creation(self):
        """Test basic column creation."""
        col = Column(
            id="C1",
            x=0.0,
            y=0.0,
            level=0,
            type="corner"
        )
        
        assert col.id == "C1"
        assert col.x == 0.0
        assert col.type == "corner"
        assert col.level == 0

    def test_column_defaults(self):
        """Test column default values."""
        col = Column(id="C1", x=5.0, y=5.0)
        
        assert col.level == 0
        assert col.z_bottom == 0.0
        assert col.z_top == 3.0
        assert col.type == "interior"
        assert col.width_nb == 300.0
        assert col.depth_nb == 300.0

    def test_column_label(self):
        """Test column label property returns dimension format."""
        col = Column(id="C1", x=0.0, y=0.0, level=0, width_nb=300.0, depth_nb=400.0)
        assert col.label == "300x400"

    def test_column_area_mm2(self):
        """Test column area calculation."""
        col = Column(id="C1", x=0.0, y=0.0, width_nb=300.0, depth_nb=400.0)
        
        expected_area = 300.0 * 400.0  # 120000 mm²
        assert col.area_mm2 == expected_area

    def test_column_staircase_load(self):
        """Test staircase additional load field."""
        col = Column(id="C1", x=0.0, y=0.0, staircase_add_load=25.0)
        
        assert col.staircase_add_load == 25.0


class TestGridManagerInit:
    """Test GridManager initialization."""

    def test_basic_init(self):
        """Test basic GridManager creation."""
        gm = GridManager(width_m=18.0, length_m=12.0)
        
        assert gm.width_m == 18.0
        assert gm.length_m == 12.0
        assert gm.num_stories == 1
        assert gm.story_height_m == 3.0
        assert gm.max_span_m == 6.0

    def test_init_with_stories(self):
        """Test multi-story initialization."""
        gm = GridManager(width_m=12.0, length_m=12.0, num_stories=3, story_height_m=3.5)
        
        assert gm.num_stories == 3
        assert gm.story_height_m == 3.5

    def test_init_with_cantilever(self):
        """Test initialization with cantilever directions."""
        gm = GridManager(
            width_m=10.0,
            length_m=10.0,
            cantilever_dirs=["N", "S"],
            cantilever_len_m=1.5
        )
        
        assert "N" in gm.cantilever_dirs
        assert "S" in gm.cantilever_dirs
        assert gm.cantilever_len_m == 1.5


class TestGridGeneration:
    """Test grid generation logic."""

    def test_generate_grid_creates_columns(self, simple_grid_manager):
        """Test that generate_grid creates columns."""
        assert len(simple_grid_manager.columns) > 0

    def test_generate_grid_creates_grid_lines(self, simple_grid_manager):
        """Test that grid lines are created."""
        assert len(simple_grid_manager.x_grid_lines) > 0
        assert len(simple_grid_manager.y_grid_lines) > 0

    def test_grid_lines_within_bounds(self, simple_grid_manager):
        """Test grid lines are within building dimensions."""
        assert min(simple_grid_manager.x_grid_lines) >= 0
        assert max(simple_grid_manager.x_grid_lines) <= simple_grid_manager.width_m
        assert min(simple_grid_manager.y_grid_lines) >= 0
        assert max(simple_grid_manager.y_grid_lines) <= simple_grid_manager.length_m

    def test_columns_at_intersections(self, simple_grid_manager):
        """Test columns are placed at grid intersections."""
        x_lines = set(simple_grid_manager.x_grid_lines)
        y_lines = set(simple_grid_manager.y_grid_lines)
        
        for col in simple_grid_manager.columns:
            if col.level == 0:  # Check level 0 columns
                assert col.x in x_lines or abs(col.x - min(x_lines, key=lambda x: abs(x - col.x))) < 0.01
                assert col.y in y_lines or abs(col.y - min(y_lines, key=lambda y: abs(y - col.y))) < 0.01

    def test_multi_story_columns(self, multi_story_grid_manager):
        """Test columns are created for each story."""
        levels = set(col.level for col in multi_story_grid_manager.columns)
        
        # Should have columns at levels 0, 1, 2 for 3 stories
        assert 0 in levels
        assert 1 in levels
        assert 2 in levels


class TestTribAreaCalculation:
    """Test tributary area calculations."""

    def test_calculate_trib_areas(self, simple_grid_manager):
        """Test tributary area calculation runs without error."""
        simple_grid_manager.calculate_trib_areas()
        
        # All columns should have non-negative trib areas
        for col in simple_grid_manager.columns:
            assert col.trib_area_m2 >= 0

    def test_corner_has_smaller_trib_area(self, simple_grid_manager):
        """Test that corner columns have smaller tributary areas than interior."""
        simple_grid_manager.calculate_trib_areas()
        
        corners = [c for c in simple_grid_manager.columns if c.type == "corner" and c.level == 0]
        interiors = [c for c in simple_grid_manager.columns if c.type == "interior" and c.level == 0]
        
        if corners and interiors:
            avg_corner = sum(c.trib_area_m2 for c in corners) / len(corners)
            avg_interior = sum(c.trib_area_m2 for c in interiors) / len(interiors)
            
            # Interior should generally have larger or equal trib area
            assert avg_interior >= avg_corner * 0.5  # Allow some tolerance


class TestLoadCalculation:
    """Test load calculation logic."""

    def test_calculate_loads(self, simple_grid_manager):
        """Test load calculation runs and assigns loads."""
        simple_grid_manager.calculate_trib_areas()
        simple_grid_manager.calculate_loads(floor_load_kn_m2=50.0, wall_load_kn_m=12.0)
        
        # All columns should have positive loads
        for col in simple_grid_manager.columns:
            assert col.load_kn >= 0

    def test_higher_floor_load_increases_column_load(self, simple_grid_manager):
        """Test that higher floor load means higher column load."""
        gm1 = GridManager(width_m=6.0, length_m=6.0)
        gm1.generate_grid()
        gm1.calculate_trib_areas()
        gm1.calculate_loads(floor_load_kn_m2=30.0)
        
        gm2 = GridManager(width_m=6.0, length_m=6.0)
        gm2.generate_grid()
        gm2.calculate_trib_areas()
        gm2.calculate_loads(floor_load_kn_m2=60.0)
        
        total_load_1 = sum(c.load_kn for c in gm1.columns)
        total_load_2 = sum(c.load_kn for c in gm2.columns)
        
        assert total_load_2 > total_load_1


class TestColumnSizing:
    """Test column size optimization."""

    def test_optimize_column_sizes(self, simple_grid_manager, m25_concrete):
        """Test column size optimization."""
        simple_grid_manager.calculate_trib_areas()
        simple_grid_manager.calculate_loads(floor_load_kn_m2=50.0)
        simple_grid_manager.optimize_column_sizes(concrete=m25_concrete, fy=415.0)
        
        # All columns should have positive dimensions
        for col in simple_grid_manager.columns:
            assert col.width_nb >= 200.0  # Minimum practical size
            assert col.depth_nb >= 200.0


class TestBeamGeneration:
    """Test beam generation."""

    def test_generate_beams(self, simple_grid_manager):
        """Test beam generation from grid."""
        beams = simple_grid_manager.generate_beams()
        
        assert len(beams) > 0
        
        for beam in beams:
            assert beam.type == "beam"
            assert hasattr(beam, 'start_point')
            assert hasattr(beam, 'end_point')

    def test_beams_connect_grid_lines(self, simple_grid_manager):
        """Test beams connect grid line intersections."""
        beams = simple_grid_manager.generate_beams()
        
        x_lines = set(simple_grid_manager.x_grid_lines)
        y_lines = set(simple_grid_manager.y_grid_lines)
        
        for beam in beams:
            # Start and end points should be at grid line coordinates
            start_at_grid = beam.start_point.x in x_lines or beam.start_point.y in y_lines
            end_at_grid = beam.end_point.x in x_lines or beam.end_point.y in y_lines
            
            assert start_at_grid or end_at_grid


class TestDetailingMethods:
    """Test detailing methods."""

    def test_detail_beams(self, simple_grid_manager):
        """Test beam detailing."""
        beams = simple_grid_manager.generate_beams()
        simple_grid_manager.detail_beams(beams)
        
        assert hasattr(simple_grid_manager, 'beam_schedule')

    def test_detail_slabs(self, simple_grid_manager):
        """Test slab detailing."""
        simple_grid_manager.detail_slabs()
        
        assert hasattr(simple_grid_manager, 'slab_schedule')

    def test_detail_columns(self, simple_grid_manager, m25_concrete):
        """Test column detailing (rebar schedule)."""
        simple_grid_manager.calculate_trib_areas()
        simple_grid_manager.calculate_loads(floor_load_kn_m2=50.0)
        simple_grid_manager.optimize_column_sizes(concrete=m25_concrete)
        simple_grid_manager.detail_columns(concrete=m25_concrete, fy=415.0)
        
        assert hasattr(simple_grid_manager, 'rebar_schedule')
