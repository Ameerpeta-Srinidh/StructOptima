import sys, os, math
sys.path.insert(0, os.getcwd())

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from src.grid_manager import GridManager
from src.materials import Concrete
from src.wall_calculator import WallCalculator

def build_all_tables():
    gm = GridManager(width_m=12.0, length_m=9.0, num_stories=2, story_height_m=3.0)
    gm.generate_grid()
    gm.generate_walls(wall_thickness_mm=200.0, include_interior=True)
    
    wall_calc = WallCalculator(mortar_ratio=4, wc_ratio=0.50)
    wb = wall_calc.calculate_all(
        gm.walls,
        num_stories=2,
        floor_height_m=3.0,
        slab_thickness_mm=125.0,
        beam_depth_mm=400.0
    )
    num_stories = 2

    # 1. Brickwork Table
    brick_data = [["Wall ID", "Span / Cols", "Len (m)", "Ht (m)", "Thk", "Gross (m³)", "Bricks", "Brick Vol", "Wet Mor", "Dry Mor", "Cem Bags", "Cem (kg)", "Sand (T)", "Water (L)"]]
    for sec in wb.wall_sections:
        span_label = f"{sec.col_start}→{sec.col_end}" if (sec.col_start and sec.col_end) else "Bay"
        brick_data.append([
            sec.wall_id, span_label, f"{sec.length_m:.2f}", f"{sec.clear_height_m:.2f}",
            f"{int(sec.core_thickness_m * 1000)}mm", f"{sec.wall_volume_m3 * num_stories:.2f}",
            f"{sec.num_bricks * num_stories:,}", f"{sec.total_brick_vol_m3 * num_stories:.2f}",
            f"{sec.wet_mortar_vol_m3 * num_stories:.3f}", f"{sec.dry_mortar_vol_m3 * num_stories:.3f}",
            f"{int(math.ceil(sec.mortar_cement_kg * num_stories / 50.0))}",
            f"{sec.mortar_cement_kg * num_stories:.1f}", f"{sec.mortar_sand_tonnes * num_stories:.2f}",
            f"{sec.mortar_water_litres * num_stories:.0f}",
        ])
    tot_vol = wb.total_wall_volume_m3
    tot_bricks = wb.total_bricks
    tot_brk_vol = sum(s.total_brick_vol_m3 for s in wb.wall_sections) * num_stories
    tot_wet = sum(s.wet_mortar_vol_m3 for s in wb.wall_sections) * num_stories
    tot_dry = sum(s.dry_mortar_vol_m3 for s in wb.wall_sections) * num_stories
    tot_cem_kg = wb.total_mortar_cement_kg
    tot_cem_bags = wb.total_mortar_cement_bags
    tot_sand_t = wb.total_mortar_sand_tonnes
    tot_water_l = wb.total_mortar_water_litres
    brick_data.append([
        "TOTAL", "All Walls", "-", "-", "-",
        f"{tot_vol:.2f}", f"{tot_bricks:,}", f"{tot_brk_vol:.2f}",
        f"{tot_wet:.2f}", f"{tot_dry:.2f}", f"{tot_cem_bags:,}",
        f"{tot_cem_kg:,.0f}", f"{tot_sand_t:.2f}", f"{tot_water_l:,.0f}"
    ])
    t_brick = Table(brick_data, repeatRows=1, colWidths=[36, 44, 28, 26, 28, 38, 38, 36, 38, 38, 36, 38, 36, 34])
    t_brick.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkorange),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 6.5),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightyellow),
        ('FONTWEIGHT', (0, -1), (-1, -1), 'BOLD'),
    ]))

    # 2. Plastering Table
    # ["Surface ID", "Location & Mix Spec", "Area (m²)", "Thk (mm)", "Mix", "Wet Vol (m³)", "Dry Vol (m³)", "Cement (Bags)", "Cement (kg)", "Sand (T)", "Water (L)"]
    plaster_data = [["Surface ID", "Location & Mix Spec", "Area (m²)", "Thk (mm)", "Mix", "Wet Vol (m³)", "Dry Vol (m³)", "Cem (Bags)", "Cem (kg)", "Sand (T)", "Water (L)"]]
    tot_p_area = 0.0
    tot_p_wet = 0.0
    tot_p_dry = 0.0
    tot_p_cem_kg = 0.0
    tot_p_sand_t = 0.0
    tot_p_water_l = 0.0

    for sec in wb.wall_sections:
        if sec.is_exterior:
            # Ext side: 15mm, 1:4
            a_ext = (sec.length_m * sec.clear_height_m) * num_stories
            w_ext = a_ext * 0.015
            d_ext = w_ext * 1.33
            c_ext_kg = (d_ext / 5.0) * 1440.0
            c_ext_bags = int(math.ceil(c_ext_kg / 50.0))
            s_ext_t = ((d_ext * 4.0 / 5.0) * 1600.0) / 1000.0
            wat_ext_l = c_ext_kg * 0.50
            plaster_data.append([
                f"{sec.wall_id}_EXT", "Ext Render (15mm 1:4)", f"{a_ext:.1f}", "15", "1:4",
                f"{w_ext:.3f}", f"{d_ext:.3f}", f"{c_ext_bags}", f"{c_ext_kg:.1f}", f"{s_ext_t:.2f}", f"{wat_ext_l:.0f}"
            ])
            tot_p_area += a_ext
            tot_p_wet += w_ext
            tot_p_dry += d_ext
            tot_p_cem_kg += c_ext_kg
            tot_p_sand_t += s_ext_t
            tot_p_water_l += wat_ext_l

            # Int side: 12mm, 1:6
            a_int = (sec.length_m * sec.clear_height_m) * num_stories
            w_int = a_int * 0.012
            d_int = w_int * 1.33
            c_int_kg = (d_int / 7.0) * 1440.0
            c_int_bags = int(math.ceil(c_int_kg / 50.0))
            s_int_t = ((d_int * 6.0 / 7.0) * 1600.0) / 1000.0
            wat_int_l = c_int_kg * 0.50
            plaster_data.append([
                f"{sec.wall_id}_INT", "Int Wall (12mm 1:6)", f"{a_int:.1f}", "12", "1:6",
                f"{w_int:.3f}", f"{d_int:.3f}", f"{c_int_bags}", f"{c_int_kg:.1f}", f"{s_int_t:.2f}", f"{wat_int_l:.0f}"
            ])
            tot_p_area += a_int
            tot_p_wet += w_int
            tot_p_dry += d_int
            tot_p_cem_kg += c_int_kg
            tot_p_sand_t += s_int_t
            tot_p_water_l += wat_int_l
        else:
            # Both sides interior: 12mm, 1:6
            a_int = (sec.length_m * sec.clear_height_m * 2.0) * num_stories
            w_int = a_int * 0.012
            d_int = w_int * 1.33
            c_int_kg = (d_int / 7.0) * 1440.0
            c_int_bags = int(math.ceil(c_int_kg / 50.0))
            s_int_t = ((d_int * 6.0 / 7.0) * 1600.0) / 1000.0
            wat_int_l = c_int_kg * 0.50
            plaster_data.append([
                f"{sec.wall_id}", "Int Part (2-Face 12mm 1:6)", f"{a_int:.1f}", "12", "1:6",
                f"{w_int:.3f}", f"{d_int:.3f}", f"{c_int_bags}", f"{c_int_kg:.1f}", f"{s_int_t:.2f}", f"{wat_int_l:.0f}"
            ])
            tot_p_area += a_int
            tot_p_wet += w_int
            tot_p_dry += d_int
            tot_p_cem_kg += c_int_kg
            tot_p_sand_t += s_int_t
            tot_p_water_l += wat_int_l

    # Ceiling Soffit Plaster
    w_m = float(getattr(gm, 'width_m', 0.0) or 0.0)
    l_m = float(getattr(gm, 'length_m', 0.0) or 0.0)
    a_ceil = w_m * l_m * num_stories
    if a_ceil > 0.0:
        w_ceil = a_ceil * 0.006
        d_ceil = w_ceil * 1.33
        c_ceil_kg = (d_ceil / 4.0) * 1440.0
        c_ceil_bags = int(math.ceil(c_ceil_kg / 50.0))
        s_ceil_t = ((d_ceil * 3.0 / 4.0) * 1600.0) / 1000.0
        wat_ceil_l = c_ceil_kg * 0.50
        plaster_data.append([
            "Ceiling Soffit", "Slab Bottom (6mm 1:3)", f"{a_ceil:.1f}", "6", "1:3",
            f"{w_ceil:.3f}", f"{d_ceil:.3f}", f"{c_ceil_bags}", f"{c_ceil_kg:.1f}", f"{s_ceil_t:.2f}", f"{wat_ceil_l:.0f}"
        ])
        tot_p_area += a_ceil
        tot_p_wet += w_ceil
        tot_p_dry += d_ceil
        tot_p_cem_kg += c_ceil_kg
        tot_p_sand_t += s_ceil_t
        tot_p_water_l += wat_ceil_l

    tot_p_cem_bags = int(math.ceil(tot_p_cem_kg / 50.0))
    plaster_data.append([
        "TOTAL", "All Plaster Surfaces", f"{tot_p_area:.1f}", "-", "-",
        f"{tot_p_wet:.3f}", f"{tot_p_dry:.3f}", f"{tot_p_cem_bags:,}", f"{tot_p_cem_kg:,.0f}", f"{tot_p_sand_t:.2f}", f"{tot_p_water_l:,.0f}"
    ])

    t_plaster = Table(plaster_data, repeatRows=1, colWidths=[44, 86, 44, 34, 32, 42, 42, 42, 46, 42, 38])
    t_plaster.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.1, 0.45, 0.45)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 6.5),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightyellow),
        ('FONTWEIGHT', (0, -1), (-1, -1), 'BOLD'),
    ]))

    # 3. Painting Table
    # ["Surface ID", "Location & Specification", "Finish Area (m²)", "Primer 1-Ct (L)", "Putty 2-Ct (kg)", "Int Emulsion 2-Ct (L)", "Ext Weather 2-Ct (L)"]
    paint_data = [["Surface ID", "Location & Specification", "Finish Area (m²)", "Primer 1-Ct (L)", "Putty 2-Ct (kg)", "Int Emulsion 2-Ct (L)", "Ext Weather 2-Ct (L)"]]
    tot_pt_area = 0.0
    tot_primer = 0.0
    tot_putty = 0.0
    tot_em_int = 0.0
    tot_em_ext = 0.0

    for sec in wb.wall_sections:
        if sec.is_exterior:
            a_ext = (sec.length_m * sec.clear_height_m) * num_stories
            pr_ext = a_ext / 8.0
            we_ext = (a_ext * 2.0) / 10.0
            paint_data.append([
                f"{sec.wall_id}_EXT", "External Weather Guard", f"{a_ext:.1f}", f"{pr_ext:.1f}", "—", "—", f"{we_ext:.1f}"
            ])
            tot_pt_area += a_ext
            tot_primer += pr_ext
            tot_em_ext += we_ext

            a_int = (sec.length_m * sec.clear_height_m) * num_stories
            pr_int = a_int / 8.0
            pu_int = a_int * 1.5
            em_int = (a_int * 2.0) / 12.0
            paint_data.append([
                f"{sec.wall_id}_INT", "Internal Acrylic Emulsion", f"{a_int:.1f}", f"{pr_int:.1f}", f"{pu_int:.1f}", f"{em_int:.1f}", "—"
            ])
            tot_pt_area += a_int
            tot_primer += pr_int
            tot_putty += pu_int
            tot_em_int += em_int
        else:
            a_int = (sec.length_m * sec.clear_height_m * 2.0) * num_stories
            pr_int = a_int / 8.0
            pu_int = a_int * 1.5
            em_int = (a_int * 2.0) / 12.0
            paint_data.append([
                f"{sec.wall_id}", "Internal Partition Emulsion", f"{a_int:.1f}", f"{pr_int:.1f}", f"{pu_int:.1f}", f"{em_int:.1f}", "—"
            ])
            tot_pt_area += a_int
            tot_primer += pr_int
            tot_putty += pu_int
            tot_em_int += em_int

    if a_ceil > 0.0:
        pr_ceil = a_ceil / 8.0
        pu_ceil = a_ceil * 1.5
        em_ceil = (a_ceil * 2.0) / 12.0
        paint_data.append([
            "Ceiling Soffit", "Slab Underside (White Emulsion)", f"{a_ceil:.1f}", f"{pr_ceil:.1f}", f"{pu_ceil:.1f}", f"{em_ceil:.1f}", "—"
        ])
        tot_pt_area += a_ceil
        tot_primer += pr_ceil
        tot_putty += pu_ceil
        tot_em_int += em_ceil

    paint_data.append([
        "TOTAL", "All Surfaces (Walls + Ceilings)", f"{tot_pt_area:.1f}", f"{tot_primer:.1f}", f"{tot_putty:,.1f}", f"{tot_em_int:.1f}", f"{tot_em_ext:.1f}"
    ])

    t_paint = Table(paint_data, repeatRows=1, colWidths=[55, 115, 50, 65, 70, 70, 70])
    t_paint.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.2, 0.25, 0.5)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightyellow),
        ('FONTWEIGHT', (0, -1), (-1, -1), 'BOLD'),
    ]))

    doc = SimpleDocTemplate("scratch/test_report_all.pdf", pagesize=A4, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    elements = [
        Paragraph("Test Brickwork Table", getSampleStyleSheet()["Heading1"]),
        t_brick,
        Spacer(1, 15),
        Paragraph("Test Plaster Table", getSampleStyleSheet()["Heading1"]),
        t_plaster,
        Spacer(1, 15),
        Paragraph("Test Paint Table", getSampleStyleSheet()["Heading1"]),
        t_paint
    ]
    doc.build(elements)
    print("All tables built into scratch/test_report_all.pdf successfully!")

if __name__ == "__main__":
    build_all_tables()
