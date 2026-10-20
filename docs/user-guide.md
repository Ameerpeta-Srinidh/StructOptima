# StructOptima — User Guide

**As of:** 2026-10-20. For site engineers, developers and owners using the web app.

StructOptima produces a **preliminary** reinforced-concrete frame design. Every result is **NOT VERIFIED** and must
be checked by a licensed structural engineer before construction. The app never invents numbers: everything it
shows comes either from the design it computed or from data you enter. If something has not been computed, the app
says so.

---

## Layout

The pages are in the bar at the top: **Setup · Overview · Checks · Members · Drawings & 3D · Reports · Site tools**.
Once a design has run, a project bar under it shows:
- the storeys, materials and zone;
- the design status (PASS / WARN / FAIL with the counts);
- "NOT VERIFIED";
- an orange **"Inputs changed — results out of date"** badge if you edit an input after the run. Every result page
  then also shows a warning. Re-run from Setup to update.

Inputs are kept when you move between pages.

## 1. Run a design (Setup page)

Fill in the five tabs on the left. The **Run design** panel on the right lists what is still missing.

1. **Building & geometry**: project name, engineer and drawing reference, then the geometry source:
   - *Manual dimensions*: plan width and length, storeys, storey height, optional cantilever balconies and
     staircase void. A plan preview shows the starting column grid;
   - *CAD drawing (DXF)*: columns as closed polylines on COL layers, beams as lines on BEAM layers. Turn on
     *Place columns automatically* if the drawing has walls only. The uploaded file is kept until you upload
     another one;
   - *BIM model (IFC)*.
2. **Occupancy & loads**: the occupancy (the load values it uses are shown) and the wall load used when the model has
   no walls.
3. **Site, seismic & wind**: the **SBC** from the site's geotechnical report (required, no default), seismic zone,
   soil type, structural system (OMRF by default; SMRF needs full IS 13920 detailing, which the tool does not
   design), importance factor (set from the occupancy; verify against IS 1893 Table 8), wind zone and terrain
   category.
4. **Materials & modelling**: concrete and steel grade; **exposure condition** (IS 456 Table 3), which sets the covers
   and the minimum grade (Table 5); **NBC type of construction** (Part 4 Table 1), which sets the fire rating of
   columns, beams and slabs. The covers and fire ratings used are shown under the inputs. Then fixed or pinned bases, cracked sections, fly-ash concrete,
   column optimisation display, plan colouring.
5. **Masonry**: wall thickness, mortar, openings, interior walls.

Then, in the Run design panel:
- tick that the site parameters apply to this site. **Changing any site parameter (SBC, zone, soil, wind zone,
  terrain, occupancy or geometry source) clears this tick**, so you confirm the values you actually run with;
- tick the verification statement;
- press **Run design**. The app opens the Overview when the design finishes.

## 2. Overview page

### Reading the status
| Banner | Meaning |
|---|---|
| FAIL (red) | At least one check failed. Do not build from this design |
| WARN (amber) | Items need an engineer's review: fallbacks, advisory checks, non-convergence, wind not considered |
| PASS for the implemented checks only — NOT VERIFIED (green) | Every check the tool performs passed. That is **not** a complete design check |

Open **"Checks NOT performed by StructOptima"** under the banner. It lists what must be checked separately:
- torsion and 3D effects, and response-spectrum analysis;
- orthogonal seismic combination;
- pattern live loading;
- P-Δ and effective length;
- IS 13920 ductile detailing;
- laps and anchorage;
- beam torsion and deflection;
- footing moments and settlement.

**Seismic analysis.** StructOptima runs the response spectrum method of IS 1893 (Part 1):2016 (clause 7.7.5) on a 3D
model with rigid floors: modes, CQC combination, scaling up to the static base shear (7.7.3) and the design
eccentricity of 7.8.2 (torsion), which also loads the frames of the other direction. The Checks page (Seismic tab)
shows the periods, the modal mass, the scale factors and the torsion ratio. Things this model cannot do appear as WARN
with the check to be done elsewhere, for example L/T-shaped plans, which IS 1893 wants analysed with flexible floors.
In Zones III–V an OMRF is a FAIL (Table 9, Note 1): select SMRF.

**Issues to resolve** lists every FAIL and WARN item, failures first. Filter by status or type; hover a cell to read
long text.

