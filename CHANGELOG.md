# Changelog

All changes made during the October 2026 audit, remediation and feature work, newest first.
Finding IDs (R*, N*, KD-*), decisions (D-*) and remediation records (RM-*) point to the detailed records in
`docs/assurance/`. Nothing listed here has been reviewed by a licensed structural engineer; every output of
StructOptima remains **preliminary and NOT VERIFIED**.

Each entry states what changed, why, the evidence (tests actually run) and what is still open.

---

## 2026-10-21 — DXF robustness: geometry bound, memory safety, DXF corpus, decisions D-32–D-38

- **OOM kills explained and fixed (N50, D-32 approved):** a line drawn far from the building made the automatic
  column placement create 3 × 10^8 nodes (~12 GiB). Geometry that is not finite or wider than 1000 m is now an input
  error before any calculation.
- **Non-finite results never pass (N51, N52):** NaN / infinite design forces stop the design; a non-finite seismic
  weight or base shear is a FAIL "Numerical failure".
- **DXF corpus** (`tests/dxf_corpus.py`): 74 named drawings + seeded random buildings in every supported convention.
  It found 8 defects, all fixed (N53–N60): mirrored blocks read mirrored; R12 polyline walls crashed the loader;
  unitless / R12 drawings and drawings with survey coordinates read at the wrong scale; circular columns on layer 0
  dropped and grid bubbles read as columns; rotated plans misread; one or two columns crashed the dynamic analysis;
  warnings repeated; IFC export, 3D viewer and drawings broken by a column beyond its capacity.
- **Drafting habits (N61–N64):** MINSERT column arrays read in full; a beam line drawn through several columns is
  one beam per span; columns drawn as four LINEs read (D-39); frozen / off layers not read (D-40); overlapping
  outlines merged (D-41); curved beams warned; NaN coordinates refused.
- **Design inputs validated (N65, D-42):** every caller of the design (Setup page, CLI, API) gets one clear input
  error for values outside the Setup page ranges; before, negative storeys, fy = 0 or an unknown soil crashed and
  SBC <= 0 was designed. UI tests feed damaged, degenerate, rotated and unitless drawings to the Setup page.
- **Decisions taken under the owner's delegation (engineer review pending):** D-33 a slab panel is required; D-34
  rotated plans are rotated back to the axes; D-35 drawing units inferred from the columns; D-36 circular columns on
  unnamed layers need two members framing in; D-37 column orientation rule deferred (needs a new hand check); D-38
  a column beyond capacity is shown as "beyond capacity", never as a number.
- **Testing:** `tests/run_suite.py` runs every file sequentially under a memory cap (CLAUDE.md resource rules);
  nightly CI job with 300 random buildings and 300 random drawings (not yet observed running).
- **Evidence:** full sequential run 1222 passed, 3 skipped, 3 xfailed, 0 failed; 1000 random DXF buildings passed;
  30 of the corpus tests fail on the code before the corpus fixes. New documents: `docs/engineering/supported-inputs.md`, `docs/assurance/readiness-gates.md`.
- **Open:** column orientation under plan rotation (N49 / D-37); engineer review of D-32–D-38; readiness gate H.

---

## 2026-10-20 — D-28 and N46 approved; residential columns match 230 mm walls (D-29)

- **D-28 approved** (DXF layer roles).
- **N46 fixed (D-30, approved):** the beam web self-weight no longer counts the slab strip that a thicker panel
  already carries to the beam centre line. Applies to beam loads, the column takedown and the seismic weight.
  Worked example (`complex_house.dxf`): W 4052.5 → 3989.5 kN, VB 101.3 → 99.7 kN, B5 load 37.22 → 36.69 kN/m.
  The formula document's Appendix A was updated.
- **D-29 (owner request), residential columns in 230 mm wall lines:** these columns get a 230 mm side across the
  wall, and the other side (450–900 mm) comes from the load.
  - Applies only where the codes allow it:
    - Zone II with OMRF (IS 13920:2016 1.1.1 and 7.1.1 require 300 mm in Zones III–V and for SMRF);
    - columns standing in a wall line (IS 456 Fig. 1: 300 mm for 2 h when free-standing; 200 mm "50 % exposed"
      for a column in a wall);
    - long side at most 900 mm (IS 456 32.1).
  - Where walls meet, orientations are balanced between x and y.
  - Growth goes along the wall unless bending about the 230 side governs.
  - Beams into a 230 side are made 230 wide, and a deep 300 mm beam widens the column.
  - Setup toggle (Materials & modelling), on by default.
