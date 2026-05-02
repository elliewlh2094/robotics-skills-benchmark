# ADR-0002: Git worktrees for parallel multi-version runs

## Status
Accepted

## Date
2026-05-02

## Context

A common workflow: run the same task against plugin `v0.1.0`, `v0.2.0`, `v0.3.0` simultaneously to compare outputs and measure variance. The user explicitly requested avoiding branch-switching inside any repo — branch-switching in long-running checkouts is slow, error-prone, and breaks IDE/editor state.

Three places where parallel checkouts could happen:
- The harness repo (no need; harness code is read-only at run time).
- The plugin repo (we need to materialize specific tags).
- External task repos (we need clean checkouts at pinned `base_sha`).

## Decision

For each `(plugin_tag, task_id, run_id)` triple, the harness:

1. Creates a **git worktree** of the task repo at `base_sha` under `/tmp/exp-scratch/<run_id>/` (using `git worktree add --detach`).
2. Materializes the plugin at the requested tag in a scratch directory (using `git worktree add` against a local clone of the plugin, or a `git clone --branch <tag>` if the local clone is unavailable).
3. Invokes Claude Code with `--plugin-dir <plugin_worktree>` and `cwd=<task_worktree>`.

Worktrees are retained on failure (for debugging) and pruned on success.

## Alternatives Considered

### Branch checkouts in a single clone
- **Pros:** Familiar; no extra disk usage.
- **Cons:** Exactly what the user wanted to avoid; serializes runs at the same task; breaks editor state if the user has the repo open.
- **Rejected.**

### Full re-clone per run
- **Pros:** Trivially isolated.
- **Cons:** Wastes disk and bandwidth; slow startup; redundant when the same task runs many times.
- **Rejected.**

### Shallow clones (`--depth 1`)
- **Pros:** Saves disk.
- **Cons:** Cannot reach historical commits if the task ever requires them; complicates retention of failed-run state for inspection.
- **Rejected** for now; reconsider if disk pressure becomes real.

### Symlink-based plugin loading
- **Pros:** No checkout overhead.
- **Cons:** Plugin tag pinning requires actual git state at the right commit; symlinking loses the tag.
- **Rejected.**

## Consequences

- ✅ Multiple plugin versions can run against the same task repo simultaneously without conflicts.
- ✅ Parallel runs at the same plugin version (for variance measurement) are also supported.
- ✅ Worktrees are first-class git citizens — `git status`, `git diff`, etc. all work inside one.
- ⚠️ Disk usage scales linearly with concurrent runs; pruning is mechanical (`git worktree prune`).
- ⚠️ Requires git ≥2.5 (worktrees were introduced in 2.5; modern systems are fine).
- ⚠️ A failed run leaves a worktree behind; a separate cleanup pass is needed periodically.

## Related ADRs

- ADR-0001 (three-surface topology) — defines what gets worktree'd.
- ADR-0006 (headless Claude Code) — the worktree path becomes the subprocess `cwd`.
