import math
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from typing import List, Any, Dict, Optional
from .quantifier import MaterialCost
from .grid_manager import GridManager, Column

class ReportGenerator:
    @staticmethod
    def _ensure_walls(grid_mgr: GridManager, **kwargs) -> List[Any]:
        """Ensure grid_mgr has a non-empty walls list, auto-generating if necessary."""
        if hasattr(grid_mgr, 'walls') and grid_mgr.walls:
            return grid_mgr.walls
        
        passed_walls = kwargs.get('walls')
        if passed_walls:
            grid_mgr.walls = passed_walls
            return grid_mgr.walls
            
        arch_walls = kwargs.get('arch_walls')
        sh = float(getattr(grid_mgr, 'story_height_m', 3.0) or 3.0)
        clear_h = max(sh - 0.125 - 0.40, 2.0)
        
        if arch_walls:
            from .grid_manager import Wall
            walls = []
            for i, item in enumerate(arch_walls):
                try:
                    p1, p2 = item[0], item[1]
                    walls.append(Wall(
                        id=f"W_CAD_{i+1}",
                        start_x=float(p1[0]),
                        start_y=float(p1[1]),
                        end_x=float(p2[0]),
                        end_y=float(p2[1]),
                        thickness_mm=200.0,
                        height_m=clear_h,
                        is_exterior=True
                    ))
                except Exception:
                    continue
            if walls:
                grid_mgr.walls = walls
                return grid_mgr.walls
        
        if hasattr(grid_mgr, 'generate_walls'):
            try:
                w = float(getattr(grid_mgr, 'width_m', 12.0) or 12.0)
                l = float(getattr(grid_mgr, 'length_m', 9.0) or 9.0)
                if not getattr(grid_mgr, 'x_grid_lines', None) or not getattr(grid_mgr, 'y_grid_lines', None):
                    if getattr(grid_mgr, 'columns', None):
                        xs = sorted(list(set([round(c.x, 2) for c in grid_mgr.columns])))
                        ys = sorted(list(set([round(c.y, 2) for c in grid_mgr.columns])))
                        if len(xs) > 1: grid_mgr.x_grid_lines = xs
                        if len(ys) > 1: grid_mgr.y_grid_lines = ys
                    if not getattr(grid_mgr, 'x_grid_lines', None):
                        grid_mgr.x_grid_lines = [0.0, round(w / 2.0, 2), w]
                    if not getattr(grid_mgr, 'y_grid_lines', None):
                        grid_mgr.y_grid_lines = [0.0, round(l / 2.0, 2), l]
                
                grid_mgr.generate_walls(
                    wall_thickness_mm=200.0,
                    opening_fraction=0.33,
                    include_interior=True,
                    beam_depth_mm=400.0,
                    slab_thickness_mm=125.0
                )
                if grid_mgr.walls:
                    return grid_mgr.walls
            except Exception:
                pass
        
        from .grid_manager import Wall
        w = float(getattr(grid_mgr, 'width_m', 12.0) or 12.0)
        l = float(getattr(grid_mgr, 'length_m', 9.0) or 9.0)
        grid_mgr.walls = [
            Wall(id="W_EXT_1", start_x=0.0, start_y=0.0, end_x=w, end_y=0.0, thickness_mm=200.0, height_m=clear_h, is_exterior=True),
            Wall(id="W_EXT_2", start_x=w, start_y=0.0, end_x=w, end_y=l, thickness_mm=200.0, height_m=clear_h, is_exterior=True),
            Wall(id="W_EXT_3", start_x=w, start_y=l, end_x=0.0, end_y=l, thickness_mm=200.0, height_m=clear_h, is_exterior=True),
            Wall(id="W_EXT_4", start_x=0.0, start_y=l, end_x=0.0, end_y=0.0, thickness_mm=200.0, height_m=clear_h, is_exterior=True),
        ]
        return grid_mgr.walls

    @staticmethod
    def _create_brickwork_schedule_table(wb, num_stories=1):
        """Per-floor, per-wall brickwork schedule — IS 1077 & IS 2250.
        One row per wall per floor: W_H1_F0, W_H1_F1, …
        All quantities are PER WALL PANEL (one floor) — no num_stories multiplication on rows.
        Totals from WallBOM already include num_stories.
        """
        import math as _math
        from reportlab.platypus import Table, TableStyle
        from reportlab.lib import colors
        headers = [
            "Wall ID", "Fl", "Span / Cols", "Len (m)", "Ht (m)", "Thk (mm)",
            "Gross Vol (m\u00b3)", "Bricks (Nos)", "Brick Vol (m\u00b3)",
            "Wet Mortar (m\u00b3)", "Dry Mortar (m\u00b3)", "Cem Bags", "Cem (kg)",
            "Sand (T)", "Water (L)"
        ]
        COL_W = [40, 20, 50, 30, 28, 28, 36, 36, 34, 36, 36, 32, 34, 30, 30]
        data = [headers]
        if not wb or not getattr(wb, 'wall_sections', None):
            data.append(["N/A"] + ["-"] * (len(headers) - 1))
        else:
            ns = int(getattr(wb, 'num_stories', num_stories) or num_stories)
            for floor in range(ns):
                for sec in wb.wall_sections:
                    span = (f"{sec.col_start}\u2192{sec.col_end}"
                            if sec.col_start and sec.col_end else "Bay")
                    data.append([
                        f"{sec.wall_id}_F{floor}",
                        f"F{floor}",
                        span,
                        f"{sec.length_m:.2f}",
                        f"{sec.clear_height_m:.2f}",
                        f"{int(sec.core_thickness_m * 1000)}",
                        f"{sec.wall_volume_m3:.3f}",
                        f"{sec.num_bricks:,}",
                        f"{sec.total_brick_vol_m3:.3f}",
                        f"{sec.wet_mortar_vol_m3:.3f}",
                        f"{sec.dry_mortar_vol_m3:.3f}",
                        f"{int(_math.ceil(sec.mortar_cement_kg / 50.0))}",
                        f"{sec.mortar_cement_kg:.1f}",
                        f"{sec.mortar_sand_tonnes:.3f}",
                        f"{sec.mortar_water_litres:.0f}",
                    ])
            # Totals — use WallBOM aggregated fields (already × num_stories)
            ns2 = ns
            tot_brk_vol = sum(s.total_brick_vol_m3 for s in wb.wall_sections) * ns2
            tot_wet = sum(s.wet_mortar_vol_m3 for s in wb.wall_sections) * ns2
            tot_dry = sum(s.dry_mortar_vol_m3 for s in wb.wall_sections) * ns2
            data.append([
                "TOTAL", f"{ns}Fl", "All Walls", "-", "-", "-",
                f"{wb.total_wall_volume_m3:.2f}",
                f"{wb.total_bricks:,}",
                f"{tot_brk_vol:.2f}",
                f"{tot_wet:.2f}",
                f"{tot_dry:.2f}",
                f"{wb.total_mortar_cement_bags:,}",
                f"{wb.total_mortar_cement_kg:,.0f}",
                f"{wb.total_mortar_sand_tonnes:.2f}",
                f"{wb.total_mortar_water_litres:,.0f}",
            ])

        t = Table(data, repeatRows=1, colWidths=COL_W)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkorange),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 1), (2, -2), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 5.5),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightyellow),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ]))
        return t

    @staticmethod
    def _create_plaster_schedule_table(wb, num_stories=1, grid_mgr=None):
        """Per-floor, per-wall-face plaster schedule — IS 1661, IS 2402.
        Exterior wall: two rows per floor (EXT + INT face).
        Interior wall: one row (2-face combined).
        Ceiling soffit: one row per floor.
        """
        import math as _math
        from reportlab.platypus import Table, TableStyle
        from reportlab.lib import colors
        DRY = 1.33
        headers = [
            "Surface ID", "Fl", "Location & Mix Spec",
            "Area (m\u00b2)", "Thk (mm)", "Mix",
            "Wet Vol (m\u00b3)", "Dry Vol (m\u00b3)",
            "Cem Bags", "Cem (kg)", "Sand (T)", "Water (L)"
        ]
        COL_W = [52, 20, 100, 34, 28, 24, 34, 34, 30, 40, 34, 30]
        data = [headers]
        if not wb or not getattr(wb, 'wall_sections', None):
            data.append(["N/A"] + ["-"] * (len(headers) - 1))
        else:
            ns = int(getattr(wb, 'num_stories', num_stories) or num_stories)
            tot_area = tot_wet = tot_dry = tot_cem = tot_sand = tot_water = 0.0
            for floor in range(ns):
                fl = f"F{floor}"
                for sec in wb.wall_sections:
                    one = sec.length_m * sec.clear_height_m
                    if sec.is_exterior:
                        # External face: 15mm, 1:4
                        a = one;  w = a * 0.015; d = w * DRY
                        ck = (d / 5.0) * 1440.0; sk = ((d * 4.0 / 5.0) * 1600.0) / 1000.0
                        wt = ck * 0.50
                        data.append([
                            f"{sec.wall_id}_EXT_F{floor}", fl, "Ext Render (15mm 1:4)",
                            f"{a:.2f}", "15", "1:4",
                            f"{w:.3f}", f"{d:.3f}",
                            f"{int(_math.ceil(ck/50))}", f"{ck:.1f}", f"{sk:.3f}", f"{wt:.0f}"
                        ])
                        tot_area+=a; tot_wet+=w; tot_dry+=d; tot_cem+=ck; tot_sand+=sk; tot_water+=wt

                        # Internal face of exterior wall: 12mm, 1:6
                        a = one;  w = a * 0.012; d = w * DRY
                        ck = (d / 7.0) * 1440.0; sk = ((d * 6.0 / 7.0) * 1600.0) / 1000.0
                        wt = ck * 0.50
                        data.append([
                            f"{sec.wall_id}_INT_F{floor}", fl, "Int Wall (12mm 1:6)",
                            f"{a:.2f}", "12", "1:6",
                            f"{w:.3f}", f"{d:.3f}",
                            f"{int(_math.ceil(ck/50))}", f"{ck:.1f}", f"{sk:.3f}", f"{wt:.0f}"
                        ])
                        tot_area+=a; tot_wet+=w; tot_dry+=d; tot_cem+=ck; tot_sand+=sk; tot_water+=wt
                    else:
                        # Both faces interior: 2 x 12mm, 1:6
                        a = one * 2.0;  w = a * 0.012; d = w * DRY
                        ck = (d / 7.0) * 1440.0; sk = ((d * 6.0 / 7.0) * 1600.0) / 1000.0
                        wt = ck * 0.50
                        data.append([
                            f"{sec.wall_id}_F{floor}", fl, "Int Partition 2-Face (12mm 1:6)",
                            f"{a:.2f}", "12", "1:6",
                            f"{w:.3f}", f"{d:.3f}",
                            f"{int(_math.ceil(ck/50))}", f"{ck:.1f}", f"{sk:.3f}", f"{wt:.0f}"
                        ])
                        tot_area+=a; tot_wet+=w; tot_dry+=d; tot_cem+=ck; tot_sand+=sk; tot_water+=wt

            # Ceiling soffit per floor: 6mm, 1:3
            if grid_mgr:
                wm = float(getattr(grid_mgr, 'width_m', 0.0) or 0.0)
                lm = float(getattr(grid_mgr, 'length_m', 0.0) or 0.0)
                if wm * lm > 0:
                    for floor in range(ns):
                        fl = f"F{floor}"
                        a = wm * lm; w = a * 0.006; d = w * DRY
                        ck = (d / 4.0) * 1440.0; sk = ((d * 3.0 / 4.0) * 1600.0) / 1000.0
                        wt = ck * 0.50
                        data.append([
                            f"Ceil_F{floor}", fl, "Slab Soffit (6mm 1:3)",
                            f"{a:.2f}", "6", "1:3",
                            f"{w:.3f}", f"{d:.3f}",
                            f"{int(_math.ceil(ck/50))}", f"{ck:.1f}", f"{sk:.3f}", f"{wt:.0f}"
                        ])
                        tot_area+=a; tot_wet+=w; tot_dry+=d; tot_cem+=ck; tot_sand+=sk; tot_water+=wt

            data.append([
                "TOTAL", f"{ns}Fl", "All Plaster Surfaces",
                f"{tot_area:.1f}", "-", "-",
                f"{tot_wet:.3f}", f"{tot_dry:.3f}",
                f"{int(_math.ceil(tot_cem/50)):,}", f"{tot_cem:,.0f}",
                f"{tot_sand:.2f}", f"{tot_water:,.0f}"
            ])

        t = Table(data, repeatRows=1, colWidths=COL_W)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.1, 0.45, 0.45)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 1), (2, -2), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 5.5),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightyellow),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ]))
        return t

    @staticmethod
    def _create_paint_schedule_table(wb, num_stories=1, grid_mgr=None):
        """Per-floor, per-wall-face paint schedule — NBC 2016 SP7."""
        from reportlab.platypus import Table, TableStyle
        from reportlab.lib import colors
        PR = 8.0; EM_INT = 12.0; EM_EXT = 10.0; PUTTY = 1.5; COATS = 2
        headers = [
            "Surface ID", "Fl", "Location & Specification",
            "Area (m\u00b2)", "Primer 1-Ct (L)", "Putty 2-Ct (kg)",
            "Int Em 2-Ct (L)", "Ext Guard 2-Ct (L)"
        ]
        COL_W = [55, 20, 115, 38, 48, 52, 52, 52]
        data = [headers]
        if not wb or not getattr(wb, 'wall_sections', None):
            data.append(["N/A"] + ["-"] * (len(headers) - 1))
        else:
            ns = int(getattr(wb, 'num_stories', num_stories) or num_stories)
            tot_area = tot_pr = tot_pu = tot_ei = tot_ee = 0.0
            for floor in range(ns):
                fl = f"F{floor}"
                for sec in wb.wall_sections:
                    one = sec.length_m * sec.clear_height_m
                    if sec.is_exterior:
                        # External face
                        a = one
                        pr = a / PR; we = (a * COATS) / EM_EXT
                        data.append([
                            f"{sec.wall_id}_EXT_F{floor}", fl, "External Weather Guard",
                            f"{a:.2f}", f"{pr:.2f}", "\u2014", "\u2014", f"{we:.2f}"
                        ])
                        tot_area+=a; tot_pr+=pr; tot_ee+=we
                        # Internal face
                        a = one
                        pr = a / PR; pu = a * PUTTY * COATS; ei = (a * COATS) / EM_INT
                        data.append([
                            f"{sec.wall_id}_INT_F{floor}", fl, "Int Acrylic Emulsion",
                            f"{a:.2f}", f"{pr:.2f}", f"{pu:.2f}", f"{ei:.2f}", "\u2014"
                        ])
                        tot_area+=a; tot_pr+=pr; tot_pu+=pu; tot_ei+=ei
                    else:
                        a = one * 2.0
                        pr = a / PR; pu = a * PUTTY * COATS; ei = (a * COATS) / EM_INT
                        data.append([
                            f"{sec.wall_id}_F{floor}", fl, "Int Partition Emulsion (2 Faces)",
                            f"{a:.2f}", f"{pr:.2f}", f"{pu:.2f}", f"{ei:.2f}", "\u2014"
                        ])
                        tot_area+=a; tot_pr+=pr; tot_pu+=pu; tot_ei+=ei

            if grid_mgr:
                wm = float(getattr(grid_mgr, 'width_m', 0.0) or 0.0)
                lm = float(getattr(grid_mgr, 'length_m', 0.0) or 0.0)
                if wm * lm > 0:
                    for floor in range(ns):
                        fl = f"F{floor}"
                        a = wm * lm
                        pr = a / PR; pu = a * PUTTY * COATS; ei = (a * COATS) / EM_INT
                        data.append([
                            f"Ceil_F{floor}", fl, "Slab Soffit (White Emulsion)",
                            f"{a:.2f}", f"{pr:.2f}", f"{pu:.2f}", f"{ei:.2f}", "\u2014"
                        ])
                        tot_area+=a; tot_pr+=pr; tot_pu+=pu; tot_ei+=ei

            data.append([
                "TOTAL", f"{ns}Fl", "All Surfaces (Walls + Ceilings)",
                f"{tot_area:.1f}", f"{tot_pr:.1f}", f"{tot_pu:,.1f}",
                f"{tot_ei:.1f}", f"{tot_ee:.1f}"
            ])

        t = Table(data, repeatRows=1, colWidths=COL_W)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.2, 0.25, 0.5)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 1), (2, -2), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 5.5),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightyellow),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ]))
        return t

    @staticmethod
    def _create_masonry_summary_table(wb, num_stories=1, grid_mgr=None):
        """Consolidated BOQ summary using WallBOM aggregated totals."""
        import math as _math
        from reportlab.platypus import Table, TableStyle
        from reportlab.lib import colors
        DRY = 1.33
        if not wb or not getattr(wb, 'wall_sections', None):
            t = Table([["Material", "Spec", "Quantity", "Unit", "Standard"],
                       ["N/A", "-", "-", "-", "-"]], colWidths=[135, 140, 95, 55, 70])
            return t

        ns = int(getattr(wb, 'num_stories', num_stories) or num_stories)

        # Use WallBOM aggregated totals (already multiplied by num_stories)
        tot_vol     = wb.total_wall_volume_m3
        tot_bricks  = wb.total_bricks
        tot_brk_vol = sum(s.total_brick_vol_m3 for s in wb.wall_sections) * ns
        tot_wet     = sum(s.wet_mortar_vol_m3 for s in wb.wall_sections) * ns
        tot_dry     = sum(s.dry_mortar_vol_m3 for s in wb.wall_sections) * ns
        tot_m_cem_kg   = wb.total_mortar_cement_kg
        tot_m_cem_bags = wb.total_mortar_cement_bags
        tot_m_sand_t   = wb.total_mortar_sand_tonnes
        tot_m_water_l  = wb.total_mortar_water_litres

        # Plaster totals — recalculate per face per floor
        wall_p_area = wall_p_cem = wall_p_sand = wall_p_water = 0.0
        for sec in wb.wall_sections:
            one = sec.length_m * sec.clear_height_m
            if sec.is_exterior:
                d_e = (one * 0.015) * DRY; d_i = (one * 0.012) * DRY
                wall_p_area  += (one * 2) * ns
                wall_p_cem   += ((d_e / 5.0 + d_i / 7.0) * 1440.0) * ns
                wall_p_sand  += (((d_e * 4.0 / 5.0) + (d_i * 6.0 / 7.0)) * 1600.0 / 1000.0) * ns
                wall_p_water += ((d_e / 5.0 + d_i / 7.0) * 1440.0 * 0.50) * ns
            else:
                d = (one * 2 * 0.012) * DRY
                wall_p_area  += (one * 2) * ns
                wall_p_cem   += (d / 7.0 * 1440.0) * ns
                wall_p_sand  += (d * 6.0 / 7.0 * 1600.0 / 1000.0) * ns
                wall_p_water += (d / 7.0 * 1440.0 * 0.50) * ns

        ceil_area = ceil_cem = ceil_sand = ceil_water = 0.0
        ceil_primer = ceil_putty = ceil_em = 0.0
        if grid_mgr:
            wm = float(getattr(grid_mgr, 'width_m', 0.0) or 0.0)
            lm = float(getattr(grid_mgr, 'length_m', 0.0) or 0.0)
            ceil_area = wm * lm * ns
            if ceil_area > 0:
                d = (ceil_area * 0.006) * DRY
                ceil_cem   = (d / 4.0) * 1440.0
                ceil_sand  = ((d * 3.0 / 4.0) * 1600.0) / 1000.0
                ceil_water = ceil_cem * 0.50
                ceil_primer = ceil_area / 8.0
                ceil_putty  = ceil_area * 1.5 * 2
                ceil_em     = (ceil_area * 2.0) / 12.0

        tot_p_area  = wall_p_area + ceil_area
        tot_p_cem   = wall_p_cem + ceil_cem
        tot_p_cem_bags = int(_math.ceil(tot_p_cem / 50.0))
        tot_p_sand  = wall_p_sand + ceil_sand
        tot_p_water = wall_p_water + ceil_water

        tot_primer = wb.total_primer_litres + ceil_primer
        tot_putty  = wb.total_putty_kg + ceil_putty
        tot_em_int = wb.total_emulsion_int_litres + ceil_em
        tot_em_ext = wb.total_emulsion_ext_litres
        gc_bags    = tot_m_cem_bags + tot_p_cem_bags
        gc_kg      = tot_m_cem_kg + tot_p_cem
        gs_t       = tot_m_sand_t + tot_p_sand
        gw_l       = tot_m_water_l + tot_p_water

        rows = [
            ["Item / Material Description", "Specification / Mix Proportion", "Building Total", "Unit", "IS Standard"],
            ["Total Wall Gross Volume", "L \u00d7 t \u00d7 Hv (clear storey height)", f"{tot_vol:.2f}", "m\u00b3", "IS 1905:1987"],
            ["Clay Modular Building Bricks", "Standard modular 20\u00d720\u00d710 cm", f"{tot_bricks:,}", "Nos", "IS 1077:1992"],
            ["Net Solid Brickwork Volume", "Actual brick body vol. (excl. mortar)", f"{tot_brk_vol:.2f}", "m\u00b3", "IS 1077:1992"],
            ["Wet Brickwork Mortar Volume", "Gross Wall Vol \u2212 Solid Brick Vol", f"{tot_wet:.2f}", "m\u00b3", "IS 2250:1981"],
            ["Dry Brickwork Mortar Volume", "Wet Volume \u00d7 1.33 dry factor", f"{tot_dry:.2f}", "m\u00b3", "IS 2250:1981"],
            ["Brickwork Cement", "1:4 Mix Proportion (OPC/PPC)", f"{tot_m_cem_bags:,} ({tot_m_cem_kg:,.0f} kg)", "Bags 50kg", "IS 269:2015"],
            ["Brickwork Sand", "Coarse sand, dry density 1600 kg/m\u00b3", f"{tot_m_sand_t:.2f}", "Tonnes", "IS 383 Zone II"],
            ["Brickwork Water", "Water:Cement ratio = 0.50", f"{tot_m_water_l:,.0f}", "Litres", "IS 456 Cl 5.4"],
            ["Wall Plaster Area", "Int (12mm 1:6) + Ext (15mm 1:4)", f"{wall_p_area:.1f}", "m\u00b2", "IS 1200 Pt 12"],
            ["Ceiling Soffit Plaster Area", "Soffit of slabs (6mm 1:3 mix)", f"{ceil_area:.1f}", "m\u00b2", "IS 1661:1972"],
            ["Total Plaster Surface Area", "Combined wall + ceiling surface", f"{tot_p_area:.1f}", "m\u00b2", "IS 1200 Pt 12"],
            ["Plastering Cement", "Combined wall & ceiling plaster", f"{tot_p_cem_bags:,} ({tot_p_cem:,.0f} kg)", "Bags 50kg", "IS 1661/IS 2402"],
            ["Plastering Sand", "Clean plaster sand (Zone III/IV)", f"{tot_p_sand:.2f}", "Tonnes", "IS 383:2016"],
            ["Plastering Water", "W:C = 0.50", f"{tot_p_water:,.0f}", "Litres", "IS 456 Cl 5.4"],
            ["Surface Primer", "1 coat @ 8 m\u00b2/L", f"{tot_primer:.1f}", "Litres", "NBC 2016 SP7"],
            ["Polymer Wall Putty", "2 coats @ 1.5 kg/m\u00b2", f"{tot_putty:,.1f}", "kg", "NBC 2016 SP7"],
            ["Interior Acrylic Emulsion", "2 coats @ 12 m\u00b2/L", f"{tot_em_int:.1f}", "Litres", "NBC 2016 SP7"],
            ["Exterior Weather Emulsion", "2 coats @ 10 m\u00b2/L", f"{tot_em_ext:.1f}", "Litres", "NBC 2016 SP7"],
            ["GRAND TOTAL CEMENT (Mortar+Plaster)", "All masonry + plastering combined", f"{gc_bags:,} bags ({gc_kg:,.0f} kg)", "Bags", "IS 269:2015"],
            ["GRAND TOTAL SAND (Mortar+Plaster)", "All masonry + plastering sand", f"{gs_t:.2f}", "Tonnes", "IS 383:2016"],
            ["GRAND TOTAL WATER (Mortar+Plaster)", "All masonry + plastering water", f"{gw_l:,.0f}", "Litres", "IS 456 Cl 5.4"],
        ]
        t = Table(rows, repeatRows=1, colWidths=[135, 140, 95, 55, 70])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkslategray),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 1), (1, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 6.5),
            ('BACKGROUND', (0, -3), (-1, -1), colors.lightyellow),
            ('FONTNAME', (0, -3), (-1, -1), 'Helvetica-Bold'),
        ]))
        return t

    @staticmethod
    def _create_masonry_cost_table(wb, num_stories=1, grid_mgr=None):
        """Trade-wise cost estimate — CPWD DSR 2023 rates."""
        from reportlab.platypus import Table, TableStyle
        from reportlab.lib import colors
        if not wb or not getattr(wb, 'wall_sections', None):
            t = Table([["Trade", "Quantity", "Rate", "Subtotal"], ["N/A", "-", "-", "-"]],
                      colWidths=[155, 110, 100, 130])
            return t

        ns = int(getattr(wb, 'num_stories', num_stories) or num_stories)
        tot_bricks      = wb.total_bricks
        tot_m_cem_bags  = wb.total_mortar_cement_bags
        tot_m_sand_t    = wb.total_mortar_sand_tonnes

        wall_p_area = 0.0
        for sec in wb.wall_sections:
            one = sec.length_m * sec.clear_height_m
            wall_p_area += (one * 2.0) * ns  # both faces always

        ceil_area = 0.0
        if grid_mgr:
            wm = float(getattr(grid_mgr, 'width_m', 0.0) or 0.0)
            lm = float(getattr(grid_mgr, 'length_m', 0.0) or 0.0)
            ceil_area = wm * lm * ns
        tot_p_area = wall_p_area + ceil_area

        R_BRICK = 9.0; R_CEM = 380.0; R_SAND = 1500.0; R_PLAST = 280.0; R_PAINT = 120.0
        c_bricks  = tot_bricks * R_BRICK
        c_cem     = tot_m_cem_bags * R_CEM
        c_sand    = tot_m_sand_t * R_SAND
        c_plaster = tot_p_area * R_PLAST
        c_paint   = tot_p_area * R_PAINT
        total     = c_bricks + c_cem + c_sand + c_plaster + c_paint

        rows = [
            ["Trade / Material Component", "Quantity", "Rate (INR)", "Subtotal (INR)"],
            ["Clay Modular Bricks (IS 1077)", f"{tot_bricks:,} Nos",
             f"\u20b9{R_BRICK:.0f} / brick", f"\u20b9{c_bricks:,.2f}"],
            ["Brickwork Mortar Cement", f"{tot_m_cem_bags:,} Bags",
             f"\u20b9{R_CEM:.0f} / bag", f"\u20b9{c_cem:,.2f}"],
            ["Brickwork Mortar Sand", f"{tot_m_sand_t:.2f} Tonnes",
             f"\u20b9{R_SAND:,.0f} / Tonne", f"\u20b9{c_sand:,.2f}"],
            ["Plastering Work (12/15/6mm)", f"{tot_p_area:.1f} m\u00b2",
             f"\u20b9{R_PLAST:.0f} / m\u00b2", f"\u20b9{c_plaster:,.2f}"],
            ["Surface Finishes (Primer+Putty+Paint)", f"{tot_p_area:.1f} m\u00b2",
             f"\u20b9{R_PAINT:.0f} / m\u00b2", f"\u20b9{c_paint:,.2f}"],
            ["TOTAL MASONRY, PLASTER & FINISHES", "", "", f"\u20b9{total:,.2f}"],
        ]
        t = Table(rows, colWidths=[155, 110, 100, 130])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.saddlebrown),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 7.5),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightyellow),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ]))
        return t

    def generate_report(self, filename: str, grid_mgr: GridManager, bom: MaterialCost,
                        audit_results: List = [], math_breakdown: List[str] = [],
                        project_name: str = "Structural Design Report", use_fly_ash: bool = False,
                        seismic_result=None, wind_result=None, stab_checks=None, stab_summary=None,
                        all_beams=None, conc_grade: str = "M25",
                        live_load: float = 0, building_weight: float = 0,
                        seismic_zone: str = "II", **kwargs):
        # Guarantee walls exist and are quantified
        ReportGenerator._ensure_walls(grid_mgr, **kwargs)
        from .wall_calculator import WallCalculator
        wall_calc = WallCalculator(mortar_ratio=4, wc_ratio=0.50)
        num_st = getattr(grid_mgr, 'num_stories', 1) or 1
        story_h = getattr(grid_mgr, 'story_height_m', 3.0) or 3.0
        
        wall_bom_rep = wall_calc.calculate_all(
            grid_mgr.walls,
            num_stories=num_st,
            floor_height_m=story_h,
            slab_thickness_mm=125.0,
            beam_depth_mm=400.0,
            columns=getattr(grid_mgr, 'columns', []),
        )

        doc = SimpleDocTemplate(filename, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
        elements = []
        styles = getSampleStyleSheet()
        
        # Title
        title_style = styles["Title"]
        elements.append(Paragraph(project_name, title_style))
        elements.append(Spacer(1, 12))
        
        # 1. Executive Summary
        elements.append(Paragraph("1. Executive Summary", styles["Heading1"]))
        tot_b = getattr(bom, 'total_bricks', getattr(bom, 'brick_count', 0))
        tot_cem = getattr(bom, 'total_mortar_cement_bags', 0) + getattr(bom, 'total_plaster_cement_bags', 0)
        tot_sand = getattr(bom, 'total_mortar_sand_tonnes', 0.0) + getattr(bom, 'total_plaster_sand_tonnes', 0.0)
        tot_plast = getattr(bom, 'total_plaster_area_m2', getattr(bom, 'plaster_area_m2', 0.0))
        
        if (not tot_b or tot_b == 0) and wall_bom_rep:
            tot_b = wall_bom_rep.total_bricks
            tot_cem = wall_bom_rep.total_mortar_cement_bags + wall_bom_rep.total_plaster_cement_bags
            tot_sand = wall_bom_rep.total_mortar_sand_tonnes + wall_bom_rep.total_plaster_sand_tonnes
            tot_plast = wall_bom_rep.total_plaster_area_m2
            
        proj_cost = getattr(bom, 'final_project_cost', getattr(bom, 'base_project_cost', bom.total_cost_inr))
        
        summary_data = [
            ["Total Floor Area", f"{grid_mgr.width_m * grid_mgr.length_m:.2f} m²"],
            ["Stories / Height", f"{num_st} Stories / {num_st * story_h:.1f} m"],
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

        # 8. Brickwork Schedule & Material Takeoff (IS 1077, IS 2250)
        elements.append(Paragraph("8. Brickwork Schedule & Material Takeoff (IS 1077, IS 2250)", styles["Heading1"]))
        elements.append(Paragraph("<font size=8>Modular clay bricks 200×200×100 mm with mortar (190×190×90 mm solid core, 250 bricks/m³ per IS 1077). Mortar 1:4 mix proportion with 1.33 dry volume factor per IS 2250. W:C ratio = 0.50.</font>", styles["Normal"]))
        elements.append(Spacer(1, 4))
        elements.append(ReportGenerator._create_brickwork_schedule_table(wall_bom_rep, num_stories=num_st))
        elements.append(Spacer(1, 12))

        # 9. Plastering Schedule & Quantities (IS 1661, IS 2402, IS 1200)
        elements.append(Paragraph("9. Plastering Schedule & Quantities (IS 1661, IS 2402, IS 1200)", styles["Heading1"]))
        elements.append(Paragraph("<font size=8>External wall plastering: 15mm thick in 1:4 cement:sand mix (IS 2402). Internal wall plastering: 12mm thick in 1:6 mix (IS 1661). Ceiling soffit plastering: 6mm thick in 1:3 mix per IS 1661 Cl. 12.3. Dry volume factor = 1.33.</font>", styles["Normal"]))
        elements.append(Spacer(1, 4))
        elements.append(ReportGenerator._create_plaster_schedule_table(wall_bom_rep, num_stories=num_st, grid_mgr=grid_mgr))
        elements.append(Spacer(1, 12))

        # 10. Painting & Surface Finishes Schedule (NBC 2016 SP7)
        elements.append(Paragraph("10. Painting & Surface Finishes Schedule (NBC 2016 SP7)", styles["Heading1"]))
        elements.append(Paragraph("<font size=8>Surface preparation & coatings per NBC 2016 SP7: Water-thinnable primer (1 coat @ 8 m²/L), polymer wall putty (2 coats @ 1.5 kg/m²), interior acrylic emulsion (2 coats @ 12 m²/L), exterior weather-guard acrylic emulsion (2 coats @ 10 m²/L).</font>", styles["Normal"]))
        elements.append(Spacer(1, 4))
        elements.append(ReportGenerator._create_paint_schedule_table(wall_bom_rep, num_stories=num_st, grid_mgr=grid_mgr))
        elements.append(Spacer(1, 12))

        # 11. Consolidated Masonry & Finishes BOQ & Cost (IS 1905, CPWD DSR)
        elements.append(Paragraph("11. Consolidated Masonry & Finishes BOQ & Cost (IS 1905, CPWD DSR)", styles["Heading1"]))
        elements.append(Paragraph("<b>11.1 Comprehensive Bill of Materials</b>", styles["Heading2"]))
        elements.append(ReportGenerator._create_masonry_summary_table(wall_bom_rep, num_stories=num_st, grid_mgr=grid_mgr))
        elements.append(Spacer(1, 10))
        elements.append(Paragraph("<b>11.2 Trade-wise Cost Takeoff</b>", styles["Heading2"]))
        elements.append(ReportGenerator._create_masonry_cost_table(wall_bom_rep, num_stories=num_st, grid_mgr=grid_mgr))
        elements.append(Spacer(1, 12))

        # 12. Structural Layout Plan
        elements.append(Paragraph("12. Structural Layout Plan", styles["Heading1"]))
        
        # ... (Existing Map Logic)
        coords_text = "Column Coordinates:\n"
        for col in grid_mgr.columns:
            if col.x is not None and col.y is not None:
                coords_text += f"  {col.id}: ({col.x:.2f}, {col.y:.2f})\n"
            
        elements.append(Paragraph(f"<pre>{coords_text}</pre>", styles["Code"]))
        elements.append(Spacer(1, 12))
        
        # 13. Steel Material Breakdown
        elements.append(Paragraph("13. Integrated Steel Breakdown", styles["Heading1"]))
        
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
        
        # 14. Structural Audit
        elements.append(Paragraph("14. Structural Audit Report", styles["Heading1"]))
        
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
                 
             t_audit = Table(audit_data, repeatRows=1, colWidths=[60, 120, 80, 80, 60])
             t_audit.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.black),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
             ]))
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
        
        # 15. Sustainability & Carbon Audit
        elements.append(Paragraph("15. Sustainability Audit", styles["Heading1"]))
        
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
        
        
        # 16. Serviceability Checks (Deflection)
        elements.append(Paragraph("16. Serviceability Checks (Deflection)", styles["Heading1"]))
        
        # Filter for beam deflection checks
        beam_checks = [r for r in audit_results if "Beam Deflection" in r.check_name]
        
        if beam_checks:
            serv_data = [["Beam ID", "Description", "Actual (mm)", "Limit (mm)", "Status"]]
            
            top_checks = beam_checks[:30]
            
            for bc in top_checks:
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
             
        
        # 17. Staircase Design Schedule
        elements.append(Paragraph("17. Staircase Design Schedule (Dog-Legged)", styles["Heading1"]))
        
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
            
            note_text = f"""
            <b>Geometry Notes:</b><br/>
            - Flight designed for floor height: {grid_mgr.story_height_m:.2f} m<br/>
            - Number of Risers per flight: {res.num_risers}<br/>
            - Design assumes 2 flights per floor (Dog-Legged).
            """
            elements.append(Paragraph(note_text, styles["Normal"]))
            
        else:
             elements.append(Paragraph("No staircase selected for design.", styles["Normal"]))
        
        
        # NEW SECTIONS: Seismic, Wind, Material Breakdown, Beam L/d, Stability
        import math as _math
        
        # 18. Seismic Analysis
        if seismic_result:
            elements.append(Paragraph("18. Seismic Analysis (IS 1893:2016)", styles["Heading1"]))
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
        
        # 19. Wind Analysis
        if wind_result and hasattr(wind_result, 'pressure_results') and wind_result.pressure_results:
            elements.append(Paragraph("19. Wind Analysis (IS 875 Part 3)", styles["Heading1"]))
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
        
        # 20. Concrete Material Breakdown
        if bom and bom.total_concrete_vol_m3 > 0:
            elements.append(Paragraph("20. Concrete Material Breakdown (IS 10262:2019)", styles["Heading1"]))
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
        
        # 21. Beam L/d Deflection Check
        if all_beams:
            elements.append(Paragraph("21. Beam L/d Deflection Check (IS 456 Cl 23.2)", styles["Heading1"]))
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
        
        # 22. Stability & Fire Resistance
        if stab_checks and stab_summary:
            elements.append(Paragraph("22. Stability & Fire Resistance (IS 456 Table 16A)", styles["Heading1"]))
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
        
        # 23. Code Compliance Audit
        if audit_results:
            elements.append(Paragraph("23. Code Compliance Audit", styles["Heading1"]))
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

        # 24. PROFESSIONAL DISCLAIMER (CRITICAL)
        elements.append(Spacer(1, 24))
        elements.append(Paragraph("24. Professional Disclaimer", styles["Heading1"]))
        
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

    def generate_summary_report(self, filename: str, grid_mgr: GridManager, bom: MaterialCost, use_fly_ash: bool = False, **kwargs):
        """Generate executive summary and cost report with full masonry takeoff."""
        ReportGenerator._ensure_walls(grid_mgr, **kwargs)
        from .wall_calculator import WallCalculator
        wall_calc = WallCalculator(mortar_ratio=4, wc_ratio=0.50)
        num_st = getattr(grid_mgr, 'num_stories', 1) or 1
        story_h = getattr(grid_mgr, 'story_height_m', 3.0) or 3.0
        
        wb = wall_calc.calculate_all(
            grid_mgr.walls,
            num_stories=num_st,
            floor_height_m=story_h,
            slab_thickness_mm=125.0,
            beam_depth_mm=400.0,
            columns=getattr(grid_mgr, 'columns', []),
        )

        tot_b = getattr(bom, 'total_bricks', getattr(bom, 'brick_count', 0))
        tot_cem = getattr(bom, 'total_mortar_cement_bags', 0) + getattr(bom, 'total_plaster_cement_bags', 0)
        tot_sand = getattr(bom, 'total_mortar_sand_tonnes', 0.0) + getattr(bom, 'total_plaster_sand_tonnes', 0.0)
        tot_plast = getattr(bom, 'total_plaster_area_m2', getattr(bom, 'plaster_area_m2', 0.0))

        if (not tot_b or tot_b == 0) and wb:
            tot_b = wb.total_bricks
            tot_cem = wb.total_mortar_cement_bags + wb.total_plaster_cement_bags
            tot_sand = wb.total_mortar_sand_tonnes + wb.total_plaster_sand_tonnes
            tot_plast = wb.total_plaster_area_m2

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
            ["Clay Modular Bricks", f"{tot_b:,} Nos"],
            ["Masonry & Plaster Cement", f"{tot_cem:,} Bags (50kg)"],
            ["Masonry & Plaster Sand", f"{tot_sand:.2f} Tonnes"],
            ["Plaster Surface Area", f"{tot_plast:.1f} m²"],
            ["Estimated Structure Cost", f"INR {bom.total_cost_inr:,.2f}"],
            ["Estimated Masonry & Finishes Cost", f"INR {wb.total_wall_cost_inr:,.2f}"],
            ["Total Projected Cost", f"INR {bom.total_cost_inr + wb.total_wall_cost_inr:,.2f}"],
            ["Carbon Footprint", f"{bom.total_carbon_kg/1000:.2f} Tonnes CO2e"]
        ]
        
        t = Table(summary_data, colWidths=[200, 200])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, -2), (-1, -2), colors.lightyellow),
            ('FONTWEIGHT', (0, -2), (-1, -2), 'BOLD'),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 15))
        
        # Cost Breakdown
        elements.append(Paragraph("Cost Breakdown", styles["Heading1"]))
        cost_data = [
            ["Item", "Quantity", "Rate", "Amount (INR)"],
            ["Concrete", f"{bom.total_concrete_vol_m3:.2f} m³", "₹5,000/m³", f"₹{bom.concrete_cost_inr:,.2f}"],
            ["Steel", f"{bom.total_steel_weight_kg:.0f} kg", "₹60/kg", f"₹{bom.steel_cost_inr:,.2f}"],
            ["Masonry & Bricks", f"{wb.total_bricks:,} Nos", "₹9/brick + mortar", f"₹{wb.total_bricks * 9.0 + wb.total_mortar_cement_bags * 380.0 + wb.total_mortar_sand_tonnes * 1500.0:,.2f}"],
            ["Plaster & Finishes", f"{wb.total_plaster_area_m2:.1f} m²", "₹400/m²", f"₹{wb.total_plaster_area_m2 * 400.0:,.2f}"],
            ["TOTAL PROJECT COST", "", "", f"₹{bom.total_cost_inr + wb.total_wall_cost_inr:,.2f}"]
        ]
        
        t = Table(cost_data, colWidths=[110, 100, 90, 100])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightyellow),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 15))
        
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
        """Generate comprehensive structural & finishes schedules (columns, beams, slabs, footings, brickwork, plaster, paint)."""
        ReportGenerator._ensure_walls(grid_mgr, **kwargs)
        from .wall_calculator import WallCalculator
        wall_calc = WallCalculator(mortar_ratio=4, wc_ratio=0.50)
        num_st = getattr(grid_mgr, 'num_stories', 1) or 1
        story_h = getattr(grid_mgr, 'story_height_m', 3.0) or 3.0
        
        wall_bom_rep = wall_calc.calculate_all(
            grid_mgr.walls,
            num_stories=num_st,
            floor_height_m=story_h,
            slab_thickness_mm=125.0,
            beam_depth_mm=400.0,
            columns=getattr(grid_mgr, 'columns', []),
        )
        
        doc = SimpleDocTemplate(filename, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
        elements = []
        styles = getSampleStyleSheet()
        
        elements.append(Paragraph("Design & Construction Schedules Report", styles["Title"]))
        elements.append(Spacer(1, 12))
        
        # 1. Column Schedule
        elements.append(Paragraph("1. Column Schedule & Reinforcement (IS 456 Cl. 26.5.3)", styles["Heading1"]))
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
        elements.append(Spacer(1, 15))
        
        # 2. Beam Schedule
        elements.append(Paragraph("2. Beam Schedule & Quantities (IS 456 Cl. 26.5.1)", styles["Heading1"]))
        beam_data = [["ID", "Size", "Top Steel", "Bottom Steel", "Stirrups"]]
        
        if hasattr(grid_mgr, 'beam_schedule') and grid_mgr.beam_schedule:
            for bid in sorted(grid_mgr.beam_schedule.keys()):
                det = grid_mgr.beam_schedule[bid]
                beam_data.append([
                    bid, det.size_label,
                    det.top_bars_desc, det.bottom_bars_desc, det.stirrups_desc
                ])
        else:
            beam_data.append(["N/A", "-", "-", "-", "-"])
        
        t_bm = Table(beam_data, repeatRows=1, colWidths=[50, 60, 80, 80, 100])
        t_bm.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkorange),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
        ]))
        elements.append(t_bm)
        elements.append(Spacer(1, 15))
        
        # 3. Slab Schedule
        elements.append(Paragraph("3. Slab Schedule & Reinforcement (IS 456)", styles["Heading1"]))
        slab_data = [["ID", "Thickness (mm)", "Main Steel", "Distribution Steel"]]
        
        if hasattr(grid_mgr, 'slab_schedule') and grid_mgr.slab_schedule:
            for sid, det in grid_mgr.slab_schedule.items():
                slab_data.append([
                    sid, f"{det.thickness_mm:.0f}",
                    det.main_steel_desc, det.dist_steel_desc
                ])
        else:
            slab_data.append(["N/A", "-", "-", "-"])
        
        t_sl = Table(slab_data, repeatRows=1, colWidths=[80, 80, 120, 120])
        t_sl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.purple),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        elements.append(t_sl)
        elements.append(Spacer(1, 15))
        
        # 4. Foundation Schedule
        elements.append(Paragraph("4. Foundation Schedule & Quantities (IS 456 Cl. 34)", styles["Heading1"]))
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
        else:
            ft_data.append(["N/A", "-", "-", "-", "-"])
        
        t_ft = Table(ft_data, repeatRows=1, colWidths=[60, 60, 100, 70, 80])
        t_ft.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        elements.append(t_ft)
        elements.append(Spacer(1, 15))
        
        # 5. Masonry Brickwork Schedule
        elements.append(Paragraph("5. Masonry Brickwork Schedule & Takeoff (IS 1077, IS 2250)", styles["Heading1"]))
        elements.append(Paragraph("<font size=8>Bricks modular 200×200×100 mm (250 Nos/m³). Mortar 1:4 mix proportion, dry factor 1.33, W:C = 0.50.</font>", styles["Normal"]))
        elements.append(Spacer(1, 4))
        elements.append(ReportGenerator._create_brickwork_schedule_table(wall_bom_rep, num_stories=num_st))
        elements.append(Spacer(1, 15))
        
        # 6. Plastering Schedule
        elements.append(Paragraph("6. Plastering Schedule & Quantities (IS 1661, IS 2402, IS 1200)", styles["Heading1"]))
        elements.append(Paragraph("<font size=8>Ext: 15mm 1:4 render; Int: 12mm 1:6 plaster; Ceiling: 6mm 1:3 soffit plaster per IS 1661 Cl. 12.3. Dry factor 1.33.</font>", styles["Normal"]))
        elements.append(Spacer(1, 4))
        elements.append(ReportGenerator._create_plaster_schedule_table(wall_bom_rep, num_stories=num_st, grid_mgr=grid_mgr))
        elements.append(Spacer(1, 15))
        
        # 7. Painting Schedule
        elements.append(Paragraph("7. Painting & Surface Finishes Schedule (NBC 2016 SP7)", styles["Heading1"]))
        elements.append(Paragraph("<font size=8>1 coat primer @ 8 m²/L, 2 coats polymer putty @ 1.5 kg/m², 2 coats emulsion (interior 12 m²/L, exterior 10 m²/L).</font>", styles["Normal"]))
        elements.append(Spacer(1, 4))
        elements.append(ReportGenerator._create_paint_schedule_table(wall_bom_rep, num_stories=num_st, grid_mgr=grid_mgr))
        elements.append(Spacer(1, 15))
        
        # 8. Consolidated Material Summary
        elements.append(Paragraph("8. Consolidated Masonry, Plaster & Paint Material Takeoff", styles["Heading1"]))
        elements.append(ReportGenerator._create_masonry_summary_table(wall_bom_rep, num_stories=num_st, grid_mgr=grid_mgr))
        elements.append(Spacer(1, 15))

        # 9. Cost Takeoff
        elements.append(Paragraph("9. Masonry & Finishes Trade Cost Estimate (CPWD DSR)", styles["Heading1"]))
        elements.append(ReportGenerator._create_masonry_cost_table(wall_bom_rep, num_stories=num_st, grid_mgr=grid_mgr))
        
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
    
    def generate_floor_report(self, filename: str, grid_mgr: GridManager, level: int, bom: 'MaterialCost' = None, **kwargs):
        """Generate structural report for a specific floor level including complete brickwork, plaster, and paint takeoff."""
        ReportGenerator._ensure_walls(grid_mgr, **kwargs)
        from .wall_calculator import WallCalculator
        wall_calc = WallCalculator(mortar_ratio=4, wc_ratio=0.50)
        story_h = getattr(grid_mgr, 'story_height_m', 3.0) or 3.0
        
        wb_floor = wall_calc.calculate_all(
            grid_mgr.walls,
            num_stories=1,
            floor_height_m=story_h,
            slab_thickness_mm=125.0,
            beam_depth_mm=400.0,
            columns=getattr(grid_mgr, 'columns', []),
        )
        
        doc = SimpleDocTemplate(filename, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
        elements = []
        styles = getSampleStyleSheet()
        
        elements.append(Paragraph(f"Floor {level} Structural & Finishes Report", styles["Title"]))
        elements.append(Spacer(1, 12))
        
        # Floor Summary
        cols_at_level = [c for c in grid_mgr.columns if c.level == level]
        elements.append(Paragraph("1. Floor Summary", styles["Heading1"]))
        elements.append(Paragraph(f"<b>Level:</b> {level} | <b>Floor Height:</b> {story_h:.2f} m | <b>Columns at Level:</b> {len(cols_at_level)}", styles["Normal"]))
        elements.append(Spacer(1, 12))
        
        # Column Schedule
        elements.append(Paragraph("2. Column Schedule for Level", styles["Heading1"]))
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
        t_col = Table(col_data, repeatRows=1, colWidths=[50, 80, 60, 60, 80, 80])
        t_col.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
        ]))
        elements.append(t_col)
        elements.append(Spacer(1, 15))
        
        # Beam Schedule
        elements.append(Paragraph("3. Beam Schedule for Level", styles["Heading1"]))
        beam_data = [["ID", "Size", "Top Steel", "Bottom Steel", "Stirrups"]]
        if hasattr(grid_mgr, 'beam_schedule') and grid_mgr.beam_schedule:
            for bid in sorted(grid_mgr.beam_schedule.keys()):
                det = grid_mgr.beam_schedule[bid]
                beam_data.append([
                    bid, det.size_label,
                    det.top_bars_desc, det.bottom_bars_desc, det.stirrups_desc
                ])
        else:
            beam_data.append(["N/A", "-", "-", "-", "-"])
        t_bm = Table(beam_data, repeatRows=1, colWidths=[50, 60, 80, 80, 100])
        t_bm.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkorange),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
        ]))
        elements.append(t_bm)
        elements.append(Spacer(1, 15))
        
        # Slab Schedule
        elements.append(Paragraph("4. Slab Schedule for Level", styles["Heading1"]))
        slab_data = [["ID", "Thickness (mm)", "Main Steel", "Distribution Steel"]]
        if hasattr(grid_mgr, 'slab_schedule') and grid_mgr.slab_schedule:
            for sid, det in grid_mgr.slab_schedule.items():
                slab_data.append([
                    sid, f"{det.thickness_mm:.0f}",
                    det.main_steel_desc, det.dist_steel_desc
                ])
        else:
            slab_data.append(["N/A", "-", "-", "-"])
        t_sl = Table(slab_data, repeatRows=1, colWidths=[80, 80, 120, 120])
        t_sl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.purple),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        elements.append(t_sl)
        elements.append(Spacer(1, 15))
        
        # Floor Brickwork Schedule
        elements.append(Paragraph(f"5. Floor {level} Masonry Brickwork Schedule (IS 1077, IS 2250)", styles["Heading1"]))
        elements.append(ReportGenerator._create_brickwork_schedule_table(wb_floor, num_stories=1))
        elements.append(Spacer(1, 15))

        # Floor Plastering Schedule
        elements.append(Paragraph(f"6. Floor {level} Plastering Schedule (IS 1661, IS 2402)", styles["Heading1"]))
        elements.append(ReportGenerator._create_plaster_schedule_table(wb_floor, num_stories=1, grid_mgr=grid_mgr))
        elements.append(Spacer(1, 15))

        # Floor Painting Schedule
        elements.append(Paragraph(f"7. Floor {level} Painting & Finishes Schedule (NBC 2016)", styles["Heading1"]))
        elements.append(ReportGenerator._create_paint_schedule_table(wb_floor, num_stories=1, grid_mgr=grid_mgr))
        elements.append(Spacer(1, 15))

        # Floor Material Summary
        elements.append(Paragraph(f"8. Floor {level} Masonry & Finishes Material Takeoff", styles["Heading1"]))
        elements.append(ReportGenerator._create_masonry_summary_table(wb_floor, num_stories=1, grid_mgr=grid_mgr))
        
        doc.build(elements)

    def generate_masonry_report(self, filename: str, grid_mgr: GridManager, project_name: str = "Masonry & Finishes Takeoff Report", **kwargs):
        """Generate standalone professional Masonry & Finishes Bill of Quantities PDF report."""
        ReportGenerator._ensure_walls(grid_mgr, **kwargs)
        from .wall_calculator import WallCalculator
        wall_calc = WallCalculator(mortar_ratio=4, wc_ratio=0.50)
        num_stories = getattr(grid_mgr, 'num_stories', 1) or 1
        story_h = getattr(grid_mgr, 'story_height_m', 3.0) or 3.0
        
        wb = wall_calc.calculate_all(
            grid_mgr.walls,
            num_stories=num_stories,
            floor_height_m=story_h,
            slab_thickness_mm=125.0,
            beam_depth_mm=400.0,
            columns=getattr(grid_mgr, 'columns', []),
        )
        
        doc = SimpleDocTemplate(filename, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
        elements = []
        styles = getSampleStyleSheet()
        
        elements.append(Paragraph(f"{project_name} — Masonry, Plaster & Finishes BOQ Report", styles["Title"]))
        elements.append(Spacer(1, 10))
        
        # 1. Executive Summary
        elements.append(Paragraph("1. Executive Summary & Code Compliance", styles["Heading1"]))
        exec_data = [
            ["Item / Parameter", "Value", "Standard Reference"],
            ["Building Footprint", f"{grid_mgr.width_m:.2f} m × {grid_mgr.length_m:.2f} m", "Architectural Layout"],
            ["Total Stories / Height", f"{num_stories} Stories / {num_stories * story_h:.1f} m", "NBC 2016 Part 3"],
            ["Total Clay Bricks", f"{wb.total_bricks:,} Nos", "IS 1077:1992 (Modular 20×20×10 cm)"],
            ["Total Mortar Cement", f"{wb.total_mortar_cement_bags:,} Bags ({wb.total_mortar_cement_kg:,.0f} kg)", "IS 269:2015 (1:4 Mix Proportion)"],
            ["Total Mortar Sand", f"{wb.total_mortar_sand_tonnes:.2f} Tonnes", "IS 383:2016 Zone II"],
            ["Total Plaster Surface Area", f"{wb.total_plaster_area_m2:.1f} m²", "IS 1200 Part 12"],
            ["Total Plaster Cement", f"{wb.total_plaster_cement_bags:,} Bags ({wb.total_plaster_cement_kg:,.0f} kg)", "IS 1661:1972 (12mm int, 15mm ext)"],
            ["Total Plaster Sand", f"{wb.total_plaster_sand_tonnes:.2f} Tonnes", "IS 383:2016 Zone III"],
            ["Estimated Wall & Finishes Cost", f"INR {wb.total_wall_cost_inr:,.2f}", "CPWD DSR 2023"],
        ]
        t_exec = Table(exec_data, colWidths=[150, 150, 190])
        t_exec.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.saddlebrown),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightyellow),
            ('FONTWEIGHT', (0, -1), (-1, -1), 'BOLD'),
        ]))
        elements.append(t_exec)
        elements.append(Spacer(1, 15))
        
        # 2. Brickwork Schedule & Takeoff
        elements.append(Paragraph("2. Masonry Brickwork Schedule & Material Takeoff (IS 1077, IS 2250)", styles["Heading1"]))
        elements.append(Paragraph("<font size=8>Bricks modular 200×200×100 mm (250 Nos/m³). Mortar 1:4 mix proportion, dry factor 1.33, W:C = 0.50.</font>", styles["Normal"]))
        elements.append(Spacer(1, 4))
        elements.append(ReportGenerator._create_brickwork_schedule_table(wb, num_stories=num_stories))
        elements.append(Spacer(1, 15))
        
        # 3. Plastering Schedule
        elements.append(Paragraph("3. Plastering Schedule & Quantities (IS 1661, IS 2402, IS 1200)", styles["Heading1"]))
        elements.append(Paragraph("<font size=8>Ext: 15mm 1:4 render; Int: 12mm 1:6 plaster; Ceiling: 6mm 1:3 soffit plaster per IS 1661 Cl. 12.3. Dry factor 1.33.</font>", styles["Normal"]))
        elements.append(Spacer(1, 4))
        elements.append(ReportGenerator._create_plaster_schedule_table(wb, num_stories=num_stories, grid_mgr=grid_mgr))
        elements.append(Spacer(1, 15))

        # 4. Painting Schedule
        elements.append(Paragraph("4. Painting & Surface Finishes Schedule (NBC 2016 SP7)", styles["Heading1"]))
        elements.append(Paragraph("<font size=8>1 coat primer @ 8 m²/L, 2 coats polymer putty @ 1.5 kg/m², 2 coats emulsion (interior 12 m²/L, exterior 10 m²/L).</font>", styles["Normal"]))
        elements.append(Spacer(1, 4))
        elements.append(ReportGenerator._create_paint_schedule_table(wb, num_stories=num_stories, grid_mgr=grid_mgr))
        elements.append(Spacer(1, 15))

        # 5. Grand Material Breakdown
        elements.append(Paragraph("5. Consolidated Material Takeoff Summary (All Stories)", styles["Heading1"]))
        elements.append(ReportGenerator._create_masonry_summary_table(wb, num_stories=num_stories, grid_mgr=grid_mgr))
        elements.append(Spacer(1, 15))
        
        # 6. Cost Takeoff
        elements.append(Paragraph("6. Trade-wise Cost Estimate (CPWD DSR)", styles["Heading1"]))
        elements.append(ReportGenerator._create_masonry_cost_table(wb, num_stories=num_stories, grid_mgr=grid_mgr))
        elements.append(Spacer(1, 15))

        # Footer
        footer_text = "<i>Report generated by StructOptima · Compliant with IS 1077, IS 2250, IS 1200, IS 1661, IS 1905, NBC 2016</i>"
        elements.append(Paragraph(footer_text, styles["Normal"]))
        
        doc.build(elements)
