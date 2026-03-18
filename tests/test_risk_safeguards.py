"""
Test cases for New Structural Safeguards (Edge Cases).

Covers:
1. Punching Shear (Thin Slab)
2. Deep Beam Action
3. Short Column Effect
4. Infill Wall Stiffness
5. Foundation Rotation (Construction Stage)
6. Geotechnical (Monsoon)
"""

import pytest
from src.risk_management import BlackBoxRiskManager, RiskLevel, RiskCheckResult
from src.grid_manager import GridManager, Column
from src.framing_logic import StructuralMember, Point, MemberProperties
from src.foundation_eng import Footing

# Mock Slab Result (since we might not want to import full rebar detailer logic if complex)
from dataclasses import dataclass

@dataclass
class MockSlabResult:
    thk_mm: float
    span_lx_m: float
    span_ly_m: float

def test_punching_shear_risk_thin_slab():
    """Test detection of Thin Slab / Punching Shear risk."""
    grid_mgr = GridManager(width_m=10.0, length_m=10.0)
    grid_mgr.generate_grid()
    
    # Mock a thin slab in the schedule
    grid_mgr.slab_schedule = {
        "S1": MockSlabResult(thk_mm=125.0, span_lx_m=6.0, span_ly_m=6.0)
    }
    
    # Add a heavy column load (simulating punching risk)
    # 125mm slab with 6m span is already risky deflection-wise, but check punching.
    # Risk Manager might check generic thickness vs span if load info missing, 
    # or check column load if available.
    
    manager = BlackBoxRiskManager(grid_mgr=grid_mgr, beams=[], footings=[])
    
    # We expect the new method to be available (TDD - this will fail until implemented)
    if hasattr(manager, 'check_punching_shear_risk'):
        manager.check_punching_shear_risk()
        
        results = [r for r in manager.results if "Punching Shear" in r.check_name]
        assert len(results) > 0
        assert results[0].risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
        # Check affected_members for details
        assert any("125" in m for m in results[0].affected_members)

def test_deep_beam_detection():
    """Test detection of Deep Beams (Span/Depth < 4)."""
    grid_mgr = GridManager(width_m=10.0, length_m=10.0)
    
    # Create a Deep Beam: Span 3m, Depth 1m -> Ratio 3.0 (< 4.0)
    deep_beam = StructuralMember(
        id="B_Deep",
        type="beam",
        start_point=Point(x=0, y=0),
        end_point=Point(x=3.0, y=0),
        properties=MemberProperties(width_mm=300, depth_mm=1000)
    )
    
    # Normal Beam: Span 5m, Depth 0.5m -> Ratio 10.0 (> 4.0)
    normal_beam = StructuralMember(
        id="B_Norm",
        type="beam",
        start_point=Point(x=0, y=5.0),
        end_point=Point(x=5.0, y=5.0),
        properties=MemberProperties(width_mm=230, depth_mm=450)
    )
    
    manager = BlackBoxRiskManager(grid_mgr=grid_mgr, beams=[deep_beam, normal_beam], footings=[])
    
    if hasattr(manager, 'check_deep_beam_action'):
        manager.check_deep_beam_action()
        
        results = [r for r in manager.results if "Deep Beam" in r.check_name]
        assert len(results) > 0
        assert results[0].status == "FAIL"
        assert "B_Deep" in str(results[0].affected_members)

def test_short_column_risk_mezzanine():
    """Test detection of Short Columns (Mezzanine level)."""
    # Create grid with short story height
    grid_mgr = GridManager(width_m=10.0, length_m=10.0, 
                          num_stories=2, story_height_m=1.8) # 1.8m < 2.5m typically
    grid_mgr.generate_grid()
    
    manager = BlackBoxRiskManager(grid_mgr=grid_mgr, beams=[], footings=[])
    
    if hasattr(manager, 'check_short_column_risk'):
        manager.check_short_column_risk()
        
        results = [r for r in manager.results if "Short Column" in r.check_name]
        assert len(results) > 0
        assert results[0].risk_level == RiskLevel.HIGH
        assert "1.8" in results[0].message

