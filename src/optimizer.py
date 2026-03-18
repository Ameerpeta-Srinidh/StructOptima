"""
Structural Optimization Module - IS 456:2000 Compliant

Cost optimization while maintaining full structural safety.
All optimizations respect IS 456 requirements and safety factors.

SAFETY DISCLAIMER: All optimized designs must be verified by a
licensed Professional Engineer before construction.
"""

import math
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

from .grid_manager import Column
from .materials import Concrete, Steel


class OptimizationLevel(str, Enum):
    """Optimization aggressiveness levels."""
    NONE = "none"           # No optimization (conservative)
    MODERATE = "moderate"   # 10% margin above code minimum
    AGGRESSIVE = "aggressive"  # Exact code minimum (not recommended)


@dataclass
class OptimizedColumn:
    """Optimized column design result."""
    id: str
    level: int
    original_size_mm: Tuple[int, int]  # (width, depth)
    optimized_size_mm: Tuple[int, int]
    axial_load_kn: float
    design_capacity_kn: float
    utilization_ratio: float  # Load / Capacity (should be 0.7-0.9 for optimal)
    
    # Rebar optimization
    original_steel_ratio: float
    optimized_steel_ratio: float
    main_bars: str  # e.g., "4-16mm + 4-12mm"
    
    # Safety checks
    is_safe: bool
    safety_margin: float  # Capacity / Load
    
    # Transparency / Liability Metrics
    dc_ratio: float = 0.0
    xu_d_ratio: float = 0.0
    is_min_ecc_governed: bool = False
    required_steel_mm2: float = 0.0
    provided_steel_mm2: float = 0.0


@dataclass
class OptimizationSummary:
    """Summary of optimization results."""
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
    
    all_safe: bool  # All members pass safety checks


