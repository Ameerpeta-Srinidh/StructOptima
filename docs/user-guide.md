# StructOptima — User Guide

**As of:** 2026-10-16. For site engineers, developers and owners using the web app.

StructOptima produces a **preliminary** reinforced-concrete frame design. Every result is **NOT VERIFIED** and must
be checked by a licensed structural engineer before construction. The app never invents numbers: everything it
shows comes either from the design it computed or from data you enter. If something has not been computed, the app
says so.

---

## 1. Run a design (main page)

1. **Geometry** (sidebar): choose one of:
   - *Manual Dimensions*: plan width and length, storeys, storey height;
   - *Import CAD (DXF)*: columns as closed polylines on COL layers, beams as lines on BEAM layers;
   - *Import BIM (IFC)*.
2. **Occupancy & Loads**: choose the occupancy, then enter the **SBC** from the site's geotechnical report. There is
   no default; the button stays disabled until you enter it.
3. **Environmental**: choose:
   - the seismic zone;
   - the soil type;
   - the structural system (OMRF by default; SMRF needs full IS 13920 detailing, which the tool does not design);
   - the importance factor;
   - the wind zone and terrain category.
4. **Materials / Advanced**: concrete and steel grade, cracked sections, fixed or pinned bases, staircase void.
5. Tick **"I confirm the SBC, seismic zone, soil type, wind zone and terrain category … apply to this site"**.
6. Tick the professional-use disclaimer, then press **Run Analysis**.

### Reading the status
| Banner | Meaning |
|---|---|
| ❌ FAIL | At least one check failed. The Analysis page lists each item. Do not build from this design |
| ⚠️ WARN | Items need an engineer's review: fallbacks, advisory checks, non-convergence, wind not considered |
| ✅ PASS for the implemented checks only — NOT VERIFIED | Every check the tool performs passed. That is **not** a complete design check |

Open **"Checks NOT performed by StructOptima"** under the banner. It lists what must be checked separately:
- torsion and 3D effects, and response-spectrum analysis;
- orthogonal seismic combination;
- pattern live loading;
- P-Δ and effective length;
- IS 13920 ductile detailing;
- laps and anchorage;
- beam torsion and deflection;
- footing moments and settlement.

## 2. Analysis page

- **Seismic, wind, stability, joints**: parameters and results of the checks.
- **Storey Drift**: relative sideways movement of each storey under the design earthquake and wind forces.
  - Earthquake drift above 0.004 × storey height is a FAIL. The design automatically enlarges the columns to try
    to meet it.
  - Wind top sway above height / 500 is a WARN.
  - Both limits are as commonly cited and still need confirmation against the printed standards.
  - Drift does not include torsion.
- **Design Failures & Overstress Report**: every FAIL / WARN item with the reason.

## 3. Schedules page

Column, beam, slab and footing schedules with the member **marks** (C1, B1, S1, F1). The same marks appear on the
drawings, the 3D viewer and the QR tags.

## 4. Drawings page

### Site Drawings (A3 set)
- Sheets:
  - S-01 column layout & schedule;
  - S-02 footing layout;
  - S-03 beams & slabs;
  - S-04 sections;
  - S-05 slab reinforcement;
  - S-06 footing sections.
- Members drawn red have FAILED; orange ones need review.
- Downloads: the full PDF set, one sheet as DXF (paper millimetres, plot 1:1), or a ZIP with every sheet.
- **IFC4 model**: open in any IFC viewer. Click a member to see its mark, size, bars and status.

### 3D View
| Control | What it does |
|---|---|
| View → Orbit | Drag to rotate, scroll / pinch to zoom, right-drag to pan |
| View → Walk-through | Stand inside the building at eye height (1.6 m) |
| Walk keys | W/A/S/D or arrow keys move; drag (mouse or finger) looks around; Q / E go down / up a floor; Shift walks faster. On a tablet or phone use the on-screen ▲ ◀ ▼ ▶ and Floor − / Floor + buttons. Click the view once before using the keyboard |
| Colour | *By member type*, or *By design status* (green PASS, orange WARN, red FAIL, grey no status) |
| Storey | Show one storey only |
| Columns / Beams / Slabs / Walls / Footings | Show or hide each kind |
| Section cut | Slide to cut the building horizontally and look inside |
| Find mark | Type a mark (e.g. `C3`) to highlight every member with it |
| Click a member | Panel with its mark, size, bars, ties / stirrups, status, governing load combination |

