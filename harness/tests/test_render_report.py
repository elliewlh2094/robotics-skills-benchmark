"""Tests for harness/render_report.py.

Per the TDD skill's DAMP-over-DRY guidance, fixtures are built in-line with
small helpers rather than a shared base. The load-bearing test is
test_round_trip_integrity: it asserts that the renderer's restored
deliverable is byte-identical to the original EXPERIMENT.md, which is the
only correctness guarantee that catches drift in patch-stripping logic.
"""
from __future__ import annotations

import json
import re
import textwrap
from pathlib import Path

import pytest

from harness.render_report import (
    BEGIN_MARKER,
    END_MARKER,
    REPORT_FILENAME,
    compose_report,
    extract_result_section,
    parse_diff,
    render_auto_block,
    render_report,
    render_instrument_health,
    render_task_definition,
)
from harness.validate_result import ResultValidationError


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------

_SHA = "0" * 40
_SHA2 = "a" * 40


def _make_diff_for_new_file(path: str, content: str) -> str:
    """Build a unified-diff that represents creating `path` with `content`.

    Mirrors what `git diff --no-index /dev/null <file>` produces for a
    brand-new file. Each content line gets a leading `+`. If the content
    does not end with a newline, the `\\ No newline at end of file` marker
    is appended so the renderer round-trips correctly.
    """
    body_lines = content.split("\n")
    has_trailing_newline = content.endswith("\n")
    if has_trailing_newline:
        body_lines = body_lines[:-1]
    line_count = len(body_lines)
    plus_lines = "\n".join(f"+{line}" for line in body_lines)
    trailer = "" if has_trailing_newline else "\n\\ No newline at end of file"
    return (
        f"diff --git a/{path} b/{path}\n"
        f"new file mode 100644\n"
        f"index 0000000..abcdef0\n"
        f"--- /dev/null\n"
        f"+++ b/{path}\n"
        f"@@ -0,0 +1,{line_count} @@\n"
        f"{plus_lines}{trailer}\n"
    )


def _minimal_success_result(experiment_id: str, files_modified: list[str]) -> dict:
    """A schema-valid status='success' result for fixtures."""
    return {
        "schema_version": 1,
        "experiment_id": experiment_id,
        "plugin_tag": "v0.1.0",
        "plugin_path": "/tmp/fake-plugin",
        "plugin_repo": None,
        "plugin_ref": None,
        "plugin_sha": _SHA,
        "task_id": "diffbot-experiment-design",
        "run_id": "test-1",
        "base_repo": "https://github.com/example/repo",
        "base_sha": _SHA2,
        "scope_files_declared": files_modified or ["EXPERIMENT.md"],
        "available_tools": ["Read", "Write"],
        "max_turns": 50,
        "seed": None,
        "status": "success",
        "started_at": "2026-05-04T12:00:00Z",
        "completed_at": "2026-05-04T12:30:00Z",
        "runtime_s": 1800.0,
        "exit_code": 0,
        "error": None,
        "files_modified": files_modified,
        "transcript_bytes": 100,
        "judge_calls": 3,
        "hook_blocks": 0,
        "scoring": {
            "scope_check": {
                "out_of_scope_file_count": 0,
                "out_of_scope_paths": [],
            },
            "rubric_scores": {
                "n_trials": 3,
                "per_trial": [
                    {
                        "scores": {"hypothesis": 2, "signals": 3},
                        "overall_recomputed": 2.5,
                        "overall_judge_reported": 2.5,
                        "rationale": f"trial {i}: solid plan",
                    }
                    for i in (1, 2, 3)
                ],
                "mean": {"hypothesis": 2.0, "signals": 3.0},
                "stdev": {"hypothesis": 0.0, "signals": 0.0},
                "overall_mean": 2.5,
                "overall_stdev": 0.0,
            },
        },
    }


