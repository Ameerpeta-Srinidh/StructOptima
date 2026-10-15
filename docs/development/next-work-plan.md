# Next Work Plan — N13 fix and site-quality visuals

**Created:** 2026-10-15 (end of session; to be resumed). **Base:** `main` at `986c090`.
Status vocabulary and rules: see `CLAUDE.md` and [../README.md](../README.md).

## 0. Decisions needed from the owner at the start of the next session

| # | Question | Default if not answered |
|---|---|---|
| Q1 | Approve the N13 load change (dead load from the designed slab thickness)? | **Approved 2026-10-16** |
| Q2 | N13 approach: per-panel thickness (recommended) or one governing thickness for the whole floor? | **Per-panel (approved)** |
| Q3 | Drawing conventions | **Approved: letters X / numbers Y, A3, 1:100 / 1:20, C/B/F/S marks (D-13)** |
| Q4 | PDF route for drawings | **Approved: ReportLab + ezdxf SVG (D-14)** |
| Q5 | Approve adding `ifcopenshell` to `requirements.txt` (Phase 2)? | **Approved (D-15)** |
| Q6 | Approve adding a JavaScript build (npm/Vite) for a custom Streamlit component (Phases 3–4)? | **Approved (D-15)** |

---

## Part A — Fix finding N13 (slab thickness vs dead load) — DONE 2026-10-16 (RM-26)

**Defect:** slabs are designed with t = max(⌈(lx/26 + 30)/5⌉·5, 125, occupancy t), but floor/roof dead
load used for beams, columns, footings and seismic weight uses the occupancy slab thickness.
Reference case: 8 × 8 m walkthrough building — slab 185 mm designed, 125 mm in loads
(≈ 1.5 kN/m² missing). Evidence: `docs/verification/manual-calculation-walkthrough.md` §10.

**Only after Q1 approval.** Steps (test-driven, per CLAUDE.md):

1. **Reproduce:** add a failing test in `tests/test_audit_findings.py` (`test_N13_dead_load_uses_designed_slab_thickness`): for the walkthrough building, the beam service UDL and column DL must include 25 × t_designed.
2. **Single thickness rule:** move the rule into one helper, e.g. `GridManager.panel_slab_thickness_mm(panel)`, used by `detail_slabs` and by loads.
3. **Loads (per-panel, Q2):**
   - `analysis_integration.beam_case_loads` / `beam_slab_coefficients`: accumulate k × (25·t_panel + SDL) per panel side instead of k × one floor DL.
   - `GridManager.calculate_loads`: column slab DL from the panels around the column (area-weighted), not one intensity.
   - `design_pipeline.storey_seismic_weights`: Σ panel area × (25·t_panel + SDL).
   - Keep roof SDL rule (no partitions).
4. **Iteration order:** slab thickness depends only on spans → compute once before the design loop.
5. **Tests:** new N13 test passes; update any test that hard-codes 6.125 kN/m² only if it uses the pipeline path; full suite green.
6. **Docs:** regenerate all numbers in the walkthrough (use the dump script recipe: run the reference building, print intermediate values, re-derive by hand); update calculation catalogue CAL-LOD-01/03/04/05, assumptions, risk register (N13 → UNVERIFIED, fix implemented), remediation log, verification results.

Size: small–medium (≈ 1 session together with the start of Part B).

---

## Part B — Visual outputs for site engineers

Goal: drawings a site engineer can print and build from, consistent with the schedules and BBS,
plus an inspectable 3D model. Research summary and licences: see the chat of 2026-10-15
(That Open Engine MIT + web-ifc MPL-2.0; ezdxf MIT with SVG/PDF backends since 1.1;
ifcopenshell LGPL; three.js MIT; xeokit AGPL — avoid; Speckle — hosted, avoid).

### Phase 1 — Site drawing set (no new dependency for DXF/SVG) — DONE 2026-10-16 (RM-27); owner review of printed sheets pending

**New package** `src/drawings/` (keep `dxf_exporter.py` until replaced):

