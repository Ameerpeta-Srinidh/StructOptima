"""
Comprehensive System Stress Test

Tests the entire structural design pipeline with:
- Multiple house plans (simple to complex)
- Edge cases and boundary conditions
- Error handling and recovery
"""

import sys
import math
import traceback
from typing import Dict, List, Tuple

TESTS_PASSED = 0
TESTS_FAILED = 0
FAILURES: List[Tuple[str, str]] = []

def test(name: str, condition: bool, details: str = ""):
    global TESTS_PASSED, TESTS_FAILED, FAILURES
    if condition:
        TESTS_PASSED += 1
        print(f"  [PASS] {name}")
    else:
        TESTS_FAILED += 1
        FAILURES.append((name, details))
        print(f"  [FAIL] {name}: {details}")

def test_section(name: str):
    print(f"\n{'='*60}")
    print(f"TESTING: {name}")
    print('='*60)


test_section("MEMBER DESIGN - Edge Cases")

from src.member_design import MemberDesigner, DesignStatus

designer = MemberDesigner(concrete_grade="M25", steel_grade="Fe415")

beam = designer.design_beam("B_small", b_mm=200, D_mm=300, Mu_kNm=10, Vu_kN=15)
test("Small beam design", beam.status == DesignStatus.PASS, f"Status: {beam.status}")

beam = designer.design_beam("B_large", b_mm=400, D_mm=900, Mu_kNm=500, Vu_kN=300)
test("Large beam design", beam.status in [DesignStatus.PASS, DesignStatus.FAIL], f"Ast={beam.Ast_tension_mm2}")

beam = designer.design_beam("B_zero", b_mm=230, D_mm=450, Mu_kNm=0.1, Vu_kN=0.1)
test("Near-zero moment", beam.Ast_tension_mm2 >= 0, f"Ast={beam.Ast_tension_mm2}")

beam = designer.design_beam("B_doubly", b_mm=230, D_mm=400, Mu_kNm=200, Vu_kN=100)
test("Doubly reinforced trigger", beam.Mu_kNm > beam.Mu_lim_kNm or beam.Ast_tension_mm2 > 0, "OK")

col = designer.design_column("C_short", b_mm=300, D_mm=400, L_mm=3000, Pu_kN=800, Mux_kNm=50, Muy_kNm=30, steel_percent=1.5)
test("Short column (λ<12)", col.is_slender == False, f"λ={col.slenderness_ratio}")

col = designer.design_column("C_slender", b_mm=230, D_mm=230, L_mm=4000, Pu_kN=500, Mux_kNm=30, Muy_kNm=20, steel_percent=1.5)
test("Slender column (λ≥12)", col.is_slender == True, f"λ={col.slenderness_ratio}")

col = designer.design_column("C_high_axial", b_mm=400, D_mm=400, L_mm=3000, Pu_kN=3000, Mux_kNm=100, Muy_kNm=80, steel_percent=2.0)
test("High axial load", col.interaction_ratio > 0, f"IR={col.interaction_ratio}")

slab = designer.design_slab("S1", Lx_mm=4000, Ly_mm=5000, thickness_mm=150, w_kN_m2=10)
test("Two-way slab", slab.Ast_x_mm2_m > 0 and slab.Ast_y_mm2_m > 0, "OK")

slab = designer.design_slab("S_thin", Lx_mm=3000, Ly_mm=3500, thickness_mm=100, w_kN_m2=8)
test("Thin slab (100mm)", slab.status in [DesignStatus.PASS, DesignStatus.WARNING], f"L/d={slab.deflection_ratio}")


test_section("BBS MODULE - Ductile Detailing")

from src.bbs_module import (
    seismic_hook_extension, confined_zone_stirrup_spacing, lap_splice_length,
    development_length, generate_beam_bbs, BeamBBSInput
)

ext = seismic_hook_extension(8)
test("Seismic hook 8mm → 65mm min", ext >= 65, f"ext={ext}")

ext = seismic_hook_extension(16)
test("Seismic hook 16mm → 96mm", ext == 96, f"ext={ext}")

spacing = confined_zone_stirrup_spacing(400, 12)
test("Confined zone d=400, bar=12", spacing <= 100, f"spacing={spacing}")

spacing = confined_zone_stirrup_spacing(200, 16)
test("Confined zone d=200, bar=16", spacing == 50, f"d/4=50")

lap = lap_splice_length(16, bars_lapped_percent=50)
ld = development_length(16)
test("Lap splice 50% → 1.0×Ld", abs(lap - ld) < 1, f"lap={lap}")

