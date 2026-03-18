
from .fea_solver import FrameSolver2D
from .grid_manager import GridManager, Column
from .framing_logic import StructuralMember
from .materials import Concrete
import math
import logging

logger = logging.getLogger(__name__)

def update_structural_analysis(gm: GridManager, beams: list[StructuralMember], fck: float = 25.0, use_cracked_sections: bool = False):
    """
    Slices the building into 2D frames and runs FEA on each.
    Updates beam.design_moment_knm and beam.design_shear_kn.
    
    Args:
        gm: GridManager with columns and grid lines
        beams: List of StructuralMember objects
        fck: Characteristic strength of concrete (N/mm²), default M25
    """
    logger.info("Starting FEA Analysis...")
    
    # Calculate E from fck (IS 456 Cl 6.2.3.1)
    E_mpa = 5000 * math.sqrt(fck)  # MPa
    E_kpa = E_mpa * 1000  # kN/m² (kPa)
    
    # 1. Slice Frames along X-Grid Lines (YZ Planes)
    # We look for Frames that lie on a constant X
    for x_grid in gm.x_grid_lines:
        solve_frame(gm, beams, plane="YZ", constant_coord=x_grid, fck=fck, use_cracked_sections=use_cracked_sections)
        
    # 2. Slice Frames along Y-Grid Lines (XZ Planes)
    for y_grid in gm.y_grid_lines:
        solve_frame(gm, beams, plane="XZ", constant_coord=y_grid, fck=fck, use_cracked_sections=use_cracked_sections)
        
