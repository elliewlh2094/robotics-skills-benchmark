# `result.json` reference

> **Canonical** — this is the source of truth for the field shape and semantics of every `experiments/<...>/result.json`. The machine-verifiable counterpart is [`harness/schemas/result.schema.yaml`](../harness/schemas/result.schema.yaml). The decision to consolidate is recorded in [ADR-0008](decisions/0008-canonical-result-json-schema.md).

## How to read this

Every experiment writes one `result.json` under `experiments/<YYYY-MM-DD>_<plugin_tag>_<task_id>_<run_id>/`. The file goes through up to two states on disk:

| State | When written | `status` field |
|---|---|---|
| **Partial** | Before the agent is invoked, by `run_experiment.py:run()`. | `incomplete` |
| **Final** | After the agent returns (or times out, or the runner catches an exception). | `success` \| `error` \| `timeout` |

The schema enforces this state machine: identification fields are required in **both** states; timing/status fields (`completed_at`, `runtime_s`, `exit_code`) may be null in the partial but **must** be non-null in any terminal state. `error` is null on `success` and on the unmodified partial; populated otherwise.

`write_result()` validates against the schema before persisting (per [ADR-0008](decisions/0008-canonical-result-json-schema.md)). On schema failure, the rejected payload is preserved at `<exp_dir>/result.invalid.json` for forensics and `ResultSchemaError` is raised.

## Field reference

Columns: **Field** | **Type** (JSON Schema notation; `T \| null` = nullable) | **When present** | **Writer** (module:function) | **Semantics**.

### Identification (always required)

| Field | Type | When | Writer | Semantics |
|---|---|---|---|---|
| `schema_version` | `integer (const: 1)` | Always | `run_experiment.py:run()` partial | Bumps on any shape change. Schema and `RESULT_SCHEMA_VERSION` constant move together. |
| `experiment_id` | `string` | Always | `run_experiment.py:run()` partial | Directory name `<YYYY-MM-DD>_<plugin_tag>_<task_id>_<run_id>` (UTC). |
| `plugin_tag` | `string` | Always | `run_experiment.py:run()` partial | Caller-supplied label (e.g., `v0.1.0`). Need not match a git ref. |
| `plugin_path` | `string` | Always | `run_experiment.py:run()` partial | Absolute path passed to `claude --plugin-dir`. |
| `plugin_repo` | `string \| null` | Always (null in `--plugin-path` mode) | `run_experiment.py:run()` partial | URL when sourced via `--plugin-repo + --plugin-ref`. |
| `plugin_ref` | `string \| null` | Always (null in `--plugin-path` mode) | `run_experiment.py:run()` partial | Git ref the runner asked git to check out. Branches drift; `plugin_sha` is canonical. |
| `plugin_sha` | `string \| null` (`^[a-f0-9]{40}$`) | Always (null when `plugin_path` is not a git working tree) | `run_experiment.py:resolve_git_sha()` | The reproducibility key per [ADR-0001](decisions/0001-three-surface-repo-topology.md). |
| `task_id` | `string` | Always | `run_experiment.py:run()` partial | Subdirectory name under `tasks/instances/`. |
| `run_id` | `string` | Always | `run_experiment.py:run()` partial | Caller-supplied (e.g., `baseline-1`). Idempotency key with `(plugin_tag, task_id, run_id)`. |
| `base_repo` | `string` | Always | `run_experiment.py:run()` partial | HTTPS URL from `task.yaml`. |
| `base_sha` | `string` (40 hex) | Always | `run_experiment.py:run()` partial | 40-char commit SHA pinned in `task.yaml`. |

### Task configuration echoed for self-contained results

