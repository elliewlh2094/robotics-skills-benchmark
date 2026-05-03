"""Unit tests for harness.validate_result.

Covers the canonical schema at harness/schemas/result.schema.yaml. The fixture
factories build minimal-but-valid result dicts; each negative test mutates one
field so the failure message points at exactly the rule under test.
"""
from __future__ import annotations

import copy

import pytest
from jsonschema import ValidationError

from harness.validate_result import iter_errors, validate


# ---------------------------------------------------------------------------
# Fixture factories
# ---------------------------------------------------------------------------

def _identification() -> dict:
    """Fields required regardless of status."""
    return {
        "schema_version": 1,
        "experiment_id": "2026-05-03_v0.1.0_diffbot-experiment-design_baseline-1",
        "plugin_tag": "v0.1.0",
        "plugin_path": "/home/u/.cache/robotics-skills-benchmark/plugins/foo__bar/_worktrees/v0.1.0",
        "plugin_repo": "https://github.com/foo/bar",
        "plugin_ref": "v0.1.0",
        "plugin_sha": "0123456789abcdef0123456789abcdef01234567",
        "task_id": "diffbot-experiment-design",
        "run_id": "baseline-1",
        "base_repo": "https://github.com/ros-controls/ros2_control_demos",
        "base_sha": "c555233658e8c0794f9bb6e1ea4059ca84bcd503",
        "scope_files_declared": ["EXPERIMENT.md"],
        "available_tools": ["Read", "Glob", "Grep", "Write", "Edit"],
        "max_turns": 50,
        "seed": None,
        "started_at": "2026-05-03T12:00:00Z",
    }


def _partial() -> dict:
    """status=incomplete: the partial-result preamble. Loose constraints."""
    base = _identification()
    base.update({
        "completed_at": None,
        "runtime_s": None,
        "exit_code": None,
        "status": "incomplete",
        "error": None,
        "files_modified": [],
        "transcript_bytes": 0,
        "scoring": {},
    })
    return base


def _success() -> dict:
    """status=success: agent ran cleanly."""
    base = _identification()
    base.update({
        "completed_at": "2026-05-03T12:30:00Z",
        "runtime_s": 1800.5,
        "exit_code": 0,
        "status": "success",
        "error": None,
        "files_modified": ["EXPERIMENT.md"],
        "transcript_bytes": 12345,
        "scoring": {
            "scope_check": {"out_of_scope_count": 0, "out_of_scope_paths": []},
            "rubric": {
                "n_trials": 3,
                "per_trial": [
                    {
                        "scores": {"hypothesis": 2, "signals": 3},
                        "overall_recomputed": 2.5,
                        "overall_judge_reported": 2.5,
                        "rationale": "specific feedback",
                    },
                    {
                        "scores": {"hypothesis": 2, "signals": 2},
                        "overall_recomputed": 2.0,
                        "overall_judge_reported": 2.0,
                        "rationale": "another rationale",
                    },
                    {
                        "scores": {"hypothesis": 3, "signals": 3},
                        "overall_recomputed": 3.0,
                        "overall_judge_reported": 3.0,
                        "rationale": "a third rationale",
                    },
                ],
                "mean": {"hypothesis": 2.33, "signals": 2.67},
                "stdev": {"hypothesis": 0.58, "signals": 0.58},
                "overall_mean": 2.5,
                "overall_stdev": 0.5,
            },
        },
    })
    return base


def _error() -> dict:
    base = _identification()
    base.update({
        "completed_at": "2026-05-03T12:05:00Z",
        "runtime_s": 300.0,
        "exit_code": 1,
        "status": "error",
        "error": {"type": "non-zero-exit", "message": "claude exited with code 1"},
        "files_modified": [],
        "transcript_bytes": 200,
        "scoring": {"scope_check": {"out_of_scope_count": 0, "out_of_scope_paths": []}},
        "scratch_dir": "/tmp/exp-scratch/v0.1.0__diffbot__baseline-1",
    })
    return base


def _timeout() -> dict:
    base = _error()
    base["status"] = "timeout"
    base["error"] = {"type": "timeout", "message": "exceeded timeout_s=1800"}
    base["exit_code"] = -1
    return base


# ---------------------------------------------------------------------------
# Happy paths — every status produces a valid result
# ---------------------------------------------------------------------------

def test_partial_is_valid():
    validate(_partial())


def test_success_is_valid():
    validate(_success())


def test_error_is_valid():
    validate(_error())


def test_timeout_is_valid():
    validate(_timeout())


def test_success_without_rubric_is_valid():
    """Tasks with verification_method=automated produce no rubric subtree."""
    r = _success()
    del r["scoring"]["rubric"]
    validate(r)


def test_error_with_rubric_failure_subtree_is_valid():
    """When the judge subprocess fails, scoring.rubric records the error."""
    r = _success()
    r["scoring"]["rubric"] = {
        "error": {"type": "JudgeInvocationError", "message": "claude judge timed out"}
    }
    validate(r)


