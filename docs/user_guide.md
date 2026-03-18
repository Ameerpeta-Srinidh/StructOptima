# User Guide

This guide explains how to use the Structural Design Platform to analyze and design reinforced concrete buildings.

---

## Overview

The platform supports three input methods:

1. **Manual Dimensions** - Enter building dimensions directly
2. **Import CAD (DXF)** - Load geometry from AutoCAD files
3. **Import BIM (IFC)** - Load from Building Information Models

---

## Web Interface (Streamlit)

### Starting the App

```bash
streamlit run app.py
```

Navigate to `http://localhost:8501` in your browser.

### Interface Layout

```
┌─────────────────────────────────────────────────────────┐
│  Structural Design Platform                              │
├──────────────┬──────────────────────────────────────────┤
│   SIDEBAR    │           MAIN CONTENT                   │
│              │                                          │
│ Input Method │    3D Visualization                      │
│ Parameters   │    Results Metrics                       │
│ Loading      │    Column Schedule                       │
│ Materials    │    Bill of Materials                     │
│ Options      │    Math Inspector                        │
│              │                                          │
│ [Run Button] │                                          │
└──────────────┴──────────────────────────────────────────┘
```

---

## Input Methods

### 1. Manual Dimensions

Best for simple, regular building layouts.

**Parameters:**
| Field | Description | Default |
|-------|-------------|---------|
| Building Width (m) | Total width in X direction | 18.0 |
| Building Length (m) | Total length in Y direction | 12.0 |
| Max Span (m) | Maximum beam span (auto-divides) | 6.0 |
| Number of Stories | Floors above ground | 2 |
| Story Height (m) | Floor-to-floor height | 3.0 |

**Cantilever Options:**
- Enable cantilevers in N/S/E/W directions
- Default cantilever length: 1.5m

### 2. Import CAD (DXF)

For projects with existing CAD drawings.

**Supported Layers:**
| Layer Name | Content | Required |
|------------|---------|----------|
| COLUMNS | Column rectangles (LWPOLYLINE) | Yes* |
| BEAMS | Beam centerlines (LINE) | No |
| WALLS | Wall centerlines (LINE) | For auto-frame |

*Required unless using auto-frame mode.

**Auto-Frame Mode:**
When enabled, the platform automatically:
1. Reads walls from the WALLS layer
2. Identifies structural nodes at wall intersections
3. Places columns at nodes
4. Generates beams between columns

### 3. Import BIM (IFC)

For projects using Building Information Modeling.

**Supported Elements:**
- IfcColumn → Columns with geometry
- IfcBeam → Beams with geometry
- IfcBuildingStorey → Floor levels

---

## Loading Parameters

### Floor Loads

| Parameter | Description | Typical Values |
|-----------|-------------|----------------|
| Floor Load (kN/m²) | Live + superimposed dead | 3-5 (residential), 5-10 (office) |
| Wall Load (kN/m) | Linear load from walls on beams | 8-15 |
| SBC (kN/m²) | Safe Bearing Capacity of soil | 100-300 |

### Material Selection

**Concrete Grades:**
- M20 (20 MPa) - Light duty
- M25 (25 MPa) - Standard
- M30 (30 MPa) - Heavy duty
- M35, M40, M50 - High-rise/special

**Steel Grade:**
- Fe415 - Standard (fy = 415 MPa)
- Fe500 - High-strength (fy = 500 MPa)

---

## Analysis Process

When you click **Run Analysis**, the platform:

1. **Grid Generation** - Creates column grid from inputs
2. **Load Calculation** - Computes tributary areas and loads
3. **Column Sizing** - Optimizes column dimensions per IS 456
4. **Beam Design** - Sizes beams and checks deflection
5. **Foundation Design** - Designs isolated footings
6. **Rebar Detailing** - Generates reinforcement schedules
7. **Structural Audit** - Independent verification checks
8. **Quantification** - Bills of materials and cost

---

## Understanding the Output

### Metrics Dashboard

| Metric | Description |
|--------|-------------|
| Total Columns | Number of columns in structure |
| Total Concrete | Cubic meters of concrete required |
| Total Steel | Kilograms of reinforcement |
| Carbon Footprint | Tons of CO₂ equivalent |

### 3D Visualization

- **Columns**: Sized boxes at grid intersections
- **Beams**: Lines connecting columns
- **Color Scale**: Load intensity (heatmap mode)

**View Modes:**
- Engineering (Heatmap) - Colors by load intensity
- Architectural (Neutral) - Uniform colors

### Column Schedule Tab

| Column | Description |
|--------|-------------|
| ID | Column identifier (e.g., C1_L0) |
| Location | (X, Y) coordinates in meters |
| Size | Width × Depth in mm |
| Load | Applied axial load in kN |
| Main Steel | Reinforcement bars (e.g., 6-16φ) |
| Stirrups | Tie bars (e.g., 8φ@150) |
| Footing | Foundation size (e.g., 1.5×1.5m) |

### Bill of Materials Tab

JSON breakdown showing:
- Concrete volumes by element type
- Steel weights
- Excavation volumes
- Estimated costs

### Math Inspector Tab

Shows step-by-step calculations for:
- Load aggregation
- Column capacity checks
- Footing punching shear

---

## Staircase Design

Enable staircase option to:
1. Create a void in the selected bay
2. Reduce tributary area for adjacent columns
3. Add reaction loads from staircase
4. Generate waist slab design

---

## Exporting Results

### PDF Report

Automatically generated after analysis:
- Project summary
- Column schedules
- Beam schedules
- Footing details
- Bill of quantities

### DXF Export

Export structural plan to CAD:
- Grid lines (dashed)
- Column outlines
- Beam centerlines
- Element labels

---

## Command Line Interface

For batch processing or scripting:

```bash
# Basic run
python main.py

# With CAD file
python main.py --cad path/to/file.dxf

# With auto-framing
python main.py --cad arch_plan.dxf --auto-frame
```

Output:
- Console log with results
- `Structural_Report_V2.pdf` generated

---

## Tips & Best Practices

### For Accurate Results

1. **Use consistent units** - Platform expects meters for dimensions
2. **Check layer names** - DXF layers must match expected names
3. **Verify SBC** - Soil bearing capacity significantly affects footing sizes
4. **Review audit** - Check FAIL items in audit results

### Performance

1. **Large models** - Limit to ~500 columns for responsive UI
2. **IFC files** - Pre-filter to structural elements only

### Troubleshooting

| Issue | Solution |
|-------|----------|
| "No columns found" | Check DXF layer names or enable auto-frame |
| Oversized footings | Verify SBC value is realistic |
| High steel percentage | Consider increasing concrete grade |
| Audit failures | Review and resize affected members |

---

## Example Workflow

### Scenario: 3-Story Office Building

1. **Input**:
   - Method: Manual Dimensions
   - Width: 24m, Length: 18m
   - Stories: 3, Height: 3.5m/story
   - Max Span: 6m

2. **Loading**:
   - Floor Load: 5 kN/m² (office)
   - Wall Load: 12 kN/m
   - SBC: 200 kN/m²

3. **Materials**:
   - Concrete: M25
   - Steel: Fe415

4. **Run Analysis** → Review Results

5. **Export**:
   - Download PDF report
   - Export DXF for CAD team

---

## Next Steps

- See [API Reference](api_reference.md) for programmatic usage
- Check [Installation Guide](installation.md) for setup help
