"""Schema tests for harness/schemas/result.schema.yaml.

Each test builds a result dict in-memory and runs it through validate_result().
Positive tests expect no error; negative tests assert that a specific kind of
malformed result is rejected. Tests use copy-and-mutate patterns over
helpers (DAMP over DRY in tests — see TDD skill).
"""
from __future__ import annotations

import copy

import pytest

from harness.validate_result import ResultValidationError, validate_result


# ---------------------------------------------------------------------------
# Reusable building blocks
# ---------------------------------------------------------------------------

# A 40-char hex sha for the SHA-shaped fields.
_SHA = "0" * 40
_SHA2 = "a" * 40


def _base_partial(**overrides) -> dict:
    """Minimal valid status='incomplete' partial-write."""
    base = {
        "schema_version": 1,
        "experiment_id": "2026-05-03_v0.1.0_diffbot-experiment-design_baseline-1",
        "plugin_tag": "v0.1.0",
        "plugin_path": "/home/u/.cache/plugins/foo/bar",
        "plugin_repo": None,
        "plugin_ref": None,
        "plugin_sha": _SHA,
        "task_id": "diffbot-experiment-design",
        "run_id": "baseline-1",
        "base_repo": "https://github.com/ros-controls/ros2_control_demos",
        "base_sha": _SHA2,
        "scope_files_declared": ["EXPERIMENT.md"],
        "available_tools": ["Read", "Glob", "Grep", "Write", "Edit"],
        "max_turns": 50,
        "seed": None,
        "status": "incomplete",
        "started_at": "2026-05-03T12:00:00Z",
        "completed_at": None,
        "runtime_s": None,
        "exit_code": None,
        "error": None,
        "files_modified": [],
        "transcript_bytes": 0,
        "scoring": {},
        "hook_blocks": 0,
        "judge_calls": 0,
        "scratch_dir": "/tmp/exp-scratch/v0.1.0__diffbot-experiment-design__baseline-1",
    }
    base.update(overrides)
    return base


def _base_success(**overrides) -> dict:
    """Minimal valid status='success' final result. No scratch_dir."""
    partial = _base_partial()
    partial.pop("scratch_dir")
    partial.update({
        "status": "success",
        "completed_at": "2026-05-03T12:30:00Z",
        "runtime_s": 1800.0,
        "exit_code": 0,
        "files_modified": ["EXPERIMENT.md"],
        "transcript_bytes": 4321,
        "judge_calls": 3,
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
                        "rationale": "decent plan",
                    },
                    {
                        "scores": {"hypothesis": 2, "signals": 3},
                        "overall_recomputed": 2.5,
                        "overall_judge_reported": 2.5,
                        "rationale": "decent plan",
                    },
                    {
                        "scores": {"hypothesis": 2, "signals": 3},
                        "overall_recomputed": 2.5,
                        "overall_judge_reported": 2.5,
                        "rationale": "decent plan",
                    },
                ],
                "mean": {"hypothesis": 2.0, "signals": 3.0},
                "stdev": {"hypothesis": 0.0, "signals": 0.0},
                "overall_mean": 2.5,
                "overall_stdev": 0.0,
            },
        },
    })
    partial.update(overrides)
    return partial


# ---------------------------------------------------------------------------
# Positive cases — all four lifecycle states
# ---------------------------------------------------------------------------

def test_partial_incomplete_validates():
    validate_result(_base_partial())


def test_full_success_validates():
    validate_result(_base_success())


def test_agent_error_validates():
    err = _base_partial()
    err.update({
        "status": "error",
        "completed_at": "2026-05-03T12:05:00Z",
        "runtime_s": 300.0,
        "exit_code": 1,
        "error": {"type": "non-zero-exit", "message": "claude exited with code 1"},
        "scoring": {
            "scope_check": {"out_of_scope_file_count": 0, "out_of_scope_paths": []},
        },
    })
    # scratch_dir already in _base_partial — required for status=error
    validate_result(err)


def test_timeout_validates():
    t = _base_partial()
    t.update({
        "status": "timeout",
        "completed_at": "2026-05-03T12:30:00Z",
        "runtime_s": 1800.0,
        "exit_code": -1,
        "error": {"type": "timeout", "message": "exceeded timeout_s=1800"},
        "scoring": {"scope_check": {"out_of_scope_file_count": 0, "out_of_scope_paths": []}},
    })
    validate_result(t)


