"""Unit tests for harness.run_experiment.

Covers pure functions and file-system helpers that don't require subprocess
or network. The actual claude-subprocess path is exercised by T1.5's
integration runs, not here.
"""
from __future__ import annotations

import json
from pathlib import Path

import subprocess

from harness.run_experiment import (
    cache_dir_for_repo,
    check_plugin_path,
    compute_scoring,
    experiment_dir_name,
    find_existing_experiment,
    gather_deliverable,
    render_transcript,
    resolve_git_sha,
    safe_path_component,
)


# ---------------------------------------------------------------------------
# cache_dir_for_repo
# ---------------------------------------------------------------------------

def test_cache_dir_for_repo_basic():
    cache = cache_dir_for_repo(Path("/tmp/cache"), "https://github.com/foo/bar")
    assert cache == Path("/tmp/cache/foo__bar")


def test_cache_dir_for_repo_with_dot_git():
    cache = cache_dir_for_repo(Path("/tmp/cache"), "https://github.com/foo/bar.git")
    assert cache == Path("/tmp/cache/foo__bar")


def test_cache_dir_for_repo_with_trailing_slash():
    cache = cache_dir_for_repo(Path("/tmp/cache"), "https://github.com/foo/bar/")
    assert cache == Path("/tmp/cache/foo__bar")


# ---------------------------------------------------------------------------
# find_existing_experiment (idempotency key independent of date prefix)
# ---------------------------------------------------------------------------

def test_find_existing_experiment_returns_none_when_root_missing(tmp_path):
    assert find_existing_experiment(tmp_path / "nonexistent", "v0.1.0", "t", "r1") is None


def test_find_existing_experiment_returns_none_when_no_match(tmp_path):
    (tmp_path / "2026-05-02_v0.1.0_other-task_r1").mkdir()
    assert find_existing_experiment(tmp_path, "v0.1.0", "diffbot", "r1") is None


def test_find_existing_experiment_matches_by_triple(tmp_path):
    target = tmp_path / "2026-05-02_v0.1.0_diffbot_r1"
    target.mkdir()
    found = find_existing_experiment(tmp_path, "v0.1.0", "diffbot", "r1")
    assert found == target


def test_find_existing_experiment_matches_regardless_of_date(tmp_path):
    """Idempotency key is the triple, not the date — runs across days collide."""
    (tmp_path / "2024-01-01_v0.1.0_diffbot_r1").mkdir()
    found = find_existing_experiment(tmp_path, "v0.1.0", "diffbot", "r1")
    assert found is not None
    assert found.name == "2024-01-01_v0.1.0_diffbot_r1"


def test_find_existing_experiment_does_not_match_run_id_prefix(tmp_path):
    """run_id 'r1' must NOT match an entry ending in 'r10'."""
    (tmp_path / "2026-05-02_v0.1.0_diffbot_r10").mkdir()
    found = find_existing_experiment(tmp_path, "v0.1.0", "diffbot", "r1")
    assert found is None


def test_find_existing_experiment_ignores_files(tmp_path):
    (tmp_path / "2026-05-02_v0.1.0_diffbot_r1").write_text("not a dir")
    assert find_existing_experiment(tmp_path, "v0.1.0", "diffbot", "r1") is None


# ---------------------------------------------------------------------------
# experiment_dir_name
# ---------------------------------------------------------------------------

def test_experiment_dir_name_format():
    name = experiment_dir_name("v0.1.0", "diffbot-experiment-design", "baseline-1")
    parts = name.split("_", 1)
    assert len(parts) == 2
    date, rest = parts
    assert len(date) == 10 and date[4] == "-" and date[7] == "-"
    assert rest == "v0.1.0_diffbot-experiment-design_baseline-1"


# ---------------------------------------------------------------------------
# check_plugin_path
# ---------------------------------------------------------------------------

def test_check_plugin_path_missing(tmp_path):
    msg = check_plugin_path(tmp_path / "does-not-exist")
    assert msg is not None
    assert "does not exist" in msg


def test_check_plugin_path_with_skills_dir(tmp_path):
    (tmp_path / "skills").mkdir()
    assert check_plugin_path(tmp_path) is None


def test_check_plugin_path_with_manifest(tmp_path):
    manifest = tmp_path / ".claude-plugin" / "plugin.json"
    manifest.parent.mkdir()
    manifest.write_text("{}")
    assert check_plugin_path(tmp_path) is None