- **New check for every design (N48):** a beam wider than the column it frames into (WARN).
- Tests: `test_wall_width_columns.py` (10) and a UI test; corrected hand values in the N13 and hand-check tests.
  Full suite **809 passed, 3 skipped**. 92-drawing sweep: 0 crashes. Torsional irregularity FAILs appear in 2
  drawings where the 230 columns make the plan's stiffness uneven.

---

## 2026-10-20 — Worked hand check; DXF drawings read the way each engineer draws them

### Worked hand check (formula document, Appendix A)
- `samples/plans/complex_house.dxf` (L-shaped G+2, Zone II, SMRF) checked by hand against the printed formulas.
  Every value agrees:
  - slab S1;
  - seismic weights 1450.2 / 1450.2 / 1152.0 kN and VB 101.3 kN;
  - beam B5 steel and stirrups;
  - column C5 (SP 16 Chart 49);
  - footing F-C5;
  - the SCWB roof joint of C1 (0.98, FAIL).
- The check is locked in `tests/test_hand_check_complex_house.py`.
- Findings:
  - beams are designed once for their worst floor (now documented);
  - N46: 0.5 kN/m of slab over each beam is counted twice (conservative; fix PROPOSED);
  - N47: three DXF problems, fixed below.

### DXF reading (D-28, PROPOSED; RM-37)
- **Layer roles from names and shapes** (new `src/dxf_layers.py`). Each layer's role is suggested from its name
  (wider vocabulary) and from what is drawn on it:
  - column-sized outlines;
  - lines running from column to column;
  - wall-thickness line pairs;
  - grid lines.

  Layers named "Layer 7", "STAMBH" or anything else are read correctly, and a drawing with everything on layer 0 is
  sorted by shape.
- **Engineer's confirmation on the Setup page:** a table of every layer (what it holds, how it is read, why, and the
  confidence) with *Read as* editable, plus a plan preview of the columns, beams and walls that will be used. A
  changed role marks the results out of date.
- **Plinth / lintel beam layers** are ignored by default; they were read as floor beams before.
- **New reports:**
  - columns drawn at another size than designed ("Drawing vs design" WARN);
  - room labels lying outside the structure that was read.
- **No change for existing drawings:** all 92 sample drawings give the same columns, beams and status as before.
- Tests: `test_dxf_layers.py` (16), the Setup-page DXF test; full suite **798 passed, 3 skipped**.

---

## 2026-10-20 — D-27 approved; documentation brought up to date; formula document

- **D-27 approved by the owner:** a soft storey is flagged only when the computed storey stiffness is more than 10 %
  below the storey above. No code change; `src/design_pipeline.py` comment updated.
- **New formula document:** `docs/formulas/StructOptima-Formulas.tex`, with the compiled
  `StructOptima-Formulas.pdf` and `build.sh`. It holds every formula, constant table, decision and edge case as
  implemented, with a dated revision history. Its tables were compared with the constants in the code.
  `CLAUDE.md` now requires a dated update and a rebuild after every check or change.
- **Documentation now describes the 3D rigid-diaphragm model, response spectrum and torsion** instead of
  "2D frames, no torsion":
  - README;
  - docs index, system overview, module catalogue, data models, interfaces, execution flows, dependency map,
    repository inventory;
  - calculation catalogue (new CAL-SEI-10 to 14 and CAL-DUR-01/02; stale covers, fire table and statuses
    corrected), assumptions register (A-SEI-01 rewritten, A-SEI-06 added);
  - known defects KD-04, KD-18, KD-24; gap analysis progress table; troubleshooting (new FAIL / WARN messages);
  - user guide, manual walkthrough, benchmark B8.
- Tests: 774 passed, 3 skipped (unchanged).

---

## 2026-10-20 — Dynamic analysis (response spectrum on a 3D rigid-diaphragm model)

