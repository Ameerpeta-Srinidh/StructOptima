"""
IS 13920:2016 with Amendments 1 (2017) and 2 (2020), checked against the printed standard
(docs/verification/standards-check-2026-10-20.md). Regression tests for findings J1-J9.
"""
import logging

import pytest

from src.bbs_module import seismic_hook_extension
from src.design_pipeline import DesignInputs, run_design
from src.grid_manager import GridManager
from src.seismic import joint_confinement_factor, joint_effective_breadth, min_concrete_grade

logging.disable(logging.CRITICAL)


# ---- J1: 9.1.1 (Amd 2) joint shear strength factor ---------------------------------------------------------

@pytest.mark.parametrize("faces,k", [(4, 1.5), (3, 1.2), (2, 1.0), (1, 1.0), (0, 1.0)])
def test_joint_factor_by_confined_faces(faces, k):
    # two beams on opposite faces is an "other joint" (1.0), not 1.2
    assert joint_confinement_factor(faces) == k


# ---- J2: 9.1.2(a) (Amd 2) effective breadth of the joint ----------------------------------------------------

def test_effective_breadth_printed_case_column_narrower_than_beam():
    # bc < bb: bj = min[bb; bc + 0.5 hc] = min(400, 300 + 225) = 400
    assert joint_effective_breadth(bb=400.0, bc=300.0, hc=450.0) == pytest.approx(400.0)
    assert joint_effective_breadth(bb=400.0, bc=250.0, hc=200.0) == pytest.approx(350.0)


def test_effective_breadth_column_wider_than_beam_uses_half_depth():
    # bc >= bb (not printed in full; mirror form, more conservative than bb + hc): min(450, 230 + 0.5 * 300)
    assert joint_effective_breadth(bb=230.0, bc=450.0, hc=300.0) == pytest.approx(380.0)


# ---- J4: 5.2 minimum concrete grade --------------------------------------------------------------------------

@pytest.mark.parametrize("zone,h,grade", [("II", 30.0, 20), ("III", 15.0, 20), ("III", 15.1, 25), ("V", 40.0, 25)])
def test_min_concrete_grade(zone, h, grade):
    assert min_concrete_grade(zone, h) == grade


# ---- J8: 3.5 / 6.3.1 / 7.4.1 (Amd 1, Amd 2) 135 degree hook extension 8 d, not less than 75 mm --------------

@pytest.mark.parametrize("dia,ext", [(6, 75.0), (8, 75.0), (10, 80.0), (12, 96.0)])
def test_seismic_hook_extension(dia, ext):
    assert seismic_hook_extension(dia) == pytest.approx(ext)


# ---- pipeline-level checks -----------------------------------------------------------------------------------

def _design(zone="III", system="SMRF", stories=3, h=3.2, w=12.0, l=9.0, **kw):
    gm = GridManager(width_m=w, length_m=l, num_stories=stories, story_height_m=h)
    gm.generate_grid()
    return run_design(gm, gm.generate_beams(), DesignInputs(num_stories=stories, story_height_m=h, seismic_zone=zone,
                                                            structural_system=system, **kw))


@pytest.fixture(scope="module")
def smrf3():
    return _design()


def test_roof_joints_checked_up_to_four_storeys(smrf3):   # J3: 7.2.1.3
    levels = {d["Level"] for d in smrf3.seismic_result.scwb_details}
    assert 3 in levels


def test_roof_joints_waived_above_four_storeys():
    r = _design(stories=5)
    assert 5 not in {d["Level"] for d in r.seismic_result.scwb_details}


def test_joint_factors_in_design_follow_9_1_1(smrf3):
    assert {j["confinement_factor"] for j in smrf3.seismic_result.joint_details} <= {1.0, 1.2, 1.5}
    # a 12 x 9 m grid has interior joints with beams on four faces, edge joints on three, corners on two
    assert {1.0, 1.2, 1.5} <= {j["confinement_factor"] for j in smrf3.seismic_result.joint_details}


def test_concrete_grade_below_minimum_is_a_failure():   # J4 in the pipeline
    r = _design(stories=5, h=3.2, conc_grade="M20")       # 16 m in Zone III -> M25 required
    rows = [f for f in r.failures if f["Type"] == "Concrete grade"]
    assert rows and rows[0]["Status"] == "FAIL" and "5.2" in rows[0]["Issue"]
    assert not any(f["Type"] == "Concrete grade" for f in _design(stories=4, conc_grade="M20").failures)  # 12.8 m


def test_reinforcement_grade_note_where_is13920_applies(smrf3):   # J5: 5.3.1 (Amd 2)
    rows = [f for f in smrf3.failures if f["Type"] == "Reinforcement grade"]
    assert rows and rows[0]["Status"] == "WARN" and "14.5" in rows[0]["Issue"]
    assert not any(f["Type"] == "Reinforcement grade" for f in _design(zone="II", system="OMRF").failures)


def test_column_geometry_limits_7_1(monkeypatch):          # J6: 7.1.1 and 7.1.2 (Amd 1: 0.4)
    from src import design_pipeline as dp
    rows = dp.is13920_column_geometry([("C1_L0", 230.0, 450.0), ("C2_L0", 300.0, 800.0), ("C3_L0", 300.0, 450.0)],
                                      largest_beam_bar_mm=12)   # 20 x 12 = 240 < 300
    by = {m: issue for m, issue in rows}
    assert "300 mm" in by["C1_L0"]          # 230 < 300
    assert "0.4" in by["C2_L0"]             # 300 / 800 = 0.375 < 0.4
    assert "C3_L0" not in by
    rows = dp.is13920_column_geometry([("C4_L0", 300.0, 450.0)], largest_beam_bar_mm=20)   # 20 x 20 = 400 > 300
    assert rows and "20" in rows[0][1]


def test_column_axial_stress_limit_amd2():                 # J7: 7.1 (Amd 2) 0.40 fck under earthquake combinations
    from src import design_pipeline as dp
    forces = [("1.5(DL+LL)", 2000.0, 0, 0), ("1.2(DL+LL+EQx)", 1100.0, 0, 0), ("0.9DL+1.5EQx", 700.0, 0, 0)]
    # 300 x 450, M25: 0.4 * 25 * 300 * 450 / 1000 = 1350 kN - the gravity case does not count
    assert dp.eq_axial_stress_ratio(forces, 300.0, 450.0, 25.0) == pytest.approx(1100e3 / (300 * 450) / (0.4 * 25))
    assert dp.eq_axial_stress_ratio([("1.5(DL+LL)", 5000.0, 0, 0)], 300.0, 450.0, 25.0) == 0.0


def test_beam_end_zone_spacing_uses_6_bar_diameters(smrf3):   # J9: 6.3.5(b) (Amd 1)
    import re
    for r in smrf3.gm.beam_schedule.values():
        m = re.search(r"\(ends \d+ mm: @ (\d+) c/c\)", r.stirrups_desc)
        if not m:
            continue
        dias = [int(x) for x in re.findall(r"-(\d+)#", r.bottom_bars_desc + " " + r.top_bars_desc)]
        assert int(m.group(1)) <= 6 * min(dias) + 1e-9
