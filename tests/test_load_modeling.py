"""
Tests for Wind Load Module (IS 875 Part 3) and Load Combinations (IS 456 Table 18).

Tests verify:
- Wind pressure calculations
- Internal pressure coefficient based on openings
- Load combinations including critical 0.9DL+1.5WL
- Seismic weight LL reduction factors
"""

import pytest
from src.wind_load import (
    WindLoadCalculator, WindZone, TerrainCategory, BuildingClass,
    calculate_wind_load, BASIC_WIND_SPEED
)
from src.load_combinations import (
    LoadCombinationManager, LoadType, CombinationType,
    calculate_seismic_weight, check_uplift_stability, get_summary_report
)
from src.seismic import (
    SeismicDesignChecker, SeismicZone, IrregularityType, AnalysisMethod
)


class TestWindLoad:
    """Tests for IS 875 Part 3 wind load calculations."""
    
    def test_basic_wind_speed_zones(self):
        """Verify basic wind speeds for each zone."""
        assert BASIC_WIND_SPEED[WindZone.ZONE_1] == 33.0
        assert BASIC_WIND_SPEED[WindZone.ZONE_3] == 44.0
        assert BASIC_WIND_SPEED[WindZone.ZONE_6] == 55.0
    
    def test_design_wind_speed_at_height(self):
        """Test Vz = Vb × k1 × k2 × k3 calculation."""
        calc = WindLoadCalculator(
            zone=WindZone.ZONE_3,
            terrain_category=TerrainCategory.CATEGORY_2
        )
        
        # At 10m, k2 = 1.0 for Category 2
        vz_10 = calc.calculate_design_wind_speed(10.0)
        # Vz = 44 × 1.0 × 1.0 × 1.0 = 44 m/s
        assert vz_10 == pytest.approx(44.0, rel=0.01)
        
        # Above 10m, k2 increases
        vz_20 = calc.calculate_design_wind_speed(20.0)
        assert vz_20 > vz_10
    
    def test_design_wind_pressure(self):
        """Test pz = 0.6 × Vz² calculation."""
        calc = WindLoadCalculator(zone=WindZone.ZONE_3)
        
        # At 10m: pz = 0.6 × 44² / 1000 = 1.16 kN/m²
        pz = calc.calculate_design_wind_pressure(10.0)
        assert pz == pytest.approx(1.16, rel=0.05)
    
    def test_internal_pressure_class_a(self):
        """Test Cpi = ±0.2 for sealed buildings (< 5% openings)."""
        calc = WindLoadCalculator(zone=WindZone.ZONE_3)
        cpi, bclass = calc.get_internal_pressure_coefficient(3.0)
        
        assert cpi == 0.2
        assert bclass == BuildingClass.CLASS_A
    
    def test_internal_pressure_class_b(self):
        """Test Cpi = ±0.5 for buildings with 5-20% openings."""
        calc = WindLoadCalculator(zone=WindZone.ZONE_3)
        cpi, bclass = calc.get_internal_pressure_coefficient(10.0)
        
        assert cpi == 0.5
        assert bclass == BuildingClass.CLASS_B
    
    def test_internal_pressure_class_c(self):
        """Test Cpi = ±0.7 for open buildings (> 20% openings)."""
        calc = WindLoadCalculator(zone=WindZone.ZONE_3)
        cpi, bclass = calc.get_internal_pressure_coefficient(25.0)
        
        assert cpi == 0.7
        assert bclass == BuildingClass.CLASS_C
    
    def test_wind_load_calculation(self):
        """Test complete wind load calculation."""
        result = calculate_wind_load(
            zone=WindZone.ZONE_3,
            height_m=12.0,
            width_m=10.0,
            length_m=15.0,
            opening_percentage=10.0
        )
        
        assert result.building_height_m == 12.0
        assert result.parameters.building_class == BuildingClass.CLASS_B
        assert result.total_base_shear_x_kn > 0
        assert result.total_base_shear_y_kn > 0
        assert len(result.warnings) > 0  # Should warn about 10% openings
    
    def test_opening_warning(self):
        """Verify warning is generated for buildings with significant openings."""
        result = calculate_wind_load(
            zone=WindZone.ZONE_3,
            height_m=9.0,
            width_m=8.0,
            length_m=12.0,
            opening_percentage=15.0
        )
        
        # Should have warning about Cpi increase
        assert any("openings" in w.lower() for w in result.warnings)


