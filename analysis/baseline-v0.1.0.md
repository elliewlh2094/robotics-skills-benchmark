# Baseline analysis: plugin `v0.1.0` on `diffbot-experiment-design`

> **What this document is.** The post-T1.5 noise-floor analysis for the
> unmodified plugin fork. The pooled stdev recorded here is the noise floor
> against which Phase 2's plugin delta would have been judged.
>
> **Status:** ⚠️ **Phase 2 calibration gate TRIGGERED.** Do not proceed to T2.1
> until the rubric is calibrated. See "Phase 2 gate decision" below.
>
> **Date:** 2026-05-05.

---

## Identity tuple (per ADR-0001)

| Field | Value |
|---|---|
| plugin_tag | `v0.1.0` |
| plugin_sha | `15edc81965fb511a0b91913523d5d77917fc4611` |
| plugin source | `https://github.com/elliewlh2094/robotics-agent-skills` (local checkout, tag created 2026-05-05) |
| task_id | `diffbot-experiment-design` |
| base_repo / base_sha | `ros-controls/ros2_control_demos` @ `c555233658e8c0794f9bb6e1ea4059ca84bcd503` |
| run_ids | `baseline-1`, `baseline-2`, `baseline-3` |
| n_trials per run | 3 (per ADR-0003) |
| total trials pooled | 9 |

All three runs passed the per-run gate: `status: success`, `EXPERIMENT.md`
produced (in scope), `plugin_sha` matches, `judge_calls == 3`,
`out_of_scope_file_count == 0`.

---

## Wall-clock and cost (agent runs only; judge cost not yet captured — see TODO.md issue 5)

| Run | Runtime (s) | Agent cost (USD) |
|---|---|---|
| baseline-1 | 154.9 | $0.4817 |
| baseline-2 | 173.0 | $0.4790 |
| baseline-3 | 163.4 | $0.4677 |
| **Total** | **491.4 s (8.19 min sequential)** | **$1.4283** |

Cost per run: $0.476 mean ($0.4677 – $0.4817 range). Stable across runs;
no anomalous outliers in agent cost or runtime.

---

## Within-run rubric (per-run, N=3 judge trials)

| Run | overall_mean | overall_stdev |
|---|---|---|
| baseline-1 | 3.00 | 0.00 |
| baseline-2 | 3.00 | 0.00 |
| baseline-3 | 3.00 | 0.00 |

---

## Cross-run pooled rubric (9 trials = 3 runs × 3 trials)

This is the canonical noise-floor measurement.

| Dimension | mean | stdev | min | max |
|---|---|---|---|---|
| controlled_variables | 3.00 | 0.0000 | 3 | 3 |
| failure_modes | 3.00 | 0.0000 | 3 | 3 |
| hypothesis_statement | 3.00 | 0.0000 | 3 | 3 |
| recorded_signals | 3.00 | 0.0000 | 3 | 3 |
| repo_grounding | 3.00 | 0.0000 | 3 | 3 |
| success_thresholds | 3.00 | 0.0000 | 3 | 3 |
| visualization_plan | 3.00 | 0.0000 | 3 | 3 |
| **overall** | **3.00** | **0.0000** | **3** | **3** |

Between-run stdev (variance of the three run-level overall means):
**0.0000**.

The judge gave the maximum grade on every dimension on every trial. Across
9 independent judge invocations on three different agent runs, the rubric
showed zero variance.

---

## Phase 2 gate decision: **PAUSED**

Per the calibration gate (see saved feedback
`feedback_phase2_rubric_calibration_gate.md`):

> if all three formal baseline tests still produce perfect scores and zero
> standard deviation, Phase 2 should be paused, and we should calibrate the
> scoring standards first.

The condition is satisfied. **Do not advance to T2.1** until calibration
work is done.

### Why this matters

Phase 2's whole purpose is to detect a measurable plugin delta against a
noise floor (per ADR-0003 and T1.5). With a saturated 3.0 ceiling and zero
variance:

