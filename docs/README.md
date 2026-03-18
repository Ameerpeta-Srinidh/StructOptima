# Structural Design Platform

An automated structural engineering platform for analyzing and designing reinforced concrete buildings per IS 456:2000.

![Platform Overview](https://img.shields.io/badge/Python-3.10+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Tests](https://img.shields.io/badge/Tests-92%20passing-brightgreen.svg)

---

## Features

- **Multi-Input Support**: Manual dimensions, CAD (DXF), or BIM (IFC) import
- **Auto-Framing**: Automatically generate structural frames from architectural layouts
- **IS 456 Compliance**: All calculations follow Indian Standard codes
- **Comprehensive Analysis**:
  - Column sizing and load takedown
  - Beam analysis with deflection checks
  - Foundation design with punching shear
  - Rebar detailing schedules
- **Bill of Materials**: Concrete, steel, excavation quantities with cost estimation
- **Carbon Tracking**: Embodied carbon calculation with fly-ash optimization
- **PDF Reports**: Professional structural design reports
- **DXF Export**: Export structural plans for CAD software
- **3D Visualization**: Interactive Plotly-based structure visualization
- **Risk Management**: Comprehensive Black Box risk checks to prevent common software failures

---

## Quick Start

### Installation

```bash
# Clone or download the project
cd c:\Srinidh\civil

# Install dependencies
pip install -r requirements.txt
```

### Run the Web App

```bash
streamlit run app.py
```

Open your browser to `http://localhost:8501`

### Run the CLI

```bash
# Default 18x12m building
python main.py

# Import from DXF
python main.py --cad sample_design.dxf

# Auto-frame from architectural walls
python main.py --cad sample_arch_only.dxf --auto-frame
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [Installation Guide](installation.md) | Detailed setup instructions |
| [User Guide](user_guide.md) | How to use the platform |
| [API Reference](api_reference.md) | Module and function documentation |
| [Risk Management](risk_management.md) | Black Box risk management checks |

---

## Project Structure

```
civil/
├── app.py                 # Streamlit web application
├── main.py                # CLI entry point
├── requirements.txt       # Python dependencies
├── pytest.ini             # Test configuration
│
├── src/                   # Core modules
│   ├── grid_manager.py    # Grid generation & column management
│   ├── materials.py       # Concrete & Steel materials
│   ├── sections.py        # Section geometry
│   ├── calculations.py    # Load analysis & checks
│   ├── foundation_eng.py  # Footing design
│   ├── rebar_detailer.py  # Reinforcement scheduling
│   ├── quantifier.py      # Bill of Materials
│   ├── report_gen.py      # PDF report generation
│   ├── audit.py           # Independent structural audit
│   ├── risk_management.py # Black Box risk management checks
│   ├── cad_loader.py      # DXF import
│   ├── bim_loader.py      # IFC import
│   ├── dxf_exporter.py    # DXF export
│   ├── visualizer.py      # 3D visualization
│   ├── logging_config.py  # Centralized logging
│   ├── auth.py            # User authentication
│   └── monitoring.py      # Error monitoring (Sentry)
│
├── tests/                 # Unit tests
│   ├── conftest.py        # Shared fixtures
│   ├── test_materials.py
│   ├── test_sections.py
│   ├── test_calculations.py
│   ├── test_foundation_eng.py
│   ├── test_grid_manager.py
│   ├── test_audit.py
│   └── test_risk_management.py
│
└── docs/                  # Documentation
    ├── README.md
    ├── installation.md
    ├── user_guide.md
    └── api_reference.md
```

---

## Requirements

- Python 3.10 or higher
- Windows, macOS, or Linux

### Key Dependencies

| Package | Purpose |
|---------|---------|
| streamlit | Web interface |
| pydantic | Data validation |
| numpy | Numerical calculations |
| ezdxf | DXF file handling |
| reportlab | PDF generation |
| plotly | 3D visualization |
| pytest | Testing framework |
| sentry-sdk | Error monitoring |

---

## Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=html
```

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LOG_LEVEL` | Logging verbosity | `INFO` |
| `SENTRY_DSN` | Sentry error tracking DSN | (disabled) |
| `STRUCT_APP_USERNAME` | Auth username | `admin` |
| `STRUCT_APP_PASSWORD_HASH` | Auth password hash | (see auth.py) |

---

## License

This project is for educational and professional use. 

---

## Support

For issues or feature requests, please contact the development team.
