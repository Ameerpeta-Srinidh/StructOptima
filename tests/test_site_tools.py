"""
Site tools that replaced simulated features (gap analysis N14, N15).

Expected values are hand calculations written next to each assertion.
"""
import math

import numpy as np
import pytest

from src.grid_manager import GridManager
from src.site_calculators import (concrete_pour_calculator, cube_test_summary, formwork_area_calculator,
                                  materials_for_mix, optimise_cutting)
from src.site_monitoring import (as_built_deviation, frequency_change, member_info, qr_png, qr_text,
                                 spectrum_from_csv, strain_readings, survey_from_csv, vibration_spectrum)

MIX = {"name": "Lab mix M25", "cement_kg_m3": 400.0, "water_kg_m3": 180.0,
       "fine_aggregate_kg_m3": 700.0, "coarse_aggregate_kg_m3": 1100.0}


def test_materials_come_only_from_the_approved_mix():
    m = materials_for_mix(10.0, MIX)
    assert m["cement_kg"] == 4000.0 and m["cement_bags"] == 80          # 10 x 400 / 50
    assert m["water_l"] == 1800 and m["fine_aggregate_t"] == 7.0 and m["coarse_aggregate_t"] == 11.0
    assert m["water_cement_ratio"] == pytest.approx(0.45)
    with pytest.raises(ValueError):
        materials_for_mix(10.0, {"cement_kg_m3": 400.0})


def test_pour_logistics():
    p = concrete_pour_calculator(25.0, 6.0, 5.0, 20.0)
    assert p["gross_volume_m3"] == 26.25                                 # 25 x 1.05
    assert p["num_trips"] == 5                                           # ceil(26.25 / 6)
    assert p["estimated_pour_time_hr"] == 1.3                            # 26.25 / 20
    assert "materials" not in p                                          # no mix -> no material quantities
    assert concrete_pour_calculator(25.0, 6.0, 0.0, 20.0, MIX)["materials"]["cement_bags"] == 200   # 25 x 400 / 50


def test_formwork_deducts_slab_thickness():
    gm = GridManager(width_m=4.0, length_m=4.0, num_stories=1, story_height_m=3.0)
    gm.generate_grid()
    c = gm.columns[0]
    c.width_nb = c.depth_nb = 300.0
    b = gm.generate_beams()[0]
    b.properties.width_mm, b.properties.depth_mm = 230.0, 450.0
    fw = formwork_area_calculator([c], [b], slab_area_m2=16.0, slab_thickness_mm=150.0)
    assert fw["column_formwork_m2"] == pytest.approx(round(1.2 * (c.z_top - c.z_bottom - 0.15), 1))   # 1.2 x 2.85
    L = math.hypot(b.end_point.x - b.start_point.x, b.end_point.y - b.start_point.y)
    assert fw["beam_formwork_m2"] == pytest.approx(round((0.23 + 2 * 0.30) * L, 1))                  # sides below slab
    assert fw["slab_formwork_m2"] == 16.0


def test_cube_summary_is_arithmetic_only():
    r = cube_test_summary(25.0, [26.0, 28.0, 30.0])
    assert (r["mean_mpa"], r["min_mpa"], r["mean_over_fck"]) == (28.0, 26.0, 1.12)
    assert r["max_deviation_from_mean_pct"] == 7.1                       # 2 / 28
    assert not any("accept" in k for k in r)
    with pytest.raises(ValueError):
        cube_test_summary(25.0, [])


def test_cutting_plan_first_fit_decreasing():
    r = optimise_cutting([("B1-T", 12, 5.0, 2), ("B2-T", 12, 7.0, 1), ("C1-L", 12, 4.0, 1), ("LONG", 16, 13.0, 3)], 12.0)
    d = r["by_diameter"][12]
    # 7 -> bar 1 (5 left), 5 -> bar 1 (0 left), 5 -> bar 2 (7 left), 4 -> bar 2 (3 left)
    assert d["stock_bars"] == 2 and d["cut_length_m"] == 21.0 and d["offcut_m"] == 3.0
    assert d["efficiency_pct"] == 87.5
    assert r["needs_lap"] == [{"Mark": "LONG", "Dia (mm)": 16, "Length (m)": 13.0, "Nos": 3}]
    assert d["cut_weight_kg"] == pytest.approx(round(21.0 * 0.888, 1))


