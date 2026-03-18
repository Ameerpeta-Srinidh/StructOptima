# Black Box Risk Management Module

## Overview

The Black Box Risk Management Module (`src/risk_management.py`) implements comprehensive checks to prevent common failures in residential building projects due to "Black Box" software usage. Based on industry reviews and failure case studies, this module addresses critical areas where software automation often leads to dangerous or expensive outcomes.

## Risk Categories

### 1. Input & Modeling Assumptions Risks

#### Fixed Support Assumption Check
- **Risk**: Users frequently model column foundations as "Fixed" supports. In reality, isolated footings on standard soil allow for rotation.
- **Consequence**: Underestimates frame drift and column moments (working on the unsafe side).
- **Mitigation**: Prompts users to define soil spring stiffness (subgrade modulus) rather than defaulting to rigid fixity.

#### Rigid Diaphragm Assumption Check
- **Risk**: Software defaults to assuming floor slabs are infinitely rigid diaphragms.
- **Consequence**: In irregular shapes (L, C) or large openings, the slab actually deforms, incorrectly distributing seismic forces.
- **Mitigation**: Detects floor plans with opening area > 30% and suggests "Semi-Rigid" analysis.

#### Site-Specific Geotechnics Check
- **Risk**: Applying standard bearing capacities without site-specific modification.
- **Consequence**: Differential settlement and slope failure (especially during monsoons).
- **Mitigation**: Warns about need for soil test reports, slope stability, and saturation effects.

### 2. Load Modeling & Analysis Failures

#### P-Delta Effects Check
- **Risk**: Ignoring secondary moments from vertical load acting on laterally displaced structure.
- **Consequence**: Underestimation of storey drift and column moments (can increase displacement by >10%).
- **Mitigation**: As per IS 16700, flags structures where P-Delta analysis should be mandatory (stability index > 0.1).

#### Pattern Loading Check
- **Risk**: Applying live load across entire floor simultaneously.
- **Consequence**: IS 456 mandates "Pattern Loading" (alternate spans loaded) for continuous beams. Missing this underestimates moments at mid-span and supports.
- **Mitigation**: Forces pattern loading analysis for continuous beam systems.

#### Floating Columns Check
- **Risk**: Columns resting on beams without flagging the irregularity.
- **Consequence**: Creates vertical irregularity and stress concentration. Missing lateral load paths are a major cause of failure.
- **Mitigation**: Detects floating columns and flags as CRITICAL issue requiring transfer beams or redesign.

### 3. Detailing & Constructibility Simplifications

#### Bend Deduction Check
- **Risk**: Calculating cutting lengths based on center-line dimensions without subtracting for steel elongation during bending.
- **Consequence**: Cut bars are too long and don't fit in formwork, leading to onsite ad-hoc cutting and wastage.
- **Mitigation**: BBS module now applies bend deductions (2d for 90° bends, 4d for 180° bends).

#### Congestion Check at Joints
- **Risk**: Reinforcement spacing too close for aggregate to pass.
- **Consequence**: Honeycombing and weak joints.
- **Mitigation**: Checks that reinforcement spacing > aggregate size + 5mm at beam-column joints.

#### Seismic Hook Detailing Check
- **Risk**: Defaulting to 90-degree hooks for stirrups.
- **Consequence**: In seismic zones (III, IV, V), IS 13920 mandates 135-degree hooks with specific extension lengths (6d or 65mm).
- **Mitigation**: Flags seismic zones and requires 135° hooks per IS 13920.

### 4. Cost Estimation & Quantity Take-off Errors

#### Opening Deduction Logic Check (IS 1200)
- **Risk**: Automatically deducting all openings from masonry/concrete volumes.
- **Consequence**: IS 1200 specifies openings < 0.1 m² are NOT deducted. Deducting everything causes under-estimation of billable quantities.
- **Mitigation**: Quantifier module now applies IS 1200 rules (only deduct openings ≥ 0.1 m²).

#### Wastage & Rolling Margin Check
- **Risk**: Billing based on exact theoretical weight of steel.
- **Consequence**: Real-world procurement must account for rolling margin (variance in unit weight) and off-cut wastage. Software estimates are often 3-5% lower than actual needs.
- **Mitigation**: Quantifier module now adds 3-5% wastage factor to steel quantities.

