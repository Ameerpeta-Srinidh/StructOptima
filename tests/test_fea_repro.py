
import logging
import sys
import os

sys.path.append(os.getcwd())

from src.fea_solver import FrameSolver2D

# Setup Logging
from src.logging_config import setup_logging
setup_logging()

def test_simple_portal_frame():
    print("Testing Simple Portal Frame...")
    solver = FrameSolver2D()
    
    # 2D Coords (Y, Z)
    # Node 0: (0, 0) - Fixed Base
    # Node 1: (0, 3) - Top Left
    # Node 2: (6, 0) - Fixed Base
    # Node 3: (6, 3) - Top Right
    
    n0 = solver.add_node(0, 0)
    n1 = solver.add_node(0, 3)
    n2 = solver.add_node(6, 0)
    n3 = solver.add_node(6, 3)
    
    # Properties
    E = 25e6 # 25 GPa
    I = 0.0054 # 300x600 column approx
    A = 0.18 # 300x600
    
    # Elements
    # Col 1
    solver.add_element(n0, n1, E, I, A)
    # Col 2
    solver.add_element(n2, n3, E, I, A)
    # Beam
    b_idx = solver.add_element(n1, n3, E, I, A)
    
    # Load
    solver.add_member_load(b_idx, 20.0)
    
    # Solve
    solver.solve()
    
    if hasattr(solver, 'displacements'):
        print("Solved Successfully!")
        print("Disp Node 1:", solver.displacements[n1*3:n1*3+3])
        forces = solver.get_member_forces(b_idx)
        print("Beam Forces:", forces)
    else:
        print("Solver Failed!")

if __name__ == "__main__":
    test_simple_portal_frame()
