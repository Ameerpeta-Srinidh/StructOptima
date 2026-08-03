"""
Practical site calculators for construction engineers.
Concrete pour planning, rebar weight lookup, formwork estimation, curing schedule.
"""
import math
from typing import Dict, List, Tuple


# Standard rebar weights per meter (kg/m) by diameter
REBAR_WEIGHT_PER_M = {
    6: 0.222, 8: 0.395, 10: 0.617, 12: 0.888,
    16: 1.578, 20: 2.466, 25: 3.853, 28: 4.834, 32: 6.313, 36: 7.990
}

# Transit mixer capacities
MIXER_CAPACITIES = {
    "6 m³ (Standard)": 6.0,
    "7 m³ (Large)": 7.0,
    "9 m³ (Jumbo)": 9.0,
    "0.5 m³ (Site Mixer)": 0.5,
}


def calculate_rebar_weight(diameter_mm: int, length_m: float, count: int) -> Dict:
    """Calculate total weight of rebar pieces."""
    unit_wt = REBAR_WEIGHT_PER_M.get(diameter_mm, diameter_mm**2 / 162.0 * 1000 / 1000)
    weight_per_bar = unit_wt * length_m
    total_weight = weight_per_bar * count
    
    return {
        "diameter_mm": diameter_mm,
        "length_m": length_m,
        "count": count,
        "unit_weight_kg_m": round(unit_wt, 3),
        "weight_per_bar_kg": round(weight_per_bar, 2),
        "total_weight_kg": round(total_weight, 2),
        "total_weight_tonnes": round(total_weight / 1000, 3),
    }


def rebar_weight_table() -> List[Dict]:
    """Returns the standard rebar weight table for all common diameters."""
    rows = []
    for dia, wt in REBAR_WEIGHT_PER_M.items():
        area = math.pi * (dia/2)**2
        rows.append({
            "Diameter (mm)": dia,
            "Area (mm²)": round(area, 1),
            "Weight (kg/m)": wt,
            "Weight per 12m bar (kg)": round(wt * 12, 2),
            "Bars per Tonne": int(1000 / (wt * 12)) if wt > 0 else 0,
        })
    return rows


def concrete_pour_calculator(
    volume_m3: float,
    mixer_type: str = "6 m³ (Standard)",
    wastage_pct: float = 3.0,
    pour_rate_m3_hr: float = 8.0,
) -> Dict:
    """Calculate concrete pour logistics."""
    cap = MIXER_CAPACITIES.get(mixer_type, 6.0)
    gross_volume = volume_m3 * (1 + wastage_pct / 100)
    num_trips = math.ceil(gross_volume / cap)
    pour_time_hr = gross_volume / pour_rate_m3_hr
    
    # IS 10262 nominal mix proportions (simplified)
    # For M25: cement = volume * 1.54 / (1+1+2) * 1/0.035 bags
    dry_factor = 1.54
    cement_bags = gross_volume * dry_factor / 4.0 / 0.035
    sand_m3 = gross_volume * dry_factor * 1 / 4.0
    agg_m3 = gross_volume * dry_factor * 2 / 4.0
    water_l = gross_volume * 0.45 * 400  # w/c ratio * cement content approx
    
    return {
        "net_volume_m3": round(volume_m3, 2),
        "wastage_pct": wastage_pct,
        "gross_volume_m3": round(gross_volume, 2),
        "mixer_type": mixer_type,
        "mixer_capacity_m3": cap,
        "num_trips": num_trips,
        "estimated_pour_time_hr": round(pour_time_hr, 1),
        "cement_bags": int(math.ceil(cement_bags)),
        "sand_m3": round(sand_m3, 2),
        "aggregate_m3": round(agg_m3, 2),
        "water_liters": int(round(water_l)),
    }


