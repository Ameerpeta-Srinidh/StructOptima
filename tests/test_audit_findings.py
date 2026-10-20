"""
Regression tests for the 2026-10 audit findings (docs/assurance/risk-register.md).

Each test is named after the finding it guards.  Where a numerical reference
is used it is derived in the test (hand calculation), not taken from the code.
"""
import logging
import math

import pytest

from src.analysis_integration import LateralLoads, build_combinations, update_structural_analysis
from src.audit import StructuralAuditor
from src.design_pipeline import DesignInputs, run_design
from src.foundation_eng import design_footing
from src.framing_logic import MemberProperties, Point, StructuralMember
from src.grid_manager import Column, GridManager
from src.materials import Concrete
from src.quantifier import Quantifier
from src.rebar_detailer import RebarDetailer, table26_coefficients
from src.seismic import evaluate_joint_checks, importance_for_occupancy, run_seismic_check
from src.wind_load import TerrainCategory, WindZone, calculate_wind_load

logging.disable(logging.CRITICAL)
M25 = Concrete.from_grade("M25")


def _grid(stories=2, w=18.0, l=12.0, h=3.5):
    gm = GridManager(width_m=w, length_m=l, num_stories=stories, story_height_m=h)
    gm.generate_grid()
    return gm, gm.generate_beams()


@pytest.fixture(scope="module")
def design_g1():
    gm, beams = _grid()
    return run_design(gm, beams, DesignInputs(num_stories=2, seismic_zone="III", wind_zone=WindZone("2"),
                                              terrain_category=TerrainCategory("2")))


# ---------------------------------------------------------------- R1 ------
def test_R1_column_design_responds_to_moment_and_min_eccentricity():
    axial = RebarDetailer.detail_column(300, 450, 900, M25, unsupported_length_m=3.5)
    bent = RebarDetailer.detail_column(300, 450, 900, M25, mux_knm=120, unsupported_length_m=3.5)
    assert bent.main_steel_area_mm2 > axial.main_steel_area_mm2 or bent.interaction_ratio > axial.interaction_ratio
    # e_min moment always applied (IS 456 Cl 25.4): l/500 + D/30 >= 20 mm
    assert max(axial.mux_design_knm, axial.muy_design_knm) >= 900 * 20 / 1000 - 1e-6


def test_R1_overloaded_column_reports_fail():
    r = RebarDetailer.detail_column(300, 450, 5000, M25)
    assert r.status == "FAIL" and r.warnings


# ---------------------------------------------------------------- R2 ------
def test_R2_beam_moments_are_factored_combinations():
    """Single bay, rigid columns: beam with one slab-panel side.  Hand value:
    w_DL, w_LL from the equivalent UDL; Mu_hog = 1.5 (w_DL + w_LL) L^2 / 12 for a
    fixed-ended beam is an upper bound for the hogging envelope."""
    gm = GridManager(width_m=4.0, length_m=4.0, num_stories=1, story_height_m=3.0)
    gm.generate_grid()
    beams = gm.generate_beams()
    gm.calculate_trib_areas()
    gm.calculate_loads(dead_load_kn_m2=5.0, live_load_kn_m2=3.0, beams=beams)
    gm.optimize_column_sizes(concrete=M25)
    summary = update_structural_analysis(gm, beams, fck=25)
    assert summary.frames_solved == summary.frames_total
    b = beams[0]
    k = 4.0 / 3.0                                  # square panel: lx/3
    sw = 0.23 * (b.properties.depth_mm / 1000 - 0.125) * 25
    extra = 25 * (0.185 - 0.125)                   # N13: 4 m panel designed 185 mm vs 125 mm occupancy slab
    w_dl = k * (5.0 + extra) + sw
    w_ll = k * 3.0
    total_service = (w_dl + w_ll) * 4.0 ** 2 / 8.0
    # statics: (hog + sag) under the factored load must equal 1.5 x service wL^2/8 (1.5(DL+LL) governs)
    assert b.mu_hogging_knm + b.mu_sagging_knm == pytest.approx(1.5 * total_service, rel=0.02)
    assert b.governing_combo.startswith("1.5(DL+LL)")


