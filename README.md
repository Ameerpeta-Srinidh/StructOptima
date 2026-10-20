<p align="center">
  <h1 align="center">🏗️ StructOptima</h1>
  <p align="center"><strong>Preliminary design aid for reinforced-concrete frame buildings</strong></p>
  <p align="center">References IS 456:2000 · IS 1893 (Part 1):2016 · IS 875 · IS 13920:2016 — not a certified code-compliance tool</p>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License"></a>
  <img src="https://img.shields.io/badge/Python-3.11%E2%80%933.13-3776AB.svg?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Streamlit-App-FF4B4B.svg?logo=streamlit&logoColor=white" alt="Streamlit">
</p>

> ⚠️ **Engineering safety notice.** StructOptima produces **preliminary** designs.
> Many calculations have not been independently verified, tabulated code values
> were transcribed and still need checking against the printed standards, and
> several analysis effects (torsion, P-Δ, response spectrum, IS 13920 ductile
> detailing) are not implemented. **Every output must be independently verified by
> a licensed structural engineer before any use in construction.** See
> [docs/engineering/limitations.md](docs/engineering/limitations.md).

---

## What it is

StructOptima takes a building layout (manual dimensions, a DXF plan or an IFC
model), generates or reads a column/beam grid, and runs a single design
pipeline (`src/design_pipeline.py`):

```
geometry → occupancy loads → load takedown → seismic + wind storey forces
→ 2D frame analysis (DL, LL, EQ, WL; IS 456 / IS 1893 combinations)
→ beam & column design (iterated until sizes stop changing)
→ slabs, staircase, isolated footings → joint / SCWB checks, audit, stability
→ quantities, BBS, masonry → design status (PASS / WARN / FAIL) + list of issues
```

Results are shown in a Streamlit web app (`app.py` + 7 pages: Setup, Overview, Checks, Members,
Drawings & 3D, Reports, Site tools) or produced by
the CLI (`main.py`), with PDF reports, Excel and DXF exports.

## Implemented features (status as of 2026-10-15)

| Feature | Notes |
|---|---|
| Manual grid, DXF import (explicit columns or auto-framing from walls), IFC import | DXF units from `$INSUNITS` with plausibility check; IFC needs `ifcopenshell` (optional) |
| Load takedown with dead / live split, walls, beam self-weight, roof loads | Occupancy loads from `src/building_types.py` |
| 2D plane-frame analysis (direct stiffness), gravity + seismic + wind load cases | Benchmarked against closed-form cases; no torsion |
| Equivalent static seismic analysis | Height, weight, soil type, importance factor, R (OMRF default) |
| Static wind loads (IS 875 Part 3) | Simplified Cpe, power-law k2 |
| Beam design (sagging, hogging, shear, compression steel) | Rectangular sections |
| Column design (P-M interaction by strain compatibility, biaxial, minimum eccentricity, slenderness) | Effective length factor 1.0 by default (engineering decision pending) |
| Two-way / one-way slabs (IS 456 Table 26 coefficients by edge condition) | Coefficient values need verification |
| Staircase flight, isolated square footings with reinforcement | Footing sizing ignores base moments (warning) |
| SCWB, joint shear, ductile tie spacing from designed members | Advisory; IS 13920 confinement not designed |
| Design status and issue list shown in UI and PDF | PDFs marked "PRELIMINARY — NOT FOR CONSTRUCTION" |
| Site drawing set (A3): column, footing, beam & slab layouts, sections, slab reinforcement, footing sections with schedules | PDF, DXF, SVG, ZIP from the Drawings page; laps/curtailment are typical notes |
| BIM model export (IFC4) with design data on every member | Opens in any IFC viewer; founding level not designed |
| 3D viewer and walk-through of the designed building (orbit, storeys, section cut, status colours, click for member data; works with touch) | Boxes only; no openings or reinforcement |
| Storey drift check (EQ 0.004 h, wind top sway H/500) | Limit values UNVERIFIED; 2D frames, no torsion |
| Site tools: BBS cutting plan, approved-mix materials, cube register, formwork, QR member tags, inspection and defect log, measured vibration / strain, as-built survey | Arithmetic on the design and on your data; nothing simulated |
| Quantities, cost, carbon, BBS, masonry/plaster/paint estimates | Estimates with fixed rates |
| Indicative column optimiser | Requires re-analysis before use |

Known limitations and open defects: [docs/engineering/limitations.md](docs/engineering/limitations.md),
[docs/assurance/known-defects.md](docs/assurance/known-defects.md).

---

## Quick start

### Prerequisites

- Python 3.11, 3.12 or 3.13 (as in CI)
- pip

### Installation

```bash
git clone https://github.com/SrinidhAmeerpta/StructOptima.git
cd StructOptima
pip install -r requirements.txt   # includes ifcopenshell for IFC import/export
```

### Run the web application

```bash
streamlit run app.py
```

Open `http://localhost:8501`. On the **Setup** page enter the inputs and the SBC, confirm the site parameters,
accept the verification statement and press **Run design** (user guide: [docs/user-guide.md](docs/user-guide.md)).

### Run from the command line

```bash
python main.py --help
python main.py --width 18 --length 12 --stories 2 --zone III --report report.pdf
python main.py --cad samples/sample_design.dxf --stories 3 --report cad_report.pdf
python main.py --cad my_walls.dxf --auto-frame --occupancy "Commercial (Office)" --soil III
```

