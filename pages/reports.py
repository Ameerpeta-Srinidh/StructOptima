"""Reports: PDF reports, Excel data and the complete export package. Files are generated when downloaded."""
import datetime
import io
import os
import tempfile
import zipfile

import streamlit as st

from src.bbs_report import BBSReportGenerator
from src.dxf_exporter import ProfessionalDXFExporter, StructuralDXFExporter
from src.exporters import ExcelExporter
from src.report_gen import ReportGenerator
from src.ui_components import page_title, require_results

require_results()
S = st.session_state
res = S['design_results']
gm = res.gm
all_beams = S.get('all_beams', [])
project_name = S.get('project_name', "PROPOSED BUILDING")
engineer_name = S.get('engineer_name', "STRUCTURAL ENGINEER")
num_stories = gm.num_stories
footings = S.get('footings', [])

# Ensure walls are present on grid manager for all schedules and takeoff reports
ReportGenerator._ensure_walls(gm)

page_title("Reports", "Every report states the design status and lists the checks StructOptima does not perform. "
                      "Files are generated when you click download.")
if res.status == "FAIL":
    st.error("Design status FAIL — reports are generated for review only and list the failing items. "
             "NOT FOR CONSTRUCTION.", icon=":material/cancel:")
elif res.status == "WARN":
    st.warning("Design status WARN — reports list the items needing engineering review. NOT FOR CONSTRUCTION.",
               icon=":material/warning:")
else:
    st.info("PASS for the implemented checks only — NOT VERIFIED. Reports remain PRELIMINARY and require independent "
            "verification.")


def _file(write, suffix=".dxf") -> bytes:
    """Run a generator that writes to a path; return the bytes. Never writes to the working directory (N10)."""
    with tempfile.TemporaryDirectory(prefix="structoptima_rep_") as d:
        path = os.path.join(d, "out" + suffix)
        write(path)
        with open(path, "rb") as fh:
            return fh.read()


def _pdf(write) -> bytes:
    return _file(write, ".pdf")


def write_design_report(path):
    ReportGenerator().generate_report(
        path, gm, res.bom, audit_results=res.audit_results, math_breakdown=res.auditor_math,
        project_name=project_name, use_fly_ash=S.get('use_fly_ash', False), seismic_result=res.seismic_result,
        wind_result=res.wind_result, stab_checks=res.stab_checks, stab_summary=res.stab_summary, all_beams=all_beams,
        conc_grade=S.get('conc_grade', 'M25'), live_load=S.get('live_load', 0), building_weight=res.building_weight,
        seismic_zone=S.get('seismic_zone'), footings=footings, design_status=res.status,
        design_failures=res.failures, design_messages=res.messages, approved_mix=S.get('approved_mix'),
        drift_results=getattr(res, 'drift_results', None),
        checks_not_performed=getattr(res, 'checks_not_performed', None))


def write_bbs(path):
    BBSReportGenerator().generate_bbs_report(path, res.project_bbs, "Bar Bending Schedule")


def write_audit(path):
    ReportGenerator().generate_audit_report(path, gm, res.audit_results, res.auditor_math)


def write_schedules(path):
    ReportGenerator().generate_schedule_report(path, gm, footings=footings, project_name=project_name)


def write_masonry(path):
    ReportGenerator().generate_masonry_report(path, gm, project_name=project_name)


def write_floor(level):
    return lambda path: ReportGenerator().generate_floor_report(path, gm, level)


def excel_bytes():
    return ExcelExporter.export_to_excel(gm, all_beams, res.bom)


REPORTS = [
    ("Structural design report", "Inputs, analysis, member design, checks, failures and checks not performed.",
     write_design_report, "Structural_Design_Report.pdf", True),
    ("Bar bending schedule", "Bar marks, shapes, cut lengths and weights for one typical floor.",
     write_bbs, "BBS_Report.pdf", res.project_bbs is not None),
    ("Audit re-check", "Consistency screen of the designed members (not independent verification).",
     write_audit, "Audit_Report.pdf", bool(res.audit_results and res.auditor_math)),
    ("Design & finishes schedules", "Column, beam, slab and footing schedules with finishes.",
     write_schedules, "Design_and_Finishes_Schedules.pdf", True),
    ("Masonry, plaster & paint BOQ", "Brickwork, mortar, plaster and paint quantities.",
     write_masonry, "Masonry_Plaster_Paint_Takeoff.pdf", True),
]


def zip_package() -> bytes:
    """All reports, Excel data and DXF plans. A part that fails is listed in _NOT_INCLUDED.txt, never dropped silently."""
    buf = io.BytesIO()
    missing = []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        def add(name, make):
            try:
                z.writestr(name, make())
            except Exception as e:
                missing.append(f"{name}: {e}")
        for title, _desc, write, fname, available in REPORTS:
            if available:
                add(fname, lambda w=write: _pdf(w))
        for lvl in range(num_stories):
            add(f"Floor_{lvl}_Report.pdf", lambda lvl=lvl: _pdf(write_floor(lvl)))
        add("Structural_Data.xlsx", excel_bytes)
        info = {"project_name": project_name, "engineer": engineer_name,
                "date": datetime.datetime.now().strftime("%d-%m-%Y"), "sheet": "S-1", "scale": "1:100"}
        add("Structural_Plan.dxf", lambda: _file(lambda p: StructuralDXFExporter.export_structural_dxf(gm, all_beams, p)))
        add("Foundation_Plan_Professional.dxf", lambda: _file(
            lambda p: ProfessionalDXFExporter(gm, all_beams, info, drawing_type="FOUNDATION").export(p)))
        add("Beam_Schedule.dxf", lambda: _file(
            lambda p: ProfessionalDXFExporter(gm, all_beams, info, drawing_type="FOUNDATION").export_beam_schedule_table(p)))
        if missing:
            z.writestr("_NOT_INCLUDED.txt", "These parts could not be generated and are NOT in this package:\n\n"
                       + "\n".join(missing) + "\n")
    return buf.getvalue()


c_pkg = st.container(border=True)
with c_pkg:
    st.markdown("#### Complete export package")
    st.caption("All PDF reports, floor-wise reports, Excel data and DXF plans in one ZIP.")
    st.download_button("Download package (ZIP)", zip_package, f"{project_name.replace(' ', '_')}_Export_Package.zip",
                       "application/zip", type="primary", key="dl_zip", icon=":material/folder_zip:")

st.markdown("#### Individual reports")
grid = st.columns(3)
for i, (title, desc, write, fname, available) in enumerate(REPORTS):
    with grid[i % 3].container(border=True, height="stretch"):
        st.markdown(f"**{title}**")
        st.caption(desc)
        if available:
            st.download_button("Download PDF", lambda w=write: _pdf(w), fname, "application/pdf", key=f"dl_{fname}",
                               icon=":material/picture_as_pdf:")
        else:
            st.caption(":orange[Not available for this design.]")
with grid[len(REPORTS) % 3].container(border=True, height="stretch"):
    st.markdown("**Excel data**")
    st.caption("Member data, schedules and quantities as a spreadsheet.")
    st.download_button("Download XLSX", excel_bytes, "Structural_Data.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_excel_data",
                       icon=":material/table_view:")

st.markdown("#### Floor-wise reports")
with st.container(horizontal=True):
    for lvl in range(num_stories):
        st.download_button(f"Floor {lvl}", lambda lvl=lvl: _pdf(write_floor(lvl)), f"Floor_{lvl}_Report.pdf",
                           "application/pdf", key=f"pdf_floor_{lvl}", icon=":material/picture_as_pdf:")
