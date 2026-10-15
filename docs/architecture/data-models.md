# Data Models

**As of:** 2026-10-15. All models are pydantic `BaseModel`s unless stated as dataclass.

## Building model (`src/grid_manager.py`, `src/framing_logic.py`)

### `Column`
| Field | Unit | Meaning |
|---|---|---|
| `id` | — | `C<n>_L<level>` (manual/CAD), `C_IFC_<guid>_L<level>` (IFC) |
| `x`, `y` | m | Plan position |
| `level` | — | Storey index (0 = ground storey) |
| `z_bottom`, `z_top` | m | Segment elevations |
| `width_nb`, `depth_nb` | mm | Section dimension along global X / along global Y (swapped when `orientation_deg` ≈ 90) |
| `trib_area_m2` | m² | Half-span tributary area |
| `load_dl_kn`, `load_ll_kn`, `load_kn` | kN | **Service** cumulative loads at the bottom of the segment; `load_kn = load_dl_kn + load_ll_kn` |
| `plinth_load_kn` | kN | Ground-storey wall load carried by plinth beams to the footing (level 0 only) |
| `design_forces` | kN, kNm | `[(combo@end, Pu, Mx, My)]` **factored**; Mx lever along X, My lever along Y |
| `type`, `junction_type`, `is_floating`, `orientation_deg`, `staircase_add_load` | | Classification / placement metadata |

### `Wall`
Geometry (m), `thickness_mm`, `height_m`, `material` (density 19.2 / 7.5 / 25 kN/m³), `opening_fraction`; `line_load_kn_m = t·h·(1 − opening)·γ`.

### `GridManager`
Grid (`x_grid_lines`, `y_grid_lines`), `columns`, `walls`, `footings`, schedules
(`rebar_schedule`, `beam_schedule`, `slab_schedule`, `staircase_schedule`),
context (`fck`, `fy`, `slab_thickness_mm`, service intensities `dead_load_kn_m2`,
`live_load_kn_m2`, `roof_*`, `superimposed_dead_kn_m2`), `void_bays`,
`boundary_segments`. **Schedules are keyed by plan member id**; use
`get_beam_result(id)` for per-level ids.

### `StructuralMember` (beam)
`id`, `start_point`, `end_point` (m), `properties` (`width_mm`, `depth_mm`),
analysis envelope (factored): `mu_sagging_knm`, `mu_hogging_knm`, `vu_kn`,
`design_moment_knm` (= max), `design_shear_kn`, `governing_combo`,
`service_udl_kn_m`, `analysis_status` (`PENDING`, `FEA_SOLVED`, `FALLBACK_*`), `level`.

## Results

| Model | File | Key fields |
|---|---|---|
| `RebarResult` (column) | `rebar_detailer.py` | `main_bars_desc`, `links_desc`, `main_steel_area_mm2`, `status`, `warnings`, `interaction_ratio`, `governing_combo`, `pu/mux/muy_design`, `steel_percent`, `hinge_zone_mm`, `hinge_spacing_mm`, `link_spacing_mm`, `math_log` |
| `BeamRebarResult` | `rebar_detailer.py` | bar descriptions, `status`, `warnings`, `span_m`, `width_mm`, `depth_mm`, `mu_sagging/hogging_knm`, `vu_kn`, required/provided top & bottom steel, `tau_v/tau_c/tau_c_max`, `span_depth_ratio`, `weight_kg_per_m` |
| `SlabRebarResult` | `rebar_detailer.py` | descriptions, `status`, `warnings`, `area_m2`, `lx_m`, `ly_m`, `table26_case`, moments, `factored_load_kn_m2`, `weight_kg_per_m2` |
| `StaircaseResult` | `rebar_detailer.py` | waist, steel, volumes, `status`, `mu_knm_per_m`, `effective_span_m` |
| `Footing` | `foundation_eng.py` | size, thickness, `status`, flags (`punching_ok`, `bending_ok`, `one_way_shear_ok`, `bearing_ok`), loads, pressure, `ast_per_m_mm2`, `rebar_desc`, `steel_weight_kg`, `warnings` |
| `SeismicAnalysisResult` (dataclass) | `seismic.py` | parameters (Z, I, R, Ta, Ah), `base_shear_kn`, storey weights/heights/forces, regularity checks, `analysis_method_check`, `scwb_details`, `joint_details`, `ductile_checks`, `ductile_verification` |
| `WindLoadResult` (dataclass) | `wind_load.py` | pressures per level, `storey_forces_x/y_kn`, base shears, overturning moments, warnings |
| `AnalysisSummary` (dataclass) | `analysis_integration.py` | frames solved / total, failed frames, combinations, messages, members outside frames |
| `DesignInputs` / `DesignResults` (dataclasses) | `design_pipeline.py` | See [interfaces-and-contracts.md](interfaces-and-contracts.md) |
| `MaterialCost` | `quantifier.py` | Volumes, steel by diameter (incl. 4 % wastage), costs, carbon, masonry quantities |
| `AuditResult` | `audit.py` | `member_id`, `check_name`, `design_value`, `limit_value`, `status`, `notes` |

## Session state (Streamlit)

`app.py` writes the legacy keys used by the pages (`gm`, `beams`, `all_beams`,
`footings`, `bom`, `audit_results`, `seismic_result`, `wind_result`,
`stab_checks`, `stab_summary`, `safety_summary`, `conc_grade`, `fck`,
`num_stories`, `story_height`, …) plus `design_results`, `design_status`,
`design_failures`, `design_messages`, `analysis_summary`, `fy`, `soil_type`,
`structural_system`, `cad_warnings`, `needs_redesign`, `geometry_beams`.
Note: `live_load` now holds the **floor live load** (kN/m²); before 2026-10 it
held total floor load including slab self-weight.
