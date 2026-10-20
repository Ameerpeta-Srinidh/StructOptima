# Standards Register

**As of:** 2026-10-20. On 2026-10-20 the cited values were compared with the printed standards supplied by the owner
(evidence, editions and amendments: [../verification/standards-check-2026-10-20.md](../verification/standards-check-2026-10-20.md)).

Status values:
- **VERIFIED**: the code value or rule matches the printed clause.
- **FIXED**: the code was corrected to the printed clause on 2026-10-20, with a regression test.
- **CONSERVATIVE**: the code differs on the safe side.
- **GAP**: the clause is not implemented.
- **UNVERIFIED**: not checked, because the standard was not available or the print is illegible.

None of these is an engineer's sign-off. Items become RESOLVED_WITH_EVIDENCE only after review by a qualified
engineer.

| Standard (edition) | Used for | Clause / table | Code location | Status |
|---|---|---|---|---|
| IS 456:2000 (all amendments) | Load factors | Table 18 | `load_combinations`, `analysis_integration` | VERIFIED |
| IS 456:2000 | Design shear strength τc, M15–M40 | Table 19 | `section_design.TAU_C_TABLES` | VERIFIED (M15 row added, T2) |
| IS 456:2000 | Maximum shear stress | Table 20 | `section_design.TAU_C_MAX` | VERIFIED (M15 added) |
| IS 456:2000 | Stress block, xu,max/d 0.53 / 0.48 / 0.46 | 38.1, Annex G | `section_design` | VERIFIED; SP 16 Tables C/D reproduced within 0.8 % |
| IS 456:2000 / SP:16 | Cold-worked steel design curve | Fig. 23A / SP:16 1.4 | `section_design._CW_POINTS` | VERIFIED (SP 16 Table A reproduced) |
| IS 456:2000 | Minimum eccentricity, Puz, αn, slender additional moments | 25.4, 39.3, 39.6, 39.7.1 | `section_design` | VERIFIED (SP 16 Example 9 reproduced) |
| IS 456:2000 | Effective length | Annex E | `detail_columns` (le = 1.0 L) | GAP (D-04) |
| IS 456:2000 | Minimum / maximum beam steel | 26.5.1.1 | `section_design`, `detail_beam` | VERIFIED |
| IS 456:2000 | Shear reinforcement, minimum stirrups, max spacing | 40.4, 26.5.1.5, 26.5.1.6 | `section_design.design_shear` | VERIFIED (SP 16 Example 10 reproduced) |
| IS 456:2000 | Column steel 0.8–6 %; ties | 26.5.3.1, 26.5.3.2 | `detail_column` | VERIFIED / CONSERVATIVE (4 % maximum) |
| IS 456:2000 | Two-way slab coefficients | Table 26 | `rebar_detailer.TABLE26` | VERIFIED; case 4 long-span negative FIXED 0.045 → 0.047 (T1) |
| IS 456:2000 | Span/depth basic values 7 / 20 / 26 | 23.2.1 | `detail_beam`, `detail_slab` | VERIFIED (modification factors not applied — GAP) |
| IS 456:2000 | Footings, punching | 34, 31.6.3.1 | `foundation_eng` | VERIFIED |
| IS 456:2000 | Exposure, minimum grade, nominal cover | Tables 3, 5, 16; 26.4.2.1, 26.4.2.2 | `durability` | FIXED (D1: exposure input; covers used throughout) |
| IS 456:2000 | Fire covers and minimum dimensions | Table 16A, Fig. 1 | `durability`, `stability` | FIXED (F1) |
| IS 456:2000 | Lateral stability of beams, column slenderness | 23.3, 25.3.1 | `stability` | VERIFIED (cantilever limits — GAP) |
| IS 456:2000 | Lateral sway under wind H/500 | 20.5 | `design_pipeline.WIND_TOP_SWAY_LIMIT` | VERIFIED |
| IS 456:2000 | Es = 200 kN/mm² | 5.6.3 | `site_monitoring.ES_MPA` | VERIFIED |
| IS 456:2000 | Bond stress, development length | 26.2.1, 26.2.1.1 | quick reference only | VERIFIED (not used in design — GAP) |
| IS 1893 (Part 1):2016 (Amd 1, 2) | Zone factors | Table 3 | `seismic.ZONE_FACTORS` | VERIFIED |
| IS 1893 (Part 1):2016 | Importance factor | Table 8 | `seismic.OCCUPANCY_IMPORTANCE` | VERIFIED as defaults (I = 1.2 for > 200 occupants is the engineer's input) |
| IS 1893 (Part 1):2016 | Response reduction factor | Table 9 | `seismic.RESPONSE_REDUCTION` | VERIFIED; Note 1 (no OMRF in Zones III–V) FIXED (S2) |
| IS 1893 (Part 1):2016 | Design spectrum, equivalent static | 6.4.2(a) | `SeismicDesignChecker.get_spectral_acceleration` | FIXED (S1) |
| IS 1893 (Part 1):2016 | Approximate period | 7.6.2, 7.6.2.1 (Amd 2) | `calculate_base_shear` | VERIFIED |
| IS 1893 (Part 1):2016 | Minimum design lateral force | 7.2.2, Table 7 | `seismic.MIN_BASE_SHEAR_FRACTION` | FIXED (S3) |
| IS 1893 (Part 1):2016 | Seismic weight live-load fraction, no roof live load | Table 10, 7.3.2 | `design_pipeline._ll_factor` | VERIFIED |
| IS 1893 (Part 1):2016 | Vertical distribution | 7.6.3 | `run_full_analysis` | VERIFIED |
| IS 1893 (Part 1):2016 | Analysis method | 7.6, 7.7.1 | `check_analysis_method` | FIXED (S4: 2002 limits replaced) |
| IS 1893 (Part 1):2016 | Irregularities: re-entrant, openings, soft storey, mass, floating columns | Tables 5, 6 (Amd 2) | `seismic`, `design_pipeline` | VERIFIED / FIXED (S5–S7) |
| IS 1893 (Part 1):2016 | Cracked section stiffness | 6.4.3.1 | `analysis_integration` | VERIFIED |
| IS 1893 (Part 1):2016 | Load combinations | 6.3.2.1 | `analysis_integration` | VERIFIED (6.3.2.2, 6.3.3 — GAP) |
| IS 1893 (Part 1):2016 | Storey drift 0.004 h | 7.11.1.1 | `design_pipeline.EQ_DRIFT_LIMIT` | VERIFIED |
| IS 13920:2016 (Amd 1, 2) | SCWB 1.4, roof waiver above 4 storeys | 7.2.1, 7.2.1.3 | `evaluate_joint_checks` | VERIFIED / FIXED (J3) |
| IS 13920:2016 | Joint shear strength and effective area | 9.1.1, 9.1.2 (Amd 2) | `joint_confinement_factor`, `joint_effective_breadth` | FIXED (J1, J2); bj for bc ≥ bb UNVERIFIED (not printed in full) |
| IS 13920:2016 | End-zone spacing beams / columns | 6.3.5 (Amd 1), 7.6.1 | `detail_beam`, `detail_column`, `bbs_module` | FIXED (J9) / CONSERVATIVE |
| IS 13920:2016 | Hook extension 8 d ≥ 75 mm | 3.5, 6.3.1, 7.4.1 (Amd 1, 2) | `bbs_module.seismic_hook_extension` | FIXED (J8) |
| IS 13920:2016 | Minimum grade, steel properties | 5.2, 5.3.1 (Amd 2) | `design_pipeline` | FIXED (J4, J5) |
| IS 13920:2016 | Column geometry, axial stress ≤ 0.40 fck | 7.1, 7.1.1, 7.1.2 (Amd 1, 2) | `design_pipeline` | FIXED (J6, J7) |
| IS 13920:2016 | Confining steel Ash, capacity-design shear | 7.6.1(c), 6.3.3, 7.5 | — | GAP |
| IS 875 (Part 1):1987 | Unit weights (RCC, brick masonry) | Table 1 | `Wall.density_kn_m3`, 25 kN/m³ | VERIFIED / CONSERVATIVE |
| IS 875 (Part 2):1987 | Imposed loads, roof | Tables 1, 2; 3.1.2 | `building_types.py` | VERIFIED; office FIXED 3.0 → 4.0 (L1); corridors / balconies — GAP |
| IS 875 (Part 3):2015 | Vb, k2, Cpe, Cpi | 6.2, Table 2, Table 5 | `wind_load.py` | VERIFIED / FIXED (W1 k2 table; W2 h/w ≥ 6); k3, k4 — GAP |
| IS 1786:2008 (Amd 1) | Bar properties | Table 3 | IS 13920 5.3.1 note | VERIFIED |
| NBC 2016 Part 4 | Fire rating by type of construction | Table 1 | `durability.NBC_TABLE1` | FIXED (F2) |
| SP 16:1980 | Design aids (benchmarks) | Tables A, C, D, F; Examples 1, 2, 3, 6, 9, 10 | `tests/test_sp16_benchmarks.py` | Reproduced |
| IS 1200, IS 1077, IS 2250, IS 1661, IS 1905 | Quantity measurement, bricks, mortar, plaster | as cited in report text | `quantifier`, `wall_calculator`, `report_gen` | UNVERIFIED (standards not obtained) |
| IS 516, IS 10262, IS 2502, SP 34, IS 1904, IS 6403 | Site tools, detailing, foundations | — | `site_*`, `bbs_*` | Available; not yet compared item by item |
| NBC 2016 Part 6 | Structural design | — | — | Not obtained |

The legacy statement "All formulas have been verified against IS 456 …" in
[../legacy/engineering_basis.md](../legacy/engineering_basis.md) is a **historical claim without
recorded evidence**; it is superseded by this register.
