# Module Catalogue

**As of:** 2026-10-15. Line numbers are indicative (definitions at the time of writing).
Status key: **P** production · **C** CLI only · **T** tests/demos only · **U** unused.

## Orchestration and entry points

| Module | Status | Responsibility | Public interface | Callers |
|---|---|---|---|---|
| `app.py` | P | Streamlit entry point: page registry and top navigation, `ui_state.keep_inputs`, `ui_state.ensure_design` (column-editor re-design), project header | Streamlit script | Streamlit |
| `pages/setup.py` | P | Project inputs in five tabs, plan preview, run panel with missing-input list; calls `ui_state.run_design_from_inputs` | Streamlit page | `app.py` |
| `pages/overview.py` | P | Status banner, checks not performed, issue list, 3D viewer, quantities, column editor | Streamlit page | `app.py` |
| `pages/checks.py`, `members.py`, `drawings.py`, `reports.py`, `site_tools.py` | P | Checks by topic; member schedules; drawing sheets / 3D / plan / CAD / DXF; reports generated on download; site tools | Streamlit pages | `app.py` |
| `main.py` | P | CLI wrapper around `run_design`, logs status / failures / BlackBox risk prompts, writes PDF | `build_parser()`, `main(argv)` → exit code 0/1/2 | user, `tests/test_pipeline_e2e.py` |
| `src/design_pipeline.py` | P | End-to-end design: loads, iteration of analysis+design, slabs, stair, footings, joint checks, BOM, BBS, audit, stability, warnings, status aggregation | `DesignInputs`, `DesignResults`, `run_design(gm, beams, inputs)` (L136), `storey_seismic_weights()` (L99) | `ui_state.py`, `main.py`, tests |

## Model and geometry

| Module | Status | Responsibility | Key interface |
|---|---|---|---|
| `grid_manager.py` | P | Building model: `Column`, `Wall`, `GridManager` (grid generation, column stacking, tributary areas, **service-load takedown** with DL/LL split, initial column sizing, beam/wall generation, slab panels, member detailing wrappers) | `generate_grid`, `stack_columns`, `calculate_trib_areas`, `calculate_loads`, `optimize_column_sizes`, `generate_beams`, `generate_walls`, `slab_panels`, `footprint_area_m2`, `get_beam_result`, `detail_beams/columns/slabs/staircase` |
| `framing_logic.py` | P | `Point`, `MemberProperties`, `StructuralMember` (beam/column plan member with analysis envelope fields); `GridSystem` (legacy, unused by production) | pydantic models |
| `materials.py` | P | `Concrete.from_grade` (Ec = 5000√fck), `Steel.from_grade` | |
| `building_types.py` | P | Occupancy load sets (`LoadParameters`) for 5 occupancies | `get_load_parameters`, `BUILDING_TYPES` |
| `sections.py` | T | Rectangular / circular / I-section properties | |
| `calculations.py`, `schema.py` | T / U | Early prototype beam/column checks and report schema | |

## Ingest

| Module | Status | Responsibility | Key interface |
|---|---|---|---|
| `cad_parser.py` | P | DXF reading (ezdxf): columns from `COL*` layers (LWPOLYLINE outlines), beams from `BEAM*` LINEs, walls by 3-tier strategy, wall centreline merging, `$INSUNITS` reading, user-facing `warnings` | `CADParser.load`, `get_unit_scale`, `extract_columns/beams/walls`, `extract_walls_normalized` |
| `cad_loader.py` | P | DXF → `GridManager` + beams; unit scale (header with plausibility check, else size heuristic); optional auto-framing; walls from DXF; `load_warnings` | `CADLoader.load_grid_manager(auto_frame, seismic_zone, story_height_m, num_stories)` |
| `auto_framer.py` | P | Wall junction nodes and beam generation from architecture | `AutoFramer.identify_structural_nodes`, `generate_beams` |
| `column_placer.py` | P | Rule-based column placement at junctions with warnings | `ColumnPlacer.generate_placement` |
| `beam_placer.py` | P | Beam layout and preliminary depths (L/12 primary, L/10 secondary, L/7 cantilever, min 400 mm) | `BeamPlacer.generate_placement` |
| `column_editor.py` | P | Validate / apply column add / remove in the UI | `ColumnEditor.validate_*`, `add_column`, `remove_column` |
| `bim_loader.py` | P (optional) | IFC → model (rewritten 2026-10, R14): unit scale, placements × extrusion, profiles, de-duplicated plan beams, `warnings` | `BIMLoader.load_grid_manager()` |

