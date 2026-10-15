# Developer Workflow

**As of:** 2026-10-15.

## Where to make changes

| Change | Edit | Do not |
|---|---|---|
| Section-level formula (flexure, shear, P-M) | `src/section_design.py` | Add another copy in a detailer, page or check |
| Member detailing rules | `src/rebar_detailer.py` | Re-derive pass/fail in pages |
| Loads / takedown | `src/grid_manager.py::calculate_loads`, `src/analysis_integration.py` | Hardcode load intensities |
| Analysis | `src/fea_solver.py` (solver), `src/analysis_integration.py` (model building) | — |
| Orchestration / status | `src/design_pipeline.py` | Duplicate orchestration in `app.py` or `main.py` |
| UI | `app.py`, `pages/`, `src/ui_components.py` | Compute engineering results in the UI |

## Rules of thumb

1. **One implementation per calculation.** If you need a variant, parameterise the production function.
2. **Every result carries `status` and `warnings`.** New checks must add their non-PASS items to the pipeline `failures` list (status aggregation block in `run_design`).
3. **Service vs factored:** follow [../architecture/interfaces-and-contracts.md](../architecture/interfaces-and-contracts.md).
4. **No silent defaults for missing data.** Prefer explicit fields over `getattr(x, "field", default)`; a missing field should fail loudly in tests.
5. **No writes to the working directory** from library code or pages; use `tempfile` or caller-provided paths.
6. **Benchmarks before formulas.** Add a test with an independently derived reference (closed form, hand calculation, SP:16 value) before or with any formula change, and record it in [../verification/verification-matrix.md](../verification/verification-matrix.md).
7. Cite standards only through [../engineering/standards-register.md](../engineering/standards-register.md); mark new citations UNVERIFIED.

## Change checklist

- [ ] Tests added/updated (numerical where possible); full suite passes with the side-effect-free command.
- [ ] Calculation catalogue, assumptions register and limitations updated if behaviour changed.
- [ ] Risk register / known defects / remediation log updated for fixes.
- [ ] No new files written to the repository by tests (`git status` clean apart from intended changes).
- [ ] UI smoke tests pass (`tests/test_streamlit_app.py`).

## Branching and commits

The base branch is `main`. Use a feature branch and pull requests; CI runs the
test suite on Python 3.11–3.13.
