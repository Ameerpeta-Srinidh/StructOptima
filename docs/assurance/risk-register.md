# Risk Register

**As of:** 2026-10-15. Original audit IDs R1–R27 are preserved; N1–N12 were
found during stage-2 verification and remediation.

**Status rule:** no item is `RESOLVED_WITH_EVIDENCE` — that requires review by a
qualified engineer with documented benchmark evidence. Items with a code change
and passing regression tests are `UNVERIFIED` (fix implemented). Severity:
C critical · H high · M medium · L low. Confidence refers to the original finding.

| ID | Finding | Sev | Conf. | Location (pre-fix) | Impact if unaddressed | Verification / regression | Status | Decision | Remediation |
|---|---|---|---|---|---|---|---|---|---|
| R1 | Columns designed for axial load only (no moments, e_min, slenderness) | C | High | `grid_manager.optimize_column_sizes`, `rebar_detailer.detail_column` | Under-designed edge/corner columns | `test_R1_*`; SP:16 benchmark B6 pending | UNVERIFIED | — | RM-01 |
| R2 | Beam design moments unfactored (FEA 20 kN/m service) | C | High | `analysis_integration` (old), `rebar_detailer.detail_beam` | Under-designed beams (net effect interacted with R10) | `test_R2_*`; B4/B5 pending | UNVERIFIED | D-01 | RM-02 |
| R3 | Beam/slab loads ignore occupancy (hardcoded 20 kN/m, 12 kN/m², 5 kN/m²) | C | High | same + `detail_slabs` | Wrong beam/slab design for heavier occupancies | `test_R3_*`, `test_R20_*` | UNVERIFIED | — | RM-02 |
| R4 | Top steel fixed at 2-12#; compression steel never provided | C | High | `rebar_detailer.detail_beam` | Hogging regions under-reinforced | `test_R4_*` | UNVERIFIED | — | RM-03 |
| R5 | Failure screen read non-existent fields → always "no failures" | C | High | `pages/1_📊_Analysis.py` | False assurance | `test_R5_*`, UI tests | UNVERIFIED | D-09 | RM-04 |
| R6 | Audit compared service load to ultimate capacity, /1.5 on footings, fixed M25/SBC | C | High | `audit.py` | False PASS banner and audit report | `test_R6_*` | UNVERIFIED | D-01 | RM-04 |
| R7 | Seismic: height fixed 9 m, R = 5 assumed, W excluded masonry, irregularity checks unused | C | High | `app.py`, `seismic.py` | Wrong base shear; ESA used where not permitted | `test_R7_*`; B7 pending | UNVERIFIED | D-02, D-03 | RM-05 |
| R8 | Wind/seismic never reached member design; combination panel added horizontal to vertical loads | C | High | `pages/1`, `load_combinations` | Lateral effects absent from design | `test_R8_*`; B8 pending | UNVERIFIED | — | RM-06 |
| R9 | Optimiser: service load with 1.15 margin, fy 500, no e_min, "all safe" | C | High | `optimizer.py` | Unsafe size suggestions shown as safe | `test_R9_*`; B10 pending | UNVERIFIED | — | RM-07 |
| R10 | FEA span moment sign error (|M1| + wL²/8) | H | High | `fea_solver.get_member_forces` | Wrong design moments | `test_fea_benchmarks.py` | UNVERIFIED (VERIFIED_FOR_CASES numerically) | — | RM-08 |
| R11 | FEA element forces mixed global stiffness with local displacements | H | High | `fea_solver.solve` | Wrong column forces | `test_column_axial_force_equals_half_beam_load` | UNVERIFIED (VERIFIED_FOR_CASES) | — | RM-08 |
| R12 | Gravity UDL reversed for beams drawn right-to-left | H | High | `fea_solver` | Upward loads on DXF beams | `test_beam_orientation_does_not_change_results` | UNVERIFIED (VERIFIED_FOR_CASES) | — | RM-08 |
| R13 | BOM dropped beam steel (per-level ids); report used 4 m spans / 16 m² slabs | H | High | `quantifier`, `report_gen`, pages | Wrong quantities/cost | `test_R13_*` | UNVERIFIED | — | RM-09 |
| R14 | IFC import unusable (AttributeError / ValidationError, no grid, no units) | H | High | `bim_loader.py` | Feature broken | `test_R14_ifc_import_roundtrip`, `test_ifc_through_pipeline` | UNVERIFIED (synthetic IFC only) | — | RM-10 |
| R15 | SCWB/joint/ductility checks were placeholders | H | High | `seismic.py`, `safety_warnings.py` | False "SCWB PASS" in UI/PDF | `test_R15_*`; B9 pending | UNVERIFIED | D-02 | RM-11 |
| R16 | Footing reinforcement not designed; flags hardcoded True | H | High | `foundation_eng.py` | Missing design; false flags | `test_R16_*`; B11 pending | UNVERIFIED | D-06 | RM-12 |
| R17 | DXF units guessed by size; Tier-2 used every line as a wall | H | Medium | `cad_loader`, `cad_parser` | Scale errors; spurious wall loads | `test_R17_*` | UNVERIFIED | — | RM-13 |
| R18 | CAD with columns but no beams crashed (IndexError) | H | High | `analysis_integration` (old) | Crash | `test_R18_missing_beams_are_generated` | UNVERIFIED | — | RM-14 |
| R19 | Takedown omitted beam self-weight; roof = floor load; stale column self-weight; DXF walls used 3 m storey | M | High | `grid_manager.calculate_loads`, `cad_loader` | Load under-estimate | `test_R19_*` | UNVERIFIED | — | RM-15 |
| R20 | Slab load fixed 5 kN/m², αx fixed 0.087, boundary inconsistency at ly/lx = 2 | M | High | `rebar_detailer.detail_slab` | Wrong slab design | `test_R20_*`; B12 pending | UNVERIFIED | D-05 | RM-16 |
| R21 | Grade/steel not propagated (FEA, beams, stairs, audit, seismic fy 500); `assume_fixed` unused | M | High | multiple | Inconsistent design | `test_R21_*`, `test_pinned_base_*` | UNVERIFIED | — | RM-17 |
| R22 | Optimiser cache ignored column data (stale results) | M | High | `pages/1` | Stale display | code review (fingerprint key) | UNVERIFIED (no automated test) | — | RM-07 |
| R23 | No conditioning check; garbage results possible; slab division by zero | M | Medium | `fea_solver`, `detail_slab` | Silent wrong results / crash | `test_mechanism_is_detected_not_solved` | UNVERIFIED | — | RM-08, RM-16 |
| R24 | Fire check covers inconsistent with design; slenderness returned dict on bad input | M | High | `stability.py` | Wrong fire check; crash | `test_R24_*` | UNVERIFIED | — | RM-18 |
| R25 | Unsupported compliance / verification claims | M | High | `report_gen`, docs | Misleading users | text review; PDF banner | UNVERIFIED | D-09 | RM-19 |
| R26 | Column grouping could reduce size by ≤ 15 mm | L | High | `optimize_column_sizes` | Minor under-size | `test_R26_*` | UNVERIFIED | — | RM-15 |
| R27 | Repository clutter (generated files, scripts, archived code); `ifcopenshell` not in requirements | L | High | repo root | Confusion | — | BLOCKED | D-07 | — |
| N1 | `app.py` read non-existent `live_load_kn_m2` → LL 2.0 for every occupancy in seismic weight | H | High | `app.py` (old) | Seismic weight wrong for heavier occupancies | pipeline uses `live_load_floor_kn_m2`; `test_R7_*` | UNVERIFIED | — | RM-05 |
| N2 | Importance factor looked up by first word of occupancy | M | High | `seismic.py` | I = 1.0 for institutional/assembly | `test_R7_importance_*` | UNVERIFIED | D-03 | RM-05 |
| N3 | Schedules page computed its own pass/fail from service load | H | High | `pages/2_📋_Schedules.py` | Second false-status source | UI tests (render only) | UNVERIFIED | — | RM-04 |
| N4 | BBS matched beams by per-level id (no beams) and used hardcoded bars/slab sizes | M | High | `bbs_report.py` | Wrong BBS | `test_R13_bbs_*` | UNVERIFIED | — | RM-09 |
| N5 | `get_logger` created `structural_design.log` in the CWD on import | L | High | `logging_config.py` | Unexpected files; tracked rotated log | UI test run checks no repo writes | UNVERIFIED | — | RM-20 |
| N6 | Wind base shear X/Y labels swapped (wrong face) | M | High | `wind_load.py` | Wrong direction of wind forces | `test_NEW_live_load_field_and_wind_direction` | UNVERIFIED | — | RM-06 |
| N7 | Slab-panel rule (3 of 4 corners) filled L-shape notches and dropped enclosed interior bays | M | High | `grid_manager.slab_panels` (introduced and corrected during remediation; the old takedown had the same full-grid assumption) | Wrong loads / false irregularity | `test_panels_exclude_l_shape_notch_*` | UNVERIFIED | — | RM-21 |
| N8 | Parser ignored entities on undeclared layers; many repository DXFs declare `$INSUNITS = 6` while drawn in mm | M | High | `cad_parser`, data | Missed geometry; 1000× scale | `test_R17_*` | UNVERIFIED (plausibility fallback only detects extents outside 1–1000 m) | — | RM-13 |
| N9 | CLI logger named `__main__` outside the configured tree (INFO lost) | L | High | `main.py` | Missing CLI output | manual CLI run | UNVERIFIED | — | RM-20 |
| N10 | Drawings page wrote DXF exports into the CWD (overwrote tracked files) | M | High | `pages/3_📐_Drawings.py` | Repository files overwritten | `test_every_page_renders_after_analysis` asserts empty CWD | UNVERIFIED | — | RM-22 |
| N11 | Footing design divided by zero for absurd loads (spacing 0) | M | High | `foundation_eng.py` | Crash | DXF sweep (0 crashes) | UNVERIFIED | — | RM-12 |
| N12 | Explicit DXF column outlines in drawing units other than mm were not converted | M | Medium | `cad_loader` | Wrong column sizes | `test_R17_insunits_drives_scale` | UNVERIFIED | — | RM-13 |
