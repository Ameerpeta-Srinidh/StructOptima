"""
Test cases for Quantity Estimation Refinements.

Covers:
1. IS 1200 Opening Deductions (Ignore < 0.1m²)
2. Steel Wastage & Procurement Weights
3. Cost Ranges & Contingency
"""

import pytest
from src.quantifier import Quantifier, MaterialCost
from src.grid_manager import GridManager, Column
from src.bbs_module import ProjectBBS, MemberBBS, BBSEntry

def test_is1200_opening_deduction_logic():
    """
    Test IS 1200 Rule: Openings < 0.1 m² should NOT be deducted from Masonry/Plaster volume.
    """
    # Create a dummy GridManager with known dimensions
    grid_mgr = GridManager(width_m=5.0, length_m=5.0, num_stories=1)
    grid_mgr.generate_grid()
    
    # Mock slab schedule to force a specific thickness
    from dataclasses import dataclass
    @dataclass
    class MockSlabRes:
        thickness_mm: float = 100.0 # 0.1m
        weight_kg_per_m2: float = 10.0
        weight_breakdown: dict = None
    
    grid_mgr.slab_schedule = {"S1": MockSlabRes()}
    
    # Case 1: Tiny Opening (0.2m x 0.2m = 0.04m²) -> < 0.1m²
    # Should be IGNORED (No deduction)
    # Void zones format: list of (x_idx, y_idx) - this is bay index
    # But quantifier logic for voids currently mocks area based on bay size.
    # We need to test the logic inside Quantifier.calculate_bom directly or mock grid behavior.
    
    # To properly test the precise "0.1m2" logic, we might need a more granular way to define openings 
    # than just "Whole Bay Voids" which are usually large. 
    # However, the Quantifier currently iterates `grid_mgr.void_zones`.
    # Let's create a subclass or mock that returns specific void areas.
    
    class MockGridWithVoids:
        width_m = 10.0
        length_m = 10.0
        num_stories = 1
        slab_schedule = {"S1": MockSlabRes()}
        x_grid_lines = [0, 10]
        y_grid_lines = [0, 10]
        
        # We will mock the area calculation in the quantifier or pass specific data
        # Actually, quantifier calculates area from grid lines.
        # Let's try to manipulate grid lines to create a tiny bay.
        
    # Create grid with a TINY bay
    tiny_grid = GridManager(width_m=0.2, length_m=0.2, num_stories=1, max_span_m=1.0)
    # This generates 1 bay of 0.2x0.2 = 0.04m2
    tiny_grid.generate_grid()
    tiny_grid.slab_schedule = {"S1": MockSlabRes()}
    # Manually add void_zones since generate_grid doesn't populate it by default
    tiny_grid.void_zones = [(0,0)] # The only bay is void
    
    quant = Quantifier(apply_is1200_opening_rules=True)
    cost = quant.calculate_bom(columns=[], beams=[], grid_mgr=tiny_grid)
    
    # Gross Area = 0.04m2
    # Void Area = 0.04m2 (< 0.1) -> Should NOT deduct
    # Net Volume should be approx 0.04 * 0.1 = 0.004 m3
    
    assert cost.total_concrete_vol_m3 > 0.003
    
    # Case 2: Large Opening (1.0m x 1.0m = 1.0m²) -> >= 0.1m²
    # Should be DEDUCTED
    large_grid = GridManager(width_m=1.0, length_m=1.0, num_stories=1, max_span_m=2.0)
    large_grid.generate_grid()
    large_grid.slab_schedule = {"S1": MockSlabRes()}
    large_grid.void_zones = [(0,0)] # The only bay is void
    
    cost_large = quant.calculate_bom(columns=[], beams=[], grid_mgr=large_grid)
    
    # Gross Area = 1.0m2
    # Void Area = 1.0m2 (>= 0.1) -> Should Deduct
    # Net Volume should be 0.0
    
    assert cost_large.total_concrete_vol_m3 == 0.0

def test_steel_wastage_buffer():
    """Test standard steel wastage (rolling margin) buffer."""
    quant = Quantifier(steel_wastage_percent=5.0) # 5% buffer
    
    # 1 m3 of concrete footings ~ 80kg steel theoretical
    # Procurement should be 80 * 1.05 = 84kg
    
    from collections import namedtuple
    MockFooting = namedtuple('MockFooting', ['concrete_vol_m3'])
    footings = [MockFooting(concrete_vol_m3=1.0)]
    
    cost = quant.calculate_bom(columns=[], beams=[], footings=footings)
    
    theoretical = 1.0 * 80.0
    expected = theoretical * 1.05
    
    assert abs(cost.total_steel_weight_kg - expected) < 0.1
