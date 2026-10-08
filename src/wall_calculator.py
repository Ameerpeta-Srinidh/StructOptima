"""
Wall Design Calculations Module — StructOptima
================================================
Complete masonry wall quantity estimation per Indian construction standards.

Brick size (IS 1077:1992):
  Without mortar: 190 x 190 x 90 mm (traditional mud brick)
  With mortar:    200 x 200 x 100 mm (modular brick)

References:
  - IS 1077:1992  — Common Burnt Clay Building Bricks
  - IS 2250:1981  — Masonry Mortar Mix Proportions
  - IS 1905:1987  — Structural Use of Unreinforced Masonry
  - IS 875 Part 1 — Dead Loads (unit weights)
  - IS 2402:1963  — Code of Practice for External Rendered Finishes
  - IS 1661:1972  — Code of Practice for Application of Cement Plaster
  - NBC 2016 SP7  — National Building Code
"""

from __future__ import annotations
import math
from typing import List, Dict, Optional, Literal
from pydantic import BaseModel


# ---------------------------------------------------------------------------
#  Constants
# ---------------------------------------------------------------------------

# Brick dimensions (m) — IS 1077 modular brick
BRICK_WITHOUT_MORTAR = (0.19, 0.19, 0.09)   # L x W x H in metres
BRICK_WITH_MORTAR    = (0.20, 0.20, 0.10)   # L x W x H with 10mm mortar joint

BRICK_VOL_WITHOUT_MORTAR = BRICK_WITHOUT_MORTAR[0] * BRICK_WITHOUT_MORTAR[1] * BRICK_WITHOUT_MORTAR[2]  # 0.003249 m3
BRICK_VOL_WITH_MORTAR    = BRICK_WITH_MORTAR[0] * BRICK_WITH_MORTAR[1] * BRICK_WITH_MORTAR[2]          # 0.004000 m3

BRICKS_PER_M3 = 1.0 / BRICK_VOL_WITH_MORTAR  # = 250

# Material densities
CEMENT_DENSITY_KG_M3 = 1440.0   # Bulk density of cement
SAND_DENSITY_KG_M3   = 1600.0   # Bulk density of dry sand
WATER_DENSITY_KG_M3  = 1000.0

# Wet-to-dry conversion factor (IS 2250 standard practice)
WET_TO_DRY_FACTOR = 1.33

# Water-to-cement ratio for mortar (standard practice)
WC_RATIO_MORTAR = 0.50

# Cement bag weight
CEMENT_BAG_KG = 50.0

# Paint coverage rates (industry standard, m2/litre)
PRIMER_COVERAGE_M2_PER_L  = 8.0    # ~25-40 microns per coat
PUTTY_COVERAGE_KG_PER_M2  = 1.5    # ~1-2 mm total (2 coats)
EMULSION_INT_COVERAGE_M2_PER_L = 12.0  # Interior emulsion, 30-40 microns/coat
EMULSION_EXT_COVERAGE_M2_PER_L = 10.0  # Exterior emulsion, 40-60 microns/coat

# Plaster thickness (m)
PLASTER_INTERNAL_M = 0.012   # 12 mm
PLASTER_EXTERNAL_M = 0.015   # 15 mm

# Plaster mortar ratios
PLASTER_INTERNAL_RATIO = 6   # 1:6
PLASTER_EXTERNAL_RATIO = 4   # 1:4

# Paint coats
PRIMER_COATS = 1
PUTTY_COATS = 2
EMULSION_COATS = 2


# ---------------------------------------------------------------------------
#  Data Models
# ---------------------------------------------------------------------------

class WallSectionResult(BaseModel):
    """Per-wall-section calculation result."""
    wall_id: str
    col_start: str = ""
    col_end: str = ""
    length_m: float
    clear_height_m: float
    core_thickness_m: float   # 0.200 or 0.100
    is_exterior: bool = True

    # Volume
    wall_volume_m3: float = 0.0

    # Bricks
    num_bricks: int = 0
    total_brick_vol_m3: float = 0.0  # actual brick volume (without mortar joints)

    # Mortar
    wet_mortar_vol_m3: float = 0.0
    dry_mortar_vol_m3: float = 0.0
    mortar_cement_vol_m3: float = 0.0
    mortar_cement_kg: float = 0.0
    mortar_cement_bags: int = 0
    mortar_sand_vol_m3: float = 0.0
    mortar_sand_kg: float = 0.0
    mortar_sand_tonnes: float = 0.0
    mortar_water_litres: float = 0.0

    # Plastering
    plaster_area_m2: float = 0.0        # both sides
    plaster_vol_m3: float = 0.0
    plaster_dry_mortar_m3: float = 0.0
    plaster_cement_kg: float = 0.0
    plaster_cement_bags: int = 0
    plaster_sand_kg: float = 0.0
    plaster_sand_tonnes: float = 0.0
    plaster_water_litres: float = 0.0

    # Paint
    paint_area_m2: float = 0.0          # both sides
    primer_litres: float = 0.0
    putty_kg: float = 0.0
    emulsion_int_litres: float = 0.0
    emulsion_ext_litres: float = 0.0


