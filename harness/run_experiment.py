#!/usr/bin/env python3
"""Run a benchmark experiment: (plugin_tag, task_id, run_id) → result.json.

Per ADR-0006: invokes Claude Code in headless mode (`claude -p`) with the
plugin loaded from --plugin-path. The same auth (Max plan) covers both this
and the rubric scorer.

Per ADR-0002: the task repo is materialized in a git worktree at base_sha
under /tmp/exp-scratch/<run-id>/ so multiple plugin versions can run against
the same task concurrently.

Per ADR-0001: task repos are referenced by URL+SHA in tasks/index.yaml and
cloned to a local cache (~/.cache/robotics-skills-benchmark/repos/) on first
use; subsequent runs reuse the cache.

Output artifacts under experiments/<YYYY-MM-DD>_<tag>_<task>_<run>/:
  - result.json  — structured result; scoring section left empty here
                   (T1.4's scorers fill it in). status field is set.
  - transcript.md — the agent's stdout, prettified if it's JSON.
  - diff.patch   — unified diff vs base_sha (includes untracked files).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
TASKS_DIR = REPO_ROOT / "tasks"
INSTANCES_DIR = TASKS_DIR / "instances"

DEFAULT_SCRATCH_ROOT = Path("/tmp/exp-scratch")
DEFAULT_EXPERIMENTS_ROOT = REPO_ROOT / "experiments"
DEFAULT_REPOS_CACHE = Path.home() / ".cache" / "robotics-skills-benchmark" / "repos"
DEFAULT_PLUGINS_CACHE = Path.home() / ".cache" / "robotics-skills-benchmark" / "plugins"
DEFAULT_MAX_TURNS = 50

RESULT_SCHEMA_VERSION = 1


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

def now_utc_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today_utc_date() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")


def safe_path_component(s: str) -> str:
    """Make a string safe for use as a filesystem path component."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_") or "_"


# ---------------------------------------------------------------------------
# Task loading
# ---------------------------------------------------------------------------

def load_task(task_id: str) -> dict:
    path = INSTANCES_DIR / task_id / "task.yaml"
    if not path.exists():
        raise FileNotFoundError(
            f"task instance not found: {path}. "
            f"Available: {sorted(p.parent.name for p in INSTANCES_DIR.glob('*/task.yaml'))}"
        )
    with path.open() as f:
        task = yaml.safe_load(f)
    task["_task_dir"] = path.parent
    return task


# ---------------------------------------------------------------------------
# Repo cache + worktree management (per ADR-0001, ADR-0002)
# ---------------------------------------------------------------------------

def cache_dir_for_repo(repos_cache: Path, base_repo: str) -> Path:
    parts = base_repo.rstrip("/").removesuffix(".git").split("/")
    owner, repo = parts[-2], parts[-1]
    return repos_cache / f"{owner}__{repo}"


def ensure_cached_clone(base_repo: str, base_sha: str, repos_cache: Path) -> Path:
    """Ensure base_repo is cloned locally and base_sha is reachable. Returns the cache dir."""
    cache = cache_dir_for_repo(repos_cache, base_repo)
    cache.parent.mkdir(parents=True, exist_ok=True)

    if not cache.exists():
        print(f"[runner] cloning {base_repo} → {cache}", file=sys.stderr)
        subprocess.run(
            ["git", "clone", "--no-checkout", base_repo, str(cache)],
            check=True,
        )

    # Verify base_sha is reachable; fetch if not
    check = subprocess.run(
        ["git", "-C", str(cache), "cat-file", "-t", base_sha],
        capture_output=True, text=True,
    )
    if check.returncode != 0:
        print(f"[runner] fetching {base_repo} (sha {base_sha[:8]} not yet present)", file=sys.stderr)
        subprocess.run(
            ["git", "-C", str(cache), "fetch", "--all", "--tags"],
            check=True,
        )
        check = subprocess.run(
            ["git", "-C", str(cache), "cat-file", "-t", base_sha],
            capture_output=True, text=True,
        )
        if check.returncode != 0:
            raise RuntimeError(
                f"base_sha {base_sha} not reachable in {base_repo} after fetch. "
                f"The upstream may have rebased or removed it."
            )
    return cache


