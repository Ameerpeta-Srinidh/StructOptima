"""
Demonstration of BBS Enhancement and Quantity Takeoff
"""

from src.bbs_module import (
    generate_beam_bbs, generate_column_bbs, generate_slab_bbs,
    BeamBBSInput, ColumnBBSInput, SlabBBSInput,
    seismic_hook_extension, confined_zone_stirrup_spacing, lap_splice_length,
    format_bbs_table
)
from src.quantity_takeoff import QuantityTakeoff

print("=" * 60)
print("BBS & QUANTITY TAKEOFF DEMO")
print("=" * 60)

print("\n" + "-" * 60)
print("IS 13920 DUCTILE DETAILING")
print("-" * 60)

print("\nSeismic Hook Extension (6d or 65mm min):")
for dia in [8, 10, 12, 16]:
    ext = seismic_hook_extension(dia)
    print(f"  {dia}mm bar: {ext}mm (6×{dia}={6*dia}mm)")

print("\nConfined Zone Stirrup Spacing:")
for d, bar_dia in [(400, 12), (450, 16), (600, 16)]:
    spacing = confined_zone_stirrup_spacing(d, bar_dia)
    print(f"  d={d}mm, bar={bar_dia}mm → {spacing:.0f}mm max")

print("\nLap Splice Length:")
for pct in [50, 75, 100]:
    lap = lap_splice_length(16, bars_lapped_percent=pct)
    print(f"  16mm, {pct}% lapped → {lap:.0f}mm")

beam = BeamBBSInput(
    member_id="B1", length_mm=6000, width_mm=230, depth_mm=450,
    main_bar_dia_mm=16, top_bars=2, bottom_bars=4,
    stirrup_dia_mm=8, stirrup_spacing_mm=150
)
beam_bbs = generate_beam_bbs(beam)

column = ColumnBBSInput(
    member_id="C1", height_mm=3000, width_mm=300, depth_mm=400,
    main_bar_dia_mm=16, num_bars=8, tie_dia_mm=8, tie_spacing_mm=150
)
col_bbs = generate_column_bbs(column)

slab = SlabBBSInput(
    member_id="S1", lx_mm=4000, ly_mm=5000, thickness_mm=150,
    main_bar_dia_mm=10, main_bar_spacing_mm=150,
    dist_bar_dia_mm=8, dist_bar_spacing_mm=200
)
slab_bbs = generate_slab_bbs(slab)

print("\n" + "-" * 60)
print("QUANTITY TAKEOFF")
print("-" * 60)

qt = QuantityTakeoff(concrete_grade="M25", steel_grade="Fe415")

qt.add_beam("B1", 6000, 230, 450)
qt.add_beam("B2", 5000, 230, 450)
qt.add_column("C1", 3000, 300, 400)
qt.add_column("C2", 3000, 300, 400)
qt.add_slab("S1", 5000, 4000, 150)

bbs_steel = {
    8: beam_bbs.total_weight_kg + col_bbs.total_weight_kg + slab_bbs.total_weight_kg * 0.3,
    10: slab_bbs.total_weight_kg * 0.7,
    16: beam_bbs.total_weight_kg * 2 + col_bbs.total_weight_kg
}
qt.add_steel_from_bbs(bbs_steel)

print(qt.generate_boq_report(built_up_area_sqft=500))

print("\n" + "-" * 60)
print("JSON OUTPUT")
print("-" * 60)
print(qt.to_json(built_up_area_sqft=500))
