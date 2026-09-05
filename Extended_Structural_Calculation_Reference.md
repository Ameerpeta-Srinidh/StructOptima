# Comprehensive Mathematical & Structural Engine Formulae (CivilApp)

This is the extended, exhaustive reference of every physical, geometrical, and structural equation utilized in the software from start to finish.

---

## 1. DXF Geometry Processing & Auto-Framing

**1.1 Wall Centerline Normalization**
When double lines (representing inner and outer wall faces) are detected, the structural centerline is computed as:
\[ X_{center} = \frac{X_{inner} + X_{outer}}{2} \quad , \quad Y_{center} = \frac{Y_{inner} + Y_{outer}}{2} \]

**1.2 Structural Grid Generation & Snapping**
Nodes are merged if their distance $d$ is less than the snapping tolerance (usually 150mm):
\[ d = \sqrt{(X_2 - X_1)^2 + (Y_2 - Y_1)^2} \le 150 \text{ mm} \]

**1.3 Span Limitation Check**
To prevent uneconomical beam depths, spans are mathematically restricted:
\[ \text{If } L_{span} > 5000 \text{ mm} \implies \text{Insert intermediate column at } L/2 \]

---

## 2. Load Takedown & Gravity Calculations

**2.1 Unit Weights (IS 875 Part 1)**
- Reinforced Concrete ($\gamma_c$): $25 \text{ kN/m}^3$
- Burnt Clay Brick ($\gamma_{brick}$): $19.2 \text{ kN/m}^3$
- AAC Block ($\gamma_{aac}$): $7.5 \text{ kN/m}^3$
- Steel ($\gamma_s$): $7850 \text{ kg/m}^3$

**2.2 Tributary Area Method (Slab Loads)**
For a grid column at intersection $(i, j)$:
\[ A_{trib} = \left(\frac{L_{x,left} + L_{x,right}}{2}\right) \times \left(\frac{L_{y,top} + L_{y,bottom}}{2}\right) \]
\[ P_{slab} = A_{trib} \times (\text{Dead Load} + \text{Live Load}) \]

**2.3 Masonry Wall Loads**
For a beam supporting a wall of height $H_{story}$ and thickness $t_{wall}$:
\[ w_{wall} = \gamma_{masonry} \times t_{wall} \times (H_{story} - D_{beam}) \text{ [kN/m]} \]
The nodal point load transferred to columns (half to each end):
\[ P_{wall\_transfer} = \frac{w_{wall} \times L_{span}}{2} \]

**2.4 Load Combinations (IS 456 Table 18)**
- Gravity Limit State: $1.5 \times (DL + LL)$
- Seismic Limit State: $1.2 \times (DL + LL \pm EQ)$ or $1.5 \times (DL \pm EQ)$

---

## 3. Finite Element Analysis (FEA) Engine

**3.1 Element Local Stiffness Matrix $[k]$**
For a 2D frame beam element (degrees of freedom: axial, shear, moment per node), a 6x6 stiffness matrix is generated:
\[
[k] = \begin{bmatrix}
\frac{EA}{L} & 0 & 0 & -\frac{EA}{L} & 0 & 0 \\
0 & \frac{12EI}{L^3} & \frac{6EI}{L^2} & 0 & -\frac{12EI}{L^3} & \frac{6EI}{L^2} \\
0 & \frac{6EI}{L^2} & \frac{4EI}{L} & 0 & -\frac{6EI}{L^2} & \frac{2EI}{L} \\
-\frac{EA}{L} & 0 & 0 & \frac{EA}{L} & 0 & 0 \\
0 & -\frac{12EI}{L^3} & -\frac{6EI}{L^2} & 0 & \frac{12EI}{L^3} & -\frac{6EI}{L^2} \\
0 & \frac{6EI}{L^2} & \frac{2EI}{L} & 0 & -\frac{6EI}{L^2} & \frac{4EI}{L}
\end{bmatrix}
\]

**3.2 Fixed End Moments (FEM)**
For a Uniformly Distributed Load $w$ acting on the beam:
\[ M_{FEM,A} = \frac{w L^2}{12} \quad , \quad M_{FEM,B} = -\frac{w L^2}{12} \]
\[ V_{FEM} = \frac{w L}{2} \]