## Analysis

| Module | Status | Responsibility | Key interface |
|---|---|---|---|
| `fea_solver.py` | P | 2D direct-stiffness frame solver, multi-case, gravity UDLs in global −Y, nodal loads, fixed/pinned bases, instability detection, internal moment diagrams | `FrameSolver2D.add_node/add_element/add_member_load/add_node_load/solve/solve_cases/moment_at/get_member_forces` |
| `analysis_integration.py` | P | Building → plane frames; beam loads from slab panels / walls / self-weight; lateral storey forces shared by stiffness; combinations; envelopes to beams; per-combination column forces | `LateralLoads`, `AnalysisSummary`, `build_combinations`, `beam_slab_coefficients`, `beam_wall_loads`, `update_structural_analysis` |
| `load_combinations.py` | P | IS 456 Table 18 / IS 1893 combination factors; seismic weight helper; overturning check | `IS_456_COMBINATIONS`, `LoadCombinationManager`, `check_overturning` (new), `check_uplift_stability` (legacy force ratio) |
| `seismic.py` | P | Equivalent static base shear, spectra by soil type, importance/R, vertical distribution, regularity screening, floating columns; SCWB / joint / ductility checks from designed members | `run_seismic_check`, `evaluate_joint_checks`, `importance_for_occupancy` |
| `wind_load.py` | P | IS 875-3 static wind pressures and storey forces in X/Y | `calculate_wind_load`, `WindLoadCalculator` |
| `analysis_config.py` | T | Configuration generator for external analysis programs (not used by production) | |

## Design

| Module | Status | Responsibility | Key interface |
|---|---|---|---|
| `section_design.py` | P (new) | Section-level IS 456 routines: τc / τc,max tables, xu,max, steel and concrete stress–strain, Mu,lim, singly/doubly flexure, shear stirrups, bar fitting, column sections, strain-compatibility interaction curves (memoised), Puz, αn, e_min, slenderness moment, biaxial check | `design_flexure`, `design_shear`, `choose_bars`, `column_section`, `interaction_curve`, `check_column`, … |
| `rebar_detailer.py` | P | Member detailing on top of `section_design`: beams (sagging/hogging/shear), columns (all combinations), slabs (Table 26), staircase flight; result models with `status`/`warnings` | `RebarDetailer.detail_beam/column/slab/staircase`, `table26_coefficients` |
| `foundation_eng.py` | P | Square isolated footing: bearing, punching (ks), one-way shear, flexure, reinforcement, eccentricity warning; overlap check | `design_footing`, `check_footing_overlaps` |
| `member_design.py` | T | Legacy alternative designer (beam/column/slab). **Not used**; its column capacity ignores axial load in Mux1 (see calculation catalogue CAL-LEG-01) | `MemberDesigner` |
| `slab_generator.py` | T | Slab panel/wall-load generator used only by tests | |
| `anchorage.py` | P | Development length tables shown in the UI | |

## Checks

| Module | Status | Responsibility |
|---|---|---|
| `audit.py` | P | Post-design consistency re-check: factored axial vs Cl 39.3-form capacity, bearing with user SBC, punching, short-term beam deflection |
| `stability.py` | P | Column / beam slenderness limits; fire check per member (rating from `durability`, IS 456 Fig. 1 / Table 16A) |
| `durability.py` | P | IS 456 Tables 3, 5, 16, 16A, Fig. 1 and NBC Part 4 Table 1: covers, minimum grade and fire ratings for an exposure and type of construction |
| `safety_warnings.py` | P | Plan irregularity screen; joint checks only from design data; cracked-section note |
| `optimizer.py` | P (Checks page) | Indicative column optimisation using the production column check |
| `risk_management.py` | C | "Black Box" engineering-judgement prompts (CLI) |
| `structural_checks.py`, `validators.py`, `layout_optimizer.py`, `layout_scorer.py` | T | Not used by production |

