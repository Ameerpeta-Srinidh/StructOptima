"""
StructOptima Core Pipeline Stress Test
======================================
Tests adversarial DXF inputs against the full structural design pipeline.
"""

import sys
import os
import io
import math
import traceback

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(__file__))

import ezdxf
from src.cad_parser import CADParser
from src.cad_loader import CADLoader
from src.grid_manager import GridManager
from src.materials import Concrete
from src.foundation_eng import design_footing
from src.framing_logic import StructuralMember, Point, MemberProperties


PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"

results = []

def log_result(test_name, status, detail=""):
    results.append((test_name, status, detail))
    msg = f"  {status} {test_name}" + (f" -- {detail}" if detail else "")
    print(msg)

def create_dxf_rect(filepath, x_min, y_min, x_max, y_max, layer="WALLS"):
    """Creates a simple rectangular room DXF."""
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    doc.layers.new(layer)
    # Four walls as LINE entities
    msp.add_line((x_min, y_min), (x_max, y_min), dxfattribs={'layer': layer})
    msp.add_line((x_max, y_min), (x_max, y_max), dxfattribs={'layer': layer})
    msp.add_line((x_max, y_max), (x_min, y_max), dxfattribs={'layer': layer})
    msp.add_line((x_min, y_max), (x_min, y_min), dxfattribs={'layer': layer})
    doc.saveas(filepath)

def create_dxf_lshape(filepath, layer="WALLS"):
    """L-shaped plan in mm: main block 10000x8000, cutout 5000x4000 from top-right."""
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    doc.layers.new(layer)
    pts = [
        (0, 0), (10000, 0), (10000, 4000), (5000, 4000),
        (5000, 8000), (0, 8000), (0, 0)
    ]
    for i in range(len(pts)-1):
        msp.add_line(pts[i], pts[i+1], dxfattribs={'layer': layer})
    doc.saveas(filepath)

def create_dxf_double_walls(filepath, thickness_mm=230):
    """Room with double-line walls (inner + outer offset)."""
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    doc.layers.new("WALLS")
    t = thickness_mm
    # Outer rectangle 6000x5000
    outer = [(0, 0), (6000, 0), (6000, 5000), (0, 5000)]
    # Inner rectangle offset inward by wall thickness
    inner = [(t, t), (6000-t, t), (6000-t, 5000-t), (t, 5000-t)]
    
    for pts in [outer, inner]:
        for i in range(len(pts)):
            p1 = pts[i]
            p2 = pts[(i+1) % len(pts)]
            msp.add_line(p1, p2, dxfattribs={'layer': 'WALLS'})
    doc.saveas(filepath)

def create_dxf_diagonal(filepath):
    """Room with a diagonal wall at 45 degrees."""
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    doc.layers.new("WALLS")
    # Rectangular boundary 8000x6000
    msp.add_line((0, 0), (8000, 0), dxfattribs={'layer': 'WALLS'})
    msp.add_line((8000, 0), (8000, 6000), dxfattribs={'layer': 'WALLS'})
    msp.add_line((8000, 6000), (0, 6000), dxfattribs={'layer': 'WALLS'})
    msp.add_line((0, 6000), (0, 0), dxfattribs={'layer': 'WALLS'})
    # Diagonal internal wall
    msp.add_line((0, 0), (4000, 4000), dxfattribs={'layer': 'WALLS'})
    doc.saveas(filepath)

def create_dxf_empty(filepath):
    """DXF with no geometry at all."""
    doc = ezdxf.new('R2010')
    doc.saveas(filepath)

def create_dxf_circles_only(filepath):
    """DXF with only circles, no lines."""
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    msp.add_circle((3000, 3000), 1500)
    msp.add_circle((6000, 3000), 500)
    doc.saveas(filepath)

def create_dxf_narrow(filepath):
    """Extremely narrow corridor: 2m x 20m."""
    create_dxf_rect(filepath, 0, 0, 2000, 20000)

def create_dxf_large_hall(filepath):
    """Large open hall: 25m x 15m — requires intermediate columns."""
    create_dxf_rect(filepath, 0, 0, 25000, 15000)


