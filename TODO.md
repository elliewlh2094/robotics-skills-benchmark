# TODO

Lightweight operational pointer. Ephemeral on purpose — the durable references are:
- [`docs/v1-plan.md`](docs/v1-plan.md) — the canonical V1 plan (overview, goals, scope, success criteria, risks)
- [`docs/v1-tasks.md`](docs/v1-tasks.md) — the structured task breakdown with full Description / Acceptance / Verification / Dependencies / Files / Estimated scope per task
- [`docs/spec.md`](docs/spec.md) — what + why
- [`docs/decisions/`](docs/decisions/) — architecture decision records (canonical)
- [`docs/roadmap.md`](docs/roadmap.md) — long-term scope beyond V1
- [`docs/candidate-repos.md`](docs/candidate-repos.md) — investigated task-repo candidates

> **Last updated:** 2026-05-03.

---

## ▶ Where to resume

**T1.5 — run V1 baseline (3 trials at unmodified fork).** Full task definition at [`docs/v1-tasks.md`](docs/v1-tasks.md).

Prereqs done: scope-check + rubric scorer landed in T1.4 (scoring section of `result.json` now populated end-to-end via `harness/scope_check.py` and `harness/score_rubric.py`; the real `claude --bare --json-schema` judge subprocess is exercised here for the first time).

Steps:
1. Tag `elliewlh2094/robotics-agent-skills` HEAD as `v0.1.0` in the plugin repo.
2. Run `harness/run_experiment.py` against `diffbot-experiment-design` at that tag, three times (`baseline-1`, `baseline-2`, `baseline-3`).
3. Sanity-check each `result.json` and that an `EXPERIMENT.md` was actually produced.
4. Compute pooled per-dimension stdev across the three runs and document in `analysis/baseline-v0.1.0.md`. **This stdev is the noise floor against which Phase 2's plugin delta is judged.**

---

## Phase progress

| Phase | Status | Tasks done | Tasks pending |
|---|---|---|---|
| Phase 1 (Foundation) | 🟡 in progress | T1.1, T1.2, T1.3, T1.4 | T1.5 |
| Phase 2 (First plugin iteration) | ⏳ blocked by Checkpoint A | — | T2.1–T2.4 |
| Phase 3 (TDD + debugging) | ⏳ post-V1 | — | T3.1–T3.5 |
| Phase 4 (Spec + planning) | ⏳ post-V1 | — | T4.1–T4.4 |

---

## 🚦 Decisions already made

All architectural decisions are recorded in [`docs/decisions/`](docs/decisions/). Quick map:

| Decision | ADR |
|---|---|
| Three-surface topology + URL+SHA task refs; reproducibility tuple uses `plugin_sha` | [0001](docs/decisions/0001-three-surface-repo-topology.md) |
| Parallel runs use git worktrees (full triple in path) | [0002](docs/decisions/0002-git-worktrees-for-parallel-runs.md) |
| Hybrid scoring: automated + LLM-judge rubric (N=3) + human spot-check | [0003](docs/decisions/0003-hybrid-scoring.md) |
| V1 ships only experiment-design; debugging is Phase 3, spec/planning Phase 4 | [0004](docs/decisions/0004-v1-staged-activities.md) |
| One logical change per plugin tag | [0005](docs/decisions/0005-one-change-per-plugin-tag.md) |
| Headless `claude -p` for runner and judge; `--tools` (not `--allowedTools`) for hard whitelist; `--max-turns` ceiling | [0006](docs/decisions/0006-headless-claude-code-for-runner-and-judge.md) |
| V1 sim_engine relaxed (mock hw OK); humble branch pinned; long-term Gazebo direction unchanged | [0007](docs/decisions/0007-v1-sim-engine-relaxation.md) |

---

## ⚠️ Open issues (transient)

1. **PyYAML 5.4.1 is older** than current 6.x. Schema's `pattern` regex catches the int-autocast-of-unquoted-SHA bug, so non-blocking. Worth upgrading at some point.
2. **No automated cleanup of stale worktrees** under `/tmp/exp-scratch/`. Worktrees from failed runs persist by design (ADR-0002), but no periodic prune is scheduled. Add a `harness/prune.py` once we have >10 stale entries.
3. **Judge-drift detection** requires human spot-check 1-in-5 (ADR-0003), but no tooling exists yet to surface "which results need human review." Schedule for Phase 5 cadence work, not blocking V1.
4. **Open questions Q1–Q4** in [`docs/v1-plan.md`](docs/v1-plan.md) §"Open questions" — resolved during execution rather than upfront.