Owner: "do the dynamic analysis part if we can, otherwise keep it as WARN with more info". Decisions D-26 (approved)
and D-27 (proposed), remediation RM-36.

### What it does
- **3D model** (`src/pseudo3d.py`): one rigid-floor model with 3 degrees of freedom per floor (X, Y, rotation),
  assembled from the condensed lateral stiffness of every plane frame. Floor mass, centre of mass and rotational
  inertia come from the slab panels.
- **Response spectrum method (IS 1893 7.7.5), used for every building:**
  - all modes, with the number needed for 90 % of the mass reported;
  - spectrum of 6.4.2(b), CQC combination;
  - scaled up to the static base shear (7.7.3).
- **Torsion (7.8.2):** design eccentricity 1.5 e_s + 0.05 b or e_s − 0.05 b, whichever is more severe for each frame.
  Torsion loads the frames of the other direction too, and column axial forces now add both directions.
- **New checks:**
  - torsional irregularity ratio (Table 5(i), Amendment 2): FAIL above 1.4; between 1.2 and 1.4, FAIL unless the
    torsional period is below the translational ones;
  - irregular modes (Table 6(vii), Amendment 2);
  - soft storey: with the dynamic analysis performed, FAIL only if drift exceeds 0.2 %; drops of the computed
    stiffness up to 10 % are ignored (D-27).
- **"Seismic method" is no longer a FAIL:**
  - re-entrant corners and large openings (which need flexible floors) give a WARN describing the check to do in
    ETABS / STAAD;
  - floors without torsional restraint give a WARN explaining that static forces were used.
- **Checks page, Seismic tab:** method used, static / dynamic / design base shear, scale factor, modes for 90 % of the
  mass, torsion ratio, design storey forces per direction, and the modes table.
- **CI:** installs the test-only `pypdfium2` (N28).

### Tests run
- `PYTHONDONTWRITEBYTECODE=1 python -m pytest tests -p no:cacheprovider -q`: **774 passed, 3 skipped**.
- New `tests/test_pseudo3d.py` checks against hand results:
  - symmetric building with ±0.05 b eccentricity → 0.525 F on the worse frame;
  - eccentric stiffness → 50.5 kN, worked by hand;
  - two-storey shear building periods (closed form);
  - single-storey response spectrum = Ah W;
  - 7.7.3 scaling; CQC equals SRSS for well-separated modes and the algebraic sum for equal ones.
- DXF sweep, Zone III SMRF: 0 crashes, all 90 drawings analysed with the response spectrum method.

---

## 2026-10-20 — Check against the printed standards, DXF import and analysis fixes

Owner instruction: "check whatever you need to check and change whatever is wrong". The code's values were compared
with the printed IS 456, IS 1893, IS 13920, IS 875, IS 1786, NBC Part 4 and SP 16. Evidence for every item is in
`docs/verification/standards-check-2026-10-20.md`; findings N29–N45, RM-35, decisions D-21–D-25.

### Main changes
- **Seismic:** the static method now uses the IS 1893:2016 rule (7.7.1) instead of the 2002 limits, so most designs
  now FAIL "Seismic method" until a dynamic analysis exists. Other changes:
  - no 1 + 15T rising branch in the static spectrum (VB was up to 16 % low);
  - minimum VB from Table 7;
  - OMRF not allowed in Zones III–V;
  - soft storey, mass irregularity and floating-column checks per Amendment 2.
- **IS 13920 (Amendments 1 and 2):**
  - joint factor and effective breadth;
  - roof strong column – weak beam waiver only above 4 storeys;
  - minimum grade by height, and the reinforcement elongation requirement;
  - column size ≥ 300 mm and ≥ 20 × the largest beam bar, aspect ratio ≥ 0.4, axial stress ≤ 0.40 fck;
  - hooks 8d ≥ 75 mm; end-zone spacing 6d.
- **IS 456:**
  - Table 26 case 4 coefficient 0.047;
  - M15 row of Table 19;
  - new **exposure** input: covers from Table 16/16A used through the whole design, minimum grade from Table 5;
  - fire per NBC Part 4 Table 1, with a new **type of construction** input;
  - fire and slenderness failures now reach the status list.
