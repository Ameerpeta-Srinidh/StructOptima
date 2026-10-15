# Changelog

All changes made during the October 2026 audit, remediation and feature work, newest first.
Finding IDs (R*, N*, KD-*), decisions (D-*) and remediation records (RM-*) point to the detailed records in
`docs/assurance/`. Nothing listed here has been reviewed by a licensed structural engineer; every output of
StructOptima remains **preliminary and NOT VERIFIED**.

Each entry states what changed, why, the evidence (tests actually run) and what is still open.

---

## 2026-10-16 — Repository clean-up and owner decisions

Commit: `chore: organise the repository; record owner decisions`. Approved by the owner (D-07): "clean the whole
civil folder, it is very messy, organize everything".

### New layout
```
app.py, main.py, pages/, src/, components/viewer3d/, tests/
samples/      sample_design.dxf, sample_arch_only.dxf, plans/, real_world/, test_cases/   (see samples/README.md)
docs/         current documentation; docs/legacy/ = historical write-ups
CHANGELOG.md, CLAUDE.md, README.md, CONTRIBUTING.md, CODE_OF_CONDUCT.md, LICENSE, deployment files
_local/       git-ignored: personal scripts and old outputs moved out of the root (see _local/README.md)
```

### Changes
- **Moved within the repository:**
  - `test_dxfs/` → `samples/test_cases/`;
  - `real_world_dxfs/` → `samples/real_world/`;
  - historical write-ups (`Extended_Structural_Calculation_Reference*`, `StructOptima_*.pdf/.docx`,
    `Structural_DXF_Translation.pdf`, `structural_calculations_manual.md`, `blueprint_text.txt`) → `docs/legacy/`;
  - the old guides (`api_reference.md`, `engineering_basis.md`, `installation.md`, `risk_management.md`,
    `user_guide.md`) → `docs/legacy/`.
- **Committed:** `samples/plans/` holds the plan DXFs the tests use (`complex_villa.dxf`, `complex_house.dxf`,
  `real_house_plan.dxf`, …). They were git-ignored before, so CI skipped those tests. Test paths are now relative to
  the repository instead of the working directory.
- **Removed from the repository** (still in git history; local copies in `_local/retired_from_repo/`):
  - old generated outputs (DXF, PDF, ZIP, JPG, a log);
  - `sample_report.pdf`, a report produced by an earlier, uncorrected version. Its download button was removed from
    the dashboard;
  - legacy scripts (`demo_*.py`, `debug_pipeline.py`, `stress_test_core.py`, `ui_test_runner.py`, `tmp_*.py`,
    `fix*.py`, `generate_sample_report.py`);
  - the folders `scratch/`, `_monetization_archive/` and `src/tests/`.
- **Moved out of the root, untracked material:** personal scripts, old reports, HTML dumps and logs went to
  `_local/`. Nothing was deleted except Python caches.
- **`.gitignore`** rewritten and grouped; `_local/` is ignored.
- **Link check:** every relative Markdown link in the repository resolves.

### Owner decisions recorded
- D-16: **automatic column enlargement for drift is approved**. The drift limit values (0.004 h, H/500) are still
  awaiting confirmation against the printed standards.
- D-07: clean-up approved and done.
- Commit messages carry no AI co-author lines from 2026-10-16 on. The owner asked for the line to be removed from the
  two older commits as well (`fix: remediate audit findings …` and `docs: add manual calculation walkthrough …`).
  That needs a history rewrite and a force-push, which the tool's permission system blocked. It is **pending** the
  owner allowing it (see the session notes).

### Tests run
- `PYTHONDONTWRITEBYTECODE=1 python -m pytest tests -p no:cacheprovider -q -rs` → **520 passed, 3 skipped, 0 failed**.
- The skips are layout-dependent:
  - `test_with_auto_framer`: no columns found in that DXF;
  - two column-editor cases: no removable column.

---

## 2026-10-16 — Nothing simulated, storey drift, explicit site inputs, 3D viewer and walk-through

Commit: `fix: remove simulated outputs, add storey drift, explicit site inputs; add 3D viewer`.
Trigger: the owner's engineering mandate and the instruction "everything should be working, nothing should be
simulated, continue the 3D work — the site will be used by real developers at construction sites".

### Gap analysis (new document)
- `docs/assurance/gap-analysis.md` measures the code against the mandate. Earlier finding IDs are kept, and new
  findings N14–N22 are recorded with evidence, status, significance, verification method, correction and acceptance
  criteria. It also sets out the remediation roadmap P1–P8.