class WallBOM(BaseModel):
    """Aggregated wall material takeoff for the entire building."""
    wall_sections: List[WallSectionResult] = []
    num_stories: int = 1

    # Totals (all stories combined)
    total_wall_volume_m3: float = 0.0
    total_bricks: int = 0

    # Brickwork mortar
    total_mortar_cement_bags: int = 0
    total_mortar_cement_kg: float = 0.0
    total_mortar_sand_tonnes: float = 0.0
    total_mortar_water_litres: float = 0.0

    # Plastering
    total_plaster_area_m2: float = 0.0
    total_plaster_cement_bags: int = 0
    total_plaster_cement_kg: float = 0.0
    total_plaster_sand_tonnes: float = 0.0
    total_plaster_water_litres: float = 0.0

    # Paint
    total_primer_litres: float = 0.0
    total_putty_kg: float = 0.0
    total_emulsion_int_litres: float = 0.0
    total_emulsion_ext_litres: float = 0.0

    # Costs (approximate DSR rates)
    brickwork_cost_inr: float = 0.0
    plaster_cost_inr: float = 0.0
    paint_cost_inr: float = 0.0
    total_wall_cost_inr: float = 0.0


# ---------------------------------------------------------------------------
#  Calculator
# ---------------------------------------------------------------------------

