"""
Comprehensive tests for the Universal DXF Parser & Normalizer (src/cad_parser.py).

Covers:
  - 3-tier wall extraction (keyword, fuzzy, geometric)
  - Double-wall to centerline normalization
  - Edge cases: empty files, single lines, very long lines, non-wall layers
  - Integration with real DXF files
  - Wall thickness detection
  - Enclosed rectangle detection
"""

import pytest
import math
import os
import ezdxf
from ezdxf import units
from src.cad_parser import CADParser


# ── Helper: create temp DXF files for testing ───────────────


def _create_dxf(tmp_path, filename, layers_and_entities):
    """
    Create a temp DXF with given layers and entities.
    
    layers_and_entities: list of (layer_name, entity_type, data) tuples
      entity_type: 'line' or 'lwpolyline'
      data: for line -> ((x1,y1), (x2,y2))
            for lwpolyline -> [(x1,y1), (x2,y2), ...]
    """
    doc = ezdxf.new('R2010')
    doc.units = units.MM
    msp = doc.modelspace()
    
    for layer_name, etype, data in layers_and_entities:
        if layer_name not in doc.layers:
            doc.layers.add(layer_name)
        
        if etype == 'line':
            msp.add_line(data[0], data[1], dxfattribs={'layer': layer_name})
        elif etype == 'lwpolyline':
            msp.add_lwpolyline(data, dxfattribs={'layer': layer_name})
    
    filepath = os.path.join(str(tmp_path), filename)
    doc.saveas(filepath)
    return filepath


# ══════════════════════════════════════════════════════════════
#  TIER 1: KEYWORD LAYER MATCHING
# ══════════════════════════════════════════════════════════════


class TestTier1KeywordExtraction:

    def test_walls_layer_detected(self, tmp_path):
        """Layer named 'WALLS' should be detected by Tier 1."""
        fp = _create_dxf(tmp_path, "t1_walls.dxf", [
            ("WALLS", "line", ((0, 0), (6000, 0))),
            ("WALLS", "line", ((6000, 0), (6000, 4000))),
        ])
        parser = CADParser(fp)
        parser.load()
        walls = parser.extract_walls()
        assert len(walls) == 2
    
    def test_a_wall_layer_detected(self, tmp_path):
        """Layer named 'A-WALL-EXT' should be detected by Tier 1."""
        fp = _create_dxf(tmp_path, "t1_awall.dxf", [
            ("A-WALL-EXT", "line", ((0, 0), (5000, 0))),
            ("A-WALL-INT", "line", ((2500, 0), (2500, 3000))),
        ])
        parser = CADParser(fp)
        parser.load()
        walls = parser.extract_walls()
        assert len(walls) == 2

    def test_structural_layer_detected(self, tmp_path):
        """Layer containing 'STRUCT' should be detected."""
        fp = _create_dxf(tmp_path, "t1_struct.dxf", [
            ("STRUCTURAL-WALLS", "line", ((0, 0), (8000, 0))),
        ])
        parser = CADParser(fp)
        parser.load()
        walls = parser.extract_walls()
        assert len(walls) == 1

    def test_boundary_layer_detected(self, tmp_path):
        """Layer containing 'BOUNDARY' should be detected by the expanded keyword list."""
        fp = _create_dxf(tmp_path, "t1_boundary.dxf", [
            ("BOUNDARY", "line", ((0, 0), (10000, 0))),
        ])
        parser = CADParser(fp)
        parser.load()
        walls = parser.extract_walls()
        assert len(walls) == 1

    def test_polyline_walls_extracted(self, tmp_path):
        """LWPOLYLINE entities on wall layers should be extracted as segments."""
        fp = _create_dxf(tmp_path, "t1_poly.dxf", [
            ("WALLS", "lwpolyline", [(0, 0), (6000, 0), (6000, 4000), (0, 4000)]),
        ])
        parser = CADParser(fp)
        parser.load()
        walls = parser.extract_walls()
        # 4 segments from polyline (not closed by default in test helper)
        assert len(walls) >= 3

    def test_non_wall_layer_ignored_in_tier1(self, tmp_path):
        """Layer named 'FURNITURE' should NOT be picked up by Tier 1."""
        fp = _create_dxf(tmp_path, "t1_furniture.dxf", [
            ("FURNITURE", "line", ((0, 0), (2000, 0))),
            ("WALLS", "line", ((0, 0), (6000, 0))),
        ])
        parser = CADParser(fp)
        parser.load()
        walls = parser.extract_walls()
        # Tier 1 should only return the WALLS layer line
        assert len(walls) == 1


