# `result.json` field reference

> **What this document is.** The human-readable canonical reference for
> `experiments/<...>/result.json`. The machine-readable counterpart is
> [`harness/schemas/result.schema.yaml`](../harness/schemas/result.schema.yaml),
> which is validated on every write inside
> [`harness/run_experiment.py:write_result()`](../harness/run_experiment.py).
>
> **Scope.** What each field means, when it's required, when it's nullable, and
> which module writes it. **Not** the field shapes — those are in the schema.
>
> **Decision context.** [ADR-0008](decisions/0008-result-json-schema-and-reference.md)
> records *why* this canonical pair exists.
>
> **Last updated:** 2026-05-05 (added `no-deliverable` lifecycle state — see Lifecycle below).

---

## Lifecycle

`status` traces the experiment's progress through five states:

```
                          ┌─────────────┐
   write_result() called  │ incomplete  │   first persisted record
   before the agent runs  └──────┬──────┘   (set in run() step 5)
                                 │
                                 │  agent subprocess returns
                                 ▼
            ┌──────────┬──────────┼──────────┬──────────┐
            ▼          ▼          ▼          ▼          ▼
        ┌────────┐ ┌────────────┐ ┌─────────┐ ┌─────────┐
        │success │ │no-deliver- │ │  error  │ │ timeout │
        │        │ │   able     │ │         │ │         │
        └────────┘ └────────────┘ └─────────┘ └─────────┘
        normal     agent ran      agent       wall-clock
        exit AND   cleanly but    crash       limit hit
        deliv-     produced no    OR runner
        erable     in-scope file  crash
        produced
```

**Invariants per state** (enforced by schema; see
[`harness/schemas/result.schema.yaml`](../harness/schemas/result.schema.yaml)):

| `status` | `error` | `scratch_dir` | `scoring` | `completed_at` |
|---|---|---|---|---|
| `incomplete`     | null | required | `{}` | null |
| `success`        | null | **forbidden** | `scope_check` required, `rubric_scores` present (when configured) | required |
| `no-deliverable` | null | **forbidden** | `scope_check` required, `rubric_scores` **absent** | required |
| `error`          | required | required | scope_check usually present | required |
| `timeout`        | required | required | scope_check usually present | required |

**Why `no-deliverable` exists.** A 0.0 in `rubric_scores` should mean "the
judge measured zero quality." It must NOT mean "there was nothing to
measure." Conflating the two would let a permission-bug regression silently
masquerade as a quality regression in cross-version comparisons (Phase 2
onward). The orchestrator detects empty deliverables via
`gather_deliverable()`'s `NO_DELIVERABLE_MARKER` sentinel, skips the judge
entirely (saving N=3 wasted invocations), and flips status from `success`
to `no-deliverable`. Surfaced in T1.5 dry-run #1 (2026-05-04) where the
runner had a permissions wiring bug; documented here so the lifecycle is
discoverable from the schema, not just from the orchestrator code.

The `scratch_dir` rule (refinement A in ADR-0008) means the worktree path is
recorded from the very first persisted record. If the runner crashes between
the partial-write and `add_worktree`, the file on disk honestly says where
the worktree *would* have been.

---

## Plugin sourcing

Two modes, distinguished by the *value* of `plugin_repo`/`plugin_ref`
(both null = local mode; both non-null = clone-and-ref mode):

| Mode | `plugin_path` | `plugin_repo` | `plugin_ref` |
|---|---|---|---|
| Local (`--plugin-path`) | path string | `null` | `null` |
| URL+ref (`--plugin-repo` + `--plugin-ref`) | path string (the materialized worktree) | URL string | git ref string |

In URL+ref mode the runner clones to `~/.cache/robotics-skills-benchmark/plugins/`
and reassigns `plugin_path` to the materialized worktree, so `plugin_path` is
always a string regardless of mode. The `oneOf` constraint in the schema
inspects values, not key presence (refinement B in ADR-0008).

The canonical reproducibility key is **`plugin_sha`**, not `plugin_tag` (a
human label) or `plugin_ref` (which can move). See
[ADR-0001](decisions/0001-three-surface-repo-topology.md).

---

## Field reference

> **Reading guide.** "Required when" describes when the field must be
> present in the persisted record. "Nullable when" describes when its value
> may be `null`. Writer paths are relative to repo root; line numbers move
> with the codebase but the function name stays stable.

### Identity & reproducibility

