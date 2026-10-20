# Standards Check against the Printed Standards (2026-10-20)

**Sources:** BIS PDFs supplied by the owner on 2026-10-20 (in the git-ignored `_local/standards/`), read through
their text layer (`pdftotext -layout`). Where the text layer was garbled, the page image was read. Editions:
- IS 456:2000 with all amendments;
- IS 1893 (Part 1):2016 with Amendments 1 (2017) and 2 (2020);
- IS 13920:2016 with Amendments 1 (2017) and 2 (2020);
- IS 875 Parts 1, 2 and 5 (1987) and Part 3 (2015);
- IS 1786:2008 with Amendment 1;
- IS 1904:2021, IS 6403:1981, SP 16:1980, SP 34:1987, IS 2502:1963, IS 10262:2019, IS 516 (Part 1/Sec 1):2021,
  NBC 2016 Part 4.

**What "VERIFIED" means here:** the value or rule in the code was compared with the printed clause and agrees. It is
*not* an engineer's sign-off. Under the project rules, items become RESOLVED_WITH_EVIDENCE only after review by a
qualified engineer.

Result codes:
- **VERIFIED**: the code matches the clause.
- **FIXED**: the code differed and was changed to the clause, with a regression test (finding id in brackets).
- **CONSERVATIVE**: the code differs on the safe side; it was kept and documented.
- **GAP**: the clause is not implemented; recorded as an open item.
- **UNVERIFIED**: the clause could not be read in full.

## IS 1893 (Part 1):2016

| Clause | Code | Result |
|---|---|---|
| 6.3.2.1, 6.3.1 + IS 456 Table 18 | 25 combinations: 1.5(DL+LL), 1.2(DL+LL±EL/WL), 1.5(DL±EL/WL), 0.9DL±1.5EL/WL, one direction at a time | VERIFIED (orthogonal frames). 100 % + 30 % (6.3.2.2) and vertical EQ (6.3.3.1, Amd 2) not implemented — GAP, listed in "checks not performed" |
| 6.4.2(a) Sa/g, equivalent static method | 1 + 15T below 0.10 s, then 2.5 | **FIXED (S1)**: flat 2.5 from T = 0 to 0.40 / 0.55 / 0.67 s; then 1.00/T, 1.36/T, 1.67/T; then 0.25 / 0.34 / 0.42 beyond 4 s. Before the fix, a single-storey infilled building with d = 18 m (Ta = 0.074 s) got Sa/g = 2.11 instead of 2.5, so Vb was 16 % low |
| 6.4.2 Ah = (Z/2)(I/R)(Sa/g) | same | VERIFIED |
| 6.4.3.1 cracked stiffness | 0.70 Ig columns, 0.35 Ig beams | VERIFIED; switching it off is now a WARN |
| Table 3 Z | 0.10 / 0.16 / 0.24 / 0.36 | VERIFIED |
| 7.2.2, Table 7 minimum VB = ρW | none | **FIXED (S3)**: ρ = 0.7 / 1.1 / 1.6 / 2.4 % for Zones II–V |
| Table 8 I | Residential 1.0, Office 1.2, Retail 1.5, Institutional 1.5, Assembly 1.5 | VERIFIED as defaults. 1.2 applies to residential or commercial buildings with more than 200 occupants, so the engineer sets I for large residential blocks |
| Table 9 R | OMRF 3.0, SMRF 5.0 | VERIFIED |
| Table 9 Note 1 | OMRF allowed in Zones III–V with a warning | **FIXED (S2)**: OMRF is not allowed in Zones III, IV and V, now a FAIL "Structural system" |
| 7.3.1, Table 10 | 25 % of imposed load (q ≤ 3 kN/m²), 50 % above | VERIFIED |
| 7.3.2 | no roof imposed load in the seismic weight | VERIFIED |
| 7.6.2(a), (c), 7.6.2.1 (Amd 2) | Ta = 0.075 h^0.75 (bare); with infill min(0.075 h^0.75, 0.09 h/√d) | VERIFIED (7.6.2.1: not more than (a), not less than (c)). The code uses the larger plan dimension for d in both directions, which gives the shorter period and is conservative |
| 7.6.3 Qi = VB Wi hi² / Σ Wj hj² | same | VERIFIED |
| 7.6, 7.7.1 method | static method up to 40 m (Zones II/III) and 12 m (IV/V) — 2002 edition | **FIXED (S4)**: static method only for regular buildings lower than 15 m in Zone II; every other building needs dynamic analysis, so the design FAILs on "Seismic method" |
| Table 5(ii) re-entrant corners > 15 % | same | VERIFIED |
| Table 5(iii) openings > 50 % | same | VERIFIED (the 10 % edge-opening case of Fig. 3C is not checked — GAP) |
| Table 6(i) soft storey (Amd 2): stiffness less than the storey above | 70 % (2002), never called | **FIXED (S5)**: stiffness = storey shear / storey drift from the EQ analysis; a storey less stiff than the one above is a FAIL |
| Table 6(ii) mass > 150 % of the floor below | never called | **FIXED (S6)**: from the storey seismic weights |
| Table 6(vi) floating columns (Amd 2): not permitted when part of or supporting the lateral system | warning only | **FIXED (S7)**: FAIL per column |
| 7.11.1.1 drift ≤ 0.004 h under VB, load factors 1.0 | same | VERIFIED (previously UNVERIFIED) |
| 7.8 torsion, accidental eccentricity | not implemented | GAP (already in "checks not performed") |