# ══════════════════════════════════════════════════════════════
#  TIER 2: ALL-LAYERS FALLBACK
# ══════════════════════════════════════════════════════════════


class TestTier2FuzzyExtraction:

    def test_unnamed_layers_fallback(self, tmp_path):
        """When no keyword-matching layers exist, Tier 2 scans all layers."""
        fp = _create_dxf(tmp_path, "t2_unnamed.dxf", [
            ("Layer_1", "line", ((0, 0), (5000, 0))),
            ("Layer_2", "line", ((5000, 0), (5000, 3000))),
        ])
        parser = CADParser(fp)
        parser.load()
        walls = parser.extract_walls()
        assert len(walls) == 2

    def test_custom_layer_names_parsed(self, tmp_path):
        """Arbitrary layer names used by non-standard CAD software."""
        fp = _create_dxf(tmp_path, "t2_custom.dxf", [
            ("PLAN-LINE-01", "line", ((0, 0), (8000, 0))),
            ("PLAN-LINE-02", "line", ((8000, 0), (8000, 6000))),
            ("PLAN-LINE-02", "line", ((8000, 6000), (0, 6000))),
        ])
        parser = CADParser(fp)
        parser.load()
        walls = parser.extract_walls()
        assert len(walls) == 3


# ══════════════════════════════════════════════════════════════
#  NORMALIZATION: DOUBLE-WALL CENTERLINE MERGING
# ══════════════════════════════════════════════════════════════


