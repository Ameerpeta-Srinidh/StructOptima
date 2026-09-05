"""
Full UI simulation test — uses EXACT same API calls as app.py.
Catches every UI-visible error without running Streamlit.
"""
import sys, os, io, traceback
sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import math
from collections import defaultdict
import pandas as pd

from src.cad_loader import CADLoader
from src.grid_manager import GridManager
from src.materials import Concrete
from src.foundation_eng import design_footing
from src.quantifier import Quantifier
from src.framing_logic import StructuralMember
from src.seismic import run_seismic_check
from src.stability import run_stability_check
from src.audit import StructuralAuditor
from src.bbs_report import BBSReportGenerator

import tempfile

DXF_DIR = os.path.join(os.path.dirname(__file__), "test_dxfs", "ui_test")
PASS, FAIL = "[PASS]", "[FAIL]"
results = []

def check(name, fn):
    try:
        fn()
        results.append((PASS, name))
        print(f"  {PASS} {name}")
    except Exception as e:
        tb = traceback.format_exc()
        last_line = tb.strip().split('\n')[-1]
        results.append((FAIL, name, last_line))
        print(f"  {FAIL} {name}")
        print(f"         -> {last_line}")

def run_pipeline(dxf_path, num_stories=2, story_height=3.0, conc_grade="M25"):
    """Mirror of app.py pipeline — uses exact same API as app.py."""
    loader = CADLoader(dxf_path)
    gm, beams = loader.load_grid_manager(auto_frame=True)

    gm.num_stories = num_stories
    gm.story_height_m = story_height

    # Stack columns across stories (same as app.py lines 415-430)
    base_cols = list(gm.columns)
    gm.columns = []
    for level in range(num_stories):
        for bc in base_cols:
            nc = bc.model_copy()
            nc.level = level
            nc.z_top = (level + 1) * story_height
            gm.columns.append(nc)

    # Calculate loads (same as app.py)
    live_load = 12.0  # kN/m2 total floor load
    wall_load = 12.0
    gm.calculate_trib_areas()
    gm.calculate_loads(floor_load_kn_m2=live_load, wall_load_kn_m=wall_load)

    # FEA
    from src.analysis_integration import update_structural_analysis
    update_structural_analysis(gm, beams, use_cracked_sections=True)

    # Design
    m_grade = Concrete.from_grade(conc_grade)
    gm.optimize_column_sizes(concrete=m_grade, fy=415.0)
    gm.detail_columns(concrete=m_grade, fy=415.0)
    gm.detail_beams(beams)
    gm.detail_slabs()

    # Footings
    level_0_cols = [c for c in gm.columns if c.level == 0]
    footings = []
    for col in level_0_cols:
        col_w = getattr(col, 'width_nb', 300)
        col_d = getattr(col, 'depth_nb', 300)
        ft = design_footing(
            axial_load_kn=col.load_kn,
            sbc_kn_m2=200,
            column_width_mm=col_w,
            column_depth_mm=col_d,
            concrete=m_grade
        )
        footings.append(ft)

    # Multi-story beams
    all_beams = []
    for i in range(num_stories):
        for b in beams:
            copied = b.model_copy(deep=True)
            copied.id = f"{b.id}_L{i}"
            copied.level = i
            all_beams.append(copied)

    # BOM
    quantifier = Quantifier()
    bom = quantifier.calculate_bom(gm.columns, all_beams, footings, grid_mgr=gm, use_fly_ash=False)

    # Audit
    auditor = StructuralAuditor(gm, all_beams, footings)
    audit_results = auditor.run_audit()

    fck = int(conc_grade[1:])
    return gm, beams, all_beams, level_0_cols, footings, bom, audit_results, fck


