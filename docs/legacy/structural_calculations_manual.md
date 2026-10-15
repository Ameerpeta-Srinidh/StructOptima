# StructOptima: Comprehensive Calculations Manual

This document provides a detailed breakdown of every single calculation, assumption, and formula used at each stage of the application's structural analysis and design pipeline. The pipeline adheres closely to **IS 456:2000** and **IS 13920:2016** (Seismic).

---

## 1. Load Calculations and Combinations

**Location:** `src/calculations.py`

### 1.1 Load Aggregation
Loads are aggregated per structural component (Dead, Live, Superimposed Loads).
- **Formula:** 
  `Factored_Load = (Dead_Load + Superimposed_Load) * 1.5 + Live_Load * 1.5`
- **Assumption:** The standard Limit State of Collapse (Combo 1) from IS 456 is used, yielding a global load factor of 1.5 across standard gravity combinations.

---

## 2. Structural Analysis (Direct Stiffness Method)

**Location:** `src/fea_solver.py`

The application uses a 2D Direct Stiffness Method (DSM) with 3 Degrees of Freedom (u, v, rotation) per node.

### 2.1 Element Stiffness Matrix
For every element, the 6x6 local stiffness matrix is computed using:
- **Axial Stiffness factors:** `A * E / L`
- **Bending Stiffness factors:** `12 * E * I / L^3`, `6 * E * I / L^2`, `4 * E * I / L`, `2 * E * I / L`

### 2.2 Global Transformation
Calculated using the rotation angle (theta) of the member:
```text
Rotation Matrix (R) for each node:
[ cos(theta)   sin(theta)   0 ]
[-sin(theta)   cos(theta)   0 ]
[     0            0        1 ]
```
- **Global K-Matrix:** `K_global = Transpose(T) * k_local * T`

### 2.3 Load Vector and Fixed End Reactions (UDL)
UDL (Uniformly Distributed Load, "w") is applied as fixed-end reactions to the nodes over length "L".
- **Shear Reaction (Fy):** `w * L / 2`
- **Fixed End Moment (M):** `w * L^2 / 12`
- **Equivalent Nodal Force:** Opposite of support reactions.
- **Solve:** The system solves `K_reduced * D_reduced = F_reduced` computationally using numpy's linear algebra solver to find displacements.

---

## 3. Beam Design (Flexure & Shear)

**Location:** `src/member_design.py`

### 3.1 Flexural Design (Moments)
Calculates the limiting moment capacity (`Mu_lim`) of the cross-section to decide if a beam is Singly or Doubly reinforced.
- **Limiting Moment:**
  `Mu_lim = 0.36 * fck * b * d^2 * (xu_max / d) * [1 - 0.42 * (xu_max / d)]`
  - *Where (xu_max / d) represents the limit neutral axis:* `0.53` (Fe250), `0.48` (Fe415), `0.46` (Fe500).

- **Singly Reinforced Area of Steel (Ast):** Used if applied moment (`Mu`) is less than or equal to `Mu_lim`
  `pt = (fck / (2 * fy)) * [ 1 - sqrt(1 - (4.598 * Mu) / (fck * b * d^2)) ] * 100`
  `Ast = (pt * b * d) / 100`

- **Doubly Reinforced:** Used if applied moment (`Mu`) is greater than `Mu_lim`
  Excess moment `Mu2 = Mu - Mu_lim` requires compression steel (`Asc`).
  `Asc = Mu2 / (fsc * (d - d'))`
  *(where `fsc` is the design stress in compression steel, approx `0.87 * fy`)*
  Total tension steel `Ast` = Steel for Mu_lim + Steel for Mu2.

### 3.2 Shear Design
- **Nominal Shear Stress (tau_v):** `tau_v = Vu / (b * d)`
- **Allowable Concrete Shear Stress (tau_c):** Interpolated from IS 456 Table 19 based on percentage steel `pt`.
- **Maximum Shear Stress (tau_c_max):** Fixed limits (e.g., 3.1 MPa for M25). If `tau_v > tau_c_max`, the section **fails** completely and must be resized.

If `tau_v > tau_c`, shear reinforcement (stirrups) is designed:
- **Shear taken by Stirrups (Vus):** `Vus = (tau_v - tau_c) * b * d`
- **Stirrup Spacing (sv):** `sv = (0.87 * fy * Asv * d) / Vus`
- **Assumption:** 8mm diameter 2-legged stirrups are the default (`Asv` ~ 100.5 mm^2). Spacing is strictly capped at `0.75 * d` or `300mm` maximum.

---

## 4. Column Sizing and PM Interaction

**Location:** `src/calculations.py` & `src/member_design.py`

### 4.1 Short Column Axial Capacity (Simplified check)
Used for early-stage pass/fail checks:
- `Pu_capacity = 0.4 * fck * Ac + 0.67 * fy * Asc`
- **Assumption:** Minimum longitudinal steel is conservatively assumed at 0.8% of gross area. 
- **Slenderness ratio (Le / r_min):** If greater than 12, it triggers a warning.

