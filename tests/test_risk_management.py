"""
Test cases for Black Box Risk Management Module.

This module tests the comprehensive risk checks implemented to prevent
common failures in structural software usage.
"""

import pytest
from src.risk_management import (
    BlackBoxRiskManager,
    RiskLevel,
    RiskCategory,
    run_risk_checks,
    format_risk_report
)
from src.grid_manager import GridManager, Column
from src.framing_logic import StructuralMember, Point, MemberProperties
from src.foundation_eng import Footing


def test_fixed_support_assumption():
    """Test check for fixed support assumption."""
    grid_mgr = GridManager(width_m=10.0, length_m=10.0, num_stories=2)
    grid_mgr.generate_grid()
    
    beams = []
    footings = [Footing(length_m=1.5, width_m=1.5, thickness_mm=300, 
                       area_m2=2.25, concrete_vol_m3=1.0, excavation_vol_m3=3.0)]
    
    # Test without soil spring (should warn)
    manager = BlackBoxRiskManager(
        grid_mgr=grid_mgr,
        beams=beams,
        footings=footings,
        subgrade_modulus_kn_m3=None  # Fixed assumption
    )
    
    manager.check_fixed_support_assumption()
    
    assert len(manager.results) > 0
    result = manager.results[0]
    assert result.check_name == "Fixed Support Assumption Check"
    assert result.risk_level == RiskLevel.HIGH
    assert result.status == "WARN"


def test_rigid_diaphragm_assumption():
    """Test check for rigid diaphragm assumption."""
    grid_mgr = GridManager(width_m=10.0, length_m=10.0, num_stories=2)
    grid_mgr.generate_grid()
    
    # Note: void_zones is not a standard GridManager field
    # The diaphragm check should still run and provide a result
    
    beams = []
    footings = []
    
    manager = BlackBoxRiskManager(
        grid_mgr=grid_mgr,
        beams=beams,
        footings=footings
    )
    
    manager.check_rigid_diaphragm_assumption()
    
    # Should produce a result for the check
    results = [r for r in manager.results if "Rigid Diaphragm" in r.check_name]
    assert len(results) > 0


def test_pdelta_effects():
    """Test check for P-Delta effects."""
    grid_mgr = GridManager(width_m=10.0, length_m=10.0, num_stories=4)  # Tall building
    grid_mgr.generate_grid()
    
    beams = []
    footings = []
    
    manager = BlackBoxRiskManager(
        grid_mgr=grid_mgr,
        beams=beams,
        footings=footings
    )
    
    manager.check_pdelta_effects()
    
    # Should warn for 4-story building
    results = [r for r in manager.results if "P-Delta" in r.check_name]
    assert len(results) > 0
    assert results[0].risk_level == RiskLevel.HIGH


def test_pattern_loading():
    """Test check for pattern loading."""
    grid_mgr = GridManager(width_m=10.0, length_m=10.0, num_stories=2)
    grid_mgr.generate_grid()
    
    # Create continuous beams (multiple beams on same line)
    beams = [
        StructuralMember(
            id="B1",
            type="beam",
            start_point=Point(x=0, y=5.0),
            end_point=Point(x=5, y=5.0),
            properties=MemberProperties(width_mm=300, depth_mm=600)
        ),
        StructuralMember(
            id="B2",
            type="beam",
            start_point=Point(x=5, y=5.0),
            end_point=Point(x=10, y=5.0),
            properties=MemberProperties(width_mm=300, depth_mm=600)
        )
    ]
    
    footings = []
    
    manager = BlackBoxRiskManager(
        grid_mgr=grid_mgr,
        beams=beams,
        footings=footings
    )
    
    manager.check_pattern_loading()
    
    # Should detect continuous beams
    results = [r for r in manager.results if "Pattern Loading" in r.check_name]
    assert len(results) > 0


