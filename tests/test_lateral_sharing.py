"""
Lateral storey forces shared between parallel 2D frames as for a rigid floor diaphragm (translation): each frame
takes force in proportion to its own lateral stiffness, beams included. Hand references below; finding A1 of the
2026-10-20 review (the previous share by column stiffness ignored the beams).
"""
import logging

import pytest

from src.analysis_integration import LateralLoads, update_structural_analysis
from src.framing_logic import MemberProperties, Point, StructuralMember
from src.grid_manager import Column, GridManager

logging.disable(logging.CRITICAL)


def _model(beam_on_b: bool):
    gm = GridManager(width_m=6.0, length_m=6.0, num_stories=1, story_height_m=3.5)
    gm.x_grid_lines, gm.y_grid_lines = [0.0, 6.0], [0.0, 6.0]
    gm.columns = [Column(id=f"C{i}", x=x, y=y, level=0, z_bottom=0.0, z_top=3.5, width_nb=300, depth_nb=300)
                  for i, (x, y) in enumerate([(0, 0), (6, 0), (0, 6), (6, 6)])]
    gm.dead_load_kn_m2, gm.live_load_kn_m2 = 1.0, 1.0
    stiff = MemberProperties(width_mm=300, depth_mm=3000)          # very stiff beam: columns act fixed-fixed
    beams = [StructuralMember(id="BA", type="beam", start_point=Point(x=0, y=0), end_point=Point(x=6, y=0),
                              properties=stiff)]
    if beam_on_b:
        beams.append(StructuralMember(id="BB", type="beam", start_point=Point(x=0, y=6), end_point=Point(x=6, y=6),
                                      properties=stiff))
    # y-direction beams keep the YZ frames stable; they do not take X load
    beams += [StructuralMember(id=f"BY{x}", type="beam", start_point=Point(x=x, y=0), end_point=Point(x=x, y=6),
                               properties=MemberProperties(width_mm=230, depth_mm=450)) for x in (0, 6)]
    return gm, beams


def test_frame_with_beam_takes_the_stiffness_share():
    gm, beams = _model(beam_on_b=False)
    s = update_structural_analysis(gm, beams, fck=25.0, lateral=LateralLoads(eq_x=[100.0], eq_y=[100.0]))
    a, b = s.lateral_shares["EQX"]["XZ@0.00"][0], s.lateral_shares["EQX"]["XZ@6.00"][0]
    # hand: fixed-fixed columns 12EI/h^3 each vs cantilever columns 3EI/h^3 each -> 12 / (12 + 3) = 0.80
    assert a + b == pytest.approx(100.0)
    assert a == pytest.approx(80.0, abs=2.0)
    assert b == pytest.approx(20.0, abs=2.0)


def test_identical_frames_share_equally():
    gm, beams = _model(beam_on_b=True)
    s = update_structural_analysis(gm, beams, fck=25.0, lateral=LateralLoads(eq_x=[100.0], eq_y=[100.0]))
    a, b = s.lateral_shares["EQX"]["XZ@0.00"][0], s.lateral_shares["EQX"]["XZ@6.00"][0]
    assert a == pytest.approx(50.0, rel=1e-6) and b == pytest.approx(50.0, rel=1e-6)


def test_frames_drift_together():
    # rigid diaphragm: both X frames move by the same amount at the floor -> one storey drift for the level
    gm, beams = _model(beam_on_b=False)
    s = update_structural_analysis(gm, beams, fck=25.0, lateral=LateralLoads(eq_x=[100.0], eq_y=[100.0]))
    drift, h, _ = s.storey_drift["EQX"][0]
    E = 5000 * 25 ** 0.5 * 1000            # kN/m2
    I = 0.3 * 0.3 ** 3 / 12                # m4 (gross: use_cracked_sections False)
    k = 2 * 12 * E * I / 3.5 ** 3 + 2 * 3 * E * I / 3.5 ** 3
    assert drift == pytest.approx(100.0 / k, rel=0.05)