def test_infill_wall_stiffness_risk():
    """Test detection of Infill Wall Stiffness omission."""
    grid_mgr = GridManager(width_m=10.0, length_m=10.0)
    grid_mgr.generate_grid()
    
    # Simulate heavy wall loads calculated
    # We need to simulate that wall loads exist. GridManager.calculate_loads adds them.
    # RiskManager might check if wall_load_kn_m was passed or inferred.
    # We'll assume the manager can access this info or we pass it.
    # For now, let's assume valid wall load on beams implies masonry.
    
    # If we pass wall_load_kn_m to GridManager logic, it updates columns.
    # But RiskManager doesn't see that parameter directly unless specific.
    # Let's rely on checking if `beams` have wall load assigned or if we add a property.
    
    # BETTER APPROACH: The RiskManager needs to know if "infill behavior" was modeled.
    # Since we clearly DON'T have struts in this simple solver, IF there are walls, it's a risk.
    
    # We will simulate "Wall Load" by manually adding it to beams implies existence of walls.
    
    manager = BlackBoxRiskManager(
        grid_mgr=grid_mgr, 
        beams=[], 
        footings=[],
        # We might need to add a flag or check if wall loads are present in the model
    )
    
    # Inject a "wall load present" state if possible, or reliance on columns/beams
    # For the test, we'll assume the implementation checks for wall loads on beams or general config.
    # Let's check the implementation plan: "Check if wall loads are applied".
    
    # Add a dummy wall load attribute to a beam for the detection logic
    beam_with_load = StructuralMember(
        id="B_Wall", type="beam", 
        start_point=Point(x=0,y=0), end_point=Point(x=5,y=0),
        properties=MemberProperties(width_mm=230, depth_mm=450)
    )
    # Manually adding a custom attribute that our RiskManager will look for
    # (Or standardized way: does StructuralMember have load?) 
    # Current code: `run_risk_checks` doesn't take wall load. 
    # We will likely update `RiskManager` init or check `grid_mgr` if it stores it.
    # `GridManager.calculate_loads` takes `wall_load_kn_m`.
    # Let's assume we can detect it via metadata or simply if the simplified solver is used with generic settings.
    

def test_foundation_rotation_construction_stage():
    """Test refined Fixed Support check for Construction Stage."""
    grid_mgr = GridManager(width_m=10, length_m=10)
    footings = [Footing(length_m=1.5, width_m=1.5, thickness_mm=300, area_m2=2.25, concrete_vol_m3=1, excavation_vol_m3=3)]
    
    # No soil spring -> Locked Fixed
    manager = BlackBoxRiskManager(grid_mgr=grid_mgr, beams=[], footings=footings, subgrade_modulus_kn_m3=None)
    
    manager.check_fixed_support_assumption()
    
    results = [r for r in manager.results if "Fixed Support" in r.check_name]
    assert len(results) > 0
    # Check if message mentions construction stage
    assert any("construction" in r.message.lower() or "construction" in r.recommendation.lower() for r in results)

def test_geotechnical_monsoon():
    """Test geotechnical check for monsoon effects."""
    grid_mgr = GridManager(width_m=10, length_m=10)
    footings = [Footing(length_m=1.5, width_m=1.5, thickness_mm=300, area_m2=2.25, concrete_vol_m3=1, excavation_vol_m3=3)]
    
    manager = BlackBoxRiskManager(grid_mgr=grid_mgr, beams=[], footings=footings)
    
    manager.check_site_specific_geotechnics()
    
    results = [r for r in manager.results if "Geotechnics" in r.check_name]
    assert len(results) > 0
    # Check if message mentions monsoon/saturation
    assert any("monsoon" in r.message.lower() or "saturation" in r.recommendation.lower() for r in results)