def run_full_pipeline(dxf_path, test_name, expect_fail=False):
    """Run the full structural pipeline on a DXF and validate results."""
    print(f"\n{'='*60}")
    print(f"TEST: {test_name}")
    print(f"File: {dxf_path}")
    print(f"{'='*60}")
    
    try:
        # 1. Parse
        parser = CADParser(dxf_path)
        parser.load()
        layers = parser.get_layers()
        walls_raw = parser.extract_walls()
        walls_norm = parser.normalize_to_centerlines(walls_raw)
        
        print(f"  Layers: {layers}")
        print(f"  Raw walls: {len(walls_raw)}, Centerlines: {len(walls_norm)}")
        
        if len(walls_norm) == 0:
            if expect_fail:
                log_result(f"{test_name} - Parsing", PASS, "Gracefully returned 0 walls as expected")
                return
            else:
                log_result(f"{test_name} - Parsing", FAIL, "No walls extracted!")
                return
        
        # 2. Load into GridManager via CADLoader
        loader = CADLoader(dxf_path)
        gm, beams = loader.load_grid_manager(auto_frame=True)
        
        n_cols = len(gm.columns)
        n_beams = len(beams)
        print(f"  Columns: {n_cols}, Beams: {n_beams}")
        print(f"  Grid X: {gm.x_grid_lines}")
        print(f"  Grid Y: {gm.y_grid_lines}")
        
        if n_cols == 0:
            log_result(f"{test_name} - Column Placement", FAIL, "No columns placed!")
            return
        
        if n_beams == 0:
            beams = gm.generate_beams()
            n_beams = len(beams)
            if n_beams == 0:
                log_result(f"{test_name} - Beam Generation", FAIL, "No beams generated!")
                return
        
        log_result(f"{test_name} - Column Placement", PASS, f"{n_cols} columns")
        log_result(f"{test_name} - Beam Generation", PASS, f"{n_beams} beams")
        
        # 3. Multi-story stacking
        num_stories = 2
        story_height = 3.0
        gm.num_stories = num_stories
        gm.story_height_m = story_height
        base_cols = [c for c in gm.columns]
        gm.columns = []
        for level in range(num_stories):
            for base_c in base_cols:
                new_c = base_c.model_copy()
                new_c.id = f"{base_c.id}_L{level}"
                new_c.level = level
                new_c.z_bottom = level * story_height
                new_c.z_top = (level + 1) * story_height
                gm.columns.append(new_c)
        
        # 4. Loads
        gm.calculate_trib_areas()
        gm.calculate_loads(floor_load_kn_m2=12.0, wall_load_kn_m=12.0)
        
        # Validate loads
        zero_load_cols = [c for c in gm.columns if c.load_kn <= 0 and c.level == 0]
        if zero_load_cols:
            log_result(f"{test_name} - Load Calculation", WARN, 
                      f"{len(zero_load_cols)} ground columns have zero/negative load!")
        else:
            log_result(f"{test_name} - Load Calculation", PASS, "All ground columns have positive loads")
        
        # Check for unreasonable loads
        max_load = max(c.load_kn for c in gm.columns)
        if max_load > 50000:  # 50,000 kN is unreasonable for low-rise
            log_result(f"{test_name} - Load Sanity", FAIL, f"Max load {max_load:.0f} kN is unreasonably high!")
        else:
            log_result(f"{test_name} - Load Sanity", PASS, f"Max load {max_load:.0f} kN")
        
        # 5. Column sizing
        m_grade = Concrete.from_grade("M25")
        gm.optimize_column_sizes(concrete=m_grade, fy=415.0)
        
        # Validate sizes
        for col in gm.columns:
            if col.width_nb < 200 or col.width_nb > 2000:
                log_result(f"{test_name} - Column Sizing", FAIL, 
                          f"Col {col.id} size {col.width_nb}x{col.depth_nb} out of range")
                break
        else:
            sizes = set((c.width_nb, c.depth_nb) for c in gm.columns if c.level == 0)
            log_result(f"{test_name} - Column Sizing", PASS, f"Sizes: {sizes}")
        
        # 6. Foundation design
        level_0_cols = [c for c in gm.columns if c.level == 0]
        footings = []
        for col in level_0_cols:
            ft = design_footing(
                axial_load_kn=col.load_kn,
                sbc_kn_m2=200.0,
                column_width_mm=col.width_nb,
                column_depth_mm=col.depth_nb,
                concrete=m_grade
            )
            footings.append(ft)
            if ft.length_m > 10.0:
                log_result(f"{test_name} - Foundation", WARN, 
                          f"Col {col.id}: Footing {ft.length_m:.1f}m exceeds practical limit")
                break
        else:
            log_result(f"{test_name} - Foundation", PASS, 
                      f"{len(footings)} footings, max size {max(f.length_m for f in footings):.2f}m")
        
        # 7. Beam design (rebar detailing)
        try:
            gm.detail_beams(beams)
            log_result(f"{test_name} - Beam Design", PASS, f"{len(gm.beam_schedule)} beams detailed")
        except Exception as e:
            log_result(f"{test_name} - Beam Design", FAIL, str(e))
        
        # 8. Column detailing
        try:
            gm.detail_columns(concrete=m_grade, fy=415.0)
            log_result(f"{test_name} - Column Detailing", PASS, f"{len(gm.rebar_schedule)} columns detailed")
        except Exception as e:
            log_result(f"{test_name} - Column Detailing", FAIL, str(e))
        
        # 9. Slab design
        try:
            gm.detail_slabs()
            log_result(f"{test_name} - Slab Design", PASS, f"{len(gm.slab_schedule)} slabs detailed")
        except Exception as e:
            log_result(f"{test_name} - Slab Design", FAIL, str(e))
        
        # 10. Span validation (IS 456 max span check)
        for b in beams:
            span_m = math.hypot(b.end_point.x - b.start_point.x, b.end_point.y - b.start_point.y)
            if span_m > 8.0:
                log_result(f"{test_name} - Span Check", WARN, 
                          f"Beam {b.id} span {span_m:.2f}m exceeds 8m recommended limit")
                break
        else:
            log_result(f"{test_name} - Span Check", PASS, "All spans within limits")
            
    except Exception as e:
        if expect_fail:
            log_result(f"{test_name} - Expected Failure", PASS, f"Correctly raised: {type(e).__name__}: {e}")
        else:
            log_result(f"{test_name} - CRASH", FAIL, f"{type(e).__name__}: {e}")
            traceback.print_exc()


