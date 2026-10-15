# Gap Analysis and Remediation Roadmap (against the StructOptima engineering mandate)

**As of:** 2026-10-16 (progress in §6). **Basis:** source code at commit `a983bdc` (plus uncommitted, unused 3D-viewer work),
the existing assurance documents, and a recheck of earlier claims against the current source. Nothing in this
document has been reviewed by a qualified structural engineer. No standard was consulted in its authoritative
printed form; every clause reference below is **as cited in the code or commonly cited** and is UNVERIFIED.

Statuses here use the mandate vocabulary: **CONFIRMED** (reproduced from the source or by execution),
**SUSPECTED** (code reading indicates it, not yet reproduced), **UNVERIFIED** (claim or fix not independently
checked). Earlier finding IDs (R1–R27, N1–N13, KD-xx) are preserved; new findings start at N14.

## 1. Summary

| Mandate area | Current state | Gap |
|---|---|---|
| §1/§7 false PASS and misleading outputs | Single status source (`design_pipeline.run_design`); failures list on every screen; "PRELIMINARY" banners | **Fabricated values on the Site Tools page (N14, N15)**; overall `PASS` only means "the implemented checks passed" (N17); storey drift never computed (N16) |
| §2 Indian Standards | Standards register lists every cited clause, all UNVERIFIED | No edition / amendment / supersession check against BIS; tabulated values not checked (KD-01) |
| §3 independent verification | FEA analytical benchmarks; hand-calculated walkthrough; regression tests | Benchmarks B1–B13 pending; no external worked examples (SP:16 etc.) checked; no reviewer |
| §4 analysis | Independent 2D frames on grid lines, DL/LL/EQ/WL, IS 456/1893 combinations, mechanism detection | No torsion / accidental eccentricity / 3D (KD-04), no drift (N16), no P-Δ, no pattern live load, no orthogonal combination, le = 1.0 (KD-02) |
| §5 design & detailing | Beams flexure+shear, columns P-M biaxial with e_min and slenderness, slabs Table 26, footings bearing/punching/one-way shear/flexure | No development length/laps/curtailment in design, no torsion design, deflection by basic L/d only, footing sizing ignores moments (KD-05), IS 13920 not designed (KD-03) |
| §6 lateral system | ESA with irregularity screen (FAIL when ESA not permitted); OMRF default, SMRF warns | Drift, torsion, accidental eccentricity, R-factor justification, ductile detailing missing |
| §7 visible failures | FAIL/WARN aggregated; non-convergence → WARN; frame solve failures listed | Silent defaults for SBC / zone / soil (N18); one-plane columns not flagged (N19); result-state semantics (N17) |
| §8 optimisation | Optimiser results labelled indicative (KD-09) | No automated re-check of optimiser output through `run_design` |
| §9 inputs & traceability | DXF units by `$INSUNITS` + plausibility; IFC import/export; marks shared across schedules, drawings and IFC | DXF unit plausibility window only (KD-06); COBie hard-codes M25 (N15) |
| §12 documentation | Full set exists under `docs/` | Several documents still dated 2026-10-15 and contain stale lines (N21) |

## 2. New findings (recheck of 2026-10-16)

