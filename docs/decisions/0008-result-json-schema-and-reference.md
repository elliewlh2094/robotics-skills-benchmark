# ADR-0008: Canonical schema + reference doc for `result.json`

## Status
Accepted

## Date
2026-05-03

## Context

The shape of `experiments/<...>/result.json` is the spine of the harness — every
scorer reads it, every cross-version comparison report parses it, and the
reproducibility tuple lives in it. By T1.4 it was being described in **six
places** with concrete drift between them:

| Where | Sample claim |
|---|---|
| `harness/run_experiment.py` | actual writer; emitted `scoring.rubric` and `out_of_scope_count` |
| `docs/spec.md` §FR3 | referenced `scoring.rubric_scores.stdev` |
| `docs/reliability-criteria.md` | declared `out_of_scope_file_count`, `skills_invoked`, `hook_blocks`, `judge_calls`, `scoring.test_pass`, `scoring.sim_metric`, `scoring.static_check` |
| `docs/v1-plan.md` §V1 success criteria | reproducibility tuple `(plugin_tag, plugin_sha, base_sha, schema_version)` |
| `docs/roadmap.md` §Versioning model + §V1 success criteria | overlapped spec.md |
| `docs/decisions/0001-three-surface-repo-topology.md` §Consequences | how `plugin_sha` lands |

The drift was not theoretical:

- **Naming**: `scoring.rubric` (code) vs `scoring.rubric_scores` (4 docs);
  `out_of_scope_count` (code, also `tasks/schema.yaml`:73) vs
  `out_of_scope_file_count` (4 docs).
- **Code-only fields** (10): `experiment_id`, `plugin_path`, `plugin_repo`,
  `plugin_ref`, `available_tools`, `max_turns`, `seed`, `started_at`,
  `completed_at`, `exit_code` — written by the runner, mentioned in no doc.
- **Doc-only fields** (6): `skills_invoked`, `hook_blocks`, `judge_calls`,
  `scoring.test_pass`, `scoring.sim_metric`, `scoring.static_check` —
  declared in docs, never written by code.

A new contributor (human or agent) reading any one doc would build a wrong
model of `result.json`'s shape. Programmatic consumers (cross-version analysis
in Phase 5+) would have no way to detect when the runner stopped writing a
field they relied on.

The pattern for fixing this is already established in this repo for **task
instances**: a JSON Schema in YAML form (`tasks/schema.yaml`, draft-07), a
small validator wrapper (`harness/validate_task.py`), and per-instance task
files (`tasks/instances/*/task.yaml`). Validation runs at the boundary
(`harness/validate_task.py --all`) and catches drift mechanically.

## Decision

Establish the same pattern for `result.json`:

1. **`harness/schemas/result.schema.yaml`** — JSON Schema draft-07 in YAML
   form. The canonical machine definition. Mirrors `tasks/schema.yaml`'s
   conventions ($id, inline block-scalar descriptions, `if/then/allOf` for
   cross-field invariants).

2. **`harness/validate_result.py`** — CLI wrapper mirroring
   `harness/validate_task.py`. Single-file mode + `--all` glob over
   `experiments/*/result.json`. Also exports `validate_result()` and
   `ResultValidationError` so the runner can call validation inline.

3. **`docs/result-json-reference.md`** — human-readable companion. One row
   per field with type, required-when, nullable-when, writer, notes. The
   "why each field exists" answer that schemas don't naturally express.

4. **Validation runs inline** inside `harness/run_experiment.py:write_result()`.
   Every result that lands on disk through the runner is schema-checked. A
   malformed result raises `ResultValidationError` rather than silently
   writing garbage.

