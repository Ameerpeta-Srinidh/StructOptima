"""
Building Type Definitions - IS 875 Part 2 Compliant Load Values

This module defines load parameters for different building occupancy types
as per IS 875 (Part 2): 1987 - Code of Practice for Design Loads
(Other Than Earthquake) For Buildings and Structures.

IMPORTANT: These values are for preliminary design only. Final designs
must be reviewed and approved by a licensed Professional Engineer.

Reference: IS 875 (Part 2): 1987, Table 1 - Imposed Floor Loads
"""

from dataclasses import dataclass
from typing import Dict, Literal
from enum import Enum


class BuildingType(str, Enum):
    """Building occupancy classification per IS 875 Part 2."""
    RESIDENTIAL = "residential"
    COMMERCIAL_OFFICE = "commercial_office"
    COMMERCIAL_RETAIL = "commercial_retail"
    INSTITUTIONAL = "institutional"
    ASSEMBLY = "assembly"


@dataclass(frozen=True)
class LoadParameters:
    """
    Load parameters for structural design per IS codes.
    
    All values in kN/m² unless otherwise specified.
    Reference: IS 875 Part 2, Table 1
    """
    # Building classification
    building_type: BuildingType
    description: str
    
    # Live Loads (IS 875 Part 2, Table 1)
    live_load_floor_kn_m2: float       # Uniformly distributed live load
    live_load_corridor_kn_m2: float    # Corridors, passages, staircases
    live_load_balcony_kn_m2: float     # Balconies
    live_load_roof_kn_m2: float        # Roof (accessible)
    
    # Dead Loads (IS 875 Part 1)
    floor_finish_kn_m2: float          # Floor finishes (tiles, screed)
    partition_load_kn_m2: float        # Partition walls (movable)
    services_load_kn_m2: float         # MEP services, false ceiling
    
    # Typical Dimensions
    story_height_m: float              # Floor-to-floor height
    slab_thickness_mm: float           # Typical slab thickness
    
    # Design Factors
    load_factor_dl: float = 1.5        # Dead load factor (IS 456)
    load_factor_ll: float = 1.5        # Live load factor (IS 456)
    
    @property
    def total_floor_load_kn_m2(self) -> float:
        """Total unfactored floor load excluding slab self-weight."""
        return (
            self.live_load_floor_kn_m2 +
            self.floor_finish_kn_m2 +
            self.partition_load_kn_m2 +
            self.services_load_kn_m2
        )
    
    @property
    def factored_floor_load_kn_m2(self) -> float:
        """Factored design floor load per IS 456 limit state method."""
        dead = self.floor_finish_kn_m2 + self.partition_load_kn_m2 + self.services_load_kn_m2
        live = self.live_load_floor_kn_m2
        return dead * self.load_factor_dl + live * self.load_factor_ll


# IS 875 Part 2 Compliant Load Definitions
# -----------------------------------------
# Reference: IS 875 (Part 2): 1987, Table 1

RESIDENTIAL = LoadParameters(
    building_type=BuildingType.RESIDENTIAL,
    description="Residential Buildings (Dwelling Houses, Flats, Apartments)",
    
    # IS 875 Part 2, Clause 3.1.1 - Dwellings
    live_load_floor_kn_m2=2.0,         # All rooms and kitchens
    live_load_corridor_kn_m2=3.0,      # Corridors, staircases
    live_load_balcony_kn_m2=3.0,       # Balconies
    live_load_roof_kn_m2=1.5,          # Accessible roof
    
    # Dead loads (typical values)
    floor_finish_kn_m2=1.0,            # Tiles + screed (50mm)
    partition_load_kn_m2=1.5,          # Brick partitions (equivalent UDL)
    services_load_kn_m2=0.5,           # MEP, false ceiling
    
    # Dimensions
    story_height_m=3.0,
    slab_thickness_mm=125,
)

COMMERCIAL_OFFICE = LoadParameters(
    building_type=BuildingType.COMMERCIAL_OFFICE,
    description="Commercial Office Buildings",
    
    # IS 875 Part 2, Clause 3.1.2 - Office Buildings
    live_load_floor_kn_m2=3.0,         # Office spaces
    live_load_corridor_kn_m2=4.0,      # Corridors, lobbies
    live_load_balcony_kn_m2=3.0,       # Balconies
    live_load_roof_kn_m2=1.5,          # Accessible roof
    
    # Dead loads
    floor_finish_kn_m2=1.0,            # Tiles/raised floor
    partition_load_kn_m2=1.0,          # Light partitions
    services_load_kn_m2=1.0,           # Heavy MEP, false ceiling
    
    # Dimensions (taller floors for commercial)
    story_height_m=3.6,
    slab_thickness_mm=150,
)