def main():
    test_dir = os.path.join(os.path.dirname(__file__), "test_dxfs", "stress")
    os.makedirs(test_dir, exist_ok=True)
    
    print("\n" + "="*70)
    print("  STRUCTOPTIMA CORE PIPELINE STRESS TEST")
    print("  Testing adversarial DXF inputs against full design pipeline")
    print("="*70)
    
    # ======== Generate test DXFs ========
    
    # Test 1: Tiny room (3m x 3m)
    f1 = os.path.join(test_dir, "tiny_room.dxf")
    create_dxf_rect(f1, 0, 0, 3000, 3000)
    run_full_pipeline(f1, "Tiny Room (3x3m)")
    
    # Test 2: Large hall (25m x 15m)
    f2 = os.path.join(test_dir, "large_hall.dxf")
    create_dxf_large_hall(f2)
    run_full_pipeline(f2, "Large Hall (25x15m)")
    
    # Test 3: L-shaped plan
    f3 = os.path.join(test_dir, "l_shape.dxf")
    create_dxf_lshape(f3)
    run_full_pipeline(f3, "L-Shaped Plan")
    
    # Test 4: Narrow corridor (2m x 20m)
    f4 = os.path.join(test_dir, "narrow_corridor.dxf")
    create_dxf_narrow(f4)
    run_full_pipeline(f4, "Narrow Corridor (2x20m)")
    
    # Test 5: Double-wall lines (230mm offset)
    f5 = os.path.join(test_dir, "double_walls.dxf")
    create_dxf_double_walls(f5)
    run_full_pipeline(f5, "Double-Line Walls (230mm)")
    
    # Test 6: Diagonal walls
    f6 = os.path.join(test_dir, "diagonal_walls.dxf")
    create_dxf_diagonal(f6)
    run_full_pipeline(f6, "Diagonal Walls (45°)")
    
    # Test 7: Thick masonry walls (400mm)
    f7 = os.path.join(test_dir, "thick_walls.dxf")
    create_dxf_double_walls(f7, thickness_mm=400)
    run_full_pipeline(f7, "Thick Walls (400mm)")
    
    # Test 8: Empty DXF
    f8 = os.path.join(test_dir, "empty.dxf")
    create_dxf_empty(f8)
    run_full_pipeline(f8, "Empty DXF (No Geometry)", expect_fail=True)
    
    # Test 9: Circles only
    f9 = os.path.join(test_dir, "circles_only.dxf")
    create_dxf_circles_only(f9)
    run_full_pipeline(f9, "Circles Only (No Lines)", expect_fail=True)
    
    # Test 10: Existing complex villa
    f10 = os.path.join(os.path.dirname(__file__), "complex_villa.dxf")
    if os.path.exists(f10):
        run_full_pipeline(f10, "Complex Villa (Real-World)")
    else:
        log_result("Complex Villa (Real-World)", WARN, "File not found")
    
    # ======== Summary ========
    print("\n" + "="*70)
    print("  STRESS TEST SUMMARY")
    print("="*70)
    
    passes = sum(1 for _, s, _ in results if s == PASS)
    fails = sum(1 for _, s, _ in results if s == FAIL)
    warns = sum(1 for _, s, _ in results if s == WARN)
    
    for name, status, detail in results:
        print(f"  {status} {name}" + (f" — {detail}" if detail else ""))
    
    print(f"\n  Total: {len(results)} checks | {PASS} {passes} | {FAIL} {fails} | {WARN} {warns}")
    
    if fails > 0:
        print(f"\n  ❌ PRODUCTION READINESS: NOT READY — {fails} critical failures found")
        return 1
    elif warns > 0:
        print(f"\n  ⚠️  PRODUCTION READINESS: CONDITIONAL — {warns} warnings to address")
        return 0
    else:
        print(f"\n  ✅ PRODUCTION READINESS: READY")
        return 0


if __name__ == "__main__":
    sys.exit(main())