5. **The 5 redundant doc locations become pointers.** They keep the framing
   they need (e.g., `reliability-criteria.md` retains the
   criterion → field mapping table — that's *its* canonical role) but stop
   redefining shapes. They link to the reference for "what does this field
   look like."

### Three sub-decisions, drawn from in-conversation clarification

#### Aspirational fields
The 6 doc-only fields fall in two camps:

- **Declare now**: `judge_calls` (top-level int; ADR-0003 automated metric;
  always 0 or N) and `hook_blocks` (top-level int; valid 0-state until T2.3
  lands the hook). Both are well-defined today.
- **Defer**: `skills_invoked`, `scoring.test_pass`, `scoring.sim_metric`,
  `scoring.static_check`. Their shapes aren't decided yet. Locking them in
  the schema would force shape decisions before the code that needs them
  exists. Instead, `scoring` uses `additionalProperties: true` so future
  scorers (Phase 3+) land without requiring a schema change first.

#### Naming
Where code and docs disagreed, **doc names won the renames** because the
docs' names are more explicit:

- `scoring.rubric` → `scoring.rubric_scores` (code rename)
- `out_of_scope_count` → `out_of_scope_file_count` (code rename)
- `scope_files_declared` (kept; runner name wins — distinguishes the
  *declared* list from the *derived* `out_of_scope_paths`)

This is safe today: zero `result.json` files exist on disk (T1.5 hasn't run).

#### Refinement: `scratch_dir` lifecycle
The schema enforces `status != "success" → scratch_dir required` and
`status == "success" → scratch_dir absent`. To make this work for the
partial-write (status="incomplete"), `scratch_dir` must be set from the
**very first** persisted record. The runner restructured to compute
`task_worktree` *before* the partial-write so the path is available
immediately — even if the runner crashes before `add_worktree`, the partial
result honestly says "this is where the worktree would have been."

#### Refinement: plugin sourcing oneOf distinguishes by value, not by key
`plugin_path`, `plugin_repo`, `plugin_ref` are all always present in the
persisted dict (Python's `json.dump` emits all keys including `None` ones).
A naive `oneOf` checking key presence (`required: [plugin_path]` vs
`required: [plugin_repo, plugin_ref]`) would be vacuously satisfied by both
branches every time. The schema's `oneOf` instead narrows the *value type*
in each branch (`type: "null"` vs `type: string`) so the distinction comes
from whether `plugin_repo`/`plugin_ref` are null or non-null strings.

## Alternatives Considered

### Keep the distributed model; just fix the naming inconsistencies
- **Pros**: Less work; no new files.
- **Cons**: Doesn't solve the structural problem (drift is *certain* to
  return — the next field added will be added in one place and not the
  others). Doesn't give programmatic consumers a way to detect drift.
- **Rejected.**

### Just write the human reference doc; no machine schema
- **Pros**: Faster to write; simpler.
- **Cons**: No mechanical drift detection. Cross-version analysis in
  Phase 5+ would still parse `result.json` blind, breaking silently when
  fields rename. The 25 schema tests we now have wouldn't exist.
- **Rejected.** The validate-on-write pattern is the load-bearing
  guarantee — it makes "result.json conforms to schema" a *runtime
  invariant*, not a hope.

### Just write the schema; no human reference
- **Pros**: Less duplication.
- **Cons**: A schema documents *shape*, not *meaning*. A reader staring at
  `available_tools: array | null` doesn't learn *why* it's null sometimes
  (the runner falls back to `--dangerously-skip-permissions` and emits a
  warning) — that context lives in the reference doc's notes column.
- **Rejected.** Schema and reference doc serve different audiences:
  schema for machines and contributors changing the runner; reference for
  humans reading the data.

### Code-side validation only (no schema file); use a Python `TypedDict` or `pydantic` model
- **Pros**: Validation lives next to the code that produces results.
- **Cons**: Locks the schema definition to Python; cross-language consumers
  (e.g., a future TypeScript dashboard reading `result.json`) can't reuse
  the contract. JSON Schema is the lingua franca.
- **Rejected.** Schema-as-data is the right shape here, matching the
  precedent set by `tasks/schema.yaml`.

### Validation as a separate post-hoc CLI step (no inline validate-on-write)
- **Pros**: Simpler runner; no validation overhead in the hot path.
- **Cons**: Validation overhead is trivial (~1 ms per dict against a
  ~250-line schema). And opting out of inline validation means corrupt
  results can land on disk and remain there until someone remembers to run
  the linter — which defeats the point.
- **Rejected.** The CLI mode is preserved for spot-checking; inline
  validation is the load-bearing path.

## Consequences

✅ **Single source of truth.** Naming inconsistencies become impossible —
the schema rejects `out_of_scope_count` (the old name) immediately.

✅ **Schema-tested writes.** Every `result.json` on disk through
`run_experiment.py:write_result()` has been schema-checked. The 5 new
validate-on-write tests guard against regressions in plugin-mode
discrimination, scratch_dir lifecycle, and the success/error invariants.

✅ **Future scorers add fields without a schema bump.** `scoring` uses
`additionalProperties: true`, so when Phase 3 lands `score_tests.py` with
`scoring.test_pass = {fail_to_pass_passing: ..., resolved: bool}`, the new
field validates without code in the schema needing to change first. The
*shape* of the new field gets locked in the schema only when its writer
lands.

⚠️ **Runner cannot write malformed results through `write_result()`.** A
schema bug (rule too strict, or a missed valid state) would break runs
hard. Mitigation: the except handler in `run()` falls back to writing
`result.invalid.json` so forensics aren't lost. Mitigation: the schema is
covered by 25 tests including all four lifecycle states and both plugin
modes.

⚠️ **Schema lives in YAML, not the code.** Contributors changing the
runner must remember to also update the schema if they add a field. The
`additionalProperties: false` at the top level catches "added a new field
but didn't update the schema" immediately — the test suite or first run
will fail. Less risky than the inverse (changing the schema and forgetting
to update the runner — that fails on first write, also caught immediately).

⚠️ **The 5 redundant doc locations need ongoing discipline** to stay
pointers rather than re-accumulate field-level claims. The CLAUDE.md "where
things are" table now points at the canonical pair, which should help.

## Related ADRs

- **ADR-0001** (three-surface topology): the reproducibility tuple
  `(plugin_tag, plugin_sha, base_sha, schema_version, run_id)` lives in the
  fields this schema now formalizes. `plugin_sha` is the canonical key per
  ADR-0001.
- **ADR-0002** (worktrees for parallel runs): `scratch_dir`'s
  presence-iff-not-success invariant is exactly the pruning rule from
  ADR-0002 made into a schema constraint.
- **ADR-0003** (hybrid scoring): `judge_calls`, `hook_blocks` (top-level
  automated metrics) and `scoring.rubric_scores` (per-trial mean+stdev) are
  the surface this ADR locks down — ADR-0003 specified the *what*, this
  ADR specifies the *exact JSON shape*.
- **ADR-0006** (headless `claude -p`): `transcript_bytes` and the
  `error.type` enum (`missing-binary`, `non-zero-exit`, `timeout`,
  `<exception class>`) come from the subprocess wrapper this ADR depended
  on.