### Removed fabricated or simulated outputs (N14, N15, N22 — D-17, approved by the owner)
| Was | Now |
|---|---|
| Site Tools "Detailed Design Report" printed a fixed modal mass of 92.5 %, fixed drifts of 8 mm and 12 mm, and a "Mu = Min Eccentricity" sample | `src/documentation.py::calculation_summary` builds the summary only from the design run: inputs, seismic parameters, drift table, governing column with its real Pu/Mux/Muy and interaction ratio, the failures list and the checks not performed. Modal mass is stated as **not computed** |
| SHM tab: random strain heat map, a synthetic FFT, a "Damage Index / Health Score" from a slider | Uploaded accelerometer CSV → FFT (Hann window, uniform-sampling check) → dominant frequency; optional change against a baseline measurement, (f/f₀)²; uploaded strain-gauge CSV → strain / yield strain (fy/Es). No damage labels |
| Digital Twin tab: invented metadata (M40, "UltraTech", "2500 kN"), random as-built deviation, fake 4D schedule, dead MEP checkboxes | As-built survey: uploaded CSV of column id, x, y vs the design grid, with a tolerance the user must enter; member data comes from the design |
| Defect "classification" guessed causes and repairs from keywords (e.g. "shear capacity exceeded → FRP") | Defect log: records exactly what was observed; every entry says "Awaiting engineer review"; CSV export; map only for coordinates the user entered |
| QR code pointed at a non-existent domain | Real QR PNG (new dependency `segno`) holding the member's schedule as plain text |
| "Simulate AR Projection" placeholder image; default Bangalore crack on the map | Removed |
| COBie always "M25" | COBie from the design: real grade, column and beam types, bars, marks, coordinates |
| BBS cut list computed but never shown; "Run Cutting Optimization" did nothing | Real cutting plan from the stock bar length (first-fit decreasing per diameter); bars longer than stock are listed for laps; CSV export |
| Mix "per IS 10262" was a fixed guess (M15 silently used M25 values); pour planner assumed 1:1:2; dashboard and PDF used the same table | The user enters the approved mix (batch weights per m³); quantities come only from it; otherwise quantities are not given |
| Curing table with prop-removal instructions | Replaced by a cube-test register (mean / min / deviation; acceptance left to the engineer) |
| Formwork: beam sides at full depth, slabs 0 m², fixed plywood price | Slab thickness deducted from column and beam sides; slab soffit area from the model; no price |
| 3D view "Deflection" mode drew an invented sag (L² × 0.002) labelled "Simulated" | Removed |
| 3D/2D colours: beams by span / 7 m; columns by service stress / 0.4 fck with M25 assumed; GLB view painted every beam green (N22) | Designed utilisation: beams max(Ast,req/Ast,prov top/bottom, τv/τc,max); columns P-M interaction ratio; FAIL always red |
| Joint-shear table labelled every joint "Interior" | Shows each joint's real confinement case (beams on 4 / 3 faces, other) from the joint check |

Removed files: `src/shm_viz.py`, `src/digital_twin.py`, `demo_bim_site_shm.py`, `tests/test_viz_integration.py`
(that test only asserted simulated output).

### Storey drift (N16 — D-16)
- `analysis_integration`: inter-storey drift per column from the unfactored EQX/EQY/WLX/WLY displacements; largest
  ratio per storey and direction; top displacement.
- `design_pipeline.drift_checks`:
  - EQ drift above 0.004 × storey height → **FAIL**;
  - wind top sway above H/500 → **WARN**;
  - wind storey drifts are reported for information.
  - Limit values are as commonly cited and **UNVERIFIED** against the printed IS 1893 and IS 456.
- Design loop: an EQ drift failure grows every column stack by one preferred size per iteration.
- Results appear on:
  - the Analysis page (new "Storey Drift" section);
  - the PDF report status page;
  - the calculation summary;
  - the failures list.
- Effect: buildings that passed before can now fail. Example: a 20 × 15 m G+3 building in zone IV reached
  0.00462 > 0.004. After column growth it reached 0.00379.

### Status and inputs (N17, N18 — D-18)
- PASS is shown everywhere as "PASS for the implemented checks only — NOT VERIFIED". That covers the dashboard,
  the Reports page, the PDF and the calculation summary.
- `DesignResults.checks_not_performed` lists what StructOptima does not check: torsion, response spectrum,
  orthogonal combination, pattern loading, P-Δ / effective length, IS 13920 detailing, laps / anchorage, beam
  torsion and deflection, and footing moments / settlement.
- SBC has no default and must be typed.
- "Run Analysis" stays disabled until the SBC is entered and the site parameters are confirmed: SBC, seismic
  zone, soil type, wind zone and terrain category.
- Wind skipped → a WARN.
- The Reports page no longer falls back to zone II.

### Other analysis fixes
- N19: a column on a frame line in one direction only is flagged WARN; it gets no frame moments in the other
  direction.
- N20: the footing base moment is un-factored by each combination's own factor, not always by 1.5.

### 3D viewer and walk-through (visuals phases 3–4 — D-15 refinement PROPOSED)
- `src/viewer_model.py` builds a JSON scene from the design (members as boxes in metres, with mark, size, bars and
  status).