# ---------------------------------------------------------------- R3 ------
def test_R3_beam_design_follows_occupancy_loads():
    def beam_moment(dl, ll):
        gm, beams = _grid(stories=1)
        gm.calculate_trib_areas()
        gm.calculate_loads(dead_load_kn_m2=dl, live_load_kn_m2=ll, beams=beams)
        gm.optimize_column_sizes(concrete=M25)
        update_structural_analysis(gm, beams, fck=25)
        return beams[0].mu_sagging_knm
    assert beam_moment(6.0, 5.0) > beam_moment(6.0, 2.0)


# ---------------------------------------------------------------- R4 ------
def test_R4_top_steel_designed_for_hogging():
    small = RebarDetailer.detail_beam(300, 600, 5, mu_sagging_knm=40, mu_hogging_knm=40, vu_kn=80)
    big = RebarDetailer.detail_beam(300, 600, 5, mu_sagging_knm=40, mu_hogging_knm=300, vu_kn=80)
    assert big.ast_top_prov_mm2 > small.ast_top_prov_mm2
    assert big.ast_top_prov_mm2 >= big.ast_top_req_mm2
    # hand check of required top steel for 300 kNm (singly, d = 600-25-8-dia/2)
    assert big.ast_top_req_mm2 > 1500


def test_R4_compression_steel_is_provided_when_doubly_reinforced():
    r = RebarDetailer.detail_beam(230, 450, 5, mu_sagging_knm=200, mu_hogging_knm=20, vu_kn=60)
    assert r.doubly_reinforced
    assert r.ast_top_prov_mm2 > 2 * 113.1 + 1   # more than the nominal hanger bars


# ---------------------------------------------------------------- R5 ------
def test_R5_failures_reach_the_status_list(monkeypatch):
    """Column growth disabled -> undersized columns must stay FAIL and must be
    reported in the single status list used by every screen and the PDF."""
    import src.design_pipeline as dp
    monkeypatch.setattr(dp, "_next_pref", lambda v: v)
    gm, beams = _grid(stories=8, w=12, l=12)
    res = dp.run_design(gm, beams, DesignInputs(num_stories=8, seismic_zone="V", max_iterations=2))
    assert res.status == "FAIL"
    failing_cols = {cid for cid, r in res.gm.rebar_schedule.items() if r.status == "FAIL"}
    assert failing_cols
    assert failing_cols == {f["Member"] for f in res.failures if f["Type"] == "Column" and f["Status"] == "FAIL"}
    # 28 m in Zone V: equivalent static method not permitted (IS 1893 7.7.1) -> the response spectrum method is used
    assert res.seismic_result.method_used.startswith("response spectrum")
    assert not any(f["Type"] == "Seismic method" for f in res.failures)


def test_R5_every_non_pass_schedule_item_is_reported(design_g1):
    reported = {(f["Type"], f["Member"]) for f in design_g1.failures}
    for bid, r in design_g1.gm.beam_schedule.items():
        assert (r.status == "PASS") or (("Beam", bid) in reported)
    for cid, r in design_g1.gm.rebar_schedule.items():
        assert (r.status == "PASS") or (("Column", cid) in reported)
    for ft in design_g1.footings:
        assert (ft.status == "PASS") or (("Footing", ft.id) in reported)


def test_R5_result_models_carry_status():
    r = RebarDetailer.detail_beam(230, 300, 6, mu_sagging_knm=60, mu_hogging_knm=80, vu_kn=400)
    assert r.status == "FAIL" and r.tau_v_Nmm2 > r.tau_c_max_Nmm2


