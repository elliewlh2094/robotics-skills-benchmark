# ADR-0004: V1 stages user-selected activities one per phase

## Status
Accepted

## Date
2026-05-02

## Context

The user selected three V1 activities to prioritize: experiment-design, debugging, and spec/planning. A literal interpretation — "ship all three at V1" — would require building three different scoring paths (rubric for experiment-design and spec/planning; test-pass for debugging) plus their respective task instances and per-task Dockerfiles before any complete loop closes.

That bundles ~12 weeks of harness work before the first end-to-end measurement is possible. The risk: by the time something runs, much of the early infrastructure has been built against guesses rather than measurements. V1's actual deliverable is *the loop closing reliably*, not breadth of coverage.

## Decision

V1 ships **only experiment-design** end-to-end. The other two user-selected activities are scheduled across subsequent phases:

| Phase | Activity added | Verification | Plugin tag |
|---|---|---|---|
| V1 (Phases 1–2) | experiment-design | rubric | v0.2.0 |
| Phase 3 | debugging | unit-test | v0.3.0 |
| Phase 4 | spec/planning | rubric | v0.4.0 |

Each phase introduces one new task type, one new plugin tag (skill/hook), and one comparison report. By Checkpoint D (end of Phase 4), all three user-selected activities have a measured baseline-vs-latest score in `analysis/reports/`.

## Alternatives Considered

### Ship all 3 activities at V1
- **Pros:** Honors user's stated priority literally.
- **Cons:** ~12-week pre-result horizon with no validation along the way; high risk of building wrong abstractions.
- **Rejected.**

### Ship 2 activities at V1
- **Pros:** Slightly broader coverage.
- **Cons:** Awkward middle ground — neither rubric-only nor test-pass-only; both scoring paths must work before any loop closes.
- **Rejected.**

### Ship debugging first (more SWE-bench-like)
- **Pros:** Test-pass scoring is well-understood; smaller harness investment.
- **Cons:** Abandons the user's primary differentiator (experiment-design — the activity that exposes general-purpose plugins' shallowness most clearly).
- **Rejected.**

## Consequences

- ✅ V1 loop closes in ~4 weeks instead of ~12.
- ✅ Phase 2 (first plugin iteration with measurement) lands within ~6 weeks.
- ✅ All three user-selected activities measured by end of Phase 4 (~10–12 weeks).
- ✅ Each phase's added scoring path is validated against a baseline before plugin work — incremental harness validation.
- ⚠️ User must accept a slower-but-firmer V1 over a broader-but-riskier V1.
- ⚠️ Cross-activity comparisons (e.g., "is plugin v0.3.0 generally better, or only on debugging?") must wait until Phase 4 ends.

## Related ADRs

- ADR-0003 (hybrid scoring) — the rubric path is exercised first; test-pass path joins in Phase 3.
- ADR-0007 (V1 sim_engine relaxation) — narrows V1 further to make the loop close faster.