- **IS 875:** office imposed load 4.0 kN/m²; wind k2 from the printed Table 2; slender buildings (h/w ≥ 6) FAIL.
- **Analysis:** storey forces are shared between frames as for a rigid floor, with slab links. This removes false
  drift FAILs and unconservative forces in stiffer frames.
- **DXF import:** rewritten. It now handles NCS and Indian layer names, blocks, POLYLINE and circular columns, plans
  inside blocks, misalignment, survey coordinates, beams drawn to column faces, duplicates and units. Leaders are no
  longer read as columns.

### Tests run
- `PYTHONDONTWRITEBYTECODE=1 python -m pytest tests -p no:cacheprovider -q`: **763 passed, 3 skipped**.
- DXF sweep of the 92 sample drawings: 0 crashes.

---

## 2026-10-20 — UI restructure and display defects

Requested by the owner: "work on the UI … give a seamless experience to the engineer". Decision D-20 (layout
PROPOSED pending owner review), remediation RM-34. No engineering formula, load, combination or cited value changed.

### Why
A review of every screen (screenshots at desktop and tablet width, before and after, in `_local/ui-audit/`) found:
- layout problems: about 30 inputs packed into a narrow sidebar that the other pages did not show; an empty main
  page before a run; the failure list at the bottom of a long page; duplicate navigation; reports and DXFs
  regenerated on every page load;
- display defects:
  - **N23** — the footing schedule always showed punching shear "OK", because it read an attribute that does not
    exist, and its steel figure was volume × 80 kg/m³ instead of the designed steel;
  - **N24** — the header showed "111/111 pass" in green while the design status was WARN;
  - **N25** — the slab schedule had no status column;
  - **N26** — after an input change the old results stayed on screen with no notice.

### Changes
- **Navigation:** a top bar with Setup · Overview · Checks · Members · Drawings & 3D · Reports · Site tools. The page
  files were renamed without emoji (`pages/checks.py` etc., git history kept).
- **Setup:** all inputs in five tabs on the main page, with a plan preview. A run panel lists exactly what is
  missing. Inputs are kept when you switch pages (`src/ui_state.py`). Changing a site parameter clears the site
  confirmation.
- **Out-of-date results:** an input fingerprint is stored with each run. The header and every result page say when
  the inputs have changed since.
- **Overview:** status banner, checks not performed, a filterable issue list (FAIL first), 3D model, quantities and
  the column editor.
- **Checks:** one tab per topic, with the failure report first. The mass–stiffness offset screen no longer shows a
  green "no torsional irregularity"; it is labelled a screen (KD-16).
- **Members:** column, beam, slab and footing schedules with coloured status columns. The rows come from
  `src/ui_tables.py`, which reads only the design results: the footing table shows bearing, punching, one-way shear
  and bending separately, plus the designed steel. Members sort naturally (C2 before C10).
- **Drawings & 3D:** only the selected view is generated. The A3 sheet fits the viewer, and pinch-zoom works on
  tablets. Downloads are built on click.
- **Reports:** generated on click. The ZIP package includes `_NOT_INCLUDED.txt` naming any part that failed (it
  was silently skipped before).
- **Site tools:** the BBS total is labelled with its scope (one typical floor).
- **Theme:** Inter font, borders and radius in `.streamlit/config.toml`; most hand-written CSS removed.
- **Standards:** `docs/engineering/standards-to-obtain.md` lists the IS codes and high-rise inputs to obtain (PDFs go
  in the git-ignored `_local/standards/`).

### Tests run
- `PYTHONDONTWRITEBYTECODE=1 python -m pytest tests -p no:cacheprovider -q -rs`: **545 passed, 3 skipped, 0 failed**
  (Ubuntu, Python 3.12.15, streamlit 1.53.0, with `pypdfium2` installed). The 3 skips are the same layout-dependent
  ones as before.
- New: `tests/test_ui_tables.py` (14) and a rewritten `tests/test_streamlit_app.py` (21).

### Still open
- Owner review on a site tablet.
- N27 / KD-21: the BBS falls back to default bars and panel size when a description cannot be parsed (engineering
  change, needs approval).
- N28 / KD-22: `pypdfium2` is missing from `requirements.txt`.

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
