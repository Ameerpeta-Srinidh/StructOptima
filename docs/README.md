# StructOptima — Documentation Index

**Status date:** 2026-10-16
**Applies to:** `main` after the 2026-10-16 work (see [../CHANGELOG.md](../CHANGELOG.md) for every change)

StructOptima is a Python / Streamlit tool that generates and checks a
**preliminary** reinforced-concrete frame design (columns, beams, slabs, a
staircase flight and isolated footings) from manual dimensions, a DXF plan or
an IFC model, and produces schedules, quantities and PDF / Excel / DXF outputs.
It references IS 456:2000, IS 1893 (Part 1):2016, IS 875 and IS 13920:2016 but
is **not** a certified code-compliance tool. Every output requires independent
verification by a licensed structural engineer.

> The previous content of this file (a duplicate of the product README) is
> superseded and remains available in git history (`git show ee7223e:docs/README.md`).

## Current documented status (summary)

| Area | Status | Where |
|---|---|---|
| Architecture & data flow | Documented from source | [architecture/](architecture/system-overview.md) |
| Engineering calculations | Catalogued; most `UNVERIFIED` against an independent engineer; FEA and several section checks `VERIFIED_FOR_CASES` | [engineering/calculation-catalogue.md](engineering/calculation-catalogue.md), [verification/verification-matrix.md](verification/verification-matrix.md) |
| Audit findings R1–R27 + N1–N22 | Code changes made for most; **none** marked resolved without engineer review | [assurance/risk-register.md](assurance/risk-register.md) |
| Test suite | 520 passed, 3 skipped, 0 failed (executed 2026-10-16) | [verification/verification-results.md](verification/verification-results.md) |
| Standards clause wording | **Not verified against printed standards** | [engineering/standards-register.md](engineering/standards-register.md) |

## Start here

- **Using the app (site engineers, owners):** [user-guide.md](user-guide.md)
- **What changed and why:** [../CHANGELOG.md](../CHANGELOG.md)
- **Gap analysis against the engineering mandate and roadmap:** [assurance/gap-analysis.md](assurance/gap-analysis.md)
- **Checking the calculations by hand:** [verification/manual-calculation-walkthrough.md](verification/manual-calculation-walkthrough.md)

## Recommended reading order (new developer)

1. [architecture/system-overview.md](architecture/system-overview.md) — what runs where
2. [architecture/execution-flows.md](architecture/execution-flows.md) — app / CLI / CAD / IFC flows and failure paths
3. [engineering/limitations.md](engineering/limitations.md) — **read before trusting any output**
4. [engineering/calculation-catalogue.md](engineering/calculation-catalogue.md) and [engineering/units-and-conventions.md](engineering/units-and-conventions.md)
5. [architecture/interfaces-and-contracts.md](architecture/interfaces-and-contracts.md) and [architecture/data-models.md](architecture/data-models.md)
6. [verification/test-execution-guide.md](verification/test-execution-guide.md) and [development/setup.md](development/setup.md)
7. [assurance/risk-register.md](assurance/risk-register.md) and [assurance/decision-log.md](assurance/decision-log.md)

## All documents

**Architecture**
- [system-overview.md](architecture/system-overview.md)
- [repository-inventory.md](architecture/repository-inventory.md)
- [module-catalogue.md](architecture/module-catalogue.md)
- [dependency-map.md](architecture/dependency-map.md)
- [execution-flows.md](architecture/execution-flows.md)
- [data-models.md](architecture/data-models.md)
- [interfaces-and-contracts.md](architecture/interfaces-and-contracts.md)

**Engineering**
- [calculation-catalogue.md](engineering/calculation-catalogue.md)
- [units-and-conventions.md](engineering/units-and-conventions.md)
- [assumptions-register.md](engineering/assumptions-register.md)
- [standards-register.md](engineering/standards-register.md)
- [standards-to-obtain.md](engineering/standards-to-obtain.md) — IS codes and high-rise inputs the owner must provide
- [limitations.md](engineering/limitations.md)

**Verification**
- [test-inventory.md](verification/test-inventory.md)
- [verification-matrix.md](verification/verification-matrix.md)
- [benchmark-plan.md](verification/benchmark-plan.md)
- [test-execution-guide.md](verification/test-execution-guide.md)
- [verification-results.md](verification/verification-results.md)
- [manual-calculation-walkthrough.md](verification/manual-calculation-walkthrough.md) — how to check every output by hand, worked for a whole building