def add_worktree(cache: Path, base_sha: str, dest: Path) -> None:
    if dest.exists():
        raise RuntimeError(f"worktree destination already exists: {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "-C", str(cache), "worktree", "add", "--detach", str(dest), base_sha],
        check=True,
    )


def remove_worktree(cache: Path, dest: Path) -> None:
    """Best-effort prune of a worktree. Safe to call on a missing worktree."""
    subprocess.run(
        ["git", "-C", str(cache), "worktree", "remove", "--force", str(dest)],
        check=False,
        capture_output=True,
    )


def resolve_git_sha(directory: Path) -> str | None:
    """Returns the 40-char HEAD commit SHA at `directory`, or None if not a git working tree."""
    if not directory.exists():
        return None
    try:
        result = subprocess.run(
            ["git", "-C", str(directory), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=False,
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    sha = result.stdout.strip()
    if len(sha) == 40 and all(c in "0123456789abcdef" for c in sha):
        return sha
    return None


# ---------------------------------------------------------------------------
# Plugin materialization (per ADR-0001 + ADR-0002)
# ---------------------------------------------------------------------------

def materialize_plugin(plugin_repo: str, plugin_ref: str, plugins_cache: Path) -> Path:
    """Clone plugin_repo to plugins_cache and create a persistent worktree at plugin_ref.

    Returns the worktree path suitable for `claude --plugin-dir`. The worktree is
    cached under <plugins_cache>/<owner>__<repo>/_worktrees/<safe_ref>/ and reused
    across runs of the same plugin tag. Not auto-pruned (cheap; reused often).
    """
    cache = cache_dir_for_repo(plugins_cache, plugin_repo)
    cache.parent.mkdir(parents=True, exist_ok=True)

    if not cache.exists():
        print(f"[runner] cloning plugin {plugin_repo} → {cache}", file=sys.stderr)
        subprocess.run(
            ["git", "clone", "--no-checkout", plugin_repo, str(cache)],
            check=True,
        )

    # Verify the ref is reachable; fetch if not.
    check = subprocess.run(
        ["git", "-C", str(cache), "rev-parse", "--verify", f"{plugin_ref}^{{commit}}"],
        capture_output=True, text=True,
    )
    if check.returncode != 0:
        print(f"[runner] fetching plugin (ref {plugin_ref!r} not yet present)", file=sys.stderr)
        subprocess.run(
            ["git", "-C", str(cache), "fetch", "--all", "--tags"],
            check=True,
        )
        check = subprocess.run(
            ["git", "-C", str(cache), "rev-parse", "--verify", f"{plugin_ref}^{{commit}}"],
            capture_output=True, text=True,
        )
        if check.returncode != 0:
            raise RuntimeError(
                f"plugin ref {plugin_ref!r} not found in {plugin_repo} after fetch"
            )

    worktree = cache / "_worktrees" / safe_path_component(plugin_ref)
    if not worktree.exists():
        worktree.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "-C", str(cache), "worktree", "add", "--detach", str(worktree), plugin_ref],
            check=True,
        )
    return worktree


# ---------------------------------------------------------------------------
# Idempotency (per T1.3 acceptance criterion)
# ---------------------------------------------------------------------------

def find_existing_experiment(
    experiments_root: Path, plugin_tag: str, task_id: str, run_id: str
) -> Path | None:
    """Idempotency key is (plugin_tag, task_id, run_id), independent of date."""
    if not experiments_root.exists():
        return None
    suffix = f"_{plugin_tag}_{task_id}_{run_id}"
    for child in experiments_root.iterdir():
        if child.is_dir() and child.name.endswith(suffix):
            return child
    return None


def experiment_dir_name(plugin_tag: str, task_id: str, run_id: str) -> str:
    return f"{today_utc_date()}_{plugin_tag}_{task_id}_{run_id}"


# ---------------------------------------------------------------------------
# Plugin sanity check
# ---------------------------------------------------------------------------

