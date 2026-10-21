"""
The DXF corpus (tests/dxf_corpus.py) through the Setup page preview and the design, the same building drawn in
equivalent ways giving the same design, and every output surviving a column that is beyond its capacity.

Found by this corpus on 2026-10-21 (all fixed, see docs/assurance/risk-register.md N53-N60): columns of mirrored
blocks read mirrored about the origin; 2D POLYLINE walls crashed the loader; units of R12 / unitless drawings and
of drawings with survey coordinates guessed wrongly (no columns found); circular columns on layer 0 dropped and grid
bubbles read as columns; rotated plans read as a cloud of grid lines; one or two columns crashed the dynamic analysis;
warnings repeated; IFC export, 3D viewer and drawings broken by a column beyond capacity.

Random buildings: STRUCTOPTIMA_CORPUS_N (default 30; the nightly CI job runs 300). A failing seed reproduces with
    STRUCTOPTIMA_CORPUS_SEED=<seed> pytest tests/test_dxf_corpus.py -k random
"""
import io
import json
import logging
import math
import os
import random
import re

import pytest

from src.cad_loader import CADLoader
from src.design_pipeline import DesignInputs, run_design
from src.ui_state import read_dxf
from tests.dxf_corpus import CASES, make, random_spec
from tests.invariants import design_violations

logging.disable(logging.CRITICAL)

N_RANDOM = int(os.environ.get("STRUCTOPTIMA_CORPUS_N", "30"))
SEEDS = [int(os.environ["STRUCTOPTIMA_CORPUS_SEED"])] if "STRUCTOPTIMA_CORPUS_SEED" in os.environ else \
    list(range(N_RANDOM))
# not frame buildings with a slab (D-33): a clear input error is the right result
NO_STRUCTURE = {"single-column", "two-columns", "three-columns-L", "one-row"}


def _design(path, n=2, zone="III", system="SMRF"):
    loader = CADLoader(str(path))
    gm, beams = loader.load_grid_manager(num_stories=n, story_height_m=3.2)
    gm.columns = gm.stack_columns([c for c in gm.columns if c.level == 0], n, 3.2)
    inp = DesignInputs(num_stories=n, story_height_m=3.2, seismic_zone=zone, structural_system=system,
                       sbc_kn_m2=150.0, max_iterations=4)
    return run_design(gm, beams, inp), inp, loader


def _check(tmp_path, name, spec, n=2, zone="III"):
    p = make(tmp_path / f"{name}.dxf", spec)
    with open(p, "rb") as fh:
        preview = read_dxf(fh.read(), None)                  # the Setup page path: never raises
    if preview["error"]:
        return "input error", preview
    try:
        res, inp, _ = _design(p, n=n, zone=zone)
    except ValueError as e:                                   # InvalidStructureError (D-33) and other input errors
        return "input error", {"error": str(e), "columns": preview["columns"]}
    bad = design_violations(res, inp)
    assert not bad, f"{name}: " + "; ".join(bad[:8])
    return "designed", preview


def _circle_limit(spec) -> bool:
    """D-36 limit: a circular column on a layer without a column name needs two members framing into it."""
    return spec.get("columns") in ("circle", "mixed") and spec.get("layers") in ("zero", "random") and \
        spec.get("beams") in ("missing_some", "none")


@pytest.mark.parametrize("name", sorted(CASES))
def test_corpus_case(tmp_path, name):
    spec = dict(CASES[name])
    outcome, preview = _check(tmp_path, name, spec)
    if name in NO_STRUCTURE:
        assert outcome == "input error"
        assert re.search(r"one line|No floor slab panel", preview["error"]), preview["error"]
        return
    assert outcome == "designed", preview.get("error")
    if spec["n_columns"] is not None:                         # walls-only drawings: columns are placed by the app
        assert len(preview["columns"]) == spec["n_columns"]
    warns = preview["warnings"]
    assert len(warns) == len(set(warns)), "repeated warnings"


