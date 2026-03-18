"""
Tests for Documentation, BIM, Site Inspection, and SHM Modules
"""

import pytest
import json
from src.documentation import DesignReportGenerator
from src.bim_interop import CobieExporter
from src.site_inspection import SiteInspectionManager
from src.shm_module import SHMPlanner

# -----------------------------------------------------------------------------
# Documentation Tests
# -----------------------------------------------------------------------------
def test_documentation_report_generation():
    doc = DesignReportGenerator(project_name="Test Project", engineer_name="John Doe")
    doc.validate_model(modal_mass_percent=95.0, freq_hz=1.5)
    doc.check_storey_drift("Storey 1", drift_mm=10.0, height_mm=3000.0)
    doc.add_sample_calculation("Beam B1", "B1", ["M = 50 kNm", "Ast = 500 mm2"], "IS 456")
    
    report = doc.generate_report()
    assert "STRUCTURAL DESIGN REPORT" in report
    assert "VALID" in report
    assert "Storey 1" in report
    assert "M = 50 kNm" in report

def test_documentation_validation_checks():
    doc = DesignReportGenerator("Invalid Project", "Jane Doe")
    res = doc.validate_model(modal_mass_percent=85.0, freq_hz=1.5)
    assert not res.is_valid
    assert len(res.warnings) > 0

# -----------------------------------------------------------------------------
# BIM Interop Tests (COBie)
# -----------------------------------------------------------------------------
def test_cobie_export():
    cobie = CobieExporter("Test BIM Project")
    cobie.add_type("C1_Column", "Column", "Rectangular Concrete Column")
    cobie.add_component("C1_01", "C1_Column", "Ground Floor", "Main Column")
    cobie.add_attribute("C1_01", "FireRating", "2hr", "Hours")
    cobie.add_coordinate("C1_01", 10.0, 20.0, 0.0)
    
    json_output = cobie.export_json()
    data = json.loads(json_output)
    
    assert data["project"] == "Test BIM Project"
    assert len(data["types"]) == 1
    assert len(data["components"]) == 1
    assert len(data["attributes"]) == 1
    assert len(data["coordinates"]) == 1
    assert data["coordinates"][0]["coordinate_x"] == 10.0

# -----------------------------------------------------------------------------
# Site Inspection Tests
# -----------------------------------------------------------------------------
def test_site_inspection_checklists():
    site = SiteInspectionManager("Test Site")
    checklist = site.generate_checklist("Pre_Pour")
    
    assert len(checklist) > 0
    assert any("stirrup hooks" in item.query for item in checklist)
    assert checklist[0].severity in ["Critical", "High"]

def test_defect_classification():
    site = SiteInspectionManager("Test Site")
    
    # Critical defect
    d1 = site.classify_defect(width_mm=5.0, pattern="Exposed Rebar", location="Beam Soffit", exposed_rebar=True)
    assert d1.severity == "Critical"
    assert "Spalling" in d1.defect_type
    
    # Shear crack
    d2 = site.classify_defect(width_mm=0.5, pattern="Diagonal Crack", location="Beam Support")
    assert d2.defect_type == "Shear Crack"
    assert "Overloading" in d2.probable_cause

# -----------------------------------------------------------------------------
# SHM Tests
# -----------------------------------------------------------------------------
def test_shm_sensor_planning():
    shm = SHMPlanner("Test SHM")
    shm.plan_sensor_deployment(roof_node_id="Node_100", critical_plastic_hinges=["Node_1", "Node_2"])
    
    assert len(shm.sensors) >= 3
    assert any(s.sensor_type == "Accelerometer" for s in shm.sensors)
    assert any(s.sensor_type == "Strain Gauge" for s in shm.sensors)

def test_shm_baseline_and_anomaly():
    shm = SHMPlanner("Test SHM")
    shm.create_baseline(freq_hz=2.0, stiffness=1000.0, drift_ratio=0.002)
    
    # Normal case
    status = shm.check_anomaly(1.95) # 2.5% drop
    assert "Normal" in status
    
    # Damage case
    status = shm.check_anomaly(1.80) # 10% drop
    assert "Stiffness Degradation" in status