| Task | Detail |
|---|---|
| B1.1 Sheet framework | A3 sheet, border, title block (project, engineer, drawing no., sheet, scale, date, revision, "PRELIMINARY — NOT FOR CONSTRUCTION"), north arrow, scale bar, legend, notes area; standard layers, text styles and lineweights |
| B1.2 Grid & dimensions | Grid bubbles (letters/numbers per Q3), overall and bay dimensions, setting-out dimensions to grid |
| B1.3 Member marking | Group identical members (same size + bars) → marks C1, C2…, B1…, F1…, S1…; the same marks appear in the Schedules page, PDF schedules and BBS (single mapping function) |
| B1.4 S-01 Column layout | Column outlines to scale with orientation, marks, size tags; column schedule table (mark, size, bars, ties per level, status) |
| B1.5 S-02 Footing layout | Footing outlines, marks, sizes, depth, centre-to-grid dimensions; footing schedule (size, depth, bottom steel) |
| B1.6 S-03 Beam layout (per floor) | Beam centre lines/outlines, marks, size labels, slab panels with thickness and mesh notes; beam schedule |
| B1.7 S-04 Typical sections | Column section (bars to scale, ties, cover), beam sections at support and mid-span (top/bottom bars, stirrups), footing section (bars, cover, PCC); generated from designed values; "typical detail" notes where design does not compute (laps, curtailment) |
| B1.8 S-05 Slab reinforcement plan | Bottom mesh per panel, top bars over continuous edges, notes |
| B1.9 Rendering | DXF → SVG via `ezdxf.addons.drawing.svg.SVGBackend`; PDF via Q4 choice; all files in a temp directory (never CWD) |
| B1.10 UI | Drawings page: sheet selector, zoomable SVG, per-sheet DXF/PDF download and a ZIP of the set; status colours/flags for FAIL/WARN members |

**Tests:** each sheet builds without error for manual, DXF and IFC sample models; DXF contains expected layers/entities; every column/beam/footing has a mark; marks match schedule groups; SVG/PDF non-empty; no files written to CWD (extend `tests/test_streamlit_app.py`).
**Acceptance:** owner review of printed A3 sheets against a checklist (legibility, marks, dimensions, sections match schedules).
Size: large (≈ 2 sessions).

### Phase 2 — IFC export (needs Q5)

- `src/ifc_exporter.py`: IfcProject/Site/Building/Storeys; IfcColumn, IfcBeam, IfcSlab, IfcFooting, IfcWall with extruded rectangular profiles; property set (mark, size, bars, ties/stirrups, status, governing combination); optional IfcReinforcingBar later.
- Download button on Drawings/Reports pages.
- Tests: export → `BIMLoader` round-trip (counts, sizes, storeys); file opens with ifcopenshell; skip if ifcopenshell missing.
Size: medium (≈ 1 session).

### Phase 3 — In-browser 3D viewer (needs Q6)

- Custom Streamlit component `components/structoptima_viewer/` (Vite + `@thatopen/components` + web-ifc); commit the built bundle so Streamlit Cloud needs no npm.
- Features: orbit, storey isolation, section planes, measurement, click member → properties panel, colour by status, highlight a mark from the schedules.
- Fallback: current model-viewer GLB when the component fails.
- Tests: AppTest renders the page; manual browser checklist (JS not testable with AppTest).
Size: large.

### Phase 4 — First-person walkthrough (needs Q6)

- three.js `PointerLockControls` (WASD, 1.7 m eye height, storey switching, collision with slabs only) in the same component, reusing the trimesh GLB or the IFC.
- **Risk to prototype first:** pointer lock inside Streamlit's component iframe (browser user-gesture/permissions).
Size: medium.

---

## Suggested session order

1. Answer Q1–Q6 → Part A (N13) → B1.1–B1.3.
2. B1.4–B1.10 (drawing set complete, UI integrated).
3. Phase 2 (IFC export).
4. Phases 3–4 (viewer and walkthrough).

Each session ends with: full test suite (side-effect-free command), docs updated per CLAUDE.md, commit, push only when the owner asks.
