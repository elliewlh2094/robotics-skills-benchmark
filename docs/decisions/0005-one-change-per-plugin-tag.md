# ADR-0005: One logical change per plugin tag

## Status
Accepted

## Date
2026-05-02

## Context

The whole point of the benchmark is to attribute score deltas to specific plugin changes — to answer questions like "did adding the `design-robotics-experiment` skill actually improve scores, or was it the hook?" If a plugin tag bundles multiple changes (3 skills + 2 hooks), a positive score delta is unattributable, and the benchmark produces no actionable signal for the next iteration.

This is also true for *negative* deltas: a regression in a bundled tag could be caused by any of the bundled items, requiring a bisect across multiple potential offenders.

Refactor-only changes have a separate role: re-running a baseline against a refactor-only tag should produce scores within 1× pooled stdev. If it doesn't, the harness has hidden coupling to plugin structure (e.g., the rubric is implicitly grading file-path conventions). Without dedicated refactor-only tags, this kind of harness drift goes undetected.

## Decision

Every plugin tag carries **exactly one logical change**:
- one new skill, OR
- one new hook, OR
- one bugfix to an existing skill or hook, OR
- a pure refactor (no behavior change).

Patch bumps (`v0.X.Y → v0.X.Y+1`) are cheap; bundling changes into a single tag is forbidden. If multiple changes are ready simultaneously, tag them sequentially:
- v0.1.0 = baseline
- v0.1.1 = refactor only (sanity check)
- v0.2.0 = +new skill
- v0.2.1 = +new hook
- ...

Each new tag must be re-run against the affected task(s) before the *next* tag is created.

## Alternatives Considered

### Free-form release boundaries (semver as practiced)
- **Pros:** Conventional; lower per-change overhead.
- **Cons:** Makes the benchmark useless as a measurement instrument; defeats the entire iterative-improvement goal.
- **Rejected.**

### Per-feature branches with delayed merging
- **Pros:** Branch-level isolation.
- **Cons:** Same problem as bundling — merge windows tend to combine multiple branches; the merge commit is a bundle.
- **Rejected.**

### Multi-change tags with explicit "what's in this tag" notes
- **Pros:** Lower tagging overhead.
- **Cons:** Too easy to lie to ourselves about what each item contributed; the discipline collapses under deadline pressure.
- **Rejected.**

## Consequences

- ✅ Score deltas attribute cleanly to specific changes.
- ✅ Refactor-only tags serve as harness sanity checks (catches scoring drift due to plugin restructure).
- ✅ Speculative additions cannot be hidden in a feature dump — each gets its own measured run.
- ⚠️ Tag count grows quickly (potentially ~12+ tags per year of active development).
- ⚠️ Slight overhead per change: tag, run benchmark (3 trials × N tasks), write report.
- ⚠️ If a bundle-feeling change is logically inseparable (e.g., a skill that only works with a corresponding hook), document the coupling in the tag's release notes and accept attribution as joint.

## Related ADRs

- ADR-0001 (separate plugin repo) — enables clean tag history.
- ADR-0003 (hybrid scoring with N=3 trials) — gives the variance baseline against which "real" deltas are judged.
