# V1 Plan — robotics-skills-benchmark

> **What this document is.** The canonical, in-repo description of V1: what it is, why it exists, what completes it, and how it gets built. The structured task list lives separately at [`docs/v1-tasks.md`](v1-tasks.md). The original off-repo plan at `~/.claude/plans/i-want-to-conduct-federated-stream.md` is the *historical* approved plan; this document is the *current* canonical version (some constraints have been refined via ADRs since).
>
> **Last updated:** 2026-05-03.

---

## Overview

V1 ships the smallest viable end-to-end loop: one plugin version produces an experiment-design artifact for one task; the harness scores it; a second plugin version produces a measurable score delta against the same task. After V1, the loop has *demonstrably closed* — every later phase scales the same loop.

The deliverable of V1 is **the loop itself**, not coverage of every robotics activity. Coverage expands across Phases 3+ on top of the validated loop.

## Goals

V1 is achieved when **all** of the following are true:

1. A single experiment run completes end-to-end, producing a `result.json` that is readable, complete, and reproducible by re-running the same command.
2. Three baseline runs at plugin tag `v0.1.0` produce a measurable score variance (stdev) that is recorded in `analysis/baseline-v0.1.0.md`.
3. A plugin tag `v0.2.0` (one new skill + one new hook) re-runs the same task and produces an `analysis/reports/<date>_v0.1.0_vs_v0.2.0.md` whose delta is honestly classified as signal or noise (delta > 1× pooled stdev = signal; ≤ = noise, reported as such).
4. The repo stays under 50 MB; no vendored task code; all task references via URL+SHA per ADR-0001.

Goal #3 is the heart of V1: it proves the feedback loop closes, not just that the runner runs.

## Scope (in / out)

### In V1

- **One activity:** experiment design (the activity where general-purpose plugins are weakest, per the spec).
- **One task instance:** `diffbot-experiment-design` against `ros-controls/ros2_control_demos@humble` (`example_2`, DiffBot mock-hardware kinematic-integration invariant). See ADR-0007.
- **One verification method:** rubric (LLM judge with N=3 trials, mean+stdev) plus automated metrics (`out_of_scope_file_count`, `files_modified`, runtime).
- **Two plugin versions:** `v0.1.0` (unmodified fork as baseline) and `v0.2.0` (one new skill + one new hook).
- **One sim engine field value:** `none` (mock hardware via ros2_control). Gazebo is reinstated as the baseline from Phase 3 onward — see ADR-0007.

### Out of V1 (deferred)

- Test-pass scoring → Phase 3.
- Sim-metric scoring → Phase 4+ when sim-metric tasks land.
- Multi-task suites → V2+.
- Sub-agents → V2+.
- Hardware classes beyond UGV → V2+.
- Activities beyond experiment-design → Phase 3 (debugging) and Phase 4 (spec/planning) per ADR-0004.
- Any actual sim run → V1 is design-only; the agent writes `EXPERIMENT.md`, nothing executes.

## Architectural decisions referenced

V1 is built on the architectural decisions recorded in `docs/decisions/`. Cliff-notes:

| ADR | Relevance to V1 |
|---|---|
| [0001](decisions/0001-three-surface-repo-topology.md) | Three-surface topology + URL+SHA task references; reproducibility tuple `(plugin_sha, base_sha, schema_version, run_id)` |
| [0002](decisions/0002-git-worktrees-for-parallel-runs.md) | Per-(plugin_tag, task_id, run_id) worktrees; full triple in path to prevent collisions |
| [0003](decisions/0003-hybrid-scoring.md) | Three signals: automated + LLM-judge rubric (N=3) + human spot-check 1-in-5 |
| [0004](decisions/0004-v1-staged-activities.md) | V1 ships only experiment-design; debugging is Phase 3, spec/planning Phase 4 |
| [0005](decisions/0005-one-change-per-plugin-tag.md) | One logical change per tag; refactor-only tags as harness sanity checks |
| [0006](decisions/0006-headless-claude-code-for-runner-and-judge.md) | Headless `claude -p` for both runner and judge; `--tools` for hard whitelist (not `--allowedTools`); `--max-turns` ceiling |
| [0007](decisions/0007-v1-sim-engine-relaxation.md) | V1 `sim_engine` relaxed to "any runnable ROS 2 / mock hardware OK"; humble branch pinned |

These are **frozen** for V1. Reversal requires a new superseding ADR.

## Phased approach

V1 is delivered across two phases. Phases 3 and 4 (debugging, spec/planning) are post-V1 but listed because they validate that the loop generalizes beyond the V1 task type — and they are explicitly in the user's roadmap.

### Phase 1 — Foundation *(target: ~4 weeks; ~3 weeks elapsed)*

Build the harness, define the V1 task, run a 3-trial baseline at the unmodified plugin (`v0.1.0`).

**Phase 1 outputs:**
- Task instance schema + validator (`tasks/schema.yaml`, `harness/validate_task.py`)
- V1 task instance (`tasks/instances/diffbot-experiment-design/`)
- Experiment runner (`harness/run_experiment.py`)
- Scope check + rubric scorer (`harness/scope_check.py`, `harness/score_rubric.py`)
- Three baseline runs at `v0.1.0` with variance documented (`analysis/baseline-v0.1.0.md`)