1. **No headroom.** The rubric cannot show plugin-induced improvement —
   only degradation. T2.1 (refactor-only tag, expected score "within 1×
   pooled stdev of v0.1.0") is meaningless when the bound is zero, and T2.4
   (the new design-skill plugin) cannot register as "improved."
2. **No measured noise floor.** A non-zero Phase 2 delta would be
   "statistically significant" only in a degenerate sense — you cannot
   distinguish signal from noise when the measured noise is zero.
3. **Three independent confounds remain unseparated.** A 3.0/0.0 result is
   consistent with at least three causes:
   - (a) The agent (Opus 4.7 [1m]) genuinely produced a perfect plan against
     a 0–3 rubric.
   - (b) The rubric's grade-3 anchors are too easy to clear; any
     well-formed plan saturates.
   - (c) The judge (also Claude) is generous to itself; an independent
     model would grade differently.

### Calibration directions to consider (not prescriptive)

Listed roughly easiest-to-hardest. Pick the cheapest set that breaks
saturation; revisit the rest only if the cheap fixes don't.

1. **Tighten grade-3 anchors in `rubric.md`.** Make grade 3 mean
   "publishable in a robotics methods note" rather than "plausible." Raise
   the bar on each dimension (e.g., `repo_grounding` grade-3 requires line
   numbers AND demonstrating non-obvious code interactions, not just
   citations).
2. **Add discriminating dimensions.** The current 7 dimensions are all
   dimensions a competent draft satisfies. Add at least one that requires
   *specific reasoning* not present in our agent's output (e.g., "discusses
   how the proposed bound would behave under update-rate doubling," or "an
   anti-failure-mode that would be missed by a naïve checklist-followers").
3. **Adversarial judge prompt.** Currently the judge defaults to
   summarization+grade. Switch to "find the strongest disqualifying
   weakness, then grade." Forces grade-3 to mean "no disqualifying
   weakness," not "passes a checklist."
4. **Cross-model judging.** Use Claude Haiku as a second judge alongside
   Opus, or vice versa; saturation that disappears under a different judge
   model is evidence for cause (c) above.
5. **Blind comparison against a deliberately-flawed plan.** Inject a
   reference deliverable known to be poor (omit failure-modes, hand-wave
   thresholds, no repo grounding). If the rubric grades it ≥ 2.0, the
   anchors are demonstrably miscalibrated.

The cheapest+most informative is (1)+(5) together: tighten anchors, then
verify the new anchors discriminate by feeding in a known-bad plan. That
gives a falsifiable check on calibration *before* re-running the baseline.

### What re-running the baseline looks like after calibration

After calibration changes, the noise floor must be re-measured. The
re-run uses fresh `run_ids` (e.g., `baseline-c1-1`, `baseline-c1-2`,
`baseline-c1-3` — the `c1` denotes calibration revision 1) so the v0.1.0
runs above remain on disk for forensic comparison. The rubric file change
is a calibration revision, not a plugin change, so plugin_tag stays
`v0.1.0`.

---

## Forensics retained

All three `experiments/2026-05-04_v0.1.0_diffbot-experiment-design_baseline-{1,2,3}/`
directories remain on disk with `result.json`, `transcript.md`, and
`diff.patch` for each. The agent's three EXPERIMENT.md drafts (one per
run, all schema-passing 3.0/0.0) are preserved in their respective
`diff.patch` files for use during anchor-tightening (cause-(b)
investigation): re-grading the same outputs against a stricter rubric is
the cheapest first calibration test.

---

## Process notes (for future T-baseline analyses)

Two harness gaps surfaced during this T1.5 cycle that are worth fixing
before the next baseline cycle (post-calibration or otherwise):

1. **Judge cost not in `result.json`.** `score_rubric.py` discards the
   `total_cost_usd` and `usage` fields from each judge subprocess. We have
   `judge_calls: 3` (count) but no per-call cost. Tracked as TODO.md issue
   5. Fix before any larger-scale calibration sweep that re-grades many
   deliverables.
2. **Transcript only captures the agent run.** Judge-call transcripts are
   not persisted; if a judge gives an unusual rationale we can't reread it
   later (the per-trial rationale field in `result.json` has the text,
   but no other context). Fine for now — `result.json.scoring.rubric_scores.per_trial[].rationale`
   is enough for cause-(b) investigation.

Neither blocks calibration work; both are about making post-calibration
analysis cheaper.
