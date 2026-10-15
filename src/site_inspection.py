"""
Site inspection records (checklists and a defect log).

Checklist items are prompts for the inspecting engineer; the referenced
standards are named without clause numbers (clauses not verified - see
docs/engineering/standards-register.md).  Defects are recorded exactly as
observed; StructOptima does not diagnose causes or prescribe repairs (the
former keyword-based "classification" was removed, gap analysis N15).
"""

from __future__ import annotations

import csv
import io
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Dict, List, Optional

from .logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class InspectionCheckItem:
    id: str
    stage: str  # Pre_Pour, Post_Pour
    query: str
    expected_value: str
    reference_code: str
    severity: str = "Medium"
    status: str = "Pending"     # Pending | Pass | Fail | N/A
    remarks: str = ""


@dataclass
class DefectRecord:
    member_id: str
    defect_type: str            # as observed, e.g. crack, honeycombing, exposed bar
    location: str
    width_mm: Optional[float] = None
    length_mm: Optional[float] = None
    exposed_rebar: bool = False
    observed_on: str = field(default_factory=lambda: date.today().isoformat())
    inspector: str = ""
    notes: str = ""
    lat: Optional[float] = None
    lon: Optional[float] = None
    review_status: str = "Awaiting engineer review"


class SiteInspectionManager:

    def __init__(self, project_name: str):
        self.project_name = project_name
        self.checklists: Dict[str, List[InspectionCheckItem]] = {}
        self.defects: List[DefectRecord] = []

    def generate_checklist(self, stage: str = "Pre_Pour") -> List[InspectionCheckItem]:
        """Inspection prompts for a construction stage."""
        items = []
        if stage == "Pre_Pour":
            items += [
                InspectionCheckItem("CHK_01", stage, "Are stirrup / tie hooks bent to the specified angle and extension?",
                                    "As per drawings", "IS 13920 / IS 456 (detailing)", "Critical"),
                InspectionCheckItem("CHK_02", stage, "Are lap splices at the locations and lengths shown on the drawings?",
                                    "As per drawings", "IS 456 / IS 13920 (laps)", "Critical"),
                InspectionCheckItem("CHK_03", stage, "Are cover blocks of the specified cover placed securely?",
                                    "Specified cover", "IS 456 (nominal cover)", "High"),
                InspectionCheckItem("CHK_04", stage, "Is formwork tight, propped, clean and to line and level?",
                                    "Yes", "IS 456 (formwork)", "High"),
                InspectionCheckItem("CHK_05", stage, "Bar count and diameters match the schedule for this member?",
                                    "As per schedule", "Issued drawings / BBS", "Critical"),
            ]
        elif stage == "Post_Pour":
            items += [
                InspectionCheckItem("CHK_06", stage, "Is honeycombing visible on the surface?", "No",
                                    "IS 456 (workmanship)", "High"),
                InspectionCheckItem("CHK_07", stage, "Are cracks visible? (record width and length in the defect log)",
                                    "No", "IS 456", "Medium"),
                InspectionCheckItem("CHK_08", stage, "Is the member plumb / to line within the specified tolerance?",
                                    "Within specified tolerance", "Project specification", "Medium"),
                InspectionCheckItem("CHK_09", stage, "Have cube specimens been cast and labelled for this pour?",
                                    "Yes", "IS 456 / IS 516 (sampling and testing)", "High"),
            ]
        self.checklists[stage] = items
        return items

    def record_defect(self, record: DefectRecord) -> DefectRecord:
        if not record.member_id or not record.defect_type:
            raise ValueError("member and defect type are required")
        if record.width_mm is not None and record.width_mm < 0:
            raise ValueError("width cannot be negative")
        self.defects.append(record)
        return record

    def get_defect_map_data(self) -> List[Dict]:
        """Map points for defects recorded with coordinates (none are invented)."""
        return [{"lat": d.lat, "lon": d.lon, "type": d.defect_type, "member": d.member_id}
                for d in self.defects if d.lat is not None and d.lon is not None]

    def defects_csv(self) -> str:
        buf = io.StringIO()
        fields = list(DefectRecord.__dataclass_fields__)
        w = csv.DictWriter(buf, fieldnames=fields)
        w.writeheader()
        for d in self.defects:
            w.writerow(asdict(d))
        return buf.getvalue()

    @staticmethod
    def checklist_csv(items: List[InspectionCheckItem], member: str, inspector: str) -> str:
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["Member", "Inspector", "Date", "Id", "Stage", "Check", "Expected", "Reference", "Severity", "Result", "Remarks"])
        for i in items:
            w.writerow([member, inspector, date.today().isoformat(), i.id, i.stage, i.query, i.expected_value,
                        i.reference_code, i.severity, i.status, i.remarks])
        return buf.getvalue()