**Phase 1 ends at Checkpoint A:** the loop runs end-to-end against the unmodified plugin; a real `result.json` exists with rubric scores; variance is measured.

### Phase 2 — First plugin iteration *(target: ~2 weeks after Checkpoint A)*

Most of this work happens in the **plugin repo** (`elliewlh2094/robotics-agent-skills`), not in this repo.

**Phase 2 outputs:**
- Plugin restructured to phase folders, tagged `v0.1.1` (refactor only, no behavior change). This serves as a harness sanity check — re-running the V1 task should produce scores within 1 stdev of `v0.1.0`.
- New skill: `design-robotics-experiment` (added to plugin under `skills/verify/`).
- New hook: `pre-commit-scope-check` (reads `BENCHMARK_SCOPE_FILES` env var; rejects out-of-scope edits).
- Plugin tagged `v0.2.0` with skill + hook.
- Three runs at `v0.2.0`, comparison report (`analysis/reports/<date>_v0.1.0_vs_v0.2.0.md`).

**Phase 2 ends at Checkpoint B:** v0.1.0 vs v0.2.0 measured on the same task; delta is signal-or-noise, classified honestly. **This is the V1 completion gate.**

### Phase 3 — TDD + debugging task type *(post-V1; target: ~2 weeks after Checkpoint B)*

Adds the test-pass scoring path. Reinstates Gazebo as the criterion (V1 sim_engine relaxation does not propagate per ADR-0007).

### Phase 4 — Spec + planning task type *(post-V1; target: ~2 weeks after Checkpoint C)*

Adds rubric-typed spec/planning tasks. Reuses `score_rubric.py`. Final V1-selected activity per ADR-0004 lands here.

## V1 success criteria (the gate)

V1 is *complete* (Checkpoint B passed) when all of these hold:

- [ ] `result.json` for `(v0.1.0, diffbot-experiment-design, baseline-1)` exists, validates against the canonical schema (per [ADR-0008](decisions/0008-canonical-result-json-schema.md); see [`docs/result-json-reference.md`](result-json-reference.md) for field definitions), and contains: rubric scores (mean ± stdev across N=3 judge trials), automated metrics (scope-check counts, files modified, runtime), audit trail (`transcript.md`, `diff.patch`), and the reproducibility tuple `(plugin_sha, base_sha, schema_version, run_id)`.
- [ ] Three baseline runs at `v0.1.0` exist; cross-run variance is documented in `analysis/baseline-v0.1.0.md`.
- [ ] Plugin tag `v0.2.0` exists in `elliewlh2094/robotics-agent-skills` with one new skill and one new hook (one logical change per tag per ADR-0005, but skill+hook are coupled here — release notes will document the coupling).
- [ ] Three runs at `v0.2.0` exist; comparison report at `analysis/reports/<date>_v0.1.0_vs_v0.2.0.md` reports per-dimension delta and pooled stdev, with explicit classification of signal vs. noise.
- [ ] The repo is under 50 MB. No vendored task code. All references via URL+SHA.

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Rubric scorer is too noisy → can't tell signal from noise | High | N=3 trials per (plugin, task), report mean ± stdev. Checkpoint B explicitly checks delta vs. pooled stdev — if too noisy, fix harness before continuing |
| Building harness consumes everything; no plugin work happens | High | Phase 1 hard-capped at 5 tasks (~4 weeks); Phase 2 ships v0.2.0 within 6 weeks of project start |
| Plugin and harness drift out of sync | Medium | Plugin SHA recorded in every result.json (per ADR-0001); harness verifies plugin loaded matches expected before running |
| External task repo disappears or rebases | Medium | All references include commit SHA, not branch. Fetch failure aborts loudly; no silent corruption |
| User-as-spot-checker becomes bottleneck | Medium-High | LLM judge for routine scoring; human spot-check 1-in-5 (per ADR-0003); spot-check only flagged-suspicious results in V1 |
| Claude Code `--tools` syntax differs from what we assume | Low | Smoke-test the runner against the V1 task with `v0.1.0` before declaring T1.5 done. Failure here means a one-line flag fix, not a redesign |
| Plugin v0.2.0 changes don't move the score | Medium | This is itself a finding — ADR-0003 commits to honest reporting of zero-effect deltas. The next iteration targets a different gap rather than tweaking v0.2.0 indefinitely |

## Open questions

These are tracked here to prevent loss; resolution may happen during execution rather than upfront.

- **Q1.** What's the exact rubric output schema in practice? `score_rubric.py` (T1.4) has to subprocess `claude -p` and parse the JSON the judge returns. The rubric defines the *target* schema, but the judge may return text that needs JSON-mode validation. Plan: use `--json-schema` flag on the judge invocation to enforce the structure.
- **Q2.** What happens at Checkpoint A if all three baseline runs produce identical scores (zero stdev)? That would be too good to be true and suggests the judge is collapsing to a deterministic answer. Plan: investigate before treating the result as valid baseline.
- **Q3.** Should the v0.1.1 refactor-only tag re-run *all* three baseline trials, or just one? Re-running all three lets us compare distributions. Cheaper alternative: one re-run, expect within 1 stdev. Going with the cheaper option for V1; revisit if score noise is high.
- **Q4.** Does Claude Code's `--tools` flag syntax accept comma-separated, space-separated, or both? Help text shows comma example; the `<tools...>` notation is ambiguous. T1.5 will surface this.
