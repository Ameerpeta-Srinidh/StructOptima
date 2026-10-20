# Repository Inventory

**As of:** 2026-10-16 (after the repository clean-up). "Tracked" = in git; "Ignored" = present locally but matched by `.gitignore`.
Production = reachable from `app.py`/`pages/` or `main.py` through imports **and** calls.

## Entry points

| File | Tracked | Kind | Notes |
|---|---|---|---|
| `app.py` | Yes | Streamlit entry point | Navigation, input persistence, project header (restructured 2026-10-20) |
| `pages/setup.py` | Yes | Streamlit page | Inputs and the design run (new 2026-10-20; replaces the sidebar of the old dashboard) |
| `pages/overview.py` | Yes | Streamlit page | Status, issues, 3D viewer, quantities, column editor (new 2026-10-20) |
| `pages/checks.py` | Yes | Streamlit page | Failure screen, seismic/wind/drift/stability/joints/combinations/L/d/optimiser tabs (was `1_📊_Analysis.py`) |
| `pages/members.py` | Yes | Streamlit page | Column / beam / slab / footing schedules, calculation logs, masonry takeoff (was `2_📋_Schedules.py`) |
| `pages/drawings.py` | Yes | Streamlit page | (was `3_📐_Drawings.py`) A3 drawing set (PDF/DXF/SVG/ZIP), IFC4 download, 3D viewer / walk-through, 2D plan, interactive CAD. DXF exports go to a temporary directory (N10, fixed 2026-10-15) |
| `pages/reports.py` | Yes | Streamlit page | PDF / Excel / BBS / ZIP downloads, generated on click (was `4_📄_Reports.py`) |
| `pages/site_tools.py` | Yes | Streamlit page | (was `5_🔧_Site_Tools.py`) BBS + cutting plan, approved-mix calculators, cube register, checklists, calculation summary, COBie, QR tags, inspection / defect log, measured vibration & strain, as-built survey (rewritten 2026-10-16; nothing simulated) |
| `components/viewer3d/` | Yes | JS source + committed bundle | `src/main.js` (three.js viewer), `dist/viewer.js` (built by `npm run build`, committed), `package.json` / `package-lock.json`; `node_modules/` ignored |
| `CHANGELOG.md` | Yes | Docs | Every 2026-10 change, why, tests run, open items |
| `docs/user-guide.md` | Yes | Docs | Current user guide (supersedes `docs/legacy/user_guide.md`) |
| `main.py` | Yes | CLI | `python main.py --help` |

## Source package `src/` (all tracked)

Status: **P** production, **T** tests/demos only, **U** unused (no importer), **C** CLI only. Details: [module-catalogue.md](module-catalogue.md).

| Group | Modules |
|---|---|
| Orchestration | `design_pipeline` P |
| Geometry / model | `grid_manager` P, `framing_logic` P, `materials` P, `building_types` P, `sections` T, `schema` U, `calculations` T |
| Ingest | `cad_parser` P, `cad_loader` P, `auto_framer` P, `column_placer` P, `beam_placer` P (via auto_framer), `column_editor` P, `bim_loader` P (needs `ifcopenshell`) |
| Analysis | `fea_solver` P, `analysis_integration` P, `pseudo3d` P, `load_combinations` P, `seismic` P, `wind_load` P, `durability` P, `analysis_config` T |
| Design | `section_design` P, `rebar_detailer` P, `foundation_eng` P, `member_design` T (legacy alternative), `slab_generator` T, `anchorage` P (UI tables) |
| Checks | `audit` P, `stability` P, `safety_warnings` P, `optimizer` P (Checks page), `risk_management` C, `structural_checks` T, `validators` T, `layout_optimizer` T, `layout_scorer` T |
| Quantities / outputs | `quantifier` P, `wall_calculator` P, `bbs_module` P, `bbs_report` P, `bbs_utils` P, `quantity_takeoff` T, `report_gen` P, `exporters` P, `dxf_exporter` P, `geometry_exporter` P, `visualizer` P, `svg_viewer` P |
| UI / infra | `ui_components` P, `ui_state` P, `ui_tables` P, `logging_config` P, `monitoring` P, `auth` U |
| Site / misc | `site_calculators` P, `site_guide` P, `site_inspection` P, `site_monitoring` P, `shm_module` T, `bim_interop` P, `documentation` P |
| Drawings / BIM / 3D | `drawings/` package P, `ifc_exporter` P, `viewer_model` P |

