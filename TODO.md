# TODO

Persistent task tracker. Read this first to see where we are; pair with `docs/spec.md` (what + why), `docs/decisions/` (architecture decision records), and `~/.claude/plans/i-want-to-conduct-federated-stream.md` (full implementation plan).

> **Last updated:** 2026-05-02 (post-ADR session). **Phase 1 in progress; T1.2 next.**

---

## ▶ Where to resume

**T1.2 — write the V1 DiffBot task instance.**

Decision recorded in [ADR-0007](docs/decisions/0007-v1-sim-engine-relaxation.md):
- Repo: `https://github.com/ros-controls/ros2_control_demos`
- Focus: `example_2` (DiffBot)
- `sim_engine`: `none` (mock hardware via ros2_control)
- Rubric-typed; agent designs an `EXPERIMENT.md` for validating the kinematic integration invariant

What's left in T1.2:
- Confirm a 40-char SHA on `master` (or whichever the default branch is)
- Author `tasks/instances/diffbot-experiment-design/task.yaml`
- Author `tasks/instances/diffbot-experiment-design/rubric.md` (5–7 dimensions, 0–3 each)
- Register in `tasks/index.yaml`
- Validate with `python harness/validate_task.py --all`

After T1.2, T1.3 (experiment runner) is unblocked; CLI invocation surface is already verified.

---

## ✅ Done

| ID | Task | Output |
|---|---|---|
| T6 | Repo scaffolding | `README.md`, `CLAUDE.md`, dir layout |
| T1.1 | Task instance schema | `tasks/schema.yaml`, sample fixture, `harness/validate_task.py`, 5 negative cases verified |
| — | Reliability criteria mapping | `docs/reliability-criteria.md` |
| — | Plugin feedback loop docs | `docs/plugin-feedback-loop.md` |
| — | Adding-a-task guide | `docs/adding-a-task.md` |
| — | Long-term roadmap | `docs/roadmap.md` |
| — | Spec / PRD | `docs/spec.md` |
| — | Architecture Decision Records | `docs/decisions/0001`–`0007` |
| — | Headless Claude Code investigation (T1.3 prep) | flags verified via `claude --help`; see ADR-0006 |
| — | V1 task repo selection | DiffBot in `ros2_control_demos`; see ADR-0007 |
| — | Candidate-repo knowledge base | `docs/candidate-repos.md` (4 detailed entries + backlog table) |
| — | `record-candidate-repo` project-level skill | `.claude/skills/record-candidate-repo/SKILL.md` |

---

## 🔄 In flight

- **T1.2** — write the DiffBot task instance (see "Where to resume" above)

---

## ⏳ Pending — Phase 1 (Foundation, target ~4 weeks)

### T1.2 — Write V1 DiffBot task instance
- **Blocked by:** T1.1 (✅)
- **Blocking:** T1.3 (logically; runner can be built against sample fixture in parallel)
- **Files:** `tasks/index.yaml`, `tasks/instances/diffbot-experiment-design/{task.yaml,rubric.md}`
- **Size:** S
- **Acceptance:**
  - 40-char SHA on `ros2_control_demos` recorded
  - `task.yaml` validates: `python harness/validate_task.py tasks/instances/diffbot-experiment-design/task.yaml`
  - Rubric has 5–7 dimensions, each with 0–3 scoring guidance (suggested: hypothesis, controlled variables, recorded signals, success thresholds, visualization plan, failure modes; possibly: integration scheme awareness)
  - Registered in `tasks/index.yaml`
  - `scope_files` set narrowly (e.g., `EXPERIMENT.md` only) so scope-discipline metric is meaningful

### T1.3 — Implement experiment runner
- **Blocked by:** T1.1 (✅) — schema-only dependency
- **Blocking:** T1.4
- **Files:** `harness/run_experiment.py`, `harness/__init__.py`
- **Size:** M
- **Acceptance:**
  - Input: `(plugin_tag, task_id, run_id)`
  - Creates worktree at `base_sha` under `/tmp/exp-scratch/<run_id>/`
  - Materializes the plugin at the requested tag
  - Invokes `claude -p` per ADR-0006 (`--plugin-dir`, `--dangerously-skip-permissions`, `--output-format json`, `--no-session-persistence`)
  - Sets env vars: `BENCHMARK_SCOPE_FILES`, optional `BENCHMARK_SEED`
  - Captures: transcript, final diff, files-modified, runtime, exit code
  - Idempotent: re-running same triple is rejected, not silently overwritten
  - Crash partway through → parseable partial `result.json` with `status: "incomplete"`
  - Worktree cleanup on success, retained on failure
- **Notes:** No `--max-turns` flag exists; use `subprocess.Popen(timeout=…)` for wall-clock cap.

### T1.4 — Implement scope-check + rubric scorer
- **Blocked by:** T1.3
- **Blocking:** T1.5
- **Files:** `harness/scope_check.py`, `harness/score_rubric.py`, `harness/tests/test_scope_check.py`
- **Size:** M
- **Acceptance:**
  - `scope_check.py`: given a diff and `scope_files` glob list, returns `{out_of_scope_count, out_of_scope_paths}`. Unit-tested with constructed diff.
  - `score_rubric.py`: given `(task, agent_output, rubric)`, subprocesses `claude -p --output-format json` (no plugin loaded) per ADR-0006. Scores each rubric dimension 0–3. Runs N=3 trials with different seeds. Returns `{per_trial: [...], mean: {...}, stdev: {...}}`.
  - `pytest harness/tests/` passes

