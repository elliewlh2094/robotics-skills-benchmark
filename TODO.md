# TODO

Lightweight operational pointer. Ephemeral on purpose — the durable references are:
- [`docs/v1-plan.md`](docs/v1-plan.md) — the canonical V1 plan (overview, goals, scope, success criteria, risks)
- [`docs/v1-tasks.md`](docs/v1-tasks.md) — the structured task breakdown with full Description / Acceptance / Verification / Dependencies / Files / Estimated scope per task
- [`docs/spec.md`](docs/spec.md) — what + why
- [`docs/decisions/`](docs/decisions/) — architecture decision records (canonical)
- [`docs/roadmap.md`](docs/roadmap.md) — long-term scope beyond V1
- [`docs/candidate-repos.md`](docs/candidate-repos.md) — investigated task-repo candidates
- [`docs/result-json-reference.md`](docs/result-json-reference.md) + [`harness/schemas/result.schema.yaml`](harness/schemas/result.schema.yaml) — canonical pair for `result.json` field shapes (validated on every write)

> **Last updated:** 2026-05-06 (T1.6a renderer extension landed; new plan adds T1.7b structural overhaul + Checkpoint A-2 — see `~/.claude/plans/i-have-read-through-swirling-bonbon.md`).

---

## ▶ Where to resume

**T1.7b: rubric + scorer + schema overhaul (atomic).** Per the approved plan (`~/.claude/plans/i-have-read-through-swirling-bonbon.md`), the manual-review pass on the three v0.1.0 baselines surfaced findings that supersede the original "pick-an-anchor-and-tighten" T1.7b. The new T1.7b couples rubric content + judge schema + result schema + renderer rationale rendering as one breaking change (with a `schema_version` bump per ADR-0008), verified by re-grading the existing 3 deliverables before any fresh agent runs.

Steps to resume:
1. **Rubric content** (`tasks/instances/diffbot-experiment-design/rubric.md`): preamble defining the experiment-design skill's core capability; tighten score-3 anchors; add explicit penalty triggers per dimension (`recorded_signals` configuration-relative, `success_thresholds` consistency vs timing precision, `repo_grounding` semantic-not-citation); add new dimensions `execution_procedure` and `design_completeness` (12-element checklist evaluated for specificity / internal consistency / sufficiency-for-execution). Total: 9 dimensions. Publish the canonical dimension key list as a single source of truth consumed by validator + scorer.
2. **Judge output schema** (`harness/score_rubric.py`): per-dimension structured rationale `{score, rationale: {positive_evidence, penalty_evidence, uncertainty, score_cap_reason}}`; top-level `overall_judge_reported`. Update `_JUDGE_INSTRUCTIONS` and `JUDGE_OUTPUT_SCHEMA` accordingly.
3. **Result schema** (`harness/schemas/result.schema.yaml`): migrate per-trial entry to the new shape; bump `schema_version` 1 → 2. Strict v2 parser validation: `dimensions` map must contain exactly the rubric's expected key set (missing/extra/misspelled keys raise `ResultValidationError` *before* aggregation).
4. **Documentation** (`docs/result-json-reference.md`): preserve v1 summary alongside v2 — do not overwrite. Tools dispatch on `schema_version`.
5. **Renderer** (`harness/render_report.py`): add v1 vs v2 dispatch in `render_rationales()`. v1 path keeps existing free-form rendering for the frozen 3 baselines; v2 path emits per-dimension blocks.
6. **Regrade utility** (`harness/regrade.py`, new): take an existing experiment dir, restore deliverable from `diff.patch`, run new rubric/judge against it, write fresh result (v2) + sidecars to `experiments/<original-id>__regrade-c1/`.
7. **Run regrade on the 3 historical baselines.** Verify all four T1.7b pass criteria (definition of "triggered penalty": concrete defect in `penalty_evidence` AND reflected in score or `score_cap_reason`):
   - ≥2/3 deliverables have a triggered penalty;
   - ≥2 distinct defect types detected;
   - every triggered `penalty_evidence` traces to specific deliverable content;
   - manual review finds no obvious false/missed penalties.
8. **Log to `analysis/baseline-v0.1.0.md` `## Regrade log`** with each criterion checked off explicitly.

Then T1.7c (fresh `baseline-c1-{1,2,3}` agent runs against the original task with new rubric — two-tier pass criteria), then T1.8 (task-suitability analysis under `analysis/`), then Checkpoint A-2 unblocks Phase 2.

**Frozen-reports policy:** the three `report.md` files under `experiments/2026-05-04_v0.1.0_diffbot-experiment-design_baseline-{1,2,3}/` are historical artifacts and **must not be re-rendered** with the T1.6a additions. The new sections (Task definition, Measurement instrument health) apply only to runs from baseline-c1 onward; existing reports stay as-is so the v0.1.0 evidence chain is preserved. The renderer code is uniform across versions; this is a process policy, not enforced in code. (The `--all` CLI flag would re-render historical reports — don't use it on the experiments dir during T1.7 work.)

Phase 1 task closure status:
- T1.1, T1.2, T1.3, T1.4, T1.4a: ✓ complete
- T1.5: ✓ complete
- T1.6: ✓ complete
- T1.6a (renderer extension: task-definition + instrument-health sections): ✓ complete
- T1.7a (judge-transcript persistence plumbing): ✓ complete (commit 91d9e70)
- T1.7b (rubric + scorer + schema overhaul, expanded scope): ⏳ next
- T1.7c (fresh baseline-c1 with new rubric): ⏳ blocked on T1.7b
- T1.8 (task-suitability analysis under `analysis/`): ⏳ can run in parallel with T1.7c
- T1.9 / T1.10 (new medium-constraint task + baseline): deferred until after T1.7c re-grade results
- Checkpoint A: 🟡 partial. Checkpoint A-2 (instrument-fitness gate) added; both must pass before Phase 2 / T2.1.

---

## Phase progress

| Phase | Status | Tasks done | Tasks pending |
|---|---|---|---|
| Phase 1 (Foundation) | 🟢 most tasks done; Checkpoints A + A-2 pending calibration | T1.1, T1.2, T1.3, T1.4, T1.4a, T1.5, T1.6, T1.6a, T1.7a | T1.7b (rubric/scorer/schema overhaul), T1.7c (`baseline-c1-*`), T1.8 (task-suitability analysis), Checkpoint A-2; T1.9/T1.10 deferred |
| Phase 2 (First plugin iteration) | 🛑 paused by Checkpoints A + A-2 | — | T2.1–T2.4 (paused) |
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
5. **Judge token/cost not captured.** ~~Phase 5 instrumentation work~~ → ✓ resolved by T1.7a (commit 91d9e70). Sidecar `judge-trial-{i}.json` files capture per-trial cost / usage / stdout-wrapper / stderr; `result.json` records a `judge_io = {path, total_cost_usd}` reference per trial.
6. **Rubric ceiling concern (calibration gate for Phase 2).** All three formal v0.1.0 baseline runs produced `overall_mean: 3.0`, `overall_stdev: 0.0` across all 7 dimensions on 9 trials. ~~Phase 2 paused~~ → tracked under T1.7b (now expanded — see "Where to resume"). Canonical research record will live in `analysis/baseline-v0.1.0.md` `## Regrade log` and `## Calibration log` sections; the saved memory file `feedback_phase2_rubric_calibration_gate.md` is an optional sync aid only and is **not** part of Checkpoint A-2 acceptance criteria (which depend solely on version-controlled repo files).
