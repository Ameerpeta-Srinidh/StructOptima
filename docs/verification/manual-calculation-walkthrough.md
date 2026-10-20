# Manual Calculation Walkthrough — checking StructOptima by hand

**Prepared:** 2026-10-15; **updated 2026-10-16** after the N13 fix (the designed slab
thickness now feeds the dead load). Values below were produced by the current code
and re-derived by hand. If the program changes, regenerate the numbers before using
this as a reference.

This guide takes one complete building through every calculation StructOptima
performs and shows how to reproduce each output with a calculator or
spreadsheet. Work through it once with the reference building; then repeat the
same steps for your own project using the checklist in §14.

> **What a hand check proves.** It proves the program applied its stated formulas
> to its stated inputs correctly. It does **not** prove that the formulas,
> assumptions or code values are right for your building — that needs a licensed
> structural engineer and the printed standards (see
> [../engineering/standards-register.md](../engineering/standards-register.md) and
> [../engineering/limitations.md](../engineering/limitations.md)).

**You will need:** a calculator or spreadsheet; IS 456:2000, SP:16, IS 1893 (Part 1):2016,
IS 875 (Parts 1–3) for checking table values; optionally a free 2D frame-analysis
program (for example Ftool — check its licence and availability yourself) for §7.

---

## 0. Reference building and how to reproduce it

| Input | Value |
|---|---|
| Plan | 8 m × 8 m, grid 2 × 2 bays of 4 m (grid lines 0, 4, 8 m both ways) |
| Storeys | 2, storey height 3.5 m |
| Occupancy | Residential |
| Concrete / steel | M25 (fck = 25 N/mm²) / Fe415 (fy = 415 N/mm²) |
| Seismic | Zone III, soil II, OMRF (R = 3), I = 1.0 |
| Wind | Zone 2, terrain category 2 |
| SBC | 200 kN/m² |
| Walls | Perimeter only, 200 mm core brick, opening deduction 0.33 |
| Options | Fixed base, cracked sections on, no staircase, no cantilevers |

**In the app:** Manual Dimensions → width 8, length 8, stories 2, height 3.5; keep all
other defaults (Residential, Zone III, soil II, OMRF, wind zone 2, terrain 2, M25, Fe415,
230 mm wall, 0.33 openings, fixed supports, cracked sections). **CLI equivalent:**

```bash
python main.py --width 8 --length 8 --stories 2 --story-height 3.5 --zone III --soil II \
  --system OMRF --wind-zone 2 --terrain 2 --sbc 200 --grade M25 --fy 415 --report ref.pdf
```

Result for this building: design status **WARN** (six advisory items — see §13).

### Naming used by the program

- Columns `C1`…`C9` numbered column-by-column from (0,0): C1 (0,0), C2 (0,4), C3 (0,8), C4 (4,0), **C5 (4,4) interior**, C6 (4,8), C7 (8,0), C8 (8,4), C9 (8,8). Suffix `_L0` = ground storey, `_L1` = first floor storey.
- Beams `B_H_n` run along X, `B_V_n` along Y. **B_H_1** = edge beam (0,0)–(4,0); **B_H_3** = interior beam (0,4)–(4,4).
- Slabs `S1`…`S4` = the four 4 × 4 m panels.

### Where each output appears in the app

| Output | Page |
|---|---|
| Column service load, bars, ties, P-M ratio, status | Members → Columns |
| Column calculation log (Pu, Mx, My, Mux1, Muy1, ratio) | Members → Calculation log |
| Beam size, bars, stirrups, Mu+ / Mu−, Vu | Members → Beams |
| Slab thickness, bars | Members → Slabs |
| Footing size | Members → Footings / Reports |
| Seismic Z, Ah, Ta, Vb, storey weights and forces | Checks → Seismic (storey-force table) |
| Wind speed, base shear | Checks → Wind |
| Failures / warnings | Overview banner and issue list; Checks → Issues |
| Quantities | Overview → Quantities; Reports |

---

## 1. Load intensities (service, kN/m²)

Source: `src/building_types.py` (Residential), `design_pipeline.run_design`,
`GridManager.panel_extra_dead_kn_m2`.