def test_check_plugin_path_empty_dir_warns(tmp_path):
    msg = check_plugin_path(tmp_path)
    assert msg is not None
    assert "skills" in msg or "plugin.json" in msg


# ---------------------------------------------------------------------------
# render_transcript
# ---------------------------------------------------------------------------

def test_render_transcript_with_json_result_field():
    stdout = json.dumps({"result": "the agent's answer", "session_id": "abc"})
    md = render_transcript(stdout, "")
    assert "## result" in md
    assert "the agent's answer" in md
    assert "Raw JSON output" in md


def test_render_transcript_with_non_json_stdout():
    stdout = "plain text response"
    md = render_transcript(stdout, "")
    assert "Raw stdout" in md
    assert "plain text response" in md


def test_render_transcript_includes_stderr_when_present():
    md = render_transcript("ok", "warning: something")
    assert "stderr" in md
    assert "warning: something" in md


def test_render_transcript_skips_empty_stderr():
    md = render_transcript("ok", "")
    assert "stderr" not in md.lower() or "## stderr" not in md


def test_render_transcript_with_text_field():
    stdout = json.dumps({"text": "alt schema"})
    md = render_transcript(stdout, "")
    assert "## text" in md
    assert "alt schema" in md


# ---------------------------------------------------------------------------
# safe_path_component (used for task worktree paths and plugin ref folders)
# ---------------------------------------------------------------------------

def test_safe_path_component_passes_safe_chars():
    assert safe_path_component("v0.1.0") == "v0.1.0"
    assert safe_path_component("baseline-1") == "baseline-1"
    assert safe_path_component("diffbot_experiment-design.v1") == "diffbot_experiment-design.v1"


def test_safe_path_component_replaces_unsafe_chars():
    assert safe_path_component("foo/bar") == "foo_bar"
    assert safe_path_component("foo bar") == "foo_bar"
    assert safe_path_component("a@b#c") == "a_b_c"


def test_safe_path_component_strips_edges():
    assert safe_path_component("/foo/") == "foo"
    assert safe_path_component("___v0.1.0___") == "v0.1.0"


def test_safe_path_component_full_triple():
    """The full (plugin_tag, task_id, run_id) triple should produce a clean filename."""
    component = safe_path_component("v0.1.0__diffbot-experiment-design__baseline-1")
    assert component == "v0.1.0__diffbot-experiment-design__baseline-1"
    assert "/" not in component
    assert " " not in component


def test_safe_path_component_handles_empty_after_strip():
    assert safe_path_component("///") == "_"


# ---------------------------------------------------------------------------
# resolve_git_sha (canonical reproducibility key per ADR-0001)
# ---------------------------------------------------------------------------

def _init_repo_with_one_commit(repo: Path) -> str:
    """Create a git repo with one commit; returns the commit SHA."""
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "commit.gpgsign", "false"], check=True)
    (repo / "f.txt").write_text("hello")
    subprocess.run(["git", "-C", str(repo), "add", "f.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-q", "-m", "init"],
        check=True, env={"GIT_COMMITTER_DATE": "2026-05-03T00:00:00Z", **__import__("os").environ},
    )
    sha = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return sha


def test_resolve_git_sha_returns_head_for_git_repo(tmp_path):
    sha = _init_repo_with_one_commit(tmp_path)
    assert resolve_git_sha(tmp_path) == sha
    assert len(sha) == 40


def test_resolve_git_sha_returns_none_for_non_git_dir(tmp_path):
    (tmp_path / "f.txt").write_text("not in a repo")
    assert resolve_git_sha(tmp_path) is None


def test_resolve_git_sha_returns_none_for_missing_dir(tmp_path):
    assert resolve_git_sha(tmp_path / "does-not-exist") is None


# ---------------------------------------------------------------------------
# gather_deliverable (T1.4 integration)
# ---------------------------------------------------------------------------

def test_gather_deliverable_includes_only_in_scope_files(tmp_path):
    (tmp_path / "EXPERIMENT.md").write_text("hypothesis: foo\n")
    (tmp_path / "notes.txt").write_text("scratch notes\n")  # out of scope
    deliverable = gather_deliverable(
        tmp_path,
        files_modified=["EXPERIMENT.md", "notes.txt"],
        scope_files=["EXPERIMENT.md"],
    )
    assert "hypothesis: foo" in deliverable
    assert "scratch notes" not in deliverable
    assert "=== EXPERIMENT.md ===" in deliverable