def check_plugin_path(plugin_path: Path) -> str | None:
    """Returns a warning message if the plugin path looks unusual; None if it looks plausible."""
    if not plugin_path.exists() or not plugin_path.is_dir():
        return f"plugin path does not exist or is not a directory: {plugin_path}"
    has_manifest = (plugin_path / ".claude-plugin" / "plugin.json").exists()
    has_skills = (plugin_path / "skills").exists()
    if not (has_manifest or has_skills):
        return (
            f"plugin path {plugin_path} has neither .claude-plugin/plugin.json "
            f"nor a skills/ directory; Claude Code may not load anything"
        )
    return None


# ---------------------------------------------------------------------------
# Agent invocation (per ADR-0006)
# ---------------------------------------------------------------------------

def run_agent(
    plugin_path: Path,
    task_worktree: Path,
    problem_statement: str,
    scope_files: list[str],
    timeout_s: int,
    available_tools: list[str] | None = None,
    max_turns: int = DEFAULT_MAX_TURNS,
    seed: str | None = None,
) -> dict:
    """Subprocess `claude -p` with the plugin loaded. Returns structured result.

    Per ADR-0006: uses `--plugin-dir`, `--output-format json`,
    `--no-session-persistence`, `--max-turns N`. Permissions handling:

      - If `available_tools` is given (preferred for V1 design tasks): use
        `--allowedTools <space-separated list>` to restrict the agent to a
        specific toolset. Bash is deliberately omitted from V1's design tasks.

      - Otherwise: fall back to `--dangerously-skip-permissions` and log a
        warning so the user is aware of the broad permission grant.

    Wall-clock timeout via `Popen.communicate(timeout=…)`. The `--max-turns`
    flag (documented but hidden from `claude --help`) provides an additional
    defense against runaway agentic loops.
    """
    cmd: list[str] = [
        "claude",
        "--plugin-dir", str(plugin_path),
        "--output-format", "json",
        "--no-session-persistence",
        "--max-turns", str(max_turns),
    ]
    if available_tools:
        # Use --tools (restrict to the listed set) rather than --allowedTools
        # (auto-allow-without-prompt; doesn't restrict availability). For headless
        # benchmark runs we want a hard restriction. See ADR-0006.
        cmd += ["--tools", ",".join(available_tools)]
    else:
        print(
            "[runner] WARNING: task has no `available_tools`; "
            "falling back to --dangerously-skip-permissions. "
            "Add an available_tools list to the task instance to scope tools tightly.",
            file=sys.stderr,
        )
        cmd.append("--dangerously-skip-permissions")
    cmd += ["-p", problem_statement]

    env = os.environ.copy()
    env["BENCHMARK_SCOPE_FILES"] = ":".join(scope_files)
    if seed is not None:
        env["BENCHMARK_SEED"] = seed

    started_iso = now_utc_iso()
    started_mono = time.monotonic()

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(task_worktree),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as e:
        return {
            "status": "error",
            "exit_code": -1,
            "stdout": "",
            "stderr": str(e),
            "runtime_s": time.monotonic() - started_mono,
            "started_at": started_iso,
            "completed_at": now_utc_iso(),
            "error": {
                "type": "missing-binary",
                "message": "`claude` binary not found on PATH. Is Claude Code installed?",
            },
        }

    try:
        stdout, stderr = proc.communicate(timeout=timeout_s)
        exit_code = proc.returncode
        if exit_code == 0:
            status, error = "success", None
        else:
            status, error = "error", {
                "type": "non-zero-exit",
                "message": f"claude exited with code {exit_code}",
            }
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            stdout, stderr = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            stdout, stderr = "", ""
        exit_code = -1
        status = "timeout"
        error = {"type": "timeout", "message": f"exceeded timeout_s={timeout_s}"}

    return {
        "status": status,
        "exit_code": exit_code,
        "stdout": stdout or "",
        "stderr": stderr or "",
        "runtime_s": time.monotonic() - started_mono,
        "started_at": started_iso,
        "completed_at": now_utc_iso(),
        "error": error,
    }


# ---------------------------------------------------------------------------
# Diff capture
# ---------------------------------------------------------------------------

