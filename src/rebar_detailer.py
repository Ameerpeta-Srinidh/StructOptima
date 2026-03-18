
import math
from typing import List, Tuple, Dict, Optional
from pydantic import BaseModel
from .materials import Concrete

class RebarResult(BaseModel):
    main_bars_desc: str # e.g., "4-16# + 4-12#"
    links_desc: str # e.g., "8# @ 200 c/c"
    main_steel_area_mm2: float
    total_steel_weight_kg_per_m: float # For BOM
    phi_main: int # Determine avg for simplicity or list
    congestion_status: str = "PASS" # PASS, WARN, FAIL
    weight_breakdown: Dict[int, float] = {} # {dia: kg_per_m}
    math_log: List[str] = [] # Engineering formula log

class StaircaseResult(BaseModel):
    waist_slab_thk_mm: float
    main_steel: str
    dist_steel: str
    concrete_vol_m3: float
    steel_weight_kg: float
    riser_mm: float
    tread_mm: float
    num_risers: int

class BeamRebarResult(BaseModel):
    top_bars_desc: str 
    bottom_bars_desc: str
    stirrups_desc: str
    size_label: str # Added field
    weight_kg_per_m: float
    provided_steel_area_mm2: float # For congestion check
    congestion_status: str = "PASS"
    weight_breakdown: Dict[int, float] = {}

class SlabRebarResult(BaseModel):

    main_steel_desc: str 
    dist_steel_desc: str 
    thickness_mm: float
    weight_kg_per_m2: float
    weight_breakdown: Dict[int, float] = {}
    
