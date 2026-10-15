# Calculation Catalogue

**As of:** 2026-10-15 (post-remediation). Formulae are written **as implemented**.
"Std" = standard cited by the code or by this documentation; every clause
reference is **UNVERIFIED** unless the [standards register](standards-register.md)
says otherwise. Status vocabulary: see [../README.md](../README.md#status-vocabulary).
Tests and evidence: [../verification/verification-matrix.md](../verification/verification-matrix.md).

Columns per entry: **Where** (file::symbol) · **Production?** · **Formula** · **Inputs/units** · **Constants & defaults** · **Assumptions** · **Std** · **Tests** · **Status / open questions**.

---

## Geometry

### CAL-GEO-01 Bay selection
- **Where:** `grid_manager.py::GridManager._choose_bay_count`, `generate_grid`. Production (manual input).
- **Formula:** n = max(1, ⌈L / 5.0⌉); if L/n < 3.0 reduce n while L/(n−1) ≤ 5.0. Grid lines at i·L/n.
- **Assumptions:** economical 3–5 m spans (project practice).
- **Tests:** `test_grid_manager.py` (structural). **Status:** UNVERIFIED (practice rule, not a code requirement).

### CAL-GEO-02 Tributary area
- **Where:** `GridManager.calculate_trib_areas`. Production.
- **Formula:** A = (½ left span + ½ right span) × (½ below + ½ above); void bay corner columns lose ¼-bay area and receive a staircase allowance 15 kN/m² × lost area (stored as `staircase_add_load`, split 80 % DL / 20 % LL in the takedown).
- **Assumptions:** no continuity factor for first interior supports; grid lines are added for every column coordinate (CAD).
- **Status:** UNVERIFIED (engineering approximation). Open: continuity factors.

### CAL-GEO-03 Slab panels / footprint
- **Where:** `GridManager.slab_panels`, `footprint_area_m2`. Production.
- **Rule:** bay is a panel if not void and (all four corners have level-0 columns **or** its centre is enclosed on all four sides by wall / beam segments — 4-ray test). Short/long edges and the number of discontinuous edges determined from neighbouring panels.
- **Tests:** `test_audit_findings.py::test_panels_exclude_l_shape_notch_and_keep_enclosed_bays`. **Status:** VERIFIED_FOR_CASES (L-shape notch excluded, enclosed interior bay kept); A-GEO-01.

## Loads

### CAL-LOD-01 Occupancy intensities
- **Where:** `building_types.py` (`RESIDENTIAL` …), `design_pipeline.run_design`. Production.
- **Formula:** floor DL = 25·t_slab + finish + partition + services; floor LL = `live_load_floor_kn_m2`; roof DL = 25·t + finish + services; roof LL = `live_load_roof_kn_m2`; stair LL = `live_load_corridor_kn_m2`.
- **Values (Residential):** LL 2.0, roof 1.5, corridor 3.0, finish 1.0, partitions 1.5, services 0.5 kN/m², t = 125 mm.
- **Std:** IS 875 (Part 1, 2) cited — values **UNVERIFIED**.

### CAL-LOD-02 Wall line load
- **Where:** `grid_manager.py::Wall.line_load_kn_m`. Production.
- **Formula:** w = t·h·(1 − opening_fraction)·γ, γ = 19.2 (brick) / 7.5 (AAC) / 25 (RCC) kN/m³; h = storey − 0.125 − 0.400 m (generated and DXF walls); opening default 0.33.
- **Status:** UNVERIFIED (densities cited to IS 875-1, not checked).

### CAL-LOD-03 Column load takedown (service)
- **Where:** `GridManager.calculate_loads`. Production.
- **Formula per column segment (top-down, cumulative):** DL = A_trib·q_DL(roof/floor) + cantilever slab share + wall share (+ roof parapet = 0.33 × storey wall) + framing beam webs (½ each beam: b·(D−t)·25·L) + column self-weight b·D·h·25 + stair DL; LL = A_trib·q_LL + cantilever + stair LL. `load_kn = DL + LL`. Ground-storey walls → `plinth_load_kn` (to footing). Without walls: `wall_load_kn_m` × half spans.
- **Assumptions:** walls lumped half to the nearest column at each end; same wall layout every storey; column sizes from the previous iteration.
- **Tests:** `test_audit_findings.py::test_R19_takedown_includes_beam_self_weight_and_roof_loads`. **Status:** UNVERIFIED (logic tested, magnitudes not benchmarked against an independent takedown).

### CAL-LOD-04 Beam gravity loads from slab panels
- **Where:** `analysis_integration.py::beam_slab_coefficients`, `beam_case_loads`. Production.
- **Formula:** beam UDL = k·q + wall + b·(D−t)·25. Two-way panel (ly/lx ≤ 2): k = lx/3 (short-edge beam), k = (lx/6)(3 − (lx/ly)²) (long-edge beam); one-way: k = lx/2 on long edges, 0 on short edges; cantilever beams: k = half adjacent grid spacing each side. Contributions of panels either side are summed; a beam spanning several sides takes the maximum.
- **Assumptions:** moment-equivalent UDLs (over-estimate end shear — conservative); walls assigned to the collinear beam or nearest parallel beam within 3 m.
- **Tests:** `test_R2_beam_moments_are_factored_combinations` (statics of a single bay), `test_R3_...`. **Status:** VERIFIED_FOR_CASES (single square bay; manual hand check 2026-10-15 of an 18×12 m edge beam: 21.21 kN/m reproduced).

### CAL-LOD-05 Seismic weight
- **Where:** `design_pipeline.py::storey_seismic_weights`. Production.
- **Formula (level j):** W_j = A_slab·q_DL + Σ beam webs + ½ walls below + ½ walls above (roof: 0.33 × walls) + ½ columns below + ½ columns above + A_slab·q_LL·f (f = 0.25 if q_LL ≤ 3, else 0.5; f = 0 at roof).
- **Std:** IS 1893 (Part 1):2016 Table 10 cited for f — **UNVERIFIED**.
- **Tests:** `test_R7_seismic_weight_includes_masonry`. **Status:** UNVERIFIED.

### CAL-COMB-01 Load combinations
- **Where:** `load_combinations.py::IS_456_COMBINATIONS`; expanded by `analysis_integration.build_combinations`. Production.
- **Set:** 1.5(DL+LL); 1.2(DL+LL±WLx/y); 1.5(DL±WLx/y); 0.9DL±1.5WLx/y; 1.2(DL+LL±EQx/y); 1.5(DL±EQx/y); 0.9DL±1.5EQx/y. Applied linearly to internal-force diagrams.
- **Not implemented:** orthogonal (100 % + 30 %) seismic combination, vertical seismic (available in `VERTICAL_SEISMIC_COMBINATIONS` but not used), LL reduction in seismic combinations.
- **Std:** IS 456 Table 18, IS 1893 — **UNVERIFIED** wording. **Tests:** `test_load_modeling.py`, `test_R8_combinations_include_wind_in_both_directions`.

## Structural analysis

### CAL-FEA-01 Element stiffness and transformation
- **Where:** `fea_solver.py::_get_local_stiffness`, `_get_transform_matrix`, `solve_cases`. Production.
- **Formula:** standard 6×6 plane frame element (EA/L, 12EI/L³, 6EI/L², 4EI/L, 2EI/L); K_global = Tᵀ k T; end forces f = k·(T·d) + FER (local).
- **Units:** E kN/m² (E = 5000√fck × 1000), I m⁴, A m², L m.
- **Tests:** `test_fea_benchmarks.py`, `test_fea_repro.py`. **Status:** VERIFIED_FOR_CASES (fixed-fixed beam, portal statics, slope-deflection portal (axially rigid), cantilever tip deflection, column axial, pinned base, superposition).

### CAL-FEA-02 Gravity UDL fixed-end forces
- **Formula:** local components p = −w·s, q = −w·c of a gravity load w (global −Y); FER = [−pL/2, −qL/2, −qL²/12, −pL/2, −qL/2, +qL²/12].
- **Status:** VERIFIED_FOR_CASES (orientation-independence test, R12).

### CAL-FEA-03 Internal moment
- **Formula:** M_local(x) = −f₂ + f₁·x + q·x²/2; reported "sagging positive" (sign flipped for members with c < 0). Stations: 21 (`get_member_forces`), 11 (combination envelopes).
- **Status:** VERIFIED_FOR_CASES (R10 benchmarks).

### CAL-FEA-04 Frame slicing and lateral load sharing
- **Where:** `update_structural_analysis`. Production.
- **Rule:** XZ frames (constant y) for X-direction lateral load, YZ frames for Y; column I about the frame's bending axis (XZ: D·b³/12; YZ: b·D³/12) × 0.70 if cracked; beam I = b·D³/12 × 0.35 if cracked; storey force share = Σ(12EI/h³) of the frame's columns in the storey below / total of all parallel frames; applied at the leftmost node of the level.
- **Assumptions:** rigid diaphragm, no torsion/accidental eccentricity, column gravity axial from the takedown (frame axial used only for lateral cases).
- **Status:** UNVERIFIED (no reference-program comparison yet — B8 in [benchmark plan](../verification/benchmark-plan.md)).

### CAL-FEA-05 Solvability check
- **Rule:** free DOF with K_ii < 1e-9 → UNSTABLE; cond(K_reduced) > 1e12 → SINGULAR; frame skipped and beams fall back to wL²/8 on both faces.
- **Tests:** `test_mechanism_is_detected_not_solved`. **Status:** VERIFIED_FOR_CASES.

## Seismic (IS 1893 (Part 1):2016, equivalent static)

| ID | Where | Formula / rule | Status |
|---|---|---|---|
| CAL-SEI-01 Spectrum | `SeismicDesignChecker.get_spectral_acceleration` | T < 0.1: 1+15T; plateau 2.5 to T₁ (I 0.40, II 0.55, III 0.67 s); then N/T (N = 1.00, 1.36, 1.67) to 4 s; floor 0.25/0.34/0.42 | UNVERIFIED (transcribed) |
| CAL-SEI-02 Period | `calculate_base_shear` | Ta = 0.075 h^0.75; if masonry infill: Ta = min(that, 0.09 h/√d), d = larger plan dimension (A-SEI-02) | UNVERIFIED |
| CAL-SEI-03 Base shear | `calculate_base_shear` | Ah = (Z/2)(I/R)(Sa/g); Vb = Ah·W; Z = 0.10/0.16/0.24/0.36; R = 3 (OMRF default) or 5 (SMRF) | Formula reproduced in `test_R7_base_shear_depends_on_height_and_weight`; constants UNVERIFIED |
| CAL-SEI-04 Vertical distribution | `run_full_analysis` | Q_i = Vb·W_i h_i² / Σ W_j h_j² | VERIFIED_FOR_CASES (sum = Vb, ratio test) |
| CAL-SEI-05 Importance | `importance_for_occupancy` | Residential 1.0, Office 1.2, Retail 1.5, Institutional 1.5, Assembly 1.5 (UI override) | UNVERIFIED — decision D-03 (proposed) |
| CAL-SEI-06 Regularity / method | `run_full_analysis`, `check_irregularities`, `check_analysis_method` | re-entrant projection estimated as √(bbox − footprint); irregular if > 15 % of plan dimension; static not allowed if irregular or h > 40 m (II/III) / 12 m (IV/V) | UNVERIFIED (crude projection estimate; limits cited, not checked) |
| CAL-SEI-07 SCWB | `seismic.evaluate_joint_checks` | ΣMc ≥ 1.4 ΣMb; Mc = column capacity at min factored Pu (strain compatibility); Mb = 0.36fck·b·xu(d − 0.42xu) with xu = 0.87fy·Ast/(0.36fck·b) ≤ xu,max, from provided top/bottom steel, d = D − 41; worse sway sense | UNVERIFIED; slab steel ignored |
| CAL-SEI-08 Joint shear | same | Vj = 1.25 fy (Ast,top + Ast,bot) (single beam: top only), no column-shear deduction; capacity k√fck·Aj, k = 1.5/1.2/1.0 by beams framing in; Aj = hc·min(bc, bb + hc) | UNVERIFIED (Aj definition and k to be checked against IS 13920:2016) |
| CAL-SEI-09 Ductile spacing | same; `rebar_detailer.detail_column/detail_beam` with `ductile=True` (SMRF) | column end zone lo = max(D, L/6, 450), s ≤ min(b/4, 6db, 100); beam end 2D zone s ≤ min(d/4, 8db, 100); **Ash not checked** | UNVERIFIED, PARTIAL |

## Wind (IS 875 Part 3:2015, static)

| ID | Where | Formula / rule | Status |
|---|---|---|---|
| CAL-WND-01 | `WindLoadCalculator.calculate_k2/…` | Vb by zone 33/39/44/47/50/55 m/s; k2 = k2,10·(z/10)^α (z > 10 m) with (k2,10, α) = (1.05, 0.09), (1.00, 0.14), (0.91, 0.17), (0.80, 0.22); Vz = Vb·k1·k2·k3 (k1 = k3 = 1); pz = 0.6 Vz² N/m² | Power law is an approximation of the code table — UNVERIFIED |
| CAL-WND-02 | `get_external_pressure_coefficients` | Cpe windward 0.8; leeward −0.3/−0.4/−0.5/−0.6 for h/b ≤ 0.5/1/2/>2; Cpi ±0.2/0.5/0.7 by openings | UNVERIFIED (simplified) |
| CAL-WND-03 | `calculate_wind_loads` | storey force at level j: F = pz(z=j·h)·(Cpe,ww + │Cpe,lw│)·B_face·trib, trib = h (h/2 at roof); X-direction face = building length (Y extent) | VERIFIED_FOR_CASES (sum and face-ratio test); Kd, Ka, Kc, k4 not applied (= 1, conservative) |
| CAL-WND-04 | `load_combinations.check_overturning` | stable if 0.9·W·B/2 > 1.5·Σ F·z | UNVERIFIED |

## Section design (IS 456:2000) — `src/section_design.py`

| ID | Symbol | Formula / rule | Status |
|---|---|---|---|
| CAL-SEC-01 | `tau_c`, `tau_c_max` | Table 19 (M20–M40) linear interpolation, pt clamped 0.15–3.0, lower tabulated grade used; Table 20 τc,max | Interpolation VERIFIED_FOR_CASES; table values UNVERIFIED |
| CAL-SEC-02 | `xu_max_ratio`, `mu_lim_knm`, `ast_singly` | xu,max/d = 0.53/0.48/0.46; Mu,lim = 0.36fck·b·d²·k(1 − 0.42k); pt = 50(fck/fy)(1 − √(1 − 4.598R/fck)) | VERIFIED_FOR_CASES (Annex-G relation and stress-block equilibrium within 0.5 %) |
| CAL-SEC-03 | `design_flexure` | Mu > Mu,lim: Ast1 = 0.36fck·b·xu,max/(0.87fy); εsc = 0.0035(1 − d'/xu,max); Asc = (Mu − Mu,lim)/((fsc − 0.446fck)(d − d')); Ast2 = Asc(fsc − 0.446fck)/(0.87fy) | VERIFIED_FOR_CASES (equilibrium) |
| CAL-SEC-04 | `design_shear` | τv = Vu/(b d); FAIL if τv > τc,max; s = min(0.87fy·Asv·d/((τv − τc)b d), 0.87fy·Asv/(0.4b), 0.75d, 300), fy ≤ 415 for stirrups; FAIL if s < 75 mm | VERIFIED_FOR_CASES (rule checks) |
| CAL-SEC-05 | `choose_bars` | smallest bar (12/16/20/25) fitting in 1 then 2 layers with clear spacing ≥ max(φ, 25 mm) | UNVERIFIED (25 mm assumes 20 mm aggregate) |
| CAL-SEC-06 | `steel_stress`, `concrete_stress` | Fe250 elastic–plastic; Fe415/500 cold-worked curve points (0.80…1.00 fyd at inelastic strain 0…0.002); concrete parabola–rectangle 0.446fck, ε₀ 0.002 | Points VERIFIED_FOR_CASES (fs(0.002) = 0.79fy for Fe415); source values UNVERIFIED |
| CAL-SEC-07 | `interaction_curve` | strain compatibility: NA inside section εcu = 0.0035; outside: 0.002 at 3h/7; 120 concrete fibres, displaced concrete deducted; closed by pure tension −0.87fy·As and uniform 0.002; memoised | VERIFIED_FOR_CASES (end points; pure bending vs independent rectangular-block solution within 3 %) |
| CAL-SEC-08 | `check_column` | Puz = 0.45fck·Ac + 0.75fy·Asc; αn = 1 (≤ 0.2) … 2 (≥ 0.8); e_min = l/500 + D/30 ≥ 20 mm applied about one axis at a time; Ma = Pu·D/2000·(le/D)² for le/D > 12 (k = 1); ratio = (Mx/Mux1)^αn + (My/Muy1)^αn ≤ 1 | UNVERIFIED (clauses not checked); le = 1.0 × unsupported length (D-04) |

