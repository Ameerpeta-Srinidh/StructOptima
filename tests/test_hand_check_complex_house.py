"""
Worked hand check of samples/plans/complex_house.dxf (formula document, Appendix A).

The drawing is loaded exactly as the Setup page loads it, then every value the appendix asks the reader to compute
by hand is recomputed here from the printed formulas and compared with the design. If this test fails, the appendix
and the site no longer agree: update both together.

Inputs: G+2 (3 storeys x 3.0 m), Residential, Zone II, soil II, SMRF, I = 1.0, SBC 150 kN/m2, M25, Fe500, Moderate
exposure, NBC Type 2, wind zone 3, terrain 2, cracked sections, fixed bases.
"""
import logging
import math
from pathlib import Path

import pytest

from src.cad_loader import CADLoader
from src.design_pipeline import DesignInputs, run_design
from src.wind_load import TerrainCategory, WindZone

logging.disable(logging.CRITICAL)

DXF = Path(__file__).resolve().parent.parent / "samples" / "plans" / "complex_house.dxf"
N, H = 3, 3.0
FCK, FY = 25.0, 500.0


@pytest.fixture(scope="module")
def res():
    loader = CADLoader(str(DXF))
    gm, beams = loader.load_grid_manager(auto_frame=False, seismic_zone="II", story_height_m=H, num_stories=N)
    gm.columns = gm.stack_columns([c for c in gm.columns if c.level == 0], N, H)
    inp = DesignInputs(num_stories=N, story_height_m=H, building_type_name="Residential", wall_load_kn_m=12.0,
                       sbc_kn_m2=150.0, conc_grade="M25", fy=FY, seismic_zone="II", soil_type="II",
                       structural_system="SMRF", importance_factor=1.0, wind_zone=WindZone("3"),
                       terrain_category=TerrainCategory("2"), use_cracked_sections=True, fixed_base=True,
                       add_staircase=False, exposure="Moderate", nbc_construction_type=2)
    return run_design(gm, beams, inp)


# ---- A.1 geometry --------------------------------------------------------------------------------------------
def test_a1_geometry_read_from_the_drawing(res):
    cols = {(round(c.x, 3), round(c.y, 3)) for c in res.gm.columns if c.level == 0}
    assert cols == {(x, y) for x in (0, 4, 8) for y in (0, 4, 8)} | {(12, 0), (12, 4)}   # L-shape, 11 columns
    assert len(res.beams) == 15 and all(b.properties.depth_mm == 600 for b in res.beams)


# ---- A.2 loads and slab ---------------------------------------------------------------------------------------
LX = 4.0
COVER_SLAB = 30.0                                       # Table 16 Moderate (30) > Table 16A 1.5 h SS slab (25)
T_SLAB = math.ceil((LX * 1000 / 26 + max(30, COVER_SLAB + 10)) / 5) * 5          # 195 mm
SDL = 1.0 + 1.5 + 0.5                                   # finish + partitions + services
W_SLAB = 1.5 * (25 * T_SLAB / 1000 + SDL + 2.0)        # 14.8125 kN/m2


def test_a2_slab_panel(res):
    s = res.gm.slab_schedule["S1"]
    assert T_SLAB == 195 and s.thickness_mm == 195
    assert s.factored_load_kn_m2 == pytest.approx(W_SLAB)
    assert s.table26_case == 4                          # corner panel: two adjacent edges discontinuous
    assert s.mx_neg_knm == pytest.approx(0.047 * W_SLAB * LX ** 2, rel=1e-6)   # Table 26 case 4, ly/lx = 1
    assert s.mx_pos_knm == pytest.approx(0.035 * W_SLAB * LX ** 2, rel=1e-6)


# ---- A.3 seismic weight and base shear ------------------------------------------------------------------------
WALL = 0.23 * (H - 0.125 - 0.400) * (1 - 0.33) * 19.2                 # 7.3226 kN/m
WEB = 0.3 * (0.6 - 0.125) * 25                                         # beam web below the 125 mm slab
AREA = 5 * 16.0                                                        # five 4 x 4 m panels
EXTRA = 25 * (T_SLAB - 125) / 1000                                     # thicker designed slab
COLS = 9 * 0.30 * 0.45 * H * 25 + 2 * 0.40 * 0.60 * H * 25            # one storey of columns
# N46 (fixed 2026-10-20): the thicker designed slab is counted to the beam centre line, so the half beam width on
# each panel side is deducted from the web: 20 panel edges on beams (5 panels x 4), each 4 m long
OVERLAP = 20 * 0.15 * EXTRA * 4.0


def test_a3_seismic_weight_and_static_base_shear(res):
    sr = res.seismic_result
    floor = AREA * (25 * 0.125 + SDL + EXTRA) + 0.25 * 2.0 * AREA + 60 * WEB - OVERLAP + 60 * WALL + COLS
    roof = AREA * (25 * 0.125 + 1.0 + 0.5 + EXTRA) + 60 * WEB - OVERLAP + 0.5 * 60 * WALL + 0.33 * 60 * WALL + COLS / 2
    assert sr.storey_weights_kn == pytest.approx([floor, floor, roof], rel=1e-6)
    W = 2 * floor + roof
    ta = min(0.075 * 9.0 ** 0.75, 0.09 * 9.0 / math.sqrt(12.0))        # 0.234 s (infill, d = 12 m)
    assert sr.parameters.fundamental_period == pytest.approx(ta)
    ah = 0.10 / 2 * 1.0 / 5.0 * 2.5                                     # Sa/g = 2.5 (T < 0.55 s, soil II)
    assert sr.base_shear_kn == pytest.approx(max(ah, 0.007) * W, rel=1e-6)
    wh2 = [w * h * h for w, h in zip(sr.storey_weights_kn, (3.0, 6.0, 9.0))]
    assert sr.storey_forces_kn[2] == pytest.approx(sr.base_shear_kn * wh2[2] / sum(wh2), rel=1e-9)
    for d in ("X", "Y"):                                                 # 7.7.3 scaling to the static VB
        dyn = sr.dynamic[d]
        assert dyn["VB design (kN)"] == pytest.approx(round(sr.base_shear_kn, 1), abs=0.051)
        assert dyn["Scale factor"] == pytest.approx(sr.base_shear_kn / dyn["VB dynamic (kN)"], rel=2e-3)


