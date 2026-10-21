# Supported Inputs

**As of:** 2026-10-21. What StructOptima reads and designs, from the code and the tests (not from intentions).
Levels: **Supported** (implemented, automatically tested, reference values where stated) · **Partial** (works with
documented limits) · **Not verified** (accepted by the UI but not covered by tests or references) · **Unsupported**
(refused with an input error, or out of scope). *Supported* is not an engineer's sign-off: every output is a
preliminary design (CLAUDE.md, [limitations](limitations.md)).

## Structural systems and buildings

| Item | Level | Evidence / limits |
|---|---|---|
| RC moment frame (columns + beams on an orthogonal grid) with two-way / one-way slabs | Supported | Pipeline tests, 9 realistic buildings, design matrix, hand check of `complex_house.dxf` (formula doc Appendix A) |
| OMRF (all zones; FAIL in Zones III-V by IS 1893 Table 9 Note 1) and SMRF | Supported | `test_is1893_2016.py`, `test_is13920_2016.py`; IS 13920 confinement (Ash) and capacity shear not designed (KD-24) |
| Plan shapes: rectangle, L, T, U, courtyard, cross, irregular bays | Supported | DXF corpus (`tests/test_dxf_corpus.py`), design matrix; re-entrant / opening plans: flexible-diaphragm analysis not performed (WARN, KD-23) |
| Storeys 1-12, storey height 2.8-4.5 m | Supported | Design matrix (pairwise + random) |
| Storeys 13-50 (Setup page allows up to 50) | Not verified | No test above 12 storeys; IS 16700 (tall buildings) not implemented; P-Delta not analysed |
| Plans up to 1000 m across | Partial | Bound D-32; largest tested: 96 x 72 m (mall corpus case, 130 columns, 2.4 s) |
| Shear walls, flat slabs, transfer girders, basements, inclined members | Unsupported | Not modelled |
| Columns on one line, or no enclosed slab panel (1-3 columns) | Unsupported (input error) | D-33 |
| Circular columns | Partial | Designed as squares of equal area (KD-27, warned) |
| Wall-width (230 mm) columns | Partial | Zone II OMRF residential only (D-29) |

## Design inputs (Setup page)

| Input | Range accepted | Tested |
|---|---|---|
| Plan width / length (manual mode) | 6-50 m | 6-36 m (design matrix) |
| Storeys / storey height | 1-50 / 2.4-6.0 m | 1-12 / 2.8-4.5 m |
| Occupancy | every entry of `building_types` | every entry (design matrix) |
| Zone / soil / system / importance | II-V / I-III / OMRF, SMRF / 1.0-1.5 | all values |
| Wind zone / terrain | 1-6 / 1-4 | all values |
| Concrete / steel | M20-M30 (matrix), Fe415, Fe500 | all |
| Exposure / NBC type | all five / 1-4 | all |
| SBC | 50-1000 kN/m2 (required, no default) | 150-200 |

## DXF drawings

| Convention | Level | Evidence |
|---|---|---|
| Units: $INSUNITS mm, cm, m, inch, foot | Supported | Corpus + equivalence tests |
| No / implausible $INSUNITS (all R12 files) | Supported | D-35: unit inferred from column outlines, spacing and extent, warned; inch vs cm can be ambiguous for large columns (KD-33) |
| Survey (UTM-size) coordinates | Supported | Only the extent is bounded (D-32); equivalence tests |
| Plan drawn rotated by any single angle | Supported | D-34: rotated back to the axes, warned; equivalence tests (30, -17, 0.5 degrees) |
| Plans with wings at different angles | Partial | Not rotated; skewed columns designed on the main axes (warned) |
| Mirrored drawings / mirrored blocks (extrusion -Z) | Supported | N53 fixed; equivalence tests |
| Columns: closed LWPOLYLINE, 2D POLYLINE, blocks (rotated, scaled incl. non-uniform, mirrored, nested, MINSERT arrays), circles, rounded (bulge) outlines, outlines drawn as separate LINEs (D-39) | Supported | Corpus, drafting-habit tests |
| Overlapping / duplicated column outlines, hollow (inner) outlines | Supported (merged, warned, D-41) | Drafting-habit tests |
| Beams: LINE, polyline per grid line, one line through several columns (split per span, N62), 3D polylines, drawn to the column faces, partly missing, none (generated on grid lines) | Supported | Corpus, drafting-habit tests |
| Curved beams (ARC) | Unsupported (warned, not read) | Drafting-habit tests |
| Frozen / switched-off layers | Not read (warned, D-40) | Drafting-habit tests |
| NaN / infinite coordinates on structural layers | Unsupported (input error) | Drafting-habit tests |
| Walls: double lines (wall layer), interior partitions, none (generated perimeter walls); walls only, no columns (automatic column placement) | Supported / Partial (automatic placement assumes millimetre-like scale) | Corpus |
| Layer names: NCS, Indian, unknown, everything on layer 0 | Supported | D-28, D-36; circular columns on unnamed layers need two members framing in (KD-32) |
| R12, R2000, R2010, R2018 | Supported | Corpus |
| Damaged files (truncated, corrupted bytes, not DXF, empty) | Input error or recovered with a warning | `test_dxf_robustness.py` |
| Annotation: text, MTEXT, dimensions, hatches, arcs, ellipses, splines, points, XLINE / RAY, paper space, far title blocks on annotation layers | Ignored | Corpus |
| Far geometry on a structural layer (> 1000 m) | Unsupported (input error) | D-32 |
| Beam sizes written as text, column sizes as text | Unsupported | Not read (KD-26) |

## IFC

Rectangular extruded columns / beams (IfcColumn, IfcBeam), storeys: Partial (see [limitations](limitations.md)).
