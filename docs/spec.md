# Specification — robotics-skills-benchmark

> **What this document is.** A single-page reference that answers *"what is this project, and why does it exist?"* without describing implementation. Pair with `docs/roadmap.md` (future scope), `docs/decisions/` (architecture decision records), `~/.claude/plans/i-want-to-conduct-federated-stream.md` (implementation plan), and `TODO.md` (current state).
>
> **Last reviewed:** 2026-05-02.

---

## 1. Problem

AI coding agents equipped with general-purpose plugins (e.g., `addyosmani/agent-skills`) handle generic software engineering well but produce **shallow results on robotics-specific reasoning**. A representative failure: when asked to "design tests" for a robot perception module, the agent writes syntactic unit tests instead of an experimental plan — it does not specify what to record in simulation, what variables to control, what success thresholds to meet, or how to visualize results.

There is currently no measured way to track whether a robotics-specialized plugin is actually getting better, on tasks that matter to robotics software development.

## 2. Goals

The project ships a **research harness** that measures and improves a Claude Code plugin (`elliewlh2094/robotics-agent-skills`) through a fixed experimental loop:

1. Make plugin quality **measurable** — every plugin version is scored on the same task set, with results comparable across versions.
2. Make plugin improvement **iterative** — measured gaps drive the next plugin change; speculative additions are out.
3. Cover **robotics-distinctive activities** — not just bug fixing, but spec writing, planning, experiment design, debugging, performance optimization, integration, and refactoring.
4. Stay **lightweight** — the harness repo must remain manageable as the task set scales to ~50+ external repos.

## 3. Non-goals

- Building a sim engine — we use Gazebo, Isaac, MuJoCo.
- Hosting an inference service — the plugin assists during development; it does not run robots in production.
- Replacing general-purpose plugins — ours specializes; users layer both.
- Vendoring task repositories — referenced by URL+SHA only.
- Single-mono-repo for plugin and harness — explicitly separate.
- OS-level / kernel / driver work below ROS.

## 4. Users

- **Primary user:** Ellie Huang. Robotics software research; uses Claude Code as her development environment.
- **Future users:** none planned for V1. Public release deferred to "Beyond V0.4" in `docs/roadmap.md`.

## 5. System overview

Three logically separate surfaces:

| Surface | Repo | Purpose |
|---|---|---|
| **Harness** | `robotics-skills-benchmark` (this repo) | Defines tasks, runs experiments, scores results, holds analysis reports |
| **Plugin under test** | `elliewlh2094/robotics-agent-skills` | The artifact being iterated. Versioned by git tags |
| **Task code** | many external repos | Real robotics codebases, referenced by `(URL, commit_sha)` only — never vendored |

**Execution model:** for each `(plugin_tag, task_id, run_id)` the harness clones the task repo into a git worktree, runs Claude Code with the pinned plugin, captures the agent's output and reasoning trail, and produces a structured `result.json`.

**Parallelism:** runs of the same task at different plugin versions execute concurrently in distinct worktrees, avoiding branch-switching inside any repo.

## 6. Functional requirements

### FR1. Task definition
- Tasks are declared as YAML files validated against a JSON Schema (`tasks/schema.yaml`).
- Each task carries: `task_id`, `base_repo`, `base_sha`, `problem_statement`, `solution_type`, `verification_method`, `scope_files`, optional `rubric_path` / `verify_script`, `timeout_s`, `sim_engine`.
- Scope is enforced: agent edits outside `scope_files` are counted and rejected at commit time.

### FR2. Experiment runner
- Input: `(plugin_tag, task_id, run_id)`.
- Clones the task repo at the pinned SHA into a scratch worktree.
- Materializes the requested plugin version.
- Invokes the agent with `problem_statement` as prompt and the plugin's scope env vars set.
- Captures: full transcript, final diff, list of files modified, runtime, exit status.
- Output: `experiments/<YYYY-MM-DD>_<plugin-tag>_<task-id>_<run-id>/{result.json,transcript.md,diff.patch}`.

### FR3. Scoring (hybrid, task-type-routed)
- **Always:** automated metrics — `out_of_scope_file_count`, `files_modified`, `runtime_s`, `exit_status`.
- **For `rubric` / `hybrid` tasks:** LLM-judge scorer with N=3 trials; reports per-dimension score, overall mean, stdev across trials.
- **For `unit-test` / `hybrid` tasks:** SWE-bench-style FAIL_TO_PASS / PASS_TO_PASS run inside per-task Docker container.
- **For `sim-metric` tasks:** parse a numeric metric from rosbag/log; with `seed_required: true`, run N trials and report success rate.

### FR4. Cross-version analysis
- A report compares two plugin tags on the same task set, reporting per-dimension delta and pooled stdev.
- Deltas smaller than 1× pooled stdev are reported as *no detectable effect* — never as "promising direction."

### FR5. Plugin feedback loop
- One logical change per plugin tag (one new skill OR one new hook OR one bugfix).
- A plugin change ships only after re-running the affected task(s) and writing a comparison report.
- The next plugin change targets the *measured* lowest-scoring rubric dimension, not opinion.

