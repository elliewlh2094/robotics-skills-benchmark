# ADR-0001: Three-surface repository topology with URL+SHA task references

## Status
Accepted

## Date
2026-05-02

## Context

The project iterates a Claude Code plugin (`elliewlh2094/robotics-agent-skills`) by running it against a benchmark of robotics tasks. Each task is a real GitHub repository at a specific commit. We expect to reference 50+ external task repositories over the project's lifetime.

Constraints:
- The harness repo must remain lightweight (target ≤50 MB) regardless of how many tasks are added.
- The plugin must be installable as a Claude Code plugin from a clean repo root.
- Multiple plugin versions need to run against the same task repo concurrently.
- Reproducibility: each result must be reconstructable from a small set of identifiers, even if upstream repos rebase or disappear.

## Decision

Three logically separate repository surfaces:

1. **Harness** (this repo, `robotics-skills-benchmark`) — task definitions (`tasks/`), runner code (`harness/`), experiment artifacts (`experiments/`), analysis (`analysis/`), docs.
2. **Plugin** (separate, `elliewlh2094/robotics-agent-skills`) — the artifact under iteration; versioned by git tags. Cleanly publishable as a Claude Code plugin from its repo root.
3. **Task code** (many external repos) — referenced in `tasks/index.yaml` by `(URL, commit_sha)` pairs only. Never vendored, never submoduled. Cloned at experiment time into a scratch worktree, discarded after the run (or retained on failure for inspection).

Reproducibility is keyed on `(plugin_sha, base_sha, schema_version, run_id)` — recorded in every `result.json`. Note: `plugin_tag` (a human-supplied label) and `plugin_ref` (a branch or tag name passed to the runner) are *also* recorded, but they can drift over time (tags can be moved, branches advance), so `plugin_sha` is the canonical key. The runner resolves the plugin's HEAD SHA at materialization time and pins it in `result.json`, regardless of whether the plugin was sourced via `--plugin-path` or `--plugin-repo + --plugin-ref`.

## Alternatives Considered

### Mono-repo with submodules
- **Pros:** Single source of truth; easy to bisect across plugin + tasks.
- **Cons:** Bloats over time as task count grows; submodule version-pinning friction; 50+ submodules become unmanageable; clone time grows linearly.
- **Rejected.**

### Plugin embedded inside this repo (e.g., under `plugin/`)
- **Pros:** Single clone for harness + plugin development.
- **Cons:** Plugin cannot be cleanly published as a Claude Code plugin from a subdirectory; blurs the harness-vs-artifact-under-test separation; the plugin under test cannot evaluate itself fairly if their codebases share a history.
- **Rejected.**

### Three separate repos: plugin + harness + experiments
- **Pros:** Maximum decoupling.
- **Cons:** For a solo project, three-repo overhead is more friction than benefit; experiments are tightly coupled to the harness's output schema and benefit from co-located analysis tools.
- **Rejected.**

## Consequences

- ✅ Meta-repo stays lightweight even as the task set scales to 50+ external references.
- ✅ Reproducibility works without depending on the harness storing task code. The reproducibility tuple `(plugin_sha, base_sha, schema_version, run_id)` is fully captured in every `result.json`; if the plugin path is not a git working tree, `plugin_sha` is null and a warning is logged. The exact JSON shape and validation rules are in [`harness/schemas/result.schema.yaml`](../../harness/schemas/result.schema.yaml) (per [ADR-0008](0008-result-json-schema-and-reference.md)); the human reference is [`docs/result-json-reference.md`](../result-json-reference.md).
- ✅ Plugin can be installed from `elliewlh2094/robotics-agent-skills` without harness machinery.
- ⚠️ Harness must handle external clones at run time → introduces a network-dependency at execution rather than at commit time.
- ⚠️ Stale upstream repos fail loudly (SHA fetch fails) — preferable to silent corruption, but requires runtime error handling.
- ⚠️ Cross-plugin debugging requires checking out the right commits in two repos; documented in `docs/plugin-feedback-loop.md`.

## Related ADRs

- ADR-0002 (worktrees for parallel runs) — operationalizes the parallelism this topology enables.
- ADR-0005 (one change per plugin tag) — relies on plugin-as-separate-repo for clean tagging.
- ADR-0008 (result.json schema + reference) — formalizes the exact shape of the `result.json` fields where this ADR's reproducibility tuple lands.
