"""
2D frame solver (direct stiffness method).

Units: kN, m, kNm.  DOFs per node: (u, v, theta) in the global X-Y plane of the
frame, where global Y is vertical (up).

Conventions (see docs/engineering/units-and-conventions.md):
  * Member end forces are expressed in member-local axes: local x runs from
    node n1 to node n2, local y is local x rotated +90 degrees.
  * Distributed member loads added with ``add_member_load`` are GRAVITY loads:
    a positive value acts in global -Y, irrespective of the direction in which
    the member was defined (fixes audit finding R12).
  * Internal bending moments returned by ``moment_at`` / ``get_member_forces``
    use the structural convention "sagging positive" (tension on the bottom
    face) for horizontal members.  For a horizontal member defined from right
    to left the local sign is flipped back so that results are orientation
    independent.
"""

import math
from typing import Dict, List, Optional, Tuple

import numpy as np

from .logging_config import get_logger

logger = get_logger(__name__)


class FrameSolver2D:
    """Direct stiffness method solver for plane frames."""

    #: Condition number above which the reduced stiffness matrix is treated as
    #: singular / a mechanism (audit finding R23).
    MAX_CONDITION_NUMBER = 1e12

    def __init__(self, fixed_base: bool = True, base_level: float = 0.0):
        self.nodes: List[Tuple[float, float]] = []
        self.elements: List[dict] = []
        self.loads: Dict[int, float] = {}            # {elem_idx: gravity UDL kN/m}
        self.node_loads: Dict[int, List[float]] = {}  # {node_idx: [Fx, Fy, M]}
        self.results: Dict[int, np.ndarray] = {}      # {elem_idx: local end forces}
        self.fixed_base = fixed_base
        self.base_level = base_level
        self.status = "NOT_SOLVED"   # NOT_SOLVED | SOLVED | UNSTABLE | SINGULAR | EMPTY
        self.status_message = ""
        self.displacements: Optional[np.ndarray] = None

    # ------------------------------------------------------------------ model
    def add_node(self, x: float, y: float) -> int:
        self.nodes.append((x, y))
        return len(self.nodes) - 1

    def add_element(self, n1_idx: int, n2_idx: int, E: float, I: float, A: float) -> int:
        self.elements.append({"n1": n1_idx, "n2": n2_idx, "E": E, "I": I, "A": A})
        return len(self.elements) - 1

    def add_member_load(self, elem_idx: int, udl_kn_m: float):
        """Gravity UDL (kN/m, positive = downward, global -Y)."""
        self.loads[elem_idx] = udl_kn_m

    def add_node_load(self, node_idx: int, fx: float = 0.0, fy: float = 0.0, m: float = 0.0):
        cur = self.node_loads.get(node_idx, [0.0, 0.0, 0.0])
        self.node_loads[node_idx] = [cur[0] + fx, cur[1] + fy, cur[2] + m]

    # --------------------------------------------------------------- geometry
    def _geom(self, elem_idx: int) -> Tuple[float, float, float]:
        el = self.elements[elem_idx]
        n1 = self.nodes[el["n1"]]
        n2 = self.nodes[el["n2"]]
        dx = n2[0] - n1[0]
        dy = n2[1] - n1[1]
        L = math.hypot(dx, dy)
        if L < 1e-9:
            raise ValueError(f"Element {elem_idx} has zero length! Nodes: {n1} to {n2}")
        return L, dx / L, dy / L

    def _get_local_stiffness(self, elem_idx: int) -> np.ndarray:
        el = self.elements[elem_idx]
        L, _, _ = self._geom(elem_idx)
        E, I, A = el["E"], el["I"], el["A"]
        a1 = E * A / L
        b1 = 12 * E * I / L**3
        b2 = 6 * E * I / L**2
        b3 = 4 * E * I / L
        b4 = 2 * E * I / L
        return np.array([
            [a1, 0, 0, -a1, 0, 0],
            [0, b1, b2, 0, -b1, b2],
            [0, b2, b3, 0, -b2, b4],
            [-a1, 0, 0, a1, 0, 0],
            [0, -b1, -b2, 0, b1, -b2],
            [0, b2, b4, 0, -b2, b3],
        ])

    def _get_transform_matrix(self, elem_idx: int) -> np.ndarray:
        _, c, s = self._geom(elem_idx)
        R = np.array([[c, s, 0], [-s, c, 0], [0, 0, 1]])
        T = np.zeros((6, 6))
        T[0:3, 0:3] = R
        T[3:6, 3:6] = R
        return T

    def _get_element_stiffness(self, elem_idx: int) -> np.ndarray:
        """Element stiffness in GLOBAL axes (kept for backward compatibility)."""
        T = self._get_transform_matrix(elem_idx)
        return T.T @ self._get_local_stiffness(elem_idx) @ T

    @staticmethod
    def _get_dof_indices(n1: int, n2: int) -> List[int]:
        return [n1 * 3, n1 * 3 + 1, n1 * 3 + 2, n2 * 3, n2 * 3 + 1, n2 * 3 + 2]

    def _local_udl(self, elem_idx: int, w_gravity: float) -> Tuple[float, float]:
        """Resolve a gravity UDL (global -Y, per unit member length) into local
        (axial p, transverse q) components."""
        _, c, s = self._geom(elem_idx)
        # global load per unit length = (0, -w); local x = (c, s); local y = (-s, c)
        p = -w_gravity * s
        q = -w_gravity * c
        return p, q

    def _fixed_end_forces(self, elem_idx: int, w_gravity: float) -> np.ndarray:
        """Fixed-end forces exerted BY the supports ON the member (local axes)."""
        L, _, _ = self._geom(elem_idx)
        p, q = self._local_udl(elem_idx, w_gravity)
        return np.array([
            -p * L / 2.0, -q * L / 2.0, -q * L**2 / 12.0,
            -p * L / 2.0, -q * L / 2.0, q * L**2 / 12.0,
        ])

    def _fixed_dofs(self) -> List[int]:
        fixed = []
        for i, (_, y) in enumerate(self.nodes):
            if abs(y - self.base_level) < 0.01:
                fixed.extend([i * 3, i * 3 + 1])
                if self.fixed_base:
                    fixed.append(i * 3 + 2)
        return fixed

    # ------------------------------------------------------------------ solve
    def solve(self):
        """Solve the single load case defined by ``self.loads`` and
        ``self.node_loads``.  Results stored in ``self.results``."""
        res = self.solve_cases({"_default": (self.loads, self.node_loads)})
        if "_default" in res:
            self.results = res["_default"]["forces"]
            self.displacements = res["_default"]["displacements"]

    def solve_cases(self, cases: Dict[str, Tuple[Dict[int, float], Dict[int, List[float]]]]) -> Dict[str, dict]:
        """Solve several load cases sharing the same stiffness matrix.

        Args:
            cases: {name: (member_gravity_udls, node_loads)}

        Returns:
            {name: {"forces": {elem: local end forces}, "displacements": array}}
            Empty dict if the structure is unstable / singular (``self.status``
            explains why).
        """
        num_nodes = len(self.nodes)
        if num_nodes == 0 or not self.elements:
            self.status = "EMPTY"
            self.status_message = "No nodes or elements"
            return {}
        num_dof = num_nodes * 3
        K = np.zeros((num_dof, num_dof))
        for i, el in enumerate(self.elements):
            idx = self._get_dof_indices(el["n1"], el["n2"])
            K[np.ix_(idx, idx)] += self._get_element_stiffness(i)

        fixed = set(self._fixed_dofs())
        free = [i for i in range(num_dof) if i not in fixed]
        if not free:
            self.status = "EMPTY"
            self.status_message = "All DOFs restrained"
            return {}

        # Mechanism detection: free DOF with no stiffness
        loose = [i for i in free if K[i, i] < 1e-9]
        if loose:
            node_idx = loose[0] // 3
            self.status = "UNSTABLE"
            self.status_message = (
                f"{len(loose)} unrestrained DOF(s) without stiffness, e.g. node {node_idx} "
                f"at {self.nodes[node_idx]} DOF={['X', 'Y', 'Rot'][loose[0] % 3]}"
            )
            logger.error("UNSTABLE frame: %s", self.status_message)
            return {}

        Kr = K[np.ix_(free, free)]
        try:
            cond = np.linalg.cond(Kr)
        except np.linalg.LinAlgError:
            cond = float("inf")
        if not np.isfinite(cond) or cond > self.MAX_CONDITION_NUMBER:
            self.status = "SINGULAR"
            self.status_message = f"Stiffness matrix ill-conditioned (cond={cond:.2e}); possible mechanism"
            logger.error("Frame solve aborted: %s", self.status_message)
            return {}

        names = list(cases.keys())
        F = np.zeros((num_dof, len(names)))
        fea_cache: Dict[str, Dict[int, np.ndarray]] = {}
        for j, name in enumerate(names):
            udls, nloads = cases[name]
            fea_cache[name] = {}
            for e, w in (udls or {}).items():
                if not w:
                    continue
                fer = self._fixed_end_forces(e, w)
                fea_cache[name][e] = fer
                T = self._get_transform_matrix(e)
                idx = self._get_dof_indices(self.elements[e]["n1"], self.elements[e]["n2"])
                F[idx, j] -= T.T @ fer
            for n, (fx, fy, m) in (nloads or {}).items():
                F[n * 3, j] += fx
                F[n * 3 + 1, j] += fy
                F[n * 3 + 2, j] += m

        try:
            Dr = np.linalg.solve(Kr, F[free, :])
        except np.linalg.LinAlgError:
            self.status = "SINGULAR"
            self.status_message = "Matrix singular"
            logger.error("Matrix singular! Check stability.")
            return {}

        out = {}
        for j, name in enumerate(names):
            D = np.zeros(num_dof)
            D[free] = Dr[:, j]
            forces = {}
            for i, el in enumerate(self.elements):
                idx = self._get_dof_indices(el["n1"], el["n2"])
                f = self._get_local_stiffness(i) @ (self._get_transform_matrix(i) @ D[idx])
                if i in fea_cache[name]:
                    f = f + fea_cache[name][i]
                forces[i] = f
            out[name] = {"forces": forces, "displacements": D, "udls": dict(cases[name][0] or {})}
        self.status = "SOLVED"
        self.status_message = ""
        return out

    # -------------------------------------------------------- post-processing
    def moment_at(self, elem_idx: int, x: float, forces: Optional[np.ndarray] = None,
                  w_gravity: Optional[float] = None) -> float:
        """Internal bending moment at distance x from n1 (sagging positive for
        horizontal members, see module docstring)."""
        f = self.results[elem_idx] if forces is None else forces
        w = self.loads.get(elem_idx, 0.0) if w_gravity is None else w_gravity
        _, c, _ = self._geom(elem_idx)
        _, q = self._local_udl(elem_idx, w)
        m_local = -f[2] + f[1] * x + q * x * x / 2.0
        # Express in the frame's "sagging positive" sense for members that run
        # right-to-left (c < 0); vertical members keep the local sign.
        return -m_local if c < -1e-9 else m_local

    def get_member_forces(self, elem_idx: int, forces: Optional[np.ndarray] = None,
                          w_gravity: Optional[float] = None, stations: int = 21) -> dict:
        """Envelope of internal forces along one member for one load case.

        Returns keys: max_moment (largest absolute moment), max_sagging (>= 0),
        max_hogging (>= 0, magnitude of the most negative moment),
        max_shear, axial (compression positive), m_end1, m_end2 (internal
        moments at the two ends, sign as ``moment_at``).
        """
        if forces is None and elem_idx not in self.results:
            return {}
        f = self.results[elem_idx] if forces is None else forces
        L, _, _ = self._geom(elem_idx)
        ms = [self.moment_at(elem_idx, L * k / (stations - 1), f, w_gravity) for k in range(stations)]
        return {
            "max_moment": max(abs(m) for m in ms),
            "max_sagging": max(0.0, max(ms)),
            "max_hogging": max(0.0, -min(ms)),
            "max_shear": max(abs(f[1]), abs(f[4])),
            "axial": float(f[0]),
            "m_end1": ms[0],
            "m_end2": ms[-1],
        }
