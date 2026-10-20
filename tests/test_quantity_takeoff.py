"""
Tests for Quantity Takeoff and Enhanced BBS Module

Tests cover:
- Ductile detailing (IS 13920)
- Concrete/shuttering BOQ
- Cost estimation
"""

import pytest
import math
from src.quantity_takeoff import (
    QuantityTakeoff, BOQSummary, CostEstimate,
    calculate_steel_ratio
)
from src.bbs_module import (
    seismic_hook_extension, confined_zone_stirrup_spacing,
    lap_splice_length, development_length,
    SEISMIC_HOOK_MIN_EXTENSION_MM, CONFINED_ZONE_MAX_SPACING_MM
)


class TestSeismicHookExtension:
    
    # IS 13920:2016 as amended (Amd 1 and 2): 8 d but not less than 75 mm
    def test_large_diameter_uses_8d(self):
        ext = seismic_hook_extension(16)
        assert ext == 128  # 8 × 16 = 128 > 75

    def test_small_diameter_uses_75mm_min(self):
        ext = seismic_hook_extension(8)
        assert ext == SEISMIC_HOOK_MIN_EXTENSION_MM == 75  # 8 × 8 = 64 < 75

    def test_boundary_case(self):
        ext = seismic_hook_extension(12)
        assert ext == max(8 * 12, 75)


class TestConfinedZoneSpacing:
    
    def test_d_by_4_governs(self):
        spacing = confined_zone_stirrup_spacing(
            effective_depth_mm=280, longitudinal_bar_dia_mm=16
        )
        assert spacing == 70  # 280/4 = 70 < 128 < 100
    
    def test_6d_governs(self):   # IS 13920 6.3.5(b) as amended by Amd 1
        spacing = confined_zone_stirrup_spacing(
            effective_depth_mm=600, longitudinal_bar_dia_mm=10
        )
        assert spacing == 60  # 600/4 = 150, 6×10 = 60 < 100
    
    def test_100mm_max_governs(self):
        spacing = confined_zone_stirrup_spacing(
            effective_depth_mm=600, longitudinal_bar_dia_mm=20
        )
        assert spacing == CONFINED_ZONE_MAX_SPACING_MM  # 600/4 = 150, 6×20 = 120 > 100


class TestLapSpliceLength:
    
    def test_normal_lap(self):
        Ld = development_length(16)
        lap = lap_splice_length(16, bars_lapped_percent=50)
        assert lap == Ld
    
    def test_excess_lap_factor(self):
        Ld = development_length(16)
        lap = lap_splice_length(16, bars_lapped_percent=75)
        assert lap == Ld * 1.4


class TestQuantityTakeoff:
    
    def test_beam_concrete_volume(self):
        qt = QuantityTakeoff()
        qt.add_beam("B1", length_mm=6000, width_mm=230, depth_mm=450)
        
        summary = qt.get_summary()
        expected = 6.0 * 0.23 * 0.45
        
        assert abs(summary.concrete_m3 - expected) < 0.01
    
    def test_column_shuttering(self):
        qt = QuantityTakeoff()
        qt.add_column("C1", height_mm=3000, width_mm=300, depth_mm=300)
        
        summary = qt.get_summary()
        expected = 2 * 3.0 * (0.3 + 0.3)
        
        assert abs(summary.shuttering_m2 - expected) < 0.01
    
    def test_slab_volume(self):
        qt = QuantityTakeoff()
        qt.add_slab("S1", length_mm=5000, width_mm=4000, thickness_mm=150)
        
        summary = qt.get_summary()
        expected = 5.0 * 4.0 * 0.15
        
        assert abs(summary.concrete_m3 - expected) < 0.01


class TestCostEstimate:
    
    def test_cost_components(self):
        qt = QuantityTakeoff()
        qt.add_beam("B1", 6000, 230, 450)
        qt.add_column("C1", 3000, 300, 300)
        qt.add_steel_from_bbs({16: 100.0, 8: 20.0})
        
        cost = qt.estimate_cost()
        
        assert cost.concrete_cost > 0
        assert cost.steel_cost > 0
        assert cost.shuttering_cost > 0
        assert cost.total_cost > 0
    
    def test_cost_per_sqft(self):
        qt = QuantityTakeoff()
        qt.add_beam("B1", 6000, 230, 450)
        qt.add_steel_from_bbs({16: 50.0})
        
        cost = qt.estimate_cost(built_up_area_sqft=1000)
        
        assert cost.cost_per_sqft > 0
        assert cost.total_cost == cost.cost_per_sqft * 1000


class TestBOQSummary:
    
    def test_json_output(self):
        qt = QuantityTakeoff()
        qt.add_beam("B1", 6000, 230, 450)
        qt.add_steel_from_bbs({16: 100.0})
        
        json_str = qt.to_json()
        
        assert "BOQ" in json_str
        assert "concrete_m3" in json_str
        assert "steel_kg" in json_str
    
    def test_boq_report(self):
        qt = QuantityTakeoff()
        qt.add_beam("B1", 6000, 230, 450)
        qt.add_column("C1", 3000, 300, 300)
        qt.add_steel_from_bbs({16: 100.0, 8: 20.0})
        
        report = qt.generate_boq_report()
        
        assert "BILL OF QUANTITIES" in report
        assert "CONCRETE" in report
        assert "STEEL" in report
        assert "COST ESTIMATE" in report


class TestSteelRatio:
    
    def test_steel_ratio(self):
        ratio = calculate_steel_ratio(steel_kg=1000, concrete_m3=10)
        assert ratio == 100.0  # kg/m³
    
    def test_zero_concrete(self):
        ratio = calculate_steel_ratio(steel_kg=100, concrete_m3=0)
        assert ratio == 0.0
