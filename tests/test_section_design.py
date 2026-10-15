"""
Hand-calculation checks for src/section_design.py.

Reference values are computed in the test from first principles (rectangular
stress block / uniform strain); table values are checked only for internal
consistency (interpolation), NOT against the printed standard.
"""
import math

import pytest

from src import section_design as sd


def test_tau_c_interpolation_and_clamping():
    assert sd.tau_c(0.50, 25) == pytest.approx(0.49)
    assert sd.tau_c(0.625, 25) == pytest.approx((0.49 + 0.57) / 2)
    assert sd.tau_c(0.05, 20) == pytest.approx(0.28)          # clamped low
    assert sd.tau_c(4.0, 20) == pytest.approx(0.82)           # clamped high
    assert sd.tau_c(1.0, 27) == sd.tau_c(1.0, 25)             # lower grade used (conservative)


def test_mu_lim_fe415_coefficient():
    # 0.36 fck xu/d (1 - 0.42 xu/d) with xu/d = 0.48 -> 0.138 fck b d^2
    assert sd.mu_lim_knm(300, 500, 25, 415) == pytest.approx(0.1380 * 25 * 300 * 500 ** 2 / 1e6, rel=2e-3)


def test_singly_reinforced_ast_satisfies_equilibrium():
    b, d, fck, fy, mu = 300, 560, 25, 415, 250.0
    ast = sd.ast_singly(mu, b, d, fck, fy)
    # IS 456 Annex G closed form that the implementation inverts
    m_annex_g = 0.87 * fy * ast * d * (1 - ast * fy / (b * d * fck)) / 1e6
    assert m_annex_g == pytest.approx(mu, rel=1e-3)
    # rectangular stress block (0.36 fck, 0.42 xu) differs by ~0.25 % by construction
    xu = 0.87 * fy * ast / (0.36 * fck * b)
    m_block = 0.87 * fy * ast * (d - 0.42 * xu) / 1e6
    assert m_block == pytest.approx(mu, rel=5e-3)


def test_doubly_reinforced_section_equilibrium():
    b, d, dp, fck, fy = 230, 400, 50, 25, 415
    mu = 1.4 * sd.mu_lim_knm(b, d, fck, fy)
    r = sd.design_flexure(mu, b, d, dp, fck, fy)
    assert r.doubly and r.asc_req > 0
    xu = 0.48 * d
    fsc = sd.steel_stress(0.0035 * (1 - dp / xu), fy)
    c_conc = 0.36 * fck * b * xu
    c_steel = r.asc_req * (fsc - 0.446 * fck)
    assert 0.87 * fy * r.ast_req == pytest.approx(c_conc + c_steel, rel=1e-6)
    m = (c_conc * (d - 0.42 * xu) + c_steel * (d - dp)) / 1e6
    assert m == pytest.approx(mu, rel=1e-6)


def test_fe415_stress_strain_points():
    fyd = 0.87 * 415
    assert sd.steel_stress(0.8 * fyd / 2e5, 415) == pytest.approx(0.8 * fyd)
    assert sd.steel_stress(0.01, 415) == pytest.approx(fyd)
    assert sd.steel_stress(-0.01, 415) == pytest.approx(-fyd)
    assert sd.steel_stress(0.001, 250) == pytest.approx(200.0)


def test_shear_minimum_and_designed_spacing():
    r = sd.design_shear(20, 300, 500, 1.0, 25, 415)           # tau_v < tau_c
    asv = 2 * math.pi * 16
    assert r.spacing_mm <= 0.87 * 415 * asv / (0.4 * 300) + 1e-6
    assert r.spacing_mm <= 0.75 * 500
    r2 = sd.design_shear(250, 300, 500, 1.0, 25, 415)
    vus = (250e3 / (300 * 500) - sd.tau_c(1.0, 25)) * 300 * 500
    assert r2.spacing_mm <= 0.87 * 415 * asv * 500 / vus
    assert r2.status == "PASS"
    r3 = sd.design_shear(600, 230, 300, 1.0, 25, 415)
    assert r3.status == "FAIL"


def test_column_interaction_end_points():
    sec = sd.column_section(300, 450, 8, 16, 25, 415)
    for direction in ("x", "y"):
        P, M = sd.interaction_curve(sec, direction)
        p0 = 0.446 * 25 * (sec.Ag - sec.As) + sd.steel_stress(0.002, 415) * sec.As
        assert P[-1] == pytest.approx(p0 / 1e3, rel=1e-9)
        assert P[0] == pytest.approx(-0.87 * 415 * sec.As / 1e3, rel=1e-9)
        assert M[-1] == pytest.approx(0.0, abs=1e-9)
        assert max(M) > sd.moment_capacity_at(0.0, (P, M)) > 0
    assert sd.puz_kn(sec) == pytest.approx((0.45 * 25 * (sec.Ag - sec.As) + 0.75 * 415 * sec.As) / 1e3)


def test_column_bending_capacity_at_zero_axial_matches_hand_value():
    """Pure bending of a 4-bar section (2-16 per face): strain compatibility
    solved independently with the 0.36 fck / 0.42 xu rectangular block."""
    sec = sd.column_section(300, 450, 4, 16, 25, 415)
    P, M = sd.interaction_curve(sec, "y")
    m_engine = sd.moment_capacity_at(0.0, (P, M))
    As = 2 * sd.BAR_AREAS[16]
    edge = 40 + 8 + 8
    d, dp, yc = 450 - edge, edge, 225.0

    def forces(xu):
        es_c = 0.0035 * (xu - dp) / xu
        es_t = 0.0035 * (d - xu) / xu
        cc = 0.36 * 25 * 300 * xu
        cs = As * (sd.steel_stress(es_c, 415) - sd.concrete_stress(es_c, 25))
        ts = As * sd.steel_stress(es_t, 415)
        return cc, cs, ts

    lo, hi = 1.0, d
    for _ in range(200):
        xu = (lo + hi) / 2
        cc, cs, ts = forces(xu)
        lo, hi = (lo, xu) if cc + cs - ts > 0 else (xu, hi)
    xu = (lo + hi) / 2
    cc, cs, ts = forces(xu)
    m_hand = (cc * (yc - 0.42 * xu) + cs * (yc - dp) + ts * (d - yc)) / 1e6
    assert m_engine == pytest.approx(m_hand, rel=0.03)   # fibre integration vs rectangular block


def test_min_eccentricity_and_additional_moment():
    assert sd.e_min_mm(6000, 600) == pytest.approx(6000 / 500 + 600 / 30)
    assert sd.e_min_mm(1000, 230) == 20.0
    assert sd.additional_moment_knm(1000, 300, 3000) == 0.0          # le/D = 10
    assert sd.additional_moment_knm(1000, 230, 4000) == pytest.approx(1000 * 230 / 2000 * (4000 / 230) ** 2 / 1000)


def test_check_column_includes_minimum_eccentricity_moment():
    sec = sd.column_section(300, 450, 8, 16, 25, 415)
    chk = sd.check_column(sec, 1000.0, 0.0, 0.0, 3500.0)
    assert max(chk.mux_kNm, chk.muy_kNm) >= 1000.0 * sd.e_min_mm(3500, 300) / 1e3 - 1e-9
    heavier = sd.check_column(sec, 1000.0, 60.0, 0.0, 3500.0)
    assert heavier.ratio > chk.ratio