def _make_experiment(
    tmp_path: Path,
    *,
    deliverable_name: str = "EXPERIMENT.md",
    deliverable_content: str = "# Plan\n\nSection one.\n",
    transcript_md: str | None = None,
    diff_text: str | None = None,
    result_overrides: dict | None = None,
) -> Path:
    """Build a complete fixture experiment directory under tmp_path."""
    experiment_id = "2026-05-04_v0.1.0_diffbot-experiment-design_test-1"
    exp_dir = tmp_path / experiment_id
    exp_dir.mkdir()

    files_modified = [deliverable_name] if deliverable_content is not None else []
    result = _minimal_success_result(experiment_id, files_modified)
    if result_overrides:
        # Deep merge for top-level keys; replace nested keys explicitly when needed
        for k, v in result_overrides.items():
            result[k] = v

    (exp_dir / "result.json").write_text(json.dumps(result, indent=2))

    if transcript_md is None:
        transcript_md = (
            "# Agent transcript\n\n## result\n\nThe agent did the thing.\n\n"
            "## Raw JSON output\n\n```json\n{}\n```\n"
        )
    (exp_dir / "transcript.md").write_text(transcript_md)

    if diff_text is None:
        diff_text = _make_diff_for_new_file(deliverable_name, deliverable_content)
    (exp_dir / "diff.patch").write_text(diff_text)

    return exp_dir


# ---------------------------------------------------------------------------
# Diff parsing unit tests
# ---------------------------------------------------------------------------

def test_parse_diff_new_file_round_trip():
    original = "line one\nline two\nline three\n"
    diff = _make_diff_for_new_file("FILE.md", original)
    files = parse_diff(diff)
    assert len(files) == 1
    assert files[0].path == "FILE.md"
    assert files[0].kind == "new"
    assert files[0].content == original


def test_parse_diff_new_file_no_trailing_newline():
    original = "line one\nline two"  # no trailing \n
    diff = _make_diff_for_new_file("FILE.md", original)
    files = parse_diff(diff)
    assert files[0].content == original


def test_parse_diff_modified_file():
    diff = textwrap.dedent("""\
        diff --git a/foo.py b/foo.py
        index 1234567..89abcde 100644
        --- a/foo.py
        +++ b/foo.py
        @@ -1,3 +1,3 @@
         keep
        -old
        +new
         keep
    """)
    files = parse_diff(diff)
    assert len(files) == 1
    assert files[0].kind == "modified"
    assert files[0].path == "foo.py"


def test_parse_diff_binary_file():
    diff = (
        "diff --git a/img.png b/img.png\n"
        "new file mode 100644\n"
        "index 0000000..1234567\n"
        "Binary files /dev/null and b/img.png differ\n"
    )
    files = parse_diff(diff)
    assert files[0].kind == "binary"
    assert files[0].path == "img.png"


def test_parse_diff_multi_file():
    diff = (
        _make_diff_for_new_file("A.md", "alpha\n")
        + _make_diff_for_new_file("B.md", "beta\n")
    )
    files = parse_diff(diff)
    assert [f.path for f in files] == ["A.md", "B.md"]
    assert all(f.kind == "new" for f in files)


def test_parse_diff_empty():
    assert parse_diff("") == []
    assert parse_diff("\n  \n") == []


# ---------------------------------------------------------------------------
# Transcript prose extraction unit tests
# ---------------------------------------------------------------------------

def test_extract_result_section_present():
    transcript = (
        "# Agent transcript\n\n## result\n\nbody one\nbody two\n\n"
        "## Raw JSON output\n\n```json\n{}\n```\n"
    )
    assert extract_result_section(transcript) == "body one\nbody two"


def test_extract_result_section_missing():
    transcript = "# Agent transcript\n\n## Raw JSON output\n\n```json\n{}\n```\n"
    assert extract_result_section(transcript) is None


# ---------------------------------------------------------------------------
# End-to-end: round-trip integrity (LOAD-BEARING)
# ---------------------------------------------------------------------------

def test_round_trip_integrity(tmp_path):
    """The restored deliverable must byte-match the original.

    Drift in patch-stripping logic shows up here as a byte mismatch. This
    is the strongest correctness signal in the suite.
    """
    original = (
        "# EXPERIMENT: Test\n\n"
        "## Section\n\n"
        "Some text with `+inline` markers and a fenced block:\n\n"
        "```python\n"
        "x = 1\n"
        "```\n\n"
        "End.\n"
    )
    exp_dir = _make_experiment(tmp_path, deliverable_content=original)

    report = render_report(exp_dir)

    # The restored deliverable is fenced with auto-detected backtick length.
    # Pull out the content between the deliverable subsection's opening and
    # closing fences.
    section = re.search(
        r"### `EXPERIMENT\.md`\n\n(`{3,})markdown\n(.*?)\n\1",
        report,
        re.DOTALL,
    )
    assert section is not None, f"could not locate restored deliverable in:\n{report}"
    restored = section.group(2) + "\n"
    assert restored == original


