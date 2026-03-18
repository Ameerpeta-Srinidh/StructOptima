import glob
import os
import json
import math
from src.cad_loader import CADLoader

def generate_svg(centerlines, columns, width=800, height=600, padding=50):
    # Calculate bounds
    min_x, min_y = float('inf'), float('inf')
    max_x, max_y = float('-inf'), float('-inf')
    
    # Check centerlines
    for (x1, y1), (x2, y2) in centerlines:
        min_x = min(min_x, x1, x2)
        max_x = max(max_x, x1, x2)
        min_y = min(min_y, y1, y2)
        max_y = max(max_y, y1, y2)
        
    # Check columns
    for c in columns:
        min_x = min(min_x, c.x * 1000)
        max_x = max(max_x, c.x * 1000)
        min_y = min(min_y, c.y * 1000)
        max_y = max(max_y, c.y * 1000)
        
    if min_x == float('inf'):
        return "<svg></svg>"
        
    # Add padding
    min_x -= padding
    max_x += padding
    min_y -= padding
    max_y += padding
    
    content_width = max_x - min_x
    content_height = max_y - min_y
    
    if content_width == 0: content_width = 1000
    if content_height == 0: content_height = 1000
    
    aspect = content_width / content_height
    
    svg = f'<svg viewBox="{min_x} {min_y} {content_width} {content_height}" width="{width}" height="{height}" style="background:#111; transform: scaleY(-1);">'
    
    # Draw Grid (Optional)
    
    # Draw Walls
    for (x1, y1), (x2, y2) in centerlines:
        svg += f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#555" stroke-width="20" stroke-linecap="round" />'
        
    # Draw Columns
    for c in columns:
        cx = c.x * 1000
        cy = c.y * 1000
        w = c.width_nb
        d = c.depth_nb
        
        # Color by type
        color = "#f72585" # Default pink
        if "corner" in c.junction_type.lower(): color = "#4cc9f0" # Cyan
        elif "t" in c.junction_type.lower(): color = "#7209b7" # Purple
        elif "edge" in c.junction_type.lower(): color = "#4361ee" # Blue
        
        # Rect centered at x,y
        svg += f'<rect x="{cx - w/2}" y="{cy - d/2}" width="{w}" height="{d}" fill="{color}" stroke="white" stroke-width="2" />'
        # Label (flipped back text)
        svg += f'<g transform="scale(1, -1) translate(0, {-2*cy})"><text x="{cx}" y="{-(cy-d/2-20)}" fill="white" font-size="150" text-anchor="middle" transform="scale(1, -1)">{c.id}</text></g>'

    svg += '</svg>'
    return svg

def run_batch():
    files = sorted(glob.glob("real_world_dxfs/*.dxf"))
    if not files:
        print("No DXF files found in real_world_dxfs/")
        return
        
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Batch Column Placement Analysis</title>
        <style>
            body { font-family: sans-serif; background: #222; color: #eee; padding: 20px; }
            .case { background: #333; margin-bottom: 30px; padding: 20px; border-radius: 8px; }
            .case h2 { color: #4cc9f0; margin-top: 0; }
            .meta { color: #aaa; margin-bottom: 10px; font-family: monospace; }
            .warnings { color: #ffca3a; background: #443300; padding: 10px; border-radius: 4px; margin-top: 10px; }
            .stats-table { width: 100%; border-collapse: collapse; margin-bottom: 10px; }
            .stats-table td { padding: 4px 8px; border-bottom: 1px solid #444; }
            .viz { text-align: center; margin-top: 10px; border: 1px solid #444; }
        </style>
    </head>
    <body>
    <h1>Column Placement Batch Validation (IS 456 / IS 13920)</h1>
    """
    
    summary_data = []

    for f in files:
        print(f"Processing {f}...")
        case_name = os.path.basename(f)
        
        try:
            loader = CADLoader(f)
            gm, beams = loader.load_grid_manager(auto_frame=True)
            
            stats = loader.placement_stats
            warnings = loader.placement_warnings
            
            # SVG Visualization
            # Fix: AutoFramer might store walls in mm, GridManager columns in m
            # We convert columns to mm for SVG in generate_svg
            
            svg = generate_svg(loader.framer.centerlines, gm.columns)
            
            warnings_html = ""
            if warnings:
                warnings_html = "<div class='warnings'><strong>Warnings:</strong><ul>"
                for w in warnings:
                    warnings_html += f"<li>[{w['severity']}] {w['message']}</li>"
                warnings_html += "</ul></div>"
            
            html += f"""
            <div class="case">
                <h2>{case_name}</h2>
                <div class="meta">
                    Columns: {len(gm.columns)} | 
                    Dimensions: {gm.width_m:.1f}m x {gm.length_m:.1f}m
                </div>
                {warnings_html}
                <div class="viz">{svg}</div>
            </div>
            """
            
            summary_data.append({
                'name': case_name,
                'cols': len(gm.columns),
                'warnings': len(warnings)
            })
            
        except Exception as e:
            print(f"Error processing {f}: {e}")
            html += f"""
            <div class="case" style="border-left: 5px solid red;">
                <h2>{case_name} (FAILED)</h2>
                <div class="meta">{str(e)}</div>
            </div>
            """
            
    html += "</body></html>"
    
    with open("batch_report.html", "w") as f:
        f.write(html)
    
    print(f"Batch analysis complete. Report saved to batch_report.html")
    
    # Print Summary to Console
    print("\n=== SUMMARY ===")
    print(f"{'Case':<30} | {'Cols':<5} | {'Warn':<5}")
    print("-" * 46)
    for s in summary_data:
        print(f"{s['name']:<30} | {s['cols']:<5} | {s['warnings']:<5}")

if __name__ == "__main__":
    run_batch()
