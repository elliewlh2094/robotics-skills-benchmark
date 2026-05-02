# Adding a benchmark task

A task instance is the unit of measurement in this benchmark. It defines what the agent is
asked to do, what it's allowed to touch, and how the result is scored.

## Quick checklist

1. Pick a public GitHub repo. Note its URL and the commit SHA you want to pin.
2. Create `tasks/instances/<task-id>/task.yaml` (kebab-case task-id matches folder name).
3. If `verification_method: rubric` or `hybrid`, write `rubric.md` in the same folder.
4. If `verification_method: unit-test`, `sim-metric`, or `hybrid`, write `verify.sh` in the same folder.
5. Validate: `python -m jsonschema -i tasks/instances/<task-id>/task.yaml tasks/schema.yaml`.
6. Register in `tasks/index.yaml` under the `tasks:` list.

## Schema reference

Full schema lives at `tasks/schema.yaml`. Required fields:

| Field | Type | Notes |
|---|---|---|
| `task_id` | string | Kebab-case. Must match folder name. |
| `base_repo` | URL | `https://github.com/owner/repo` |
| `base_sha` | 40-char hex | Pin to a commit, **not** a branch |
| `problem_statement` | string | Prompt given to the agent. State explicitly where output should land. |
| `solution_type` | enum | `bugfix \| spec \| design \| perf \| refactor` |
| `verification_method` | enum | `unit-test \| sim-metric \| rubric \| hybrid` |
| `scope_files` | array of globs | Files the agent is allowed to write |
| `timeout_s` | int (60–14400) | Hard wall-clock cap |

Optional but commonly set:

| Field | When to use |
|---|---|
| `rubric_path` | Required for `rubric` / `hybrid` verification |
| `verify_script` | Required for `unit-test` / `sim-metric` / `hybrid` |
| `sim_engine` | `gazebo` for V1/V2 tasks; `none` if no sim needed |
| `seed_required` | `true` for sim-metric tasks where nondeterminism matters |

## Walked example

A design task pointing at a fictional ROS 2 navigation repo:

```yaml
# tasks/instances/nav2-experiment-design/task.yaml
task_id: nav2-experiment-design
base_repo: https://github.com/example/nav2-tutorial
base_sha: a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0
problem_statement: |
  The repository contains a ROS 2 node `wall_follower` that uses a 2D LiDAR to maintain
  a constant distance from the right-hand wall. We suspect the controller becomes unstable
  at speeds above 1.0 m/s.

  Write an experiment plan to EXPERIMENT.md that would validate or refute this hypothesis
  in Gazebo. Include: hypothesis, controlled variables, signals to record, success
  thresholds, visualization plan, and failure modes.

  Do not modify the source code. Do not run anything — just produce the plan.
solution_type: design
verification_method: rubric
scope_files:
  - "EXPERIMENT.md"
rubric_path: rubric.md
timeout_s: 1800
sim_engine: gazebo
seed_required: false
description: |
  Tests whether the agent can produce a thoughtful experiment plan grounded in the
  repo's actual node structure, vs. a generic checklist.
```

## Choosing scope_files well

`scope_files` is enforced by the `pre-commit-scope-check` hook in the plugin. The harness
sets `BENCHMARK_SCOPE_FILES` to this list before invoking the agent.

- **Be specific.** `"**/*"` defeats the scope-discipline measurement.
- **Allow the output target.** If `problem_statement` says "write to EXPERIMENT.md",
  `EXPERIMENT.md` must be in `scope_files`.
- **Don't allow the source code unless the task requires editing it.** A design task should
  typically only allow the output document. A bugfix task should allow the buggy file(s).
- **Include test files only if the task asks for tests.** Otherwise the agent will write
  "tests" to game the rubric.

## Validation

The schema is in YAML, so we use a small wrapper instead of the `jsonschema` CLI directly
(its CLI is JSON-only).

```bash
# Validate one instance:
python harness/validate_task.py tasks/instances/<task-id>/task.yaml

# Validate every instance at once:
python harness/validate_task.py --all
```

Output is one line per file: `OK <path>` or `FAIL <path>` followed by indented error
messages. Exit code is non-zero if any instance fails.

> **YAML gotcha:** quote `base_sha`. A SHA like `0000000000000000000000000000000000000000`
> is parsed as the integer `0` by PyYAML 5.x unless quoted. The schema rejects non-strings.

## Sanity-checking a new rubric

After writing `rubric.md`, do a dry run:

1. Hand-write a "definitely good" sample answer and a "definitely bad" sample answer.
2. Run `harness/score_rubric.py` against each.
3. The good one should score ≥2.5 mean across dimensions; the bad one should score ≤1.0.
4. If the rubric can't distinguish them, it won't distinguish plugin versions either.
   Revise the rubric before submitting the task.
