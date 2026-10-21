"""
The invariant checker (tests/invariants.py) must itself be trusted: a clean design passes every rule, and each kind
of injected fault is caught by its rule. Without this, a checker that silently checks nothing would look like a
perfect app.
"""
import copy
import logging
import math

import pytest

from src.design_pipeline import DesignInputs, run_design
from src.grid_manager import GridManager
from tests.invariants import design_violations

logging.disable(logging.CRITICAL)


@pytest.fixture(scope="module")
def clean():
    gm = GridManager(width_m=12.0, length_m=9.0, num_stories=3, story_height_m=3.0)
    gm.generate_grid()
    inp = DesignInputs(num_stories=3, story_height_m=3.0, seismic_zone="III", structural_system="SMRF",
                       sbc_kn_m2=200.0)
    return run_design(gm, gm.generate_beams(), inp), inp


def test_clean_design_passes(clean):
    res, inp = clean
    assert design_violations(res, inp) == []


def _rules(res, inp):
    return {x.split(":")[0] for x in design_violations(res, inp)}


FAULTS = {
    "G2": lambda r: setattr(r, "status", "PASS" if r.status != "PASS" else "FAIL"),
    "G3": lambda r: r.failures.append({"Member": "B1", "Type": "Beam", "Status": r.status, "Issue": "ratio nan"}),
    "G4": lambda r: setattr(r.gm.columns[0], "load_kn", float("nan")),
    "S2": lambda r: setattr(r.seismic_result, "base_shear_kn", r.seismic_result.base_shear_kn * 1.1),
    "S3": lambda r: r.seismic_result.storey_forces_kn.__setitem__(0, r.seismic_result.storey_forces_kn[0] + 5.0),
    "C2": lambda r: setattr(r.gm.columns[0], "width_nb", 230.0),
    "C5": lambda r: setattr(r.gm.rebar_schedule[r.gm.columns[0].id], "interaction_ratio", 1.3),
    "C7": lambda r: setattr(r.gm.columns[-1], "depth_nb", r.gm.columns[-1].depth_nb + 50.0),
    "B2": lambda r: setattr(next(iter(r.gm.beam_schedule.values())), "ast_top_prov_mm2", 1.0),
    "B4": lambda r: setattr(next(iter(r.gm.beam_schedule.values())), "stirrups_desc", "2L-8# @ 350 c/c"),
    "F1": lambda r: r.footings.pop(0),
    "F3": lambda r: (setattr(r.footings[0], "bearing_pressure_kn_m2", 999.0), setattr(r.footings[0], "status", "PASS")),
    "D1": lambda r: setattr(r.gm, "beam_cover_mm", 20.0),
    "Q1": lambda r: setattr(r.bom, "total_steel_weight_kg", 0.0),
}


@pytest.mark.parametrize("rule", sorted(FAULTS))
def test_each_injected_fault_is_caught(clean, rule):
    res, inp = clean
    bad = copy.deepcopy(res)
    FAULTS[rule](bad)
    assert rule in _rules(bad, inp), f"{rule} not detected"


def test_hidden_column_failure_is_caught(clean):
    res, inp = clean
    bad = copy.deepcopy(res)
    cid = bad.gm.columns[0].id
    bad.gm.rebar_schedule[cid].status = "FAIL"
    assert "C8" in _rules(bad, inp)


def test_omrf_in_zone_iii_must_fail(clean):
    res, inp = clean
    bad = copy.deepcopy(res)
    inp2 = copy.copy(inp)
    inp2.structural_system = "OMRF"
    bad.failures = [f for f in bad.failures if f["Type"] != "Structural system"]
    bad.seismic_result.base_shear_kn *= 5 / 3          # keep S2 consistent with R = 3
    bad.seismic_result.storey_forces_kn = [f * 5 / 3 for f in bad.seismic_result.storey_forces_kn]
    assert "S5" in _rules(bad, inp2)
    assert math.isfinite(bad.building_weight)
