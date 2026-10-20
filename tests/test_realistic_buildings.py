"""
End-to-end runs of realistic Indian RC buildings and edge cases. Each run is checked three ways:

1. code values recomputed independently in the test from the printed clauses (IS 1893 6.4.2, 7.2.2, 7.6.2,
   7.6.3) - the design must use exactly these;
2. equilibrium / consistency (storey forces sum to VB, footing loads against the seismic weight, every member
   designed, the status list agrees with the check tables);
3. physical plausibility ranges that catch unit and scale errors (seismic weight 8-18 kN/m2 of floor, concrete
   0.2-0.8 m3/m2, reinforcement 40-200 kg per m3 of concrete).

Passing these is not evidence that a design is safe; it shows the pipeline applies the clauses it cites and
produces physically sensible numbers for ordinary buildings.
"""
import logging
import math

import pytest

from src.design_pipeline import DesignInputs, run_design
from src.grid_manager import GridManager
from src.wind_load import TerrainCategory, WindZone

logging.disable(logging.CRITICAL)

Z = {"II": 0.10, "III": 0.16, "IV": 0.24, "V": 0.36}
RHO = {"II": 0.007, "III": 0.011, "IV": 0.016, "V": 0.024}
SPEC = {"I": (0.40, 1.00, 0.25), "II": (0.55, 1.36, 0.34), "III": (0.67, 1.67, 0.42)}

CASES = {
    "G+1 house, Zone III": dict(w=9, l=12, n=2, h=3.0, seismic_zone="III", structural_system="SMRF", sbc_kn_m2=150),
    "G+3 apartment, Zone IV soft soil": dict(w=15, l=20, n=4, h=3.0, seismic_zone="IV", structural_system="SMRF",
                                             soil_type="III", sbc_kn_m2=100, conc_grade="M30", fy=500.0),
    "G+4 office, Zone II": dict(w=18, l=24, n=5, h=3.6, seismic_zone="II", building_type_name="Commercial (Office)",
                                sbc_kn_m2=200),
    "G+2 school, Zone V": dict(w=24, l=9, n=3, h=3.6, seismic_zone="V", structural_system="SMRF",
                               building_type_name="Institutional", sbc_kn_m2=200, conc_grade="M30"),
    "single-storey shop": dict(w=6, l=6, n=1, h=3.5, seismic_zone="II", sbc_kn_m2=200),
    "G+9, Zone V": dict(w=15, l=15, n=10, h=3.0, seismic_zone="V", structural_system="SMRF", sbc_kn_m2=250,
                        conc_grade="M30", fy=500.0),
    "SBC 75 kN/m2": dict(w=12, l=12, n=3, h=3.0, seismic_zone="III", structural_system="SMRF", sbc_kn_m2=75),
    "long narrow 48 x 6 m": dict(w=48, l=6, n=2, h=3.0, seismic_zone="II", sbc_kn_m2=200),
    "6 m storey": dict(w=12, l=12, n=1, h=6.0, seismic_zone="II", sbc_kn_m2=200),
}


def _run(case):
    c = dict(CASES[case])
    w, l, n, h = c.pop("w"), c.pop("l"), c.pop("n"), c.pop("h")
    gm = GridManager(width_m=w, length_m=l, num_stories=n, story_height_m=h)
    gm.generate_grid()
    r = run_design(gm, gm.generate_beams(), DesignInputs(num_stories=n, story_height_m=h, wind_zone=WindZone("3"),
                                                         terrain_category=TerrainCategory("3"), **c))
    return r, dict(CASES[case])


@pytest.fixture(scope="module", params=list(CASES))
def run(request):
    return _run(request.param)