**3.3 Global System Solution**
Transformation matrix $[T]$ rotates $[k]$ to global axes:
\[ [K_{global}] = [T]^T [k] [T] \]
The system solves for nodal displacements $\{u\}$ using the inverse stiffness matrix:
\[ \{F\} = [K_{global}] \{u\} \implies \{u\} = [K_{global}]^{-1} \{F\} \]
Member forces are then retrieved: $\{f\} = [k] [T] \{u\} + \{f_{FEM}\}$

---

## 4. Column Design (IS 456:2000)

**4.1 Slenderness Check (Cl. 25.1.2)**
\[ \lambda = \frac{L_{eff}}{b_{min}} \]
If $\lambda < 12$, it is a Short Column. (App enforces short column mechanics for standard floors).

**4.2 Minimum Eccentricity (Cl. 25.4)**
\[ e_{min} = \frac{L}{500} + \frac{D}{30} \ge 20 \text{ mm} \]

**4.3 Axial Capacity & Steel Sizing (Cl. 39.3)**
Gross concrete area sizing (Before steel):
\[ P_u \le 0.4 f_{ck} A_g \implies A_{g,req} = \frac{P_u}{0.4 f_{ck}} \]
Solving for longitudinal reinforcement area ($A_{sc}$):
\[ P_u = 0.4 f_{ck} (A_g - A_{sc}) + 0.67 f_y A_{sc} \]
\[ A_{sc} = \frac{P_u - 0.4 f_{ck} A_g}{0.67 f_y - 0.4 f_{ck}} \]
Limits: $\max(0.008 A_g, A_{sc}) \le A_{prov} \le 0.04 A_g$

---

## 5. Beam Design (IS 456 Annex G)

**5.1 Effective Depth Heuristics**
Using span-to-depth ratios to prevent excessive deflection (Cl 23.2.1):
\[ D_{req} = \frac{L_{span}}{12} \text{ (Conservative assumption over standard 20)} \]

**5.2 Ultimate Moment Capacity & Neutral Axis**
Depth of neutral axis ($x_u$):
\[ x_u = \frac{0.87 f_y A_{st}}{0.36 f_{ck} b} \]
Limiting neutral axis depth for Fe415 steel:
\[ x_{u,max} = 0.48 d \]
Moment of Resistance ($M_u$):
\[ M_u = 0.87 f_y A_{st} d \left(1 - \frac{A_{st} f_y}{b d f_{ck}}\right) \]
*If $x_u > x_{u,max}$, the section must be redesigned as doubly reinforced.*

**5.3 Shear Design (Stirrups)**
Nominal shear stress:
\[ \tau_v = \frac{V_u}{b d} \]
Max allowable concrete shear $\tau_{c,max}$ (Table 20): e.g., $3.1 \text{ MPa}$ for M25. If $\tau_v > \tau_{c,max}$, section size must increase.
Design shear strength of concrete $\tau_c$ (Table 19) is interpolated based on:
\[ p_t = \frac{100 A_{st}}{b d} \]
Required shear force for stirrups:
\[ V_{us} = V_u - \tau_c b d \]
Stirrup spacing $S_v$:
\[ S_v = \frac{0.87 f_y A_{sv} d}{V_{us}} \le \min(0.75d, 300\text{mm}) \]

---

## 6. Slab Design Basics

**6.1 Thickness Calculation**
\[ d_{slab} = \frac{L_{short}}{26} \text{ (Continuous)} \quad \text{or} \quad \frac{L_{short}}{20} \text{ (Simply Supported)} \]
Minimum overall depth $D_{slab} = 125\text{ mm}$ or $150\text{ mm}$.

**6.2 Minimum Distribution Steel**
For High Yield Strength Deformed (HYSD) bars (Fe415/Fe500):
\[ A_{st,min} = 0.12\% \times b \times D \]

---

## 7. Isolated Footing Design

**7.1 Base Area Sizing**
Adding $10\%$ self-weight of the footing:
\[ P_{design} = P_{axial} \times 1.1 \]
\[ A_{req} = \frac{P_{design}}{SBC} \]
Side of square footing: $B = \sqrt{A_{req}}$

