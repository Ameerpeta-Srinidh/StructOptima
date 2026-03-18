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
    
    def test_large_diameter_uses_6d(self):
        ext = seismic_hook_extension(16)
        assert ext == 96  # 6 × 16 = 96 > 65
    
    def test_small_diameter_uses_65mm_min(self):
        ext = seismic_hook_extension(8)
        assert ext == SEISMIC_HOOK_MIN_EXTENSION_MM  # 6 × 8 = 48 < 65
    
    def test_boundary_case(self):
        ext = seismic_hook_extension(12)
        assert ext == max(6 * 12, 65)


class TestConfinedZoneSpacing:
    
    def test_d_by_4_governs(self):
        spacing = confined_zone_stirrup_spacing(
            effective_depth_mm=280, longitudinal_bar_dia_mm=16
        )
        assert spacing == 70  # 280/4 = 70 < 128 < 100
    
    def test_8d_governs(self):
        spacing = confined_zone_stirrup_spacing(
            effective_depth_mm=600, longitudinal_bar_dia_mm=10
        )
        assert spacing == 80  # 600/4 = 150, 8×10 = 80 < 100
    
    def test_100mm_max_governs(self):
        spacing = confined_zone_stirrup_spacing(
            effective_depth_mm=600, longitudinal_bar_dia_mm=16
        )
        assert spacing == CONFINED_ZONE_MAX_SPACING_MM


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
