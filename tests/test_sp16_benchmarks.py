"""
Benchmarks against SP 16:1980 "Design Aids for Reinforced Concrete to IS 456" (tables and worked examples typed
from the printed document, 2026-10-20). Tolerances reflect the design aid's rounding and chart reading, and are
stated per test. Agreement here is evidence that the section routines reproduce the published design aid; it is
not a sign-off of the design.
"""
from types import SimpleNamespace

import pytest

from src import section_design as sd


# ---- Table C and Table D: limiting moment of resistance (singly reinforced) ---------------------------------

# The code uses the IS 456 (38.1) rounded xu,max/d = 0.53 / 0.48 / 0.46; SP 16 tabulated with unrounded values
# (about 0.531 / 0.479 / 0.456), so agreement is within 0.6 %.
@pytest.mark.parametrize("fy,ratio", [(250, 0.149), (415, 0.138), (500, 0.133)])
def test_table_c_mu_lim_over_fck_bd2(fy, ratio):
    b, d = 1000.0, 1000.0
    assert sd.mu_lim_knm(b, d, 20.0, fy) * 1e6 / (b * d * d) / 20.0 == pytest.approx(ratio, rel=0.006)


@pytest.mark.parametrize("fck,fy,value", [(15, 415, 2.07), (20, 415, 2.76), (25, 415, 3.45), (30, 415, 4.14),
                                          (20, 500, 2.66), (25, 500, 3.33), (30, 500, 3.99), (15, 250, 2.24),
                                          (20, 250, 2.98), (25, 250, 3.73), (30, 250, 4.47)])
def test_table_d_mu_lim_over_bd2(fck, fy, value):
    assert sd.mu_lim_knm(1000.0, 1000.0, fck, fy) * 1e6 / 1e9 == pytest.approx(value, rel=0.008)  # + 2-decimal rounding


@pytest.mark.parametrize("fy,value", [(250, 21.97), (415, 19.82), (500, 18.87)])
def test_table_c_pt_lim_fy_over_fck(fy, value):
    # IS 456 rounds xu,max/d (0.53 / 0.48 / 0.46); SP 16 used the unrounded strain values -> within 1 %
    k = sd.xu_max_ratio(fy)
    assert 0.36 * k / 0.87 * 100.0 == pytest.approx(value, rel=0.01)


# ---- Example 1: singly reinforced beam (300 x 600, d = 562.5, M15, Fe415, Mu = 170 kNm) -> As = 10.02 cm2 ----

def test_example_1_singly_reinforced_beam():
    assert sd.ast_singly(170.0, 300.0, 562.5, 15.0, 415.0) == pytest.approx(1002.0, rel=0.01)


# ---- Example 3: doubly reinforced (Mu = 320 kNm, d'/d = 0.1 tables): pt = 1.117 %, pc = 0.418 % --------------

def test_example_3_doubly_reinforced_beam():
    r = sd.design_flexure(320.0, 300.0, 562.5, 56.25, 15.0, 415.0)
    assert r.ast_req == pytest.approx(1885.0, rel=0.02)     # 18.85 cm2
    assert r.asc_req == pytest.approx(705.0, rel=0.03)      # 7.05 cm2


# ---- Table A (1.4): cold-worked bars, total strain -> design stress --------------------------------------------

@pytest.mark.parametrize("fy,strain,stress", [
    (415, 0.00144, 288.7), (415, 0.00163, 306.7), (415, 0.00192, 324.8), (415, 0.00241, 342.8),
    (415, 0.00276, 351.8), (415, 0.00380, 360.9),
    (500, 0.00174, 347.8), (500, 0.00195, 369.6), (500, 0.00226, 391.3), (500, 0.00277, 413.0),
    (500, 0.00312, 423.9), (500, 0.00417, 434.8)])
def test_table_a_steel_stress(fy, strain, stress):
    # SP 16 prints 288.1 for Fe 415 at 0.80 fyd; 0.80 x 0.87 x 415 = 288.8 (the printed value is a misprint)
    assert float(sd.steel_stress(strain, fy)) == pytest.approx(stress, rel=0.005)


# ---- Table F: stress in compression steel of doubly reinforced beams --------------------------------------------

@pytest.mark.parametrize("fy,ratio,fsc", [(415, 0.05, 355), (415, 0.10, 353), (415, 0.15, 342), (415, 0.20, 329),
                                          (500, 0.05, 424), (500, 0.10, 412), (500, 0.15, 395), (500, 0.20, 370)])
def test_table_f_compression_steel_stress(fy, ratio, fsc):
    strain = 0.0035 * (1.0 - ratio / sd.xu_max_ratio(fy))
    assert float(sd.steel_stress(strain, fy)) == pytest.approx(fsc, rel=0.012)


# ---- Example 6: square column 450 x 450, M25, Fe415, Pu = 2500 kN, Mu = 200 kNm -> p = 2.5 % on four sides -----

def test_example_6_column_capacity_at_chart_steel():
    # 16 bars of 20 mm = 2.48 % (SP 16 Chart 45: p = 2.5 %). Chart reading and d'/D (SP 16 uses the 0.15 chart
    # for d'/D = 0.12) -> capacity within 10 % of 200 kNm.
    sec = sd.column_section(450.0, 450.0, 16, 20, 25.0, 415.0, clear_cover=40.0)
    m = sd.moment_capacity_at(2500.0, sd.interaction_curve(sec, "x"))
    assert 180.0 <= m <= 220.0


# ---- Example 9: slender column 400 x 300, M30, Fe415, Pu = 1500 kN ---------------------------------------------

def test_example_9_puz():
    # Chart 63: Puz / Ag = 22.5 N/mm2 for p = 3 % -> Puz = 2700 kN
    ag = 400.0 * 300.0
    sec = SimpleNamespace(fck=30.0, fy=415.0, Ag=ag, As=0.03 * ag)
    assert sd.puz_kn(sec) == pytest.approx(2700.0, rel=0.01)


def test_example_9_additional_moments():
    # Table I: lex/D = 15 -> e/D = 0.113 -> Max = 67.8 kNm; ley/b = 16.7 -> 0.140 -> May = 63.0 kNm
    assert sd.additional_moment_knm(1500.0, 400.0, 6000.0) == pytest.approx(67.8, rel=0.01)
    assert sd.additional_moment_knm(1500.0, 300.0, 5000.0) == pytest.approx(63.0, rel=0.01)


def test_example_9_minimum_eccentricity():
    assert sd.e_min_mm(7000.0, 400.0) == pytest.approx(27.3, abs=0.05)
    assert sd.e_min_mm(7000.0, 300.0) == pytest.approx(24.0, abs=0.05)


# ---- Example 10: shear (300 x 600, d = 562.5, M15, pt = 0.8 %, Vu = 180 kN, Fe250 stirrups) -> 8 mm 2L @ 140 ---

def test_example_10_shear():
    r = sd.design_shear(180.0, 300.0, 562.5, 0.8, 15.0, 250.0, stirrup_dia=8, legs=2)
    assert r.tau_v == pytest.approx(1.07, abs=0.01)
    assert r.tau_c == pytest.approx(0.55, abs=0.01)
    assert r.spacing_mm == pytest.approx(140.0, abs=5.0)


# ---- Example 2: slab 100 mm, d = 80 mm, M15, Fe415, Mu = 9.6 kNm/m -> pt = 0.475 %, As = 3.8 cm2/m --------------

def test_example_2_slab():
    assert sd.ast_singly(9.6, 1000.0, 80.0, 15.0, 415.0) == pytest.approx(380.0, rel=0.02)
