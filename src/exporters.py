
import pandas as pd
import io
from typing import List, Any
from .grid_manager import GridManager
from .quantifier import MaterialCost

class ExcelExporter:
    """
    Handles exporting project data to Excel using pandas and openpyxl.
    """
    
    @staticmethod
    def export_to_excel(grid_mgr: GridManager, beams: List[Any], bom: MaterialCost, footings: Any = None, *args, **kwargs) -> bytes:
        """
        Creates an Excel file in memory and returns bytes.
        Sheets: Column Schedule, Beam Schedule, BOM, Foundation Schedule, Wall Takeoff.
        """
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            
            # 1. Column Schedule
            col_data = []
            for col in grid_mgr.columns:
                rebar = "-"
                ties = "-"
                math_log_exists = "No"
                if hasattr(grid_mgr, 'rebar_schedule') and col.id in grid_mgr.rebar_schedule:
                    res = grid_mgr.rebar_schedule[col.id]
                    rebar = res.main_bars_desc
                    ties = res.links_desc
                    math_log_exists = "Yes" if res.math_log else "No"
                    
                col_data.append({
                    "ID": col.id,
                    "Level": col.level,
                    "Loc X": col.x,
                    "Loc Y": col.y,
                    "Load (kN)": col.load_kn,
                    "Size": col.label,
                    "Main Steel": rebar,
                    "Ties": ties,
                    "Log Available": math_log_exists
                })
            
            df_cols = pd.DataFrame(col_data)
            df_cols.to_excel(writer, sheet_name='Column Schedule', index=False)
            
            # 2. Beam Schedule
            beam_data = []
            # We use beams list passed in or iterate beam_schedule
            # Iterate schedule if available for detailed rebar
            if hasattr(grid_mgr, 'beam_schedule') and grid_mgr.beam_schedule:
                for bid, det in grid_mgr.beam_schedule.items():
                   beam_data.append({
                       "Beam ID": bid,
                       "Size": det.size_label if hasattr(det, 'size_label') else "N/A",
                       "Top Steel": det.top_bars_desc,
                       "Bot Steel": det.bottom_bars_desc,
                       "Stirrups": det.stirrups_desc
                   })
            else:
                 # Fallback to geometry list
                 for b in beams:
                     beam_data.append({
                         "Beam ID": b.id,
                         "Size": b.properties.label,
                         "Start": f"{b.start_point.x},{b.start_point.y}",
                         "End": f"{b.end_point.x},{b.end_point.y}"
                     })
                     
            df_beams = pd.DataFrame(beam_data)
            df_beams.to_excel(writer, sheet_name='Beam Schedule', index=False)
            
            # 3. BOM
            # Convert dictionary to lists
            bom_data = [
                {"Item": "Total Concrete (m3)", "Value": bom.total_concrete_vol_m3},
                {"Item": "Total Steel (kg)", "Value": bom.total_steel_weight_kg},
                {"Item": "Total Bricks (Nos)", "Value": getattr(bom, 'total_bricks', getattr(bom, 'brick_count', 0))},
                {"Item": "Total Mortar Cement (Bags)", "Value": getattr(bom, 'total_mortar_cement_bags', 0)},
                {"Item": "Total Plaster Cement (Bags)", "Value": getattr(bom, 'total_plaster_cement_bags', 0)},
                {"Item": "Total Sand (Tonnes)", "Value": getattr(bom, 'total_mortar_sand_tonnes', 0.0) + getattr(bom, 'total_plaster_sand_tonnes', 0.0)},
                {"Item": "Total Plaster Area (m2)", "Value": getattr(bom, 'total_plaster_area_m2', getattr(bom, 'plaster_area_m2', 0.0))},
                {"Item": "Total Cost (INR)", "Value": bom.total_cost_inr}
            ]
            
            # Add breakdown
            for k, v in bom.steel_by_diameter.items():
                bom_data.append({"Item": f"Steel Dia {k} mm (kg)", "Value": v})
                
            df_bom = pd.DataFrame(bom_data)
            df_bom.to_excel(writer, sheet_name='Bill of Materials', index=False)

            # 4. Foundation Schedule
            passed_ft = footings if footings is not None else kwargs.get('footings', getattr(grid_mgr, 'footings', []))
            if isinstance(passed_ft, dict):
                passed_ft = list(passed_ft.values())
            if passed_ft:
                ft_export = []
                for ft in passed_ft:
                    if ft is not None:
                        ft_export.append({
                            "Footing ID": getattr(ft, 'id', 'F'),
                            "Length (m)": getattr(ft, 'length_m', 0.0),
                            "Width (m)": getattr(ft, 'width_m', 0.0),
                            "Thickness (mm)": getattr(ft, 'thickness_mm', 0.0),
                            "Concrete Vol (m3)": getattr(ft, 'concrete_vol_m3', 0.0),
                            "Excavation Vol (m3)": getattr(ft, 'excavation_vol_m3', 0.0)
                        })
                if ft_export:
                    df_ft = pd.DataFrame(ft_export)
                    df_ft.to_excel(writer, sheet_name='Foundation Schedule', index=False)

            # 5. Wall Takeoff
            if hasattr(grid_mgr, 'walls') and grid_mgr.walls:
                from .wall_calculator import WallCalculator
                w_calc = WallCalculator(mortar_ratio=4, wc_ratio=0.50)
                n_stories = getattr(grid_mgr, 'num_stories', 1)
                st_h = getattr(grid_mgr, 'story_height_m', 3.0)
                wb = w_calc.calculate_all(grid_mgr.walls, num_stories=n_stories, floor_height_m=st_h)
                
                wall_export = []
                for s in wb.wall_sections:
                    wall_export.append({
                        "Wall ID": s.wall_id,
                        "Span": f"{s.col_start}->{s.col_end}" if (s.col_start and s.col_end) else "Bay",
                        "Type": "Exterior" if s.is_exterior else "Interior",
                        "Length (m)": s.length_m,
                        "Clear Ht (m)": s.clear_height_m,
                        "Thickness (mm)": int(s.core_thickness_m * 1000),
                        "Gross Vol (m3)": s.wall_volume_m3,
                        "Bricks (Nos)": s.num_bricks * n_stories,
                        "Wet Mortar (m3)": round(s.wet_mortar_vol_m3 * n_stories, 3),
                        "Dry Mortar (m3)": round(s.dry_mortar_vol_m3 * n_stories, 3),
                        "Mortar Cement (kg)": round(s.mortar_cement_kg * n_stories, 1),
                        "Mortar Sand (T)": round(s.mortar_sand_tonnes * n_stories, 3),
                        "Water (L)": round((s.mortar_water_litres + s.plaster_water_litres) * n_stories, 0),
                        "Plaster (m2)": round(s.plaster_area_m2 * n_stories, 1),
                        "Plaster Cement (kg)": round(s.plaster_cement_kg * n_stories, 1),
                        "Plaster Sand (T)": round(s.plaster_sand_tonnes * n_stories, 3),
                        "Primer (L)": round(s.primer_litres * n_stories, 2),
                        "Putty (kg)": round(s.putty_kg * n_stories, 1),
                        "Emulsion (L)": round((s.emulsion_int_litres + s.emulsion_ext_litres) * n_stories, 2),
                    })
                df_w = pd.DataFrame(wall_export)
                df_w.to_excel(writer, sheet_name='Wall Takeoff', index=False)
                
        return output.getvalue()