## IS 13920:2016 (Amendments 1 and 2)

| Clause | Code | Result |
|---|---|---|
| 1.1.1 scope: mandatory in Zones III, IV and V | ductile rules only for SMRF | Ductile checks below now run in Zones III–V and for any SMRF |
| 5.2 minimum grade: M20, or M25 above 15 m in Zones III–V | M25 for every Zone III+ building | **FIXED (J4)**: by height; below the minimum is a FAIL |
| 5.3.1 (Amd 2): elongation ≥ 14.5 %, TS/YS 1.15–1.25, grades 415 / 500 / 550 | none | **FIXED (J5)**: WARN. IS 1786 Table 3 minimums don't guarantee it: plain Fe 500 has 12 % elongation, and the TS/YS minimum is 1.06–1.12, so the bars must be D-grade and confirmed by mill certificates |
| 6.3.5(b) (Amd 1) beam end-zone spacing d/4, 6 db, 100 mm | 8 db | **FIXED (J9)** in `rebar_detailer` and `bbs_module.confined_zone_stirrup_spacing` |
| 3.5, 6.3.1(a), 7.4.1 (Amd 1, 2) 135° hook extension 8 d ≥ 75 mm | 6 d ≥ 65 mm | **FIXED (J8)** (`bbs_module.seismic_hook_extension`) |
| 7.1 (Amd 2) column axial stress ≤ 0.40 fck under EQ combinations | none | **FIXED (J7)**: FAIL per column |
| 7.1.1 least column dimension ≥ max(300 mm, 20 × largest beam bar) | none | **FIXED (J6)**: FAIL, using the largest beam bar in the building (conservative) |
| 7.1.2 (Amd 1) aspect ratio ≥ 0.4 | none | **FIXED (J6)** |
| 7.2.1 ΣMc ≥ 1.4 ΣMb | same | VERIFIED |
| 7.2.1.3 roof joints waived only above 4 storeys | roof joints never checked | **FIXED (J3)** |
| 8.1 / 7.6.1 hinge length lo ≥ max(larger dimension, clear span / 6, 450 mm) | storey height / 6 | CONSERVATIVE |
| 7.6.1(b) (Amd 1) confining spacing 6 db | min(b/4, 6 db, 100 mm) | CONSERVATIVE (stricter than the amended clause) |
| 7.6.1(c) Ash | not implemented | GAP (known, KD) |
| 9.1.1 (Amd 2) τjc = 1.5 / 1.2 / 1.0 √fck for 4 / 3 / other faces | 1.2 also for two opposite faces | **FIXED (J1)** |
| 9.1.2(a) (Amd 2) bj = min[bb; bc + 0.5 hc] if bc < bb | hc × min(bc, bb + hc) | **FIXED (J2)** for bc < bb. For bc ≥ bb the formula is not printed in full in this copy, so the mirror form min[bc; bb + 0.5 hc] is used (UNVERIFIED, conservative) |
| 9.1.2(b) demand from beam bars at 1.25 fy | same | VERIFIED |

