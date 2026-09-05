import sys, os, traceback
sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from src.cad_loader import CADLoader
from src.quantifier import Quantifier
from src.foundation_eng import design_footing
from src.audit import StructuralAuditor

dxf = os.path.join("test_dxfs", "ui_test", "2bhk_simple.dxf")

try:
    loader = CADLoader(dxf)
    gm, beams = loader.load_grid_manager(auto_frame=True)
    print(f"Loaded: {len(gm.columns)} cols, {len(beams)} beams")
    
    gm.num_stories = 2
    gm.story_height_m = 3.0
    
    base_cols = list(gm.columns)
    gm.columns = []
    for level in range(gm.num_stories):
        for bc in base_cols:
            nc = bc.model_copy()
            nc.level = level
            nc.z_top = (level + 1) * gm.story_height_m
            gm.columns.append(nc)
    
    print("Stack OK")
    gm.calculate_loads(floor_load_kn_m2=12.0, wall_load_kn_m=12.0)
    print("Loads OK")
    gm.optimize_column_sizes(fck=25, fy=415)
    print("Optimize OK")
    
    level_0_cols = [c for c in gm.columns if c.level == 0]
    footings = []
    for c in level_0_cols:
        col_w = max(getattr(c, 'width_mm', 0), getattr(c, 'depth_mm', 0), 
                    getattr(c, 'width_nb', 0), getattr(c, 'depth_nb', 0), 230)
        f = design_footing(c.load_kn, sbc=200, fck=25, column_width_mm=col_w)
        footings.append(f)
    print(f"Footings OK: {len(footings)}")
    
    gm.detail_beams(fck=25, fy=415)
    print("detail_beams OK")
    gm.detail_columns(fck=25, fy=415)
    print("detail_columns OK")
    gm.detail_slabs(fck=25, fy=415)
    print("detail_slabs OK")
    
    q = Quantifier(gm, beams, footings)
    bom = q.compute()
    print(f"BOM OK: {bom.total_concrete_vol_m3:.1f} m3")
    
    auditor = StructuralAuditor(gm, beams, footings, fck=25, seismic_zone="III")
    results = auditor.run_audit()
    print(f"Audit OK: {len(results)} checks")
    
except Exception as e:
    print("\n=== FULL TRACEBACK ===")
    traceback.print_exc()