## Quantities and outputs

| Module | Status | Responsibility |
|---|---|---|
| `quantifier.py` | P | Concrete, steel (from schedules), masonry, excavation, finishes, cost, carbon |
| `wall_calculator.py` | P | Brick / mortar / plaster / paint quantities (not assessed in detail) |
| `bbs_module.py`, `bbs_report.py`, `bbs_utils.py` | P | Bar bending schedule (one typical floor) and PDF |
| `report_gen.py` | P | PDF reports (full, summary, schedule, audit, floor, masonry) |
| `exporters.py` | P | Excel export |
| `ifc_exporter.py` (2026-10-16) | P | IFC4 export: storeys, IfcColumn/IfcBeam/IfcSlab/IfcWall/IfcFooting extrusions in metres with `Pset_StructOptima` (mark, size, bars, status, governing combination); footings shown directly below the column base (founding level not designed). API: `export_ifc(gm, beams, footings, project_name) -> bytes` |
| `drawings/` (package, 2026-10-16) | P | Site drawing set on A3 sheets: `primitives.py` (paper-mm primitives rendered to SVG, DXF via ezdxf, PDF via ReportLab), `sheet.py` (border, title block, grid bubbles, dimensions, tables, notes, auto plan scale), `marks.py` (C/B/F/S marks for identical members), `sheets.py` (S-01 columns, S-02 footings, S-03 beams & slabs, S-04 sections, S-05 slab reinforcement, S-06 footing sections, continuation sheets). API: `build_drawing_set`, `sheets_to_pdf`, `sheets_to_zip`, `compute_marks` |
| `dxf_exporter.py`, `geometry_exporter.py`, `visualizer.py`, `svg_viewer.py` | P | Older DXF exports and 3D/2D views (not assessed) |
| `quantity_takeoff.py` | T | Alternative BOQ module used only by tests/demos |

## UI / infrastructure / site tools

| Module | Status | Notes |
|---|---|---|
| `ui_components.py` | P | Project header (status from `ui_tables.design_status_summary`), status badges and table colouring, `require_results` / `stale_notice`, member search (uses `get_beam_result`), IS 456 quick reference (UNVERIFIED) |
| `ui_state.py` | P | `in_*` input defaults and persistence across pages, `input_fingerprint` / `results_state`, `missing_inputs`, geometry acquisition, `run_design_from_inputs`, `ensure_design` |
| `ui_tables.py` | P | Pure row builders for the issue list and the column, beam, slab and footing schedules; `BBS_SCOPE` text (tests: `test_ui_tables.py`) |
| `logging_config.py` | P | `get_logger` is console-only unless `STRUCTOPTIMA_LOG_FILE` is set; `setup_logging()` adds a rotating file handler (CLI) |
| `monitoring.py` | P | Sentry wrappers, active only with `SENTRY_DSN` |
| `auth.py` | U | Password helpers, not imported |
| `site_calculators.py` | P | Rebar weights, approved-mix materials (`materials_for_mix`), pour logistics, formwork contact area, cube-test summary, BBS cutting plan (`optimise_cutting`) — nothing assumed (2026-10-16) |
| `site_monitoring.py` (new 2026-10-16) | P | User-supplied measurements vs design: accelerometer spectrum, frequency change, strain vs yield strain, as-built survey deviation, member info and QR tags (segno) |
| `documentation.py` (rewritten 2026-10-16) | P | `calculation_summary(res, project, engineer)` — plain-text record built only from `DesignResults` |
| `site_inspection.py` (rewritten 2026-10-16) | P | Inspection prompts (standards named, clauses not cited), `DefectRecord` log with CSV export; no diagnosis |
| `site_guide.py`, `bim_interop.py` | P | Static checklists (values as cited, UNVERIFIED); COBie JSON writer (fed from the design on the Site Tools page) |
| `shm_module.py` | T | Sensor-planning helper used only by tests |
| `viewer_model.py` (new 2026-10-16) | P | `build_scene(gm, beams, footings)` JSON scene (metres, Z up) and `viewer_html(scene)` with the committed bundle `components/viewer3d/dist/viewer.js` (three.js; source `components/viewer3d/src/main.js`, build `npm run build`) |
