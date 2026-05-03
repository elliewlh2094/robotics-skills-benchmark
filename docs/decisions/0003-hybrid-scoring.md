# ADR-0003: Hybrid scoring — automated metrics + LLM-judge rubric + human spot-check

## Status
Accepted. **Updated 2026-05-03:** field names listed below in the Decision section (`exit_status`, `out_of_scope_file_count`, etc.) reflect the original drafting. The canonical names are now in [`docs/result-json-reference.md`](../result-json-reference.md) per [ADR-0008](0008-canonical-result-json-schema.md): `exit_code`, `scoring.scope_check.out_of_scope_count`, `scoring.scope_check.out_of_scope_paths`, `scoring.rubric.{mean,stdev,overall_mean,overall_stdev}`. The N=3 trials + recompute-overall semantics described here are unchanged.

## Date
2026-05-02

## Context

SWE-bench's binary pass/fail model handles ~3 of the 9 target activities (debugging, perf-fix, integration-bugfix). The other 6 — refining ideas, defining specifications, planning, designing experiments, TDD design, refactoring quality — produce design artifacts (markdown, code structure, test plans) without a golden test to run.

We need a scoring model that:
- Handles non-test-pass tasks (the project's differentiator vs. SWE-bench).
- Produces *interpretable* score deltas across plugin versions, not just rankings.
- Survives at scale — pure-human scoring becomes a bottleneck within ~10 experiments.
- Detects its own drift — pure-LLM scoring is cheap but blind to systematic bias.
- Aligns with reliability criterion C2 (verifiability) — multiple corroborating signals per result.

## Decision

Each `result.json` carries up to **three signal sources**, routed by the task's `verification_method`:

1. **Automated metrics (always present):**
   - `out_of_scope_file_count`, `out_of_scope_paths`
   - `files_modified`, `runtime_s`, `exit_status`
   - `transcript_bytes`, `judge_calls` (cost proxies)

2. **LLM-judge rubric (`rubric` and `hybrid` tasks):**
   - Claude in a fresh context (no plugin loaded), given the task + agent output + rubric.
   - Returns structured JSON scoring each rubric dimension 0–3.
   - **N=3 trials with different seeds**; reports `mean`, `stdev`, and `per_trial` array.

3. **Test-pass (`unit-test` and `hybrid` tasks):**
   - SWE-bench-style FAIL_TO_PASS / PASS_TO_PASS in a per-task Docker container.

Plus: **human spot-check 1-in-5** to detect judge drift; disagreements logged in `analysis/judge-drift.md`.

## Alternatives Considered

### Pure automated scoring
- **Pros:** Cheap, reproducible, no judge-drift risk.
- **Cons:** Excludes 6 of the 9 target activities; collapses to a SWE-bench clone.
- **Rejected.**

### Pure human scoring
- **Pros:** Highest-quality signal.
- **Cons:** Bottlenecks at ~10 experiments; cannot scale to monthly cadence.
- **Rejected.**

### Pure LLM-judge scoring
- **Pros:** Cheap and scalable.
- **Cons:** Judge drift goes undetected; no second opinion. Especially risky given the judge and the agent share a model family (see ADR-0006).
- **Rejected.**

### Two-judge consensus (e.g., Claude + GPT-4)
- **Pros:** Cross-model triangulation.
- **Cons:** Doubles scoring cost; introduces a second auth surface; doesn't fix shared-model bias on reasoning patterns the user actually cares about.
- **Rejected** for now; reconsider in Phase 5+ if drift becomes the primary failure mode.

## Consequences

- ✅ Loop closes for non-test-pass tasks — the differentiating capability vs. SWE-bench.
- ✅ Variance is *measured*, not assumed. A score delta within 1× pooled stdev is reported as noise (see `docs/plugin-feedback-loop.md`).
- ✅ Multiple signals per result satisfy reliability criterion C2 (verifiability).
- ⚠️ Judge cost: N=3 trials per rubric task ≈ 3× judge LLM calls. Bounded by Max plan (see ADR-0006), so $ cost is zero, but wall-clock cost adds ~30–90 s per rubric task.
- ⚠️ Judge and agent share model family → systematic biases (e.g., over-rating verbose outputs) won't cancel. Human spot-check 1-in-5 is the only mitigation; if drift rate stays below threshold, we're fine.
- ⚠️ Rubric authoring quality directly affects scoring noise. Bad rubric → noisy scores → can't detect plugin deltas. Documented as a risk in `docs/adding-a-task.md` ("Sanity-checking a new rubric").

## Related ADRs

- ADR-0006 (headless Claude Code for runner and judge) — both signals share auth.
- ADR-0007 (V1 sim_engine relaxation) — V1's verification_method is `rubric`, so this scoring model is exercised first.