| ID | Finding | Evidence (source location) | Status | Sev | Significance | Requirement / missing reference | Independent verification | Proposed correction | Acceptance criteria |
|---|---|---|---|---|---|---|---|---|---|
| N14 | Site Tools → BIM & Handover → *Design Reports* generates a "Detailed Design Report" with **hard-coded** modal mass participation 92.5 %, storey drifts 8 mm and 12 mm on 3000 mm storeys, and a sample calculation "Mu = Min Eccentricity"; the download is labelled PDF but is text | `pages/5_🔧_Site_Tools.py:351-375`; `src/documentation.py` | CONFIRMED | C | A user sees drift and modal checks that were never computed, presented as results for their building | Mandate §5, §7, §9 (no placeholder results); IS 1893 drift/modal requirements (clauses to verify) | Code reading; render the page and compare the report to the model | Remove the report, or disable it until it is generated only from computed results | No value in any report that does not come from the model; UI test asserts the fabricated numbers are absent |
| N15 | *SHM & IoT* and *Digital Twin* tabs show **random / simulated** values (strain heat map, FFT, damage index from a slider with base frequency fixed 1.5 Hz, as-built deviation `random.uniform(-10, 10)`), element list includes hard-coded "B1", "B2"; *COBie* tab writes "RCC Column M25 / RCC Beam M25" regardless of the designed grade | `pages/5_🔧_Site_Tools.py:313-345, 379-400, 438-460`; `src/shm_viz.py:23-41`; `src/digital_twin.py:53` | CONFIRMED | H | Simulated monitoring data can be mistaken for real structural health information; COBie data contradicts the design | Mandate §1, §9 | Code reading | Remove these tabs or label them unmistakably as demonstrations with no connection to the building; COBie to use the actual grade | No random or fixed demo value presented as building data; COBie grade equals `DesignInputs.conc_grade` (test) |
| N16 | Storey drift is **not computed** in the production pipeline; the design can report PASS with no drift check. A drift helper exists only for the fabricated report (N14) | `src/design_pipeline.py` (no drift step); `src/documentation.py:85` | CONFIRMED | H | Flexible frames can pass while violating the code drift limit; drift also governs separation and non-structural damage | IS 1893 (Part 1):2016 storey-drift limit (commonly cited Cl 7.11.1, 0.004 h) — **to verify** | Analytical portal-frame benchmark (k = 12EI/h³ per column, fixed–fixed) and hand check on the walkthrough building | Compute storey displacement from each frame's EQ/WL solution (unfactored, with the code-required load level), report max storey drift ratio per direction, FAIL above the verified limit | Benchmark matches hand value within 1 %; drift appears in the failures list and the report |
| N17 | Overall `status = "PASS"` means "every implemented check passed". Checks outside the implemented scope (drift, torsion, IS 13920 detailing, development/lap lengths, orthogonal effects, pattern loading, footing moments) do not affect it, and every engineering value is UNVERIFIED | `src/design_pipeline.py:300-338`; UI banners | CONFIRMED | H | A "PASS" can be read as engineering validation | Mandate §7 result states | Review of the status aggregation | Replace the overall state with explicit states (e.g. `COMPLETED_WITHIN_IMPLEMENTED_CHECKS` / `COMPLETED_WITH_WARNINGS` / `FAILED` / `UNSUPPORTED_CONFIGURATION`) plus an always-present `NOT_VERIFIED` qualifier and a list of checks not performed | No screen, report or export shows a bare "PASS"; the list of unperformed checks is shown with every result |
| N18 | Safety-critical inputs are pre-filled with plausible defaults that the user need not confirm: SBC 200 kN/m², seismic zone, soil type, wind zone (`app.py:105, 121, 134`); `DesignInputs` defaults; `wind_zone=None` silently skips wind with no message; the Reports page falls back to zone "II" while the Analysis page falls back to "III" | `app.py:105-134`; `src/design_pipeline.py:41-49, 204-210`; `pages/4_📄_Reports.py:48`; `pages/1_📊_Analysis.py:340` | CONFIRMED | M | Geotechnical and seismic parameters are site-specific; an unconfirmed default can size every footing and member | Mandate §7 ("no default value should silently replace a safety-critical input") | Code reading; UI test | Require explicit entry/confirmation of SBC, zone, soil, wind zone before design; record "wind not considered" as a WARN when skipped; remove inconsistent fallbacks | Design cannot run without confirmed inputs; skipped wind appears in failures |
| N19 | A column that lies on only one frame line receives lateral moments in that direction only, without a warning (the warning is raised only when the column lies on no frame) | `src/analysis_integration.py:455-480` | SUSPECTED | M | Under-estimated biaxial moments for columns off the orthogonal grid (CAD/IFC plans) | Mandate §4 ("never silently omit a force component") | Construct a CAD plan with an offset column; inspect `design_forces` | WARN (or FAIL for EQ zones) when one direction has no frame; document | Test reproduces and the column is flagged |
| N20 | Footing base moment is "un-factored" by dividing the worst factored bottom moment by 1.5 for every combination, including EQ/WL combinations with factor 1.2 | `src/design_pipeline.py:251` | CONFIRMED (code) | L | Under-estimates the service moment by up to 20 % in the base-moment WARN (moments are not used for sizing, KD-05) | IS 456 Table 18 factors (to verify) | Hand calculation | Carry service-combination moments explicitly | Unit test with hand values |
| N21 | Documentation drift: `limitations.md` still says the Drawings page writes DXF files into the working directory (fixed by N10); several registers still dated 2026-10-15 | `docs/engineering/limitations.md` (Operational) | CONFIRMED | L | Misleading documentation | Mandate §12 | Read | Correct and re-date | — |

Rechecked and **not** a finding: the approximate period uses the larger plan dimension in `0.09 h / √d` and takes the
smaller of the two formulas (`src/seismic.py:359-361`), which gives the shorter period and therefore the larger or
equal spectral acceleration — conservative for both directions (code basis still UNVERIFIED).

## 3. Earlier findings rechecked

The R1–R27 and N1–N13 fixes remain **UNVERIFIED** (code changed, regression tests pass, no independent engineering
review). Rechecks against current source: R5/N3 (single status source) — confirmed in `run_design`; R8 (lateral
loads reach design) — confirmed, EQ/WL storey forces are shared by frame stiffness (`analysis_integration.py:314-396`);
R16 (footing reinforcement designed) — confirmed in `foundation_eng`. Open known defects KD-01…KD-16 stand as recorded
in [known-defects.md](known-defects.md).

