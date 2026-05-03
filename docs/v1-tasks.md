# Implementation Plan: V1 Tasks — robotics-skills-benchmark

> **Structure follows** `agent-skills:planning-and-task-breakdown` (per-task Description / Acceptance / Verification / Dependencies / Files / Estimated scope; checkpoints between phases).
>
> Pair with [`docs/v1-plan.md`](v1-plan.md) for the narrative plan, [`docs/spec.md`](spec.md) for what+why, [`docs/decisions/`](decisions/) for canonical architectural decisions, and [`TODO.md`](../TODO.md) for the operational pointer.
>
> **Last updated:** 2026-05-03.

---

## Overview

V1 ships the smallest viable feedback loop: one plugin version produces an experiment-design artifact for one task; the harness scores it via rubric + automated metrics; a second plugin version produces a measurable, honestly-classified score delta against the same task.

This document enumerates every task across V1 (Phase 1 + Phase 2) and the post-V1 phases (3 + 4) that complete coverage of the user's three V1-selected activities. Each task is sized to fit a single focused session.

## Architecture decisions

The decisions underlying these tasks are pinned in [`docs/decisions/`](decisions/). Each phase below includes which ADRs are load-bearing for that phase.

## Task list

---

### Phase 1: Foundation *(target: ~4 weeks)*

Build the harness, define the V1 task, run a 3-trial baseline at the unmodified plugin.

#### Task T1.1: Define task instance schema  ✅

**Description:** Author a JSON Schema (in YAML form, draft-07) that validates one task instance. Schema fields per [`docs/spec.md`](spec.md) §6.1: `task_id`, `base_repo`, `base_sha`, `problem_statement`, `solution_type`, `verification_method`, `scope_files`, optional `rubric_path` / `verify_script`, `timeout_s`, `sim_engine`, `available_tools`. Conditional `if/then` rules ensure `rubric_path` is required when `verification_method` is `rubric` or `hybrid`. Provide a sample fixture and a YAML-aware validator wrapper (the `jsonschema` CLI is JSON-only).

**Acceptance criteria:**
- [x] `tasks/schema.yaml` exists with all required fields
- [x] Conditional `if/then` rules enforce rubric_path / verify_script presence
- [x] `tasks/instances/sample/{task.yaml,rubric.md}` validates against the schema
- [x] At least 5 negative test cases verified (missing required, malformed SHA, bad enum, missing rubric_path under conditional, malformed task_id)
- [x] `harness/validate_task.py` provides `--all` mode and single-path mode

**Verification:**
- [x] `python3 harness/validate_task.py --all` exits 0
- [x] Hand-run negative cases all rejected with clear error messages

**Dependencies:** None

**Files likely touched:**
- `tasks/schema.yaml`
- `tasks/instances/sample/task.yaml`
- `tasks/instances/sample/rubric.md`
- `harness/validate_task.py`
- `docs/adding-a-task.md`

**Estimated scope:** Small (1–2 files of substance + scaffolding)

---

#### Task T1.2: Write V1 DiffBot task instance  ✅

**Description:** Pick a small public ROS 2 repo with a sharp testable invariant. Write a rubric-typed task that asks the agent to produce `EXPERIMENT.md` validating that invariant. Per ADR-0007, V1 relaxes the Gazebo sim_engine requirement: the chosen repo (`ros-controls/ros2_control_demos@humble`, `example_2` DiffBot) uses ros2_control mock hardware. The agent designs an experiment for that runtime, not for Gazebo.

**Acceptance criteria:**
- [x] One concrete task repo selected; URL + 40-char SHA on the `humble` branch recorded
- [x] `task.yaml` validates against the schema
- [x] Rubric has 5–7 dimensions, each scored 0–3, with explicit grade-level guidance
- [x] `available_tools` set narrowly to `[Read, Glob, Grep, Write, Edit]` (no Bash; design-only)
- [x] `scope_files` set narrowly to `["EXPERIMENT.md"]` so scope-discipline metric is meaningful
- [x] Registered in `tasks/index.yaml`

