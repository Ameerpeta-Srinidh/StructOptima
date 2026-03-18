import glob
import math
from src.cad_loader import CADLoader

def analyze_quality(filepath):
    loader = CADLoader(filepath)
    gm, _ = loader.load_grid_manager(auto_frame=True)
    cols = gm.columns
    
    # 1. Grid Alignment Score
    # Real engineers align columns. 
    # Count how many columns share x or y coordinates (perfectly or nearperfectly)
    x_coords = [round(c.x, 2) for c in cols]
    y_coords = [round(c.y, 2) for c in cols]
    
    unique_x = set(x_coords)
    unique_y = set(y_coords)
    
    # Perfect alignment means fewer unique coords than columns
    # Score = 1 - (unique_lines / total_cols) ... roughly
    # Better: for each column, does it share x or y with at least one other?
    aligned_count = 0
    for c in cols:
        cx, cy = round(c.x, 2), round(c.y, 2)
        shares_x = x_coords.count(cx) > 1
        shares_y = y_coords.count(cy) > 1
        if shares_x or shares_y:
            aligned_count += 1
            
    alignment_score = (aligned_count / len(cols)) * 100 if cols else 0
    
    # 2. Span Efficiency
    # Optimal span is 3m to 6m. 
    # Measure distance to nearest neighbor for each column
    spans = []
    for i, c1 in enumerate(cols):
        nearest = float('inf')
        for j, c2 in enumerate(cols):
            if i==j: continue
            d = math.hypot(c1.x-c2.x, c1.y-c2.y)
            if d < nearest: nearest = d
        spans.append(nearest)
        
    avg_span = sum(spans) / len(spans) if spans else 0
    efficient_spans = len([s for s in spans if 2.5 <= s <= 7.0])
    span_score = (efficient_spans / len(spans)) * 100 if spans else 0
    
    # 4. Beam Quality Checks
    print("\n  BEAM CHECKS:")
    from src.beam_placer import BeamPlacer
    # Load beam data if available
    try:
        # BeamPlacer needs: columns (dict), walls, slab_boundary
        # Walls are in loader.framer.centerlines
        walls = loader.framer.centerlines
        
        # Convert Pydantic columns to dicts (GridManager uses Meters, BeamPlacer needs MM)
        # We need to detect if scaling happened. 
        # But generally BeamPlacer works best in MM.
        # Check walls unit. walls from framer are RAW.
        # If raw is MM (large numbers), we must scale cols back to MM.
        
        # Heuristic: check wall coordinate magnitude
        max_wall_coord = 0
        if walls:
             max_wall_coord = max(max(w[0][0], w[1][0]) for w in walls)
        
        scale_to_mm = 1.0
        if max_wall_coord > 1000:
             # Walls are huge (MM), but cols are small (M)
             # We assume cols need * 1000
             scale_to_mm = 1000.0
             
        cols_dict = []
        for c in gm.columns:
            cols_dict.append({
                'id': c.id,
                'x': c.x * scale_to_mm,
                'y': c.y * scale_to_mm,
                'width': c.width_nb,
                'depth': c.depth_nb,
                'junction_type': c.junction_type,
                'is_floating': c.is_floating
            })
            
        # Slab boundary: use framer's building envelope if available, else None
        slab_boundary = None 
        # (For now we rely on BeamPlacer to compute hull if no boundary provided, 
        # but for Cantilevers we need a real boundary. In valid DXFs, we might not have a specific slab layer 
        # distinct from walls. Let's assume walls define the boundary for now or use the hull.)
        
        # Actually, let's create a synthetic slab boundary from the walls for testing cantilevers?
        # Or just pass None and it won't check cantilevers fully (except duplicates).
        # But wait, we want to test cantilevers.
        # Construct a simple hull from walls for slab boundary?
        # For our "real_world" generated DXFs, we don't strictly have a "slab" polyline, just walls.
        # But we added "balconies" in the 3BHK generation as walls. 
        # Real BeamPlacer logic uses `self.columns` and `self.slab_boundary`.
        # If `slab_boundary` is None, `_detect_cantilevers` returns early.
        # We need to simulate a slab boundary that includes the balconies.
        # The walls themselves include the balcony walls.
        # Let's collect all wall endpoints as the "boundary" points for this test.
        boundary_points = []
        for p1, p2 in walls:
            boundary_points.append(p1)
            boundary_points.append(p2)
        
        placer = BeamPlacer(cols_dict, walls, boundary_points)
        res = placer.generate_placement()
        beams = res.beams
        
        cantilevers = [b for b in beams if b.is_cantilever]
        
        # Check specific warning strings
        unsafe_cant = []
        hierarchy_fail = []
        deep_beams = []
        long_spans = []
        
        for b in beams:
             for w in b.warnings:
                 if "Back-span" in w: unsafe_cant.append(b)
                 if "Depth reduced" in w: hierarchy_fail.append(b)
                 if "DEEP BEAM" in w: deep_beams.append(b)
                 if "7.0m limit" in w: long_spans.append(b)

        print(f"  Total Beams: {len(beams)}")
        print(f"  Cantilevers: {len(cantilevers)} (Unsafe: {len(unsafe_cant)})")
        print(f"  Hierarchy Adjustments: {len(hierarchy_fail)}")
        print(f"  Deep Beams (L/D < 4): {len(deep_beams)}")
        print(f"  Critical Spans (>7m): {len(long_spans)}")
        
        if len(beams) > 0:
            print("\n  SAMPLE WARNINGS:")
            count = 0
            for b in beams:
                if b.warnings:
                    print(f"    {b.id}: {b.warnings}")
                    count += 1
                    if count > 5: break
        
        if unsafe_cant:
            print(f"  [FAIL] Unsafe cantilevers found!")
        if long_spans:
            print(f"  [WARN] Long spans > 7m found.")
            
    except Exception as e:
        print(f"  [ERROR] Beam placement failed: {e}")

    print("-" * 30)
    
    return alignment_score, span_score

def run_analysis():
    files = sorted(glob.glob("real_world_dxfs/real_2*.dxf"))
    total_align = 0
    total_span = 0
    
    print("\nENGINEERING METRICS AUDIT\n" + "="*30)
    
    for f in files:
        a, s = analyze_quality(f)
        total_align += a
        total_span += s
        
    avg_align = total_align / len(files)
    avg_span = total_span / len(files)
    
    print(f"\nOVERALL SCORE:")
    print(f"  Avg Alignment: {avg_align:.1f}%")
    print(f"  Avg Span Efficiency: {avg_span:.1f}%")

if __name__ == "__main__":
    run_analysis()
