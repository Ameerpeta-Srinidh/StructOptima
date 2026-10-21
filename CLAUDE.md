# CLAUDE.md — StructOptima

Persistent instructions for working in this repository. Keep this file short;
detailed architecture and engineering information lives in `docs/` (start at
`docs/README.md`).

## Project

StructOptima is a Python/Streamlit **preliminary** design aid for reinforced-concrete
frame buildings (references IS 456, IS 1893 Part 1, IS 875, IS 13920). It is not a
certified analysis/design or code-compliance tool.

- Entry points: `app.py` (Streamlit navigation entry point) + `pages/` (setup, overview, checks, members, drawings,
  reports, site_tools), `main.py` (CLI). Inputs live in `in_*` session keys (`src/ui_state.py`); table rows shown in
  the UI are built from the design results in `src/ui_tables.py` (never estimated or defaulted in a page).
- Standards PDFs (copyrighted) go in the git-ignored `_local/standards/`; list in
  `docs/engineering/standards-to-obtain.md`. Read them before verifying any cited clause.
- All design orchestration goes through `src/design_pipeline.py::run_design`, which
  returns `DesignResults.status` and `failures` — the single source of design status.
- Core chain: `grid_manager` (model, service-load takedown) → `analysis_integration`
  (2D frames, load cases, combinations; `pseudo3d` rigid-diaphragm 3D model for the response spectrum and
  torsion) → `fea_solver` → `rebar_detailer` →
  `section_design` (IS 456 section checks); plus `seismic`, `wind_load`,
  `foundation_eng`, `durability` (covers / grade / fire), `quantifier`, `report_gen`. Ingest: `cad_loader`/`cad_parser`, `bim_loader`.
  Site drawings: `src/drawings/` (one primitive model rendered to PDF/DXF/SVG; marks shared with schedules).
  3D viewer: `src/viewer_model.py` + `components/viewer3d` (edit `src/main.js`, run `npm run build`, commit
  `dist/viewer.js` — Streamlit Cloud does not run npm).
- Nothing shown to users may be simulated, random or placeholder: every value comes from the design or from
  data the user enters (owner instruction 2026-10-16; see `docs/assurance/gap-analysis.md`).
- Several modules are test-only or unused (e.g. `member_design`, `validators`,
  `structural_checks`, `auth`) — check `docs/architecture/module-catalogue.md`
  before assuming a module is in the production path.

## Running tests

Configuration: `pytest.ini` (`testpaths = tests`); CI: `.github/workflows/ci.yml`.
Use the resource-safe runner (one file at a time, memory-capped, exact counts, non-zero exit on anything not
passed; logs outside the repository):

```bash
PYTHONDONTWRITEBYTECODE=1 python tests/run_suite.py --layer regression      # or unit, geometry, engineering,
PYTHONDONTWRITEBYTECODE=1 python tests/run_suite.py tests/test_drift.py     #   integration, reference, all
```

Plain pytest for one quick file: `PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/<file> -p no:cacheprovider -q`.
Layers, measured times / memory and side effects: `docs/verification/test-execution-guide.md`.
Legacy one-off scripts were moved out of the repository on 2026-10-16 (local copies in the
git-ignored `_local/`; history in git). Do not add scripts or generated outputs at the root:
inputs go in `samples/`, documents in `docs/`, personal material in `_local/`.
IFC tests need the optional `ifcopenshell` (skipped otherwise).

## Resource safety (machine: ~14 GiB RAM, 4 GiB swap)

- Never use parallel pytest workers (`-n`) and never start two test runs or other memory-heavy jobs at once:
  `-n 8` / `-n 2` were OOM-killed on 2026-10-21 (one worker at 11.8 GiB). Parallelism only after measuring.
- Start with the targeted test file; widen in batches (`tests/run_suite.py` layers). Cap ad-hoc diagnostics with
  `prlimit --as=<bytes>` and a `timeout`, and watch peak memory (`/usr/bin/time -f %M`).
- If memory grows unexpectedly, stop and find the allocating step (smallest input, capped) before running it again.
- An interrupted, timed-out or OOM-killed run is a failed run, never a pass. Measured per-file costs are in
  `docs/verification/test-execution-guide.md`; keep them current when a file changes cost.

## Engineering correctness (non-negotiable)

- Structural calculations are engineering-critical. Running without error, or a green test suite, is not evidence
  that a result is correct or that a building is safe; never say or imply otherwise.
