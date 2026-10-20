# System Overview

**As of:** 2026-10-15 (post-remediation working tree)

## Purpose

StructOptima produces a preliminary RC frame design for low-rise buildings and
presents it with schedules, quantities and reports. It is a design aid, not a
certified analysis/design program (see [../engineering/limitations.md](../engineering/limitations.md)).

## Runtime components

| Component | Entry | Role |
|---|---|---|
| Streamlit entry point | `app.py` | Top navigation (`st.navigation`), keeps inputs across pages, re-design after a column-editor change, project header with the design status |
| Streamlit pages | `pages/setup.py`, `overview.py`, `checks.py`, `members.py`, `drawings.py`, `reports.py`, `site_tools.py` | Setup collects the inputs and runs the design; the others read `st.session_state` and display status, issues, checks, schedules, drawings, reports and site tools (since 2026-10-20) |
| UI state and tables | `src/ui_state.py`, `src/ui_tables.py`, `src/ui_components.py` | Input defaults and persistence, input fingerprint (out-of-date results), geometry acquisition and the run; schedule / issue rows from the design results; shared header, badges and table styling |
| CLI | `main.py` | Same pipeline for a rectangular grid or a DXF, writes a PDF report, logs status; exit code 1 when the design status is FAIL |
| Design pipeline | `src/design_pipeline.py::run_design` | Single orchestration of loads → analysis → design → checks → quantities (since 2026-10) |
| Libraries | `src/*.py` | Geometry, loads, FEA, section design, detailing, seismic, wind, quantities, reports |

There is no server-side persistence, database or background worker. External
services: optional Sentry error reporting (`src/monitoring.py`, enabled only when
the `SENTRY_DSN` environment variable is set). `src/auth.py` exists but is not
imported anywhere (see [module-catalogue.md](module-catalogue.md)).

## High-level architecture

```mermaid
flowchart LR
  subgraph Inputs
    M[Manual grid<br/>GridManager.generate_grid]
    D[DXF<br/>CADParser → CADLoader<br/>(AutoFramer, ColumnPlacer)]
    I[IFC<br/>BIMLoader]
  end
  subgraph Pipeline["src/design_pipeline.run_design"]
    L[Load intensities<br/>building_types]
    T[Takedown<br/>GridManager.calculate_loads]
    S[Seismic storey forces<br/>seismic.run_seismic_check]
    W[Wind storey forces<br/>wind_load.calculate_wind_load]
    A[2D frame analysis + combinations<br/>analysis_integration → fea_solver]
    B[Beam / column design<br/>rebar_detailer → section_design]
    F[Slabs, stair, footings<br/>rebar_detailer, foundation_eng]
    C[Joint/SCWB, audit, stability,<br/>safety warnings]
    Q[Quantities, BBS, masonry<br/>quantifier, bbs_report, wall_calculator]
  end
  subgraph Outputs
    UI[Streamlit pages]
    PDF[report_gen PDFs]
    XL[exporters Excel]
    DXF[dxf_exporter]
  end
  M --> L
  D --> L
  I --> L
  L --> T --> S --> A
  T --> W --> A
  A --> B -->|sizes changed: iterate| T
  B --> F --> C --> Q --> UI
  Q --> PDF
  Q --> XL
  Q --> DXF
```

## Design status — single source of truth

`run_design` returns `DesignResults.status` (`PASS` / `WARN` / `FAIL`) and
`DesignResults.failures` (list of `{Member, Type, Status, Issue}`), aggregated
from every member result, the audit re-check, frame-analysis failures, SCWB /
joint checks, the seismic-method screen and footing overlaps
(`src/design_pipeline.py`, "status aggregation" block). The project header,
the Overview banner and issue list, the Checks page failure screen, the
schedule status columns (via `ui_tables`) and the PDF report all read this list (this
replaced the screens that always reported success — audit finding R5).

## Key characteristics

- Units: kN, m internally for loads/geometry; mm for section dimensions; see [../engineering/units-and-conventions.md](../engineering/units-and-conventions.md).
- Analysis: linear elastic 2D frames, one per grid line, rigid-diaphragm load sharing by column stiffness.
- Design: IS 456 limit-state section checks; columns by strain-compatibility P-M interaction with biaxial check.
- Iteration: up to `DesignInputs.max_iterations` (default 6) analysis/design passes until beam depths and column sizes stop growing.
- Performance (measured 2026-10-15, Windows, Python 3.13): G+1 18×12 m ≈ 1 s; G+7 12×12 m ≈ 2 s; 84 repository DXFs in 43 s total.
