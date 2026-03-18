import math
from enum import Enum

class BendDeductionType(Enum):
    NONE = 0
    IS_2502 = 1
    SP_34 = 2

class HookType(Enum):
    L_BEND = 1
    U_HOOK = 2
    SEISMIC_135 = 3
    STANDARD_90 = 4

from dataclasses import dataclass

@dataclass
class CuttingLengthResult:
    cutting_length_mm: float
    deduction_mm: float = 0.0

class BBSUtils:
    @staticmethod
    def calculate_cutting_length(shape_code: int | str, dims_mm: dict, bar_dia_mm: float = 0.0, bend_deduction: BendDeductionType = BendDeductionType.IS_2502, hook_type: HookType = HookType.STANDARD_90) -> CuttingLengthResult:
        """
        Calculates cutting length including bend deductions.
        shape_code: 0 (Straight), 21 (L), etc.
        dims_mm: Dictionary of dimensions (A, B, C...)
        hook_type: Type of hook (STANDARD_90, SEISMIC_135, etc.)
        """
        total_len = sum(dims_mm.values())
        deduction = 0.0
        
        if bend_deduction != BendDeductionType.NONE:
            sc_str = str(shape_code)
            if sc_str in ["21", "L-Shape", "U-Shape", "51", "Box"]:
                 num_bends = 0
                 if sc_str in ["21", "L-Shape"]: num_bends = 1
                 elif sc_str in ["U-Shape"]: num_bends = 2
                 elif sc_str in ["51", "Box"]: num_bends = 4
                 
                 # Deduction per bend depends on hook type
                 if hook_type == HookType.SEISMIC_135:
                     deduction_per_bend = 3 * bar_dia_mm  # 135-degree hooks per IS 13920
                 else:
                     deduction_per_bend = 2 * bar_dia_mm  # Standard 90-degree
                 
                 deduction = num_bends * deduction_per_bend
                 
        return CuttingLengthResult(cutting_length_mm=total_len - deduction, deduction_mm=deduction)

def generate_bar_shape_svg(shape_code: str, dims: dict) -> str:
    """
    Generates an SVG string for a given bar shape code and dimensions.
    Returns a raw SVG string that can be embedded in HTML/Markdown.
    
    dims: dict with keys 'A', 'B', 'C', 'D', 'E' depending on shape.
    """
    
    width = 100
    height = 50
    stroke_width = 3
    color = "black"
    
    svg_header = f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">'
    svg_footer = '</svg>'
    
    path_d = ""
    labels = []
    
    # Scale factor to fit in 100x50 box
    # We use a normalized coordinate system 0-100
    
    if shape_code == "L-Shape" or shape_code == "21":
        # L-Shape: A (Horizontal) + B (Vertical Hook normally? Or A vertical B horizontal)
        # Standard: A is usually the long leg, B is hook? 
        # Let's assume A = Horizontal, B = Vertical Up
        
        # Draw L
        margin = 10
        # Start bottom left
        x0, y0 = margin, height - margin
        x1, y1 = width - margin, height - margin # A leg
        x2, y2 = margin, margin # B leg
        
        path_d = f"M {x0} {y2} L {x0} {y0} L {x1} {y0}"
        
        # Labels
        labels.append((x0 - 5, (y0+y2)/2, "B"))
        labels.append(((x0+x1)/2, y0 + 10, "A"))
        
    elif shape_code == "U-Shape" or shape_code == "21": # Note: 21 is actually code for something else often. Using logic names.
        # U-Shape (Stirrup or Link): A (Vert), B (Horiz), C (Vert)
        margin = 10
        x0, y0 = margin, margin # Top Left
        x1, y1 = margin, height - margin # Bot Left
        x2, y2 = width - margin, height - margin # Bot Right
        x3, y3 = width - margin, margin # Top Right
        
        path_d = f"M {x0} {y0} L {x1} {y1} L {x2} {y2} L {x3} {y3}"
        
        labels.append((x0-5, (y0+y1)/2, "A"))
        labels.append(((x1+x2)/2, y1+10, "B"))
        labels.append((x2+5, (y2+y3)/2, "C"))

    elif shape_code == "Box" or shape_code == "51":
        # Closed Stirrup
        margin = 10
        x0, y0 = margin, margin
        x1, y1 = margin, height - margin
        x2, y2 = width - margin, height - margin
        x3, y3 = width - margin, margin
        
        path_d = f"M {x0} {y0} L {x1} {y1} L {x2} {y2} L {x3} {y3} Z" # Close path
        
        labels.append((x0-5, (y0+y1)/2, "A"))
        labels.append(((x1+x2)/2, y1+10, "B"))

    elif shape_code == "Crank" or shape_code == "41":
        # Cranked Bar
        # Straight -> Crank -> Straight
        margin = 5
        x0, y0 = margin, height - margin # Start
        x1, y1 = 30, height - margin # Crank start
        x2, y2 = 45, margin # Crank top
        x3, y3 = width - margin, margin # End
        
        path_d = f"M {x0} {y0} L {x1} {y1} L {x2} {y2} L {x3} {y2}"
        
        labels.append(((x0+x1)/2, y0+10, "A"))
        labels.append(((x2+x3)/2, y2-5, "C"))
        
    else:
        # Default Straight Bar
        margin = 10
        y = height / 2
        path_d = f"M {margin} {y} L {width-margin} {y}"
        labels.append((width/2, y+15, "L"))

    # Construct SVG
    svg_content = f'<path d="{path_d}" stroke="{color}" stroke-width="{stroke_width}" fill="none" />'
    
    # Add Text
    for lx, ly, text in labels:
        svg_content += f'<text x="{lx}" y="{ly}" font-family="Arial" font-size="10" fill="red" text-anchor="middle">{text}</text>'

    return svg_header + svg_content + svg_footer

def get_site_vernacular(bar_mark: str) -> str:
    """
    Translates academic bar marks to site vernacular.
    Example: 
    - B1 (Bottom Layer 1) -> "Bottom-Bottom" (Main Mesh)
    - T1 (Top Layer 1) -> "Top-Main" (Distribution)
    - ST (Stirrup) -> "Ring / Link"
    """
    check = bar_mark.upper()
    if "ST" in check:
        return "Ring / Link"
    elif "B1" in check:
        return "Bottom-Bottom (Main)"
    elif "B2" in check:
        return "Bottom-Top (Cross)"
    elif "T1" in check:
        return "Top-Main (Support)"
    elif "T2" in check:
        return "Top-Dist (Extra)"
    elif "EF" in check:
        return "Face Bar (Side)"
    return bar_mark
