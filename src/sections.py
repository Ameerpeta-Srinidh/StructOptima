from abc import ABC, abstractmethod
from typing import Literal
import math
from pydantic import BaseModel, Field, PositiveFloat

class SectionProperties(BaseModel):
    """Output properties for a section."""
    area: float
    ix: float # Moment of Inertia about major axis (presumed horizontal X-X)
    iy: float # Moment of Inertia about minor axis (presumed vertical Y-Y)
    zx: float # Section modulus about X-X
    zy: float # Section modulus about Y-Y

class Section(BaseModel, ABC):
    """Base abstract section class."""
    name: str = Field(..., description="Name or identifier of the section")
    
    @abstractmethod
    def calculate_properties(self) -> SectionProperties:
        """Calculates geometric properties."""
        pass

class RectangularSection(Section):
    type: Literal["rectangular"] = "rectangular"
    width_b: PositiveFloat = Field(..., description="Width (b) of the section in mm")
    depth_d: PositiveFloat = Field(..., description="Depth (d) of the section in mm")

    def calculate_properties(self) -> SectionProperties:
        b = self.width_b
        d = self.depth_d
        
        area = b * d
        ix = (b * d**3) / 12
        iy = (d * b**3) / 12
        zx = ix / (d / 2)
        zy = iy / (b / 2)
        
        return SectionProperties(area=area, ix=ix, iy=iy, zx=zx, zy=zy)

class CircularSection(Section):
    type: Literal["circular"] = "circular"
    diameter: PositiveFloat = Field(..., description="Diameter of the section in mm")

    def calculate_properties(self) -> SectionProperties:
        dia = self.diameter
        radius = dia / 2
        
        area = math.pi * radius**2
        inertia = (math.pi * dia**4) / 64 # Ix = Iy for circle
        z = inertia / radius
        
        return SectionProperties(area=area, ix=inertia, iy=inertia, zx=z, zy=z)

class ISection(Section):
    type: Literal["i_section"] = "i_section"
    flange_width_bf: PositiveFloat = Field(..., description="Width of flange in mm")
    flange_thickness_tf: PositiveFloat = Field(..., description="Thickness of flange in mm")
    web_thickness_tw: PositiveFloat = Field(..., description="Thickness of web in mm")
    overall_depth_d: PositiveFloat = Field(..., description="Overall depth in mm")

    def calculate_properties(self) -> SectionProperties:
        bf = self.flange_width_bf
        tf = self.flange_thickness_tf
        tw = self.web_thickness_tw
        D = self.overall_depth_d
        dw = D - 2 * tf # Depth of web portion only (clear distance between flanges)
        
        # Area = 2*Flanges + Web
        area = 2 * (bf * tf) + (dw * tw)
        
        # Ix: Outer rectangle - Inner rectangles (voids)
        # Outer: B * D^3 / 12
        # Inner void sum width: (B - tw)
        # Inner void height: dw
        ix = ((bf * D**3) - ((bf - tw) * dw**3)) / 12
        
        # Iy: 2*Flanges + Web
        # Flange Iy = tf * bf^3 / 12
        # Web Iy = dw * tw^3 / 12
        iy = 2 * (tf * bf**3 / 12) + (dw * tw**3 / 12)
        
        zx = ix / (D / 2)
        zy = iy / (bf / 2)
        
        return SectionProperties(area=area, ix=ix, iy=iy, zx=zx, zy=zy)
