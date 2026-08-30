"""
Comprehensive Column Placement & Beam Sizing Test Suite
Benchmarked against IS 456:2000, IS 13920:2016, IS 875 Pt1-2, SP 34:1987, NBC 2016
"""

import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.grid_manager import GridManager, Column
from src.column_placer import ColumnPlacer, JunctionType
from src.beam_placer import BeamPlacer, SupportType

# ── Real-life benchmarks ──────────────────────────────────────────────────────
RULES = {
    "max_bay_m":         5.0,   # IS 456 Table 26 economical span
    "min_bay_m":         3.0,   # SP 34 / NBC 2016
    "min_col_abs_mm":    200,   # IS 456 Cl 34.1.3
    "min_col_seismic":   300,   # IS 13920 Cl 6.1.3
    "min_aspect":        0.4,   # IS 13920 Cl 7.1.2
    "max_res_col_mm":    800,   # Sanity: G+2/G+3 residential max
    "beam_primary_ld":   12,    # SP 34 Ch6
    "beam_secondary_ld": 10,
    "beam_min_w":        200,   # IS 13920 Cl 6.2.1
    "beam_min_d":        300,
}

# ── Helpers ────────────────────────────────────────────────────────────────────
def check_bay_sizes(gm, label):
    failures = []
    for pts in [sorted(gm.x_grid_lines), sorted(gm.y_grid_lines)]:
        for i in range(len(pts)-1):
            s = abs(pts[i+1] - pts[i])
            if s > RULES["max_bay_m"] + 0.01:
                failures.append(f"{label}: span {s:.2f}m > {RULES['max_bay_m']}m (IS 456 Table 26)")
            if s < RULES["min_bay_m"] - 0.01 and len(pts) > 2:
                failures.append(f"{label}: span {s:.2f}m < {RULES['min_bay_m']}m (uneconomical, SP 34)")
    return failures

def check_column_sizes(gm, label, seismic=True):
    failures = []
    seen = set()
    for col in (c for c in gm.columns if c.level == 0):
        if col.id in seen: continue
        seen.add(col.id)
        w, d = col.width_nb, col.depth_nb
        sm = min(w, d)
        if sm < RULES["min_col_abs_mm"]:
            failures.append(f"{label} {col.id}({col.type}): {w:.0f}x{d:.0f} < 200mm abs min (IS 456 Cl 34.1.3)")
        if seismic and sm < RULES["min_col_seismic"]:
            failures.append(f"{label} {col.id}({col.type}): {w:.0f}x{d:.0f} < 300mm seismic (IS 13920 Cl 6.1.3)")
        asp = sm / max(w,d)
        if asp < RULES["min_aspect"]:
            failures.append(f"{label} {col.id}: aspect {asp:.2f} < 0.4 (IS 13920 Cl 7.1.2)")
        if w > RULES["max_res_col_mm"] or d > RULES["max_res_col_mm"]:
            failures.append(f"{label} {col.id}: {w:.0f}x{d:.0f} oversized for residential (load error?)")
    return failures

def check_beam_depths(beams, label):
    failures = []
    for b in beams:
        s = math.hypot(b.end_point.x-b.start_point.x, b.end_point.y-b.start_point.y)*1000
        d = b.properties.depth_mm
        w = b.properties.width_mm
        if s < 100: continue
        if w < RULES["beam_min_w"]:
            failures.append(f"{label} {b.id}: width {w:.0f}mm < 200mm (IS 13920 Cl 6.2.1)")
        if d < RULES["beam_min_d"]:
            failures.append(f"{label} {b.id}: depth {d:.0f}mm < 300mm site min")
        if "BC_" not in b.id:
            ld = s/d if d > 0 else 999
            if ld > 12.5:
                failures.append(f"{label} {b.id}: L/d={ld:.1f}>12 (span={s/1000:.1f}m, d={d:.0f}mm) - too shallow (SP 34 Ch6)")
    return failures

def check_loads(gm, label):
    failures = []
    gc = [c for c in gm.columns if c.level == 0]
    if not gc: return failures
    est = gm.width_m * gm.length_m * 8.0 * gm.num_stories
    tot = sum(c.load_kn for c in gc)
    if tot > 0 and est > 0:
        r = tot/est
        if r > 3.0:
            failures.append(f"{label}: total col load {tot:.0f}kN = {r:.1f}x expected {est:.0f}kN (floor_load too high?)")
        if r < 0.2:
            failures.append(f"{label}: total col load {tot:.0f}kN only {r:.1f}x expected (load calc error?)")
    return failures

