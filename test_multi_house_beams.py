"""
Comprehensive Beam Placement Testing with Different House Types

This script tests the IS-code beam placer against realistic Indian house configurations
and validates against engineering best practices used in real construction.

House Types Tested:
1. 1BHK Apartment (9m x 6m)
2. 2BHK Standard (12m x 9m) 
3. 3BHK Villa (15m x 12m)
4. L-Shaped House (Irregular layout)
5. Large Hall (Single 10m span - tests secondary beams)
"""

from src.beam_placer import BeamPlacer, BeamType, SupportType
import json

def test_house(name, columns, walls, seismic_zone='III'):
    """Run beam placement and compare with engineering standards."""
    placer = BeamPlacer(columns=columns, walls=walls, seismic_zone=seismic_zone)
    result = placer.generate_placement()
    
    print(f"\n{'='*60}")
    print(f"HOUSE TYPE: {name}")
    print(f"{'='*60}")
    print(f"Columns: {len(columns)}")
    print(f"Seismic Zone: {seismic_zone}")
    print()
    
    print("BEAM STATISTICS:")
    print(f"  Primary Beams: {result.stats['primary']}")
    print(f"  Secondary Beams: {result.stats['secondary']}")
    print(f"  Cantilever Beams: {result.stats['cantilever']}")
    print(f"  Slab Panels: {result.stats['slab_panels']}")
    print(f"  Warnings: {result.stats['warnings_count']}")
    print()
    
    # Validate against IS codes
    print("IS-CODE VALIDATION:")
    issues = []
    
    for beam in result.beams:
        # Check L/d ratio (should be 10-15 for residential)
        ld_ratio = beam.span_mm / beam.depth_mm if beam.depth_mm > 0 else 0
        if ld_ratio < 8 or ld_ratio > 20:
            issues.append(f"  {beam.id}: L/d={ld_ratio:.1f} (expected 10-15)")
        
        # Check b/D ratio for seismic zones (IS 13920: b/D >= 0.3)
        bd_ratio = beam.width_mm / beam.depth_mm
        if seismic_zone in ['III', 'IV', 'V'] and bd_ratio < 0.3:
            issues.append(f"  {beam.id}: b/D={bd_ratio:.2f} < 0.3 (IS 13920 violation)")
        
        # Check minimum width (IS 13920: b >= 200mm)
        if seismic_zone in ['III', 'IV', 'V'] and beam.width_mm < 200:
            issues.append(f"  {beam.id}: width={beam.width_mm}mm < 200mm (IS 13920)")
        
        # Check minimum depth
        if beam.depth_mm < 300:
            issues.append(f"  {beam.id}: depth={beam.depth_mm}mm < 300mm minimum")
    
    if issues:
        print("  ISSUES FOUND:")
        for issue in issues:
            print(issue)
    else:
        print("  ✓ All beams comply with IS 456 and IS 13920")
    print()
    
    # Show beam details
    print("BEAM DETAILS:")
    for beam in result.beams[:6]:
        ld = beam.span_mm / beam.depth_mm if beam.depth_mm > 0 else 0
        bd = beam.width_mm / beam.depth_mm
        hidden = "HIDDEN" if beam.is_hidden_in_wall else "VISIBLE"
        print(f"  {beam.id}: {int(beam.width_mm)}x{int(beam.depth_mm)}mm, "
              f"span={beam.span_mm/1000:.1f}m, L/d={ld:.1f}, b/D={bd:.2f} [{hidden}]")
    
    if len(result.beams) > 6:
        print(f"  ... and {len(result.beams) - 6} more beams")
    
    # Slab panels
    if result.slab_panels:
        print()
        print("SLAB PANELS:")
        for panel in result.slab_panels[:4]:
            status = "NEEDS SECONDARY" if panel.needs_secondary else "OK"
            print(f"  {panel.id}: {panel.area_m2:.1f}m2, span={panel.short_span_mm/1000:.1f}m [{status}]")
    
    return result