def test_round_trip_integrity_no_trailing_newline(tmp_path):
    """A deliverable without a trailing newline should also round-trip."""
    original = "line one\nline two"  # no \n
    exp_dir = _make_experiment(tmp_path, deliverable_content=original)

    report = render_report(exp_dir)

    section = re.search(
        r"### `EXPERIMENT\.md`\n\n(`{3,})markdown\n(.*?)\n\1",
        report,
        re.DOTALL,
    )
    assert section is not None
    # The renderer always adds a \n before the closing fence even when the
    # content has none, but the captured group (.*?) excludes that trailing
    # \n. So the captured text equals the original byte-for-byte.
    assert section.group(2) == original


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_render_no_deliverable(tmp_path):
    exp_dir = _make_experiment(
        tmp_path,
        deliverable_content="",
        result_overrides={
            "status": "no-deliverable",
            "files_modified": [],
            "judge_calls": 0,
            "scoring": {
                "scope_check": {
                    "out_of_scope_file_count": 0,
                    "out_of_scope_paths": [],
                },
            },
        },
        diff_text="",
    )
    report = render_report(exp_dir)
    assert "No in-scope files were produced" in report
    assert "no-deliverable" in report


def test_render_missing_result_section(tmp_path):
    exp_dir = _make_experiment(
        tmp_path,
        transcript_md="# Agent transcript\n\nno H2 sections here\n",
    )
    report = render_report(exp_dir)
    assert "could not locate `## result`" in report


def test_render_missing_transcript(tmp_path):
    exp_dir = _make_experiment(tmp_path)
    (exp_dir / "transcript.md").unlink()
    report = render_report(exp_dir)
    assert "Source file not found at `transcript.md`" in report


def test_render_missing_diff(tmp_path):
    exp_dir = _make_experiment(tmp_path)
    (exp_dir / "diff.patch").unlink()
    report = render_report(exp_dir)
    assert "Source file not found at `diff.patch`" in report


def test_render_modified_file_emits_warning(tmp_path):
    diff = textwrap.dedent("""\
        diff --git a/EXPERIMENT.md b/EXPERIMENT.md
        index 1234567..89abcde 100644
        --- a/EXPERIMENT.md
        +++ b/EXPERIMENT.md
        @@ -1,2 +1,2 @@
         keep
        -old
        +new
    """)
    exp_dir = _make_experiment(tmp_path, diff_text=diff)
    report = render_report(exp_dir)
    assert "modified, not newly created" in report


def test_render_invalid_result_json_raises(tmp_path):
    exp_dir = _make_experiment(tmp_path)
    bad = json.loads((exp_dir / "result.json").read_text())
    bad["plugin_sha"] = "not-a-sha"  # violates pattern
    (exp_dir / "result.json").write_text(json.dumps(bad))
    with pytest.raises(ResultValidationError):
        render_report(exp_dir)


def test_render_rubric_table_includes_all_dimensions(tmp_path):
    exp_dir = _make_experiment(tmp_path)
    report = render_report(exp_dir)
    # Header row + separator + one row per dimension
    assert "| dimension | mean | stdev | trial_1 | trial_2 | trial_3 |" in report
    assert "| hypothesis |" in report
    assert "| signals |" in report


def test_render_rationales_section_includes_all_trials(tmp_path):
    exp_dir = _make_experiment(tmp_path)
    report = render_report(exp_dir)
    for i in (1, 2, 3):
        assert f"### Trial {i}" in report
        assert f"trial {i}: solid plan" in report


# ---------------------------------------------------------------------------
# T1.6a: task-definition section
# ---------------------------------------------------------------------------

