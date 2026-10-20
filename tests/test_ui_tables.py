"""
Tests for the schedule and status rows shown in the UI (src/ui_tables.py).

Regression tests for display defects found in the 2026-10-20 UI review:
- N23: the footing schedule read a non-existent attribute ``punching_shear_status`` and always showed
  "OK" for punching shear; its steel column was volume x 80 kg/m3 instead of the designed steel.
- N24: the project header showed the audit re-check count ("111/111 pass", green) while the design
  status was WARN or FAIL.
- N25: the slab schedule had no status column although slab designs carry PASS/WARN/FAIL.
"""
import logging
from types import SimpleNamespace

import pytest

from src.design_pipeline import DesignInputs, run_design
from src.drawings import compute_marks
from src.drawings.marks import Marks
from src.foundation_eng import Footing
from src.grid_manager import GridManager
from src.ui_tables import (BBS_SCOPE, beam_rows, column_rows, design_status_summary, footing_rows, issue_rows,
                           slab_rows)

logging.disable(logging.CRITICAL)


def _footing(**kw):
    base = dict(id="F-C1_L0", length_m=1.5, width_m=1.5, thickness_mm=300.0, area_m2=2.25, concrete_vol_m3=0.675,
                excavation_vol_m3=3.4, sbc_kn_m2=200.0, bearing_pressure_kn_m2=150.0, rebar_desc="10# @ 150 c/c both ways",
                steel_weight_kg=41.3)
    base.update(kw)
    return Footing(**base)


@pytest.fixture(scope="module")
def res():
    gm = GridManager(width_m=18.0, length_m=12.0, num_stories=2, story_height_m=3.5)
    gm.generate_grid()
    return run_design(gm, gm.generate_beams(), DesignInputs(num_stories=2, seismic_zone="III", sbc_kn_m2=200.0))


@pytest.fixture(scope="module")
def marks(res):
    return compute_marks(res.gm, res.beams, list(res.footings))


# ---- N23: footing schedule ---------------------------------------------------------------------------------

def test_footing_punching_failure_is_shown():
    # the attribute the old page read never existed, so it always fell back to "OK"
    assert not hasattr(_footing(), "punching_shear_status")
    row = footing_rows([_footing(status="FAIL", punching_ok=False)], Marks())[0]
    assert row["Punching"] == "FAIL"
    assert row["Status"] == "FAIL"


@pytest.mark.parametrize("field,column", [("bearing_ok", "Bearing"), ("one_way_shear_ok", "One-way shear"),
                                          ("bending_ok", "Bending"), ("punching_ok", "Punching")])
def test_each_footing_check_is_reported(field, column):
    assert footing_rows([_footing(**{field: False}, status="FAIL")], Marks())[0][column] == "FAIL"
    assert footing_rows([_footing()], Marks())[0][column] == "PASS"


def test_footing_steel_is_the_designed_steel():
    row = footing_rows([_footing(steel_weight_kg=41.3)], Marks())[0]
    assert row["Steel (kg)"] == pytest.approx(41.3)
    assert row["Bars"] == "10# @ 150 c/c both ways"


def test_footing_rows_match_design(res, marks):
    rows = footing_rows(res.footings, marks)
    assert len(rows) == len(res.footings)
    for ft, row in zip(res.footings, rows):
        assert row["Footing"] == ft.id
        assert row["Status"] == ft.status
        assert row["Punching"] == ("PASS" if ft.punching_ok else "FAIL")
        assert row["Steel (kg)"] == pytest.approx(ft.steel_weight_kg, abs=0.05)


# ---- N24: one design status everywhere ---------------------------------------------------------------------

def test_status_summary_follows_design_status_not_audit():
    fake = SimpleNamespace(status="WARN", failures=[{"Status": "WARN"}, {"Status": "WARN"}],
                           audit_results=[SimpleNamespace(status="PASS")] * 5)
    s = design_status_summary(fake)
    assert s["status"] == "WARN" and s["n_warn"] == 2 and s["n_fail"] == 0


def test_status_summary_counts(res):
    s = design_status_summary(res)
    assert s["status"] == res.status
    assert s["n_fail"] == sum(1 for f in res.failures if f["Status"] == "FAIL")
    assert s["n_warn"] == sum(1 for f in res.failures if f["Status"] == "WARN")


def test_issue_rows_put_failures_first(res):
    rows = issue_rows(res.failures)
    assert len(rows) == len(res.failures)
    order = [r["Status"] for r in rows]
    assert order == sorted(order, key=lambda s: {"FAIL": 0, "WARN": 1}.get(s, 2))


# ---- schedules show the production design results ------------------------------------------------------------

def test_column_rows_use_column_design(res, marks):
    rows = column_rows(res.gm, marks)
    assert len(rows) == len(res.gm.columns)
    for row in rows:
        r = res.gm.rebar_schedule.get(row["ID"])
        if r is None:
            assert row["Status"] == "NOT DESIGNED"
        else:
            assert row["Status"] == r.status
            assert row["P-M ratio"] == pytest.approx(r.interaction_ratio, abs=0.005)
            assert row["Main bars"] == r.main_bars_desc


def test_beam_rows_use_beam_design(res, marks):
    rows = beam_rows(res.gm, marks)
    assert len(rows) == len(res.gm.beam_schedule)
    for row in rows:
        r = res.gm.beam_schedule[row["Beam"]]
        assert row["Status"] == r.status
        assert row["Span (m)"] == pytest.approx(r.span_m, abs=0.005)


def test_slab_rows_have_status(res, marks):   # N25
    rows = slab_rows(res.gm, marks)
    assert len(rows) == len(res.gm.slab_schedule)
    for row in rows:
        assert row["Status"] == res.gm.slab_schedule[row["Slab"]].status


def test_bbs_scope_is_stated():
    assert "one typical floor" in BBS_SCOPE and "footings" in BBS_SCOPE
