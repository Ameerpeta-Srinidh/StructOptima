"""
Tests for Bar Bending Schedule (BBS) Module.

Tests cover:
    - Helper function calculations (hooks, weights, development length)
    - BBS generation for beams, columns, and slabs
    - Project summary aggregation
    - Sample input/output validation
"""

import math
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.bbs_module import (
    hook_length_90,
    hook_length_135,
    unit_weight,
    development_length,
    stirrup_cutting_length,
    generate_beam_bbs,
    generate_column_bbs,
    generate_slab_bbs,
    generate_project_bbs,
    BeamBBSInput,
    ColumnBBSInput,
    SlabBBSInput,
    STEEL_DENSITY_KG_M3,
    HOOK_90_FACTOR,
    HOOK_135_FACTOR
)


class TestHookLengthCalculations:
    """Tests for hook length helper functions."""
    
    def test_hook_length_90_for_12mm(self):
        """90° hook for 12mm bar should be 9 x 12 = 108mm."""
        result = hook_length_90(12)
        assert result == 9 * 12
        assert result == 108
    
    def test_hook_length_90_for_16mm(self):
        """90° hook for 16mm bar should be 9 x 16 = 144mm."""
        result = hook_length_90(16)
        assert result == 144
    
    def test_hook_length_135_for_8mm(self):
        """135° hook for 8mm bar should be 10 x 8 = 80mm."""
        result = hook_length_135(8)
        assert result == 10 * 8
        assert result == 80
    
    def test_hook_length_135_for_10mm(self):
        """135° hook for 10mm bar should be 10 x 10 = 100mm."""
        result = hook_length_135(10)
        assert result == 100
    
    def test_hook_factors_are_correct(self):
        """Verify IS 456 hook factors are set correctly."""
        assert HOOK_90_FACTOR == 9
        assert HOOK_135_FACTOR == 10


class TestUnitWeightCalculation:
    """Tests for unit weight (kg/m) calculation."""
    
    def test_unit_weight_formula(self):
        """Verify unit weight formula: W = πd²/4 × density / 10⁶."""
        for dia in [8, 10, 12, 16, 20, 25]:
            # Correct formula: area_mm² × density_kg_m³ / 10⁶ = kg/m
            expected = (math.pi * dia**2 / 4) * STEEL_DENSITY_KG_M3 / 1e6
            result = unit_weight(dia)
            assert abs(result - expected) < 0.001
    
    def test_unit_weight_12mm(self):
        """12mm bar should weigh approximately 0.889 kg/m."""
        result = unit_weight(12)
        assert abs(result - 0.888) < 0.01
    
    def test_unit_weight_16mm(self):
        """16mm bar should weigh approximately 1.58 kg/m."""
        result = unit_weight(16)
        assert abs(result - 1.578) < 0.01
    
    def test_unit_weight_practical_formula(self):
        """Check against practical formula: W ≈ d²/162."""
        for dia in [8, 10, 12, 16, 20]:
            calculated = unit_weight(dia)
            practical = dia**2 / 162.2
            assert abs(calculated - practical) < 0.02


class TestDevelopmentLength:
    """Tests for development length calculation."""
    
    def test_development_length_16mm_fe415_m25(self):
        """Ld for 16mm Fe415 in M25 should be approximately 644mm."""
        ld = development_length(16, fy=415.0, fck=25.0)
        expected = (0.87 * 415 * 16) / (4 * 1.4 * 1.6)
        assert abs(ld - expected) < 1.0
    
    def test_development_length_increases_with_diameter(self):
        """Larger diameter should have larger Ld."""
        ld_12 = development_length(12)
        ld_16 = development_length(16)
        ld_20 = development_length(20)
        assert ld_12 < ld_16 < ld_20
    
    def test_development_length_increases_with_fy(self):
        """Higher yield strength should increase Ld."""
        ld_415 = development_length(16, fy=415.0)
        ld_500 = development_length(16, fy=500.0)
        assert ld_415 < ld_500


class TestStirrupCuttingLength:
    """Tests for stirrup/tie cutting length calculation."""
    
    def test_stirrup_basic_calculation(self):
        """Test stirrup cutting length for 300x600 beam with 25mm cover.
        
        IS 456 formula: perimeter + 2×10d (hooks) - 4×2d (corner bend deductions)
        = perimeter + 20d - 8d = perimeter + 12d
        """
        result = stirrup_cutting_length(300, 600, 25, 8)
        
        clear_b = 300 - 2 * 25  # 250
        clear_d = 600 - 2 * 25  # 550
        perimeter = 2 * (clear_b + clear_d)  # 1600
        # Hooks: 2 × 10 × 8 = 160
        # Corner bend deductions: 4 × 2 × 8 = 64
        # Net hook allowance: 160 - 64 = 96
        expected = perimeter + 12 * 8  # 1600 + 96 = 1696
        
        assert abs(result - expected) < 1.0
    
    def test_stirrup_for_column(self):
        """Test tie cutting length for 300x300 column."""
        result = stirrup_cutting_length(300, 300, 40, 8)
        
        clear_b = 300 - 2 * 40  # 220
        clear_d = 300 - 2 * 40  # 220
        perimeter = 2 * (clear_b + clear_d)  # 880
        # Net hook allowance: 12d = 96
        expected = perimeter + 12 * 8  # 880 + 96 = 976
        
        assert abs(result - expected) < 1.0


