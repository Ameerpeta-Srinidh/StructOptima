from typing import List, Dict, Union, Optional, Any
from pydantic import BaseModel
from .grid_manager import Column
from .framing_logic import StructuralMember

class MaterialCost(BaseModel):
    total_concrete_vol_m3: float
    total_steel_weight_kg: float
    total_cost_inr: float
    concrete_cost_inr: float
    steel_cost_inr: float
    total_carbon_kg: float = 0.0
    concrete_carbon_kg: float = 0.0
    steel_carbon_kg: float = 0.0
    steel_by_diameter: Dict[Union[str, int], float] = {}  # {dia: kg}
    
    # Masonry/Wall quantities
    brick_count: int = 0
    mortar_vol_m3: float = 0.0
    plaster_area_m2: float = 0.0
    brickwork_cost_inr: float = 0.0
    
    # Detailed Masonry Breakdown per Indian Standards
    wall_bom: Optional[Dict[str, Any]] = None
    total_bricks: int = 0
    total_mortar_cement_bags: int = 0
    total_mortar_sand_tonnes: float = 0.0
    total_mortar_water_litres: float = 0.0
    total_plaster_cement_bags: int = 0
    total_plaster_sand_tonnes: float = 0.0
    total_plaster_water_litres: float = 0.0
    total_primer_litres: float = 0.0
    total_putty_kg: float = 0.0
    total_emulsion_int_litres: float = 0.0
    total_emulsion_ext_litres: float = 0.0
    
    # Cost Ranges (Min/Max)
    excavation_cost_range: Dict[str, float] = {} # {"min": 0, "max": 0}
    finishing_cost_range: Dict[str, float] = {} # {"min": 0, "max": 0}
    
    # Contingency
    base_project_cost: float = 0.0
    contingency_amount: float = 0.0
    cost_index_amount: float = 0.0
    final_project_cost: float = 0.0
    
    # Material breakdown (M25 mix design)
    cement_bags: float = 0.0  # Number of 50kg bags
    cement_kg: float = 0.0
    sand_m3: float = 0.0  # Fine aggregate
    aggregate_m3: float = 0.0  # Coarse aggregate (20mm)
    water_liters: float = 0.0
    
    total_excavation_vol_m3: float = 0.0
    total_finish_area_m2: float = 0.0

