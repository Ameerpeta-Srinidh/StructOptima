"""
Full Structural Design Pipeline Demo

Simulates the complete workflow from Architectural Input to Final BOQ:
1. Architectural Input (Simulated DXF data)
2. Structural Framing (Column/Beam extraction)
3. Analysis Configuration (Seismic/Wind)
4. Structural Analysis (Simplified Load Flow)
5. Member Design (Beams/Columns/Slabs)
6. Detailing & BBS (IS 13920)
7. Quantity Takeoff & Costing (BOQ)
"""

import json
from src.column_placer import ColumnPlacer
from src.beam_placer import BeamPlacer
from src.slab_generator import SlabGenerator
from src.analysis_config import AnalysisConfigGenerator
from src.member_design import MemberDesigner
from src.bbs_module import generate_beam_bbs, generate_column_bbs, BeamBBSInput, ColumnBBSInput
from src.quantity_takeoff import QuantityTakeoff

def run_pipeline():
    print("="*80)
    print("STRUCTURAL DESIGN AUTOMATION PIPELINE")
    print("="*80)
    
    # -------------------------------------------------------------------------
    # 1. Architectural Input (Simulated for Complex Villa)
    # -------------------------------------------------------------------------
    print("\n1. ARCHITECTURAL INPUT")
    print("-" * 40)
    # L-shaped building with a courtyard
    nodes = [
        (0,0), (6000,0), (10000,0), 
        (10000,8000), (4000,8000), (4000,4000), 
        (0,4000), (0,0)
    ]
    walls = [
        ((0,0), (6000,0)), ((6000,0), (10000,0)), 
        ((10000,0), (10000,8000)), ((10000,8000), (4000,8000)),
        ((4000,8000), (4000,4000)), ((4000,4000), (0,4000)),
        ((0,4000), (0,0)),
        # Internal walls
        ((6000,0), (6000,4000)), ((6000,4000), (4000,4000))
    ]
    print(f"Loaded {len(nodes)} nodes and {len(walls)} walls.")

    # -------------------------------------------------------------------------
    # 2. Structural Framing
    # -------------------------------------------------------------------------
    print("\n2. STRUCTURAL FRAMING")
    print("-" * 40)
    
    # Place Columns
    cp = ColumnPlacer(nodes=nodes, centerlines=walls, seismic_zone="IV")
    col_res = cp.generate_placement()
    print(f"Generated {len(col_res.columns)} columns.")
    
    # Place Beams
    col_dicts = [{"x": c.x, "y": c.y, "id": c.id} for c in col_res.columns]
    bp = BeamPlacer(columns=col_dicts, walls=walls, seismic_zone="IV")
    beam_res = bp.generate_placement()
    print(f"Generated {len(beam_res.beams)} beams.")
    
    # Identify Slabs
    # BeamPlacer already identifies panels, but let's use SlabGenerator for deeper analysis
    # Convert beams to format expected by SlabGenerator
    sg_beams = [
        {"start_point": {"x": b.start_x, "y": b.start_y}, 
         "end_point": {"x": b.end_x, "y": b.end_y}} 
        for b in beam_res.beams
    ]
    sg_cols = [{"x": c.x, "y": c.y} for c in col_res.columns]
    
    sg = SlabGenerator(beams=sg_beams, columns=sg_cols, walls=walls)
    slab_res = sg.generate()
    print(f"Generated {len(slab_res.slabs)} slabs.")

    # -------------------------------------------------------------------------
    # 3. Analysis Configuration
    # -------------------------------------------------------------------------
    print("\n3. ANALYSIS CONFIGURATION (IS 1893)")
    print("-" * 40)
    
    ac_gen = AnalysisConfigGenerator(zone="IV", num_storeys=2)
    ac_gen.add_floor_mass("Floor1", 3.0, 1500, 500, 2.0, False)
    ac_gen.add_floor_mass("Roof", 6.0, 1200, 0, 0, True)
    
    analysis_config = ac_gen.generate()
    print(f"Base Shear Calculation: Z=0.24, I=1.0, R=5")
    print(f"Total Seismic Weight: {analysis_config.total_seismic_weight_kn:.2f} kN")
    print(f"Load Combinations: {len(analysis_config.load_combinations)}")

    # -------------------------------------------------------------------------
    # 4. Member Design & 5. BBS
    # -------------------------------------------------------------------------
    print("\n4. MEMBER DESIGN & BBS")
    print("-" * 40)
    
    designer = MemberDesigner(concrete_grade="M25", steel_grade="Fe415")
    qt = QuantityTakeoff(concrete_grade="M25", steel_grade="Fe500") # Using Fe500 for BOQ
    
    total_steel = {}
    
    print(f"Processing {len(beam_res.beams)} beams...")
    for i, b in enumerate(beam_res.beams[:5]): # Sample first 5
        if b.span_mm <= 0:
            print(f"  Skipping Beam {i} ({b.id}) due to zero span")
            continue
            
        print(f"  Beam {i}: {b.id}, Span={b.span_mm}")
        # Simplify design forces (in real app, these come from FEA)
        design = designer.design_beam(b.id, b.width_mm, b.depth_mm, 45.0, 30.0)
        
        try:
            # input for BBS (simplified mapping)
            bbs_input = BeamBBSInput(
                member_id=b.id, length_mm=b.span_mm, 
                width_mm=b.width_mm, depth_mm=b.depth_mm,
                main_bar_dia_mm=16, top_bars=2, bottom_bars=3, 
                stirrup_dia_mm=8, stirrup_spacing_mm=150
            )
            print("  BBS Input created")
            bbs = generate_beam_bbs(bbs_input)
            print("  BBS generated")
        except Exception as e:
            print(f"  ERROR for {b.id}: {e}")
            import traceback
            traceback.print_exc()
            continue
        
        # Add to QT
        qt.add_beam(b.id, b.span_mm, b.width_mm, b.depth_mm)
        for entry in bbs.entries:
            total_steel[entry.bar_diameter_mm] = total_steel.get(entry.bar_diameter_mm, 0) + entry.total_weight_kg

    # Process Columns
    for c in col_res.columns[:3]:
        design = designer.design_column(c.id, c.width, c.depth, 3000, 500, 20, 20, 1.0)
        
        bbs_input = ColumnBBSInput(
            member_id=c.id, height_mm=3000, width_mm=c.width, depth_mm=c.depth,
            main_bar_dia_mm=16, num_bars=8, tie_dia_mm=8, tie_spacing_mm=100
        )
        bbs = generate_column_bbs(bbs_input)
        
        qt.add_column(c.id, 3000, c.width, c.depth)
        for entry in bbs.entries:
            total_steel[entry.bar_diameter_mm] = total_steel.get(entry.bar_diameter_mm, 0) + entry.total_weight_kg

    # Process Slabs
    for s in slab_res.slabs[:2]:
        qt.add_slab(s.id, s.Lx_mm, s.Ly_mm, s.thickness_mm)
        # Simplify steel approx 8kg/m2 for demo
        steel_wt = (s.area_m2 * 25) # approx vol * 0.8%
        total_steel[8] = total_steel.get(8, 0) + steel_wt

    # -------------------------------------------------------------------------
    # 6. Quantity Takeoff
    # -------------------------------------------------------------------------
    print("\n5. QUANTITY TAKEOFF")
    print("-" * 40)
    
    qt.add_steel_from_bbs(total_steel)
    report = qt.generate_boq_report(built_up_area_sqft=1200)
    print(report)
    
    print("\n" + "="*80)
    print("PIPELINE EXECUTION SUCCESSFUL")
    print("="*80)

if __name__ == "__main__":
    run_pipeline()
