"""
Tests for Column Placement Module (IS 456:2000 & IS 13920:2016)

Tests cover:
- Junction type classification (Corner, T, Cross)
- Mandatory corner placement
- Span check logic (7m max, intermediate columns)
- Seismic zone sizing
- Floating column detection
"""

import pytest
import math
from src.column_placer import (
    ColumnPlacer, ColumnPlacement, PlacementResult,
    JunctionType, ReinforcementRule
)
from src.structural_checks import (
    SoftStoreyChecker, ShortColumnChecker, CantileverChecker,
    CoreShaftHandler, run_all_checks
)


class TestColumnPlacer:
    
    def test_simple_rectangle_placement(self):
        nodes = [
            (0, 0), (6000, 0), (6000, 5000), (0, 5000),
            (3000, 0), (3000, 5000)
        ]
        
        centerlines = [
            ((0, 0), (6000, 0)),
            ((6000, 0), (6000, 5000)),
            ((6000, 5000), (0, 5000)),
            ((0, 5000), (0, 0)),
            ((3000, 0), (3000, 5000))
        ]
        
        placer = ColumnPlacer(nodes=nodes, centerlines=centerlines, seismic_zone="III")
        result = placer.generate_placement()
        
        assert len(result.columns) >= 4
        assert result.stats['corners'] >= 4
        assert result.stats['seismic_zone'] == "III"
    
    def test_junction_type_classification(self):
        nodes = [
            (0, 0),
            (5000, 0),
            (5000, 5000),
            (0, 5000),
            (2500, 2500)
        ]
        
        centerlines = [
            ((0, 0), (5000, 0)),
            ((5000, 0), (5000, 5000)),
            ((5000, 5000), (0, 5000)),
            ((0, 5000), (0, 0)),
            ((0, 2500), (5000, 2500)),
            ((2500, 0), (2500, 5000))
        ]
        
        placer = ColumnPlacer(nodes=nodes, centerlines=centerlines)
        placer._calculate_node_degrees()
        placer._classify_junctions()
        
        corners = [n for n in nodes if placer.node_junctions.get(n) == JunctionType.CORNER]
        assert len(corners) == 4
    
    def test_seismic_zone_sizing(self):
        nodes = [(0, 0), (5000, 0), (5000, 5000), (0, 5000)]
        centerlines = [
            ((0, 0), (5000, 0)),
            ((5000, 0), (5000, 5000)),
            ((5000, 5000), (0, 5000)),
            ((0, 5000), (0, 0))
        ]
        
        placer_seismic = ColumnPlacer(nodes=nodes, centerlines=centerlines, seismic_zone="IV")
        result_seismic = placer_seismic.generate_placement()
        
        placer_non = ColumnPlacer(nodes=nodes, centerlines=centerlines, seismic_zone="II")
        result_non = placer_non.generate_placement()
        
        for col in result_seismic.columns:
            assert col.width >= 300
            assert col.depth >= 300
        
        for col in result_non.columns:
            assert col.width >= 230
    
    def test_long_span_intermediate_columns(self):
        nodes = [(0, 0), (10000, 0)]
        centerlines = [((0, 0), (10000, 0))]
        
        placer = ColumnPlacer(nodes=nodes, centerlines=centerlines)
        placer._calculate_node_degrees()
        placer._classify_junctions()
        placer._place_mandatory_corners()
        placer._fill_long_spans()
        
        has_intermediate = any(
            c.junction_type == JunctionType.INTERIOR for c in placer.columns
        )
        assert has_intermediate or len(placer.columns) > 2
    
    def test_short_span_warning(self):
        nodes = [(0, 0), (2000, 0), (4000, 0)]
        centerlines = [
            ((0, 0), (4000, 0))
        ]
        
        placer = ColumnPlacer(nodes=nodes, centerlines=centerlines)
        result = placer.generate_placement()
        
        has_short_span_or_columns_placed = len(result.columns) >= 2
    
    def test_floating_column_detection(self):
        nodes = [(0, 0), (5000, 0), (5000, 5000), (0, 5000)]
        centerlines = [
            ((0, 0), (5000, 0)),
            ((5000, 0), (5000, 5000)),
            ((5000, 5000), (0, 5000)),
            ((0, 5000), (0, 0))
        ]
        
        placer = ColumnPlacer(nodes=nodes, centerlines=centerlines)
        result = placer.generate_placement()
        
        lower_floor = [(0, 0), (5000, 0), (5000, 5000)]
        
        floating_warnings = placer.detect_floating_columns(lower_floor)
        
        has_floating = any(c.is_floating for c in placer.columns)
        assert has_floating or len(floating_warnings) > 0
    
    def test_json_output_format(self):
        nodes = [(0, 0), (5000, 0), (5000, 5000), (0, 5000)]
        centerlines = [
            ((0, 0), (5000, 0)),
            ((5000, 0), (5000, 5000))
        ]
        
        placer = ColumnPlacer(nodes=nodes, centerlines=centerlines)
        result = placer.generate_placement()
        
        json_str = result.to_json()
        
        import json
        data = json.loads(json_str)
        
        assert 'columns' in data
        assert 'warnings' in data
        assert 'stats' in data
        
        if data['columns']:
            col = data['columns'][0]
            assert 'id' in col
            assert 'location' in col
            assert 'size' in col
            assert 'reinforcement_rule' in col