def test_floating_columns():
    """Test check for floating columns."""
    grid_mgr = GridManager(width_m=10.0, length_m=10.0, num_stories=2)
    grid_mgr.generate_grid()
    
    # Note: The floating column check analyzes the columns already in grid_mgr
    # After generate_grid(), columns are properly placed at level 0
    # The check should run and provide appropriate results
    
    # Create a mock beam (required to prevent early return in check function)
    mock_beam = StructuralMember(
        id="B1",
        type="beam",
        start_point=Point(x=0.0, y=0.0),
        end_point=Point(x=5000.0, y=0.0),
        properties=MemberProperties(width_mm=300, depth_mm=600)
    )
    beams = [mock_beam]
    footings = []
    
    manager = BlackBoxRiskManager(
        grid_mgr=grid_mgr,
        beams=beams,
        footings=footings
    )
    
    manager.check_floating_columns()
    
    # Check should run and produce a result
    results = [r for r in manager.results if "Floating Column" in r.check_name]
    assert len(results) > 0


def test_seismic_hook_detailing():
    """Test check for seismic hook detailing."""
    grid_mgr = GridManager(width_m=10.0, length_m=10.0, num_stories=2)
    grid_mgr.generate_grid()
    
    beams = []
    footings = []
    
    # Test in seismic zone IV
    manager = BlackBoxRiskManager(
        grid_mgr=grid_mgr,
        beams=beams,
        footings=footings,
        seismic_zone="IV"
    )
    
    manager.check_seismic_hook_detailing()
    
    # Should require 135° hooks
    results = [r for r in manager.results if "Seismic Hook" in r.check_name]
    assert len(results) > 0
    assert results[0].risk_level == RiskLevel.CRITICAL


def test_sanity_weight_vs_reaction():
    """Test sanity check for weight vs reaction."""
    grid_mgr = GridManager(width_m=10.0, length_m=10.0, num_stories=2)
    grid_mgr.generate_grid()
    
    # Set column loads
    for col in grid_mgr.columns:
        if col.level == 0:
            col.load_kn = 500.0
    
    beams = []
    footings = [
        Footing(length_m=1.5, width_m=1.5, thickness_mm=300,
               area_m2=2.25, concrete_vol_m3=1.0, excavation_vol_m3=3.0)
        for _ in range(len([c for c in grid_mgr.columns if c.level == 0]))
    ]
    
    manager = BlackBoxRiskManager(
        grid_mgr=grid_mgr,
        beams=beams,
        footings=footings
    )
    
    manager.check_sanity_weight_vs_reaction()
    
    # Should perform sanity check
    results = [r for r in manager.results if "Sanity Check" in r.check_name]
    assert len(results) > 0


def test_run_all_checks():
    """Test running all checks together."""
    grid_mgr = GridManager(width_m=10.0, length_m=10.0, num_stories=3)
    grid_mgr.generate_grid()
    
    beams = []
    footings = [Footing(length_m=1.5, width_m=1.5, thickness_mm=300,
                       area_m2=2.25, concrete_vol_m3=1.0, excavation_vol_m3=3.0)]
    
    results, report = run_risk_checks(
        grid_mgr=grid_mgr,
        beams=beams,
        footings=footings,
        seismic_zone="IV"
    )
    
    assert len(results) > 0
    assert "RISK MANAGEMENT REPORT" in report
    
    # Check that all major categories are covered
    categories = set(r.category for r in results)
    assert RiskCategory.MODELING in categories
    assert RiskCategory.ANALYSIS in categories
    assert RiskCategory.DETAILING in categories
    assert RiskCategory.COST in categories


def test_format_risk_report():
    """Test risk report formatting."""
    grid_mgr = GridManager(width_m=10.0, length_m=10.0, num_stories=2)
    grid_mgr.generate_grid()
    
    beams = []
    footings = []
    
    manager = BlackBoxRiskManager(
        grid_mgr=grid_mgr,
        beams=beams,
        footings=footings
    )
    
    manager.run_all_checks()
    report = format_risk_report(manager.results)
    
    assert "BLACK BOX RISK MANAGEMENT REPORT" in report
    assert "SUMMARY:" in report
    assert len(manager.results) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
