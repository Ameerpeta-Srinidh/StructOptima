"""
Tests for Analysis Configuration Module (IS 1893:2016, IS 16700)

Tests cover:
- Seismic parameters (zone factors, R values)
- SMRF mandate for Zone III+
- Stiffness modifiers (cracked sections)
- Seismic mass reduction (25%/50% LL)
- Load combination generation
- Uplift cases (0.9DL ± 1.5EL)
- P-Delta trigger conditions
"""

import pytest
import json
from src.analysis_config import (
    AnalysisConfigGenerator, AnalysisConfig,
    SeismicParameters, StiffnessModifiers, PDeltaSettings,
    StructuralFrameType, DiaphragmType, SoilType,
    ZONE_FACTORS, RESPONSE_REDUCTION,
    calculate_base_shear
)


class TestSeismicParameters:
    
    def test_zone_factors(self):
        assert ZONE_FACTORS["II"] == 0.10
        assert ZONE_FACTORS["III"] == 0.16
        assert ZONE_FACTORS["IV"] == 0.24
        assert ZONE_FACTORS["V"] == 0.36
    
    def test_response_reduction_smrf(self):
        assert RESPONSE_REDUCTION[StructuralFrameType.SMRF] == 5.0
    
    def test_response_reduction_omrf(self):
        assert RESPONSE_REDUCTION[StructuralFrameType.OMRF] == 3.0
    
    def test_smrf_mandate_zone_iii(self):
        gen = AnalysisConfigGenerator(
            zone="III",
            frame_type="OMRF"
        )
        
        assert gen.frame_type == StructuralFrameType.SMRF
        assert len(gen.warnings) > 0
        assert "SMRF" in gen.warnings[0]
    
    def test_smrf_mandate_zone_v(self):
        gen = AnalysisConfigGenerator(
            zone="V",
            frame_type="OMRF"
        )
        
        assert gen.frame_type == StructuralFrameType.SMRF
    
    def test_omrf_allowed_zone_ii(self):
        gen = AnalysisConfigGenerator(
            zone="II",
            frame_type="OMRF"
        )
        
        assert gen.frame_type == StructuralFrameType.OMRF


class TestStiffnessModifiers:
    
    def test_default_values(self):
        modifiers = StiffnessModifiers()
        
        assert modifiers.columns == 0.70
        assert modifiers.beams == 0.35
        assert modifiers.slabs == 0.25
        assert modifiers.shear_walls == 0.70
    
    def test_generator_applies_modifiers(self):
        gen = AnalysisConfigGenerator(zone="III")
        config = gen.generate()
        
        assert config.stiffness_modifiers.columns == 0.70
        assert config.stiffness_modifiers.beams == 0.35


class TestSeismicMass:
    
    def test_ll_reduction_upto_3kn(self):
        gen = AnalysisConfigGenerator(zone="III")
        gen.add_floor_mass(
            floor_id="Floor 1",
            level_m=3.0,
            dead_load_kn=500,
            live_load_kn=200,
            live_load_intensity_kn_m2=2.0,
            is_roof=False
        )
        
        fm = gen.floor_masses[0]
        assert fm.effective_live_load_kn == 200 * 0.25
        assert fm.seismic_mass_kn == 500 + 50
    
    def test_ll_reduction_above_3kn(self):
        gen = AnalysisConfigGenerator(zone="III")
        gen.add_floor_mass(
            floor_id="Storage Floor",
            level_m=6.0,
            dead_load_kn=500,
            live_load_kn=400,
            live_load_intensity_kn_m2=5.0,
            is_roof=False
        )
        
        fm = gen.floor_masses[0]
        assert fm.effective_live_load_kn == 400 * 0.50
        assert fm.seismic_mass_kn == 500 + 200
    
    def test_roof_exception(self):
        gen = AnalysisConfigGenerator(zone="III")
        gen.add_floor_mass(
            floor_id="Roof",
            level_m=12.0,
            dead_load_kn=300,
            live_load_kn=150,
            live_load_intensity_kn_m2=1.5,
            is_roof=True
        )
        
        fm = gen.floor_masses[0]
        assert fm.effective_live_load_kn == 0
        assert fm.seismic_mass_kn == 300


