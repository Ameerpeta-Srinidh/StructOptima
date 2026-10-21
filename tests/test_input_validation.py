"""
Design inputs outside the supported domain (D-42) are one clear input error before any calculation, whatever the
caller (Setup page, CLI, API). Found 2026-10-21 by passing each bad value to run_design: negative storeys, fy = 0, an
unknown soil and max_iterations = 0 crashed (TypeError, ZeroDivisionError, KeyError, UnboundLocalError); SBC <= 0,
a 50 m storey, M99 concrete and 150 % openings were designed; NaN values failed deep in the design with messages such
as "cannot convert float NaN to integer".
"""
import logging
import math

import pytest

from src.design_pipeline import DesignInputs, InvalidInputError, run_design
from src.grid_manager import GridManager

logging.disable(logging.CRITICAL)
nan, inf = math.nan, math.inf

BAD = [("num_stories", 0), ("num_stories", -2), ("num_stories", 2.5), ("num_stories", 51),
       ("story_height_m", 0.0), ("story_height_m", -3.0), ("story_height_m", nan), ("story_height_m", inf),
       ("story_height_m", 50.0), ("sbc_kn_m2", 0.0), ("sbc_kn_m2", -50.0), ("sbc_kn_m2", nan),
       ("wall_load_kn_m", nan), ("wall_load_kn_m", -5.0), ("conc_grade", "M99"), ("conc_grade", "X"),
       ("fy", 0.0), ("fy", 250.0), ("fy", nan), ("seismic_zone", "VI"), ("soil_type", "IV"),
       ("structural_system", "XYZ"), ("importance_factor", 0.0), ("importance_factor", nan),
       ("wall_opening_fraction", 1.5), ("wall_opening_fraction", -0.1), ("max_iterations", 0), ("le_factor", 0.0),
       ("le_factor", nan), ("mortar_ratio", 0), ("wall_core_thickness_mm", 0.0), ("wind_opening_percentage", nan),
       ("num_stories", True)]


def _model():
    gm = GridManager(width_m=9.0, length_m=8.0, num_stories=2, story_height_m=3.0)
    gm.generate_grid()
    return gm, gm.generate_beams()


@pytest.mark.parametrize("field, value", BAD, ids=[f"{f}={v!r}" for f, v in BAD])
def test_bad_input_is_one_clear_error_before_any_calculation(field, value):
    gm, beams = _model()
    inp = DesignInputs(**dict(dict(num_stories=2, story_height_m=3.0, sbc_kn_m2=150.0), **{field: value}))
    with pytest.raises(InvalidInputError, match=rf"{field} = "):
        run_design(gm, beams, inp)
    assert all(c.load_kn == 0.0 for c in gm.columns)          # nothing was calculated


@pytest.mark.parametrize("field, lo, hi", [("num_stories", 1, 50), ("story_height_m", 2.4, 6.0),
                                           ("sbc_kn_m2", 50.0, 1000.0), ("wall_load_kn_m", 0.0, 50.0),
                                           ("wall_opening_fraction", 0.0, 0.5), ("importance_factor", 1.0, 1.5),
                                           ("le_factor", 0.5, 3.0), ("max_iterations", 1, 20)])
def test_range_ends_are_accepted(field, lo, hi):
    for v in (lo, hi):
        DesignInputs(**{field: v}).validate()


@pytest.mark.parametrize("grade", ["M20", "M25", "M30", "M35", "M40"])
def test_supported_grades(grade):
    DesignInputs(conc_grade=grade, fy=500.0).validate()


def test_several_problems_are_listed_together():
    with pytest.raises(InvalidInputError) as e:
        DesignInputs(num_stories=0, sbc_kn_m2=-1.0, soil_type="IV").validate()
    msg = str(e.value)
    assert "num_stories" in msg and "sbc_kn_m2" in msg and "soil_type" in msg


def test_cli_reports_an_input_problem_with_exit_code_2(tmp_path, monkeypatch):
    import main
    monkeypatch.chdir(tmp_path)
    assert main.main(["--stories", "0", "--report", str(tmp_path / "r.pdf")]) == 2
    assert not (tmp_path / "r.pdf").exists()
