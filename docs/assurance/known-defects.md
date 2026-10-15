# Known Defects and Open Issues

**As of:** 2026-10-15. Current behaviour that is known to be wrong, incomplete or
risky after the 2026-10 remediation. For engineering simplifications see
[../engineering/limitations.md](../engineering/limitations.md); for the full
history see [risk-register.md](risk-register.md).

| ID | Issue | Severity | Status | Workaround / next step |
|---|---|---|---|---|
| KD-01 | Many tabulated code values (τc, τc,max, Table 26, steel curve, spectra, wind k2/Cpe, fire table) transcribed without verification against the printed standards | H | UNVERIFIED | Line-by-line check by an engineer (B1, B12, B13) |
| KD-02 | Column effective length factor fixed at 1.0 (no Annex E) — may be unconservative for sway frames | H | BLOCKED (D-04) | Engineer to decide method; `DesignInputs.le_factor` available |
| KD-03 | IS 13920 ductile detailing not designed (Ash, capacity shear, joint reinforcement); SMRF selection only warns | H | CONFIRMED_DEFECT (by scope) | Use OMRF (default) or design ductile detailing externally |
| KD-04 | No torsion / accidental eccentricity; 2D frames only | H | CONFIRMED_DEFECT (by scope) | External 3D analysis for irregular buildings |
| KD-05 | Footing sizing ignores base moments (warning only) | M | BLOCKED (D-06) | Review WARN items manually |
| KD-06 | Many repository DXFs carry a wrong `$INSUNITS` (metres for mm drawings); detection relies on an extent plausibility window (1–1000 m) | M | UNVERIFIED | Correct drawing units in source DXFs |
| KD-07 | Designs of some repository plans do not converge within 4–6 iterations (columns keep growing) | M | Observed in sweep | Increase `max_iterations` or review layout; status shows WARN/FAIL |
| KD-08 | Re-entrant corner screen uses √(bbox − footprint) as the projection — crude | M | UNVERIFIED | Engineer review of flagged plans |
| KD-09 | Optimiser results are indicative; re-analysis with optimised sizes not automated | M | UNVERIFIED | Do not apply optimiser sizes without a full re-run |
| KD-10 | Quantities double-count beam/slab/column concrete overlaps; fixed rates | L | Known | Treat as estimates |
| KD-11 | `ifcopenshell` not in `requirements.txt` (IFC optional) | L | BLOCKED (D-07) | `pip install ifcopenshell` |
| KD-12 | Legacy root scripts and `src/tests/*` use pre-2026-10 APIs and write files | L | Known | Do not run; candidates for removal (D-07) |
| KD-13 | Legacy docs (`api_reference.md`, `user_guide.md`, `installation.md`, `engineering_basis.md`, `risk_management.md`) partly describe pre-2026-10 behaviour | L | Known | Banners added; rewrite pending |
| KD-14 | `member_design.py` (test-only) column capacity ignores axial load (CAL-LEG-01) | L | CONFIRMED_DEFECT | Do not use outside tests |
| KD-15 | CI has not been observed running the 2026-10 changes | M | NOT_ASSESSED | Push to a branch and check CI |
| KD-16 | Torsional-irregularity indicator on the Analysis page uses a CoM–CoR offset > 5 % heuristic, not the IS 1893 displacement-based definition | M | UNVERIFIED | Engineer review |