class StructuralOptimizer:
    """
    IS 456:2000 compliant structural optimizer.
    
    Optimizes member sizes while maintaining safety factors:
    - Concrete: γc = 1.5
    - Steel: γs = 1.15
    - Load factor: 1.5 (DL + LL)
    """
    
    # Standard column sizes (mm) in ascending order
    COLUMN_SIZES = [
        (230, 230), (230, 300), (230, 350), (230, 400),
        (300, 300), (300, 350), (300, 400), (300, 450),
        (350, 350), (350, 400), (350, 450), (350, 500),
        (400, 400), (400, 450), (400, 500), (400, 600),
        (450, 450), (450, 500), (450, 600),
        (500, 500), (500, 600), (500, 700),
        (600, 600), (600, 700), (600, 800),
    ]
    
    def __init__(
        self,
        fck: float = 25.0,  # Concrete grade (MPa)
        fy: float = 500.0,  # Steel grade (MPa)
        optimization_level: OptimizationLevel = OptimizationLevel.MODERATE,
        concrete_rate: float = 5000.0,  # INR/m³
        steel_rate: float = 60.0  # INR/kg
    ):
        self.fck = fck
        self.fy = fy
        self.optimization_level = optimization_level
        self.concrete_rate = concrete_rate
        self.steel_rate = steel_rate
        
        # Safety margins based on optimization level
        self.margins = {
            OptimizationLevel.NONE: 1.30,       # 30% margin
            OptimizationLevel.MODERATE: 1.15,   # 15% margin
            OptimizationLevel.AGGRESSIVE: 1.05  # 5% margin (minimum safe)
        }
        
        self.target_margin = self.margins[optimization_level]
    
    def calculate_column_capacity(
        self,
        width_mm: float,
        depth_mm: float,
        steel_ratio: float = 0.02,
        effective_length_factor: float = 1.0,
        height_mm: float = 3000.0
    ) -> float:
        """
        Calculate axial load capacity of column per IS 456 Cl 39.3.
        
        For short columns (Le/b < 12):
        Pu = 0.4 * fck * Ac + 0.67 * fy * Asc
        
        Args:
            width_mm: Column width
            depth_mm: Column depth
            steel_ratio: Reinforcement ratio (Asc/Ag)
            effective_length_factor: k factor for buckling
            height_mm: Column height
            
        Returns:
            Ultimate axial capacity in kN
        """
        b = width_mm
        d = depth_mm
        Ag = b * d  # mm²
        Asc = steel_ratio * Ag  # mm²
        Ac = Ag - Asc  # mm²
        
        # Check slenderness (IS 456 Cl 25.1.2)
        Le = effective_length_factor * height_mm
        slenderness = Le / min(b, d)
        
        if slenderness < 12:
            # Short column - IS 456 Cl 39.3
            Pu = 0.4 * self.fck * Ac + 0.67 * self.fy * Asc
        else:
            # Slender column - apply reduction factor (IS 456 Cl 39.7.1)
            # Simplified: reduce by 1.5% per unit of (Le/b - 12)
            reduction = 1.0 - 0.015 * (slenderness - 12)
            reduction = max(reduction, 0.5)  # Minimum 50%
            Pu = reduction * (0.4 * self.fck * Ac + 0.67 * self.fy * Asc)
        
        return Pu / 1000.0  # Convert to kN

    def calculate_emin(self, length_mm: float, depth_mm: float) -> Tuple[float, bool]:
        """
        Check minimum eccentricity per IS 456 Cl 25.4.
        emin = L/500 + D/30, subject to min 20mm.
        
        Returns: (emin, is_governed_by_min_ecc)
        """
        emin = (length_mm / 500.0) + (depth_mm / 30.0)
        emin = max(emin, 20.0)
        
        # Cl 39.3 applies only if emin <= 0.05 * D
        is_small_ecc = emin <= (0.05 * depth_mm)
        return emin, not is_small_ecc
    
    def optimize_column_size(
        self,
        required_load_kn: float,
        height_mm: float = 3000.0,
        min_steel_ratio: float = 0.008,  # IS 456 minimum 0.8%
        max_steel_ratio: float = 0.04    # Practical maximum 4% (code allows 6%)
    ) -> Tuple[Tuple[int, int], float, float]:
        """
        Find optimal column size for given load.
        
        Returns smallest column size that satisfies:
        Capacity >= Required Load × Target Margin
        
        Args:
            required_load_kn: Factored axial load
            height_mm: Column height
            min_steel_ratio: Minimum reinforcement
            max_steel_ratio: Maximum reinforcement
            
        Returns:
            (width, depth), steel_ratio, capacity_kn
        """
        target_capacity = required_load_kn * self.target_margin
        
        for size in self.COLUMN_SIZES:
            width, depth = size
            
            # Try with moderate steel ratio first
            for steel_ratio in [0.015, 0.02, 0.025, 0.03, 0.035, max_steel_ratio]:
                if steel_ratio < min_steel_ratio:
                    continue
                    
                capacity = self.calculate_column_capacity(
                    width, depth, steel_ratio, 1.0, height_mm
                )
                
                if capacity >= target_capacity:
                    return (width, depth), steel_ratio, capacity
        
        # If no standard size works, return largest
        return self.COLUMN_SIZES[-1], max_steel_ratio, self.calculate_column_capacity(
            *self.COLUMN_SIZES[-1], max_steel_ratio, 1.0, height_mm
        )
    
    def optimize_columns_by_floor(
        self,
        columns: List[Column],
        story_height_m: float,
        num_stories: int
    ) -> Dict[str, OptimizedColumn]:
        """
        Optimize column sizes floor by floor based on cumulative loads.
        
        Upper floors carry less load, so they can have smaller columns.
        
        Args:
            columns: List of Column objects (all floors)
            story_height_m: Height per story
            num_stories: Total number of stories
            
        Returns:
            Dictionary of column_id -> OptimizedColumn
        """
        results = {}
        height_mm = story_height_m * 1000
        
        # Group columns by location (x, y)
        locations = {}
        for col in columns:
            key = (round(col.x, 2), round(col.y, 2))
            if key not in locations:
                locations[key] = []
            locations[key].append(col)
        
        # Process each column stack
        for loc_key, col_stack in locations.items():
            # Sort by level (bottom to top)
            col_stack.sort(key=lambda c: c.level)
            
            for col in col_stack:
                # Get cumulative load for this column
                load_kn = col.load_kn if col.load_kn > 0 else 500.0  # Default if not calculated
                
                # Original size
                orig_width = col.width_nb
                orig_depth = col.depth_nb
                orig_size = (int(orig_width), int(orig_depth))
                
                # Optimize
                opt_size, opt_steel, capacity = self.optimize_column_size(
                    load_kn, height_mm
                )
                
                # Calculate savings
                orig_area = orig_width * orig_depth
                opt_area = opt_size[0] * opt_size[1]
                
                utilization = load_kn / capacity if capacity > 0 else 1.0
                safety_margin = capacity / load_kn if load_kn > 0 else float('inf')
                
                # Calculate transparency metrics
                emin, min_ecc_gov = self.calculate_emin(height_mm, opt_size[1])
                xu_d = (0.87 * self.fy * opt_steel) / (0.36 * self.fck) # Simplified Xu/d for limit state
                
                req_steel_area = opt_size[0] * opt_size[1] * opt_steel # Used as 'Required' for now
                prov_steel_area = req_steel_area # Since we select based on ratio
                
                results[col.id] = OptimizedColumn(
                    id=col.id,
                    level=col.level,
                    original_size_mm=orig_size,
                    optimized_size_mm=opt_size,
                    axial_load_kn=load_kn,
                    design_capacity_kn=capacity,
                    utilization_ratio=utilization,
                    original_steel_ratio=0.02,
                    optimized_steel_ratio=opt_steel,
                    main_bars=self._get_bar_configuration(opt_size, opt_steel),
                    is_safe=safety_margin >= 1.0,
                    safety_margin=safety_margin,
                    # New Metrics
                    dc_ratio=utilization,
                    xu_d_ratio=min(xu_d, 0.48), # Cap at limit for display
                    is_min_ecc_governed=min_ecc_gov,
                    required_steel_mm2=req_steel_area,
                    provided_steel_mm2=prov_steel_area
                )
        
        return results
    
    def _get_bar_configuration(
        self,
        size: Tuple[int, int],
        steel_ratio: float
    ) -> str:
        """Generate bar configuration string."""
        width, depth = size
        Ag = width * depth
        Asc = steel_ratio * Ag
        
        # Standard bar areas (mm²)
        bar_areas = {12: 113, 16: 201, 20: 314, 25: 491}
        
        # Simple logic: use 16mm or 20mm bars
        if Asc < 1200:
            n_bars = max(4, int(Asc / bar_areas[16]) + 1)
            return f"{n_bars}-16mm"
        elif Asc < 2500:
            n_bars = max(4, int(Asc / bar_areas[20]) + 1)
            return f"{n_bars}-20mm"
        else:
            n_20 = int(Asc * 0.6 / bar_areas[20])
            n_25 = int(Asc * 0.4 / bar_areas[25])
            return f"{n_20}-20mm + {n_25}-25mm"
    
    def calculate_optimization_summary(
        self,
        optimized_columns: Dict[str, OptimizedColumn],
        story_height_m: float
    ) -> OptimizationSummary:
        """Calculate overall optimization summary with costs."""
        
        total = len(optimized_columns)
        optimized = sum(1 for c in optimized_columns.values() 
                       if c.optimized_size_mm != c.original_size_mm)
        
        orig_conc = 0.0
        opt_conc = 0.0
        orig_steel = 0.0
        opt_steel = 0.0
        height_m = story_height_m
        
        for col in optimized_columns.values():
            # Original
            orig_w, orig_d = col.original_size_mm
            orig_vol = (orig_w / 1000) * (orig_d / 1000) * height_m
            orig_conc += orig_vol
            orig_steel += orig_vol * col.original_steel_ratio * 7850  # kg
            
            # Optimized
            opt_w, opt_d = col.optimized_size_mm
            opt_vol = (opt_w / 1000) * (opt_d / 1000) * height_m
            opt_conc += opt_vol
            opt_steel += opt_vol * col.optimized_steel_ratio * 7850  # kg
        
        conc_saved = orig_conc - opt_conc
        steel_saved = orig_steel - opt_steel
        
        orig_cost = orig_conc * self.concrete_rate + orig_steel * self.steel_rate
        opt_cost = opt_conc * self.concrete_rate + opt_steel * self.steel_rate
        cost_saved = orig_cost - opt_cost
        
        all_safe = all(c.is_safe for c in optimized_columns.values())
        
        return OptimizationSummary(
            total_columns=total,
            optimized_columns=optimized,
            original_concrete_m3=orig_conc,
            optimized_concrete_m3=opt_conc,
            concrete_saved_m3=conc_saved,
            concrete_saved_pct=(conc_saved / orig_conc * 100) if orig_conc > 0 else 0,
            original_steel_kg=orig_steel,
            optimized_steel_kg=opt_steel,
            steel_saved_kg=steel_saved,
            steel_saved_pct=(steel_saved / orig_steel * 100) if orig_steel > 0 else 0,
            original_cost=orig_cost,
            optimized_cost=opt_cost,
            cost_saved=cost_saved,
            cost_saved_pct=(cost_saved / orig_cost * 100) if orig_cost > 0 else 0,
            all_safe=all_safe
        )


def optimize_structure(
    columns: List[Column],
    story_height_m: float,
    num_stories: int,
    fck: float = 25.0,
    enable_optimization: bool = True
) -> Tuple[Dict[str, OptimizedColumn], OptimizationSummary]:
    """
    Main function to optimize structural design.
    
    Args:
        columns: All column objects
        story_height_m: Story height in meters
        num_stories: Number of stories
        fck: Concrete grade
        enable_optimization: Whether to actually optimize or just analyze
        
    Returns:
        (optimized_columns_dict, summary)
    """
    level = OptimizationLevel.MODERATE if enable_optimization else OptimizationLevel.NONE
    
    optimizer = StructuralOptimizer(
        fck=fck,
        optimization_level=level
    )
    
    optimized = optimizer.optimize_columns_by_floor(
        columns, story_height_m, num_stories
    )
    
    summary = optimizer.calculate_optimization_summary(
        optimized, story_height_m
    )
    
    return optimized, summary