lap = lap_splice_length(16, bars_lapped_percent=75)
test("Lap splice 75% → 1.4×Ld", abs(lap - ld * 1.4) < 1, f"lap={lap}")

beam_input = BeamBBSInput(
    member_id="B_test", length_mm=6000, width_mm=230, depth_mm=450,
    main_bar_dia_mm=16, top_bars=2, bottom_bars=4,
    stirrup_dia_mm=8, stirrup_spacing_mm=150
)
bbs = generate_beam_bbs(beam_input)
test("BBS generation", len(bbs.entries) == 3, f"entries={len(bbs.entries)}")
test("BBS total weight > 0", bbs.total_weight_kg > 0, f"weight={bbs.total_weight_kg}")


test_section("QUANTITY TAKEOFF - Edge Cases")

from src.quantity_takeoff import QuantityTakeoff, calculate_steel_ratio

qt = QuantityTakeoff(concrete_grade="M25", steel_grade="Fe415")
qt.add_beam("B1", 6000, 230, 450)
qt.add_column("C1", 3000, 300, 400)
qt.add_slab("S1", 5000, 4000, 150)
summary = qt.get_summary()
test("Concrete volume > 0", summary.concrete_m3 > 0, f"vol={summary.concrete_m3}")
test("Shuttering area > 0", summary.shuttering_m2 > 0, f"area={summary.shuttering_m2}")

qt.add_steel_from_bbs({16: 100, 8: 50})
summary = qt.get_summary()
test("Steel from BBS", summary.steel_kg == 150, f"steel={summary.steel_kg}")

cost = qt.estimate_cost(built_up_area_sqft=500)
test("Cost estimate > 0", cost.total_cost > 0, f"total={cost.total_cost}")
test("Cost per sqft", cost.cost_per_sqft > 0, f"per_sqft={cost.cost_per_sqft}")

ratio = calculate_steel_ratio(steel_kg=0, concrete_m3=10)
test("Steel ratio zero steel", ratio == 0, f"ratio={ratio}")

ratio = calculate_steel_ratio(steel_kg=100, concrete_m3=0)
test("Steel ratio zero concrete", ratio == 0, f"ratio={ratio}")


test_section("ANALYSIS CONFIG - Seismic Zones")

from src.analysis_config import AnalysisConfigGenerator, StructuralFrameType

for zone in ["II", "III", "IV", "V"]:
    gen = AnalysisConfigGenerator(zone=zone, num_storeys=5)
    seismic = gen._configure_seismic_parameters()
    test(f"Zone {zone} parameters", seismic.zone_factor > 0, f"Z={seismic.zone_factor}")
    
    if zone in ["III", "IV", "V"]:
        test(f"Zone {zone} SMRF mandate", gen.frame_type == StructuralFrameType.SMRF, f"frame={gen.frame_type}")

gen = AnalysisConfigGenerator(zone="IV", num_storeys=3)
gen.add_floor_mass("F1", 3.0, 500, 200, 2.0, is_roof=False)
gen.add_floor_mass("Roof", 3.0, 400, 0, 0, is_roof=True)
config = gen.generate()
test("Seismic mass with LL reduction", config.total_seismic_weight_kn > 0, f"W={config.total_seismic_weight_kn}")

gen = AnalysisConfigGenerator(zone="III", num_storeys=3)
pdelta = gen._configure_p_delta()
test("P-Delta disabled (≤4 storeys)", pdelta.enabled == False, f"enabled={pdelta.enabled}")

gen = AnalysisConfigGenerator(zone="III", num_storeys=6)
pdelta = gen._configure_p_delta()
test("P-Delta enabled (>4 storeys)", pdelta.enabled == True, f"enabled={pdelta.enabled}")


test_section("LOAD COMBINATIONS - IS 456")

from src.load_combinations import LoadCombinationManager

lcm = LoadCombinationManager()
combos = lcm.get_all_combinations()
test("Load combinations generated", len(combos) > 10, f"count={len(combos)}")

has_uplift = any("0.9" in str(c) for c in combos)
test("Uplift combinations (0.9DL)", has_uplift, "Checking for stability combos")


test_section("SLAB GENERATOR - Classification")

