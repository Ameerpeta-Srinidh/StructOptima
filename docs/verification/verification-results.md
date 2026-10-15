# Verification Results

All results below were **executed on 2026-10-15** on the development machine
(Windows 11, Python 3.13.7, pytest 9.0.2, numpy 2.4.2, streamlit 1.53.0,
ifcopenshell 0.8.4) against the working tree (base `ee7223e` + uncommitted
2026-10 changes). They are evidence that the code behaves as tested, **not**
evidence of engineering correctness beyond the stated reference cases.

## 1. Test suite

| Run | Command | Result |
|---|---|---|
| Baseline before changes | `pytest tests -p no:cacheprovider --ignore=tests/test_fea_repro.py` | 413 passed, **2 failed** (`test_beam_placer.py` depth tests expecting L/15 while code uses L/12, L/10 since commit "FIX 8"), 3 skipped |
| After remediation (final) | `pytest tests -p no:cacheprovider` | **493 passed, 3 skipped, 0 failed** (≈ 22–33 s) |
| After N13 fix (2026-10-16) | same | **494 passed, 3 skipped, 0 failed** (≈ 63 s; one run, later runs ≈ 22 s) |
| After drawing set (2026-10-16) | same | **504 passed, 3 skipped, 0 failed** (≈ 22 s) |

Skipped: `test_beam_placer.py::test_with_auto_framer` (local `complex_villa.dxf` yields no columns), two `test_column_editor.py` tests (no removable column in the layout).

Historical claim superseded: "407 unit tests passed, 82 integration stress tests passed" (legacy `docs/engineering_basis.md`) — no record of that run exists.

## 2. Closed-form / hand-calculation references encoded in tests

| Case | Reference | Result |
|---|---|---|
| Fixed-fixed beam, w = 10 kN/m, L = 6 m | hog wL²/12 = 30, sag wL²/24 = 15 kNm | 30.0 / 15.0 |
| Portal 6 × 3 m, EI equal, axially rigid | slope-deflection 48 kNm | 48.0 (finite A: 47.7) |
| Cantilever 3 m, tip 10 kN | M = 30 kNm, δ = PL³/3EI | exact |
| Beam drawn right-to-left | identical forces, gravity downward | identical (R12) |
| Column axial in portal | wL/2 | exact |
| Singly reinforced 300×560, Mu = 250 kNm | Annex-G relation | Ast = 1442 mm² (rel. err. < 1e-3) |
| Doubly reinforced 230×400, 1.4 Mu,lim | force and moment equilibrium | exact |
| Column 300×450, 4-16 pure bending | independent rectangular-block strain compatibility | within 3 % |
| Vertical seismic distribution | Q ∝ W h² | exact |
| Beam UDL single square bay | statics hog + sag = 1.5 w L²/8 | within 2 % |

## 3. Manual hand checks performed during remediation (not in tests)

| Check | Hand value | Program |
|---|---|---|
| Edge beam, 18×12 m grid, residential: slab k = 1.474 m × 6.125 + wall 7.65 + web 1.58 + LL 2.95 | 21.21 kN/m | 21.21 kN/m |
| Staircase 3.5 m storey, M25: w ≈ 12.1 kN/m², Mu ≈ 74 kNm/m, Ast ≈ 1084 mm²/m | 12-100 (1131 mm²/m) | 12 mm @ 100 |
| Fe415 stress at 0.002 strain | ≈ 0.79 fy (SP:16 commonly quoted) | 327.7 N/mm² = 0.79 fy |

## 4. Stage-2 reproductions (before remediation, recorded for traceability)

R1–R9, R15 were reproduced on 2026-10-15 before the changes (e.g. audit 142/142
PASS on an overloaded design, beam schedule unchanged between 5 and 15 kN/m²,
optimizer `all_safe = True` with 6/40 columns below 1.5 × load, SCWB ratios
unchanged by a 600×1200 beam). After remediation each has a regression test in
`tests/test_audit_findings.py`.

## 4a. Manual walkthrough (2026-10-15)

A complete 8 × 8 m, 2-storey reference building was hand-checked step by step
([manual-calculation-walkthrough.md](manual-calculation-walkthrough.md)): load intensities, wall load,
takedown (C1, C5), beam loads, storey weights, Ta, Ah, Vb, storey forces, wind forces, an
independently rebuilt 2D frame (B_H_3 envelope −61.61 / +24.32 kNm; C5 base moment 43.44 kNm),
beam flexure and shear, column interaction (0.588), slab S1, footing F-C5 and concrete
quantities all reproduce the program values. The walkthrough found finding **N13** (slab
thickness used in loads ≠ designed slab thickness). After the N13 fix (2026-10-16) the walkthrough
was regenerated and every value re-derived by hand again (e.g. C5 base DL 264.32 kN, B_H_3 26.96 kN/m,
W 1643.89 kN, Vb 109.59 kN, B_H_3 Mu− 73.33 kNm, C5 interaction 0.649, F-C5 350 mm governed by
one-way shear).

## 5. End-to-end runs

| Run | Result |
|---|---|
| CLI `main.py --width 18 --length 12 --stories 3 --zone III` (scratch dir) | exit 0, PDF 72 kB |
| CLI with `samples/sample_design.dxf` | exit 0, PDF 32 kB, warning: `$INSUNITS` implausible → millimetres inferred |
| Headless UI (`AppTest`): dashboard + 5 pages after an analysis | no exceptions |
| DXF sweep: 84 repository DXFs, auto-frame fallback, 2 storeys, 4 iterations | 0 crashes; 2 graceful input errors (empty / circles only); statuses: 55 WARN, 27 FAIL. FAIL causes: "Seismic method" (irregular plans), columns not converged within 4 iterations, 2 unstable frames in one plan, beams in two large plans |
| Performance: G+7, 12×12 m, zone V | 1.8 s (was 127 s before memoising/vectorising interaction curves) |

## 5a. Drawing set visual review (2026-10-16)

Sheets for an 18 × 12 m G+1 building with a staircase void and a 40 × 30 m G+2 building were rendered to PNG
(pypdfium2, scratch directory) and reviewed by the developer: grid bubbles, dimension chains, marks, schedules,
void marking, sections (1:10 / 1:20) and footing sections are legible; fixes applied after review (dimension
offsets, void cross, slab label overlap, top-bar labels, section scale). **Owner/site-engineer review pending.**

## 6. Side-effect incident during testing

The first headless UI run (from the repository root) caused the Drawings page
to overwrite `Beam_Schedule.dxf` and `Foundation_Plan_Professional.dxf` (tracked)
and `Floor_0_Plan.dxf`, `Floor_1_Plan.dxf`, `Structural_Plan.dxf` (ignored), and
appended to `structural_design.log`. The two tracked files were restored with
`git checkout`; the ignored files were regenerated outputs and could not be
restored to their prior content. The UI tests now run in `tmp_path`, and
implicit log-file creation was removed (finding N5).
