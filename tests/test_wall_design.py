"""
Tests for Wall Design Calculations & 3D Wall Visualization
============================================================
Tests cover:
  - Wall volume formula: Vw = L x t x Hv
  - Brick count: Nb = Vw / 0.004 = 250 x Vw
  - Wet mortar: Vm,wet = Vw - Vbrick
  - Dry mortar: Vm,dry = Vm,wet x 1.33
  - Cement bags, sand tonnes, water (W:C = 0.50)
  - Plastering (12mm int 1:6, 15mm ext 1:4)
  - Paint (primer 1 coat, putty 2 coats, emulsion 2 coats)
  - Wall generation in GridManager
  - 3D GeometryExporter show_walls toggle
  - Quantifier BOM wall integration
"""

import math
import pytest
from src.grid_manager import GridManager, Wall
from src.wall_calculator import WallCalculator, WallBOM, WallSectionResult
from src.quantifier import Quantifier
from src.geometry_exporter import GeometryExporter
from src.framing_logic import StructuralMember, Point, MemberProperties


class TestWallCalculatorFormulas:
    """Tests all exact formulas specified for wall design."""

    def test_wall_geometry_and_volume(self):
        calc = WallCalculator(mortar_ratio=4, wc_ratio=0.50)
        # 5m wall, 0.20m (200mm) thickness, 2.975m clear height (3.5 - 0.125 - 0.40)
        sec = calc.calculate_wall_section(
            wall_id="W1",
            length_m=5.0,
            clear_height_m=3.0,
            core_thickness_m=0.20,
            is_exterior=True,
        )
        # Vw = 5.0 * 0.20 * 3.0 = 3.0 m3
        assert sec.wall_volume_m3 == pytest.approx(3.0, rel=1e-4)

    def test_brick_quantity(self):
        calc = WallCalculator(mortar_ratio=4, wc_ratio=0.50)
        sec = calc.calculate_wall_section(
            wall_id="W1",
            length_m=5.0,
            clear_height_m=3.0,
            core_thickness_m=0.20,
            is_exterior=True,
        )
        # Nb = 250 * 3.0 = 750 bricks
        assert sec.num_bricks == 750
        # Solid brick volume = 750 * (0.19 * 0.19 * 0.09) = 2.43675 m3
        assert sec.total_brick_vol_m3 == pytest.approx(750 * 0.19 * 0.19 * 0.09, rel=1e-4)

    def test_mortar_quantities(self):
        calc = WallCalculator(mortar_ratio=4, wc_ratio=0.50)
        sec = calc.calculate_wall_section(
            wall_id="W1",
            length_m=5.0,
            clear_height_m=3.0,
            core_thickness_m=0.20,
            is_exterior=True,
        )
        # Wet mortar = 3.0 - (750 * 0.003249) = 3.0 - 2.43675 = 0.56325 m3
        expected_wet = 3.0 - (750 * 0.19 * 0.19 * 0.09)
        assert sec.wet_mortar_vol_m3 == pytest.approx(expected_wet, rel=1e-4)

        # Dry mortar = Wet mortar * 1.33
        expected_dry = expected_wet * 1.33
        assert sec.dry_mortar_vol_m3 == pytest.approx(expected_dry, rel=1e-4)

        # Cement (1:4 ratio -> 1/5 parts)
        expected_cement_vol = expected_dry / 5.0
        expected_cement_kg = expected_cement_vol * 1440.0
        assert sec.mortar_cement_kg == pytest.approx(expected_cement_kg, rel=1e-3)
        assert sec.mortar_cement_bags == int(math.ceil(expected_cement_kg / 50.0))

        # Sand (4/5 parts)
        expected_sand_vol = expected_dry * 4.0 / 5.0
        expected_sand_kg = expected_sand_vol * 1600.0
        assert sec.mortar_sand_tonnes == pytest.approx(expected_sand_kg / 1000.0, rel=1e-3)

        # Water = 0.50 * Cement weight
        assert sec.mortar_water_litres == pytest.approx(0.50 * expected_cement_kg, rel=1e-3)

    def test_plastering_internal_and_external(self):
        calc = WallCalculator(mortar_ratio=4, wc_ratio=0.50)
        # Exterior wall: 15mm outside (1:4), 12mm inside (1:6)
        sec_ext = calc.calculate_wall_section(
            wall_id="W_EXT",
            length_m=4.0,
            clear_height_m=3.0,
            core_thickness_m=0.20,
            is_exterior=True,
        )
        # Plaster area both sides = 2 * (4 * 3) = 24 m2
        assert sec_ext.plaster_area_m2 == pytest.approx(24.0, rel=1e-4)
        assert sec_ext.plaster_cement_bags > 0
        assert sec_ext.plaster_sand_tonnes > 0
        assert sec_ext.plaster_water_litres == pytest.approx(0.50 * sec_ext.plaster_cement_kg, rel=1e-3)

        # Interior partition wall: 12mm both sides (1:6)
        sec_int = calc.calculate_wall_section(
            wall_id="W_INT",
            length_m=4.0,
            clear_height_m=3.0,
            core_thickness_m=0.10,
            is_exterior=False,
        )
        assert sec_int.plaster_area_m2 == pytest.approx(24.0, rel=1e-4)
        assert sec_int.plaster_vol_m3 == pytest.approx(24.0 * 0.012, rel=1e-4)

    def test_paint_coatings(self):
        calc = WallCalculator(mortar_ratio=4)
        sec = calc.calculate_wall_section(
            wall_id="W1",
            length_m=5.0,
            clear_height_m=3.0,
            core_thickness_m=0.20,
            is_exterior=True,
        )
        # Area = 30 m2 total (15 m2 int, 15 m2 ext)
        assert sec.paint_area_m2 == 30.0
        assert sec.primer_litres > 0
        assert sec.putty_kg > 0
        assert sec.emulsion_int_litres > 0
        assert sec.emulsion_ext_litres > 0