def test_gather_deliverable_marks_empty_when_nothing_in_scope(tmp_path):
    deliverable = gather_deliverable(
        tmp_path,
        files_modified=["src/main.py", "README.md"],
        scope_files=["EXPERIMENT.md"],
    )
    assert "no in-scope files" in deliverable.lower()


def test_gather_deliverable_handles_glob_pattern(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("a body\n")
    (tmp_path / "docs" / "b.md").write_text("b body\n")
    deliverable = gather_deliverable(
        tmp_path,
        files_modified=["docs/a.md", "docs/b.md", "src/x.py"],
        scope_files=["docs/*"],
    )
    assert "a body" in deliverable
    assert "b body" in deliverable
    assert "=== src/x.py ===" not in deliverable


# ---------------------------------------------------------------------------
# compute_scoring (T1.4 integration)
# ---------------------------------------------------------------------------

_BASIC_DIFF = (
    "diff --git a/EXPERIMENT.md b/EXPERIMENT.md\n"
    "new file mode 100644\n"
    "--- /dev/null\n"
    "+++ b/EXPERIMENT.md\n"
    "@@ -0,0 +1,1 @@\n"
    "+hello\n"
)


def test_compute_scoring_runs_scope_check_only_when_no_rubric():
    task = {
        "scope_files": ["EXPERIMENT.md"],
        "verification_method": "automated",
        # No rubric_path — judge should NOT be called.
        "_task_dir": Path("/nonexistent"),
    }
    scoring, judge_calls = compute_scoring(
        task, _BASIC_DIFF, "deliverable", judge_runner=lambda _: 1 / 0
    )
    assert scoring["scope_check"] == {"out_of_scope_file_count": 0, "out_of_scope_paths": []}
    assert "rubric_scores" not in scoring
    assert judge_calls == 0


def test_compute_scoring_invokes_judge_for_rubric_method(tmp_path):
    rubric_path = tmp_path / "rubric.md"
    rubric_path.write_text("rubric body")
    task = {
        "scope_files": ["EXPERIMENT.md"],
        "verification_method": "rubric",
        "rubric_path": "rubric.md",
        "_task_dir": tmp_path,
    }
    fake_judge = lambda _: {"scores": {"hypothesis": 2}, "overall": 2.0, "rationale": "ok"}
    scoring, judge_calls = compute_scoring(
        task, _BASIC_DIFF, "deliverable", n_trials=3, judge_runner=fake_judge
    )

    assert scoring["scope_check"]["out_of_scope_file_count"] == 0
    assert scoring["rubric_scores"]["mean"] == {"hypothesis": 2.0}
    assert scoring["rubric_scores"]["overall_mean"] == 2.0
    assert scoring["rubric_scores"]["n_trials"] == 3
    assert judge_calls == 3


def test_compute_scoring_records_judge_failure_without_raising(tmp_path):
    rubric_path = tmp_path / "rubric.md"
    rubric_path.write_text("rubric body")
    task = {
        "scope_files": ["EXPERIMENT.md"],
        "verification_method": "rubric",
        "rubric_path": "rubric.md",
        "_task_dir": tmp_path,
    }

    def broken_judge(_prompt: str) -> dict:
        from harness.score_rubric import JudgeInvocationError as _E
        raise _E("simulated judge failure")

    scoring, judge_calls = compute_scoring(
        task, _BASIC_DIFF, "deliverable", n_trials=1, judge_runner=broken_judge
    )
    # scope-check still ran — losing the judge shouldn't lose the rest.
    assert scoring["scope_check"] == {"out_of_scope_file_count": 0, "out_of_scope_paths": []}
    assert "error" in scoring["rubric_scores"]
    assert "simulated judge failure" in scoring["rubric_scores"]["error"]["message"]
    # Failed before any trial completed → judge_calls reports 0.
    assert judge_calls == 0


def test_compute_scoring_records_missing_rubric_file(tmp_path):
    task = {
        "scope_files": ["EXPERIMENT.md"],
        "verification_method": "rubric",
        "rubric_path": "missing.md",
        "_task_dir": tmp_path,
    }
    scoring, judge_calls = compute_scoring(task, _BASIC_DIFF, "deliverable")
    assert "error" in scoring["rubric_scores"]
    assert scoring["rubric_scores"]["error"]["type"] == "FileNotFoundError"
    assert judge_calls == 0
