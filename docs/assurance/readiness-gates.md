# Production-Readiness Gates

**As of:** 2026-10-21. A feature is production-ready only when every gate has passed; none of the gates replaces
the review of a qualified structural engineer (gate H). Status values: **PASSED** (evidence recorded), **PARTIAL**,
**FAILED**, **BLOCKED** (needs an outside decision or input), **NOT VERIFIED**.

**Overall: NOT production-ready.** StructOptima is a preliminary design aid (CLAUDE.md). Gate H has not been started,
gate D is partial, and several code checks are not performed (KD-24, KD-28).

| Gate | What it requires | Status | Evidence | What is missing |
|---|---|---|---|---|
| A Requirements | Requirements, assumptions, supported inputs and acceptance criteria documented and traceable | PARTIAL | [standards register](../engineering/standards-register.md), [calculation catalogue](../engineering/calculation-catalogue.md), [assumptions](../engineering/assumptions-register.md), [supported inputs](../engineering/supported-inputs.md), [verification matrix](../verification/verification-matrix.md), decision log D-01..D-41 | Owner requirements for high-rise, ductile detailing and effective length (D-04 BLOCKED); acceptance tolerances against a reference program (D-08 not made) |
| B Implementation | Code paths inspected and reviewed | PARTIAL | Module catalogue, 2026-10 audits (R1-R27, N1-N64), this session's review of the DXF / analysis / output paths | Line-by-line review of `report_gen`, `visualizer`, `quantifier`, `bbs_module` not repeated since 2026-10-15 |
| C Automated tests | Unit, integration, regression and boundary tests pass | PASSED (for what is tested) | `python tests/run_suite.py`: see [verification results](../verification/verification-results.md); DXF corpus, design matrix, metamorphic, invariants | Coverage gaps A1-A10 in the [test inventory](../verification/test-inventory.md) |
| D Engineering validation | Critical calculations independently verified | PARTIAL | SP 16 examples, closed-form FEA, worked hand check of one building, printed-standard check of 2026-10-20 | Comparison with a reference program (ETABS / STAAD) for a multi-storey building; wind, footing, BBS and quantity hand checks |
| E Model consistency | Geometry, connectivity, loads, results, schedules and reports satisfy the invariants | PASSED (for tested inputs) | `tests/invariants.py` on every corpus / matrix design; output tests in `test_dxf_corpus.py` | Invariants on report text beyond the status banner |
| F Resource safety | Representative workloads within limits; memory behaviour investigated | PASSED | N50 root cause (OOM) fixed and locked by a memory-capped test; per-file peak <= 340 MB; largest corpus building 2.4 s | Scaling beyond 130 columns not measured |
| G Output quality | Deliverables accurate, consistent, traceable, professionally presented | PARTIAL | Status banner and failure list in every report (D-09); non-finite values never printed (D-38) | Professional review of the drawing set and reports (KD-20, KD-21) |
| H Independent review | Qualified engineering review of safety-critical requirements | NOT STARTED (BLOCKED) | — | A licensed structural engineer must review the design rules, the decisions marked "engineer review pending" and the reference cases |
