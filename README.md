# robotics-skills-benchmark

A research harness for iteratively improving a Claude Code plugin specialized for robotics software development.

## What this is

This repository is the **meta-research harness** for the plugin under iteration:
[`elliewlh2094/robotics-agent-skills`](https://github.com/elliewlh2094/robotics-agent-skills)
(forked from `arpitg1304/robotics-agent-skills`).

Inspired by [SWE-bench](https://github.com/swe-bench/SWE-bench), it works the same way at a glance —
give an AI agent a real GitHub repo and a task, then measure whether the agent solved it. But
the scoring extends beyond test-pass to cover the activities general-purpose plugins handle poorly
on robotics work: experiment design, debugging, spec writing, and planning.

## Repository layout

| Directory | Purpose |
|---|---|
| `tasks/` | Benchmark task definitions: `index.yaml` registry + per-task instance folders |
| `harness/` | Eval-runner code: experiment runner, scorers, Docker environments |
| `experiments/` | One folder per `(plugin-version, task, run)` triple; contains `result.json` and artifacts |
| `analysis/` | Cross-experiment analysis scripts and reports |
| `docs/` | Reliability criteria, contributor guides, feedback-loop documentation |

External task repositories are referenced **by URL + commit SHA** in `tasks/index.yaml` —
nothing is vendored or submoduled. The repo stays lightweight as the task set grows.

## How an experiment works

```
python harness/run_experiment.py --plugin v0.1.0 --task <task-id> --run baseline-1
```

1. Clones the task repo at the pinned commit into a scratch git worktree
2. Materializes the plugin at the requested git tag
3. Invokes Claude Code with the plugin loaded and the task's `problem_statement` as prompt
4. Captures transcript, diff, files-modified, runtime
5. Scores via `score_rubric.py` (LLM-judge, N=3 trials) and/or `score_tests.py` (test-pass)
6. Writes everything to `experiments/<YYYY-MM-DD>_<plugin-tag>_<task-id>_<run-id>/`

## Adding a benchmark task

See [`docs/adding-a-task.md`](docs/adding-a-task.md).

## Reliability definition

This project operationalizes 5 reliability criteria (auditability, verifiability, output-stability,
scope-discipline, recoverability). See [`docs/reliability-criteria.md`](docs/reliability-criteria.md)
for how each maps to specific fields captured in every `result.json`.

## Status

Phase 1 (foundation) — see plan at `/home/starlab/.claude/plans/i-want-to-conduct-federated-stream.md`.

For the long-term vision (V1 deliverables, near-term versions, full original scope, deliberate
non-goals), see [`docs/roadmap.md`](docs/roadmap.md).
