"""
Wind Load Module - IS 875 (Part 3): 2015

Implements wind load calculations for buildings per IS 875 Part 3.

Features:
- Basic wind speed (Vb) by zone
- Design wind velocity (Vz) based on height
- Wind pressure coefficients (Cpe, Cpi)
- Design wind pressure for walls and roofs

Reference: IS 875 (Part 3): 2015 - Code of Practice for Design Loads
(Other than Earthquake) for Buildings and Structures, Part 3: Wind Loads

DISCLAIMER: All designs must be verified by a licensed Structural Engineer
before construction.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum
import math


class WindZone(str, Enum):
    """Wind zones of India per IS 875 Part 3."""
    ZONE_1 = "1"  # Vb = 33 m/s
    ZONE_2 = "2"  # Vb = 39 m/s
    ZONE_3 = "3"  # Vb = 44 m/s
    ZONE_4 = "4"  # Vb = 47 m/s
    ZONE_5 = "5"  # Vb = 50 m/s
    ZONE_6 = "6"  # Vb = 55 m/s


class TerrainCategory(str, Enum):
    """Terrain categories per IS 875 Part 3 Table 2."""
    CATEGORY_1 = "1"  # Exposed open terrain (sea coast, flat treeless plains)
    CATEGORY_2 = "2"  # Open terrain with scattered obstructions (suburbs)
    CATEGORY_3 = "3"  # Terrain with many closely spaced obstructions (industrial)
    CATEGORY_4 = "4"  # Terrain with numerous large obstructions (city centers)


class BuildingClass(str, Enum):
    """Building classes per IS 875 Part 3."""
    CLASS_A = "A"  # Buildings with walls and roof with openings < 5%
    CLASS_B = "B"  # Buildings with walls and roof with openings 5-20%
    CLASS_C = "C"  # Buildings with walls and roof with openings > 20%


BASIC_WIND_SPEED = {
    WindZone.ZONE_1: 33.0,
    WindZone.ZONE_2: 39.0,
    WindZone.ZONE_3: 44.0,
    WindZone.ZONE_4: 47.0,
    WindZone.ZONE_5: 50.0,
    WindZone.ZONE_6: 55.0,
}

TERRAIN_CONSTANTS = {
    TerrainCategory.CATEGORY_1: {"k2_10": 1.05, "alpha": 0.09, "z_gradient": 10},
    TerrainCategory.CATEGORY_2: {"k2_10": 1.00, "alpha": 0.14, "z_gradient": 10},
    TerrainCategory.CATEGORY_3: {"k2_10": 0.91, "alpha": 0.17, "z_gradient": 10},
    TerrainCategory.CATEGORY_4: {"k2_10": 0.80, "alpha": 0.22, "z_gradient": 10},
}

# IS 875 (Part 3):2015 Table 2 - k2 by height (m) for terrain categories 1, 2, 3, 4 (typed from the printed table)
K2_TABLE = [
    (10, (1.05, 1.00, 0.91, 0.80)), (15, (1.09, 1.05, 0.97, 0.80)), (20, (1.12, 1.07, 1.01, 0.80)),
    (30, (1.15, 1.12, 1.06, 0.97)), (50, (1.20, 1.17, 1.12, 1.10)), (100, (1.26, 1.24, 1.20, 1.20)),
    (150, (1.30, 1.28, 1.24, 1.24)), (200, (1.32, 1.30, 1.27, 1.27)), (250, (1.34, 1.32, 1.29, 1.28)),
    (300, (1.35, 1.34, 1.31, 1.30)), (350, (1.35, 1.35, 1.32, 1.31)), (400, (1.35, 1.35, 1.34, 1.32)),
    (450, (1.35, 1.35, 1.35, 1.33)), (500, (1.35, 1.35, 1.35, 1.34)),
]
K2_TABLE_COLUMN = {TerrainCategory.CATEGORY_1: 0, TerrainCategory.CATEGORY_2: 1, TerrainCategory.CATEGORY_3: 2,
                   TerrainCategory.CATEGORY_4: 3}

INTERNAL_PRESSURE_COEFFICIENT = {
    BuildingClass.CLASS_A: 0.2,
    BuildingClass.CLASS_B: 0.5,
    BuildingClass.CLASS_C: 0.7,
}


@dataclass
class WindLoadParameters:
    """Wind load design parameters."""
    zone: WindZone
    basic_wind_speed_ms: float
    terrain_category: TerrainCategory
    building_class: BuildingClass
    k1: float = 1.0  # Risk coefficient (default for general buildings)
    k3: float = 1.0  # Topography factor (default for flat terrain)
    

@dataclass
class WindPressureResult:
    """Wind pressure calculation result for a height level."""
    height_m: float
    k2: float  # Terrain and height factor
    design_wind_speed_ms: float  # Vz = Vb × k1 × k2 × k3
    design_wind_pressure_kn_m2: float  # pz = 0.6 × Vz²
    cpe_windward: float  # External pressure coefficient (windward wall)
    cpe_leeward: float  # External pressure coefficient (leeward wall)
    cpi: float  # Internal pressure coefficient
    net_pressure_windward_kn_m2: float  # pz × (Cpe - Cpi)
    net_pressure_leeward_kn_m2: float


@dataclass
class WindLoadResult:
    """Complete wind load analysis result."""
    parameters: WindLoadParameters
    building_height_m: float
    building_width_m: float
    building_length_m: float
    opening_percentage: float
    pressure_results: List[WindPressureResult] = field(default_factory=list)
    total_base_shear_x_kn: float = 0.0
    total_base_shear_y_kn: float = 0.0
    total_overturning_moment_x_knm: float = 0.0
    total_overturning_moment_y_knm: float = 0.0
    # Storey forces (kN) at floor levels 1..N for wind blowing along +X / +Y
    storey_forces_x_kn: List[float] = field(default_factory=list)
    storey_forces_y_kn: List[float] = field(default_factory=list)
    storey_heights_m: List[float] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class WindLoadCalculator:
    """
    IS 875 (Part 3): 2015 Wind Load Calculator.
    
    Calculates design wind pressure and forces for buildings.
    """
    
    def __init__(
        self,
        zone: WindZone,
        terrain_category: TerrainCategory = TerrainCategory.CATEGORY_2,
        k1: float = 1.0,
        k3: float = 1.0
    ):
        """
        Initialize wind load calculator.
        
        Args:
            zone: Wind zone (1-6)
            terrain_category: Terrain category (1-4)
            k1: Risk coefficient (1.0 for general buildings, 1.08 for critical)
            k3: Topography factor (1.0 for flat terrain)
        """
        self.zone = zone
        self.terrain_category = terrain_category
        self.k1 = k1
        self.k3 = k3
        self.vb = BASIC_WIND_SPEED[zone]
        
    def calculate_k2(self, height_m: float) -> float:
        """Terrain and height multiplier k2, IS 875 (Part 3):2015 Table 2 with linear interpolation (table note);
        heights below 10 m take the 10 m value. Checked against the printed table 2026-10-20 (the previous
        power-law approximation was up to 3 % low, e.g. terrain category 1 at 50 m: 1.16 instead of 1.20)."""
        col = K2_TABLE_COLUMN[self.terrain_category]
        z = max(height_m, K2_TABLE[0][0])
        if z >= K2_TABLE[-1][0]:
            return K2_TABLE[-1][1][col]
        for (z1, v1), (z2, v2) in zip(K2_TABLE, K2_TABLE[1:]):
            if z1 <= z <= z2:
                return v1[col] + (v2[col] - v1[col]) * (z - z1) / (z2 - z1)
        return K2_TABLE[-1][1][col]

    def calculate_design_wind_speed(self, height_m: float) -> float:
        """
        Calculate design wind speed Vz at height z.
        
        Vz = Vb × k1 × k2 × k3
        
        Args:
            height_m: Height above ground in meters
            
        Returns:
            Design wind speed in m/s
        """
        k2 = self.calculate_k2(height_m)
        vz = self.vb * self.k1 * k2 * self.k3
        return vz
    
    def calculate_design_wind_pressure(self, height_m: float) -> float:
        """
        Calculate design wind pressure pz at height z.
        
        pz = 0.6 × Vz² (N/m²) = 0.0006 × Vz² (kN/m²)
        
        Args:
            height_m: Height above ground in meters
            
        Returns:
            Design wind pressure in kN/m²
        """
        vz = self.calculate_design_wind_speed(height_m)
        pz = 0.6 * vz ** 2 / 1000.0  # Convert N/m² to kN/m²
        return pz
    
    def get_external_pressure_coefficients(
        self,
        height_m: float,
        width_m: float,
        length_m: float,
        wind_direction: str = "along_length"
    ) -> Tuple[float, float]:
        """
        Get external pressure coefficients Cpe for walls.
        
        Simplified values per IS 875 Part 3 Table 5.
        
        Args:
            height_m: Building height
            width_m: Building width
            length_m: Building length
            wind_direction: "along_length" or "along_width"
            
        Returns:
            (Cpe_windward, Cpe_leeward)
        """
        if wind_direction == "along_length":
            d = length_m
            b = width_m
        else:
            d = width_m
            b = length_m
        
        h_by_b = height_m / b if b > 0 else 1.0
        
        cpe_windward = 0.8
        
        if h_by_b <= 0.5:
            cpe_leeward = -0.3
        elif h_by_b <= 1.0:
            cpe_leeward = -0.4
        elif h_by_b <= 2.0:
            cpe_leeward = -0.5
        else:
            cpe_leeward = -0.6
        
        return cpe_windward, cpe_leeward
    
    def get_internal_pressure_coefficient(
        self,
        opening_percentage: float
    ) -> Tuple[float, BuildingClass]:
        """
        Get internal pressure coefficient Cpi based on opening percentage.
        
        IS 875 Part 3:
        - Openings < 5%: Cpi = ±0.2 (Class A - effectively sealed)
        - Openings 5-20%: Cpi = ±0.5 (Class B)
        - Openings > 20%: Cpi = ±0.7 (Class C)
        
        Args:
            opening_percentage: Percentage of wall area with openings
            
        Returns:
            (Cpi, BuildingClass)
        """
        if opening_percentage < 5.0:
            return INTERNAL_PRESSURE_COEFFICIENT[BuildingClass.CLASS_A], BuildingClass.CLASS_A
        elif opening_percentage <= 20.0:
            return INTERNAL_PRESSURE_COEFFICIENT[BuildingClass.CLASS_B], BuildingClass.CLASS_B
        else:
            return INTERNAL_PRESSURE_COEFFICIENT[BuildingClass.CLASS_C], BuildingClass.CLASS_C
    
    def calculate_wind_loads(
        self,
        height_m: float,
        width_m: float,
        length_m: float,
        opening_percentage: float = 10.0,
        storey_height_m: float = 3.0
    ) -> WindLoadResult:
        """
        Calculate complete wind load analysis for a building.
        
        Args:
            height_m: Total building height in meters
            width_m: Building width in meters
            length_m: Building length in meters
            opening_percentage: Percentage of wall area with openings
            storey_height_m: Height per storey for level-wise calculations
            
        Returns:
            WindLoadResult with all calculations
        """
        cpi, building_class = self.get_internal_pressure_coefficient(opening_percentage)
        
        parameters = WindLoadParameters(
            zone=self.zone,
            basic_wind_speed_ms=self.vb,
            terrain_category=self.terrain_category,
            building_class=building_class,
            k1=self.k1,
            k3=self.k3
        )
        
        result = WindLoadResult(
            parameters=parameters,
            building_height_m=height_m,
            building_width_m=width_m,
            building_length_m=length_m,
            opening_percentage=opening_percentage
        )
        
        if opening_percentage >= 5.0 and opening_percentage < 20.0:
            result.warnings.append(
                f"Building has {opening_percentage:.1f}% openings (Class B). "
                f"Internal pressure Cpi = ±{cpi} significantly increases wall/roof loads "
                "compared to sealed building (±0.2)."
            )
        elif opening_percentage >= 20.0:
            result.warnings.append(
                f"Building is open (>{opening_percentage:.1f}% openings, Class C). "
                f"Internal pressure Cpi = ±{cpi} is high. Verify cladding design."
            )
        
        num_levels = max(1, int(round(height_m / storey_height_m)))
        # X direction: wind blows along X, loaded face spans the building
        # length (Y extent); Y direction: face spans the width (X extent).
        cpe_ww_x, cpe_lw_x = self.get_external_pressure_coefficients(height_m, length_m, width_m, "along_length")
        cpe_ww_y, cpe_lw_y = self.get_external_pressure_coefficients(height_m, width_m, length_m, "along_length")

        for j in range(1, num_levels + 1):
            z = min(j * storey_height_m, height_m)
            k2 = self.calculate_k2(z)
            vz = self.calculate_design_wind_speed(z)
            pz = self.calculate_design_wind_pressure(z)
            # cladding-type net pressures (both signs of Cpi considered) - reported only
            p_ww = max((pz * (cpe_ww_x - cpi), pz * (cpe_ww_x + cpi)), key=abs)
            p_lw = max((pz * (cpe_lw_x - cpi), pz * (cpe_lw_x + cpi)), key=abs)
            result.pressure_results.append(WindPressureResult(
                height_m=z, k2=k2, design_wind_speed_ms=vz, design_wind_pressure_kn_m2=pz,
                cpe_windward=cpe_ww_x, cpe_leeward=cpe_lw_x, cpi=cpi,
                net_pressure_windward_kn_m2=p_ww, net_pressure_leeward_kn_m2=p_lw))
            # Tributary height: full storey for intermediate floors, half at roof
            trib = storey_height_m if j < num_levels else storey_height_m / 2.0
            # Global force uses external coefficients only (internal pressure cancels)
            fx = pz * (cpe_ww_x + abs(cpe_lw_x)) * length_m * trib
            fy = pz * (cpe_ww_y + abs(cpe_lw_y)) * width_m * trib
            result.storey_forces_x_kn.append(fx)
            result.storey_forces_y_kn.append(fy)
            result.storey_heights_m.append(z)
        result.total_base_shear_x_kn = sum(result.storey_forces_x_kn)
        result.total_base_shear_y_kn = sum(result.storey_forces_y_kn)
        result.total_overturning_moment_x_knm = sum(f * z for f, z in zip(result.storey_forces_x_kn, result.storey_heights_m))
        result.total_overturning_moment_y_knm = sum(f * z for f, z in zip(result.storey_forces_y_kn, result.storey_heights_m))
        min_b = min(width_m, length_m) if min(width_m, length_m) > 0 else 1.0
        if height_m / min_b >= 6.0:
            result.warnings.append(
                "UNCONSERVATIVE: h/w >= 6 - IS 875 (Part 3):2015 Table 5 gives Cpe up to +0.95 / -1.85 (net 2.8) for "
                "such buildings; the simplified coefficients used here (net <= 1.4) under-estimate the wind force")
        if height_m / min_b > 5.0 or height_m > 50.0:
            result.warnings.append("Height/width > 5 or height > 50 m: dynamic (gust factor) effects of IS 875 Part 3 "
                                   "are NOT evaluated - static wind only")
        result.warnings.append("Kd, Ka, Kc and k4 factors of IS 875 Part 3:2015 not applied (taken as 1.0); Cpe values simplified")
        return result


def calculate_wind_load(
    zone: WindZone,
    height_m: float,
    width_m: float,
    length_m: float,
    terrain_category: TerrainCategory = TerrainCategory.CATEGORY_2,
    opening_percentage: float = 10.0,
    storey_height_m: float = 3.0
) -> WindLoadResult:
    """
    Convenience function to calculate wind loads.
    
    Args:
        zone: Wind zone (1-6)
        height_m: Building height in meters
        width_m: Building width in meters
        length_m: Building length in meters
        terrain_category: Terrain category (1-4)
        opening_percentage: Percentage of wall openings
        
    Returns:
        WindLoadResult
    """
    calculator = WindLoadCalculator(zone=zone, terrain_category=terrain_category)
    return calculator.calculate_wind_loads(
        height_m=height_m,
        width_m=width_m,
        length_m=length_m,
        opening_percentage=opening_percentage,
        storey_height_m=storey_height_m
    )