class TestLoadCombinations:
    
    def test_gravity_combination_exists(self):
        gen = AnalysisConfigGenerator(zone="III")
        config = gen.generate()
        
        gravity_combos = [c for c in config.load_combinations 
                          if c["name"] == "1.5(DL+LL)"]
        assert len(gravity_combos) >= 1
    
    def test_seismic_combinations_exist(self):
        gen = AnalysisConfigGenerator(zone="III")
        config = gen.generate()
        
        eq_combos = [c for c in config.load_combinations 
                     if "EQX" in str(c.get("factors", {}))]
        assert len(eq_combos) >= 4
    
    def test_uplift_combinations_exist(self):
        gen = AnalysisConfigGenerator(zone="III")
        config = gen.generate()
        
        uplift_combos = [c for c in config.load_combinations 
                          if c.get("is_critical") and "Uplift" in c["name"]]
        
        assert len(uplift_combos) >= 4
    
    def test_uplift_has_0_9_dl_factor(self):
        gen = AnalysisConfigGenerator(zone="III")
        config = gen.generate()
        
        uplift_combos = [c for c in config.load_combinations 
                          if "Uplift" in c["name"]]
        
        for combo in uplift_combos:
            assert combo["factors"]["DL"] == 0.9
    
    def test_total_combinations_count(self):
        gen = AnalysisConfigGenerator(zone="III", include_wind=True)
        config = gen.generate()
        
        assert len(config.load_combinations) >= 15


class TestPDelta:
    
    def test_enabled_for_5_storeys(self):
        gen = AnalysisConfigGenerator(zone="III", num_storeys=5)
        config = gen.generate()
        
        assert config.p_delta.enabled is True
    
    def test_disabled_for_3_storeys(self):
        gen = AnalysisConfigGenerator(zone="III", num_storeys=3)
        config = gen.generate()
        
        assert config.p_delta.enabled is False
    
    def test_threshold_at_4_storeys(self):
        gen = AnalysisConfigGenerator(zone="III", num_storeys=4)
        config = gen.generate()
        
        assert config.p_delta.enabled is False


class TestDiaphragm:
    
    def test_rigid_for_small_cutout(self):
        gen = AnalysisConfigGenerator(zone="III", plan_cutout_percent=10)
        config = gen.generate()
        
        assert config.diaphragm_type == DiaphragmType.RIGID
    
    def test_semi_rigid_for_large_cutout(self):
        gen = AnalysisConfigGenerator(zone="III", plan_cutout_percent=35)
        config = gen.generate()
        
        assert config.diaphragm_type == DiaphragmType.SEMI_RIGID
        assert len(gen.warnings) > 0


class TestJsonOutput:
    
    def test_json_format(self):
        gen = AnalysisConfigGenerator(zone="IV", num_storeys=6)
        gen.add_floor_mass("F1", 3.0, 500, 200, 2.0, False)
        gen.add_floor_mass("F2", 6.0, 500, 200, 2.0, False)
        config = gen.generate()
        
        json_str = config.to_json()
        data = json.loads(json_str)
        
        assert "analysis_config" in data
        assert "load_combinations" in data
        assert "floor_masses" in data
        
        ac = data["analysis_config"]
        assert "seismic_parameters" in ac
        assert "stiffness_modifiers" in ac
        assert "p_delta_effect" in ac
        assert ac["seismic_parameters"]["Z"] == 0.24


class TestBaseShear:
    
    def test_base_shear_calculation(self):
        vb = calculate_base_shear(
            seismic_weight_kn=10000,
            zone_factor=0.16,
            importance_factor=1.0,
            response_reduction=5.0,
            sa_g=2.5
        )
        
        expected = (0.16 * 1.0 * 2.5) / (2 * 5.0) * 10000
        assert abs(vb - expected) < 0.01
