"""
Test slab generation with multiple house types.
Validates IS 456 compliance for slab sizing and load calculation.
"""

from src.slab_generator import SlabGenerator, SlabType

def test_house(name, columns, walls=None, text_annotations=None):
    print(f"\n{'='*60}")
    print(f"HOUSE: {name}")
    print(f"{'='*60}")
    
    gen = SlabGenerator(
        beams=[],
        columns=columns,
        walls=walls or [],
        text_annotations=text_annotations or [],
        storey_height_mm=3000,
        steel_grade="Fe415"
    )
    result = gen.generate()
    
    print(f"Slabs Generated: {result.stats['total_slabs']}")
    print(f"  One-Way: {result.stats['one_way_slabs']}")
    print(f"  Two-Way: {result.stats['two_way_slabs']}")
    print(f"Total Area: {result.stats['total_slab_area_m2']:.1f} m2")
    print()
    
    print("SLAB DETAILS:")
    for slab in result.slabs:
        ratio = slab.Ly_mm / slab.Lx_mm if slab.Lx_mm > 0 else 0
        print(f"  {slab.id}: {slab.slab_type.value}")
        print(f"       Lx={slab.Lx_mm/1000:.1f}m, Ly={slab.Ly_mm/1000:.1f}m, Ly/Lx={ratio:.2f}")
        print(f"       Thickness: {int(slab.thickness_mm)}mm")
        print(f"       Dead: {slab.total_dead_kn_m2:.2f} kN/m2")
        print(f"       Live: {slab.total_live_kn_m2:.2f} kN/m2")
        print(f"       Factored: {slab.total_factored_kn_m2:.2f} kN/m2")
        if slab.warnings:
            print(f"       Warnings: {slab.warnings}")
    
    return result

# 1BHK Apartment (9m x 6m) - Two-Way Slab
bhk1_columns = [
    {'id': 'C1', 'x': 0, 'y': 0},
    {'id': 'C2', 'x': 4500, 'y': 0},
    {'id': 'C3', 'x': 9000, 'y': 0},
    {'id': 'C4', 'x': 0, 'y': 6000},
    {'id': 'C5', 'x': 4500, 'y': 6000},
    {'id': 'C6', 'x': 9000, 'y': 6000},
]

# 2BHK Standard with corridor
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

# One-Way Slab Case (narrow corridor 2.5m x 6m, Ly/Lx > 2)
corridor_columns = [
    {'id': 'C1', 'x': 0, 'y': 0},
    {'id': 'C2', 'x': 2500, 'y': 0},
    {'id': 'C3', 'x': 0, 'y': 6000},
    {'id': 'C4', 'x': 2500, 'y': 6000},
]

# Staircase Zone Test
stair_columns = [
    {'id': 'C1', 'x': 0, 'y': 0},
    {'id': 'C2', 'x': 3000, 'y': 0},
    {'id': 'C3', 'x': 3000, 'y': 4000},
    {'id': 'C4', 'x': 0, 'y': 4000},
]
stair_annotations = [{'text': 'STAIRCASE', 'x': 1500, 'y': 2000}]

if __name__ == "__main__":
    print("="*60)
    print("SLAB GENERATION - IS 456 VALIDATION")
    print("="*60)
    
    results = []
    
    results.append(test_house("1BHK Apartment (9m x 6m)", bhk1_columns))
    results.append(test_house("2BHK Standard (12m x 9m)", bhk2_columns))
    results.append(test_house("Corridor (One-Way)", corridor_columns))
    results.append(test_house("Staircase Zone", stair_columns, text_annotations=stair_annotations))
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print()
    print("| House | Slabs | Type | Thickness | Load Factor |")
    print("|-------|-------|------|-----------|-------------|")
    
    for r in results:
        for s in r.slabs:
            print(f"| {s.id} | {s.area_m2:.1f}m2 | {s.slab_type.value} | "
                  f"{int(s.thickness_mm)}mm | {s.total_factored_kn_m2:.1f} kN/m2 |")
    
    print()
    print("IS 456 COMPLIANCE CHECK:")
    all_ok = True
    for r in results:
        for s in r.slabs:
            if s.thickness_mm < 125:
                print(f"  FAIL: {s.id} thickness < 125mm")
                all_ok = False
            if s.total_factored_kn_m2 < 5:
                print(f"  WARN: {s.id} factored load seems low")
    
    if all_ok:
        print("  All slabs comply with IS 456 minimum requirements")
