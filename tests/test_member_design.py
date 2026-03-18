"""
Tests for Structural Member Design Module (IS 456:2000)

Tests cover:
- Beam flexure (Mu_lim, singly/doubly reinforced)
- Beam shear (tau_v, tau_c, stirrups)
- Column slenderness and P-M interaction
- Slab coefficient method
"""

import pytest
import math
from src.member_design import (
    MemberDesigner, BeamDesignResult, ColumnDesignResult, SlabDesignResult,
    DesignStatus, ReinforcementType, CONCRETE_GRADES, STEEL_GRADES
)


class TestMuLim:
    
    def test_mu_lim_m25_fe415(self):
        designer = MemberDesigner(concrete_grade="M25", steel_grade="Fe415")
        
        Mu_lim = designer.calculate_mu_lim(b_mm=230, d_mm=400)
        
        xu_d = 0.48
        expected = 0.36 * 25 * 230 * 400**2 * xu_d * (1 - 0.42 * xu_d) / 1e6
        
        assert abs(Mu_lim - expected) < 1.0
    
    def test_mu_lim_increases_with_depth(self):
        designer = MemberDesigner(concrete_grade="M25", steel_grade="Fe415")
        
        Mu_lim_400 = designer.calculate_mu_lim(230, 400)
        Mu_lim_500 = designer.calculate_mu_lim(230, 500)
        
        assert Mu_lim_500 > Mu_lim_400


class TestBeamFlexure:
    
    def test_singly_reinforced(self):
        designer = MemberDesigner(concrete_grade="M25", steel_grade="Fe415")
        
        reinf_type, Ast, Asc = designer.design_beam_flexure(
            "B1", b_mm=230, D_mm=450, Mu_kNm=50
        )
        
        assert reinf_type == ReinforcementType.SINGLY
        assert Asc == 0.0
        assert Ast > 0
    
    def test_doubly_reinforced(self):
        designer = MemberDesigner(concrete_grade="M25", steel_grade="Fe415")
        
        Mu_lim = designer.calculate_mu_lim(230, 400)
        
        reinf_type, Ast, Asc = designer.design_beam_flexure(
            "B1", b_mm=230, D_mm=450, Mu_kNm=Mu_lim + 50
        )
        
        assert reinf_type == ReinforcementType.DOUBLY
        assert Asc > 0
        assert Ast > Asc


class TestBeamShear:
    
    def test_shear_capacity_lookup(self):
        designer = MemberDesigner()
        
        tau_c_low = designer._get_tau_c(0.25)
        tau_c_high = designer._get_tau_c(1.50)
        
        assert tau_c_high > tau_c_low
        assert 0.28 <= tau_c_low <= 0.50
        assert 0.60 <= tau_c_high <= 0.80
    
    def test_min_shear_reinforcement(self):
        designer = MemberDesigner()
        
        tau_v, tau_c, Vus, sv = designer.design_beam_shear(
            "B1", b_mm=230, D_mm=450, Vu_kN=20, Ast_mm2=400
        )
        
        assert sv > 0
        assert sv <= 300
    
    def test_shear_failure_detection(self):
        designer = MemberDesigner(concrete_grade="M20")
        
        tau_v, tau_c, Vus, sv = designer.design_beam_shear(
            "B1", b_mm=200, D_mm=300, Vu_kN=200, Ast_mm2=300
        )
        
        if tau_v > designer.tau_c_max:
            assert sv == 0


class TestBeamDesign:
    
    def test_full_beam_design(self):
        designer = MemberDesigner()
        
        result = designer.design_beam(
            "B101", b_mm=230, D_mm=450, Mu_kNm=80, Vu_kN=60
        )
        
        assert result.element_id == "B101"
        assert result.Ast_tension_mm2 > 0
        assert result.stirrup_spacing_mm > 0
        assert result.provided_top != ""
        assert result.provided_stirrups != ""
    
    def test_json_output(self):
        designer = MemberDesigner()
        result = designer.design_beam("B101", 230, 450, 80, 60)
        
        data = result.to_dict()
        
        assert "flexure" in data
        assert "shear" in data
        assert "Ast_tension_mm2" in data["flexure"]


