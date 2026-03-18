"""
Unit tests for src/foundation_eng.py - Footing design and punching shear.
"""
import pytest
import math
from src.foundation_eng import (
    Footing,
    calculate_punching_shear_capacity,
    design_footing
)
from src.materials import Concrete


class TestPunchingShearCapacity:
    """Test punching shear capacity calculation."""

    def test_m25_concrete(self):
        """Test punching shear capacity for M25 concrete."""
        fck = 25.0
        capacity = calculate_punching_shear_capacity(300.0, fck)
        
        # τc = 0.25 * √fck = 0.25 * 5 = 1.25 N/mm²
        expected = 0.25 * math.sqrt(fck)
        assert capacity == pytest.approx(expected, rel=0.01)

    def test_m30_concrete(self):
        """Test punching shear capacity for M30 concrete."""
        fck = 30.0
        capacity = calculate_punching_shear_capacity(300.0, fck)
        
        expected = 0.25 * math.sqrt(fck)
        assert capacity == pytest.approx(expected, rel=0.01)

    def test_higher_grade_increases_capacity(self):
        """Verify higher concrete grade increases shear capacity."""
        cap_m25 = calculate_punching_shear_capacity(300.0, 25.0)
        cap_m40 = calculate_punching_shear_capacity(300.0, 40.0)
        
        assert cap_m40 > cap_m25


class TestDesignFooting:
    """Test footing design function."""

    def test_basic_footing_design(self):
        """Test basic footing design with standard inputs."""
        footing = design_footing(
            axial_load_kn=400.0,
            sbc_kn_m2=200.0,
            column_width_mm=300.0,
            column_depth_mm=300.0
        )
        
        assert isinstance(footing, Footing)
        assert footing.length_m > 0
        assert footing.width_m > 0
        assert footing.thickness_mm >= 300.0  # Minimum thickness

    def test_square_footing(self):
        """Verify footing is square (length = width)."""
        footing = design_footing(axial_load_kn=500.0, sbc_kn_m2=200.0)
        
        assert footing.length_m == footing.width_m

    def test_minimum_size(self):
        """Test that footing has minimum size of 1.0m."""
        # Very small load should still give minimum 1.0m footing
        footing = design_footing(axial_load_kn=50.0, sbc_kn_m2=200.0)
        
        assert footing.length_m >= 1.0
        assert footing.width_m >= 1.0

    def test_size_increases_with_load(self):
        """Verify footing size increases with higher load."""
        footing_low = design_footing(axial_load_kn=300.0, sbc_kn_m2=200.0)
        footing_high = design_footing(axial_load_kn=800.0, sbc_kn_m2=200.0)
        
        assert footing_high.length_m >= footing_low.length_m

    def test_size_increases_with_lower_sbc(self):
        """Verify footing size increases with weaker soil."""
        footing_strong = design_footing(axial_load_kn=500.0, sbc_kn_m2=300.0)
        footing_weak = design_footing(axial_load_kn=500.0, sbc_kn_m2=100.0)
        
        assert footing_weak.length_m >= footing_strong.length_m

    def test_thickness_for_punching_shear(self):
        """Test that thickness is sufficient for punching shear."""
        footing = design_footing(
            axial_load_kn=1000.0,  # High load
            sbc_kn_m2=200.0,
            column_width_mm=400.0,
            column_depth_mm=400.0
        )
        
        # High load should require more thickness
        assert footing.thickness_mm >= 300.0

    def test_high_load_safety_buffer(self):
        """Test 50mm safety buffer for loads > 800kN near shear limit."""
        footing = design_footing(
            axial_load_kn=900.0,
            sbc_kn_m2=200.0,
            column_width_mm=300.0,
            column_depth_mm=300.0
        )
        
        # Should have adequate thickness for high load
        assert footing.thickness_mm >= 300.0
        assert footing.status == "PASS"

    def test_size_rounding_to_50mm(self):
        """Verify footing dimensions are rounded to 50mm increments."""
        footing = design_footing(axial_load_kn=450.0, sbc_kn_m2=200.0)
        
        # Check that side is multiple of 0.05m (50mm)
        remainder = footing.length_m % 0.05
        assert remainder < 0.001 or abs(remainder - 0.05) < 0.001

    def test_with_concrete_material(self):
        """Test footing design with explicit Concrete material."""
        concrete = Concrete.from_grade("M30")
        
        footing = design_footing(
            axial_load_kn=600.0,
            sbc_kn_m2=200.0,
            column_width_mm=350.0,
            column_depth_mm=350.0,
            concrete=concrete
        )
        
        assert isinstance(footing, Footing)
        assert footing.status == "PASS"

    def test_concrete_volume_calculation(self):
        """Test concrete volume calculation."""
        footing = design_footing(
            axial_load_kn=400.0,
            sbc_kn_m2=200.0
        )
        
        # Volume = Area * Thickness
        expected_vol = footing.area_m2 * (footing.thickness_mm / 1000.0)
        assert footing.concrete_vol_m3 == pytest.approx(expected_vol, rel=0.01)

    def test_excavation_volume_calculation(self):
        """Test excavation volume calculation (1.5m depth)."""
        footing = design_footing(
            axial_load_kn=400.0,
            sbc_kn_m2=200.0
        )
        
        # Excavation = Area * 1.5m
        expected_exc = footing.area_m2 * 1.5
        assert footing.excavation_vol_m3 == pytest.approx(expected_exc, rel=0.01)


class TestFootingModel:
    """Test Footing Pydantic model."""

    def test_footing_creation(self):
        """Test direct Footing creation."""
        footing = Footing(
            length_m=1.5,
            width_m=1.5,
            thickness_mm=350.0,
            area_m2=2.25,
            concrete_vol_m3=0.7875,
            excavation_vol_m3=3.375,
            status="PASS"
        )
        
        assert footing.length_m == 1.5
        assert footing.thickness_mm == 350.0
        assert footing.status == "PASS"

    def test_footing_default_status(self):
        """Test default status is PASS."""
        footing = Footing(
            length_m=1.0,
            width_m=1.0,
            thickness_mm=300.0,
            area_m2=1.0,
            concrete_vol_m3=0.3,
            excavation_vol_m3=1.5
        )
        
        assert footing.status == "PASS"