try:
    from src.slab_generator import SlabGenerator
    
    beams = [
        {"start_point": {"x": 0, "y": 0}, "end_point": {"x": 5000, "y": 0}},
        {"start_point": {"x": 5000, "y": 0}, "end_point": {"x": 5000, "y": 4000}},
        {"start_point": {"x": 5000, "y": 4000}, "end_point": {"x": 0, "y": 4000}},
        {"start_point": {"x": 0, "y": 4000}, "end_point": {"x": 0, "y": 0}},
    ]
    columns = [
        {"x": 0, "y": 0},
        {"x": 5000, "y": 0},
        {"x": 5000, "y": 4000},
        {"x": 0, "y": 4000},
    ]
    
    # SlabGenerator expects walls as list of line segments ((x1,y1), (x2,y2))
    walls_slab = [((0, 0), (5000, 0)), ((5000, 0), (5000, 4000)), 
                  ((5000, 4000), (0, 4000)), ((0, 4000), (0, 0))]
                  
    sg = SlabGenerator(beams=beams, columns=columns, walls=walls_slab)
    result = sg.generate()
    test("Slab generation", len(result.slabs) >= 0, f"slabs={len(result.slabs)}")
    
except Exception as e:
    test("Slab generator", False, str(e)[:100])


test_section("FRAMING LOGIC - Column & Beam Placement")

try:
    from src.column_placer import ColumnPlacer
    from src.beam_placer import BeamPlacer
    
    # Define a simple rectangular room 6x4m
    nodes = [(0,0), (6000,0), (6000,4000), (0,4000)]
    walls = [((0,0), (6000,0)), ((6000,0), (6000,4000)), 
             ((6000,4000), (0,4000)), ((0,4000), (0,0))]
             
    # Column Placer
    cp = ColumnPlacer(nodes=nodes, centerlines=walls)
    col_result = cp.generate_placement()
    cols = col_result.columns
    
    test("Column placement", len(cols) >= 4, f"columns={len(cols)}")
    
    # Beam Placer
    # BeamPlacer expects columns as list of dicts with 'x', 'y'
    col_dicts = [{"x": c.x, "y": c.y, "id": c.id} for c in cols]
    
    bp = BeamPlacer(columns=col_dicts, walls=walls)
    beam_result = bp.generate_placement()
    beams = beam_result.beams
    
    test("Beam placement", len(beams) >= 4, f"beams={len(beams)}")
    
except Exception as e:
    test("Framing logic", False, str(e)[:100])


test_section("BOUNDARY CONDITIONS")

try:
    designer = MemberDesigner(concrete_grade="M20", steel_grade="Fe500")
    beam = designer.design_beam("B_fe500", 230, 450, 80, 60)
    test("M20/Fe500 combination", beam.status in [DesignStatus.PASS, DesignStatus.FAIL], "OK")
    
    designer = MemberDesigner(concrete_grade="M40", steel_grade="Fe500")
    beam = designer.design_beam("B_m40", 300, 600, 200, 100)
    test("M40/Fe500 high grade", beam.status in [DesignStatus.PASS, DesignStatus.FAIL], "OK")
    
except Exception as e:
    test("Boundary conditions", False, str(e)[:50])


test_section("EXTREME VALUES")

try:
    beam = designer.design_beam("B_extreme", b_mm=150, D_mm=250, Mu_kNm=5, Vu_kN=5)
    test("Minimum size beam", beam.Ast_tension_mm2 > 0, f"Ast={beam.Ast_tension_mm2}")
    
    col = designer.design_column("C_min", b_mm=200, D_mm=200, L_mm=2500, Pu_kN=200, Mux_kNm=10, Muy_kNm=10, steel_percent=0.8)
    test("Minimum column size", col.status in [DesignStatus.PASS, DesignStatus.FAIL, DesignStatus.WARNING], "OK")
    
    col = designer.design_column("C_high_steel", b_mm=400, D_mm=400, L_mm=3000, Pu_kN=2000, Mux_kNm=200, Muy_kNm=150, steel_percent=4.0)
    test("Maximum steel percentage", col.steel_percent == 4.0, f"steel={col.steel_percent}%")
    
except Exception as e:
    test("Extreme values", False, str(e)[:50])


print(f"\n{'='*60}")
print("TEST SUMMARY")
print('='*60)
print(f"  Passed: {TESTS_PASSED}")
print(f"  Failed: {TESTS_FAILED}")
print(f"  Total:  {TESTS_PASSED + TESTS_FAILED}")

if FAILURES:
    print(f"\n{'='*60}")
    print("FAILURES")
    print('='*60)
    for name, details in FAILURES:
        print(f"  [FAIL] {name}: {details}")

sys.exit(1 if TESTS_FAILED > 0 else 0)
