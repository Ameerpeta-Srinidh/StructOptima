# Standards Register

**As of:** 2026-10-15.

No printed standard was available to the authors of this documentation. All
clause numbers below are **as cited in the source code or comments** and every
entry is **UNVERIFIED** until an engineer checks the wording, applicability and
edition against the authoritative publication. Values transcribed into code are
listed so they can be checked line by line.

| Standard (edition cited) | Used for | Cited clause / table (as in code) | Code location | Verification |
|---|---|---|---|---|
| IS 456:2000 | Limit-state design | Table 18 (load factors) | `load_combinations.IS_456_COMBINATIONS` | UNVERIFIED |
| IS 456:2000 | Design shear strength | Table 19 values M20–M40 | `section_design.TAU_C_TABLES` | UNVERIFIED — check every value |
| IS 456:2000 | Maximum shear stress | Table 20 | `section_design.TAU_C_MAX` | UNVERIFIED |
| IS 456:2000 | Stress block, xu,max/d | Cl 38.1, Annex G | `section_design` | UNVERIFIED |
| IS 456:2000 / SP:16 | Cold-worked steel design curve | Fig. 23A / SP:16 Table A | `section_design._CW_POINTS` | UNVERIFIED |
| IS 456:2000 | Compression members: minimum eccentricity, axial formula, biaxial, slenderness | Cl 25.4, 39.3, 39.6, 39.7.1 | `section_design.check_column`, `audit.audit_columns` | UNVERIFIED |
| IS 456:2000 | Effective length | Annex E (not implemented; le = 1.0 L) | `detail_columns` | BLOCKED (D-04) |
| IS 456:2000 | Minimum / maximum beam steel | Cl 26.5.1.1 | `section_design.min_tension_steel`, `detail_beam` | UNVERIFIED |
| IS 456:2000 | Shear reinforcement | Cl 40, 26.5.1.6 | `section_design.design_shear` | UNVERIFIED |
| IS 456:2000 | Column ties | Cl 26.5.3.2 | `detail_column` | UNVERIFIED |
| IS 456:2000 | Two-way slab coefficients | Table 26 (9 cases × 8 ratios) | `rebar_detailer.TABLE26` | UNVERIFIED — check every value (D-05) |
| IS 456:2000 | Span/depth ratios | Cl 23.2.1 (basic values only) | `detail_beam`, `detail_slab` | UNVERIFIED |
| IS 456:2000 | Footings, punching | Cl 34, 31.6.3.1 | `foundation_eng` | UNVERIFIED |
| IS 456:2000 | Fire resistance | Table 16A | `stability.FIRE_RESISTANCE_TABLE` | UNVERIFIED |
| IS 456:2000 | Lateral stability of beams, column slenderness limit | Cl 23.3, 25.3.1 | `stability` | UNVERIFIED |
| IS 1893 (Part 1):2016 | Zone factors | Table 3 | `seismic.ZONE_FACTORS` | UNVERIFIED |
| IS 1893 (Part 1):2016 | Importance factor | Table 8 | `seismic.OCCUPANCY_IMPORTANCE` | UNVERIFIED (D-03) |
| IS 1893 (Part 1):2016 | Response reduction factor | Table 9 | `seismic.RESPONSE_REDUCTION` | UNVERIFIED (D-02) |
| IS 1893 (Part 1):2016 | Design spectrum (equivalent static) | spectrum equations for soil I/II/III | `SeismicDesignChecker.SPECTRUM` | UNVERIFIED |
| IS 1893 (Part 1):2016 | Approximate period | Cl 7.6.2 | `calculate_base_shear` | UNVERIFIED |
| IS 1893 (Part 1):2016 | Seismic weight LL fraction | Table 10 | `design_pipeline._ll_factor` | UNVERIFIED |
| IS 1893 (Part 1):2016 | Vertical distribution of base shear | equivalent static distribution | `run_full_analysis` | UNVERIFIED |
| IS 1893 (Part 1):2016 | Irregularities / analysis method | Tables 5, 6; Cl 7.7 (as cited) | `check_irregularities`, `check_analysis_method` | UNVERIFIED |
| IS 1893 (Part 1):2016 | Cracked section stiffness | Cl 6.4.3.1 (as cited) | `analysis_integration` | UNVERIFIED |
| IS 13920:2016 | SCWB 1.4 factor | Cl 7.2.1 (as cited) | `evaluate_joint_checks` | UNVERIFIED |
| IS 13920:2016 | Joint shear strength coefficients | Cl 9 (as cited) | `evaluate_joint_checks` | UNVERIFIED |
| IS 13920:2016 | End-zone spacing | beam / column special confining provisions (as cited) | `detail_beam`, `detail_column`, `evaluate_joint_checks` | UNVERIFIED; Ash not implemented |
| IS 875 (Part 1):1987 | Material unit weights | Table 1 (as cited) | `Wall.density_kn_m3` | UNVERIFIED |
| IS 875 (Part 2):1987 | Imposed loads | Table 1 (as cited) | `building_types.py` | UNVERIFIED |
| IS 875 (Part 3):2015 | Basic wind speed, k2, pz, Cpe, Cpi | zones, Table 2, Table 5 (as cited) | `wind_load.py` | UNVERIFIED (k2 power-law approximation) |
| IS 1200, IS 1077, IS 2250, IS 1661, IS 1905 | Quantity measurement, bricks, mortar, plaster | as cited in report text | `quantifier`, `wall_calculator`, `report_gen` | NOT_ASSESSED |
| NBC 2016 | Fire rating by height | as cited | `stability._get_required_fire_rating` | UNVERIFIED |

The legacy statement "All formulas have been verified against IS 456 …" in
[../engineering_basis.md](../engineering_basis.md) is a **historical claim without
recorded evidence**; it is superseded by this register.
