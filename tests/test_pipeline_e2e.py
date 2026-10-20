"""
End-to-end tests of the production pipeline (src/design_pipeline.py) and its
outputs.  Files are written only to pytest's tmp_path.  These tests show that
the workflow runs and that outputs are internally consistent; they do NOT
establish engineering correctness (see docs/verification/verification-matrix.md).
"""
import glob
import logging
import os

import pytest

from src.design_pipeline import DesignInputs, run_design
from src.grid_manager import GridManager
from src.wind_load import TerrainCategory, WindZone

logging.disable(logging.CRITICAL)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _manual(stories=2, w=18.0, l=12.0, **kw):
    gm = GridManager(width_m=w, length_m=l, num_stories=stories, story_height_m=3.5)
    gm.cantilever_dirs = kw.pop("cant", [])
    gm.generate_grid()
    beams = gm.generate_beams()
    inputs = DesignInputs(num_stories=stories, wind_zone=WindZone("2"), terrain_category=TerrainCategory("2"), **kw)
    return run_design(gm, beams, inputs)


@pytest.fixture(scope="module")
def res():
    return _manual(add_staircase=True)


def test_pipeline_produces_consistent_outputs(res):
    gm = res.gm
    assert res.analysis_summary.frames_solved == res.analysis_summary.frames_total > 0
    assert set(gm.rebar_schedule) == {c.id for c in gm.columns}
    assert len(gm.beam_schedule) == len(res.beams)
    assert len(res.footings) == len([c for c in gm.columns if c.level == 0])
    assert res.bom.total_steel_weight_kg > 0 and res.bom.total_concrete_vol_m3 > 0
    assert res.status in ("PASS", "WARN", "FAIL")
    order = {"PASS": 0, "WARN": 1, "FAIL": 2}
    worst = max([f["Status"] for f in res.failures] + ["PASS"], key=order.get)
    assert order[res.status] >= order[worst]
    assert res.converged


def test_every_column_has_combinations_including_lateral(res):
    for c in res.gm.columns:
        names = {f[0] for f in c.design_forces}
        assert any("EQx" in n for n in names) and any("WLy" in n for n in names)


def test_staircase_void_excluded_from_slabs_but_not_regularity(res):
    gm = res.gm
    assert gm.void_bays
    assert len(gm.slab_panels()) == len(gm.slab_panels(include_voids=True)) - len(gm.void_bays)
    # a stair void is not a plan irregularity (the Zone III method failure itself is IS 1893 7.7.1)
    assert not any(f["Type"] == "Seismic method" and "irregular" in f["Issue"] for f in res.failures)


@pytest.mark.parametrize("zone,occupancy", [("II", "Residential"), ("IV", "Assembly Hall"), ("V", "Commercial (Office)")])
def test_pipeline_runs_for_zones_and_occupancies(zone, occupancy):
    r = _manual(stories=3, seismic_zone=zone, building_type_name=occupancy)
    assert r.analysis_summary.ok
    assert r.seismic_result.parameters.zone.value == zone


def test_cantilevers_and_pinned_bases():
    r = _manual(stories=1, cant=["left", "top"], fixed_base=False)
    assert any(b.id.startswith("BC_") for b in r.beams)
    assert r.analysis_summary.ok


def test_smrf_selection_marks_scwb_failures_as_fail():
    r = _manual(stories=3, seismic_zone="IV", structural_system="SMRF")
    assert r.seismic_result.parameters.response_reduction == 5.0
    for f in r.failures:
        if f["Type"] in ("SCWB", "Joint shear"):
            assert f["Status"] == "FAIL"


def test_reports_and_exports_are_generated(res, tmp_path):
    from src.report_gen import ReportGenerator
    from src.bbs_report import BBSReportGenerator
    from src.exporters import ExcelExporter
    rg = ReportGenerator()
    pdf = tmp_path / "report.pdf"
    rg.generate_report(str(pdf), res.gm, res.bom, audit_results=res.audit_results, math_breakdown=res.auditor_math,
                       seismic_result=res.seismic_result, wind_result=res.wind_result, stab_checks=res.stab_checks,
                       stab_summary=res.stab_summary, all_beams=res.all_beams, building_weight=res.building_weight,
                       footings=res.footings, design_status=res.status, design_failures=res.failures,
                       design_messages=res.messages)
    assert pdf.stat().st_size > 5000
    rg.generate_audit_report(str(tmp_path / "audit.pdf"), res.gm, res.audit_results, res.auditor_math)
    rg.generate_schedule_report(str(tmp_path / "sched.pdf"), res.gm, footings=res.footings)
    BBSReportGenerator().generate_bbs_report(str(tmp_path / "bbs.pdf"), res.project_bbs, "BBS")
    xl = ExcelExporter.export_to_excel(res.gm, res.all_beams, res.bom, res.footings)
    assert len(xl) > 1000
    for name in ("audit.pdf", "sched.pdf", "bbs.pdf"):
        assert (tmp_path / name).stat().st_size > 1000


@pytest.mark.parametrize("path", sorted(glob.glob(os.path.join(ROOT, "samples", "sample_design.dxf")) +
                                        glob.glob(os.path.join(ROOT, "samples", "real_world", "*.dxf"))[:3]))
def test_cad_files_through_pipeline(path):
    from src.cad_loader import CADLoader
    ld = CADLoader(path)
    gm, beams = ld.load_grid_manager(auto_frame=True, story_height_m=3.2, num_stories=2)
    gm.columns = gm.stack_columns([c for c in gm.columns if c.level == 0], 2, 3.2)
    r = run_design(gm, beams, DesignInputs(num_stories=2, story_height_m=3.2, max_iterations=4))
    assert r.gm.rebar_schedule and r.gm.beam_schedule
    assert r.analysis_summary.frames_total > 0


def test_ifc_through_pipeline(tmp_path):
    pytest.importorskip("ifcopenshell")
    from tests.ifc_fixture import build_frame_ifc
    from src.bim_loader import BIMLoader
    p = tmp_path / "f.ifc"
    build_frame_ifc(str(p))
    gm, beams = BIMLoader(str(p)).load_grid_manager()
    r = run_design(gm, beams, DesignInputs(num_stories=gm.num_stories, story_height_m=gm.story_height_m))
    assert r.analysis_summary.ok and r.gm.rebar_schedule


def test_cli_main(tmp_path, monkeypatch):
    import main as cli
    monkeypatch.setattr(cli, "setup_logging", lambda *a, **k: None)   # avoid writing a log file
    out = tmp_path / "cli.pdf"
    code = cli.main(["--width", "9", "--length", "8", "--stories", "1", "--zone", "II", "--report", str(out)])
    assert code in (0, 1)
    assert out.stat().st_size > 5000