# ============================================================
# HOUSE TYPE 1: 1BHK Apartment (30ft x 20ft = 9m x 6m)
# Typical urban apartment unit
# ============================================================
bhk1_columns = [
    {'id': 'C1', 'x': 0, 'y': 0},
    {'id': 'C2', 'x': 4500, 'y': 0},
    {'id': 'C3', 'x': 9000, 'y': 0},
    {'id': 'C4', 'x': 0, 'y': 6000},
    {'id': 'C5', 'x': 4500, 'y': 6000},
    {'id': 'C6', 'x': 9000, 'y': 6000},
]

bhk1_walls = [
    ((0, 0), (4500, 0)), ((4500, 0), (9000, 0)),
    ((0, 0), (0, 6000)), ((9000, 0), (9000, 6000)),
    ((0, 6000), (4500, 6000)), ((4500, 6000), (9000, 6000)),
    ((4500, 0), (4500, 6000)),  # Internal partition
]


# ============================================================
# HOUSE TYPE 2: 2BHK Standard (40ft x 30ft = 12m x 9m)
# Common middle-class home layout
# ============================================================
bhk2_columns = [
    {'id': 'C1', 'x': 0, 'y': 0},
    {'id': 'C2', 'x': 4000, 'y': 0},
    {'id': 'C3', 'x': 8000, 'y': 0},
    {'id': 'C4', 'x': 12000, 'y': 0},
    {'id': 'C5', 'x': 0, 'y': 4500},
    {'id': 'C6', 'x': 4000, 'y': 4500},
    {'id': 'C7', 'x': 8000, 'y': 4500},
    {'id': 'C8', 'x': 12000, 'y': 4500},
    {'id': 'C9', 'x': 0, 'y': 9000},
    {'id': 'C10', 'x': 4000, 'y': 9000},
    {'id': 'C11', 'x': 8000, 'y': 9000},
    {'id': 'C12', 'x': 12000, 'y': 9000},
]

bhk2_walls = [
    # Outer walls
    ((0, 0), (4000, 0)), ((4000, 0), (8000, 0)), ((8000, 0), (12000, 0)),
    ((0, 9000), (4000, 9000)), ((4000, 9000), (8000, 9000)), ((8000, 9000), (12000, 9000)),
    ((0, 0), (0, 4500)), ((0, 4500), (0, 9000)),
    ((12000, 0), (12000, 4500)), ((12000, 4500), (12000, 9000)),
    # Internal partitions
    ((4000, 0), (4000, 4500)),  # Bedroom 1 wall
    ((8000, 4500), (8000, 9000)),  # Bedroom 2 wall
]


# ============================================================
# HOUSE TYPE 3: 3BHK Villa (50ft x 40ft = 15m x 12m)
# Larger villa with living hall
# ============================================================
bhk3_columns = [
    {'id': 'C1', 'x': 0, 'y': 0},
    {'id': 'C2', 'x': 5000, 'y': 0},
    {'id': 'C3', 'x': 10000, 'y': 0},
    {'id': 'C4', 'x': 15000, 'y': 0},
    {'id': 'C5', 'x': 0, 'y': 6000},
    {'id': 'C6', 'x': 5000, 'y': 6000},
    {'id': 'C7', 'x': 10000, 'y': 6000},
    {'id': 'C8', 'x': 15000, 'y': 6000},
    {'id': 'C9', 'x': 0, 'y': 12000},
    {'id': 'C10', 'x': 5000, 'y': 12000},
    {'id': 'C11', 'x': 10000, 'y': 12000},
    {'id': 'C12', 'x': 15000, 'y': 12000},
]

bhk3_walls = [
    # Outer walls
    ((0, 0), (5000, 0)), ((5000, 0), (10000, 0)), ((10000, 0), (15000, 0)),
    ((0, 12000), (5000, 12000)), ((5000, 12000), (10000, 12000)), ((10000, 12000), (15000, 12000)),
    ((0, 0), (0, 6000)), ((0, 6000), (0, 12000)),
    ((15000, 0), (15000, 6000)), ((15000, 6000), (15000, 12000)),
    # Internal partitions 
    ((5000, 0), (5000, 6000)),   # Bedroom partition
    ((10000, 6000), (10000, 12000)),  # Living/Kitchen partition
]


