"""
Practical site calculators for construction engineers.
Concrete pour planning (from an approved mix), rebar weight lookup, formwork areas,
cube-test arithmetic and stock-length cutting optimisation. Nothing here assumes a mix or
acceptance criterion.
"""
import math
from typing import Dict, List, Optional, Tuple


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


def materials_for_mix(volume_m3: float, mix: Dict) -> Dict:
    """Material quantities for ``volume_m3`` of concrete from an approved mix.

    ``mix`` holds the batch weights per m3 of the user's approved mix design
    (lab / RMC supplier): ``cement_kg_m3``, ``water_kg_m3``, ``fine_aggregate_kg_m3``,
    ``coarse_aggregate_kg_m3`` (and optional ``name``).  No mix is assumed.
    """
    for k in ("cement_kg_m3", "water_kg_m3", "fine_aggregate_kg_m3", "coarse_aggregate_kg_m3"):
        if mix.get(k) is None or mix[k] < 0:
            raise ValueError(f"approved mix needs {k}")
    v = max(volume_m3, 0.0)
    return {
        "cement_kg": round(v * mix["cement_kg_m3"], 1),
        "cement_bags": int(math.ceil(v * mix["cement_kg_m3"] / 50.0 - 1e-9)),
        "water_l": round(v * mix["water_kg_m3"], 0),          # 1 kg water = 1 L
        "fine_aggregate_t": round(v * mix["fine_aggregate_kg_m3"] / 1000.0, 3),
        "coarse_aggregate_t": round(v * mix["coarse_aggregate_kg_m3"] / 1000.0, 3),
        "water_cement_ratio": round(mix["water_kg_m3"] / mix["cement_kg_m3"], 3) if mix["cement_kg_m3"] > 0 else None,
    }


def concrete_pour_calculator(
    volume_m3: float,
    mixer_capacity_m3: float,
    wastage_pct: float,
    pour_rate_m3_hr: float,
    mix: Optional[Dict] = None,
) -> Dict:
    """Pour logistics from the user's inputs; materials only from an approved mix."""
    if mixer_capacity_m3 <= 0 or pour_rate_m3_hr <= 0:
        raise ValueError("mixer capacity and pour rate must be positive")
    gross_volume = volume_m3 * (1 + wastage_pct / 100)
    out = {
        "net_volume_m3": round(volume_m3, 2),
        "wastage_pct": wastage_pct,
        "gross_volume_m3": round(gross_volume, 2),
        "mixer_capacity_m3": mixer_capacity_m3,
        "num_trips": int(math.ceil(gross_volume / mixer_capacity_m3 - 1e-9)),
        "estimated_pour_time_hr": round(gross_volume / pour_rate_m3_hr, 1),
    }
    if mix:
        out["materials"] = materials_for_mix(gross_volume, mix)
    return out


def formwork_area_calculator(
    columns: list = None,
    beams: list = None,
    slab_area_m2: float = 0.0,
    slab_thickness_mm: float = 0.0,
) -> Dict:
    """Contact area of formwork (m2).

    Columns: perimeter x (segment height - slab thickness) for every column
    segment.  Beams: (soffit width + 2 x (depth - slab thickness)) x centre-line
    length for every beam copy passed (one per floor).  Slabs: soffit area as
    given.  Overlaps at joints are not deducted (conservative).
    """
    t = slab_thickness_mm / 1000.0
    col_formwork = 0.0
    for c in columns or []:
        perimeter_m = 2 * (c.width_nb + c.depth_nb) / 1000.0
        col_formwork += perimeter_m * max((c.z_top - c.z_bottom) - t, 0.0)
    beam_formwork = 0.0
    for b in beams or []:
        span_m = math.hypot(b.end_point.x - b.start_point.x, b.end_point.y - b.start_point.y)
        depth_m = b.properties.depth_mm / 1000.0
        width_m = b.properties.width_mm / 1000.0
        beam_formwork += (width_m + 2 * max(depth_m - t, 0.0)) * span_m
    total = col_formwork + beam_formwork + slab_area_m2
    return {
        "column_formwork_m2": round(col_formwork, 1),
        "beam_formwork_m2": round(beam_formwork, 1),
        "slab_formwork_m2": round(slab_area_m2, 1),
        "total_formwork_m2": round(total, 1),
        "plywood_sheets_8x4": int(math.ceil(total / (2.44 * 1.22) - 1e-9)),   # 2.44 x 1.22 m sheets, no reuse
    }


def cube_test_summary(fck_mpa: float, specimen_strengths_mpa: List[float]) -> Dict:
    """Mean / minimum of one sample's cube strengths against the specified fck.

    Arithmetic only: acceptance must be judged by the engineer under IS 456
    (acceptance criteria) and IS 516 (testing) - not decided here.
    """
    vals = [float(v) for v in specimen_strengths_mpa if v is not None and v > 0]
    if not vals or fck_mpa <= 0:
        raise ValueError("enter at least one cube strength and the specified grade")
    mean = sum(vals) / len(vals)
    return {
        "specimens": len(vals),
        "mean_mpa": round(mean, 2),
        "min_mpa": round(min(vals), 2),
        "max_mpa": round(max(vals), 2),
        "max_deviation_from_mean_pct": round(max(abs(v - mean) for v in vals) / mean * 100.0, 1),
        "mean_over_fck": round(mean / fck_mpa, 3),
    }


def optimise_cutting(pieces: List[Tuple[str, int, float, int]], stock_length_m: float) -> Dict:
    """First-fit-decreasing cutting plan from stock bars, per diameter.

    ``pieces``: (bar mark, diameter mm, cutting length m, number of pieces).
    Pieces longer than the stock bar cannot be cut from one bar and are listed
    under ``needs_lap`` (lap / coupler location to be detailed by the engineer).
    Returns per diameter: stock bars needed, cut weight, offcut, efficiency.
    """
    if stock_length_m <= 0:
        raise ValueError("stock length must be positive")
    by_dia: Dict[int, List[Tuple[float, str]]] = {}
    needs_lap = []
    for mark, dia, length, n in pieces:
        if length <= 0 or n <= 0:
            continue
        if length > stock_length_m + 1e-9:
            needs_lap.append({"Mark": mark, "Dia (mm)": dia, "Length (m)": round(length, 3), "Nos": n})
            continue
        by_dia.setdefault(int(dia), []).extend([(float(length), mark)] * int(n))
    out = {}
    for dia, items in sorted(by_dia.items()):
        items.sort(key=lambda t: -t[0])
        bars: List[List] = []          # [remaining length, [cuts]]
        for length, mark in items:
            for b in bars:
                if b[0] >= length - 1e-9:
                    b[0] -= length
                    b[1].append(mark)
                    break
            else:
                bars.append([stock_length_m - length, [mark]])
        unit = REBAR_WEIGHT_PER_M.get(dia, dia ** 2 / 162.0)
        used = sum(l for l, _ in items)
        out[dia] = {
            "stock_bars": len(bars),
            "cut_length_m": round(used, 2),
            "offcut_m": round(sum(b[0] for b in bars), 2),
            "efficiency_pct": round(used / (len(bars) * stock_length_m) * 100.0, 1) if bars else 0.0,
            "stock_weight_kg": round(len(bars) * stock_length_m * unit, 1),
            "cut_weight_kg": round(used * unit, 1),
            "plan": [{"Bar": i + 1, "Cuts": ", ".join(b[1]), "Offcut (m)": round(b[0], 3)} for i, b in enumerate(bars)],
        }
    return {"by_diameter": out, "needs_lap": needs_lap}
