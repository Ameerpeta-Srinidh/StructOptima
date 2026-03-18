"""
Site Inspection & Quality Control Module

Generates digital checklists for site engineers and classifies defects.
- Inspection Checklists (Pre-pour, Post-pour) based on IS 13920
- Defect Classification Logic (Simulated AI Vision)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
import json
from datetime import datetime

from .logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class InspectionCheckItem:
    id: str
    stage: str  # Pre-pour, Post-pour
    query: str
    expected_value: str
    reference_code: str
    severity: str = "Medium"
    status: str = "Pending"
    remarks: str = ""


@dataclass
class DefectAnalysis:
    defect_type: str
    severity: str
    pattern_description: str
    probable_cause: str
    remedial_action: str
    location_coords: Optional[Dict[str, float]] = None # {"lat": ..., "lon": ...} or {"x": ..., "y": ...}


class SiteInspectionManager:
    
    def __init__(self, project_name: str):
        self.project_name = project_name
        self.checklists: Dict[str, List[InspectionCheckItem]] = {}
        self.defects: List[DefectAnalysis] = []

    def generate_checklist(self, stage: str = "Pre_Pour") -> List[InspectionCheckItem]:
        """Generate mandatory checklist based on construction stage."""
        items = []
        
        if stage == "Pre_Pour":
            # IS 13920 / IS 456 Checks
            items.append(InspectionCheckItem(
                id="CHK_01", stage=stage,
                query="Are stirrup hooks bent at 135° with 65mm extension?",
                expected_value="Yes", reference_code="IS 13920 Cl 3.5", severity="Critical"
            ))
            items.append(InspectionCheckItem(
                id="CHK_02", stage=stage,
                query="Is lap splice location at mid-height (cols) / mid-span (beams)?",
                expected_value="Yes", reference_code="IS 13920 Cl 7.3", severity="Critical"
            ))
            items.append(InspectionCheckItem(
                id="CHK_03", stage=stage,
                query="Are cover blocks placed securely?",
                expected_value="Yes", reference_code="IS 456 Cl 26.4", severity="High"
            ))
            items.append(InspectionCheckItem(
                id="CHK_04", stage=stage,
                query="Is formwork watertight and cleaned?",
                expected_value="Yes", reference_code="IS 456 Cl 11.1", severity="High"
            ))
            
        elif stage == "Post_Pour":
            items.append(InspectionCheckItem(
                id="CHK_05", stage=stage,
                query="Is honeycombing visible on surface?",
                expected_value="No", reference_code="IS 456 Cl 14", severity="High"
            ))
            items.append(InspectionCheckItem(
                id="CHK_06", stage=stage,
                query="Are shrinkage cracks visible?",
                expected_value="No (<0.3mm)", reference_code="IS 456", severity="Medium"
            ))
            items.append(InspectionCheckItem(
                id="CHK_07", stage=stage,
                query="Checking for verticality/plumb?",
                expected_value="< H/500", reference_code="IS 456", severity="Medium"
            ))
            
        self.checklists[stage] = items
        return items

    def classify_defect(
        self, 
        width_mm: float, 
        pattern: str, 
        location: str,
        exposed_rebar: bool = False,
        coordinates: Optional[Dict[str, float]] = None
    ) -> DefectAnalysis:
        """
        Classify defect based on visual characteristics (Simulated AI Logic).
        """
        severity = "Low"
        defect_type = "Unknown"
        cause = "Unknown"
        action = "Monitor"

        if exposed_rebar:
            severity = "Critical"
            defect_type = "Spalling / Corrosion"
            cause = "Insufficient cover or carbonation"
            action = "Immediate structural repair (grouting/jacketing)"
            
        elif "honeycomb" in pattern.lower():
            defect_type = "Honeycombing"
            severity = "High" if width_mm > 50 else "Medium"
            cause = "Poor compaction or grout leakage"
            action = "Chip off and pressure grout"
            
        elif width_mm > 0.3:
            severity = "High"
            # Improved logic: Check pattern AND location for keywords
            p_low = pattern.lower()
            l_low = location.lower()
            
            if "diagonal" in p_low or "shear" in p_low or "shear" in l_low:
                defect_type = "Shear Crack"
                cause = "Shear capacity exceeded (Overloading)"
                action = "Structural strengthening (FRP/Epoxy injection)"
            elif "vertical" in p_low and ("mid-span" in l_low or "flexure" in l_low):
                defect_type = "Flexural Crack"
                cause = "Bending moment exceeded"
                action = "Epoxy injection"
        else:
            # Fine cracks
            severity = "Low"
            defect_type = "Shrinkage Crack"
            cause = "Rapid moisture loss during curing"
            action = "Surface sealing"

        analysis = DefectAnalysis(
            defect_type=defect_type,
            severity=severity,
            pattern_description=pattern,
            probable_cause=cause,
            remedial_action=action,
            location_coords=coordinates
        )
        self.defects.append(analysis)
        return analysis

    def generate_qr_code(self, element_id: str) -> str:
        """
        Simulates generating a QR code URL/String for an element.
        In real app, returns image bytes or URL.
        """
        return f"https://project-phoenix.app/bim/{element_id}?ver=latest"

    def annotate_site_photo(self, photo_name: str, annotation_type: str) -> str:
        """
        Simulates drawing an annotation on an image logic.
        Returns a status message.
        """
        return f"Annotated '{photo_name}' with {annotation_type} marker."

    def get_defect_map_data(self) -> List[Dict]:
        """
        Returns data for Geo-Tag map visualization.
        """
        map_data = []
        for d in self.defects:
            if d.location_coords:
                map_data.append({
                    "lat": d.location_coords.get("lat"),
                    "lon": d.location_coords.get("lon"),
                    "type": d.defect_type,
                    "severity": d.severity
                })
        return map_data

    def to_json(self) -> str:
        return json.dumps({
            "project": self.project_name,
            "checklists": {k: [i.__dict__ for i in v] for k, v in self.checklists.items()},
            "defects": [d.__dict__ for d in self.defects]
        }, indent=2)