| Item | Formula | Value |
|---|---|---|
| Slab self-weight (occupancy slab 125 mm) | 25 × 0.125 | 3.125 |
| Superimposed dead (finish 1.0 + partitions 1.5 + services 0.5) | | 3.000 |
| **Floor DL** (occupancy slab) | 3.125 + 3.0 | **6.125** |
| **Floor LL** | Residential floor | **2.0** |
| **Roof DL** (no partitions) | 3.125 + 1.0 + 0.5 | **4.625** |
| **Roof LL** | accessible roof | **1.5** |
| **Extra for the thicker designed slab** | 25 × (t_designed − 0.125); the 4 m panels are designed 185 mm (§10): 25 × 0.060 | **+1.5** on floor and roof DL |

So the dead load actually used for the 4 m panels is **7.625** (floor) and **6.125** (roof) kN/m².
Check the LL / finish values against IS 875 Parts 1–2 yourself.

## 2. Wall line load

Source: `Wall.line_load_kn_m`, `GridManager.generate_walls`.

- Clear height h = 3.5 − 0.125 (slab) − 0.400 (beam) = **2.975 m**
- w = t × h × (1 − openings) × γ = 0.20 × 2.975 × (1 − 0.33) × 19.2 = **7.654 kN/m**

Each 4 m perimeter wall weighs 4 × 7.654 = 30.62 kN. Program: `7.6541` ✔.

## 3. Tributary areas and column load takedown (service)

Source: `GridManager.calculate_trib_areas`, `calculate_loads`.

**Tributary area** = (half span left + half span right) × (half span below + half span above):
corner 2 × 2 = **4 m²**, edge 4 × 2 = **8 m²**, interior 4 × 4 = **16 m²**.

**Per-storey contributions** (the column in storey k carries the floor at its top):

| Item | Formula |
|---|---|
| Slab | A_trib × (roof or floor DL + 1.5 thicker-slab extra) and A_trib × (roof or floor LL) |
| Beam webs | ½ × each framing beam's web weight: web = 0.23 × (0.35 − 0.125) × 25 = 1.294 kN/m; per 4 m beam ½ × 4 × 1.294 = 2.5875 kN |
| Walls | ½ of each wall ending at the column (30.62/2 = 15.31 kN per wall); roof: parapet = 0.33 × that |
| Column self-weight | 0.30 × 0.45 × 3.5 × 25 = 11.8125 kN |

### Interior column C5 (4 beams, no walls)

| Storey | DL | LL |
|---|---|---|
| L1 (roof) | 16 × (4.625 + 1.5) = 98.0; + 4 × 2.5875 = 10.35; + 11.8125 → **120.16** | 16 × 1.5 = **24.0** |
| L0 (adds floor 1) | 16 × (6.125 + 1.5) = 122.0; + 10.35; + 11.8125 = 144.16 → cumulative **264.32** | 16 × 2.0 = 32 → cumulative **56.0** |

Service load at the base of C5: 264.32 + 56.0 = **320.32 kN**. Program ✔ (`DL 264.32 LL 56.0 P 320.32`).

### Corner column C1 (2 beams, 2 walls)

| Storey | DL | LL |
|---|---|---|
| L1 | 4 × 6.125 = 24.5; walls 0.33 × 2 × 15.31 = 10.10; beams 2 × 2.5875 = 5.175; column 11.8125 → **51.59** | 4 × 1.5 = **6.0** |
| L0 | 4 × 7.625 = 30.5; walls 2 × 15.31 = 30.62; 5.175; 11.8125 = 78.11 → cumulative **129.69** | 4 × 2 = 8 → **14.0** |

Ground-storey walls sit on plinth beams: **plinth load** = 2 × 15.31 = **30.62 kN** (added at the footing). Program ✔.

Spreadsheet tip: one row per storey, columns for slab / beams / walls / self-weight, then a running total from the roof down.

## 4. Beam loads (service UDL, kN/m)

Source: `analysis_integration.beam_slab_coefficients`, `beam_case_loads`.

A square 4 × 4 m two-way panel sends a **triangular** load to each beam. The program uses
the moment-equivalent UDL width **k = lx/3 = 4/3 = 1.333 m** per panel side (for a
rectangular panel the long-side beams get k = (lx/6)(3 − (lx/ly)²)).

| Beam | k | Floor DL | Floor LL | Floor total | Roof total |
|---|---|---|---|---|---|
| B_H_3 interior (2 panels) | 2.667 | 2.667 × 7.625 + web 1.294 = **21.627** | 2.667 × 2 = **5.333** | **26.96** | 2.667 × 6.125 + 1.294 + 2.667 × 1.5 = 21.63 |
| B_H_1 edge (1 panel + wall) | 1.333 | 1.333 × 7.625 + 1.294 + wall 7.654 = **19.114** | **2.667** | **21.78** | (roof wall = 0.33 × 7.654) |