**Verification:**
- [x] `python3 harness/validate_task.py --all` exits 0
- [x] Manual review of rubric dimensions for sharpness
- [x] SHA verified via `git ls-remote https://github.com/ros-controls/ros2_control_demos refs/heads/humble`

**Dependencies:** T1.1

**Files likely touched:**
- `tasks/instances/diffbot-experiment-design/task.yaml`
- `tasks/instances/diffbot-experiment-design/rubric.md`
- `tasks/index.yaml`

**Estimated scope:** Small

---

#### Task T1.3: Implement experiment runner  ✅

**Description:** Author `harness/run_experiment.py`. Takes `(plugin_tag, task_id, run_id)` plus plugin source (either `--plugin-path` or `--plugin-repo + --plugin-ref`). Materializes a worktree of the task repo at `base_sha`. Resolves the plugin's commit SHA via `git rev-parse HEAD`. Subprocesses `claude -p` per ADR-0006 (with `--tools` whitelist from `task.available_tools`, `--max-turns N`, `--output-format json`, `--no-session-persistence`). Captures transcript, diff (including untracked files via `git add -A` + `git diff --cached base_sha`), files-modified, runtime, exit code. Writes a partial `result.json` with `status: "incomplete"` *before* invoking the agent so Python-level crashes leave parseable forensics.

**Acceptance criteria:**
- [x] CLI accepts both plugin-source modes; rejects ambiguous combinations
- [x] Worktree path includes the full triple (`scratch_root/<plugin_tag>__<task_id>__<run_id>`) to prevent cross-experiment collisions per ADR-0002
- [x] Idempotency: re-running same triple is rejected (suffix-match against existing experiments dir, date-independent)
- [x] Partial `result.json` written before agent runs; updated on completion; preserved on Python exception
- [x] Worktree pruned on success; retained on failure with `scratch_dir` recorded
- [x] `result.json` records `plugin_sha` (resolved at materialization time per ADR-0001)

**Verification:**
- [x] `python3 -m pytest harness/tests/ -q` passes (24 tests at task close)
- [x] CLI smoke test against bad task ID produces clean error with available-tasks hint
- [x] CLI mutual-exclusion smoke tests: no plugin source, both sources, repo without ref all error correctly

**Dependencies:** T1.1 (schema only; runner is task-content-agnostic)

**Files likely touched:**
- `harness/__init__.py`
- `harness/run_experiment.py`
- `harness/tests/__init__.py`
- `harness/tests/test_run_experiment.py`

**Estimated scope:** Medium (1 substantial source file + tests)

---

#### Task T1.4: Implement scope-check and rubric scorer

**Description:** Two scoring modules.
- `harness/scope_check.py`: given a unified diff and a `scope_files` glob list, returns `{out_of_scope_count, out_of_scope_paths}`. Pure function; cheap to test with hand-constructed diffs.
- `harness/score_rubric.py`: given `(task, agent_output, rubric)`, subprocess `claude -p --output-format json` (no plugin loaded) per ADR-0006. Use `--json-schema` to enforce the rubric's output shape. Run **N=3 trials**, returning `{per_trial: [...], mean: {dim: float}, stdev: {dim: float}, overall_mean: float, overall_stdev: float}`.

After both modules exist, `harness/run_experiment.py` is updated to call them inline and merge results into `result.json.scoring`.

**Acceptance criteria:**
- [ ] `scope_check.py` correctly identifies out-of-scope paths for at least three constructed-diff fixtures
- [ ] `score_rubric.py` returns a structured result with per-dimension scores and stdev across N=3 trials
- [ ] Stdev is reported even if zero (some judge configurations may collapse — Open Question Q2 in [`docs/v1-plan.md`](v1-plan.md))
- [ ] Runner integration: `result.json.scoring` is populated end-to-end on a smoke run
- [ ] Permission-denial: rubric scorer never loads the plugin (judge runs in a clean cwd with no `--plugin-dir`)

