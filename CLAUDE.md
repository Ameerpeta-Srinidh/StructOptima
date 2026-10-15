# CLAUDE.md — StructOptima

Persistent instructions for working in this repository. Keep this file short;
detailed architecture and engineering information lives in `docs/` (start at
`docs/README.md`).

## Project

StructOptima is a Python/Streamlit **preliminary** design aid for reinforced-concrete
frame buildings (references IS 456, IS 1893 Part 1, IS 875, IS 13920). It is not a
certified analysis/design or code-compliance tool.

- Entry points: `app.py` (Streamlit dashboard) + `pages/` (5 pages), `main.py` (CLI).
- All design orchestration goes through `src/design_pipeline.py::run_design`, which
  returns `DesignResults.status` and `failures` — the single source of design status.
- Core chain: `grid_manager` (model, service-load takedown) → `analysis_integration`
  (2D frames, load cases, combinations) → `fea_solver` → `rebar_detailer` →
  `section_design` (IS 456 section checks); plus `seismic`, `wind_load`,
  `foundation_eng`, `quantifier`, `report_gen`. Ingest: `cad_loader`/`cad_parser`, `bim_loader`.
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
Side-effect-free run (no cache/bytecode files in the repo):

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest tests -p no:cacheprovider -q
```

Subsets and side effects: `docs/verification/test-execution-guide.md`.
Do not run `src/tests/*.py`, `demo_*.py`, `stress_test_core.py`, `ui_test_runner.py`
or `generate_*.py` casually — they write files into the repository.
IFC tests need the optional `ifcopenshell` (skipped otherwise).

## Engineering correctness (non-negotiable)

- Never change formulas, units, load factors/combinations, design assumptions,
  tabulated code values or cited provisions without (a) documented evidence
  (independent hand calculation, closed-form result, or authoritative reference)
  and (b) explicit approval from the user.
- Never invent standard clauses or values. Unverified citations go into
  `docs/engineering/standards-register.md` marked UNVERIFIED.
- Respect the load contract: `Column.load_kn` and related fields are **service**
  loads; analysis envelopes, `design_forces` and `detail_*` inputs are **factored**
  (`docs/architecture/interfaces-and-contracts.md`).
- One implementation per calculation: change the production function in
  `section_design` / `rebar_detailer` etc. rather than adding a copy.

## Working method (test-driven)

1. Reproduce the defect (minimal script or failing test) before changing code.
2. Add a regression test — numerical and against an independently derived
   reference where possible.
3. Make the minimal fix; avoid unrelated refactoring.
4. Run the relevant tests, then the full suite; confirm `git status` shows no
   files written by tests.
5. Before changing an interface, inspect all callers and dependents (pages, reports,
   exporters and the pipeline consume result fields).

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

## Final response requirements

Every task summary must state:
- files changed (and files created/deleted);
- tests actually run (commands) and their results, including failures and skips —
  never claim tests pass without running them;
- engineering formulas, assumptions or provisions affected, if any;
- remaining uncertainties, unverified items and decisions needed from the user.