class RebarDetailer:
    """
    Handles detailing logic for structural members based on IS 456:2000.
    """
    
    @staticmethod
    def check_congestion(ag_mm2: float, ast_mm2: float, element_type: str = "column") -> str:
        """
        IS 456:2000 Cl 26.5.3.1: Max reinforcement 6% (columns), 4% practical.
        Beams: Max 4%.
        """
        if ag_mm2 <= 0: return "FAIL"
        percentage = (ast_mm2 / ag_mm2) * 100.0
        
        limit = 4.0 # Practical limit for pouring
        if percentage > 6.0: return "FAIL"
        if percentage > 4.0: return "WARN: CONGESTED"
        return "PASS"

    @staticmethod
    def detail_column(
        b_mm: float, 
        d_mm: float, 
        pu_kn: float, 
        concrete: Concrete, 
        level: int = 0,
        fy: float = 415.0
    ) -> RebarResult:
        """
        Determines reinforcement for a short column.
        Formula: Pu = 0.4*fck*Ac + 0.67*fy*Asc
        Pu in N.
        """
        pu_n = pu_kn * 1000.0
        ag = b_mm * d_mm
        fck = concrete.fck
        
        # 1. Calculate Ast required
        numerator = pu_n - (0.4 * fck * ag)
        denominator = (0.67 * fy) - (0.4 * fck)
        
        asc_calc = 0.0
        if denominator != 0:
             asc_calc = numerator / denominator
        
        # 2. Check Min/Max
        min_asc = 0.008 * ag
        max_asc = 0.04 * ag # Design for 4% max first, but allow check later
        
        req_asc = max(asc_calc, min_asc)
        
        # 3. Select Bars
        bar_opts = [12, 16, 20, 25]
        
        selected_bars = ""
        provided_area = 0.0
        main_dia = 12
        num_bars = 4
        
        # Optimize selection
        for phi in bar_opts:
            a_bar = (math.pi * phi**2) / 4.0
            nb = math.ceil(req_asc / a_bar)
            
            if nb < 4: nb = 4
            
            # Ensure even number for rect column symmetry usually
            if nb % 2 != 0: nb += 1
                
            if nb <= 16: # Practical limit for bundle
                num_bars = nb
                main_dia = phi
                provided_area = nb * a_bar
                selected_bars = f"{num_bars}-{phi}#"
                break
        
        if provided_area == 0: # Fallback if huge load
             main_dia = 25
             num_bars = math.ceil(req_asc / 490.8)
             if num_bars % 2 != 0: num_bars += 1
             provided_area = num_bars * 490.8
             selected_bars = f"{num_bars}-{main_dia}#"

        # Congestion Audit
        status = RebarDetailer.check_congestion(ag, provided_area, "column")

        # 4. Stirrups (Links)
        calc_pitch = min(b_mm, d_mm, 16 * main_dia, 300.0)
        
        if level == 0:
            pitch = min(calc_pitch, 150.0)
        else:
            pitch = min(calc_pitch, 200.0)
            
        pitch = math.floor(pitch / 25.0) * 25.0
        link_dia = max(main_dia / 4.0, 6.0)
        link_dia_practical = 8 if link_dia <= 8 else (10 if link_dia <=10 else 12)
        
        link_desc = f"{link_dia_practical}# @ {int(pitch)} c/c"
        
        # 5. Calculate Weight Breakdown
        weights = {}
        
        # Main
        w_main = (provided_area / 1e6) * 1.0 * 7850.0 
        weights[main_dia] = w_main
        
        # Links
        p_link = 2 * ((b_mm - 80) + (d_mm - 80)) + 24 * link_dia_practical
        if p_link < 0: p_link = 0
        num_links = 1000.0 / pitch
        a_link = (math.pi * link_dia_practical**2) / 4.0
        w_links = (num_links * p_link / 1000.0) * (a_link / 1e6) * 7850.0
        
        weights[link_dia_practical] = weights.get(link_dia_practical, 0) + w_links
        
        total_w = sum(weights.values())
        
        # Math Logging
        logs = []
        logs.append(f"Column Design (ID: N/A, Size: {int(b_mm)}x{int(d_mm)})")
        logs.append(f"1. Factored Load (Pu): {pu_kn:.1f} kN = {pu_n:.0f} N")
        logs.append(f"2. Gross Area (Ag): {b_mm} * {d_mm} = {ag:.0f} mm2")
        logs.append(f"3. Concrete Contribution (0.4 * fck * Ag):")
        term1 = 0.4 * fck * ag
        logs.append(f"   0.4 * {fck} * {ag} = {term1:.0f} N")
        logs.append(f"4. Steel Contribution Required (Pu - Conc):")
        logs.append(f"   {pu_n:.0f} - {term1:.0f} = {pu_n - term1:.0f} N")
        logs.append(f"5. Steel Area Calculation:")
        if denominator != 0:
            logs.append(f"   Asc_req = (Pu - 0.4*fck*Ag) / (0.67*fy - 0.4*fck)")
            logs.append(f"   Asc_calc = {asc_calc:.2f} mm2")
        else:
            logs.append("   Denominator zero error.")
            
        logs.append(f"6. Minimum Steel Check (0.8%):")
        logs.append(f"   0.008 * {ag} = {min_asc:.2f} mm2")
        logs.append(f"   Design Asc = max({asc_calc:.2f}, {min_asc:.2f}) = {req_asc:.2f} mm2")
        
        logs.append(f"7. Selected Reinforcement:")
        logs.append(f"   {selected_bars} (Area Provided: {provided_area:.2f} mm2)")
        
        cap_chk = (0.4 * fck * (ag - provided_area)) + (0.67 * fy * provided_area)
        logs.append(f"8. Final Capacity Check:")
        logs.append(f"   Capacity = {cap_chk/1000.0:.1f} kN vs Demand {pu_kn:.1f} kN")
        logs.append(f"   Result: {'PASS' if cap_chk >= pu_n else 'FAIL'}")

        return RebarResult(
            main_bars_desc=selected_bars,
            links_desc=link_desc,
            main_steel_area_mm2=provided_area,
            total_steel_weight_kg_per_m=total_w,
            phi_main=main_dia,
            congestion_status=status,
            weight_breakdown=weights,
            math_log=logs
        )

    @staticmethod
    def detail_beam(
        b_mm: float, 
        d_mm: float, 
        span_m: float, 
        load_kn_m: float,
        design_moment_knm: float = 0.0,
        design_shear_kn: float = 0.0
    ) -> BeamRebarResult:
        """
        Simplified Beam Design.
        Uses FEA forces if provided, else approximation.
        """
        
        if design_moment_knm > 0:
             mu_kNm = design_moment_knm
        else:
             w = load_kn_m
             l = span_m
             mu_kNm = (w * l**2) / 8.0 # Conservative sim supported
             
        mu_Nmm = mu_kNm * 1e6
        
        cover = 25
        deff = d_mm - cover - 10 
        
        min_ast = (0.85 / 415.0) * b_mm * deff
        ast_req = mu_Nmm / (0.87 * 415.0 * 0.9 * deff)
        ast = max(ast_req, min_ast)
        
        # Bottom Steel
        # Smart Selection: Avoid too many small bars
        bar_opts = [12, 16, 20, 25]
        phi = 12
        num = 2
        a_bar = 113.0
        
        for dia in bar_opts:
            area = (math.pi * dia**2)/4
            n = math.ceil(ast / area)
            n = max(2, n)
            
            # Prefer this diameter if it fits in 1-2 layers (say <= 6 bars)
            if n <= 6:
                phi = dia
                num = n
                a_bar = area
                break
        else:
            # If still fails (huge load), take the largest
            phi = 25
            a_bar = 490.8
            num = math.ceil(ast / a_bar)
            num = max(2, num)
            
        bot_desc = f"{num}-{phi}#"
        
        # Top Steel (Anchor)
        top_phi = 12
        top_desc = f"2-{top_phi}#"
        top_ast = 2 * 113.0
        
        # Stirrups
        stirrup_phi = 8
        stirrup_desc = "2L-8# @ 150 c/c"
        
        # Congestion
        total_steel_area = (num * a_bar) + top_ast
        status = RebarDetailer.check_congestion(b_mm * d_mm, total_steel_area, "beam")
        
        # Breakdown
        weights = {}
        
        # Bot
        w_bot = (num * a_bar / 1e6) * 7850
        weights[phi] = weights.get(phi, 0) + w_bot
        
        # Top
        w_top = (top_ast / 1e6) * 7850
        weights[top_phi] = weights.get(top_phi, 0) + w_top
        
        # Stirrups
        a_stir = 2 * 50.2
        perim = 2 * (b_mm + d_mm)
        num_stir = 1000 / 150.0
        w_stir = (num_stir * perim/1000.0 * a_stir/1e6) * 7850
        weights[stirrup_phi] = weights.get(stirrup_phi, 0) + w_stir
        
        total_w = sum(weights.values())
        
        return BeamRebarResult(
            top_bars_desc=top_desc,
            bottom_bars_desc=bot_desc,
            stirrups_desc=stirrup_desc,
            size_label=f"{int(b_mm)}x{int(d_mm)}",
            weight_kg_per_m=total_w,
            provided_steel_area_mm2=total_steel_area,
            congestion_status=status,
            weight_breakdown=weights
        )

    @staticmethod
    def detail_staircase(
        floor_height_m: float,
        flight_width_m: float = 1.2,
        fy: float = 415.0,
        fck: float = 25.0
    ) -> StaircaseResult:
        """
        Design a Dog-Legged Staircase (One Flight).
        Assumes 2 flights per floor.
        """
        # Geometric Design
        flight_height = floor_height_m / 2.0
        
        # Riser/Tread assumptions
        desired_riser = 150.0
        num_risers = round((flight_height * 1000) / desired_riser)
        actual_riser = (flight_height * 1000) / num_risers
        tread = 250.0 if actual_riser > 160 else 300.0
        num_treads = num_risers - 1
        
        # Waist Slab Sizing
        # Span = Horizontal projection + Landings
        # Approx effective span = 3.5m typically
        # Depth ~ Span / 25
        eff_span_m = (num_treads * tread / 1000.0) + 1.2 + 1.2 # Including landings
        min_depth = (eff_span_m * 1000) / 25.0
        waist_thk = math.ceil(min_depth / 10.0) * 10.0
        waist_thk = max(waist_thk, 150.0) # Minimum 150mm
        
        # Load Calculation
        # Dead Load on Slope
        # Avg thickness approx = waist_thk + (Riser/2) * (Tread / sqrt(R^2+T^2)) ... simplified
        # Load:
        # Waist Slab DL: 25 * D * sqrt(1 + R^2/T^2)
        hyp = math.sqrt(actual_riser**2 + tread**2)
        slope_factor = hyp / tread
        dl_slab = 25.0 * (waist_thk/1000.0) * slope_factor # kN/m2 on plan
        dl_steps = 25.0 * (actual_riser/1000.0) / 2.0 # Avg step thickness
        ll = 3.0 # Residential/Public
        ff = 1.0 # Floor finish
        
        total_load = dl_slab + dl_steps + ll + ff
        factored_load = 1.5 * total_load
        
        # Moment
        # Mu = w * l^2 / 8
        mu_knm = factored_load * (eff_span_m**2) / 8.0
        
        # Check Depth for Bending
        # Mu_lim = 0.138 fck b d^2 (Fe415)
        # d_req = sqrt(Mu / (0.138 fck b))
        eff_d = waist_thk - 25.0 # Cover 25
        
        mu_lim = 0.138 * fck * 1000.0 * (eff_d**2) / 1e6
        
        if mu_knm > mu_lim:
             # Increase depth if failing (rare for stairs unless huge span)
             waist_thk += 50.0
             eff_d += 50.0
        
        # Steel Calculation
        # Mu = 0.87 fy Ast d (1 - ...)
        # Approx Ast = Mu / (0.87 fy 0.9 d)
        ast_req = (mu_knm * 1e6) / (0.87 * fy * 0.9 * eff_d)
        
        # Min Steel 0.12%
        min_ast = 0.0012 * 1000.0 * waist_thk
        ast_prov = max(ast_req, min_ast)
        
        # Spacing (10mm bars likely)
        dia = 10
        area_bar = (math.pi * dia**2) / 4
        spacing = (area_bar * 1000.0) / ast_prov
        spacing = math.floor(spacing / 10.0) * 10.0
        spacing = min(spacing, 300, 3 * eff_d)
        
        main_desc = f"{dia}mm @ {int(spacing)}mm c/c"
        
        # Dist Steel (8mm)
        dist_ast = 0.0012 * 1000.0 * waist_thk
        dia_d = 8
        area_d = (math.pi * dia_d**2) / 4
        spacing_d = (area_d * 1000.0) / dist_ast
        spacing_d = min(spacing_d, 300, 5 * eff_d)
        dist_desc = f"{dia_d}mm @ {int(spacing_d)}mm c/c"
        
        # Quantities
        # Volume: Waist (Slope) + Steps
        slope_len = (num_treads * tread) * slope_factor / 1000.0
        vol_waist = slope_len * flight_width_m * (waist_thk/1000.0)
        vol_steps = num_risers * (actual_riser/1000.0 * tread/1000.0 / 2.0) * flight_width_m
        total_vol = vol_waist + vol_steps
        
        # Steel Weight Approx 100kg/m3
        total_steel = total_vol * 100.0 
        
        return StaircaseResult(
            waist_slab_thk_mm=waist_thk,
            main_steel=main_desc,
            dist_steel=dist_desc,
            concrete_vol_m3=total_vol,
            steel_weight_kg=total_steel,
            riser_mm=actual_riser,
            tread_mm=tread,
            num_risers=num_risers
        )

    @staticmethod
    def detail_slab(lx_m: float, ly_m: float, slab_thk_mm: float = 125.0) -> SlabRebarResult:
        ratio = max(lx_m, ly_m) / min(lx_m, ly_m)
        is_two_way = ratio < 2.0
        
        min_ast = 0.0012 * 1000 * slab_thk_mm
        
        # Main
        phi_main = 10
        a_bar = 78.5
        spacing_main = (1000 * a_bar) / min_ast
        spacing_main = min(spacing_main, 300.0)
        spacing_main = math.floor(spacing_main/25)*25
        main_desc = f"10# @ {int(spacing_main)} c/c"
        
        # Dist
        phi_dist = 8
        a_dist = 50.2
        spacing_dist = (1000 * a_dist) / min_ast
        spacing_dist = min(spacing_dist, 450.0)
        spacing_dist = math.floor(spacing_dist/25)*25
        dist_desc = f"8# @ {int(spacing_dist)} c/c"
        
        if is_two_way: dist_desc = main_desc
             
        # Breakdown (Per m2)
        weights = {}
        
        # Main
        len_main_per_m2 = 1000.0 / spacing_main
        w_main = len_main_per_m2 * (a_bar/1e6) * 7850
        weights[phi_main] = weights.get(phi_main, 0) + w_main
        
        # Dist
        len_dist_per_m2 = 1000.0 / spacing_dist
        if is_two_way: 
             # In 2-way, usually secondary is same as main
             w_dist = len_main_per_m2 * (a_bar/1e6) * 7850
             weights[phi_main] += w_dist # Add to 10mm
        else:
             w_dist = len_dist_per_m2 * (a_dist/1e6) * 7850
             weights[phi_dist] = weights.get(phi_dist, 0) + w_dist
             
        total_w = sum(weights.values())
        
        return SlabRebarResult(
            main_steel_desc=main_desc,
            dist_steel_desc=dist_desc,
            thickness_mm=slab_thk_mm,
            weight_kg_per_m2=total_w,
            weight_breakdown=weights
        )
