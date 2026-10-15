# Repository Inventory

**As of:** 2026-10-15. "Tracked" = in git; "Ignored" = present locally but matched by `.gitignore`.
Production = reachable from `app.py`/`pages/` or `main.py` through imports **and** calls.

## Entry points

| File | Tracked | Kind | Notes |
|---|---|---|---|
| `app.py` | Yes | Streamlit main page | Rewritten 2026-10 to call `run_design` |
| `pages/1_📊_Analysis.py` | Yes | Streamlit page | Seismic/wind/stability/combinations/optimiser/failure screen |
| `pages/2_📋_Schedules.py` | Yes | Streamlit page | Column / beam / slab schedules, math logs |
| `pages/3_📐_Drawings.py` | Yes | Streamlit page | 3D/2D views, DXF export. **Writes DXF files to the current working directory on every render** (see [../development/troubleshooting.md](../development/troubleshooting.md)) |
| `pages/4_📄_Reports.py` | Yes | Streamlit page | PDF / Excel / BBS / ZIP downloads |
| `pages/5_🔧_Site_Tools.py` | Yes | Streamlit page | BBS utilities, inspection, SHM, COBie |
| `main.py` | Yes | CLI | `python main.py --help` |

## Source package `src/` (all tracked)

Status: **P** production, **T** tests/demos only, **U** unused (no importer), **C** CLI only. Details: [module-catalogue.md](module-catalogue.md).

| Group | Modules |
|---|---|
| Orchestration | `design_pipeline` P |
| Geometry / model | `grid_manager` P, `framing_logic` P, `materials` P, `building_types` P, `sections` T, `schema` U, `calculations` T |
| Ingest | `cad_parser` P, `cad_loader` P, `auto_framer` P, `column_placer` P, `beam_placer` P (via auto_framer), `column_editor` P, `bim_loader` P (needs `ifcopenshell`) |
| Analysis | `fea_solver` P, `analysis_integration` P, `load_combinations` P, `seismic` P, `wind_load` P, `analysis_config` T |
| Design | `section_design` P, `rebar_detailer` P, `foundation_eng` P, `member_design` T (legacy alternative), `slab_generator` T, `anchorage` P (UI tables) |
| Checks | `audit` P, `stability` P, `safety_warnings` P, `optimizer` P (Analysis page), `risk_management` C, `structural_checks` T, `validators` T, `layout_optimizer` T, `layout_scorer` T |
| Quantities / outputs | `quantifier` P, `wall_calculator` P, `bbs_module` P, `bbs_report` P, `bbs_utils` P, `quantity_takeoff` T, `report_gen` P, `exporters` P, `dxf_exporter` P, `geometry_exporter` P, `visualizer` P, `svg_viewer` P |
| UI / infra | `ui_components` P, `logging_config` P, `monitoring` P, `auth` U |
| Site / misc | `site_calculators` P, `site_guide` P, `site_inspection` P, `shm_module` P, `shm_viz` P, `digital_twin` P, `bim_interop` P, `documentation` P |
| `src/tests/` | `comprehensive_validation.py`, `test_column_placement.py`, `test_full_pipeline.py`, `md_to_html.py`, `md_to_pdf.py` — scripts, **not collected by pytest** (`testpaths = tests`); several write files |

## Tests `tests/` (tracked unless noted)

See [../verification/test-inventory.md](../verification/test-inventory.md). New in 2026-10:
`test_fea_benchmarks.py`, `test_section_design.py`, `test_audit_findings.py`,
`test_pipeline_e2e.py`, `test_streamlit_app.py`, `ifc_fixture.py` (helper);
rewritten: `test_fea_repro.py`; updated: `test_beam_placer.py`.

## Configuration and deployment

| File | Purpose |
|---|---|
| `requirements.txt` | Runtime + test dependencies (pinned except `sentry-sdk`, `scipy`). `ifcopenshell` is **not** listed (optional, IFC import only) |
| `pytest.ini` | `testpaths = tests`, `-v --tb=short`, ignores DeprecationWarning |
| `.github/workflows/ci.yml` | CI: Python 3.11/3.12/3.13, `pip install -r requirements.txt pytest-cov`, `pytest tests/ --cov=src` |
| `Dockerfile`, `docker-compose.yml`, `Procfile`, `.dockerignore` | Container / PaaS deployment of the Streamlit app (not assessed) |
| `.streamlit/config.toml`, `.streamlit/secrets.toml.example` | Streamlit configuration |

## Scripts at repository root (excluded from documentation scope beyond this table)

| File(s) | Tracked | Reason for exclusion |
|---|---|---|
| `demo_*.py` (5) | Yes | Demonstrations of individual modules; not part of production; some write files |
| `debug_pipeline.py`, `stress_test_core.py`, `ui_test_runner.py`, `generate_sample_report.py`, `tmp_*.py`, `fix.py`, `fix_deprecation.py` | Yes | Historical developer scripts; written against pre-2026-10 APIs; may write files; not maintained |
| `scratch/` | Yes | Scratch PDFs and one script |
| `_monetization_archive/` | Yes | Archived payment/terms pages, not imported |
| `generate_*.py`, `analyze_*.py`, `run_batch_analysis.py`, `verify_15_cases.py`, `visualize_autoframes.py`, `test_*.py` at root | Ignored | Local developer scripts (not in git) |

## Data and artefacts

| Path | Tracked | Notes |
|---|---|---|
| `samples/*.dxf`, `real_world_dxfs/*.dxf`, `test_dxfs/**` | Yes | Input DXFs used by tests and the 2026-10 sweep. Many declare `$INSUNITS = 6` (metres) while drawn in millimetres — handled by the plausibility fallback (finding N8) |
| `Beam_Schedule.dxf`, `Foundation_Plan_*.dxf`, `*.pdf`, `*.docx`, `*.zip`, `*.jpg` at root | Yes | Generated outputs / reference documents committed historically. `Beam_Schedule.dxf` and `Foundation_Plan_Professional.dxf` are overwritten by the Drawings page when run from the repository root |
| `Extended_Structural_Calculation_Reference*.md/.pdf`, `structural_calculations_manual.md`, `blueprint_text.txt`, `StructOptima_*.pdf/.docx` | Yes | Historical reference write-ups; not reviewed against the current code |
| `structural_design.log.1` | Yes | Rotated log committed by accident (R27) |
| Root `*.pdf`, `Floor_*_Plan.dxf`, `Structural_Plan.dxf`, logs, `*.html` | Ignored | Generated outputs |

## Clutter (R27)

Not removed (deletion requires an owner decision — see [../assurance/decision-log.md](../assurance/decision-log.md), D-07).