**7.2 Punching Shear (Two-Way Shear)**
Critical perimeter is at a distance $d/2$ from column face.
Allowable shear stress:
\[ \tau_c = 0.25 \sqrt{f_{ck}} \text{ (in N/mm}^2\text{)} \]
Actual punching stress check:
\[ \tau_v = \frac{P_u - (\text{Soil Pressure} \times \text{Critical Area})}{\text{Perimeter} \times d} \le \tau_c \]

**7.3 Flexure (Bending)**
Moment at the face of the column:
\[ M_u = \frac{p_{net} \times L_{cantilever}^2}{2} \times B \]

---

## 8. Lateral Dynamics: Earthquake (IS 1893:2016)

**8.1 Seismic Weight Calculation**
Live Load reduction based on Table 10:
- If $LL \le 3 \text{ kN/m}^2$, use $25\%$ of LL.
- If $LL > 3 \text{ kN/m}^2$, use $50\%$ of LL.
- Roof LL is always $0\%$.
\[ W = \sum DL + \sum (\text{fraction} \times LL) \]

**8.2 Fundamental Time Period**
For buildings with masonry infill panels:
\[ T_a = \frac{0.09 \times h}{\sqrt{d}} \]
*(where $h$ is total height, $d$ is base dimension along earthquake direction).*

**8.3 Design Base Shear**
Horizontal Seismic Coefficient $A_h$:
\[ A_h = \frac{Z}{2} \times \frac{I}{R} \times \frac{S_a}{g} \]
Total Base Shear:
\[ V_B = A_h \times W \]

**8.4 Vertical Distribution of Base Shear**
Force at floor $i$:
\[ Q_i = V_B \frac{W_i h_i^2}{\sum W_j h_j^2} \]

---

## 9. Lateral Dynamics: Wind (IS 875 Part 3)

**9.1 Design Wind Speed**
\[ V_z = V_b \times k_1 \times k_2 \times k_3 \times k_4 \]
- $V_b$: Basic wind speed of the region
- $k_1$: Probability / Risk factor
- $k_2$: Terrain and height multiplier
- $k_3$: Topography factor
- $k_4$: Importance factor for cyclonic regions

**9.2 Wind Pressure & Force**
\[ P_z = 0.6 \times V_z^2 \text{ [N/m}^2\text{]} \]
Total story force:
\[ F = P_z \times (\text{Width} \times \text{Story Height}) \]

---

## 10. Bar Bending Schedule (BBS) Metrics

**10.1 Development Length ($L_d$)**
For deformed bars in tension (IS 456 Cl. 26.2.1):
\[ L_d = \frac{\phi \times 0.87 f_y}{4 \times \tau_{bd}} \]
*(Note: $\tau_{bd}$ is increased by 60% for deformed bars, and 25% if in compression).*

**10.2 Cutting Length of Box Stirrups**
For a column of size $A \times B$ with clear cover $c$:
\[ x = A - 2c , \quad y = B - 2c \]
\[ L_{cut} = 2(x + y) + 24\phi \text{ (Hook length)} \]

---

## 11. Bill of Quantities (BOM) & Cost Calculations

**11.1 Masonry Volume to Unit Conversion**
Number of standard Indian bricks ($190 \times 90 \times 90$ mm) with $10\text{mm}$ mortar:
\[ \text{Volume per brick with mortar} = 0.2 \times 0.1 \times 0.1 = 0.002 \text{ m}^3 \]
\[ \text{Bricks per } m^3 = \frac{1}{0.002} = 500 \text{ bricks} \]

**11.2 Mortar & Plaster Calculations**
Mortar occupies roughly $30\%$ of total brickwork volume:
\[ V_{mortar} = V_{wall\_total} \times 0.30 \]
Plastering Surface Area (Double-sided):
\[ A_{plaster} = (L_{wall} \times H_{wall} - A_{openings}) \times 2 \]

**11.3 Total Structural Cost Aggregation**
\[ C_{total} = (V_{concrete} \times C_{conc\_rate}) + (W_{steel} \times C_{steel\_rate}) + (\text{Bricks} \times C_{brick}) + (V_{excavation} \times C_{excavation}) + \text{Overrides} \]
