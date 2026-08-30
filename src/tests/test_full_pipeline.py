"""
STRUCTOPTIMA — COMPREHENSIVE END-TO-END PIPELINE TEST
=======================================================
Tests every stage: DXF load → FEA → column sizing → beam sizing →
footing design → BOM → seismic → wind → stability → audit → BBS → PDF report.

IS Code Coverage:
  IS 456:2000   — Column/beam sizing checks
  IS 875 Pt 1-2 — Load assumptions
  IS 13920:2016 — 300mm seismic minimum
  IS 1893:2016  — Seismic base shear
  IS 875 Pt 3   — Wind pressure
  SP 34:1987    — Beam L/d = 12
"""

import sys, os, math, glob, traceback, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.cad_loader import CADLoader
from src.grid_manager import GridManager, Column
from src.materials import Concrete
from src.foundation_eng import design_footing
from src.quantifier import Quantifier
from src.framing_logic import StructuralMember, Point, MemberProperties
from src.analysis_integration import update_structural_analysis
from src.seismic import run_seismic_check
from src.wind_load import calculate_wind_load, WindZone, TerrainCategory
from src.stability import run_stability_check
from src.audit import StructuralAuditor
from src.bbs_report import generate_bbs_from_grid_manager
from src.report_gen import ReportGenerator
import tempfile

CONC = "M25"
FY = 415.0
N_STORIES = 3
SH = 3.5
FL = 6.5
WL = 12.0
SBC = 200.0
SZ = "III"


