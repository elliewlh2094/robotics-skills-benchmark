# CLAUDE.md — context for future sessions

## What this project is

Long-term research harness for iteratively improving the Claude Code plugin
`elliewlh2094/robotics-agent-skills` (forked from `arpitg1304/robotics-agent-skills`).

The user (Ellie Huang, `applejuicepie@gmail.com`) is conducting an informal research project.
The plan lives at `~/.claude/plans/i-want-to-conduct-federated-stream.md`.

## Architectural decisions (do not relitigate without reason)

The canonical record is `docs/decisions/` (ADRs). Cliff-notes:

1. **Repository topology** — harness here, plugin separate repo (versioned by tag), external tasks referenced by URL+SHA. No vendoring, no submodules, parallel runs via worktrees. → [ADR-0001](docs/decisions/0001-three-surface-repo-topology.md), [ADR-0002](docs/decisions/0002-git-worktrees-for-parallel-runs.md)

2. **Hybrid scoring** — automated metrics + LLM-judge rubric (N=3 trials, mean+stdev) + test-pass (Docker) + human spot-check 1-in-5. → [ADR-0003](docs/decisions/0003-hybrid-scoring.md)

3. **V1 stages activities** — experiment-design only at V1; debugging Phase 3; spec/planning Phase 4. → [ADR-0004](docs/decisions/0004-v1-staged-activities.md)

4. **One change per plugin tag** — bundles forbidden; refactor-only tags as harness sanity checks. → [ADR-0005](docs/decisions/0005-one-change-per-plugin-tag.md)

5. **Headless `claude -p` for runner AND judge** — Max plan covers both; no separate API key. CLI flags must be verified via `claude --help` (a research agent hallucinated `--max-turns`). → [ADR-0006](docs/decisions/0006-headless-claude-code-for-runner-and-judge.md)

6. **V1 `sim_engine` relaxed** — V1 task is design-only, so mock-hardware repos are OK. Gazebo reinstated as baseline from Phase 3 onward. → [ADR-0007](docs/decisions/0007-v1-sim-engine-relaxation.md)

7. **Plugin progression** — `arpitg1304/robotics-agent-skills` has 10 knowledge skills; we add the behavioral layer (phased workflow skills, sub-agents, hooks). Hooks are load-bearing for the scope-discipline reliability criterion, not polish.

8. **Judge isolation via cwd, not `--bare`** — judge subprocess runs without `--bare` in a per-process tempdir under `/tmp/robotics-benchmark-judge-cwd-…`; project-local plugins (`agent-skills`, `explanatory-output-style`) are excluded by cwd. Six user-level plugins are loaded and accepted for V1; revisit at Phase 3 when debugging tasks may overlap with `andrej-karpathy-skills`. Smoke test (`harness/smoke_test_judge.py`) verifies via `system/init` event before each plugin-version baseline. → [ADR-0009](docs/decisions/0009-judge-isolation-without-bare-mode.md)

## Workflow rules

- **Never run `git commit` without explicit per-message approval.**
  Staging (`git add`) is fine without asking. Before commit:
  1. Show the *exact* commit message text you would use.
  2. Wait for an explicit "commit it" (or equivalent) reply from the user.
  3. Only then run `git commit`.
  Approval of commit *structure* (e.g., "split into two", "one commit is fine")
  does NOT carry forward as approval of the message text. Same rule applies to
  `git push`, `git reset --hard`, `git rebase`, and any other history-affecting
  operation.

## Common gotchas

- `data_for_presentation/` is gitignored (presentation materials, not part of the project).
- The plugin under test lives in a separate repo. To work on it, `cd` to its checkout —
  this repo only contains the harness and task definitions.
- When adding a task: write `task.yaml`, validate against `tasks/schema.yaml`, register in
  `tasks/index.yaml`. See `docs/adding-a-task.md`.
- Rubric scoring is non-deterministic by design. Trust the mean ± stdev across N=3 trials,
  not any single score.
- **Runner permissions: `--tools` AND `--allowedTools` must both be passed (with the same
  list).** `--tools` restricts availability; `--allowedTools` auto-approves. Without
  `--allowedTools`, headless mode prompts on every Write/Edit and the agent stalls — the
  run completes `status: "success"` with zero deliverable. Surfaced in T1.5 dry-run #1
  (2026-05-04); fix in `harness/run_experiment.py:run_agent()`. ADR-0006 amended 2026-05-05.
- **`status: "no-deliverable"` ≠ `"success"`.** When the agent runs cleanly but produces
  no in-scope file, the runner flips status to `no-deliverable`, skips the judge, and
  omits `rubric_scores`. A 0.0 rubric score should mean "judge measured zero quality,"
  not "there was nothing to measure." See `docs/result-json-reference.md` Lifecycle.

## Reliability criteria → result.json fields

Every `experiments/<id>/result.json` must capture evidence for all 5 reliability criteria.
See `docs/reliability-criteria.md` for the full mapping.

## Where things are

| Need | Location |
|---|---|
| Architectural decisions (canonical) | `docs/decisions/` (ADRs) |
| V1 plan (canonical) | `docs/v1-plan.md` |
| V1 task breakdown (per planning-and-task-breakdown skill format) | `docs/v1-tasks.md` |
| Long-term vision and scope boundaries | `docs/roadmap.md` |
| Spec / PRD | `docs/spec.md` |
| Operational pointer ("where am I right now") | `TODO.md` |
| Candidate task repositories (investigated, archived for later use) | `docs/candidate-repos.md` |
| Skill: record a new investigated repo into the candidate KB | `.claude/skills/record-candidate-repo/SKILL.md` |
| Add a new benchmark task | `tasks/instances/<task-id>/` + register in `tasks/index.yaml` |
| Modify the runner | `harness/run_experiment.py` |
| Tweak scoring | `harness/score_rubric.py` or `harness/score_tests.py` |
| Add a new sim Dockerfile | `harness/docker/<task-id>/` |
| Read past experiments | `experiments/<YYYY-MM-DD>_<tag>_<task>_<run>/result.json` |
| `result.json` field reference (canonical) | `docs/result-json-reference.md` (human) + `harness/schemas/result.schema.yaml` (machine, validated on every write) |
| Cross-version analysis | `analysis/reports/` |
