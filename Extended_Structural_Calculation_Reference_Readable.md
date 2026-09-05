# Comprehensive Mathematical & Structural Engine Formulae (CivilApp)

This is the extended, exhaustive reference of every physical, geometrical, and structural equation utilized in the software from start to finish.

---

## 1. DXF Geometry Processing & Auto-Framing

**1.1 Wall Centerline Normalization**
When double lines (representing inner and outer wall faces) are detected, the structural centerline is computed as:
  X_center = (X_inner + X_outer) / 2
  Y_center = (Y_inner + Y_outer) / 2

**1.2 Structural Grid Generation & Snapping**
Nodes are merged if their distance 'd' is less than the snapping tolerance (usually 150mm):
  d = sqrt( (X2 - X1)^2 + (Y2 - Y1)^2 ) <= 150 mm

**1.3 Span Limitation Check**
To prevent uneconomical beam depths, spans are mathematically restricted:
  If L_span > 5000 mm  -->  Insert intermediate column at L/2

---

## 2. Load Takedown & Gravity Calculations

**2.1 Unit Weights (IS 875 Part 1)**
- Reinforced Concrete: 25 kN/m³
- Burnt Clay Brick: 19.2 kN/m³
- AAC Block: 7.5 kN/m³
- Steel: 7850 kg/m³

**2.2 Tributary Area Method (Slab Loads)**
For a grid column at intersection (i, j):
  A_trib = [ (Lx_left + Lx_right)/2 ] * [ (Ly_top + Ly_bottom)/2 ]
  P_slab = A_trib * (Dead_Load + Live_Load)

**2.3 Masonry Wall Loads**
For a beam supporting a wall of height H_story and thickness t_wall:
  w_wall = Density_masonry * t_wall * (H_story - D_beam)  [kN/m]
The nodal point load transferred to columns (half to each end):
  P_wall_transfer = (w_wall * L_span) / 2

**2.4 Load Combinations (IS 456 Table 18)**
- Gravity Limit State: 1.5 * (DL + LL)
- Seismic Limit State: 1.2 * (DL + LL +/- EQ) or 1.5 * (DL +/- EQ)

---

## 3. Finite Element Analysis (FEA) Engine

**3.1 Element Local Stiffness Matrix [k]**
For a 2D frame beam element (axial, shear, moment per node), a 6x6 stiffness matrix is generated:
  [k] = 
  [  EA/L       0          0      -EA/L       0          0      ]
  [   0      12EI/L^3   6EI/L^2     0     -12EI/L^3   6EI/L^2   ]
  [   0      6EI/L^2    4EI/L       0     -6EI/L^2    2EI/L     ]
  [ -EA/L       0          0       EA/L       0          0      ]
  [   0     -12EI/L^3  -6EI/L^2     0      12EI/L^3  -6EI/L^2   ]
  [   0      6EI/L^2    2EI/L       0     -6EI/L^2    4EI/L     ]

**3.2 Fixed End Moments (FEM)**
For a Uniformly Distributed Load 'w' acting on the beam:
  M_FEM_A = (w * L^2) / 12
  M_FEM_B = -(w * L^2) / 12
  V_FEM = (w * L) / 2

**3.3 Global System Solution**
Transformation matrix [T] rotates [k] to global axes:
  [K_global] = [T]^T * [k] * [T]
The system solves for nodal displacements {u} using the inverse stiffness matrix:
  {F} = [K_global] * {u}   -->   {u} = [K_global]^-1 * {F}

---

## 4. Column Design (IS 456:2000)

**4.1 Slenderness Check (Cl. 25.1.2)**
  Slenderness Ratio = L_eff / b_min
  If Ratio < 12, it is a Short Column.

**4.2 Minimum Eccentricity (Cl. 25.4)**
  e_min = L/500 + D/30  (Must be >= 20 mm)

**4.3 Axial Capacity & Steel Sizing (Cl. 39.3)**
Gross concrete area sizing (Before steel):
  P_u <= 0.4 * fck * Ag   -->   Ag_req = P_u / (0.4 * fck)

Solving for longitudinal reinforcement area (Asc):
  P_u = 0.4 * fck * (Ag - Asc) + 0.67 * fy * Asc
  Asc = (P_u - 0.4 * fck * Ag) / (0.67 * fy - 0.4 * fck)

  Limits: 0.8% Ag <= Asc_provided <= 4.0% Ag

