<p align="center">
  <h1 align="center">🏗️ StructOptima</h1>
  <p align="center"><strong>Automated Structural Design Engine for Reinforced Concrete Buildings</strong></p>
  <p align="center">IS 456:2000 · IS 1893:2016 · IS 13920:2016 · IS 875</p>
</p>

<p align="center">
  <a href="#features"><img src="https://img.shields.io/badge/Modules-51-blue.svg" alt="Modules"></a>
  <a href="#testing"><img src="https://img.shields.io/badge/Tests-28%20suites-brightgreen.svg" alt="Tests"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License"></a>
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB.svg?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Streamlit-App-FF4B4B.svg?logo=streamlit&logoColor=white" alt="Streamlit">
</p>

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Indian Standard Code Compliance](#indian-standard-code-compliance)
- [Testing](#testing)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)
- [Author](#author)

---

## Overview

**StructOptima** is a full-stack automated structural design platform that takes a building's architectural layout (from manual input, DXF, or IFC files) and produces a complete structural design package — including column placement, beam design, foundation engineering, rebar detailing, cost estimation, and professional PDF reports.

The engine follows Indian Standard codes (IS 456, IS 1893, IS 13920, IS 875) for all calculations, making it directly applicable to real-world Indian construction projects.

### What It Does

```
Architectural Input (DXF/IFC/Manual)
        │
        ▼
┌─────────────────────────────────────┐
│         StructOptima Engine         │
│                                     │
│  ① Auto-Frame Detection            │
│  ② IS-Code Column Placement        │
│  ③ Beam Generation & Design        │
│  ④ Load Analysis (FEA)             │
│  ⑤ Foundation Design               │
│  ⑥ Rebar Detailing (BBS)           │
│  ⑦ Seismic & Stability Checks      │
│  ⑧ Cost Optimization               │
│  ⑨ Bill of Materials               │
│  ⑩ Risk Management & Audit         │
└─────────────────────────────────────┘
        │
        ▼
  PDF Reports · DXF Plans · Excel Exports
  3D Visualization · BBS Schedules
```

---

## Features

### 🏛️ Structural Analysis
- **Auto-Framing**: Automatically detects structural nodes from architectural walls and places IS-code compliant columns
- **Column Placement Engine**: Junction-aware placement (corner, T-junction, cross, edge) with IS 13920 seismic detailing
- **Column Editor**: Interactive add/remove columns with real-time structural integrity validation
- **Beam Design**: Automatic beam generation with deflection and shear checks
- **Slab Design**: One-way and two-way slab classification with IS 456 reinforcement
- **Staircase Design**: Waist slab design with void zone handling

### 🔬 Advanced Analysis
- **Finite Element Analysis**: 2D frame solver with stiffness method
- **Seismic Analysis**: Full IS 1893:2016 compliance — base shear, drift checks, strong column-weak beam
- **Wind Load Analysis**: IS 875 Part 3 compliant wind pressure calculations
- **Load Combinations**: IS 456 & IS 1893 factored load combinations (1.5DL+1.5LL, 1.2DL+1.2LL+1.2EQ, etc.)
- **Stability Checks**: Slenderness ratio and fire resistance per IS 456 Table 16A

### 📐 Detailing & Scheduling
- **Rebar Detailing**: Automatic reinforcement with development length per IS 456 Cl. 26.2
- **Bar Bending Schedule (BBS)**: Complete BBS with cutting lengths, bend deductions, hook allowances
- **Anchorage Calculations**: Development length tables for all bar sizes
- **Member Design**: Beam and column design with capacity checks

### 💰 Estimation & Optimization
- **Bill of Materials**: Concrete (cement/sand/aggregate/water), steel, formwork quantities
- **Cost Estimation**: INR-based costing for concrete, steel, excavation, finishing
- **Cost Optimizer**: Floor-wise column optimization maintaining IS 456 safety factors
- **Carbon Footprint**: Embodied CO₂ calculation with fly-ash/slag reduction option
- **Quantity Takeoff**: IS 1200 compliant measurement with shuttering areas

### 📊 Visualization & Reporting
- **3D Interactive Visualization**: Plotly-based with Engineering, Architectural, Deflection, Utilization, and Load Path views
- **PDF Reports**: Professional structural design reports with schedules and calculations
- **DXF Export**: Floor-wise structural plans for AutoCAD
- **Excel Export**: Complete data export via openpyxl
- **BIM Interop**: COBie data export for facility management

### 🛡️ Quality Assurance
- **Independent Structural Audit**: Automated IS 456 compliance verification
- **Black Box Risk Management**: 13+ risk checks including equilibrium, capacity, and drift
- **Safety Warnings Module**: Proactive warnings for unusual design conditions
- **Structural Validators**: Input validation with engineering limits

### 📥 Input Flexibility
- **Manual Entry**: Parametric building dimensions with cantilever options
- **CAD Import (DXF)**: Reads COLUMNS, BEAMS, WALLS layers from DXF files
- **BIM Import (IFC)**: Reads IfcColumn, IfcBeam elements with material properties
- **Sample DXF Generators**: Scripts to generate test DXF files for development

### 🏗️ Construction Support
- **Site Inspection Checklists**: Stage-wise inspection items per IS 456
- **Structural Health Monitoring (SHM)**: Sensor placement planning
- **Site Guide**: Construction sequence and methodology notes

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Presentation Layer                  │
│  app.py (Streamlit)  │  main.py (CLI)                │
└──────────────┬──────────────────────┬────────────────┘
               │                      │
┌──────────────▼──────────────────────▼────────────────┐
│                    Core Engine                        │
│                                                       │
│  grid_manager.py    ─── Column grid & load takedown   │
│  column_placer.py   ─── IS-code column placement      │
│  auto_framer.py     ─── Wall→Structure detection      │
│  beam_placer.py     ─── Beam generation & sizing      │
│  fea_solver.py      ─── Stiffness method FEA          │
│  slab_generator.py  ─── Slab panel detection          │
│  foundation_eng.py  ─── Isolated footing design       │
│  rebar_detailer.py  ─── Reinforcement scheduling      │
│  optimizer.py       ─── Cost optimization             │
└──────────────┬───────────────────────────────────────┘
               │
┌──────────────▼───────────────────────────────────────┐
│                   Analysis Layer                      │
│                                                       │
│  analysis_integration.py ─── FEA orchestration        │
│  seismic.py              ─── IS 1893 seismic          │
│  wind_load.py            ─── IS 875 wind loads        │
│  load_combinations.py    ─── Factored combinations    │
│  stability.py            ─── Slenderness & fire       │
│  structural_checks.py    ─── Design verification      │
│  calculations.py         ─── Core IS 456 formulas     │
└──────────────┬───────────────────────────────────────┘
               │
┌──────────────▼───────────────────────────────────────┐
│                   Output Layer                        │
│                                                       │
│  report_gen.py     ─── PDF report generation          │
│  dxf_exporter.py   ─── DXF plan export                │
│  visualizer.py     ─── 3D Plotly visualization        │
│  exporters.py      ─── Excel export                   │
│  bbs_module.py     ─── Bar bending schedule           │
│  quantifier.py     ─── Bill of materials              │
│  quantity_takeoff.py ── IS 1200 measurement           │
│  bim_interop.py    ─── COBie export                   │
└──────────────────────────────────────────────────────┘
```

---

## Quick Start

### Prerequisites

- Python 3.10 or higher
- pip package manager

### Installation

```bash
# Clone the repository
git clone https://github.com/SrinidhAmeerpta/StructOptima.git
cd StructOptima

# Install dependencies
pip install -r requirements.txt
```

### Run the Web Application

```bash
streamlit run app.py
```

Open your browser to `http://localhost:8501`.

### Run from Command Line

```bash
# Default 18×12m building analysis
python main.py

# Import from DXF (pre-placed columns)
python main.py --cad preplaced_columns.dxf

# Auto-frame from architectural walls
python main.py --cad complex_villa.dxf --auto-frame
```

---

## Usage

### Web Interface (Streamlit)

The Streamlit app provides a complete GUI with:

1. **Sidebar**: Input method selection, building parameters, loading, seismic zone, materials
2. **Column Editor**: Add/remove columns with IS 456 validation (for auto-framed projects)
3. **Results Dashboard**: Metrics, 3D visualization, schedules, reports
4. **Export Options**: PDF, DXF, Excel downloads

### Input Methods

| Method | Description | Best For |
|--------|-------------|----------|
| Manual Dimensions | Enter width, length, stories | Simple regular buildings |
| Import CAD (DXF) | Upload AutoCAD DXF file | Projects with existing drawings |
| Import BIM (IFC) | Upload IFC model | BIM-integrated workflows |

### DXF Layer Convention

| Layer | Entity Type | Purpose |
|-------|-------------|---------|
| `COLUMNS` | LWPOLYLINE | Column outlines (closed rectangles) |
| `BEAMS` | LINE | Beam centerlines |
| `WALLS` | LINE / LWPOLYLINE | Architectural walls (for auto-frame) |
| `FOOTINGS` | LWPOLYLINE | Footing outlines (optional) |

### Example: Creating a Custom DXF

```python
import ezdxf

doc = ezdxf.new()
msp = doc.modelspace()
doc.layers.new(name='COLUMNS', dxfattribs={'color': 1})

# Add a 300×300mm column at position (4000, 5000)mm
msp.add_lwpolyline(
    [(3850, 4850), (4150, 4850), (4150, 5150), (3850, 5150), (3850, 4850)],
    dxfattribs={'layer': 'COLUMNS'}
)

doc.saveas("my_design.dxf")
```

---

## Project Structure

```
StructOptima/
├── app.py                          # Streamlit web application (1581 lines)
├── main.py                         # CLI entry point
├── requirements.txt                # Python dependencies
├── pytest.ini                      # Test configuration
├── LICENSE                         # MIT License
├── README.md                       # This file
├── CONTRIBUTING.md                 # Contribution guidelines
├── CODE_OF_CONDUCT.md              # Community standards
│
├── src/                            # Core engine (51 modules)
│   ├── grid_manager.py             # Grid generation, column management, load takedown
│   ├── column_placer.py            # IS 456/13920 automated column placement
│   ├── column_editor.py            # Interactive column add/remove with validation
│   ├── auto_framer.py              # Wall intersection → structural node detection
│   ├── beam_placer.py              # Beam generation and sizing
│   ├── slab_generator.py           # Slab panel detection and design
│   ├── fea_solver.py               # 2D frame stiffness method solver
│   ├── analysis_integration.py     # FEA orchestration for full structure
│   ├── analysis_config.py          # Analysis parameters and configuration
│   ├── seismic.py                  # IS 1893:2016 seismic analysis
│   ├── wind_load.py                # IS 875 Part 3 wind load analysis
│   ├── load_combinations.py        # IS 456 & IS 1893 load combinations
│   ├── stability.py                # Slenderness & fire resistance checks
│   ├── structural_checks.py        # Design verification routines
│   ├── calculations.py             # Core IS 456 engineering formulas
│   ├── materials.py                # Concrete & steel material models
│   ├── sections.py                 # Cross-section geometry properties
│   ├── foundation_eng.py           # Isolated footing design
│   ├── rebar_detailer.py           # Reinforcement detailing engine
│   ├── member_design.py            # Beam & column member design
│   ├── anchorage.py                # Development length (IS 456 Cl. 26.2)
│   ├── bbs_module.py               # Bar bending schedule generation
│   ├── bbs_report.py               # BBS PDF report generation
│   ├── bbs_utils.py                # BBS utilities & bend deductions
│   ├── optimizer.py                # Cost optimization engine
│   ├── quantifier.py               # Bill of materials & costing
│   ├── quantity_takeoff.py         # IS 1200 quantity measurement
│   ├── building_types.py           # IS 875 Part 2 occupancy loads
│   ├── framing_logic.py            # Structural member data models
│   ├── cad_parser.py               # DXF file parser
│   ├── cad_loader.py               # DXF → GridManager loader
│   ├── bim_loader.py               # IFC → GridManager loader
│   ├── bim_interop.py              # COBie export
│   ├── dxf_exporter.py             # DXF plan export
│   ├── exporters.py                # Excel export
│   ├── report_gen.py               # PDF report generation
│   ├── visualizer.py               # 3D Plotly visualization
│   ├── audit.py                    # Independent structural audit
│   ├── risk_management.py          # Black box risk management (13+ checks)
│   ├── safety_warnings.py          # Proactive safety warnings
│   ├── validators.py               # Input validation
│   ├── site_inspection.py          # Construction inspection checklists
│   ├── site_guide.py               # Construction methodology
│   ├── shm_module.py               # Structural health monitoring planner
│   ├── shm_viz.py                  # SHM visualization
│   ├── digital_twin.py             # Digital twin foundation
│   ├── documentation.py            # Design report generation
│   ├── auth.py                     # User authentication
│   ├── monitoring.py               # Sentry error monitoring
│   ├── logging_config.py           # Centralized logging
│   ├── schema.py                   # Data schemas
│   └── __pycache__/
│
├── tests/                          # Test suite (28 test files)
│   ├── conftest.py                 # Shared pytest fixtures
│   ├── test_grid_manager.py
│   ├── test_column_placer.py
│   ├── test_column_editor.py
│   ├── test_beam_placer.py
│   ├── test_calculations.py
│   ├── test_materials.py
│   ├── test_sections.py
│   ├── test_foundation_eng.py
│   ├── test_member_design.py
│   ├── test_load_modeling.py
│   ├── test_slab_generator.py
│   ├── test_bbs_module.py
│   ├── test_quantity_takeoff.py
│   ├── test_estimation_refinements.py
│   ├── test_audit.py
│   ├── test_risk_management.py
│   ├── test_risk_safeguards.py
│   ├── test_validators.py
│   ├── test_analysis_config.py
│   ├── test_new_modules.py
│   ├── test_viz_integration.py
│   └── ...
│
├── docs/                           # Documentation
│   ├── README.md                   # Docs overview
│   ├── installation.md             # Setup instructions
│   ├── user_guide.md               # End-user guide
│   ├── api_reference.md            # Module API docs
│   └── risk_management.md          # Risk management docs
│
├── test_dxfs/                      # Test DXF case files (15 cases)
├── real_world_dxfs/                # Real-world style DXF samples (5 files)
│
├── generate_sample_dxf.py          # Sample DXF generators
├── generate_complex_villa.py
├── generate_realistic_house.py
├── generate_preplaced_columns_dxf.py
│
├── demo_full_pipeline.py           # Full pipeline demonstration
├── demo_member_design.py           # Member design demo
├── demo_quantity_takeoff.py        # Quantity takeoff demo
├── demo_bim_site_shm.py           # BIM/SHM demo
└── analyze_villa.py                # Villa analysis with HTML visualization
```

---

## Indian Standard Code Compliance

| Code | Coverage |
|------|----------|
| **IS 456:2000** | Column design (Cl. 39.3), beam design, slab design, development length (Cl. 26.2), deflection limits (Span/250), fire resistance (Table 16A), minimum steel ratios |
| **IS 1893:2016** | Zone factors (II-V), design acceleration coefficients, base shear calculation, story drift limits, strong column-weak beam check |
| **IS 13920:2016** | Special confining reinforcement, seismic detailing for ductile frames, minimum column dimensions (300mm in Zone III+) |
| **IS 875 Part 1** | Dead load — self-weight of materials, floor finishes |
| **IS 875 Part 2** | Live load — occupancy-based floor loads (residential, office, commercial, etc.) |
| **IS 875 Part 3** | Wind load — basic wind speed, terrain factors, pressure coefficients |
| **IS 1200** | Quantity measurement — concrete work, formwork area, excavation volumes |

### Safety Factors Used

| Factor | Value | Reference |
|--------|-------|-----------|
| Concrete (γc) | 1.5 | IS 456 Cl. 36.4.2 |
| Steel (γs) | 1.15 | IS 456 Cl. 36.4.2 |
| Dead Load factor | 1.5 | IS 456 Table 18 |
| Live Load factor | 1.5 | IS 456 Table 18 |

---

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test
python -m pytest tests/test_column_placer.py -v

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=html
```

The test suite includes:
- Unit tests for all core calculations
- Integration tests for the full pipeline
- Validation tests for IS code compliance
- Edge case tests for unusual geometries

---

## Documentation

| Document | Description |
|----------|-------------|
| [Installation Guide](docs/installation.md) | Detailed setup instructions |
| [User Guide](docs/user_guide.md) | How to use the platform |
| [API Reference](docs/api_reference.md) | Module and function documentation |
| [Risk Management](docs/risk_management.md) | Black Box risk management system |

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LOG_LEVEL` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`) | `INFO` |
| `SENTRY_DSN` | Sentry error tracking DSN | *(disabled)* |
| `STRUCT_APP_USERNAME` | Application auth username | `admin` |
| `STRUCT_APP_PASSWORD_HASH` | Application auth password hash | *(see auth.py)* |

---

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## Author

**Srinidh Ameerpta**

---

## Disclaimer

> ⚠️ **This software is intended for educational and preliminary design purposes.** All structural designs produced by this software must be independently verified by a licensed structural engineer before use in construction. The author assumes no liability for designs produced by this software.
