# ADR-0009: Judge isolation via cwd + flags, not `--bare`

## Status
Accepted (smoke-tested 2026-05-04)

## Date
2026-05-04

## Context

ADR-0006 §"Judge invocation" specified that the judge would run in a fresh
context with "no plugin loaded and a clean cwd." T1.4's implementation
operationalized that as `claude --bare …` because `--bare`'s help text
explicitly enumerates the things it skips: hooks, LSP, plugin sync, auto-memory,
keychain reads, CLAUDE.md auto-discovery.

In review preceding T1.5 (the V1 baseline runs), two facts emerged that
invalidate the `--bare` path:

1. **`--bare` strictly requires an API key.** Per `claude --bare --help`:
   *"Anthropic auth is strictly `ANTHROPIC_API_KEY` or `apiKeyHelper` via
   `--settings` (OAuth and keychain are never read)."* The user's Max plan
   provides OAuth credentials, not an API key. `claude setup-token` produces a
   long-lived OAuth token (`sk-ant-oat01-…`), which is the wrong format for the
   `apiKeyHelper`/`ANTHROPIC_API_KEY` slot — it returned `Invalid API key` when
   wired in. Adopting `--bare` would therefore require provisioning a real
   Anthropic API key on a separate billing surface from the Max plan.

2. **Project-local plugins are excluded by cwd, not by `--bare`.** The
   `agent-skills` plugin (`addy-agent-skills`) and `explanatory-output-style`
   plugin are installed at the project level for *this* repo. When a `claude`
   subprocess runs with `cwd` outside the repo, it does not load them.
   Verified empirically by parsing the `system/init` event from
   `--output-format stream-json`: with `cwd=/tmp/robotics-benchmark-judge-cwd-…`,
   the loaded `plugins` array contains only the 6 user-level plugins, and the
   `skills` array contains zero `agent-skills:*` entries.

The judge surface needs isolation from skills/plugins that compete with the
robotics plugin under test, but does **not** need to be sealed off from
everything `--bare` blocks. A flag-and-cwd-based isolation contract is
sufficient and preserves the Max-plan auth path.

## Decision

The judge does **not** use `--bare`. It runs as:

```
claude --print
       --output-format json
       --no-session-persistence
       --disable-slash-commands
       --max-turns 3
       --json-schema "<JUDGE_OUTPUT_SCHEMA>"
       --allowedTools ""
       -p "<judge_prompt>"
```

with `cwd=<per-process tempdir under /tmp/robotics-benchmark-judge-cwd-…>` and
no environment override. Authentication uses the user's interactive OAuth
(keychain) — the same credential the runner uses. No setup-token, no API key,
no `--settings` file.

**Rationale per flag:**

- `--no-session-persistence`: prevents cross-call state in `~/.claude/projects/`.
- `--disable-slash-commands`: stops skills from being auto-resolved into the
  prompt. Note: this disables *skill* loading; native tools are gated by the
  `--allowedTools` flag below.
- `--max-turns 3`: empirically the minimum value that allows `--json-schema`
  to complete. The structured-output mechanism is implemented internally as a
  forced tool round-trip (assistant emits a `tool_use` block, the harness
  delivers a `tool_result`, the assistant emits the final text). Three turns
  cover this; one turn errors with `error_max_turns` / `stop_reason: tool_use`.
- `--json-schema`: structured output. The parsed JSON object lands in
  `wrapper["structured_output"]` — *not* in `wrapper["result"]`, which carries
  the model's plain-text accompaniment. Older versions inlined JSON in `result`;
  the parser falls back to that path for compatibility.
- `--allowedTools ""`: empty allowlist = no real tools exposed. The
  structured-output round-trip is internal and is not gated by this flag.
- `cwd=<isolated tempdir>`: load-bearing for project-local plugin exclusion.
  Per-process (cached after `mkdtemp`, removed at interpreter exit). A
  dedicated prefix (`robotics-benchmark-judge-cwd-`) is used in preference to
  `/tmp` so that any project-CLAUDE.md or `.claude/` that happens to sit in
  `/tmp` cannot be picked up, and any stray writes are contained.

**User-level plugins loaded by the judge** (per `system/init` on 2026-05-04):
`andrej-karpathy-skills`, `claude-md-management`, `commit-commands`, `hookify`,
`security-guidance`, `skill-creator`. These are accepted for V1 because none
overlap with the experiment-design rubric content. **Revisit at Phase 3**:
`andrej-karpathy-skills` includes goal-driven-execution guidance (write the
reproducer test first) that overlaps with the planned debugging-task rubric;
its presence in the baseline would silently flatten the eventual robotics-plugin
debugging delta.

## Verification

`harness/smoke_test_judge.py` runs two probes:

1. **cwd-exclusion (deterministic)** — spawns `claude --output-format stream-json`
   from the judge cwd, parses the first `system/init` event, asserts no
   forbidden plugin (`agent-skills`, `explanatory-output-style`) is in the
   loaded `plugins` array, and asserts no skill identifier starts with
   those plugin namespaces.
2. **Auth + structured output** — round-trips a trivial rubric through
   `subprocess_judge_runner`. Pass requires both OAuth-via-keychain to work
   and the `wrapper["structured_output"]` payload to parse cleanly.

Both probes passed on 2026-05-04 with `claude_code_version: 2.1.126`. The
smoke test must be re-run **before each plugin-version baseline** as a
regression check against future Claude Code releases changing plugin-discovery
or structured-output behavior.

## Alternatives Considered

### Keep `--bare`; provision an Anthropic API key
- **Pros:** `--bare`'s isolation contract is binary-enforced and easier to
  reason about than env+flag-based isolation.
- **Cons:** Separate billing surface (API spend) on top of the Max plan; small
  per-baseline cost but adds an account-management burden the project doesn't
  otherwise need; defeats the spirit of ADR-0006 ("single auth surface").
- **Rejected.**

### Keep `--bare`; use `setup-token` + `apiKeyHelper`
- **Cons:** Token-format mismatch. `setup-token` produces an OAuth access token
  (`sk-ant-oat01-`) consumed via Bearer auth on a code path `--bare` blocks.
  `apiKeyHelper`'s output is treated as an API key (`x-api-key` header). Wiring
  the OAuth token through `apiKeyHelper` returns `Invalid API key`.
- **Rejected** (verified empirically before this ADR was written).

### Drop `--bare`; isolate via clean `HOME` env override
- **Pros:** Stronger isolation than cwd alone (also blocks `~/.claude/CLAUDE.md`
  and user-level plugins).
- **Cons:** More implementation surface (per-process tempdir for HOME, possible
  symlink of the credentials file if keychain proves HOME-dependent on Linux);
  blocks the 6 user-level plugins, which on inspection don't actually compete
  with V1 task content. Cost outweighs benefit at this stage.
- **Rejected for V1**, with the explicit understanding that Phase 3 may revisit
  this if user-level plugins start overlapping with debugging/spec/planning
  task rubrics.

### Manual judge runs (no automation)
- **Cons:** Defeats N=3 stdev measurement; kills T1.5's noise-floor objective.
- **Rejected.**

## Consequences

- ✅ Same Max plan covers runner and judge surfaces (restores ADR-0006's spirit).
- ✅ No new auth setup, no separate API account, no token-management code path.
- ✅ Project-local high-impact skills (`agent-skills:spec`, `agent-skills:plan`,
  `agent-skills:idea-refine`, etc.) are deterministically excluded from judge
  scoring.
- ⚠️ Isolation is a **convention** (cwd outside repo + specific flags), not a
  binary guarantee. A future Claude Code release that changes plugin-discovery
  rules could silently re-load local plugins. The smoke test is the
  pre-baseline regression check.
- ⚠️ Six user-level plugins remain loaded by the judge. For V1 (experiment
  design), none overlap rubric content. **Action item for Phase 3:**
  re-evaluate `andrej-karpathy-skills` overlap with debugging-task rubrics
  before Phase 3 baselines are run.
- ⚠️ User's `~/.claude/CLAUDE.md` (currently the Karpathy behavioral guidelines
  + auto-memory pointer) is loaded into the judge's system prompt. Today's
  content is process-oriented (think-before-coding, simplicity, surgical
  changes) and does not bias rubric scoring. **Discipline:** keep
  `~/.claude/CLAUDE.md` process-oriented; do not add evaluation-oriented
  guidance ("always demand tests in code reviews"). A future ADR may add a
  `result.json` snapshot of `~/.claude/CLAUDE.md`'s SHA to detect drift.
- ⚠️ The user-side artifacts created during the failed `setup-token` attempt
  (`~/.local/bin/robotics-benchmark-claude-auth-helper` and
  `~/.config/robotics-skills-benchmark/judge-settings.json`) are no longer
  referenced by the harness and can be deleted.

## Related ADRs

- **ADR-0006** (headless Claude Code for both surfaces) — narrowed by this ADR
  on the judge surface specifically: judge invocation flags differ from
  ADR-0006's sketch (no `--bare`, +`--disable-slash-commands`, +`--max-turns 3`,
  cwd is per-process tempdir not "a clean cwd"). ADR-0006's auth claim ("Max
  plan covers both surfaces") is preserved.
- **ADR-0003** (hybrid scoring) — judge independence requirement is satisfied
  by cwd-exclusion + `--disable-slash-commands` + `--allowedTools ""`,
  rather than by `--bare`'s blanket isolation.