### 4.2 P-M Interaction Algorithm (Detailed Biaxial check)
Operates essentially by calculating the interaction ratio under biaxial bending:
- **Interaction Formula:** `Ratio = (Mux / Mux1)^alpha_n + (Muy / Muy1)^alpha_n` (Needs to be <= 1.0)
- **Plastic capacity (Puz):** `Puz = 0.45 * fck * Ag + 0.75 * fy * Ast`
- **Exponent (alpha_n):** Interpolated between 1.0 (if Pu/Puz <= 0.2) and 2.0 (if Pu/Puz >= 0.8).
- **Minimum Eccentricity Penalty:** `e_min = (L / 500) + (D / 30)`, minimum 20mm. The resulting extra moments (`Pu * e_min`) are evaluated against the current design moment. 
- **Slender Columns:** Receive an additional bending moment calculated via the exact IS 456 deflection multiplier: `M_add = Pu * (L^2 / (2000 * D))`.

---

## 5. Slab Design (Coefficient Method)

**Location:** `src/member_design.py`

Slabs are resolved using the **IS 456 Annex D Allowable Coefficient tables**.
- **Moments:**
  `Mx = alpha_x * w * Lx^2`
  `My = alpha_y * w * Lx^2`
- **Alpha Coefficients:** Dictated by the edge continuity (e.g., *Two adjacent edges continuous*, *All edges continuous*). Defaults to `two_adjacent_continuous` where `alpha_x` is approx 0.047 and `alpha_y` is approx 0.045.
- **Reinforcement:** Moment translates to required steel area exactly like the beam flexure equations. Minimum steel threshold is rigidly set at `0.12%` of Gross Area for Fe415/Fe500 grades.

---

## 6. Foundation Design (Isolated Footings)

**Location:** `src/foundation_eng.py`

### 6.1 Base Area Sizing
- **Required Area:** `Area = (Load * 1.1) / SBC`
- **Assumptions:** A +10% factor accounts for the self-weight of the footing. SBC (Safe Bearing Capacity) defaults to 200 kN/m^2. The footing is strictly enforced to be a square shape (`side = sqrt(Area)`).

### 6.2 Punching Shear / Thickness Iteration
Footing thickness increments upward sequentially in 50mm steps until it passes the punching shear threshold.
- **Critical Perimeter:** Occurs at a distance of `d/2` from the column face.
- **Perimeter Length:** `2 * (Column_width + d) + 2 * (Column_depth + d)`
- **Allowable Shear Stress (tau_allowable):** `0.25 * sqrt(fck)`
- **Actual Shear Stress:** `Stress = Load / (Perimeter * d)`
- **Optimization:** Triggers a fast-break "safety buffer" adding an extra 50mm if the punching stress sits within 5% of the absolute limit for columns exceeding 800kN total load.

---

## 7. Seismic Analysis & Irregularities (IS 1893 & IS 13920)

**Location:** `src/seismic.py`

### 7.1 Seismic Base Shear (Vb)
- **Fundamental Period (Ta):** `Ta = 0.075 * h^0.75` (assuming an RC Moment Resisting Frame).
- **Design Horizontal Acceleration (Ah):** `Ah = (Z / 2) * (I / R) * (Sa / g)`
- **Seismic Weight Calculation:** `Total Dead Load + Reduced Live Load`
  - Live load is reduced by 25% if intensity <= 3.0 kN/m^2
  - Live load is reduced by 50% if intensity > 3.0 kN/m^2

### 7.2 Irregularity Checks
- **Mass Irregularity:** Flags if one storey has > 150% of the mass of the adjacent storey.
- **Soft Storey:** Flags if a floor's stiffness is < 60% of the floor above.
- **Re-entrant Corner:** Triggers if L-shape corners indent > 15% into the total floor's XY footprint.

### 7.3 Strong Column - Weak Beam (SCWB)
IS 13920 requires column capacities to eclipse connected beam capacities to avoid localized joint failure.
- **Check Threshold:** `Sum(Moment_Columns) >= 1.4 * Sum(Moment_Beams)`
- Uses simplified flexure capacities at the 0.4*Pu curve intersection mark to swiftly calculate node ratio checks during early stages.

---

## 8. Material Quantifier & Cost Estimations

**Location:** `src/quantifier.py`

Calculates volumes dimensionally across the structure object-graph:
- **Concrete Mix Ratio (M25):** Exactly assumes a nominal `1:1:2` volume configuration. Yields estimates of 400kg cement, 0.44 m^3 sand, and 0.88 m^3 aggregates per cubic meter.
- **Steel Factor Overrides:** If precision rebar schedules aren't available, default volumetric interpolation acts as fallback:
  - Columns: 150 kg per m^3
  - Beams: 120 kg per m^3
  - Footings: 80 kg per m^3
- **Wastage Factor:** A rigorous `4%` markup is systematically chained across steel calculations representing rolling margin off-cuts.
- **Slab Opening Rule:** Observes IS 1200—Only literal geometric openings exceeding exactly `0.1 m^2` are mathematically deducted from the gross floor concrete volume estimations.

---

> [!NOTE]
> All formulas within the application prioritize limit-state conservative methodology. Where exact computational FEA stress values aren't readily computable, the IS Code's prescriptive worst-case equations are utilized as bounds for ultimate safety.
