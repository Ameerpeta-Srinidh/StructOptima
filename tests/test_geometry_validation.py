"""
Drawings with geometry no building has (a line 10^11 drawing units long, non-finite coordinates) are input errors
raised before any framing or design, and never exhaust memory; non-finite forces never pass a column check.

Root cause (2026-10-21): the 'huge coordinates' DXF mutation (LINE starts x 1e7) reached the design. Without
column entities the auto-framer put a node every 5 m along each wall (3 x 10^8 nodes for real_3_l_shape_farmhouse,
~12 GiB, OOM-killed); with columns, kilometre-long beams and walls gave W and VB ~ 10^14 kN and Pu > Puz in every
column (interaction ratio inf).
"""
import logging
import math
import subprocess
import sys
from pathlib import Path

import ezdxf
import pytest

from src.cad_loader import CADLoader
from src.design_pipeline import DesignInputs, run_design
from src.framing_logic import MemberProperties, Point, StructuralMember
from src.grid_manager import MAX_PLAN_EXTENT_M, Column, GridManager, check_plan_geometry
from src.materials import Concrete
from src.rebar_detailer import RebarDetailer
from src import section_design as sd
from tests.dxf_conventions import make_plan

logging.disable(logging.CRITICAL)
ROOT = Path(__file__).resolve().parent.parent
FARMHOUSE = ROOT / "samples" / "real_world" / "real_3_l_shape_farmhouse.dxf"   # walls only: auto-frame path


def _stretch_one_line(src, dst, layer_part=None, factor=1e7):
    """Copy of ``src`` with the start of one LINE (on a layer containing ``layer_part``; the start farthest from the
    origin, which a multiplication moves) multiplied by ``factor``."""
    doc = ezdxf.readfile(src)
    line = max((e for e in doc.modelspace() if e.dxftype() == "LINE"
                and (layer_part is None or layer_part in e.dxf.layer)), key=lambda e: abs(e.dxf.start))
    line.dxf.start = (line.dxf.start.x * factor, line.dxf.start.y * factor)
    doc.saveas(dst)
    return dst


def test_far_wall_line_is_rejected_before_auto_framing_within_bounded_memory(tmp_path):
    """Regression for the OOM: run in a child process limited to 1.5 GiB of address space, so a regression fails
    with MemoryError / a non-zero exit instead of exhausting the machine."""
    resource = pytest.importorskip("resource")
    p = _stretch_one_line(FARMHOUSE, tmp_path / "far.dxf")
    code = ("import sys, logging; logging.disable(50); sys.path.insert(0, sys.argv[2])\n"
            "from src.cad_loader import CADLoader\n"
            "try:\n    CADLoader(sys.argv[1]).load_grid_manager(num_stories=2, story_height_m=3.2)\n"
            "except ValueError as e:\n    print('INPUT ERROR:', e); sys.exit(0)\n"
            "print('LOADED'); sys.exit(3)\n")
    lim = 1536 * 1024 ** 2
    r = subprocess.run([sys.executable, "-c", code, str(p), str(ROOT)], capture_output=True, text=True, timeout=120,
                       preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_AS, (lim, lim)))
    assert r.returncode == 0, r.stdout + r.stderr[-2000:]
    assert "1000 m even if the drawing is in millimetres" in r.stdout


def test_unstretched_farmhouse_still_loads():
    gm, _ = CADLoader(str(FARMHOUSE)).load_grid_manager(num_stories=2, story_height_m=3.2)
    assert gm.columns


def test_far_beam_end_with_drawn_columns_is_an_input_error(tmp_path):
    p = _stretch_one_line(make_plan(tmp_path / "plan.dxf"), tmp_path / "far.dxf", layer_part="BEAM")
    with pytest.raises(ValueError, match="1000 m"):
        CADLoader(str(p)).load_grid_manager(num_stories=2, story_height_m=3.2)


def test_survey_offset_far_from_origin_is_not_rejected(tmp_path):
    """Absolute coordinates are not limited, only the extent: a plan drawn at UTM-like coordinates (in metres)."""
    p = make_plan(tmp_path / "utm.dxf", units="m", offset=(512345.0, 2034567.0))
    gm, beams = CADLoader(p).load_grid_manager(num_stories=2, story_height_m=3.2)
    assert max(c.x for c in gm.columns) == pytest.approx(18.0)       # make_plan X grid 0 ... 18 m


# ---- check_plan_geometry (metres): bound = MAX_PLAN_EXTENT_M, the existing $INSUNITS plausibility limit --------
def _gm(xs):
    gm = GridManager(width_m=max(xs), length_m=6.0, num_stories=1, story_height_m=3.0)
    gm.columns = [Column(id=f"C{i}", x=x, y=y, width_nb=300, depth_nb=300) for i, x in enumerate(xs) for y in (0, 6)]
    return gm


def _beam(x1, x2):
    return StructuralMember(id="B1", type="beam", start_point=Point(x=x1, y=0.0), end_point=Point(x=x2, y=0.0),
                            properties=MemberProperties(width_mm=300, depth_mm=600))