| Field | Type | Required when | Nullable when | Writer | Notes |
|---|---|---|---|---|---|
| `schema_version` | int (`= 1`) | always | never | `run_experiment.py:run()` (partial dict) | Bumped only on incompatible shape changes. Part of the reproducibility tuple per ADR-0001. |
| `experiment_id` | string | always | never | `run_experiment.py:run()` | Self-referential: matches the parent dir basename `<YYYY-MM-DD>_<plugin_tag>_<task_id>_<run_id>`. |
| `plugin_tag` | string | always | never | `run_experiment.py:run()` | Human-supplied label (e.g., `v0.1.0`). Need not match `plugin_ref`. Not canonical for reproducibility. |
| `plugin_path` | string | always | never | `run_experiment.py:run()` | Local FS path passed to `claude --plugin-dir`. In URL+ref mode, the materialized cache worktree. |
| `plugin_repo` | string \| null | always | local mode | `run_experiment.py:run()` | URL of plugin repo when URL+ref mode used. Pairs with `plugin_ref`. |
| `plugin_ref` | string \| null | always | local mode | `run_experiment.py:run()` | Git ref (tag/branch/SHA) requested at materialization time. |
| `plugin_sha` | string (40 hex) \| null | always | when `plugin_path` is not a git working tree | `run_experiment.py:resolve_git_sha()` | **Canonical reproducibility key.** Resolved at run time. Runner emits a stderr warning when null. |
| `task_id` | string | always | never | `run_experiment.py:run()` | Matches `tasks/instances/<id>/`. |
| `run_id` | string | always | never | `run_experiment.py:run()` | Distinguishes repeated runs (e.g., `baseline-1`, `baseline-2`). |
| `base_repo` | string (URL) | always | never | `run_experiment.py:run()` | Copied from `task.yaml` at run time. |
| `base_sha` | string (40 hex) | always | never | `run_experiment.py:run()` | Pinned commit the task worktree was checked out at. |

### Run-time configuration snapshot

| Field | Type | Required when | Nullable when | Writer | Notes |
|---|---|---|---|---|---|
| `scope_files_declared` | list[string] | always | never | `run_experiment.py:run()` | Snapshot of `task.yaml` `scope_files` at run time. The `_declared` suffix distinguishes from `out_of_scope_paths` (the *derived* violation list). |
| `available_tools` | list[string] \| null | always | when task didn't declare a list | `run_experiment.py:run()` | Null → runner fell back to `--dangerously-skip-permissions` and emitted a warning. |
| `max_turns` | int (≥1) | always | never | `run_experiment.py:run()` | The `--max-turns` ceiling per ADR-0006. |
| `seed` | string \| null | always | when not set | `run_experiment.py:run()` | `BENCHMARK_SEED` env var. Used by sim-metric tasks (Phase 4+). |

### Lifecycle / outcome

| Field | Type | Required when | Nullable when | Writer | Notes |
|---|---|---|---|---|---|
| `status` | enum | always | never | `run_experiment.py:run()` (initial=incomplete; updated post-agent) | One of `incomplete`, `success`, `no-deliverable`, `error`, `timeout`. See lifecycle diagram above. |
| `started_at` | string (ISO 8601) | always | never | `run_experiment.py:now_utc_iso()` | Initially the partial-write time; overwritten with the agent subprocess's actual start time once it runs. |
| `completed_at` | string \| null | always | when `status=incomplete` | `run_experiment.py:run_agent()` | UTC ISO 8601. Set when agent finishes (success/error/timeout) or runner crashes. |
| `runtime_s` | number \| null | always | when `status=incomplete` | `run_experiment.py:run_agent()` | Wall-clock seconds, agent start to agent end (or crash point). |
| `exit_code` | int \| null | always | when `status=incomplete` | `run_experiment.py:run_agent()` | Subprocess exit. `-1` indicates runner-aborted (timeout or missing binary). |
| `error` | object \| null | always | when `status ∈ {incomplete, success, no-deliverable}` | `run_experiment.py:run_agent()` or `run()` except handler | Shape: `{type: string, message: string}`. `type` examples: `missing-binary`, `non-zero-exit`, `timeout`, exception class names. |
| `files_modified` | list[string] | always | never (empty list when no edits) | `run_experiment.py:capture_diff()` | From `git diff --cached --name-only base_sha` after `git add -A`. Includes untracked files. |
| `transcript_bytes` | int (≥0) | always | never | `run_experiment.py:run_agent()` | `len(agent_stdout)`. The actual transcript is rendered to `transcript.md` alongside. |

### Top-level automated metrics (per ADR-0003)

| Field | Type | Required when | Nullable when | Writer | Notes |
|---|---|---|---|---|---|
| `hook_blocks` | int (≥0) | always | never | `run_experiment.py:run()` (partial=0; populated post-agent) | Count of `pre-commit-scope-check` hook rejections. **Always 0 in Phase 1** — the hook lands at task T2.3 and will populate this from hook output thereafter. Valid 0-state today, not "unknown". |
| `judge_calls` | int (≥0) | always | never | `run_experiment.py:compute_scoring()` (=`n_trials` when rubric ran on a non-empty deliverable, else 0) | Number of LLM-judge subprocess invocations. `0` in the no-deliverable state — judge is skipped to avoid logging "scored 0 because empty" 3× and wasting API budget. Surfaced at top level for cost-tracking analytics in Phase 5+. |

### Scratch / cleanup

| Field | Type | Required when | Nullable when | Writer | Notes |
|---|---|---|---|---|---|
| `scratch_dir` | string | `status ∈ {incomplete, error, timeout}` | never (when present) | `run_experiment.py:run()` (partial dict) | FS path of the task worktree. Set from the very first partial-write (refinement A). **Forbidden when `status ∈ {success, no-deliverable}`** — worktree pruned per ADR-0002 in both terminal-clean states. |

