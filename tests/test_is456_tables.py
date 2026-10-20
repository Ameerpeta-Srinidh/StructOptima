"""
IS 456:2000 tables transcribed in the code, compared with an independent copy typed from the printed standard
(with all amendments) on 2026-10-20. See docs/verification/standards-check-2026-10-20.md.
"""
import pytest

from src.rebar_detailer import TABLE26, TABLE26_CASE, TABLE26_RATIOS, table26_coefficients
from src.section_design import TAU_C_MAX, TAU_C_TABLES

# Table 26: case -> (short-span negative, short-span positive, long-span negative, long-span positive);
# None = no value printed (edge not continuous)
PRINTED_26 = {
    1: ([.032, .037, .043, .047, .051, .053, .060, .065], [.024, .028, .032, .036, .039, .041, .045, .049], .032, .024),
    2: ([.037, .043, .048, .051, .055, .057, .064, .068], [.028, .032, .036, .039, .041, .044, .048, .052], .037, .028),
    3: ([.037, .044, .052, .057, .063, .067, .077, .085], [.028, .033, .039, .044, .047, .051, .059, .065], .037, .028),
    4: ([.047, .053, .060, .065, .071, .075, .084, .091], [.035, .040, .045, .049, .053, .056, .063, .069], .047, .035),
    5: ([.045, .049, .052, .056, .059, .060, .065, .069], [.035, .037, .040, .043, .044, .045, .049, .052], None, .035),
    6: (None, [.035, .043, .051, .057, .063, .068, .080, .088], .045, .035),
    7: ([.057, .064, .071, .076, .080, .084, .091, .097], [.043, .048, .053, .057, .060, .064, .069, .073], None, .043),
    8: (None, [.043, .051, .059, .065, .071, .076, .087, .096], .057, .043),
    9: (None, [.056, .064, .072, .079, .085, .089, .100, .107], None, .056),
}

PRINTED_19 = {   # pt: M15, M20, M25, M30, M35, M40 and above
    0.15: (.28, .28, .29, .29, .29, .30), 0.25: (.35, .36, .36, .37, .37, .38), 0.50: (.46, .48, .49, .50, .50, .51),
    0.75: (.54, .56, .57, .59, .59, .60), 1.00: (.60, .62, .64, .66, .67, .68), 1.25: (.64, .67, .70, .71, .73, .74),
    1.50: (.68, .72, .74, .76, .78, .79), 1.75: (.71, .75, .78, .80, .82, .84), 2.00: (.71, .79, .82, .84, .86, .88),
    2.25: (.71, .81, .85, .88, .90, .92), 2.50: (.71, .82, .88, .91, .93, .95), 2.75: (.71, .82, .90, .94, .96, .98),
    3.00: (.71, .82, .92, .96, .99, 1.01),
}


def test_table_26_ratios():
    assert TABLE26_RATIOS == [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.75, 2.0]


@pytest.mark.parametrize("case", range(1, 10))
def test_table_26_matches_printed_standard(case):
    neg, pos, y_neg, y_pos = TABLE26[case]
    p_neg, p_pos, p_yneg, p_ypos = PRINTED_26[case]
    assert neg == p_neg
    assert pos == p_pos
    assert y_neg == (p_yneg or 0.0)     # no printed value = edge discontinuous = no negative moment
    assert y_pos == p_ypos


def test_table_26_case_mapping():
    # (discontinuous short edges, discontinuous long edges) -> case, per the case titles (Case 2 as corrected by
    # the amendment: "One Short Edge Discontinuous")
    assert TABLE26_CASE == {(0, 0): 1, (1, 0): 2, (0, 1): 3, (1, 1): 4, (2, 0): 5, (0, 2): 6, (2, 1): 7, (1, 2): 8,
                            (2, 2): 9}


def test_table_26_interpolation_between_columns():
    case, neg, pos, _, _ = table26_coefficients(1.15, 0, 0)
    assert case == 1 and neg == pytest.approx((.037 + .043) / 2) and pos == pytest.approx((.028 + .032) / 2)


def test_table_26_case_4_long_span_negative_is_0_047():   # finding T1
    assert table26_coefficients(1.0, 1, 1)[3] == pytest.approx(0.047)


def test_table_19_matches_printed_standard():
    for i, grade in enumerate((15, 20, 25, 30, 35, 40)):
        assert dict(TAU_C_TABLES[grade]) == {pt: v[i] for pt, v in PRINTED_19.items()}


def test_table_20_matches_printed_standard():
    assert TAU_C_MAX == {15: 2.5, 20: 2.8, 25: 3.1, 30: 3.5, 35: 3.7, 40: 4.0}


def test_m15_uses_its_own_column():   # was silently given the M20 values (unconservative)
    from src.section_design import tau_c
    assert tau_c(0.8, 15) == pytest.approx(0.54 + (0.60 - 0.54) * 0.05 / 0.25)
