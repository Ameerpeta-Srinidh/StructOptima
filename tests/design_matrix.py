"""
Every option of the Setup page as a test parameter, and generators of buildings over them (test helper).

- ``pairwise_cases()``: a covering array in which every pair of values of any two options appears together in at
  least one building (greedy construction, deterministic). Pair interactions are where most defects hide: a 230 mm
  wall column only misbehaves with a deep beam, a soft storey only with pinned bases, and so on.
- ``random_case(seed)``: a building with every option drawn at random (seeded, reproducible).
- ``build(case)``: the model and DesignInputs exactly as the Setup page builds them in manual mode.

The values cover the ranges the Setup page accepts, with the extremes included (smallest and largest plans, one
storey and tall buildings, every zone, soil, grade, exposure and construction type).
"""
import itertools
import random
from typing import Dict, List

from src.building_types import BUILDING_TYPES
from src.design_pipeline import DesignInputs
from src.grid_manager import GridManager
from src.wind_load import TerrainCategory, WindZone

OPTIONS: Dict[str, list] = {
    "plan": [(6.0, 6.0), (9.0, 12.0), (18.0, 12.0), (24.0, 9.0), (7.5, 30.0), (36.0, 24.0)],
    "storeys": [1, 2, 4, 7, 12],
    "storey_h": [2.8, 3.2, 4.5],
    "occupancy": list(BUILDING_TYPES),
    "zone": ["II", "III", "IV", "V"],
    "soil": ["I", "II", "III"],
    "system": ["OMRF", "SMRF"],
    "wind_zone": [None, "1", "3", "6"],
    "terrain": ["1", "2", "4"],
    "conc": ["M20", "M25", "M30"],
    "fy": [415.0, 500.0],
    "exposure": ["Mild", "Moderate", "Severe", "Very severe", "Extreme"],
    "nbc": [1, 2, 3, 4],
    "cracked": [True, False],
    "fixed_base": [True, False],
    "staircase": [False, True],
    "cantilevers": [(), ("top",), ("left", "right")],
    "interior_walls": [False, True],
    "wall_type": ["230", "115"],
    "openings": [0.2, 0.33, 0.5],
    "col_match_wall": [True, False],
    "sbc": [75.0, 150.0, 300.0],
}


def pairwise_cases(seed: int = 1, candidates: int = 40) -> List[Dict]:
    """Greedy covering array: repeatedly add the candidate case that covers the most uncovered value pairs."""
    rnd = random.Random(seed)
    keys = list(OPTIONS)
    uncovered = set()
    for a, b in itertools.combinations(range(len(keys)), 2):
        for i in range(len(OPTIONS[keys[a]])):
            for j in range(len(OPTIONS[keys[b]])):
                uncovered.add((a, i, b, j))
    cases = []
    while uncovered:
        best, best_cov = None, -1
        # seed each candidate with one uncovered pair so every iteration makes progress
        target = next(iter(sorted(uncovered)))
        for _ in range(candidates):
            idx = [rnd.randrange(len(OPTIONS[k])) for k in keys]
            idx[target[0]], idx[target[2]] = target[1], target[3]
            cov = sum(1 for a, b in itertools.combinations(range(len(keys)), 2) if (a, idx[a], b, idx[b]) in uncovered)
            if cov > best_cov:
                best, best_cov = idx, cov
        for a, b in itertools.combinations(range(len(keys)), 2):
            uncovered.discard((a, best[a], b, best[b]))
        cases.append({k: OPTIONS[k][i] for k, i in zip(keys, best)})
    return cases


def random_case(seed: int) -> Dict:
    rnd = random.Random(seed)
    case = {k: rnd.choice(v) for k, v in OPTIONS.items()}
    case["plan"] = (round(rnd.uniform(6.0, 40.0) * 2) / 2, round(rnd.uniform(6.0, 40.0) * 2) / 2)
    case["storeys"] = rnd.randint(1, 15)
    case["storey_h"] = round(rnd.uniform(2.7, 4.8), 1)
    case["sbc"] = float(rnd.choice([60, 80, 100, 120, 150, 200, 250, 400]))
    return case


def case_id(case: Dict) -> str:
    w, l = case["plan"]
    return (f"{w:g}x{l:g}-G{case['storeys']}-{case['occupancy'].split()[0][:5]}-Z{case['zone']}-{case['system']}-"
            f"S{case['soil']}-{case['conc']}-{int(case['fy'])}")


def build(case: Dict, max_iterations: int = 6):
    w, l = case["plan"]
    n, h = case["storeys"], case["storey_h"]
    gm = GridManager(width_m=w, length_m=l, num_stories=n, story_height_m=h)
    gm.cantilever_dirs = list(case["cantilevers"])
    gm.cantilever_len_m = 1.5
    gm.generate_grid()
    beams = gm.generate_beams()
    inp = DesignInputs(
        num_stories=n, story_height_m=h, building_type_name=case["occupancy"], sbc_kn_m2=case["sbc"],
        conc_grade=case["conc"], fy=case["fy"], seismic_zone=case["zone"], soil_type=case["soil"],
        structural_system=case["system"],
        wind_zone=WindZone(case["wind_zone"]) if case["wind_zone"] else None,
        terrain_category=TerrainCategory(case["terrain"]) if case["wind_zone"] else None,
        use_cracked_sections=case["cracked"], fixed_base=case["fixed_base"], add_staircase=case["staircase"],
        wall_core_thickness_mm=200.0 if case["wall_type"] == "230" else 100.0,
        wall_opening_fraction=case["openings"], include_interior_walls=case["interior_walls"],
        column_matches_wall=None if case["col_match_wall"] else False,
        exposure=case["exposure"], nbc_construction_type=case["nbc"], max_iterations=max_iterations)
    return gm, beams, inp
