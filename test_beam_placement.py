"""
Test script to verify IS-code beam placement with a realistic house layout.
"""

from src.beam_placer import BeamPlacer, BeamType, SupportType

# Realistic 12m x 9m Indian house with 4x3 grid layout
columns = [
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

# Walls along all beam lines
walls = [
    # Horizontal walls (X direction)
    ((0, 0), (4000, 0)), ((4000, 0), (8000, 0)), ((8000, 0), (12000, 0)),
    ((0, 4500), (4000, 4500)), ((4000, 4500), (8000, 4500)), ((8000, 4500), (12000, 4500)),
    ((0, 9000), (4000, 9000)), ((4000, 9000), (8000, 9000)), ((8000, 9000), (12000, 9000)),
    # Vertical walls (Y direction)
    ((0, 0), (0, 4500)), ((0, 4500), (0, 9000)),
    ((12000, 0), (12000, 4500)), ((12000, 4500), (12000, 9000)),
]

placer = BeamPlacer(columns=columns, walls=walls, seismic_zone='IV')
result = placer.generate_placement()

print('=== IS-CODE BEAM PLACEMENT VERIFICATION ===')
print(f'Seismic Zone: IV (IS 13920 checks applied)')
print()
print('STATISTICS:')
print(f'  Primary Beams: {result.stats["primary"]}')
print(f'  Secondary Beams: {result.stats["secondary"]}')
print(f'  Slab Panels: {result.stats["slab_panels"]}')
print(f'  Warnings: {result.stats["warnings_count"]}')
print()
print('PRIMARY BEAMS (Sample):')
for b in result.beams[:8]:
    ld_ratio = b.span_mm / b.depth_mm if b.depth_mm > 0 else 0
    bd_ratio = b.width_mm / b.depth_mm
    print(f'  {b.id}: {int(b.width_mm)}x{int(b.depth_mm)}mm, span={b.span_mm:.0f}mm')
    print(f'       L/d={ld_ratio:.1f}, b/D={bd_ratio:.2f}, hidden={b.is_hidden_in_wall}')
    if b.warnings:
        print(f'       Warnings: {b.warnings}')
print()
print('SLAB PANELS:')
for p in placer.slab_panels:
    print(f'  {p.id}: {p.area_m2:.1f}m2, span={p.short_span_mm:.0f}mm, needs_secondary={p.needs_secondary}')
print()
print('JSON Output Sample:')
import json
data = json.loads(result.to_json())
print(f'  Total beams in JSON: {len(data["beams"])}')
print(f'  Total warnings in JSON: {len(data["warnings"])}')