@pytest.mark.parametrize("seed", SEEDS)
def test_random_building(tmp_path, seed):
    spec = random_spec(seed)
    r = random.Random(seed)
    outcome, preview = _check(tmp_path, f"rand{seed}", spec, n=r.choice([1, 2, 3, 5]),
                              zone=r.choice(["II", "III", "IV", "V"]))
    if outcome == "input error":
        # only drawings that genuinely hold no slab panel may be refused
        assert re.search(r"one line|No floor slab panel", preview["error"]), f"seed {seed}: {preview['error']}"
        assert spec["shape"] in ("rect", "L", "T", "U", "courtyard", "cross", "irregular")
        assert min(spec["nx"], spec["ny"]) <= 1 or _circle_limit(spec), f"seed {seed}: {preview['error']}"
        return
    if spec["n_columns"] is not None:
        if _circle_limit(spec):
            assert len(preview["columns"]) <= spec["n_columns"]
        else:
            assert len(preview["columns"]) == spec["n_columns"], f"seed {seed}"



# ---- the same building drawn in equivalent ways gives the same design ---------------------------------------
BASE = dict(nx=3, ny=2, bays=[4.0, 5.0], seed=1)


def _summary(res):
    return {"columns": len([c for c in res.gm.columns if c.level == 0]), "beams": len(res.beams),
            "sizes": sorted((round(c.width_nb), round(c.depth_nb)) for c in res.gm.columns if c.level == 0),
            "W": res.building_weight, "VB": res.seismic_result.base_shear_kn, "status": res.status}


@pytest.fixture(scope="module")
def reference(tmp_path_factory):
    p = make(tmp_path_factory.mktemp("ref") / "ref.dxf", dict(BASE))
    return _summary(_design(p)[0])


@pytest.mark.parametrize("variant", [
    dict(rotate=30.0), dict(rotate=0.5), dict(rotate=-17.0, units="m"), dict(mirror=True),
    dict(units="in", version="R12"), dict(units="ft", version="R12"), dict(units="cm", version="R12"),
    dict(units="m", version="R12", offset=(512345.678, 2034567.891)), dict(units="none", offset=(250.0, -80.0)),
    dict(columns="block_mirrored"), dict(columns="block_scaled", units="in"), dict(columns="block_nested"),
    dict(nest=True, columns="block", rotate=30.0), dict(layers="zero"), dict(layers="random"),
    dict(duplicate_columns=True, version="R12", units="cm"), dict(xlines=True, title_far=True, paperspace=True),
], ids=lambda v: "-".join(f"{k}={v[k]}" for k in v)[:70])
def test_equivalent_drawings_give_the_same_design(tmp_path, reference, variant):
    res, _, loader = _design(make(tmp_path / "v.dxf", dict(BASE, **variant)))
    got = _summary(res)
    for k in ("columns", "beams", "sizes", "status"):
        assert got[k] == reference[k], k
    assert got["W"] == pytest.approx(reference["W"], rel=1e-6)
    assert got["VB"] == pytest.approx(reference["VB"], rel=1e-6)
    if variant.get("rotate") and abs(variant["rotate"]) >= 0.05:
        assert any("rotated by" in w for w in loader.load_warnings)


# ---- outputs with a column beyond its capacity (D-38) -------------------------------------------------------
@pytest.fixture(scope="module")
def beyond_capacity():
    from src.grid_manager import GridManager
    gm = GridManager(width_m=9.0, length_m=8.0, num_stories=2, story_height_m=3.0)
    gm.generate_grid()
    inp = DesignInputs(num_stories=2, story_height_m=3.0, seismic_zone="III", structural_system="SMRF",
                       sbc_kn_m2=150.0)
    res = run_design(gm, gm.generate_beams(), inp)
    r = res.gm.rebar_schedule[sorted(res.gm.rebar_schedule)[0]]
    r.interaction_ratio, r.status = math.inf, "FAIL"
    r.warnings.append("Factored axial load 9999 kN is outside the interaction diagram of the section (Puz = 2000 kN)")
    return res, inp


BAD = re.compile(r"\b(nan|inf|Infinity|NaN)\b")


def test_invariants_accept_only_a_reported_beyond_capacity_ratio(beyond_capacity):
    res, inp = beyond_capacity
    assert not [v for v in design_violations(res, inp) if v.startswith("G4")]
    r = res.gm.rebar_schedule[sorted(res.gm.rebar_schedule)[0]]
    saved = list(r.warnings)
    r.warnings[:] = [w for w in r.warnings if "outside the interaction diagram" not in w]
    try:
        assert any(v.startswith("G4") for v in design_violations(res, inp))
    finally:
        r.warnings[:] = saved


