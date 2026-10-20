"""
Rigid-diaphragm 3D model and IS 1893 dynamic procedures (src/pseudo3d.py) against hand calculations.
"""
import math

import numpy as np
import pytest

from src import pseudo3d as p3

L = 10.0      # square plan, m
K = 1000.0    # lateral stiffness of one single-storey frame, kN/m


def _single_storey(k_xz=(K, K), k_yz=(K, K), w=1000.0):
    frames = [p3.Frame("XZ@0", "XZ", 0.0, np.array([[k_xz[0]]])), p3.Frame("XZ@L", "XZ", L, np.array([[k_xz[1]]])),
              p3.Frame("YZ@0", "YZ", 0.0, np.array([[k_yz[0]]])), p3.Frame("YZ@L", "YZ", L, np.array([[k_yz[1]]]))]
    floors = [p3.Floor(weight_kn=w, xcm=L / 2, ycm=L / 2, r2=(L * L + L * L) / 12.0)]
    return frames, floors, p3.assemble(frames, 1)


def test_symmetric_building_accidental_eccentricity():
    # hand: e_s = 0, e_d = +/- 0.05 L; M = 0.05 F L; K_theta about the centre = 4 K (L/2)^2 = K L^2
    # extra force on an X frame = K (L/2) M / K_theta = 0.025 F -> 0.525 F on the worse frame, +/-0.025 F on Y frames
    frames, floors, K3 = _single_storey()
    r = p3.design_direction("X", "static", frames, floors, K3, np.array([100.0]), 100.0, L, (0.0, L),
                            lambda t: 0.1)
    xz = sorted(abs(r.frame_forces[k][0]) for k in ("XZ@0", "XZ@L"))
    assert xz[1] == pytest.approx(52.5, rel=1e-9)
    assert abs(r.frame_forces["YZ@0"][0]) == pytest.approx(2.5, rel=1e-9)
    assert r.torsion_ratio == pytest.approx(0.525 / 0.5, rel=1e-9)


def test_eccentric_stiffness_matches_hand_formula():
    k1, k2 = K, 3 * K                    # X frames at y = 0 and y = L
    frames, floors, K3 = _single_storey(k_xz=(k1, k2))
    F = 100.0
    r = p3.design_direction("X", "static", frames, floors, K3, np.array([F]), F, L, (0.0, L), lambda t: 0.1)
    ycr = k2 * L / (k1 + k2)                       # 0.75 L
    es = L / 2 - ycr                                # -0.25 L
    k_theta = k1 * ycr ** 2 + k2 * (L - ycr) ** 2 + 2 * K * (L / 2) ** 2
    best = {}
    for ed in (1.5 * es - 0.05 * L, es + 0.05 * L):          # s = -1
        # force applied at y_cr + e_d: f_i = k_i F / sum k + k_i (y_i - y_cr) F e_d / K_theta
        f1 = k1 / (k1 + k2) * F + k1 * (0.0 - ycr) * F * ed / k_theta
        f2 = k2 / (k1 + k2) * F + k2 * (L - ycr) * F * ed / k_theta
        for key, f in (("XZ@0", f1), ("XZ@L", f2)):
            best[key] = max(best.get(key, 0.0), abs(f))
    for key in ("XZ@0", "XZ@L"):
        assert abs(r.frame_forces[key][0]) == pytest.approx(best[key], rel=1e-9)
    assert r.eccentricity_m[0][0] == pytest.approx(es)
    assert abs(r.frame_forces["XZ@0"][0]) == pytest.approx(50.5, rel=1e-9)     # worked by hand: 25 + 25.5


def test_two_storey_shear_building_periods():
    # each X frame: storey stiffness k/2 -> building K = k [[2, -1], [-1, 1]]; masses m: w^2 = (k/m)(3 -/+ sqrt5)/2
    k, w = 20000.0, 500.0
    kf = 0.5 * k * np.array([[2.0, -1.0], [-1.0, 1.0]])
    frames = [p3.Frame("XZ@0", "XZ", 0.0, kf), p3.Frame("XZ@L", "XZ", L, kf),
              p3.Frame("YZ@0", "YZ", 0.0, 3 * kf), p3.Frame("YZ@L", "YZ", L, 3 * kf)]
    floors = [p3.Floor(w, L / 2, L / 2, L * L / 6.0)] * 2
    K3, M3 = p3.assemble(frames, 2), p3.mass_matrix(floors)
    omega, phi, modes = p3.modes(K3, M3, floors)
    m = w / p3.G
    expected = sorted(2 * math.pi / math.sqrt(k / m * (3 + s * math.sqrt(5)) / 2) for s in (-1, 1))[::-1]
    tx = [md.period_s for md in modes if md.kind == "X"]
    assert tx == pytest.approx(expected, rel=1e-9)
    assert sum(md.mass_x for md in modes) == pytest.approx(1.0, rel=1e-9)


def test_single_storey_response_spectrum_equals_ah_w():
    frames, floors, K3 = _single_storey()
    M3 = p3.mass_matrix(floors)
    modal = p3.modes(K3, M3, floors)
    T = 2 * math.pi / math.sqrt(2 * K / (1000.0 / p3.G))
    ah = lambda t: 0.08 * (1.0 if t > 0.4 else 2.5)
    r = p3.design_direction("X", "response spectrum", frames, floors, K3, np.array([1.0]), 0.0, L, (0.0, L), ah,
                            modal=modal)
    assert r.base_shear_dynamic_kn == pytest.approx(ah(T) * 1000.0, rel=1e-6)
    assert r.scale_factor == 1.0 and r.mass_90pc == pytest.approx(1.0)


def test_scaling_to_static_base_shear():   # IS 1893 7.7.3
    frames, floors, K3 = _single_storey()
    modal = p3.modes(K3, p3.mass_matrix(floors), floors)
    r = p3.design_direction("X", "response spectrum", frames, floors, K3, np.array([1.0]), 500.0, L, (0.0, L),
                            lambda t: 0.1, modal=modal)
    assert r.scale_factor == pytest.approx(500.0 / 100.0)
    assert r.base_shear_kn == pytest.approx(500.0)


def test_cqc_reduces_to_srss_for_separated_modes():
    vals = np.array([[3.0], [4.0]])
    assert p3.cqc(vals, np.array([1.0, 30.0]))[0] == pytest.approx(5.0, rel=1e-3)
    # identical frequencies: fully correlated -> algebraic sum
    assert p3.cqc(vals, np.array([5.0, 5.0]))[0] == pytest.approx(7.0, rel=1e-9)


def test_unstable_rotation_detected():
    frames = [p3.Frame("XZ@0", "XZ", 0.0, np.array([[K]])), p3.Frame("YZ@0", "YZ", 0.0, np.array([[K]]))]
    assert not p3.is_stable(p3.assemble(frames, 1))       # one frame per direction: no torsional stiffness
    assert p3.is_stable(_single_storey()[2])
