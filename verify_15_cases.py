import glob
import os
import math
from src.cad_loader import CADLoader
from src.column_placer import JunctionType

def dist(p1, p2):
    return math.hypot(p1[0]-p2[0], p1[1]-p2[1])

def verify_case(filepath):
    print(f"\nAnalyzing {os.path.basename(filepath)}...")
    loader = CADLoader(filepath)
    gm, _ = loader.load_grid_manager(auto_frame=True)
    cols = gm.columns
    framer = loader.framer
    
    # 1. Check Corners
    # Find bounding box of walls
    all_x = []
    all_y = []
    for (x1, y1), (x2, y2) in framer.centerlines:
        all_x.extend([x1, x2])
        all_y.extend([y1, y2])
    
    if not all_x: 
        print("  [SKIP] No walls found")
        return

    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)
    
    # Check if corners have columns (tolerance 500mm)
    corners = [(min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y)]
    missing_corners = []
    for cx, cy in corners:
        found = False
        for c in cols:
            if dist((c.x*1000, c.y*1000), (cx, cy)) < 800:
                found = True
                break
        if not found:
            # Check if there's actually a wall corner there (might be L-shape)
            # Simple check: is there a wall ending near this corner?
            wall_at_corner = False
            for (wx1, wy1), (wx2, wy2) in framer.centerlines:
                if dist((wx1, wy1), (cx, cy)) < 500 or dist((wx2, wy2), (cx, cy)) < 500:
                    wall_at_corner = True
                    break
            if wall_at_corner:
                missing_corners.append((cx, cy))
    
    if missing_corners:
        print(f"  [FAIL] Missing corner columns at: {missing_corners}")
    else:
        print("  [PASS] All structural corners have columns")

    # 2. Check Spans
    max_measured_span = 0
    min_measured_span = float('inf')
    
    for i, c1 in enumerate(cols):
        # Find nearest neighbor
        nearest = float('inf')
        for j, c2 in enumerate(cols):
            if i == j: continue
            d = dist((c1.x, c1.y), (c2.x, c2.y)) * 1000 # to mm
            if d < nearest: nearest = d
            
            # Check grid alignment for span
            if abs(c1.x - c2.x) < 0.2 or abs(c1.y - c2.y) < 0.2: # Aligned
                if d < 500: continue # Same col
                # Is there a wall between them? (simplified)
                # We assume if aligned on grid, valid span
                pass
                
        if nearest < min_measured_span: min_measured_span = nearest
        if nearest > max_measured_span: max_measured_span = nearest
        
        # Check specific bad spans
        if nearest > 8000: # 8m absolute max
             print(f"  [WARN] Column {c1.id} has nearest neighbor at {nearest:.0f}mm (Possible massive span)")

    # 3. Check for Clustered Columns
    clustered = []
    for i, c1 in enumerate(cols):
        for j, c2 in enumerate(cols):
            if i >= j: continue
            d = dist((c1.x, c1.y), (c2.x, c2.y)) * 1000
            if d < 800: # Less than 800mm
                clustered.append(f"{c1.id}-{c2.id} ({d:.0f}mm)")
    
    if clustered:
        print(f"  [FAIL] Clustered columns found: {clustered}")
    else:
        print("  [PASS] No clustered columns (<800mm)")

    print(f"  Total Columns: {len(cols)}")
    print(f"  Min Span: {min_measured_span:.0f}mm")
    
    # Case Specific Checks
    case_name = os.path.basename(filepath)
    if "open_hall" in case_name:
        # Should have NO interior columns
        interior_cols = [c for c in cols if "interior" in c.junction_type.lower()]
        if interior_cols:
            print(f"  [FAIL] Open Hall has {len(interior_cols)} interior columns! Expect 0.")
        else:
            print("  [PASS] Open Hall has 0 interior columns.")
            
    if "small_rect" in case_name:
        # 6x8m. Perimeter is 28m. 
        # Corners=4. 
        # Spans: 6m side -> 0 intermediate (span 6m < 7m).
        # 8m side -> 1 intermediate (span 8m > 7m). 
        # Total expected: 4 + 2 = 6 columns. 
        # Wait, adaptive span for small bldg might be smaller?
        # min(7000, 6000*0.6) = 3600?? No, L_short = 6000. 
        # Adaptive max_span = min(7000, max(3000, 6000*0.6)) = 3600mm.
        # If max_span is 3.6m:
        # 6m side needs 1 intermediate (3m, 3m).
        # 8m side needs 2 intermediates (2.6, 2.6, 2.6).
        # Total: 4 (corners) + 2 (short sides) + 4 (long sides) = 10 cols?
        # Let's see what it produced.
        pass

def run_all():
    files = sorted(glob.glob("real_world_dxfs/*.dxf"))
    with open("verification_report_real.log", "w", encoding="utf-8") as log:
        for f in files:
            try:
                # Redirect print to log
                import sys
                original_stdout = sys.stdout
                sys.stdout = log
                verify_case(f)
                sys.stdout = original_stdout
            except Exception as e:
                log.write(f"  [ERROR] Failed to verify {f}: {e}\n")
    print("Verification complete. Check verification_report.log")

if __name__ == "__main__":
    run_all()