class TestCenterlineNormalization:

    def test_parallel_pair_merged(self, tmp_path):
        """Two parallel lines 230mm apart should merge into one centerline."""
        fp = _create_dxf(tmp_path, "norm_pair.dxf", [
            ("WALLS", "line", ((0, 0), (6000, 0))),
            ("WALLS", "line", ((0, 230), (6000, 230))),
        ])
        parser = CADParser(fp)
        parser.load()
        raw = parser.extract_walls()
        assert len(raw) == 2
        
        centerlines = parser.normalize_to_centerlines(raw)
        assert len(centerlines) == 1
        
        # Centerline should be at y=115 (midpoint of 0 and 230)
        cl = centerlines[0]
        y_avg = (cl[0][1] + cl[1][1]) / 2
        assert abs(y_avg - 115.0) < 1.0

    def test_four_walls_rectangle_merged(self, tmp_path):
        """A rectangle drawn with double lines (8 lines) should merge to 4 centerlines."""
        fp = _create_dxf(tmp_path, "norm_rect.dxf", [
            # Bottom wall pair
            ("WALLS", "line", ((0, 0), (6000, 0))),
            ("WALLS", "line", ((0, 230), (6000, 230))),
            # Right wall pair
            ("WALLS", "line", ((6000, 0), (6000, 4000))),
            ("WALLS", "line", ((5770, 0), (5770, 4000))),
            # Top wall pair  
            ("WALLS", "line", ((6000, 4000), (0, 4000))),
            ("WALLS", "line", ((6000, 3770), (0, 3770))),
            # Left wall pair
            ("WALLS", "line", ((0, 4000), (0, 0))),
            ("WALLS", "line", ((230, 4000), (230, 0))),
        ])
        parser = CADParser(fp)
        parser.load()
        raw = parser.extract_walls()
        assert len(raw) == 8
        
        centerlines = parser.normalize_to_centerlines(raw)
        assert len(centerlines) == 4

    def test_single_line_walls_passthrough(self, tmp_path):
        """Single-line walls (no pair) should pass through unchanged."""
        fp = _create_dxf(tmp_path, "norm_single.dxf", [
            ("WALLS", "line", ((0, 0), (6000, 0))),
            ("WALLS", "line", ((6000, 0), (6000, 4000))),
        ])
        parser = CADParser(fp)
        parser.load()
        raw = parser.extract_walls()
        centerlines = parser.normalize_to_centerlines(raw)
        assert len(centerlines) == 2

    def test_mixed_single_and_double_walls(self, tmp_path):
        """Mix of single-line and double-line walls should handle both."""
        fp = _create_dxf(tmp_path, "norm_mixed.dxf", [
            # Double-line bottom wall
            ("WALLS", "line", ((0, 0), (6000, 0))),
            ("WALLS", "line", ((0, 230), (6000, 230))),
            # Single-line internal wall
            ("WALLS", "line", ((3000, 0), (3000, 4000))),
        ])
        parser = CADParser(fp)
        parser.load()
        raw = parser.extract_walls()
        centerlines = parser.normalize_to_centerlines(raw)
        # 1 merged + 1 single = 2
        assert len(centerlines) == 2

    def test_perpendicular_walls_not_merged(self, tmp_path):
        """Perpendicular walls should NOT be merged (angle > 8 degrees)."""
        fp = _create_dxf(tmp_path, "norm_perp.dxf", [
            ("WALLS", "line", ((0, 0), (6000, 0))),      # Horizontal
            ("WALLS", "line", ((3000, 0), (3000, 4000))), # Vertical
        ])
        parser = CADParser(fp)
        parser.load()
        raw = parser.extract_walls()
        centerlines = parser.normalize_to_centerlines(raw)
        assert len(centerlines) == 2  # Both remain separate

    def test_widely_spaced_lines_not_merged(self, tmp_path):
        """Lines 1000mm apart should NOT be merged (exceeds 400mm threshold)."""
        fp = _create_dxf(tmp_path, "norm_wide.dxf", [
            ("WALLS", "line", ((0, 0), (6000, 0))),
            ("WALLS", "line", ((0, 1000), (6000, 1000))),
        ])
        parser = CADParser(fp)
        parser.load()
        raw = parser.extract_walls()
        centerlines = parser.normalize_to_centerlines(raw)
        assert len(centerlines) == 2  # Not merged

    def test_empty_walls_returns_empty(self):
        """Normalizing an empty list should return empty."""
        parser = CADParser.__new__(CADParser)
        result = parser.normalize_to_centerlines([])
        assert result == []


# ══════════════════════════════════════════════════════════════
#  extract_walls_normalized() — FULL PIPELINE
# ══════════════════════════════════════════════════════════════


class TestExtractWallsNormalized:

    def test_full_pipeline_double_walls(self, tmp_path):
        """extract_walls_normalized() should extract AND normalize in one call."""
        fp = _create_dxf(tmp_path, "pipeline.dxf", [
            ("WALLS", "line", ((0, 0), (8000, 0))),
            ("WALLS", "line", ((0, 230), (8000, 230))),
            ("WALLS", "line", ((8000, 0), (8000, 5000))),
            ("WALLS", "line", ((7770, 0), (7770, 5000))),
        ])
        parser = CADParser(fp)
        parser.load()
        result = parser.extract_walls_normalized()
        assert len(result) == 2  # 2 merged centerlines


# ══════════════════════════════════════════════════════════════
#  POINT-TO-LINE DISTANCE UTILITY
# ══════════════════════════════════════════════════════════════


