"""
Columns 230 mm wide to match 230 mm walls in residential buildings (owner request 2026-10-20, decision D-29).

Code limits, read from the printed standards:
- IS 13920:2016 1.1.1: mandatory in Zones III, IV and V (optional in Zone II); 7.1.1: minimum column dimension
  max(300 mm, 20 db). A frame designed as SMRF (R = 5) relies on IS 13920 detailing, so 300 mm applies there too.
  -> 230 mm only in Zone II with OMRF.
- IS 456 Fig. 1: a column built into a wall line is "50 % exposed": 2 h needs 200 mm along the wall; a free-standing
  ("fully exposed") column needs 300 mm. -> only columns standing in a wall line get the 230 mm side, across the wall.
- IS 456 32.1: a member longer than 4 x its thickness is a wall -> the long side stops at 900 mm (4 x 230 = 920).
"""
import logging

import pytest

from src.design_pipeline import DesignInputs, run_design
from src.grid_manager import GridManager
from src.stability import FireRating, StabilityChecker

logging.disable(logging.CRITICAL)


def _design(zone="II", system="OMRF", occupancy="Residential", match=None, stories=3, w=12.0, l=9.0):
    gm = GridManager(width_m=w, length_m=l, num_stories=stories, story_height_m=3.0)
    gm.generate_grid()
    inp = DesignInputs(num_stories=stories, story_height_m=3.0, seismic_zone=zone, structural_system=system,
                       building_type_name=occupancy, sbc_kn_m2=200.0, column_matches_wall=match)
    return run_design(gm, gm.generate_beams(), inp)


def _on_perimeter(c, gm):
    xs, ys = gm.x_grid_lines, gm.y_grid_lines
    return c.x in (xs[0], xs[-1]) or c.y in (ys[0], ys[-1])


def test_wall_columns_are_230_across_the_wall_in_zone_ii_omrf_residential():
    r = _design()
    gm = r.gm
    cols = [c for c in gm.columns if c.level == 0]
    edge_x = [c for c in cols if c.y in (gm.y_grid_lines[0], gm.y_grid_lines[-1]) and c.x not in
              (gm.x_grid_lines[0], gm.x_grid_lines[-1])]                   # on the front / back walls (along x)
    assert edge_x and all(c.wall_dir == "x" and c.depth_nb == 230 and c.width_nb >= 450 for c in edge_x)
    edge_y = [c for c in cols if c.x in (gm.x_grid_lines[0], gm.x_grid_lines[-1]) and c.y not in
              (gm.y_grid_lines[0], gm.y_grid_lines[-1])]                   # on the side walls (along y)
    assert edge_y and all(c.wall_dir == "y" and c.width_nb == 230 and c.depth_nb >= 450 for c in edge_y)
    # free-standing interior columns (no wall in the model) stay at least 300 x 450
    for c in cols:
        if not _on_perimeter(c, gm):
            assert c.wall_dir is None and min(c.width_nb, c.depth_nb) >= 300
    # every storey of a stack keeps the same size and orientation
    for c in gm.columns:
        base = next(b for b in cols if (b.x, b.y) == (c.x, c.y))
        assert (c.width_nb, c.depth_nb, c.wall_dir) == (base.width_nb, base.depth_nb, base.wall_dir)
    assert any("230 mm" in m for m in r.messages)


def test_long_side_never_exceeds_four_times_the_wall():
    r = _design(stories=4, w=15.0, l=12.0)
    for c in r.gm.columns:
        if c.wall_dir:
            assert min(c.width_nb, c.depth_nb) == 230 and max(c.width_nb, c.depth_nb) <= 900


@pytest.mark.parametrize("zone,system", [("III", "SMRF"), ("IV", "SMRF"), ("II", "SMRF")])
def test_not_applied_where_is13920_requires_300(zone, system):
    r = _design(zone=zone, system=system)
    assert all(min(c.width_nb, c.depth_nb) >= 300 and c.wall_dir is None for c in r.gm.columns)
    assert any("IS 13920" in m and "7.1.1" in m for m in r.messages)


def test_off_for_other_occupancies_unless_selected():
    r = _design(occupancy="Commercial (Office)")
    assert all(c.wall_dir is None for c in r.gm.columns)
    r = _design(occupancy="Commercial (Office)", match=True)
    assert any(c.wall_dir for c in r.gm.columns)
    r = _design(match=False)
    assert all(c.wall_dir is None for c in r.gm.columns)


def test_fire_check_uses_50_percent_exposed_for_wall_columns():
    chk = StabilityChecker(num_floors=3, building_height_m=9.0)
    ok, _, _ = chk.check_fire_resistance_column(230, 450, 40, FireRating.TWO_HOUR, wall_dir="x")
    assert ok                                         # 450 along the wall >= 200 (Fig. 1, 50 % exposed, 2 h)
    ok, _, why = chk.check_fire_resistance_column(230, 450, 40, FireRating.TWO_HOUR)
    assert not ok and "300" in why                    # free-standing: 300 (fully exposed, 2 h)
    ok, _, _ = chk.check_fire_resistance_column(230, 450, 40, FireRating.FOUR_HOUR, wall_dir="x")
    assert not ok                                     # wall along x, but only 230 along it: 4 h needs 350


def test_design_with_wall_columns_has_no_fire_or_beam_width_failure():
    r = _design()
    kinds = {(f["Type"], f["Status"]) for f in r.failures}
    assert not any(t in ("Fire resistance", "Slenderness", "Beam wider than column") for t, _ in kinds), kinds


def test_beam_wider_than_column_is_reported():
    from src.design_pipeline import beams_wider_than_columns
    gm = GridManager(width_m=8.0, length_m=4.0, num_stories=1, story_height_m=3.0)
    gm.generate_grid()
    beams = gm.generate_beams()
    for c in gm.columns:
        c.width_nb, c.depth_nb = 450.0, 230.0          # 230 across x-direction beams
    bx = next(b for b in beams if abs(b.start_point.y - b.end_point.y) < 1e-6)
    bx.properties.width_mm = 300.0
    rows = beams_wider_than_columns(gm, beams)
    assert bx.id in {r[0] for r in rows}


def test_dxf_house_columns_are_balanced_and_beams_fit():
    """samples/plans/complex_house.dxf: walls meet at almost every column, so the long sides must be shared between
    the two directions (otherwise one direction has almost no column stiffness), and every beam framing into a
    230 mm side must be 230 mm wide."""
    from pathlib import Path
    from src.cad_loader import CADLoader
    dxf = Path(__file__).resolve().parent.parent / "samples" / "plans" / "complex_house.dxf"
    gm, beams = CADLoader(str(dxf)).load_grid_manager()
    gm.columns = gm.stack_columns([c for c in gm.columns if c.level == 0], 3, 3.0)
    r = run_design(gm, beams, DesignInputs(num_stories=3, story_height_m=3.0, sbc_kn_m2=150.0, seismic_zone="II"))
    base = [c for c in r.gm.columns if c.level == 0]
    nx = sum(1 for c in base if c.wall_dir == "x")
    ny = sum(1 for c in base if c.wall_dir == "y")
    assert nx + ny == 11 and abs(nx - ny) <= 1
    assert not any(f["Type"] == "Beam wider than column" for f in r.failures)
