# Roadmap

A living document. The approved implementation plan (`~/.claude/plans/i-want-to-conduct-federated-stream.md`)
covers concrete next steps; this file captures the **full long-term vision** so that, however the
project drifts, the original scope remains visible.

> **Reading order.** Start with [North Star](#north-star) for the why. Then [V1 deliverables](#v1-the-smallest-viable-loop) for the next ~4 weeks. Then [Near-term versions](#near-term-versions-in-the-approved-plan) for the next 3-4 months. Then [Beyond V0.4](#beyond-v04--the-rest-of-the-original-vision) for the rest of the original vision.

---

## North Star

A Claude Code plugin that gives an AI agent **reliable** robotics-software-development capability —
where "reliable" is operationalized by 5 specific criteria (auditability, verifiability,
output-stability, scope-discipline, recoverability) and the plugin's quality is **measured** rather
than asserted, on a benchmark that goes beyond SWE-bench-style bug fixing.

Two things are true at the same time:

1. **General-purpose plugins** (e.g., `addyosmani/agent-skills`) handle SW-engineering workflow well
   but produce shallow results on robotics-specific reasoning. The clearest example: when asked to
   "design tests" they write syntactic unit tests rather than experimental plans (what to record in
   sim, what to vary, how to visualize, what to falsify).
2. **`arpitg1304/robotics-agent-skills`** has solid robotics knowledge skills but lacks the
   *behavioral* layer (phased workflow skills, sub-agents, lifecycle hooks) — and lacks a
   measurement harness for tracking improvement.

This project closes both gaps simultaneously.

---

## Versioning model

| Surface | Versioning |
|---|---|
| Plugin (`elliewlh2094/robotics-agent-skills`) | Git tags, semver-ish: `vMAJOR.MINOR.PATCH` |
| Harness (this repo) | Untagged for now; tagged when external contributors arrive |
| Task instances | `tasks/index.yaml` carries `schema_version`; bump on schema breaking changes |
| Result artifacts | Pinned by `(plugin_tag, base_sha, schema_version, run_id)` in `result.json` |

**Plugin version conventions:**

- **Patch bump (`v0.X.Y` → `v0.X.Y+1`)** — one new skill OR one new hook OR one bugfix.
- **Minor bump** — a structural change (e.g., reorganizing skills folder), or a hook system change.
- **Major bump** — breaking changes to plugin manifest or skill discovery model.

> **Rule:** one logical change per tag. Bundling (e.g., "added 3 skills and 2 hooks") makes
> attribution impossible. Always tag in between.

---

## V1 — the smallest viable loop

**Target:** ~4 weeks. **One plugin version delta, end-to-end measured.**

### V1 deliverables

| Artifact | Status |
|---|---|
| Repo scaffolding (README, CLAUDE.md, dirs, docs) | ✅ done |
| Task instance JSON Schema + validator | ✅ done |
| Sample fixture + 5 negative-test cases | ✅ done |
| Reliability-criteria → result.json field mapping | ✅ done |
| Real V1 task instance (`ros2_control_demos`/example_2 — DiffBot, mock hardware; see [ADR-0007](decisions/0007-v1-sim-engine-relaxation.md)) | ⏳ T1.2 |
| `harness/run_experiment.py` — full runner | ⏳ T1.3 |
| `harness/scope_check.py` + `harness/score_rubric.py` | ⏳ T1.4 |
| Plugin tagged `v0.1.0` (unmodified baseline) | ⏳ T1.5 |
| 3 baseline runs at v0.1.0; variance documented | ⏳ T1.5 |
| Plugin tagged `v0.1.1` (refactor to phase folders, no behavior change) | ⏳ Phase 2 / T2.1 |
| Plugin tagged `v0.2.0` (+`design-robotics-experiment` skill, +`pre-commit-scope-check` hook) | ⏳ Phase 2 |
| 3 runs at v0.2.0; v0.1.0-vs-v0.2.0 report | ⏳ Phase 2 / T2.4 |

### V1 success criteria

- One full experiment loop runs end-to-end: `(plugin_tag, task_id, run_id) → result.json`
- Result contains: rubric scores (mean ± stdev across N=3 judge trials), automated metrics (scope-check, runtime, files_modified), audit trail (transcript, diff). Schema-validated on every write per [ADR-0008](decisions/0008-result-json-schema-and-reference.md); full field reference at [`docs/result-json-reference.md`](result-json-reference.md).
- v0.2.0 score delta vs v0.1.0 is interpretable (>1× pooled stdev = real signal; ≤ = honestly reported as noise)
- Repo stays under 50 MB; no vendored task code

### V1 explicitly excludes

- Test-pass scoring (Phase 3)
- Sim-metric scoring (later)
- Multi-task suites (V2+)
- Sub-agents (V2+)
- Any hardware class beyond UGV
- Any activity beyond experiment-design
- Running anything in sim (V1 is design-only — see [ADR-0007](decisions/0007-v1-sim-engine-relaxation.md))

---

## Near-term versions (in the approved plan)

These are the next 2-3 plugin tags after V1's `v0.2.0`. Each is one phase in the implementation plan.

### v0.3.0 — TDD + debugging task type *(Phase 3 in plan)*

**Target:** ~2 weeks after v0.2.0.

- New task type: `verification_method: unit-test` (SWE-bench-style FAIL_TO_PASS / PASS_TO_PASS)
- New harness module: `harness/score_tests.py`
- New per-task Dockerfile pattern: `harness/docker/<task-id>/`
- New plugin skill: `robot-debugging` (under `skills/build/` or `skills/verify/`)
- One ROS 2 task with a known bug pinned at SHA

### v0.4.0 — Spec + planning task type *(Phase 4 in plan)*

**Target:** ~2 weeks after v0.3.0.

- Rubric-only path (reuses `harness/score_rubric.py`)
- New plugin skill: one of `define-robotics-spec` or `plan-robotics-tasks` — pick whichever the data says is more impactful
- A spec/planning task instance

### Checkpoint at v0.4.0

All three V1-selected activities (experiment-design, debugging, spec/planning) measured with
a baseline-vs-latest score in `analysis/reports/`. **This is the first point at which the
loop has demonstrated value across multiple activity types.**

---

## Beyond v0.4 — the rest of the original vision

Everything below is in the original spec but **not** scheduled. Each item is a candidate for the
monthly "lowest-scoring rubric dimension" cadence — driven by data, not opinion.

### Robotics-development activities still to cover

The user's original 9 activities, with V1 status noted:

| # | Activity | V1 status | Where it likely lands |
|---|---|---|---|
| 1 | Refining ideas | not yet | v0.5+ rubric task; would lean on existing `idea-refine` skill from `addyosmani/agent-skills` |
| 2 | Defining specifications | v0.4 | rubric task |
| 3 | Creating plans / breaking down tasks | v0.4 | rubric task |
| 4 | Designing experiments based on robotics knowledge | **V1** | rubric task |
| 5 | Test-driven development | v0.3 | unit-test task |
| 6 | Debugging | v0.3 | unit-test task with regression-finding |
| 7 | Performance optimization | not yet | sim-metric task; needs latency / throughput / determinism rubric |
| 8 | System modules integration | not yet | hybrid task; cross-package coordination |
| 9 | Refactoring / quality / complexity reduction | not yet | rubric + static-analysis hybrid |

Activities 7–9 are the long tail. They are the most *robotics-distinctive* in some ways
(perf-opt for real-time control loops; integration across LiDAR + nav + control; refactoring
under hard ABI constraints) but also hardest to score reliably.

### Hardware classes still to cover

| Class | V1 status | Likely additions |
|---|---|---|
| **UGV** (wheeled / tracked ground robots) | **V1** | Differential-drive controller skill, odometry-fusion skill |
| **UAV** | not yet | PX4/MAVLink integration skill, attitude-control rubric, no-fly-zone safety hook |
| **Robotic arm** | not yet | MoveIt2 skill, IK reasoning skill, gripper-policy skill, collision-check hook |
| **Multi-robot** | not yet | Discovery / coordination skills, namespace-discipline hook |
| **Legged / humanoid** | optional | Likely never in scope unless user pivots |

### Integration technologies to cover

| Tech | Likely skill / sub-agent |
|---|---|
| **LiDAR** | Point cloud preprocessing skill, sensor-calibration rubric |
| **Image recognition** | Vision pipeline skill, dataset-handling skill |
| **SLAM** | slam_toolbox / cartographer skills, map-quality rubric |
| **TF2 / transforms** | Frame-discipline skill (very common bug source) |
| **`ros2_control`** | Controller-design skill, real-time-budget rubric |
| **`robot_description` / URDF / xacro** | Description authoring skill, kinematic-validity hook |
| **Sim engines** | Gazebo (V1), then Isaac Sim, then MuJoCo |

### Sub-agents to add

`addyosmani/agent-skills` has 3 (code-reviewer, test-engineer, security-auditor). Robotics
candidates:

- **`experiment-reviewer`** — reviews experiment-design output against the rubric in a fresh
  context. Functions as a built-in critic the agent can self-invoke.
- **`sim-debugger`** — assists when a sim run fails; reads gazebo logs, ros2 node lists,
  rosbag2 contents.
- **`hardware-safety-reviewer`** — gates control commands or actuator ranges on
  hardware-capable tasks. Mandatory before any hardware-in-the-loop work.
- **`tf-tree-auditor`** — checks transform graph for cycles / floating frames / stale frames.

### Hooks to add

| Hook | Purpose | Reliability criterion |
|---|---|---|
| **`pre-commit-scope-check`** (V2) | Reject commits touching files outside `BENCHMARK_SCOPE_FILES` | C4: scope-discipline |
| **`post-test-coverage-check`** | Warn if agent's TDD work lands a test without an assertion | C2: verifiability |
| **`pre-launch-safety-check`** | Refuse `ros2 launch` against real hardware unless `BENCHMARK_HARDWARE_OK=1` | C5: recoverability |
| **`sim-determinism-check`** | Warn when sim runs differ across N=3 trials beyond a threshold | C3: stability |
| **`tf-cycle-check`** | Run on URDF/xacro edits; reject impossible transform graphs | C2: verifiability |
| **`real-time-budget-check`** | Warn if a callback's measured execution time exceeds budget declared in code | C2: verifiability |

### Evaluation system expansions

- **Hardware-in-the-loop tasks** — declare via `sim_engine: hardware`; harness skips unless
  user explicitly opts in. Initially manually graded; eventually rosbag-based metrics.
- **Cross-plugin comparisons** — same task, run against `arpitg1304/robotics-agent-skills`,
  `addyosmani/agent-skills`, and our fork. Establishes external baseline.
- **Multi-trial sim with seed variance** — for sim-metric tasks: run with N seeds, report
  success rate not raw outcome.
- **Cost tracking** — token counts and dollar estimates per `result.json`. Triggers a "cheap
  vs. expensive plugin version" axis once data exists.
- **Judge-drift dashboard** — over time, compare LLM-judge scores to human spot-check scores
  on the same outputs. Tracks whether the judge is becoming systematically biased.

### Harness/repo expansions

- **CI integration** — only when collaborators arrive. Until then, runner is a CLI invocation.
- **Web dashboard** — view cross-version score deltas, trend lines, judge-drift charts.
  Probably a static site generated from `experiments/*/result.json`.
- **Public leaderboard** — if/when project goes public.
- **Auto-bisect on regression** — when a plugin tag drops a score by >1 stdev, auto-rerun
  intermediate commits to find the offender.
- **Task-importance weighting** — once we have many tasks, not all are equal; declare weights
  in `tasks/index.yaml`.

---

## Cross-reference: status by dimension

| Dimension | V1 | v0.3 | v0.4 | v0.5+ |
|---|---|---|---|---|
| **Activities measured** | experiment-design | + debugging | + spec/planning | refactoring, perf-opt, integration |
| **Hardware classes** | UGV | UGV | UGV | UAV → arm → multi-robot |
| **Sim engines** | any runnable ROS 2 (mock hw OK)¹ | Gazebo | Gazebo | Isaac Sim, MuJoCo |
| **Verification methods** | rubric | + unit-test | + unit-test | + sim-metric, + hybrid |
| **Sub-agents** | none | none | none | experiment-reviewer first |
| **Hooks** | scope-check | + 1 more | + 1 more | safety, tf, real-time, ... |
| **Plugin skills (count)** | 10 (knowledge) + 1 + 1 hook | + 1 | + 1 | data-driven monthly cadence |

¹ V1 only — see [ADR-0007](decisions/0007-v1-sim-engine-relaxation.md). The agent's task is to *design* an experiment; the underlying repo can use mock hardware. Gazebo is reinstated as the baseline from Phase 3 onward when verification involves running sims.

---

## Out of scope — forever (unless user explicitly reverses)

These are **deliberate** non-goals. Reversing any of them changes the project's character, so
flag them in conversation rather than silently expanding.

- **Hosting an inference service** — the plugin assists humans / agents during development;
  it does not run robots in production.
- **Robot OS-level work** (kernel patches, RT-kernel tuning, hardware drivers below ROS) —
  out of scope; covered by other tooling and not what plugins are good at.
- **Building a sim engine** — we use existing ones (Gazebo, Isaac, MuJoCo); we do not author one.
- **Replacing `addyosmani/agent-skills` for general SW work** — ours specializes; users layer both.
- **Vendoring task repositories** — already locked: URL+SHA references only.
- **Single-mono-repo for plugin + harness** — already locked: separate repos.

---

## Review cadence

- **Per-experiment** — runner produces a `result.json`; no roadmap update.
- **End of each phase** — re-read this document, mark items completed, add items discovered
  during work. Update the cross-reference table.
- **Monthly during active iteration** — pick the lowest-scoring rubric dimension across
  recent experiments. The chosen plugin change for that month should target it. Note the
  decision in `analysis/reports/<YYYY-MM>_review.md`.
- **Quarterly** — read this whole document. Retire items no longer interesting. Promote items
  from "Beyond V0.4" into a scheduled phase. Reconfirm the "Out of scope" list.

This document is **not** a contract. It exists so that decisions made under deadline pressure
can be audited later against what we said we'd build.
