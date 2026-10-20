"""
IS 875 (Part 3):2015 wind values checked against the printed standard on 2026-10-20.
"""
import pytest

from src.wind_load import (BASIC_WIND_SPEED, K2_TABLE, TerrainCategory, WindLoadCalculator, WindZone,
                           calculate_wind_load)

PRINTED_T2 = {10: (1.05, 1.00, 0.91, 0.80), 15: (1.09, 1.05, 0.97, 0.80), 20: (1.12, 1.07, 1.01, 0.80),
              30: (1.15, 1.12, 1.06, 0.97), 50: (1.20, 1.17, 1.12, 1.10), 100: (1.26, 1.24, 1.20, 1.20),
              150: (1.30, 1.28, 1.24, 1.24), 200: (1.32, 1.30, 1.27, 1.27), 250: (1.34, 1.32, 1.29, 1.28),
              300: (1.35, 1.34, 1.31, 1.30), 350: (1.35, 1.35, 1.32, 1.31), 400: (1.35, 1.35, 1.34, 1.32),
              450: (1.35, 1.35, 1.35, 1.33), 500: (1.35, 1.35, 1.35, 1.34)}
CATS = [TerrainCategory.CATEGORY_1, TerrainCategory.CATEGORY_2, TerrainCategory.CATEGORY_3, TerrainCategory.CATEGORY_4]


def test_table_2_matches_print():
    assert dict(K2_TABLE) == PRINTED_T2


@pytest.mark.parametrize("i,cat", list(enumerate(CATS)))
def test_k2_at_tabulated_heights_and_between(i, cat):
    calc = WindLoadCalculator(zone=WindZone.ZONE_2, terrain_category=cat)
    for z, row in PRINTED_T2.items():
        assert calc.calculate_k2(z) == pytest.approx(row[i])
    assert calc.calculate_k2(3.0) == pytest.approx(PRINTED_T2[10][i])              # below 10 m: 10 m value
    assert calc.calculate_k2(40.0) == pytest.approx((PRINTED_T2[30][i] + PRINTED_T2[50][i]) / 2)


def test_basic_wind_speeds():   # Fig. 1 / Annex A zones
    assert [BASIC_WIND_SPEED[z] for z in WindZone] == [33.0, 39.0, 44.0, 47.0, 50.0, 55.0]


def test_slender_building_is_flagged_unconservative():
    r = calculate_wind_load(zone=WindZone.ZONE_3, height_m=60.0, width_m=9.0, length_m=12.0,
                            terrain_category=TerrainCategory.CATEGORY_2, storey_height_m=3.0)
    assert any(w.startswith("UNCONSERVATIVE") for w in r.warnings)
    r2 = calculate_wind_load(zone=WindZone.ZONE_3, height_m=9.0, width_m=9.0, length_m=12.0,
                             terrain_category=TerrainCategory.CATEGORY_2, storey_height_m=3.0)
    assert not any(w.startswith("UNCONSERVATIVE") for w in r2.warnings)