def test_base_shear_follows_is1893(run):
    r, c = run
    sr = r.seismic_result
    H = c["n"] * c["h"]
    d = max(c["w"], c["l"])
    ta = min(0.075 * H ** 0.75, 0.09 * H / math.sqrt(d))          # infilled frame, 7.6.2(c) bounded by 7.6.2.1
    t_end, num, floor = SPEC[c.get("soil_type", "II")]
    sa = 2.5 if ta <= t_end else (num / ta if ta <= 4.0 else floor)
    I = {"Residential": 1.0, "Commercial (Office)": 1.2, "Institutional": 1.5}[c.get("building_type_name", "Residential")]
    R = 5.0 if c.get("structural_system") == "SMRF" else 3.0
    ah = Z[c["seismic_zone"]] / 2 * I / R * sa
    assert sr.parameters.fundamental_period == pytest.approx(ta, rel=1e-6)
    assert sr.base_shear_kn == pytest.approx(max(ah, RHO[c["seismic_zone"]]) * r.building_weight, rel=1e-6)
    # 7.6.3: storey forces sum to VB and follow W h^2
    assert sum(sr.storey_forces_kn) == pytest.approx(sr.base_shear_kn, rel=1e-9)
    wh2 = [w * hh * hh for w, hh in zip(sr.storey_weights_kn, sr.storey_heights_m)]
    for f, q in zip(sr.storey_forces_kn, wh2):
        assert f == pytest.approx(sr.base_shear_kn * q / sum(wh2), rel=1e-9)


def test_plausible_quantities(run):
    r, c = run
    area = c["w"] * c["l"] * c["n"]
    assert 8.0 <= r.building_weight / area <= 18.0                  # kN per m2 of floor
    assert 0.2 <= r.bom.total_concrete_vol_m3 / area <= 0.8        # m3 per m2 of floor
    assert 40.0 <= r.bom.total_steel_weight_kg / r.bom.total_concrete_vol_m3 <= 200.0


def test_every_member_is_designed(run):
    r, _ = run
    gm = r.gm
    assert set(gm.rebar_schedule) == {col.id for col in gm.columns}
    assert len(gm.beam_schedule) == len(r.beams)
    assert len(r.footings) == len([col for col in gm.columns if col.level == 0])
    for res in list(gm.rebar_schedule.values()) + list(gm.beam_schedule.values()) + list(gm.slab_schedule.values()):
        assert res.status in ("PASS", "WARN", "FAIL")
    for ft in r.footings:
        assert all(math.isfinite(v) and v > 0 for v in (ft.length_m, ft.thickness_mm, ft.steel_weight_kg))


def test_footing_loads_are_consistent_with_the_building_weight(run):
    r, _ = run
    service = sum(ft.service_load_kn for ft in r.footings)
    # footings carry the full DL + LL (+ ground-storey walls on plinth beams); the seismic weight has 25-50 % of the
    # floor live load and no roof live load, so the footing total must be at least W and not wildly above it
    assert r.building_weight * 0.9 <= service <= r.building_weight * 1.6


def test_status_list_agrees_with_the_check_tables(run):
    r, c = run
    drift_fail = any(d["Status"] == "FAIL" for d in r.drift_results)
    assert drift_fail == any(f["Type"] == "Storey drift" and f["Status"] == "FAIL" for f in r.failures)
    method_needed = c["seismic_zone"] != "II" or c["n"] * c["h"] >= 15.0
    assert method_needed == any(f["Type"] == "Seismic method" for f in r.failures)
    order = {"PASS": 0, "WARN": 1, "FAIL": 2}
    assert order[r.status] >= max([order[f["Status"]] for f in r.failures] + [0])


def test_wind_pressure_follows_is875(run):
    r, c = run
    from src.wind_load import K2_TABLE
    top = r.wind_result.pressure_results[-1]
    z = max(top.height_m, 10.0)
    hs = [h for h, _ in K2_TABLE]
    i = max(k for k in range(len(hs)) if hs[k] <= z)
    k2 = K2_TABLE[i][1][2] if hs[i] == z or i == len(hs) - 1 else \
        K2_TABLE[i][1][2] + (K2_TABLE[i + 1][1][2] - K2_TABLE[i][1][2]) * (z - hs[i]) / (hs[i + 1] - hs[i])
    vz = 44.0 * k2                                                   # zone 3: Vb = 44 m/s, k1 = k3 = 1
    assert top.design_wind_speed_ms == pytest.approx(vz, rel=1e-6)
    assert top.design_wind_pressure_kn_m2 == pytest.approx(0.6 * vz ** 2 / 1000.0, rel=1e-6)