---

## 5. Beam Design (IS 456 Annex G)

**5.1 Effective Depth Heuristics**
Using span-to-depth ratios to prevent excessive deflection (Cl 23.2.1):
  D_req = L_span / 12  (Conservative assumption over standard 20)

**5.2 Ultimate Moment Capacity & Neutral Axis**
Depth of neutral axis (xu):
  x_u = (0.87 * fy * Ast) / (0.36 * fck * b)

Limiting neutral axis depth for Fe415 steel:
  x_u_max = 0.48 * d

Moment of Resistance (Mu):
  M_u = 0.87 * fy * Ast * d * [ 1 - (Ast * fy)/(b * d * fck) ]

**5.3 Shear Design (Stirrups)**
Nominal shear stress:
  Tau_v = V_u / (b * d)

Design shear strength of concrete (Tau_c) is interpolated based on:
  p_t = (100 * Ast) / (b * d)

Required shear force for stirrups:
  V_us = V_u - (Tau_c * b * d)

Stirrup spacing Sv:
  S_v = (0.87 * fy * Asv * d) / V_us  (<= 0.75d or 300mm)

---

## 6. Slab Design Basics

**6.1 Thickness Calculation**
  d_slab = L_short / 26  (Continuous)
  d_slab = L_short / 20  (Simply Supported)
  Minimum overall depth = 125 mm or 150 mm

**6.2 Minimum Distribution Steel**
For High Yield Strength Deformed (HYSD) bars (Fe415/Fe500):
  Ast_min = 0.12% * b * D

---

## 7. Isolated Footing Design

**7.1 Base Area Sizing**
Adding 10% self-weight of the footing:
  P_design = P_axial * 1.1
  A_req = P_design / SBC
  Side of square footing B = sqrt(A_req)

**7.2 Punching Shear (Two-Way Shear)**
Critical perimeter is at a distance d/2 from column face.
Allowable shear stress:
  Tau_c = 0.25 * sqrt(fck)  [in N/mm²]

**7.3 Flexure (Bending)**
Moment at the face of the column:
  M_u = (p_net * L_cantilever^2 / 2) * B

---

## 8. Lateral Dynamics: Earthquake (IS 1893:2016)

**8.1 Seismic Weight Calculation**
Live Load reduction based on Table 10:
  W = Sum(DL) + Sum(Fraction * LL)  (Roof LL is always 0%)

**8.2 Fundamental Time Period**
For buildings with masonry infill panels:
  T_a = (0.09 * h) / sqrt(d)

**8.3 Design Base Shear**
Horizontal Seismic Coefficient (Ah):
  A_h = (Z / 2) * (I / R) * (Sa / g)

Total Base Shear:
  V_B = A_h * W

---

## 9. Lateral Dynamics: Wind (IS 875 Part 3)

**9.1 Design Wind Speed**
  V_z = V_b * k1 * k2 * k3 * k4

**9.2 Wind Pressure & Force**
  P_z = 0.6 * V_z^2  [N/m²]
Total story force:
  F = P_z * (Width * Story_Height)

---

## 10. Bar Bending Schedule (BBS) Metrics

**10.1 Development Length (L_d)**
For deformed bars in tension (IS 456 Cl. 26.2.1):
  L_d = (phi * 0.87 * fy) / (4 * Tau_bd)

**10.2 Cutting Length of Box Stirrups**
For a column of size A x B with clear cover c:
  x = A - 2c  ,  y = B - 2c
  L_cut = 2*(x + y) + 24*phi  (Includes hook length)

---

## 11. Bill of Quantities (BOM) & Cost Calculations

**11.1 Masonry Volume to Unit Conversion**
Number of standard Indian bricks (190x90x90 mm) with 10mm mortar:
  Volume per brick = 0.2 * 0.1 * 0.1 = 0.002 m³
  Bricks per m³ = 1 / 0.002 = 500 bricks

**11.2 Mortar & Plaster Calculations**
Mortar occupies roughly 30% of total brickwork volume:
  V_mortar = V_wall_total * 0.30
Plastering Surface Area (Double-sided):
  A_plaster = (L_wall * H_wall - A_openings) * 2

**11.3 Total Structural Cost Aggregation**
  Cost = (V_conc * 6000) + (W_steel * 70) + (Bricks * 8) + (V_excav * 250)
