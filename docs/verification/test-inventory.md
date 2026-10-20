# Test Inventory

**As of:** 2026-10-16. 523 collected tests in `tests/` (520 passed, 3 skipped on 2026-10-16 — see [verification-results.md](verification-results.md)).

Classification of the strongest assertion type in each file:
**E** executes only · **A** structural/boolean assertions · **N** meaningful numerical assertions · **R** numerical assertions against an independently derived reference (closed form / hand calculation in the test) · **UI** headless UI smoke.

| File | Tests | Type | Production modules covered | Notes / side effects |
|---|---|---|---|---|
| `test_fea_benchmarks.py` (new) | 9 | R | `fea_solver` | Closed-form beam/portal/cantilever, orientation, superposition, mechanism |
| `test_fea_repro.py` (rewritten) | 2 | R | `fea_solver` | Portal statics + slope-deflection (axially rigid) |
| `test_section_design.py` (new) | 10 | R | `section_design` | Annex-G / stress-block equilibrium, doubly reinforced equilibrium, shear rules, interaction end points, independent pure-bending solution |
| `test_audit_findings.py` (new) | 35 | R/N/A | pipeline, analysis, detailing, seismic, wind, footing, audit, optimiser, CAD, IFC, quantities | One or more tests per finding R1–R26 and N-findings; writes DXF/IFC only to `tmp_path` |
| `test_pipeline_e2e.py` (new) | 15 | A/N | `design_pipeline`, reports, exporters, CAD/IFC ingest, CLI | PDFs/Excel to `tmp_path`; CLI with file logging monkeypatched off; reads repository DXFs |
| `test_drift.py` (new 2026-10-16) | 5 | R | `analysis_integration`, `design_pipeline` | Portal drift vs hand value, cracked modifier ratio, limits/status, pipeline drift rows, one-plane column flag |
| `test_site_tools.py` (new 2026-10-16) | 9 | A | `site_calculators`, `site_monitoring` | Hand values for materials, pour, formwork, cubes, cutting plan, FFT, strain, survey, member info / QR |
| `test_drawings.py` (new 2026-10-16) | 13 | A | `src/drawings` | Sheets present and ordered, every member marked, identical marks = identical detailing, schedules carry marks and statuses, void marked, PDF/SVG/DXF consistency, large-plan scaling, CAD and IFC inputs, no files written |
| `test_streamlit_app.py` (rewritten 2026-10-20) | 21 | UI | `app.py`, all pages, `ui_state` | `streamlit.testing.AppTest`: every page after a run and without one, run gating, site confirmation cleared on change, inputs kept across pages, out-of-date results, BBS scope; CWD = `tmp_path` (no page may write to it) |
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

## Not collected / not maintained

- Former `src/tests/*.py` and root scripts (`stress_test_core.py`, `ui_test_runner.py`, `demo_*.py`, …) were moved out
  of the repository on 2026-10-16 (see repository-inventory.md).

## CI

`.github/workflows/ci.yml` runs `pytest tests/ --cov=src` on Python 3.11, 3.12 and 3.13 (installs `pytest-cov`). CI installs `ifcopenshell` from `requirements.txt` since 2026-10-16, so IFC tests should run there (not yet observed). The CI command does not disable the pytest cache (harmless in CI). CI results are not visible from this workspace — **no CI run has been observed for the 2026-10 changes**.