### Scoring

`scoring` is an object with `additionalProperties: true` so future scorers
(Phase 3+ `score_tests.py`, Phase 4+ `sim_metric`, etc.) can add fields
without a schema bump. Today, two sub-keys are defined:

#### `scoring.scope_check`
Always present once `status != incomplete`. Computed by
[`harness/scope_check.py:compute_scope_violations()`](../harness/scope_check.py).

| Field | Type | Notes |
|---|---|---|
| `out_of_scope_file_count` | int (≥0) | Number of paths the agent touched that don't match any pattern in `scope_files`. |
| `out_of_scope_paths` | list[string] | Sorted, deduplicated list of those paths. |

#### `scoring.rubric_scores`
Present iff the task's `verification_method ∈ {rubric, hybrid}` AND
`status != "no-deliverable"`. When `status == "no-deliverable"` the judge
is not invoked (there is nothing to evaluate) and `rubric_scores` is
absent — see Lifecycle above. Two shapes (validated via `oneOf`) when
present:

**Success shape** — `score_rubric()` completed all trials:

| Field | Type | Notes |
|---|---|---|
| `n_trials` | int (≥1) | Number of judge trials run. Default 3 per ADR-0003. |
| `per_trial` | list[object] | One entry per trial — see "per-trial entry" below. |
| `mean` | dict[string, number] | Per-dimension arithmetic mean across trials. |
| `stdev` | dict[string, number] | Per-dimension sample stdev (N−1 denominator). 0.0 for single-trial runs. |
| `overall_mean` | number (0–3) | Mean of per-trial recomputed overalls. |
| `overall_stdev` | number (≥0) | Sample stdev of per-trial recomputed overalls. |

**Per-trial entry shape**:

| Field | Type | Notes |
|---|---|---|
| `scores` | dict[string, int] | Dimension name → integer 0–3 per the rubric grade scale. |
| `overall_recomputed` | number (0–3) | Mean of `scores` values, computed by us — not trusted from the judge. |
| `overall_judge_reported` | number \| null | The judge's claimed overall. Preserved for audit; **not** aggregated. Spotting judges that disagree with their own arithmetic is one signal of judge drift. |
| `rationale` | string | 2-4 sentences from the judge citing strengths/weaknesses of the deliverable. |
| `judge_io` | object \| absent | **Optional** (T1.7a). Reference to the per-trial sidecar containing the raw judge subprocess output. Absent on T1.5 baselines that predate sidecar capture. Per ADR-0008, optional additions don't bump `schema_version`. Shape: `{path: string, total_cost_usd: number \| null}`. The sidecar lives at `experiments/<id>/<path>` and contains the full stdout wrapper, stderr, returncode, duration, cost, and usage record — the heavy data is kept out of `result.json` itself to keep validation fast and the file readable. |

**Failure shape** — judge subprocess errored before completing all trials.
The runner records this rather than raising, so transcript + diff +
scope_check are still on disk for forensics:

| Field | Type | Notes |
|---|---|---|
| `error` | `{type: string, message: string}` | E.g., `JudgeInvocationError`, `FileNotFoundError`. |

---

## Future fields

These are declared in [`docs/reliability-criteria.md`](reliability-criteria.md)
as goals but are **not** in the schema yet. Their shapes will be locked when
the code that writes them lands.

| Field | Phase | Writer (when implemented) | Notes |
|---|---|---|---|
| `skills_invoked` | TBD | post-processor over `transcript.md` | List of plugin skills that fired during the run (grep'd from transcript). |
| `scoring.test_pass` | Phase 3 | `harness/score_tests.py` (T3.2) | SWE-bench-style FAIL_TO_PASS / PASS_TO_PASS results from per-task Docker container. Shape: `{fail_to_pass_passing, pass_to_pass_passing, fail_to_pass_total, pass_to_pass_total, resolved: bool}`. |
| `scoring.sim_metric` | Phase 4 | TBD | Numeric metric parsed from rosbag/log; with `seed_required: true`, success rate over N trials. |
| `scoring.static_check` | TBD | TBD | Refactor-task static analysis results. |

These can land without a schema bump (`scoring.additionalProperties: true`).
When they do, this reference doc gets a row and the schema gets an explicit
property definition.

---

## Reliability criteria → field mapping

The criterion → field mapping is the canonical role of
[`docs/reliability-criteria.md`](reliability-criteria.md). For *what* each
field captures and *why* it satisfies a particular reliability criterion,
see that doc. For *shape* and *types*, see this doc and the schema.

---

## Validation

```bash
# Validate every result.json on disk
python3 harness/validate_result.py --all

# Validate one specific result
python3 harness/validate_result.py experiments/<dir>/result.json
```

Validation also runs **inline** inside
[`harness/run_experiment.py:write_result()`](../harness/run_experiment.py).
Any malformed payload raises `ResultValidationError` and never lands on disk.
If even the runner's error-state result fails validation, the runner falls
back to writing `result.invalid.json` so forensics aren't lost.
