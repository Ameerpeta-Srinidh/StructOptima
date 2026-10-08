from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from typing import List
from .quantifier import MaterialCost
from .grid_manager import GridManager, Column

class ReportGenerator:
    def generate_report(self, filename: str, grid_mgr: GridManager, bom: MaterialCost,
                        audit_results: List = [], math_breakdown: List[str] = [],
                        project_name: str = "Structural Design Report", use_fly_ash: bool = False,
                        seismic_result=None, wind_result=None, stab_checks=None, stab_summary=None,
                        all_beams=None, conc_grade: str = "M25",
                        live_load: float = 0, building_weight: float = 0,
                        seismic_zone: str = "II", **kwargs):
        doc = SimpleDocTemplate(filename, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()
        
        # Title
        title_style = styles["Title"]
        elements.append(Paragraph(project_name, title_style))
        elements.append(Spacer(1, 12))
        
        # 1. Executive Summary
        elements.append(Paragraph("1. Executive Summary", styles["Heading1"]))
        num_st = getattr(grid_mgr, 'num_stories', 1)
        tot_b = getattr(bom, 'total_bricks', getattr(bom, 'brick_count', 0))
        tot_cem = getattr(bom, 'total_mortar_cement_bags', 0) + getattr(bom, 'total_plaster_cement_bags', 0)
        tot_sand = getattr(bom, 'total_mortar_sand_tonnes', 0.0) + getattr(bom, 'total_plaster_sand_tonnes', 0.0)
        tot_plast = getattr(bom, 'total_plaster_area_m2', getattr(bom, 'plaster_area_m2', 0.0))
        proj_cost = getattr(bom, 'final_project_cost', getattr(bom, 'base_project_cost', bom.total_cost_inr))
        
        summary_data = [
            ["Total Floor Area", f"{grid_mgr.width_m * grid_mgr.length_m:.2f} m²"],
            ["Stories / Height", f"{num_st} Stories / {num_st * getattr(grid_mgr, 'story_height_m', 3.0):.1f} m"],
            ["RCC Concrete Volume", f"{bom.total_concrete_vol_m3:.2f} m³"],
            ["Reinforcement Steel", f"{bom.total_steel_weight_kg:.0f} kg"],
            ["Clay Modular Bricks", f"{tot_b:,} Nos" if tot_b else "N/A"],
            ["Masonry & Plaster Cement", f"{tot_cem:,} Bags (50kg)" if tot_cem else "N/A"],
            ["Masonry & Plaster Sand", f"{tot_sand:.2f} Tonnes" if tot_sand else "N/A"],
            ["Plaster Surface Area", f"{tot_plast:.1f} m²" if tot_plast else "N/A"],
            ["Total Estimated Cost", f"INR {proj_cost:,.2f}"]
        ]
        t = Table(summary_data, colWidths=[200, 200])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightyellow),
            ('FONTWEIGHT', (0, -1), (-1, -1), 'BOLD'),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 12))
        
        # 2. Design Basis
        elements.append(Paragraph("2. Design Basis", styles["Heading1"]))
        basis_text = """
        <b>Design Codes & Standards:</b><br/>
        - IS 456:2000 (Code of Practice for Plain and Reinforced Concrete)<br/><br/>
        
        <b>Material Properties:</b><br/>
        - Concrete: M25 (Density: 25 kN/m3, E = 5000sqrt(fck))<br/>
        - Steel: Fe415 (Density: 78.5 kN/m3, E = 2x10^5 MPa)<br/><br/>
        
        <b>Loading & Analysis:</b><br/>
        - Design Load: User Input (Factored)<br/>
        - Load Path: Tributary Area Method (Corner: 25%, Edge: 50%, Interior: 100% of bay)<br/>
        - Beam Analysis: Simplified Simply Supported/Continuous assumptions.<br/>
          (M = wL^2/8 or wL^2/10, Deflection checked against L/250)<br/><br/>
          
        <b>Column Design:</b><br/>
        - Short Column Assumption (Le/r < 12)<br/>
        - Sizing Criteria: Axial Stress Check (Pu/Ag <= 0.4 fck)<br/>
        Note: Steel capacity (0.67 fy Asc) is reserved as safety margin.<br/><br/>
        
        <b>Foundation Design:</b><br/>
        - Isolated Square Footings<br/>
        - Area Required = Load * 1.1 / SBC (1.1 factor for self-weight)<br/>
        - Depth Check: Punching Shear at d/2 distance (Limit: 0.25sqrt(fck))<br/><br/>
        
        <b>Estimation Basis:</b><br/>
        - Concrete Cost: INR 5000/m3<br/>
        - Steel Cost: INR 60/kg<br/>
        - Rebar Ratios: Columns 150kg/m3, Beams 120kg/m3, Footings 80kg/m3
        """
        elements.append(Paragraph(basis_text, styles["Normal"]))
        elements.append(Spacer(1, 12))
        
        # 3. Column Schedule
        elements.append(Paragraph("3. Column Schedule & Quantities (IS 456 Cl. 26.5.3)", styles["Heading1"]))
        col_data = [["ID", "Level", "Loc (x,y)", "Load (kN)", "Size (mm)", "Conc (m3)", "Steel (kg)", "Status"]]
        sorted_cols = sorted(grid_mgr.columns, key=lambda c: (c.x, c.y, c.level))
        for col in sorted_cols:
            h = getattr(col, 'z_top', 3.0) - getattr(col, 'z_bottom', 0.0)
            if h <= 0: h = 3.0
            col_vol = (col.width_nb / 1000.0) * (col.depth_nb / 1000.0) * h
            col_steel = col_vol * 150.0
            col_data.append([
                col.id,
                f"L{col.level}",
                f"({col.x:.2f}, {col.y:.2f})",
                f"{col.load_kn:.1f}",
                f"{int(col.width_nb)}x{int(col.depth_nb)}",
                f"{col_vol:.2f}",
                f"{col_steel:.1f}",
                "PASS"
            ])
            
        t_cols = Table(col_data, repeatRows=1, colWidths=[45, 35, 75, 50, 65, 45, 45, 40])
        t_cols.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 7.5),
        ]))
        elements.append(t_cols)
        elements.append(Spacer(1, 12))
        
        # 4. Member Reinforcement Schedule
        elements.append(Paragraph("4. Reinforcement Schedule (IS 456 Cl. 26.5)", styles["Heading1"]))
        
        rebar_data = [["Col ID", "Main Bars", "Links (Stirrups)"]]
        if hasattr(grid_mgr, 'rebar_schedule') and grid_mgr.rebar_schedule:
             for col in sorted_cols:
                 if col.id in grid_mgr.rebar_schedule:
                     det = grid_mgr.rebar_schedule[col.id]
                     rebar_data.append([
                         col.id,
                         det.main_bars_desc,
                         det.links_desc
                     ])
        else:
            rebar_data.append(["N/A", "Run Detailing", "First"])
            
        t_rebar = Table(rebar_data, repeatRows=1, colWidths=[100, 150, 150])
        t_rebar.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkred),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        elements.append(t_rebar)
        elements.append(Spacer(1, 12))

        # 5. Foundation Schedule
        elements.append(Paragraph("5. Foundation Schedule & Quantities (IS 456 Cl. 34)", styles["Heading1"]))
        footing_data = [["Col ID", "Load (kN)", "Size (m)", "Depth (mm)", "Conc (m3)", "Steel (kg)"]]
        
        passed_footings = kwargs.get('footings', [])
        if isinstance(passed_footings, dict):
            passed_footings = list(passed_footings.values())
        
        if passed_footings:
            level_0_cols = [c for c in grid_mgr.columns if getattr(c, 'level', 0) == 0]
            for col, ft in zip(level_0_cols, passed_footings):
                if not ft or isinstance(ft, str):
                    continue
                ft_vol = getattr(ft, 'concrete_vol_m3', 0.0)
                if ft_vol == 0.0:
                    ft_vol = getattr(ft, 'length_m', 1.0) * getattr(ft, 'width_m', 1.0) * (getattr(ft, 'thickness_mm', 300.0) / 1000.0)
                ft_steel = ft_vol * 80.0
                footing_data.append([
                    col.id,
                    f"{col.load_kn:.1f}",
                    f"{getattr(ft, 'length_m', 1.0):.2f} x {getattr(ft, 'width_m', 1.0):.2f}",
                    f"{getattr(ft, 'thickness_mm', 300.0):.0f}",
                    f"{ft_vol:.2f}",
                    f"{ft_steel:.1f}"
                ])
        else:
            footing_data.append(["N/A", "-", "-", "-", "-", "-"])

        t_found = Table(footing_data, repeatRows=1, colWidths=[60, 60, 100, 60, 60, 60])
        t_found.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
        ]))
        elements.append(t_found)
        elements.append(Spacer(1, 12))

        # 6. Beam Schedule
        elements.append(Paragraph("6. Beam Schedule & Quantities (IS 456 Cl. 26.5.1)", styles["Heading1"]))
        beam_data = [["ID", "Size (mm)", "Span (m)", "Conc (m3)", "Steel (kg)", "Top Steel", "Bot Steel", "Stirrups"]]
        
        if hasattr(grid_mgr, 'beam_schedule') and grid_mgr.beam_schedule:
            sorted_b_ids = sorted(grid_mgr.beam_schedule.keys())
            for bid in sorted_b_ids:
                det = grid_mgr.beam_schedule[bid]
                bm_span = getattr(det, 'length_m', getattr(det, 'span_m', 4.0))
                bm_w = 0.23
                bm_d = 0.40
                if hasattr(det, 'size_label') and 'x' in det.size_label:
                    try:
                        p = det.size_label.split('x')
                        bm_w = float(p[0]) / 1000.0
                        bm_d = float(p[1]) / 1000.0
                    except Exception: pass
                bm_vol = bm_w * bm_d * bm_span
                bm_steel = bm_vol * 120.0
                
                beam_data.append([
                    bid,
                    det.size_label,
                    f"{bm_span:.2f}",
                    f"{bm_vol:.2f}",
                    f"{bm_steel:.1f}",
                    Paragraph(getattr(det, 'top_bars_desc', '-'), styles["Normal"]),
                    Paragraph(getattr(det, 'bottom_bars_desc', '-'), styles["Normal"]),
                    Paragraph(getattr(det, 'stirrups_desc', '-'), styles["Normal"])
                ])
        else:
            beam_data.append(["N/A", "-", "-", "-", "-", "-", "-", "-"])

        t_beam = Table(beam_data, repeatRows=1, colWidths=[40, 45, 40, 40, 45, 70, 70, 90])
        t_beam.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkorange),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTSIZE', (0,0), (-1,-1), 7),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        elements.append(t_beam)
        elements.append(Spacer(1, 12))

        # 7. Slab Schedule
        elements.append(Paragraph("7. Slab Schedule & Quantities", styles["Heading1"]))
        slab_data = [["ID", "Thk (mm)", "Area (m2)", "Conc (m3)", "Steel (kg)", "Main Mesh", "Dist Mesh"]]
        
        if hasattr(grid_mgr, 'slab_schedule') and grid_mgr.slab_schedule:
            for sid, det in grid_mgr.slab_schedule.items():
                s_area = getattr(det, 'area_m2', 16.0)
                s_thk = getattr(det, 'thickness_mm', 125.0)
                s_vol = s_area * (s_thk / 1000.0)
                s_steel = s_vol * 90.0
                slab_data.append([
                    sid,
                    f"{s_thk:.0f}",
                    f"{s_area:.1f}",
                    f"{s_vol:.2f}",
                    f"{s_steel:.1f}",
                    getattr(det, 'main_steel_desc', '-'),
                    getattr(det, 'dist_steel_desc', '-')
                ])
        else:
            slab_data.append(["N/A", "-", "-", "-", "-", "-", "-"])
                
        t_slab = Table(slab_data, repeatRows=1, colWidths=[50, 50, 50, 50, 50, 95, 95])
        t_slab.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.purple),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 7.5),
        ]))
        elements.append(t_slab)
        elements.append(Spacer(1, 12))

        # 8. Masonry Wall Design & Material Takeoff (IS 1077, IS 2250, IS 1661)
        elements.append(Paragraph("8. Masonry Wall Design & Material Takeoff", styles["Heading1"]))
        from .wall_calculator import WallCalculator
        wall_calc = WallCalculator(mortar_ratio=4, wc_ratio=0.50)
        num_stories = getattr(grid_mgr, 'num_stories', 1)
        story_h = getattr(grid_mgr, 'story_height_m', 3.0)
        
        elements.append(Paragraph("<b>8.1 Individual Wall Section Material Takeoff</b>", styles["Heading2"]))
        elements.append(Paragraph("<font size=8>Quantities per wall segment per floor: Bricks = 250 × Vol (IS 1077), Mortar dry factor = 1.33 (IS 2250), Plaster 12/15mm (IS 1661/2402).</font>", styles["Normal"]))
        elements.append(Spacer(1, 4))
        
        wall_data = [["Wall ID", "Span / Cols", "Len (m)", "Ht (m)", "Thk", "Vol (m3)", "Bricks", "Mortar (m3)", "Cem (kg)", "Sand (T)", "Plaster (m2)"]]
        
        wall_bom_rep = None
        if hasattr(grid_mgr, 'walls') and grid_mgr.walls:
            wall_bom_rep = wall_calc.calculate_all(
                grid_mgr.walls,
                num_stories=num_stories,
                floor_height_m=story_h,
                slab_thickness_mm=125.0,
                beam_depth_mm=400.0,
            )
            for sec in wall_bom_rep.wall_sections:
                span_label = f"{sec.col_start}→{sec.col_end}" if (sec.col_start and sec.col_end) else "Bay"
                wall_data.append([
                    sec.wall_id,
                    span_label,
                    f"{sec.length_m:.2f}",
                    f"{sec.clear_height_m:.2f}",
                    f"{int(sec.core_thickness_m * 1000)}mm",
                    f"{sec.wall_volume_m3:.2f}",
                    f"{sec.num_bricks:,}",
                    f"{sec.wet_mortar_vol_m3:.3f}",
                    f"{sec.mortar_cement_kg:.1f}",
                    f"{sec.mortar_sand_tonnes:.2f}",
                    f"{sec.plaster_area_m2:.1f}",
                ])
        else:
            wall_data.append(["N/A", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-"])
            
        t_wall = Table(wall_data, repeatRows=1, colWidths=[45, 55, 40, 35, 35, 45, 45, 55, 45, 45, 50])
        t_wall.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkorange),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(t_wall)
        elements.append(Spacer(1, 10))
        
        # 8.2 Overall Masonry & Finishes Summary
        elements.append(Paragraph("<b>8.2 Overall Masonry & Finishes Material Summary (All Stories)</b>", styles["Heading2"]))
        if wall_bom_rep:
            wb = wall_bom_rep
            tot_cem_bags = wb.total_mortar_cement_bags + wb.total_plaster_cement_bags
            tot_sand_t = wb.total_mortar_sand_tonnes + wb.total_plaster_sand_tonnes
            
            summary_masonry = [
                ["Item / Material", "Specification / Mix", "Building Total", "Unit", "IS Standard"],
                ["Total Wall Gross Volume", "L × t × Hv (clear height)", f"{wb.total_wall_volume_m3:.2f}", "m³", "IS 1905:1987"],
                ["Clay Building Bricks", "Modular 20×20×10 cm (with mortar)", f"{wb.total_bricks:,}", "Nos", "IS 1077:1992"],
                ["Wet Mortar Volume", "Wall Vol − Solid Brick Vol", f"{sum(s.wet_mortar_vol_m3 for s in wb.wall_sections)*num_stories:.2f}", "m³", "IS 2250:1981"],
                ["Dry Mortar Volume", "Wet Volume × 1.33 factor", f"{sum(s.dry_mortar_vol_m3 for s in wb.wall_sections)*num_stories:.2f}", "m³", "IS 2250:1981"],
                ["Brickwork Cement", "1:4 Mix Proportion", f"{wb.total_mortar_cement_bags:,} ({wb.total_mortar_cement_kg:,.0f} kg)", "Bags (50kg)", "IS 269:2015"],
                ["Brickwork Sand", "Dry bulk density 1600 kg/m³", f"{wb.total_mortar_sand_tonnes:.2f}", "Tonnes", "IS 383 Zone II"],
                ["Masonry Water", "W:C ratio = 0.50", f"{wb.total_mortar_water_litres:,.0f}", "Litres", "IS 456 Cl 5.4"],
                ["Total Plaster Surface Area", "Both sides (12mm int / 15mm ext)", f"{wb.total_plaster_area_m2:.1f}", "m²", "IS 1200 Pt 12"],
                ["Plastering Cement", "1:6 internal, 1:4 external", f"{wb.total_plaster_cement_bags:,} ({wb.total_plaster_cement_kg:,.0f} kg)", "Bags (50kg)", "IS 1661 / IS 2402"],
                ["Plastering Sand", "Clean river / M-sand", f"{wb.total_plaster_sand_tonnes:.2f}", "Tonnes", "IS 383 Zone III"],
                ["Plastering Water", "W:C ratio = 0.50", f"{wb.total_plaster_water_litres:,.0f}", "Litres", "IS 456 Cl 5.4"],
                ["Surface Primer", "1 coat (25–40 microns) @ 8 m²/L", f"{wb.total_primer_litres:.1f}", "Litres", "NBC 2016"],
                ["Wall Putty", "2 coats (1–2 mm) @ 1.5 kg/m²", f"{wb.total_putty_kg:,.1f}", "kg", "NBC 2016"],
                ["Interior Acrylic Emulsion", "2 coats (30–40 microns) @ 12 m²/L", f"{wb.total_emulsion_int_litres:.1f}", "Litres", "NBC 2016"],
                ["Exterior Weather Emulsion", "2 coats (40–60 microns) @ 10 m²/L", f"{wb.total_emulsion_ext_litres:.1f}", "Litres", "NBC 2016"],
                ["TOTAL CEMENT (Masonry + Plaster)", "Mortar + Plaster combined", f"{tot_cem_bags:,} bags ({tot_cem_bags*50:,.0f} kg)", "Bags", "IS 269"],
                ["TOTAL SAND (Masonry + Plaster)", "Mortar + Plaster combined", f"{tot_sand_t:.2f}", "Tonnes", "IS 383"],
            ]
            t_mas_sum = Table(summary_masonry, repeatRows=1, colWidths=[140, 130, 90, 60, 70])
            t_mas_sum.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkslategray),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('ALIGN', (0, 1), (1, -1), 'LEFT'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('BACKGROUND', (0, -2), (-1, -1), colors.lightyellow),
                ('FONTWEIGHT', (0, -2), (-1, -1), 'BOLD'),
            ]))
            elements.append(t_mas_sum)
            elements.append(Spacer(1, 12))

        # 9. Structural Layout Plan
        elements.append(Paragraph("9. Structural Layout Plan", styles["Heading1"]))
        
        # ... (Existing Map Logic)
        coords_text = "Column Coordinates:\n"
        for col in grid_mgr.columns:
            if col.x is not None and col.y is not None:
                coords_text += f"  {col.id}: ({col.x:.2f}, {col.y:.2f})\n"
            
        elements.append(Paragraph(f"<pre>{coords_text}</pre>", styles["Code"]))
        elements.append(Spacer(1, 12))
        
        # 10. Steel Material Breakdown
        elements.append(Paragraph("10. Integrated Steel Breakdown", styles["Heading1"]))
        
        steel_data = [["Bar Diameter", "Total Weight (kg)"]]
        
        if bom.steel_by_diameter:
             # Sort keys: integers separate from strings
             keys = bom.steel_by_diameter.keys()
             int_keys = sorted([k for k in keys if isinstance(k, int)])
             str_keys = sorted([k for k in keys if isinstance(k, str)])
             
             for k in int_keys:
                 steel_data.append([f"{k} mm", f"{bom.steel_by_diameter[k]:.1f}"])
                 
             for k in str_keys:
                 steel_data.append([f"{k}", f"{bom.steel_by_diameter[k]:.1f}"])
                 
             # Total
             steel_data.append(["TOTAL", f"{bom.total_steel_weight_kg:.1f}"])
        else:
             steel_data.append(["All diameters", f"{bom.total_steel_weight_kg:.1f}"])
             
        t_steel = Table(steel_data, repeatRows=1)
        t_steel.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkcyan),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTWEIGHT', (0, -1), (-1, -1), 'BOLD'), # Total bold
        ]))
        elements.append(t_steel)
        
        elements.append(Spacer(1, 12))
        
        # 10. Structural Audit (Phase 14)
        elements.append(Paragraph("10. Structural Audit Report", styles["Heading1"]))
        
        if audit_results:
             audit_data = [["Member", "Check", "Design Val", "Limit", "Status"]]
             
             for res in audit_results:
                 # Color code status?
                 status_str = res.status
                 audit_data.append([
                     res.member_id,
                     res.check_name,
                     f"{res.design_value:.1f}",
                     f"{res.limit_value:.1f}",
                     status_str
                 ])
             
             # No limit
             # if len(audit_data) > 50:
             #    audit_data = audit_data[:50]
             #    audit_data.append(["...", "...", "...", "...", "..."])
                 
             t_audit = Table(audit_data, repeatRows=1, colWidths=[60, 120, 80, 80, 60])
             t_audit.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.black),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
             ]))
             # Color rows based on status? 
             # ReportLab logic for row conditional formatting is verbose. Skipping for now.
             
             elements.append(t_audit)
             elements.append(Spacer(1, 12))
             
             # Math Breakdown
             if math_breakdown:
                 elements.append(Paragraph("<b>Math Verification Logs:</b>", styles["Heading2"]))
                 for log in math_breakdown:
                     elements.append(Paragraph(f"<pre>{log}</pre>", styles["Code"]))
                     elements.append(Spacer(1, 6))
        else:
             elements.append(Paragraph("No audit results available.", styles["Normal"]))
        
        # 11. Sustainability & Carbon Audit (NEW)
        elements.append(Paragraph("11. Sustainability Audit", styles["Heading1"]))
        
        green_status = "Optimized (Green Concrete)" if use_fly_ash else "Standard (OPC)"
        elements.append(Paragraph(f"<b>Design Strategy:</b> {green_status}", styles["Normal"]))
        elements.append(Spacer(1, 12))
        
        # Carbon Table
        carb_data = [
            ["Material", "Quantity", "Emission Factor", "Total CO2e (kg)"],
            ["Concrete", f"{bom.total_concrete_vol_m3:.2f} m3", f"{'200' if use_fly_ash else '300'} kg/m3", f"{bom.concrete_carbon_kg:.1f}"],
            ["Steel", f"{bom.total_steel_weight_kg:.0f} kg", "1.85 kg/kg", f"{bom.steel_carbon_kg:.1f}"],
            ["TOTAL", "-", "-", f"{bom.total_carbon_kg:.1f}"]
        ]
        
        t_carb = Table(carb_data, colWidths=[100, 100, 100, 100])
        t_carb.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTWEIGHT', (0, -1), (-1, -1), 'BOLD'),
        ]))
        elements.append(t_carb)
        elements.append(Spacer(1, 12))
        
        if not use_fly_ash:
            opt_text = """
            <b>Wait! You can reduce your Carbon Footprint.</b><br/>
            Refining the design to use <b>Fly Ash based Concrete (PPC)</b> instead of OPC 
            can reduce concrete emissions by approximately 15-20%. <br/>
            Switch "Use Green Concrete" ON in the dashboard to see savings. (Note: PPC is slower setting and has lower early strength, use only if confirmed by RMC supplier).
            """
            elements.append(Paragraph(opt_text, styles["Normal"]))
        else:
            baseline = bom.concrete_carbon_kg * (300/200) # Reverse calc approx
            savings = baseline - bom.concrete_carbon_kg
            success_text = f"""
            <b>Great Job!</b><br/>
            By choosing Green Concrete, you saved approx <b>{savings/1000.0:.2f} Tonnes</b> of CO2 emissions 
            compared to standard Ordinary Portland Cement (OPC).
            """
            elements.append(Paragraph(success_text, styles["Normal"]))
        
        
        # 12. Serviceability Checks (Deflection)
        elements.append(Paragraph("12. Serviceability Checks (Deflection)", styles["Heading1"]))
        
        # Filter for beam deflection checks
        beam_checks = [r for r in audit_results if "Beam Deflection" in r.check_name]
        
        if beam_checks:
            serv_data = [["Beam ID", "Description", "Actual (mm)", "Limit (mm)", "Status"]]
            
            # Show top 30 to avoid overflow? use slicing
            top_checks = beam_checks[:30]
            
            for bc in top_checks:
                 # Notes format: "Defl: 5.23mm vs Limit 12.00mm"
                 # Extract values roughly or use AuditResult
                 # Actually AuditResult has exact values
                 serv_data.append([
                     bc.member_id,
                     "Span/250 Check",
                     f"{bc.design_value:.3f}",
                     f"{bc.limit_value:.2f}",
                     bc.status
                 ])
            
            if len(beam_checks) > 30:
                 serv_data.append(["...", "...", "...", "...", "..."])
                 
            t_serv = Table(serv_data, repeatRows=1, colWidths=[80, 150, 80, 80, 60], splitByRow=0)
            t_serv.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.teal),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ]))
            elements.append(t_serv)
        else:
             elements.append(Paragraph("No beam serviceability checks performed.", styles["Normal"]))
             
        
        # 13. Staircase Design Schedule (NEW)
        elements.append(Paragraph("13. Staircase Design Schedule (Dog-Legged)", styles["Heading1"]))
        
        if hasattr(grid_mgr, 'staircase_schedule') and grid_mgr.staircase_schedule:
            stair_data = [["ID", "Riser/Tread", "Waist Slab", "Main Steel", "Dist Steel"]]
            
            for sid, res in grid_mgr.staircase_schedule.items():
                stair_data.append([
                    sid,
                    f"{res.riser_mm:.0f} / {res.tread_mm:.0f} mm",
                    f"{res.waist_slab_thk_mm:.0f} mm",
                    res.main_steel,
                    res.dist_steel
                ])
                
            t_stair = Table(stair_data, colWidths=[60, 100, 80, 120, 120])
            t_stair.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.brown),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            elements.append(t_stair)
            
            # Add note about geometry
            note_text = f"""
            <b>Geometry Notes:</b><br/>
            - Flight designed for floor height: {grid_mgr.story_height_m:.2f} m<br/>
            - Number of Risers per flight: {res.num_risers}<br/>
            - Design assumes 2 flights per floor (Dog-Legged).
            """
            elements.append(Paragraph(note_text, styles["Normal"]))
            
        else:
             elements.append(Paragraph("No staircase selected for design.", styles["Normal"]))
        
        
        # NEW SECTIONS: Seismic, Wind, Material Breakdown, Beam L/d, Stability (Changes 4 & 10)
        import math as _math
        
        # --- Seismic Analysis ---
        if seismic_result:
            elements.append(Paragraph("Seismic Analysis (IS 1893:2016)", styles["Heading1"]))
            try:
                _z = getattr(seismic_result.parameters, 'zone_factor', '—')
                _ah = getattr(seismic_result.parameters, 'design_acceleration', 0)
                _vb = getattr(seismic_result, 'base_shear_kn', 0)
                _ta = getattr(seismic_result.parameters, 'fundamental_period', 0)
                _scwb_req = getattr(seismic_result.parameters, 'scwb_required', False)
                _scwb_ok = getattr(seismic_result, 'all_scwb_pass', True)
                seismic_tbl = [
                    ["Parameter", "Value"],
                    ["Seismic Zone", seismic_zone],
                    ["Zone Factor (Z)", str(_z)],
                    ["Design Acceleration (Ah)", f"{_ah:.4f}"],
                    ["Fundamental Period (Ta)", f"{_ta:.3f} s"],
                    ["Base Shear (Vb)", f"{_vb:.1f} kN"],
                    ["Strong Column–Weak Beam", "REQUIRED" if _scwb_req else "Not Required"],
                    ["SCWB Status", "PASS" if _scwb_ok else "FAIL — See Analysis Page"],
                ]
                t_seis = Table(seismic_tbl, colWidths=[200, 200])
                t_seis.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
                    ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.black),
                    ('BACKGROUND', (-1,-1), (-1,-1), colors.pink if not _scwb_ok else colors.lightgreen),
                ]))
                elements.append(t_seis)
            except Exception as _e:
                elements.append(Paragraph(f"Seismic data available but error rendering: {_e}", styles["Normal"]))
            elements.append(Spacer(1, 12))
        
        # --- Wind Analysis ---
        if wind_result and hasattr(wind_result, 'pressure_results') and wind_result.pressure_results:
            elements.append(Paragraph("Wind Analysis (IS 875 Part 3)", styles["Heading1"]))
            try:
                _vd = wind_result.pressure_results[-1].design_wind_speed_ms
                _vwx = getattr(wind_result, 'total_base_shear_x_kn', 0)
                _vwy = getattr(wind_result, 'total_base_shear_y_kn', 0)
                wind_tbl = [
                    ["Parameter", "Value"],
                    ["Design Wind Speed (Top)", f"{_vd:.1f} m/s"],
                    ["Wind Base Shear (X)", f"{_vwx:.1f} kN"],
                    ["Wind Base Shear (Y)", f"{_vwy:.1f} kN"],
                ]
                t_wind = Table(wind_tbl, colWidths=[200, 200])
                t_wind.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.steelblue),
                    ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.black),
                ]))
                elements.append(t_wind)
            except Exception as _e:
                elements.append(Paragraph(f"Wind data available but error rendering: {_e}", styles["Normal"]))
            elements.append(Spacer(1, 12))
        
        # --- Concrete Material Breakdown (IS 10262:2019) ---
        if bom and bom.total_concrete_vol_m3 > 0:
            elements.append(Paragraph("Concrete Material Breakdown (IS 10262:2019)", styles["Heading1"]))
            try:
                from .site_calculators import mix_design_table
                _mix = mix_design_table(conc_grade)
                _vol = bom.total_concrete_vol_m3
                _fa_density = 1600.0
                _ca_density = 1450.0
                _fa_m3 = _mix['fine_aggregate_kg_m3'] / _fa_density
                _ca_m3 = _mix['coarse_aggregate_kg_m3'] / _ca_density
                mat_tbl = [
                    ["Material", "Per m³", "Total"],
                    ["Wet Concrete Volume", "", f"{_vol:.2f} m³"],
                    ["Cement (50kg bags)", f"{_mix['cement_bags_per_m3']} bags", f"{_vol * _mix['cement_bags_per_m3']:.1f} bags"],
                    ["Fine Aggregate (Sand)", f"{_fa_m3:.3f} m³", f"{_vol * _fa_m3:.2f} m³"],
                    ["Coarse Aggregate (20mm)", f"{_ca_m3:.3f} m³", f"{_vol * _ca_m3:.2f} m³"],
                    ["Water", f"{_mix['water_kg_m3']} kg", f"{_vol * _mix['water_kg_m3']:.0f} kg"],
                    ["Water:Cement Ratio", str(_mix['water_cement_ratio']), "—"],
                    ["Nominal Mix Ratio", _mix['nominal_ratio'], "—"],
                ]
                t_mat = Table(mat_tbl, colWidths=[170, 100, 130])
                t_mat.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.darkorange),
                    ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.black),
                    ('FONTSIZE', (0,0), (-1,-1), 9),
                ]))
                elements.append(t_mat)
                elements.append(Paragraph("Note: Indicative quantities per IS 10262:2019. Add 3-5% wastage for actual procurement.", styles["Normal"]))
            except Exception as _e:
                elements.append(Paragraph(f"Mix design data error: {_e}", styles["Normal"]))
            elements.append(Spacer(1, 12))
        
        # --- Beam L/d Check ---
        if all_beams:
            elements.append(Paragraph("Beam L/d Deflection Check (IS 456 Cl 23.2)", styles["Heading1"]))
            try:
                ld_tbl = [["Beam ID", "Span (mm)", "Depth (mm)", "Actual L/d", "Allowable", "Status"]]
                for _b in all_beams:
                    try:
                        _dx = _b.end_point.x - _b.start_point.x
                        _dy = _b.end_point.y - _b.start_point.y
                        _span_m = (_dx**2 + _dy**2)**0.5
                        _span_mm = _span_m * 1000
                        _dep = getattr(_b.properties, 'depth_mm', 0) if hasattr(_b, 'properties') else 0
                        _ald = _span_mm / _dep if _dep > 0 else 0
                        _allow = 7.0 if getattr(getattr(_b, 'properties', None), 'is_cantilever', False) else 20.0
                        _st = "PASS" if _ald <= _allow else "FAIL"
                        ld_tbl.append([getattr(_b, 'id', '?'), f"{_span_mm:.0f}", f"{_dep:.0f}",
                                       f"{_ald:.1f}", f"{_allow:.0f}", _st])
                    except Exception:
                        continue
                t_ld = Table(ld_tbl, repeatRows=1)
                t_ld.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.teal),
                    ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.black),
                    ('FONTSIZE', (0,0), (-1,-1), 8),
                ]))
                elements.append(t_ld)
            except Exception as _e:
                elements.append(Paragraph(f"L/d check error: {_e}", styles["Normal"]))
            elements.append(Spacer(1, 12))
        
        # --- Stability & Fire Resistance ---
        if stab_checks and stab_summary:
            elements.append(Paragraph("Stability & Fire Resistance (IS 456 Table 16A)", styles["Heading1"]))
            try:
                _total = stab_summary.total_members
                _pass_st = stab_summary.passed_stability
                _pass_fr = stab_summary.passed_fire
                elements.append(Paragraph(
                    f"Members Checked: {_total} | Passed Stability: {_pass_st}/{_total} | Passed Fire: {_pass_fr}/{_total}",
                    styles["Normal"]
                ))
                if stab_summary.recommendations:
                    for _r in stab_summary.recommendations:
                        elements.append(Paragraph(f"• {_r}", styles["Normal"]))
            except Exception as _e:
                elements.append(Paragraph(f"Stability data error: {_e}", styles["Normal"]))
            elements.append(Spacer(1, 12))
        
        # --- Code Compliance Audit ---
        if audit_results:
            elements.append(Paragraph("Code Compliance Audit", styles["Heading1"]))
            audit_tbl = [["Check", "Status", "Notes"]]
            for _ar in audit_results:
                _chk = getattr(_ar, 'check_name', getattr(_ar, 'rule', str(_ar)))
                _st = getattr(_ar, 'status', 'OK')
                _notes = getattr(_ar, 'message', getattr(_ar, 'notes', ''))
                audit_tbl.append([str(_chk)[:40], str(_st), str(_notes)[:60]])
            t_audit = Table(audit_tbl, repeatRows=1, colWidths=[150, 60, 190])
            t_audit.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.darkgreen),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('GRID', (0,0), (-1,-1), 0.5, colors.black),
                ('FONTSIZE', (0,0), (-1,-1), 8),
            ]))
            elements.append(t_audit)
            elements.append(Spacer(1, 12))

        # 14. PROFESSIONAL DISCLAIMER (CRITICAL)
        elements.append(Spacer(1, 24))
        elements.append(Paragraph("14. Professional Disclaimer", styles["Heading1"]))
        
        disclaimer_text = """
        <b>IMPORTANT NOTICE - READ CAREFULLY</b><br/><br/>
        
        This structural design report is generated by automated software for <b>PRELIMINARY DESIGN 
        AND EDUCATIONAL PURPOSES ONLY</b>.<br/><br/>
        
        <b>Key Limitations:</b><br/>
        • The software uses simplified analysis methods (tributary area, short column assumptions).<br/>
        • Seismic forces (IS 1893) and Wind loads (IS 875 Pt 3) have been incorporated for basic checks, but require full dynamic analysis for high-rise buildings.<br/>
        • Site-specific soil conditions, groundwater, and other geotechnical factors are not evaluated.<br/>
        • Local building codes may have additional requirements beyond IS 456:2000.<br/><br/>
        
        <b>Required Actions Before Construction:</b><br/>
        • All designs MUST be reviewed and sealed by a licensed Professional Engineer (PE).<br/>
        • Independent structural analysis should be performed using appropriate software.<br/>
        • Geotechnical investigation and foundation recommendations are required.<br/>
        • All applicable permits and approvals must be obtained.<br/><br/>
        
        <b>Liability Disclaimer:</b><br/>
        The developers, operators, and distributors of this software assume NO LIABILITY for any 
        damages, losses, or injuries arising from the use of designs produced by this tool. 
        Use of this software constitutes acceptance of this disclaimer.
        """
        
        # Create a bordered paragraph for emphasis
        disclaimer_style = ParagraphStyle(
            'Disclaimer',
            parent=styles['Normal'],
            fontSize=9,
            leading=12,
            borderWidth=1,
            borderColor=colors.red,
            borderPadding=10,
            backColor=colors.Color(1, 0.95, 0.95)  # Light red background
        )
        elements.append(Paragraph(disclaimer_text, disclaimer_style))
        
        # Footer with code reference
        elements.append(Spacer(1, 12))
        footer_text = """
        <i>Generated by StructOptima. This report is a preliminary design aid compliant with 
        IS 456:2000, IS 1893:2016, IS 13920:2016.<br/>
        All designs must be verified by a licensed Structural Engineer prior to construction.<br/>
        Safety Factors: γc = 1.5 (concrete), γs = 1.15 (steel) | Load Factor: 1.5 (DL + LL)<br/>
        © 2026 StructOptima — Built by Srinidh Ameerpeta & Charan Tej | v1.0.0</i>
        """
        elements.append(Paragraph(footer_text, styles["Normal"]))

        doc.build(elements)

    def generate_summary_report(self, filename: str, grid_mgr: GridManager, bom: MaterialCost, use_fly_ash: bool = False):
        """Generate executive summary and cost report."""
        doc = SimpleDocTemplate(filename, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()
        
        elements.append(Paragraph("Structural Design Summary Report", styles["Title"]))
        elements.append(Spacer(1, 12))
        
        # Executive Summary
        elements.append(Paragraph("Executive Summary", styles["Heading1"]))
        summary_data = [
            ["Parameter", "Value"],
            ["Total Floor Area", f"{grid_mgr.width_m * grid_mgr.length_m:.2f} m²"],
            ["Number of Stories", f"{grid_mgr.num_stories}"],
            ["Story Height", f"{grid_mgr.story_height_m:.2f} m"],
            ["Total Columns", f"{len(grid_mgr.columns)}"],
            ["Total Concrete", f"{bom.total_concrete_vol_m3:.2f} m³"],
            ["Total Steel", f"{bom.total_steel_weight_kg:.0f} kg"],
            ["Estimated Cost", f"INR {bom.total_cost_inr:,.2f}"],
            ["Carbon Footprint", f"{bom.total_carbon_kg/1000:.2f} Tonnes CO2e"]
        ]
        
        t = Table(summary_data, colWidths=[200, 200])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 20))
        
        # Cost Breakdown
        elements.append(Paragraph("Cost Breakdown", styles["Heading1"]))
        cost_data = [
            ["Item", "Quantity", "Rate", "Amount (INR)"],
            ["Concrete", f"{bom.total_concrete_vol_m3:.2f} m³", "₹5,000/m³", f"₹{bom.concrete_cost_inr:,.2f}"],
            ["Steel", f"{bom.total_steel_weight_kg:.0f} kg", "₹60/kg", f"₹{bom.steel_cost_inr:,.2f}"],
            ["TOTAL", "", "", f"₹{bom.total_cost_inr:,.2f}"]
        ]
        
        t = Table(cost_data, colWidths=[100, 100, 100, 100])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 20))
        
        # Sustainability
        elements.append(Paragraph("Sustainability Metrics", styles["Heading1"]))
        green_status = "Green Concrete (Fly Ash)" if use_fly_ash else "Standard OPC"
        elements.append(Paragraph(f"<b>Concrete Type:</b> {green_status}", styles["Normal"]))
        elements.append(Spacer(1, 10))
        
        carb_data = [
            ["Material", "Emission Factor", "Total CO2e (kg)"],
            ["Concrete", f"{'200' if use_fly_ash else '300'} kg/m³", f"{bom.concrete_carbon_kg:.1f}"],
            ["Steel", "1.85 kg/kg", f"{bom.steel_carbon_kg:.1f}"],
            ["TOTAL", "", f"{bom.total_carbon_kg:.1f}"]
        ]
        
        t = Table(carb_data, colWidths=[130, 130, 130])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ]))
        elements.append(t)
        
        doc.build(elements)
    
    def generate_schedule_report(self, filename: str, grid_mgr: GridManager, footings=None, *args, **kwargs):
        """Generate member schedules (columns, beams, slabs, footings)."""
        doc = SimpleDocTemplate(filename, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()
        
        elements.append(Paragraph("Design Schedules Report", styles["Title"]))
        elements.append(Spacer(1, 12))
        
        # Column Schedule
        elements.append(Paragraph("Column Schedule", styles["Heading1"]))
        col_data = [["ID", "Level", "Size (mm)", "Load (kN)", "Main Steel", "Stirrups"]]
        
        sorted_cols = sorted(grid_mgr.columns, key=lambda c: (c.x, c.y, c.level))
        for col in sorted_cols:
            main_rebar = "-"
            ties = "-"
            if hasattr(grid_mgr, 'rebar_schedule') and col.id in grid_mgr.rebar_schedule:
                res = grid_mgr.rebar_schedule[col.id]
                main_rebar = res.main_bars_desc
                ties = res.links_desc
            
            col_data.append([
                col.id, f"L{col.level}",
                f"{int(col.width_nb)}x{int(col.depth_nb)}",
                f"{col.load_kn:.1f}", main_rebar, ties
            ])
        
        t = Table(col_data, repeatRows=1, colWidths=[50, 40, 60, 60, 80, 80])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 20))
        
        # Beam Schedule
        elements.append(Paragraph("Beam Schedule", styles["Heading1"]))
        beam_data = [["ID", "Size", "Top Steel", "Bottom Steel", "Stirrups"]]
        
        if hasattr(grid_mgr, 'beam_schedule') and grid_mgr.beam_schedule:
            for bid in sorted(grid_mgr.beam_schedule.keys()):
                det = grid_mgr.beam_schedule[bid]
                beam_data.append([
                    bid, det.size_label,
                    det.top_bars_desc, det.bottom_bars_desc, det.stirrups_desc
                ])
        
        t = Table(beam_data, repeatRows=1, colWidths=[50, 60, 80, 80, 100])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkorange),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 20))
        
        # Slab Schedule
        elements.append(Paragraph("Slab Schedule", styles["Heading1"]))
        slab_data = [["ID", "Thickness (mm)", "Main Steel", "Distribution Steel"]]
        
        if hasattr(grid_mgr, 'slab_schedule') and grid_mgr.slab_schedule:
            for sid, det in grid_mgr.slab_schedule.items():
                slab_data.append([
                    sid, f"{det.thickness_mm:.0f}",
                    det.main_steel_desc, det.dist_steel_desc
                ])
        
        t = Table(slab_data, repeatRows=1, colWidths=[80, 80, 120, 120])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.purple),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 20))
        
        # Foundation Schedule
        elements.append(Paragraph("Foundation Schedule", styles["Heading1"]))
        ft_data = [["Col ID", "Load (kN)", "Size (m)", "Depth (mm)", "Concrete (m³)"]]
        passed_footings = footings if footings is not None else kwargs.get('footings', [])
        if isinstance(passed_footings, dict):
            passed_footings = list(passed_footings.values())
        if passed_footings:
            level_0_cols = [c for c in grid_mgr.columns if getattr(c, 'level', 0) == 0]
            for col, ft in zip(level_0_cols, passed_footings):
                if ft is not None:
                    ft_data.append([
                        getattr(col, 'id', '-'), f"{getattr(col, 'load_kn', 0.0):.1f}",
                        f"{getattr(ft, 'length_m', 0.0):.2f}x{getattr(ft, 'width_m', 0.0):.2f}",
                        f"{getattr(ft, 'thickness_mm', 0.0):.0f}", f"{getattr(ft, 'concrete_vol_m3', 0.0):.2f}"
                    ])
        
        t = Table(ft_data, repeatRows=1, colWidths=[60, 60, 100, 70, 80])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        elements.append(t)
        
        # Wall Schedule & Material Takeoff
        elements.append(Spacer(1, 20))
        elements.append(Paragraph("Masonry Wall Schedule & Material Takeoff", styles["Heading1"]))
        wall_data = [["Wall ID", "Span / Cols", "Len (m)", "Ht (m)", "Thk", "Bricks", "Mortar (m3)", "Cem (kg)", "Sand (T)", "Plaster (m2)"]]
        if hasattr(grid_mgr, 'walls') and grid_mgr.walls:
            from .wall_calculator import WallCalculator
            wall_calc = WallCalculator(mortar_ratio=4, wc_ratio=0.50)
            wall_bom_rep = wall_calc.calculate_all(
                grid_mgr.walls,
                num_stories=getattr(grid_mgr, 'num_stories', 1),
                floor_height_m=getattr(grid_mgr, 'story_height_m', 3.0),
                slab_thickness_mm=125.0,
                beam_depth_mm=400.0,
            )
            for sec in wall_bom_rep.wall_sections:
                span_label = f"{sec.col_start}→{sec.col_end}" if (sec.col_start and sec.col_end) else "Bay"
                wall_data.append([
                    sec.wall_id, span_label, f"{sec.length_m:.2f}", f"{sec.clear_height_m:.2f}",
                    f"{int(sec.core_thickness_m * 1000)}mm", f"{sec.num_bricks:,}", f"{sec.wet_mortar_vol_m3:.3f}",
                    f"{sec.mortar_cement_kg:.1f}", f"{sec.mortar_sand_tonnes:.2f}", f"{sec.plaster_area_m2:.1f}"
                ])
        else:
            wall_data.append(["N/A", "-", "-", "-", "-", "-", "-", "-", "-", "-"])
            
        t_w_sched = Table(wall_data, repeatRows=1, colWidths=[50, 60, 45, 40, 40, 50, 60, 50, 50, 55])
        t_w_sched.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkorange),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 7.5),
        ]))
        elements.append(t_w_sched)
        
        doc.build(elements)
    
    def generate_audit_report(self, filename: str, grid_mgr: GridManager, audit_results: List = [], math_breakdown: List[str] = []):
        """Generate structural audit report with math verification."""
        doc = SimpleDocTemplate(filename, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()
        
        elements.append(Paragraph("Structural Audit Report", styles["Title"]))
        elements.append(Spacer(1, 12))
        
        # Audit Summary
        passed = len([r for r in audit_results if r.status == "PASS"])
        failed = len([r for r in audit_results if r.status == "FAIL"])
        total = len(audit_results)
        
        elements.append(Paragraph("Audit Summary", styles["Heading1"]))
        elements.append(Paragraph(f"<b>Total Checks:</b> {total}", styles["Normal"]))
        elements.append(Paragraph(f"<b>Passed:</b> {passed}", styles["Normal"]))
        elements.append(Paragraph(f"<b>Failed:</b> {failed}", styles["Normal"]))
        elements.append(Spacer(1, 20))
        
        # Audit Results Table
        if audit_results:
            elements.append(Paragraph("Detailed Audit Results", styles["Heading1"]))
            audit_data = [["Member", "Check", "Design", "Limit", "Status"]]
            
            for res in audit_results:
                audit_data.append([
                    res.member_id, res.check_name,
                    f"{res.design_value:.1f}", f"{res.limit_value:.1f}",
                    res.status
                ])
            
            t = Table(audit_data, repeatRows=1, colWidths=[60, 120, 70, 70, 50])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.black),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
            ]))
            elements.append(t)
            elements.append(Spacer(1, 20))
        
        # Math Breakdown
        if math_breakdown:
            elements.append(Paragraph("Math Verification Logs", styles["Heading1"]))
            for log in math_breakdown[:20]:
                elements.append(Paragraph(f"<pre>{log}</pre>", styles["Code"]))
                elements.append(Spacer(1, 6))
        
        doc.build(elements)
    
    def generate_floor_report(self, filename: str, grid_mgr: GridManager, level: int, bom: 'MaterialCost' = None):
        """Generate structural report for a specific floor level."""
        doc = SimpleDocTemplate(filename, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()
        
        elements.append(Paragraph(f"Floor {level} Structural Report", styles["Title"]))
        elements.append(Spacer(1, 12))
        
        # Floor Summary
        cols_at_level = [c for c in grid_mgr.columns if c.level == level]
        elements.append(Paragraph("Floor Summary", styles["Heading1"]))
        elements.append(Paragraph(f"<b>Level:</b> {level}", styles["Normal"]))
        elements.append(Paragraph(f"<b>Floor Height:</b> {grid_mgr.story_height_m:.2f} m", styles["Normal"]))
        elements.append(Paragraph(f"<b>Columns at this level:</b> {len(cols_at_level)}", styles["Normal"]))
        elements.append(Spacer(1, 20))
        
        # Column Schedule for this level
        elements.append(Paragraph("Column Schedule", styles["Heading1"]))
        col_data = [["ID", "Location (x,y)", "Size (mm)", "Load (kN)", "Main Steel", "Stirrups"]]
        
        for col in cols_at_level:
            main_rebar = "-"
            ties = "-"
            if hasattr(grid_mgr, 'rebar_schedule') and col.id in grid_mgr.rebar_schedule:
                res = grid_mgr.rebar_schedule[col.id]
                main_rebar = res.main_bars_desc
                ties = res.links_desc
            
            col_data.append([
                col.id, f"({col.x:.2f}, {col.y:.2f})",
                f"{int(col.width_nb)}x{int(col.depth_nb)}",
                f"{col.load_kn:.1f}", main_rebar, ties
            ])
        
        t = Table(col_data, repeatRows=1, colWidths=[50, 80, 60, 60, 80, 80])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 20))
        
        # Beam Schedule
        elements.append(Paragraph("Beam Schedule", styles["Heading1"]))
        beam_data = [["ID", "Size", "Top Steel", "Bottom Steel", "Stirrups"]]
        
        if hasattr(grid_mgr, 'beam_schedule') and grid_mgr.beam_schedule:
            for bid in sorted(grid_mgr.beam_schedule.keys()):
                det = grid_mgr.beam_schedule[bid]
                beam_data.append([
                    bid, det.size_label,
                    det.top_bars_desc, det.bottom_bars_desc, det.stirrups_desc
                ])
        
        t = Table(beam_data, repeatRows=1, colWidths=[50, 60, 80, 80, 100])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkorange),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 20))
        
        # Slab at this level
        elements.append(Paragraph("Slab Schedule", styles["Heading1"]))
        slab_data = [["ID", "Thickness (mm)", "Main Steel", "Distribution Steel"]]
        
        if hasattr(grid_mgr, 'slab_schedule') and grid_mgr.slab_schedule:
            for sid, det in grid_mgr.slab_schedule.items():
                slab_data.append([
                    sid, f"{det.thickness_mm:.0f}",
                    det.main_steel_desc, det.dist_steel_desc
                ])
        
        t = Table(slab_data, repeatRows=1, colWidths=[80, 80, 120, 120])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.purple),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        elements.append(t)
        
        doc.build(elements)
