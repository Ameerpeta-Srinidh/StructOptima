"""Generate a sample report PDF for the demo download button."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from src.grid_manager import GridManager
from src.materials import Concrete
from src.foundation_eng import design_footing
from src.quantifier import Quantifier
from src.report_gen import ReportGenerator
from src.framing_logic import StructuralMember, Point, MemberProperties
from src.audit import StructuralAuditor

# Create a demo G+1 residential structure
gm = GridManager(width_m=12.0, length_m=9.0, num_stories=2, story_height_m=3.0)
gm.generate_grid()
beams = gm.generate_beams()

gm.calculate_trib_areas()
gm.calculate_loads(floor_load_kn_m2=8.0, wall_load_kn_m=12.0)

m_grade = Concrete.from_grade("M25")
gm.optimize_column_sizes(concrete=m_grade, fy=415.0)
gm.detail_columns(concrete=m_grade, fy=415.0)
gm.detail_beams(beams)
gm.detail_slabs()

# Foundation
level_0_cols = [c for c in gm.columns if c.level == 0]
footings = []
for col in level_0_cols:
    ft = design_footing(
        axial_load_kn=col.load_kn,
        sbc_kn_m2=200.0,
        column_width_mm=col.width_nb,
        column_depth_mm=col.depth_nb,
        concrete=m_grade,
    )
    footings.append(ft)

gm.footings = footings

# Create beams for all stories
all_beams = []
for i in range(2):
    for b in beams:
        copied = StructuralMember(
            id=f"{b.id}_L{i}",
            type="beam",
            start_point=Point(x=b.start_point.x, y=b.start_point.y, z=0),
            end_point=Point(x=b.end_point.x, y=b.end_point.y, z=0),
            properties=b.properties,
        )
        all_beams.append(copied)

# BOM
quantifier = Quantifier()
bom = quantifier.calculate_bom(gm.columns, all_beams, footings, grid_mgr=gm)

# Audit
auditor = StructuralAuditor(gm, all_beams, footings)
audit_results = auditor.run_audit()

# Generate report
reporter = ReportGenerator()
reporter.generate_report(
    "sample_report.pdf",
    gm,
    bom,
    audit_results=audit_results,
    math_breakdown=auditor.math_breakdown,
    project_name="StructOptima Sample Report — G+1 Residential Building (12m × 9m)",
    use_fly_ash=False,
)
print("sample_report.pdf generated successfully")
