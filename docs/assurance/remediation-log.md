# Remediation Log

**Date of changes:** 2026-10-15. Base commit `ee7223e`; changes are **uncommitted**
in the working tree at the time of writing. No reviewer has signed off any item.
Test evidence: [../verification/verification-results.md](../verification/verification-results.md).

| Ref | Findings | Change | Files | Tests |
|---|---|---|---|---|
| RM-01 | R1 | Columns designed for every factored combination at both ends with strain-compatibility P-M interaction, biaxial check, e_min about one axis at a time, slenderness moments; failing stacks grow in the pipeline loop | `section_design.py` (new), `rebar_detailer.detail_column`, `grid_manager.detail_columns`, `design_pipeline.py` | `test_R1_*`, `test_section_design.py` |
| RM-02 | R2, R3 | Beam loads from slab panels (equivalent UDLs), walls and webs as DL/LL cases; factored combination envelopes (sagging, hogging, shear) written to beams | `analysis_integration.py` (rewritten), `framing_logic.py` | `test_R2_*`, `test_R3_*` |
| RM-03 | R4 | Separate top/bottom design, compression steel provided, bar fitting, shear from envelope, span/d warning | `rebar_detailer.detail_beam` | `test_R4_*` |
| RM-04 | R5, R6, N3 | Result models carry `status`/`warnings`; pipeline aggregates `failures`; Analysis/Schedules/Reports pages and dashboard read it; audit uses factored loads, user SBC/grade, plinth loads | `rebar_detailer`, `foundation_eng`, `design_pipeline`, `audit.py`, `app.py`, `pages/1,2,4` | `test_R5_*`, `test_R6_*`, UI tests |
| RM-05 | R7, N1, N2 | Real height, soil-specific spectrum, infill period option, importance mapping + override, selectable R (OMRF default), storey weights incl. masonry, vertical distribution, regularity / ESA screen | `seismic.py`, `design_pipeline.py`, `app.py` | `test_R7_*` |
| RM-06 | R8, N6 | Seismic and wind storey forces applied as load cases; combinations from `load_combinations`; overturning moment check; wind storey forces and correct faces | `analysis_integration.py`, `wind_load.py`, `load_combinations.check_overturning`, `pages/1` | `test_R8_*`, `test_NEW_*` |
| RM-07 | R9, R22 | Optimiser uses the production column check, factored forces, fy 415, minimum sizes; indicative only; cache keyed by column fingerprint | `optimizer.py` (rewritten), `pages/1` | `test_R9_*` |
| RM-08 | R10, R11, R12, R23 | FEA rewritten: local stiffness for end forces, gravity in global −Y, correct moment diagram, multi-case solve, nodal loads, pinned/fixed base, mechanism and conditioning checks | `fea_solver.py` | `test_fea_benchmarks.py`, `test_fea_repro.py` |
| RM-09 | R13, N4 | BOM beam lookup by plan id; per-panel slab steel; designed footing steel; column volume by segment height; report spans/areas from results; BBS from designed bars | `quantifier.py`, `report_gen.py`, `bbs_report.py`, `grid_manager.get_beam_result`, pages | `test_R13_*` |
| RM-10 | R14 | IFC loader rewritten (units, placements, extrusions, grid, de-duplication, warnings) | `bim_loader.py` | `test_R14_*`, `test_ifc_through_pipeline` |
| RM-11 | R15 | SCWB, joint shear and ductile spacing computed from designed members; placeholder joint checks removed | `seismic.evaluate_joint_checks`, `safety_warnings.py` | `test_R15_*` |
| RM-12 | R16, N11 | Footing reinforcement, ks punching, soil reaction deduction, one-way shear with τc(pt), real flags, eccentricity warning, overlap check, spacing guard | `foundation_eng.py` | `test_R16_*`, DXF sweep |
| RM-13 | R17, N8, N12 | `$INSUNITS` with plausibility fallback, warnings; Tier-2 excludes annotation layers; layers from entities; explicit column outlines converted by unit | `cad_parser.py`, `cad_loader.py` | `test_R17_*` |
| RM-14 | R18 | Missing beams generated with a message | `design_pipeline.py` | `test_R18_*` |
| RM-15 | R19, R26 | DL/LL takedown, beam webs, roof loads, plinth loads, recomputed each iteration; DXF wall height from storey height; upward-only grouping | `grid_manager.py`, `cad_loader.py` | `test_R19_*`, `test_R26_*` |
| RM-16 | R20, R23 | Slab Table 26 by edge case and ratio, actual factored load, consistent one-way limit, spacing guards | `rebar_detailer.detail_slab`, `grid_manager.detail_slabs` | `test_R20_*` |
| RM-17 | R21 | fck/fy propagated (FEA, beams, slabs, stairs, audit, seismic, optimiser); steel grade selectable; `assume_fixed` wired to pinned/fixed bases | multiple | `test_R21_*`, `test_pinned_base_*` |
| RM-18 | R24 | Fire check uses design covers; invalid dimensions raise `ValueError` | `stability.py` | `test_R24_*` |
| RM-19 | R25 | Compliance claims removed from PDFs; PRELIMINARY banner; legacy docs bannered | `report_gen.py`, `app.py`, docs | review |
| RM-20 | N5, N9 | Console-only logging by default; CLI logger in `src` tree | `logging_config.py`, `main.py` | test runs leave no log file |
| RM-21 | N7 | Slab panels: all four corners or enclosed by walls/beams; footprint for regularity includes voids | `grid_manager.slab_panels`, `footprint_area_m2`, `design_pipeline` | `test_panels_*` |
| RM-22 | N10 | Drawings page writes exports to a private temp directory | `pages/3_📐_Drawings.py` | UI test asserts empty CWD |
| RM-23 | — | New single orchestration `run_design` used by app and CLI; CLI arguments for occupancy, zone, soil, system, wind, SBC, grade, fy | `design_pipeline.py` (new), `app.py`, `main.py` | `test_pipeline_e2e.py` |
| RM-24 | — | Stale beam-depth tests aligned with the documented L/12 / L/10 rule | `tests/test_beam_placer.py` | — |
| RM-25 | — | Performance: vectorised, memoised interaction curves | `section_design.py` | timing in verification results |

## Behaviour changes users will notice

- Designs generally require more steel/larger sections than before (factored loads, lateral loads, P-M interaction).
- Many previously "PASS" designs now report WARN or FAIL with specific items.
- Default R = 3 increases seismic base shear relative to the previous R = 5.
- CLI writes the same report but logs status and returns exit code 1 on FAIL.