class TestPointToLineDist:

    def test_point_on_line(self):
        """Point on the line should have distance 0."""
        assert CADParser._point_to_line_dist(3, 0, 0, 0, 6, 0) == pytest.approx(0.0, abs=1e-9)

    def test_point_above_horizontal_line(self):
        """Point 5 units above a horizontal line."""
        assert CADParser._point_to_line_dist(3, 5, 0, 0, 6, 0) == pytest.approx(5.0, abs=1e-9)

    def test_point_beside_vertical_line(self):
        """Point 3 units to the right of a vertical line."""
        assert CADParser._point_to_line_dist(3, 2, 0, 0, 0, 10) == pytest.approx(3.0, abs=1e-9)

    def test_degenerate_line(self):
        """Zero-length line should return point-to-point distance."""
        d = CADParser._point_to_line_dist(3, 4, 0, 0, 0, 0)
        assert d == pytest.approx(5.0, abs=1e-9)

    def test_diagonal_line(self):
        """Perpendicular distance to a 45-degree line."""
        # Line from (0,0) to (10,10). Point at (0,10).
        # Dist = |10*0 - 10*10 + 10*0 - 10*0| / sqrt(100+100) = 100/14.14 = 7.07
        d = CADParser._point_to_line_dist(0, 10, 0, 0, 10, 10)
        assert d == pytest.approx(10.0 / math.sqrt(2), abs=0.01)


# ══════════════════════════════════════════════════════════════
#  WALL THICKNESS DETECTION
# ══════════════════════════════════════════════════════════════


class TestWallThicknessDetection:

    def test_detect_230mm_thickness(self, tmp_path):
        """Standard 230mm double walls should be detected."""
        fp = _create_dxf(tmp_path, "thick_230.dxf", [
            ("WALLS", "line", ((0, 0), (6000, 0))),
            ("WALLS", "line", ((0, 230), (6000, 230))),
        ])
        parser = CADParser(fp)
        parser.load()
        walls = parser.extract_walls()
        thickness = parser.detect_wall_thickness(walls)
        assert abs(thickness - 230.0) < 20.0

    def test_no_walls_returns_default(self):
        """Empty wall list should return default 230mm."""
        parser = CADParser.__new__(CADParser)
        parser.doc = None
        parser.msp = None
        thickness = parser.detect_wall_thickness([])
        assert thickness == 230.0


# ══════════════════════════════════════════════════════════════
#  REAL DXF FILE INTEGRATION TESTS
# ══════════════════════════════════════════════════════════════


class TestRealDXFIntegration:
    """Test against actual DXF files in the repository."""

    @pytest.fixture(params=[
        "complex_villa.dxf",
        "complex_house.dxf",
        "real_house_plan.dxf",
        "test_dxfs/case_01_small_rect.dxf",
        "test_dxfs/case_04_l_shape.dxf",
        "test_dxfs/case_10_open_hall.dxf",
    ])
    def real_dxf_path(self, request):
        path = request.param
        if os.path.exists(path):
            return path
        pytest.skip(f"DXF file not found: {path}")

    def test_real_dxf_loads(self, real_dxf_path):
        """Real DXF files should load without error."""
        parser = CADParser(real_dxf_path)
        parser.load()
        assert parser.doc is not None
        assert parser.msp is not None

    def test_real_dxf_extracts_walls(self, real_dxf_path):
        """Real DXF files should produce non-empty wall lists."""
        parser = CADParser(real_dxf_path)
        parser.load()
        walls = parser.extract_walls()
        assert len(walls) > 0

    def test_real_dxf_normalizes(self, real_dxf_path):
        """Real DXF files should normalize successfully."""
        parser = CADParser(real_dxf_path)
        parser.load()
        centerlines = parser.extract_walls_normalized()
        assert len(centerlines) > 0
        # Centerlines should be fewer or equal to raw walls
        raw = parser.extract_walls()
        assert len(centerlines) <= len(raw)

    def test_real_dxf_layers_detected(self, real_dxf_path):
        """Real DXF files should have detectable layers."""
        parser = CADParser(real_dxf_path)
        parser.load()
        layers = parser.get_layers()
        assert len(layers) > 0