## Member detailing — `src/rebar_detailer.py`, `src/grid_manager.py`

### CAL-BEM-01 Beams
- **Production:** yes (`GridManager.detail_beams` → `RebarDetailer.detail_beam`).
- **Rules:** d = D − cover(25) − stirrup(8) − φ/2 (two layers: − φ − 12.5); bottom = max(Ast(Mu,sag), Asc(hog), 0.85bd/fy if sagging); top = max(Ast(Mu,hog), Asc(sag), 0.85bd/fy if hogging, 2-12 nominal); FAIL if a face > 4 % bD or bars need > 2 layers; shear with pt = min(top, bottom); WARN if span/d > 20 (simply supported) or 26 (continuous) — modification factors not evaluated. Depth grows from max(current, span/12 rounded to 50, 300 mm) by 50 mm while FAIL or ρ > 2.5 %, up to 1200 mm; width 300 when D > 750.
- **Tests:** `test_R4_*`, `test_R5_result_models_carry_status`. **Status:** UNVERIFIED (engineering review pending); A-BEM-01 (rectangular, no flange action).

### CAL-COL-01 Columns
- **Production:** yes (`detail_columns` → `detail_column`).
- **Rules:** candidates n ∈ {8…40} (project minimum 8 bars, φ ≥ 16), φ ∈ {16, 20, 25, 32}, As ≥ 0.8 % Ag, ≤ 4 % Ag; perimeter spacing ≤ 300 mm c/c, clear ≥ max(φ, 25); smallest area satisfying `check_column` for every combination; ties pitch min(b, D, 16φ, 300), 150 mm at level 0 (project rule); tie dia max(φ/4, 6) → 8/10/12; SMRF: end-zone spacing.
- **Tests:** `test_R1_*`. **Status:** UNVERIFIED.