# ---- A.4 beam B5 ----------------------------------------------------------------------------------------------
def _ast(mu_knm, b, d):
    r = mu_knm * 1e6 / (b * d * d)
    return 50 * FCK / FY * (1 - math.sqrt(1 - 4.598 * r / FCK)) * b * d / 100


def test_a4_beam_b5(res):
    b5 = next(b for b in res.all_beams if b.id == "B5_L0")
    k = LX / 3                                                           # each side, two-way square panel
    udl = 2 * k * (25 * 0.125 + SDL + EXTRA + 2.0) + WEB - 2 * 0.15 * EXTRA + WALL   # 36.69 kN/m service (N46)
    assert b5.service_udl_kn_m == pytest.approx(udl, rel=1e-6)
    s = res.gm.beam_schedule["B5"]
    d = 600 - 30 - 8 - 12 / 2                                            # 556 mm
    assert s.ast_top_req_mm2 == pytest.approx(_ast(s.mu_hogging_knm, 300, d), rel=1e-4)
    tau_v = s.vu_kn * 1e3 / (300 * d)
    assert s.tau_v_Nmm2 == pytest.approx(tau_v, rel=1e-6)
    pt = 100 * s.ast_bottom_prov_mm2 / (300 * d)                         # smaller face, 0.203 %
    assert s.tau_c_Nmm2 == pytest.approx(0.29 + (pt - 0.15) / 0.10 * (0.36 - 0.29), rel=1e-4)
    sv = min(0.87 * 415 * 100.53 * d / ((tau_v - s.tau_c_Nmm2) * 300 * d), 0.87 * 415 * 100.53 / (0.4 * 300),
             0.75 * d, 300)
    assert sv == pytest.approx(300.0)
    assert "@ 300" in s.stirrups_desc and "@ 70" in s.stirrups_desc   # ductile end zone min(d/4, 6x12, 100) -> 70


# ---- A.5 column C5, ground storey -----------------------------------------------------------------------------
def test_a5_column_c5(res):
    c = next(x for x in res.gm.columns if x.id == "C5_L0")
    pu_gravity = next(f[1] for f in c.design_forces if f[0] == "1.5(DL+LL)@bottom")
    assert pu_gravity == pytest.approx(1.5 * c.load_kn, rel=1e-9)
    s = res.gm.rebar_schedule["C5_L0"]
    ac = 400 * 600 - s.main_steel_area_mm2
    puz = (0.45 * FCK * ac + 0.75 * FY * s.main_steel_area_mm2) / 1e3
    assert f"Puz = {puz:.0f} kN" in " ".join(s.math_log)
    # SP 16 Chart 49 (Fe500, d'/D = 0.15): independent strain-compatibility value 190 kNm; the site's 199 kNm uses
    # the actual 10-bar layout. Accept the chart reading within 10 %.
    mux1 = float(next(x for x in s.math_log if "Mux1" in x).split("Mux1 = ")[1].split()[0])
    assert mux1 == pytest.approx(190.0, rel=0.10)
    assert s.interaction_ratio < 1.0


# ---- A.6 footing under C5 -------------------------------------------------------------------------------------
def test_a6_footing_c5(res):
    ft = next(f for f in res.footings if f.id == "F-C5_L0")
    side = math.ceil(math.sqrt(1.1 * ft.service_load_kn / 150.0) / 0.05) * 0.05
    assert ft.length_m == pytest.approx(side) and side == pytest.approx(2.40)
    d = ft.thickness_mm - 50 - 12
    qu = ft.factored_load_kn / side ** 2
    vu = ft.factored_load_kn - qu * (0.4 + d / 1e3) * (0.6 + d / 1e3)
    tau = vu * 1e3 / (2 * ((400 + d) + (600 + d)) * d)
    assert tau <= min(1.0, 0.5 + 400 / 600) * 0.25 * math.sqrt(FCK)                       # punching passes
    mu_per_m = qu * ((side - 0.4) / 2) ** 2 / 2
    assert ft.ast_per_m_mm2 == pytest.approx(max(_ast(mu_per_m, 1000, d), 0.0012 * 1000 * ft.thickness_mm), rel=1e-3)


# ---- A.7 strong column / weak beam at the roof of C1 -----------------------------------------------------------
def test_a7_scwb_roof_joint_c1(res):
    j = next(d for d in res.seismic_result.scwb_details if d["Joint"] == "J_C1_L2_X")
    ast = res.gm.beam_schedule["B1"].ast_top_prov_mm2                    # 3-12 = 339 mm2
    d = 600 - 30 - 16
    xu = 0.87 * FY * ast / (0.36 * FCK * 300)
    mb = 0.87 * FY * ast * (d - 0.42 * xu) / 1e6                         # 78.4 kNm
    assert j["Sum Mb (kNm)"] == pytest.approx(mb, abs=0.06)
    assert j["Ratio"] < 1.4 and not j["pass"]                            # IS 13920 7.2.1: FAIL (roof checked, <= 4 storeys)
    assert any(f["Member"] == "J_C1_L2_X" and f["Status"] == "FAIL" for f in res.failures)
