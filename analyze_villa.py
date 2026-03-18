"""
Run column placement and generate visualization for complex_villa.dxf
"""

from src.cad_loader import CADLoader
import json

loader = CADLoader('complex_villa.dxf')
gm, beams = loader.load_grid_manager(auto_frame=True, seismic_zone='III')

print('=== COLUMN PLACEMENT RESULTS ===')
print(f'Total Columns: {len(gm.columns)}')
print(f'Total Beams: {len(beams)}')
print()
print('Column Details:')
for c in gm.columns:
    print(f'  {c.id}: ({c.x:.2f}m, {c.y:.2f}m) - {c.junction_type} - {int(c.width_nb)}x{int(c.depth_nb)}mm')
print()
print('Placement Stats:')
print(json.dumps(loader.placement_stats, indent=2))
print()
print('Warnings:')
for w in loader.placement_warnings:
    print(f'  [{w["severity"]}] {w["message"]}')

html = '''<!DOCTYPE html>
<html>
<head>
    <title>Complex Villa - Column Placement</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #1a1a2e; color: #fff; }
        h1 { color: #4cc9f0; text-align: center; }
        .container { display: flex; gap: 20px; }
        .plan { flex: 2; }
        .legend { flex: 1; background: #16213e; padding: 20px; border-radius: 10px; }
        svg { background: #0f0f23; border-radius: 10px; }
        .wall { stroke: #888; stroke-width: 2; }
        .column { fill: #f72585; stroke: #fff; stroke-width: 1; }
        .column-corner { fill: #4cc9f0; }
        .column-t { fill: #7209b7; }
        .column-cross { fill: #f72585; }
        .column-edge { fill: #4361ee; }
        .label { font-size: 10px; fill: #fff; }
        .stats { margin-top: 20px; }
        .stat-item { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #333; }
        .dot { width: 15px; height: 15px; border-radius: 3px; display: inline-block; margin-right: 10px; }
    </style>
</head>
<body>
    <h1>Complex Villa Floor Plan - IS-Code Column Placement</h1>
    <div class="container">
        <div class="plan">
            <svg viewBox="-200 -200 2200 1800" width="800" height="600">
'''

scale = 0.1

walls = [
    ((0, 0), (18000, 0)), ((18000, 0), (18000, 12000)),
    ((18000, 12000), (0, 12000)), ((0, 12000), (0, 0)),
    ((6000, 0), (6000, 5000)), ((6000, 5000), (0, 5000)),
    ((6000, 7000), (0, 7000)), ((6000, 7000), (6000, 12000)),
    ((12000, 0), (12000, 5000)), ((12000, 5000), (6000, 5000)),
    ((12000, 7000), (6000, 7000)), ((12000, 7000), (12000, 12000)),
    ((6000, 5000), (6000, 7000)), ((15000, 0), (15000, 5000)),
    ((15000, 5000), (18000, 5000)), ((15000, 7000), (18000, 7000)),
    ((15000, 7000), (15000, 12000)), ((12000, 5000), (12000, 7000)),
    ((15000, 5000), (15000, 7000)), ((3000, 5000), (3000, 7000)),
    ((13500, 5000), (13500, 7000)),
    ((-1500, 2000), (-1500, 5000)), ((-1500, 2000), (0, 2000)), ((-1500, 5000), (0, 5000)),
    ((-1500, 7000), (-1500, 10000)), ((-1500, 7000), (0, 7000)), ((-1500, 10000), (0, 10000)),
    ((18000, 2000), (19500, 2000)), ((19500, 2000), (19500, 5000)), ((19500, 5000), (18000, 5000)),
    ((18000, 7000), (19500, 7000)), ((19500, 7000), (19500, 10000)), ((19500, 10000), (18000, 10000)),
    ((6000, 12000), (6000, 13500)), ((6000, 13500), (12000, 13500)), ((12000, 13500), (12000, 12000)),
]

for (x1, y1), (x2, y2) in walls:
    html += f'<line x1="{x1*scale}" y1="{(14000-y1)*scale}" x2="{x2*scale}" y2="{(14000-y2)*scale}" class="wall"/>\n'

for c in gm.columns:
    x = c.x * 1000 * scale
    y = (14000 - c.y * 1000) * scale
    size = 8
    
    jtype = c.junction_type
    cls = 'column'
    if 'corner' in jtype.lower():
        cls += ' column-corner'
    elif 't' in jtype.lower() or 't_' in jtype.lower():
        cls += ' column-t'
    elif 'cross' in jtype.lower():
        cls += ' column-cross'
    else:
        cls += ' column-edge'
    
    html += f'<rect x="{x-size/2}" y="{y-size/2}" width="{size}" height="{size}" class="{cls}"/>\n'
    html += f'<text x="{x}" y="{y-12}" class="label" text-anchor="middle">{c.id}</text>\n'

html += '''
            </svg>
        </div>
        <div class="legend">
            <h3>Legend</h3>
            <p><span class="dot" style="background:#4cc9f0"></span> Corner Column</p>
            <p><span class="dot" style="background:#7209b7"></span> T-Junction Column</p>
            <p><span class="dot" style="background:#f72585"></span> Cross-Junction Column</p>
            <p><span class="dot" style="background:#4361ee"></span> Edge Column</p>
            
            <div class="stats">
                <h3>Placement Statistics</h3>
'''

html += f'''
                <div class="stat-item"><span>Total Columns</span><span>{len(gm.columns)}</span></div>
                <div class="stat-item"><span>Corners</span><span>{loader.placement_stats.get('corners', 0)}</span></div>
                <div class="stat-item"><span>T-Junctions</span><span>{loader.placement_stats.get('t_junctions', 0)}</span></div>
                <div class="stat-item"><span>Cross-Junctions</span><span>{loader.placement_stats.get('cross_junctions', 0)}</span></div>
                <div class="stat-item"><span>Edge</span><span>{loader.placement_stats.get('edge', 0)}</span></div>
                <div class="stat-item"><span>Seismic Zone</span><span>{loader.placement_stats.get('seismic_zone', 'III')}</span></div>
            </div>
            
            <div class="stats">
                <h3>Room Labels</h3>
                <p>Bedrooms: Bottom-left, Top-left</p>
                <p>Living Hall: Center area</p>
                <p>Kitchen: Bottom-right</p>
                <p>Bathrooms: Right side</p>
                <p>Stairwell: Central core</p>
                <p>Balconies: Left, Right, Top</p>
            </div>
        </div>
    </div>
    <p style="text-align:center; margin-top:20px; color:#666;">
        Generated using IS 456:2000 & IS 13920:2016 compliant automated column placement
    </p>
</body>
</html>
'''

with open('complex_villa_plan.html', 'w') as f:
    f.write(html)
    
print()
print('=== VISUALIZATION SAVED ===')
print('File: complex_villa_plan.html')
