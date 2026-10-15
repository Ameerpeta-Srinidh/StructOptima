# Troubleshooting

**As of:** 2026-10-15.

| Symptom | Likely cause | What to do |
|---|---|---|
| DXF building appears 1000× too large/small or "implausible extent" warning | Wrong or missing `$INSUNITS` in the DXF (ezdxf writes 6 = metres by default) | Set drawing units in the CAD file; the loader falls back to a size heuristic only outside 1–1000 m |
| "No columns or wall geometry found in the DXF file" | No closed LWPOLYLINEs on COL* layers and no line geometry | Put columns on a `COLUMNS` layer or walls on a `WALL*` layer |
| Warning that line segments from non-WALL layers were used as walls | Tier-2/3 wall fallback | Move walls to a `WALL*` layer; remove furniture/annotation lines |
| IFC import error / IFC option disabled | `ifcopenshell` missing or no IfcColumn | `pip install ifcopenshell`; check the model contains IfcColumn with extruded rectangular profiles |
| Design status FAIL with "Seismic method" | Irregular plan or height above the ESA limit for the zone | The tool cannot provide a valid seismic analysis; use response spectrum analysis externally |
| "Design did not converge" | Columns keep growing; large spans / heavy loads | Increase `max_iterations` (CLI/API), adjust layout |
| "Frame not solved" | Unsupported beam lines (mechanism) in a frame | Check columns exist at beam ends; affected beams use simply supported fallback |
| Many SCWB / joint WARN items | Advisory for OMRF (R = 3) | Review; mandatory (FAIL) when SMRF is selected |
| Footing WARN "edge pressure … with base moment" | Fixed-base moments not used for sizing (D-06) | Engineer to size for eccentric pressure |
| `structural_design.log` appears | CLI (`main.py`) or `STRUCTOPTIMA_LOG_FILE` set | Expected for the CLI |
| Slow first run | Interaction curves are computed then memoised | Subsequent designs reuse cached curves |
| Tests create `.pytest_cache` / `__pycache__` | Default pytest behaviour | Use the command in the test execution guide |
