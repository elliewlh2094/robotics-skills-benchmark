# Plugin feedback loop

How experimental findings flow back into `elliewlh2094/robotics-agent-skills`.

## The loop

```
                 ┌─ harness clones plugin at tag v0.X.0
                 │
plugin repo ─────┤
   (git tags)    │
                 └─ result.json delta vs. v0.X-1.0
                          │
                          ▼
                 analysis/reports/*.md
                          │
                          ▼
                 lowest-scoring rubric dimension
                          │
                          ▼
                 1 new skill OR 1 new hook
                          │
                          ▼
                 plugin commit + new tag v0.(X+1).0
                          │
                          └─────────────► (loop repeats)
```

## Cadence

- **Per-experiment:** runner produces `result.json`; no plugin change yet.
- **End of phase (or weekly during active iteration):** review recent results,
  identify the weakest measured area, plan one targeted plugin change.
- **Plugin change:** **one** new skill OR **one** new hook per tag bump.
  Do not bundle multiple changes — it makes attribution impossible.
- **After plugin tag:** re-run the affected task(s) at the new tag,
  write `analysis/reports/<date>_<old-tag>_vs_<new-tag>.md`.

## Rules

1. **Never ship a plugin change without a measured baseline first.** Every new tag
   must have a "before" set of `result.json` to compare against.

2. **One change per tag.** If you add a skill AND a hook in the same tag, you cannot
   tell which one moved the score. Always tag between changes, even if the runs
   are scheduled together.

3. **Honesty about effect size.** If the score delta is smaller than 1× pooled stdev,
   the report says "no detectable effect" — not "promising direction." This is the
   single most important rule for keeping the loop honest.

4. **No speculative skills.** Only add skills/hooks that target a *measured* gap
   (lowest-scoring rubric dimension across recent experiments). Speculative additions
   inflate the plugin without measurable benefit.

5. **Refactors get their own tag.** A pure-refactor tag (like `v0.1.1` after `v0.1.0`)
   is a sanity check — re-running the baseline at the refactor tag should produce
   scores within 1 stdev. If it doesn't, the harness has hidden coupling to plugin
   structure that needs fixing.

## Where things land

| Outcome | Lands where |
|---|---|
| Raw run output | `experiments/<id>/` (this repo) |
| Cross-version comparison | `analysis/reports/` (this repo) |
| New skill or hook | plugin repo (`elliewlh2094/robotics-agent-skills`) |
| Plugin tag | plugin repo |
| Updated reliability criteria | `docs/reliability-criteria.md` (this repo) |

## Branch hygiene in the plugin repo

User wants to avoid frequent branch-switching. Recommended convention:

- `main` always points to the latest tagged release.
- Each experimental change goes on its own short-lived branch
  (e.g., `add-design-experiment-skill`).
- Merge to `main` only after the new-tag re-run shows a real (≥1 stdev) effect,
  OR after a deliberate "this didn't work, but the data is interesting" conclusion.
- Tag immediately on merge.
- Delete the branch.

This way the plugin repo always has a clean tag history and `main` is always
something the harness can run.