### CAL-COL-02 Initial column sizing
- **Where:** `GridManager.optimize_column_sizes`. Production (starting point only).
- **Rule:** smallest square from 230 mm (+50) with 0.4fck·Ac + 0.67fy·Asc ≥ 1.5·P_service at 0.8 %; then ≥ 300×450 (project), interior P > 400 kN → ≥ 400×600, snap to preferred sizes, wall alignment, stack locking, upward-only grouping (R26). Final sizes come from the P-M design iteration.

### CAL-SLB-01/02 Slabs
- **Where:** `GridManager.detail_slabs`, `RebarDetailer.detail_slab`. Production.
- **Thickness:** t = max(⌈(lx/26 + 30)/5⌉·5, 125, occupancy slab thickness).
- **Moments:** two-way: Table 26 case from (discontinuous short edges, discontinuous long edges), coefficients interpolated on ly/lx ∈ [1, 2]; Mx = αx·w·lx², My = αy·w·lx²; one-way (ly/lx > 2): wlx²/8 for span and support. w = 1.5(25t + SDL + LL).
- **Steel:** Ast from CAL-SEC-02, ≥ 0.12 % bD, bars 8/10/12 with spacing ≥ 100 mm and ≤ min(3d, 300) (distribution ≤ min(5d, 450)); FAIL if moment > Mu,lim or spacing impossible; WARN if lx/d > basic ratio.
- **Tests:** `test_R20_*`. **Status:** UNVERIFIED (Table 26 values transcribed, D-05); corner torsion steel not detailed.

