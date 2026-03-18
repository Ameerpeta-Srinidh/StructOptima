"""
Demonstration of Analysis Configuration for G+4 Residential Building
"""

from src.analysis_config import AnalysisConfigGenerator

gen = AnalysisConfigGenerator(
    zone="IV",
    soil_type="II",
    frame_type="SMRF",
    importance_factor=1.0,
    num_storeys=5,
    storey_height_m=3.0,
    plan_cutout_percent=10,
    include_wind=True
)

for i in range(1, 5):
    gen.add_floor_mass(
        floor_id=f"Floor {i}",
        level_m=i * 3.0,
        dead_load_kn=800,
        live_load_kn=320,
        live_load_intensity_kn_m2=2.0,
        is_roof=False
    )

gen.add_floor_mass(
    floor_id="Roof",
    level_m=15.0,
    dead_load_kn=500,
    live_load_kn=150,
    live_load_intensity_kn_m2=1.5,
    is_roof=True
)

config = gen.generate()

print("=" * 60)
print("ANALYSIS CONFIGURATION - G+4 RESIDENTIAL (ZONE IV)")
print("=" * 60)
print()
print("SEISMIC PARAMETERS:")
sp = config.seismic_params
print(f"  Zone: {sp.zone} (Z = {sp.zone_factor})")
print(f"  Frame Type: {sp.frame_type.value} (R = {sp.response_reduction})")
print(f"  Importance Factor (I): {sp.importance_factor}")
print()
print("STIFFNESS MODIFIERS (IS 1893 Cl 6.4.3):")
sm = config.stiffness_modifiers
print(f"  Columns: {sm.columns} I_gross")
print(f"  Beams: {sm.beams} I_gross")
print(f"  Slabs: {sm.slabs} I_gross")
print()
print("P-DELTA SETTINGS:")
pd = config.p_delta
print(f"  Enabled: {pd.enabled}")
print(f"  Reason: {pd.reason}")
print()
print("SEISMIC MASS:")
print(f"  Total Seismic Weight: {config.total_seismic_weight_kn:.0f} kN")
for fm in config.floor_masses:
    ll_factor = 0.25 if fm.live_load_intensity_kn_m2 <= 3.0 else 0.50
    if fm.is_roof:
        ll_factor = 0.0
    print(f"  {fm.floor_id}: DL={fm.dead_load_kn:.0f}kN + "
          f"{ll_factor*100:.0f}%×LL = {fm.seismic_mass_kn:.0f}kN")
print()
print("LOAD COMBINATIONS:")
print(f"  Total: {len(config.load_combinations)}")
critical = [c for c in config.load_combinations if c.get('is_critical')]
print(f"  Critical (Uplift): {len(critical)}")
print()
print("Sample Combinations:")
for i, combo in enumerate(config.load_combinations[:6]):
    print(f"  {combo['id']}: {combo['name']}")
print("  ...")
for combo in critical[:2]:
    print(f"  {combo['id']}: {combo['name']} [CRITICAL]")
print()
if config.warnings:
    print("WARNINGS:")
    for w in config.warnings:
        print(f"  - {w}")