def test_plugin_path_mode_with_null_repo_and_ref_is_valid():
    """When sourced via --plugin-path, plugin_repo and plugin_ref are null."""
    r = _success()
    r["plugin_repo"] = None
    r["plugin_ref"] = None
    validate(r)


def test_plugin_sha_null_is_valid_when_path_not_a_git_worktree():
    r = _success()
    r["plugin_sha"] = None
    validate(r)


# ---------------------------------------------------------------------------
# Negative cases — required fields
# ---------------------------------------------------------------------------

def test_missing_schema_version_rejected():
    r = _success()
    del r["schema_version"]
    with pytest.raises(ValidationError, match="schema_version"):
        validate(r)


def test_missing_scoring_rejected():
    r = _success()
    del r["scoring"]
    with pytest.raises(ValidationError, match="scoring"):
        validate(r)


def test_missing_status_rejected():
    r = _success()
    del r["status"]
    with pytest.raises(ValidationError, match="status"):
        validate(r)


def test_unknown_top_level_field_rejected():
    """additionalProperties: false at the top level catches typos and stale fields."""
    r = _success()
    r["skils_invoked"] = []  # typo of skills_invoked, also a "planned" field
    with pytest.raises(ValidationError):
        validate(r)


# ---------------------------------------------------------------------------
# Negative cases — type / shape constraints
# ---------------------------------------------------------------------------

def test_schema_version_must_be_one():
    r = _success()
    r["schema_version"] = 2
    with pytest.raises(ValidationError):
        validate(r)


def test_invalid_status_enum_rejected():
    r = _success()
    r["status"] = "almost-done"
    with pytest.raises(ValidationError, match="status"):
        validate(r)


def test_malformed_plugin_sha_rejected():
    r = _success()
    r["plugin_sha"] = "not-a-sha"
    with pytest.raises(ValidationError):
        validate(r)


def test_malformed_base_sha_rejected():
    r = _success()
    r["base_sha"] = "abc123"  # too short
    with pytest.raises(ValidationError):
        validate(r)


def test_negative_transcript_bytes_rejected():
    r = _success()
    r["transcript_bytes"] = -1
    with pytest.raises(ValidationError):
        validate(r)


# ---------------------------------------------------------------------------
# Negative cases — status-conditional rules
# ---------------------------------------------------------------------------

def test_success_with_non_null_error_rejected():
    """status=success implies error MUST be null."""
    r = _success()
    r["error"] = {"type": "anything", "message": "should not be here"}
    with pytest.raises(ValidationError):
        validate(r)


def test_success_with_null_runtime_rejected():
    """status=success implies runtime_s MUST be non-null."""
    r = _success()
    r["runtime_s"] = None
    with pytest.raises(ValidationError):
        validate(r)


def test_success_with_null_exit_code_rejected():
    r = _success()
    r["exit_code"] = None
    with pytest.raises(ValidationError):
        validate(r)


def test_error_with_null_error_object_rejected():
    """status=error implies error MUST be a populated object."""
    r = _error()
    r["error"] = None
    with pytest.raises(ValidationError):
        validate(r)


def test_error_object_missing_type_rejected():
    r = _error()
    r["error"] = {"message": "no type"}
    with pytest.raises(ValidationError):
        validate(r)


# ---------------------------------------------------------------------------
# Negative cases — scoring sub-schema
# ---------------------------------------------------------------------------

def test_scope_check_with_negative_count_rejected():
    r = _success()
    r["scoring"]["scope_check"]["out_of_scope_count"] = -1
    with pytest.raises(ValidationError):
        validate(r)


def test_scope_check_missing_paths_rejected():
    r = _success()
    del r["scoring"]["scope_check"]["out_of_scope_paths"]
    with pytest.raises(ValidationError):
        validate(r)


def test_rubric_with_neither_success_nor_failure_shape_rejected():
    r = _success()
    r["scoring"]["rubric"] = {"some_other_shape": True}
    with pytest.raises(ValidationError):
        validate(r)


def test_rubric_per_trial_missing_rationale_rejected():
    r = _success()
    r["scoring"]["rubric"]["per_trial"][0].pop("rationale")
    with pytest.raises(ValidationError):
        validate(r)


def test_rubric_negative_stdev_rejected():
    """Stdev cannot be negative — sample stdev is non-negative by construction."""
    r = _success()
    r["scoring"]["rubric"]["overall_stdev"] = -0.1
    with pytest.raises(ValidationError):
        validate(r)


# ---------------------------------------------------------------------------
# iter_errors — for the validate-on-write hook's forensic message
# ---------------------------------------------------------------------------

def test_iter_errors_returns_empty_for_valid():
    assert iter_errors(_success()) == []


def test_iter_errors_returns_messages_for_invalid():
    r = _success()
    r["status"] = "almost-done"
    msgs = iter_errors(r)
    assert msgs
    assert any("status" in m for m in msgs)
