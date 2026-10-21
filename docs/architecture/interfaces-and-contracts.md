# Interfaces and Contracts

**As of:** 2026-10-15.

## Load semantics (decision D-01, proposed)

| Quantity | Contract |
|---|---|
| `Column.load_kn`, `load_dl_kn`, `load_ll_kn`, `plinth_load_kn` | **Service** (unfactored) |
| `Column.design_forces`, `StructuralMember.mu_*`, `vu_kn`, `design_moment_knm`, `design_shear_kn` | **Factored** combination results |
| `RebarDetailer.detail_*` inputs (`pu_kn`, `mux_knm`, `mu_sagging_knm`, …, `factored_load_kn_m2`) | **Factored** |
| `RebarDetailer.detail_slab(load_kn_m2=…)` (legacy argument) | Service, multiplied by 1.5 internally |
| `design_footing(axial_load_kn)` | Service; `factored_load_kn` optional (else 1.5 × service) |
| `StructuralAuditor` | Reads service loads and factors them itself |

## `run_design(gm, beams, inputs) -> DesignResults`

Preconditions: `gm` has grid lines and columns stacked for `inputs.num_stories`
(manual: `generate_grid`; DXF: `CADLoader` + `stack_columns`; IFC: as loaded).
`beams` are plan beams (one per bay side); may be empty (generated).
Side effects: mutates `gm` (loads, sizes, schedules) and `beams` (sizes,
envelopes). No files are written.
Raises `ValueError` before any calculation when `grid_manager.check_plan_geometry(gm, beams)` fails
(non-finite coordinate, or columns / beams / walls spanning more than `MAX_PLAN_EXTENT_M` = 1000 m; D-32).

`DesignInputs` (defaults): `num_stories=2`, `story_height_m=3.5`,
`building_type_name="Residential"`, `wall_load_kn_m=12` (only without walls),
`sbc_kn_m2=200` (library default only — the Setup page requires the user to enter it), `conc_grade="M25"`, `fy=415`, `seismic_zone="III"`,
`soil_type="II"`, `structural_system="OMRF"`, `importance_factor=None` (occupancy
default), `wind_zone=None` (no wind), `terrain_category=None` (category 2),
`wind_opening_percentage=10`, `use_cracked_sections=True`, `fixed_base=True`,
`add_staircase=False`, masonry settings, `align_to_wall=None`, `exposure="Moderate"` (IS 456 Table 3; sets covers
and minimum grade), `nbc_construction_type=2` (NBC Part 4 Table 1; sets fire ratings), `max_iterations=6`,
`le_factor=1.0`. The design writes the covers to `gm.beam_cover_mm / slab_cover_mm / column_cover_mm /
footing_cover_mm`, which detailing, joint checks, BBS and drawings use.

`DesignResults.status`: worst of the `failures` statuses; at least `WARN` if not converged.

Added 2026-10-16:
- `DesignResults.status_label` — display text; PASS is shown as "PASS (implemented checks only) - NOT VERIFIED".
- `DesignResults.verification` = `"NOT_VERIFIED"`; `DesignResults.checks_not_performed` = list of checks the tool
  does not do (`design_pipeline.CHECKS_NOT_PERFORMED`). Every screen / report showing the status must show both.
- `DesignResults.drift_results` — list of dicts `Check, Case, Direction, Storey, Column, Drift (mm), Height (mm),
  Ratio, Limit, Status` (`PASS` / `FAIL` / `WARN` / `INFO`). Built by `design_pipeline.drift_checks(storey_drift,
  top_displacement, total_height_m)`; limits `EQ_DRIFT_LIMIT = 0.004`, `WIND_TOP_SWAY_LIMIT = 1/500` (UNVERIFIED).

## Analysis

`CADParser(path, layer_map=None, layer_roles=None)`, `CADLoader(path, layer_roles=None)` (2026-10-20): `layer_roles` maps
layer name -> "column" / "beam" / "wall" / "mixed" / "ignore" as confirmed by the engineer (layers not listed are
ignored; no wall guessing); None uses `dxf_layers.analyse_layers`. The loader fills `GridManager.drawn_column_sizes_mm`
("x,y" -> drawn mm) for explicit columns; `run_design` adds a "Drawing vs design" WARN where the design differs.

