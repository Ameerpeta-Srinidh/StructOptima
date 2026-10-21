# Test Execution Guide

**As of:** 2026-10-21 (Ubuntu, Python 3.12 venv, 14 GiB RAM, 4 GiB swap).

## Rules (see also CLAUDE.md → Resource safety)

- Run tests **sequentially**. `pytest -n 8` and `-n 2` were OOM-killed on 2026-10-21 (one worker at 11.8 GiB on a
  DXF fuzz case, N50, fixed). Measured per-file costs are below; parallel workers only after measuring them again.
- Start with the file you changed, then its layer, then everything.
- An interrupted, timed-out or killed run is a failed run.

## The runner: `tests/run_suite.py`

```bash
PYTHONDONTWRITEBYTECODE=1 python tests/run_suite.py --list                 # layers and their files
PYTHONDONTWRITEBYTECODE=1 python tests/run_suite.py tests/test_drift.py    # one or more files
PYTHONDONTWRITEBYTECODE=1 python tests/run_suite.py --layer regression     # a layer
PYTHONDONTWRITEBYTECODE=1 python tests/run_suite.py                        # every test file (≈ 7 min)
PYTHONDONTWRITEBYTECODE=1 python tests/run_suite.py --layer regression -- -k huge   # arguments after -- go to pytest
```

What it does:
- one pytest process per test file, one at a time (`-p no:xdist -p no:cacheprovider`);
- each process under `RLIMIT_AS` (`--as-limit-gib`, default 6), killed above `--max-rss-gib` resident memory
  (default 4) or when the machine has less than `--kill-free-gib` available (default 1); a file is not started below
  `--min-free-gib` available (default 3); `--timeout` seconds per file (default 900);
- exact counts from JUnit XML; skip and xfail reasons listed;
- logs, JUnit XML and `summary.md` (time and peak RSS per file) in `--out` (default: a new temp directory), never in
  the repository;
- files that changed in the repository during the run (content hash of every modified / untracked file before and
  after) are reported — do not edit files while a run is going, or they are reported too;
- exit status 0 only when every file passed and nothing was written; FAIL, ERROR (including "no tests collected"),
  INTERRUPTED (timeout, memory kill, signal) give 1.

Self-checked 2026-10-21: a passing file → exit 0; a failing test → FAIL, exit 1; `--timeout 1` → INTERRUPTED; a
memory limit below the process size → INTERRUPTED (killed); `-k` matching nothing → ERROR; a test modifying an
already-untracked file → reported, exit 1.

### Layers

| Layer | Purpose | Files |
|---|---|---|
| `unit` | fast tests of single modules (includes non-production modules) | see `--list` |
| `geometry` | DXF reading, units, layer roles, grids, placement, geometry validation | |
| `engineering` | IS 456 / 1893 / 13920 / 875 calculations, FEA, dynamic analysis, drift, footings | |
| `integration` | pipeline end to end, realistic buildings, drawings, UI (AppTest) | |
| `regression` | audit findings, damaged / extreme drawings, invariants, metamorphic relations, design matrix | |
| `reference` | independent references: hand checks, closed forms, SP 16 | |

A file can be in several layers. A new test file is reported as *unclassified* until it is added to `LAYERS`.

## Measured cost per file (2026-10-21 final run, sequential, runner)

Full run (after RM-42): 55 files, **1222 passed, 0 failed, 0 errors, 3 skipped, 3 xfailed**, 476 s of test processes.
Peak resident memory per test process: ≤ 367 MB. `STRUCTOPTIMA_CORPUS_N=1000` (random DXF buildings only,
`-- -k random`): 1002 passed in 767 s, 170 MB. Files over 5 s or 200 MB:

| File | Tests | Wall (s) | Peak RSS (MB) |
|---|---|---|---|
| `test_design_matrix.py` | 60 | 286 | 132 |
| `test_dxf_corpus.py` | 138 | 40 | 367 |
| `test_dxf_robustness.py` | 113 | 47 | 279 |
| `test_streamlit_app.py` | 23 | 13 | 250 |
| `test_metamorphic.py` | 13 | 14 | 97 |
| `test_realistic_buildings.py` | 54 | 8 | 94 |
| `test_pipeline_e2e.py` | 15 | 8 | 308 |
| `test_audit_findings.py` | 36 | 4 | 224 |
| `test_drawings.py` | 13 | 5 | 246 |

All other files: ≤ 2.1 s and ≤ 120 MB. `STRUCTOPTIMA_FUZZ_N` (default 12) sets the number of random buildings in
`test_design_matrix.py` (≈ 4 s each) and `STRUCTOPTIMA_CORPUS_N` (default 30) the random DXF buildings in
`test_dxf_corpus.py` (≈ 0.3 s each); the nightly CI job uses 300 of each.

## Plain pytest (one quick file)

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/test_section_design.py -p no:cacheprovider -q
```

`-p no:cacheprovider` avoids `.pytest_cache/`; `PYTHONDONTWRITEBYTECODE` avoids `__pycache__/` (also for ad-hoc
scripts that import `src` or `tests`).

## Ad-hoc diagnostics

Cap memory and time, and measure:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/time -f "%e s %M kB" timeout 300 prlimit --as=3221225472 \
    python my_diagnostic.py
```

Scripts go in a scratch directory outside the repository (or `_local/`).

## CI

`.github/workflows/ci.yml`: job `test` (push / pull request; Python 3.11–3.13; plain pytest with coverage;
45 min timeout) and job `fuzz` (nightly 20:30 UTC and manual; regression layer through the runner with
`STRUCTOPTIMA_FUZZ_N=300`; logs uploaded as the `fuzz-run` artifact). The `fuzz` job was added 2026-10-21 and has
**not been observed running**.

## Side effects of the test suite

| Test group | Writes | Location |
|---|---|---|
| CAD / DXF exporter / IFC / reports / CLI / DXF robustness tests | DXF, IFC, PDF, XLSX | pytest `tmp_path` (system temp) |
| `test_streamlit_app.py` | nothing (asserted: the CWD stays empty) | `tmp_path` (the test changes CWD) |
| `test_pipeline_e2e.py::test_cli_main` | PDF | `tmp_path`; file logging monkeypatched off |
| `test_geometry_validation.py` | DXF | `tmp_path`; one child Python process (1.5 GiB address-space cap) |
| All others | nothing | — |

No test accesses the network. Logging is console-only unless `STRUCTOPTIMA_LOG_FILE` is set.

## Optional dependencies

- `ifcopenshell` — IFC tests are skipped when missing (`pytest.importorskip`).
- `pypdfium2` — test-only (PDF rendering check in `test_drawings.py`).
- No property-based testing library is installed; generated cases use seeded `random` (`tests/design_matrix.py`).

## Scripts that are NOT safe to run casually

The legacy scripts (`src/tests/*.py`, `stress_test_core.py`, `ui_test_runner.py`, `demo_*.py`,
`debug_pipeline.py`, `generate_*.py`) were moved out of the repository on 2026-10-16 (local copies in
`_local/`). They wrote PDFs/DXFs into the folder they ran in and used pre-2026-10 APIs; do not restore them
into the repository.
