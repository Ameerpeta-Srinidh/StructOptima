# Units and Conventions

**As of:** 2026-10-15.

## Units

| Quantity | Unit | Notes |
|---|---|---|
| Plan coordinates, spans, heights | m | `Column.x/y/z_*`, `Point`, grid lines |
| Section dimensions, covers, bar diameters | mm | `width_nb`, `depth_nb`, `properties.width_mm/depth_mm` |
| Forces | kN | |
| Moments | kNm | Section routines use N·mm internally and convert |
| Area loads | kN/m² | |
| Line loads | kN/m | |
| Stresses | N/mm² (MPa) | `fck`, `fy`, τ |
| Elastic modulus in FEA | kN/m² | E = 5000√fck × 1000 |
| Steel areas | mm² | per metre width for slabs/footings |
| Seismic weight | kN | |
| DXF drawing units | from `$INSUNITS` (1 in, 2 ft, 4 mm, 5 cm, 6 m) | fallback heuristic: max |coord| > 500 ⇒ mm; implausible header (extent outside 1–1000 m) ignored with warning |
| IFC lengths | project length unit via `ifcopenshell.util.unit.calculate_unit_scale` | |

## Coordinate systems

- Global plan X along `width_m`, Y along `length_m`, Z vertical (up).
- `Column.width_nb` is measured along X and `depth_nb` along Y (swapped when `orientation_deg` ≈ 90°).
- 2D frames: XZ frames (constant y, 2D coords (x, z)) resist X-direction lateral load; YZ frames (constant x, (y, z)).
- Column moment naming: **Mx** = moment whose lever arm is along X (sway in X, uses dimension `width_nb`); **My** = lever arm along Y (`depth_nb`).

## Sign conventions (FEA)

- Member local x from node 1 to node 2; local y = local x rotated +90°.
- Gravity UDL input positive = global −Y regardless of member direction.
- End force vector `[Fx1, Fy1, M1, Fx2, Fy2, M2]` acts **on the member** in local axes; column axial compression = `Fx1` positive.
- Internal moment: sagging positive (tension at the bottom) for horizontal members, orientation-independent; hogging reported as a positive magnitude (`max_hogging`).

## Load factors and statuses

- Service vs factored contract: see [../architecture/interfaces-and-contracts.md](../architecture/interfaces-and-contracts.md#load-semantics-decision-d-01-proposed).
- Member status: PASS / WARN / FAIL; design status = worst member/check status.

## Numerical tolerances

| Tolerance | Value | Where |
|---|---|---|
| Point on plane / line | 0.10 m | `analysis_integration.TOL` |
| Node merge | 0.05 m | `analysis_integration.MERGE_TOL` |
| Grid snap / column match | 0.01 m (trib), 0.1 m (CAD snap) | `grid_manager`, `cad_loader` |
| Wall-on-beam match | 0.15 m; nearest parallel beam within 3 m | `beam_wall_loads` |
| Base node detection | |y − base| < 0.01 m | `FrameSolver2D._fixed_dofs` |
| Mechanism | K_ii < 1e-9 | `solve_cases` |
| Ill-conditioning | cond > 1e12 | `FrameSolver2D.MAX_CONDITION_NUMBER` |
| Interaction curve | 120 fibres, 131 neutral-axis positions + 2 end points | `section_design` |
| Moment stations | 21 (single case), 11 (combinations) | `fea_solver`, `analysis_integration` |