def _seed_fake_task_yaml(tasks_dir: Path, task_id: str, body: str) -> None:
    """Write a fake task.yaml under tasks_dir so the renderer can find it."""
    task_dir = tasks_dir / task_id
    task_dir.mkdir(parents=True)
    (task_dir / "task.yaml").write_text(body)


def test_task_definition_renders_all_fields(tmp_path):
    tasks_dir = tmp_path / "tasks_root"
    _seed_fake_task_yaml(
        tasks_dir,
        "diffbot-experiment-design",
        textwrap.dedent("""\
            task_id: diffbot-experiment-design
            problem_statement: |
              Hypothetical objective.
              Multi-line statement.
            scope_files:
              - "EXPERIMENT.md"
            available_tools:
              - Read
              - Write
            verification_method: rubric
        """),
    )
    exp_dir = _make_experiment(tmp_path)
    text = render_report(exp_dir, tasks_dir=tasks_dir)
    assert "## Task definition" in text
    assert "Hypothetical objective." in text
    assert "Multi-line statement." in text
    assert "**scope_files:** `EXPERIMENT.md`" in text
    assert "**available_tools:** `Read`, `Write`" in text
    assert "**verification_method:** `rubric`" in text


def test_task_definition_missing_emits_warning(tmp_path):
    """If task.yaml is absent, the section emits a `>` warning, not a crash."""
    tasks_dir = tmp_path / "empty_tasks_root"
    tasks_dir.mkdir()
    exp_dir = _make_experiment(tmp_path)
    text = render_report(exp_dir, tasks_dir=tasks_dir)
    assert "## Task definition" in text
    assert "Task definition not found at" in text
    # Other sections still rendered.
    assert "## Run identity" in text
    assert "## Restored deliverable" in text


def test_task_definition_yaml_parse_error(tmp_path):
    tasks_dir = tmp_path / "tasks_root"
    _seed_fake_task_yaml(
        tasks_dir,
        "diffbot-experiment-design",
        ":\n  invalid: yaml: : :\n",  # malformed
    )
    exp_dir = _make_experiment(tmp_path)
    text = render_report(exp_dir, tasks_dir=tasks_dir)
    assert "Failed to parse" in text


# ---------------------------------------------------------------------------
# T1.6a: measurement-instrument-health section
# ---------------------------------------------------------------------------

def _saturated_scoring(dims: list[str], n_trials: int = 3) -> dict:
    """Build a `scoring` dict where every dimension is 3.0 with zero stdev."""
    return {
        "scope_check": {
            "out_of_scope_file_count": 0,
            "out_of_scope_paths": [],
        },
        "rubric_scores": {
            "n_trials": n_trials,
            "per_trial": [
                {
                    "scores": {d: 3 for d in dims},
                    "overall_recomputed": 3.0,
                    "overall_judge_reported": 3.0,
                    "rationale": f"trial {i}: looks great",
                }
                for i in range(1, n_trials + 1)
            ],
            "mean": {d: 3.0 for d in dims},
            "stdev": {d: 0.0 for d in dims},
            "overall_mean": 3.0,
            "overall_stdev": 0.0,
        },
    }


def test_instrument_health_warns_on_saturation():
    scoring = _saturated_scoring(["hypothesis", "signals", "thresholds"])
    out = render_instrument_health(scoring)
    assert "## Measurement instrument health" in out
    assert "Measurement-instrument warning" in out
    assert "saturated" in out


def test_instrument_health_healthy_when_below_ceiling():
    """Default fixture has hypothesis mean=2.0; expect the 'meaningful' line."""
    scoring = {
        "rubric_scores": {
            "mean": {"hypothesis": 2.0, "signals": 3.0},
            "stdev": {"hypothesis": 0.0, "signals": 0.0},
        }
    }
    out = render_instrument_health(scoring)
    assert "Measurement instrument health" in out
    assert "meaningful" in out
    assert "warning" not in out.lower()


def test_instrument_health_silent_when_no_rubric_data():
    """No rubric_scores → return empty string (section absent from report)."""
    assert render_instrument_health({}) == ""
    assert render_instrument_health({"rubric_scores": {}}) == ""


def test_instrument_health_warning_appears_when_fixture_overridden_to_saturate(tmp_path):
    exp_dir = _make_experiment(
        tmp_path,
        result_overrides={
            "scoring": _saturated_scoring(["hypothesis", "signals"]),
        },
    )
    text = render_report(exp_dir)
    assert "Measurement-instrument warning" in text