## IS 456:2000 (with amendments)

| Clause | Code | Result |
|---|---|---|
| Table 18 partial safety factors | as above | VERIFIED |
| Table 19 τc, M20–M40 (all 13 rows) | `section_design.TAU_C_TABLES` | VERIFIED, every value. The code has no M15 row and would use M20 values for fck < 20; the UI offers M20–M30 only |
| Table 20 τc,max | 2.8 / 3.1 / 3.5 / 3.7 / 4.0 | VERIFIED |
| Table 26 two-way slab coefficients (9 cases × 8 ratios + long span) | `rebar_detailer.TABLE26` | VERIFIED except one value: **FIXED (T1)**, case 4 (two adjacent edges discontinuous) long-span negative coefficient is 0.047, not 0.045. Case 2 title as corrected by the amendment ("One Short Edge Discontinuous") matches the mapping |
| 38.1 xu,max/d 0.53 / 0.48 / 0.46 | same | VERIFIED |
| 39.6 Puz = 0.45 fck Ac + 0.75 fy Asc; αn 1.0–2.0 linear for Pu/Puz 0.2–0.8 | same | VERIFIED |
| 25.4 e_min = l/500 + D/30 ≥ 20 mm, one axis at a time | same | VERIFIED |
| 39.7.1 Ma = Pu D/2000 (le/D)², slender above le/D = 12 (25.1.2) | same; the reduction factor k of 39.7.1.1 is taken as 1.0 | VERIFIED (k = 1 is conservative) |
| 25.3.1 unsupported length ≤ 60 × least dimension; 23.3 beam L ≤ 60 b and 250 b²/d | same | VERIFIED; cantilever limits (25 b, 100 b²/d) are not checked — GAP. Slenderness failures now reach the status list |
| 26.5.1.1 As,min = 0.85 bd/fy; 26.5.1.5 sv ≤ 0.75 d, 300 mm; 26.5.1.6 Asv/(b sv) ≥ 0.4/(0.87 fy), fy ≤ 415 | same | VERIFIED |
| 40.4 Vus = 0.87 fy Asv d / sv | same | VERIFIED |
| 26.5.2.1 slab As,min 0.12 % (HYSD) | same | VERIFIED |
| 26.5.3.1 column steel 0.8–6 % | 0.8–4 % | CONSERVATIVE (4 % practical limit) |
| 26.5.3.2(c) tie pitch ≤ least dimension, 16 φ, 300 mm; tie diameter ≥ φ/4, ≥ 6 mm | same | VERIFIED |
| Table 3 exposure, Table 5 minimum grade (RCC: M20 / M25 / M30 / M35 / M40), Table 16 cover (20 / 30 / 45 / 50 / 75 mm) | none — fixed covers 25 / 20 / 40 / 50 mm and only M20 checked | **FIXED (D1)**: new input "exposure condition" (default Moderate); covers = max(Table 16, Table 16A) and are used throughout the design, joint check, BBS and drawings; grade below Table 5 is a FAIL |
| 26.4.2.1 column cover ≥ 40 mm; 26.4.2.2 footing cover 50 mm | 40 / 50 mm | VERIFIED |
| Table 16A fire covers; Fig. 1 minimum dimensions | column covers 20–30 mm up to 1.5 h, 1.5 h column 200 mm, beam/slab covers below the table from 2 h | **FIXED (F1)**, values read from the page image: columns 40 mm at every period; beams (continuous) 20 / 20 / 20 / 30 / 40 / 50; slabs (simply supported) 20 / 20 / 25 / 35 / 45 / 55; columns fully exposed 150 / 200 / 250 / 300 / 400 / 450 mm |
| 31.6.3.1 punching ks τc, τc = 0.25 √fck, ks = 0.5 + βc ≤ 1; 34.2.4.1 one-way shear at d; 34.1.2 edge thickness ≥ 150 mm | same | VERIFIED |