The model shows members as solid boxes: no openings, reinforcement or stair flights. Footings are hidden in
walk-through because they are below ground. Use the drawing set for construction details.

## 5. Reports page

The PDF reports carry:
- the design status and failures list;
- "NOT VERIFIED" and the checks not performed;
- the storey drift table.

Material quantities appear only if you have entered your approved mix (see 6.2).

## 6. Site Tools page

### 6.1 Bar Bending Schedule
- Shows the steel by diameter and the member-wise BBS.
- **Cutting plan**: enter the stock bar length delivered to site. The plan cuts the longest pieces first, using as
  few stock bars as possible.
- It reports, per diameter: stock bars needed, offcut and efficiency.
- Bars longer than the stock length are listed separately. They need a lap or coupler where the drawings or the
  engineer show it.
- Download the plan as CSV.

### 6.2 Site Calculators
- **Rebar weight**: kg per metre = d²/162.
- **Approved mix design**: enter the batch weights per m³ of your approved mix (lab trial mix or RMC supplier):
  cement, water, fine aggregate and coarse aggregate. Press *Save*. These drive every material quantity in the app;
  without them no cement or aggregate quantity is shown.
- **Cube test register**: enter the specified grade, up to three cube strengths and the test age. The register
  shows the mean, minimum and deviation. Acceptance is decided by the engineer under IS 456 / IS 516.
- **Concrete pour planner**: volume (defaults to the model total), mixer capacity, wastage and the pour rate you
  achieve. It gives trips, pour time and materials from the approved mix.
- **Formwork contact area**: from the model, with slab thickness deducted from column and beam sides. Sheet count
  assumes single use.

### 6.3 Site Checklists
Prompts for formwork, reinforcement, concreting and curing. Numbers in them are as cited and unverified; the
project specification and the engineer's instructions govern.

### 6.4 BIM & Handover
| Tab | Use |
|---|---|
| Calculation Summary | Text record of this design (inputs, seismic, drift, governing column, failures, checks not performed). Download .txt. Also COBie JSON from the design |
| Member Tags (QR) | Pick a member. Print its QR and fix it to the formwork or cage; any phone camera reads the member's schedule offline |
| Site Inspection | Pick stage, member and inspector; mark each check Pass / Fail / N/A with remarks; download the record as CSV. **Defect log**: record observed defects (type, location, crack width / length, optional GPS). Each entry is marked "Awaiting engineer review". Download CSV; entries with GPS appear on a map |
| Measured Vibration & Strain | Upload an accelerometer CSV to get its spectrum and dominant frequency, plus the change from a baseline frequency if you enter one. Upload strain-gauge readings to compare them with yield strain. The app does not judge damage |
| As-Built Survey | Enter the specified positional tolerance, then upload surveyed column centres. The app shows the deviation of each column from the design grid, and which columns exceed the tolerance |

### CSV formats (first row may be a header)
| Upload | Columns | Example |
|---|---|---|
| Accelerometer | time (s), acceleration (any unit); at least 64 rows, evenly spaced (within 1 %) | `0.00,0.0012` |
| Strain gauges | gauge or member id, microstrain | `C3-north,850` |
| As-built survey | column id (as in the design, e.g. `C1`), x (m), y (m) in the design grid coordinates | `C1,0.004,-0.003` |

## 7. Limits to remember

- 2D frames only: no torsion. Irregular plans need an independent 3D analysis.
- Equivalent static seismic method only. Where it is not permitted the design FAILs ("Seismic method").
- Laps, anchorage and curtailment are typical notes on the drawings, not designed.
- Full list: [engineering/limitations.md](engineering/limitations.md). Changes: [../CHANGELOG.md](../CHANGELOG.md).