- `components/viewer3d` holds the three.js viewer. The source is `src/main.js`; the bundle `dist/viewer.js` is
  committed so Streamlit Cloud needs no npm.
- Features:
  - orbit view, and a walk-through at eye height (keyboard, drag to look, on-screen buttons for touch screens);
  - storey isolation and a section cut;
  - colour by member type or design status;
  - click a member for its data;
  - find members by mark.
- Shown on the Drawings page "3D View" tab; the older GLB view is kept behind a checkbox.
- Plain three.js was used instead of That Open Engine: there is no WASM inside the Streamlit iframe, and pointer
  lock is not available in that iframe.

### Site checklists
- Clause numbers that could not be verified were removed from the inspection prompts.
- The checklist values are marked "as cited, UNVERIFIED".
- The cover prompt refers to the drawings instead of a fixed 25 mm.

### Tests run
- Command: `PYTHONDONTWRITEBYTECODE=1 python -m pytest tests -p no:cacheprovider -q` → **520 passed, 3 skipped,
  0 failed**.
- New test files:
  - `tests/test_drift.py`: portal hand value 3.333 mm, model 3.356 mm;
  - `tests/test_site_tools.py`: hand values;
  - viewer tests in `tests/test_drawings.py`.
- New UI tests: SBC / confirmation gating, NOT VERIFIED status, no simulated values on Site Tools.
- The 3D viewer was rendered in headless Chrome and the screenshots were reviewed.

### Dependencies
- `segno==1.6.1` (Python, QR codes).
- Build-time only: `three` 0.170.0 and `esbuild` 0.24.0 (npm).

### Open
- Confirmation of the drift limits and of automatic column growth (D-16).
- Owner review of the viewer on a site tablet or phone.
- Torsion is not included in drift.
- Roadmap P2–P8 (`docs/assurance/gap-analysis.md`).

---

## 2026-10-16 — IFC export (visuals phase 2)

Commit: `feat(ifc): IFC4 export of the designed structure with design property sets`.
- `src/ifc_exporter.py` writes an IFC4 model of the designed structure: storeys, columns, beams, slabs, walls and
  footings.
- Every member carries a `Pset_StructOptima` property set: mark, size, bars, status, governing combination.
- Download on the Drawings page.
- `ifcopenshell==0.8.4.post1` added to `requirements.txt` (D-15).
- Test: `test_ifc_export_roundtrip` (export → re-import → counts, sizes, marks).

## 2026-10-16 — A3 site drawing set (visuals phase 1)

Commit: `feat(drawings): A3 site drawing set with marks, schedules and sections`.
- New `src/drawings/` package. One primitive model is rendered to SVG, DXF and PDF (ReportLab, D-14).
- Sheets:
  - S-01 column layout + schedule;
  - S-02 footing layout;
  - S-03 beams & slabs;
  - S-04 sections;
  - S-05 slab reinforcement;
  - S-06 footing sections;
  - continuation sheets.
- Marks C/B/F/S are shared with the Schedules page; FAIL members are drawn red and WARN members orange.
- Drawings page: pan/zoom viewer; downloads of the PDF set, a sheet as DXF, and a ZIP.
- Tests: `tests/test_drawings.py`. Developer visual review done; owner review of printed sheets pending.

## 2026-10-16 — N13: dead load from the designed slab thickness

Commit: `fix(N13): dead load uses each panel's designed slab thickness`.
- Problem: slabs were designed thicker (span/26 + 30 mm) than the occupancy slab used for dead load.
- Fix: each panel's extra weight is now added to beam, column, footing and seismic loads. This is the per-panel
  approach approved by the owner (D-12).
- Test: `test_N13_dead_load_uses_designed_slab_thickness`, against hand values.
- The manual walkthrough was regenerated with the new numbers.

## 2026-10-15 — Manual calculation walkthrough

Commit: `docs: add manual calculation walkthrough; record finding N13`.
- `docs/verification/manual-calculation-walkthrough.md` traces a whole building by hand, from loads to footings,
  mapping each output to its formula.
- That walkthrough found N13.

## 2026-10-15 — Audit remediation R1–R26, N1–N12

Commit: `fix: remediate audit findings R1-R26 and N1-N12; add design pipeline, benchmarks and docs`.
- One design pipeline (`src/design_pipeline.py::run_design`) with a single status and failures list.
- Columns designed for P-M biaxial bending with e_min and slenderness.
- Factored beam envelopes from 2D frames under DL/LL/EQ/WL with IS 456 / IS 1893 combinations.
- FEA sign and transformation fixes.
- Seismic weight, period and importance fixes.
- Footing reinforcement design.
- DXF unit handling; IFC import fixed.
- No file writes into the working directory.
- Full documentation set under `docs/` and FEA benchmarks.
- Details: `docs/assurance/remediation-log.md` RM-01 to RM-25.