def run_full_pipeline(dxf_path, auto_frame=True):
    name = os.path.basename(dxf_path)
    failures = []
    warns = []
    t0 = time.time()
    print(f"\n{'='*60}\nFILE: {name}  [auto={auto_frame}]\n{'='*60}")

    # S1: Load DXF
    try:
        loader = CADLoader(dxf_path)
        gm, beams = loader.load_grid_manager(auto_frame=auto_frame)
        print(f"  OK  S1:Load — {len(gm.columns)} cols, {len(beams)} beams")
    except Exception as e:
        failures.append(f"S1:Load — {type(e).__name__}: {e}")
        print(f"  FAIL S1:Load — {e}")
        return {"name": name, "passed": False, "failures": failures, "time": 0}

    # S2: Scale check
    if gm.x_grid_lines and gm.y_grid_lines:
        w = max(gm.x_grid_lines) - min(gm.x_grid_lines)
        h = max(gm.y_grid_lines) - min(gm.y_grid_lines)
        if w < 0.5 or h < 0.5:
            failures.append(f"S2:Scale — {w:.2f}x{h:.2f}m (scale error?)")
        elif w > 500 or h > 500:
            failures.append(f"S2:Scale — {w:.1f}x{h:.1f}m (unit error?)")
        else:
            print(f"  OK  S2:Scale — {w:.1f}x{h:.1f}m")

    # S3: Stack columns
    try:
        base_cols = list(gm.columns)
        gm.num_stories = N_STORIES
        gm.story_height_m = SH
        gm.columns = []
        for lv in range(N_STORIES):
            for bc in base_cols:
                nc = bc.model_copy()
                nc.id = f"{bc.id}_L{lv}"
                nc.level = lv
                nc.z_bottom = lv * SH
                nc.z_top = (lv + 1) * SH
                gm.columns.append(nc)
        print(f"  OK  S3:Stack — {len(gm.columns)} column segments")
    except Exception as e:
        failures.append(f"S3:Stack — {type(e).__name__}: {e}")
        traceback.print_exc()

    # S4: Loads
    try:
        gm.calculate_trib_areas()
        gm.calculate_loads(floor_load_kn_m2=FL, wall_load_kn_m=WL)
        gc = [c for c in gm.columns if c.level == 0]
        loads = [c.load_kn for c in gc]
        if not loads or max(loads) <= 0:
            failures.append(f"S4:Loads — zero or negative loads")
        elif max(loads) > 15000:
            warns.append(f"S4:Loads — very high load {max(loads):.0f}kN")
        else:
            print(f"  OK  S4:Loads — {min(loads):.0f}–{max(loads):.0f} kN")
    except Exception as e:
        failures.append(f"S4:Loads — {type(e).__name__}: {e}")
        traceback.print_exc()

    # S5: FEA
    try:
        all_beams = []
        for i in range(N_STORIES):
            for b in beams:
                cb = b.model_copy(deep=True)
                cb.id = f"{b.id}_L{i}"
                cb.level = i
                all_beams.append(cb)
        update_structural_analysis(gm, all_beams, use_cracked_sections=True)
        solved = sum(1 for b in all_beams if getattr(b, "analysis_status", "") == "FEA_SOLVED")
        print(f"  OK  S5:FEA — {solved}/{len(all_beams)} beams FEA-solved")
    except Exception as e:
        failures.append(f"S5:FEA — {type(e).__name__}: {e}")
        traceback.print_exc()

    # S6: Column sizing
    try:
        conc = Concrete.from_grade(CONC)
        gm.optimize_column_sizes(concrete=conc, fy=FY, seismic_zone=SZ)
        gc2 = [c for c in gm.columns if c.level == 0]
        too_small = [c for c in gc2 if min(c.width_nb, c.depth_nb) < 300]
        if too_small:
            failures.append(
                f"S6:ColSize — {len(too_small)} cols <300mm seismic (IS 13920 Cl 6.1.3): "
                f"e.g. {too_small[0].id}={too_small[0].width_nb:.0f}x{too_small[0].depth_nb:.0f}"
            )
        else:
            sizes = sorted(set((int(c.width_nb), int(c.depth_nb)) for c in gc2))
            print(f"  OK  S6:ColSize — {sizes}")
    except Exception as e:
        failures.append(f"S6:ColSize — {type(e).__name__}: {e}")
        traceback.print_exc()

    # S7: Detail columns
    try:
        gm.detail_columns(concrete=conc, fy=FY)
        n_sched = len(gm.rebar_schedule) if hasattr(gm, "rebar_schedule") else 0
        print(f"  OK  S7:ColDetail — {n_sched} entries in rebar_schedule")
    except Exception as e:
        failures.append(f"S7:ColDetail — {type(e).__name__}: {e}")
        traceback.print_exc()

    # S8: Beam depth check
    if not beams:
        warns.append("S8: no beams, auto-generating")
        beams = gm.generate_beams()
        all_beams = []
        for i in range(N_STORIES):
            for b in beams:
                cb = b.model_copy(deep=True)
                cb.id = f"{b.id}_L{i}"
                cb.level = i
                all_beams.append(cb)

    bad_ld = []
    for b in beams:
        s_mm = math.hypot(b.end_point.x - b.start_point.x,
                          b.end_point.y - b.start_point.y) * 1000
        d = b.properties.depth_mm
        if s_mm > 100 and d > 0 and "BC_" not in b.id:
            ld = s_mm / d
            if ld > 12.5:
                bad_ld.append(f"{b.id}:L/d={ld:.1f}")
    if bad_ld:
        failures.append(f"S8:BeamDepth — {len(bad_ld)} too shallow: {bad_ld[:2]}")
    else:
        depths = sorted(set(int(b.properties.depth_mm) for b in beams if "BC_" not in b.id))
        print(f"  OK  S8:Beams — depths={depths}mm, L/d<=12")

    # S9: Detail beams
    try:
        gm.detail_beams(beams)
        neg = []
        for bid, res in gm.beam_schedule.items():
            for attr in ["top_steel_mm2", "bottom_steel_mm2"]:
                v = getattr(res, attr, 0)
                if v < 0:
                    neg.append(f"{bid}.{attr}={v:.0f}")
        if neg:
            failures.append(f"S9:BeamDetail — negative steel: {neg[:3]}")
        else:
            print(f"  OK  S9:BeamDetail — {len(gm.beam_schedule)} beams, no negative steel")
    except Exception as e:
        failures.append(f"S9:BeamDetail — {type(e).__name__}: {e}")
        traceback.print_exc()

    # S10: Footings
    try:
        gc_l0 = [c for c in gm.columns if c.level == 0]
        footings = []
        for col in gc_l0:
            ft = design_footing(col.load_kn, SBC, col.width_nb, col.depth_nb, conc)
            footings.append(ft)
        print(f"  OK  S10:Footings — {len(footings)} designed")
    except Exception as e:
        failures.append(f"S10:Footings — {type(e).__name__}: {e}")
        traceback.print_exc()
        footings = []

    # S11: BOM
    try:
        quant = Quantifier()
        bom = quant.calculate_bom(gm.columns, all_beams, footings, grid_mgr=gm)
        if bom.total_concrete_vol_m3 <= 0:
            failures.append("S11:BOM — zero concrete")
        elif bom.total_steel_weight_kg <= 0:
            failures.append("S11:BOM — zero steel")
        else:
            print(f"  OK  S11:BOM — concrete={bom.total_concrete_vol_m3:.1f}m3 "
                  f"steel={bom.total_steel_weight_kg:.0f}kg")
    except Exception as e:
        failures.append(f"S11:BOM — {type(e).__name__}: {e}")
        traceback.print_exc()
        bom = None

    # S12: Seismic
    try:
        fck = int(CONC[1:])
        bw = (bom.total_concrete_vol_m3 * 25 + bom.total_steel_weight_kg * 0.00981
              + gm.width_m * gm.length_m * N_STORIES * FL) if bom else 5000
        seismic_result = run_seismic_check(
            gm.columns, all_beams, bw,
            zone=SZ, building_type="residential", fck=fck
        )
        # SeismicAnalysisResult is a dataclass — use attribute access
        vb = getattr(seismic_result, "base_shear_kn", 0) or 0
        print(f"  OK  S12:Seismic — Vb={vb:.0f}kN")
    except Exception as e:
        failures.append(f"S12:Seismic — {type(e).__name__}: {e}")
        traceback.print_exc()
        seismic_result = None

    # S13: Wind
    try:
        wind_result = calculate_wind_load(
            zone=WindZone("2"), height_m=N_STORIES * SH,
            width_m=gm.width_m, length_m=gm.length_m,
            terrain_category=TerrainCategory("2"), opening_percentage=10.0
        )
        # WindLoadResult is a dataclass — use attribute access
        pz_list = getattr(wind_result, "pressure_results", [])
        top_pz = pz_list[-1].design_wind_pressure_kn_m2 if pz_list else 0.0
        print(f"  OK  S13:Wind — top_pz={top_pz:.3f}kN/m2 "
              f"Vx={getattr(wind_result,'total_base_shear_x_kn',0):.0f}kN")
    except Exception as e:
        failures.append(f"S13:Wind — {type(e).__name__}: {e}")
        traceback.print_exc()
        wind_result = None

    # S14: Stability
    try:
        stab_checks, stab_summary = run_stability_check(gm.columns, all_beams, N_STORIES, SH)
        print(f"  OK  S14:Stability — {stab_summary}")
    except Exception as e:
        failures.append(f"S14:Stability — {type(e).__name__}: {e}")
        traceback.print_exc()
        stab_checks, stab_summary = [], "error"

    # S15: Audit
    try:
        auditor = StructuralAuditor(gm, all_beams, footings)
        audit_results = auditor.run_audit()
        fails_a = [r for r in audit_results if r.status == "FAIL"]
        print(f"  OK  S15:Audit — {len(audit_results)-len(fails_a)}/{len(audit_results)} pass")
    except Exception as e:
        failures.append(f"S15:Audit — {type(e).__name__}: {e}")
        traceback.print_exc()

    # S16: BBS
    try:
        bbs = generate_bbs_from_grid_manager(gm, beams, "Test")
        print(f"  OK  S16:BBS — generated")
    except Exception as e:
        failures.append(f"S16:BBS — {type(e).__name__}: {e}")
        traceback.print_exc()

    # S17: PDF Report
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
        reporter = ReportGenerator()
        reporter.generate_report(
            tmp_path, gm, bom,
            project_name="AutoTest Pipeline",
            seismic_result=seismic_result,
            wind_result=wind_result,
            stab_checks=stab_checks,
            stab_summary=stab_summary,
            all_beams=all_beams,
            conc_grade=CONC,
            live_load=FL,
            building_weight=bw if bom else 5000,
            seismic_zone=SZ,
        )
        pdf_size = os.path.getsize(tmp_path) if os.path.exists(tmp_path) else 0
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        if pdf_size < 1000:
            failures.append(f"S17:Report — PDF too small ({pdf_size}B)")
        else:
            print(f"  OK  S17:Report — PDF {pdf_size//1024}KB")
    except Exception as e:
        failures.append(f"S17:Report — {type(e).__name__}: {e}")
        traceback.print_exc()

    elapsed = time.time() - t0
    for w in warns:
        print(f"  WARN: {w}")
    status = "PASS" if not failures else f"FAIL ({len(failures)})"
    print(f"  [{status}]  time={elapsed:.1f}s")
    return {"name": name, "passed": not failures, "failures": failures, "time": elapsed}