Program `svc` (max over storeys): B_H_3 26.96 ✔, B_H_1 21.781 ✔.

## 5. Seismic (equivalent static)

> Since 2026-10-20 the design forces come from the response spectrum method scaled to this static base shear
> (CAL-SEI-11); the static values below are still computed and are the scaling target (IS 1893 7.7.3).

Source: `design_pipeline.storey_seismic_weights`, `seismic.run_seismic_check`.

### Storey weights

Quantities per storey: slab area 64 m²; beam webs 12 beams × 4 m × 1.294 = 62.10 kN;
walls 8 × 30.62 = 244.93 kN; columns 9 × 11.8125 = 106.31 kN.

| Level | Formula | W (kN) |
|---|---|---|
| 1 (h = 3.5 m) | 64 × 7.625 = 488.0; + 62.10; walls ½ below + ½ above = 244.93; columns ½ + ½ = 106.31; LL 64 × 2 × **0.25** = 32.0 | **933.34** |
| 2 roof (h = 7.0 m) | 64 × 6.125 = 392.0; + 62.10; walls ½ × 244.93 + parapet 0.33 × 244.93 = 203.29; columns ½ × 106.31 = 53.16; roof LL × 0 | **710.55** |
| **Total W** | | **1643.89** |

(0.25 = live-load fraction for LL ≤ 3 kN/m² — IS 1893 Table 10; check it.)

### Period, spectrum, base shear

| Step | Formula | Value |
|---|---|---|
| Ta bare frame | 0.075 h^0.75 = 0.075 × 7^0.75 | 0.323 s |
| Ta with infill | 0.09 h / √d = 0.09 × 7 / √8 | **0.223 s** (program uses the shorter) |
| Sa/g (medium soil, 0.10 ≤ T ≤ 0.55) | | **2.5** |
| Ah | (Z/2)(I/R)(Sa/g) = (0.16/2)(1.0/3)(2.5) | **0.06667** |
| Vb | Ah × W = 0.06667 × 1643.89 | **109.59 kN** |

### Storey forces Qi = Vb × Wi hi² / Σ Wj hj²

Σ W h² = 933.34 × 3.5² + 710.55 × 7² = 11 433 + 34 817 = 46 250.
Q1 = 109.59 × 11 433 / 46 250 = **27.09 kN**; Q2 = 109.59 × 34 817 / 46 250 = **82.50 kN**. Program ✔.

Each of the three parallel frames in a direction has identical columns, so each frame takes
**one third**: 9.03 kN at level 1 and 27.50 kN at level 2.

## 6. Wind (static)

Source: `wind_load.calculate_wind_loads`.

| Step | Formula | Value |
|---|---|---|
| Vb (zone 2) | | 39 m/s |
| k2 (z ≤ 10 m, terrain 2) | | 1.0 |
| Vz | 39 × 1 × 1 × 1 | 39 m/s |
| pz | 0.6 × 39² = 912.6 N/m² | **0.9126 kN/m²** |
| Cpe | windward 0.8; leeward for h/b = 7/8 = 0.875 → −0.4 | |
| Level 1 force | pz × (0.8 + 0.4) × face 8 m × trib 3.5 m | **30.66 kN** |
| Roof force | same with trib 1.75 m | **15.33 kN** |

Program ✔ (`Fx [30.663, 15.332]`). Here seismic governs (109.6 kN vs 46.0 kN base shear).

## 7. Frame analysis — beam moments

The program solves each grid line as a 2D frame. Two ways to check.

### 7a. Statics check (always possible, no software)

For any span under a UDL w: **average end (hogging) moment + mid-span (sagging) moment = w L² / 8**.
Dead load on B_H_3, level 1: w = 21.627 kN/m, L = 4 m → wL²/8 = **43.25 kNm**.

### 7b. Independent frame model (Ftool or similar)

Model grid line y = 4 m as a 2D frame and reproduce the program's results load case by load case:

| Item | Value |
|---|---|
| Nodes | x = 0, 4, 8 m; z = 0, 3.5, 7.0 m; bases fixed |
| E | 5000 √fck = 25 000 N/mm² |
| Columns 300 (along X) × 450 | I = 450 × 300³ / 12 × **0.70** (cracked) = 7.09 × 10⁸ mm⁴; A = 0.135 m² |
| Beams 230 × 350 | I = 230 × 350³ / 12 × **0.35** (cracked) = 2.88 × 10⁸ mm⁴; A = 0.0805 m² |
| DL case | floor beams 21.627 kN/m, roof beams 17.627 kN/m |
| LL case | floor 5.333 kN/m, roof 4.0 kN/m |
| EQX case | 9.03 kN at (0, 3.5), 27.50 kN at (0, 7.0), horizontal |

