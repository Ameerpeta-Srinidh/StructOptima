# Installation Guide

This guide walks you through setting up the Structural Design Platform on your system.

---

## Prerequisites

### System Requirements

- **Operating System**: Windows 10/11, macOS 10.15+, or Linux (Ubuntu 20.04+)
- **Python**: 3.10 or higher
- **RAM**: 4 GB minimum, 8 GB recommended
- **Disk Space**: 500 MB for installation

### Verify Python Installation

```bash
python --version
# Should show Python 3.10.x or higher
```

If Python is not installed, download it from [python.org](https://www.python.org/downloads/).

---

## Installation Steps

### 1. Navigate to Project Directory

```bash
cd c:\Srinidh\civil
```

### 2. Create Virtual Environment (Recommended)

```bash
# Create virtual environment
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate

# macOS/Linux:
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

This installs all required packages:

| Package | Version | Purpose |
|---------|---------|---------|
| pydantic | ≥2.0.0 | Data validation models |
| numpy | ≥1.20.0 | Numerical calculations |
| pytest | ≥7.0.0 | Testing framework |
| reportlab | ≥4.0.0 | PDF report generation |
| streamlit | ≥1.30.0 | Web interface |
| plotly | ≥5.18.0 | 3D visualization |
| ezdxf | ≥1.1.0 | DXF file handling |
| pandas | ≥2.0.0 | Data manipulation |
| openpyxl | ≥3.1.0 | Excel file support |
| sentry-sdk | ≥1.35.0 | Error monitoring |

### 4. Verify Installation

```bash
# Run tests to verify everything works
python -m pytest tests/ -v
```

You should see:
```
============================= 92 passed in 0.28s ==============================
```

---

## Optional: BIM Support (IFC Files)

To enable IFC file import, install IfcOpenShell:

```bash
pip install ifcopenshell
```

> **Note**: IfcOpenShell may require additional system dependencies on some platforms.

---

## Running the Application

### Web Interface (Streamlit)

```bash
streamlit run app.py
```

This opens a browser window at `http://localhost:8501`.

### Command Line Interface

```bash
# Run with default parameters
python main.py

# Run with a DXF file
python main.py --cad sample_design.dxf

# Run with auto-framing from architectural layout
python main.py --cad sample_arch_only.dxf --auto-frame
```

---

## Configuration

### Environment Variables

Set these before running for production:

#### Windows (PowerShell)

```powershell
# Set log level
$env:LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR

# Enable Sentry error tracking (optional)
$env:SENTRY_DSN = "https://your-dsn@sentry.io/project-id"

# Custom authentication (optional)
$env:STRUCT_APP_USERNAME = "your_username"
$env:STRUCT_APP_PASSWORD_HASH = "<hash>"
```

#### Linux/macOS

```bash
export LOG_LEVEL="INFO"
export SENTRY_DSN="https://your-dsn@sentry.io/project-id"
export STRUCT_APP_USERNAME="your_username"
export STRUCT_APP_PASSWORD_HASH="<hash>"
```

### Generating Password Hash

```bash
python -c "from src.auth import generate_password_hash; print(generate_password_hash('your_password'))"
```

---

## Troubleshooting

### Common Issues

#### "Module not found" errors

Ensure your virtual environment is activated:
```bash
# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

#### DXF files not loading

Verify ezdxf is installed:
```bash
pip show ezdxf
```

#### Streamlit won't start

Check if port 8501 is available:
```bash
streamlit run app.py --server.port 8502
```

#### Tests failing

Ensure you're in the correct directory:
```bash
cd c:\Srinidh\civil
python -m pytest tests/ -v
```

---

## Updating

To update to the latest version:

```bash
# Pull latest code (if using git)
git pull

# Update dependencies
pip install -r requirements.txt --upgrade
```

---

## Uninstalling

```bash
# Deactivate virtual environment
deactivate

# Remove virtual environment folder
# Windows:
rmdir /s venv

# macOS/Linux:
rm -rf venv
```

---

## Next Steps

- Read the [User Guide](user_guide.md) to learn how to use the platform
- Check the [API Reference](api_reference.md) for programmatic usage
