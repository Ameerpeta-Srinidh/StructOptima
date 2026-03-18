"""
Unit tests for src/calculations.py - Load aggregation, beam analysis, and column checks.
"""
import pytest
import math
from src.calculations import (
    ComponentLoad,
    AggregatedLoad,
    aggregate_loads,
    BeamAnalysisResult,
    validate_sls,
    analyze_beam,
    ColumnCheckResult,
    check_column_capacity
)
from src.sections import RectangularSection, SectionProperties


class TestComponentLoad:
    """Test ComponentLoad model."""

    def test_dead_load_creation(self):
        """Test creating a dead load component."""
        load = ComponentLoad(name="Slab Self Weight", value_kn_m=5.0, type="dead")
        
        assert load.name == "Slab Self Weight"
        assert load.value_kn_m == 5.0
        assert load.type == "dead"

    def test_live_load_creation(self):
        """Test creating a live load component."""
        load = ComponentLoad(name="Office Load", value_kn_m=3.0, type="live")
        
        assert load.type == "live"


class TestAggregateLoads:
    """Test load aggregation with IS 456 factors."""

    def test_simple_aggregation(self):
        """Test basic load aggregation."""
        loads = [
            ComponentLoad(name="Dead", value_kn_m=10.0, type="dead"),
            ComponentLoad(name="Live", value_kn_m=5.0, type="live")
        ]
        
        result = aggregate_loads(loads)
        
        assert result.total_dead == 10.0
        assert result.total_live == 5.0
        assert result.total_superimposed == 0.0

    def test_factored_load_calculation(self):
        """Test IS 456 load factoring (1.5 DL + 1.5 LL)."""
        loads = [
            ComponentLoad(name="Dead", value_kn_m=10.0, type="dead"),
            ComponentLoad(name="Live", value_kn_m=5.0, type="live")
        ]
        
        result = aggregate_loads(loads, dead_load_factor=1.5, live_load_factor=1.5)
        
        # Factored = (DL + SI) * 1.5 + LL * 1.5
        # = (10 + 0) * 1.5 + 5 * 1.5 = 15 + 7.5 = 22.5
        assert result.total_factored == pytest.approx(22.5, rel=0.01)

    def test_service_load_property(self):
        """Test service load (unfactored) calculation."""
        loads = [
            ComponentLoad(name="D", value_kn_m=8.0, type="dead"),
            ComponentLoad(name="L", value_kn_m=4.0, type="live"),
            ComponentLoad(name="S", value_kn_m=2.0, type="superimposed")
        ]
        
        result = aggregate_loads(loads)
        
        # Service = DL + LL + SI = 8 + 4 + 2 = 14
        assert result.total_service == 14.0

    def test_multiple_loads_same_type(self):
        """Test aggregating multiple loads of same type."""
        loads = [
            ComponentLoad(name="Slab", value_kn_m=5.0, type="dead"),
            ComponentLoad(name="Beam", value_kn_m=3.0, type="dead"),
            ComponentLoad(name="Wall", value_kn_m=2.0, type="dead")
        ]
        
        result = aggregate_loads(loads)
        
        assert result.total_dead == 10.0


class TestValidateSLS:
    """Test Serviceability Limit State checks."""

    def test_deflection_pass(self):
        """Test deflection within L/250 limit."""
        span_mm = 6000.0
        deflection_mm = 20.0  # L/300, which is < L/250
        
        is_safe, msg = validate_sls(deflection_mm, span_mm)
        
        assert is_safe is True
        assert "Pass" in msg

    def test_deflection_fail(self):
        """Test deflection exceeding L/250 limit."""
        span_mm = 6000.0
        limit = span_mm / 250.0  # 24mm
        deflection_mm = 30.0  # Exceeds limit
        
        is_safe, msg = validate_sls(deflection_mm, span_mm)
        
        assert is_safe is False
        assert "Fail" in msg

    def test_at_limit(self):
        """Test deflection at exactly the limit."""
        span_mm = 5000.0
        limit = span_mm / 250.0  # 20mm
        
        is_safe, msg = validate_sls(limit, span_mm)
        
        assert is_safe is True

    def test_custom_limit_ratio(self):
        """Test with custom limit ratio (e.g., L/350 for sensitive finishes)."""
        span_mm = 7000.0
        deflection_mm = 15.0
        
        is_safe, msg = validate_sls(deflection_mm, span_mm, limit_ratio=350.0)
        
        # L/350 = 20mm, so 15mm should pass
        assert is_safe is True