def test_plan_up_to_the_bound_is_accepted():
    check_plan_geometry(_gm([0.0, 6.0]), [_beam(0.0, MAX_PLAN_EXTENT_M - 1.0)])


def test_plan_beyond_the_bound_names_the_members():
    with pytest.raises(ValueError, match=r"spans 1,001 m in X \(from the column C0 to the beam B1\)"):
        check_plan_geometry(_gm([0.0, 6.0]), [_beam(0.0, MAX_PLAN_EXTENT_M + 1.0)])


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_non_finite_coordinate_is_an_input_error(bad):
    gm = _gm([0.0, 6.0])
    gm.columns[1].x = bad
    with pytest.raises(ValueError, match="invalid coordinate"):
        check_plan_geometry(gm, [])


def test_run_design_rejects_geometry_before_calculating():
    gm = _gm([0.0, 6.0])
    with pytest.raises(ValueError, match="1000 m"):
        run_design(gm, [_beam(0.0, 5000.0)], DesignInputs(num_stories=1, story_height_m=3.0, sbc_kn_m2=150.0))
    assert all(c.load_kn == 0.0 for c in gm.columns)          # nothing was calculated


# ---- column check: non-finite forces fail loudly; Pu beyond the diagram stays a FAIL with a readable message ---
SEC = sd.column_section(300, 450, 6, 16, 25, 500, 40)


@pytest.mark.parametrize("pu, mx, my", [(math.nan, 10.0, 10.0), (800.0, math.nan, 10.0), (800.0, 10.0, math.inf),
                                        (math.inf, 10.0, 10.0)])
def test_check_column_rejects_non_finite_forces(pu, mx, my):
    """A NaN force used to return ratio -1.0 (governing case ''), i.e. a pass."""
    with pytest.raises(FloatingPointError):
        sd.check_column(SEC, pu, mx, my, 3000.0)


def test_axial_load_beyond_squash_load_fails_with_a_readable_message():
    puz = sd.puz_kn(SEC)
    assert math.isinf(sd.check_column(SEC, 1.5 * puz, 10.0, 10.0, 3000.0).ratio)   # meaning unchanged
    r = RebarDetailer.detail_column(300, 450, 50 * puz, Concrete.from_grade("M25"), fy=500.0)
    assert r.status == "FAIL"
    assert any("outside the interaction diagram" in w for w in r.warnings)
    assert not any("inf" in w.split() for w in r.warnings)


@pytest.mark.parametrize("kw", [dict(mu_sagging_knm=math.nan, mu_hogging_knm=100.0, vu_kn=80.0),
                                dict(mu_sagging_knm=100.0, mu_hogging_knm=math.inf, vu_kn=80.0),
                                dict(mu_sagging_knm=100.0, mu_hogging_knm=100.0, vu_kn=math.nan)])
def test_beam_design_rejects_non_finite_forces(kw):
    """These used to reach math.floor as ValueError / OverflowError: a broken analysis read as an input error."""
    with pytest.raises(FloatingPointError, match="non-finite"):
        RebarDetailer.detail_beam(300, 600, 5.0, fck=25, fy=500, **kw)


def test_only_the_structureless_samples_are_input_errors():
    """test_dxf_robustness.test_every_sample_drawing accepts a ValueError as 'clear input error': without this list a
    regression that made valid samples unreadable would pass there. Checked 2026-10-21: 2 of 92 samples."""
    import glob
    expected = {"test_cases/stress/circles_only.dxf", "test_cases/stress/empty.dxf"}
    errors = set()
    for p in sorted(glob.glob(str(ROOT / "samples" / "**" / "*.dxf"), recursive=True)):
        try:
            CADLoader(p).load_grid_manager(num_stories=2, story_height_m=3.2)
        except ValueError:
            errors.add(str(Path(p).relative_to(ROOT / "samples")))
    assert errors == expected


@pytest.mark.parametrize("field", ["base_shear_kn"])
def test_nan_in_the_seismic_result_never_gives_a_usable_design(monkeypatch, field):
    """Inject a NaN after the static seismic calculation: the run must end in a numerical error or a FAIL status
    carrying the 'Numerical failure' row - never PASS / WARN."""
    import src.seismic as seismic
    real = seismic.run_seismic_check

    def broken(*a, **k):
        r = real(*a, **k)
        setattr(r, field, math.nan)
        return r
    monkeypatch.setattr(seismic, "run_seismic_check", broken)
    gm = GridManager(width_m=9.0, length_m=6.0, num_stories=2, story_height_m=3.0)
    gm.generate_grid()
    inp = DesignInputs(num_stories=2, story_height_m=3.0, seismic_zone="II", sbc_kn_m2=150.0, max_iterations=2)
    try:
        res = run_design(gm, gm.generate_beams(), inp)
    except FloatingPointError:
        return
    assert res.status == "FAIL"
    assert any(f["Type"] == "Numerical failure" for f in res.failures)