### T1.5 — Run V1 baseline (3 trials at unmodified fork)
- **Blocked by:** T1.4
- **Files:** `experiments/<id>/...`, `analysis/baseline-v0.1.0.md`
- **Size:** S (mostly waiting for runs)
- **Acceptance:**
  - Tag `elliewlh2094/robotics-agent-skills` as `v0.1.0` (unmodified fork)
  - 3 baseline runs complete; each has a valid `result.json`
  - Variance documented in `analysis/baseline-v0.1.0.md`

### ✅ Checkpoint A — gate before plugin work begins
- One full experiment loop runs end-to-end with rubric + scope-check
- Variance across 3 baseline runs is measured (essential for distinguishing real plugin deltas from noise per ADR-0003)
- No vendored task code; all references via URL+SHA per ADR-0001
- **Pause and review.**

---

## ⏳ Pending — Phase 2 (First plugin iteration, ~2 weeks after Checkpoint A)

> Phase 2 happens in the **plugin repo**, not this one.

| ID | Task | Where | Size |
|---|---|---|---|
| T2.1 | Restructure plugin to phase folders, tag `v0.1.1` (refactor only — see ADR-0005) | plugin repo | M |
| T2.2 | Author `design-robotics-experiment` skill | plugin repo | S |
| T2.3 | Add `pre-commit-scope-check` hook | plugin repo | S |
| T2.4 | Run V1 task at `v0.2.0`, write comparison report | this repo | S |

### ✅ Checkpoint B — feedback loop validated
- v0.1.0 vs v0.2.0 measured; delta is signal-or-noise, classified honestly per ADR-0003
- Total loop time per experiment is measured

---

## ⏳ Pending — Phase 3 (TDD + debugging task type, ~2 weeks after Checkpoint B)

> Phase 3 reinstates the Gazebo criterion (the V1 relaxation in ADR-0007 does NOT propagate).

| ID | Task | Files | Size |
|---|---|---|---|
| T3.1 | Define test-pass task instance + Dockerfile (Gazebo-shipping ROS 2 repo) | `tasks/instances/<id>/`, `harness/docker/<id>/` | M |
| T3.2 | Implement `harness/score_tests.py` (FAIL_TO_PASS / PASS_TO_PASS) | `harness/score_tests.py` | M |
| T3.3 | Run debugging task against v0.2.0 (baseline for v0.3.0) | `experiments/` | S |
| T3.4 | Author `robot-debugging` skill, tag `v0.3.0` | plugin repo | M |
| T3.5 | Re-run debugging task at v0.3.0, write report | `experiments/`, `analysis/reports/` | S |

### ✅ Checkpoint C — two task types, three plugin versions

---

## ⏳ Pending — Phase 4 (Spec + planning task type, ~2 weeks after Checkpoint C)

Mirrors Phase 3: rubric-typed spec/planning task → baseline → add `define-robotics-spec` or `plan-robotics-tasks` skill → tag `v0.4.0` → re-run → report.

### ✅ Checkpoint D — all three V1-selected activities measured (per ADR-0004)

---

## ⏳ Pending — Phase 5+ (long-term cadence)

- **Monthly:** lowest-scoring rubric dimension drives next plugin change. One skill or hook per tag (ADR-0005).
- **Quarterly:** review entire task list, retire stale tasks, add UAV/arm tasks once UGV path is mature.
- **Per-experiment:** human spot-check 1-in-5 (ADR-0003); log judge-vs-human disagreement in `analysis/judge-drift.md`.

See `docs/roadmap.md` for the full long-term scope (other activities, hardware classes, integration tech, sub-agent and hook candidates).

---

## 🚦 Decisions already made (don't re-litigate)

All architectural decisions are recorded in `docs/decisions/`. Quick map:

| Decision | ADR |
|---|---|
| Three-surface topology: meta-repo + plugin repo + URL+SHA task refs | [0001](docs/decisions/0001-three-surface-repo-topology.md) |
| Parallel runs use git worktrees, not branches | [0002](docs/decisions/0002-git-worktrees-for-parallel-runs.md) |
| Hybrid scoring: automated + LLM-judge rubric + human spot-check | [0003](docs/decisions/0003-hybrid-scoring.md) |
| V1 ships only experiment-design; debugging is Phase 3, spec/planning Phase 4 | [0004](docs/decisions/0004-v1-staged-activities.md) |
| One logical change per plugin tag | [0005](docs/decisions/0005-one-change-per-plugin-tag.md) |
| Headless `claude -p` for both runner and judge (no separate API key on Max plan) | [0006](docs/decisions/0006-headless-claude-code-for-runner-and-judge.md) |
| V1 sim_engine relaxed (mock hardware OK); Gazebo direction unchanged for Phase 3+ | [0007](docs/decisions/0007-v1-sim-engine-relaxation.md) |

---

## ⚠️ Open issues / things to flag

1. **PyYAML 5.4.1 is older** (current is 6.x). Not blocking — schema's `pattern` regex catches the YAML→int autocast bug for unquoted SHAs. Worth upgrading at some point.
2. **No automated cleanup of stale worktrees** under `/tmp/exp-scratch/`. Worktrees from failed runs persist by design (per ADR-0002), but no periodic prune is scheduled. Add a cron or a `harness/prune.py` once we have >10 stale entries.
3. **Judge-drift detection requires human spot-check 1-in-5** per ADR-0003, but no tooling exists yet to surface "which results need human review." Build into Phase 5 cadence work, not blocking V1.
