# Sample input files

Input drawings used by the tests and for trying the app (Import CAD (DXF)). All are in millimetres unless
the file's `$INSUNITS` says otherwise. Many of these files declare a wrong `$INSUNITS`; see KD-06 in
`docs/assurance/known-defects.md`.

| Path | Contents | Used by |
|---|---|---|
| `sample_design.dxf` | Small framed plan (columns, beams) | `tests/test_drawings.py`, `tests/test_pipeline_e2e.py`, `main.py --cad` example |
| `sample_arch_only.dxf` | Architectural plan without structure (auto-framing) | manual trials |
| `plans/` | House / villa / mansion plans (`complex_villa.dxf`, `complex_house.dxf`, `real_house_plan.dxf`, …) | `tests/test_cad_parser.py`, `tests/test_beam_placer.py` |
| `real_world/` | Five realistic residential plans | `tests/test_pipeline_e2e.py` (first three) |
| `test_cases/` | Generated test plans: `case_01…` shapes, `builder_pitch/`, `stress/`, `new_complex/`, `ui_test/`, `validation/`, `real_world/` | `tests/test_cad_parser.py` (cases 01, 04, 10); the rest for manual sweeps |
