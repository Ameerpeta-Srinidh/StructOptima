"""
Demonstration of Member Design for Typical Frame Elements
"""

from src.member_design import MemberDesigner

designer = MemberDesigner(concrete_grade="M25", steel_grade="Fe415")

print("=" * 60)
print("STRUCTURAL MEMBER DESIGN - IS 456:2000")
print("=" * 60)

print("\n" + "=" * 60)
print("BEAM B101 (230x450mm)")
print("=" * 60)

beam = designer.design_beam(
    element_id="B101",
    b_mm=230,
    D_mm=450,
    Mu_kNm=85,
    Vu_kN=65
)

print(f"Status: {beam.status.value}")
print(f"Mu = {beam.Mu_kNm:.1f} kNm, Mu_lim = {beam.Mu_lim_kNm:.1f} kNm")
print(f"Type: {beam.reinforcement_type.value}")
print(f"Tension Steel: {beam.Ast_tension_mm2:.0f} mm² → {beam.provided_top}")
print(f"Shear: τv = {beam.tau_v_Nmm2:.2f} N/mm², τc = {beam.tau_c_Nmm2:.2f} N/mm²")
print(f"Stirrups: {beam.provided_stirrups}")

print("\n" + "=" * 60)
print("COLUMN C1 (300x400mm)")
print("=" * 60)

col = designer.design_column(
    element_id="C1",
    b_mm=300,
    D_mm=400,
    L_mm=3000,
    Pu_kN=900,
    Mux_kNm=45,
    Muy_kNm=30,
    steel_percent=1.5
)

print(f"Status: {col.status.value}")
print(f"Pu = {col.Pu_kN:.0f} kN")
print(f"Slenderness: λ = {col.slenderness_ratio:.1f} ({'Slender' if col.is_slender else 'Short'})")
print(f"Min eccentricity: {col.e_min_mm:.1f} mm")
print(f"Interaction Ratio: {col.interaction_ratio:.3f} {'✓' if col.interaction_ratio <= 1.0 else '✗'}")
print(f"Steel: {col.Ast_mm2:.0f} mm² ({col.steel_percent:.1f}%) → {col.provided_steel}")
print(f"Ties: 8mm @ {int(col.tie_spacing_mm)}mm c/c")

print("\n" + "=" * 60)
print("SLAB S1 (4.0m x 5.0m, 150mm thick)")
print("=" * 60)

slab = designer.design_slab(
    element_id="S1",
    Lx_mm=4000,
    Ly_mm=5000,
    thickness_mm=150,
    w_kN_m2=10.5,
    edge_condition="two_adjacent_continuous"
)

print(f"Status: {slab.status.value}")
print(f"Mx = {slab.Mx_kNm_m:.2f} kNm/m, My = {slab.My_kNm_m:.2f} kNm/m")
print(f"Steel X: {slab.Ast_x_mm2_m:.0f} mm²/m → {slab.provided_x}")
print(f"Steel Y: {slab.Ast_y_mm2_m:.0f} mm²/m → {slab.provided_y}")
print(f"L/d = {slab.deflection_ratio:.1f} ({'OK' if slab.deflection_ok else 'FAIL'})")

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"Beam B101: {beam.status.value} - {beam.provided_top}, {beam.provided_stirrups}")
print(f"Column C1: {col.status.value} - IR={col.interaction_ratio:.3f}, {col.provided_steel}")
print(f"Slab S1: {slab.status.value} - {slab.provided_x}, {slab.provided_y}")
