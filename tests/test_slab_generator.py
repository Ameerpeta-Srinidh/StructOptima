"""
Tests for Slab Generation Module (IS 456:2000)

Tests cover:
- Closed loop detection from beam grid
- One-way vs Two-way classification (Ly/Lx > 2.0)
- Thickness calculation (L/25-35, min 125mm)
- Load calculation (self-weight, floor finish, live)
- Wall load mapping
- Special zone detection (staircase, lift, void)
"""

import pytest
import math
from src.slab_generator import (
    SlabGenerator, SlabElement, SlabType, SlabZoneType,
    WallLoad, SlabGenerationResult, SlabLoad, LoadType
)


class TestSlabGenerator:
    
    def test_closed_loop_detection(self):
        columns = [
            {'id': 'C1', 'x': 0, 'y': 0},
            {'id': 'C2', 'x': 4000, 'y': 0},
            {'id': 'C3', 'x': 4000, 'y': 3000},
            {'id': 'C4', 'x': 0, 'y': 3000},
        ]
        beams = []
        walls = []
        
        gen = SlabGenerator(beams=beams, columns=columns, walls=walls)
        loops = gen._find_closed_loops()
        
        assert len(loops) == 1
    
    def test_one_way_classification(self):
        columns = [
            {'id': 'C1', 'x': 0, 'y': 0},
            {'id': 'C2', 'x': 2500, 'y': 0},
            {'id': 'C3', 'x': 2500, 'y': 6000},
            {'id': 'C4', 'x': 0, 'y': 6000},
        ]
        
        gen = SlabGenerator(beams=[], columns=columns, walls=[])
        result = gen.generate()
        
        assert len(result.slabs) == 1
        assert result.slabs[0].slab_type == SlabType.ONE_WAY
        assert result.slabs[0].aspect_ratio > 2.0
    
    def test_two_way_classification(self):
        columns = [
            {'id': 'C1', 'x': 0, 'y': 0},
            {'id': 'C2', 'x': 4000, 'y': 0},
            {'id': 'C3', 'x': 4000, 'y': 3500},
            {'id': 'C4', 'x': 0, 'y': 3500},
        ]
        
        gen = SlabGenerator(beams=[], columns=columns, walls=[])
        result = gen.generate()
        
        assert len(result.slabs) == 1
        assert result.slabs[0].slab_type == SlabType.TWO_WAY
        assert result.slabs[0].aspect_ratio <= 2.0
    
    def test_thickness_one_way(self):
        gen = SlabGenerator(beams=[], columns=[], walls=[], steel_grade="Fe415")
        
        t = gen._calculate_thickness(3500, SlabType.ONE_WAY)
        
        expected = math.ceil((3500 / 28) / 5) * 5
        expected = max(expected, 125)
        assert t == expected
        assert t >= 125
    
    def test_thickness_two_way(self):
        gen = SlabGenerator(beams=[], columns=[], walls=[], steel_grade="Fe415")
        
        t = gen._calculate_thickness(4000, SlabType.TWO_WAY)
        
        expected = math.ceil((4000 / 35) / 5) * 5
        expected = max(expected, 125)
        assert t == expected
        assert t >= 125
    
    def test_minimum_thickness(self):
        gen = SlabGenerator(beams=[], columns=[], walls=[], steel_grade="Fe415")
        
        t = gen._calculate_thickness(2000, SlabType.TWO_WAY)
        
        assert t >= 125
    
    def test_void_detection(self):
        columns = [
            {'id': 'C1', 'x': 0, 'y': 0},
            {'id': 'C2', 'x': 800, 'y': 0},
            {'id': 'C3', 'x': 800, 'y': 800},
            {'id': 'C4', 'x': 0, 'y': 800},
        ]
        
        gen = SlabGenerator(beams=[], columns=columns, walls=[])
        loops = gen._find_closed_loops()
        valid = gen._filter_valid_panels(loops)
        
        assert len(valid) == 0
    
    def test_staircase_detection(self):
        columns = [
            {'id': 'C1', 'x': 0, 'y': 0},
            {'id': 'C2', 'x': 3000, 'y': 0},
            {'id': 'C3', 'x': 3000, 'y': 4000},
            {'id': 'C4', 'x': 0, 'y': 4000},
        ]
        text_annotations = [
            {'text': 'STAIRCASE', 'x': 1500, 'y': 2000}
        ]
        
        gen = SlabGenerator(
            beams=[], columns=columns, walls=[],
            text_annotations=text_annotations
        )
        result = gen.generate()
        
        assert len(result.slabs) == 1
        assert result.slabs[0].zone_type == SlabZoneType.STAIRCASE
    
    def test_load_calculation(self):
        columns = [
            {'id': 'C1', 'x': 0, 'y': 0},
            {'id': 'C2', 'x': 4000, 'y': 0},
            {'id': 'C3', 'x': 4000, 'y': 4000},
            {'id': 'C4', 'x': 0, 'y': 4000},
        ]
        
        gen = SlabGenerator(beams=[], columns=columns, walls=[])
        result = gen.generate()
        
        slab = result.slabs[0]
        
        assert slab.total_dead_kn_m2 > 0
        assert slab.total_live_kn_m2 == 2.0
        assert slab.total_factored_kn_m2 > 0
        
        expected_factored = 1.5 * slab.total_dead_kn_m2 + 1.5 * slab.total_live_kn_m2
        assert abs(slab.total_factored_kn_m2 - expected_factored) < 0.1
    
    def test_wall_load_calculation(self):
        columns = [
            {'id': 'C1', 'x': 0, 'y': 0},
            {'id': 'C2', 'x': 5000, 'y': 0},
        ]
        beams = [
            {'id': 'B1', 'start_x': 0, 'start_y': 0, 'end_x': 5000, 'end_y': 0}
        ]
        walls = [
            ((0, 0), (5000, 0))
        ]
        
        gen = SlabGenerator(
            beams=beams, columns=columns, walls=walls,
            storey_height_mm=3000, beam_depth_mm=450
        )
        gen._map_wall_loads()
        
        assert len(gen.wall_loads) >= 1
        
        if gen.wall_loads:
            wl = gen.wall_loads[0]
            expected = 0.230 * (2.55) * 20
            assert abs(wl.load_kn_m - expected) < 1.0
    
    def test_json_output_format(self):
        columns = [
            {'id': 'C1', 'x': 0, 'y': 0},
            {'id': 'C2', 'x': 4000, 'y': 0},
            {'id': 'C3', 'x': 4000, 'y': 4000},
            {'id': 'C4', 'x': 0, 'y': 4000},
        ]
        
        gen = SlabGenerator(beams=[], columns=columns, walls=[])
        result = gen.generate()
        
        json_str = result.to_json()
        
        import json
        data = json.loads(json_str)
        
        assert 'slabs' in data
        assert 'loads_on_beams' in data
        assert 'warnings' in data
        assert 'stats' in data
        
        if data['slabs']:
            slab = data['slabs'][0]
            assert 'id' in slab
            assert 'type' in slab
            assert 'dimensions' in slab
            assert 'thickness' in slab
            assert 'loads' in slab
    
    def test_large_panel_warning(self):
        columns = [
            {'id': 'C1', 'x': 0, 'y': 0},
            {'id': 'C2', 'x': 8000, 'y': 0},
            {'id': 'C3', 'x': 8000, 'y': 6000},
            {'id': 'C4', 'x': 0, 'y': 6000},
        ]
        
        gen = SlabGenerator(beams=[], columns=columns, walls=[])
        result = gen.generate()
        
        assert len(result.warnings) > 0 or len(result.slabs[0].warnings) > 0
    
    def test_multi_panel_grid(self):
        columns = [
            {'id': 'C1', 'x': 0, 'y': 0},
            {'id': 'C2', 'x': 4000, 'y': 0},
            {'id': 'C3', 'x': 8000, 'y': 0},
            {'id': 'C4', 'x': 0, 'y': 4000},
            {'id': 'C5', 'x': 4000, 'y': 4000},
            {'id': 'C6', 'x': 8000, 'y': 4000},
        ]
        
        gen = SlabGenerator(beams=[], columns=columns, walls=[])
        result = gen.generate()
        
        assert result.stats['total_slabs'] == 2