def capture_diff(task_worktree: Path, base_sha: str) -> tuple[str, list[str]]:
    """Capture the agent's full diff vs base_sha, including untracked files.

    Trick: `git add -A` first, then `git diff --cached base_sha`. Staging makes
    new files visible to diff without committing them.
    """
    subprocess.run(
        ["git", "-C", str(task_worktree), "add", "-A"],
        check=True, capture_output=True,
    )
    diff = subprocess.run(
        ["git", "-C", str(task_worktree), "diff", "--cached", base_sha],
        capture_output=True, text=True, check=True,
    ).stdout
    names = subprocess.run(
        ["git", "-C", str(task_worktree), "diff", "--cached", "--name-only", base_sha],
        capture_output=True, text=True, check=True,
    ).stdout
    files = [f for f in names.strip().split("\n") if f]
    return diff, files


# ---------------------------------------------------------------------------
# Transcript prettifier
# ---------------------------------------------------------------------------

def render_transcript(stdout: str, stderr: str) -> str:
    """Render the agent's output as readable markdown. Falls back to raw on parse failure."""
    body = ["# Agent transcript", ""]
    parsed = None
    try:
        parsed = json.loads(stdout)
    except (json.JSONDecodeError, ValueError):
        pass

    if isinstance(parsed, dict):
        # Common claude --output-format json shape: {"result": "...", ...} or
        # {"text": "...", ...}. Render whichever is present, plus the raw JSON
        # at the end for full audit.
        for key in ("result", "text", "response", "output"):
            if key in parsed and isinstance(parsed[key], str):
                body += [f"## {key}", "", parsed[key], ""]
                break
        body += ["## Raw JSON output", "", "```json", json.dumps(parsed, indent=2), "```", ""]
    else:
        body += ["## Raw stdout", "", "```", stdout.rstrip(), "```", ""]

    if stderr.strip():
        body += ["## stderr", "", "```", stderr.rstrip(), "```", ""]

    return "\n".join(body)


# ---------------------------------------------------------------------------
# Result writer
# ---------------------------------------------------------------------------