Below it:
- the **3D model**: click a member for its details;
- the **quantities**: concrete, reinforcement, cost and carbon for all floors;
- material breakdowns.

For DXF models with automatic column placement, the **column editor** at the bottom adds or removes columns. A
change re-runs the design.

## 3. Checks page

One tab per topic:
- **Issues**: the design failures and overstress report, plus the strong column – weak beam details;
- **Seismic**: zone factor, Ah, base shear, I / R, storey forces, ductile detailing requirements;
- **Wind**: design wind speed and base shears;
- **Drift**: relative sideways movement of each storey under the design earthquake and wind forces.
  - Earthquake drift above 0.004 × storey height is a FAIL. The design automatically enlarges the columns to try
    to meet it.
  - Wind top sway above height / 500 is a WARN.
  - Both limits are as commonly cited and still need confirmation against the printed standards.
  - Drift does not include torsion.
- **Stability & fire**: fire rating, slenderness and minimum dimensions;
- **Joints & plan**: plan irregularity warnings, the mass – stiffness offset screen, deep beams, joint shear and
  the stiffness modifiers. The offset screen is not the IS 1893 torsional irregularity check: torsion is not
  analysed;
- **Load combinations**: the combinations applied and the overall overturning check;
- **Deflection (L/d)**: basic span / depth ratios, without modification factors;
- **Optimisation**: only when turned on in Setup. It is indicative only.

## 4. Members page

Find any member by id at the top, then one tab per member type:
- **Columns** (filter by level and status);
- **Beams**, **Slabs** and **Footings**;
- **Calculation log**: the column design steps;
- **Walls & finishes**: the masonry takeoff.

Every table has a coloured **Status** column. The footing table shows each footing check separately: bearing,
punching, one-way shear and bending.

The member **marks** (C1, B1, S1, F1) are the same on the drawings, the 3D viewer and the QR tags.

## 5. Drawings & 3D page

Choose a view at the top: Drawing sheets, 3D model, Plan, CAD view or DXF exports. Only the chosen view is
generated.

### 5.1 Drawing sheets (A3 set)
- Sheets:
  - S-01 column layout & schedule;
  - S-02 footing layout;
  - S-03 beams & slabs;
  - S-04 sections;
  - S-05 slab reinforcement;
  - S-06 footing sections.
- Members drawn red have FAILED; orange ones need review.
- Zoom with the scroll wheel or a two-finger pinch; drag to pan; double-click to reset.
- **Download** menu:
  - the full PDF set;
  - one sheet as DXF (paper millimetres, plot 1:1);
  - a ZIP with every sheet;
  - the **IFC4 model**, which opens in any IFC viewer.

### 5.2 3D model
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

## 6. Reports page

Files are generated when you click download. The complete package (ZIP) contains every report, the floor-wise
reports, Excel data and DXF plans; if a part cannot be generated, the ZIP contains `_NOT_INCLUDED.txt` naming it.

The PDF reports carry:
- the design status and failures list;
- "NOT VERIFIED" and the checks not performed;
- the storey drift table.

Material quantities appear only if you have entered your approved mix (see 7.2).

## 7. Site tools page

### 7.1 Bar Bending Schedule
- Shows the steel by diameter and the member-wise BBS.
- **Scope**: one typical floor (its beams and slab panels) and the ground-storey columns. Upper-storey columns,
  footings, staircases and wastage are not in it, so its total is smaller than the Overview reinforcement total,
  which covers all floors.
- **Cutting plan**: enter the stock bar length delivered to site. The plan cuts the longest pieces first, using as
  few stock bars as possible.
- It reports, per diameter: stock bars needed, offcut and efficiency.
- Bars longer than the stock length are listed separately. They need a lap or coupler where the drawings or the
  engineer show it.
- Download the plan as CSV.

### 7.2 Site Calculators
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

### 7.3 Site Checklists
Prompts for formwork, reinforcement, concreting and curing. Numbers in them are as cited and unverified; the
project specification and the engineer's instructions govern.

### 7.4 BIM & Handover
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

## 8. Limits to remember

- 2D frames only: no torsion. Irregular plans need an independent 3D analysis.
- Equivalent static seismic method only. Where it is not permitted the design FAILs ("Seismic method").
- Laps, anchorage and curtailment are typical notes on the drawings, not designed.
- Full list: [engineering/limitations.md](engineering/limitations.md). Changes: [../CHANGELOG.md](../CHANGELOG.md).
