# API Reference

This document provides detailed documentation for the core modules and classes in the Structural Design Platform.

---

## Table of Contents

- [Materials](#materials)
- [Sections](#sections)
- [Grid Manager](#grid-manager)
- [Calculations](#calculations)
- [Foundation Engineering](#foundation-engineering)
- [Audit](#audit)
- [CAD/BIM Loaders](#cadbim-loaders)
- [Utilities](#utilities)

---

## Materials

### `src/materials.py`

#### `Concrete`

Represents concrete material properties per IS 456:2000.

```python
from src.materials import Concrete

# Create from grade string
concrete = Concrete.from_grade("M25")
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `grade` | str | Grade name (e.g., "M25") |
| `fck` | float | Characteristic strength (MPa) |
| `modulus_of_elasticity` | float | E = 5000√fck (MPa) |
| `density` | float | 25 kN/m³ |
| `poissons_ratio` | float | 0.2 |
| `embodied_carbon_factor` | float | kgCO₂/m³ |

**Class Methods:**

```python
@classmethod
def from_grade(cls, grade: str) -> Concrete
```
Creates Concrete instance from grade string ("M20", "M25", "M30", etc.)

---

#### `Steel`

Represents reinforcement steel properties.

```python
from src.materials import Steel

steel = Steel.from_grade("Fe415")
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `grade` | str | Grade name (e.g., "FE415") |
| `fy` | float | Yield strength (MPa) |
| `modulus_of_elasticity` | float | 200,000 MPa |
| `density` | float | 78.5 kN/m³ |

---

## Sections

### `src/sections.py`

#### `RectangularSection`

```python
from src.sections import RectangularSection

section = RectangularSection(
    name="Beam-1",
    width_b=300.0,  # mm
    depth_d=600.0   # mm
)
props = section.calculate_properties()
```

**Returns `SectionProperties`:**

| Property | Type | Description |
|----------|------|-------------|
| `area` | float | Cross-sectional area (mm²) |
| `ix` | float | Moment of inertia about X (mm⁴) |
| `iy` | float | Moment of inertia about Y (mm⁴) |
| `zx` | float | Section modulus about X (mm³) |
| `zy` | float | Section modulus about Y (mm³) |

---

#### `CircularSection`

```python
from src.sections import CircularSection

section = CircularSection(name="Pile", diameter=500.0)
props = section.calculate_properties()
```

---

#### `ISection`

```python
from src.sections import ISection

section = ISection(
    name="ISMB300",
    flange_width_bf=140.0,
    flange_thickness_tf=12.0,
    web_thickness_tw=8.0,
    overall_depth_d=300.0
)
```

---

## Grid Manager

### `src/grid_manager.py`

#### `Column`

Represents a structural column.

```python
from src.grid_manager import Column

column = Column(
    id="C1",
    x=0.0,
    y=0.0,
    level=0,
    type="corner",  # "corner", "edge", "interior"
    width_nb=300.0,
    depth_nb=300.0
)
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `id` | str | Unique identifier |
| `x`, `y` | float | Location in meters |
| `level` | int | Floor level (0=ground) |
| `type` | str | Position type |
| `trib_area_m2` | float | Tributary area |
| `load_kn` | float | Applied load |
| `width_nb`, `depth_nb` | float | Dimensions (mm) |
| `label` | property | Returns "WxD" string |
| `area_mm2` | property | Cross-sectional area |

---

#### `GridManager`

Main class for grid generation and structural management.

```python
from src.grid_manager import GridManager

gm = GridManager(
    width_m=18.0,
    length_m=12.0,
    num_stories=2,
    story_height_m=3.0,
    max_span_m=6.0
)
```

**Methods:**

```python
def generate_grid(self) -> None
```
Generates column grid based on dimensions and max span.

```python
def calculate_trib_areas(
    self,
    staircase_bay: Optional[Tuple[int, int]] = None,
    void_zones: List[Tuple[int, int]] = None
) -> None
```
Calculates tributary areas for all columns.

```python
def calculate_loads(
    self,
    floor_load_kn_m2: float,
    wall_load_kn_m: float = 0.0
) -> None
```
Performs load takedown from top to bottom.

```python
def optimize_column_sizes(
    self,
    concrete: Concrete,
    fy: float = 415.0
) -> None
```
Sizes columns per IS 456 Cl 39.3.

```python
def generate_beams(self) -> List[StructuralMember]
```
Creates beam elements between grid points.

```python
def detail_beams(self, beams: List[Any]) -> None
```
Generates beam reinforcement schedule.

```python
def detail_slabs(self) -> None
```
Generates slab reinforcement schedule.

```python
def detail_columns(
    self,
    concrete: Concrete,
    fy: float = 415.0
) -> None
```
Generates column reinforcement schedule.

---

## Calculations

### `src/calculations.py`

#### `aggregate_loads`

```python
from src.calculations import aggregate_loads, ComponentLoad

loads = [
    ComponentLoad(name="Slab", value_kn_m=5.0, type="dead"),
    ComponentLoad(name="Live", value_kn_m=3.0, type="live"),
]

result = aggregate_loads(loads, dead_load_factor=1.5, live_load_factor=1.5)
# result.total_factored -> 12.0 kN/m
```

---

#### `analyze_beam`

```python
from src.calculations import analyze_beam
from src.sections import RectangularSection

section = RectangularSection(name="B1", width_b=300, depth_d=600)
props = section.calculate_properties()

result = analyze_beam(
    span_mm=6000.0,
    load_kn_m=30.0,
    section_props=props,
    elastic_modulus_mpa=25000.0,
    support_type="simply_supported"  # or "continuous"
)
```

**Returns `BeamAnalysisResult`:**

| Property | Type | Description |
|----------|------|-------------|
| `max_bending_moment_kNm` | float | Maximum moment |
| `max_shear_force_kN` | float | Maximum shear |
| `max_deflection_mm` | float | Maximum deflection |
| `is_safe_deflection` | bool | Passes L/250 check |
| `status_msg` | str | Result description |

---

#### `check_column_capacity`

```python
from src.calculations import check_column_capacity

result = check_column_capacity(
    load_kN=500.0,
    section_props=props,
    effective_length_mm=3000.0,
    fck=25.0,
    fy=415.0,
    gross_area_mm2=90000.0
)
```

**Returns `ColumnCheckResult`:**

| Property | Type | Description |
|----------|------|-------------|
| `axial_capacity_kN` | float | Pu per IS 456 |
| `load_applied_kN` | float | Applied load |
| `is_safe` | bool | Capacity > Load |
| `slenderness_ratio` | float | Le/r |
| `status_msg` | str | Description |

---

## Foundation Engineering

### `src/foundation_eng.py`

#### `design_footing`

```python
from src.foundation_eng import design_footing
from src.materials import Concrete

footing = design_footing(
    axial_load_kn=500.0,
    sbc_kn_m2=200.0,
    column_width_mm=300.0,
    column_depth_mm=300.0,
    concrete=Concrete.from_grade("M25")
)
```

**Returns `Footing`:**

| Property | Type | Description |
|----------|------|-------------|
| `length_m` | float | Footing length |
| `width_m` | float | Footing width |
| `thickness_mm` | float | Footing depth |
| `area_m2` | float | Plan area |
| `concrete_vol_m3` | float | Concrete volume |
| `excavation_vol_m3` | float | Excavation volume |
| `status` | str | "PASS" or "FAIL" |

---

## Audit

### `src/audit.py`

#### `StructuralAuditor`

Independent verification of structural design.

```python
from src.audit import StructuralAuditor

auditor = StructuralAuditor(
    grid_mgr=gm,
    beams=beams,
    footings=footings
)

results = auditor.run_audit()

for result in results:
    if result.status == "FAIL":
        print(f"{result.member_id}: {result.check_name} - {result.notes}")
```

**Methods:**

| Method | Description |
|--------|-------------|
| `run_audit()` | Executes all checks |
| `audit_columns()` | Checks column capacity |
| `audit_footings()` | Checks bearing & punching shear |
| `audit_beams()` | Checks deflection limits |

**Returns `List[AuditResult]`:**

| Property | Type | Description |
|----------|------|-------------|
| `member_id` | str | Element ID |
| `check_name` | str | Check type |
| `design_value` | float | Actual value |
| `limit_value` | float | Allowable value |
| `status` | str | "PASS", "FAIL", "WARN" |
| `notes` | str | Description |

---

## CAD/BIM Loaders

### `src/cad_loader.py`

#### `CADLoader`

```python
from src.cad_loader import CADLoader

loader = CADLoader("path/to/file.dxf")
grid_manager, beams = loader.load_grid_manager(auto_frame=False)
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `auto_frame` | bool | Generate structure from walls |

---

### `src/bim_loader.py`

#### `BIMLoader`

```python
from src.bim_loader import BIMLoader

loader = BIMLoader("path/to/file.ifc")
grid_manager, beams = loader.load_grid_manager()
```

---

## Utilities

### Logging

```python
from src.logging_config import get_logger, setup_logging

# Setup (call once at startup)
setup_logging(log_level=logging.DEBUG)

# Get logger for module
logger = get_logger(__name__)
logger.info("Message with %s", variable)
```

---

### Authentication

```python
from src.auth import (
    check_authentication,
    authenticate_user,
    logout_user,
    get_current_user
)

# In Streamlit app
if not check_authentication():
    authenticate_user()
    st.stop()

# Get current user
username = get_current_user()

# Logout
logout_user()
```

---

### Error Monitoring

```python
from src.monitoring import (
    init_sentry,
    capture_exception,
    set_user_context,
    monitor_performance
)

# Initialize
init_sentry()

# Capture exception
try:
    risky_operation()
except Exception as e:
    capture_exception(e)

# Performance monitoring decorator
@monitor_performance("expensive_analysis")
def analyze():
    pass
```

---

## Type Definitions

### Common Types

```python
from typing import List, Tuple, Optional, Dict, Any
from pydantic import BaseModel

# Point coordinates
Point = Tuple[float, float]

# Bay index (x_index, y_index)
BayIndex = Tuple[int, int]
```

---

## Error Handling

All modules raise standard Python exceptions:

| Exception | When |
|-----------|------|
| `ValueError` | Invalid input parameters |
| `FileNotFoundError` | Missing CAD/BIM file |
| `IOError` | File read/write errors |
| `ezdxf.DXFStructureError` | Corrupted DXF file |

Example:

```python
try:
    loader = CADLoader("missing.dxf")
except FileNotFoundError:
    logger.error("DXF file not found")
except ValueError as e:
    logger.error("Invalid geometry: %s", e)
```