class WallCalculator:
    """Computes brick, mortar, plastering and paint quantities for masonry walls."""

    def __init__(
        self,
        mortar_ratio: int = 4,       # Cement:Sand = 1:ratio (default 1:4)
        wc_ratio: float = 0.50,
        opening_fraction: float = 0.33,
    ):
        self.mortar_ratio = mortar_ratio
        self.wc_ratio = wc_ratio
        self.opening_fraction = opening_fraction

    # ----- Per-wall calculation -----

    def calculate_wall_section(
        self,
        wall_id: str,
        length_m: float,
        clear_height_m: float,
        core_thickness_m: float,
        is_exterior: bool = True,
        col_start: str = "",
        col_end: str = "",
    ) -> WallSectionResult:
        """Calculate all quantities for a single wall section.

        Args:
            length_m: Distance between two columns (m).
            clear_height_m: Hv = Hf - ts - Db (m).
            core_thickness_m: Core brick thickness (0.200 or 0.100 m).
            is_exterior: True for external walls (thicker plaster, exterior paint).
        """

        res = WallSectionResult(
            wall_id=wall_id,
            col_start=col_start,
            col_end=col_end,
            length_m=length_m,
            clear_height_m=clear_height_m,
            core_thickness_m=core_thickness_m,
            is_exterior=is_exterior,
        )

        # ===== 1. WALL VOLUME =====
        # V_wall = L x t x Hv
        res.wall_volume_m3 = length_m * core_thickness_m * clear_height_m

        # ===== 2. BRICK QUANTITY =====
        # Number of bricks = Wall volume / Volume of each brick with mortar
        # = Wall volume / 0.004 = 250 * Wall volume
        res.num_bricks = int(math.ceil(res.wall_volume_m3 * BRICKS_PER_M3))

        # Total volume of bricks used (without mortar)
        res.total_brick_vol_m3 = res.num_bricks * BRICK_VOL_WITHOUT_MORTAR

        # ===== 3. MORTAR =====
        # Wet mortar = Wall volume - brick volume (without mortar)
        res.wet_mortar_vol_m3 = max(0.0, res.wall_volume_m3 - res.total_brick_vol_m3)

        # Dry mortar = Wet mortar x 1.33
        res.dry_mortar_vol_m3 = res.wet_mortar_vol_m3 * WET_TO_DRY_FACTOR

        # Cement: Sand = 1 : mortar_ratio => total parts = 1 + mortar_ratio
        total_parts = 1 + self.mortar_ratio

        # Cement
        res.mortar_cement_vol_m3 = res.dry_mortar_vol_m3 / total_parts
        res.mortar_cement_kg = res.mortar_cement_vol_m3 * CEMENT_DENSITY_KG_M3
        res.mortar_cement_bags = int(math.ceil(res.mortar_cement_kg / CEMENT_BAG_KG))

        # Sand
        res.mortar_sand_vol_m3 = res.dry_mortar_vol_m3 * self.mortar_ratio / total_parts
        res.mortar_sand_kg = res.mortar_sand_vol_m3 * SAND_DENSITY_KG_M3
        res.mortar_sand_tonnes = res.mortar_sand_kg / 1000.0

        # Water (W:C = 0.50)
        res.mortar_water_litres = self.wc_ratio * res.mortar_cement_kg

        # ===== 4. PLASTERING (both sides) =====
        plaster_area_one_side = length_m * clear_height_m
        res.plaster_area_m2 = plaster_area_one_side * 2.0  # both sides
        res.paint_area_m2 = res.plaster_area_m2  # paint covers same area

        # Plaster volume & mortar
        if is_exterior:
            # External side: 15mm, 1:4
            ext_vol = plaster_area_one_side * PLASTER_EXTERNAL_M
            ext_dry = ext_vol * WET_TO_DRY_FACTOR
            ext_parts = 1 + PLASTER_EXTERNAL_RATIO
            ext_cement_kg = (ext_dry / ext_parts) * CEMENT_DENSITY_KG_M3
            ext_sand_kg = (ext_dry * PLASTER_EXTERNAL_RATIO / ext_parts) * SAND_DENSITY_KG_M3

            # Internal side: 12mm, 1:6
            int_vol = plaster_area_one_side * PLASTER_INTERNAL_M
            int_dry = int_vol * WET_TO_DRY_FACTOR
            int_parts = 1 + PLASTER_INTERNAL_RATIO
            int_cement_kg = (int_dry / int_parts) * CEMENT_DENSITY_KG_M3
            int_sand_kg = (int_dry * PLASTER_INTERNAL_RATIO / int_parts) * SAND_DENSITY_KG_M3

            res.plaster_vol_m3 = ext_vol + int_vol
            res.plaster_dry_mortar_m3 = ext_dry + int_dry
            res.plaster_cement_kg = ext_cement_kg + int_cement_kg
            res.plaster_sand_kg = ext_sand_kg + int_sand_kg
        else:
            # Both sides internal: 12mm, 1:6
            total_vol = res.plaster_area_m2 * PLASTER_INTERNAL_M
            total_dry = total_vol * WET_TO_DRY_FACTOR
            total_parts = 1 + PLASTER_INTERNAL_RATIO
            res.plaster_vol_m3 = total_vol
            res.plaster_dry_mortar_m3 = total_dry
            res.plaster_cement_kg = (total_dry / total_parts) * CEMENT_DENSITY_KG_M3
            res.plaster_sand_kg = (total_dry * PLASTER_INTERNAL_RATIO / total_parts) * SAND_DENSITY_KG_M3

        res.plaster_cement_bags = int(math.ceil(res.plaster_cement_kg / CEMENT_BAG_KG))
        res.plaster_sand_tonnes = res.plaster_sand_kg / 1000.0
        res.plaster_water_litres = self.wc_ratio * res.plaster_cement_kg

        # ===== 5. PAINT =====
        if is_exterior:
            # Internal side: primer + putty + interior emulsion
            int_paint_area = plaster_area_one_side
            # External side: primer + exterior emulsion (no putty on exterior)
            ext_paint_area = plaster_area_one_side

            res.primer_litres = (
                (int_paint_area * PRIMER_COATS / PRIMER_COVERAGE_M2_PER_L) +
                (ext_paint_area * PRIMER_COATS / PRIMER_COVERAGE_M2_PER_L)
            )
            res.putty_kg = int_paint_area * PUTTY_COVERAGE_KG_PER_M2 * PUTTY_COATS
            res.emulsion_int_litres = int_paint_area * EMULSION_COATS / EMULSION_INT_COVERAGE_M2_PER_L
            res.emulsion_ext_litres = ext_paint_area * EMULSION_COATS / EMULSION_EXT_COVERAGE_M2_PER_L
        else:
            # Both sides interior
            res.primer_litres = res.paint_area_m2 * PRIMER_COATS / PRIMER_COVERAGE_M2_PER_L
            res.putty_kg = res.paint_area_m2 * PUTTY_COVERAGE_KG_PER_M2 * PUTTY_COATS
            res.emulsion_int_litres = res.paint_area_m2 * EMULSION_COATS / EMULSION_INT_COVERAGE_M2_PER_L
            res.emulsion_ext_litres = 0.0

        return res

    # ----- Whole-building calculation -----

    def calculate_all(
        self,
        walls: list,
        num_stories: int = 1,
        floor_height_m: float = 3.5,
        slab_thickness_mm: float = 125.0,
        beam_depth_mm: float = 400.0,
    ) -> WallBOM:
        """Calculate wall quantities for the entire building.

        Args:
            walls: List of Wall objects from grid_manager.
            num_stories: Number of floors.
            floor_height_m: Story height.
            slab_thickness_mm: Slab thickness.
            beam_depth_mm: Beam depth.

        Returns:
            WallBOM with per-section and aggregated quantities.
        """
        # Clear wall height: Hv = Hf - ts - Db
        clear_height = floor_height_m - (slab_thickness_mm / 1000.0) - (beam_depth_mm / 1000.0)
        clear_height = max(clear_height, 0.5)  # Safety minimum

        sections: List[WallSectionResult] = []

        for w in walls:
            length = getattr(w, 'length_m', 0.0)
            if length < 0.1:
                continue

            core_t = getattr(w, 'thickness_mm', 200.0) / 1000.0
            is_ext = getattr(w, 'is_exterior', True)
            col_start_id = getattr(w, 'col_start_id', "")
            col_end_id = getattr(w, 'col_end_id', "")

            sec = self.calculate_wall_section(
                wall_id=w.id,
                length_m=length,
                clear_height_m=clear_height,
                core_thickness_m=core_t,
                is_exterior=is_ext,
                col_start=col_start_id,
                col_end=col_end_id,
            )
            sections.append(sec)

        # Aggregate — multiply by num_stories for totals
        bom = WallBOM(
            wall_sections=sections,
            num_stories=num_stories,
        )

        for sec in sections:
            bom.total_wall_volume_m3   += sec.wall_volume_m3 * num_stories
            bom.total_bricks           += sec.num_bricks * num_stories

            bom.total_mortar_cement_kg     += sec.mortar_cement_kg * num_stories
            bom.total_mortar_sand_tonnes   += sec.mortar_sand_tonnes * num_stories
            bom.total_mortar_water_litres  += sec.mortar_water_litres * num_stories

            bom.total_plaster_area_m2      += sec.plaster_area_m2 * num_stories
            bom.total_plaster_cement_kg    += sec.plaster_cement_kg * num_stories
            bom.total_plaster_sand_tonnes  += sec.plaster_sand_tonnes * num_stories
            bom.total_plaster_water_litres += sec.plaster_water_litres * num_stories

            bom.total_primer_litres        += sec.primer_litres * num_stories
            bom.total_putty_kg             += sec.putty_kg * num_stories
            bom.total_emulsion_int_litres  += sec.emulsion_int_litres * num_stories
            bom.total_emulsion_ext_litres  += sec.emulsion_ext_litres * num_stories

        # Cement bags (whole numbers)
        bom.total_mortar_cement_bags = int(math.ceil(bom.total_mortar_cement_kg / CEMENT_BAG_KG))
        bom.total_plaster_cement_bags = int(math.ceil(bom.total_plaster_cement_kg / CEMENT_BAG_KG))

        # Approximate costs (DSR 2023 approximate rates)
        # Brickwork: ~8000 INR/m3 (including labour)
        bom.brickwork_cost_inr = bom.total_wall_volume_m3 * 8000.0
        # Plastering: ~35 INR/m2 (materials) + ~25 INR/m2 (labour)
        bom.plaster_cost_inr = bom.total_plaster_area_m2 * 60.0
        # Painting: ~40 INR/m2 (primer+putty+emulsion+labour)
        bom.paint_cost_inr = (bom.total_plaster_area_m2) * 40.0

        bom.total_wall_cost_inr = bom.brickwork_cost_inr + bom.plaster_cost_inr + bom.paint_cost_inr

        return bom