def grid_test(name, W, L, stories, fl=4.0, wl=10.0):
    print(f"\n{'='*60}\nTEST: {name}\n  {W}m x {L}m | G+{stories-1} | FL={fl}kN/m2\n{'='*60}")
    gm = GridManager(width_m=W, length_m=L, num_stories=stories, story_height_m=3.5)
    gm.generate_grid()
    gm.calculate_trib_areas()
    gm.calculate_loads(floor_load_kn_m2=fl, wall_load_kn_m=wl)
    from src.materials import Concrete
    gm.optimize_column_sizes(concrete=Concrete.from_grade("M25"), fy=415.0)
    beams = gm.generate_beams()

    xs = sorted(gm.x_grid_lines); ys = sorted(gm.y_grid_lines)
    sx = [abs(xs[i+1]-xs[i]) for i in range(len(xs)-1)]
    sy = [abs(ys[i+1]-ys[i]) for i in range(len(ys)-1)]
    gc = [c for c in gm.columns if c.level==0]
    sizes = sorted(set((int(c.width_nb),int(c.depth_nb)) for c in gc))
    loads = [c.load_kn for c in gc]

    print(f"  Grid: {len(xs)-1}x{len(ys)-1} | SpansX:{[f'{s:.2f}m' for s in sx]} SpansY:{[f'{s:.2f}m' for s in sy]}")
    print(f"  Columns(GF): {len(gc)} | Sizes: {sizes}")
    print(f"  Loads: min={min(loads):.0f} max={max(loads):.0f} avg={sum(loads)/len(loads):.0f} kN")
    bd = [b.properties.depth_mm for b in beams if "BC_" not in b.id]
    if bd: print(f"  Beam depths: {sorted(set(bd))}mm")

    failures = []
    failures += check_bay_sizes(gm, name)
    failures += check_column_sizes(gm, name)
    failures += check_beam_depths(beams, name)
    failures += check_loads(gm, name)

    if failures:
        print(f"\n  FAIL ({len(failures)}):")
        for f in failures: print(f"    x {f}")
    else:
        print(f"\n  PASS - all IS code checks satisfied")
    return {"name":name,"passed":not failures,"failures":failures}

def placer_test(name, nodes, cls, envelope=None, zone="III"):
    print(f"\n{'='*60}\nTEST (Placer): {name} [Zone {zone}]\n{'='*60}")
    p = ColumnPlacer(nodes=nodes, centerlines=cls, seismic_zone=zone, building_envelope=envelope)
    r = p.generate_placement()
    cols = r.columns
    sizes = sorted(set((int(c.width),int(c.depth)) for c in cols))
    print(f"  Placed: {r.stats['total_columns']} cols | sizes: {sizes}")
    min_mm = 300 if zone in ["III","IV","V"] else 230
    failures = []
    for c in cols:
        sm = min(c.width, c.depth)
        if sm < min_mm:
            failures.append(f"{name} {c.id}({c.junction_type.value}): {c.width:.0f}x{c.depth:.0f} < {min_mm}mm")
        asp = sm/max(c.width,c.depth)
        if asp < 0.4:
            failures.append(f"{name} {c.id}: aspect {asp:.2f}<0.4")
    for i,c1 in enumerate(cols):
        for c2 in cols[i+1:]:
            dist = math.hypot(c1.x-c2.x,c1.y-c2.y)
            if 0 < dist < 600:
                failures.append(f"{name}: {c1.id}&{c2.id} only {dist:.0f}mm apart (too close)")
    if failures:
        print(f"\n  FAIL ({len(failures)}):")
        for f in failures: print(f"    x {f}")
    else:
        print(f"\n  PASS")
    return {"name":name,"passed":not failures,"failures":failures}

# ── Test Cases ────────────────────────────────────────────────────────────────
def tc1():  return grid_test("TC1 2BHK 10x12m G+2",   10, 12, 3)
def tc2():  return grid_test("TC2 Apartment 12x15m G+3", 12, 15, 4)
def tc3():  return grid_test("TC3 Small House 8x8m G+1",  8,  8, 2)
def tc4():  return grid_test("TC4 Commercial 15x20m GF", 15, 20, 1, fl=6.5, wl=8.0)
def tc5():  return grid_test("TC5 Row House 6x18m G+2",   6, 18, 3)
def tc6():  return grid_test("TC6 Large 20x25m G+5",     20, 25, 6)
def tc7():  return grid_test("TC7 Minimal 5x6m G+1",      5,  6, 2)

