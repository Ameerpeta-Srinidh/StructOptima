from typing import List, Tuple, Dict, Set, Optional
import math
from .cad_parser import CADParser
from .logging_config import get_logger
from .framing_logic import StructuralMember, Point, MemberProperties

logger = get_logger(__name__)

class AutoFramer:
    def __init__(self, parser: CADParser):
        self.parser = parser
        self.nodes = []
        self.columns = []
        self.beams = []
        self.centerlines = []
        
        self.max_span_mm = 7000.0
        self.snap_tolerance_mm = 600.0
        self.min_wall_len_mm = 600.0
        self.cluster_tolerance_mm = 1000.0
        self.double_wall_tolerance_mm = 350.0

    def _is_close(self, p1, p2, tol=None):
        if tol is None:
            tol = self.cluster_tolerance_mm
        return math.hypot(p1[0]-p2[0], p1[1]-p2[1]) < tol

    def _walls_are_parallel(self, w1, w2, angle_tol_deg=10.0):
        v1 = (w1[1][0] - w1[0][0], w1[1][1] - w1[0][1])
        v2 = (w2[1][0] - w2[0][0], w2[1][1] - w2[0][1])
        mag1 = math.hypot(v1[0], v1[1])
        mag2 = math.hypot(v2[0], v2[1])
        if mag1 < 1 or mag2 < 1:
            return False
        dot = (v1[0]*v2[0] + v1[1]*v2[1]) / (mag1 * mag2)
        dot = max(-1.0, min(1.0, dot))
        angle = math.degrees(math.acos(abs(dot)))
        return angle < angle_tol_deg

    def _wall_perpendicular_distance(self, w1, w2):
        mx1 = (w1[0][0] + w1[1][0]) / 2
        my1 = (w1[0][1] + w1[1][1]) / 2
        return self._point_to_segment_dist((mx1, my1), w2[0], w2[1])

    def _extract_wall_centerlines(self, walls):
        if not walls:
            return []
        used = [False] * len(walls)
        centerlines = []
        
        for i, w1 in enumerate(walls):
            if used[i]:
                continue
            group = [w1]
            used[i] = True
            
            for j, w2 in enumerate(walls):
                if i == j or used[j]:
                    continue
                if self._walls_are_parallel(w1, w2):
                    dist = self._wall_perpendicular_distance(w1, w2)
                    if dist < self.double_wall_tolerance_mm:
                        group.append(w2)
                        used[j] = True
            
            if len(group) >= 2:
                all_starts = [w[0] for w in group]
                all_ends = [w[1] for w in group]
                avg_sx = sum(p[0] for p in all_starts) / len(all_starts)
                avg_sy = sum(p[1] for p in all_starts) / len(all_starts)
                avg_ex = sum(p[0] for p in all_ends) / len(all_ends)
                avg_ey = sum(p[1] for p in all_ends) / len(all_ends)
                centerlines.append(((avg_sx, avg_sy), (avg_ex, avg_ey)))
                logger.info(f"Merged {len(group)} parallel walls into centerline")
            else:
                centerlines.append(w1)
        
        return centerlines

    def identify_structural_nodes(self):
        walls = self.parser.extract_walls()
        if not walls:
             logger.warning("No walls found on 'WALLS' layer.")
             return

        valid_walls = []
        for start, end in walls:
            length = math.hypot(end[0]-start[0], end[1]-start[1])
            if length > self.min_wall_len_mm:
                valid_walls.append((start, end))
        
        self.centerlines = self._extract_wall_centerlines(valid_walls)
        
        candidate_points = []
        for start, end in self.centerlines:
            candidate_points.append(start)
            candidate_points.append(end)
            
            dx = end[0] - start[0]
            dy = end[1] - start[1]
            length = math.hypot(dx, dy)
            
            if length > self.max_span_mm:
                num_spans = math.ceil(length / 5000.0)
                if num_spans > 1:
                    step_x = dx / num_spans
                    step_y = dy / num_spans
                    for i in range(1, num_spans):
                        mx = start[0] + i * step_x
                        my = start[1] + i * step_y
                        candidate_points.append((mx, my))
                        logger.info(f"Added intermediate column for {length:.0f}mm span at ({mx:.1f}, {my:.1f})")

        unique_nodes = []
        while candidate_points:
            pt = candidate_points.pop(0)
            cluster = [pt]
            remaining = []
            for other in candidate_points:
                if self._is_close(pt, other):
                    cluster.append(other)
                else:
                    remaining.append(other)
            candidate_points = remaining
            
            nx = sum(p[0] for p in cluster) / len(cluster)
            ny = sum(p[1] for p in cluster) / len(cluster)
            unique_nodes.append((nx, ny))
            
        self.nodes = self._filter_nodes(unique_nodes, self.centerlines)
        self._snap_to_grid() 
        
        logger.info("Identified %d structural nodes after filtering/snapping.", len(self.nodes))
        
    def _filter_nodes(self, nodes, walls):
        """
        Filters out:
        1. Short Spurs: Degree 1 nodes connected to a junction (Degree 3+) by a short wall (< 1.2m).
        2. Collinear Joints: Degree 2 straight lines.
        """
        filtered = []
        
        # Helper to get degree of a node based on CURRENT wall list
        def get_degree(p):
            count = 0
            for ws, we in walls:
                if self._is_close(p, ws) or self._is_close(p, we):
                    count += 1
            return count

        for n in nodes:
            # Find connected walls and neighbors
            connected_walls = []
            neighbors = []
            
            for w_start, w_end in walls:
                if self._is_close(n, w_start):
                    connected_walls.append((w_start, w_end))
                    neighbors.append(w_end)
                elif self._is_close(n, w_end):
                    connected_walls.append((w_start, w_end))
                    neighbors.append(w_start)
            
            degree = len(connected_walls)
            
            # RULE 1: Remove Short Spurs (Degree 1 connected to a Hub)
            if degree == 1:
                neighbor = neighbors[0]
                dist = math.hypot(n[0]-neighbor[0], n[1]-neighbor[1])
                neighbor_degree = get_degree(neighbor)
                
                # If short spur (< 1.2m) connected to a Junction (Degree >= 3) or Corner (Degree >= 2)
                # Actually, if it's a short sticking out wall from a main wall, remove it.
                if dist < 1200 and neighbor_degree >= 2:
                    logger.info(f"Removing short spur node at ({n[0]:.1f}, {n[1]:.1f}) connected to hub.")
                    continue
            
            # RULE 2: Check Degree 2 (Corner or Straight?)
            if degree == 2:
                # Vectors from N
                w1 = connected_walls[0]
                w2 = connected_walls[1]
                
                # Identify other ends
                p1 = w1[1] if self._is_close(n, w1[0]) else w1[0]
                p2 = w2[1] if self._is_close(n, w2[0]) else w2[0]
                
                v1 = (p1[0]-n[0], p1[1]-n[1])
                v2 = (p2[0]-n[0], p2[1]-n[1])
                
                # Dot product
                mag1 = math.hypot(v1[0], v1[1])
                mag2 = math.hypot(v2[0], v2[1])
                
                if mag1 < 1 or mag2 < 1: 
                    filtered.append(n)
                    continue
                    
                dot = (v1[0]*v2[0] + v1[1]*v2[1]) / (mag1*mag2)
                
                # Collinear if angle approx 180 (dot approx -1)
                if dot < -0.90: 
                    logger.info(f"Removing collinear node at ({n[0]:.1f}, {n[1]:.1f})")
                    continue 
            
            filtered.append(n)
            
        return filtered

    def _snap_to_grid(self):
        """Aligns nodes that are close in X or Y to form a regular grid."""
        if not self.nodes: return
        
        # Snap X
        xs = sorted(list(set([n[0] for n in self.nodes])))
        snapped_x = {} # original -> snapped
        
        current_group = [xs[0]]
        for i in range(1, len(xs)):
            if abs(xs[i] - xs[i-1]) < self.snap_tolerance_mm:
                current_group.append(xs[i])
            else:
                # Finalize group
                avg_x = sum(current_group) / len(current_group)
                for x in current_group: snapped_x[x] = avg_x
                current_group = [xs[i]]
        # Last group
        avg_x = sum(current_group) / len(current_group)
        for x in current_group: snapped_x[x] = avg_x
        
        # Snap Y
        ys = sorted(list(set([n[1] for n in self.nodes])))
        snapped_y = {}
        
        current_group = [ys[0]]
        for i in range(1, len(ys)):
            if abs(ys[i] - ys[i-1]) < self.snap_tolerance_mm:
                current_group.append(ys[i])
            else:
                avg_y = sum(current_group) / len(current_group)
                for y in current_group: snapped_y[y] = avg_y
                current_group = [ys[i]]
        avg_y = sum(current_group) / len(current_group)
        for y in current_group: snapped_y[y] = avg_y
        
        # Apply Logic: Map original nodes closest to these snapped values?
        # Actually simplest is just to update node list
        new_nodes = []
        for x, y in self.nodes:
            # Find closest key in map (since floating point might mismatch slightly)
            # Brute search is fine for N < 100
            closest_x = min(snapped_x.keys(), key=lambda k: abs(k-x))
            closest_y = min(snapped_y.keys(), key=lambda k: abs(k-y))
            new_nodes.append((snapped_x[closest_x], snapped_y[closest_y]))
            
        # Remove duplicates created by snapping
        self.nodes = list(set(new_nodes))
        
        # FINAL PASS: Merge nodes that are still too close
        # Moderate merge for "side-by-side" columns (e.g. < 600mm)
        self._merge_close_nodes(min_dist=600.0)

    def _merge_close_nodes(self, min_dist=600.0):
        # ... (logic same) ...
        """Merges nodes that are closer than min_dist."""
        if not self.nodes: return
        
        merged = []
        # Sort by X then Y to make processing somewhat ordered
        sorted_nodes = sorted(self.nodes, key=lambda p: (p[0], p[1]))
        
        while sorted_nodes:
            pt = sorted_nodes.pop(0)
            group = [pt]
            
            # Find all neighbors within min_dist
            # Naive O(N^2) is fine for small N
            remaining = []
            for other in sorted_nodes:
                if math.hypot(pt[0]-other[0], pt[1]-other[1]) < min_dist:
                    group.append(other)
                else:
                    remaining.append(other)
            
            sorted_nodes = remaining
            
            # Average
            avg_x = sum(p[0] for p in group) / len(group)
            avg_y = sum(p[1] for p in group) / len(group)
            merged.append((avg_x, avg_y))
            
            if len(group) > 1:
                logger.info(f"Merged {len(group)} close columns into one at ({avg_x:.1f}, {avg_y:.1f})")
                
        self.nodes = merged

    def generate_columns(self) -> List[Dict]:
        """Places columns at identified nodes."""
        if not self.nodes:
            self.identify_structural_nodes()
            
        self.columns = []
        for i, (nx, ny) in enumerate(self.nodes):
            self.columns.append({
                'x': nx,
                'y': ny,
                'width': 300, # Default
                'depth': 300,
                'id': f"AC{i+1}"
            })
        return self.columns

    def generate_beams(self, use_fallback: bool = True, use_is_code: bool = False, 
                        seismic_zone: str = "III") -> List[StructuralMember]:
        """
        Generates beams connecting columns.
        
        Args:
            use_fallback: If True, add beams between adjacent columns even without wall
            use_is_code: If True, use IS 456/13920 compliant BeamPlacer for realistic sizing
            seismic_zone: Seismic zone for IS 13920 checks (III, IV, V are seismic)
        
        Returns:
            List of StructuralMember beams
        """
        if not self.columns: self.generate_columns()
        
        if use_is_code:
            return self._generate_is_code_beams(seismic_zone)
        
        walls = self.parser.extract_walls()
        beams = []
        beam_count = 0
        beam_pairs_added = set()
        
        unique_x = sorted(list(set([c['x'] for c in self.columns])))
        unique_y = sorted(list(set([c['y'] for c in self.columns])))
        
        def add_beam(c1, c2, direction):
            nonlocal beam_count
            pair_key = (min(c1['x'], c2['x']), min(c1['y'], c2['y']), max(c1['x'], c2['x']), max(c1['y'], c2['y']))
            if pair_key in beam_pairs_added:
                return
            beam_pairs_added.add(pair_key)
            beam_count += 1
            beams.append(StructuralMember(
                id=f"AB_{direction}_{beam_count}",
                type="beam",
                start_point=Point(x=c1['x'], y=c1['y']),
                end_point=Point(x=c2['x'], y=c2['y']),
                properties=MemberProperties(width_mm=230, depth_mm=450)
            ))
        
        for x in unique_x:
            cols_on_line = sorted([c for c in self.columns if abs(c['x'] - x) < 1.0], key=lambda c: c['y'])
            for i in range(len(cols_on_line) - 1):
                c1 = cols_on_line[i]
                c2 = cols_on_line[i+1]
                span = abs(c2['y'] - c1['y'])
                
                is_connected = self._check_wall_connectivity((c1['x'], c1['y']), (c2['x'], c2['y']), walls)
                
                if is_connected:
                    add_beam(c1, c2, "V")
                elif use_fallback and span <= self.max_span_mm:
                    add_beam(c1, c2, "V")
                    logger.info(f"Fallback beam V: ({c1['x']:.0f},{c1['y']:.0f}) -> ({c2['x']:.0f},{c2['y']:.0f})")

        for y in unique_y:
            cols_on_line = sorted([c for c in self.columns if abs(c['y'] - y) < 1.0], key=lambda c: c['x'])
            for i in range(len(cols_on_line) - 1):
                c1 = cols_on_line[i]
                c2 = cols_on_line[i+1]
                span = abs(c2['x'] - c1['x'])
                
                is_connected = self._check_wall_connectivity((c1['x'], c1['y']), (c2['x'], c2['y']), walls)
                
                if is_connected:
                    add_beam(c1, c2, "H")
                elif use_fallback and span <= self.max_span_mm:
                    add_beam(c1, c2, "H")
                    logger.info(f"Fallback beam H: ({c1['x']:.0f},{c1['y']:.0f}) -> ({c2['x']:.0f},{c2['y']:.0f})")
                    
        self.beams = beams
        
        self._ensure_minimum_connectivity(beams, beam_pairs_added)
        
        return self.beams
    
    def _ensure_minimum_connectivity(self, beams, beam_pairs_added):
        """
        Ensures every column has at least 2 beam connections.
        Connects hanging columns to their nearest neighbors.
        Falls back to extended spans for isolated columns.
        """
        def get_beam_count(col):
            count = 0
            for b in self.beams:
                if ((abs(b.start_point.x - col['x']) < 100 and abs(b.start_point.y - col['y']) < 100) or
                    (abs(b.end_point.x - col['x']) < 100 and abs(b.end_point.y - col['y']) < 100)):
                    count += 1
            return count
        
        beam_count = len(self.beams)
        isolated_columns = []
        
        for col in self.columns:
            connections = get_beam_count(col)
            
            if connections >= 2:
                continue
            
            max_search_dist = self.max_span_mm * 1.5
            
            candidates = []
            for other in self.columns:
                if other['id'] == col['id']:
                    continue
                    
                dx = abs(other['x'] - col['x'])
                dy = abs(other['y'] - col['y'])
                dist = math.hypot(dx, dy)
                
                if dist > max_search_dist:
                    continue
                
                if dist < 500:
                    continue
                
                pair_key = (min(col['x'], other['x']), min(col['y'], other['y']), 
                           max(col['x'], other['x']), max(col['y'], other['y']))
                if pair_key in beam_pairs_added:
                    continue
                
                is_horizontal = dx > dy
                over_limit = dist > self.max_span_mm
                candidates.append((dist, other, is_horizontal, pair_key, over_limit))
            
            candidates.sort(key=lambda x: (x[4], x[0]))
            
            needed = 2 - connections
            added = 0
            for dist, other, is_horizontal, pair_key, over_limit in candidates[:needed]:
                beam_count += 1
                direction = "H" if is_horizontal else "V"
                self.beams.append(StructuralMember(
                    id=f"AB_{direction}_{beam_count}",
                    type="beam",
                    start_point=Point(x=col['x'], y=col['y']),
                    end_point=Point(x=other['x'], y=other['y']),
                    properties=MemberProperties(width_mm=230, depth_mm=450)
                ))
                beam_pairs_added.add(pair_key)
                if over_limit:
                    logger.warning(f"Extended span beam ({dist:.0f}mm) connecting {col['id']} to {other['id']} - requires intermediate support")
                else:
                    logger.info(f"Connected hanging column {col['id']} to {other['id']} ({dist:.0f}mm)")
                added += 1
            
            if connections + added < 2:
                isolated_columns.append(col)
        
        if isolated_columns:
            for col in isolated_columns:
                logger.warning(f"STRUCTURAL WARNING: Column {col['id']} at ({col['x']:.0f}, {col['y']:.0f}) could not be connected - review required")

    def _check_wall_connectivity(self, p1, p2, walls):
        """
        Returns True if a wall segment roughly coincides with segment p1-p2.
        Checks multiple sample points and uses proper angle-based parallelism.
        """
        beam_len = math.hypot(p2[0]-p1[0], p2[1]-p1[1])
        if beam_len < 1:
            return False
        
        num_samples = max(3, int(beam_len / 1000))
        sample_points = []
        for i in range(num_samples):
            t = (i + 0.5) / num_samples
            sx = p1[0] + t * (p2[0] - p1[0])
            sy = p1[1] + t * (p2[1] - p1[1])
            sample_points.append((sx, sy))
        
        wall_tolerance = 500.0
        
        for start, end in walls:
            v_beam = (p2[0]-p1[0], p2[1]-p1[1])
            v_wall = (end[0]-start[0], end[1]-start[1])
            
            beam_mag = math.hypot(v_beam[0], v_beam[1])
            wall_mag = math.hypot(v_wall[0], v_wall[1])
            
            if wall_mag < 1:
                continue
            
            dot = (v_beam[0]*v_wall[0] + v_beam[1]*v_wall[1]) / (beam_mag * wall_mag)
            dot = max(-1.0, min(1.0, dot))
            angle = math.degrees(math.acos(abs(dot)))
            
            if angle > 15.0:
                continue
            
            points_near_wall = 0
            for sp in sample_points:
                dist = self._point_to_segment_dist(sp, start, end)
                if dist < wall_tolerance:
                    points_near_wall += 1
            
            if points_near_wall >= len(sample_points) * 0.5:
                return True
        
        return False
        
    def _point_to_segment_dist(self, p, a, b):
        """Distance from point p to segment a-b."""
        px, py = p
        ax, ay = a
        bx, by = b
        
        l2 = (bx-ax)**2 + (by-ay)**2
        if l2 == 0: return math.hypot(px-ax, py-ay)
        
        t = ((px-ax)*(bx-ax) + (py-ay)*(by-ay)) / l2
        t = max(0, min(1, t))
        
        proj_x = ax + t*(bx-ax)
        proj_y = ay + t*(by-ay)
        
        return math.hypot(px-proj_x, py-proj_y)
    
    def _generate_is_code_beams(self, seismic_zone: str = "III") -> List[StructuralMember]:
        """
        Uses IS 456/13920 compliant BeamPlacer for realistic beam sizing.
        
        This method implements proper structural engineering practices:
        - L/d ratios per IS 456 (Cantilever: L/7, SS: L/12-15, Continuous: L/15-26)
        - Seismic checks per IS 13920 (b/D >= 0.3, b >= 200mm)
        - Slab panel detection and secondary beam placement
        - Cantilever back-span verification (L_back >= 1.5 * L_cant)
        """
        from .beam_placer import BeamPlacer, BeamType
        
        walls = self.parser.extract_walls()
        
        placer = BeamPlacer(
            columns=self.columns,
            walls=walls,
            seismic_zone=seismic_zone
        )
        
        result = placer.generate_placement()
        
        beams = []
        for bp in result.beams:
            beam = StructuralMember(
                id=bp.id,
                type="beam",
                start_point=Point(x=bp.start_x, y=bp.start_y),
                end_point=Point(x=bp.end_x, y=bp.end_y),
                properties=MemberProperties(width_mm=bp.width_mm, depth_mm=bp.depth_mm)
            )
            beams.append(beam)
        
        self.beams = beams
        self.beam_placement_result = result
        
        logger.info(f"IS-Code BeamPlacer: Generated {len(beams)} beams "
                   f"(Primary: {result.stats.get('primary', 0)}, "
                   f"Secondary: {result.stats.get('secondary', 0)}, "
                   f"Cantilever: {result.stats.get('cantilever', 0)})")
        
        return self.beams

