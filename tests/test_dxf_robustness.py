"""
DXF and IFC input as users send it: every sample drawing through a full design and the invariant checker, the same
plan drawn in every convention giving the same design, damaged files giving input errors (never crashes), and the
IFC export read back into the same structure.
"""
import glob
import logging
import os
import random
from pathlib import Path

import ezdxf
import pytest

from src.cad_loader import CADLoader
from src.design_pipeline import DesignInputs, run_design
from tests.dxf_conventions import make_plan
from tests.invariants import design_violations

logging.disable(logging.CRITICAL)
ROOT = Path(__file__).resolve().parent.parent
SAMPLES = sorted(glob.glob(str(ROOT / "samples" / "**" / "*.dxf"), recursive=True))
INPUT_ERRORS = (ValueError,)        # what the Setup page shows as a fixable input problem


def _design(path, n=2, h=3.2, zone="II", **kw):
    loader = CADLoader(str(path), **kw)
    gm, beams = loader.load_grid_manager(num_stories=n, story_height_m=h)
    gm.columns = gm.stack_columns([c for c in gm.columns if c.level == 0], n, h)
    inp = DesignInputs(num_stories=n, story_height_m=h, seismic_zone=zone, sbc_kn_m2=150.0, max_iterations=4)
    return run_design(gm, beams, inp), inp


@pytest.mark.parametrize("path", SAMPLES, ids=[os.path.relpath(p, ROOT / "samples") for p in SAMPLES])
def test_every_sample_drawing(path):
    try:
        res, inp = _design(path)
    except INPUT_ERRORS:
        return                                            # empty / structure-less drawings: clear input error
    bad = design_violations(res, inp)
    assert not bad, "\n".join(bad[:20])


def _summary(res):
    cols = sorted((round(c.x, 3), round(c.y, 3), c.width_nb, c.depth_nb) for c in res.gm.columns if c.level == 0)
    return {"cols": cols, "beams": len(res.beams), "W": round(res.building_weight, 3),
            "VB": round(res.seismic_result.base_shear_kn, 3), "steel": round(res.bom.total_steel_weight_kg, 1),
            "status": res.status}


@pytest.fixture(scope="module")
def reference(tmp_path_factory):
    return _summary(_design(make_plan(tmp_path_factory.mktemp("ref") / "ref.dxf"))[0])


@pytest.mark.parametrize("variant", [
    dict(units="cm"), dict(units="m"), dict(units="none"), dict(offset=(512345.0, 2034567.0)),
    dict(columns="block"), dict(columns="block_rotated"), dict(columns="polyline"), dict(nest=True),
    dict(dxfversion="R12"), dict(layers="indian"), dict(layers="ncs_long"), dict(beam_style="to_face"),
    dict(beam_style="lwpoly"), dict(duplicate_columns=True), dict(jitter=0.04),
    dict(layer_names={"col": "Layer 7", "beam": "Layer 8", "wall": "Layer 2"}),
    dict(layer_names={k: "0" for k in ("col", "beam", "wall", "grid", "grid_iden", "col_iden", "dims", "door",
                                       "hatch")}),
], ids=lambda v: "-".join(f"{k}={v[k]}" for k in v)[:60])
def test_same_plan_in_any_convention_gives_the_same_design(tmp_path, reference, variant):
    res, _ = _design(make_plan(tmp_path / "v.dxf", **variant))
    got = _summary(res)
    if variant.get("jitter") or variant.get("layer_names", {}).get("wall") == "0":
        # jitter: grid lines are the mean of the drawn column positions (within the 150 mm clustering), so the design
        # is the same up to a few millimetres; everything on layer 0: a door leaf drawn along a wall face is read as
        # a short wall (documented limitation) - same members, weights within 0.5 %
        assert [c[2:] for c in got["cols"]] == [c[2:] for c in reference["cols"]]
        assert got["beams"] == reference["beams"] and got["status"] == reference["status"]
        for k in ("W", "VB", "steel"):
            assert got[k] == pytest.approx(reference[k], rel=0.005), k
        return
    assert got == reference


