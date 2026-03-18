"""
Comprehensive Error Audit Script - File output version
Tests every major import, class instantiation, and method call used by app.py.
"""
import sys, os, math, traceback
sys.path.insert(0, os.getcwd())

LOG_FILE = os.path.join(os.getcwd(), "audit_report.txt")

errors = []

class Logger:
    def __init__(self, path):
        self.f = open(path, 'w', encoding='utf-8')
    def log(self, msg):
        self.f.write(msg + '\n')
        self.f.flush()
    def close(self):
        self.f.close()

log = Logger(LOG_FILE)

def test(name, func):
    try:
        result = func()
        log.log(f"  [OK] {name}")
        return result
    except Exception as e:
        tb = traceback.format_exc()
        errors.append((name, str(e), tb))
        log.log(f"  [FAIL] {name}: {e}")
        return None

log.log("=" * 60)
log.log("COMPREHENSIVE APP AUDIT")
log.log("=" * 60)

modules = {}

def import_test(mod_path, names):
    try:
        mod = __import__(mod_path, fromlist=names)
        result = {}
        for name in names:
            try:
                result[name] = getattr(mod, name)
                log.log(f"  [OK] {mod_path}.{name}")
            except AttributeError:
                errors.append((f"Import {mod_path}.{name}", f"module '{mod_path}' has no attribute '{name}'", ""))
                log.log(f"  [FAIL] {mod_path}.{name} - NOT FOUND")
        return result
    except ImportError as e:
        errors.append((f"Import {mod_path}", str(e), traceback.format_exc()))
        log.log(f"  [FAIL] Module {mod_path}: {e}")
        return {}

# ===== PHASE 1: IMPORTS =====
log.log("\n[1/8] Testing Imports...")
modules.update(import_test("src.grid_manager", ["GridManager"]))
modules.update(import_test("src.materials", ["Concrete"]))
modules.update(import_test("src.foundation_eng", ["design_footing"]))
modules.update(import_test("src.quantifier", ["Quantifier"]))
modules.update(import_test("src.visualizer", ["Visualizer"]))
modules.update(import_test("src.report_gen", ["ReportGenerator"]))
modules.update(import_test("src.bbs_report", ["BBSReportGenerator", "generate_bbs_from_grid_manager"]))
modules.update(import_test("src.framing_logic", ["StructuralMember", "Point", "MemberProperties"]))
modules.update(import_test("src.exporters", ["ExcelExporter"]))
modules.update(import_test("src.building_types", ["BUILDING_TYPES", "get_load_parameters", "get_design_load_summary"]))
modules.update(import_test("src.optimizer", ["optimize_structure", "OptimizationLevel"]))
modules.update(import_test("src.stability", ["run_stability_check", "FireRating", "FIRE_RESISTANCE_TABLE"]))
modules.update(import_test("src.anchorage", ["AnchorageCalculator", "get_development_length_table"]))
modules.update(import_test("src.seismic", ["run_seismic_check", "SEISMIC_ZONES", "ZONE_DESCRIPTIONS"]))
modules.update(import_test("src.safety_warnings", ["run_safety_warnings_check"]))
modules.update(import_test("src.bbs_utils", ["BBSUtils", "BendDeductionType", "HookType", "CuttingLengthResult", "generate_bar_shape_svg", "get_site_vernacular"]))
modules.update(import_test("src.documentation", ["DesignReportGenerator"]))
modules.update(import_test("src.bim_interop", ["CobieExporter"]))
modules.update(import_test("src.site_inspection", ["SiteInspectionManager"]))
modules.update(import_test("src.shm_module", ["SHMPlanner"]))
modules.update(import_test("src.shm_viz", ["SHMDashboard"]))
modules.update(import_test("src.digital_twin", ["DigitalTwinExplorer"]))

# ===== PHASE 2: ENUM ATTRIBUTES =====
log.log("\n[2/8] Testing Enum Attributes...")
BDT = modules.get("BendDeductionType")
HT = modules.get("HookType")
if BDT:
    test("BendDeductionType.NONE", lambda: BDT.NONE)
    test("BendDeductionType.IS_2502", lambda: BDT.IS_2502)
    test("BendDeductionType.SP_34", lambda: BDT.SP_34)
