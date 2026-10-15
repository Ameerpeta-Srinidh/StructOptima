# Limitations

**As of:** 2026-10-16. Read this before relying on any StructOptima output.

## Scope

- Regular, low-rise RC moment frames with rectangular columns and beams on orthogonal grid lines.
- Outputs are **preliminary**. Every result requires independent verification by a licensed structural engineer. Reports carry a "PRELIMINARY — NOT FOR CONSTRUCTION" banner.

## Analysis

- Independent 2D plane frames along grid lines; beams off grid lines are designed as simply supported (warning).
- No torsion, accidental eccentricity, diaphragm flexibility, P-Δ or second-order analysis.
- Storey drift is computed per column from the 2D frames (since 2026-10-16); without torsion it under-estimates drift at the flexible edge of irregular plans. Limit values are UNVERIFIED.
- Equivalent static seismic method only; buildings that exceed the cited regularity/height limits are reported as FAIL ("Seismic method"), not analysed by response spectrum.
- No orthogonal seismic combination, vertical seismic or pattern live loading.
- Column gravity axial load from tributary areas (not from frame continuity).
- Static wind only; dynamic/gust effects are flagged for tall/slender buildings but not computed; Kd, Ka, Kc, k4 taken as 1.0.
- Linear elastic with uniform cracked-section modifiers.

## Design

- IS 13920 ductile detailing is **not** designed: no confining steel (Ash), no capacity-design shear, no joint reinforcement design. Selecting SMRF (R = 5) shows a warning; the tool cannot justify R = 5.
- SCWB and joint-shear checks use simplified capacities (slab steel ignored, no column-shear deduction) and are advisory for OMRF.
- Column effective length factor 1.0 by default (no Annex E calculation).
- Beams are rectangular (no flange action); deflection checked by basic span/d ratios only (no modification factors, no long-term calculation in design; the audit uses an approximate short-term deflection).
- No curtailment, development length or lap checks in member design (tables exist in `anchorage.py`; BBS uses its own rules).
- Slabs: Table 26 coefficients (values transcribed, to be verified); no corner torsion steel; one-way slabs use wl²/8 everywhere.
- Staircase: single typical flight with a fixed geometry assumption.
- Footings: square isolated pads only; base moments not used for sizing (warning only); no combined footings, rafts, piles, uplift resistance or settlement.

## Ingest

- DXF: columns must be closed LWPOLYLINEs on layers containing COL/PILLAR/STANCHION; beams LINEs on BEAM layers; wall detection by layer keywords with fallbacks that can pick up non-structural lines (warned). Auto-framing assumes drawings in millimetres.
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
