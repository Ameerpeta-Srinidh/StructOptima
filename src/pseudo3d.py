"""
Rigid-diaphragm 3D model of a frame building (3 degrees of freedom per floor: ux, uy, rotation about the vertical
axis through the origin) assembled from the condensed lateral stiffness of the plane frames, and the seismic
procedures of IS 1893 (Part 1):2016 that run on it:

- natural modes (7.7.5.1), number of modes for 90 % of the mass (7.7.5.2), CQC combination (7.7.5.3(a)),
  design spectrum for the response spectrum method (6.4.2(b)), scaling to the static base shear (7.7.3);
- design eccentricity e_d = 1.5 e_s + 0.05 b or e_s - 0.05 b (7.8.2) for the static and the response spectrum method;
- torsional irregularity ratio (Table 5(i), Amendment 2) and the torsional / translational period check;
- lateral irregularity of modes (Table 6(vii), Amendment 2).

The floors are rigid in their own plane: flexible diaphragms (re-entrant corners, large openings - Table 5(ii), (iii)
as amended) are outside this model and are reported by the design pipeline.

Units: kN, m, s. Weights in kN; mass = W / g.
"""
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
from scipy.linalg import eigh

G = 9.81
ZETA = 0.05            # IS 1893 7.7.5.3(a): modal damping 5 %


@dataclass
class Frame:
    key: str            # "XZ@0.00" / "YZ@4.50"
    plane: str          # "XZ": frame along X at y = coord; "YZ": along Y at x = coord
    coord: float
    K: np.ndarray       # N x N condensed lateral stiffness at the floor levels (kN/m)


@dataclass
class Floor:
    weight_kn: float
    xcm: float
    ycm: float
    r2: float            # polar radius of gyration squared about the centre of mass (m2)


def transform(frame: Frame, n: int) -> np.ndarray:
    """N x 3N map from floor DOFs (ux, uy, rz per floor) to the frame's in-plane floor displacements."""
    T = np.zeros((n, 3 * n))
    for i in range(n):
        if frame.plane == "XZ":
            T[i, 3 * i] = 1.0
            T[i, 3 * i + 2] = -frame.coord
        else:
            T[i, 3 * i + 1] = 1.0
            T[i, 3 * i + 2] = frame.coord
    return T


def assemble(frames: List[Frame], n: int) -> np.ndarray:
    K3 = np.zeros((3 * n, 3 * n))
    for f in frames:
        T = transform(f, n)
        K3 += T.T @ f.K @ T
    return K3


def mass_matrix(floors: List[Floor]) -> np.ndarray:
    n = len(floors)
    M = np.zeros((3 * n, 3 * n))
    for i, fl in enumerate(floors):
        m = fl.weight_kn / G
        Tcm = np.array([[1.0, 0.0, -fl.ycm], [0.0, 1.0, fl.xcm], [0.0, 0.0, 1.0]])
        M[3 * i:3 * i + 3, 3 * i:3 * i + 3] = Tcm.T @ np.diag([m, m, m * fl.r2]) @ Tcm
    return M


def is_stable(K3: np.ndarray) -> bool:
    """Every floor DOF (both translations and the rotation) restrained by some frame."""
    w = np.linalg.eigvalsh((K3 + K3.T) / 2.0)
    return bool(w.min() > 1e-9 * max(1.0, w.max()))


def has_rotational_mass(M3: np.ndarray) -> bool:
    """Every floor has mass in both translations and in rotation (positive definite mass matrix). A floor without
    slab panels has no rotational inertia: the eigenvalue problem then has no solution (scipy LinAlgError)."""
    try:
        np.linalg.cholesky((M3 + M3.T) / 2.0)
    except np.linalg.LinAlgError:
        return False
    return True


def static_solve(K3: np.ndarray, F: np.ndarray) -> np.ndarray:
    return np.linalg.solve(K3, F)


