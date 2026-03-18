"""
Unit tests for src/materials.py - Concrete and Steel material classes.
"""
import pytest
import math
from src.materials import Concrete, Steel, Material


class TestConcrete:
    """Test suite for Concrete material class."""

    def test_from_grade_m25(self):
        """Test M25 concrete creation."""
        c = Concrete.from_grade("M25")
        
        assert c.grade == "M25"
        assert c.fck == 25.0
        assert c.density == 25.0  # IS 456 value
        assert c.poissons_ratio == 0.2
        
        # Check elastic modulus: E = 5000 * sqrt(fck)
        expected_e = 5000 * math.sqrt(25.0)
        assert c.modulus_of_elasticity == pytest.approx(expected_e, rel=0.01)

    def test_from_grade_m30(self):
        """Test M30 concrete creation."""
        c = Concrete.from_grade("M30")
        
        assert c.grade == "M30"
        assert c.fck == 30.0
        expected_e = 5000 * math.sqrt(30.0)
        assert c.modulus_of_elasticity == pytest.approx(expected_e, rel=0.01)

    def test_from_grade_m40(self):
        """Test M40 high-strength concrete."""
        c = Concrete.from_grade("M40")
        
        assert c.fck == 40.0
        expected_e = 5000 * math.sqrt(40.0)
        assert c.modulus_of_elasticity == pytest.approx(expected_e, rel=0.01)

    def test_from_grade_lowercase(self):
        """Test that lowercase grade strings work."""
        c = Concrete.from_grade("m25")
        assert c.grade == "M25"
        assert c.fck == 25.0

    def test_from_grade_all_standard_grades(self):
        """Test all standard IS 456 concrete grades."""
        grades = ["M20", "M25", "M30", "M35", "M40", "M50"]
        expected_fck = [20.0, 25.0, 30.0, 35.0, 40.0, 50.0]
        
        for grade, fck in zip(grades, expected_fck):
            c = Concrete.from_grade(grade)
            assert c.fck == fck
            assert c.grade == grade

    def test_embodied_carbon_default(self):
        """Test default embodied carbon factor for OPC."""
        c = Concrete.from_grade("M25")
        assert c.embodied_carbon_factor == 300.0  # kgCO2/m3


class TestSteel:
    """Test suite for Steel material class."""

    def test_from_grade_fe415(self):
        """Test Fe415 steel creation."""
        s = Steel.from_grade("Fe415")
        
        assert s.grade == "FE415"
        assert s.fy == 415.0
        assert s.density == 78.5
        assert s.modulus_of_elasticity == 2e5  # 200 GPa
        assert s.poissons_ratio == 0.3

    def test_from_grade_fe500(self):
        """Test Fe500 steel creation."""
        s = Steel.from_grade("Fe500")
        
        assert s.grade == "FE500"
        assert s.fy == 500.0

    def test_from_grade_lowercase(self):
        """Test that lowercase grade strings work."""
        s = Steel.from_grade("fe415")
        assert s.grade == "FE415"

    def test_embodied_carbon_factor(self):
        """Test steel embodied carbon factor."""
        s = Steel.from_grade("Fe415")
        assert s.embodied_carbon_factor == 1.85  # kgCO2/kg


class TestMaterialValidation:
    """Test Pydantic validation for materials."""

    def test_concrete_has_required_fields(self):
        """Ensure Concrete has all required Material fields."""
        c = Concrete.from_grade("M25")
        
        assert hasattr(c, 'name')
        assert hasattr(c, 'density')
        assert hasattr(c, 'modulus_of_elasticity')
        assert hasattr(c, 'poissons_ratio')
        assert hasattr(c, 'fck')
        assert hasattr(c, 'grade')

    def test_steel_has_required_fields(self):
        """Ensure Steel has all required Material fields."""
        s = Steel.from_grade("Fe415")
        
        assert hasattr(s, 'name')
        assert hasattr(s, 'density')
        assert hasattr(s, 'modulus_of_elasticity')
        assert hasattr(s, 'poissons_ratio')
        assert hasattr(s, 'fy')
        assert hasattr(s, 'grade')