`update_structural_analysis(gm, beams, fck, use_cracked_sections, fixed_base, lateral, seismic=None) -> AnalysisSummary`
- Reads `gm` service intensities (falls back to residential defaults with a message).
- `lateral`: `LateralLoads(eq_x, eq_y, wl_x, wl_y)` whole-building storey forces at levels 1..N (kN).
- Writes beam envelopes and column `design_forces`; resets previous values first.
- `AnalysisSummary` additions (2026-10-16): `storey_drift[case][level] = (drift m, storey height m, column id)` for
  EQX/EQY/WLX/WLY (largest ratio over all columns and frames), `top_displacement[case] = (m, column id)`,
  `columns_one_plane[column id] = missing plane ("XZ"/"YZ")`.
- `seismic`: `SeismicSpec(method, floors, static_forces, vb_static, ah_of_t, extent_x, extent_y)` (2026-10-20). When given
  and the floors are restrained in rotation, the EQX / EQY forces on every frame (both planes) come from
  `pseudo3d.design_direction` (response spectrum, scaling, design eccentricity) and the wind forces are applied at
  the plan centre of the 3D model; otherwise translation-only sharing of `lateral`.
- `AnalysisSummary.lateral_shares[case][frame key]` (forces per level on each frame) and
  `AnalysisSummary.seismic_design` (`"X"` / `"Y"`: `pseudo3d.DirectionResult`; `"modes"`; `"regularity"`;
  `"model"`).
- `SeismicAnalysisResult.method_used` and `.dynamic` (periods, modal mass, VB static / dynamic / design, scale
  factor, torsion ratio, storey forces per direction) are filled by `run_design`.

`FrameSolver2D` contract: gravity UDL positive = global −Y; `solve_cases` returns
`{}` and sets `status` to `UNSTABLE` / `SINGULAR` / `EMPTY` when the model cannot
be solved; `moment_at` sign = sagging positive for horizontal members.

## Detailing results

Every `RebarResult`, `BeamRebarResult`, `SlabRebarResult`, `StaircaseResult`
and `Footing` carries `status` ∈ {PASS, WARN, FAIL} and `warnings`. Consumers must
use these fields (the Overview, Checks page, schedules, header and PDF do); they must not
re-derive pass/fail from other quantities.

## Ingest contracts

- `CADLoader.load_grid_manager(...) -> (GridManager, beams)`; geometry in metres, column sizes in mm; warnings in `load_warnings`; raises `ValueError` when no geometry, when the raw drawing spans more than 10^6 drawing units or has a non-finite coordinate (checked before the auto-framer), or when `check_plan_geometry` fails (D-32).
- `BIMLoader.load_grid_manager() -> (GridManager, beams)`; warnings in `warnings`; raises `ValueError` when no columns.

## Logging, caching, configuration

- `get_logger(name)`: console handler on the `src` logger; file output only if `STRUCTOPTIMA_LOG_FILE` is set or an entry point calls `setup_logging()` (CLI). `LOG_LEVEL` env var sets the level.
- Streamlit caching: Checks page `run_optimization` keyed by an explicit fingerprint of columns and their design forces (R22). `section_design._curve_cached` memoises interaction curves (LRU, 4096 entries, keyed by geometry, bars, fck, fy).
- Environment variables: `SENTRY_DSN` (monitoring), `LOG_LEVEL`, `STRUCTOPTIMA_LOG_FILE`.

## Error behaviour

Library functions raise `ValueError` for invalid geometry/inputs (e.g. stability
checks with zero dimensions — R24, `calculate_loads` without loads, `check_plan_geometry`). The Setup page shows a
`ValueError` from geometry acquisition as an input problem (`ui_state.InputError`). Numerical
non-solvability is reported through statuses, not exceptions, except non-finite design forces:
`section_design.check_column`, `design_flexure` and `design_shear` raise `FloatingPointError` (a broken analysis is
never a pass and never an input error; N51, N52). A non-finite W or VB is a FAIL row "Numerical failure".