- Standards in scope (editions as in `docs/engineering/standards-register.md`): IS 456:2000, IS 1893 (Part 1):2016
  (Amd 1, 2), IS 13920:2016 (Amd 1, 2), IS 875 Parts 1 and 2:1987 and Part 3:2015, SP 16:1980, IS 1786:2008,
  NBC 2016 Parts 4 and 6. Claim only the clauses the register marks implemented; never claim code compliance.
- State the evidence level of every behaviour you report: **implemented** (code exists) / **automatically tested**
  (a test asserts it) / **independently verified** (hand calculation, closed form, SP 16 or printed standard) /
  **professionally reviewed** (qualified engineer; nothing is yet).
- Never change formulas, units, load factors/combinations, design assumptions, safety factors, numerical
  tolerances, tabulated code values or cited provisions to make a test pass, and never without (a) documented
  evidence (independent hand calculation, closed-form result, or authoritative reference) and (b) explicit
  approval from the user.
- Never invent standard clauses or values. Unverified citations go into
  `docs/engineering/standards-register.md` marked UNVERIFIED.
- Respect the load contract: `Column.load_kn` and related fields are **service**
  loads; analysis envelopes, `design_forces` and `detail_*` inputs are **factored**
  (`docs/architecture/interfaces-and-contracts.md`).
- One implementation per calculation: change the production function in
  `section_design` / `rebar_detailer` etc. rather than adding a copy.

## Change control (test-driven)

Before changing code: read the module, its callers and its tests; record the baseline (run the affected test
files); check `git status` / `git diff` and preserve every unrelated change, tracked or untracked (never
`git reset --hard`, `git clean`, blanket checkout or revert). Before changing an interface, inspect all callers and
dependents (pages, reports, exporters and the pipeline consume result fields).

Fixing a defect:
1. Reproduce it with the smallest input (script or failing test), capped as under Resource safety.
2. Find the underlying cause, not just the example; add a regression test that fails before the fix — for the
   reported case and for the general rule — numerical and against an independent reference where possible.
3. Make the smallest fix; no unrelated refactoring.
4. Run the regression test, then the affected layers, then the wider suite in batches; investigate every new
   failure; confirm `git status` shows no files written by tests.

Never delete, skip or xfail a failing test, weaken an assertion or invariant (`tests/invariants.py`), widen a
tolerance, change an expected value or suppress a warning to get a green run. An expectation that is genuinely
wrong is changed only with the engineering requirement and independent evidence written next to it.
Invalid input is rejected with a clear `ValueError` before expensive calculations; non-finite or implausible
intermediate results fail loudly (`FloatingPointError` / FAIL status) — never clipped, replaced by finite numbers
or hidden.

## Completion criteria

A task is done only with: a reviewed diff; new or updated tests; the targeted tests, affected regression and
integration tests and `tests/invariants.py` checks actually run and passing (or failures reported); the
documentation below updated. Report what was not run and why. Never report a test as passed unless its run
completed.

## Safety

- Successful execution or passing tests is **not** evidence of structural safety
  or code compliance. Say so explicitly when reporting results.
- Failed, incomplete, fallback and unverified results must surface as `status`
  (PASS/WARN/FAIL) and `warnings` on result objects and reach the pipeline
  `failures` list — never hide them behind `getattr(..., default)` or success messages.
- Do not mark anything verified or resolved without recorded evidence; risk-register
  items become RESOLVED_WITH_EVIDENCE only after review by a qualified engineer.
- Library code and pages must not write into the working directory.

## Documentation maintenance

When implementation changes, update the affected documents in the same change:
`docs/architecture/*` (modules, flows, interfaces), `docs/engineering/*`
(calculation catalogue, assumptions, limitations, standards),
`docs/verification/*` (test inventory, verification matrix, results with date),
`docs/assurance/*` (risk register, known defects, decision log, remediation log).
Label decisions as PROPOSED unless the user approved them.
**Formula document (owner instruction 2026-10-20):** after every check or modification, update
`docs/formulas/StructOptima-Formulas.tex` — a dated entry at the top of the revision history, the affected
section, `\lastupdated` — then run `docs/formulas/build.sh` and commit the `.tex` and the `.pdf` together.

## Final response requirements

Every task summary must state:
- files changed (and files created/deleted);
- tests actually run (commands) and their results, including failures and skips —
  never claim tests pass without running them;
- engineering formulas, assumptions or provisions affected, if any;
- remaining uncertainties, unverified items and decisions needed from the user.