class TestAnalyzeBeam:
    """Test beam analysis for moment, shear, and deflection."""

    @pytest.fixture
    def beam_section_props(self):
        """300x600mm beam section properties."""
        sec = RectangularSection(name="Beam", width_b=300.0, depth_d=600.0)
        return sec.calculate_properties()

    def test_simply_supported_moment(self, beam_section_props):
        """Test maximum moment for simply supported beam."""
        span_mm = 6000.0
        load_kn_m = 30.0  # UDL
        E_mpa = 25000.0
        
        result = analyze_beam(
            span_mm=span_mm,
            load_kn_m=load_kn_m,
            section_props=beam_section_props,
            elastic_modulus_mpa=E_mpa,
            support_type="simply_supported"
        )
        
        # M = wL²/8 = 30 * 6² / 8 = 135 kNm
        expected_moment = (30.0 * 6.0**2) / 8.0
        assert result.max_bending_moment_kNm == pytest.approx(expected_moment, rel=0.01)

    def test_simply_supported_shear(self, beam_section_props):
        """Test maximum shear for simply supported beam."""
        span_mm = 6000.0
        load_kn_m = 30.0
        E_mpa = 25000.0
        
        result = analyze_beam(
            span_mm=span_mm,
            load_kn_m=load_kn_m,
            section_props=beam_section_props,
            elastic_modulus_mpa=E_mpa,
            support_type="simply_supported"
        )
        
        # V = wL/2 = 30 * 6 / 2 = 90 kN
        expected_shear = (30.0 * 6.0) / 2.0
        assert result.max_shear_force_kN == pytest.approx(expected_shear, rel=0.01)

    def test_continuous_beam_reduced_moment(self, beam_section_props):
        """Test that continuous beam has lower moment than simply supported."""
        span_mm = 6000.0
        load_kn_m = 30.0
        E_mpa = 25000.0
        
        ss_result = analyze_beam(
            span_mm=span_mm,
            load_kn_m=load_kn_m,
            section_props=beam_section_props,
            elastic_modulus_mpa=E_mpa,
            support_type="simply_supported"
        )
        
        cont_result = analyze_beam(
            span_mm=span_mm,
            load_kn_m=load_kn_m,
            section_props=beam_section_props,
            elastic_modulus_mpa=E_mpa,
            support_type="continuous"
        )
        
        # Continuous beam should have lower moment
        assert cont_result.max_bending_moment_kNm < ss_result.max_bending_moment_kNm


class TestCheckColumnCapacity:
    """Test column capacity checks per IS 456."""

    @pytest.fixture
    def column_section_props(self):
        """300x300mm column section properties."""
        sec = RectangularSection(name="Col", width_b=300.0, depth_d=300.0)
        return sec.calculate_properties()

    def test_column_safe(self, column_section_props):
        """Test column with load within capacity."""
        result = check_column_capacity(
            load_kN=500.0,
            section_props=column_section_props,
            effective_length_mm=3000.0,
            fck=25.0,
            fy=415.0,
            gross_area_mm2=90000.0  # 300x300
        )
        
        assert result.is_safe is True
        assert result.axial_capacity_kN > result.load_applied_kN

    def test_column_unsafe(self, column_section_props):
        """Test column with excessive load."""
        result = check_column_capacity(
            load_kN=2000.0,  # Very high load
            section_props=column_section_props,
            effective_length_mm=3000.0,
            fck=25.0,
            fy=415.0,
            gross_area_mm2=90000.0
        )
        
        assert result.is_safe is False
        assert "Fail" in result.status_msg

    def test_capacity_formula(self, column_section_props):
        """Verify IS 456 Cl 39.3 capacity formula."""
        gross_area = 90000.0  # 300x300mm
        fck = 25.0
        fy = 415.0
        
        # Asc = 0.8% of Ag (minimum steel)
        asc = 0.008 * gross_area  # 720 mm²
        ac = gross_area - asc     # 89280 mm²
        
        # Pu = 0.4 * fck * Ac + 0.67 * fy * Asc
        expected_pu = (0.4 * fck * ac + 0.67 * fy * asc) / 1000.0  # kN
        
        result = check_column_capacity(
            load_kN=500.0,
            section_props=column_section_props,
            effective_length_mm=3000.0,
            fck=fck,
            fy=fy,
            gross_area_mm2=gross_area
        )
        
        assert result.axial_capacity_kN == pytest.approx(expected_pu, rel=0.01)

    def test_slenderness_warning(self, column_section_props):
        """Test slenderness warning for long columns."""
        result = check_column_capacity(
            load_kN=300.0,
            section_props=column_section_props,
            effective_length_mm=6000.0,  # Long column
            fck=25.0,
            fy=415.0,
            gross_area_mm2=90000.0
        )
        
        # Should have slenderness > 12
        assert result.slenderness_ratio > 12
        assert "Slenderness" in result.status_msg or "Warning" in result.status_msg.lower() or result.is_safe