## Tests `tests/` (tracked unless noted)

See [../verification/test-inventory.md](../verification/test-inventory.md). New in 2026-10:
`test_fea_benchmarks.py`, `test_section_design.py`, `test_audit_findings.py`,
`test_pipeline_e2e.py`, `test_streamlit_app.py`, `test_ui_tables.py`, `ifc_fixture.py` (helper);
rewritten: `test_fea_repro.py`; updated: `test_beam_placer.py`.

## Configuration and deployment

| File | Purpose |
|---|---|
| `requirements.txt` | Runtime + test dependencies (pinned except `sentry-sdk`, `scipy`); `ifcopenshell==0.8.4.post1` added 2026-10-16 (IFC import/export) |
| `pytest.ini` | `testpaths = tests`, `-v --tb=short`, ignores DeprecationWarning |
| `.github/workflows/ci.yml` | CI: Python 3.11/3.12/3.13, `pip install -r requirements.txt pytest-cov`, `pytest tests/ --cov=src` |
| `Dockerfile`, `docker-compose.yml`, `Procfile`, `.dockerignore` | Container / PaaS deployment of the Streamlit app (not assessed) |
| `.streamlit/config.toml`, `.streamlit/secrets.toml.example` | Streamlit configuration |

## Repository layout (after the 2026-10-16 clean-up)

```
app.py, main.py            Streamlit entry point and CLI
pages/                     Streamlit pages
src/                       Engineering, ingest, output and UI modules
components/viewer3d/       3D viewer source + committed bundle
tests/                     pytest suite
samples/                   Input DXFs: sample_design.dxf, sample_arch_only.dxf, plans/, real_world/, test_cases/
docs/                      Documentation; docs/legacy/ = historical write-ups (not current)
CHANGELOG.md, CLAUDE.md, README.md, CONTRIBUTING.md, CODE_OF_CONDUCT.md, LICENSE
requirements.txt, pytest.ini, Dockerfile, docker-compose.yml, Procfile, .streamlit/, .github/
_local/                    (git-ignored) personal scripts and old outputs moved out of the root
```

## Data

| Path | Tracked | Notes |
|---|---|---|
| `samples/` | Yes | Input DXFs used by tests and manual trials; see `samples/README.md`. Many declare `$INSUNITS = 6` (metres) while drawn in millimetres — handled by the plausibility fallback (finding N8). `samples/plans/` added 2026-10-16 (the tests already used these files but they were git-ignored, so CI skipped those tests) |
| `docs/legacy/` | Yes | Historical write-ups and pre-2026-10 guides (`Extended_Structural_Calculation_Reference*`, `structural_calculations_manual.md`, `StructOptima_*.pdf/.docx`, `Structural_DXF_Translation.pdf`, `blueprint_text.txt`, `api_reference.md`, `engineering_basis.md`, `installation.md`, `risk_management.md`, `user_guide.md`). Not reviewed against the current code |

## Clean-up of 2026-10-16 (R27, D-07 — approved by the owner)

Removed from the repository (still in git history; copies kept locally under the git-ignored `_local/`):
- generated outputs at the root: `Beam_Schedule.dxf`, `Foundation_Plan_*.dxf/.jpg`, `Structural_Design_Report (1)/(2).pdf`,
  `Untitled_Project_Export_Package.zip`, `test_report_inspect.pdf`, `complex_villa.jpg`, `structural_design.log.1`,
  `sample_report.pdf` (a report from an earlier version; its download button was removed from `app.py`);
- legacy scripts: `debug_pipeline.py`, `demo_*.py`, `fix.py`, `fix_deprecation.py`, `generate_sample_report.py`,
  `stress_test_core.py`, `tmp_*.py`, `ui_test_runner.py`;
- folders: `scratch/`, `_monetization_archive/`, `src/tests/`.

Moved: `test_dxfs/` → `samples/test_cases/`, `real_world_dxfs/` → `samples/real_world/`, reference documents →
`docs/legacy/`. Untracked personal scripts, outputs and logs at the root → `_local/` (nothing deleted except
Python caches).