Expected results for **B_H_3 at level 1** (hogging negative):

| Case | M left | M mid | M right | Check |
|---|---|---|---|---|
| DL | −25.75 | +15.25 | −30.26 | (25.75 + 30.26)/2 + 15.25 = 43.25 = wL²/8 ✔ |
| LL | −6.32 | +3.77 | −7.48 | |
| EQX | +19.83 | +0.60 | −18.63 | |

Combinations (IS 456 Table 18 / IS 1893 factors), worst values along the span:

| Combination | Most negative | Most positive |
|---|---|---|
| 1.5(DL + LL) | −56.60 | **+28.53** |
| 1.5(DL + EQx) | **−73.33** | +27.62 |
| 1.5(DL − EQx) | −68.37 | +24.47 |

Program envelope for B_H_3: **Mu+ = 28.53, Mu− = 73.33 kNm** (governing 1.5(DL+EQx)) ✔.
Column C5_L0 bottom moment under EQX = 32.84 kNm → 0.9DL − 1.5EQx gives 1.5 × 32.84 = **49.27 kNm**
(dead-load moment is zero by symmetry) — matches the column log (§9).

## 8. Beam design — B_H_3 (230 × 350, M25, Fe415)

Source: `rebar_detailer.detail_beam`, `section_design`.

### Top steel (hogging Mu = 73.33 kNm)

| Step | Formula | Value |
|---|---|---|
| Effective depth | d = 350 − 25 cover − 8 stirrup − 20/2 (program picks 20 mm top bars) | 307 mm |
| Mu,lim | 0.138 fck b d² = 0.138 × 25 × 230 × 307² | 74.8 kNm > 73.33 → singly reinforced (only just) |
| R | Mu / (b d²) = 73.33×10⁶ / (230 × 307²) | 3.383 |
| pt | 50 (fck/fy) [1 − √(1 − 4.6 R / fck)] = 3.012 × (1 − √0.3778) | 1.161 % |
| Ast required | pt × b × d / 100 | **820 mm²** (program 819.4 ✔) |
| Minimum | 0.85 b d / fy = 0.85 × 230 × 307 / 415 | 145 mm² |
| Provided | 3-20 = 3 × 314.2 | 943 mm² ✔ (fits: 3 × 20 + 2 × 25 = 110 ≤ 230 − 66 = 164 mm) |

Bottom steel (sagging 28.53 kNm) works the same way → 271 mm² → 3-12 (339 mm²) ✔.

### Shear (Vu = 83.0 kN)

| Step | Formula | Value |
|---|---|---|
| τv | Vu / (b d), d = smaller of top/bottom = 307 | 83 000 / (230 × 307) = 1.176 N/mm² |
| pt for τc | smaller face: 339.3 × 100 / (230 × 307) | 0.481 % |
| τc (Table 19, M25, interpolate 0.25 → 0.36, 0.50 → 0.49) | 0.36 + 0.13 × 0.231/0.25 | 0.480 N/mm² |
| τc,max (M25) | | 3.1 → section OK |
| Vus | (τv − τc) b d | 49.1 kN |
| Spacing for strength | 0.87 fy Asv d / Vus = 0.87 × 415 × 100.5 × 307 / 49 120 | 226.8 mm |
| Minimum-steel limit | 0.87 fy Asv / (0.4 b) | 394 mm |
| Maximum | min(0.75 d, 300) = 230.3 | governing 226.8 → round down to 5 mm → **2L-8 @ 225** ✔ |

## 9. Column design — C5_L0 (300 × 450, 8-16)

Source: `rebar_detailer.detail_column`, `section_design.check_column`. The column log
on the Members page (Calculation log) shows every value below.