if HT:
    test("HookType.L_BEND", lambda: HT.L_BEND)
    test("HookType.U_HOOK", lambda: HT.U_HOOK)
    test("HookType.SEISMIC_135", lambda: HT.SEISMIC_135)
    test("HookType.STANDARD_90", lambda: HT.STANDARD_90)

# ===== PHASE 3: CORE LOGIC =====
log.log("\n[3/8] Testing Core Logic...")
GM = modules.get("GridManager")
gm = None; beams = []
if GM:
    gm = test("GridManager(width_m=10, length_m=10)", lambda: GM(width_m=10, length_m=10))
    if gm:
        test("gm.generate_grid()", lambda: gm.generate_grid())
        r = test("gm.generate_beams()", lambda: gm.generate_beams())
        if r: beams = r; log.log(f"     Beams: {len(beams)}, Columns: {len(gm.columns)}")

# ===== PHASE 4: MATERIALS =====
log.log("\n[4/8] Testing Materials...")
Conc = modules.get("Concrete")
concrete = None
if Conc:
    concrete = test("Concrete.from_grade('M25')", lambda: Conc.from_grade("M25"))
    if concrete:
        for a in ["fck","density","modulus_of_elasticity","poissons_ratio"]:
            test(f"concrete.{a}", lambda attr=a: getattr(concrete, attr))

# ===== PHASE 5: VISUALIZATION =====
log.log("\n[5/8] Testing Visualization...")
Viz = modules.get("Visualizer")
if Viz and gm and concrete:
    viz = test("Visualizer()", lambda: Viz())
    if viz:
        for mode in ["Engineering","Architectural","Deflection","Utilization","Load Path"]:
            test(f"create_structure_figure(mode={mode})", lambda m=mode: viz.create_structure_figure(gm, beams, [], concrete, view_mode=m))

# ===== PHASE 6: BBS =====
log.log("\n[6/8] Testing BBS...")
BBSCls = modules.get("BBSUtils")
if BBSCls and BDT:
    test("BBSUtils.calculate_cutting_length(straight)", lambda: BBSCls.calculate_cutting_length(shape_code=0, dims_mm={"A":3500}, bar_dia_mm=16, bend_deduction=BDT.IS_2502))
    test("BBSUtils.calculate_cutting_length(box)", lambda: BBSCls.calculate_cutting_length(shape_code=51, dims_mm={"A":300,"B":200}, bar_dia_mm=8, bend_deduction=BDT.SP_34))
    
    # Test hook_type param (app.py passes this!)
    try:
        BBSCls.calculate_cutting_length(shape_code=51, dims_mm={"A":300,"B":200}, bar_dia_mm=8, bend_deduction=BDT.SP_34, hook_type=HT.SEISMIC_135)
        log.log("  [OK] BBSUtils.calculate_cutting_length with hook_type")
    except TypeError as e:
        if "hook_type" in str(e):
            errors.append(("BBSUtils.calculate_cutting_length(hook_type=...)", f"TypeError: {e}", "app.py passes hook_type but method doesn't accept it"))
            log.log(f"  [FAIL] BBSUtils.calculate_cutting_length(hook_type=...): {e}")
    
    clr = BBSCls.calculate_cutting_length(shape_code=0, dims_mm={"A":3500}, bar_dia_mm=16)
    test("CuttingLengthResult.cutting_length_mm", lambda: clr.cutting_length_mm)

gen_bbs = modules.get("generate_bbs_from_grid_manager")
if gen_bbs and gm: test("generate_bbs_from_grid_manager(gm)", lambda: gen_bbs(gm))

svg_gen = modules.get("generate_bar_shape_svg")
if svg_gen:
    for s in ["L-Shape","U-Shape","Box","Crank","Straight"]:
        test(f"generate_bar_shape_svg('{s}')", lambda sh=s: svg_gen(sh, {"A":500,"B":200}))

vern = modules.get("get_site_vernacular")
if vern:
    for m in ["B1","T1","ST1","EF1"]:
        test(f"get_site_vernacular('{m}')", lambda mk=m: vern(mk))

# ===== PHASE 7: ANALYSIS MODULES =====
log.log("\n[7/8] Testing Analysis Modules...")

