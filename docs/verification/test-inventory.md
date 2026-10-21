# Test Inventory

**As of:** 2026-10-21. 1160 collected tests in 53 files (2026-10-21 full sequential run: 1154 passed, 0 failed, 3 skipped,
3 xfailed — see [verification-results.md](verification-results.md)). Time, memory and the
runner layers of every file: [test-execution-guide.md](test-execution-guide.md).

Classification of the strongest assertion type in each file:
**E** executes only · **A** structural/boolean assertions · **N** meaningful numerical assertions · **R** numerical assertions against an independently derived reference (closed form / hand calculation in the test) · **UI** headless UI smoke.

| File | Tests | Type | Production modules covered | Notes / side effects |
|---|---|---|---|---|
| `test_fea_benchmarks.py` (new) | 9 | R | `fea_solver` | Closed-form beam/portal/cantilever, orientation, superposition, mechanism |
| `test_fea_repro.py` (rewritten) | 2 | R | `fea_solver` | Portal statics + slope-deflection (axially rigid) |
| `test_section_design.py` (new) | 10 | R | `section_design` | Annex-G / stress-block equilibrium, doubly reinforced equilibrium, shear rules, interaction end points, independent pure-bending solution |
| `test_audit_findings.py` (new) | 36 | R/N/A | pipeline, analysis, detailing, seismic, wind, footing, audit, optimiser, CAD, IFC, quantities | One or more tests per finding R1–R26 and N-findings; writes DXF/IFC only to `tmp_path` |
| `test_pipeline_e2e.py` (new) | 15 | A/N | `design_pipeline`, reports, exporters, CAD/IFC ingest, CLI | PDFs/Excel to `tmp_path`; CLI with file logging monkeypatched off; reads repository DXFs |
| `test_drift.py` (new 2026-10-16) | 5 | R | `analysis_integration`, `design_pipeline` | Portal drift vs hand value, cracked modifier ratio, limits/status, pipeline drift rows, one-plane column flag |
| `test_site_tools.py` (new 2026-10-16) | 9 | A | `site_calculators`, `site_monitoring` | Hand values for materials, pour, formwork, cubes, cutting plan, FFT, strain, survey, member info / QR |
| `test_drawings.py` (new 2026-10-16) | 13 | A | `src/drawings` | Sheets present and ordered, every member marked, identical marks = identical detailing, schedules carry marks and statuses, void marked, PDF/SVG/DXF consistency, large-plan scaling, CAD and IFC inputs, no files written |
| `test_streamlit_app.py` (rewritten 2026-10-20) | 23 | UI | `app.py`, all pages, `ui_state` | `streamlit.testing.AppTest`: every page after a run and without one, run gating, site confirmation cleared on change, inputs kept across pages, out-of-date results, BBS scope; CWD = `tmp_path` (no page may write to it) |
| `test_wall_width_columns.py` (new 2026-10-20) | 10 | B | `design_pipeline`, `stability` | 230 mm wall columns (D-29): orientation across the wall, long side <= 900, not in Zones III-V / SMRF, occupancy, fire 50 % exposed, balanced junctions on complex_house.dxf, beam wider than column |
| `test_dxf_layers.py` (new 2026-10-20) | 16 | B | `dxf_layers`, `cad_parser`, `cad_loader` | Layer roles from names (NCS, Indian) and from shapes (default names, other languages, everything on layer 0), plinth / lintel layers, confirmed mapping, room labels outside the structure, drawn-vs-designed WARN |
| `test_hand_check_complex_house.py` (new 2026-10-20) | 7 | A | pipeline | Worked hand check of samples/plans/complex_house.dxf (formula document Appendix A): slab, seismic weight and VB, beam, column, footing, SCWB |
| `test_pseudo3d.py` (new 2026-10-20) | 7 | B | `pseudo3d` | Hand checks of the rigid-diaphragm model: eccentricity, eccentric stiffness, shear-building periods, SDOF response spectrum, scaling, CQC, rotational stability |
| `test_is1893_2016.py` (new 2026-10-20) | 33 | A | `seismic`, pipeline | 6.4.2(a) spectrum, minimum VB (Table 7), 7.7.1 method rule, Table 9 Note 1, Table 6 soft storey / mass / floating columns, 6.4.3.1 |
| `test_is13920_2016.py` (new 2026-10-20) | 23 | A | `seismic`, `bbs_module`, pipeline | Joint factor and breadth (Amd 2), minimum grade, roof SCWB, steel properties, column geometry and axial stress, hooks, end-zone spacing |
| `test_is456_tables.py` (new 2026-10-20) | 16 | A | `rebar_detailer`, `section_design` | Tables 19, 20, 26 compared with an independent copy of the printed tables |
| `test_durability.py` (new 2026-10-20) | 18 | A | `durability`, `stability`, pipeline | Tables 5, 16, 16A, Fig. 1, NBC Table 1; covers reach the design; grade and fire failures |
| `test_is875_wind.py` (new 2026-10-20) | 7 | A | `wind_load` | Table 2 k2, Vb, h/w ≥ 6 |
| `test_sp16_benchmarks.py` (new 2026-10-20) | 45 | B | `section_design` | SP 16 Tables A, C, D, F and Examples 1, 2, 3, 6, 9, 10 |
| `test_lateral_sharing.py` (new 2026-10-20) | 3 | B | `analysis_integration` | Rigid-diaphragm sharing: 12 : 3 hand split, equal frames, common drift |
| `test_dxf_conventions.py` + helper `dxf_conventions.py` (new 2026-10-20) | 23 | E2E | `cad_parser`, `cad_loader`, pipeline | Real drafting conventions (see verification results 5d) |
| `test_realistic_buildings.py` (new 2026-10-20) | 54 | E2E | pipeline | 9 realistic buildings: clause values recomputed, equilibrium, plausibility ranges |
| `test_ui_tables.py` (new 2026-10-20) | 14 | A | `ui_tables` | Regression for N23–N25: footing checks and steel from the footing design, status summary from `res.status`, issue order, column / beam / slab rows equal the design results |
| `test_geometry_validation.py` (new 2026-10-21) | 20 | R/A | `grid_manager.check_plan_geometry`, `cad_loader`, `section_design`, `rebar_detailer`, pipeline | N50–N52 regressions: far line rejected before auto-framing (child process capped at 1.5 GiB; fails with MemoryError if the guard is removed), far beam end, survey offsets accepted, 1000 m bound both sides, NaN / inf coordinates, `run_design` rejects before calculating, non-finite column and beam forces, Pu > Puz message; a NaN injected into the seismic result ends in FAIL 'Numerical failure' or a numerical error, never PASS; only the 2 structure-less samples are input errors |
| `test_dxf_corpus.py` + helper `dxf_corpus.py` (new 2026-10-21) | 125 (+ `STRUCTOPTIMA_CORPUS_N`) | E2E/A/metamorphic | `cad_parser`, `cad_loader`, `dxf_layers`, `ui_state.read_dxf`, pipeline, every output | 74 named DXF cases (shapes, units, versions, column / beam / wall styles, layer conventions, rotation, mirroring, offsets, nesting, noise, degenerate structures) + 30 seeded random buildings: input error or a design satisfying the invariants, every drawn column read; 17 equivalent drawings of one building give the same design (W, VB within 1e-6); every output with a column beyond capacity (D-38). 30 tests fail on the code before RM-40 |
| `test_dxf_robustness.py` + helper `dxf_conventions.py` (new 2026-10-21, owner) | 113 | E2E/A | `cad_parser`, `cad_loader`, `ui_state.read_dxf`, pipeline, `bim_loader`, `ifc_exporter` | Every sample drawing through a full design and `tests/invariants.py`; the same plan in 17 drawing conventions gives the same design; 8 damaged-file mutations x 3 sources give input errors, not crashes; IFC round trip |
| `test_invariants.py` + helper `invariants.py` (new 2026-10-21, owner) | 17 | A | `tests/invariants.py` | The invariant checker itself: a clean design passes, each injected fault is caught by its rule |
| `test_metamorphic.py` (new 2026-10-21, owner) | 13 | A | pipeline | Relations between designs (determinism, monotonicity in zone / load, mirror / rotation); 3 strict xfails: plan rotation (N49, owner decision pending) |
| `test_design_matrix.py` + helper `design_matrix.py` (new 2026-10-21, owner) | 60 (+ `STRUCTOPTIMA_FUZZ_N`) | A | pipeline | Pairwise covering array over every Setup option + seeded random buildings, all checked against the invariants |
| `test_grid_manager.py` | 23 | A | `grid_manager` | Detailing tests only assert attributes exist (weak) |
| `test_foundation_eng.py` | 16 | N | `foundation_eng` | Minimum sizes, monotonicity, volumes |
| `test_load_modeling.py` | 22 | N | `wind_load`, `load_combinations` | Spot values (Vz, pz, Cpi), combination arithmetic |
| `test_audit.py` | 13 | A | `audit` | Structure of audit output |
| `test_materials.py` | 12 | N | `materials` | |
| `test_cad_parser.py` | 47 | A/N | `cad_parser` | DXFs to `tmp_path` |
| `test_beam_placer.py` | 13 | N | `beam_placer` | Depth rules updated to L/12, L/10 on 2026-10-15; 1 skip (needs local `complex_villa.dxf` with columns) |
| `test_column_placer.py` | 13 | A | `column_placer`, `structural_checks` | |
| `test_column_editor.py` | 15 | A | `column_editor` | 2 skips (layout-dependent) |
| `test_bbs_module.py` | 35 | N | `bbs_module` | Hook/lap/cutting length arithmetic |
| `test_estimation_refinements.py` | 2 | N | `quantifier` | Legacy slab-deduction path, wastage |
| `test_wall_design.py` | 9 | N | `wall_calculator`, `geometry_exporter` | |
| `test_dxf_exporter.py` | 3 | A | `dxf_exporter` | DXF to `tmp_path` |
| `test_new_modules.py` | 6 | A | `documentation`, `bim_interop`, `site_inspection`, `shm_module` | Calculation summary from results; defect log (2026-10-16 rewrite; `test_viz_integration.py` removed with the simulated modules it tested) |
| `test_risk_management.py`, `test_risk_safeguards.py` | 9 + 6 | A | `risk_management` | |
| `test_member_design.py` | 21 | N | `member_design` (**not production**) | |
| `test_analysis_config.py` | 23 | A/N | `analysis_config` (**not production**) | |
| `test_calculations.py`, `test_sections.py`, `test_quantity_takeoff.py`, `test_slab_generator.py`, `test_layout_scorer.py`, `test_validators.py` | 17+11+17+13+36+32 | A/N | non-production modules | |