**Assurance**
- [risk-register.md](assurance/risk-register.md)
- [known-defects.md](assurance/known-defects.md)
- [decision-log.md](assurance/decision-log.md)
- [remediation-log.md](assurance/remediation-log.md)

**Development**
- [setup.md](development/setup.md)
- [developer-workflow.md](development/developer-workflow.md)
- [troubleshooting.md](development/troubleshooting.md)
- [release-checklist.md](development/release-checklist.md)

**Legacy documents (moved to [legacy/](legacy/) on 2026-10-16; partly outdated — see banners inside)**
- [engineering_basis.md](legacy/engineering_basis.md), [api_reference.md](legacy/api_reference.md),
  [installation.md](legacy/installation.md), [user_guide.md](legacy/user_guide.md), [risk_management.md](legacy/risk_management.md)
- Earlier write-ups: `legacy/Extended_Structural_Calculation_Reference*`, `legacy/structural_calculations_manual.md`,
  `legacy/StructOptima_*.pdf/.docx`, `legacy/Structural_DXF_Translation.pdf`

## Critical known limitations (short list)

Full list: [engineering/limitations.md](engineering/limitations.md).

- 2D plane frames along grid lines; **no torsion / accidental eccentricity**, no P-Δ, no response spectrum analysis.
- IS 13920 ductile detailing is **not** designed (end-zone spacing only); R = 5 (SMRF) is therefore not justified by the tool.
- Tabulated code values (τc, τc,max, Table 26 coefficients, steel stress–strain, spectra) were transcribed and **need checking against the printed standards**.
- Column effective length factor is 1.0 by default (engineering decision required, IS 456 Annex E).
- Footing sizing ignores base moments (flagged as a warning only); no combined footings, piles or rafts.
- Quantities and costs are estimates with fixed rates and allowances.

## Status vocabulary

| Status | Meaning |
|---|---|
| `NOT_ASSESSED` | Not looked at |
| `IN_PROGRESS` | Work started, not complete |
| `UNVERIFIED` | Implemented / changed, no independent evidence |
| `VERIFIED_FOR_CASES` | Matches an independently derived reference for the listed cases only |
| `CONFIRMED_DEFECT` | Defect reproduced, not yet changed |
| `BLOCKED` | Needs a decision / information not available |
| `RESOLVED_WITH_EVIDENCE` | Fixed **and** reviewed by a qualified engineer with documented evidence (none so far) |

## Documentation coverage matrix

| Source area | Inventory | Module catalogue | Flows | Calculations | Tests mapped |
|---|---|---|---|---|---|
| `app.py`, `main.py`, `pages/` | Yes | Yes | Yes | n/a | UI smoke tests |
| Production analysis/design (`src/design_pipeline.py`, `analysis_integration`, `fea_solver`, `section_design`, `rebar_detailer`, `grid_manager`, `foundation_eng`, `seismic`, `wind_load`, `load_combinations`) | Yes | Yes | Yes | Yes | Yes |
| Checks (`audit`, `stability`, `safety_warnings`, `optimizer`, `risk_management`) | Yes | Yes | Yes | Yes | Partial |
| Ingest (`cad_parser`, `cad_loader`, `auto_framer`, `column_placer`, `beam_placer`, `column_editor`, `bim_loader`) | Yes | Yes | Yes | Geometry only | Partial |
| Quantities / outputs (`quantifier`, `wall_calculator`, `bbs_*`, `report_gen`, `exporters`, `dxf_exporter`, `visualizer`) | Yes | Yes | Yes | Summary only | Partial |
| Test-only / unused modules | Yes | Yes (marked) | n/a | Summary | Existing tests |

## Incomplete or unverified sections

- Clause-level wording of every cited standard (see [standards-register.md](engineering/standards-register.md)).
- Masonry / plaster / paint quantity rules in `wall_calculator.py` and `report_gen.py` — catalogued at summary level only.
- `auto_framer.py`, `column_placer.py`, `beam_placer.py` placement heuristics — documented at interface level; placement quality unverified.
- `dxf_exporter.py`, `geometry_exporter.py`, `visualizer.py` drawing correctness — not assessed.
- Site tools (`site_*`, `shm_*`, `digital_twin`, `bim_interop`, `documentation`) — inventoried; behaviour not assessed.