stab = modules.get("run_stability_check")
if stab and gm:
    r = test("run_stability_check()", lambda: stab(gm.columns, beams, 1, 3.0))
    if r:
        checks, summary = r
        for a in ["total_members","passed_stability","passed_fire","all_passed","failed_members","recommendations","fire_rating_used"]:
            test(f"stability_summary.{a}", lambda attr=a: getattr(summary, attr))

seis = modules.get("run_seismic_check")
if seis and gm:
    r = test("run_seismic_check()", lambda: seis(gm.columns, beams, 1000.0, zone="III", building_type="residential", fck=25))
    if r:
        for a in ["parameters","base_shear_kn","warnings","all_scwb_pass","all_ductile_pass","has_floating_columns"]:
            test(f"seismic_result.{a}", lambda attr=a: getattr(r, attr))
        if hasattr(r,'parameters'):
            for a in ["zone_factor","design_acceleration","scwb_required","fundamental_period"]:
                test(f"seismic_result.parameters.{a}", lambda attr=a: getattr(r.parameters, attr))

quant = modules.get("Quantifier")
if quant and gm:
    q = test("Quantifier()", lambda: quant())
    if q:
        bom = test("calculate_bom()", lambda: q.calculate_bom(gm.columns, beams, [], grid_mgr=gm))
        if bom:
            for a in ["total_concrete_vol_m3","total_steel_weight_kg","total_cost_usd","total_carbon_kg","cement_bags","cement_kg","sand_m3","aggregate_m3","water_liters"]:
                test(f"bom.{a}", lambda attr=a: getattr(bom, attr))
        test("calculate_bom(use_fly_ash=False)", lambda: q.calculate_bom(gm.columns, beams, [], grid_mgr=gm, use_fly_ash=False))

safety = modules.get("run_safety_warnings_check")
if safety and gm: test("run_safety_warnings_check()", lambda: safety(gm.columns, beams))

anch = modules.get("AnchorageCalculator")
if anch: test("AnchorageCalculator(fck=25, fy=500)", lambda: anch(fck=25, fy=500))

opt = modules.get("optimize_structure")
if opt and gm:
    r = test("optimize_structure()", lambda: opt(gm.columns, 3.0, 1, fck=25, enable_optimization=True))
    if r:
        oc, os_ = r
        for a in ["all_safe","concrete_saved_m3","concrete_saved_pct","steel_saved_kg","steel_saved_pct","cost_saved","cost_saved_pct"]:
            test(f"opt_summary.{a}", lambda attr=a: getattr(os_, attr))

# ===== PHASE 8: DIGITAL TWIN & SHM =====
log.log("\n[8/8] Testing Digital Twin, SHM, Site Inspection...")

DTE = modules.get("DigitalTwinExplorer")
if DTE: test("DigitalTwinExplorer('Test')", lambda: DTE("Test"))

SHMD = modules.get("SHMDashboard")
if SHMD:
    shm = test("SHMDashboard('Test')", lambda: SHMD("Test"))
    if shm:
        test("get_damage_index()", lambda: shm.get_damage_index(1.45, 1.5))
        test("calculate_fft_spectrum()", lambda: shm.calculate_fft_spectrum(1.45))
        test("generate_heatmap_data()", lambda: shm.generate_heatmap_data(["C1"]))

SIM = modules.get("SiteInspectionManager")
if SIM:
    sim = test("SiteInspectionManager('Test')", lambda: SIM("Test"))
    if sim:
        test("generate_checklist()", lambda: sim.generate_checklist("Pre_Pour"))
        test("generate_qr_code()", lambda: sim.generate_qr_code("C1"))

cobie = modules.get("CobieExporter")
if cobie: test("CobieExporter()", lambda: cobie())

doc = modules.get("DesignReportGenerator")
if doc: test("DesignReportGenerator()", lambda: doc())

# ===== FINAL REPORT =====
log.log("\n" + "=" * 60)
if errors:
    log.log(f"AUDIT FAILED: {len(errors)} errors found\n")
    for i, (name, err, tb) in enumerate(errors, 1):
        log.log(f"--- Error {i}: {name} ---")
        log.log(f"    {err}")
        if tb:
            for line in tb.strip().split('\n')[-5:]:
                log.log(f"    {line}")
        log.log("")
else:
    log.log("ALL CHECKS PASSED")
log.log("=" * 60)
log.close()
sys.exit(1 if errors else 0)