# ============================================================
# HOUSE TYPE 4: L-Shaped House (Irregular layout)
# Tests handling of non-rectangular layouts
# ============================================================
lshape_columns = [
    {'id': 'C1', 'x': 0, 'y': 0},
    {'id': 'C2', 'x': 5000, 'y': 0},
    {'id': 'C3', 'x': 10000, 'y': 0},
    {'id': 'C4', 'x': 0, 'y': 5000},
    {'id': 'C5', 'x': 5000, 'y': 5000},
    {'id': 'C6', 'x': 10000, 'y': 5000},
    {'id': 'C7', 'x': 0, 'y': 10000},
    {'id': 'C8', 'x': 5000, 'y': 10000},
    # L-shape: no columns at (10000, 10000)
]

lshape_walls = [
    ((0, 0), (5000, 0)), ((5000, 0), (10000, 0)),
    ((10000, 0), (10000, 5000)),
    ((10000, 5000), (5000, 5000)),
    ((5000, 5000), (5000, 10000)),
    ((5000, 10000), (0, 10000)),
    ((0, 10000), (0, 5000)), ((0, 5000), (0, 0)),
]


# ============================================================
# HOUSE TYPE 5: Large Hall (Single 10m span - tests secondary beams)
# Wedding hall / function room with large open space
# ============================================================
hall_columns = [
    {'id': 'C1', 'x': 0, 'y': 0},
    {'id': 'C2', 'x': 10000, 'y': 0},
    {'id': 'C3', 'x': 0, 'y': 8000},
    {'id': 'C4', 'x': 10000, 'y': 8000},
]

hall_walls = [
    ((0, 0), (10000, 0)),
    ((10000, 0), (10000, 8000)),
    ((10000, 8000), (0, 8000)),
    ((0, 8000), (0, 0)),
]


# ============================================================
# RUN ALL TESTS
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("IS-CODE BEAM PLACEMENT - MULTI-HOUSE VALIDATION")
    print("Comparing against real engineering practices")
    print("=" * 60)
    
    results = []
    
    # Run tests
    results.append(("1BHK Apartment (9m x 6m)", 
                   test_house("1BHK Apartment (9m x 6m)", bhk1_columns, bhk1_walls, "III")))
    
    results.append(("2BHK Standard (12m x 9m)", 
                   test_house("2BHK Standard (12m x 9m)", bhk2_columns, bhk2_walls, "IV")))
    
    results.append(("3BHK Villa (15m x 12m)", 
                   test_house("3BHK Villa (15m x 12m)", bhk3_columns, bhk3_walls, "III")))
    
    results.append(("L-Shaped House", 
                   test_house("L-Shaped House", lshape_columns, lshape_walls, "III")))
    
    results.append(("Large Hall (10m span)", 
                   test_house("Large Hall (10m span)", hall_columns, hall_walls, "IV")))
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY - REAL-WORLD ENGINEERING COMPARISON")
    print("=" * 60)
    print()
    print("| House Type | Beams | Panels | L/d Range | Status |")
    print("|------------|-------|--------|-----------|--------|")
    
    for name, result in results:
        beams = len(result.beams)
        panels = len(result.slab_panels)
        if result.beams:
            ld_min = min(b.span_mm / b.depth_mm for b in result.beams if b.depth_mm > 0)
            ld_max = max(b.span_mm / b.depth_mm for b in result.beams if b.depth_mm > 0)
            ld_range = f"{ld_min:.1f}-{ld_max:.1f}"
        else:
            ld_range = "N/A"
        status = "OK" if result.stats['warnings_count'] < 3 else "REVIEW"
        short_name = name[:20]
        print(f"| {short_name:20} | {beams:5} | {panels:6} | {ld_range:9} | {status:6} |")
    
    print()
    print("ENGINEERING STANDARDS USED:")
    print("  - IS 456:2000 - L/d ratios for beam depth")
    print("  - IS 13920:2016 - Seismic detailing (b/D >= 0.3, b >= 200mm)")
    print("  - Min depth 300mm for residential")
    print("  - Secondary beams for panels > 35m2 or span > 6m")
    print("  - Wall thickness 230mm for hidden beams")