Helper: `tests/ifc_fixture.py` (builds a 2-storey IFC frame with `ifcopenshell.api`), `tests/conftest.py` (fixtures).

## Audit 2026-10-21 (gaps found by reading the code and the tests)

Evidence levels: *implemented* / *automatically tested* / *independently verified* (hand, closed form, SP 16, printed
standard) / *professionally reviewed* (none yet).

| # | Finding | Evidence | Next step |
|---|---|---|---|
| A1 | `auto_framer` (production fallback when a drawing has no columns; site of the N50 OOM) has no direct test; `test_beam_placer.py::test_with_auto_framer` is **always skipped** (its DXF yields no columns) | skip reason in every run | Direct tests of node identification and beam generation on a walls-only drawing |
| A11 | DXF reading had no corpus beyond the samples and one generated plan: 8 defects found 2026-10-21 (N53-N60) | `tests/test_dxf_corpus.py` | Closed; nightly CI runs 300 random buildings |
| A2 | `test_dxf_robustness.py::test_every_sample_drawing` passes when loading raises `ValueError`; a regression making valid samples unreadable would pass | 2 of 92 samples raise today, both structure-less | Closed by `test_only_the_structureless_samples_are_input_errors` |
| A3 | The two `test_column_editor.py` removal tests are **always skipped** (no removable column in the layout): column removal is untested | skip reasons | Build a layout with a removable column |
| A4 | `safety_warnings` (production: plan irregularity screen, joint checks) has no direct test; only exercised through the pipeline | no test imports it | Hand-value tests for the screens it reports |
| A5 | `anchorage` was catalogued as production but is not imported anywhere (laps and anchorage are not designed; drawing note says so) | grep 2026-10-21; catalogue corrected | None unless laps are designed |
| A6 | `test_grid_manager.py` detailing tests assert only that attributes exist | file review (2026-10-16 note) | Replace by value checks or remove the duplicate coverage |
| A7 | Non-finite results: column / beam checks raise, W / VB FAIL (N51, N52); an interaction ratio `inf` for Pu > Puz is still stored (KD-29) and `invariants.py` G4 rejects it | `test_geometry_validation.py` | Owner decision on KD-29 |
| A8 | Independent references exist for sections (SP 16), FEA (closed form), one building (complex_house hand check), drift, pseudo-3D; none for wind pressures on a whole building, footing sizes, BBS cutting lengths or quantities | inventory above | Add hand-checked cases; engineer review |
| A9 | No property-based library (none installed; not added); generated cases use seeded random (`design_matrix.py`) | requirements | Keep seeded generation; add DXF geometry generators if needed |
| A10 | Runtime / memory: largest file 284 s (`test_design_matrix.py`), largest peak RSS 308 MB; parallel workers OOM-killed before the N50 fix | runner summary 2026-10-21 | Run through `tests/run_suite.py` |

## Not collected / not maintained

- Former `src/tests/*.py` and root scripts (`stress_test_core.py`, `ui_test_runner.py`, `demo_*.py`, …) were moved out
  of the repository on 2026-10-16 (see repository-inventory.md).

## CI

`.github/workflows/ci.yml` runs `pytest tests/ --cov=src` on Python 3.11, 3.12 and 3.13 (installs `pytest-cov`). CI installs `ifcopenshell` from `requirements.txt` since 2026-10-16, so IFC tests should run there (not yet observed). The CI command does not disable the pytest cache (harmless in CI). CI results are not visible from this workspace — **no CI run has been observed for the 2026-10 changes**.
