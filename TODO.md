# TODO

Lightweight operational pointer. Ephemeral on purpose — the durable references are:
- [`docs/v1-plan.md`](docs/v1-plan.md) — the canonical V1 plan (overview, goals, scope, success criteria, risks)
- [`docs/v1-tasks.md`](docs/v1-tasks.md) — the structured task breakdown with full Description / Acceptance / Verification / Dependencies / Files / Estimated scope per task
- [`docs/spec.md`](docs/spec.md) — what + why
- [`docs/decisions/`](docs/decisions/) — architecture decision records (canonical)
- [`docs/roadmap.md`](docs/roadmap.md) — long-term scope beyond V1
- [`docs/candidate-repos.md`](docs/candidate-repos.md) — investigated task-repo candidates
- [`docs/result-json-reference.md`](docs/result-json-reference.md) + [`harness/schemas/result.schema.yaml`](harness/schemas/result.schema.yaml) — canonical pair for `result.json` field shapes (validated on every write)

> **Last updated:** 2026-05-05 (T1.5 complete; **Phase 2 calibration gate triggered** — see `analysis/baseline-v0.1.0.md`).

---

## ▶ Where to resume

**Rubric calibration (NEW — pre-T2.1).** T1.5 completed; all three formal baseline runs at `v0.1.0` produced `overall_mean: 3.0`, `overall_stdev: 0.0` across all 7 dimensions on all 9 trials (3 runs × 3 trials). The Phase 2 calibration gate has triggered. Phase 2 (T2.1–T2.4) is paused.

Full T1.5 forensics: [`analysis/baseline-v0.1.0.md`](analysis/baseline-v0.1.0.md). Calibration directions are listed there in increasing cost; cheapest+most informative is anchor-tightening + a known-bad reference deliverable to verify discrimination.

Steps to resume:
1. **Decide calibration approach.** Pick from `analysis/baseline-v0.1.0.md` §"Calibration directions to consider" (anchor-tightening, new dimensions, adversarial judge prompt, cross-model judging, blind comparison). User decision required before edits.
2. Apply rubric changes (likely in `tasks/instances/diffbot-experiment-design/rubric.md`).
3. Re-run the baseline as `baseline-c1-{1,2,3}` (the `c1` denotes calibration revision 1; `v0.1.0` plugin_tag stays the same since the plugin didn't change). The previous `baseline-{1,2,3}` runs remain on disk for forensic comparison.
4. Re-evaluate the gate. Proceed to T2.1 only when at least one dimension shows `mean < 3.0` OR `stdev > 0`.

Phase 1 task closure status:
- T1.1, T1.2, T1.3, T1.4, T1.4a: ✓ complete
- T1.5: ✓ complete (per acceptance criteria — the analysis doc is the deliverable; it correctly documents that the noise floor is degenerate)
- Checkpoint A: 🟡 partial — three runs landed and variance documented, but the "pause and review" guard fired. Cannot mark Checkpoint A passed until calibration changes the picture.

---

## Phase progress

| Phase | Status | Tasks done | Tasks pending |
|---|---|---|---|
| Phase 1 (Foundation) | 🟢 tasks done; Checkpoint A pending calibration | T1.1, T1.2, T1.3, T1.4, T1.4a, T1.5 | (rubric calibration, then re-run as `baseline-c1-*`) |
| Phase 2 (First plugin iteration) | 🛑 paused by Phase 2 calibration gate | — | T2.1–T2.4 (paused) |
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
| Headless `claude -p` for runner and judge; `--tools` + `--allowedTools` (complementary: restrict + auto-approve) with the same task whitelist; `--max-turns` ceiling | [0006](docs/decisions/0006-headless-claude-code-for-runner-and-judge.md) (amended 2026-05-05) |
| V1 sim_engine relaxed (mock hw OK); humble branch pinned; long-term Gazebo direction unchanged | [0007](docs/decisions/0007-v1-sim-engine-relaxation.md) |
| `result.json` canonical pair: schema (machine, validated on every write) + reference doc (human); 5 prior locations now point at this pair | [0008](docs/decisions/0008-result-json-schema-and-reference.md) |

---

## ⚠️ Open issues (transient)

1. **PyYAML 5.4.1 is older** than current 6.x. Schema's `pattern` regex catches the int-autocast-of-unquoted-SHA bug, so non-blocking. Worth upgrading at some point.
2. **No automated cleanup of stale worktrees** under `/tmp/exp-scratch/`. Worktrees from failed runs persist by design (ADR-0002), but no periodic prune is scheduled. Add a `harness/prune.py` once we have >10 stale entries.
3. **Judge-drift detection** requires human spot-check 1-in-5 (ADR-0003), but no tooling exists yet to surface "which results need human review." Schedule for Phase 5 cadence work, not blocking V1.
4. **Open questions Q1–Q4** in [`docs/v1-plan.md`](docs/v1-plan.md) §"Open questions" — resolved during execution rather than upfront.
5. **Judge token/cost not captured.** `result.json` records `judge_calls` (count) but not the per-trial token usage or `cost_usd` that `claude --json-schema` returns. Surfaced during T1.5 dry-runs when extracting cost from artifacts. `score_rubric.py` discards the judge subprocess's `usage`/`total_cost_usd`. Phase 5 instrumentation work; non-blocking for V1.
6. **Rubric ceiling concern (calibration gate for Phase 2).** Dry-run #2 produced `overall_mean: 3.0`, `overall_stdev: 0.0` across all 7 dimensions. If the formal baselines reproduce this saturation, Phase 2 must pause for rubric calibration — see TODO step 4 above and the saved feedback memory `feedback_phase2_rubric_calibration_gate.md`.