def simulate_schedules_page(gm, beams, level_0_cols, footings, fck):
    """Reproduce every DataFrame build from Schedules page."""
    level_map = defaultdict(list)
    for col in gm.columns:
        level_map[col.level].append(col)
    ground_cols = level_map.get(min(level_map.keys()), [])

    for level in sorted(level_map.keys()):
        data = []
        for col in level_map[level]:
            load  = getattr(col, 'load_kn', 0)
            width = getattr(col, 'width_mm', getattr(col, 'width_nb', 300))
            depth = getattr(col, 'depth_mm', getattr(col, 'depth_nb', width))
            cap   = getattr(col, 'capacity_kn', 0) or ((0.4*fck*width*depth/1000)+(0.67*415*0.008*width*depth/1000))
            dc    = min(load / cap, 1.0) if cap > 0 else 0.0

            footing_size = "N/A"
            if level == min(level_map.keys()):
                idx = next((i for i, gc in enumerate(ground_cols) if gc.id == col.id), None)
                if idx is not None and idx < len(footings):
                    f = footings[idx]
                    footing_size = f"{f.length_m:.1f}x{f.width_m:.1f}x{f.thickness_mm/1000:.2f}m"

            main_steel = "N/A"
            stirrups = "N/A"
            if hasattr(gm, 'rebar_schedule') and gm.rebar_schedule and col.id in gm.rebar_schedule:
                rebar = gm.rebar_schedule[col.id]
                main_steel = str(getattr(rebar, 'main_bars_desc', getattr(rebar, 'main_steel', 'N/A')))
                stirrups = str(getattr(rebar, 'links_desc', getattr(rebar, 'stirrups', 'N/A')))

            data.append({
                "ID": col.id,
                "Size (mm)": f"{width:.0f}x{depth:.0f}",
                "Load (kN)": f"{load:.1f}",
                "D/C Ratio": float(dc),
                "Main Steel": main_steel,
                "Stirrups": stirrups,
                "Footing Size": footing_size,
                "Status": "Fail" if dc > 0.9 else ("Warning" if dc >= 0.7 else "Pass"),
            })
        df = pd.DataFrame(data)
        assert len(df) >= 0  # just check it builds

    # Beam schedule
    beam_data = []
    if hasattr(gm, 'beam_schedule') and gm.beam_schedule:
        for bid, b_info in gm.beam_schedule.items():
            if isinstance(b_info, dict):
                row = {k: str(v) for k, v in b_info.items()}
            else:
                row = {
                    "Beam ID": str(bid),
                    "Size (mm)": f"{getattr(b_info,'width_mm',230):.0f}x{getattr(b_info,'depth_mm',450):.0f}",
                    "Bot Steel": str(getattr(b_info, 'bottom_bars_desc', 'N/A')),
                    "Top Steel": str(getattr(b_info, 'top_bars_desc', 'N/A')),
                    "Stirrups": str(getattr(b_info, 'stirrups_desc', 'N/A')),
                }
            beam_data.append(row)
    pd.DataFrame(beam_data)

    # Footing schedule
    footing_data = []
    for i, cid in enumerate(level_0_cols):
        if i < len(footings):
            f = footings[i]
            footing_data.append({
                "Column ID": getattr(cid, 'id', str(i)),
                "Footing Size (m)": f"{f.length_m:.1f}x{f.width_m:.1f}",
                "Depth (m)": f"{f.thickness_mm/1000:.2f}",
            })
    pd.DataFrame(footing_data)


def simulate_analysis_page(gm, all_beams, footings, bom, audit_results, fck):
    """Run Analysis page data computations."""
    sr = run_seismic_check(
        gm.columns, all_beams,
        bom.total_concrete_vol_m3 * 25 + bom.total_steel_weight_kg * 0.00981,
        zone="III", building_type="residential", fck=fck
    )
    sc, ss = run_stability_check(gm.columns, all_beams, gm.num_stories, gm.story_height_m)
    # BOM metrics access
    _ = f"{bom.total_concrete_vol_m3:.2f}"
    _ = f"{bom.total_steel_weight_kg:.0f}"
    _ = f"{bom.total_cost_inr:,.0f}"
    _ = f"{bom.total_carbon_kg/1000:.2f}"


def simulate_drawings_page(gm, all_beams, footings):
    """Test visualiser code — mirrors pages/3_Drawings.py."""
    from src.visualizer import Visualizer
    v = Visualizer()
    fig = v.create_2d_plan(gm, all_beams, view_mode="Engineering", level=1)
    assert fig is not None, "2D plan returned None"