def frame_forces(frames: List[Frame], U: np.ndarray, n: int) -> Dict[str, np.ndarray]:
    return {f.key: f.K @ (transform(f, n) @ U) for f in frames}


@dataclass
class Mode:
    period_s: float
    kind: str                    # "X", "Y" or "torsion" (largest share of kinetic energy)
    mass_x: float                # effective mass fraction for shaking along X
    mass_y: float


def modes(K3: np.ndarray, M3: np.ndarray, floors: List[Floor]) -> Tuple[np.ndarray, np.ndarray, List[Mode]]:
    """(omega, Phi, mode list) sorted by increasing frequency."""
    w2, phi = eigh(K3, M3)
    w2 = np.clip(w2, 1e-12, None)
    omega = np.sqrt(w2)
    n = len(floors)
    rx, ry = influence(n, "X"), influence(n, "Y")
    mtot = sum(fl.weight_kn for fl in floors) / G
    out = []
    for k in range(len(omega)):
        p = phi[:, k]
        mk = p @ M3 @ p
        tx = ty = tr = 0.0
        for i, fl in enumerate(floors):
            m = fl.weight_kn / G
            ux, uy, rz = p[3 * i], p[3 * i + 1], p[3 * i + 2]
            tx += m * (ux - fl.ycm * rz) ** 2
            ty += m * (uy + fl.xcm * rz) ** 2
            tr += m * fl.r2 * rz ** 2
        kind = ("X", "Y", "torsion")[int(np.argmax([tx, ty, tr]))]
        out.append(Mode(period_s=float(2 * np.pi / omega[k]), kind=kind,
                        mass_x=float((p @ M3 @ rx) ** 2 / mk / mtot), mass_y=float((p @ M3 @ ry) ** 2 / mk / mtot)))
    return omega, phi, out


def influence(n: int, direction: str) -> np.ndarray:
    r = np.zeros(3 * n)
    r[(0 if direction == "X" else 1)::3] = 1.0
    return r


def cqc(values: np.ndarray, omega: np.ndarray) -> np.ndarray:
    """Combine modal responses (modes x quantities) by CQC, IS 1893 7.7.5.3(a), zeta = 0.05."""
    v = np.atleast_2d(values)
    nm = v.shape[0]
    rho = np.empty((nm, nm))
    for i in range(nm):
        for j in range(nm):
            b = omega[j] / omega[i]
            rho[i, j] = 8 * ZETA ** 2 * (1 + b) * b ** 1.5 / ((1 - b * b) ** 2 + 4 * ZETA ** 2 * b * (1 + b) ** 2)
    return np.sqrt(np.clip(np.einsum("iq,ij,jq->q", v, rho, v), 0.0, None))


def storey_shears(floor_forces: np.ndarray) -> np.ndarray:
    """Storey shear in storey i (between floor i-1 and i) = sum of floor forces at floor i and above."""
    return np.cumsum(floor_forces[::-1])[::-1]


def forces_from_shears(v: np.ndarray) -> np.ndarray:
    """7.7.5.4(f): F_roof = V_roof, F_i = V_i - V_(i+1)."""
    return v - np.append(v[1:], 0.0)


@dataclass
class DirectionResult:
    direction: str
    method: str                                   # "static" or "response spectrum"
    base_shear_kn: float                          # design value (after scaling)
    base_shear_dynamic_kn: float = 0.0            # unscaled response spectrum value
    scale_factor: float = 1.0                     # 7.7.3
    storey_forces_kn: List[float] = field(default_factory=list)
    frame_forces: Dict[str, np.ndarray] = field(default_factory=dict)   # design lateral forces per frame
    modes_for_90pc: int = 0
    mass_90pc: float = 0.0
    eccentricity_m: List[Tuple[float, float]] = field(default_factory=list)   # (e_s, e_d governing) per floor
    torsion_ratio: float = 1.0                    # max Delta_max / Delta_ave (Table 5(i))


