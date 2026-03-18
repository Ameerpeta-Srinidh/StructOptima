from typing import List, Dict, Optional
import random

class DigitalTwinExplorer:
    """
    Manages Digital Twin interactions: Metadata retrieval, As-Built comparisons,
    and system Isolation.
    """
    
    def __init__(self, project_name: str):
        self.project_name = project_name
        self.toggled_systems = {"Structural": True, "MEP": False, "Architectural": True}
        self.view_state = "As-Designed" # or "As-Built"
        
    def get_element_metadata(self, element_id: str) -> Dict[str, str]:
        """
        Simulates retrieving COBie/BIM metadata for a selected element.
        In a real app, this would query the BIM database.
        """
        # Simulated database
        base_data = {
            "FireRating": "2 Hours",
            "ConcreteGrade": "M40",
            "InstallationDate": "2025-11-15",
            "Manufacturer": "UltraTech",
            "WarrantyExpire": "2035-11-15"
        }
        
        if "C" in element_id:
            base_data.update({
                "Type": "Column",
                "RebarDensity": "180 kg/m3",
                "LoadCapacity": "2500 kN",
                "Finish": "Exposed Concrete"
            })
        elif "B" in element_id:
             base_data.update({
                "Type": "Beam",
                "RebarDensity": "120 kg/m3",
                "Span": "5.4m",
                "Finish": "Plastered"
            })
        else:
            base_data["Type"] = "Unknown Component"
            
        return base_data

    def get_as_built_deviation(self, element_id: str) -> Dict[str, float]:
        """
        Returns deviation data (mm) comparing Design vs Reality (Simulated).
        """
        # Random deviation simulation
        dx = round(random.uniform(-10, 10), 1)
        dy = round(random.uniform(-10, 10), 1)
        dz = round(random.uniform(-5, 5), 1)
        
        return {"dx": dx, "dy": dy, "dz": dz, "total_mm": round((dx**2 + dy**2 + dz**2)**0.5, 1)}

    def toggle_system(self, system: str, active: bool):
        if system in self.toggled_systems:
            self.toggled_systems[system] = active

    def generate_construction_schedule_overlay(self, current_date: str) -> List[str]:
        """
        Returns list of element IDs that should be constructing at this date (4D sim).
        """
        # Dummy logic
        if "2025" in current_date:
            return ["F1", "F2", "C1", "C2"] # Foundations and Ground Cols
        return ["All"]