# ---- damaged files -------------------------------------------------------------------------------------------
def _mutations(src: Path, out: Path, rnd: random.Random):
    data = src.read_bytes()
    yield "truncated", data[: len(data) // 3]
    b = bytearray(data)
    for _ in range(40):
        b[rnd.randrange(len(b))] = rnd.randrange(32, 127)
    yield "corrupted bytes", bytes(b)
    yield "empty", b""
    yield "not a dxf", b"%PDF-1.7\n" + data[:500]
    doc = ezdxf.readfile(src)
    msp = doc.modelspace()
    ents = list(msp)
    for e in rnd.sample(ents, len(ents) // 2):
        msp.delete_entity(e)
    p = out / "half.dxf"
    doc.saveas(p)
    yield "half the entities deleted", p.read_bytes()
    doc = ezdxf.readfile(src)
    for e in doc.modelspace():
        if e.dxftype() == "LINE":
            e.dxf.start = (e.dxf.start.x * 1e7, e.dxf.start.y * 1e7)
    p = out / "huge.dxf"
    doc.saveas(p)
    yield "huge coordinates", p.read_bytes()
    doc = ezdxf.readfile(src)
    for e in doc.modelspace():
        if e.dxftype() == "LINE":
            e.dxf.end = e.dxf.start
    p = out / "zero.dxf"
    doc.saveas(p)
    yield "zero-length lines", p.read_bytes()
    doc = ezdxf.readfile(src)
    for e in doc.modelspace():
        e.dxf.layer = "".join(rnd.choice("ABCXYZ019-_ ") for _ in range(8)).strip() or "L"
    p = out / "renamed.dxf"
    doc.saveas(p)
    yield "random layer names", p.read_bytes()


FUZZ_SOURCES = [ROOT / "samples" / "plans" / "complex_house.dxf", ROOT / "samples" / "sample_design.dxf",
                ROOT / "samples" / "real_world" / "real_3_l_shape_farmhouse.dxf"]


@pytest.mark.parametrize("src", FUZZ_SOURCES, ids=[p.name for p in FUZZ_SOURCES])
def test_damaged_drawings_give_input_errors_not_crashes(tmp_path, src):
    from src.ui_state import read_dxf
    rnd = random.Random(7)
    for name, data in _mutations(src, tmp_path, rnd):
        try:
            out = read_dxf(data, None)                    # the Setup page preview path
        except INPUT_ERRORS:
            continue
        except Exception as e:                            # noqa: BLE001 - anything else is a crash on the page
            pytest.fail(f"{name}: preview crashed with {type(e).__name__}: {e}")
        if out["error"]:
            continue
        p = tmp_path / "m.dxf"
        p.write_bytes(data)
        try:
            res, inp = _design(p)
        except INPUT_ERRORS:
            continue
        except Exception as e:                            # noqa: BLE001
            pytest.fail(f"{name}: design crashed with {type(e).__name__}: {e}")
        bad = design_violations(res, inp)
        assert not bad, f"{name}: " + "; ".join(bad[:5])


# ---- IFC round trip ------------------------------------------------------------------------------------------
def test_ifc_export_reads_back_the_same_structure(tmp_path):
    pytest.importorskip("ifcopenshell")
    from src.bim_loader import BIMLoader
    from src.ifc_exporter import export_ifc
    res, _ = _design(make_plan(tmp_path / "p.dxf"))
    p = tmp_path / "m.ifc"
    p.write_bytes(export_ifc(res.gm, res.all_beams, res.footings))
    gm2, beams2 = BIMLoader(str(p)).load_grid_manager()
    base = lambda g: sorted((round(c.x, 2), round(c.y, 2), round(c.width_nb), round(c.depth_nb))
                            for c in g.columns if c.level == 0)
    assert base(gm2) == base(res.gm)
    assert gm2.num_stories == res.gm.num_stories
    assert len(beams2) == len(res.beams)              # plan beams (the IFC holds one copy per floor)