def run_grid_pipeline(label, width, length, stories=3):
    t0 = time.time()
    print(f"\n{'='*60}\nGRID: {label}\n{'='*60}")
    failures = []
    try:
        gm = GridManager(width_m=width, length_m=length, num_stories=stories, story_height_m=SH)
        gm.generate_grid()
        beams = gm.generate_beams()
        gm.calculate_trib_areas()
        gm.calculate_loads(floor_load_kn_m2=FL, wall_load_kn_m=WL)

        all_beams = []
        for i in range(stories):
            for b in beams:
                cb = b.model_copy(deep=True)
                cb.id = f"{b.id}_L{i}"
                cb.level = i
                all_beams.append(cb)

        update_structural_analysis(gm, all_beams, use_cracked_sections=True)

        conc = Concrete.from_grade(CONC)
        gm.optimize_column_sizes(concrete=conc, fy=FY, seismic_zone=SZ)

        gc = [c for c in gm.columns if c.level == 0]
        bad = [c for c in gc if min(c.width_nb, c.depth_nb) < 300]
        if bad:
            failures.append(f"ColSize: {len(bad)} cols <300mm (IS 13920)")

        xs = sorted(gm.x_grid_lines)
        ys = sorted(gm.y_grid_lines)
        spans = [abs(xs[i+1]-xs[i]) for i in range(len(xs)-1)] + [abs(ys[i+1]-ys[i]) for i in range(len(ys)-1)]
        bad_spans = [s for s in spans if s > 5.01]
        if bad_spans:
            failures.append(f"BaySpan: {bad_spans} exceeds 5m (IS 456 Table 26)")

        gm.detail_columns(concrete=conc, fy=FY)
        gm.detail_beams(beams)

        neg_beam = []
        for bid, res in gm.beam_schedule.items():
            for attr in ["top_steel_mm2", "bottom_steel_mm2"]:
                v = getattr(res, attr, 0)
                if v < 0:
                    neg_beam.append(f"{bid}.{attr}={v:.0f}")
        if neg_beam:
            failures.append(f"NegBeamSteel: {neg_beam[:2]}")

        gc_l0 = [c for c in gm.columns if c.level == 0]
        footings = [design_footing(c.load_kn, SBC, c.width_nb, c.depth_nb, conc) for c in gc_l0]
        quant = Quantifier()
        bom = quant.calculate_bom(gm.columns, all_beams, footings, grid_mgr=gm)

        fck = int(CONC[1:])
        bw = bom.total_concrete_vol_m3*25 + bom.total_steel_weight_kg*0.00981 + width*length*stories*FL
        seismic_result = run_seismic_check(gm.columns, all_beams, bw, zone=SZ, building_type="residential", fck=fck)
        wind_result = calculate_wind_load(WindZone("2"), stories*SH, width, length, TerrainCategory("2"), 10.0)
        stab_checks, stab_summary = run_stability_check(gm.columns, all_beams, stories, SH)

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
        reporter_g = ReportGenerator()
        reporter_g.generate_report(
            tmp_path, gm, bom,
            project_name="Grid Test",
            seismic_result=seismic_result,
            wind_result=wind_result,
            stab_checks=stab_checks,
            stab_summary=stab_summary,
            all_beams=all_beams,
            conc_grade=CONC,
            live_load=FL,
            building_weight=bw,
            seismic_zone=SZ,
        )
        pdf_sz = os.path.getsize(tmp_path) if os.path.exists(tmp_path) else 0
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        if pdf_sz < 1000:
            failures.append(f"PDF empty ({pdf_sz}B)")

        sizes = sorted(set((int(c.width_nb), int(c.depth_nb)) for c in gc))
        status = "OK" if not failures else "FAIL"
        print(f"  [{status}] spans={[round(s,2) for s in spans[:4]]} sizes={sizes}")
        vb = getattr(seismic_result, "base_shear_kn", 0) or 0
        print(f"       concrete={bom.total_concrete_vol_m3:.1f}m3 "
              f"steel={bom.total_steel_weight_kg:.0f}kg "
              f"Vb={vb:.0f}kN "
              f"PDF={pdf_sz//1024}KB")
        if failures:
            for f in failures:
                print(f"       x {f}")
        return {"name": label, "passed": not failures, "failures": failures, "time": time.time()-t0}
    except Exception as e:
        traceback.print_exc()
        return {"name": label, "passed": False, "failures": [str(e)], "time": time.time()-t0}