## 7. Reliability requirements

The user-defined reliability criteria, each mapped to a captured field:

| # | Criterion | Captured by |
|---|---|---|
| C1 | **Auditability** — agent's reasoning is inspectable | `transcript.md`, `diff.patch`, `files_modified`, `skills_invoked` |
| C2 | **Verifiability** — output is checkable mechanically | `scoring.test_pass`, `scoring.rubric_scores`, `scoring.sim_metric`, `static_check` |
| C3 | **Stability** — same input → similar output | `rubric_scores.stdev` across N=3 trials; pooled stdev across runs |
| C4 | **Scope-discipline** — no unrelated edits | `out_of_scope_file_count`, `out_of_scope_paths`, `hook_blocks` |
| C5 | **Recoverability** — failure point is identifiable | `status`, `error`, `scratch_dir` retained on failure |

See `docs/reliability-criteria.md` for the full mapping and mechanism per criterion.

## 8. Key entities

### Task instance
A YAML document under `tasks/instances/<task-id>/` defining one benchmark problem. Schema-validated. Immutable in spirit — a meaningful change creates a new task with a different `task_id`, not a mutation of an existing one. (The base_sha can be updated for upstream-rebase reasons; the `problem_statement` and `rubric` should not be edited mid-experiment.)

### Experiment result
A folder under `experiments/<YYYY-MM-DD>_<plugin-tag>_<task-id>_<run-id>/` containing `result.json`, `transcript.md`, `diff.patch`, optional `notes.md`. Reconstructable from `(plugin_tag, base_sha, task_yaml)` alone.

### Plugin version
A git tag on `elliewlh2094/robotics-agent-skills`. Tags carry one logical change each. The unmodified fork ships as `v0.1.0`.

### Comparison report
A markdown file under `analysis/reports/<YYYY-MM-DD>_<old-tag>_vs_<new-tag>.md` summarizing per-task deltas, pooled stdev, and qualitative observations. Required before the new tag is considered "validated."

## 9. Constraints

- **Repo size:** harness repo stays under 50 MB. No vendored task code; no result blobs over a few KB.
- **Reproducibility:** every result is reconstructable from `(plugin_tag, base_sha, schema_version, run_id)`.
- **Scoring honesty:** any score delta within 1× pooled stdev is reported as noise; reports do not exaggerate.
- **One change per tag:** plugin tags carry one logical change each, to make attribution possible.
- **Determinism where it matters:** sim-metric tasks pin random seeds and run N trials.

## 10. Success metrics (V1)

V1 is achieved when **all** are true:

1. A single experiment run completes end-to-end and produces a valid `result.json`.
2. Three baseline runs at `v0.1.0` produce a measurable score variance (stdev) that's recorded.
3. A plugin tag `v0.2.0` (one new skill + one new hook) re-runs the same task and produces a comparison report whose delta is honestly classified as signal or noise.
4. Three V1-selected activity types (experiment-design, debugging, spec/planning) each have at least one task and at least one baseline+v0.X measurement by the end of Phase 4.
5. Repo stays under 50 MB; no vendored task code.

## 11. Architecture Decision Records

The decisions underlying this spec are recorded in `docs/decisions/` as ADRs. Read these for the *why*, including alternatives considered and consequences accepted:

| # | Title |
|---|---|
| [ADR-0001](decisions/0001-three-surface-repo-topology.md) | Three-surface repository topology with URL+SHA task references |
| [ADR-0002](decisions/0002-git-worktrees-for-parallel-runs.md) | Git worktrees for parallel multi-version runs |
| [ADR-0003](decisions/0003-hybrid-scoring.md) | Hybrid scoring: automated + LLM-judge rubric + human spot-check |
| [ADR-0004](decisions/0004-v1-staged-activities.md) | V1 stages user-selected activities one per phase |
| [ADR-0005](decisions/0005-one-change-per-plugin-tag.md) | One logical change per plugin tag |
| [ADR-0006](decisions/0006-headless-claude-code-for-runner-and-judge.md) | Headless Claude Code for both runner and judge |
| [ADR-0007](decisions/0007-v1-sim-engine-relaxation.md) | V1 `sim_engine` criterion relaxed; long-term Gazebo unchanged |

## 12. References

- **`addyosmani/agent-skills`** — architectural inspiration (skill anatomy, sub-agents, hooks, Define→Plan→Build→Verify→Review→Ship phases).
- **`arpitg1304/robotics-agent-skills`** — the fork's parent. Provides 10 knowledge skills (ROS 1/2, perception, testing, etc.) we extend with the behavioral layer.
- **`elliewlh2094/robotics-agent-skills`** — Ellie's fork; the artifact under iteration.
- **SWE-bench** — task-instance schema and Docker-sandbox scoring inspiration; we extend its model with rubric-based scoring for non-test tasks.
- **`harunkurtdev/ros2-claude-code-template`**, **`henki-robotics/henki_ros2_best_practices`**, **`K-Dense-AI/scientific-agent-skills`** — secondary references; consulted for layering and structural patterns.
