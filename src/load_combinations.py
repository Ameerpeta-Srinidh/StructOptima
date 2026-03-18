"""
Load Combinations Module - IS 456:2000 Table 18 & IS 1893:2016

Implements mandatory load combinations for structural design per Indian Standards.

Features:
- IS 456 Table 18 limit state combinations
- Critical uplift/overturning combination (0.9DL + 1.5WL)
- Seismic load combinations with vertical component
- Seismic weight calculation with LL reduction factor

Reference:
- IS 456:2000 Table 18 - Load Combinations for Limit State Design
- IS 1893 (Part 1): 2016 - Seismic Weight and Load Combinations

DISCLAIMER: All designs must be verified by a licensed Structural Engineer
before construction.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum


class LoadType(str, Enum):
    """Types of loads for combination."""
    DEAD = "DL"
    LIVE = "LL"
    WIND = "WL"
    SEISMIC_X = "EQx"
    SEISMIC_Y = "EQy"
    SEISMIC_Z = "EQz"  # Vertical seismic


class CombinationType(str, Enum):
    """Types of load combinations."""
    STRENGTH = "Strength"  # Ultimate limit state
    SERVICEABILITY = "Serviceability"  # Service limit state
    STABILITY = "Stability"  # Overturning/uplift check


@dataclass
class LoadCase:
    """Single load case with magnitude."""
    load_type: LoadType
    magnitude_kn: float = 0.0
    magnitude_kn_m2: float = 0.0  # For distributed loads
    description: str = ""


@dataclass
class LoadCombination:
    """A single load combination with factors."""
    name: str
    combination_type: CombinationType
    factors: Dict[LoadType, float]  # {LoadType: factor}
    description: str
    is_critical: bool = False  # Flag for often-missed combinations
    is_code_requirement: str = ""  # Which code mandates this


@dataclass
class CombinedLoadResult:
    """Result of applying a load combination."""
    combination_name: str
    factored_dead_kn: float
    factored_live_kn: float
    factored_wind_kn: float
    factored_seismic_kn: float
    total_factored_kn: float
    is_uplift_case: bool = False


@dataclass
class SeismicWeightResult:
    """Seismic weight calculation per IS 1893."""
    total_dead_load_kn: float
    total_live_load_kn: float
    live_load_intensity_kn_m2: float
    ll_reduction_factor: float  # 0.25 or 0.50 per IS 1893
    effective_live_load_kn: float
    seismic_weight_kn: float
    code_reference: str


IS_456_COMBINATIONS = [
    LoadCombination(
        name="1.5(DL+LL)",
        combination_type=CombinationType.STRENGTH,
        factors={LoadType.DEAD: 1.5, LoadType.LIVE: 1.5},
        description="Dead + Live (no lateral loads)",
        is_code_requirement="IS 456 Table 18"
    ),
    LoadCombination(
        name="1.2(DL+LL+WL)",
        combination_type=CombinationType.STRENGTH,
        factors={LoadType.DEAD: 1.2, LoadType.LIVE: 1.2, LoadType.WIND: 1.2},
        description="Dead + Live + Wind",
        is_code_requirement="IS 456 Table 18"
    ),
    LoadCombination(
        name="1.2(DL+LL-WL)",
        combination_type=CombinationType.STRENGTH,
        factors={LoadType.DEAD: 1.2, LoadType.LIVE: 1.2, LoadType.WIND: -1.2},
        description="Dead + Live - Wind (reverse)",
        is_code_requirement="IS 456 Table 18"
    ),
    LoadCombination(
        name="1.5(DL+WL)",
        combination_type=CombinationType.STRENGTH,
        factors={LoadType.DEAD: 1.5, LoadType.WIND: 1.5},
        description="Dead + Wind (no live load)",
        is_code_requirement="IS 456 Table 18"
    ),
    LoadCombination(
        name="1.5(DL-WL)",
        combination_type=CombinationType.STRENGTH,
        factors={LoadType.DEAD: 1.5, LoadType.WIND: -1.5},
        description="Dead - Wind (reverse)",
        is_code_requirement="IS 456 Table 18"
    ),
    LoadCombination(
        name="0.9DL+1.5WL",
        combination_type=CombinationType.STABILITY,
        factors={LoadType.DEAD: 0.9, LoadType.WIND: 1.5},
        description="CRITICAL: Uplift/Overturning check - minimum DL resisting wind",
        is_critical=True,
        is_code_requirement="IS 456 Table 18"
    ),
    LoadCombination(
        name="0.9DL-1.5WL",
        combination_type=CombinationType.STABILITY,
        factors={LoadType.DEAD: 0.9, LoadType.WIND: -1.5},
        description="CRITICAL: Uplift/Overturning check (reverse wind)",
        is_critical=True,
        is_code_requirement="IS 456 Table 18"
    ),
    LoadCombination(
        name="1.2(DL+LL+EQx)",
        combination_type=CombinationType.STRENGTH,
        factors={LoadType.DEAD: 1.2, LoadType.LIVE: 1.2, LoadType.SEISMIC_X: 1.2},
        description="Dead + Live + Seismic X",
        is_code_requirement="IS 1893"
    ),
    LoadCombination(
        name="1.2(DL+LL-EQx)",
        combination_type=CombinationType.STRENGTH,
        factors={LoadType.DEAD: 1.2, LoadType.LIVE: 1.2, LoadType.SEISMIC_X: -1.2},
        description="Dead + Live - Seismic X (reverse)",
        is_code_requirement="IS 1893"
    ),
    LoadCombination(
        name="1.2(DL+LL+EQy)",
        combination_type=CombinationType.STRENGTH,
        factors={LoadType.DEAD: 1.2, LoadType.LIVE: 1.2, LoadType.SEISMIC_Y: 1.2},
        description="Dead + Live + Seismic Y",
        is_code_requirement="IS 1893"
    ),
    LoadCombination(
        name="1.2(DL+LL-EQy)",
        combination_type=CombinationType.STRENGTH,
        factors={LoadType.DEAD: 1.2, LoadType.LIVE: 1.2, LoadType.SEISMIC_Y: -1.2},
        description="Dead + Live - Seismic Y (reverse)",
        is_code_requirement="IS 1893"
    ),
    LoadCombination(
        name="1.5(DL+EQx)",
        combination_type=CombinationType.STRENGTH,
        factors={LoadType.DEAD: 1.5, LoadType.SEISMIC_X: 1.5},
        description="Dead + Seismic X (no live)",
        is_code_requirement="IS 1893"
    ),
    LoadCombination(
        name="0.9DL+1.5EQx",
        combination_type=CombinationType.STABILITY,
        factors={LoadType.DEAD: 0.9, LoadType.SEISMIC_X: 1.5},
        description="CRITICAL: Seismic uplift/overturning check",
        is_critical=True,
        is_code_requirement="IS 1893"
    ),
    LoadCombination(
        name="0.9DL+1.5EQy",
        combination_type=CombinationType.STABILITY,
        factors={LoadType.DEAD: 0.9, LoadType.SEISMIC_Y: 1.5},
        description="CRITICAL: Seismic uplift/overturning check Y",
        is_critical=True,
        is_code_requirement="IS 1893"
    ),
]

VERTICAL_SEISMIC_COMBINATIONS = [
    LoadCombination(
        name="1.2(DL+LL+EQx+EQz)",
        combination_type=CombinationType.STRENGTH,
        factors={
            LoadType.DEAD: 1.2, 
            LoadType.LIVE: 1.2, 
            LoadType.SEISMIC_X: 1.2,
            LoadType.SEISMIC_Z: 1.2
        },
        description="With vertical seismic - for cantilevers and large spans",
        is_critical=True,
        is_code_requirement="IS 1893/IS 16700"
    ),
    LoadCombination(
        name="1.2(DL+LL+EQx-EQz)",
        combination_type=CombinationType.STRENGTH,
        factors={
            LoadType.DEAD: 1.2, 
            LoadType.LIVE: 1.2, 
            LoadType.SEISMIC_X: 1.2,
            LoadType.SEISMIC_Z: -1.2
        },
        description="With downward vertical seismic",
        is_critical=True,
        is_code_requirement="IS 1893/IS 16700"
    ),
]


class LoadCombinationManager:
    """
    Manages load combinations per IS 456 and IS 1893.
    
    Ensures all mandatory combinations including critical uplift cases
    are generated and applied.
    """
    
    def __init__(
        self,
        include_wind: bool = True,
        include_seismic: bool = True,
        include_vertical_seismic: bool = False,
        seismic_zone: str = "III"
    ):
        """
        Initialize load combination manager.
        
        Args:
            include_wind: Include wind load combinations
            include_seismic: Include seismic load combinations
            include_vertical_seismic: Include vertical seismic (Ez) for cantilevers
            seismic_zone: Seismic zone (affects vertical seismic requirement)
        """
        self.include_wind = include_wind
        self.include_seismic = include_seismic
        self.include_vertical_seismic = include_vertical_seismic
        self.seismic_zone = seismic_zone
        
        self.combinations: List[LoadCombination] = []
        self._build_combinations()
    
    def _build_combinations(self):
        """Build the list of applicable combinations."""
        for combo in IS_456_COMBINATIONS:
            has_wind = LoadType.WIND in combo.factors
            has_seismic = any(
                lt in combo.factors 
                for lt in [LoadType.SEISMIC_X, LoadType.SEISMIC_Y]
            )
            
            if has_wind and not self.include_wind:
                continue
            if has_seismic and not self.include_seismic:
                continue
            
            self.combinations.append(combo)
        
        if self.include_seismic and self.include_vertical_seismic:
            for combo in VERTICAL_SEISMIC_COMBINATIONS:
                self.combinations.append(combo)
    
    def get_all_combinations(self) -> List[LoadCombination]:
        """Get all applicable load combinations."""
        return self.combinations
    
    def get_critical_combinations(self) -> List[LoadCombination]:
        """Get only the critical combinations (often missed)."""
        return [c for c in self.combinations if c.is_critical]
    
    def get_stability_combinations(self) -> List[LoadCombination]:
        """Get stability/uplift checking combinations."""
        return [
            c for c in self.combinations 
            if c.combination_type == CombinationType.STABILITY
        ]
    
    def apply_combination(
        self,
        combination: LoadCombination,
        dead_load_kn: float,
        live_load_kn: float = 0.0,
        wind_load_kn: float = 0.0,
        seismic_x_kn: float = 0.0,
        seismic_y_kn: float = 0.0,
        seismic_z_kn: float = 0.0
    ) -> CombinedLoadResult:
        """
        Apply a load combination to given loads.
        
        Args:
            combination: LoadCombination to apply
            dead_load_kn: Unfactored dead load
            live_load_kn: Unfactored live load
            wind_load_kn: Unfactored wind load
            seismic_x_kn: Unfactored seismic X
            seismic_y_kn: Unfactored seismic Y
            seismic_z_kn: Unfactored seismic Z (vertical)
            
        Returns:
            CombinedLoadResult
        """
        loads = {
            LoadType.DEAD: dead_load_kn,
            LoadType.LIVE: live_load_kn,
            LoadType.WIND: wind_load_kn,
            LoadType.SEISMIC_X: seismic_x_kn,
            LoadType.SEISMIC_Y: seismic_y_kn,
            LoadType.SEISMIC_Z: seismic_z_kn,
        }
        
        factored_dead = dead_load_kn * combination.factors.get(LoadType.DEAD, 0.0)
        factored_live = live_load_kn * combination.factors.get(LoadType.LIVE, 0.0)
        factored_wind = wind_load_kn * combination.factors.get(LoadType.WIND, 0.0)
        factored_seismic = (
            seismic_x_kn * combination.factors.get(LoadType.SEISMIC_X, 0.0) +
            seismic_y_kn * combination.factors.get(LoadType.SEISMIC_Y, 0.0) +
            seismic_z_kn * combination.factors.get(LoadType.SEISMIC_Z, 0.0)
        )
        
        total = factored_dead + factored_live + factored_wind + factored_seismic
        
        is_uplift = combination.combination_type == CombinationType.STABILITY
        
        return CombinedLoadResult(
            combination_name=combination.name,
            factored_dead_kn=factored_dead,
            factored_live_kn=factored_live,
            factored_wind_kn=factored_wind,
            factored_seismic_kn=factored_seismic,
            total_factored_kn=total,
            is_uplift_case=is_uplift
        )
    
    def apply_all_combinations(
        self,
        dead_load_kn: float,
        live_load_kn: float = 0.0,
        wind_load_kn: float = 0.0,
        seismic_x_kn: float = 0.0,
        seismic_y_kn: float = 0.0,
        seismic_z_kn: float = 0.0
    ) -> List[CombinedLoadResult]:
        """Apply all combinations and return results."""
        results = []
        for combo in self.combinations:
            result = self.apply_combination(
                combo, dead_load_kn, live_load_kn, 
                wind_load_kn, seismic_x_kn, seismic_y_kn, seismic_z_kn
            )
            results.append(result)
        return results
    
    def get_governing_combination(
        self,
        dead_load_kn: float,
        live_load_kn: float = 0.0,
        wind_load_kn: float = 0.0,
        seismic_x_kn: float = 0.0,
        seismic_y_kn: float = 0.0,
        seismic_z_kn: float = 0.0
    ) -> Tuple[LoadCombination, CombinedLoadResult]:
        """Find the combination that produces maximum load."""
        results = self.apply_all_combinations(
            dead_load_kn, live_load_kn, 
            wind_load_kn, seismic_x_kn, seismic_y_kn, seismic_z_kn
        )
        
        max_result = max(results, key=lambda r: r.total_factored_kn)
        max_combo = next(
            c for c in self.combinations 
            if c.name == max_result.combination_name
        )
        
        return max_combo, max_result


def calculate_seismic_weight(
    dead_load_kn: float,
    live_load_kn: float,
    live_load_intensity_kn_m2: float
) -> SeismicWeightResult:
    """
    Calculate seismic weight per IS 1893 (Part 1): 2016.
    
    Seismic weight = Full DL + (Reduction Factor × LL)
    
    Reduction Factor:
    - 25% if live load intensity ≤ 3.0 kN/m²
    - 50% if live load intensity > 3.0 kN/m²
    
    Args:
        dead_load_kn: Total dead load in kN
        live_load_kn: Total live load in kN
        live_load_intensity_kn_m2: Live load per unit area (for determining factor)
        
    Returns:
        SeismicWeightResult with calculations
    """
    if live_load_intensity_kn_m2 <= 3.0:
        ll_factor = 0.25
    else:
        ll_factor = 0.50
    
    effective_ll = live_load_kn * ll_factor
    seismic_weight = dead_load_kn + effective_ll
    
    return SeismicWeightResult(
        total_dead_load_kn=dead_load_kn,
        total_live_load_kn=live_load_kn,
        live_load_intensity_kn_m2=live_load_intensity_kn_m2,
        ll_reduction_factor=ll_factor,
        effective_live_load_kn=effective_ll,
        seismic_weight_kn=seismic_weight,
        code_reference=f"IS 1893 Cl. 7.4.3: {int(ll_factor*100)}% LL for intensity "
                       f"{'≤' if live_load_intensity_kn_m2 <= 3.0 else '>'} 3.0 kN/m²"
    )


def check_uplift_stability(
    dead_load_kn: float,
    wind_load_kn: float = 0.0,
    seismic_load_kn: float = 0.0
) -> Tuple[bool, float, str]:
    """
    Check stability against uplift/overturning.
    
    Uses 0.9DL + 1.5(WL or EQ) combination.
    
    Args:
        dead_load_kn: Total dead load (resisting)
        wind_load_kn: Wind load (overturning)
        seismic_load_kn: Seismic load (overturning)
        
    Returns:
        (is_stable, factor_of_safety, message)
    """
    resisting = 0.9 * dead_load_kn
    overturning = 1.5 * max(wind_load_kn, seismic_load_kn)
    
    if overturning <= 0:
        return True, float('inf'), "No lateral load - stable"
    
    fos = resisting / overturning
    
    if fos >= 1.0:
        return True, fos, f"Stable: FoS = {fos:.2f} ≥ 1.0"
    else:
        return False, fos, f"UNSTABLE: FoS = {fos:.2f} < 1.0 - Foundation may uplift!"


def get_summary_report(
    manager: LoadCombinationManager,
    dead_load_kn: float,
    live_load_kn: float,
    wind_load_kn: float = 0.0,
    seismic_x_kn: float = 0.0
) -> str:
    """Generate a summary report of all load combinations."""
    lines = []
    lines.append("=" * 80)
    lines.append("LOAD COMBINATIONS SUMMARY (IS 456 Table 18 / IS 1893)")
    lines.append("=" * 80)
    
    lines.append(f"\nInput Loads:")
    lines.append(f"  Dead Load (DL): {dead_load_kn:.2f} kN")
    lines.append(f"  Live Load (LL): {live_load_kn:.2f} kN")
    lines.append(f"  Wind Load (WL): {wind_load_kn:.2f} kN")
    lines.append(f"  Seismic X (EQx): {seismic_x_kn:.2f} kN")
    
    lines.append(f"\n{'-' * 80}")
    lines.append(f"{'Combination':<25} {'Type':<15} {'Factored (kN)':<15} {'Critical?':<10}")
    lines.append(f"{'-' * 80}")
    
    results = manager.apply_all_combinations(
        dead_load_kn, live_load_kn, wind_load_kn, seismic_x_kn
    )
    
    for combo, result in zip(manager.combinations, results):
        critical = "⚠️ YES" if combo.is_critical else ""
        lines.append(
            f"{combo.name:<25} {combo.combination_type.value:<15} "
            f"{result.total_factored_kn:>12.2f}   {critical}"
        )
    
    max_combo, max_result = manager.get_governing_combination(
        dead_load_kn, live_load_kn, wind_load_kn, seismic_x_kn
    )
    
    lines.append(f"\n{'-' * 80}")
    lines.append(f"GOVERNING COMBINATION: {max_combo.name}")
    lines.append(f"Maximum Factored Load: {max_result.total_factored_kn:.2f} kN")
    
    is_stable, fos, msg = check_uplift_stability(dead_load_kn, wind_load_kn, seismic_x_kn)
    lines.append(f"\nUplift/Overturning Check: {msg}")
    
    lines.append("=" * 80)
    
    return "\n".join(lines)
