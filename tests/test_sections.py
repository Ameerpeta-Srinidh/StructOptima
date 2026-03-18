"""
Unit tests for src/sections.py - Section geometry and properties.
"""
import pytest
import math
from src.sections import (
    SectionProperties,
    RectangularSection,
    CircularSection,
    ISection
)


class TestRectangularSection:
    """Test suite for RectangularSection class."""

    def test_basic_properties(self):
        """Test basic rectangular section 300x600mm."""
        sec = RectangularSection(name="Test", width_b=300.0, depth_d=600.0)
        props = sec.calculate_properties()
        
        # Area = b * d = 300 * 600 = 180000 mm²
        assert props.area == pytest.approx(180000.0, rel=0.01)
        
        # Ix = b*d³/12 = 300*600³/12 = 5.4e9 mm⁴
        expected_ix = (300.0 * 600.0**3) / 12.0
        assert props.ix == pytest.approx(expected_ix, rel=0.01)
        
        # Iy = d*b³/12 = 600*300³/12 = 1.35e9 mm⁴
        expected_iy = (600.0 * 300.0**3) / 12.0
        assert props.iy == pytest.approx(expected_iy, rel=0.01)

    def test_section_modulus(self):
        """Test section modulus calculation."""
        sec = RectangularSection(name="Test", width_b=300.0, depth_d=600.0)
        props = sec.calculate_properties()
        
        # Zx = Ix / (d/2) = Ix / 300
        expected_zx = props.ix / 300.0
        assert props.zx == pytest.approx(expected_zx, rel=0.01)
        
        # Zy = Iy / (b/2) = Iy / 150
        expected_zy = props.iy / 150.0
        assert props.zy == pytest.approx(expected_zy, rel=0.01)

    def test_square_section(self):
        """Test square section where Ix = Iy."""
        sec = RectangularSection(name="Square", width_b=400.0, depth_d=400.0)
        props = sec.calculate_properties()
        
        assert props.ix == pytest.approx(props.iy, rel=0.01)
        assert props.zx == pytest.approx(props.zy, rel=0.01)
        assert props.area == 160000.0

    def test_slender_section(self):
        """Test a slender section (200x800mm)."""
        sec = RectangularSection(name="Slender", width_b=200.0, depth_d=800.0)
        props = sec.calculate_properties()
        
        assert props.area == 160000.0
        # Ix should be much larger than Iy for slender section
        assert props.ix > props.iy


class TestCircularSection:
    """Test suite for CircularSection class."""

    def test_basic_properties(self):
        """Test circular section with 300mm diameter."""
        sec = CircularSection(name="Circ", diameter=300.0)
        props = sec.calculate_properties()
        
        radius = 150.0
        
        # Area = π * r²
        expected_area = math.pi * radius**2
        assert props.area == pytest.approx(expected_area, rel=0.01)
        
        # I = π * d⁴ / 64 (same for Ix and Iy)
        expected_i = (math.pi * 300.0**4) / 64.0
        assert props.ix == pytest.approx(expected_i, rel=0.01)
        assert props.iy == pytest.approx(expected_i, rel=0.01)

    def test_circular_symmetry(self):
        """Verify circular sections have Ix = Iy and Zx = Zy."""
        sec = CircularSection(name="Circ", diameter=500.0)
        props = sec.calculate_properties()
        
        assert props.ix == props.iy
        assert props.zx == props.zy

    def test_section_modulus_circular(self):
        """Test section modulus for circular section."""
        dia = 400.0
        sec = CircularSection(name="Circ", diameter=dia)
        props = sec.calculate_properties()
        
        # Z = I / r
        expected_z = props.ix / (dia / 2.0)
        assert props.zx == pytest.approx(expected_z, rel=0.01)


class TestISection:
    """Test suite for ISection class."""

    def test_basic_i_section(self):
        """Test standard I-section properties."""
        sec = ISection(
            name="ISMB300",
            flange_width_bf=140.0,
            flange_thickness_tf=12.0,
            web_thickness_tw=8.0,
            overall_depth_d=300.0
        )
        props = sec.calculate_properties()
        
        # Area = 2*flange + web
        dw = 300.0 - 2 * 12.0  # web depth = 276mm
        expected_area = 2 * (140.0 * 12.0) + (dw * 8.0)
        assert props.area == pytest.approx(expected_area, rel=0.01)

    def test_i_section_inertia(self):
        """Test I-section moment of inertia calculation."""
        sec = ISection(
            name="Test",
            flange_width_bf=200.0,
            flange_thickness_tf=15.0,
            web_thickness_tw=10.0,
            overall_depth_d=400.0
        )
        props = sec.calculate_properties()
        
        bf = 200.0
        tf = 15.0
        tw = 10.0
        D = 400.0
        dw = D - 2 * tf
        
        # Ix formula: (bf * D³ - (bf-tw) * dw³) / 12
        expected_ix = ((bf * D**3) - ((bf - tw) * dw**3)) / 12.0
        assert props.ix == pytest.approx(expected_ix, rel=0.01)

    def test_i_section_weak_axis(self):
        """Test weak axis (Iy) is less than strong axis (Ix)."""
        sec = ISection(
            name="Test",
            flange_width_bf=150.0,
            flange_thickness_tf=10.0,
            web_thickness_tw=6.0,
            overall_depth_d=300.0
        )
        props = sec.calculate_properties()
        
        # For typical I-sections, Ix >> Iy
        assert props.ix > props.iy


class TestSectionProperties:
    """Test SectionProperties model."""

    def test_section_properties_creation(self):
        """Test direct creation of SectionProperties."""
        props = SectionProperties(
            area=10000.0,
            ix=1e8,
            iy=5e7,
            zx=1e6,
            zy=5e5
        )
        
        assert props.area == 10000.0
        assert props.ix == 1e8
        assert props.iy == 5e7