## 4. Remediation roadmap (mandate §13 order)

Each work item follows the mandate §11 workflow: evidence → expected behaviour established independently → test
first → smallest change → approval where safety-critical → regression → documentation.

| Phase | Work items | Needs |
|---|---|---|
| **P1 — False results and misleading claims** | WI-1 remove/disable fabricated and simulated outputs (N14, N15); WI-2 result-state semantics and "checks not performed" list (N17); WI-3 confirmed safety-critical inputs, wind-skip visibility, consistent fallbacks (N18); WI-4 one-plane column flag (N19) | Owner approval of scope changes (removing features, changing statuses) |
| **P2 — Critical analysis/design gaps** | WI-5 storey drift (N16); WI-6 accidental eccentricity / torsion screening or a declared-scope FAIL for torsionally irregular plans (KD-04, KD-16); WI-7 effective length per Annex E or a conservative declared rule (KD-02); WI-8 orthogonal combination and pattern live load; WI-9 footing sizing with base moments (KD-05, N20) | Verified clauses (IS 1893, IS 456); approval for each formula |
| **P3 — Independent benchmarks** | WI-10 obtain the authoritative editions/amendments of IS 456, IS 875 (1, 2, 3), IS 1893 (1), IS 13920, IS 1786, IS 1904 and record them; WI-11 line-by-line check of transcribed tables (KD-01); WI-12 benchmarks B1–B13 against SP:16 / published worked examples / independent software | Copies of the standards (owner to procure); reviewer |
| **P4 — Lateral load path completeness** | WI-13 R-factor justification: either design IS 13920 detailing (Ash, capacity shear, joints) or restrict the declared scope; WI-14 response-spectrum / 3D analysis or explicit UNSUPPORTED_CONFIGURATION beyond ESA limits | Engineering decision on scope |
| **P5 — Reinforcement, foundations, reports** | WI-15 development length, laps, curtailment in design and drawings; WI-16 deflection with modification factors; WI-17 report/BBS/quantity consistency tests | Verified clauses |
| **P6 — Inputs and robustness** | WI-18 DXF unit confirmation by the user (KD-06); input validation layer with typed units | — |
| **P7 — Architecture** | WI-19 typed result model carrying status per check; remove legacy scripts (D-07); CI observed (KD-15) | — |
| **P8 — Future scope (no claims until verified)** | 3D frame with rigid diaphragm, modal analysis, P-Δ, IS 16700 applicability; 3D viewer / walkthrough (paused, see below) | — |

## 5. First safety-critical work item

**WI-1 — Remove fabricated and simulated engineering outputs (N14, N15).** It is the only place where the
application presents numbers that were never computed for the user's building (drift, modal mass, damage index,
as-built deviation). It changes no formula, so its expected behaviour is unambiguous; it is small and testable
(a UI test asserting the absence of the fixed values). It is a **scope change** (removes or disables visible
features), so it needs owner approval before implementation (mandate §11.7).

WI-2 (status semantics) and WI-5 (drift) follow; WI-5 needs the verified IS 1893 drift clause before the limit is
coded.

## 6. Progress (2026-10-16, after the owner's instruction "everything should be working, nothing simulated, continue the 3D work")

| Item | State |
|---|---|
| WI-1 (N14, N15) | Implemented (RM-30): simulated features removed or replaced by calculations on the design / user data. Also found and fixed **N22** (invented utilisation colours in the 3D and 2D views, RM-32) |
| WI-2 (N17) | Implemented (RM-30): status label "NOT VERIFIED", checks-not-performed list on the dashboard, Reports page, PDF and calculation summary |
| WI-3 (N18) | Implemented (RM-30): SBC must be typed, site parameters confirmed before a run, wind-skip WARN, no fallback zone on the Reports page |
| WI-4 (N19) | Flag implemented (RM-29); moments in the missing direction are still not computed (KD-19) |
| WI-5 (N16) | Implemented (RM-29, D-16): drift computed, EQ drift FAIL grows column stacks; **limit values UNVERIFIED** — owner/engineer confirmation requested |
| N20 | Implemented (RM-29) |
| 3D viewer / walk-through | Implemented (RM-31) |
| P2–P8 | Open |

## 7. Work paused by this analysis (superseded)

The browser 3D viewer / walkthrough (visuals phases 3–4, D-15) is user-experience work (mandate priority 8). Its
uncommitted files (`src/viewer_model.py`, `components/viewer3d/`) are not imported anywhere and change no
results. It stays paused until P1 is done or the owner decides otherwise.
