# Reliability criteria — operationalized

The user defined "reliable" robotics-software-development by 5 criteria. Every experiment
must produce evidence for each. This document maps each criterion to specific fields the
harness captures in `result.json` and to the mechanism that produces them.

## C1. Auditability — *I can understand why the agent did what it did*

**Captured by:**
- `transcript.md` — full agent reasoning trail (truncated to 50 KB)
- `diff.patch` — exact change set vs. `base_sha`
- `result.json.files_modified` — list of files written or created
- `result.json.skills_invoked` — which plugin skills the agent loaded (read from transcript)

**Mechanism:** runner captures stdout/stderr of the Claude Code subprocess; post-processor
greps for skill-load markers.

## C2. Verifiability — *output can be checked by tests, sim, static analysis, or logs*

**Captured by:**
- `result.json.scoring.test_pass` — for `unit-test` / `hybrid` tasks (FAIL_TO_PASS + PASS_TO_PASS)
- `result.json.scoring.rubric_scores` — for `rubric` / `hybrid` tasks (per-dimension + overall)
- `result.json.scoring.sim_metric` — for `sim-metric` / `hybrid` tasks (numeric metric extracted from rosbag)
- `result.json.static_check` — for refactor tasks (e.g., `ros2 doctor`, `ament_lint`)

**Mechanism:** scorer modules under `harness/score_*.py`; each task declares which methods
apply via `verification_method`.

## C3. Output-stability — *under fixed conditions, results are consistent*

**Captured by:**
- `result.json.run_id` — distinguishes repeated runs of the same `(plugin_tag, task_id)`
- `result.json.scoring.rubric_scores.stdev` — N=3 LLM-judge trials with different seeds
- `analysis/reports/<date>_<plugin>_vs_<plugin>.md` — pooled stdev across plugin versions

**Mechanism:** harness runs each baseline and post-change comparison ≥3 times. If an
observed delta between plugin versions is smaller than 1× pooled stdev, the report
calls it noise — never a "promising trend."

## C4. Scope-discipline — *the agent does not modify unrelated files or expand requirements*

**Captured by:**
- `result.json.out_of_scope_file_count` — number of files outside `scope_files` that were modified
- `result.json.out_of_scope_paths` — the actual paths
- `result.json.hook_blocks` — count of `pre-commit-scope-check` hook rejections

**Mechanism:**
1. Plugin-side `pre-commit-scope-check` hook reads `BENCHMARK_SCOPE_FILES` env var, refuses
   to commit out-of-scope edits, gives the agent a chance to self-correct.
2. After the run, `harness/scope_check.py` re-checks the final diff (defense-in-depth in
   case the agent worked around the hook).

## C5. Recoverability — *I can find the failure point and restore stable state*

**Captured by:**
- `result.json.status` — `success | incomplete | error | timeout`
- `result.json.error` — exception type + message if applicable
- `result.json.scratch_dir` — path to the worktree (retained on failure for inspection)
- Pre-run state is a clean clone at `base_sha`; post-run state is reachable via `diff.patch`

**Mechanism:** runner uses `try/finally` to write a partial `result.json` even on crash.
Worktrees are retained for failed runs; cleaned on success.

## Cross-criterion: timing & cost

Every `result.json` also includes:
- `runtime_s` — wall-clock from invocation to scorer completion
- `transcript_bytes` — raw transcript size (proxy for token cost)
- `judge_calls` — number of LLM-judge trials (3 for rubric/hybrid, 0 for test-pass)

These don't enforce reliability directly but are needed to detect when reliability gains
are paid for in unaffordable ways.