def centres_of_resistance(frames: List[Frame], pattern: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Floor centres of resistance (x from the YZ frames, y from the XZ frames): storey stiffness of each frame
    under the lateral force pattern, k = V / drift, and the stiffness-weighted frame positions."""
    n = len(pattern)
    v = storey_shears(pattern)
    num = {"XZ": np.zeros(n), "YZ": np.zeros(n)}
    den = {"XZ": np.zeros(n), "YZ": np.zeros(n)}
    for f in frames:
        try:
            u = np.linalg.solve(f.K, pattern)
        except np.linalg.LinAlgError:
            continue
        d = u - np.append(0.0, u[:-1])
        k = np.where(np.abs(d) > 1e-15, v / np.where(np.abs(d) > 1e-15, d, 1.0), 0.0)
        num[f.plane] += k * f.coord
        den[f.plane] += k
    xcr = np.divide(num["YZ"], den["YZ"], out=np.zeros(n), where=den["YZ"] > 0)
    ycr = np.divide(num["XZ"], den["XZ"], out=np.zeros(n), where=den["XZ"] > 0)
    return xcr, ycr


def eccentric_loads(direction: str, forces: np.ndarray, floors: List[Floor], cr: np.ndarray, b: float,
                    extra_only: bool) -> Tuple[List[np.ndarray], List[Tuple[float, float]]]:
    """The two load vectors of IS 1893 7.8.2 for storey forces along ``direction``.

    Forces act at x_cm / y_cm + delta with delta = 0.5 e_s + 0.05 b s (e_d = 1.5 e_s + 0.05 b) or delta = -0.05 b s
    (e_d = e_s - 0.05 b), s = sign of e_s. With ``extra_only`` only the torsional moments of the additional
    eccentricity are returned (response spectrum: e_s is already in the dynamic model)."""
    n = len(floors)
    vecs, ecc = [], []
    deltas = []
    for i, fl in enumerate(floors):
        es = (fl.ycm - cr[i]) if direction == "X" else (fl.xcm - cr[i])
        s = 1.0 if es >= 0 else -1.0
        deltas.append((0.5 * es + 0.05 * b * s, -0.05 * b * s))
        ecc.append((es, 1.5 * es + 0.05 * b * s))
    for case in (0, 1):
        F = np.zeros(3 * n)
        for i, fl in enumerate(floors):
            d = deltas[i][case]
            if direction == "X":
                F[3 * i] = 0.0 if extra_only else forces[i]
                F[3 * i + 2] = -forces[i] * ((0.0 if extra_only else fl.ycm) + d)
            else:
                F[3 * i + 1] = 0.0 if extra_only else forces[i]
                F[3 * i + 2] = forces[i] * ((0.0 if extra_only else fl.xcm) + d)
        vecs.append(F)
    return vecs, ecc


def torsion_ratio(direction: str, U: np.ndarray, extent: Tuple[float, float], n: int) -> float:
    """Table 5(i) (Amd 2): Delta_max / Delta_ave of the total displacements at the two plan ends, max over floors."""
    worst = 1.0
    for i in range(n):
        ux, uy, rz = U[3 * i:3 * i + 3]
        ends = [ux - e * rz for e in extent] if direction == "X" else [uy + e * rz for e in extent]
        dmax, dmin = max(ends, key=abs), min(ends, key=abs)
        if abs(dmax) < 1e-15:
            continue
        dave = (abs(dmax) + (abs(dmin) if np.sign(dmin) == np.sign(dmax) else -abs(dmin))) / 2.0
        worst = max(worst, abs(dmax) / dave if dave > 0 else float("inf"))
    return worst


def design_direction(direction: str, method: str, frames: List[Frame], floors: List[Floor], K3: np.ndarray,
                     static_forces: np.ndarray, vb_static: float, b: float, extent: Tuple[float, float],
                     ah_of_t: Callable[[float], float], modal=None) -> DirectionResult:
    """Design lateral forces on every frame (both planes) for shaking along ``direction``.

    static: storey forces ``static_forces`` (7.6.3) with the two eccentricity cases of 7.8.2;
    response spectrum: CQC of the modal frame responses (all modes), scaled up to ``vb_static`` (7.7.3), plus the
    additional torsion of 7.8.2. Each frame takes the more severe of the two eccentricity cases."""
    n = len(floors)
    xcr, ycr = centres_of_resistance(frames, np.asarray(static_forces, dtype=float))
    cr = ycr if direction == "X" else xcr
    res = DirectionResult(direction=direction, method=method, base_shear_kn=float(np.sum(static_forces)))
    # torsional irregularity ratio under the static forces with e_d = 1.5 e_s + 0.05 b
    vecs, ecc = eccentric_loads(direction, np.asarray(static_forces), floors, cr, b, extra_only=False)
    res.torsion_ratio = torsion_ratio(direction, static_solve(K3, vecs[0]), extent, n)
    res.eccentricity_m = ecc
    if method == "static":
        cases = [frame_forces(frames, static_solve(K3, F), n) for F in vecs]
        res.storey_forces_kn = [float(v) for v in static_forces]
    else:
        omega, phi, mlist = modal
        M3 = mass_matrix(floors)
        r = influence(n, direction)
        per_frame = {f.key: [] for f in frames}
        total_x = []
        for k in range(len(omega)):
            p = phi[:, k]
            gamma = (p @ M3 @ r) / (p @ M3 @ p)
            ah = ah_of_t(2 * np.pi / omega[k])
            Fk = M3 @ p * gamma * ah * G
            Uk = p * gamma * ah * G / omega[k] ** 2
            ff = frame_forces(frames, Uk, n)
            for f in frames:
                per_frame[f.key].append(storey_shears(ff[f.key]))
            total_x.append(storey_shears(Fk[(0 if direction == "X" else 1)::3]))
        v_total = cqc(np.array(total_x), omega)
        res.base_shear_dynamic_kn = float(v_total[0])
        res.scale_factor = max(1.0, vb_static / res.base_shear_dynamic_kn) if res.base_shear_dynamic_kn > 0 else 1.0
        storey = forces_from_shears(v_total) * res.scale_factor
        res.storey_forces_kn = [float(v) for v in storey]
        res.base_shear_kn = float(v_total[0] * res.scale_factor)
        fx = [m.mass_x if direction == "X" else m.mass_y for m in mlist]
        cum = np.cumsum(fx)
        res.modes_for_90pc = int(np.argmax(cum >= 0.9) + 1) if cum[-1] >= 0.9 else len(fx)
        res.mass_90pc = float(cum[res.modes_for_90pc - 1])
        dyn = {k: forces_from_shears(cqc(np.array(v), omega)) * res.scale_factor for k, v in per_frame.items()}
        tvecs, _ = eccentric_loads(direction, storey, floors, cr, b, extra_only=True)
        cases = []
        for F in tvecs:
            tor = frame_forces(frames, static_solve(K3, F), n)
            cases.append({k: dyn[k] + tor[k] for k in dyn})
    for f in frames:
        a, c = cases[0][f.key], cases[1][f.key]
        res.frame_forces[f.key] = a if abs(a.sum()) >= abs(c.sum()) else c
    return res


@dataclass
class RegularityOfModes:
    first3_mass_x: float
    first3_mass_y: float
    t1x: Optional[float]
    t1y: Optional[float]
    t_torsion: Optional[float]


def regularity_of_modes(mlist: List[Mode]) -> RegularityOfModes:
    """Table 6(vii) (Amd 2) quantities and the periods used by Table 5(i)."""
    def first(kind):
        return next((m.period_s for m in mlist if m.kind == kind), None)
    return RegularityOfModes(first3_mass_x=float(sum(m.mass_x for m in mlist[:3])),
                             first3_mass_y=float(sum(m.mass_y for m in mlist[:3])),
                             t1x=first("X"), t1y=first("Y"), t_torsion=first("torsion"))