def test_instrument_health_section_absent_in_no_deliverable_report(tmp_path):
    """no-deliverable runs skip the judge → no rubric_scores → section absent."""
    exp_dir = _make_experiment(
        tmp_path,
        deliverable_content="",
        result_overrides={
            "status": "no-deliverable",
            "files_modified": [],
            "judge_calls": 0,
            "scoring": {
                "scope_check": {
                    "out_of_scope_file_count": 0,
                    "out_of_scope_paths": [],
                },
            },
        },
        diff_text="",
    )
    text = render_report(exp_dir)
    assert "## Measurement instrument health" not in text


# ---------------------------------------------------------------------------
# Marker preservation
# ---------------------------------------------------------------------------

def test_marker_preservation_on_rerender(tmp_path):
    """User edits to the Manual review section survive re-rendering."""
    exp_dir = _make_experiment(tmp_path)
    # First render writes the file.
    report_path = exp_dir / REPORT_FILENAME
    report_path.write_text(render_report(exp_dir))

    # User adds a note.
    text = report_path.read_text()
    user_note = "USER_NOTE_UNIQUE_TOKEN: anchors look too easy on dim X"
    text = text.replace(
        "## Manual review",
        f"## Manual review\n\n{user_note}",
    )
    report_path.write_text(text)

    # Re-render.
    report_path.write_text(render_report(exp_dir))

    final = report_path.read_text()
    assert user_note in final
    assert BEGIN_MARKER in final
    assert END_MARKER in final


def test_force_clobbers_manual_review(tmp_path):
    exp_dir = _make_experiment(tmp_path)
    report_path = exp_dir / REPORT_FILENAME
    report_path.write_text(render_report(exp_dir))

    text = report_path.read_text()
    user_note = "USER_NOTE_UNIQUE_TOKEN_2"
    text += f"\n\n{user_note}\n"
    report_path.write_text(text)

    report_path.write_text(render_report(exp_dir, force=True))
    final = report_path.read_text()
    assert user_note not in final


def test_compose_report_missing_markers_raises():
    auto = "auto content"
    legacy = "# Old report without any markers\n\nsome content\n"
    with pytest.raises(RuntimeError, match="missing BEGIN/END AUTO markers"):
        compose_report(auto, "exp-id", legacy, force=False)


def test_compose_report_force_bypasses_marker_check():
    auto = "auto content"
    legacy = "# Old report without any markers\n"
    out = compose_report(auto, "exp-id", legacy, force=True)
    assert BEGIN_MARKER in out
    assert "auto content" in out


def test_compose_report_idempotent_without_user_edits(tmp_path):
    """Two consecutive renders with no manual edits produce the same bytes."""
    exp_dir = _make_experiment(tmp_path)
    first = render_report(exp_dir)
    (exp_dir / REPORT_FILENAME).write_text(first)
    second = render_report(exp_dir)
    assert first == second


# ---------------------------------------------------------------------------
# Smoke test against the real baselines
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE_DIRS = sorted(
    (REPO_ROOT / "experiments").glob(
        "2026-05-04_v0.1.0_diffbot-experiment-design_baseline-*"
    )
)


@pytest.mark.parametrize(
    "exp_dir", BASELINE_DIRS, ids=[d.name for d in BASELINE_DIRS]
)
def test_real_baseline_renders_without_error(exp_dir):
    """Sanity: each on-disk baseline renders cleanly and contains expected anchors.

    The three v0.1.0 baselines are saturated, so the instrument-health
    warning is expected to fire here. (Per the calibration-gate plan, the
    on-disk reports themselves are frozen as historical artifacts; this
    test only exercises the renderer in-memory.)
    """
    text = render_auto_block(exp_dir)
    assert "## Run identity" in text
    assert "## Task definition" in text
    assert "## Agent transcript" in text
    assert "## Restored deliverable" in text
    assert "## Rubric scores" in text
    assert "## Measurement instrument health" in text
    assert "Measurement-instrument warning" in text
    assert "## Judge rationales" in text
    assert "EXPERIMENT.md" in text
