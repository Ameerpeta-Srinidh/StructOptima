
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
    def export_to_excel(grid_mgr: GridManager, beams: List[Any], bom: MaterialCost) -> bytes:
        """
        Creates an Excel file in memory and returns bytes.
        Sheets: Column Schedule, Beam Schedule, BOM.
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
                {"Item": "Total Cost (INR)", "Value": bom.total_cost_inr}
            ]
            
            # Add breakdown
            for k, v in bom.steel_by_diameter.items():
                bom_data.append({"Item": f"Steel Dia {k} mm (kg)", "Value": v})
                
            df_bom = pd.DataFrame(bom_data)
            df_bom.to_excel(writer, sheet_name='Bill of Materials', index=False)
            
        return output.getvalue()
