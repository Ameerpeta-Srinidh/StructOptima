"""
Tests for the site drawing set (src/drawings).

They check structure and consistency (sheets, marks, schedules, outputs).
Drawing quality itself needs a visual review (docs/development/next-work-plan.md B1).
"""
import io
import logging
import os
import zipfile

import pytest

from src.design_pipeline import DesignInputs, run_design
from src.drawings import build_drawing_set, compute_marks, sheets_to_pdf, sheets_to_zip
from src.drawings.sheet import grid_letter
from src.grid_manager import GridManager

logging.disable(logging.CRITICAL)
PROJECT = {"project": "Test", "engineer": "E", "date": "2026-10-16", "ref": "R1", "status_line": "DESIGN STATUS: WARN"}


def _design(w=18.0, l=12.0, n=2, **kw):
    gm = GridManager(width_m=w, length_m=l, num_stories=n, story_height_m=3.5)
    gm.generate_grid()
    return run_design(gm, gm.generate_beams(), DesignInputs(num_stories=n, **kw))


@pytest.fixture(scope="module")
def res():
    return _design(add_staircase=True)


@pytest.fixture(scope="module")
def sheets(res):
    return build_drawing_set(res.gm, res.beams, res.footings, PROJECT)


def test_grid_letters_skip_i_and_o():
    assert [grid_letter(i) for i in range(10)] == list("ABCDEFGHJK")
    assert grid_letter(23) == "Z" and grid_letter(24) == "AA"


def test_core_sheets_present(sheets):
    numbers = [s.number for s in sheets]
    for n in ("S-01", "S-02", "S-03", "S-04", "S-05", "S-06"):
        assert n in numbers
    assert numbers == sorted(numbers)


def test_every_member_has_a_mark_and_marks_group_identical_members(res):
    m = compute_marks(res.gm, res.beams, res.footings)
    assert set(m.columns) == {c.id for c in res.gm.columns}
    assert set(m.beams) == {b.id for b in res.beams}
    assert set(m.footings) == {f.id for f in res.footings}
    assert set(m.slabs) == set(res.gm.slab_schedule)
    for b in res.beams:                         # same mark => same detailing
        same = [o for o in res.beams if m.beams[o.id] == m.beams[b.id]]
        r0 = res.gm.get_beam_result(b.id)
        for o in same:
            r = res.gm.get_beam_result(o.id)
            assert (r.size_label, r.top_bars_desc, r.bottom_bars_desc, r.stirrups_desc) == \
                   (r0.size_label, r0.top_bars_desc, r0.bottom_bars_desc, r0.stirrups_desc)
    assert sum(i.count for i in m.column_info.values()) == len({(c.x, c.y) for c in res.gm.columns})


def test_schedules_show_every_mark_with_its_status(res, sheets):
    m = compute_marks(res.gm, res.beams, res.footings)
    texts = " ".join(it.text for s in sheets for it in s.drawing.items if it.kind == "text")
    for info in list(m.column_info.values()) + list(m.beam_info.values()) + list(m.footing_info.values()):
        assert info.mark in texts
    s01 = next(s for s in sheets if s.number == "S-01")
    statuses = [it.text for it in s01.drawing.items if it.kind == "text" and it.text in ("PASS", "WARN", "FAIL")]
    assert statuses                               # column schedule carries statuses


def test_every_sheet_has_title_block_and_preliminary_flag(sheets):
    for s in sheets:
        texts = [it.text for it in s.drawing.items if it.kind == "text"]
        assert any("NOT FOR CONSTRUCTION" in t for t in texts)
        assert s.number in texts


def test_void_bay_is_marked_on_beam_layout(res, sheets):
    assert res.gm.void_bays
    s03 = next(s for s in sheets if s.number == "S-03")
    assert any(it.text == "STAIR / VOID" for it in s03.drawing.items if it.kind == "text")


def test_outputs_are_consistent(sheets):
    pdf = sheets_to_pdf(sheets)
    assert pdf[:4] == b"%PDF" and len(pdf) > 10000
    import pypdfium2 as pdfium
    assert len(pdfium.PdfDocument(pdf)) == len(sheets)
    z = zipfile.ZipFile(io.BytesIO(sheets_to_zip(sheets)))
    names = z.namelist()
    for s in sheets:
        assert f"dxf/{s.number}.dxf" in names and f"svg/{s.number}.svg" in names
    s = sheets[0]
    svg = s.drawing.to_svg()
    assert svg.startswith("<svg") and svg.count("<text") == sum(1 for it in s.drawing.items if it.kind == "text")
    import ezdxf
    doc = ezdxf.read(io.StringIO(s.drawing.to_dxf_bytes().decode("utf-8")))
    assert len(doc.modelspace().query("TEXT")) == sum(1 for it in s.drawing.items if it.kind == "text")
    assert {"GRID", "COLUMNS", "TITLE"} <= {l.dxf.name for l in doc.layers}


def test_large_plan_paginates_schedules_and_scales_down():
    r = _design(w=40, l=30, n=3)
    sheets = build_drawing_set(r.gm, r.beams, r.footings, PROJECT)
    s01 = next(s for s in sheets if s.number == "S-01")
    assert s01.scale != "1:100"                   # 40 x 30 m does not fit an A3 plan area at 1:100
    nums = [s.number for s in sheets]
    if len(compute_marks(r.gm, r.beams, r.footings).beam_info) > 40:
        assert any(n.startswith("S-03") and n != "S-03" for n in nums)


def test_drawings_for_ifc_and_cad_inputs(tmp_path):
    from src.cad_loader import CADLoader
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ld = CADLoader(os.path.join(root, "samples", "sample_design.dxf"))
    gm, beams = ld.load_grid_manager(auto_frame=True, story_height_m=3.2, num_stories=2)
    gm.columns = gm.stack_columns([c for c in gm.columns if c.level == 0], 2, 3.2)
    r = run_design(gm, beams, DesignInputs(num_stories=2, story_height_m=3.2, max_iterations=3))
    assert build_drawing_set(r.gm, r.beams, r.footings, PROJECT)
    pytest.importorskip("ifcopenshell")
    from tests.ifc_fixture import build_frame_ifc
    from src.bim_loader import BIMLoader
    p = tmp_path / "f.ifc"
    build_frame_ifc(str(p))
    gm, beams = BIMLoader(str(p)).load_grid_manager()
    r = run_design(gm, beams, DesignInputs(num_stories=gm.num_stories, story_height_m=gm.story_height_m))
    assert build_drawing_set(r.gm, r.beams, r.footings, PROJECT)


def test_building_drawings_writes_no_files(res, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    s = build_drawing_set(res.gm, res.beams, res.footings, PROJECT)
    sheets_to_zip(s)
    assert not list(tmp_path.iterdir())