class TestLoadCombinations:
    """Tests for IS 456 Table 18 load combinations."""
    
    def test_basic_combination(self):
        """Test 1.5(DL+LL) combination."""
        manager = LoadCombinationManager(include_wind=False, include_seismic=False)
        
        results = manager.apply_all_combinations(
            dead_load_kn=100.0,
            live_load_kn=50.0
        )
        
        # 1.5(DL+LL) = 1.5 × 150 = 225 kN
        assert any(r.combination_name == "1.5(DL+LL)" for r in results)
        combo_result = next(r for r in results if r.combination_name == "1.5(DL+LL)")
        assert combo_result.total_factored_kn == pytest.approx(225.0, rel=0.01)
    
    def test_critical_uplift_combination(self):
        """Test 0.9DL + 1.5WL (uplift/overturning) is included."""
        manager = LoadCombinationManager(include_wind=True, include_seismic=False)
        
        critical = manager.get_critical_combinations()
        
        # Should include 0.9DL+1.5WL
        combo_names = [c.name for c in critical]
        assert "0.9DL+1.5WL" in combo_names
    
    def test_uplift_combination_values(self):
        """Verify 0.9DL+1.5WL calculation."""
        manager = LoadCombinationManager(include_wind=True, include_seismic=False)
        
        results = manager.apply_all_combinations(
            dead_load_kn=100.0,
            live_load_kn=50.0,
            wind_load_kn=40.0
        )
        
        # 0.9DL + 1.5WL = 0.9×100 + 1.5×40 = 90 + 60 = 150 kN
        uplift = next(r for r in results if r.combination_name == "0.9DL+1.5WL")
        assert uplift.factored_dead_kn == pytest.approx(90.0, rel=0.01)
        assert uplift.factored_wind_kn == pytest.approx(60.0, rel=0.01)
        assert uplift.is_uplift_case == True
    
    def test_seismic_combinations(self):
        """Test seismic load combinations are included."""
        manager = LoadCombinationManager(include_wind=False, include_seismic=True)
        
        combos = manager.get_all_combinations()
        combo_names = [c.name for c in combos]
        
        assert "1.2(DL+LL+EQx)" in combo_names
        assert "0.9DL+1.5EQx" in combo_names
    
    def test_governing_combination(self):
        """Test finding the governing (maximum) combination."""
        manager = LoadCombinationManager(include_wind=True, include_seismic=False)
        
        gov_combo, gov_result = manager.get_governing_combination(
            dead_load_kn=100.0,
            live_load_kn=50.0,
            wind_load_kn=30.0
        )
        
        # 1.5(DL+LL) = 225 should be maximum
        assert gov_result.total_factored_kn >= 225.0


class TestSeismicWeight:
    """Tests for seismic weight with LL reduction per IS 1893."""
    
    def test_ll_reduction_25_percent(self):
        """Test 25% LL reduction for intensity ≤ 3.0 kN/m²."""
        result = calculate_seismic_weight(
            dead_load_kn=1000.0,
            live_load_kn=200.0,
            live_load_intensity_kn_m2=2.0  # Residential
        )
        
        assert result.ll_reduction_factor == 0.25
        assert result.effective_live_load_kn == pytest.approx(50.0, rel=0.01)
        assert result.seismic_weight_kn == pytest.approx(1050.0, rel=0.01)
    
    def test_ll_reduction_50_percent(self):
        """Test 50% LL reduction for intensity > 3.0 kN/m²."""
        result = calculate_seismic_weight(
            dead_load_kn=1000.0,
            live_load_kn=400.0,
            live_load_intensity_kn_m2=5.0  # Commercial/Assembly
        )
        
        assert result.ll_reduction_factor == 0.50
        assert result.effective_live_load_kn == pytest.approx(200.0, rel=0.01)
        assert result.seismic_weight_kn == pytest.approx(1200.0, rel=0.01)
    
    def test_code_reference_included(self):
        """Verify IS 1893 Cl. 7.4.3 is referenced."""
        result = calculate_seismic_weight(
            dead_load_kn=500.0,
            live_load_kn=100.0,
            live_load_intensity_kn_m2=2.0
        )
        
        assert "IS 1893" in result.code_reference