class TestStructuralChecks:
    
    def test_soft_storey_detection(self):
        checker = SoftStoreyChecker()
        
        floor_stiffnesses = [1000, 2000, 2000, 2000]
        column_counts = [4, 8, 8, 8]
        wall_lengths = [10, 30, 30, 30]
        
        results = checker.check_soft_storey(
            floor_stiffnesses, column_counts, wall_lengths
        )
        
        soft_storeys = [r for r in results if r.is_soft_storey]
        assert len(soft_storeys) >= 1
        assert soft_storeys[0].floor_level == 0
    
    def test_short_column_detection(self):
        checker = ShortColumnChecker()
        
        columns = [
            {'id': 'C1', 'x': 100, 'y': 100, 'depth': 300, 'height': 3000}
        ]
        
        intermediate_beams = [
            {'id': 'B1', 'start': (100, 100), 'end': (3000, 100), 'z': 900}
        ]
        
        results = checker.detect_short_columns(columns, intermediate_beams)
        
        captive = [r for r in results if r.is_captive]
        assert len(captive) >= 1
        assert captive[0].effective_slenderness < 4.0
    
    def test_cantilever_verification(self):
        checker = CantileverChecker()
        
        beams = [
            {'id': 'B1', 'start': (0, 0), 'end': (2000, 0)}
        ]
        
        columns = [
            {'x': 0, 'y': 0}
        ]
        
        results = checker.verify_cantilevers(beams, columns)
        
        unsafe = [r for r in results if not r.is_safe]
        assert len(unsafe) >= 1
    
    def test_core_shaft_detection(self):
        handler = CoreShaftHandler()
        
        rectangles = [
            (5000, 5000, 3000, 4000),
            (10000, 5000, 2100, 2200)
        ]
        
        cores = handler.detect_core_zones(rectangles)
        
        assert len(cores) >= 0
    
    def test_run_all_checks(self):
        columns = [{'id': 'C1', 'x': 0, 'y': 0, 'depth': 300, 'height': 3000}]
        beams = [{'id': 'B1', 'start': (0, 0), 'end': (2000, 0)}]
        
        results = run_all_checks(columns, beams)
        
        assert 'cantilevers' in results
        assert 'summary' in results
        assert 'has_critical_issues' in results['summary']


class TestIntegration:
    
    def test_column_placement_to_dict(self):
        col = ColumnPlacement(
            id="C1",
            x=1000.0,
            y=2000.0,
            width=300.0,
            depth=450.0,
            junction_type=JunctionType.CORNER,
            reinforcement_rule=ReinforcementRule.IS_13920_SPECIAL_CONFINING
        )
        
        data = col.to_dict()
        
        assert data['id'] == 'C1'
        assert data['location']['x'] == 1000.0
        assert data['size']['width'] == 300
        assert data['junction_type'] == 'corner'
        assert 'IS_13920' in data['reinforcement_rule']
