# Benchmark Plan

**As of:** 2026-10-15. Benchmarks needed to raise calculations to evidence level 5
(engineer-reviewed). IDs follow the stage-2 backlog (B0–B10).

Each benchmark must record: inputs, reference source (hand calculation, SP:16
table/chart, textbook example or reference program and version), the reviewer,
the tolerance, and the test that encodes it.

| ID | Benchmark | Reference needed | Acceptance | Depends on | Status |
|---|---|---|---|---|---|
| B0 | Containment: no unevaluated check shown as PASS | — | UI/PDF strings reviewed | — | Done in code 2026-10-15 (UNVERIFIED by owner) |
| B1 | Harness & reference set | Decision D-08 (standards editions, reviewer, reference tool) | Benchmark folder with signed worksheets | D-08 | BLOCKED |
| B2 | Truthful status reporting | Forced-fail fixtures | Every non-PASS member appears in UI/PDF | — | Implemented; tests `test_R5_*` |
| B3 | FEA | Closed form (done) + reference program for a 3-bay, 3-storey frame (gravity + lateral) | Member forces within 1 % | B1 | Closed-form part VERIFIED_FOR_CASES |
| B4 | Beam loads | Hand tributary calculation for interior/edge beams of a 2×2 bay floor | Within 1 % | B1 | Single-bay statics done |
| B5 | Beam design | SP:16 Tables (singly, doubly) and one continuous-beam worked example | Ast within 2 % | B3, B4 | Equilibrium checks done |
| B6 | Column P-M, biaxial, slender | SP:16 interaction charts (≥ 3 points per chart for 2 sections), one biaxial and one slender worked example | Capacity within 3 % | B3 | End points and pure bending done |
| B7 | Seismic inputs | Hand ESA for a regular G+3 building (W, Ta, Sa/g, Vb, Q_i) | Within 1 % | B1, D-02, D-03 | Distribution verified |
| B8 | Lateral analysis | Reference-program 3D model of a regular building (no torsion) vs 2D frames | Storey shears/drifts within 10 % (document) | B3, B7 | NOT_ASSESSED |
| B9 | SCWB / joint | Hand joint calculation from provided steel | Ratios within 2 % | B5, B6, B8 | NOT_ASSESSED |
| B10 | Optimiser | Re-analysis with optimised sizes passes production checks | All members PASS after re-run | B6 | NOT_ASSESSED |
| B11 | Footing | Worked isolated footing example (bearing, punching, one-way, flexure, steel) | Thickness/steel match | B1 | NOT_ASSESSED |
| B12 | Slab | Table 26 value check + worked corner panel | Moments within 1 % | D-05 | NOT_ASSESSED |
| B13 | Wind | Table-based k2 and Cpe for two buildings | Pressures within 2 % | B1 | NOT_ASSESSED |
| B14 | Quantities | Manual take-off for one small building | Concrete/steel within 5 % | — | NOT_ASSESSED |
