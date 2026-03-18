
import numpy as np
import math
from typing import List, Dict, Optional, Tuple
from .logging_config import get_logger

logger = get_logger(__name__)

class FrameSolver2D:
    """
    Direct Stiffness Method Solver for 2D Frames.
    DOFs per node: 3 (u, v, theta).
    Units: kN, m, kNm.
    """
    def __init__(self):
        self.nodes = [] # List of (x, y) tuples
        self.elements = [] # List of dicts {n1, n2, E, I, A}
        self.loads = {} # {element_index: udl_kn_m}
        self.node_loads = {} # {node_idx: [Fx, Fy, M]} - Not used much for UDL dominant
        self.results = {} # {elem_idx: forces}
        
    def add_node(self, x: float, y: float) -> int:
        self.nodes.append((x, y))
        return len(self.nodes) - 1
        
    def add_element(self, n1_idx: int, n2_idx: int, E: float, I: float, A: float) -> int:
        self.elements.append({
            "n1": n1_idx,
            "n2": n2_idx,
            "E": E,
            "I": I,
            "A": A
        })
        return len(self.elements) - 1
        
    def add_member_load(self, elem_idx: int, udl_kn_m: float):
        self.loads[elem_idx] = udl_kn_m
        
    def solve(self):
        num_nodes = len(self.nodes)
        num_dof = num_nodes * 3
        
        K_global = np.zeros((num_dof, num_dof))
        F_global = np.zeros(num_dof)
        
        # 1. Assemble Stiffness Matrix
        for i, el in enumerate(self.elements):
            k_local = self._get_element_stiffness(i)
            dof_indices = self._get_dof_indices(el['n1'], el['n2'])
            
            # Add to Global K
            for r in range(6):
                for c in range(6):
                    row = dof_indices[r]
                    col = dof_indices[c]
                    K_global[row, col] += k_local[r, c]
                    
        # 2. Load Vector (Fixed End Actions)
        # Convert Member UDL to Nodal Forces (Global)
        self.fixed_end_actions = {} # Store for post-processing {elem_idx: local_force_vector}
        
        for i, udl in self.loads.items():
            if udl == 0: continue
            
            # Local FER (Fixed End Reactions)
            # Vector = [Fx1, Fy1, M1, Fx2, Fy2, M2]
            # UDL (w) corresponds to local y-axis downwards usually? 
            # Assume local y is perpendicular to beam.
            
            # Length
            n1 = self.nodes[self.elements[i]['n1']]
            n2 = self.nodes[self.elements[i]['n2']]
            L = math.sqrt((n2[0]-n1[0])**2 + (n2[1]-n1[1])**2)
            
            # Fixed End Moments/Shears (Standard wL^2/12)
            # Reaction is UP (+y local), Moment is CCW (+).
            # Left Node: Fy = wL/2, M = wL^2/12
            # Right Node: Fy = wL/2, M = -wL^2/12
            
            # Note: Input UDL is usually gravity (downwards). 
            # If our local y is up, then force is -w * L.
            # Let's assume UDL is positive value acting DOWN (Load).
            # So Reaction is UP (+) wL/2.
            # Fixed End Moment (Reaction from support to beam):
            # Left: +wL^2/12 (CCW) 
            # Right: -wL^2/12 (CW)
            
            w = udl 
            r_shear = w * L / 2.0
            r_moment = (w * L**2) / 12.0
            
            # Fixed End Reactions (Forces applied BY support ON member)
            fer_local = np.array([0, r_shear, r_moment, 0, r_shear, -r_moment])
            
            self.fixed_end_actions[i] = fer_local
            
            # Equivalent Nodal Forces (Action ON Node = - Reaction)
            # We need to transform these to Global Frame before subtracting from F_global
            
            T = self._get_transform_matrix(i)
            fer_global = T.T @ fer_local # F_global = T_transpose * F_local
            
            # Add neg of reaction to Nodal Load Vector (Equivalent Load)
            dof_indices = self._get_dof_indices(self.elements[i]['n1'], self.elements[i]['n2'])
            for r in range(6):
                idx = dof_indices[r]
                F_global[idx] -= fer_global[r]
                
        # 3. Boundary Conditions
        # Assume nodes at y=0 are FIXED supports (classic building frame assumption)
        fixed_dofs = []
        for i, (x, y) in enumerate(self.nodes):
            if abs(y) < 0.01: # Base
                base_idx = i * 3
                fixed_dofs.extend([base_idx, base_idx+1, base_idx+2])
                
        # Reduce Matrix
        free_dofs = [i for i in range(num_dof) if i not in fixed_dofs]
        
        if not free_dofs:
            return # Trivial
            
        # Check for mechanisms / floating nodes
        for i in free_dofs:
            if K_global[i, i] < 1e-4:
                node_idx = i // 3
                dof_type = ["X", "Y", "Rot"][i % 3]
                node_coords = self.nodes[node_idx]
                logger.error(f"UNSTABLE DOF: Node {node_idx} at {node_coords} DOF={dof_type} (K_ii={K_global[i,i]})")
                logger.error("  This usually means the node is not connected to any stiff element in this direction.")
        
        K_reduced = K_global[np.ix_(free_dofs, free_dofs)]
        F_reduced = F_global[free_dofs]
        
        # Power of Numpy
        try:
            d_reduced = np.linalg.solve(K_reduced, F_reduced)
        except np.linalg.LinAlgError:
            logger.error("Matrix Singular! Check stability.")
            logger.error("DUMPING MODEL FOR DEBUG:")
            for i, n in enumerate(self.nodes):
                logger.error(f"Node {i}: {n}")
            for i, el in enumerate(self.elements):
                logger.error(f"Elem {i}: {el['n1']}->{el['n2']}")
            return

        # map back
        D_global = np.zeros(num_dof)
        D_global[free_dofs] = d_reduced
        
        self.displacements = D_global
        
        # 4. Member End Forces
        for i, el in enumerate(self.elements):
            k_local = self._get_element_stiffness(i)
            T = self._get_transform_matrix(i)
            
            dof_indices = self._get_dof_indices(el['n1'], el['n2'])
            d_global_elem = D_global[dof_indices]
            
            # Transform global disp to local
            d_local = T @ d_global_elem
            
            # F = k * d
            f_local = k_local @ d_local
            
            # Superimpose Fixed End Actions
            if i in self.fixed_end_actions:
                 f_local += self.fixed_end_actions[i]
                 
            self.results[i] = f_local

    def get_member_forces(self, elem_idx: int) -> dict:
        if elem_idx not in self.results: return {}
        
        f = self.results[elem_idx]
        # f = [Fx1, Fy1, M1, Fx2, Fy2, M2]
        
        # Max Moment? 
        # Check ends
        m1 = f[2]
        m2 = f[5]
        
        # Check Mid-span for UDL?
        # Parabolic dip: M_mid = wL^2/8 - (M_avg) approx for simply supported, 
        # but here we have end moments.
        # M(x) = M1 + V1*x - w*x^2/2
        
        n1 = self.nodes[self.elements[elem_idx]['n1']]
        n2 = self.nodes[self.elements[elem_idx]['n2']]
        L = math.sqrt((n2[0]-n1[0])**2 + (n2[1]-n1[1])**2)
        
        w = self.loads.get(elem_idx, 0.0)
        
        # V1 is f[1]
        v1 = f[1]
        
        # Candidate max locations: Ends and where Shear = 0
        # V(x) = V1 - w*x = 0 => x = V1/w
        
        moments = [abs(m1), abs(m2)]
        
        if w != 0:
            x_zero_shear = v1 / w
            if 0 < x_zero_shear < L:
                m_span = m1 + v1*x_zero_shear - (w * x_zero_shear**2)/2.0
                moments.append(abs(m_span))
                
        max_m = max(moments)
        max_v = max(abs(f[1]), abs(f[4]))
        
        return {
            "max_moment": max_m,
            "max_shear": max_v
        }

    def _get_element_stiffness(self, elem_idx: int):
        el = self.elements[elem_idx]
        n1 = self.nodes[el['n1']]
        n2 = self.nodes[el['n2']]
        
        dx = n2[0] - n1[0]
        dy = n2[1] - n1[1]
        L = math.sqrt(dx*dx + dy*dy)
        if L < 1e-9:
             raise ValueError(f"Element {elem_idx} has zero length! Nodes: {n1} to {n2}")
        
        E = el['E'] # kN/m2 (kPa)
        I = el['I'] # m4
        A = el['A'] # m2
        
        # Local Stiffness Matrix (6x6)
        # u1, v1, th1, u2, v2, th2
        k = np.zeros((6, 6))
        
        a1 = (E * A) / L
        b1 = (12 * E * I) / (L**3)
        b2 = (6 * E * I) / (L**2)
        b3 = (4 * E * I) / L
        b4 = (2 * E * I) / L
        
        # Axial
        k[0, 0] = a1; k[0, 3] = -a1
        k[3, 0] = -a1; k[3, 3] = a1
        
        # Bending
        k[1, 1] = b1; k[1, 2] = b2; k[1, 4] = -b1; k[1, 5] = b2
        k[2, 1] = b2; k[2, 2] = b3; k[2, 4] = -b2; k[2, 5] = b4
        k[4, 1] = -b1; k[4, 2] = -b2; k[4, 4] = b1; k[4, 5] = -b2
        k[5, 1] = b2; k[5, 2] = b4; k[5, 4] = -b2; k[5, 5] = b3
        
        # Transform to Global
        T = self._get_transform_matrix(elem_idx)
        k_global = T.T @ k @ T
        return k_global

    def _get_transform_matrix(self, elem_idx: int):
        el = self.elements[elem_idx]
        n1 = self.nodes[el['n1']]
        n2 = self.nodes[el['n2']]
        
        dx = n2[0] - n1[0]
        dy = n2[1] - n1[1]
        L = math.sqrt(dx*dx + dy*dy)
        if L == 0: L = 1e-9
        
        c = dx / L
        s = dy / L
        
        # T = [ R 0 ]
        #     [ 0 R ]
        # R = [ c  s  0 ]
        #     [-s  c  0 ]
        #     [ 0  0  1 ]
        
        T = np.zeros((6, 6))
        
        R = np.array([
            [c, s, 0],
            [-s, c, 0],
            [0, 0, 1]
        ])
        
        T[0:3, 0:3] = R
        T[3:6, 3:6] = R
        
        return T
        
    def _get_dof_indices(self, n1: int, n2: int):
        return [n1*3, n1*3+1, n1*3+2, n2*3, n2*3+1, n2*3+2]