# ---------------------------------------------------------------- R6 ------
def test_R6_audit_uses_factored_load_and_user_sbc():
    gm = GridManager(width_m=6, length_m=6, num_stories=1, story_height_m=3)
    gm.generate_grid()
    col = gm.columns[0]
    col.width_nb, col.depth_nb = 300, 450
    gm.detail_columns(M25)
    asc = gm.rebar_schedule[col.id].main_steel_area_mm2
    cap = (0.4 * 25 * (300 * 450 - asc) + 0.67 * 415 * asc) / 1000
    col.load_kn = 0.9 * cap                      # service below capacity, factored above
    a = StructuralAuditor(gm, [], [], sbc_kn_m2=100)
    a.audit_columns()
    assert [r.status for r in a.audit_log if r.member_id == col.id] == ["FAIL"]

    ft = design_footing(600, sbc_kn_m2=100, column_width_mm=300, column_depth_mm=450, concrete=M25)
    gm2 = GridManager(width_m=6, length_m=6, num_stories=1)
    gm2.columns = [Column(id="C1_L0", x=0, y=0, load_kn=600, width_nb=300, depth_nb=450)]
    a2 = StructuralAuditor(gm2, [], [ft], sbc_kn_m2=100)
    a2.audit_footings()
    bearing = [r for r in a2.audit_log if r.check_name == "Bearing Pressure"][0]
    assert bearing.design_value == pytest.approx(600 * 1.1 / ft.area_m2)
    assert bearing.limit_value == 100


# ---------------------------------------------------------------- R7 ------
def test_R7_base_shear_depends_on_height_and_weight():
    gm, _ = _grid()
    lo = run_seismic_check(gm.columns, [], 10000, zone="IV", height_m=7.0)
    hi = run_seismic_check(gm.columns, [], 10000, zone="IV", height_m=40.0)
    assert hi.parameters.fundamental_period > lo.parameters.fundamental_period
    assert hi.base_shear_kn < lo.base_shear_kn
    # hand: Ta = 0.075 h^0.75, medium soil, Ah = Z/2 I/R Sa/g with R = 3 (OMRF default)
    ta = 0.075 * 40 ** 0.75
    assert hi.base_shear_kn == pytest.approx(0.24 / 2 * 1.0 / 3.0 * 1.36 / ta * 10000, rel=1e-6)


def test_R7_storey_forces_follow_wh2_distribution():
    r = run_seismic_check([], [], 3000, zone="III", height_m=10.5, storey_weights_kn=[1000, 1000, 1000],
                          storey_heights_m=[3.5, 7.0, 10.5])
    assert sum(r.storey_forces_kn) == pytest.approx(r.base_shear_kn)
    assert r.storey_forces_kn[2] / r.storey_forces_kn[0] == pytest.approx((10.5 / 3.5) ** 2)


def test_R7_importance_factor_uses_full_occupancy_name():
    assert importance_for_occupancy("Assembly Hall") == 1.5
    assert importance_for_occupancy("Institutional") == 1.5
    assert importance_for_occupancy("Residential") == 1.0


def test_R7_seismic_weight_includes_masonry(design_g1):
    gm = design_g1.gm
    walls = sum(w.length_m * w.line_load_kn_m for w in gm.walls)
    concrete_only = design_g1.bom.total_concrete_vol_m3 * 25
    assert design_g1.building_weight > walls     # masonry is part of W
    assert design_g1.seismic_result.storey_weights_kn


# ---------------------------------------------------------------- R8 ------
def test_R8_lateral_loads_produce_column_moments():
    gm, beams = _grid()
    gm.calculate_trib_areas()
    gm.calculate_loads(dead_load_kn_m2=6.0, live_load_kn_m2=2.0, beams=beams)
    gm.optimize_column_sizes(concrete=M25)
    update_structural_analysis(gm, beams, fck=25)
    grav = {c.id: max(abs(f[2]) for f in c.design_forces) for c in gm.columns}
    update_structural_analysis(gm, beams, fck=25, lateral=LateralLoads(eq_x=[100, 200], eq_y=[100, 200]))
    lat = {c.id: max(abs(f[2]) for f in c.design_forces) for c in gm.columns}
    assert all(lat[k] >= grav[k] - 1e-9 for k in grav)
    assert any(lat[k] > grav[k] + 1.0 for k in grav)
    names = [f[0] for f in gm.columns[0].design_forces]
    assert any("EQx" in n for n in names) and any("0.9DL" in n for n in names)


def test_R8_combinations_include_wind_in_both_directions():
    names = [n for n, _ in build_combinations(True, True)]
    assert "1.5(DL+LL)" in names and "1.2(DL+LL+WLx)" in names and "1.2(DL+LL+WLy)" in names