class TestBeamBBSGeneration:
    """Tests for beam BBS generation."""
    
    @pytest.fixture
    def sample_beam(self):
        return BeamBBSInput(
            member_id="B1",
            length_mm=6000,
            width_mm=300,
            depth_mm=600,
            clear_cover_mm=25,
            main_bar_dia_mm=16,
            top_bars=2,
            bottom_bars=4,
            stirrup_dia_mm=8,
            stirrup_spacing_mm=150
        )
    
    def test_beam_bbs_has_three_entries(self, sample_beam):
        """Beam BBS should have entries for top, bottom, and stirrups."""
        bbs = generate_beam_bbs(sample_beam)
        assert len(bbs.entries) == 3
    
    def test_beam_bbs_member_type(self, sample_beam):
        """Member type should be 'beam'."""
        bbs = generate_beam_bbs(sample_beam)
        assert bbs.member_type == "beam"
    
    def test_beam_bbs_bar_marks(self, sample_beam):
        """Bar marks should be A, B, C for top, bottom, stirrups."""
        bbs = generate_beam_bbs(sample_beam)
        marks = [e.bar_mark for e in bbs.entries]
        assert marks == ["A", "B", "C"]
    
    def test_beam_top_bar_cutting_length(self, sample_beam):
        """Top bar cutting length = span + 2×9d (hooks) - 2×2d (bend deductions).
        
        IS 456: span + 14d (net hook allowance after bend deductions)
        """
        bbs = generate_beam_bbs(sample_beam)
        top_entry = bbs.entries[0]
        
        # span + 2*9d (hooks) - 2*2d (bend deductions) = span + 14d
        expected = 6000 + 14 * 16  # 6224
        assert abs(top_entry.cutting_length_mm - expected) < 1.0
    
    def test_beam_stirrup_count(self, sample_beam):
        """Number of stirrups = (span / spacing) + 1."""
        bbs = generate_beam_bbs(sample_beam)
        stirrup_entry = bbs.entries[2]
        
        expected = math.ceil(6000 / 150) + 1
        assert stirrup_entry.number_of_bars == expected
    
    def test_beam_total_weight_positive(self, sample_beam):
        """Total weight should be positive."""
        bbs = generate_beam_bbs(sample_beam)
        assert bbs.total_weight_kg > 0


class TestColumnBBSGeneration:
    """Tests for column BBS generation."""
    
    @pytest.fixture
    def sample_column(self):
        return ColumnBBSInput(
            member_id="C1",
            height_mm=3000,
            width_mm=300,
            depth_mm=300,
            clear_cover_mm=40,
            main_bar_dia_mm=16,
            num_bars=8,
            tie_dia_mm=8,
            tie_spacing_mm=150
        )
    
    def test_column_bbs_has_two_entries(self, sample_column):
        """Column BBS should have entries for main bars and ties."""
        bbs = generate_column_bbs(sample_column)
        assert len(bbs.entries) == 2
    
    def test_column_bbs_member_type(self, sample_column):
        """Member type should be 'column'."""
        bbs = generate_column_bbs(sample_column)
        assert bbs.member_type == "column"
    
    def test_column_bar_marks(self, sample_column):
        """Bar marks should be M and T for main and ties."""
        bbs = generate_column_bbs(sample_column)
        marks = [e.bar_mark for e in bbs.entries]
        assert marks == ["M", "T"]
    
    def test_column_main_bar_includes_ld(self, sample_column):
        """Main bar cutting length should include Ld and lap."""
        bbs = generate_column_bbs(sample_column)
        main_entry = bbs.entries[0]
        
        ld = development_length(16)
        lap = 40 * 16
        expected = 3000 + ld + lap
        
        assert abs(main_entry.cutting_length_mm - expected) < 1.0
    
    def test_column_tie_count(self, sample_column):
        """Number of ties = (height / spacing) + 1."""
        bbs = generate_column_bbs(sample_column)
        tie_entry = bbs.entries[1]
        
        expected = math.ceil(3000 / 150) + 1
        assert tie_entry.number_of_bars == expected