## IS 875 (Parts 1, 2, 3)

| Clause | Code | Result |
|---|---|---|
| Part 1 Table 1: RCC 22.75–26.5 kN/m³ (1–5 % steel); brick masonry 1920 kg/m³ = 18.85 kN/m³ | 25.0 / 19.2 | VERIFIED / CONSERVATIVE |
| Part 2 Table 1: residential rooms 2.0; retail shops 4.0; assembly without fixed seats 5.0; institutional wards 2.0, classrooms 3.0 | same | VERIFIED |
| Part 2 Table 1 v): offices 2.5 (with separate storage) or 4.0 (without) | 3.0 | **FIXED (L1)**: 4.0 (storage cannot be assumed) |
| Part 2 Table 1: corridors, stairs, balconies (3.0 residential, 4.0 others) | single floor load for the whole floor | GAP |
| Part 2 Table 2: accessible flat roof 1.5 kN/m² | 1.5 | VERIFIED |
| Part 2 3.1.2 light partitions ≥ 33⅓ % of the partition weight per metre run | 1.0–1.5 kN/m² by occupancy | VERIFIED as minimum allowances |
| Part 3 Vb by zone 33 / 39 / 44 / 47 / 50 / 55 m/s | same | VERIFIED |
| Part 3 Table 2 k2 | power law k2,10 (z/10)^α | **FIXED (W1)**: printed table with linear interpolation; the power law was up to 3 % low (terrain category 1 at 50 m: 1.16 vs 1.20) |
| Part 3 7.2 Pd = Kd Ka Kc Pz (≥ 0.7 Pz) | factors taken as 1.0 | CONSERVATIVE |
| Part 3 Table 5 Cpe for walls | windward +0.8, leeward −0.3 to −0.6 | CONSERVATIVE for h/w < 6 (table net 0.8–1.05). For h/w ≥ 6 the table gives up to +0.95 / −1.85: **FIXED (W2)** — now a FAIL |
| Part 3 k3 (topography), k4 (cyclonic importance) | 1.0, no input | GAP: sites on slopes > 3° or on the cyclone-prone coasts need these factors |

## NBC 2016 Part 4 (fire)

| Clause | Code | Result |
|---|---|---|
| Table 1 fire rating by type of construction and element (columns supporting > 1 floor 240 / 120 / 120 / 120 min; one floor or roof 180 / 90 / 60 / 60; floors 120 / 90 / 60 / 60) | one rating by number of floors and height (not in NBC) | **FIXED (F2)**: new input "NBC type of construction" (default Type 2); ratings per element; fire failures now reach the status list |

## IS 1786:2008 (Amendment 1)

| Clause | Result |
|---|---|
| Table 3: elongation Fe 415 14.5 %, Fe 415D 18 %, Fe 500 12 %, Fe 500D 16 %, Fe 550D 14.5 %; TS/YS minimum 1.06–1.12 | Used for the IS 13920 5.3.1 note (J5): plain Fe 500 does not meet 14.5 % elongation |

## SP 16:1980 benchmarks (`tests/test_sp16_benchmarks.py`)

| Item | Result |
|---|---|
| Table C (Mu,lim / fck bd², pt,lim fy/fck) and Table D (Mu,lim / bd² for M15–M30, Fe250/415/500) | Reproduced within 0.8 %. The code uses IS 456's rounded xu,max/d; SP 16 used unrounded values |
| Table A (cold-worked bar stress–strain) and Table F (compression-steel stress) | Within 0.5 % / 1.2 %. SP 16 prints 288.1 N/mm² for Fe 415 at 0.80 fyd, but 0.8 × 0.87 × 415 = 288.8, so the printed value is a misprint |
| Example 1 (singly reinforced beam As = 10.02 cm²), Example 2 (slab 3.8 cm²/m), Example 3 (doubly reinforced As = 18.85, Asc = 7.05 cm²) | Reproduced within 1 % / 2 % / 2–3 % |
| Example 6 (450 × 450 column, Pu = 2500 kN, Mu = 200 kNm at p = 2.5 %) | Capacity of the code's section at 2.48 % within 10 % (chart reading, d'/D 0.13 vs 0.15) |
| Example 9 (Puz = 2700 kN; Max = 67.8, May = 63.0 kNm; e_min 27.3 / 24.0 mm) | Reproduced within 1 % |
| Example 10 (shear: τv = 1.07, τc = 0.55, 8 mm 2-legged stirrups at 140 mm) | Reproduced once the M15 row of Table 19 was added (**FIXED T2**: M15 used the M20 values, which is unconservative) |