def simulate_reports_page(gm, all_beams, bom, audit_results):
    """Check report generators don't crash."""
    from src.report_gen import ReportGenerator
    r = ReportGenerator()
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
        r.generate_report(tmp.name, gm, bom,
                          audit_results=audit_results,
                          math_breakdown=None,
                          project_name="Test Build",
                          use_fly_ash=False)
    sz = os.path.getsize(tmp.name)
    os.unlink(tmp.name)
    assert sz > 0, f"PDF was empty ({sz} bytes)"


def simulate_site_tools_page(gm, bom):
    """Test Site Tools calculators — no bom_results key needed."""
    from src.site_calculators import rebar_weight_table, concrete_pour_calculator, curing_schedule
    rw = rebar_weight_table()
    assert len(rw) > 0
    cp = concrete_pour_calculator(volume_m3=50.0)
    assert cp is not None
    cs = curing_schedule("M25")
    assert cs is not None
    # Pre-fill calculator volumes from bom (what Site Tools page should do)
    vol = bom.total_concrete_vol_m3
    steel = bom.total_steel_weight_kg
    assert vol > 0 and steel > 0


# ── Run tests ────────────────────────────────────────────────────────────────
dxf_files = sorted(f for f in os.listdir(DXF_DIR) if f.endswith('.dxf'))
print(f"\nFound {len(dxf_files)} DXF test files\n{'='*60}")

for dxf_name in dxf_files:
    dxf_path = os.path.join(DXF_DIR, dxf_name)
    label = dxf_name.replace('.dxf', '')
    print(f"\n{'='*60}")
    print(f"FILE: {dxf_name}")
    print(f"{'='*60}")

    gm = beams = all_beams = level_0_cols = footings = bom = audit_results = fck = None
    pipeline_ok = True

    try:
        gm, beams, all_beams, level_0_cols, footings, bom, audit_results, fck = run_pipeline(dxf_path)
        results.append((PASS, f"{label} - Pipeline"))
        print(f"  {PASS} {label} - Pipeline ({len(gm.columns)} cols, {len(all_beams)} beams, {len(footings)} footings)")
    except Exception as e:
        tb = traceback.format_exc()
        last_line = tb.strip().split('\n')[-1]
        results.append((FAIL, f"{label} - Pipeline", last_line))
        print(f"  {FAIL} {label} - Pipeline\n         -> {last_line}")
        # Print context lines to help debugging
        lines = tb.strip().split('\n')
        for l in lines[-8:]:
            print(f"    {l}")
        pipeline_ok = False

    if not pipeline_ok:
        continue

    check(f"{label} - Schedules Page",  lambda: simulate_schedules_page(gm, beams, level_0_cols, footings, fck))
    check(f"{label} - Analysis Page",   lambda: simulate_analysis_page(gm, all_beams, footings, bom, audit_results, fck))
    check(f"{label} - Drawings Page",   lambda: simulate_drawings_page(gm, all_beams, footings))
    check(f"{label} - Reports Page",    lambda: simulate_reports_page(gm, all_beams, bom, audit_results))
    check(f"{label} - Site Tools Page", lambda: simulate_site_tools_page(gm, bom))

# ── Summary ──────────────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"  UI TEST SUMMARY")
print(f"{'='*60}")
passed = [r for r in results if r[0] == PASS]
failed = [r for r in results if r[0] == FAIL]
for r in results:
    status = r[0]
    name = r[1]
    err = r[2] if len(r) > 2 else ""
    if status == FAIL:
        print(f"  {status} {name}")
        print(f"    -> {err}")
    else:
        print(f"  {status} {name}")

print(f"\n  Total: {len(results)} | {PASS} {len(passed)} | {FAIL} {len(failed)}")
if not failed:
    print(f"\n  ALL TESTS PASSED - UI is ready for demo!")
else:
    print(f"\n  {len(failed)} TESTS FAILED - need fixing")
