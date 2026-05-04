# Architecture Decision Records

This directory contains ADRs for `robotics-skills-benchmark`. Each ADR records one
architectural decision: the context, the choice made, alternatives considered, and the
consequences accepted.

## Index

| # | Status | Title | Date |
|---|---|---|---|
| [ADR-0001](0001-three-surface-repo-topology.md) | Accepted | Three-surface repository topology with URL+SHA task references | 2026-05-02 |
| [ADR-0002](0002-git-worktrees-for-parallel-runs.md) | Accepted | Git worktrees for parallel multi-version runs | 2026-05-02 |
| [ADR-0003](0003-hybrid-scoring.md) | Accepted | Hybrid scoring: automated metrics + LLM-judge rubric + human spot-check | 2026-05-02 |
| [ADR-0004](0004-v1-staged-activities.md) | Accepted | V1 stages user-selected activities one per phase | 2026-05-02 |
| [ADR-0005](0005-one-change-per-plugin-tag.md) | Accepted | One logical change per plugin tag | 2026-05-02 |
| [ADR-0006](0006-headless-claude-code-for-runner-and-judge.md) | Accepted | Headless Claude Code for both runner and LLM judge | 2026-05-02 |
| [ADR-0007](0007-v1-sim-engine-relaxation.md) | Accepted | V1 sim_engine criterion relaxed; long-term Gazebo direction unchanged | 2026-05-02 |
| [ADR-0008](0008-result-json-schema-and-reference.md) | Accepted | Canonical `result.json` schema + reference doc, validated on every write | 2026-05-03 |
| [ADR-0009](0009-judge-isolation-without-bare-mode.md) | Accepted | Judge isolation via cwd + flags, not `--bare` (narrows ADR-0006 §judge) | 2026-05-04 |

## Conventions

- **Filename:** `NNNN-kebab-case-title.md`
- **Numbering:** sequential, never reused; do not renumber when an ADR is superseded.
- **Status lifecycle:** `Proposed → Accepted → (Superseded by ADR-NNNN | Deprecated)`. Old ADRs are not deleted; supersession is explicit.
- **One decision per ADR.** If you find yourself writing "and also...", that's a second ADR.

## When to write a new ADR

Any decision that satisfies *at least one* of:

- Would be expensive to reverse (changes data model, repo topology, auth surface, scoring shape)
- Has been re-litigated by yourself or a future agent more than once
- Crosses a project boundary (harness ↔ plugin ↔ task code)
- Is non-obvious from reading the code

When unsure: write it. A 10-minute ADR is cheaper than a 2-hour debate six months from now.

## When to NOT write an ADR

- Single-file refactors
- Tactical implementation choices that have no bearing on future decisions
- "What library to use" type choices when both options are interchangeable
- Spec details (those go in `docs/spec.md`)
- Operational task tracking (those go in `TODO.md`)
