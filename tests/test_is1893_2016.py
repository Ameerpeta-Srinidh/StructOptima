"""
IS 1893 (Part 1):2016 with Amendments 1 (2017) and 2 (2020), checked against the printed standard
(docs/verification/standards-check-2026-10-20.md). Each test cites the clause; expected values are hand
calculations from the clause text.

Regression tests for findings S1-S7 of the 2026-10-20 standards check.
"""
import logging
import math

import pytest

from src.design_pipeline import DesignInputs, run_design
from src.grid_manager import GridManager
from src.seismic import (AnalysisMethod, FloatingColumnCheck, SeismicDesignChecker, SeismicZone, check_soft_storeys,
                         run_seismic_check)

logging.disable(logging.CRITICAL)


def _checker(zone="III", soil="II", system="SMRF"):
    return SeismicDesignChecker(zone=SeismicZone(zone), soil_type=soil, structural_system=system)


# ---- S1: 6.4.2(a) spectrum for the equivalent static method has no short-period ramp --------------------------

@pytest.mark.parametrize("soil,t_end,num,floor", [("I", 0.40, 1.00, 0.25), ("II", 0.55, 1.36, 0.34),
                                                  ("III", 0.67, 1.67, 0.42)])
def test_static_spectrum_follows_clause_6_4_2_a(soil, t_end, num, floor):
    c = _checker(soil=soil)
    for t in (0.01, 0.05, 0.09, 0.10, t_end):
        assert c.get_spectral_acceleration(t) == pytest.approx(2.5)
    for t in (t_end + 0.01, 1.0, 2.0, 4.0):
        assert c.get_spectral_acceleration(t) == pytest.approx(num / t)
    assert c.get_spectral_acceleration(4.5) == pytest.approx(floor)


def test_response_spectrum_branch_keeps_the_ramp():   # 6.4.2(b), for a future dynamic analysis
    c = _checker()
    assert c.get_spectral_acceleration(0.05, method="response_spectrum") == pytest.approx(1 + 15 * 0.05)


def test_single_storey_infilled_building_gets_the_plateau():
    # 7.6.2(c): Ta = 0.09 h / sqrt(d) = 0.09 * 3.5 / sqrt(18) = 0.0742 s (< 0.10 s); 7.6.2.1 (Amd 2): not more
    # than 0.075 h^0.75 = 0.193 s.  Sa/g = 2.5 -> Vb = Z/2 * I/R * 2.5 * W = 0.08 * 1/5 * 2.5 * 1000 = 40 kN
    r = run_seismic_check([], [], 1000.0, zone="III", height_m=3.5, structural_system="SMRF",
                          base_dimension_m=18.0, masonry_infill=True)
    assert r.parameters.fundamental_period == pytest.approx(0.09 * 3.5 / math.sqrt(18.0), rel=1e-6)
    assert r.base_shear_kn == pytest.approx(40.0, rel=1e-6)


# ---- S3: 7.2.2 / Table 7 minimum design lateral force ------------------------------------------------------

@pytest.mark.parametrize("zone,rho", [("II", 0.007), ("III", 0.011), ("IV", 0.016), ("V", 0.024)])
def test_minimum_base_shear_table_7(zone, rho):
    # 150 m, rock: Ta = 0.075 * 150^0.75 = 3.21 s, Sa/g = 1/Ta; with R = 5 every zone falls below rho W
    r = run_seismic_check([], [], 10000.0, zone=zone, height_m=150.0, soil_type="I", structural_system="SMRF",
                          storey_weights_kn=[5000.0, 5000.0], storey_heights_m=[75.0, 150.0])
    z = {"II": 0.10, "III": 0.16, "IV": 0.24, "V": 0.36}[zone]
    ta = 0.075 * 150.0 ** 0.75
    assert z / 2 * 1.0 / 5.0 * (1.0 / ta) < rho                     # the spectrum value is below the minimum
    assert r.base_shear_kn == pytest.approx(rho * 10000.0, rel=1e-6)
    assert sum(r.storey_forces_kn) == pytest.approx(r.base_shear_kn)