### CAL-STR-01 Staircase
- **Where:** `RebarDetailer.detail_staircase`. Production when "Add Staircase" is selected.
- **Rule:** dog-legged flight, risers ≈ 150 mm, tread 250/300, span = going + 2 × 1.2 m landings, waist ≥ max(span/25, 150) increased until Mu ≤ Mu,lim and a 10/12/16 mm spacing ≥ 100 mm exists; w = 25·t·(√(R²+T²)/T) + 25R/2 + LL + FF; Mu = 1.5wL²/8; steel weight 100 kg/m³ allowance.
- **Status:** UNVERIFIED; hand check of one case recorded in [verification-results.md](../verification/verification-results.md).

### CAL-FND-01 Isolated footing
- **Where:** `foundation_eng.py::design_footing`. Production.
- **Rules:** side = √(1.1·P_service/SBC) ≥ 1.5 m (P ≤ 400) / 2.0 m, rounded up to 50 mm, FAIL > 10 m; thickness from 300/350 mm in 50 mm steps until punching (perimeter at d/2, Vu = Pu − qu·(c1+d)(c2+d), τ ≤ ks·0.25√fck, ks = 0.5 + βc ≤ 1), flexure at the face of the smaller column side (Mu = qu·c²/2 ≤ Mu,lim) and one-way shear at d (τc from provided pt) pass; d = t − 50 − 12; Ast ≥ 0.12 %; bars 12 (16 if needed) both ways; eccentricity warning if e = M_base/P > B/6 or edge pressure > SBC.
- **Tests:** `test_foundation_eng.py`, `test_R16_*`. **Status:** UNVERIFIED (flexure hand check in test reproduces the implemented formula); D-06 base moments.

