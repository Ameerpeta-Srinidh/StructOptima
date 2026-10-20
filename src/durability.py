"""
Durability and fire requirements: exposure (IS 456:2000 Tables 3, 5, 16), fire resistance (IS 456 Table 16A and
Fig. 1) and the fire rating of each structural element by type of construction (NBC 2016 Part 4, Table 1).

All values typed from the printed standards and checked on 2026-10-20
(docs/verification/standards-check-2026-10-20.md; tests/test_durability.py).
"""
from dataclasses import dataclass
from typing import Dict

EXPOSURES = ["Mild", "Moderate", "Severe", "Very severe", "Extreme"]

# IS 456 Table 16: nominal cover (mm) for durability
TABLE16_COVER = {"Mild": 20, "Moderate": 30, "Severe": 45, "Very severe": 50, "Extreme": 75}

# IS 456 Table 5, reinforced concrete: (minimum cement kg/m3, maximum free w/c, minimum grade)
TABLE5_RCC = {"Mild": (300, 0.55, 20), "Moderate": (300, 0.50, 25), "Severe": (320, 0.45, 30),
              "Very severe": (340, 0.45, 35), "Extreme": (360, 0.40, 40)}

# IS 456 Table 16A: nominal cover (mm) for fire resistance (hours):
# (beam simply supported, beam continuous, slab simply supported, slab continuous, column)
TABLE16A = {0.5: (20, 20, 20, 20, 40), 1.0: (20, 20, 20, 20, 40), 1.5: (20, 20, 25, 20, 40),
            2.0: (40, 30, 35, 25, 40), 3.0: (60, 40, 45, 35, 40), 4.0: (70, 50, 55, 45, 40)}

# IS 456 Fig. 1: minimum dimensions (mm) for fire resistance (hours):
# (beam width b, slab thickness D, column fully exposed, column 50 % exposed, column one face exposed)
FIG1_MIN = {0.5: (200, 75, 150, 125, 100), 1.0: (200, 95, 200, 160, 120), 1.5: (200, 110, 250, 200, 140),
            2.0: (200, 125, 300, 200, 160), 3.0: (240, 150, 400, 300, 200), 4.0: (280, 170, 450, 350, 240)}

# NBC 2016 Part 4 Table 1 (minutes) by type of construction 1..4:
#   vii a) columns, beams ... supporting more than one floor; vii b) supporting one floor only;
#   vii c) supporting a roof only; ix) floor construction
NBC_TABLE1 = {
    "supporting_more_than_one_floor": {1: 240, 2: 120, 3: 120, 4: 120},
    "supporting_one_floor": {1: 180, 2: 90, 3: 60, 4: 60},
    "supporting_roof_only": {1: 180, 2: 90, 3: 60, 4: 60},
    "floor": {1: 120, 2: 90, 3: 60, 4: 60},
}


def hours(minutes: int) -> float:
    """NBC minutes -> the IS 456 Table 16A / Fig. 1 row (rounded up to the next tabulated period)."""
    for h in (0.5, 1.0, 1.5, 2.0, 3.0, 4.0):
        if minutes <= h * 60 + 1e-9:
            return h
    raise ValueError(f"Fire resistance {minutes} min exceeds the 4 h covered by IS 456 Table 16A")


def required_fire_hours(construction_type: int, role: str) -> float:
    return hours(NBC_TABLE1[role][construction_type])


@dataclass(frozen=True)
class DurabilityRequirements:
    exposure: str
    construction_type: int
    beam_cover_mm: float
    slab_cover_mm: float
    column_cover_mm: float
    footing_cover_mm: float
    min_grade: int                 # IS 456 Table 5 (RCC)
    max_wc: float
    min_cement_kg_m3: int
    column_fire_h: float           # columns supporting more than one floor
    top_column_fire_h: float       # top-storey columns (roof only)
    beam_fire_h: float
    slab_fire_h: float

    def column_fire_hours(self, supports_more_than_one_floor: bool) -> float:
        return self.column_fire_h if supports_more_than_one_floor else self.top_column_fire_h


def requirements(exposure: str, construction_type: int, fck: float = 25.0) -> DurabilityRequirements:
    """Covers and grade for an exposure condition and NBC type of construction.

    - Beams: max(Table 16, Table 16A continuous beam) - frame beams are continuous.
    - Slabs: max(Table 16, Table 16A simply supported slab) - edge panels may act simply supported (conservative).
    - Columns: max(Table 16, Table 16A, 40 mm of 26.4.2.1).
    - Footings: max(Table 16, 50 mm of 26.4.2.2).
    Table 16 Note 3 (5 mm less for severe / very severe exposure with M35 or above) is applied; Note 1 (5 mm less
    for bars up to 12 mm in mild exposure) is not used (conservative).
    """
    if exposure not in TABLE16_COVER:
        raise ValueError(f"Unknown exposure {exposure!r}; one of {EXPOSURES}")
    if construction_type not in (1, 2, 3, 4):
        raise ValueError("NBC type of construction must be 1, 2, 3 or 4")
    t16 = TABLE16_COVER[exposure]
    if exposure in ("Severe", "Very severe") and fck >= 35:
        t16 -= 5
    col_h = required_fire_hours(construction_type, "supporting_more_than_one_floor")
    top_h = required_fire_hours(construction_type, "supporting_roof_only")
    beam_h = required_fire_hours(construction_type, "supporting_one_floor")
    slab_h = required_fire_hours(construction_type, "floor")
    cement, wc, grade = TABLE5_RCC[exposure]
    return DurabilityRequirements(
        exposure=exposure, construction_type=construction_type,
        beam_cover_mm=float(max(t16, TABLE16A[beam_h][1])),
        slab_cover_mm=float(max(t16, TABLE16A[slab_h][2])),
        column_cover_mm=float(max(t16, TABLE16A[col_h][4], 40)),
        footing_cover_mm=float(max(t16, 50)),
        min_grade=grade, max_wc=wc, min_cement_kg_m3=cement,
        column_fire_h=col_h, top_column_fire_h=top_h, beam_fire_h=beam_h, slab_fire_h=slab_h)


def fire_min_dimensions(hours_: float) -> Dict[str, int]:
    b, d, col_full, col_half, col_one = FIG1_MIN[hours_]
    return {"beam_width": b, "slab_thickness": d, "column_fully_exposed": col_full,
            "column_50pc_exposed": col_half, "column_one_face": col_one}