The CLI exits with code 1 when the design status is FAIL and writes
`structural_design.log` in the current directory.

---

## Usage

### Input methods

| Method | Description |
|---|---|
| Manual Dimensions | Width, length, storeys; optional cantilever balconies |
| Import CAD (DXF) | Columns as closed LWPOLYLINEs on `COLUMNS`/`COL*` layers, beams as LINEs on `BEAM*` layers, walls on `WALL*` layers (used for auto-framing and wall loads) |
| Import BIM (IFC) | IfcColumn / IfcBeam with extruded rectangular profiles; storeys and heights from the model |

### DXF layer convention

| Layer | Entity type | Purpose |
|---|---|---|
| `COLUMNS` | LWPOLYLINE (closed) | Column outlines |
| `BEAMS` | LINE | Beam centre lines |
| `WALLS` | LINE / LWPOLYLINE | Architectural walls (auto-frame, wall loads) |

Set the drawing units (`$INSUNITS`) correctly; drawings without units are scaled
by a size heuristic and a warning is shown.

### Example: creating a DXF

```python
import ezdxf

doc = ezdxf.new()
doc.header["$INSUNITS"] = 4           # millimetres
msp = doc.modelspace()
doc.layers.new(name="COLUMNS", dxfattribs={"color": 1})

# 300 x 300 mm column at (4000, 5000) mm
msp.add_lwpolyline([(3850, 4850), (4150, 4850), (4150, 5150), (3850, 5150)],
                   close=True, dxfattribs={"layer": "COLUMNS"})
doc.saveas("my_design.dxf")
```

---

## Repository structure

```
app.py                Streamlit entry point (navigation, input persistence, project header)
main.py               CLI
pages/                Setup, Overview, Checks, Members, Drawings & 3D, Reports, Site tools
src/design_pipeline.py   End-to-end design orchestration (single source of design status)
src/                  Engineering, ingest, output and UI modules (see docs/architecture/module-catalogue.md)
tests/                pytest suite (unit, benchmark, end-to-end, headless UI)
docs/                 Documentation (start at docs/README.md)
components/viewer3d/  3D viewer (source + committed bundle)
samples/              Example and test DXF files (see samples/README.md)
docs/legacy/          Historical documents (not current)
```

Full inventory, including legacy scripts and generated artefacts:
[docs/architecture/repository-inventory.md](docs/architecture/repository-inventory.md).

---

## Testing

```bash
# side-effect-free run (no cache / bytecode files in the repository)
PYTHONDONTWRITEBYTECODE=1 python -m pytest tests -p no:cacheprovider -q

# with coverage (as in CI)
python -m pytest tests --cov=src --cov-report=term-missing
```

Last recorded run (2026-10-16, Python 3.13.7): **520 passed, 3 skipped, 0 failed**.
Passing tests show the code behaves as tested; they are not proof of
engineering correctness. Evidence per calculation:
[docs/verification/verification-matrix.md](docs/verification/verification-matrix.md).

---

## Documentation

Start at **[docs/README.md](docs/README.md)** (index, reading order, coverage matrix).

- How to use the app on site: **[docs/user-guide.md](docs/user-guide.md)**
- Every change and why: **[CHANGELOG.md](CHANGELOG.md)**

| Area | Documents |
|---|---|
| Architecture | [system overview](docs/architecture/system-overview.md), [execution flows](docs/architecture/execution-flows.md), [module catalogue](docs/architecture/module-catalogue.md), [interfaces](docs/architecture/interfaces-and-contracts.md) |
| Engineering | [calculation catalogue](docs/engineering/calculation-catalogue.md), [units](docs/engineering/units-and-conventions.md), [assumptions](docs/engineering/assumptions-register.md), [standards](docs/engineering/standards-register.md), [limitations](docs/engineering/limitations.md) |
| Verification | [test inventory](docs/verification/test-inventory.md), [verification matrix](docs/verification/verification-matrix.md), [results](docs/verification/verification-results.md) |
| Assurance | [risk register](docs/assurance/risk-register.md), [known defects](docs/assurance/known-defects.md), [decision log](docs/assurance/decision-log.md), [remediation log](docs/assurance/remediation-log.md) |
| Development | [setup](docs/development/setup.md), [workflow](docs/development/developer-workflow.md), [troubleshooting](docs/development/troubleshooting.md), [release checklist](docs/development/release-checklist.md) |

---

## Environment variables

| Variable | Description | Default |
|---|---|---|
| `LOG_LEVEL` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO` |
| `STRUCTOPTIMA_LOG_FILE` | Enable file logging for library code at this path | *(console only)* |
| `SENTRY_DSN` | Sentry error tracking | *(disabled)* |

(`src/auth.py` reads `STRUCT_APP_USERNAME` / `STRUCT_APP_PASSWORD_HASH` but is not used by the application.)

---

## Contributing

Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) and
[docs/development/developer-workflow.md](docs/development/developer-workflow.md).

## License

MIT — see [LICENSE](LICENSE).

## Authors

Srinidh Ameerpeta & Charan Tej

## Disclaimer

> This software is intended for education and **preliminary** design only. It
> is not a certified structural analysis or design program and does not certify
> compliance with any standard. All designs must be independently verified by a
> licensed structural engineer before use in construction. The authors assume no
> liability for designs produced with this software.