## Other findings from the 2026-10-20 testing

| Id | Finding | Result |
|---|---|---|
| A1 | Lateral storey forces were shared between parallel 2D frames by column stiffness only (beams ignored), and column tops of a frame without beams were not connected. Frames with missing beams got as much load as fully framed ones: their drift was overstated (false drift FAILs in 40 of 92 sample drawings), and stiffer frames got less load than a rigid floor gives them (unconservative member forces) | **FIXED**: rigid-diaphragm sharing in translation from each frame's condensed lateral stiffness (unit floor loads); slab links tie the nodes of a level that no beam connects. Hand check: portal with a rigid beam beside a cantilever pair gives a 12 : 3 split (`tests/test_lateral_sharing.py`) |
| P1 | The audit's beam deflection screen used an assumed 20 kN/m load when the analysis gave no service load | **FIXED**: not evaluated without an analysis load |
| Q1 | The IS 456 quick reference card said "max column steel 4 %" (the code allows 6 %), "min column 230 mm" (not in IS 456; IS 13920 requires 300 mm) and "beam cover 25 mm" (cover depends on exposure) | **FIXED** with clause numbers |
| X1 | DXF: leaders and tags on column layers (e.g. S-COLS-IDEN) were read as columns, which doubled the columns and grid lines of a normally annotated drawing | **FIXED**: whole-word layer matching, annotation layers excluded, only closed outlines |
| X2 | DXF: columns drawn as blocks, old POLYLINEs or circles, and plans bound inside a block, were not read | **FIXED**: blocks exploded (layer-0 inheritance), POLYLINE, CIRCLE (equal-area square, warned), unbound xrefs reported |
| X3 | DXF: no grid clustering (millimetre drafting misalignment created extra grid lines); beam ends drawn to column faces not connected; survey coordinates passed through; duplicate outlines double-counted; "closed" tolerance relative to coordinate size (a column at survey coordinates lost a corner) | **FIXED** (`tests/test_dxf_conventions.py`, 23 cases) |
| X4 | DXF wall thickness: millimetre thresholds applied to drawings in metres; midpoint instead of perpendicular distance | **FIXED** (unit-aware, perpendicular, overlapping pairs) |

## Dynamic analysis added after the check (D-26)

IS 1893 7.7.5 (response spectrum), 7.7.3 (scaling), 7.8.2 (design eccentricity), Table 5(i) and Table 6(vii) as amended
are implemented on a rigid-diaphragm 3D model (`src/pseudo3d.py`) and checked against hand results
(`tests/test_pseudo3d.py`).

| Hand check | Result |
|---|---|
| Symmetric single storey, 4 equal frames, e_d = ±0.05 b | worse frame 0.525 F; transverse frames ±0.025 F; Δmax / Δave = 1.05 |
| X frames of stiffness k and 3k, e_s = −0.25 L | frame forces equal the closed-form centre-of-resistance solution (50.5 kN on the flexible side for F = 100 kN) |
| Two-storey shear building | periods 2π / √((k/m)(3 ∓ √5)/2) |
| Single storey, response spectrum | VB = Ah(T) W |
| 7.7.3 | scaled to VB static when lower |
| CQC | SRSS for separated modes, algebraic sum for equal frequencies |

Not represented: flexible diaphragms (re-entrant corners, openings > 50 %), reported as WARN.

