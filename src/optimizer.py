"""
Column size optimisation (indicative).

For each column segment the smallest standard section is found that passes
the PRODUCTION column check (:meth:`RebarDetailer.detail_column`: factored
combinations from the analysis, P-M interaction, minimum eccentricity,
slenderness) with a utilisation margin, while respecting the same minimum
sizes as the main design.

IMPORTANT: member forces come from the current analysis, which used the
current (unoptimised) stiffnesses.  Optimised sizes therefore require a full
re-analysis and re-design before use; ``OptimizationSummary.requires_reanalysis``
is always True.  (Audit finding R9: the previous version compared SERVICE
loads with a 1.15 margin, used fy = 500 and ignored minimum eccentricity.)
"""

import math
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

from .grid_manager import Column
from .materials import Concrete


class OptimizationLevel(str, Enum):
    NONE = "none"              # interaction ratio <= 1/1.30
    MODERATE = "moderate"      # interaction ratio <= 1/1.15
    AGGRESSIVE = "aggressive"  # interaction ratio <= 1/1.05


@dataclass
class OptimizedColumn:
    id: str
    level: int
    original_size_mm: Tuple[int, int]
    optimized_size_mm: Tuple[int, int]
    axial_load_kn: float                 # governing FACTORED axial load
    design_capacity_kn: float            # axial capacity of the optimised section (Cl 39.3 form, indicative)
    utilization_ratio: float             # governing P-M interaction ratio of the optimised section
    original_steel_ratio: float
    optimized_steel_ratio: float
    main_bars: str
    is_safe: bool
    safety_margin: float                 # 1 / interaction ratio
    dc_ratio: float = 0.0
    xu_d_ratio: float = 0.0              # retained for UI compatibility (not computed for columns)
    is_min_ecc_governed: bool = False
    required_steel_mm2: float = 0.0
    provided_steel_mm2: float = 0.0


@dataclass
class OptimizationSummary:
    total_columns: int
    optimized_columns: int
    original_concrete_m3: float
    optimized_concrete_m3: float
    concrete_saved_m3: float
    concrete_saved_pct: float
    original_steel_kg: float
    optimized_steel_kg: float
    steel_saved_kg: float
    steel_saved_pct: float
    original_cost: float
    optimized_cost: float
    cost_saved: float
    cost_saved_pct: float
    all_safe: bool
    requires_reanalysis: bool = True