class TestGridManagerWallGeneration:
    """Tests wall generation within GridManager."""

    def test_generate_walls_perimeter(self):
        gm = GridManager(width_m=12.0, length_m=12.0, num_stories=2, story_height_m=3.0)
        gm.generate_grid()
        gm.generate_walls(wall_thickness_mm=200.0, opening_fraction=0.33, include_interior=False)

        assert len(gm.walls) > 0
        # Perimeter walls only -> all walls should have is_exterior = True
        assert all(w.is_exterior for w in gm.walls)
        # Wall clear height should be story_height - slab - beam
        expected_clear_h = 3.0 - (125.0 / 1000.0) - (400.0 / 1000.0)
        for w in gm.walls:
            assert w.height_m == pytest.approx(expected_clear_h, rel=1e-3)
            assert w.thickness_mm == 200.0

    def test_generate_walls_with_interior(self):
        gm = GridManager(width_m=12.0, length_m=12.0, num_stories=1, story_height_m=3.0)
        gm.generate_grid()
        gm.generate_walls(wall_thickness_mm=100.0, include_interior=True)

        assert len(gm.walls) > 0
        # Should have both exterior and interior walls
        exterior_walls = [w for w in gm.walls if w.is_exterior]
        interior_walls = [w for w in gm.walls if not w.is_exterior]
        assert len(exterior_walls) > 0
        assert len(interior_walls) > 0


class TestGeometryExporterWallToggle:
    """Tests 3D scene construction and show_walls toggle."""

    def test_3d_scene_show_walls_toggle(self):
        gm = GridManager(width_m=12.0, length_m=12.0, num_stories=2, story_height_m=3.0)
        gm.generate_grid()
        beams = gm.generate_beams()
        gm.generate_walls(wall_thickness_mm=200.0)

        # Scene with walls
        scene_with = GeometryExporter.create_structure_scene(gm, beams, [], show_walls=True)
        glb_with = GeometryExporter.export_to_glb_base64(scene_with)
        assert len(glb_with) > 0

        # Scene without walls
        scene_without = GeometryExporter.create_structure_scene(gm, beams, [], show_walls=False)
        glb_without = GeometryExporter.export_to_glb_base64(scene_without)
        assert len(glb_without) > 0

        # Scene with walls has more geometries/bytes than scene without
        assert len(glb_with) > len(glb_without)


class TestQuantifierWallBOMIntegration:
    """Tests BOM calculation with WallCalculator integration."""

    def test_bom_contains_wall_quantities(self):
        gm = GridManager(width_m=12.0, length_m=12.0, num_stories=2, story_height_m=3.0)
        gm.generate_grid()
        beams = gm.generate_beams()
        gm.generate_walls(wall_thickness_mm=200.0)

        q = Quantifier()
        bom = q.calculate_bom(gm.columns, beams, [], grid_mgr=gm)

        assert bom.brick_count > 0
        assert bom.total_bricks > 0
        assert bom.total_mortar_cement_bags > 0
        assert bom.total_mortar_sand_tonnes > 0
        assert bom.total_plaster_cement_bags > 0
        assert bom.total_plaster_sand_tonnes > 0
        assert bom.total_primer_litres > 0
        assert bom.wall_bom is not None