class Quantifier:
    def __init__(
        self, 
        concrete_rate: float = 5000.0, 
        steel_rate: float = 60.0,
        apply_is1200_opening_rules: bool = True,
        steel_wastage_percent: float = 4.0  # 3-5% for rolling margin + off-cut wastage
    ):
        self.concrete_rate = concrete_rate # INR/m3
        self.steel_rate = steel_rate # INR/kg
        self.apply_is1200_opening_rules = apply_is1200_opening_rules
        self.steel_wastage_percent = steel_wastage_percent
        
        # DSR 2023 Based Rates (Approx converted to USD/Unit for consistency, or just assume Unit is Currency)
        # Excavation: 207 (Earth) to 1599 (Rock) -> Let's use currency agnostic "Units"
        self.excavation_rate_min = 200.0 
        self.excavation_rate_max = 1600.0
        
        # Finishing (Plaster/Paint): 300 to 500 per m2
        self.finish_rate_min = 300.0
        self.finish_rate_max = 500.0
        
        self.contingency_percent = 5.0
        self.cost_index_percent = 0.0 # User input typically
        
    def calculate_column_volume(self, columns: List[Column], height_m: float = 3.0) -> float:
        total_vol = 0.0
        for col in columns:
            # width_nb is mm, convert to m
            w_m = col.width_nb / 1000.0
            d_m = col.depth_nb / 1000.0
            vol = w_m * d_m * height_m
            total_vol += vol
        return total_vol
        
    def calculate_beam_volume(self, beams: List[StructuralMember]) -> float:
        total_vol = 0.0
        for beam in beams:
            # Simple distance calc for length
            dx = beam.end_point.x - beam.start_point.x
            dy = beam.end_point.y - beam.start_point.y
            dz = (beam.end_point.z - beam.start_point.z) if hasattr(beam.start_point, 'z') else 0.0
            length = (dx**2 + dy**2 + dz**2)**0.5
            
            w_m = beam.properties.width_mm / 1000.0
            d_m = beam.properties.depth_mm / 1000.0
            vol = w_m * d_m * length
            total_vol += vol
        return total_vol

    def calculate_bom(
        self, 
        columns: List[Column], 
        beams: List[StructuralMember], 
        footings: List[BaseModel] = [],
        grid_mgr: 'GridManager' = None, # Needed to access schedule dicts
        use_fly_ash: bool = False # Optimization toggle
    ) -> MaterialCost:
        # Volumes
        col_vol = self.calculate_column_volume(columns)
        beam_vol = self.calculate_beam_volume(beams)
        
        footing_conc_vol = sum(f.concrete_vol_m3 for f in footings)
        
        # Slab Volume Calculation (Fixed)
        # Apply IS 1200 opening deduction rules
        slab_vol = 0.0
        if grid_mgr and hasattr(grid_mgr, 'slab_schedule') and grid_mgr.slab_schedule:
            # Calculate total slab area from grid
            if grid_mgr.x_grid_lines and grid_mgr.y_grid_lines:
                actual_area = 0.0
                if grid_mgr.slab_schedule:
                    for slab_id, slab in grid_mgr.slab_schedule.items():
                        if hasattr(slab, 'area_m2'):
                            actual_area += slab.area_m2
                if actual_area > 0:
                    total_floor_area = actual_area
                else:
                    total_floor_area = grid_mgr.width_m * grid_mgr.length_m
                num_stories = getattr(grid_mgr, 'num_stories', 1)
                
                # Get average thickness from slab schedule
                thicknesses = [sres.thickness_mm for sres in grid_mgr.slab_schedule.values()]
                avg_thickness_m = (sum(thicknesses) / len(thicknesses)) / 1000.0 if thicknesses else 0.125
                
                # Calculate opening deductions per IS 1200
                # IS 1200: Only openings >= 0.1 m² are deducted
                opening_deduction_area = 0.0
                if self.apply_is1200_opening_rules and hasattr(grid_mgr, 'void_zones') and grid_mgr.void_zones:
                    for void in grid_mgr.void_zones:
                        # Calculate void area (simplified: assume one bay)
                        span_x = grid_mgr.x_grid_lines[1] - grid_mgr.x_grid_lines[0] if len(grid_mgr.x_grid_lines) > 1 else 6.0
                        span_y = grid_mgr.y_grid_lines[1] - grid_mgr.y_grid_lines[0] if len(grid_mgr.y_grid_lines) > 1 else 6.0
                        void_area = span_x * span_y
                        
                        # IS 1200: Only deduct if >= 0.1 m²
                        if void_area >= 0.1:
                            opening_deduction_area += void_area
                
                # Net floor area after opening deductions
                net_floor_area = total_floor_area - opening_deduction_area
                slab_vol = net_floor_area * avg_thickness_m * num_stories
        
        total_conc = col_vol + beam_vol + footing_conc_vol + slab_vol
        
        # Steel Estimation (Detailed)
        total_steel = 0.0
        steel_by_dia = {} # {8: 0.0, 10: 0.0, ...}
        
        # 1. Columns
        # Try to use detailed schedule if available
        use_detailed = False
        if grid_mgr and hasattr(grid_mgr, 'rebar_schedule') and grid_mgr.rebar_schedule:
            use_detailed = True
            for col in columns:
                if col.id in grid_mgr.rebar_schedule:
                    res = grid_mgr.rebar_schedule[col.id]
                    # weight breakdown available?
                    if hasattr(res, 'weight_breakdown') and res.weight_breakdown:
                        # Col height?
                        h = col.z_top - col.z_bottom
                        if h <= 0: h = 3.0
                        
                        for dia, kg_pm in res.weight_breakdown.items():
                            w = kg_pm * h
                            steel_by_dia[dia] = steel_by_dia.get(dia, 0) + w
                            total_steel += w
                    else:
                        # Fallback to total
                        h = col.z_top - col.z_bottom
                        w = res.total_steel_weight_kg_per_m * h
                        # Assign to 'Unknown' or avg dia?
                        steel_by_dia['Unknown'] = steel_by_dia.get('Unknown', 0) + w
                        total_steel += w
        
        if not use_detailed:
             # Fallback
             steel_cols = col_vol * 150.0
             steel_by_dia['Est_Col'] = steel_cols
             total_steel += steel_cols
             
        # 2. Beams
        use_detailed_beams = False
        if grid_mgr and hasattr(grid_mgr, 'beam_schedule') and grid_mgr.beam_schedule:
            use_detailed_beams = True
            for b in beams:
                if b.id in grid_mgr.beam_schedule:
                    res = grid_mgr.beam_schedule[b.id]
                    # Length
                    dx = b.end_point.x - b.start_point.x
                    dy = b.end_point.y - b.start_point.y
                    l = (dx**2 + dy**2)**0.5
                    
                    if hasattr(res, 'weight_breakdown') and res.weight_breakdown:
                        for dia, kg_pm in res.weight_breakdown.items():
                            w = kg_pm * l
                            steel_by_dia[dia] = steel_by_dia.get(dia, 0) + w
                            total_steel += w
                    else:
                         w = res.weight_kg_per_m * l
                         steel_by_dia['Unknown'] = steel_by_dia.get('Unknown', 0) + w
                         total_steel += w
        
        if not use_detailed_beams:
            steel_beams = beam_vol * 120.0
            steel_by_dia['Est_Beam'] = steel_beams
            total_steel += steel_beams
            
        # 3. Slab (Approximation from schedule if possible)
        # We need area. 
        # grid_mgr.width_m * grid_mgr.length_m * stories
        if grid_mgr and hasattr(grid_mgr, 'slab_schedule'):
             # Avg weight per m2 from a sample slab?
             # Take S1
             if 'S1' in grid_mgr.slab_schedule:
                 s_res = grid_mgr.slab_schedule['S1']
                 # Total area
                 actual_area = 0.0
                 if grid_mgr.slab_schedule:
                     for slab_id, slab in grid_mgr.slab_schedule.items():
                         if hasattr(slab, 'area_m2'):
                             actual_area += slab.area_m2
                 if actual_area > 0:
                     total_area = actual_area * grid_mgr.num_stories
                 else:
                     total_area = grid_mgr.width_m * grid_mgr.length_m * grid_mgr.num_stories
                 
                 # Subtract void?
                 
                 if hasattr(s_res, 'weight_breakdown') and s_res.weight_breakdown:
                     for dia, kg_pm2 in s_res.weight_breakdown.items():
                         w = kg_pm2 * total_area
                         steel_by_dia[dia] = steel_by_dia.get(dia, 0) + w
                         total_steel += w
                 else:
                     w = s_res.weight_kg_per_m2 * total_area
                     steel_by_dia['Unknown'] = steel_by_dia.get('Unknown', 0) + w
                     total_steel += w
        
        # 4. Footings
        steel_footings = footing_conc_vol * 80.0
        steel_by_dia[10] = steel_by_dia.get(10, 0) + steel_footings # Assume 10mm for footings
        total_steel += steel_footings
        
        # Apply wastage and rolling margin to steel quantities
        # Real-world procurement must account for:
        # - Rolling margin (variance in steel unit weight): 2-3%
        # - Off-cut wastage (cutting bars from stock lengths): 2-3%
        # Total: 3-5% typically
        steel_wastage_factor = 1.0 + (self.steel_wastage_percent / 100.0)
        total_steel_with_wastage = total_steel * steel_wastage_factor
        
        # Update steel_by_diameter with wastage
        steel_by_dia_with_wastage = {}
        for dia, weight in steel_by_dia.items():
            steel_by_dia_with_wastage[dia] = weight * steel_wastage_factor
        
        # Use wastage-adjusted values
        total_steel = total_steel_with_wastage
        steel_by_dia = steel_by_dia_with_wastage
        
        # 5. Staircase (NEW)
        if grid_mgr and hasattr(grid_mgr, 'staircase_schedule') and grid_mgr.staircase_schedule:
             # Scale by num stories
             num_flights = grid_mgr.num_stories if hasattr(grid_mgr, 'num_stories') else 1
             for k, res in grid_mgr.staircase_schedule.items():
                 # 2 flights per floor usually in dog legged, detail_staircase did 1 flight logic?
                 # rebar_detailer: "Design a Dog-Legged Staircase (One Flight)."
                 # So we need 2 * num_stories flights.
                 qty = 2 * num_flights
                 
                 s_conc = res.concrete_vol_m3 * qty
                 s_steel = res.steel_weight_kg * qty
                 
                 total_conc += s_conc
                 total_steel += s_steel
                 
                 # Carbon
                 if use_fly_ash:
                      pass # handled in total calc
                 else:
                      pass
                      
                 steel_by_dia[10] = steel_by_dia.get(10, 0) + s_steel # Approx 10mm

        
        # Costs
        cost_conc = total_conc * self.concrete_rate
        cost_steel = total_steel * self.steel_rate
        total_cost = cost_conc + cost_steel
        
        # Carbon Calculation
        # Factors:
        # Concrete: Default 300, Fly Ash ~200 (kg/m3)
        conc_factor = 200.0 if use_fly_ash else 300.0
        # Steel: 1.85 kg/kg
        steel_factor = 1.85 
        
        carbon_conc = total_conc * conc_factor
        carbon_steel = total_steel * steel_factor
        total_carbon = carbon_conc + carbon_steel
        
        # Calculate material breakdown using IS 10262 design mix values
        # Defaulting to M25 (340 kg/m3) since grade isn't directly passed here.
        fck = 25.0
        if fck == 20: cement_per_m3 = 320.0
        elif fck == 25: cement_per_m3 = 340.0
        elif fck == 30: cement_per_m3 = 360.0
        elif fck == 35: cement_per_m3 = 380.0
        elif fck >= 40: cement_per_m3 = 400.0
        else: cement_per_m3 = 340.0
        
        cement_kg = total_conc * cement_per_m3
        cement_bags = cement_kg / 50.0
        water_liters = total_conc * 170.0 # ~170 L/m3 for w/c ~ 0.50
        
        # Approximate sand/aggregate volumes based on remaining mass (Density ~2400kg/m3)
        # Remaining mass = 2400 - cement - water = 1890 kg/m3. 
        # Assume Sand:Agg ratio ~ 1:2 by weight -> Sand ~630 kg, Agg ~1260 kg.
        # Volume: Sand (~1600 kg/m3) -> 0.39 m3, Agg (~1450 kg/m3) -> 0.87 m3
        sand_m3 = total_conc * 0.39
        aggregate_m3 = total_conc * 0.87
        
        # Recalculate costs with wastage-adjusted steel
        cost_steel = total_steel * self.steel_rate
        total_cost = cost_conc + cost_steel
        
        # Recalculate carbon with wastage-adjusted steel
        carbon_steel = total_steel * steel_factor
        total_carbon = carbon_conc + carbon_steel
        
        # 6. Masonry Walls (Detailed IS-standard calculation)
        brick_count = 0
        mortar_vol = 0.0
        plaster_area = 0.0
        brickwork_cost = 0.0
        wall_bom_dict = None
        tot_bricks = 0
        m_cem_bags = 0
        m_sand_tonnes = 0.0
        m_water_l = 0.0
        p_cem_bags = 0
        p_sand_tonnes = 0.0
        p_water_l = 0.0
        primer_l = 0.0
        putty_kg = 0.0
        emulsion_int_l = 0.0
        emulsion_ext_l = 0.0
        
        if grid_mgr and hasattr(grid_mgr, 'walls') and grid_mgr.walls:
            from .wall_calculator import WallCalculator
            wall_calc = WallCalculator(mortar_ratio=4, wc_ratio=0.50)
            num_stories = getattr(grid_mgr, 'num_stories', 1)
            story_h = getattr(grid_mgr, 'story_height_m', 3.5)
            
            slab_th_mm = 125.0
            if hasattr(grid_mgr, 'slab_schedule') and grid_mgr.slab_schedule:
                th_list = [s.thickness_mm for s in grid_mgr.slab_schedule.values() if hasattr(s, 'thickness_mm')]
                if th_list:
                    slab_th_mm = sum(th_list) / len(th_list)

            bm_depth_mm = 400.0
            if beams:
                d_list = [getattr(b.properties, 'depth_mm', 400.0) for b in beams if getattr(b, 'properties', None)]
                if d_list:
                    bm_depth_mm = sum(d_list) / len(d_list)

            wall_bom_obj = wall_calc.calculate_all(
                grid_mgr.walls,
                num_stories=num_stories,
                floor_height_m=story_h,
                slab_thickness_mm=slab_th_mm,
                beam_depth_mm=bm_depth_mm,
            )
            wall_bom_dict = wall_bom_obj.model_dump() if hasattr(wall_bom_obj, 'model_dump') else wall_bom_obj.dict()
            brick_count = wall_bom_obj.total_bricks
            tot_bricks = wall_bom_obj.total_bricks
            mortar_vol = sum(w.wet_mortar_vol_m3 for w in wall_bom_obj.wall_sections) * num_stories
            plaster_area = wall_bom_obj.total_plaster_area_m2
            brickwork_cost = wall_bom_obj.total_wall_cost_inr
            
            m_cem_bags = wall_bom_obj.total_mortar_cement_bags
            m_sand_tonnes = wall_bom_obj.total_mortar_sand_tonnes
            m_water_l = wall_bom_obj.total_mortar_water_litres
            p_cem_bags = wall_bom_obj.total_plaster_cement_bags
            p_sand_tonnes = wall_bom_obj.total_plaster_sand_tonnes
            p_water_l = wall_bom_obj.total_plaster_water_litres
            primer_l = wall_bom_obj.total_primer_litres
            putty_kg = wall_bom_obj.total_putty_kg
            emulsion_int_l = wall_bom_obj.total_emulsion_int_litres
            emulsion_ext_l = wall_bom_obj.total_emulsion_ext_litres

        # 7. Excavation & Finishes (Ranges)
        excavation_vol = footing_conc_vol * 3.0 # Rough approx: excavation is 3x concrete vol
        
        exc_cost_min = excavation_vol * self.excavation_rate_min
        exc_cost_max = excavation_vol * self.excavation_rate_max
        
        # Finish Area: Floor + Ceiling + Wall Plaster
        finish_area = 0.0
        if grid_mgr:
            actual_area = 0.0
            if hasattr(grid_mgr, 'slab_schedule') and grid_mgr.slab_schedule:
                for slab_id, slab in grid_mgr.slab_schedule.items():
                    if hasattr(slab, 'area_m2'):
                        actual_area += slab.area_m2
            
            if actual_area > 0:
                total_floor_area = actual_area * getattr(grid_mgr, 'num_stories', 1)
            else:
                total_floor_area = grid_mgr.width_m * grid_mgr.length_m * getattr(grid_mgr, 'num_stories', 1)
            finish_area = (total_floor_area * 2.0) + plaster_area
            
        finish_cost_min = finish_area * self.finish_rate_min
        finish_cost_max = finish_area * self.finish_rate_max

        # Base Cost includes masonry
        base_cost = total_cost + brickwork_cost + (exc_cost_min + finish_cost_min)
        
        # Contingency
        cont_amt = base_cost * (self.contingency_percent / 100.0)
        idx_amt = base_cost * (self.cost_index_percent / 100.0)
        final_amt = base_cost + cont_amt + idx_amt
        
        return MaterialCost(
            total_concrete_vol_m3=total_conc,
            total_steel_weight_kg=total_steel,  # Includes wastage and rolling margin
            total_cost_inr=total_cost, # Structure Only
            concrete_cost_inr=cost_conc,
            steel_cost_inr=cost_steel,
            total_carbon_kg=total_carbon,
            concrete_carbon_kg=carbon_conc,
            steel_carbon_kg=carbon_steel,
            steel_by_diameter=steel_by_dia,  # Includes wastage
            cement_bags=cement_bags,
            cement_kg=cement_kg,
            sand_m3=sand_m3,
            aggregate_m3=aggregate_m3,
            water_liters=water_liters,
            
            # Masonry fields
            brick_count=brick_count,
            mortar_vol_m3=mortar_vol,
            plaster_area_m2=plaster_area,
            brickwork_cost_inr=brickwork_cost,
            
            # Detailed Masonry Breakdown
            wall_bom=wall_bom_dict,
            total_bricks=tot_bricks,
            total_mortar_cement_bags=m_cem_bags,
            total_mortar_sand_tonnes=m_sand_tonnes,
            total_mortar_water_litres=m_water_l,
            total_plaster_cement_bags=p_cem_bags,
            total_plaster_sand_tonnes=p_sand_tonnes,
            total_plaster_water_litres=p_water_l,
            total_primer_litres=primer_l,
            total_putty_kg=putty_kg,
            total_emulsion_int_litres=emulsion_int_l,
            total_emulsion_ext_litres=emulsion_ext_l,
            
            # New Fields
            total_excavation_vol_m3=excavation_vol,
            total_finish_area_m2=finish_area,
            excavation_cost_range={"min": exc_cost_min, "max": exc_cost_max},
            finishing_cost_range={"min": finish_cost_min, "max": finish_cost_max},
            base_project_cost=base_cost,
            contingency_amount=cont_amt,
            cost_index_amount=idx_amt,
            final_project_cost=final_amt
        )