def tc8():
    W,H = 12000,10000
    n = [(0,0),(W,0),(W,H),(0,H)]
    cl = [((0,0),(W,0)),((W,0),(W,H)),((W,H),(0,H)),((0,H),(0,0))]
    return placer_test("TC8 Box 12x10m", n, cl, n, "III")

def tc9():
    W,H,MY = 12000,8000,4000
    n = [(0,0),(W,0),(W,H),(0,H),(0,MY),(W,MY),(4000,0),(4000,MY),(4000,H),(8000,0),(8000,MY),(8000,H)]
    cl = [((0,0),(4000,0)),((4000,0),(8000,0)),((8000,0),(W,0)),
          ((W,0),(W,MY)),((W,MY),(W,H)),((W,H),(8000,H)),((8000,H),(4000,H)),((4000,H),(0,H)),
          ((0,H),(0,MY)),((0,MY),(0,0)),
          ((0,MY),(4000,MY)),((4000,MY),(8000,MY)),((8000,MY),(W,MY))]
    env = [(0,0),(W,0),(W,H),(0,H)]
    return placer_test("TC9 Interior Wall 12x8m", n, cl, env, "III")

def tc10():
    W,H,MY = 10000,8000,4000
    n = [(0,0),(W,0),(W,H),(0,H),(0,MY),(W,MY),(5000,0),(5000,MY),(5000,H)]
    cl = [((0,0),(5000,0)),((5000,0),(W,0)),((W,0),(W,H)),((0,H),(W,H)),((0,0),(0,H)),
          ((0,MY),(5000,MY)),((5000,MY),(W,MY))]
    env = [(0,0),(W,0),(W,H),(0,H)]
    return placer_test("TC10 Zone V 10x8m", n, cl, env, "V")

def tc11():
    n = [(0,0),(12000,0),(12000,6000),(8000,6000),(8000,10000),(0,10000)]
    cl = [((0,0),(12000,0)),((12000,0),(12000,6000)),((12000,6000),(8000,6000)),
          ((8000,6000),(8000,10000)),((8000,10000),(0,10000)),((0,10000),(0,0)),
          ((0,6000),(8000,6000)),((4000,0),(4000,10000)),((8000,0),(8000,6000))]
    env = n
    return placer_test("TC11 L-Shape 12x10m", n, cl, env, "III")

def tc12():
    print(f"\n{'='*60}\nTEST TC12: Beam Depth Validation (L/d=12)\n{'='*60}")
    failures = []
    for span_m in [3.0, 3.5, 4.0, 4.5, 5.0]:
        gm = GridManager(width_m=span_m, length_m=span_m, num_stories=2)
        gm.generate_grid()
        beams = gm.generate_beams()
        for b in beams:
            s = math.hypot(b.end_point.x-b.start_point.x, b.end_point.y-b.start_point.y)*1000
            if abs(s-span_m*1000)<100:
                d = b.properties.depth_mm
                ld = s/d
                req = math.ceil((s/12)/50)*50
                req = max(req, 300)
                ok = d >= req
                sym = "OK" if ok else "FAIL"
                print(f"  {span_m:.1f}m: D={d:.0f}mm L/d={ld:.1f} (req>={req:.0f}mm) [{sym}]")
                if not ok:
                    failures.append(f"Span {span_m}m: depth {d}mm < {req}mm")
                break
    if failures:
        print(f"\n  FAIL:"); [print(f"    x {f}") for f in failures]
    else:
        print(f"\n  PASS - all beam depths satisfy L/d <= 12")
    return {"name":"TC12 Beam Sizing","passed":not failures,"failures":failures}

# ── Runner ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n"+"="*60)
    print("STRUCTOPTIMA — COLUMN & BEAM PLACEMENT TEST SUITE")
    print("IS 456:2000 | IS 13920:2016 | SP 34:1987 | IS 875")
    print("="*60)
    results = [tc1(),tc2(),tc3(),tc4(),tc5(),tc6(),tc7(),
               tc8(),tc9(),tc10(),tc11(),tc12()]
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    print(f"\n{'='*60}")
    print(f"SUMMARY: {passed}/{total} PASSED")
    for r in results:
        sym = "OK" if r["passed"] else "FAIL"
        print(f"  [{sym}] {r['name']}")
        if not r["passed"]:
            for f in r["failures"][:2]: print(f"         - {f}")
    print("="*60)
    sys.exit(0 if passed==total else 1)