# ---------------------------------------------------------------- R9 ------
def test_R9_optimizer_uses_production_check_and_minimums(design_g1):
    from src.optimizer import optimize_structure
    cols = [c for c in design_g1.gm.columns if c.level == 0]
    oc, summary = optimize_structure(cols, 3.5, 2, fck=25, seismic_zone="III",
                                     rebar_schedule=design_g1.gm.rebar_schedule)
    assert summary.requires_reanalysis
    for o in oc.values():
        assert min(o.optimized_size_mm) >= 300 and max(o.optimized_size_mm) >= 450
        assert o.is_safe == (o.utilization_ratio <= 1 / 1.15 + 1e-9)
        assert o.axial_load_kn >= 1.5 * 0.9 * min(c.load_kn for c in cols)   # factored load used


# ---------------------------------------------------------------- R13 -----
def test_R13_bom_includes_beam_steel_for_per_level_ids(design_g1):
    gm = design_g1.gm
    q = Quantifier()
    with_beams = q.calculate_bom(gm.columns, design_g1.all_beams, design_g1.footings, grid_mgr=gm)
    no_beams = q.calculate_bom(gm.columns, [], design_g1.footings, grid_mgr=gm)
    expected = sum(gm.get_beam_result(b.id).weight_kg_per_m *
                   math.hypot(b.end_point.x - b.start_point.x, b.end_point.y - b.start_point.y)
                   for b in design_g1.all_beams) * 1.04
    assert with_beams.total_steel_weight_kg - no_beams.total_steel_weight_kg == pytest.approx(expected, rel=1e-6)


def test_R13_bbs_contains_beams_with_designed_bars(design_g1):
    members = design_g1.project_bbs.members
    beam_members = [m for m in members if m.member_type.lower() == "beam"]
    assert len(beam_members) == len(design_g1.gm.beam_schedule)


# ---------------------------------------------------------------- R14 -----
def test_R14_ifc_import_roundtrip(tmp_path):
    ifcopenshell = pytest.importorskip("ifcopenshell")
    from tests.ifc_fixture import build_frame_ifc
    from src.bim_loader import BIMLoader
    for unit_mm in (True, False):
        path = tmp_path / f"frame_{unit_mm}.ifc"
        build_frame_ifc(str(path), unit_mm=unit_mm)
        gm, beams = BIMLoader(str(path)).load_grid_manager()
        assert gm.num_stories == 2 and gm.story_height_m == pytest.approx(3.5)
        assert gm.x_grid_lines == [0.0, 4.5] and gm.y_grid_lines == [0.0, 4.0]
        assert len(gm.columns) == 8 and {c.width_nb for c in gm.columns} == {300.0}
        assert all(c.z_top - c.z_bottom == pytest.approx(3.5) for c in gm.columns)
        assert len(beams) == 4 and all(b.properties.depth_mm == 400.0 for b in beams)


# ---------------------------------------------------------------- R16 -----
def test_R16_footing_reinforcement_and_flags():
    ft = design_footing(900, sbc_kn_m2=150, column_width_mm=300, column_depth_mm=450, concrete=M25)
    assert ft.ast_per_m_mm2 >= 0.0012 * 1000 * ft.thickness_mm
    assert ft.rebar_desc and ft.steel_weight_kg > 0
    assert ft.punching_ok and ft.bending_ok and ft.one_way_shear_ok and ft.bearing_ok
    # hand: bending at column face
    side = ft.length_m * 1000
    qu = 1.5 * 900 * 1000 / side ** 2
    mu = qu * ((side - 300) / 2) ** 2 / 2 * 1000 / 1e6
    from src.section_design import ast_singly
    assert ft.ast_per_m_mm2 == pytest.approx(max(ast_singly(mu, 1000, ft.effective_depth_mm, 25, 415),
                                                 0.0012 * 1000 * ft.thickness_mm), rel=1e-6)


def test_R16_base_moment_eccentricity_flagged():
    ft = design_footing(300, sbc_kn_m2=200, base_moment_knm=200, concrete=M25)
    assert ft.status in ("WARN", "FAIL") and any("eccentricity" in w.lower() or "pressure" in w.lower() for w in ft.warnings)


