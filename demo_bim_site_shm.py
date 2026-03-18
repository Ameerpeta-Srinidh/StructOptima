"""
Demo: Documentation, BIM, Site Inspection, and SHM Integration

Simulates the post-design phase:
1. Generates Design Report with validation checks.
2. Exports COBie v3 data for Facility Management.
3. Generates Site Inspection Checklists.
4. Plans SHM Sensor Deployment.
"""

import json
from src.documentation import DesignReportGenerator
from src.bim_interop import CobieExporter
from src.site_inspection import SiteInspectionManager
from src.shm_module import SHMPlanner

def run_demo():
    print("="*80)
    print("POST-DESIGN & CONSTRUCTION HANDOVER DEMO")
    print("="*80)
    
    # -------------------------------------------------------------------------
    # 1. Structural Design Report
    # -------------------------------------------------------------------------
    print("\n1. STRUCTURAL DESIGN REPORT GENERATION")
    print("-" * 40)
    
    report_gen = DesignReportGenerator(project_name="Complex Villa G+2", engineer_name="Antigravity AI")
    
    # Simulate Analysis Results
    print("Validating Model...")
    val_res = report_gen.validate_model(modal_mass_percent=92.5, freq_hz=1.85)
    print(f"Validation Status: {'VALID' if val_res.is_valid else 'INVALID'}")
    
    print("Checking Drifts...")
    report_gen.check_storey_drift("Ground", 8.0, 3500.0)
    report_gen.check_storey_drift("First", 12.0, 3200.0)
    report_gen.check_storey_drift("Roof", 15.0, 3200.0) # 15/3200 = 0.0046 > 0.004 (Fail)
    
    print("Adding Sample Calculations...")
    report_gen.add_sample_calculation(
        "Beam B1 Flexure", "B1_G", 
        ["Mu = 150 kNm", "d = 450mm", "Ast_req = 980 mm2", "Provided 3-20#"], 
        "IS 456 Cl 21.1"
    )
    
    report_text = report_gen.generate_report()
    print("\n--- REPORT PREVIEW ---")
    print(report_text[:500] + "...\n(truncated)")
    
    # -------------------------------------------------------------------------
    # 2. COBie BIM Export
    # -------------------------------------------------------------------------
    print("\n2. COBie v3 DATA EXPORT")
    print("-" * 40)
    
    cobie = CobieExporter("Complex Villa G+2")
    
    # Definitions
    cobie.add_type("C400x400", "Column", "Rectangular RCC Column 400x400")
    cobie.add_type("B300x600", "Beam", "RCC Beam 300x600")
    
    # Instances
    cobie.add_component("C1_G_01", "C400x400", "Ground Floor", "Main Corner Column")
    cobie.add_attribute("C1_G_01", "ConcreteGrade", "M30", "Grade")
    cobie.add_attribute("C1_G_01", "ReinforcementRatio", "2.1", "%")
    cobie.add_coordinate("C1_G_01", 0.0, 0.0, 0.0)
    
    json_out = cobie.export_json()
    print(f"Generated COBie JSON ({len(json_out)} bytes)")
    
    # -------------------------------------------------------------------------
    # 3. Site Inspection
    # -------------------------------------------------------------------------
    print("\n3. SITE INSPECTION & QC")
    print("-" * 40)
    
    site = SiteInspectionManager("Complex Villa Site")
    checklist = site.generate_checklist("Pre_Pour")
    print(f"Generated Pre-Pour Checklist with {len(checklist)} items:")
    for item in checklist:
        print(f" [ ] {item.id}: {item.query} (Ref: {item.reference_code})")
        
    # Simulate Defect
    print("\nAnalyzing Site Photo (Simulated)...")
    defect = site.classify_defect(width_mm=0.8, pattern="Diagonal check near support", location="Beam End")
    print(f"Defect Detected: {defect.defect_type} (Severity: {defect.severity})")
    print(f"Action: {defect.remedial_action}")
    
    # -------------------------------------------------------------------------
    # 4. Structural Health Monitoring
    # -------------------------------------------------------------------------
    print("\n4. SHM & DIGITAL TWIN SETUP")
    print("-" * 40)
    
    shm = SHMPlanner("Complex Villa SHM")
    shm.plan_sensor_deployment("Node_Roof_Center", ["Node_Col_Base_1", "Node_Beam_Joint_5"])
    
    # Initial Baseline
    baseline = shm.create_baseline(freq_hz=1.85, stiffness=25000.0, drift_ratio=0.003)
    print(f"Baseline Established: Freq={baseline.fundamental_frequency_hz}Hz")
    
    # Simulate Monitoring
    print("Monitoring Stream...")
    print(f"T+1 Month: {shm.check_anomaly(1.84)}")
    print(f"T+1 Year:  {shm.check_anomaly(1.70)}") # Significant drop
    
    print("\n" + "="*80)
    print("DEMO SUCCESSFUL")
    print("="*80)

if __name__ == "__main__":
    run_demo()
