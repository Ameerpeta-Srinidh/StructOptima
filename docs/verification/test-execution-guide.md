# Test Execution Guide

**As of:** 2026-10-15.

## Recommended command (no side effects in the repository)

Git Bash / Linux / macOS:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest tests -p no:cacheprovider -q -o addopts=""
```

PowerShell:

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"; python -m pytest tests -p no:cacheprovider -q -o addopts=""
```

- `-p no:cacheprovider` avoids `.pytest_cache/`; `PYTHONDONTWRITEBYTECODE` avoids `__pycache__/`.
- `-o addopts=""` overrides the verbose default in `pytest.ini` (optional).
- Runtime ≈ 20–35 s on the development machine (2026-10-15).

Plain `pytest` (as in CI) also works; it creates the cache directories.

## Side effects of the test suite (assessed 2026-10-15)

| Test group | Writes | Location |
|---|---|---|
| CAD / DXF exporter / IFC / reports / CLI tests | DXF, IFC, PDF, XLSX | pytest `tmp_path` (system temp) |
| `test_streamlit_app.py` | DXF exports from the Drawings page | `tmp_path` (the test changes CWD) |
| `test_pipeline_e2e.py::test_cli_main` | PDF | `tmp_path`; file logging monkeypatched off |
| All others | nothing | — |

No test accesses the network. Logging is console-only unless
`STRUCTOPTIMA_LOG_FILE` is set.

## Optional dependencies

- `ifcopenshell` — IFC tests are skipped when missing (`pytest.importorskip`).
- `streamlit` — required (listed in requirements); UI tests use `streamlit.testing.v1.AppTest`.

## Useful subsets

```bash
python -m pytest tests/test_fea_benchmarks.py tests/test_section_design.py   # numerical benchmarks
python -m pytest tests/test_audit_findings.py -k R7                          # one finding
python -m pytest tests/test_pipeline_e2e.py tests/test_streamlit_app.py      # end-to-end + UI
python -m pytest tests --cov=src --cov-report=term-missing                    # coverage (needs pytest-cov)
```

## Scripts that are NOT safe to run casually

`src/tests/*.py`, `stress_test_core.py`, `ui_test_runner.py`, `demo_*.py`,
`debug_pipeline.py`, `generate_*.py`: write PDFs/DXFs into the repository,
some batch-process many files, and several use pre-2026-10 APIs.

## DXF sweep (manual, read-only)

The 2026-10-15 sweep of all 84 repository DXFs through the pipeline was run
from a scratch directory with an ad-hoc script (not part of the repository);
results are summarised in [verification-results.md](verification-results.md).