## Checks

| ID | Where | Rule | Status |
|---|---|---|---|
| CAL-CHK-01 Audit | `audit.py` | Pu,max (combinations) vs 0.4fck(Ag−As) + 0.67fy·As (notes Cl 39.3 applicability); bearing (P+plinth)·1.1/A ≤ SBC; punching as CAL-FND-01; deflection 5wL⁴/(384E·0.5Ig) ≤ L/250 with analysed service UDL | Consistency screen only |
| CAL-CHK-02 Stability / fire | `stability.py` | column le/D ≤ 60; beam L/b ≤ min(60, 250b/D); fire table by storeys/height; covers 40 (columns) / 25 (beams) | UNVERIFIED (table values) |
| CAL-CHK-03 Optimiser | `optimizer.py` | smallest standard size (≥ 300×450; ≥ 300 in III–V) whose production column check gives ratio ≤ 1/1.15 (moderate) under current forces; `requires_reanalysis = True` | Indicative only |
| CAL-CHK-04 BlackBox prompts | `risk_management.py` | Rule-of-thumb prompts (CLI) | NOT_ASSESSED |

## Quantities and cost — `src/quantifier.py`

| ID | Rule | Status |
|---|---|---|
| CAL-QTY-01 Concrete | columns b·D·h (segment height); beams b·D·L (no overlap deduction with slabs/columns); slabs Σ panel area × thickness × storeys; footings; staircase (2 flights/storey) | UNVERIFIED (overlaps double-counted, conservative) |
| CAL-QTY-02 Steel | columns/beams/slabs from detailing weight breakdowns × length/area (beam lookup by plan id, R13); footings from designed bars (else 80 kg/m³); +4 % wastage; staircase 100 kg/m³ | UNVERIFIED |
| CAL-QTY-03 Mix materials | cement 320/340/360/380/400 kg/m³ for M20/25/30/35/≥40; water 170 L/m³; sand 0.39, aggregate 0.87 m³ per m³ | Indicative nominal values (A-QTY-03) |
| CAL-QTY-04 Cost / carbon | concrete 5000 INR/m³, steel 60 INR/kg, excavation 200–1600 INR/m³, finishes 300–500 INR/m², contingency 5 %; carbon 300 (200 fly ash) kg/m³, 1.85 kg/kg | Fixed rates — UNVERIFIED |
| CAL-QTY-05 Masonry / plaster / paint | `wall_calculator.py`, `report_gen.py` | NOT_ASSESSED in detail |
| CAL-BBS-01 BBS | `bbs_report.generate_bbs_from_grid_manager` → `bbs_module`: one typical floor; designed bar counts/diameters, stirrup/tie spacing, slab panel sizes | UNVERIFIED |

## Legacy / non-production calculations

| ID | Where | Note |
|---|---|---|
| CAL-LEG-01 | `member_design.py::check_pm_interaction` | Mux1 from a balanced-section expression that ignores Pu — not suitable for use; test-only |
| CAL-LEG-02 | `analysis_config.py::calculate_base_shear` | Separate spectrum table; not used by production |
| CAL-LEG-03 | `calculations.py`, `quantity_takeoff.py`, `slab_generator.py`, `structural_checks.py` | Test-only, not assessed |
