"""
Shared pytest fixtures for Structural Design Platform tests.
"""
import sys
import os
import pytest

# Ensure src is in path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.materials import Concrete, Steel
from src.grid_manager import GridManager, Column
from src.framing_logic import StructuralMember, MemberProperties, Point
from src.foundation_eng import Footing


# --- Material Fixtures ---

@pytest.fixture
def m25_concrete():
    """M25 grade concrete material."""
    return Concrete.from_grade("M25")


@pytest.fixture
def m30_concrete():
    """M30 grade concrete material."""
    return Concrete.from_grade("M30")


@pytest.fixture
def fe415_steel():
    """Fe415 grade steel material."""
    return Steel.from_grade("Fe415")


@pytest.fixture
def fe500_steel():
    """Fe500 grade steel material."""
    return Steel.from_grade("Fe500")


# --- Grid Manager Fixtures ---

@pytest.fixture
def simple_grid_manager():
    """A simple 6x6m single-story grid manager."""
    gm = GridManager(width_m=6.0, length_m=6.0, num_stories=1, story_height_m=3.0)
    gm.generate_grid()
    return gm


@pytest.fixture
def multi_story_grid_manager():
    """A 12x12m 3-story grid manager."""
    gm = GridManager(width_m=12.0, length_m=12.0, num_stories=3, story_height_m=3.0)
    gm.generate_grid()
    return gm


# --- Column Fixtures ---

@pytest.fixture
def sample_corner_column():
    """A sample corner column with known properties."""
    return Column(
        id="C1",
        x=0.0,
        y=0.0,
        level=0,
        type="corner",
        trib_area_m2=9.0,
        load_kn=200.0,
        width_nb=300.0,
        depth_nb=300.0
    )


@pytest.fixture
def sample_interior_column():
    """A sample interior column with higher load."""
    return Column(
        id="C5",
        x=6.0,
        y=6.0,
        level=0,
        type="interior",
        trib_area_m2=36.0,
        load_kn=800.0,
        width_nb=400.0,
        depth_nb=400.0
    )


# --- Beam Fixtures ---

@pytest.fixture
def sample_beam():
    """A sample 6m simply-supported beam."""
    return StructuralMember(
        id="B1",
        type="beam",
        start_point=Point(x=0.0, y=0.0),
        end_point=Point(x=6.0, y=0.0),
        properties=MemberProperties(width_mm=300.0, depth_mm=600.0)
    )


@pytest.fixture
def sample_beams(simple_grid_manager):
    """Generate beams for a simple grid."""
    return simple_grid_manager.generate_beams()


# --- Footing Fixtures ---

@pytest.fixture
def sample_footing():
    """A sample designed footing."""
    return Footing(
        length_m=1.5,
        width_m=1.5,
        thickness_mm=350.0,
        area_m2=2.25,
        concrete_vol_m3=0.7875,
        excavation_vol_m3=3.375
    )


# --- Helper Functions ---

@pytest.fixture
def tolerance():
    """Default numerical tolerance for floating point comparisons."""
    return 0.01  # 1% tolerance
