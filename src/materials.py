from typing import Optional, Literal
from pydantic import BaseModel, Field, PositiveFloat

class Material(BaseModel):
    """Base material class."""
    name: str = Field(..., description="Name of the material")
    density: PositiveFloat = Field(..., description="Density in kN/m3")
    modulus_of_elasticity: PositiveFloat = Field(..., description="Young's Modulus (E) in N/mm2 (MPa)")
    poissons_ratio: float = Field(..., ge=0, le=0.5, description="Poisson's Ratio")
    embodied_carbon_factor: float = Field(default=0.0, description="kgCO2e per unit mass/volume")

class Concrete(Material):
    """Concrete material based on IS 456."""
    material_type: Literal["concrete"] = "concrete"
    grade: str = Field(..., description="Grade of concrete (e.g., M20, M25)")
    fck: PositiveFloat = Field(..., description="Characteristic compressive strength in N/mm2 (MPa)")

    @classmethod
    def from_grade(cls, grade: str) -> "Concrete":
        """Factory method to create Concrete from grade string (e.g., 'M25')."""
        grade_map = {
            "M20": 20.0, "M25": 25.0, "M30": 30.0, "M35": 35.0, "M40": 40.0, "M50": 50.0
        }
        val = int(grade.upper().replace('M', '')) if grade.upper().startswith('M') else 20
        fck_val = float(val)
        
        # IS 456:2000 Cl. 6.2.3.1 - Ec = 5000 * sqrt(fck)
        ec = 5000 * (fck_val ** 0.5)
        
        # Embodied Carbon: OPC ~300-350 kg/m3. 
        # We can adjust this later via instance update if Fly Ash is used.
        return cls(
            name=f"Concrete {grade}",
            grade=grade.upper(),
            density=25.0, # IS 456 Cl 19.2.1 (Reinforced Concrete)
            fck=fck_val,
            modulus_of_elasticity=ec,
            poissons_ratio=0.2, # IS 456 Cl 6.2.5
            embodied_carbon_factor=300.0 # kgCO2/m3 (Default OPC)
        )

class Steel(Material):
    """Steel material based on IS 456 / IS 800."""
    material_type: Literal["steel"] = "steel"
    grade: str = Field(..., description="Grade of steel (e.g., Fe415, Fe500)")
    fy: PositiveFloat = Field(..., description="Yield strength in N/mm2 (MPa)")

    @classmethod
    def from_grade(cls, grade: str) -> "Steel":
        """Factory method to create Steel from grade string (e.g., 'Fe415')."""
        val = int(grade.upper().replace('FE', '')) if grade.upper().startswith('FE') else 415
        fy_val = float(val)
        
        return cls(
            name=f"Steel {grade}",
            grade=grade.upper(),
            density=78.5, # Standard value
            fy=fy_val,
            modulus_of_elasticity=2e5, # 2.0 x 10^5 N/mm2
            poissons_ratio=0.3,
            embodied_carbon_factor=1.85 # kgCO2/kg (Avg recycled/virgin mix)
        )
