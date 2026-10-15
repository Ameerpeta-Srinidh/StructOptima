"""
Tests for Documentation, BIM, Site Inspection, and SHM Modules
"""

import pytest
import json
from src.documentation import calculation_summary
from src.bim_interop import CobieExporter
from src.site_inspection import DefectRecord, SiteInspectionManager
from src.shm_module import SHMPlanner

# -----------------------------------------------------------------------------
# Documentation: the calculation summary uses only design results (N14)
# -----------------------------------------------------------------------------
@pytest.fixture(scope="module")
def design():
    import logging
    logging.disable(logging.CRITICAL)
    from src.design_pipeline import DesignInputs, run_design
    from src.grid_manager import GridManager
    gm = GridManager(width_m=12.0, length_m=9.0, num_stories=2, story_height_m=3.2)
    gm.generate_grid()
    return run_design(gm, gm.generate_beams(), DesignInputs(num_stories=2, story_height_m=3.2, max_iterations=3))


def test_calculation_summary_reports_computed_values_only(design):
    text = calculation_summary(design, "Test Project", "E")
    assert f"base shear Vb = {design.seismic_result.base_shear_kn:.1f} kN" in text
    for r in design.drift_results:
        assert f"{r['Drift (mm)']:>9.2f}" in text
    assert "modal mass participation: NOT COMPUTED" in text
    assert "NOT VERIFIED" in text and all(c in text for c in design.checks_not_performed)

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
    assert any("hooks" in item.query for item in checklist)
    assert checklist[0].severity in ["Critical", "High"]

def test_defect_log_records_observations_without_diagnosis():
    site = SiteInspectionManager("Test Site")
    site.record_defect(DefectRecord("C1", "Crack", "Column top", width_mm=0.4, inspector="A"))
    site.record_defect(DefectRecord("B2", "Honeycombing", "Soffit", lat=17.4, lon=78.4))
    assert len(site.defects) == 2 and all(d.review_status == "Awaiting engineer review" for d in site.defects)
    assert site.get_defect_map_data() == [{"lat": 17.4, "lon": 78.4, "type": "Honeycombing", "member": "B2"}]
    assert len(site.defects_csv().splitlines()) == 3
    assert not hasattr(site, "classify_defect")
    with pytest.raises(ValueError):
        site.record_defect(DefectRecord("", "Crack", "x"))

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