# ---------------------------------------------------------------- R15 -----
def test_R15_scwb_uses_designed_beams(design_g1):
    sr = design_g1.seismic_result
    assert sr.scwb_evaluated and sr.scwb_details
    gm = design_g1.gm
    # double every beam's provided steel -> beam capacities rise -> ratios fall
    before = {d["Joint"]: d["Ratio"] for d in sr.scwb_details}
    for r in gm.beam_schedule.values():
        r.ast_top_prov_mm2 *= 2
        r.ast_bottom_prov_mm2 *= 2
    after = evaluate_joint_checks(gm, design_g1.beams, 25, 415, sr)
    # beam capacity is capped at xu,max, so heavily reinforced beams may not gain capacity:
    # no ratio may increase and at least one must decrease
    assert all(d["Ratio"] <= before[d["Joint"]] for d in after.scwb_details)
    assert any(d["Ratio"] < before[d["Joint"]] for d in after.scwb_details)
    for r in gm.beam_schedule.values():
        r.ast_top_prov_mm2 /= 2
        r.ast_bottom_prov_mm2 /= 2
    assert sr.ductile_verification in ("PARTIAL_SPACING_ONLY", "NOT_REQUIRED")


# ---------------------------------------------------------------- R17 -----
def _dxf(tmp_path, name, insunits, scale, extra_layer=None):
    import ezdxf
    doc = ezdxf.new()
    if insunits is not None:
        doc.header["$INSUNITS"] = insunits
    msp = doc.modelspace()
    for (x, y) in [(0, 0), (6, 0), (0, 5), (6, 5)]:
        x0, y0 = x * scale, y * scale
        h = 0.15 * scale
        msp.add_lwpolyline([(x0 - h, y0 - h), (x0 + h, y0 - h), (x0 + h, y0 + h), (x0 - h, y0 + h)],
                           close=True, dxfattribs={"layer": "COLUMNS"})
    if extra_layer:
        msp.add_line((0, -2 * scale), (6 * scale, -2 * scale), dxfattribs={"layer": extra_layer})
    p = tmp_path / name
    doc.saveas(p)
    return str(p)


def test_R17_insunits_drives_scale(tmp_path):
    from src.cad_loader import CADLoader
    for units, scale in ((4, 1000.0), (6, 1.0), (5, 100.0)):
        ld = CADLoader(_dxf(tmp_path, f"u{units}.dxf", units, scale))
        gm, _ = ld.load_grid_manager()
        assert gm.width_m == pytest.approx(6.0) and gm.length_m == pytest.approx(5.0)
        assert gm.columns[0].width_nb == pytest.approx(300.0)
        assert not any("INSUNITS" in w for w in ld.load_warnings)


def test_R17_unitless_drawing_is_flagged(tmp_path):
    from src.cad_loader import CADLoader
    ld = CADLoader(_dxf(tmp_path, "u0.dxf", 0, 1000.0))
    ld.load_grid_manager()
    assert any("INSUNITS" in w for w in ld.load_warnings)


def test_R17_tier2_excludes_annotation_layers(tmp_path):
    import ezdxf
    from src.cad_parser import CADParser
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_line((0, 0), (5000, 0), dxfattribs={"layer": "DIMENSIONS"})
    msp.add_line((0, 0), (0, 4000), dxfattribs={"layer": "LAYER1"})
    p = tmp_path / "t2.dxf"
    doc.saveas(p)
    cp = CADParser(str(p))
    cp.load()
    walls = cp.extract_walls()
    assert len(walls) == 1 and cp.warnings


# ---------------------------------------------------------------- R18 -----
def test_R18_missing_beams_are_generated():
    gm, _ = _grid(stories=1, w=8, l=8)
    res = run_design(gm, [], DesignInputs(num_stories=1, seismic_zone="II"))
    assert res.beams and any("No beams supplied" in m for m in res.messages)