def test_vibration_spectrum_finds_the_measured_frequency():
    fs, T, f0 = 100.0, 20.0, 2.5
    t = np.arange(0, T, 1 / fs)
    a = 0.05 * np.sin(2 * np.pi * f0 * t) + 0.01 * np.sin(2 * np.pi * 9.0 * t)
    s = vibration_spectrum(t, a)
    assert s["sampling_hz"] == pytest.approx(fs) and s["resolution_hz"] == pytest.approx(fs / t.size)
    assert abs(s["dominant_hz"] - f0) <= s["resolution_hz"]
    csv_bytes = ("time,accel\n" + "\n".join(f"{x:.4f},{y:.6f}" for x, y in zip(t, a))).encode()
    assert abs(spectrum_from_csv(csv_bytes)["dominant_hz"] - f0) <= s["resolution_hz"]
    with pytest.raises(ValueError):
        vibration_spectrum(t[:10], a[:10])
    bad_t = t.copy()
    bad_t[100:] += 0.5
    with pytest.raises(ValueError):
        vibration_spectrum(bad_t, a)


def test_frequency_change_and_strain():
    fc = frequency_change(1.8, 2.0)
    assert fc["change_pct"] == pytest.approx(-10.0) and fc["apparent_stiffness_ratio"] == pytest.approx(0.81)
    r = strain_readings([("SG1", 1250.0)], fy_mpa=500.0)[0]
    assert r["Yield strain (µε)"] == 2500 and r["Strain / yield strain"] == 0.5 and r["Stress if elastic (MPa)"] == 250.0


def test_as_built_deviation_against_design_grid():
    gm = GridManager(width_m=8.0, length_m=8.0, num_stories=1, story_height_m=3.0)
    gm.generate_grid()
    c = gm.columns[0]
    res = as_built_deviation(gm, [(c.id, c.x + 0.003, c.y + 0.004), ("ZZ", 0.0, 0.0)], tolerance_mm=10.0)
    row = res["rows"][0]
    assert row["Deviation (mm)"] == 5.0 and row["Status"] == "Within tolerance"      # sqrt(3^2 + 4^2)
    assert res["unknown_ids"] == ["ZZ"] and len(res["not_surveyed"]) == len(gm.columns) - 1
    assert as_built_deviation(gm, [(c.id, c.x + 0.012, c.y)], 10.0)["exceeding"] == 1
    with pytest.raises(ValueError):
        as_built_deviation(gm, [(c.id, c.x, c.y)], 0.0)
    assert survey_from_csv(gm, f"id,x,y\n{c.id},{c.x},{c.y}\n".encode(), 5.0)["rows"][0]["Deviation (mm)"] == 0.0


def test_member_info_and_qr_use_design_data():
    import logging
    logging.disable(logging.CRITICAL)
    from src.design_pipeline import DesignInputs, run_design
    from src.drawings import compute_marks
    gm = GridManager(width_m=8.0, length_m=8.0, num_stories=1, story_height_m=3.0)
    gm.generate_grid()
    r = run_design(gm, gm.generate_beams(), DesignInputs(num_stories=1, story_height_m=3.0, max_iterations=2))
    marks = compute_marks(r.gm, r.beams, r.footings)
    c = r.gm.columns[0]
    info = member_info(r.gm, r.beams, r.footings, marks, c.id)
    assert info["Main bars"] == r.gm.rebar_schedule[c.id].main_bars_desc and info["Concrete"] == f"M{r.gm.fck:.0f}"
    assert member_info(r.gm, r.beams, r.footings, marks, r.beams[0].id)["Stirrups"] == \
        r.gm.get_beam_result(r.beams[0].id).stirrups_desc
    assert member_info(r.gm, r.beams, r.footings, marks, "nope") == {}
    txt = qr_text(info, "P", c.id)
    assert info["Main bars"] in txt and "http" not in txt
    assert qr_png(txt)[:8] == b"\x89PNG\r\n\x1a\n"