COMMERCIAL_RETAIL = LoadParameters(
    building_type=BuildingType.COMMERCIAL_RETAIL,
    description="Retail/Shopping Buildings (Shops, Shopping Malls)",
    
    # IS 875 Part 2, Clause 3.1.3 - Shops and Shopping Malls
    live_load_floor_kn_m2=4.0,         # Shop floors
    live_load_corridor_kn_m2=5.0,      # Public corridors
    live_load_balcony_kn_m2=4.0,       # Balconies
    live_load_roof_kn_m2=1.5,          # Accessible roof
    
    # Dead loads
    floor_finish_kn_m2=1.5,            # Heavy finishes
    partition_load_kn_m2=0.5,          # Minimal partitions
    services_load_kn_m2=1.0,           # HVAC, fire systems
    
    # Dimensions
    story_height_m=4.0,
    slab_thickness_mm=150,
)

INSTITUTIONAL = LoadParameters(
    building_type=BuildingType.INSTITUTIONAL,
    description="Institutional Buildings (Schools, Hospitals, Offices)",
    
    # IS 875 Part 2, Clause 3.1.5 - Institutional Buildings
    live_load_floor_kn_m2=3.0,         # Wards, classrooms
    live_load_corridor_kn_m2=4.0,      # Corridors (not less than)
    live_load_balcony_kn_m2=3.0,       # Balconies
    live_load_roof_kn_m2=1.5,          # Accessible roof
    
    # Dead loads
    floor_finish_kn_m2=1.0,
    partition_load_kn_m2=1.0,
    services_load_kn_m2=1.5,           # Medical/lab equipment
    
    # Dimensions
    story_height_m=3.6,
    slab_thickness_mm=150,
)

ASSEMBLY = LoadParameters(
    building_type=BuildingType.ASSEMBLY,
    description="Assembly Buildings (Theaters, Auditoriums, Convention)",
    
    # IS 875 Part 2, Clause 3.1.6 - Assembly Buildings
    live_load_floor_kn_m2=5.0,         # Fixed seating
    live_load_corridor_kn_m2=5.0,      # Public areas
    live_load_balcony_kn_m2=5.0,       # Balconies
    live_load_roof_kn_m2=1.5,          # Accessible roof
    
    # Dead loads
    floor_finish_kn_m2=1.5,
    partition_load_kn_m2=0.5,
    services_load_kn_m2=2.0,           # Heavy acoustics, lighting
    
    # Dimensions
    story_height_m=4.5,
    slab_thickness_mm=175,
)


# Lookup dictionary for easy access
BUILDING_TYPES: Dict[str, LoadParameters] = {
    "Residential": RESIDENTIAL,
    "Commercial (Office)": COMMERCIAL_OFFICE,
    "Commercial (Retail/Shopping)": COMMERCIAL_RETAIL,
    "Institutional": INSTITUTIONAL,
    "Assembly Hall": ASSEMBLY,
}


def get_load_parameters(building_type_name: str) -> LoadParameters:
    """
    Get load parameters for a building type.
    
    Args:
        building_type_name: One of the keys in BUILDING_TYPES
        
    Returns:
        LoadParameters object with IS 875 compliant values
    """
    if building_type_name not in BUILDING_TYPES:
        raise ValueError(f"Unknown building type: {building_type_name}. "
                        f"Valid types: {list(BUILDING_TYPES.keys())}")
    return BUILDING_TYPES[building_type_name]


def get_design_load_summary(params: LoadParameters) -> str:
    """Generate a summary string of design loads for reports."""
    return f"""
Design Loads (IS 875 Part 2)
----------------------------
Building Type: {params.description}

Live Loads:
  - Floor areas: {params.live_load_floor_kn_m2} kN/m²
  - Corridors/Stairs: {params.live_load_corridor_kn_m2} kN/m²
  - Balconies: {params.live_load_balcony_kn_m2} kN/m²
  - Roof (accessible): {params.live_load_roof_kn_m2} kN/m²

Dead Loads (superimposed):
  - Floor finish: {params.floor_finish_kn_m2} kN/m²
  - Partitions: {params.partition_load_kn_m2} kN/m²
  - Services: {params.services_load_kn_m2} kN/m²

Total Unfactored Floor Load: {params.total_floor_load_kn_m2:.2f} kN/m²
Factored Design Load (1.5DL + 1.5LL): {params.factored_floor_load_kn_m2:.2f} kN/m²

Story Height: {params.story_height_m} m
Typical Slab Thickness: {params.slab_thickness_mm} mm
"""
