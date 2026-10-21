"""
StructOptima command-line entry point.

Runs the same design pipeline as the Streamlit app (src/design_pipeline.py)
for a rectangular grid or a DXF file and writes a PDF report.

Example:
    python main.py --width 18 --length 12 --stories 2 --zone III
    python main.py --cad samples/sample_design.dxf --stories 3
"""

import argparse
import os
import sys

sys.path.append(os.path.join(os.getcwd(), 'src'))

from src.building_types import BUILDING_TYPES
from src.design_pipeline import DesignInputs, run_design
from src.grid_manager import GridManager
from src.logging_config import get_logger, setup_logging
from src.report_gen import ReportGenerator
from src.wind_load import TerrainCategory, WindZone

logger = get_logger("src.cli")   # inside the configured "src" logger tree


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="StructOptima - preliminary RC frame design (not for construction)")
    p.add_argument('--cad', type=str, help="Path to a DXF file (columns on COL* layers or walls for auto-framing)")
    p.add_argument('--auto-frame', action='store_true', help="Place columns automatically from architectural walls")
    p.add_argument('--width', type=float, default=18.0, help="Plan width in m (manual grid)")
    p.add_argument('--length', type=float, default=12.0, help="Plan length in m (manual grid)")
    p.add_argument('--stories', type=int, default=2)
    p.add_argument('--story-height', type=float, default=3.5)
    p.add_argument('--occupancy', default="Residential", choices=list(BUILDING_TYPES.keys()))
    p.add_argument('--zone', default="III", choices=["II", "III", "IV", "V"])
    p.add_argument('--soil', default="II", choices=["I", "II", "III"])
    p.add_argument('--system', default="OMRF", choices=["OMRF", "SMRF"])
    p.add_argument('--wind-zone', default="2", choices=[str(i) for i in range(1, 7)])
    p.add_argument('--terrain', default="2", choices=["1", "2", "3", "4"])
    p.add_argument('--sbc', type=float, default=200.0, help="Safe bearing capacity kN/m2")
    p.add_argument('--grade', default="M25", choices=["M20", "M25", "M30", "M35", "M40"])
    p.add_argument('--fy', type=float, default=415.0, choices=[415.0, 500.0])
    p.add_argument('--report', default="Structural_Report_V2.pdf", help="Output PDF path")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging()
    logger.info("=== STRUCTOPTIMA (preliminary design aid - NOT FOR CONSTRUCTION) ===")

    if args.cad:
        from src.cad_loader import CADLoader
        try:
            loader = CADLoader(args.cad)
            gm, beams = loader.load_grid_manager(auto_frame=args.auto_frame, seismic_zone=args.zone,
                                                 story_height_m=args.story_height, num_stories=args.stories)
        except Exception as e:
            logger.error("Error loading CAD: %s", e)
            return 2
        for w in loader.load_warnings:
            logger.warning("Input: %s", w)
        gm.columns = gm.stack_columns([c for c in gm.columns if c.level == 0], args.stories, args.story_height)
    else:
        gm = GridManager(width_m=args.width, length_m=args.length, num_stories=args.stories,
                         story_height_m=args.story_height)
        gm.generate_grid()
        beams = gm.generate_beams()

    inputs = DesignInputs(
        num_stories=args.stories, story_height_m=args.story_height, building_type_name=args.occupancy,
        sbc_kn_m2=args.sbc, conc_grade=args.grade, fy=args.fy, seismic_zone=args.zone, soil_type=args.soil,
        structural_system=args.system, wind_zone=WindZone(args.wind_zone),
        terrain_category=TerrainCategory(args.terrain),
        project_name=os.path.basename(args.cad) if args.cad else f"{args.width}x{args.length}m grid")
    from src.design_pipeline import InvalidInputError
    from src.grid_manager import InvalidStructureError
    try:
        res = run_design(gm, beams, inputs)
    except (InvalidInputError, InvalidStructureError) as e:
        logger.error("Input problem: %s", e)
        return 2

    bom = res.bom
    logger.info("Design status: %s (%d failing, %d warnings, %d iterations, converged=%s)", res.status,
                sum(f["Status"] == "FAIL" for f in res.failures), sum(f["Status"] == "WARN" for f in res.failures),
                res.iterations, res.converged)
    for f in res.failures:
        logger.warning("[%s] %s %s: %s", f["Status"], f["Type"], f["Member"], f["Issue"])
    logger.info("Seismic: W = %.0f kN, Vb = %.0f kN, Ta = %.2f s", res.building_weight, res.seismic_result.base_shear_kn,
                res.seismic_result.parameters.fundamental_period)
    logger.info("Concrete %.2f m3 | Steel %.0f kg (incl. wastage) | Structure cost INR %,.0f",
                bom.total_concrete_vol_m3, bom.total_steel_weight_kg, bom.total_cost_inr)

    # "Black Box" engineering-judgement prompts (retained from the previous CLI)
    from src.risk_management import BlackBoxRiskManager
    for rr in BlackBoxRiskManager(res.gm, res.all_beams, res.footings, fck=res.gm.fck, fy=res.gm.fy).run_all_checks():
        logger.warning("[RISK %s] %s -> %s", rr.risk_level.name, rr.message, rr.recommendation)

    ReportGenerator().generate_report(
        args.report, res.gm, bom, audit_results=res.audit_results, math_breakdown=res.auditor_math,
        project_name=inputs.project_name, seismic_result=res.seismic_result, wind_result=res.wind_result,
        stab_checks=res.stab_checks, stab_summary=res.stab_summary, all_beams=res.all_beams,
        conc_grade=args.grade, building_weight=res.building_weight, seismic_zone=args.zone, footings=res.footings,
        design_status=res.status, design_failures=res.failures, design_messages=res.messages)
    logger.info("Report written: %s", args.report)
    return 1 if res.status == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