def write_result(experiment_dir: Path, result: dict) -> None:
    experiment_dir.mkdir(parents=True, exist_ok=True)
    result_path = experiment_dir / "result.json"
    tmp = result_path.with_suffix(".json.tmp")
    with tmp.open("w") as f:
        json.dump(result, f, indent=2, sort_keys=True)
    tmp.replace(result_path)


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def run(
    plugin_tag: str,
    task_id: str,
    run_id: str,
    *,
    plugin_path: Path | None = None,
    plugin_repo: str | None = None,
    plugin_ref: str | None = None,
    scratch_root: Path = DEFAULT_SCRATCH_ROOT,
    experiments_root: Path = DEFAULT_EXPERIMENTS_ROOT,
    repos_cache: Path = DEFAULT_REPOS_CACHE,
    plugins_cache: Path = DEFAULT_PLUGINS_CACHE,
    max_turns: int = DEFAULT_MAX_TURNS,
    seed: str | None = None,
) -> Path:
    """Execute one experiment. Returns the path to the experiment directory.

    Plugin sourcing — exactly one of:
      - `plugin_path`: a local directory already at the desired tag (caller manages checkout).
      - `(plugin_repo, plugin_ref)`: clone the URL and worktree at the ref (cached).
    """
    if (plugin_path is None) == (plugin_repo is None):
        raise ValueError(
            "Exactly one of `plugin_path` or `(plugin_repo, plugin_ref)` must be provided."
        )
    if plugin_repo is not None and plugin_ref is None:
        raise ValueError("`plugin_repo` requires `plugin_ref`.")

    # 1. Idempotency check (per ADR-0001 reproducibility key)
    existing = find_existing_experiment(experiments_root, plugin_tag, task_id, run_id)
    if existing is not None:
        raise RuntimeError(
            f"experiment for ({plugin_tag}, {task_id}, {run_id}) already exists at {existing}. "
            f"Pick a different run_id, or delete the existing experiment to re-run."
        )

    # 2. Load task instance
    task = load_task(task_id)
    base_repo: str = task["base_repo"]
    base_sha: str = task["base_sha"]
    problem_statement: str = task["problem_statement"]
    scope_files: list[str] = task["scope_files"]
    timeout_s: int = task["timeout_s"]
    available_tools: list[str] | None = task.get("available_tools")

    # 3. Resolve plugin path (clone+worktree if URL+ref mode)
    if plugin_path is None:
        assert plugin_repo is not None and plugin_ref is not None
        plugin_path = materialize_plugin(plugin_repo, plugin_ref, plugins_cache)
    plugin_warning = check_plugin_path(plugin_path)
    if plugin_warning:
        print(f"[runner] WARNING: {plugin_warning}", file=sys.stderr)

    # Resolve the plugin's actual commit SHA. This is the canonical
    # reproducibility key — `plugin_ref` (a branch/tag) can move; `plugin_tag`
    # is a human-supplied label; only `plugin_sha` pins the bytes the agent
    # ran with. Recorded in result.json regardless of plugin source mode.
    plugin_sha = resolve_git_sha(plugin_path)
    if plugin_sha is None:
        print(
            f"[runner] WARNING: plugin path {plugin_path} is not a git working tree; "
            "result.json will record plugin_sha=null. Reproducibility from this "
            "result will require the user to remember what was at that path.",
            file=sys.stderr,
        )

    # 4. Prepare experiment dir + write incomplete partial result.
    #    If the runner itself crashes after this point, the partial remains
    #    for debugging (per T1.3 acceptance criterion).
    exp_dir = experiments_root / experiment_dir_name(plugin_tag, task_id, run_id)
    partial: dict = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "experiment_id": exp_dir.name,
        "plugin_tag": plugin_tag,
        "plugin_path": str(plugin_path),
        "plugin_repo": plugin_repo,
        "plugin_ref": plugin_ref,
        "plugin_sha": plugin_sha,
        "task_id": task_id,
        "run_id": run_id,
        "base_repo": base_repo,
        "base_sha": base_sha,
        "scope_files_declared": scope_files,
        "available_tools": available_tools,
        "max_turns": max_turns,
        "seed": seed,
        "started_at": now_utc_iso(),
        "completed_at": None,
        "runtime_s": None,
        "exit_code": None,
        "status": "incomplete",
        "error": None,
        "files_modified": [],
        "transcript_bytes": 0,
        "scoring": {},
    }
    write_result(exp_dir, partial)

    # 5. Materialize the task worktree at base_sha. Path includes the full
    #    triple to prevent collisions across concurrent (plugin_tag, task_id, run_id)
    #    experiments that happen to share a run_id.
    cache = ensure_cached_clone(base_repo, base_sha, repos_cache)
    task_worktree = scratch_root / safe_path_component(f"{plugin_tag}__{task_id}__{run_id}")
    if task_worktree.exists():
        # Stale leftover from a previous failed run; prune before re-creating.
        remove_worktree(cache, task_worktree)
    add_worktree(cache, base_sha, task_worktree)

    final_result = dict(partial)
    success_for_cleanup = False

    try:
        # 6. Run the agent
        agent = run_agent(
            plugin_path=plugin_path,
            task_worktree=task_worktree,
            problem_statement=problem_statement,
            scope_files=scope_files,
            timeout_s=timeout_s,
            available_tools=available_tools,
            max_turns=max_turns,
            seed=seed,
        )
        final_result.update({
            "started_at": agent["started_at"],
            "completed_at": agent["completed_at"],
            "runtime_s": agent["runtime_s"],
            "exit_code": agent["exit_code"],
            "status": agent["status"],
            "error": agent["error"],
            "transcript_bytes": len(agent["stdout"]),
        })

        # 7. Capture diff and files-modified
        diff_text, files_modified = capture_diff(task_worktree, base_sha)
        final_result["files_modified"] = files_modified

        # 8. Write artifacts
        (exp_dir / "diff.patch").write_text(diff_text)
        (exp_dir / "transcript.md").write_text(render_transcript(agent["stdout"], agent["stderr"]))

        # 9. Persist final result
        write_result(exp_dir, final_result)

        success_for_cleanup = (final_result["status"] == "success")

    except Exception as e:
        # Runner-level crash. Persist what we know so the experiment dir is
        # parseable; surface the exception to the caller.
        final_result.update({
            "status": "error",
            "error": {"type": type(e).__name__, "message": str(e)},
            "completed_at": now_utc_iso(),
        })
        write_result(exp_dir, final_result)
        raise
    finally:
        # 10. Cleanup per ADR-0002: prune worktree on success, retain on failure.
        if success_for_cleanup:
            remove_worktree(cache, task_worktree)
        else:
            # Record the retained worktree path for inspection.
            final_result["scratch_dir"] = str(task_worktree)
            write_result(exp_dir, final_result)

    return exp_dir


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run one benchmark experiment.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Plugin sourcing: --plugin-path OR (--plugin-repo + --plugin-ref). Mutually exclusive.
    plugin_group = parser.add_argument_group("plugin sourcing (one of two modes)")
    plugin_group.add_argument(
        "--plugin-path", type=Path, default=None,
        help="Local directory containing the plugin (already at the desired tag). "
             "Use this when developing on the plugin or working with a tag that doesn't yet exist remotely.",
    )
    plugin_group.add_argument(
        "--plugin-repo", default=None,
        help="Plugin repo URL. Together with --plugin-ref, the runner clones to "
             "~/.cache/robotics-skills-benchmark/plugins/ and creates a worktree at the ref.",
    )
    plugin_group.add_argument(
        "--plugin-ref", default=None,
        help="Git ref (tag, branch, or SHA) to check out. Required with --plugin-repo.",
    )

    parser.add_argument("--plugin-tag", required=True,
                        help="Tag identifier recorded in result.json (e.g., v0.1.0). "
                             "Need not match plugin_ref exactly — useful for pre-tag development.")
    parser.add_argument("--task", required=True, dest="task_id",
                        help="Task ID (subdirectory name under tasks/instances/).")
    parser.add_argument("--run", required=True, dest="run_id",
                        help="Run ID (e.g., baseline-1).")

    parser.add_argument("--max-turns", type=int, default=DEFAULT_MAX_TURNS,
                        help=f"Hard cap on agentic loop turns. Default: {DEFAULT_MAX_TURNS}.")
    parser.add_argument("--scratch-root", type=Path, default=DEFAULT_SCRATCH_ROOT,
                        help=f"Where task worktrees live. Default: {DEFAULT_SCRATCH_ROOT}")
    parser.add_argument("--experiments-root", type=Path, default=DEFAULT_EXPERIMENTS_ROOT,
                        help=f"Where result.json artifacts go. Default: {DEFAULT_EXPERIMENTS_ROOT}")
    parser.add_argument("--repos-cache", type=Path, default=DEFAULT_REPOS_CACHE,
                        help=f"Where task repos are cached. Default: {DEFAULT_REPOS_CACHE}")
    parser.add_argument("--plugins-cache", type=Path, default=DEFAULT_PLUGINS_CACHE,
                        help=f"Where plugin clones are cached. Default: {DEFAULT_PLUGINS_CACHE}")
    parser.add_argument("--seed", default=None,
                        help="Optional BENCHMARK_SEED env var passed to the agent.")
    args = parser.parse_args(argv)

    if (args.plugin_path is None) == (args.plugin_repo is None):
        parser.error("provide either --plugin-path OR (--plugin-repo + --plugin-ref)")
    if args.plugin_repo is not None and args.plugin_ref is None:
        parser.error("--plugin-repo requires --plugin-ref")

    try:
        exp_dir = run(
            plugin_tag=args.plugin_tag,
            task_id=args.task_id,
            run_id=args.run_id,
            plugin_path=args.plugin_path.resolve() if args.plugin_path else None,
            plugin_repo=args.plugin_repo,
            plugin_ref=args.plugin_ref,
            scratch_root=args.scratch_root,
            experiments_root=args.experiments_root,
            repos_cache=args.repos_cache,
            plugins_cache=args.plugins_cache,
            max_turns=args.max_turns,
            seed=args.seed,
        )
    except Exception as e:
        print(f"[runner] FAILED: {type(e).__name__}: {e}", file=sys.stderr)
        return 2

    print(str(exp_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
