import sys
import os
import logging

sys.path.append(os.path.join(os.getcwd(), 'src'))

from src.grid_manager import GridManager
from src.materials import Concrete
from src.framing_logic import MemberProperties, StructuralMember, Point
from src.quantifier import Quantifier
from src.report_gen import ReportGenerator
from src.foundation_eng import design_footing
from src.logging_config import setup_logging, get_logger

import argparse
from src.cad_loader import CADLoader
from src.risk_management import BlackBoxRiskManager
from src.bbs_module import format_project_summary, generate_project_bbs

# Initialize logging
setup_logging()
logger = get_logger(__name__)

def generate_beams_for_grid(grid_mgr: GridManager) -> list[StructuralMember]:
    # Re-using logic from Phase 2
    beams = []
    beam_count = 0
    
    # Horizontal
    for y in grid_mgr.y_grid_lines:
        for i in range(len(grid_mgr.x_grid_lines) - 1):
            x1 = grid_mgr.x_grid_lines[i]
            x2 = grid_mgr.x_grid_lines[i+1]
            beam_count += 1
            beams.append(StructuralMember(
                id=f"B_H_{beam_count}",
                type="beam",
                start_point=Point(x=x1, y=y),
                end_point=Point(x=x2, y=y),
                properties=MemberProperties(width_mm=300, depth_mm=600) # Default
            ))
            
    # Vertical
    for x in grid_mgr.x_grid_lines:
        for i in range(len(grid_mgr.y_grid_lines) - 1):
            y1 = grid_mgr.y_grid_lines[i]
            y2 = grid_mgr.y_grid_lines[i+1]
            beam_count += 1
            beams.append(StructuralMember(
                id=f"B_V_{beam_count}",
                type="beam",
                start_point=Point(x=x, y=y1),
                end_point=Point(x=x, y=y2),
                properties=MemberProperties(width_mm=300, depth_mm=600)
            ))
    return beams

def main():
    parser = argparse.ArgumentParser(description="Automated Structural Design Engine")
    parser.add_argument('--cad', type=str, help="Path to DXF file for structural geometry")
    parser.add_argument('--auto-frame', action='store_true', help="Automatically generate structure from architectural walls (WALLS layer)")
    args = parser.parse_args()

    logger.info("=== AUTOMATED STRUCTURAL DESIGN ENGINE ===")
    
    # 1. Initialization
    width = 18.0
    length = 12.0
    load_kn_m2 = 50.0
    sbc = 200.0  # kN/m2
    
    gm = None
    beams = []
    
    if args.cad:
        logger.info("Loading geometry from CAD: %s", args.cad)
        try:
            loader = CADLoader(args.cad)
            gm, beams = loader.load_grid_manager(auto_frame=args.auto_frame)
            if args.auto_frame:
                 logger.info("[Auto-Frame]: Columns auto-generated. Generating default beams for grid...")
                 beams = generate_beams_for_grid(gm)
                 
            logger.info("Loaded %d columns and %d beams from CAD.", len(gm.columns), len(beams))
            logger.debug("Inferred Grid: %d x-lines, %d y-lines.", len(gm.x_grid_lines), len(gm.y_grid_lines))
        except Exception as e:
            logger.error("Error loading CAD: %s", e)
            return
    else:
        logger.info("Building: %sx%sm. Load: %s kN/m2. SBC: %s kN/m2", width, length, load_kn_m2, sbc)
        gm = GridManager(width_m=width, length_m=length)
        gm.generate_grid()
        # For default generation, we generate beams later using the helper
        beams = generate_beams_for_grid(gm)
    
    # 2. Loads & Sizing
    logger.info("Calculating loads and sizing columns...")
    gm.calculate_trib_areas()
    gm.calculate_loads(floor_load_kn_m2=50.0) # High load for testing
    
    # 1.5 Advanced Analysis
    from src.analysis_integration import update_structural_analysis
    update_structural_analysis(gm, beams) # Assuming 'all_beams' refers to the 'beams' variable
    
    # 2. Sizing & Detailing
    m_grade = Concrete.from_grade("M25")
    gm.optimize_column_sizes(concrete=m_grade)
    
    # 3. Foundation Design
    logger.info("Designing footings...")
    footings = []
    for col in gm.columns:
        ft = design_footing(
            axial_load_kn=col.load_kn,
            sbc_kn_m2=sbc,
            column_width_mm=col.width_nb,
            column_depth_mm=col.depth_nb,
            concrete=m_grade
        )
        footings.append(ft)
    
    # Attach footings to gm for report
    gm.footings = footings
    
    # Verify Center Column (if exists in this geometry)
    interior_cols = [c for c in gm.columns if c.type == "interior"]
    if interior_cols:
        center_col = interior_cols[0]
        center_ft = footings[gm.columns.index(center_col)]
        logger.debug("[CHECK] Sample Interior Col (%s) Load: %.2f kN", center_col.id, center_col.load_kn)
        logger.debug("[CHECK] Footing: %sx%sm, Depth: %smm", center_ft.length_m, center_ft.width_m, center_ft.thickness_mm)
    
    # 3.5 Structural Auditing & Safeguards
    logger.info("Running Structural Safeguards Analysis...")
    risk_mgr = BlackBoxRiskManager(gm, beams, footings)
    risk_results = risk_mgr.run_all_checks()
    
    if risk_results:
        logger.warning("!!! RISK SAFEGUARDS TRIBBLED !!!")
        for res in risk_results:
             logger.warning("[%s] %s", res.risk_level.name, res.message)
             logger.warning("    -> Recommendation: %s", res.recommendation)
    else:
        logger.info("Structural Safeguards: CLEARED. No critical risks detected.")
    
    # 4. Quantification
    # Use defaults (INR) which are now set in Quantifier class
    quantifier = Quantifier() 
    bom = quantifier.calculate_bom(gm.columns, beams, footings)
    
    logger.info("=== BILL OF MATERIALS & COSTING ===")
    logger.info("Total Concrete:       %.2f m3", bom.total_concrete_vol_m3)
    logger.info("Total Steel (Theor):  %.2f kg", bom.total_steel_weight_kg)
    logger.info("Total Steel (Proc):   %.2f kg (incl. 4%% Wastage)", bom.total_steel_weight_kg * 1.04)
    
    logger.info("--- Cost Estimates ---")
    logger.info("Concrete Cost:        INR %,.2f", bom.concrete_cost_usd)
    logger.info("Steel Cost:           INR %,.2f", bom.steel_cost_usd)
    
    logger.info("Excavation Cost:      INR %,.2f - %,.2f", bom.excavation_cost_range['min'], bom.excavation_cost_range['max'])
    logger.info("Finishing Cost:       INR %,.2f - %,.2f", bom.finishing_cost_range['min'], bom.finishing_cost_range['max'])
    
    logger.info("Base Project Cost:    INR %,.2f", bom.base_project_cost)
    logger.info("Contingency (5%%):     INR %,.2f", bom.contingency_amount)
    logger.info("TOTAL PROJECT COST:   INR %,.2f", bom.final_project_cost)
    
    # 5. Reporting
    report_file = "Structural_Report_V2.pdf"
    logger.info("Generating report: %s...", report_file)
    reporter = ReportGenerator()
    project_name = f"Design from {os.path.basename(args.cad)}" if args.cad else "18x12m Design with Foundation"
    reporter.generate_report(report_file, gm, bom, project_name=project_name)
    logger.info("Report generated successfully.")

if __name__ == "__main__":
    main()
