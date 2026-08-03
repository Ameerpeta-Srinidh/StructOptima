import streamlit as st
import sys, os, io, zipfile, tempfile
import datetime

sys.path.append(os.path.join(os.getcwd(), 'src'))
from src.ui_components import inject_css, render_project_header, render_section_header, render_no_analysis_warning, render_is_code_reference
from src.report_gen import ReportGenerator
from src.bbs_report import BBSReportGenerator
from src.exporters import ExcelExporter
from src.dxf_exporter import StructuralDXFExporter, ProfessionalDXFExporter

st.set_page_config(page_title='StructOptima — Reports', layout='wide', page_icon='📄')
inject_css()
render_project_header()
render_is_code_reference()

if not st.session_state.get('analysis_done'):
    render_no_analysis_warning()
    st.stop()

# Get required data from session state
gm = st.session_state.get('gm')
all_beams = st.session_state.get('beams')
if not all_beams:
    all_beams = st.session_state.get('all_beams', [])
bom = st.session_state.get('bom')
audit_results = st.session_state.get('audit_results')
auditor_math = st.session_state.get('auditor_math')
project_bbs = st.session_state.get('project_bbs')
project_name = st.session_state.get('project_name', "PROPOSED BUILDING")
engineer_name = st.session_state.get('engineer_name', "STRUCTURAL ENGINEER")
use_fly_ash = st.session_state.get('use_fly_ash', False)
num_stories = gm.num_stories if gm else 1

if not gm or not all_beams:
    st.error("Missing critical engineering data. Please re-run the analysis.")
    st.stop()

st.markdown("### 📦 Export Package")

# Ensure required attributes for reports
if not hasattr(gm, 'footings'):
    gm.footings = st.session_state.get('footings', [])
if not hasattr(gm, 'project_name'):
    gm.project_name = project_name

def generate_zip_package():
    zip_buffer = io.BytesIO()
    with tempfile.TemporaryDirectory() as tmpdirname:
        reporter = ReportGenerator()
        bbs_reporter = BBSReportGenerator()
        
        # 1. Complete Report
        report_file = os.path.join(tmpdirname, "Structural_Design_Report.pdf")
        reporter.generate_report(
            report_file, 
            gm, 
            bom, 
            audit_results=audit_results, 
            math_breakdown=auditor_math,
            project_name=project_name,
            use_fly_ash=use_fly_ash
        )
        
        # 2. BBS Report
        if project_bbs:
            bbs_file = os.path.join(tmpdirname, "BBS_Report.pdf")
            bbs_reporter.generate_bbs_report(bbs_file, project_bbs, "Bar Bending Schedule")
            
        # 3. Audit Report
        if audit_results and auditor_math:
            audit_file = os.path.join(tmpdirname, "Audit_Report.pdf")
            reporter.generate_audit_report(audit_file, gm, audit_results, auditor_math)
            
        # 4. Floor-wise Reports
        for lvl in range(num_stories):
            floor_pdf = os.path.join(tmpdirname, f"Floor_{lvl}_Report.pdf")
            reporter.generate_floor_report(floor_pdf, gm, lvl)
            
        # 5. Excel Data
        xls_data = ExcelExporter.export_to_excel(gm, all_beams, bom)
        xls_file = os.path.join(tmpdirname, "Structural_Data.xlsx")
        with open(xls_file, "wb") as f:
            f.write(xls_data)
            
        # 6. DXF Plans
        dxf_plan = os.path.join(tmpdirname, "Structural_Plan.dxf")
        StructuralDXFExporter.export_structural_dxf(gm, all_beams, dxf_plan)
        
        design_info = {
            "project_name": project_name,
            "engineer": engineer_name,
            "date": datetime.datetime.now().strftime("%d-%m-%Y"),
            "sheet": "S-1",
            "scale": "1:100"
        }
        
        try:
            prof_exporter = ProfessionalDXFExporter(gm, all_beams, design_info, drawing_type="FOUNDATION")
            
            prof_dxf = os.path.join(tmpdirname, "Foundation_Plan_Professional.dxf")
            prof_exporter.export(prof_dxf)
            
            beam_sched = os.path.join(tmpdirname, "Beam_Schedule.dxf")
            prof_exporter.export_beam_schedule_table(beam_sched)
        except Exception:
            pass
            
        # Create ZIP
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
            for root, dirs, files in os.walk(tmpdirname):
                for file in files:
                    file_path = os.path.join(root, file)
                    zip_file.write(file_path, file)
                    
    zip_buffer.seek(0)
    return zip_buffer.getvalue()

st.markdown("""
<style>
div.stButton > button[kind="primary"] {
    width: 100%;
    padding: 1.5rem;
    font-size: 1.2rem;
    font-weight: bold;
    background: linear-gradient(135deg, #2e7d32 0%, #1b5e20 100%);
    border: none;
    box-shadow: 0 4px 15px rgba(0,0,0,0.1);
}
</style>
""", unsafe_allow_html=True)

with st.spinner("Preparing full export package..."):
    zip_data = generate_zip_package()
    st.download_button(
        label="📦 Download Complete Package (ZIP)",
        data=zip_data,
        file_name=f"{project_name.replace(' ', '_')}_Export_Package.zip",
        mime="application/zip",
        type="primary"
    )

st.markdown("---")
st.subheader("📄 Individual Reports")

reporter = ReportGenerator()
bbs_reporter = BBSReportGenerator()

col1, col2, col3, col4 = st.columns(4)

with col1:
    with st.spinner("Generating Report..."):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            reporter.generate_report(
                tmp.name, gm, bom, audit_results=audit_results, 
                math_breakdown=auditor_math, project_name=project_name, use_fly_ash=use_fly_ash
            )
        with open(tmp.name, "rb") as f:
            st.download_button("📑 Complete Report", f.read(), "Structural_Design_Report.pdf", "application/pdf")

with col2:
    if project_bbs:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            bbs_reporter.generate_bbs_report(tmp.name, project_bbs, "Bar Bending Schedule")
        with open(tmp.name, "rb") as f:
            st.download_button("🔩 BBS Report", f.read(), "BBS_Report.pdf", "application/pdf")

with col3:
    if audit_results and auditor_math:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            reporter.generate_audit_report(tmp.name, gm, audit_results, auditor_math)
        with open(tmp.name, "rb") as f:
            st.download_button("✅ Audit Report", f.read(), "Audit_Report.pdf", "application/pdf")

with col4:
    xls_data = ExcelExporter.export_to_excel(gm, all_beams, bom)
    st.download_button("📊 Excel Data", xls_data, "Structural_Data.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

st.markdown("---")
st.subheader("🏢 Floor-wise Reports")

floor_cols = st.columns(min(num_stories, 4))
for lvl in range(num_stories):
    col_idx = lvl % 4
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        reporter.generate_floor_report(tmp.name, gm, lvl)
    with open(tmp.name, "rb") as f:
        floor_cols[col_idx].download_button(
            label=f"📄 Floor {lvl} Report",
            data=f.read(),
            file_name=f"Floor_{lvl}_Report.pdf",
            mime="application/pdf",
            key=f"pdf_floor_{lvl}"
        )