# ---------------------------------------------------------------- R19 -----
def test_R19_takedown_includes_beam_self_weight_and_roof_loads():
    gm, beams = _grid(stories=2)
    gm.calculate_trib_areas()
    gm.calculate_loads(dead_load_kn_m2=6.0, live_load_kn_m2=2.0, roof_dead_kn_m2=4.0, roof_live_kn_m2=1.5)
    no_beams = {c.id: c.load_dl_kn for c in gm.columns}
    gm.calculate_loads(dead_load_kn_m2=6.0, live_load_kn_m2=2.0, roof_dead_kn_m2=4.0, roof_live_kn_m2=1.5, beams=beams)
    roof = [c for c in gm.columns if c.level == 1][0]
    assert roof.load_ll_kn == pytest.approx(roof.trib_area_m2 * 1.5)
    assert all(c.load_kn == pytest.approx(c.load_dl_kn + c.load_ll_kn) for c in gm.columns)
    assert any(abs(c.load_dl_kn - no_beams[c.id]) > 0.1 for c in gm.columns)


# ---------------------------------------------------------------- R20 -----
def test_R20_slab_uses_table26_case_and_actual_load():
    assert table26_coefficients(1.0, 0, 0)[1:3] == (0.032, 0.024)
    assert table26_coefficients(1.5, 1, 1)[0] == 4
    a = RebarDetailer.detail_slab(4, 4, 150, factored_load_kn_m2=10, disc_short_edges=0, disc_long_edges=0)
    b = RebarDetailer.detail_slab(4, 4, 150, factored_load_kn_m2=20, disc_short_edges=0, disc_long_edges=0)
    assert a.mx_pos_knm == pytest.approx(0.024 * 10 * 16)
    assert b.mx_pos_knm == pytest.approx(2 * a.mx_pos_knm)
    one_way = RebarDetailer.detail_slab(2, 4.5, 150, factored_load_kn_m2=10)
    assert not one_way.is_two_way and one_way.mx_pos_knm == pytest.approx(10 * 4 / 8)


# ---------------------------------------------------------------- R21 -----
def test_R21_grade_propagates_to_design(design_g1):
    gm, beams = _grid()
    res = run_design(gm, beams, DesignInputs(num_stories=2, conc_grade="M30", seismic_zone="III"))
    assert res.gm.fck == 30
    assert "M30" in res.gm.rebar_schedule[res.gm.columns[0].id].math_log[0]


# ---------------------------------------------------------------- R24 -----
def test_R24_invalid_dimensions_raise():
    from src.stability import StabilityChecker
    with pytest.raises(ValueError):
        StabilityChecker(2, 7.0).check_column_slenderness(0, 300, 3000)


# ---------------------------------------------------------------- R26 -----
def test_R26_column_grouping_never_reduces_size():
    gm, _ = _grid(stories=1)
    gm.calculate_trib_areas()
    gm.calculate_loads(floor_load_kn_m2=8.0)
    gm.optimize_column_sizes(concrete=M25)
    for c in gm.columns:
        assert c.width_nb >= 300 and c.depth_nb >= 450


# ------------------------------------------------- new findings (stage 2) --
def test_NEW_live_load_field_and_wind_direction():
    w = calculate_wind_load(WindZone("2"), 7.0, 18.0, 12.0, storey_height_m=3.5)
    # X-direction wind loads the face spanning the length (12 m)
    assert w.total_base_shear_x_kn / w.total_base_shear_y_kn == pytest.approx(12.0 / 18.0, rel=0.1)
    assert sum(w.storey_forces_x_kn) == pytest.approx(w.total_base_shear_x_kn)
    assert len(w.storey_forces_x_kn) == 2


def test_R17_implausible_insunits_falls_back_with_warning(tmp_path):
    from src.cad_loader import CADLoader
    # header says metres (ezdxf default) but geometry is in millimetres
    ld = CADLoader(_dxf(tmp_path, "wrong_units.dxf", 6, 1000.0))
    gm, _ = ld.load_grid_manager()
    assert gm.width_m == pytest.approx(6.0)
    assert any("implausible" in w for w in ld.load_warnings)


