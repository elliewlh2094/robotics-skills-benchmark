# ADR-0006: Headless Claude Code for both runner and LLM judge

## Status
Accepted

## Date
2026-05-02

## Context

The harness has two distinct LLM-invocation surfaces:

1. **Runner** (T1.3) — invokes the agent under test with the plugin loaded, against a task in a worktree.
2. **LLM judge** (T1.4) — invokes Claude in a *fresh* context (no plugin) to score a rubric task per ADR-0003.

Both surfaces want the same model. Two implementation paths exist:
- Subprocess `claude -p` (Claude Code in headless mode).
- Direct `api.anthropic.com` calls via the Anthropic SDK.

The user is on the Claude Max monthly plan. Per Anthropic billing model:
- Headless `claude -p` is covered by the Max plan, just like interactive sessions.
- Direct API calls (`api.anthropic.com`) are billed separately, even with a Max subscription.

Verified via `claude --help` (2026-05-02): `--plugin-dir`, `-p/--print`, `--dangerously-skip-permissions`, `--output-format json`, `--no-session-persistence`, and `--max-budget-usd` are all real CLI flags. There is **no `--max-turns` flag** despite a research agent's earlier claim.

## Decision

Both the runner and the rubric scorer subprocess `claude -p`:

**Runner invocation (sketch):**
```
claude --plugin-dir <plugin_worktree>
       --dangerously-skip-permissions
       --output-format json
       --no-session-persistence
       -p "<problem_statement>"
```
with `cwd=<task_worktree>` and env vars `BENCHMARK_SCOPE_FILES`, optional `BENCHMARK_SEED`.

**Judge invocation (sketch):**
```
claude --output-format json
       --no-session-persistence
       -p "<judge_prompt_with_rubric_and_agent_output>"
```
with no plugin loaded and a clean cwd.

Wall-clock timeout via `subprocess.Popen(timeout=…)` since `--max-turns` does not exist. `--max-budget-usd` is informational on Max plan but useful as a sanity cap in case auth ever falls through to API mode.

## Alternatives Considered

### Anthropic SDK for the judge
- **Pros:** Lower per-call overhead (~1 s saved on subprocess startup); direct access to streaming and structured output APIs.
- **Cons:** Separate billing surface; redundant auth setup; Max-plan benefit lost on every judge call (~3 calls × N tasks × M plugin versions).
- **Rejected.**

### Mixed approach: SDK for runner, CLI for judge (or vice versa)
- **Cons:** Worst of both worlds — two failure surfaces, two auth paths.
- **Rejected.**

### Headless via API key from `claude setup-token`
- **Pros:** Works in CI environments without a logged-in session.
- **Cons:** Unnecessary today (Max-plan login covers headless). Reconsider when external collaborators arrive.
- **Rejected for now.**

## Consequences

- ✅ Single auth surface (`claude auth login`); zero extra cost for judge calls on Max plan.
- ✅ Runner and judge use the same subprocess pattern → simpler harness, single set of tests.
- ✅ `--no-session-persistence` keeps `~/.claude/projects/` clean of benchmark sessions (avoids bloat).
- ⚠️ Runner and judge share model family → systematic biases (e.g., both over-rate verbose plans) won't cancel. Mitigation: human spot-check 1-in-5 (see ADR-0003).
- ⚠️ Subprocess startup overhead (~1–3 s per invocation) — negligible vs. the LLM call itself but noticeable in a tight harness loop.
- ⚠️ CLI flag set is authoritative only via `claude --help`. A research agent hallucinated `--max-turns 50` during investigation; future flag claims must be verified against `--help` before being relied on.
- ⚠️ When/if external collaborators arrive, switch to `claude setup-token` for CI; this ADR will then be supersed by a successor.

## Related ADRs

- ADR-0003 (hybrid scoring) — the LLM-judge component is what this implements.
- ADR-0001 (three-surface topology) — `--plugin-dir` is what makes plugin pinning by tag work cleanly without polluting global config.