def test_minimum_does_not_change_ordinary_low_rise():
    r = run_seismic_check([], [], 1000.0, zone="III", height_m=7.0, structural_system="SMRF")
    assert r.base_shear_kn == pytest.approx(0.08 * 0.2 * 2.5 * 1000.0)   # 4 % > 1.1 %


# ---- S4: 7.6 and 7.7.1 - equivalent static method only for regular buildings < 15 m in Zone II -------------

@pytest.mark.parametrize("zone,h,allowed", [("II", 14.9, True), ("II", 15.0, False), ("III", 7.0, False),
                                            ("IV", 3.5, False), ("V", 3.5, False)])
def test_static_method_permitted_only_per_7_7_1(zone, h, allowed):
    m = _checker(zone=zone).check_analysis_method([], num_stories=1, building_height_m=h)
    assert m.static_allowed is allowed
    assert m.required_method == (AnalysisMethod.EQUIVALENT_STATIC if allowed else AnalysisMethod.RESPONSE_SPECTRUM)
    if not allowed:
        assert "7.7.1" in m.reason


# ---- S2: Table 9 Note 1 - OMRF not allowed in Zones III, IV and V ------------------------------------------

def _design(zone, system, stories=2, **kw):
    gm = GridManager(width_m=12.0, length_m=9.0, num_stories=stories, story_height_m=3.2)
    gm.generate_grid()
    return run_design(gm, gm.generate_beams(), DesignInputs(num_stories=stories, story_height_m=3.2,
                                                            seismic_zone=zone, structural_system=system, **kw))


@pytest.mark.parametrize("zone,system,expect", [("II", "OMRF", False), ("III", "OMRF", True), ("V", "OMRF", True),
                                                ("III", "SMRF", False)])
def test_omrf_not_permitted_in_zones_iii_to_v(zone, system, expect):
    r = _design(zone, system)
    rows = [f for f in r.failures if f["Type"] == "Structural system"]
    assert bool(rows) is expect
    if expect:
        assert rows[0]["Status"] == "FAIL" and "Table 9" in rows[0]["Issue"]
        assert r.status == "FAIL"


def test_zone_ii_low_rise_regular_building_has_no_method_failure():
    r = _design("II", "OMRF")
    assert not any(f["Type"] == "Seismic method" for f in r.failures)


def test_zone_iii_building_uses_the_response_spectrum_method():
    # 7.7.1 requires dynamic analysis -> 7.7.5 response spectrum on the 3D rigid-diaphragm model, scaled to VB (7.7.3)
    r = _design("III", "SMRF")
    assert r.seismic_result.method_used.startswith("response spectrum")
    assert not any(f["Type"] == "Seismic method" for f in r.failures)
    for d in ("X", "Y"):
        dyn = r.seismic_result.dynamic[d]
        assert dyn["Scale factor"] >= 1.0
        assert dyn["VB design (kN)"] >= dyn["VB static (kN)"] - 1e-6
        assert dyn["Mass in those modes %"] >= 90.0


# ---- S6: Table 6(ii) mass irregularity -----------------------------------------------------------------------

def test_mass_irregularity_detected_from_storey_weights():
    r = run_seismic_check([], [], 3600.0, zone="II", height_m=9.0, storey_weights_kn=[1000.0, 1600.0, 1000.0],
                          storey_heights_m=[3.0, 6.0, 9.0], structural_system="OMRF")
    assert any(i.irregularity_type.value == "Mass Irregularity" and i.is_irregular for i in r.irregularity_checks)
    assert not r.static_analysis_allowed


def test_equal_storeys_are_not_mass_irregular():
    r = run_seismic_check([], [], 3000.0, zone="II", height_m=9.0, storey_weights_kn=[1000.0, 1000.0, 900.0],
                          storey_heights_m=[3.0, 6.0, 9.0], structural_system="OMRF")
    assert r.static_analysis_allowed


