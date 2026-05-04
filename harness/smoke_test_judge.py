"""Manual smoke test for the judge subprocess (ADR-0009).

Three probes against the real `claude` binary:

  1. cwd-exclusion (deterministic) — spawn `claude --output-format stream-json`
     from the isolated judge cwd, parse the `system/init` event, and assert
     no project-local plugin (`agent-skills`, `explanatory-output-style`) is
     in the loaded plugin list. This is protocol-level evidence, not a model
     question, so it cannot be fooled by hallucination.

  2. Auth + structured output — round-trip a trivial rubric through the real
     `subprocess_judge_runner`. Pass = parsed scores; fail = JudgeInvocationError.

  3. Plugin allowlist (eyeball) — print the loaded plugin list so the human
     can confirm only expected user-level plugins appear.

Not part of pytest: hits the real `claude` binary and consumes a small number
of judge tokens. Run manually before T1.5 baselines:

    python3 -m harness.smoke_test_judge

Per ADR-0009: cwd-based exclusion is the load-bearing mechanism. If a future
Claude Code release changes plugin-discovery rules (e.g., starts loading
project-local plugins regardless of cwd), this smoke test catches it before
a baseline run silently absorbs the change.
"""
from __future__ import annotations

import json
import subprocess
import sys

from harness.score_rubric import (
    JudgeInvocationError,
    _build_judge_cmd,
    _judge_cwd,
    build_judge_prompt,
    subprocess_judge_runner,
)

_TINY_RUBRIC = """Score the deliverable on two dimensions, each 0-3:
- clarity: is the text understandable?
- brevity: is it concise?
"""

_TINY_DELIVERABLE = "The cat sat on the mat."

# Plugins we expect to be EXCLUDED when cwd is outside this repo. These are
# the project-local plugins per the /plugins UI screenshot dated 2026-05-04.
_FORBIDDEN_PLUGINS = {"agent-skills", "explanatory-output-style"}


def _print_header(title: str) -> None:
    print(f"\n=== {title} ===")


def cwd_exclusion_probe() -> tuple[bool, list[str]]:
    """Spawn `claude --output-format stream-json` from the judge cwd, parse
    the system/init event, and assert no project-local plugin is loaded.

    Returns (passed, loaded_plugin_names) so the caller can also print the
    plugin list for eyeball confirmation.
    """
    _print_header("Probe 1 — cwd-based local-plugin exclusion (system/init)")
    cwd = _judge_cwd()
    print(f"  cwd: {cwd}")
    cmd = [
        "claude",
        "--print",
        "--output-format", "stream-json",
        "--verbose",  # required for --print + stream-json
        "--no-session-persistence",
        "--disable-slash-commands",
        "--max-turns", "1",
        "--tools", "",
        "-p", "hi",
    ]
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=300)
    if proc.returncode != 0:
        print(f"FAIL: claude exited {proc.returncode}: {proc.stderr.strip()[:500]}",
              file=sys.stderr)
        return False, []
    first_line = proc.stdout.splitlines()[0] if proc.stdout else ""
    try:
        event = json.loads(first_line)
    except json.JSONDecodeError as e:
        print(f"FAIL: first stream-json event is not JSON: {first_line[:200]!r} ({e})",
              file=sys.stderr)
        return False, []
    if event.get("type") != "system" or event.get("subtype") != "init":
        print(f"FAIL: expected system/init, got type={event.get('type')!r} "
              f"subtype={event.get('subtype')!r}", file=sys.stderr)
        return False, []
    if event.get("cwd") != str(cwd):
        print(f"FAIL: system/init cwd={event.get('cwd')!r} != expected {str(cwd)!r}",
              file=sys.stderr)
        return False, []
    plugin_names = sorted(p["name"] for p in event.get("plugins", []))
    leaked = _FORBIDDEN_PLUGINS & set(plugin_names)
    if leaked:
        print(f"FAIL: forbidden local plugins loaded: {leaked}", file=sys.stderr)
        return False, plugin_names
    # Also defense-in-depth: assert no skill identifier starts with the
    # local-plugin namespace (e.g., "agent-skills:spec").
    skill_ids = event.get("skills", [])
    leaked_skills = [s for s in skill_ids if any(s.startswith(p + ":") for p in _FORBIDDEN_PLUGINS)]
    if leaked_skills:
        print(f"FAIL: forbidden skills loaded: {leaked_skills}", file=sys.stderr)
        return False, plugin_names
    print(f"  loaded plugins ({len(plugin_names)}): {plugin_names}")
    print("PASS")
    return True, plugin_names


def auth_and_structured_output_probe() -> bool:
    """Round-trip a trivial rubric through subprocess_judge_runner.

    Failure mode pre-ADR-0009 was 'Not logged in' or 'Invalid API key'; passing
    here proves OAuth (keychain) auth works without --bare.
    """
    _print_header("Probe 2 — auth + structured output via subprocess_judge_runner")
    print(f"  cmd: {_build_judge_cmd('<prompt>')}")
    try:
        payload = subprocess_judge_runner(build_judge_prompt(_TINY_RUBRIC, _TINY_DELIVERABLE))
    except JudgeInvocationError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return False
    if not isinstance(payload, dict) or "scores" not in payload:
        print(f"FAIL: payload missing 'scores': {payload!r}", file=sys.stderr)
        return False
    print(f"  payload: {json.dumps(payload, indent=2)[:400]}")
    print("PASS")
    return True


def main() -> int:
    ok1, plugin_names = cwd_exclusion_probe()
    ok2 = auth_and_structured_output_probe()

    _print_header("Summary")
    print(f"  cwd-exclusion probe:        {'PASS' if ok1 else 'FAIL'}")
    print(f"  auth + structured output:   {'PASS' if ok2 else 'FAIL'}")
    if ok1:
        print(f"  judge sees these plugins:   {plugin_names}")
        print("  (eyeball: confirm none of these compete with the V1 task rubric)")
    return 0 if (ok1 and ok2) else 1


if __name__ == "__main__":
    sys.exit(main())
