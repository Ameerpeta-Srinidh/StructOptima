# Test Inventory

**As of:** 2026-10-15. 496 collected tests in `tests/` (493 passed, 3 skipped on 2026-10-15 — see [verification-results.md](verification-results.md)).

Classification of the strongest assertion type in each file:
**E** executes only · **A** structural/boolean assertions · **N** meaningful numerical assertions · **R** numerical assertions against an independently derived reference (closed form / hand calculation in the test) · **UI** headless UI smoke.

| File | Tests | Type | Production modules covered | Notes / side effects |
|---|---|---|---|---|
| `test_fea_benchmarks.py` (new) | 9 | R | `fea_solver` | Closed-form beam/portal/cantilever, orientation, superposition, mechanism |
| `test_fea_repro.py` (rewritten) | 2 | R | `fea_solver` | Portal statics + slope-deflection (axially rigid) |
| `test_section_design.py` (new) | 10 | R | `section_design` | Annex-G / stress-block equilibrium, doubly reinforced equilibrium, shear rules, interaction end points, independent pure-bending solution |
| `test_audit_findings.py` (new) | 35 | R/N/A | pipeline, analysis, detailing, seismic, wind, footing, audit, optimiser, CAD, IFC, quantities | One or more tests per finding R1–R26 and N-findings; writes DXF/IFC only to `tmp_path` |
| `test_pipeline_e2e.py` (new) | 15 | A/N | `design_pipeline`, reports, exporters, CAD/IFC ingest, CLI | PDFs/Excel to `tmp_path`; CLI with file logging monkeypatched off; reads repository DXFs |
| `test_streamlit_app.py` (new) | 7 | UI | `app.py`, all pages | `streamlit.testing.AppTest`; CWD = `tmp_path` (the Drawings page writes DXFs to CWD) |
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
| `test_viz_integration.py` | 3 | A | site tools | |
| `test_new_modules.py` | 7 | A | `documentation`, `bim_interop`, `site_inspection`, `shm_module` | |
| `test_risk_management.py`, `test_risk_safeguards.py` | 9 + 6 | A | `risk_management` | |
| `test_member_design.py` | 21 | N | `member_design` (**not production**) | |
| `test_analysis_config.py` | 23 | A/N | `analysis_config` (**not production**) | |
| `test_calculations.py`, `test_sections.py`, `test_quantity_takeoff.py`, `test_slab_generator.py`, `test_layout_scorer.py`, `test_validators.py` | 17+11+17+13+36+32 | A/N | non-production modules | |

Helper: `tests/ifc_fixture.py` (builds a 2-storey IFC frame with `ifcopenshell.api`), `tests/conftest.py` (fixtures).

## Not collected / not maintained

- `src/tests/*.py` — scripts outside `testpaths`; several write PDFs/DXFs.
- Root scripts (`stress_test_core.py`, `ui_test_runner.py`, `demo_*.py`, …) — not tests; written against older APIs.

## CI

`.github/workflows/ci.yml` runs `pytest tests/ --cov=src` on Python 3.11, 3.12 and 3.13 (installs `pytest-cov`). CI does not install `ifcopenshell`, so IFC tests are skipped there (`pytest.importorskip`). The CI command does not disable the pytest cache (harmless in CI). CI results are not visible from this workspace — **no CI run has been observed for the 2026-10 changes**.