| Step | Formula | Value |
|---|---|---|
| Governing combination (from analysis) | 0.9DL − 1.5EQx at bottom | Pu = 0.9 × 264.32 ≈ 237.8 kN, Mx = 49.3 kNm (lever along X → section depth 300 mm) |
| Minimum eccentricity about the 300 face | L/500 + D/30 = 3500/500 + 300/30 = 17 → **20 mm** (minimum) | Pu e = 4.8 kNm < 49.3 → analysis moment governs |
| Minimum eccentricity about the 450 face | 7 + 450/30 = 22 mm | My = 237.8 × 0.022 = **5.23 kNm** (applied about one axis at a time) |
| Slenderness | le/D = 3500/300 = 11.7 < 12 → short column | no additional moment |
| Steel | 8-16 = 1608 mm² = 1.19 % (≥ 0.8 %, ≤ 4 %) | |
| Puz | 0.45 fck Ac + 0.75 fy Asc = 0.45×25×(135 000 − 1608) + 0.75×415×1608 | **2001 kN** |
| αn | Pu/Puz = 0.119 ≤ 0.2 | **1.0** |
| Mux1, Muy1 (uniaxial capacities at Pu) | from SP:16 charts (below) — program: | 80.8 kNm, 134.2 kNm |
| Interaction | (49.3/80.8)^1.0 + (5.23/134.2)^1.0 | **0.649 ≤ 1.0 ✔** (program 0.649) |

**Checking Mux1 with SP:16.** Use the interaction chart for a rectangular section with
reinforcement equally distributed on four sides, your fy, and d′/D ≈ (40 + 8 + 8)/300 = 0.19
(use the 0.20 chart). Compute:

- Pu / (fck b D) = 237 800 / (25 × 450 × 300) = **0.070**
- p / fck = 1.19 / 25 = **0.048**

Read Mu / (fck b D²) from the chart, then Mux1 = value × 25 × 450 × 300². The program's
80.8 kNm corresponds to a chart value of **0.080**; expect your reading to be within a few
percent. Repeat with D = 450 (d′/D ≈ 0.12, use the 0.15 chart) for Muy1 (program 134.2 kNm).

Quick sanity check for gravity only: Cl 39.3 axial capacity 0.4 fck Ac + 0.67 fy Asc
= 0.4×25×133 392 + 0.67×415×1608 = **1781 kN**, far above the gravity Pu = 1.5 × 320.32 = 480.5 kN.

## 10. Slab — S1 (corner panel 4 × 4 m)

Source: `GridManager.panel_slab_thickness_mm`, `detail_slabs`, `rebar_detailer.detail_slab`.

| Step | Formula | Value |
|---|---|---|
| Thickness rule | ⌈(lx/26 + 30)/5⌉ × 5 = ⌈(153.8 + 30)/5⌉ × 5 | **185 mm** |
| Edge condition | two adjacent edges discontinuous → Table 26 **case 4**, ly/lx = 1.0 | αx− 0.047, αx+ 0.035, αy− 0.045, αy+ 0.035 |
| Factored load | 1.5 × (25 × 0.185 + 3.0 + 2.0) | **14.44 kN/m²** |
| Mx+ | 0.035 × 14.44 × 4² | **8.09 kNm/m** |
| Mx− | 0.047 × 14.44 × 16 | **10.86 kNm/m** |
| d | 185 − 20 − 5 | 160 mm |
| Ast for Mx− | R = 10.86×10⁶/(1000 × 160²) = 0.424 → pt = 0.120 % → 192 mm²/m | |
| Minimum 0.12 % | 0.0012 × 1000 × 185 | **222 mm²/m** governs |
| Bars | 8 mm: 50.27 × 1000 / 222 = 226 → round down to 10 | **8 @ 220** ✔ |

Check the Table 26 coefficients in your copy of IS 456 (they were typed into the program).

> **Finding N13** — found by this walkthrough on 2026-10-15 and fixed on 2026-10-16. The slab is
> designed 185 mm thick while the occupancy slab is 125 mm; the extra 25 × 0.060 = 1.5 kN/m²
> is now included in the beam, column, footing and seismic loads (§1, §3–§5).

## 11. Footing — under C5

Source: `foundation_eng.design_footing`.

