"""
Portal frame regression (formerly a print-only script that also wrote a log
file at import time).  Same geometry as before: 6 m x 3 m portal, all members
E = 25 GPa, I = 0.0054 m4, A = 0.18 m2, UDL 20 kN/m on the beam, fixed bases.

Reference: for equal EI of beam and columns in a fixed-base portal, moment
distribution / slope-deflection gives the beam end moment
    M_end = w L^2 / 12 * k
with k depending only on stiffness ratios; here it is checked through statics
(end moment + midspan sagging = wL^2/8) and symmetry, and the column axial
force wL/2.
"""
import pytest

from src.fea_solver import FrameSolver2D


def test_simple_portal_frame():
    solver = FrameSolver2D()
    n0, n1 = solver.add_node(0, 0), solver.add_node(0, 3)
    n2, n3 = solver.add_node(6, 0), solver.add_node(6, 3)
    E, I, A = 25e6, 0.0054, 0.18
    c1 = solver.add_element(n0, n1, E, I, A)
    c2 = solver.add_element(n2, n3, E, I, A)
    b = solver.add_element(n1, n3, E, I, A)
    solver.add_member_load(b, 20.0)
    solver.solve()

    assert solver.status == "SOLVED"
    f = solver.get_member_forces(b)
    assert f["m_end1"] == pytest.approx(f["m_end2"], rel=1e-9)            # symmetry
    assert abs(f["m_end1"]) + f["max_sagging"] == pytest.approx(20 * 36 / 8, rel=1e-6)
    assert solver.get_member_forces(c1)["axial"] == pytest.approx(60.0, rel=1e-6)
    assert solver.get_member_forces(c2)["axial"] == pytest.approx(60.0, rel=1e-6)
    # With finite axial stiffness the beam thrust lets the joints move inward a
    # little, so the end moment is slightly below the inextensible value below.
    assert 45.0 < abs(f["m_end1"]) < 48.0


def test_portal_matches_slope_deflection_when_members_inextensible():
    """Slope-deflection, symmetric portal, no sway, axially rigid members:
    M_end = (wL^2/12) (4EI/h) / (4EI/h + 2EI/L) = 60 x (4/3) / (4/3 + 1/3) = 48 kNm."""
    solver = FrameSolver2D()
    n0, n1 = solver.add_node(0, 0), solver.add_node(0, 3)
    n2, n3 = solver.add_node(6, 0), solver.add_node(6, 3)
    E, I, A = 25e6, 0.0054, 1e4
    solver.add_element(n0, n1, E, I, A)
    solver.add_element(n2, n3, E, I, A)
    b = solver.add_element(n1, n3, E, I, A)
    solver.add_member_load(b, 20.0)
    solver.solve()
    assert abs(solver.get_member_forces(b)["m_end1"]) == pytest.approx(48.0, rel=1e-4)
