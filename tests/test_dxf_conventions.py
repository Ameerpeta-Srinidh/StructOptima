"""
DXF import against real drafting conventions (tests/dxf_conventions.py generates the drawings).

Every case must give the same structure: 20 columns of 300 (x) x 450 (y) mm on the grid x 0 / 4.5 / 9 / 13.5 / 18 m,
y 0 / 4 / 8 / 12 m, 31 beams joining column centres, 230 mm perimeter walls - and nothing from the annotation
(grid bubbles, tags, leaders, dimensions, doors) may become a structural member.
"""
import logging
import math

import pytest

from src.cad_loader import CADLoader
from tests.dxf_conventions import COL_B, COL_D, N_BEAMS, N_COLUMNS, X, Y, make_plan

logging.disable(logging.CRITICAL)


def load(tmp_path, name="plan.dxf", **kw):
    path = make_plan(tmp_path / name, **kw)
    loader = CADLoader(path)
    gm, beams = loader.load_grid_manager(num_stories=1, story_height_m=3.2)
    return loader, gm, beams


def assert_structure(gm, beams, *, col_size=(COL_B, COL_D), tol=0.002, grid_tol=0.002):
    cols = [c for c in gm.columns if c.level == 0]
    assert len(cols) == N_COLUMNS, [(round(c.x, 3), round(c.y, 3)) for c in cols]
    assert gm.x_grid_lines == pytest.approx(X, abs=grid_tol)
    assert gm.y_grid_lines == pytest.approx(Y, abs=grid_tol)
    for c in cols:
        assert c.width_nb == pytest.approx(col_size[0] * 1000, abs=tol * 1000)
        assert c.depth_nb == pytest.approx(col_size[1] * 1000, abs=tol * 1000)
    assert len(beams) == N_BEAMS
    centres = {(round(c.x, 3), round(c.y, 3)) for c in cols}
    for b in beams:   # every beam end lands on a column centre
        for pt in (b.start_point, b.end_point):
            assert min(math.hypot(pt.x - x, pt.y - y) for x, y in centres) < 1e-6, (b.id, pt)


@pytest.mark.parametrize("layers", ["ncs", "ncs_long", "indian"])
def test_layer_conventions(tmp_path, layers):
    _, gm, beams = load(tmp_path, layers=layers)
    assert_structure(gm, beams)


@pytest.mark.parametrize("units", ["mm", "cm", "m"])
def test_declared_units(tmp_path, units):
    loader, gm, beams = load(tmp_path, units=units)
    assert_structure(gm, beams)
    assert not any("units" in w.lower() for w in loader.load_warnings)


def test_unitless_millimetre_drawing_is_flagged(tmp_path):
    loader, gm, beams = load(tmp_path, units="none")
    assert_structure(gm, beams)
    assert any("$INSUNITS" in w for w in loader.load_warnings)


@pytest.mark.parametrize("columns", ["polyline", "block", "block_rotated"])
def test_column_drawing_styles(tmp_path, columns):
    _, gm, beams = load(tmp_path, columns=columns)
    assert_structure(gm, beams)


def test_r12_drawing(tmp_path):
    _, gm, beams = load(tmp_path, dxfversion="R12")
    assert_structure(gm, beams)


def test_plan_bound_inside_one_block(tmp_path):
    _, gm, beams = load(tmp_path, nest=True)
    assert_structure(gm, beams)


def test_circular_columns_use_the_equivalent_area_square(tmp_path):
    loader, gm, beams = load(tmp_path, columns="circle")
    side = 0.450 * math.sqrt(math.pi) / 2     # same area as a 450 mm circle
    assert_structure(gm, beams, col_size=(side, side))
    assert any("circular" in w.lower() for w in loader.load_warnings)


def test_duplicate_outlines_count_once(tmp_path):
    loader, gm, beams = load(tmp_path, duplicate_columns=True)
    assert_structure(gm, beams)
    assert any("duplicate" in w.lower() for w in loader.load_warnings)


def test_drafting_misalignment_is_clustered_onto_grid_lines(tmp_path):
    loader, gm, beams = load(tmp_path, jitter=0.012)       # +/- 12 mm
    # grid line = mean of its 4 or 5 columns, measured from the first line's mean -> within 2 x 12 mm of the design grid
    assert_structure(gm, beams, grid_tol=0.024)
    assert any("aligned to the grid" in w for w in loader.load_warnings)


def test_survey_coordinates_are_moved_to_the_origin(tmp_path):
    loader, gm, beams = load(tmp_path, offset=(500000.0, 2000000.0), units="m")
    assert_structure(gm, beams)
    assert any("origin" in w.lower() for w in loader.load_warnings)


@pytest.mark.parametrize("beam_style", ["lwpoly", "to_face"])
def test_beam_drawing_styles(tmp_path, beam_style):
    _, gm, beams = load(tmp_path, beam_style=beam_style)
    assert_structure(gm, beams)


def test_look_alike_layers_are_not_columns(tmp_path):
    _, gm, beams = load(tmp_path, extra_column_layers=["COLOR-FILL", "PROTOCOL", "COL-TEXT", "S-COLS-NOTE"])
    assert_structure(gm, beams)


@pytest.mark.parametrize("units", ["mm", "m"])
def test_wall_thickness_in_millimetres(tmp_path, units):
    _, gm, _ = load(tmp_path, units=units)
    assert gm.walls and all(w.thickness_mm == pytest.approx(230.0, abs=1.0) for w in gm.walls)


def test_empty_drawing_gives_a_clear_error(tmp_path):
    import ezdxf
    doc = ezdxf.new()
    doc.modelspace().add_text("JUST A NOTE")
    path = tmp_path / "empty.dxf"
    doc.saveas(path)
    with pytest.raises(ValueError, match="No"):
        CADLoader(str(path)).load_grid_manager()


def test_design_runs_on_a_convention_drawing(tmp_path):
    from src.design_pipeline import DesignInputs, run_design
    path = make_plan(tmp_path / "plan.dxf", layers="ncs", columns="block")
    loader = CADLoader(str(path))
    gm, beams = loader.load_grid_manager(num_stories=3, story_height_m=3.2)
    gm.columns = gm.stack_columns([c for c in gm.columns if c.level == 0], 3, 3.2)
    res = run_design(gm, beams, DesignInputs(num_stories=3, story_height_m=3.2, seismic_zone="II"))
    assert res.analysis_summary.frames_solved == res.analysis_summary.frames_total > 0
    assert len([c for c in res.gm.columns if c.level == 0]) == N_COLUMNS
