"""
Storey drift (N16) and one-direction frame columns (N19).

Benchmark: one-storey, one-bay building with 300 x 300 columns and very deep
(near-rigid) beams under a lateral storey force V.  Storey stiffness in X is
the sum over the columns of 12 E I / h^3 (fixed-fixed sway, gross sections):

    E = 5000 sqrt(25) MPa = 25e6 kN/m2,  I = 0.3^4 / 12 = 6.75e-4 m4,  h = 3 m
    k = 12 * 25e6 * 6.75e-4 / 27 = 7500 kN/m per column, 4 columns -> 30 000 kN/m
    V = 100 kN  ->  drift = 100 / 30 000 = 3.333 mm,  ratio 0.001111

Beam flexibility (I_beam / I_col = 1000) and column axial shortening make the
model slightly softer than the rigid-beam value: tolerance 2 %.
"""
import logging

import pytest

from src.analysis_integration import LateralLoads, update_structural_analysis
from src.design_pipeline import DesignInputs, drift_checks, run_design
from src.grid_manager import GridManager

logging.disable(logging.CRITICAL)


def _one_bay(h=3.0):
    gm = GridManager(width_m=4.0, length_m=4.0, num_stories=1, story_height_m=h)
    gm.generate_grid()
    assert len(gm.x_grid_lines) == 2 and len(gm.y_grid_lines) == 2
    for c in gm.columns:
        c.width_nb = c.depth_nb = 300.0
    beams = gm.generate_beams()
    for b in beams:
        b.properties.width_mm, b.properties.depth_mm = 300.0, 3000.0
    gm.dead_load_kn_m2, gm.live_load_kn_m2 = 5.0, 2.0
    gm.roof_dead_kn_m2, gm.roof_live_kn_m2 = 5.0, 1.5
    return gm, beams


def test_storey_drift_matches_portal_hand_value():
    gm, beams = _one_bay()
    s = update_structural_analysis(gm, beams, fck=25.0, use_cracked_sections=False,
                                   lateral=LateralLoads(eq_x=[100.0], eq_y=[100.0]))
    drift, h, _ = s.storey_drift["EQX"][0]
    assert h == pytest.approx(3.0)
    assert drift == pytest.approx(100.0 / 30000.0, rel=0.02)
    assert s.storey_drift["EQY"][0][0] == pytest.approx(drift, rel=1e-6)   # square building
    assert s.top_displacement["EQX"][0] == pytest.approx(drift, rel=1e-6)  # one storey: top = drift


def test_drift_scales_with_cracked_column_modifier():
    gm, beams = _one_bay()
    g = update_structural_analysis(gm, beams, fck=25.0, use_cracked_sections=False, lateral=LateralLoads(eq_x=[100.0]))
    gm, beams = _one_bay()
    c = update_structural_analysis(gm, beams, fck=25.0, use_cracked_sections=True, lateral=LateralLoads(eq_x=[100.0]))
    # columns 0.70 Ig -> about 1/0.70 times the drift (beams stay near-rigid)
    assert c.storey_drift["EQX"][0][0] / g.storey_drift["EQX"][0][0] == pytest.approx(1 / 0.70, rel=0.03)


def test_drift_checks_limits_and_status():
    drift = {"EQX": {0: (0.0130, 3.0, "C1"), 1: (0.0100, 3.0, "C2")},
             "WLX": {0: (0.0020, 3.0, "C1"), 1: (0.0010, 3.0, "C2")}}
    top = {"EQX": (0.023, "C2"), "WLX": (0.0130, "C2")}   # H = 6 m -> H/500 = 12 mm
    rows = drift_checks(drift, top, total_height_m=6.0)
    eq = [r for r in rows if r["Case"] == "EQX"]
    assert [r["Status"] for r in eq] == ["FAIL", "PASS"]           # 13/3000 = 0.00433 > 0.004
    assert eq[0]["Ratio"] == pytest.approx(0.013 / 3.0)
    wl = [r for r in rows if r["Case"] == "WLX"]
    assert wl[-1]["Check"].startswith("Top sway") and wl[-1]["Status"] == "WARN"   # 13 mm > 12 mm


def test_pipeline_reports_drift_for_every_storey_and_direction():
    gm = GridManager(width_m=12.0, length_m=9.0, num_stories=3, story_height_m=3.2)
    gm.generate_grid()
    res = run_design(gm, gm.generate_beams(), DesignInputs(num_stories=3, story_height_m=3.2, max_iterations=3))
    eq = [r for r in res.drift_results if r["Check"] == "Storey drift" and r["Case"] in ("EQX", "EQY")]
    assert len(eq) == 2 * 3
    assert all(r["Drift (mm)"] > 0 for r in eq)
    fails = [r for r in res.drift_results if r["Status"] == "FAIL"]
    assert all(any(f["Type"] == "Storey drift" for f in res.failures) for _ in fails)


def test_column_on_one_frame_line_is_flagged():
    gm, beams = _one_bay()
    # an extra column on grid line y = 0 but off every x grid line: it lies on the
    # XZ frame only, so it receives no frame moments about the other axis
    extra = gm.columns[0].model_copy(deep=True)
    extra.id, extra.x, extra.y = "CX", 2.0, 0.0
    gm.columns.append(extra)
    s = update_structural_analysis(gm, beams, fck=25.0, lateral=LateralLoads(eq_x=[50.0], eq_y=[50.0]))
    assert s.columns_one_plane == {"CX": "YZ"}
    assert any("one direction only" in m for m in s.messages)