def test_viewer_json_is_valid_in_a_browser(beyond_capacity):
    from src.viewer_model import build_scene, viewer_html
    res, _ = beyond_capacity
    scene = build_scene(res.gm, res.beams, res.footings)
    text = json.dumps(scene)

    def reject(c):
        raise ValueError(f"{c} is not valid JSON")
    json.loads(text, parse_constant=reject)
    assert "beyond capacity" in text
    viewer_html(scene)


def test_ifc_export_with_a_column_beyond_capacity(beyond_capacity):
    pytest.importorskip("ifcopenshell")
    from src.ifc_exporter import export_ifc
    res, _ = beyond_capacity
    data = export_ifc(res.gm, res.beams, res.footings, "T").decode("utf-8", "replace")
    assert "beyond capacity" in data


def test_tables_and_drawings_show_text_not_inf(beyond_capacity):
    from src import ui_tables as t
    from src.drawings import build_drawing_set, compute_marks
    res, _ = beyond_capacity
    marks = compute_marks(res.gm, res.beams, res.footings)
    rows = t.column_rows(res.gm, marks)
    assert any(r["P-M ratio"] == "beyond capacity (Pu outside the interaction diagram)" for r in rows)
    assert not BAD.search(json.dumps(rows, default=str))
    sheets = build_drawing_set(res.gm, res.beams, res.footings, {"name": "T", "engineer": "E", "ref": "R"})
    assert not BAD.search(" ".join(s.drawing.to_svg() for s in sheets))


def test_reports_with_a_column_beyond_capacity(beyond_capacity, tmp_path):
    import openpyxl
    from src.exporters import ExcelExporter
    from src.report_gen import ReportGenerator
    res, _ = beyond_capacity
    ReportGenerator().generate_report(
        str(tmp_path / "r.pdf"), res.gm, res.bom, audit_results=res.audit_results, math_breakdown=res.auditor_math,
        seismic_result=res.seismic_result, wind_result=res.wind_result, stab_checks=res.stab_checks,
        stab_summary=res.stab_summary, all_beams=res.all_beams, building_weight=res.building_weight,
        footings=res.footings, design_status=res.status, design_failures=res.failures, design_messages=res.messages)
    ReportGenerator().generate_schedule_report(str(tmp_path / "s.pdf"), res.gm, footings=res.footings)
    wb = openpyxl.load_workbook(io.BytesIO(ExcelExporter.export_to_excel(res.gm, res.all_beams, res.bom, res.footings)))
    cells = " ".join(str(c.value) for ws in wb for row in ws.iter_rows() for c in row if isinstance(c.value, str))
    assert not BAD.search(cells)


# ---- drafting habits found in real drawings ---------------------------------------------------------------------
from tests.dxf_corpus import HARD, make_hard  # noqa: E402


@pytest.mark.parametrize("name", sorted(HARD))
def test_drafting_habit(tmp_path, name):
    """N61 (MINSERT), N62 (beam lines through columns), D-39 (columns as lines), D-40 (frozen / off layers), D-41
    (overlapping outlines), curved beams, NaN coordinates: each read as the drawing shows it, or refused clearly."""
    expected = HARD[name][1]
    p = make_hard(tmp_path / f"{name}.dxf", name)
    with open(p, "rb") as fh:
        preview = read_dxf(fh.read(), None)
    if expected[0] == "input error":
        assert preview["error"] and expected[1] in preview["error"]
        return
    assert preview["error"] is None, preview["error"]
    assert (len(preview["columns"]), len(preview["beams"])) == expected[1:3]
    if expected[3]:
        assert any(expected[3] in w for w in preview["warnings"]), preview["warnings"]
    res, inp, _ = _design(p)
    assert not design_violations(res, inp)
    spans = sorted(round(b.length_m(), 3) if hasattr(b, "length_m") else
                   round(math.hypot(b.end_point.x - b.start_point.x, b.end_point.y - b.start_point.y), 3)
                   for b in res.beams)
    assert max(spans) <= 4.5 + 1e-6                     # no beam spans more than one bay of the drawn grid