| Step | Formula | Value |
|---|---|---|
| Service load | column 320.32 + plinth 0 | 320.32 kN |
| Area | 1.1 × 320.32 / 200 = 1.76 m² → side 1.33 m; project minimum 1.5 m (P ≤ 400 kN) | **1.5 × 1.5 m** |
| Bearing pressure | 1.1 × 320.32 / 2.25 | 156.6 kN/m² ≤ 200 ✔ |
| Factored load | worst level-0 combination = 1.5(DL+LL) = 1.5 × 320.32 | 480.5 kN |
| Net factored pressure qu | 480 490 / 1500² | 0.2136 N/mm² |
| **Trial 1: t = 300 mm**, d = 300 − 50 − 12 = 238 | punching: τ = (480 490 − 0.2136 × 538 × 688) / (2 × (538 + 688) × 238) = 0.688 ≤ ks 0.25√25 = 1.25 ✔ (βc = 0.67 → ks = 1); bending Mu = 0.2136 × 600²/2 = 38.4 kNm/m → Ast 462 mm²/m (pt 0.194 %) | one-way shear at d: τv = 0.2136 × (600 − 238)/238 = 0.325 **>** τc(0.194 %) ≈ 0.321 ✘ → thicken by 50 mm |
| **Trial 2: t = 350 mm**, d = 288 | punching OK; Mu = 38.4 kNm/m → R = 0.464 → pt 0.131 % → 378 mm²/m; minimum 0.12 % × 1000 × 350 = **420 mm²/m** governs | one-way: τv = 0.2136 × 312/288 = 0.231 ≤ τc(0.15 %) = 0.29 ✔ |
| Bars | 12 mm: 113.1 × 1000 / 420 = 269 → round down to 10 | **12 @ 260 both ways** ✔ (program: 350 mm, 12 @ 260) |

The footing shows **WARN**: with the fixed-base moment from the seismic case, the edge pressure
reaches ≈ 233 kN/m² > 200, and the program sizes footings for axial load only (decision D-06).
F-C4 and F-C6 show the same warning (203 kN/m²).

## 12. Quantities

| Item | Formula | Value (m³) |
|---|---|---|
| Columns | 18 segments × 0.30 × 0.45 × 3.5 | 8.505 |
| Beams | 24 (12 per floor) × 0.23 × 0.35 × 4 | 7.728 |
| Slabs | 4 panels × 16 m² × 0.185 × 2 floors | 23.680 |
| Footings | 8 × 1.5 × 1.5 × 0.30 + 1 × 1.5 × 1.5 × 0.35 (F-C5) | 6.188 |
| **Total** | | **46.100** ✔ |

Steel totals come from each member's bar weights (kg/m = area mm² × 7850 / 10⁶) times
length, plus 4 % wastage — check a few members, not all.

## 13. Advisory items in this example

- **SCWB J_C5_L0_X = 1.38; J_C4_L0_X and J_C6_L0_X = 1.33 (< 1.4)** — column capacities above and
  below the joint vs beam capacities from provided steel. Advisory for OMRF; FAIL for SMRF.
- **Footings F-C4, F-C5, F-C6 edge pressure** — see §11.

---

## 14. How to check your own building

Follow the same order; each step uses outputs of the previous ones.

1. **Intensities** (§1) from your occupancy, plus 25 × (designed − occupancy slab thickness); check against IS 875.
2. **Walls** (§2): t × h × (1 − openings) × γ.
3. **Takedown** (§3) for one corner, one edge and one interior column, top to bottom.
   Compare with the Members page "Service load (kN)".
4. **Beam loads** (§4) for one edge and one interior beam (k = lx/3 or (lx/6)(3 − (lx/ly)²)).
5. **Seismic** (§5): storey weights → Ta → Sa/g → Ah → Vb → storey forces. Compare with the
   Checks page (Seismic tab) table.
6. **Wind** (§6) for the bottom storey.
7. **Frame** (§7): statics check (hog avg + sag = wL²/8) for one beam; optionally model
   one frame in a 2D program with the §7b table recipe.
8. **Beam design** (§8): Ast from Mu with the pt formula, bar count, then stirrups.
9. **Column** (§9): read the column math log; check e_min, Puz, αn and the interaction sum;
   check Mux1 on an SP:16 chart.
10. **Slab** (§10): thickness, Table 26 case, moments, Ast and spacing.
11. **Footing** (§11): area, punching, one-way shear, bending, steel — note which check sets the thickness.
12. **Quantities** (§12): volumes by member type.

**Tolerances.** Expect agreement within about 1 % for loads, forces and steel areas
(rounding), and within a few percent for chart readings. Bar choices round **up**; spacings
round **down**.

**If a number does not match:** re-check your inputs first (units, storey height, slab
thickness, which combination governs); then note the member, the step and both values and
raise it as an issue — it may be a defect (as N13 was).

**Spreadsheet layout suggestion:** one sheet per step above, inputs in blue cells copied
from the app, formulas exactly as in the tables here, and a "program value / my value /
difference %" column for every result.
