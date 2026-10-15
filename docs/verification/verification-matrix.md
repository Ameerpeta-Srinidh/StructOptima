# Verification Matrix

**As of:** 2026-10-15. Maps every critical production calculation (IDs from the
[calculation catalogue](../engineering/calculation-catalogue.md)) to its tests and
independent evidence.

Evidence levels: **0** none · **1** executes · **2** structural assertions · **3** numerical assertions (self-consistent) · **4** independently derived reference (closed form / hand calculation, written in the test, **not reviewed by a licensed engineer**) · **5** engineer-reviewed benchmark (none yet).

| ID | Calculation | Tests | Evidence level | Status | Missing evidence |
|---|---|---|---|---|---|
| CAL-FEA-01..03 | Frame stiffness, gravity FER, internal moments | `test_fea_benchmarks.py` (all), `test_fea_repro.py` | 4 | VERIFIED_FOR_CASES | Multi-bay, multi-storey comparison with a reference program (B3) |
| CAL-FEA-04 | Frame slicing, lateral sharing | `test_R8_lateral_loads_produce_column_moments` | 2 | UNVERIFIED | Reference-program building model (B8) |
| CAL-FEA-05 | Solvability | `test_mechanism_is_detected_not_solved` | 4 | VERIFIED_FOR_CASES | — |
| CAL-LOD-03 | Column takedown | `test_R19_*`, `test_grid_manager.py` | 3 | UNVERIFIED | Independent hand takedown of one stack (B1) |
| CAL-LOD-04 | Beam loads from slabs | `test_R2_*` (statics), `test_R3_*` | 4 (single bay) | VERIFIED_FOR_CASES | Multi-panel hand check |
| CAL-LOD-05 | Seismic weight | `test_R7_seismic_weight_includes_masonry` | 2 | UNVERIFIED | Hand storey-weight calculation |
| CAL-COMB-01 | Combinations | `test_load_modeling.py`, `test_R8_combinations_*` | 3 | UNVERIFIED | Standard wording check |
| CAL-SEI-01..03 | Spectrum, period, base shear | `test_R7_base_shear_depends_on_height_and_weight` | 3 (formula reproduced) | UNVERIFIED | Spectrum/Z/I/R values vs IS 1893 |
| CAL-SEI-04 | Vertical distribution | `test_R7_storey_forces_follow_wh2_distribution` | 4 | VERIFIED_FOR_CASES | — |
| CAL-SEI-05 | Importance | `test_R7_importance_factor_uses_full_occupancy_name` | 2 | UNVERIFIED | Decision D-03 |
| CAL-SEI-06 | Regularity / method | `test_staircase_void_excluded_from_slabs_but_not_regularity`, `test_R5_failures_reach_the_status_list` | 2 | UNVERIFIED | Engineer review of the screen |
| CAL-SEI-07/08 | SCWB, joint shear | `test_R15_scwb_uses_designed_beams` | 2 | UNVERIFIED | Hand joint calculation; IS 13920 check |
| CAL-SEI-09 | Ductile spacing | `test_R15_*` (status only) | 1 | UNVERIFIED | Ash design not implemented |
| CAL-WND-01..03 | Wind | `test_load_modeling.py`, `test_NEW_live_load_field_and_wind_direction` | 3 | UNVERIFIED (k2/Cpe) | Table-based k2, Cpe per IS 875-3 |
| CAL-WND-04 | Overturning | — | 0 | UNVERIFIED | Unit test with hand values |
| CAL-SEC-01 | τc / τc,max | `test_tau_c_interpolation_and_clamping` | 3 | UNVERIFIED (values) | Line-by-line check vs IS 456 Tables 19/20 |
| CAL-SEC-02 | Mu,lim, singly Ast | `test_mu_lim_fe415_coefficient`, `test_singly_reinforced_ast_satisfies_equilibrium` | 4 | VERIFIED_FOR_CASES | SP-16 table spot checks (B5) |
| CAL-SEC-03 | Doubly reinforced | `test_doubly_reinforced_section_equilibrium`, `test_R4_compression_steel_*` | 4 | VERIFIED_FOR_CASES | SP-16 doubly table spot checks |
| CAL-SEC-04 | Shear | `test_shear_minimum_and_designed_spacing` | 4 (rules) | VERIFIED_FOR_CASES | — |
| CAL-SEC-06 | Stress–strain | `test_fe415_stress_strain_points` | 3 | UNVERIFIED (values) | SP-16 Table A check |
| CAL-SEC-07 | Interaction curve | `test_column_interaction_end_points`, `test_column_bending_capacity_at_zero_axial_matches_hand_value` | 4 | VERIFIED_FOR_CASES | SP-16 interaction chart points (B6) |
| CAL-SEC-08 | Biaxial / e_min / slenderness | `test_min_eccentricity_and_additional_moment`, `test_check_column_includes_minimum_eccentricity_moment`, `test_R1_*` | 3 | UNVERIFIED | Worked biaxial and slender examples (B6) |
| CAL-BEM-01 | Beam detailing | `test_R4_*`, `test_R5_result_models_carry_status` | 3 | UNVERIFIED | Engineer-reviewed beam examples |
| CAL-COL-01 | Column detailing | `test_R1_*` | 3 | UNVERIFIED | Engineer-reviewed column examples |
| CAL-SLB-02 | Slabs | `test_R20_*` | 3 | UNVERIFIED (Table 26 values) | Table 26 check; worked example |
| CAL-STR-01 | Staircase | — (hand check in verification-results) | 3 | UNVERIFIED | Unit test |
| CAL-FND-01 | Footing | `test_foundation_eng.py`, `test_R16_*` | 3 | UNVERIFIED | Worked footing example (B7) |
| CAL-CHK-01 | Audit | `test_audit.py`, `test_R6_*` | 3 | UNVERIFIED | — (consistency screen by design) |
| CAL-CHK-03 | Optimiser | `test_R9_*` | 3 | UNVERIFIED | Re-analysis verification loop |
| CAL-QTY-01/02 | Concrete / steel | `test_R13_*`, `test_estimation_refinements.py` | 4 (beam steel sum) | VERIFIED_FOR_CASES (aggregation) | Manual take-off comparison |
| CAL-BBS-01 | BBS | `test_R13_bbs_contains_beams_with_designed_bars`, `test_bbs_module.py` | 3 | UNVERIFIED | — |
| Ingest | DXF units / walls / IFC | `test_R14_*`, `test_R17_*`, `test_cad_parser.py`, `test_pipeline_e2e.py` | 3 | VERIFIED_FOR_CASES (synthetic DXF/IFC) | Real-world IFC exports |
| UI | Dashboard and pages | `test_streamlit_app.py` | 1 (renders without exception) | UNVERIFIED | Visual / content review |

| CAL-FEA-06 | Storey drift | `tests/test_drift.py` | 4 (closed-form portal) | VERIFIED_FOR_CASES (portal); limits UNVERIFIED | Multi-storey comparison with a reference program; printed IS 1893 limit |
| CAL-SITE-01 | Site arithmetic (materials, pour, formwork, cubes, cutting plan, spectrum, strain, survey) | `tests/test_site_tools.py` | 4 (hand values) | VERIFIED_FOR_CASES | — |
| Viewer | 3D scene geometry and data | `test_viewer_scene_matches_the_design` | 2 | UNVERIFIED | Owner review on a tablet / phone at site |

No calculation is `RESOLVED_WITH_EVIDENCE` or at evidence level 5.
