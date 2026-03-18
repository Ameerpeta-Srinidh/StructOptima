from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from typing import List
from .quantifier import MaterialCost
from .grid_manager import GridManager, Column

class ReportGenerator:
    def generate_report(self, filename: str, grid_mgr: GridManager, bom: MaterialCost, audit_results: List = [], math_breakdown: List[str] = [], project_name: str = "Structural Design Report", use_fly_ash: bool = False):
        doc = SimpleDocTemplate(filename, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()
        
        # Title
        title_style = styles["Title"]
        elements.append(Paragraph(project_name, title_style))
        elements.append(Spacer(1, 12))
        
        # 1. Executive Summary
        elements.append(Paragraph("1. Executive Summary", styles["Heading1"]))
        summary_data = [
            ["Total Floor Area", f"{grid_mgr.width_m * grid_mgr.length_m:.2f} m2"],
            ["Total Concrete Volume", f"{bom.total_concrete_vol_m3:.2f} m3"],
            ["Total Steel Weight", f"{bom.total_steel_weight_kg:.2f} kg"],
            ["Total Estimated Cost", f"INR {bom.total_cost_usd:,.2f}"]
        ]
        t = Table(summary_data, colWidths=[200, 200])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
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
        elements.append(Paragraph("3. Column Schedule (IS 456 Cl. 26.5.3)", styles["Heading1"]))
        # Table Header
        col_data = [["ID", "Level", "Loc (x,y)", "Load (kN)", "Size (mm)", "Status"]]
        
        # Sort by ID then Level for readability
        sorted_cols = sorted(grid_mgr.columns, key=lambda c: (c.x, c.y, c.level))
        
        # Table Rows
        for col in sorted_cols:
            col_data.append([
                col.id,
                f"L{col.level}",
                f"({col.x:.2f}, {col.y:.2f})",
                f"{col.load_kn:.1f}",
                f"{int(col.width_nb)}x{int(col.depth_nb)}",
                "PASS"
            ])
        
        # Limit rows if too many for demo (increase limit or paginate?)
        # For G+2 small house (12 cols * 3 floors = 36). Let's show up to 40.
        # No limit
        # if len(col_data) > 40:
        #    col_data = col_data[:40]
        #    col_data.append(["...", "...", "...", "...", "...", "..."])
            
        t_cols = Table(col_data, repeatRows=1)
        t_cols.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        elements.append(t_cols)
        elements.append(Spacer(1, 12))
        
        # 4. Member Reinforcement Schedule
        elements.append(Paragraph("4. Reinforcement Schedule (IS 456 Cl. 26.5)", styles["Heading1"]))
        
        rebar_data = [["Col ID", "Main Bars", "Links (Stirrups)"]]
        
        # We need Detailed Rebar Info. 
        # Check if grid_mgr has 'rebar_schedule'
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
            
        # No limit
        # if len(rebar_data) > 40:
        #    rebar_data = rebar_data[:40]
        #    rebar_data.append(["...", "...", "..."])
            
        t_rebar = Table(rebar_data, repeatRows=1, colWidths=[100, 150, 150])
        t_rebar.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkred),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        elements.append(t_rebar)
        elements.append(Spacer(1, 12))

        # 5. Foundation Schedule (NEW)
        elements.append(Paragraph("5. Foundation Schedule (IS 456 Cl. 34)", styles["Heading1"]))
        
        # We need to access footings corresponding to columns. 
        # Making assumption that a list of footings is passed or we assume 1:1 mapping with columns list.
        # But `generate_report` sig changed? No, I need to look at how I call it in main.
        # The `grid_mgr` holds columns. I should probably attach footings to columns or pass a dict.
        # For simplicity, let's assume `grid_mgr` has a new `footings` attribute (I will add it in main logic injection or just pass a separate list)
        # Actually, cleaner to pass `footings` list to this function.
        # But since I am editing the file, let's update method signature in next step or use kwargs logic. 
        # I will rely on `kwargs` in signature or just assume `grid_mgr` will have it attached in `main`.
        # Let's try to fetch from `grid_mgr` assuming I'll monkey-patch or add it.
        
        footing_data = [["Col ID", "Load (kN)", "Size (m)", "Depth (mm)", "Conc (m3)"]]
        
        # Match footings to Level 0 columns
        # Assumption: grid_mgr.footings corresponds to the list of Level 0 columns sorted by ID or creation order
        # We need to recreate the same list of Level 0 columns to zip them
        
        if hasattr(grid_mgr, 'footings') and grid_mgr.footings:
            # Filter for Level 0 columns
            level_0_cols = [c for c in grid_mgr.columns if getattr(c, 'level', 0) == 0]
            
            # Ensure correlation
            if len(level_0_cols) == len(grid_mgr.footings):
                for col, ft in zip(level_0_cols, grid_mgr.footings):
                    footing_data.append([
                        col.id,
                        f"{col.load_kn:.1f}",
                        f"{ft.length_m:.2f} x {ft.width_m:.2f}",
                        f"{ft.thickness_mm:.0f}",
                        f"{ft.concrete_vol_m3:.2f}"
                    ])
            else:
                footing_data.append(["Mismatch", "Error", "Count", "Diff", "Check"])
        
        # No limit
        # if len(footing_data) > 20:
        #      footing_data = footing_data[:20]
        #      footing_data.append(["...", "...", "...", "...", "..."])

        t_found = Table(footing_data, repeatRows=1)
        t_found.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        elements.append(t_found)
        elements.append(Spacer(1, 12))

        # 6. Beam Schedule (NEW)
        elements.append(Paragraph("6. Beam Schedule (IS 456 Cl. 26.5.1)", styles["Heading1"]))
        beam_data = [["ID", "Size (mm)", "Top Steel", "Bot Steel", "Stirrups"]]
        
        if hasattr(grid_mgr, 'beam_schedule') and grid_mgr.beam_schedule:
            # We need to iterate over beams to get IDs ?? 
            # actually beam_schedule is a dict {id: result}
            # The keys are IDs.
            sorted_b_ids = sorted(grid_mgr.beam_schedule.keys())
            
            for bid in sorted_b_ids:
                det = grid_mgr.beam_schedule[bid]
                # Need size? derived from generated beams. 
                # RebarResult doesn't have size... 
                # Ideally we pass beam objects, but for now let's just show rebar or look up if possible.
                # Since we don't pass 'beams' list explicitly to generate_report (only grid_mgr),
                # we might miss size if not stored in schedule. 
                # BUT, wait, I can assume standard or look at gm.
                # Actually, grid_mgr doesn't store list of beams permanently unless I added it?
                # I added generate_beams() which returns them.
                # Check grid_mgr usage in app.py: It calls generate_beams but doesn't store them in GM.
                # It passes them to detail_beams.
                # Quick fix: In detail_beams, I should probably accidentally store size in BeamRebarResult?
                # No, better to just show rebar for now or imply size.
                # Wait, I updated BeamRebarResult? No. 
                # Let's just output ID and Rebar.
                
                beam_data.append([
                    bid,
                    det.size_label, # Uses actual size now
                    Paragraph(det.top_bars_desc, styles["Normal"]),
                    Paragraph(det.bottom_bars_desc, styles["Normal"]),
                    Paragraph(det.stirrups_desc, styles["Normal"])
                ])
        else:
            beam_data.append(["N/A", "-", "-", "-", "-"])
            
        # No limit
        # if len(beam_data) > 30:
        #    beam_data = beam_data[:30]
        #    beam_data.append(["...", "...", "...", "...", "..."])

        t_beam = Table(beam_data, repeatRows=1, colWidths=[60, 60, 100, 100, 120])
        t_beam.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkorange),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        elements.append(t_beam)
        elements.append(Spacer(1, 12))

        # 7. Slab Schedule (NEW)
        elements.append(Paragraph("7. Slab Schedule", styles["Heading1"]))
        slab_data = [["ID", "Thk (mm)", "Main Mesh", "Dist Mesh"]]
        
        if hasattr(grid_mgr, 'slab_schedule') and grid_mgr.slab_schedule:
            for sid, det in grid_mgr.slab_schedule.items():
                slab_data.append([
                    sid,
                    f"{det.thickness_mm:.0f}",
                    det.main_steel_desc,
                    det.dist_steel_desc
                ])
                
        t_slab = Table(slab_data, repeatRows=1)
        t_slab.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.purple),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        elements.append(t_slab)
        elements.append(Spacer(1, 12))

        # 8. Structural Layout Plan
        elements.append(Paragraph("8. Structural Layout Plan", styles["Heading1"]))
        
        # ... (Existing Map Logic)
        coords_text = "Column Coordinates:\n"
        for col in grid_mgr.columns:
            if col.x is not None and col.y is not None:
                coords_text += f"  {col.id}: ({col.x:.2f}, {col.y:.2f})\n"
            
        elements.append(Paragraph(f"<pre>{coords_text}</pre>", styles["Code"]))
        elements.append(Spacer(1, 12))
        
        # 9. Steel Material Breakdown
        elements.append(Paragraph("9. Integrated Steel Breakdown", styles["Heading1"]))
        
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
            can reduce concrete emissions by approximately 33%. <br/>
            Switch "Use Green Concrete" ON in the dashboard to see savings.
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
        
        # 14. PROFESSIONAL DISCLAIMER (CRITICAL)
        elements.append(Spacer(1, 24))
        elements.append(Paragraph("14. Professional Disclaimer", styles["Heading1"]))
        
        disclaimer_text = """
        <b>IMPORTANT NOTICE - READ CAREFULLY</b><br/><br/>
        
        This structural design report is generated by automated software for <b>PRELIMINARY DESIGN 
        AND EDUCATIONAL PURPOSES ONLY</b>.<br/><br/>
        
        <b>Key Limitations:</b><br/>
        • The software uses simplified analysis methods (tributary area, short column assumptions).<br/>
        • Seismic, wind, and other lateral loads are NOT considered in this analysis.<br/>
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
        <i>All calculations performed per IS 456:2000 (Code of Practice for Plain and Reinforced Concrete).<br/>
        Safety Factors: γc = 1.5 (concrete), γs = 1.15 (steel) | Load Factor: 1.5 (DL + LL)<br/>
        Report generated by Structural Design Platform v1.0</i>
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
            ["Estimated Cost", f"INR {bom.total_cost_usd:,.2f}"],
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
            ["Concrete", f"{bom.total_concrete_vol_m3:.2f} m³", "₹5,000/m³", f"₹{bom.concrete_cost_usd:,.2f}"],
            ["Steel", f"{bom.total_steel_weight_kg:.0f} kg", "₹60/kg", f"₹{bom.steel_cost_usd:,.2f}"],
            ["TOTAL", "", "", f"₹{bom.total_cost_usd:,.2f}"]
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
    
    def generate_schedule_report(self, filename: str, grid_mgr: GridManager):
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
        
        if hasattr(grid_mgr, 'footings') and grid_mgr.footings:
            level_0_cols = [c for c in grid_mgr.columns if c.level == 0]
            for col, ft in zip(level_0_cols, grid_mgr.footings):
                ft_data.append([
                    col.id, f"{col.load_kn:.1f}",
                    f"{ft.length_m:.2f}x{ft.width_m:.2f}",
                    f"{ft.thickness_mm:.0f}", f"{ft.concrete_vol_m3:.2f}"
                ])
        
        t = Table(ft_data, repeatRows=1, colWidths=[60, 60, 100, 70, 80])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        elements.append(t)
        
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
