"""
BBS Report Generator - PDF generation for Bar Bending Schedules.

Generates professional PDF reports with:
    - Member-wise BBS tables
    - Steel summary by diameter
    - Cutting length details
    - Total quantities
"""

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import mm
from typing import List, Optional

from .bbs_module import (
    ProjectBBS, MemberBBS, BBSEntry,
    BeamBBSInput, ColumnBBSInput, SlabBBSInput,
    generate_beam_bbs, generate_column_bbs, generate_slab_bbs,
    generate_project_bbs
)


class BBSReportGenerator:
    """Generates PDF Bar Bending Schedule reports."""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles for BBS reports."""
        self.styles.add(ParagraphStyle(
            'BBSTitle',
            parent=self.styles['Title'],
            fontSize=18,
            spaceAfter=20,
            textColor=colors.darkblue
        ))
        
        self.styles.add(ParagraphStyle(
            'MemberHeader',
            parent=self.styles['Heading2'],
            fontSize=12,
            textColor=colors.darkgreen,
            spaceBefore=15,
            spaceAfter=8
        ))
        
        self.styles.add(ParagraphStyle(
            'TableNote',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.grey,
            italics=True
        ))
    
    def generate_bbs_report(
        self,
        filename: str,
        project_bbs: ProjectBBS,
        project_name: str = "Bar Bending Schedule"
    ):
        """
        Generate complete BBS report as PDF.
        
        Args:
            filename: Output PDF filename
            project_bbs: ProjectBBS object with all member BBS data
            project_name: Title for the report
        """
        doc = SimpleDocTemplate(
            filename,
            pagesize=A4,
            rightMargin=15*mm,
            leftMargin=15*mm,
            topMargin=20*mm,
            bottomMargin=20*mm
        )
        elements = []
        
        # Title
        elements.append(Paragraph(project_name, self.styles['BBSTitle']))
        elements.append(Paragraph(
            "IS 456:2000 Based | Non-Seismic Detailing",
            self.styles['Normal']
        ))
        elements.append(Spacer(1, 15))
        
        # Design Assumptions Box
        elements.append(Paragraph("Design Assumptions", self.styles['Heading2']))
        assumptions = """
        <b>Hook Lengths:</b> 90° = 9d, 135° = 10d (IS 456 Cl. 26.2.2.1)<br/>
        <b>Development Length:</b> Ld = 0.87·fy·d / (4·τbd) for HYSD bars<br/>
        <b>Steel Density:</b> 7850 kg/m³<br/>
        <b>Stirrup Hooks:</b> 135° both ends<br/>
        <b>Lap Splice:</b> Not included (single bar lengths assumed)
        """
        elements.append(Paragraph(assumptions, self.styles['Normal']))
        elements.append(Spacer(1, 20))
        
        # Project Summary
        elements.append(Paragraph("Steel Summary", self.styles['Heading1']))
        summary_data = [["Bar Diameter (mm)", "Weight (kg)", "% of Total"]]
        
        sorted_dias = sorted(project_bbs.summary_by_diameter.keys())
        for dia in sorted_dias:
            wt = project_bbs.summary_by_diameter[dia]
            pct = (wt / project_bbs.total_steel_kg * 100) if project_bbs.total_steel_kg > 0 else 0
            summary_data.append([str(dia), f"{wt:.2f}", f"{pct:.1f}%"])
        
        summary_data.append(["TOTAL", f"{project_bbs.total_steel_kg:.2f}", "100%"])
        
        t_summary = Table(summary_data, colWidths=[80, 100, 80])
        t_summary.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
        ]))
        elements.append(t_summary)
        elements.append(Spacer(1, 20))
        
        # Member-wise BBS
        elements.append(PageBreak())
        elements.append(Paragraph("Member-wise Bar Bending Schedule", self.styles['Heading1']))
        
        # Group by member type
        beams = [m for m in project_bbs.members if m.member_type == "beam"]
        columns = [m for m in project_bbs.members if m.member_type == "column"]
        slabs = [m for m in project_bbs.members if m.member_type == "slab"]
        
        # Beams
        if beams:
            elements.append(Paragraph("BEAMS", self.styles['Heading2']))
            for member in beams:
                elements.extend(self._create_member_table(member))
        
        # Columns
        if columns:
            elements.append(Paragraph("COLUMNS", self.styles['Heading2']))
            for member in columns:
                elements.extend(self._create_member_table(member))
        
        # Slabs
        if slabs:
            elements.append(Paragraph("SLABS", self.styles['Heading2']))
            for member in slabs:
                elements.extend(self._create_member_table(member))
        
        # Footer
        elements.append(Spacer(1, 30))
        elements.append(Paragraph(
            "<i>All quantities to be verified on site. Wastage allowance (3-5%) to be added separately.</i>",
            self.styles['TableNote']
        ))
        
        doc.build(elements)
    
    def _create_member_table(self, member: MemberBBS) -> List:
        """Create table elements for a single member BBS."""
        elements = []
        
        # Member header
        header_text = f"<b>{member.member_id}</b> | {member.member_type.upper()} | {member.member_size}"
        elements.append(Paragraph(header_text, self.styles['MemberHeader']))
        
        # BBS table
        bbs_data = [["Mark", "Dia (mm)", "Shape", "Cut Len (mm)", "Nos", "Unit Wt", "Total (kg)"]]
        
        for entry in member.entries:
            # Truncate shape description if too long
            shape = entry.shape_code
            if len(shape) > 25:
                shape = shape[:22] + "..."
            
            bbs_data.append([
                entry.bar_mark,
                str(entry.bar_diameter_mm),
                shape,
                f"{entry.cutting_length_mm:.0f}",
                str(entry.number_of_bars),
                f"{entry.unit_weight_kg_per_m:.3f}",
                f"{entry.total_weight_kg:.2f}"
            ])
        
        # Total row
        bbs_data.append(["", "", "", "", "", "TOTAL:", f"{member.total_weight_kg:.2f}"])
        
        t = Table(bbs_data, colWidths=[35, 40, 120, 55, 35, 45, 50])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (2, 0), (2, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('BACKGROUND', (0, -1), (-1, -1), colors.Color(0.95, 0.95, 0.95)),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 10))
        
        return elements


def generate_bbs_from_grid_manager(grid_mgr, beams_list, project_name: str = "Project") -> ProjectBBS:
    """
    Generate ProjectBBS from GridManager data.
    
    Args:
        grid_mgr: GridManager with column, beam, slab schedules
        beams_list: List of beam StructuralMember objects
        project_name: Project identifier
        
    Returns:
        ProjectBBS with all member BBS data
    """
    beam_inputs = []
    column_inputs = []
    slab_inputs = []
    
    # Extract beam BBS inputs from beam_schedule
    if hasattr(grid_mgr, 'beam_schedule') and grid_mgr.beam_schedule:
        for bid, det in grid_mgr.beam_schedule.items():
            # Find corresponding beam from list
            beam_obj = None
            for b in beams_list:
                if b.id == bid:
                    beam_obj = b
                    break
            
            if beam_obj and beam_obj.end_point:
                # Calculate beam length from start and end points
                dx = beam_obj.end_point.x - beam_obj.start_point.x
                dy = beam_obj.end_point.y - beam_obj.start_point.y
                beam_length_m = (dx**2 + dy**2) ** 0.5
                
                beam_inputs.append(BeamBBSInput(
                    member_id=bid,
                    length_mm=beam_length_m * 1000,
                    width_mm=beam_obj.properties.width_mm,
                    depth_mm=beam_obj.properties.depth_mm,
                    clear_cover_mm=25,
                    main_bar_dia_mm=16,
                    top_bars=2,
                    bottom_bars=4,
                    stirrup_dia_mm=8,
                    stirrup_spacing_mm=150
                ))
    
    # Extract column BBS inputs
    level_0_cols = [c for c in grid_mgr.columns if c.level == 0]
    for col in level_0_cols:
        # Get rebar info if available
        main_dia = 16
        num_bars = 8
        tie_spacing = 150
        
        if hasattr(grid_mgr, 'rebar_schedule') and col.id in grid_mgr.rebar_schedule:
            res = grid_mgr.rebar_schedule[col.id]
            main_dia = res.phi_main if hasattr(res, 'phi_main') else 16
        
        column_inputs.append(ColumnBBSInput(
            member_id=col.id,
            height_mm=grid_mgr.story_height_m * 1000,
            width_mm=col.width_nb,
            depth_mm=col.depth_nb,
            clear_cover_mm=40,
            main_bar_dia_mm=main_dia,
            num_bars=num_bars,
            tie_dia_mm=8,
            tie_spacing_mm=tie_spacing
        ))
    
    # Extract slab BBS inputs
    if hasattr(grid_mgr, 'slab_schedule') and grid_mgr.slab_schedule:
        for sid, det in grid_mgr.slab_schedule.items():
            slab_inputs.append(SlabBBSInput(
                member_id=sid,
                lx_mm=4000,
                ly_mm=5000,
                thickness_mm=det.thickness_mm,
                clear_cover_mm=20,
                main_bar_dia_mm=10,
                main_bar_spacing_mm=150,
                dist_bar_dia_mm=8,
                dist_bar_spacing_mm=200
            ))
    
    return generate_project_bbs(beam_inputs, column_inputs, slab_inputs, project_name)