def solve_frame(gm, all_beams, plane="YZ", constant_coord=0.0, fck=25.0, use_cracked_sections=False):
    solver = FrameSolver2D()
    
    # Stiffness Modifiers (IS 1893:2016 Cl 6.4.3.1 / IS 16700:2017 Table 2)
    # Uncracked (Gross) vs Cracked (Effective)
    if use_cracked_sections:
        col_mod = 0.70
        beam_mod = 0.35
        # slab_mod = 0.25 (not modeled explicitly in frame)
    else:
        col_mod = 1.0
        beam_mod = 1.0
    
    # Tolerance for "lying on plane"
    TOL = 0.1
    
    # Filter Members belonging to this frame
    frame_cols = []
    frame_beams = []
    
    # Node merging with tolerance
    # structure: list of {'x': x, 'y': y, 'idx': idx}
    node_registry = [] 
    
    def get_or_add_node(x2d, y2d):
        # Scan for existing node within small tolerance
        MERGE_TOL = 0.05 # 50mm
        for n in node_registry:
            dist = math.hypot(n['x'] - x2d, n['y'] - y2d)
            if dist < MERGE_TOL:
                return n['idx']
        
        # New node
        idx = solver.add_node(x2d, y2d)
        node_registry.append({'x': x2d, 'y': y2d, 'idx': idx})
        return idx
    
    # 1. Columns
    # In YZ Plane (X constant), 2D coords are (y, z)
    # In XZ Plane (Y constant), 2D coords are (x, z)
    
    for col in gm.columns:
        # Check if col is roughly on this plane
        if plane == "YZ":
            if abs(col.x - constant_coord) < TOL:
                n1 = get_or_add_node(col.y, col.z_bottom)
                n2 = get_or_add_node(col.y, col.z_top)
                
                # Add Element
                # E = 25000 MPa = 25e6 kPa (kN/m2)
                # I = b*d^3/12 m4
                # Prop?
                b_m = col.width_nb / 1000.0
                d_m = col.depth_nb / 1000.0
                I_gross = (b_m * d_m**3)/12.0
                I = I_gross * col_mod
                A = b_m * d_m
                E = 5000 * math.sqrt(fck) * 1000 # E in kPa
                
                elem_idx = solver.add_element(n1, n2, E, I, A)
                
        elif plane == "XZ":
            if abs(col.y - constant_coord) < TOL:
                n1 = get_or_add_node(col.x, col.z_bottom)
                n2 = get_or_add_node(col.x, col.z_top)
                
                b_m = col.width_nb / 1000.0
                d_m = col.depth_nb / 1000.0
                I_gross = (b_m * d_m**3)/12.0
                I = I_gross * col_mod
                A = b_m * d_m
                E = 5000 * math.sqrt(fck) * 1000
                
                elem_idx = solver.add_element(n1, n2, E, I, A)
    
    # 2. Beams
    for beam in all_beams:
        # Check alignment
        # Beam is on plane if BOTH start and end satisfy coord
        if plane == "YZ":
            on_plane = abs(beam.start_point.x - constant_coord) < TOL and \
                       abs(beam.end_point.x - constant_coord) < TOL
            
            if on_plane:
                # 2D Coords are (y, z=?)
                # Beams are typically at ceiling level of a story
                # We need to find Z height. It's not stored in beam directly usually?
                # GridManager generates beams at Z=0 in simple logic?
                # Ah, we need to associate beams with levels.
                # In main.py we expanded beams for all stories?
                # Actually main.py: "all_beams.extend(beams)" just copies the Objects.
                # The Objects (StructuralMember) don't have Z !
                # This is a gap in the data model. StructuralMember assumes 2D plan.
                
                # Workaround: The caller passed `beams` which are just 2D plan beams.
                # We need to "stack" them for each story.
                pass
        
    # CRITICAL FIX for Integration:
    # Since StructuralMember in the current project is purely 2D (Plan View),
    # performing a full multi-story frame analysis requires assuming Z levels.
    # We will iterate through Stories and add beams at each level to the solver.
    
    num_stories = gm.num_stories
    story_h = gm.story_height_m
    
    # We iterate the unique plan beams and replicate them for each level
    unique_plan_beams = all_beams if isinstance(all_beams[0], StructuralMember) else []
    # Note: main.py passes `all_beams` which is `beams * num_stories`. 
    # But they are same identities if valid?
    # Actually main.py does: `all_beams.extend(beams)`. Copies reference?
    # Yes, simple list extend copies references. So they are the SAME objects repeated.
    
    # We need to update the `design_moment` on the object. If we have 1 object representing 3 floors,
    # we will overwrite it 3 times. We should take the MAX forces across all levels for design envelope.
    
    # Let's filter unique plan beams first by ID
    unique_map = {b.id: b for b in all_beams}
    plan_beams = list(unique_map.values()) 
    
    for beam in plan_beams:
         if plane == "YZ":
            is_aligned = abs(beam.start_point.x - constant_coord) < TOL and \
                         abs(beam.end_point.x - constant_coord) < TOL
                         
            if is_aligned:
                # Add this beam at every story level
                for level in range(1, num_stories+1):
                    # Check Length first
                    dy = abs(beam.end_point.y - beam.start_point.y)
                    if dy < 0.001: continue
                    
                    z_level = level * story_h
                    n1 = get_or_add_node(beam.start_point.y, z_level)
                    n2 = get_or_add_node(beam.end_point.y, z_level)
                    
                    if n1 == n2:
                        continue # Skip zero length elements after merge
                    
                    b_m = beam.properties.width_mm / 1000.0
                    d_m = beam.properties.depth_mm / 1000.0
                    I_gross = (b_m * d_m**3)/12.0 
                    I = I_gross * beam_mod
                    A = b_m * d_m
                    E = 5000 * math.sqrt(fck) * 1000
                    
                    e_idx = solver.add_element(n1, n2, E, I, A)
                    
                    # Load
                    # 20 kN/m + SW
                    sw = A * 25.0
                    load = 20.0 + sw
                    solver.add_member_load(e_idx, load)
                    
                    # Map element back to beam object to store results
                    # Dictionary to track: beam_obj -> [list of result_indices_across_levels]
                    if not hasattr(solver, 'beam_map'): solver.beam_map = {}
                    if beam.id not in solver.beam_map: solver.beam_map[beam.id] = []
                    solver.beam_map[beam.id].append(e_idx)

         elif plane == "XZ":
            is_aligned = abs(beam.start_point.y - constant_coord) < TOL and \
                         abs(beam.end_point.y - constant_coord) < TOL
            
            if is_aligned:
                for level in range(1, num_stories+1):
                    # Check length
                    dx = abs(beam.end_point.x - beam.start_point.x)
                    if dx < 0.001: continue

                    z_level = level * story_h
                    n1 = get_or_add_node(beam.start_point.x, z_level)
                    n2 = get_or_add_node(beam.end_point.x, z_level)
                    
                    if n1 == n2:
                        continue
                    
                    b_m = beam.properties.width_mm / 1000.0
                    d_m = beam.properties.depth_mm / 1000.0
                    I_gross = (b_m * d_m**3)/12.0 
                    I = I_gross * beam_mod
                    A = b_m * d_m
                    E = 5000 * math.sqrt(fck) * 1000
                    
                    e_idx = solver.add_element(n1, n2, E, I, A)
                    
                    sw = A * 25.0
                    load = 20.0 + sw
                    solver.add_member_load(e_idx, load)
                    
                    if not hasattr(solver, 'beam_map'): solver.beam_map = {}
                    if beam.id not in solver.beam_map: solver.beam_map[beam.id] = []
                    solver.beam_map[beam.id].append(e_idx)

    # SOLVE
    if len(solver.nodes) > 0:
        logger.info(f"Solving Frame Plane={plane} Coord={constant_coord} | Nodes: {len(solver.nodes)} | Elements: {len(solver.elements)}")
        solver.solve()
        
        # Post Process
        if hasattr(solver, 'beam_map'):
            for bid, elem_indices in solver.beam_map.items():
                max_m = 0.0
                max_v = 0.0
                
                # We need to find the beam object again to update it
                beam_obj = unique_map.get(bid)
                if not beam_obj: continue
                
                for idx in elem_indices:
                    res = solver.get_member_forces(idx)
                    if res:
                        max_m = max(max_m, res.get('max_moment', 0))
                        max_v = max(max_v, res.get('max_shear', 0))
                
                # Update Beam only if this frame gave higher forces (Max Envelope)
                beam_obj.design_moment_knm = max(beam_obj.design_moment_knm, max_m)
                beam_obj.design_shear_kn = max(beam_obj.design_shear_kn, max_v)
                beam_obj.analysis_status = "FEA_SOLVED"