| Field | Type | When | Writer | Semantics |
|---|---|---|---|---|
| `scope_files_declared` | `array<string>` | Always | `run_experiment.py:run()` partial | Echo of `task.scope_files`. Re-scoring works without re-reading `task.yaml`. |
| `available_tools` | `array<string> \| null` | Always (null when task didn't declare one) | `run_experiment.py:run()` partial | Echo of `task.available_tools`; null path uses `--dangerously-skip-permissions`. |
| `max_turns` | `integer (≥1)` | Always | `run_experiment.py:run()` partial | Hard cap passed to `claude --max-turns`. |
| `seed` | `string \| null` | Always (null when task is not seed-required) | `run_experiment.py:run()` partial | `BENCHMARK_SEED` env var passed to the agent. |

### Timing and status

| Field | Type | When | Writer | Semantics |
|---|---|---|---|---|
| `started_at` | `string` (ISO-8601 UTC) | Always | `run_experiment.py:run()` partial | Set when partial is written. |
| `completed_at` | `string \| null` | Null on partial; non-null in any terminal status | `run_experiment.py:run_agent()` → `run()` final write | ISO-8601 UTC. |
| `runtime_s` | `number \| null (≥0)` | Null on partial; non-null in any terminal status | `run_experiment.py:run_agent()` | Wall-clock seconds, agent invocation → completion. |
| `exit_code` | `integer \| null` | Null on partial; non-null in any terminal status | `run_experiment.py:run_agent()` | `Popen.returncode` semantics. `-1` = runner-killed (timeout). |
| `status` | `enum [success, error, timeout, incomplete]` | Always | `run_experiment.py:run_agent()` → `run()` exception handler | See state machine above. |
| `error` | `null \| {type: string, message: string}` | Always; null when `status==success`; non-null when `status∈{error, timeout}` | `run_experiment.py:run_agent()` / `run()` exception handler | Conditional shape enforced by schema. |

### Output artifacts

| Field | Type | When | Writer | Semantics |
|---|---|---|---|---|
| `files_modified` | `array<string>` | Always (`[]` on partial) | `run_experiment.py:capture_diff()` | Output of `git diff --cached --name-only` vs `base_sha`. Includes new and deleted files. |
| `transcript_bytes` | `integer (≥0)` | Always (`0` on partial) | `run_experiment.py:run()` post-agent | Size of agent stdout in bytes. Full content lives in sidecar `transcript.md`. |

### Scoring

The `scoring` object is always present (empty `{}` on the partial). Its sub-fields are appended by the scorers as they run. New scorer types add new sub-fields with each schema-version bump.

| Field | Type | When | Writer | Semantics |
|---|---|---|---|---|
| `scoring` | `object` | Always (`{}` on partial) | `run_experiment.py:compute_scoring()` | Container; `additionalProperties: true` for forward compatibility. |
| `scoring.scope_check` | `{out_of_scope_count: int≥0, out_of_scope_paths: array<string>}` | Always present after `capture_diff()` | `harness.scope_check.compute_scope_violations` | Files the agent touched outside `scope_files_declared`. Reliability criterion C4. |
| `scoring.rubric` | `oneOf(success, failure)` (see below) | When `task.verification_method ∈ {rubric, hybrid}` and a rubric is set | `harness.score_rubric.score_rubric` | Aggregated N-trial LLM judge per [ADR-0003](decisions/0003-hybrid-scoring.md). |

**`scoring.rubric` success branch:**

| Sub-field | Type | Semantics |
|---|---|---|
| `n_trials` | `integer (≥1)` | Number of judge invocations. V1 default: 3. |
| `per_trial[]` | `array<{scores, overall_recomputed, overall_judge_reported, rationale}>` | One entry per judge call; preserved for audit. |
| `per_trial[].scores` | `{dim: number}` | Judge's per-dimension score (rubric defines dimensions). |
| `per_trial[].overall_recomputed` | `number` | Mean of `scores` values. **Aggregated, not the judge's claim.** |
| `per_trial[].overall_judge_reported` | `number \| null` | The judge's `overall` field; preserved for audit; **not** used in aggregation. |
| `per_trial[].rationale` | `string` | The judge's free-form justification. |
| `mean` | `{dim: number}` | Per-dimension arithmetic mean across trials. |
| `stdev` | `{dim: number (≥0)}` | Per-dimension sample stdev (`statistics.stdev`). N=1 → 0.0 by convention. |
| `overall_mean` | `number` | Mean of `per_trial[].overall_recomputed`. |
| `overall_stdev` | `number (≥0)` | Sample stdev across trials. The noise floor for plugin-version comparisons. |

**`scoring.rubric` failure branch** (when the judge subprocess fails):

| Sub-field | Type | Semantics |
|---|---|---|
| `error.type` | `string` | Exception class (e.g., `JudgeInvocationError`). |
| `error.message` | `string` | Detail string. |

### Optional, only present when retained for debugging

| Field | Type | When | Writer | Semantics |
|---|---|---|---|---|
| `scratch_dir` | `string` | Present on `status ∈ {error, timeout, incomplete}` when worktree was created and not pruned (per [ADR-0002](decisions/0002-git-worktrees-for-parallel-runs.md)) | `run_experiment.py:run()` finally clause | Filesystem path of the retained task worktree. Absent on success. |

## Examples

### Minimal valid partial

```json
{
  "schema_version": 1,
  "experiment_id": "2026-05-03_v0.1.0_diffbot-experiment-design_baseline-1",
  "plugin_tag": "v0.1.0",
  "plugin_path": "/home/u/.cache/.../v0.1.0",
  "plugin_repo": null,
  "plugin_ref": null,
  "plugin_sha": null,
  "task_id": "diffbot-experiment-design",
  "run_id": "baseline-1",
  "base_repo": "https://github.com/ros-controls/ros2_control_demos",
  "base_sha": "c555233658e8c0794f9bb6e1ea4059ca84bcd503",
  "scope_files_declared": ["EXPERIMENT.md"],
  "available_tools": ["Read", "Glob", "Grep", "Write", "Edit"],
  "max_turns": 50,
  "seed": null,
  "started_at": "2026-05-03T12:00:00Z",
  "completed_at": null,
  "runtime_s": null,
  "exit_code": null,
  "status": "incomplete",
  "error": null,
  "files_modified": [],
  "transcript_bytes": 0,
  "scoring": {}
}
```

### Minimal valid `success` (rubric task)

Same as above with these overrides:

```json
{
  "completed_at": "2026-05-03T12:30:00Z",
  "runtime_s": 1800.5,
  "exit_code": 0,
  "status": "success",
  "files_modified": ["EXPERIMENT.md"],
  "transcript_bytes": 12345,
  "scoring": {
    "scope_check": {"out_of_scope_count": 0, "out_of_scope_paths": []},
    "rubric": {
      "n_trials": 3,
      "per_trial": [
        {"scores": {"hypothesis": 2, "signals": 3}, "overall_recomputed": 2.5,
         "overall_judge_reported": 2.5, "rationale": "..."}
      ],
      "mean": {"hypothesis": 2.0, "signals": 3.0},
      "stdev": {"hypothesis": 0.0, "signals": 0.0},
      "overall_mean": 2.5,
      "overall_stdev": 0.0
    }
  }
}
```

### Minimal valid `error`

```json
{
  "status": "error",
  "completed_at": "2026-05-03T12:05:00Z",
  "runtime_s": 300.0,
  "exit_code": 1,
  "error": {"type": "non-zero-exit", "message": "claude exited with code 1"},
  "scratch_dir": "/tmp/exp-scratch/v0.1.0__diffbot-experiment-design__baseline-1"
}
```

## Planned (not yet in schema)

These fields are referenced in [`docs/reliability-criteria.md`](reliability-criteria.md) but are **not** part of schema v1. Each lands in the PR that implements the producing feature, with a schema version bump (per [ADR-0008](decisions/0008-canonical-result-json-schema.md)). The canonical task entries that will add them:

| Planned field | Reliability criterion | Adding task | Notes |
|---|---|---|---|
| `skills_invoked` | C1 (auditability) | Phase 2 (when transcript-extraction lands; not yet a numbered task) | List of plugin skills the agent loaded during the run. Source: `claude -p` output stream. |
| `hook_blocks` | C4 (scope-discipline) | T2.3 (`pre-commit-scope-check` hook in plugin) | Count of out-of-scope edit attempts the hook rejected. Source: hook stderr or transcript. |
| `static_check` | C2 (verifiability) | Phase 3+ (refactor-task scoring) | Result of language-server or formatter checks for refactor tasks. |
| `judge_calls` | Cost proxy | Optional; today inferable from `scoring.rubric.n_trials` | Total judge subprocess invocations including retries. |

## Related documents

- [ADR-0001](decisions/0001-three-surface-repo-topology.md) — reproducibility tuple, why `plugin_sha` is the canonical pin.
- [ADR-0002](decisions/0002-git-worktrees-for-parallel-runs.md) — `scratch_dir` retention policy on failure.
- [ADR-0003](decisions/0003-hybrid-scoring.md) — N=3 trials with mean ± stdev; recompute-overall-from-scores convention.
- [ADR-0006](decisions/0006-headless-claude-code-for-runner-and-judge.md) — runner CLI flags and `--bare` for the judge.
- [ADR-0008](decisions/0008-canonical-result-json-schema.md) — this consolidation.
- [`docs/spec.md`](spec.md) — FR3 references this file for field shape; the spec keeps narrative about *which* metrics matter and *why*.
- [`docs/reliability-criteria.md`](reliability-criteria.md) — maps the five reliability criteria to specific result.json fields.
