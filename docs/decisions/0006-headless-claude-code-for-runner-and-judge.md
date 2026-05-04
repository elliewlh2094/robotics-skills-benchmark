# ADR-0006: Headless Claude Code for both runner and LLM judge

## Status
Accepted (judge-invocation §narrowed by [ADR-0009](0009-judge-isolation-without-bare-mode.md) on 2026-05-04 — `--bare` not used; isolation via cwd + `--disable-slash-commands` + `--allowedTools ""`. Auth claim "Max plan covers both surfaces" is preserved.)

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

Verified via `claude --help` and the official docs (`docs.claude.com/en/docs/claude-code/cli-reference`, 2026-05-02 / 2026-05-03):

- `--plugin-dir`, `-p/--print`, `--dangerously-skip-permissions`, `--allowedTools` / `--allowed-tools`, `--output-format json`, `--no-session-persistence`, `--max-budget-usd`, `--permission-mode` — all real and present in `--help`.
- `--max-turns N` (limit agentic loop turns; `--print` mode only) — also real, but **hidden from `claude --help`**. Confirmed via the docs site and a live test: `claude --max-turns 1 --output-format json -p "say hi"` exits cleanly with `num_turns: 1`. **Lesson learned:** `claude --help` is not exhaustive; the docs site is canonical for the full flag set.

## Decision

Both the runner and the rubric scorer subprocess `claude -p`:

**Runner invocation (sketch):**
```
claude --plugin-dir <plugin_worktree>
       --output-format json
       --no-session-persistence
       --max-turns N                              # defense against runaway loops
       --tools "<task.available_tools>"           # preferred when task declares them
       OR
       --dangerously-skip-permissions             # fallback with explicit warning
       -p "<problem_statement>"
```
with `cwd=<task_worktree>` and env vars `BENCHMARK_SCOPE_FILES`, optional `BENCHMARK_SEED`.

Tool-availability strategy:
- **Preferred:** every task instance declares an `available_tools` list (e.g. `["Read", "Glob", "Grep", "Write", "Edit"]` for V1 design tasks). Runner passes these to `--tools <comma-separated>`. Bash is deliberately omitted from V1's design tasks since the agent should not be running anything.
- **Fallback only:** if a task lacks `available_tools`, the runner falls back to `--dangerously-skip-permissions` and logs an explicit warning to stderr so the wide grant is never silent.

**Important — `--tools` vs `--allowedTools`:** these flags are *not* equivalent despite the names suggesting otherwise.
- `--tools "Read Edit Write"`: hard whitelist; tools not in the list are unavailable to the agent. This is the **restriction** flag.
- `--allowedTools "Read Edit Write"`: tools in the list auto-execute without prompting; tools *not* in the list are still available, just prompted. In headless `-p` mode there's no human to answer prompts, so non-listed-tool calls have undefined behavior (hang / timeout / fail). This is the **auto-allow** flag, not a restriction.

The runner uses `--tools` because we want a hard restriction. The schema field is named `available_tools` (mirroring the docs' wording "list of available tools from the built-in set") so that reading the task instance and reading `claude --help` agree on what the field means. An earlier name (`allowed_tools`) was rejected because it invited confusion with the `--allowedTools` flag — they have *different* semantics.

**Judge invocation (sketch):**
```
claude --output-format json
       --no-session-persistence
       --max-turns N
       -p "<judge_prompt_with_rubric_and_agent_output>"
```
with no plugin loaded and a clean cwd. The judge needs no tool access at all (it produces structured JSON from a single prompt), so `--allowedTools ""` or omitting tool flags entirely is fine.

Two layers of bound:
- `--max-turns` caps the agentic loop count.
- `subprocess.Popen.communicate(timeout=…)` caps wall-clock time.

`--max-budget-usd` is informational on Max plan but useful as a sanity cap in case auth ever falls through to API mode.

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
- ⚠️ `claude --help` is **not exhaustive**: `--max-turns` is real but hidden from `--help`. The canonical reference is the official docs site (`docs.claude.com/.../cli-reference`); future flag claims must be verified there, not from `--help` alone.
- ⚠️ The `result.json` from `--output-format json` includes a `total_cost_usd` field that reports the *equivalent API cost* of the call. On Max plan this is informational, not billed. Useful for cost-tracking analytics in Phase 5+; should not be interpreted as actual spend by future readers.
- ⚠️ When/if external collaborators arrive, switch to `claude setup-token` for CI; this ADR will then be superseded by a successor.

## Related ADRs

- ADR-0003 (hybrid scoring) — the LLM-judge component is what this implements.
- ADR-0001 (three-surface topology) — `--plugin-dir` is what makes plugin pinning by tag work cleanly without polluting global config.
