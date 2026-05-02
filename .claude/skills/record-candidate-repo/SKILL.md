---
name: record-candidate-repo
description: Use when a robotics repository has been investigated and determined useful for the long-term roadmap but not for the current task. Captures the investigation as a structured entry in docs/candidate-repos.md so future task-selection conversations can start from prior work. Trigger phrases include "save this repo for later", "add to candidate KB", "log repo for future tasks", "this could be useful in Phase X".
---

# record-candidate-repo

## Overview

This project scopes V1 narrowly and stages broader robotics activities across later phases. During task-selection conversations we frequently investigate repos that *could* serve as benchmark task sources but aren't the right fit *now*. Without a system, that investigation gets lost — six months later we re-investigate the same repo from scratch.

This skill prevents that. When a repo is judged useful but not for the current task, it gets a permanent entry in `docs/candidate-repos.md`, structured for fast lookup.

## When to use

**Trigger when:**
- A repo was investigated and a positive finding emerged (sharp invariant, good license, active maintenance, clean structure) but the repo doesn't fit the current task scope.
- A user explicitly asks to "save this repo for future tasks" / "add to candidate KB" / "this could be useful for Phase X" / "archive for later".
- A user mentions a repo by name and wants the conversation's analysis preserved.

**Skip when:**
- The repo is already the active task source (it goes in `tasks/instances/`, not the candidate KB).
- The investigation produced *only* negative findings (too big, abandoned, wrong license). One-line "rejected: <reason>" can go in the at-a-glance table without a full entry.
- The repo has only been *mentioned* in passing without investigation. Add it to the **Backlog: un-investigated mentions** table at the bottom of `docs/candidate-repos.md` instead of writing a full entry.
- The user is currently in Plan Mode — write the entry to the plan file as proposed work, not to the KB.

## Process

### 1. Verify required facts before writing

Do not write an entry from memory or from prior agent claims alone. Confirm:

- **Repo URL** is reachable (e.g., `gh repo view <owner>/<repo>` or `WebFetch`).
- **Default branch name** — verify; do not assume `main`.
- **Latest commit SHA** — full 40-char form, with date. Use:
  - `gh api repos/<owner>/<repo>/branches/<default-branch>` for the SHA + date, or
  - `git ls-remote https://github.com/<owner>/<repo> HEAD`, or
  - `WebFetch` on the repo page (look for the latest commit indicator).
- **License** — check the repo's license file or `gh repo view`.
- **Maintenance signal** — stars, forks, open issues, recent commit cadence. Brief, not exhaustive.

If any of these can't be verified in this session, add the repo to the **Backlog** table instead of a full entry.

### 2. Write the entry

Append a new section to `docs/candidate-repos.md` using the template below. The section heading should be `## <owner>/<repo>` (matches the at-a-glance table anchor).

```markdown
## <owner>/<repo>

- **URL:** https://github.com/<owner>/<repo>
- **Default branch:** `<branch>`
- **Latest commit at investigation:** `<40-char-sha>` (<YYYY-MM-DD>)
- **License:** <license>
- **Maintenance:** <one-line maintenance signal>

### Description

<1–2 paragraphs: what the repo does, what packages/components it ships, who maintains it, what platform it targets>

### Suitability matrix

| Task type | Fit | Notes |
|---|---|---|
| Rubric — experiment-design | <Strong/Possible/Weak/❌> | <one-line why> |
| Rubric — spec/planning | <…> | <one-line why> |
| Test-pass — debugging | <…> | <one-line why> |
| Sim-metric — perf | <…> | <one-line why> |
| Integration / multi-robot | <…> | <one-line why> |

### Why archived for later

<2–4 sentences: why this didn't fit the current task scope, and what would unlock it for use>

### Risks / caveats

- <license, branch protection, distro coupling, maintenance freshness, anything weird>
- <…>
```

Use ⭐ to mark the **single best long-term fit** in the suitability matrix. Each repo should have exactly one ⭐.

### 3. Update the at-a-glance table

At the top of `docs/candidate-repos.md`, add or update a row for this repo:

```markdown
| [<owner>/<repo>](#owner-repo) | <YYYY-MM-DD> | <one-line "best long-term fit" — phase + activity + reason> | <status emoji + word> |
```

Use the existing status legend (✅ in use, 🗄️ archived for later, 📋 backlog, ❌ rejected, 🔄 superseded).

The anchor in the link must lowercase the org/repo and replace `/` with `-` (Markdown auto-anchor convention). Verify the link by clicking it after the edit.

### 4. Cross-link if relevant

If the repo connects to an existing roadmap item (e.g., "this is the natural fit for Phase 4 sim-metric tasks"), add a `<!-- candidate: <repo-name> -->` HTML comment near the relevant section in `docs/roadmap.md`. This keeps the roadmap clean visually while letting future readers grep for candidates.

## Template field guide

- **Latest commit SHA:** must be the full 40-char form. Do not use short hashes — they collide.
- **Suitability matrix `Fit` values:** use one of `⭐ Strong`, `Strong`, `Possible`, `Weak`, `❌`. The ⭐ marks *the best fit for that repo*; matrix-wide judgments use the unstarred labels.
- **Why archived:** be specific about what would unlock the repo for use. "Too big" is not enough; "too big for V1's rubric sharpness; suitable when sim-metric scoring lands in Phase 4" is.
- **Risks / caveats:** anything that would surprise someone three months from now. License gotchas, distro coupling, abandonment risk, structural quirks.

## Anti-patterns to avoid

- **Don't write entries from memory.** Verify the SHA and the date *now*, before the conversation moves on.
- **Don't duplicate.** Before writing, search `docs/candidate-repos.md` for the repo name. If it's already there, *update* the existing entry; do not append a second one.
- **Don't fold negative-only findings into a full entry.** A two-line "this repo was investigated and rejected because <reason>" in the rejected section of the at-a-glance table is sufficient.
- **Don't soft-pedal the "Why archived" section.** "Could be useful someday" is useless; pin the unlock condition.
- **Don't add backlog entries to the detailed-entry section.** Backlog goes in the table at the bottom; only investigated repos get full entries.
- **Don't lose investigation work in conversation history.** If you investigated a repo this turn and it doesn't fit the current task, log it before the conversation moves on.

## Verification

After writing or updating an entry:

- [ ] At-a-glance table row matches the section heading exactly (link works).
- [ ] All required fields are present and verified (URL, default branch, SHA, license, maintenance).
- [ ] Suitability matrix has exactly one ⭐.
- [ ] "Why archived for later" names a specific unlock condition (phase / activity / verification method).
- [ ] No duplicate entry for the same repo.
- [ ] Status emoji is one of the documented set.