def test_no_deliverable_validates():
    """status='no-deliverable': agent ran cleanly but produced nothing in scope.

    Same shape as 'success' (error null, scratch_dir absent, completed_at set,
    exit_code 0) but rubric_scores is absent — the judge was skipped because
    there was nothing to evaluate. judge_calls is 0.
    """
    nd = _base_partial()
    nd.pop("scratch_dir")
    nd.update({
        "status": "no-deliverable",
        "completed_at": "2026-05-03T12:05:00Z",
        "runtime_s": 263.1,
        "exit_code": 0,
        "files_modified": [],
        "transcript_bytes": 4321,
        "judge_calls": 0,
        "scoring": {
            "scope_check": {"out_of_scope_file_count": 0, "out_of_scope_paths": []},
        },
    })
    validate_result(nd)


# ---------------------------------------------------------------------------
# Plugin sourcing oneOf — refinement B (distinguish by VALUE not key presence)
# ---------------------------------------------------------------------------

def test_local_plugin_mode_validates():
    """plugin_repo and plugin_ref are both null → local mode."""
    r = _base_partial(plugin_repo=None, plugin_ref=None)
    validate_result(r)


def test_url_ref_plugin_mode_validates():
    """plugin_repo and plugin_ref both non-null → URL+ref mode."""
    r = _base_partial(
        plugin_repo="https://github.com/elliewlh2094/robotics-agent-skills",
        plugin_ref="v0.1.0",
    )
    validate_result(r)


def test_mixed_mode_one_null_one_string_rejected():
    """plugin_repo null but plugin_ref string is neither mode — must fail."""
    r = _base_partial(plugin_repo=None, plugin_ref="v0.1.0")
    with pytest.raises(ResultValidationError):
        validate_result(r)


def test_other_mixed_mode_rejected():
    """plugin_repo string but plugin_ref null is also not a valid mode."""
    r = _base_partial(plugin_repo="https://x/y", plugin_ref=None)
    with pytest.raises(ResultValidationError):
        validate_result(r)


# ---------------------------------------------------------------------------
# scratch_dir invariants — refinement A
# ---------------------------------------------------------------------------

def test_success_with_scratch_dir_rejected():
    """On success the worktree was pruned; scratch_dir must not be present.
    Schema enforces this via `properties: {scratch_dir: false}` in the success
    branch — the false-schema rejects any value. The error message references
    the value rather than the field name, so we check on the exception type."""
    r = _base_success()
    r["scratch_dir"] = "/tmp/exp-scratch/foo"
    with pytest.raises(ResultValidationError):
        validate_result(r)


def test_incomplete_without_scratch_dir_rejected():
    """Per refinement A, scratch_dir is set from the very first partial-write."""
    r = _base_partial()
    r.pop("scratch_dir")
    with pytest.raises(ResultValidationError, match="scratch_dir"):
        validate_result(r)


def test_error_without_scratch_dir_rejected():
    """status=error retains the worktree for forensics; scratch_dir required."""
    err = _base_partial()
    err.update({
        "status": "error",
        "completed_at": "2026-05-03T12:05:00Z",
        "runtime_s": 300.0,
        "exit_code": 1,
        "error": {"type": "non-zero-exit", "message": "x"},
        "scoring": {"scope_check": {"out_of_scope_file_count": 0, "out_of_scope_paths": []}},
    })
    err.pop("scratch_dir")
    with pytest.raises(ResultValidationError, match="scratch_dir"):
        validate_result(err)


# ---------------------------------------------------------------------------
# status-specific invariants
# ---------------------------------------------------------------------------

def test_success_with_non_null_error_rejected():
    r = _base_success()
    r["error"] = {"type": "x", "message": "y"}
    with pytest.raises(ResultValidationError):
        validate_result(r)


def test_error_status_with_null_error_rejected():
    err = _base_partial()
    err.update({
        "status": "error",
        "completed_at": "2026-05-03T12:05:00Z",
        "runtime_s": 300.0,
        "exit_code": 1,
        "error": None,  # invalid: error status requires non-null error
        "scoring": {"scope_check": {"out_of_scope_file_count": 0, "out_of_scope_paths": []}},
    })
    with pytest.raises(ResultValidationError):
        validate_result(err)


def test_incomplete_with_premature_scoring_rejected():
    """Partial-write must have scoring={}; scope_check landing here is a bug."""
    r = _base_partial()
    r["scoring"] = {"scope_check": {"out_of_scope_file_count": 0, "out_of_scope_paths": []}}
    with pytest.raises(ResultValidationError):
        validate_result(r)


def test_incomplete_with_nonzero_judge_calls_rejected():
    r = _base_partial()
    r["judge_calls"] = 3
    with pytest.raises(ResultValidationError):
        validate_result(r)


def test_success_without_scope_check_rejected():
    """Once the agent ran, scope_check is mandatory in scoring."""
    r = _base_success()
    r["scoring"].pop("scope_check")
    with pytest.raises(ResultValidationError, match="scope_check"):
        validate_result(r)