if __name__ == "__main__":
    print("\n" + "#"*60)
    print("  STRUCTOPTIMA — FULL PIPELINE PRODUCTION TEST")
    print("  IS 456:2000 | IS 13920:2016 | IS 1893:2016 | SP 34:1987")
    print("#"*60)

    all_results = []

    print("\n### SECTION A: Manual Grid Pipeline Tests ###")
    all_results.append(run_grid_pipeline("2BHK 10x12m G+2", 10, 12, 3))
    all_results.append(run_grid_pipeline("Apartment 12x15m G+3", 12, 15, 4))
    all_results.append(run_grid_pipeline("Row House 6x18m G+2", 6, 18, 3))
    all_results.append(run_grid_pipeline("Large 20x25m G+5", 20, 25, 6))
    all_results.append(run_grid_pipeline("Minimal 5x6m G+1", 5, 6, 2))
    all_results.append(run_grid_pipeline("Commercial 15x20m", 15, 20, 1))

    print("\n### SECTION B: Real-World DXF Tests ###")
    priority_dxfs = [
        "test_dxfs/case_01_small_rect.dxf",
        "test_dxfs/case_02_medium_rect.dxf",
        "test_dxfs/case_03_large_grid.dxf",
        "test_dxfs/case_04_l_shape.dxf",
        "test_dxfs/case_05_c_shape.dxf",
        "test_dxfs/case_06_t_shape.dxf",
        "test_dxfs/case_08_long_narrow.dxf",
        "test_dxfs/case_09_small_rooms.dxf",
        "test_dxfs/case_10_open_hall.dxf",
        "test_dxfs/case_13_mixed_spans.dxf",
        "test_dxfs/case_15_complex_villa_sim.dxf",
        "real_world_dxfs/real_1_3bhk_standard.dxf",
        "real_world_dxfs/real_2_4bhk_luxury_villa.dxf",
        "real_world_dxfs/real_3_l_shape_farmhouse.dxf",
        "real_world_dxfs/real_4_duplex_ground.dxf",
        "real_world_dxfs/real_5_irregular.dxf",
        "complex_house.dxf",
        "complex_villa.dxf",
        "realistic_indian_house.dxf",
        "real_house_plan.dxf",
        "samples/sample_arch_only.dxf",
        "samples/sample_design.dxf",
    ]
    for dxf in priority_dxfs:
        if os.path.exists(dxf):
            all_results.append(run_full_pipeline(dxf, auto_frame=True))
        else:
            print(f"  SKIP: {dxf}")

    print("\n### SECTION C: Stress/Edge DXF Tests ###")
    for dxf in sorted(glob.glob("test_dxfs/stress/*.dxf")):
        all_results.append(run_full_pipeline(dxf, auto_frame=True))

    print("\n### SECTION D: New Complex Architecture Tests ###")
    new_complex = sorted(glob.glob("test_dxfs/new_complex/*.dxf"))
    for dxf in new_complex:
        all_results.append(run_full_pipeline(dxf, auto_frame=True))

    # Summary
    passed = sum(1 for r in all_results if r.get("passed"))
    total = len(all_results)
    fails = [r for r in all_results if not r.get("passed")]

    print("\n" + "#"*60)
    print(f"  RESULT: {passed}/{total} PASSED")
    if fails:
        print(f"\n  FAILURES ({len(fails)}):")
        for r in fails:
            print(f"  x {r['name']}")
            for f in r.get("failures", [])[:3]:
                print(f"      - {f}")
    else:
        print("  ALL TESTS PASSED")
    times = [r.get("time", 0) for r in all_results]
    print(f"\n  Timing: avg={sum(times)/max(len(times),1):.1f}s total={sum(times):.0f}s")
    print("#"*60)
    sys.exit(0 if not fails else 1)