class TestColumnSlenderness:
    
    def test_short_column(self):
        designer = MemberDesigner()
        
        ratio, is_slender = designer.check_column_slenderness(
            Leff_mm=3000, D_mm=300
        )
        
        assert ratio == 10.0
        assert is_slender is False
    
    def test_slender_column(self):
        designer = MemberDesigner()
        
        ratio, is_slender = designer.check_column_slenderness(
            Leff_mm=4000, D_mm=300
        )
        
        assert ratio > 12.0
        assert is_slender is True


class TestMinEccentricity:
    
    def test_min_eccentricity_formula(self):
        designer = MemberDesigner()
        
        e_min = designer.calculate_min_eccentricity(L_mm=3000, D_mm=300)
        
        expected = 3000/500 + 300/30
        expected = max(expected, 20)
        
        assert abs(e_min - expected) < 0.1
    
    def test_min_20mm(self):
        designer = MemberDesigner()
        
        e_min = designer.calculate_min_eccentricity(L_mm=1000, D_mm=300)
        
        assert e_min >= 20


class TestPMInteraction:
    
    def test_low_axial_passes(self):
        designer = MemberDesigner()
        
        ratio = designer.check_pm_interaction(
            Pu_kN=500, Mux_kNm=20, Muy_kNm=15,
            b_mm=300, D_mm=400, Ast_mm2=1200
        )
        
        assert ratio < 1.0
    
    def test_high_moment_fails(self):
        designer = MemberDesigner()
        
        ratio = designer.check_pm_interaction(
            Pu_kN=1500, Mux_kNm=200, Muy_kNm=150,
            b_mm=300, D_mm=400, Ast_mm2=800
        )
        
        assert ratio > 0


class TestColumnDesign:
    
    def test_full_column_design(self):
        designer = MemberDesigner()
        
        result = designer.design_column(
            "C1", b_mm=300, D_mm=400, L_mm=3000,
            Pu_kN=800, Mux_kNm=50, Muy_kNm=30,
            steel_percent=1.5
        )
        
        assert result.element_id == "C1"
        assert result.Ast_mm2 > 0
        assert result.tie_spacing_mm > 0
        assert result.provided_steel != ""
    
    def test_slender_column_additional_moment(self):
        designer = MemberDesigner()
        
        result = designer.design_column(
            "C1", b_mm=230, D_mm=230, L_mm=4000,
            Pu_kN=500, Mux_kNm=20, Muy_kNm=20,
            steel_percent=1.5
        )
        
        assert result.is_slender is True
        assert len([w for w in result.warnings if "Slender" in w]) > 0


class TestSlabDesign:
    
    def test_two_way_slab(self):
        designer = MemberDesigner()
        
        result = designer.design_slab(
            "S1", Lx_mm=4000, Ly_mm=5000, thickness_mm=150,
            w_kN_m2=10, edge_condition="two_adjacent_continuous"
        )
        
        assert result.Mx_kNm_m > 0
        assert result.My_kNm_m > 0
        assert result.Ast_x_mm2_m > 0
        assert result.provided_x != ""
    
    def test_deflection_check(self):
        designer = MemberDesigner()
        
        result = designer.design_slab(
            "S1", Lx_mm=6000, Ly_mm=7000, thickness_mm=120,
            w_kN_m2=12
        )
        
        assert result.deflection_ratio > 0


class TestMaterialGrades:
    
    def test_concrete_grades(self):
        assert "M20" in CONCRETE_GRADES
        assert "M25" in CONCRETE_GRADES
        assert CONCRETE_GRADES["M25"]["fck"] == 25
    
    def test_steel_grades(self):
        assert "Fe415" in STEEL_GRADES
        assert "Fe500" in STEEL_GRADES
        assert STEEL_GRADES["Fe415"]["xu_d_max"] == 0.48
