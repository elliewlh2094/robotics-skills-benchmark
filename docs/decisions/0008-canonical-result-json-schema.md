# ADR-0008: Canonical schema and reference for `result.json`

## Status
Accepted

## Date
2026-05-03

## Context

`result.json` is the harness's central data contract: every experiment writes one (`experiments/<...>/result.json`); every reliability criterion in [`docs/reliability-criteria.md`](../reliability-criteria.md) is judged against its fields; every future cross-version analysis script will read it. Until now its definition was implicit — the only authoritative listing was the `partial: dict = {…}` literal in `harness/run_experiment.py:run()` plus the `compute_scoring()` helper. Five other documents described subsets of that structure independently, and they had diverged:

| Divergence | Where |
|---|---|
| Field name `exit_code` (code) vs `exit_status` (`docs/spec.md` FR3) | naming mismatch |
| `scope_files_declared` (code) vs `scope_files` (multiple docs in narrative) | naming mismatch |
| `skills_invoked`, `hook_blocks`, `static_check`, `judge_calls` promised in `docs/reliability-criteria.md` | not yet written by code |
| Reproducibility-tuple field set restated in `docs/v1-plan.md`, `docs/roadmap.md`, [ADR-0001](0001-three-surface-repo-topology.md) | three near-duplicates |

[T1.4](../v1-tasks.md) just landed three new top-level/nested fields (`scoring.scope_check`, `scoring.rubric`, plus the `compute_scoring()` shape). T1.5 will produce the first real `result.json` files on disk. Locking the schema **before** real data exists costs nothing; once `experiments/` is populated, every schema change becomes a migration. This is the cheapest possible moment to consolidate.

The harness already has the template for this work: `tasks/schema.yaml` (JSON Schema in YAML, draft-07, `if/then` conditional rules) and `harness/validate_task.py` (dual-mode CLI: `--all` walking + single-path).

## Decision

Establish three concrete artifacts and one runtime guarantee.

1. **Canonical schema** — [`harness/schemas/result.schema.yaml`](../../harness/schemas/result.schema.yaml). JSON Schema draft-07 in YAML. Status-conditional rules: `if status == "incomplete"` allows `completed_at`/`runtime_s`/`exit_code` to be null and `files_modified`/`scoring` to be empty; `if status ∈ {success, error, timeout}` requires those fields non-null; `if status == "success"` additionally requires `error: null`; `if status ∈ {error, timeout}` additionally requires `error: {type, message}`. Top-level `additionalProperties: false` so typos and stale fields are caught at validation time. The `scoring` object uses `additionalProperties: true` so future scorers can append.

2. **Human-readable reference** — [`docs/result-json-reference.md`](../result-json-reference.md). One row per field with **Type | When present | Writer (module:function) | Semantics**. Includes the status state-machine, four worked examples (one per status), and a "Planned" section listing the four deferred fields with the task ID that will add them.

3. **Validator** — [`harness/validate_result.py`](../../harness/validate_result.py). Mirrors `validate_task.py` exactly: CLI with `--all` (walks `experiments/*/result.json`) and single-path modes; programmatic `validate(result_dict)` (raises `jsonschema.ValidationError`) and `iter_errors(result_dict)` (returns list of human-readable messages).

4. **Validate-on-write** — `harness/run_experiment.py:write_result()` calls the validator before the atomic rename. On schema failure: writes the rejected payload to `<exp_dir>/result.invalid.json` and raises `ResultSchemaError`. The runtime cost is ~ms per write; the failure mode it catches is "you broke the schema in your last commit" — which is exactly when you want to know.

Companion edits in this same change:
- `docs/spec.md` FR3, `docs/reliability-criteria.md`, `docs/v1-plan.md`, `docs/roadmap.md` reduce inline field listings to pointers at the canonical reference. They keep their *narrative* (which metrics matter, why, criteria-to-fields mappings) but stop redefining the field set.
- ADR-0001 receives a single forward-pointer line under Status (ADRs themselves are historical and are not edited beyond that).
- `docs/spec.md` FR3 also corrects `exit_status` → `exit_code` to match the runner.

