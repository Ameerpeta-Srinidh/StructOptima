"""
Closed-form benchmarks for FrameSolver2D (audit findings R10, R11, R12, R23).

Reference values are derived from elementary structural mechanics, not from
the implementation:
  * fixed-fixed beam, UDL w:   M_support = wL^2/12 (hogging), M_mid = wL^2/24 (sagging)
  * any span under UDL:        M_hog,avg + M_sag,mid = wL^2/8 (statics)
  * cantilever, tip load P:    M_base = P h, tip deflection = P h^3 / (3 E I)
"""
import math

import pytest

from src.fea_solver import FrameSolver2D

E = 25e6  # kN/m2


def portal(w=10.0, L=6.0, h=3.0, reverse=False, rigid_cols=False, fixed=True):
    s = FrameSolver2D(fixed_base=fixed)
    n0, n1 = s.add_node(0, 0), s.add_node(0, h)
    n2, n3 = s.add_node(L, 0), s.add_node(L, h)
    ic = 1e3 if rigid_cols else 0.3 * 0.45 ** 3 / 12
    c1 = s.add_element(n0, n1, E, ic, 0.135)
    c2 = s.add_element(n2, n3, E, ic, 0.135)
    b = s.add_element(n3, n1, E, 0.3 * 0.6 ** 3 / 12, 0.18) if reverse else s.add_element(n1, n3, E, 0.3 * 0.6 ** 3 / 12, 0.18)
    s.add_member_load(b, w)
    s.solve()
    return s, b, c1, c2


def test_fixed_fixed_beam_moments_match_closed_form():
    s, b, _, _ = portal(rigid_cols=True)
    r = s.get_member_forces(b)
    assert r["max_hogging"] == pytest.approx(10 * 36 / 12, rel=1e-3)
    assert r["max_sagging"] == pytest.approx(10 * 36 / 24, rel=1e-3)
    assert r["max_shear"] == pytest.approx(30.0, rel=1e-6)


def test_portal_span_statics_hog_plus_sag_equals_wl2_over_8():
    s, b, _, _ = portal()
    r = s.get_member_forces(b)
    hog_avg = (abs(r["m_end1"]) + abs(r["m_end2"])) / 2
    assert hog_avg + r["max_sagging"] == pytest.approx(10 * 36 / 8, rel=1e-3)


@pytest.mark.parametrize("rigid", [True, False])
def test_beam_orientation_does_not_change_results(rigid):
    a = portal(rigid_cols=rigid)
    b = portal(rigid_cols=rigid, reverse=True)
    ra, rb = a[0].get_member_forces(a[1]), b[0].get_member_forces(b[1])
    for k in ("max_sagging", "max_hogging", "max_shear"):
        assert ra[k] == pytest.approx(rb[k], rel=1e-9)
    # gravity acts downward in both cases (R12)
    assert a[0].displacements[4] < 0 and b[0].displacements[4] < 0


def test_column_axial_force_equals_half_beam_load():
    s, _, c1, c2 = portal()
    assert s.get_member_forces(c1)["axial"] == pytest.approx(30.0, rel=1e-6)
    assert s.get_member_forces(c2)["axial"] == pytest.approx(30.0, rel=1e-6)


def test_cantilever_tip_load_moment_and_deflection():
    s = FrameSolver2D()
    a, t = s.add_node(0, 0), s.add_node(0, 3)
    e = s.add_element(a, t, E, 0.002, 0.1)
    s.add_node_load(t, fx=10.0)
    s.solve()
    r = s.get_member_forces(e)
    assert abs(r["m_end1"]) == pytest.approx(30.0, rel=1e-9)
    assert s.displacements[3] == pytest.approx(10 * 3 ** 3 / (3 * E * 0.002), rel=1e-9)


def test_pinned_base_has_zero_base_moment_and_larger_span_moment():
    s, b, c1, _ = portal(fixed=False)
    sf, bf, _, _ = portal(fixed=True)
    assert abs(s.get_member_forces(c1)["m_end1"]) < 1e-6
    assert s.get_member_forces(b)["max_sagging"] > sf.get_member_forces(bf)["max_sagging"]


def test_solve_cases_superposition():
    s = FrameSolver2D()
    n0, n1, n2, n3 = s.add_node(0, 0), s.add_node(0, 3), s.add_node(5, 0), s.add_node(5, 3)
    s.add_element(n0, n1, E, 0.003, 0.12)
    s.add_element(n2, n3, E, 0.003, 0.12)
    b = s.add_element(n1, n3, E, 0.005, 0.15)
    res = s.solve_cases({"A": ({b: 12.0}, {}), "B": ({}, {n1: [8.0, 0, 0]}), "AB": ({b: 12.0}, {n1: [8.0, 0, 0]})})
    fa, fb, fab = (res[k]["forces"][b] for k in ("A", "B", "AB"))
    assert all(abs((x + y) - z) < 1e-6 for x, y, z in zip(fa, fb, fab))


def test_mechanism_is_detected_not_solved():
    s = FrameSolver2D()
    a, b = s.add_node(0, 3), s.add_node(4, 3)     # beam with no supports
    s.add_element(a, b, E, 0.002, 0.1)
    s.add_member_load(0, 10.0)
    s.solve()
    assert s.status in ("SINGULAR", "UNSTABLE")
    assert s.results == {}