class StructuralOptimizer:
    COLUMN_SIZES = [
        (230, 230), (230, 300), (230, 350), (230, 400),
        (300, 300), (300, 350), (300, 400), (300, 450),
        (350, 350), (350, 400), (350, 450), (350, 500),
        (400, 400), (400, 450), (400, 500), (400, 600),
        (450, 450), (450, 500), (450, 600),
        (500, 500), (500, 600), (500, 700),
        (600, 600), (600, 700), (600, 800),
    ]
    MARGINS = {OptimizationLevel.NONE: 1.30, OptimizationLevel.MODERATE: 1.15, OptimizationLevel.AGGRESSIVE: 1.05}

    def __init__(self, fck: float = 25.0, fy: float = 415.0,
                 optimization_level: OptimizationLevel = OptimizationLevel.MODERATE,
                 concrete_rate: float = 5000.0, steel_rate: float = 60.0,
                 min_width_mm: float = 300.0, min_depth_mm: float = 450.0):
        self.fck = fck
        self.fy = fy
        self.optimization_level = optimization_level
        self.concrete_rate = concrete_rate
        self.steel_rate = steel_rate
        self.min_width = min_width_mm
        self.min_depth = min_depth_mm
        self.target_margin = self.MARGINS[optimization_level]

    def _candidates(self) -> List[Tuple[int, int]]:
        out = set()
        for a, b in self.COLUMN_SIZES:
            for w, d in ((a, b), (b, a)):
                if min(w, d) >= self.min_width and max(w, d) >= self.min_depth:
                    out.add((w, d))
        return sorted(out, key=lambda s: (s[0] * s[1], s))

    def optimize_column(self, col: Column, concrete: Concrete):
        from .rebar_detailer import RebarDetailer
        combos = col.design_forces or [("1.5(DL+LL) axial only", 1.5 * col.load_kn, 0.0, 0.0)]
        L = max(col.z_top - col.z_bottom, 0.1)
        limit = 1.0 / self.target_margin
        best = None
        for w, d in self._candidates():
            res = RebarDetailer.detail_column(w, d, combos[0][1], concrete, col.level, self.fy, combos=combos,
                                              unsupported_length_m=L, column_id=col.id)
            if res.status != "FAIL" and res.interaction_ratio <= limit:
                return (w, d), res, True
            if best is None or res.interaction_ratio < best[1].interaction_ratio:
                best = ((w, d), res)
        return best[0], best[1], False

    def optimize_columns_by_floor(self, columns: List[Column], story_height_m: float, num_stories: int,
                                  rebar_schedule: Optional[dict] = None) -> Dict[str, OptimizedColumn]:
        concrete = Concrete.from_grade(f"M{int(self.fck)}")
        results = {}
        for col in columns:
            size, res, ok = self.optimize_column(col, concrete)
            ag = size[0] * size[1]
            orig_res = (rebar_schedule or {}).get(col.id)
            orig_ratio = orig_res.main_steel_area_mm2 / (col.width_nb * col.depth_nb) if orig_res else 0.02
            pu = max([f[1] for f in col.design_forces], default=1.5 * col.load_kn)
            cap = (0.4 * self.fck * (ag - res.main_steel_area_mm2) + 0.67 * self.fy * res.main_steel_area_mm2) / 1000.0
            results[col.id] = OptimizedColumn(
                id=col.id, level=col.level, original_size_mm=(int(col.width_nb), int(col.depth_nb)),
                optimized_size_mm=size, axial_load_kn=pu, design_capacity_kn=cap,
                utilization_ratio=res.interaction_ratio, original_steel_ratio=orig_ratio,
                optimized_steel_ratio=res.main_steel_area_mm2 / ag, main_bars=res.main_bars_desc, is_safe=ok,
                safety_margin=(1.0 / res.interaction_ratio) if res.interaction_ratio > 0 else float("inf"),
                dc_ratio=res.interaction_ratio,
                is_min_ecc_governed=max((max(abs(f[2]), abs(f[3])) for f in (col.design_forces or [("", 0, 0.0, 0.0)])),
                                        default=0.0) < 0.99 * max(res.mux_design_knm, res.muy_design_knm),
                required_steel_mm2=res.main_steel_area_mm2, provided_steel_mm2=res.main_steel_area_mm2)
        return results

    def calculate_optimization_summary(self, optimized: Dict[str, OptimizedColumn], story_height_m: float) -> OptimizationSummary:
        oc = os_ = ac = as_ = 0.0
        for c in optimized.values():
            v0 = c.original_size_mm[0] * c.original_size_mm[1] / 1e6 * story_height_m
            v1 = c.optimized_size_mm[0] * c.optimized_size_mm[1] / 1e6 * story_height_m
            oc += v0
            ac += v1
            os_ += v0 * c.original_steel_ratio * 7850.0
            as_ += v1 * c.optimized_steel_ratio * 7850.0
        cost0 = oc * self.concrete_rate + os_ * self.steel_rate
        cost1 = ac * self.concrete_rate + as_ * self.steel_rate
        pct = lambda a, b: (a - b) / a * 100.0 if a > 0 else 0.0
        return OptimizationSummary(
            total_columns=len(optimized),
            optimized_columns=sum(1 for c in optimized.values() if c.optimized_size_mm != c.original_size_mm),
            original_concrete_m3=oc, optimized_concrete_m3=ac, concrete_saved_m3=oc - ac, concrete_saved_pct=pct(oc, ac),
            original_steel_kg=os_, optimized_steel_kg=as_, steel_saved_kg=os_ - as_, steel_saved_pct=pct(os_, as_),
            original_cost=cost0, optimized_cost=cost1, cost_saved=cost0 - cost1, cost_saved_pct=pct(cost0, cost1),
            all_safe=all(c.is_safe for c in optimized.values()), requires_reanalysis=True)


def optimize_structure(columns: List[Column], story_height_m: float, num_stories: int, fck: float = 25.0,
                       enable_optimization: bool = True, fy: float = 415.0, seismic_zone: str = "III",
                       rebar_schedule: Optional[dict] = None, min_width_mm: float = 300.0,
                       min_depth_mm: float = 450.0) -> Tuple[Dict[str, OptimizedColumn], OptimizationSummary]:
    """Indicative column optimisation - see module docstring."""
    level = OptimizationLevel.MODERATE if enable_optimization else OptimizationLevel.NONE
    if seismic_zone in ("III", "IV", "V"):
        min_width_mm = max(min_width_mm, 300.0)
    opt = StructuralOptimizer(fck=fck, fy=fy, optimization_level=level,
                              min_width_mm=min_width_mm, min_depth_mm=min_depth_mm)
    results = opt.optimize_columns_by_floor(columns, story_height_m, num_stories, rebar_schedule)
    return results, opt.calculate_optimization_summary(results, story_height_m)
