# Decision Log

**As of:** 2026-10-15.

All decisions below are **PROPOSED** by the development assistant during the
2026-10 remediation. None has been approved by the project owner or a licensed
structural engineer. The project owner's instruction on 2026-10-15 was to "fix
all" findings; that instruction is recorded here as authority to implement code
changes, **not** as engineering approval of the choices.

| ID | Decision (proposed) | Rationale | Alternatives | Affected code | Owner approval |
|---|---|---|---|---|---|
| D-01 | `Column.load_kn` and related fields are SERVICE loads; factors are applied only in analysis combinations, detailing inputs and the audit | Removes the mixed service/factored semantics behind R2, R6, R9 | Store factored loads | `grid_manager`, `analysis_integration`, `audit`, `optimizer`, `design_pipeline` | Pending |
| D-02 | Default structural system OMRF (R = 3); SMRF (R = 5) only on user selection with a warning; SCWB/joint failures FAIL only for SMRF (WARN/advisory for OMRF) | Tool does not design IS 13920 detailing | Keep R = 5 and implement full IS 13920 | `seismic`, `design_pipeline`, `app.py` | Pending — permissibility of OMRF in zones III–V must be checked against IS 1893 Table 9 |
| D-03 | Importance factor defaults: Residential 1.0, Office 1.2, Retail 1.5, Institutional 1.5, Assembly 1.5; user override in the UI | Conservative defaults pending occupancy-specific review | 1.0 everywhere | `seismic.OCCUPANCY_IMPORTANCE`, `app.py` | Pending |
| D-04 | Column effective length factor 1.0 × storey height (configurable) | No Annex E implementation; conservative alternatives need sway assessment | Use a fixed 1.2–2.0 factor; implement Annex E charts | `detail_columns`, `DesignInputs.le_factor` | **BLOCKED** — engineering decision required |
| D-05 | Two-way slab coefficients from IS 456 Table 26 as transcribed in `rebar_detailer.TABLE26` | Replaces a single fixed coefficient | Annex D yield-line method | `rebar_detailer` | Pending — values must be checked |
| D-06 | Footing sizing keeps axial-only area; base-moment effects reported as WARN | Avoids silent redesign without SBC increase rules | Size for eccentric pressure | `foundation_eng`, `design_pipeline` | Pending |
| D-07 | Do not delete or move repository clutter; do not add `ifcopenshell` to requirements | File deletion / dependency changes need owner approval | Clean up | — | Pending |
| D-08 | Benchmark reference set (standard editions, reviewer, reference software) | Needed for evidence level 5 | — | docs/verification | **Not made** |
| D-09 | Single design-status list drives dashboard, Analysis page, Reports page banner and PDF; PDF carries "PRELIMINARY — NOT FOR CONSTRUCTION" | Containment of false assurance (R5, R6, R15, R25) | Disable exports | `design_pipeline`, `app.py`, pages, `report_gen` | Pending |
| D-10 | Interaction curves memoised (LRU 4096) and vectorised | 127 s → 1.8 s for a G+7 building | No cache | `section_design` | Pending |
| D-11 | `get_logger` console-only by default; file logging only via `setup_logging()` or `STRUCTOPTIMA_LOG_FILE` | No files created on import (N5) | Previous behaviour | `logging_config` | Pending |