class TestUpliftStability:
    """Tests for uplift/overturning stability check."""
    
    def test_stable_building(self):
        """Test stable building (DL >> WL)."""
        is_stable, fos, msg = check_uplift_stability(
            dead_load_kn=500.0,
            wind_load_kn=50.0
        )
        
        assert is_stable == True
        assert fos > 1.0
        assert "Stable" in msg
    
    def test_unstable_building(self):
        """Test unstable building (WL >> DL)."""
        is_stable, fos, msg = check_uplift_stability(
            dead_load_kn=50.0,
            wind_load_kn=100.0
        )
        
        assert is_stable == False
        assert fos < 1.0
        assert "UNSTABLE" in msg


class TestIrregularityCheck:
    """Tests for irregularity checks in seismic module."""
    
    def test_seismic_weight_25_percent(self):
        """Test seismic weight calculation with 25% LL reduction."""
        checker = SeismicDesignChecker(
            zone=SeismicZone.ZONE_III,
            building_type="residential"
        )
        
        result = checker.calculate_seismic_weight(
            dead_load_kn=1000.0,
            live_load_kn=200.0,
            live_load_intensity_kn_m2=2.0
        )
        
        assert result.ll_reduction_factor == 0.25
        assert result.seismic_weight_kn == pytest.approx(1050.0, rel=0.01)
    
    def test_re_entrant_corner_irregular(self):
        """Test re-entrant corner detection (> 15% = irregular)."""
        checker = SeismicDesignChecker(zone=SeismicZone.ZONE_III)
        
        irregularities = checker.check_irregularities(
            floor_width_m=20.0,
            floor_length_m=20.0,
            re_entrant_x_m=5.0,  # 25% - should be irregular
            re_entrant_y_m=0.0
        )
        
        re_entrant = next(
            (ir for ir in irregularities if ir.irregularity_type == IrregularityType.RE_ENTRANT_CORNER),
            None
        )
        
        assert re_entrant is not None
        assert re_entrant.is_irregular == True
        assert re_entrant.value == pytest.approx(25.0, rel=0.1)
    
    def test_static_analysis_blocked_for_irregular(self):
        """Test that static analysis is blocked for irregular buildings."""
        checker = SeismicDesignChecker(zone=SeismicZone.ZONE_IV)
        
        irregularities = checker.check_irregularities(
            floor_width_m=20.0,
            floor_length_m=20.0,
            re_entrant_x_m=6.0,  # 30% - irregular
            re_entrant_y_m=0.0
        )
        
        method_check = checker.check_analysis_method(
            irregularities=irregularities,
            num_stories=3,
            building_height_m=9.0
        )
        
        assert method_check.static_allowed == False
        assert method_check.required_method == AnalysisMethod.RESPONSE_SPECTRUM
    
    def test_static_allowed_for_regular_low_rise(self):
        """Test static analysis allowed for regular low-rise."""
        checker = SeismicDesignChecker(zone=SeismicZone.ZONE_III)
        
        irregularities = []  # No irregularities
        
        method_check = checker.check_analysis_method(
            irregularities=irregularities,
            num_stories=3,
            building_height_m=9.0
        )
        
        assert method_check.static_allowed == True
        assert method_check.required_method == AnalysisMethod.EQUIVALENT_STATIC
