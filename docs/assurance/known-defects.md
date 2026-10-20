# Known Defects and Open Issues

**As of:** 2026-10-20. Current behaviour that is known to be wrong, incomplete or
risky after the 2026-10 remediation. For engineering simplifications see
[../engineering/limitations.md](../engineering/limitations.md); for the full
history see [risk-register.md](risk-register.md).

| ID | Issue | Severity | Status | Workaround / next step |
|---|---|---|---|---|
| KD-01 | Many tabulated code values (τc, τc,max, Table 26, steel curve, spectra, wind k2/Cpe, fire table) transcribed without verification against the printed standards | H | UNVERIFIED | Line-by-line check by an engineer (B1, B12, B13) |
| KD-02 | Column effective length factor fixed at 1.0 (no Annex E) — may be unconservative for sway frames | H | BLOCKED (D-04) | Engineer to decide method; `DesignInputs.le_factor` available |
| KD-03 | IS 13920 ductile detailing not designed (Ash, capacity shear, joint reinforcement); SMRF selection only warns | H | CONFIRMED_DEFECT (by scope) | Use OMRF (default) or design ductile detailing externally |
| KD-04 | Torsion and accidental eccentricity: implemented 2026-10-20 on the rigid-diaphragm 3D model (CAL-SEI-12); flexible diaphragms not modelled | M | Partly resolved (RM-36) | External flexible-diaphragm 3D analysis for re-entrant / open plans |
| KD-05 | Footing sizing ignores base moments (warning only) | M | BLOCKED (D-06) | Review WARN items manually |
| KD-06 | Many repository DXFs carry a wrong `$INSUNITS` (metres for mm drawings); detection relies on an extent plausibility window (1–1000 m) | M | UNVERIFIED | Correct drawing units in source DXFs |
| KD-07 | Designs of some repository plans do not converge within 4–6 iterations (columns keep growing) | M | Observed in sweep | Increase `max_iterations` or review layout; status shows WARN/FAIL |
| KD-08 | Re-entrant corner screen uses √(bbox − footprint) as the projection — crude | M | UNVERIFIED | Engineer review of flagged plans |
| KD-09 | Optimiser results are indicative; re-analysis with optimised sizes not automated | M | UNVERIFIED | Do not apply optimiser sizes without a full re-run |
| KD-10 | Quantities double-count beam/slab/column concrete overlaps; fixed rates | L | Known | Treat as estimates |
| KD-11 | (Closed 2026-10-16) `ifcopenshell` was not in `requirements.txt` | — | Added (D-15) | — |
| KD-12 | (Closed 2026-10-16) Legacy root scripts and `src/tests/*` used pre-2026-10 APIs and wrote files — moved out of the repository | — | Closed | — (was: candidates for removal (D-07) |
| KD-13 | Legacy docs (now in `docs/legacy/`: `api_reference.md`, `user_guide.md`, `installation.md`, `engineering_basis.md`, `risk_management.md`) partly describe pre-2026-10 behaviour | L | Known | Banners added; rewrite pending |
| KD-14 | `member_design.py` (test-only) column capacity ignores axial load (CAL-LEG-01) | L | CONFIRMED_DEFECT | Do not use outside tests |
| KD-15 | CI has not been observed running the 2026-10 changes | M | NOT_ASSESSED | Push to a branch and check CI |
| KD-16 | Mass – stiffness offset screen (Checks → Joints & plan) uses a CoM–CoR offset > 5 % heuristic, not the IS 1893 displacement-based definition. Since 2026-10-20 it is labelled a screen and no longer shows a green "no torsional irregularity" result | M | UNVERIFIED | Engineer review; replace with the IS 1893 check once a 3D analysis exists |
| KD-17 | (Closed in code 2026-10-16) Slab dead load used the occupancy slab thickness while slabs were designed thicker (N13) | — | UNVERIFIED (fix implemented, see RM-26) | Engineer review of the per-panel load rule |
| KD-18 | Storey drift limits (0.004 h EQ, H/500 wind) checked against the printed standards 2026-10-20; drifts include torsion (rigid floors); automatic column growth for drift (D-16) | L | VERIFIED limits | Flexible-diaphragm check for re-entrant plans |
| KD-19 | A column lying on a frame line in one direction only gets no frame moments in the other direction (now WARN, N19) | M | Known | Add beams / frames on that line or check the column separately |
| KD-20 | 3D viewer: geometry is boxes from the design (no openings, reinforcement or stairs); walk-through has no collision; footings drawn directly below the column base | L | Known (by scope) | Use the drawing set for construction details |
| KD-21 | BBS: default bars, spacings and slab panel size used when a member description cannot be parsed (N27). The BBS covers one typical floor and the ground-storey columns; footings, upper columns and staircases are not in it | M | Known (scope now stated in the UI) | Replace the fallbacks by an explicit "not scheduled" entry (needs approval); extend the BBS to all floors and footings |
| KD-22 | `pypdfium2` is a test-only dependency (N28) | L | Resolved in CI 2026-10-20 | Installed by `.github/workflows/ci.yml` and `docs/development/setup.md` |
| KD-23 | Dynamic analysis: response spectrum on a rigid-diaphragm 3D model implemented 2026-10-20 (D-26). Not covered: flexible diaphragms (re-entrant corners, openings > 50 %; WARN), time history, P-Δ. Floor mass centre / inertia from slab panels only | M | Partly resolved | Full 3D frame model with flexible diaphragms (high-rise phase) |
| KD-24 | IS 13920 confining steel (Ash) and capacity-design shear, IS 1893 100 % + 30 % (non-orthogonal systems only) and vertical earthquake | H | Open | Listed in "checks not performed" |
| KD-25 | Joint effective breadth for bc ≥ bb: the printed copy of IS 13920 9.1.2(a) does not show it in full; the mirror form min[bc; bb + 0.5 hc] is used | M | UNVERIFIED | Confirm from another print / BIS |
| KD-26 | DXF beams get an initial 300 × 600 mm section (plan drawings carry no beam size); width is kept, depth is designed | L | Known | Enter beam widths from the architectural drawing (future input) |
| KD-27 | Circular columns are designed as squares of equal area (warning shown) | M | Known | Design circular columns separately |
| KD-28 | Imposed loads on corridors, stairs and balconies, wind k3 / k4, cantilever lateral stability limits not modelled | M | Open | See standards register GAP rows |