# ---- S5: Table 6(i) as amended (Amd 2) - soft storey: stiffness less than the storey above --------------------

@pytest.mark.parametrize("k,soft", [([100.0, 100.0], []), ([120.0, 100.0], []), ([99.0, 100.0], [0]),
                                    ([80.0, 90.0, 100.0], [0, 1])])
def test_soft_storey_definition(k, soft):
    assert [c.storey for c in check_soft_storeys(k)] == soft


# ---- S7: Table 6(vi) as amended (Amd 2) - floating columns not permitted -----------------------------------

def test_floating_column_is_a_failure(monkeypatch):
    fc = FloatingColumnCheck(column_id="C9_L1", is_floating=True, supporting_beam_id="B_H_3", transfer_load_kn=120.0,
                             warning="C9 starts on beam B_H_3")
    monkeypatch.setattr(SeismicDesignChecker, "detect_floating_columns", lambda self, cols, beams: [fc])
    r = _design("II", "OMRF")
    rows = [f for f in r.failures if f["Type"] == "Floating column"]
    assert rows and rows[0]["Status"] == "FAIL" and rows[0]["Member"] == "C9_L1"


# ---- 6.4.3.1: cracked stiffness is required ------------------------------------------------------------------

def test_gross_stiffness_is_flagged():
    r = _design("II", "OMRF", use_cracked_sections=False)
    assert any(f["Type"] == "Stiffness modifiers" and f["Status"] == "WARN" for f in r.failures)
    assert not any(f["Type"] == "Stiffness modifiers" for f in _design("II", "OMRF").failures)


def test_soft_storey_tolerance_for_computed_stiffness():   # D-27
    assert check_soft_storeys([207578.0, 208808.0], tolerance=0.10) == []
    assert [c.storey for c in check_soft_storeys([150000.0, 210000.0], tolerance=0.10)] == [0]


# ---- D-26: dynamic analysis on the rigid-diaphragm 3D model -----------------------------------------------------

def test_torsion_loads_the_frames_of_the_other_direction():
    r = _design("III", "SMRF")
    shares = r.analysis_summary.lateral_shares["EQX"]
    yz = [v for k, v in shares.items() if k.startswith("YZ")]
    assert yz and any(abs(x) > 0 for v in yz for x in v)          # accidental torsion (7.8.2) reaches Y frames
    xz = [sum(v) for k, v in shares.items() if k.startswith("XZ")]
    # each frame takes its more severe eccentricity case (7.8.2), so the X frames together carry at least VB
    vb = r.seismic_result.dynamic["X"]["VB design (kN)"]
    assert vb - 1e-6 <= sum(xz) <= 1.15 * vb


def test_re_entrant_plan_is_a_warning_with_the_check_to_do():
    import os
    from src.cad_loader import CADLoader
    path = os.path.join(os.path.dirname(__file__), "..", "samples", "test_cases", "stress", "l_shape.dxf")
    loader = CADLoader(path)
    gm, beams = loader.load_grid_manager(num_stories=2, story_height_m=3.2)
    gm.columns = gm.stack_columns([c for c in gm.columns if c.level == 0], 2, 3.2)
    r = run_design(gm, beams, DesignInputs(num_stories=2, story_height_m=3.2, seismic_zone="III",
                                           structural_system="SMRF", max_iterations=3))
    rows = [f for f in r.failures if f["Type"] == "Seismic method"]
    assert rows and all(f["Status"] == "WARN" for f in rows)
    assert "FLEXIBLE" in rows[0]["Issue"] and "ETABS" in rows[0]["Issue"]


def test_no_stale_static_method_warning_after_dynamic_analysis():
    r = _design("III", "SMRF")
    assert not any("results are not valid for design" in w for w in r.seismic_result.warnings)
    assert any("response spectrum method (7.7.5) was used" in w for w in r.seismic_result.warnings)