# ---------------------------------------------- footprint / slab panels ----
def test_panels_exclude_l_shape_notch_and_keep_enclosed_bays():
    gm = GridManager(width_m=8, length_m=8)
    gm.x_grid_lines, gm.y_grid_lines = [0, 4, 8], [0, 4, 8]
    pts = [(0, 0), (4, 0), (8, 0), (0, 4), (4, 4), (8, 4), (0, 8), (4, 8)]
    gm.columns = [Column(id=f"C{i}", x=x, y=y) for i, (x, y) in enumerate(pts)]
    gm.boundary_segments = [((0, 0), (8, 0)), ((8, 0), (8, 4)), ((8, 4), (4, 4)), ((4, 4), (4, 8)),
                            ((4, 8), (0, 8)), ((0, 8), (0, 0)), ((0, 4), (8, 4)), ((4, 0), (4, 4))]
    assert gm.footprint_area_m2() == pytest.approx(48.0)      # notch (3 corner columns) excluded

    # interior bay without corner columns but enclosed by walls/beams is kept
    gm2 = GridManager(width_m=8, length_m=8)
    gm2.x_grid_lines, gm2.y_grid_lines = [0, 4, 8], [0, 4, 8]
    gm2.columns = [Column(id=f"C{i}", x=x, y=y) for i, (x, y) in enumerate([(0, 0), (8, 0), (0, 8), (8, 8)])]
    gm2.boundary_segments = [((0, 0), (8, 0)), ((8, 0), (8, 8)), ((8, 8), (0, 8)), ((0, 8), (0, 0))]
    assert gm2.footprint_area_m2() == pytest.approx(64.0)


# ---------------------------------------------------------------- N13 -----
def test_N13_dead_load_uses_designed_slab_thickness():
    """Walkthrough building (8 x 8 m, 4 m panels): slabs are designed 185 mm
    (lx/26 + 30), the occupancy slab is 125 mm. Hand reference: the extra
    25 x (0.185 - 0.125) = 1.5 kN/m2 must reach beams, columns and seismic weight."""
    gm, beams = _grid(stories=2, w=8, l=8)
    # Mild exposure + NBC type 3 -> 20 mm slab cover (Table 16 / 16A), the cover the hand reference assumes
    res = run_design(gm, beams, DesignInputs(num_stories=2, seismic_zone="III", exposure="Mild", nbc_construction_type=3))
    gm = res.gm
    extra = 25 * (0.185 - 0.125)
    assert all(s.thickness_mm == 185 for s in gm.slab_schedule.values())
    # interior beam B_H_3: k = 2 x 4/3 (two square panels)
    b = next(x for x in res.beams if x.id == "B_H_3")
    # N46: the extra slab runs to the beam centre line, so b/2 x extra per adjacent panel is taken off the web
    def web_of(x, n_panels):
        return x.properties.width_mm / 1000 * ((x.properties.depth_mm / 1000 - 0.125) * 25 - n_panels * 0.5 * extra)
    web = web_of(b, 2)
    k = 8 / 3
    assert b.service_udl_kn_m == pytest.approx(k * (6.125 + extra) + web + k * 2.0, rel=1e-6)
    # interior column C5 at the base: 16 m2 x extra on each of 2 floors more than the 125 mm takedown
    c5 = next(c for c in gm.columns if c.id == "C5_L0")
    beam_webs = 4 * 0.5 * 4 * web                      # the four beams framing into C5 are interior (2 panels)
    col_sw = 0.3 * 0.45 * 3.5 * 25
    hand_dl = 16 * (4.625 + extra) + beam_webs + col_sw + 16 * (6.125 + extra) + beam_webs + col_sw
    assert c5.load_dl_kn == pytest.approx(hand_dl, rel=1e-6)
    # seismic weight: hand storey weights incl. the extra slab weight (64 m2 per level)
    def n_adj(x):                                       # beams on the interior grid line 4 m carry two panels
        mid = ((x.start_point.x + x.end_point.x) / 2, (x.start_point.y + x.end_point.y) / 2)
        on = mid[1] if abs(x.start_point.y - x.end_point.y) < 1e-6 else mid[0]
        return 2 if abs(on - 4.0) < 1e-6 else 1
    webs = sum(web_of(x, n_adj(x)) * 4 for x in res.beams)
    walls = sum(w.length_m * w.line_load_kn_m for w in gm.walls)
    cols = 9 * col_sw
    w1 = 64 * (6.125 + extra) + webs + walls + cols + 64 * 2.0 * 0.25
    w2 = 64 * (4.625 + extra) + webs + 0.5 * walls + 0.33 * walls + 0.5 * cols
    assert res.seismic_result.storey_weights_kn == pytest.approx([w1, w2], rel=1e-6)