def formwork_area_calculator(
    columns: list = None,
    beams: list = None,
    slab_area_m2: float = 0.0,
    story_height_m: float = 3.0,
) -> Dict:
    """Estimate formwork area for columns, beams, and slabs."""
    col_formwork = 0.0
    if columns:
        for c in columns:
            perimeter_m = 2 * (c.width_nb + c.depth_nb) / 1000.0
            col_formwork += perimeter_m * story_height_m
    
    beam_formwork = 0.0
    if beams:
        for b in beams:
            span_m = math.hypot(
                b.end_point.x - b.start_point.x,
                b.end_point.y - b.start_point.y
            )
            # Beam formwork = bottom + 2 sides
            depth_m = b.properties.depth_mm / 1000.0
            width_m = b.properties.width_mm / 1000.0
            beam_formwork += (width_m + 2 * depth_m) * span_m
    
    total = col_formwork + beam_formwork + slab_area_m2
    
    # Plywood estimation (standard 8'×4' = 2.44m × 1.22m = 2.97 m²)
    plywood_sheets = math.ceil(total / 2.97)
    
    return {
        "column_formwork_m2": round(col_formwork, 1),
        "beam_formwork_m2": round(beam_formwork, 1),
        "slab_formwork_m2": round(slab_area_m2, 1),
        "total_formwork_m2": round(total, 1),
        "plywood_sheets_8x4": plywood_sheets,
        "plywood_cost_approx_inr": plywood_sheets * 1200,  # ~INR 1200/sheet
    }


def curing_schedule(grade: str = "M25") -> List[Dict]:
    """Returns IS 456 curing schedule with expected strength gain."""
    fck = int(grade.replace("M", ""))
    
    return [
        {"Day": 1, "Expected Strength (%)": 16, f"Expected fck (MPa)": round(0.16 * fck, 1),
         "Action": "Keep forms wet. No load."},
        {"Day": 3, "Expected Strength (%)": 40, f"Expected fck (MPa)": round(0.40 * fck, 1),
         "Action": "Continuous curing. Side forms may be removed for columns."},
        {"Day": 7, "Expected Strength (%)": 65, f"Expected fck (MPa)": round(0.65 * fck, 1),
         "Action": "Curing must continue. Slab props can be partially released."},
        {"Day": 14, "Expected Strength (%)": 90, f"Expected fck (MPa)": round(0.90 * fck, 1),
         "Action": "Test cubes due. Re-propping may begin for slabs."},
        {"Day": 28, "Expected Strength (%)": 100, f"Expected fck (MPa)": round(1.00 * fck, 1),
         "Action": "Design strength reached. Full dead load may be applied."},
    ]


def mix_design_table(grade: str = "M25") -> Dict:
    """Returns IS 10262 indicative mix proportions."""
    fck = int(grade.replace("M", ""))
    
    # Standard target mean strength
    # ft = fck + 1.65 * s (s = 4 MPa std dev for good control)
    ft = fck + 1.65 * 4.0
    
    # Approximate proportions by grade
    proportions = {
        20: {"cement": 340, "water": 170, "fa": 700, "ca": 1200, "wc": 0.50, "ratio": "1:2.06:3.53"},
        25: {"cement": 380, "water": 171, "fa": 670, "ca": 1190, "wc": 0.45, "ratio": "1:1.76:3.13"},
        30: {"cement": 410, "water": 168, "fa": 650, "ca": 1180, "wc": 0.41, "ratio": "1:1.59:2.88"},
        35: {"cement": 440, "water": 165, "fa": 630, "ca": 1170, "wc": 0.38, "ratio": "1:1.43:2.66"},
        40: {"cement": 460, "water": 161, "fa": 610, "ca": 1160, "wc": 0.35, "ratio": "1:1.33:2.52"},
    }
    
    p = proportions.get(fck, proportions[25])
    
    return {
        "grade": grade,
        "target_mean_strength_mpa": round(ft, 1),
        "cement_kg_m3": p["cement"],
        "water_kg_m3": p["water"],
        "fine_aggregate_kg_m3": p["fa"],
        "coarse_aggregate_kg_m3": p["ca"],
        "water_cement_ratio": p["wc"],
        "nominal_ratio": p["ratio"],
        "cement_bags_per_m3": round(p["cement"] / 50, 1),
        "note": "Indicative proportions per IS 10262. Actual mix design requires trial mixes."
    }
