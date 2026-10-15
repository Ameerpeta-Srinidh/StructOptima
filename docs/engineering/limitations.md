# Limitations

**As of:** 2026-10-15. Read this before relying on any StructOptima output.

## Scope

- Regular, low-rise RC moment frames with rectangular columns and beams on orthogonal grid lines.
- Outputs are **preliminary**. Every result requires independent verification by a licensed structural engineer. Reports carry a "PRELIMINARY — NOT FOR CONSTRUCTION" banner.

## Analysis

- Independent 2D plane frames along grid lines; beams off grid lines are designed as simply supported (warning).
- No torsion, accidental eccentricity, diaphragm flexibility, P-Δ or second-order analysis.
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

## Quantities and costs

- Estimates with fixed unit rates, allowances and nominal mix proportions; concrete overlaps (beam/slab/column) not deducted; BBS covers one typical floor.

## Verification status

- Most engineering calculations are **UNVERIFIED** against an independent engineer or authoritative references; see [../verification/verification-matrix.md](../verification/verification-matrix.md).
- Tabulated code values were transcribed and must be checked against the printed standards ([standards-register.md](standards-register.md)).

## Operational

- The Drawings page writes DXF files into the current working directory each time it renders (overwrites tracked `Beam_Schedule.dxf` and `Foundation_Plan_Professional.dxf` when run from the repository root).
- `ifcopenshell` is optional and not listed in `requirements.txt`.
