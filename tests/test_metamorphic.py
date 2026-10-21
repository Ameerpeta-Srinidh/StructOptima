"""
Relations between designs that must hold whatever the individual numbers are (metamorphic testing). They catch
defects that no single design reveals - an orientation rule biased to one axis, a load that does not grow with the
zone, hidden state that makes two identical runs differ.
"""
import copy
import logging

import pytest

from src.design_pipeline import run_design
from tests.design_matrix import build
from tests.invariants import design_violations

logging.disable(logging.CRITICAL)

BASE = {"plan": (18.0, 12.0), "storeys": 4, "storey_h": 3.2, "occupancy": "Residential", "zone": "III", "soil": "II",
        "system": "SMRF", "wind_zone": "3", "terrain": "2", "conc": "M25", "fy": 500.0, "exposure": "Moderate",
        "nbc": 2, "cracked": True, "fixed_base": True, "staircase": False, "cantilevers": (), "interior_walls": False,
        "wall_type": "230", "openings": 0.33, "col_match_wall": True, "sbc": 200.0}


def _run(**over):
    case = dict(BASE, **over)
    gm, beams, inp = build(case)
    res = run_design(gm, beams, inp)
    assert not design_violations(res, inp), design_violations(res, inp)[:10]
    return res


def _summary(res):
    return {
        "W": round(res.building_weight, 6),
        "VB": round(res.seismic_result.base_shear_kn, 6),
        "concrete": round(res.bom.total_concrete_vol_m3, 6),
        "steel": round(res.bom.total_steel_weight_kg, 3),
        "status": res.status,
        "issues": sorted((f["Type"], f["Status"]) for f in res.failures),
        "columns": sorted((round(c.x, 3), round(c.y, 3), c.level, c.width_nb, c.depth_nb) for c in res.gm.columns),
        "footings": sorted((f.id, round(f.length_m, 3), f.thickness_mm) for f in res.footings),
    }


def test_same_input_gives_the_same_design():
    assert _summary(_run()) == _summary(_run())


@pytest.mark.xfail(strict=True, reason="N49: columns always start 300 (x) x 450 (y) whatever the plan orientation, "
                                       "so a plan drawn rotated 90 degrees gets a different design; the orientation "
                                       "rule needs an owner decision (D-31 proposed)")
@pytest.mark.parametrize("over", [
    dict(),                                                     # SMRF, Zone III
    dict(zone="II", system="OMRF"),                             # 230 mm wall columns active
    dict(zone="II", system="OMRF", interior_walls=True),
])
def test_rotating_the_plan_changes_nothing(over):
    a = _run(plan=(18.0, 12.0), **over)
    b = _run(plan=(12.0, 18.0), **over)
    assert a.building_weight == pytest.approx(b.building_weight, rel=1e-6)
    assert a.seismic_result.base_shear_kn == pytest.approx(b.seismic_result.base_shear_kn, rel=1e-6)
    assert a.bom.total_concrete_vol_m3 == pytest.approx(b.bom.total_concrete_vol_m3, rel=0.01)
    assert a.bom.total_steel_weight_kg == pytest.approx(b.bom.total_steel_weight_kg, rel=0.03)
    swap = {"X": "Y", "Y": "X"}
    types_a = sorted((f["Type"], f["Status"]) for f in a.failures)
    types_b = sorted((f["Type"], f["Status"]) for f in b.failures)
    assert [t for t in types_a if t[0] != "Torsional irregularity"] == \
           [t for t in types_b if t[0] != "Torsional irregularity"]
    da, db = a.seismic_result.dynamic, b.seismic_result.dynamic
    assert da["X"]["VB design (kN)"] == pytest.approx(db[swap["X"]]["VB design (kN)"], abs=0.11)


@pytest.mark.parametrize("over", [
    dict(),
    dict(zone="II", system="OMRF"),
    dict(zone="II", system="OMRF", interior_walls=True),
    dict(zone="V"),
])
def test_symmetric_plan_is_not_torsionally_irregular(over):
    res = _run(plan=(12.0, 12.0), **over)
    for d in ("X", "Y"):
        assert res.seismic_result.dynamic[d]["Torsion ratio"] <= 1.2 + 1e-6, (d, res.seismic_result.dynamic[d])
    assert not any(f["Type"] == "Torsional irregularity" for f in res.failures)


def test_base_shear_grows_with_zone():
    vb = [_run(zone=z).seismic_result.base_shear_kn for z in ("II", "III", "IV", "V")]
    assert vb == sorted(vb) and len(set(vb)) == 4


def test_base_shear_does_not_fall_on_softer_soil():
    vb = [_run(soil=s, storeys=7).seismic_result.base_shear_kn for s in ("I", "II", "III")]
    assert vb == sorted(vb)


def test_footings_do_not_shrink_on_weaker_soil():
    areas = [sum(f.length_m * f.width_m for f in _run(sbc=s).footings) for s in (300.0, 150.0, 75.0)]
    assert areas == sorted(areas)


def test_more_storeys_load_the_base_column_more():
    def base_load(n):
        res = _run(storeys=n)
        return max(c.load_kn for c in res.gm.columns if c.level == 0)
    loads = [base_load(n) for n in (1, 2, 4)]
    assert loads == sorted(loads) and len(set(loads)) == 3


def test_heavier_occupancy_is_heavier():
    w = [_run(occupancy=o).building_weight for o in ("Residential", "Commercial (Office)", "Assembly Hall")]
    assert w == sorted(w)
