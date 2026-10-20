"""
Exposure covers and grades (IS 456 Tables 3, 5, 16, 16A, Fig. 1, 26.4.2) and fire ratings by type of construction
(NBC 2016 Part 4 Table 1), checked against the printed standards on 2026-10-20.
"""
import logging

import pytest

from src.design_pipeline import DesignInputs, run_design
from src.durability import (FIG1_MIN, NBC_TABLE1, TABLE16_COVER, TABLE16A, TABLE5_RCC, fire_min_dimensions, hours,
                            requirements)
from src.grid_manager import GridManager
from src.stability import FIRE_RESISTANCE_TABLE, FireRating

logging.disable(logging.CRITICAL)


def test_printed_tables():
    assert TABLE16_COVER == {"Mild": 20, "Moderate": 30, "Severe": 45, "Very severe": 50, "Extreme": 75}
    assert {k: v[2] for k, v in TABLE5_RCC.items()} == {"Mild": 20, "Moderate": 25, "Severe": 30, "Very severe": 35,
                                                         "Extreme": 40}
    assert TABLE16A[2.0] == (40, 30, 35, 25, 40) and TABLE16A[4.0] == (70, 50, 55, 45, 40)
    assert all(v[4] == 40 for v in TABLE16A.values())          # columns 40 mm for every period
    assert FIG1_MIN[1.5][2] == 250 and FIG1_MIN[2.0][2] == 300 and FIG1_MIN[4.0][2] == 450
    assert NBC_TABLE1["supporting_more_than_one_floor"] == {1: 240, 2: 120, 3: 120, 4: 120}
    assert NBC_TABLE1["floor"] == {1: 120, 2: 90, 3: 60, 4: 60}


@pytest.mark.parametrize("minutes,h", [(30, 0.5), (60, 1.0), (90, 1.5), (120, 2.0), (180, 3.0), (240, 4.0)])
def test_minutes_to_table_row(minutes, h):
    assert hours(minutes) == h


@pytest.mark.parametrize("exposure,ctype,beam,slab,col,foot", [
    ("Mild", 2, 20, 25, 40, 50),        # beams 1.5 h continuous 20; slabs 1.5 h simply supported 25
    ("Moderate", 2, 30, 30, 40, 50),
    ("Moderate", 1, 40, 35, 40, 50),    # type 1: beams 3 h continuous 40, floors 2 h simply supported 35
    ("Severe", 2, 45, 45, 45, 50),
    ("Extreme", 4, 75, 75, 75, 75),
])
def test_required_covers(exposure, ctype, beam, slab, col, foot):
    r = requirements(exposure, ctype)
    assert (r.beam_cover_mm, r.slab_cover_mm, r.column_cover_mm, r.footing_cover_mm) == (beam, slab, col, foot)


def test_table16_note3_reduction_for_m35_and_above():
    assert requirements("Severe", 4, fck=35).beam_cover_mm == 40
    assert requirements("Severe", 4, fck=30).beam_cover_mm == 45


def test_fire_table_built_from_fig1_and_table16a():
    fr = FIRE_RESISTANCE_TABLE[FireRating.ONE_HALF_HOUR]
    assert fr.min_column_width_mm == 250 and fr.min_cover_column_mm == 40
    assert fire_min_dimensions(2.0)["slab_thickness"] == 125


def _design(**kw):
    gm = GridManager(width_m=12.0, length_m=9.0, num_stories=3, story_height_m=3.2)
    gm.generate_grid()
    return run_design(gm, gm.generate_beams(), DesignInputs(num_stories=3, story_height_m=3.2, seismic_zone="II", **kw))


def test_covers_reach_the_design():
    r = _design(exposure="Severe")
    assert (r.gm.beam_cover_mm, r.gm.slab_cover_mm, r.gm.column_cover_mm, r.gm.footing_cover_mm) == (45, 45, 45, 50)
    assert all(c.actual_cover_mm in (45,) for c in r.stab_checks)


def test_grade_below_exposure_minimum_is_a_failure():
    rows = [f for f in _design(exposure="Moderate", conc_grade="M20").failures if f["Type"] == "Durability"]
    assert rows and rows[0]["Status"] == "FAIL" and "Table 5" in rows[0]["Issue"]
    assert not any(f["Type"] == "Durability" for f in _design(exposure="Mild", conc_grade="M20").failures)


def test_type_1_construction_needs_450_mm_columns():
    # NBC type 1: columns supporting more than one floor 240 min -> 4 h -> 450 mm fully exposed (IS 456 Fig. 1)
    r = _design(nbc_construction_type=1)
    rows = [f for f in r.failures if f["Type"] == "Fire resistance" and "column" in f["Issue"]]
    assert rows and "450mm" in rows[0]["Issue"]
    assert not any(f["Type"] == "Fire resistance" and "column" in f["Issue"] for f in _design().failures)


def test_slabs_are_checked_for_fire():
    r = _design()
    assert any(c.member_type == "slab" for c in r.stab_checks)
