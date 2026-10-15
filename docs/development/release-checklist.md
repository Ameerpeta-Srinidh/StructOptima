# Release Checklist

**As of:** 2026-10-15. No release has been approved under this checklist.

## Mandatory before any release

- [ ] Full test suite passes locally with the side-effect-free command and in CI on 3.11, 3.12, 3.13 (record run IDs).
- [ ] `git status` shows no files written by tests.
- [ ] [risk-register.md](../assurance/risk-register.md): every C/H item has a decision; none is described as resolved without engineer review.
- [ ] [decision-log.md](../assurance/decision-log.md): D-02, D-03, D-04, D-05, D-06 approved or explicitly deferred by the owner.
- [ ] Standards register values checked by an engineer, or the release notes state they are unverified.
- [ ] UI shows the PRELIMINARY banner and the design status; PDFs show "NOT FOR CONSTRUCTION".
- [ ] README and docs index updated (dates, test counts, status).
- [ ] Remediation log lists every change since the previous release.
- [ ] Manual smoke test: manual grid, one DXF, one IFC (if supported), all pages, all downloads.

## Engineering sign-off (required before any claim beyond "preliminary")

- [ ] Benchmarks B3–B13 completed with a named reviewer ([benchmark-plan.md](../verification/benchmark-plan.md)).
- [ ] Verification matrix updated to evidence level 5 for the claimed scope.
- [ ] Reviewer name, date and scope recorded here.

| Release | Date | Tests | Reviewer | Scope claimed |
|---|---|---|---|---|
| — | — | — | — | — |
