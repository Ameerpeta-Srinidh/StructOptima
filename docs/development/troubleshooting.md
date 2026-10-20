# Troubleshooting

**As of:** 2026-10-15.

| Symptom | Likely cause | What to do |
|---|---|---|
| DXF building appears 1000× too large/small or "implausible extent" warning | Wrong or missing `$INSUNITS` in the DXF (ezdxf writes 6 = metres by default) | Set drawing units in the CAD file; the loader falls back to a size heuristic only outside 1–1000 m |
| "No columns or wall geometry found in the DXF file" | No closed LWPOLYLINEs on COL* layers and no line geometry | Put columns on a `COLUMNS` layer or walls on a `WALL*` layer |
| Warning that line segments from non-WALL layers were used as walls | Tier-2/3 wall fallback | Move walls to a `WALL*` layer; remove furniture/annotation lines |
| IFC import error / IFC option disabled | `ifcopenshell` missing or no IfcColumn | `pip install ifcopenshell`; check the model contains IfcColumn with extruded rectangular profiles |
| WARN "Seismic method" | Re-entrant corners or large floor openings: IS 1893 (Amd 2) wants a flexible-diaphragm 3D analysis; or fewer than two frame lines in a direction (no torsional restraint) | Check with a flexible-diaphragm 3D model (ETABS / STAAD); add frame lines |
| FAIL "Structural system" | OMRF selected in Zone III, IV or V (IS 1893 Table 9 Note 1) | Select SMRF |
| FAIL "Irregular modes" | Zone IV / V and the X and Y fundamental periods within 10 %, or the first three modes below 65 % mass (Table 6(vii), Amd 2) | Make the two directions' stiffness different (column orientation, sizes) |
| FAIL / WARN "Torsional irregularity" | Δmax / Δave above 1.2 at the plan ends | Balance the stiffness in plan; above 1.4 the configuration must be revised |
| "Design did not converge" | Columns keep growing; large spans / heavy loads | Increase `max_iterations` (CLI/API), adjust layout |
| "Frame not solved" | Unsupported beam lines (mechanism) in a frame | Check columns exist at beam ends; affected beams use simply supported fallback |
| Many SCWB / joint WARN items | Advisory for OMRF (R = 3) | Review; mandatory (FAIL) when SMRF is selected |
| Footing WARN "edge pressure … with base moment" | Fixed-base moments not used for sizing (D-06) | Engineer to size for eccentric pressure |
| `structural_design.log` appears | CLI (`main.py`) or `STRUCTOPTIMA_LOG_FILE` set | Expected for the CLI |
| Slow first run | Interaction curves are computed then memoised | Subsequent designs reuse cached curves |
| Tests create `.pytest_cache` / `__pycache__` | Default pytest behaviour | Use the command in the test execution guide |