### 5. Summary Checklist

#### Sanity Check: Building Weight vs Base Reaction
- **Risk**: Discrepancy indicates modeling or load calculation error.
- **Consequence**: Major errors in load calculations.
- **Mitigation**: Flags if total building weight vs total base reaction deviates by > 10-20%.

## Usage

### Basic Usage

```python
from src.risk_management import run_risk_checks
from src.grid_manager import GridManager
from src.framing_logic import StructuralMember
from src.foundation_eng import Footing

# Initialize your structure
grid_mgr = GridManager(width_m=10.0, length_m=10.0, num_stories=3)
grid_mgr.generate_grid()

beams = [...]  # Your beam list
footings = [...]  # Your footing list

# Run all risk checks
results, report = run_risk_checks(
    grid_mgr=grid_mgr,
    beams=beams,
    footings=footings,
    fck=25.0,
    fy=415.0,
    seismic_zone="IV",
    aggregate_size_mm=20.0,
    subgrade_modulus_kn_m3=30000.0  # Optional: soil spring stiffness
)

# Print formatted report
print(report)
```

### Advanced Usage

```python
from src.risk_management import BlackBoxRiskManager, format_risk_report

# Create manager with custom parameters
manager = BlackBoxRiskManager(
    grid_mgr=grid_mgr,
    beams=beams,
    footings=footings,
    fck=25.0,
    fy=415.0,
    seismic_zone="IV",
    aggregate_size_mm=20.0,
    subgrade_modulus_kn_m3=30000.0
)

# Run all checks
results = manager.run_all_checks()

# Access individual results
for result in results:
    if result.risk_level == "CRITICAL":
        print(f"CRITICAL: {result.check_name}")
        print(f"  {result.message}")
        print(f"  Recommendation: {result.recommendation}")

# Generate formatted report
report = format_risk_report(results)
print(report)
```

## Integration with Existing Modules

### BBS Module Updates

The BBS module (`src/bbs_module.py`) has been updated to apply bend deductions:

- **90° bends**: Deduct 2d per bend
- **180° bends**: Deduct 4d per bend
- Applied to all cutting length calculations (beams, columns, slabs, stirrups)

### Quantifier Module Updates

The Quantifier module (`src/quantifier.py`) has been updated to:

- **IS 1200 Opening Rules**: Only deduct openings ≥ 0.1 m² from concrete volumes
- **Wastage & Rolling Margin**: Add 3-5% to steel quantities (configurable via `steel_wastage_percent` parameter)

## Risk Levels

- **CRITICAL**: Immediate safety concern (e.g., floating columns, seismic hook violations)
- **HIGH**: Significant design error (e.g., fixed supports, pattern loading omission)
- **MEDIUM**: Potential issue (e.g., site-specific geotechnics, wastage)
- **LOW**: Informational
- **PASS**: Check passed

## Report Format

The risk report includes:

1. **Summary Statistics**: Count of issues by risk level
2. **Detailed Results by Category**:
   - Modeling Assumptions
   - Load Modeling & Analysis
   - Detailing & Constructibility
   - Cost Estimation & Quantity

Each result includes:
- Check name and risk level
- Status (PASS/WARN/FAIL)
- Message describing the issue
- Affected members (if applicable)
- Calculated vs limit values (if applicable)
- Recommendation for mitigation

## Testing

Run the test suite:

```bash
python -m pytest tests/test_risk_management.py -v
```

## References

- IS 456:2000 - Plain and Reinforced Concrete Code of Practice
- IS 13920:2016 - Ductile Detailing of Reinforced Concrete Structures
- IS 1200 - Method of Measurement of Building and Civil Engineering Works
- IS 16700:2017 - Criteria for Structural Safety of Tall Concrete Buildings
- IS 1893 - Criteria for Earthquake Resistant Design of Structures

## Disclaimer

All designs must be verified by a licensed Structural Engineer before construction. This module provides automated checks to flag potential issues but does not replace professional engineering judgment.