**Verification:**
- [ ] `python3 -m pytest harness/tests/test_scope_check.py harness/tests/test_score_rubric.py -q` passes
- [ ] Hand-run on a deliberately good and deliberately bad EXPERIMENT.md fixture — good scores ≥2.5 mean, bad scores ≤1.0 mean (rubric sharpness check, also called for in `docs/adding-a-task.md`)

**Dependencies:** T1.3 (runner reads task.yaml; scorers will be invoked from runner once present)

**Files likely touched:**
- `harness/scope_check.py`
- `harness/score_rubric.py`
- `harness/tests/test_scope_check.py`
- `harness/tests/test_score_rubric.py`
- `harness/run_experiment.py` (extend orchestration)

**Estimated scope:** Medium

---

#### Task T1.4a: Canonical `result.json` schema  ✅

**Description:** Consolidate the implicit `result.json` shape (previously restated across 5 docs and the runner's `partial:` literal) into one machine-verifiable schema, one human-readable reference, and a validate-on-write hook in the runner. Lock the contract before T1.5 writes the first real data — every later schema change becomes a migration. Per [ADR-0008](decisions/0008-canonical-result-json-schema.md).

**Acceptance criteria:**
- [x] `harness/schemas/result.schema.yaml` exists; status-conditional `if/then` rules cover partial/success/error/timeout
- [x] `docs/result-json-reference.md` covers every field with Type / When present / Writer / Semantics; "Planned" section lists the four deferred fields
- [x] `harness/validate_result.py` provides `--all` + single-path CLI plus `validate(dict)` / `iter_errors(dict)` programmatic API
- [x] `write_result()` validates before atomic rename; rejected payload preserved at `result.invalid.json`
- [x] [ADR-0008](decisions/0008-canonical-result-json-schema.md) records the decision; ADR-0001 receives a forward-pointer
- [x] `docs/spec.md` FR3, `docs/reliability-criteria.md`, `docs/v1-plan.md`, `docs/roadmap.md` reduced to pointers (narrative kept, field listings removed)
- [x] `docs/spec.md` FR3 corrected: `exit_status` → `exit_code` (matches code)

**Verification:**
- [x] `python3 -m pytest harness/tests/ -q` passes (90 tests at task close: 27 prior + 12 scope_check + 12 score_rubric + 7 runner-integration + 29 validator + 3 write_result regression)
- [x] `python3 harness/validate_result.py --all` exits 0 (no result.json files yet, but command works)
- [x] `grep -rn "exit_status" docs/ harness/` returns nothing

**Dependencies:** T1.4 (just landed `scoring.scope_check` and `scoring.rubric` — the schema captures their shape)

**Files likely touched:**
- `harness/schemas/result.schema.yaml`
- `harness/validate_result.py`
- `harness/tests/test_validate_result.py`
- `harness/run_experiment.py` (`write_result()` validate-on-write + `ResultSchemaError`)
- `docs/result-json-reference.md`
- `docs/decisions/0008-canonical-result-json-schema.md`
- `docs/spec.md`, `docs/reliability-criteria.md`, `docs/v1-plan.md`, `docs/roadmap.md`, `docs/decisions/0001-three-surface-repo-topology.md`

**Estimated scope:** Small-to-medium (schema + validator + reference doc + ADR + 5 doc reductions)

---

#### Task T1.5: Run V1 baseline (3 trials at unmodified fork)

**Description:** Tag the current `elliewlh2094/robotics-agent-skills` HEAD as `v0.1.0` in the plugin repo. Run `run_experiment.py` against the V1 task at this tag, three times (`baseline-1`, `baseline-2`, `baseline-3`). Sanity-check that each `result.json` is well-formed and that the agent actually produced an `EXPERIMENT.md`. Measure per-dimension stdev across the three runs and document in `analysis/baseline-v0.1.0.md`. This stdev sets the noise floor against which Phase 2's plugin delta is judged.

**Acceptance criteria:**
- [ ] Three `experiments/...v0.1.0...diffbot-experiment-design...baseline-{1,2,3}/` directories exist with valid `result.json`
- [ ] Each has a non-empty `EXPERIMENT.md` in `diff.patch`
- [ ] `result.json.scoring.rubric.stdev` and `overall_stdev` recorded for all three
- [ ] Cross-run pooled stdev recorded in `analysis/baseline-v0.1.0.md`
- [ ] If any run's status is not `success`, the deviation is investigated and documented before the task closes

**Verification:**
- [ ] All three result.json files parse with `python3 -c "import json; json.load(open('experiments/.../result.json'))"`
- [ ] Visual review of each EXPERIMENT.md for plausible content (the agent wrote *something* on-topic)
- [ ] `analysis/baseline-v0.1.0.md` is concrete with numeric stdev values, not handwaving

**Dependencies:** T1.4 (scoring), T1.4a (schema validation), T1.3 (runner), T1.2 (task)

**Files likely touched:**
- `experiments/2026-...-_v0.1.0_diffbot-experiment-design_baseline-{1,2,3}/`
- `analysis/baseline-v0.1.0.md`

**Estimated scope:** Small (mostly waiting for runs and documenting; no new code)

---

#### Checkpoint A: Foundation — Loop runs end-to-end on baseline

- [ ] One full experiment loop produces a `result.json` with rubric + scope-check + reproducibility tuple
- [ ] Three baseline runs measured; cross-run variance documented in `analysis/baseline-v0.1.0.md`
- [ ] Repo stays under 50 MB; no vendored task code
- [ ] **Pause and review.** If variance is unexpectedly high or low, investigate before proceeding

---

### Phase 2: First plugin iteration *(target: ~2 weeks after Checkpoint A; happens mostly in the plugin repo)*

Make the plugin do something measurably different. Verify the loop closes.

#### Task T2.1: Restructure plugin to phase folders, tag v0.1.1 (refactor only)

**Description:** In the plugin repo (`elliewlh2094/robotics-agent-skills`), reorganize the existing 10 knowledge skills into `skills/knowledge/`. Create empty `skills/{define,plan,build,verify,review,ship}/` directories mirroring `addyosmani/agent-skills`'s phased structure. Add `.claude-plugin/plugin.json` if not already present. Tag this state as `v0.1.1`. **No behavior change** — this is a pure refactor whose purpose is to serve as a harness sanity check (re-running the V1 task should produce scores within 1 stdev of `v0.1.0`).

**Acceptance criteria:**
- [ ] Plugin still loads in Claude Code without errors (`claude --plugin-dir <path> -p "ping"` exits 0)
- [ ] All 10 existing skills moved under `skills/knowledge/`; six empty phase directories created
- [ ] `.claude-plugin/plugin.json` present and valid
- [ ] Tagged `v0.1.1` in plugin repo

**Verification:**
- [ ] Re-run V1 task at `v0.1.1` once. Score is within 1× pooled stdev of `v0.1.0` baseline (per ADR-0005, refactor-only tags must not move the score)
- [ ] If score moves outside 1 stdev: harness has hidden coupling to plugin structure → diagnose before proceeding

**Dependencies:** Checkpoint A (need a baseline to compare against)

**Files likely touched:**
- (plugin repo) `.claude-plugin/plugin.json`
- (plugin repo) `skills/knowledge/`, `skills/{define,plan,build,verify,review,ship}/`

**Estimated scope:** Medium

---

#### Task T2.2: Author `design-robotics-experiment` skill

**Description:** Write `skills/verify/design-robotics-experiment/SKILL.md` modeled on `addyosmani/agent-skills` skill anatomy (frontmatter with name+description for triggering, when-to-use, process steps, anti-patterns, red flags, verification checklist). The skill should guide the agent to produce: hypothesis, controlled variables, recorded signals (with rates and rationale), success thresholds (quantitative, with units), visualization plan (specific tooling + signals), failure modes (≥3 with mitigations), and **repo-grounded references** (specific code constructs from the task repo, not generic checklists). The seventh rubric dimension grades exactly this last point.

**Acceptance criteria:**
- [ ] Skill follows the documented anatomy (frontmatter + standard sections)
- [ ] Skill triggers on relevant prompts (manually verified via direct invocation)
- [ ] Skill explicitly counters the "generic checklist" failure mode by instructing the agent to read source files first
- [ ] Skill mentions Gazebo-related primitives (rosbag2, plotjuggler, sim time) for forward compatibility, even though V1's task uses mock hardware

**Verification:**
- [ ] Manual: invoke the skill on a hand-crafted prompt; review output quality. Should be markedly more grounded than `v0.1.0`'s output on the same prompt.

**Dependencies:** T2.1

**Files likely touched:**
- (plugin repo) `skills/verify/design-robotics-experiment/SKILL.md`

**Estimated scope:** Small

---

#### Task T2.3: Add `pre-commit-scope-check` hook

**Description:** Add a hook to the plugin that runs before any commit-tool invocation by the agent. The hook reads `BENCHMARK_SCOPE_FILES` (set by the runner) and rejects commits that touch files outside that list. Reliability criterion C4 (scope-discipline) maps to this hook (per `docs/reliability-criteria.md`). The hook must no-op when `BENCHMARK_SCOPE_FILES` is unset (so it doesn't interfere with normal plugin use outside the benchmark).

**Acceptance criteria:**
- [ ] Hook present and registered in plugin manifest
- [ ] When `BENCHMARK_SCOPE_FILES` is set: hook rejects out-of-scope edits, gives the agent feedback, agent can self-correct
- [ ] When `BENCHMARK_SCOPE_FILES` is unset: hook no-ops (verified by running normal Claude Code outside the benchmark)
- [ ] `result.json.hook_blocks` count increments on rejection (runner reads from transcript or hook output)

**Verification:**
- [ ] Manual: prompt agent to modify an out-of-scope file with `BENCHMARK_SCOPE_FILES` set; observe rejection
- [ ] Manual: same prompt with the env var unset; observe normal behavior
- [ ] Tag plugin as `v0.2.0` after T2.2 + T2.3 are both committed in plugin repo

**Dependencies:** T2.1 (plugin structure must exist)

**Files likely touched:**
- (plugin repo) `hooks/pre-commit-scope-check.sh` (or equivalent file format)
- (plugin repo) plugin.json (hook registration)

**Estimated scope:** Small

---

#### Task T2.4: Run V1 task at v0.2.0; write comparison report

**Description:** Run the V1 task three times at plugin tag `v0.2.0`. Compare to the `v0.1.0` baseline on (a) per-rubric-dimension mean delta, (b) `out_of_scope_file_count` delta, (c) `hook_blocks` delta, (d) runtime delta, (e) qualitative agent-behavior observations from transcripts. Write `analysis/reports/<YYYY-MM-DD>_v0.1.0_vs_v0.2.0.md`. **The report must classify the score delta as signal or noise honestly:** delta ≤ 1× pooled stdev = noise (no detectable effect). No "promising trend" language for non-significant deltas (per ADR-0003).

**Acceptance criteria:**
- [ ] Three experiments at `v0.2.0` logged with valid `result.json`
- [ ] Comparison report exists at `analysis/reports/<date>_v0.1.0_vs_v0.2.0.md`
- [ ] Report includes: numeric per-dimension delta, pooled stdev, signal-or-noise verdict, qualitative observations from at least one transcript pair
- [ ] If delta is in the noise: report says so explicitly; does NOT call it "promising"

**Verification:**
- [ ] Report exists and is honest about effect size
- [ ] At least one paragraph describes *why* the delta is what it is (e.g., "the new skill changed how the agent structured its hypothesis, but the rubric does not yet probe structure")

**Dependencies:** T2.2, T2.3 (both must be in `v0.2.0`); Checkpoint A (need baseline)

**Files likely touched:**
- `experiments/2026-...-_v0.2.0_diffbot-experiment-design_*/`
- `analysis/reports/<date>_v0.1.0_vs_v0.2.0.md`

**Estimated scope:** Small

---

#### Checkpoint B: Feedback loop validated  *(this is the V1 completion gate)*

- [ ] Two plugin versions (v0.1.0, v0.2.0) measured on the same task
- [ ] Score delta is interpretable; signal-vs-noise classified honestly
- [ ] Total wall-clock time per experiment recorded — informs whether to scale or simplify
- [ ] **If delta is in the noise:** the failure mode is the harness, not the plugin. Fix harness sensitivity before adding more skills

**V1 is complete when Checkpoint B is signed off.**

---

### Phase 3: TDD + debugging task type *(post-V1; target: ~2 weeks after Checkpoint B)*

Add the test-pass scoring path. Reinstates Gazebo as the criterion (per ADR-0007, the V1 sim_engine relaxation does NOT propagate).

#### Task T3.1: Define test-pass task instance + Dockerfile

**Description:** Pick a ROS 2 + Gazebo repo with a known bug (or inject one at a known SHA). Write a task with `verification_method: unit-test`, `sim_engine: gazebo`, including FAIL_TO_PASS test names. Build a per-task Dockerfile under `harness/docker/<task-id>/` that sets up the ROS 2 environment and Gazebo. Container must be reproducible from the Dockerfile alone.

**Acceptance criteria:**
- [ ] Task instance validates against schema
- [ ] Dockerfile builds cleanly: `docker build harness/docker/<task-id>/`
- [ ] Inside the container, `verify.sh` exits 0 when the gold patch is applied; non-zero when it isn't (smoke test)

**Verification:**
- [ ] Schema validation passes
- [ ] Dockerfile build succeeds in <30 minutes
- [ ] Smoke test the verify.sh against gold patch and base state

**Dependencies:** Checkpoint B

**Files likely touched:**
- `tasks/instances/<task-id>/{task.yaml,verify.sh}`
- `tasks/index.yaml`
- `harness/docker/<task-id>/Dockerfile`

**Estimated scope:** Medium

---

#### Task T3.2: Implement `harness/score_tests.py`

**Description:** SWE-bench-style scorer: build/use the task's Docker container, apply the agent's diff inside the container, run FAIL_TO_PASS + PASS_TO_PASS test sets, parse results. Returns `{fail_to_pass_passing, pass_to_pass_passing, fail_to_pass_total, pass_to_pass_total, resolved: bool}`. Hooks into runner's scoring pipeline alongside `score_rubric.py`.

**Acceptance criteria:**
- [ ] Scorer correctly identifies "resolved" (all FAIL_TO_PASS now pass AND all PASS_TO_PASS still pass) on a hand-crafted fixture
- [ ] Container cleanup after each scoring run (no leaked containers)
- [ ] Timeout per task respected (default 30 min for sim, configurable)

**Verification:**
- [ ] Pytest suite for scorer with fake-diff fixtures
- [ ] End-to-end smoke test: run T3.1 task, scorer reports correct outcome on gold-patch and on empty-diff cases

**Dependencies:** T3.1

**Files likely touched:**
- `harness/score_tests.py`
- `harness/tests/test_score_tests.py`
- `harness/run_experiment.py` (extend orchestration)

**Estimated scope:** Medium

---

#### Task T3.3: Run debugging task against v0.2.0 (baseline for v0.3.0)

**Description:** Run the new debugging task three times at plugin tag `v0.2.0`. This establishes the v0.2.0 baseline against which v0.3.0 will be compared. Same shape as T1.5 but for the new task type.

**Acceptance criteria:** [ ] Three runs; valid result.json each; baseline file documenting variance.

**Dependencies:** T3.2

**Files likely touched:** `experiments/`, `analysis/baseline-v0.2.0-debugging.md`

**Estimated scope:** Small

---

#### Task T3.4: Author `robot-debugging` skill in plugin; tag v0.3.0

**Description:** Add a new skill that guides the agent through robotics-specific debugging workflows: reproducing the bug deterministically, isolating the failing component, reading rosbag/log output, formulating a minimal fix, regression testing. Tag plugin `v0.3.0`.

**Acceptance criteria:** [ ] Skill present, follows anatomy, triggers correctly. [ ] Plugin tagged.

**Dependencies:** T3.3

**Files likely touched:** (plugin repo) `skills/.../robot-debugging/SKILL.md`

**Estimated scope:** Medium

---

#### Task T3.5: Re-run debugging task at v0.3.0; write comparison report

**Description:** Three runs at v0.3.0; comparison report against v0.2.0 baseline. Same honesty rules as T2.4.

**Acceptance criteria:** [ ] Report exists; signal-vs-noise classified honestly.

**Dependencies:** T3.4

**Files likely touched:** `experiments/`, `analysis/reports/<date>_v0.2.0_vs_v0.3.0.md`

**Estimated scope:** Small

---

#### Checkpoint C: Two task types, three plugin versions

- [ ] Both `rubric` and `unit-test` verification methods work end-to-end
- [ ] v0.1.0 → v0.2.0 → v0.3.0 trajectory has measured deltas at each step

---

### Phase 4: Spec + planning task type *(post-V1; target: ~2 weeks after Checkpoint C)*

Add rubric-typed spec/planning tasks. Reuses `score_rubric.py` — no new scorer needed.

#### Task T4.1: Define rubric-typed spec/planning task instance

**Description:** Pick a ROS 2 repo where the agent must produce a spec or break a feature into ordered tasks. Write rubric covering: scope clarity, dependency analysis, milestone identification, risk surfacing.

**Dependencies:** Checkpoint C

**Estimated scope:** Small

---

#### Task T4.2: Run baseline at v0.3.0 against the new task

**Dependencies:** T4.1

**Estimated scope:** Small

---

#### Task T4.3: Author `define-robotics-spec` OR `plan-robotics-tasks` skill; tag v0.4.0

**Description:** Pick whichever target the user wants more (specification authoring or task breakdown for robotics work). Author the skill following the anatomy.

**Dependencies:** T4.2

**Estimated scope:** Medium

---

#### Task T4.4: Re-run task at v0.4.0; write comparison report

**Dependencies:** T4.3

**Estimated scope:** Small

---

#### Checkpoint D: All three V1-selected activities measured

- [ ] experiment-design (Phase 2), debugging (Phase 3), spec/planning (Phase 4) all have measured deltas across at least two plugin versions
- [ ] `analysis/reports/` contains the cross-version reports
- [ ] **This is the end of the user-selected V1 activity coverage.** From Phase 5 onward, monthly cadence drives plugin changes from data, not roadmap commitments

---

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Rubric scorer is too noisy | High | N=3 trials; explicit pooled-stdev gate at Checkpoints B and C |
| Harness consumes all time; no plugin work | High | Phase 1 hard-capped at 5 tasks (~4 weeks); enforce at Checkpoint A |
| Plugin and harness drift | Medium | `plugin_sha` recorded in every result.json (per ADR-0001) |
| External task repos rebase or disappear | Medium | All references include commit SHA; fetch failure aborts loudly |
| Sim nondeterminism contaminates Phase 3+ tasks | Medium | For sim-metric tasks: pin seed, run N=5, report success rate |
| Judge drift goes undetected | Medium-High | Human spot-check 1-in-5; log disagreements in `analysis/judge-drift.md` |
| Scope creep — V1 expands to all 3 activities | High | This document explicitly stages activities across Phases 2/3/4 (ADR-0004) |

## Open questions

See [`docs/v1-plan.md`](v1-plan.md) §"Open questions" for the canonical list (Q1–Q4 around rubric output schema, baseline determinism, refactor-tag re-run depth, `--tools` flag syntax).