# ---------------------------------------------------------------------------
# Field-shape invariants
# ---------------------------------------------------------------------------

def test_invalid_plugin_sha_rejected():
    r = _base_partial(plugin_sha="not-a-sha")
    with pytest.raises(ResultValidationError):
        validate_result(r)


def test_null_plugin_sha_validates():
    """Allowed when plugin path isn't a git working tree (runner emits warning)."""
    r = _base_partial(plugin_sha=None)
    validate_result(r)


def test_unknown_top_level_field_rejected():
    """additionalProperties: false on top-level object catches drift."""
    r = _base_partial()
    r["mystery_field"] = "wat"
    with pytest.raises(ResultValidationError):
        validate_result(r)


def test_score_outside_0_3_rejected():
    r = _base_success()
    r["scoring"]["rubric_scores"]["per_trial"][0]["scores"]["hypothesis"] = 5
    with pytest.raises(ResultValidationError):
        validate_result(r)


def test_overall_mean_outside_0_3_rejected():
    r = _base_success()
    r["scoring"]["rubric_scores"]["overall_mean"] = 999.0
    with pytest.raises(ResultValidationError):
        validate_result(r)


def test_rubric_scores_missing_stdev_rejected():
    r = _base_success()
    del r["scoring"]["rubric_scores"]["stdev"]
    with pytest.raises(ResultValidationError):
        validate_result(r)


def test_rubric_scores_error_path_validates():
    """The judge can fail; scoring.rubric_scores becomes {error: {...}}."""
    r = _base_success()
    r["scoring"]["rubric_scores"] = {
        "error": {"type": "JudgeInvocationError", "message": "claude judge timed out"},
    }
    validate_result(r)


def test_unknown_scoring_subkey_allowed():
    """Future scorers (test_pass, sim_metric, static_check) land here without
    a schema bump (additionalProperties: true on scoring)."""
    r = _base_success()
    r["scoring"]["test_pass"] = {"resolved": True}
    validate_result(r)


# ---------------------------------------------------------------------------
# schema_version is pinned
# ---------------------------------------------------------------------------

def test_wrong_schema_version_rejected():
    r = _base_partial(schema_version=2)
    with pytest.raises(ResultValidationError):
        validate_result(r)


# ---------------------------------------------------------------------------
# T1.7a — optional judge_io reference on per_trial entries
# ---------------------------------------------------------------------------

def test_per_trial_with_judge_io_validates():
    """The optional judge_io ref (path + total_cost_usd) is accepted on per_trial."""
    r = _base_success()
    for i, trial in enumerate(r["scoring"]["rubric_scores"]["per_trial"], start=1):
        trial["judge_io"] = {
            "path": f"judge-trial-{i}.json",
            "total_cost_usd": 0.0123,
        }
    validate_result(r)


def test_per_trial_without_judge_io_still_validates():
    """Existing T1.5 baselines (no judge_io) must continue to validate."""
    r = _base_success()
    for trial in r["scoring"]["rubric_scores"]["per_trial"]:
        assert "judge_io" not in trial
    validate_result(r)


def test_per_trial_with_null_total_cost_validates():
    """total_cost_usd may be null when the wrapper doesn't surface a cost."""
    r = _base_success()
    r["scoring"]["rubric_scores"]["per_trial"][0]["judge_io"] = {
        "path": "judge-trial-1.json",
        "total_cost_usd": None,
    }
    validate_result(r)


def test_per_trial_judge_io_missing_path_rejected():
    r = _base_success()
    r["scoring"]["rubric_scores"]["per_trial"][0]["judge_io"] = {
        "total_cost_usd": 0.012,
    }
    with pytest.raises(ResultValidationError):
        validate_result(r)


def test_per_trial_judge_io_non_string_path_rejected():
    r = _base_success()
    r["scoring"]["rubric_scores"]["per_trial"][0]["judge_io"] = {
        "path": 123,
        "total_cost_usd": 0.012,
    }
    with pytest.raises(ResultValidationError):
        validate_result(r)


def test_per_trial_judge_io_extra_field_rejected():
    """additionalProperties: false guards the small reference object."""
    r = _base_success()
    r["scoring"]["rubric_scores"]["per_trial"][0]["judge_io"] = {
        "path": "judge-trial-1.json",
        "total_cost_usd": 0.012,
        "extra": "nope",
    }
    with pytest.raises(ResultValidationError):
        validate_result(r)


def test_schema_version_unchanged_after_t17a():
    """Per ADR-0008, optional additions don't bump schema_version."""
    r = _base_success()
    assert r["schema_version"] == 1
    validate_result(r)