## Alternatives Considered

### Two separate schemas (partial, final)
- **Pros:** Simpler conditional rules in each schema; the partial schema is loose, the final is strict.
- **Cons:** Doubles the validation surface and the maintenance burden; readers must know which schema applies; the `write_result()` hook would need a status-dispatch step. The status-conditional `allOf` pattern in one schema gives the same enforcement with one source of truth.
- **Rejected.**

### Forward-looking nullable-required for the four planned fields
- **Pros:** Readers can code against the final shape today; no schema bump when a planned field lands.
- **Cons:** The runner must write `null` for fields whose semantics aren't yet defined. The reference doc would need to explain what `skills_invoked: null` means before `skills_invoked` has a producer — that's "documenting fiction." Cleaner to add each field in the PR that implements it, with a schema bump to capture the new contract.
- **Rejected.** The "Planned" section of the reference doc surfaces the gap honestly without lying about the contract.

### No validate-on-write; validate only via standalone CLI / pytest / CI
- **Pros:** Zero runtime overhead; runner stays small.
- **Cons:** A schema-violating result.json can land on disk and propagate to analysis before being caught. Validate-on-write moves the failure from "discovered by analysis script weeks later" to "discovered by the runner that wrote it" — and the `result.invalid.json` artifact preserves forensics either way.
- **Rejected.**

### Pydantic models or dataclasses instead of JSON Schema
- **Pros:** Type-checked Python; IDE auto-complete on field names.
- **Cons:** Inconsistent with the existing `tasks/schema.yaml` pattern; introduces a new dependency; doesn't help non-Python readers (planned analysis scripts, future dashboard tooling). JSON Schema is the lingua franca for cross-tool validation.
- **Rejected.** The same `Draft7Validator` already validates `tasks/schema.yaml`; reusing it keeps the harness coherent.

## Consequences

- ✅ Single source of truth: any change to result.json shape requires editing schema.yaml + reference.md + bumping `RESULT_SCHEMA_VERSION` together. The validate-on-write hook makes it impossible to land code that writes a divergent shape without also updating the schema.
- ✅ The five other docs lose the burden of restating field definitions and can focus on what they're actually for (spec narrative, reliability framing, V1/long-term planning).
- ✅ The validator runs in CI / pytest (`harness/tests/test_validate_result.py` covers happy paths + ≥4 negative cases) and at runtime in every experiment write. Schema drift is caught at three layers.
- ⚠️ Schema-version bumps now have a checklist: schema.yaml `const: N`, `RESULT_SCHEMA_VERSION = N`, reference-doc note, ADR successor (or amendment) explaining the change. This adds friction — intentionally; result.json is a long-lived contract.
- ⚠️ The four "Planned" fields (`skills_invoked`, `hook_blocks`, `static_check`, `judge_calls`) remain *promised* in `docs/reliability-criteria.md` but are not yet enforceable. The reference doc's Planned section is the index of when each lands; future readers can see the gap without inferring it from a missing-field discovery.
- ⚠️ The `additionalProperties: false` at top level means experimental field additions need a schema bump even for prototyping. Workaround for short-lived experiments: nest under `scoring.<scorer_name>` (which is `additionalProperties: true`).

## Related ADRs

- [ADR-0001](0001-three-surface-repo-topology.md) — defines the reproducibility tuple `(plugin_sha, base_sha, schema_version, run_id)`. The canonical field-by-field listing now lives in the result.json reference rather than being restated in the consequences section.
- [ADR-0002](0002-git-worktrees-for-parallel-runs.md) — defines `scratch_dir` retention policy for failed experiments.
- [ADR-0003](0003-hybrid-scoring.md) — defines the `scoring.rubric` shape (N=3 trials, mean ± stdev). The schema's `definitions.rubricSuccess` enforces this.
- [ADR-0006](0006-headless-claude-code-for-runner-and-judge.md) — defines the runner's `available_tools` and `max_turns` fields. Both are echoed into result.json for self-contained reproducibility.
