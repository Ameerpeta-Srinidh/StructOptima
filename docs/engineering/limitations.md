# Limitations

**As of:** 2026-10-16. Read this before relying on any StructOptima output.

## Scope

- Regular, low-rise RC moment frames with rectangular columns and beams on orthogonal grid lines.
- Outputs are **preliminary**. Every result requires independent verification by a licensed structural engineer. Reports carry a "PRELIMINARY — NOT FOR CONSTRUCTION" banner.

## Analysis

- Independent 2D plane frames along grid lines; beams off grid lines are designed as simply supported (warning).
- Rigid floor diaphragms only (no flexible-diaphragm analysis); no P-Δ or second-order analysis.
- Storey drift is computed per column from the 2D frames (since 2026-10-16); without torsion it under-estimates drift at the flexible edge of irregular plans. Limits checked against IS 1893 7.11.1.1 and IS 456 20.5 (2026-10-20).
- Storey forces are shared between parallel frames as for a rigid floor in translation (each frame's condensed lateral stiffness; slab links tie the column tops a beam does not connect) since 2026-10-20.
- Seismic forces by the response spectrum method (IS 1893 7.7.5) on a rigid-diaphragm 3D model assembled from the condensed frame stiffnesses (3 DOF per floor), CQC of all modes, scaled to the static VB (7.7.3), with design eccentricity (7.8.2). Floor centre of mass and rotational inertia from the slab panels (columns and walls not located individually). Re-entrant corners and large openings need a flexible-diaphragm 3D model (WARN).
- No orthogonal seismic combination, vertical seismic or pattern live loading.
- Column gravity axial load from tributary areas (not from frame continuity).
- Static wind only; dynamic/gust effects are flagged for tall/slender buildings but not computed; Kd, Ka, Kc taken as 1.0 (conservative); k3 and k4 taken as 1.0 (sloping sites and cyclone-prone coasts need them); h/w ≥ 6 is a FAIL.
- Linear elastic with uniform cracked-section modifiers.

## Design

- IS 13920 ductile detailing is **not** designed: no confining steel (Ash), no capacity-design shear, no joint reinforcement design. Selecting SMRF (R = 5) shows a warning; the tool cannot justify R = 5.
- SCWB and joint-shear checks use simplified capacities (slab steel ignored, no column-shear deduction) and are advisory for OMRF.
- Column effective length factor 1.0 by default (no Annex E calculation).
- Beams are rectangular (no flange action); deflection checked by basic span/d ratios only (no modification factors, no long-term calculation in design; the audit uses an approximate short-term deflection).
- No curtailment, development length or lap checks in member design (tables exist in `anchorage.py`; BBS uses its own rules).
- Slabs: Table 26 coefficients (checked against the printed table 2026-10-20); no corner torsion steel; one-way slabs use wl²/8 everywhere.
- Staircase: single typical flight with a fixed geometry assumption.
- Footings: square isolated pads only; base moments not used for sizing (warning only); no combined footings, rafts, piles, uplift resistance or settlement.

## Ingest

- DXF: columns are closed LWPOLYLINE / POLYLINE outlines or circles on layers whose name contains a whole word COL, COLS, COLUMN, PILLAR … (annotation words such as IDEN, TEXT, TAG, DIM, HATCH exclude a layer), directly or inside blocks; beams are LINE / polyline centre lines on BEAM / GIRDER layers. Plans in blocks are exploded; unbound xrefs are reported. Grid lines within 150 mm are merged; beam ends within half a column + 150 mm of a column are moved to its centre; drawings are moved to the origin. Circular columns become equal-area squares (warned). Beam sizes are not read (initial 300 × 600). Wall detection by layer keywords with fallbacks that can pick up non-structural lines (warned). Auto-framing assumes drawings in millimetres.
- Drawings whose `$INSUNITS` disagree with the geometry are detected only when the resulting extent is outside 1–1000 m.
- IFC: only rectangular extruded profiles; inclined beams skipped; storey heights averaged; one plan beam layout for all storeys.

## Drawings

- The drawing set shows designed sizes and bars only. Laps, curtailment, anchorage, corner torsion steel, PCC and
  starter-bar details are typical notes, not designed. Beams carry the same bars at supports and mid-span.
- One typical floor layout is drawn (the design uses one plan beam layout for all storeys).
- DXF sheets are in paper millimetres (plot 1:1), not real-world coordinates.

## Quantities and costs

- Estimates with fixed unit rates, allowances and nominal mix proportions; concrete overlaps (beam/slab/column) not deducted; BBS covers one typical floor.

## Verification status

- Most engineering calculations are **UNVERIFIED** against an independent engineer or authoritative references; see [../verification/verification-matrix.md](../verification/verification-matrix.md).
- Tabulated code values were transcribed and must be checked against the printed standards ([standards-register.md](standards-register.md)).

## Operational

- Site Tools results are arithmetic on the design or on data you enter (approved mix, cube results, sensor records, survey); StructOptima does not judge acceptance, damage or repairs.
- The 3D viewer shows the designed members as boxes (no openings, reinforcement or stairs; no collision in walk-through).
- IFC export places footings directly below the column base (founding level not designed) and uses one beam/slab layout for every storey.