class TestSlabBBSGeneration:
    """Tests for slab BBS generation."""
    
    @pytest.fixture
    def sample_two_way_slab(self):
        return SlabBBSInput(
            member_id="S1",
            lx_mm=4000,
            ly_mm=5000,
            thickness_mm=150,
            clear_cover_mm=20,
            main_bar_dia_mm=10,
            main_bar_spacing_mm=150,
            dist_bar_dia_mm=8,
            dist_bar_spacing_mm=200
        )
    
    @pytest.fixture
    def sample_one_way_slab(self):
        return SlabBBSInput(
            member_id="S2",
            lx_mm=2000,
            ly_mm=6000,
            thickness_mm=125,
            clear_cover_mm=20,
            main_bar_dia_mm=10,
            main_bar_spacing_mm=150,
            dist_bar_dia_mm=8,
            dist_bar_spacing_mm=250
        )
    
    def test_slab_bbs_has_two_entries(self, sample_two_way_slab):
        """Slab BBS should have entries for main and distribution bars."""
        bbs = generate_slab_bbs(sample_two_way_slab)
        assert len(bbs.entries) == 2
    
    def test_slab_bbs_member_type(self, sample_two_way_slab):
        """Member type should be 'slab'."""
        bbs = generate_slab_bbs(sample_two_way_slab)
        assert bbs.member_type == "slab"
    
    def test_slab_bar_marks(self, sample_two_way_slab):
        """Bar marks should be M and D for main and distribution."""
        bbs = generate_slab_bbs(sample_two_way_slab)
        marks = [e.bar_mark for e in bbs.entries]
        assert marks == ["M", "D"]
    
    def test_two_way_slab_detection(self, sample_two_way_slab):
        """Slab with Ly/Lx < 2 should be two-way."""
        bbs = generate_slab_bbs(sample_two_way_slab)
        assert "Two-Way" in bbs.member_size
    
    def test_one_way_slab_detection(self, sample_one_way_slab):
        """Slab with Ly/Lx >= 2 should be one-way."""
        bbs = generate_slab_bbs(sample_one_way_slab)
        assert "One-Way" in bbs.member_size
    
    def test_slab_main_bars_along_short_span(self, sample_two_way_slab):
        """Main bar cutting length should be based on short span.
        
        IS 456: span + 14d (2×9d hooks - 2×2d bend deductions)
        """
        bbs = generate_slab_bbs(sample_two_way_slab)
        main_entry = bbs.entries[0]
        
        lx = min(4000, 5000)
        # span + 2*9d (hooks) - 2*2d (bend deductions) = span + 14d
        expected = lx + 14 * 10  # 4140
        
        assert abs(main_entry.cutting_length_mm - expected) < 1.0


class TestProjectBBSGeneration:
    """Tests for project-level BBS aggregation."""
    
    def test_project_summary_aggregation(self):
        """Project should correctly aggregate weights by diameter."""
        beam = BeamBBSInput(
            member_id="B1", length_mm=6000, width_mm=300, depth_mm=600,
            clear_cover_mm=25, main_bar_dia_mm=16, top_bars=2, bottom_bars=4,
            stirrup_dia_mm=8, stirrup_spacing_mm=150
        )
        column = ColumnBBSInput(
            member_id="C1", height_mm=3000, width_mm=300, depth_mm=300,
            clear_cover_mm=40, main_bar_dia_mm=16, num_bars=8,
            tie_dia_mm=8, tie_spacing_mm=150
        )
        slab = SlabBBSInput(
            member_id="S1", lx_mm=4000, ly_mm=5000, thickness_mm=150,
            clear_cover_mm=20, main_bar_dia_mm=10, main_bar_spacing_mm=150,
            dist_bar_dia_mm=8, dist_bar_spacing_mm=200
        )
        
        project = generate_project_bbs([beam], [column], [slab])
        
        assert len(project.members) == 3
        assert project.total_steel_kg > 0
        assert len(project.summary_by_diameter) > 0
    
    def test_project_total_matches_member_sum(self):
        """Project total should equal sum of all member totals."""
        beam = BeamBBSInput(
            member_id="B1", length_mm=5000, width_mm=250, depth_mm=500,
            clear_cover_mm=25, main_bar_dia_mm=12, top_bars=2, bottom_bars=3,
            stirrup_dia_mm=8, stirrup_spacing_mm=175
        )
        
        project = generate_project_bbs([beam], [], [])
        
        expected_total = sum(m.total_weight_kg for m in project.members)
        assert abs(project.total_steel_kg - expected_total) < 0.01


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    def test_minimum_bars(self):
        """Should handle minimum bar counts."""
        beam = BeamBBSInput(
            member_id="B_min", length_mm=3000, width_mm=230, depth_mm=400,
            clear_cover_mm=25, main_bar_dia_mm=12, top_bars=2, bottom_bars=2,
            stirrup_dia_mm=8, stirrup_spacing_mm=200
        )
        bbs = generate_beam_bbs(beam)
        assert bbs.total_weight_kg > 0
    
    def test_large_section(self):
        """Should handle large sections."""
        column = ColumnBBSInput(
            member_id="C_large", height_mm=4000, width_mm=600, depth_mm=600,
            clear_cover_mm=50, main_bar_dia_mm=25, num_bars=12,
            tie_dia_mm=10, tie_spacing_mm=175
        )
        bbs = generate_column_bbs(column)
        assert bbs.total_weight_kg > 0
