# Assumptions Register

**As of:** 2026-10-15. Each assumption is an engineering simplification made
in code. "Effect" states the expected direction where it can be argued; all
remain **UNVERIFIED** until reviewed by a qualified engineer.

| ID | Assumption | Where | Effect / note |
|---|---|---|---|
| A-GEO-01 | A bay is a slab panel if all 4 corners have columns or its centre is enclosed by wall/beam lines | `GridManager.slab_panels` | Irregular CAD plans; may misclassify bays bounded by partial walls |
| A-GEO-02 | Same plan beam layout on every storey (IFC beams de-duplicated) | `bim_loader`, pipeline | Not valid for set-backs / transfer floors |
| A-LOD-01 | Occupancy intensities as in `building_types.py` | | Values to be confirmed against IS 875 |
| A-LOD-02 | Roof parapet = 0.33 × storey wall | `calculate_loads`, `beam_case_loads`, seismic weight | |
| A-LOD-03 | Stair allowance 15 kN/m² (80 % DL / 20 % LL) on the void bay corners | `calculate_trib_areas`, `calculate_loads` | Replaces a stair analysis |
| A-LOD-04 | Moment-equivalent triangular/trapezoidal UDLs for beams | `beam_slab_coefficients` | Over-estimates end shear (conservative) |
| A-LOD-05 | Walls not on a beam go to the nearest parallel beam within 3 m | `beam_wall_loads` | |
| A-LOD-06 | Column gravity axial from tributary takedown, not from the frames | `update_structural_analysis` | Ignores continuity redistribution |
| A-FEA-01 | 2D frames on grid lines; storey forces shared by each frame's condensed lateral stiffness (rigid diaphragm in translation, slab links) since 2026-10-20; no torsion | `update_structural_analysis` | Unconservative for torsionally irregular plans |
| A-FEA-02 | Cracked modifiers 0.70 (columns) / 0.35 (beams) applied to all load cases when enabled (default on) | | |
| A-FEA-03 | Beam self-weight uses web below slab b·(D − t) | | Slab counted over full panel |
| A-SEI-01 | Response spectrum on a rigid-diaphragm 3D model for every building; floor mass centre and rotational inertia from the slab panels; centre of resistance from frame storey stiffness under the static pattern | `pseudo3d.py` | D-26; flexible diaphragms → WARN |
| A-SEI-06 | Soft storey when computed storey stiffness is > 10 % below the storey above | `design_pipeline` | D-27 (approved) |
| A-SEI-02 | With masonry infill the shorter of 0.075h^0.75 and 0.09h/√d (d = larger plan dimension) is used | `calculate_base_shear` | Shorter period → equal or larger Sa |
| A-SEI-03 | R = 3 (OMRF) default; SMRF R = 5 only on user selection with warning | | Decision D-02 |
| A-SEI-04 | Importance factor defaults by occupancy (1.0–1.5) | `importance_for_occupancy` | Decision D-03 |
| A-SEI-05 | Re-entrant projection estimated as √(bbox − footprint) | `run_full_analysis` | Crude screen |
| A-WND-01 | k1 = k3 = 1, Kd = Ka = Kc = k4 = 1; k2 from IS 875-3 Table 2; simplified Cpe | `wind_load.py` | Kd/Ka/Kc = 1 and the Cpe used are conservative for h/w < 6; k3 / k4 must be set by the engineer on slopes / cyclonic coasts |
| A-SEC-01 | Clear spacing ≥ max(φ, 25 mm) (20 mm aggregate) | `choose_bars`, `detail_column` | |
| A-SEC-02 | Slenderness additional moment reduction factor k = 1 | `check_column` | Conservative |
| A-SEC-03 | Effective length = 1.0 × unsupported (storey) length | `detail_columns(le_factor=1.0)` | **Engineering decision needed** (D-04); may be unconservative for sway frames |
| A-BEM-01 | Rectangular beams (no T/L flange action); shear pt = min(top, bottom) | `detail_beam` | Conservative |
| A-BEM-02 | Basic span/d limits without modification factors produce WARN only | `detail_beam` | |
| A-COL-01 | Project minimum 8 bars ≥ 16 mm; ties 150 mm at level 0 | `detail_column` | Practice rule retained |
| A-COL-02 | Project minimum column 300×450; interior > 400 kN → 400×600 (initial sizing) | `optimize_column_sizes` | Practice rule retained; except D-29 wall columns |
| A-COL-03 | Residential columns in 230 mm wall lines: 230 × (450-900) mm, Zone II OMRF only; wall line = wall ≥ 200 mm with centre line within 120 mm of the column centre; junction orientation balanced between x and y | `design_pipeline.apply_wall_width_columns` | D-29 |
| A-SLB-01 | One-way slabs: wl²/8 at span and supports | `detail_slab` | Conservative |
| A-STR-01 | Stair flight spans going + 2 × 1.2 m landings, simply supported | `detail_staircase` | |
| A-FND-01 | Area sizing uses P_service × 1.1 (self-weight + backfill) | `design_footing` | |
| A-FND-02 | Footing sizing ignores base moments (warning only) | `design_footing` | Decision D-06 |
| A-QTY-01 | 4 % steel wastage; 80 kg/m³ footing steel when not designed; 100 kg/m³ stair steel | `quantifier` | |
| A-QTY-02 | Fixed unit rates (INR) and carbon factors | `quantifier` | |
| A-QTY-03 | Nominal cement contents per grade | `quantifier` | Not a mix design |
| A-DUR-01 | Exposure default Moderate; covers = max(Table 16, Table 16A); beams with the continuous fire cover, slabs with the simply supported one | `durability.requirements` | D-21 |
| A-DUR-02 | Fire ratings from NBC Part 4 Table 1 for the chosen type of construction (default Type 2); columns below the top storey "support more than one floor"; columns fully exposed (Fig. 1) | `durability`, `stability` | D-22 |

