"""Unit tests for harness.score_rubric.

The rubric scorer subprocess `claude --bare -p` per ADR-0006. To keep these
tests fast and deterministic, the subprocess invocation is injected as a
`judge_runner` callable; tests pass fakes. The real subprocess adapter is
exercised by T1.5's live baseline runs, not here.
"""
from __future__ import annotations

import math

import pytest

from harness.score_rubric import (
    JUDGE_OUTPUT_SCHEMA,
    JudgeInvocationError,
    build_judge_prompt,
    score_rubric,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

def _constant_judge(scores: dict, overall: float, rationale: str = "ok"):
    def _runner(prompt: str) -> dict:
        return {"scores": dict(scores), "overall": overall, "rationale": rationale}
    return _runner


def _sequence_judge(outputs: list[dict]):
    it = iter(outputs)

    def _runner(prompt: str) -> dict:
        return next(it)

    return _runner


# ---------------------------------------------------------------------------
# Aggregation: identical trials → zero stdev
# ---------------------------------------------------------------------------

def test_three_identical_trials_give_zero_stdev():
    judge = _constant_judge({"hypothesis": 2, "signals": 3}, overall=2.5)
    result = score_rubric("rubric", "deliverable", n_trials=3, judge_runner=judge)

    assert result["mean"] == {"hypothesis": 2.0, "signals": 3.0}
    assert result["stdev"] == {"hypothesis": 0.0, "signals": 0.0}
    assert result["overall_mean"] == 2.5
    assert result["overall_stdev"] == 0.0
    assert len(result["per_trial"]) == 3
    assert result["n_trials"] == 3


# ---------------------------------------------------------------------------
# Aggregation: varying scores → correct mean and sample stdev
# ---------------------------------------------------------------------------

def test_varying_trials_compute_mean_and_sample_stdev():
    judge = _sequence_judge([
        {"scores": {"x": 1}, "overall": 1.0, "rationale": "r1"},
        {"scores": {"x": 2}, "overall": 2.0, "rationale": "r2"},
        {"scores": {"x": 3}, "overall": 3.0, "rationale": "r3"},
    ])
    result = score_rubric("r", "d", n_trials=3, judge_runner=judge)

    assert result["mean"]["x"] == 2.0
    assert math.isclose(result["stdev"]["x"], 1.0)  # sample stdev of 1,2,3 is 1.0
    assert result["overall_mean"] == 2.0
    assert math.isclose(result["overall_stdev"], 1.0)


# ---------------------------------------------------------------------------
# Honest aggregation: recompute per-trial overall from scores
# ---------------------------------------------------------------------------

def test_per_trial_overall_recomputed_from_scores_not_judge_claim():
    """If the judge's `overall` disagrees with mean(scores), trust the scores."""
    judge = _sequence_judge([
        {"scores": {"a": 0, "b": 3}, "overall": 999.0, "rationale": "lying"},
        {"scores": {"a": 0, "b": 3}, "overall": 999.0, "rationale": "lying"},
        {"scores": {"a": 0, "b": 3}, "overall": 999.0, "rationale": "lying"},
    ])
    result = score_rubric("r", "d", n_trials=3, judge_runner=judge)

    assert result["overall_mean"] == 1.5  # mean of (0,3) — the judge's 999 is ignored
    # Per-trial entries preserve both the judge's claim and the recomputed value
    # so audit can spot judges that disagree with their own arithmetic.
    assert result["per_trial"][0]["overall_recomputed"] == 1.5
    assert result["per_trial"][0]["overall_judge_reported"] == 999.0


# ---------------------------------------------------------------------------
# Per-trial bookkeeping: rationale and full scores preserved
# ---------------------------------------------------------------------------

def test_per_trial_preserves_rationale_and_scores_for_audit():
    judge = _sequence_judge([
        {"scores": {"a": 2, "b": 1}, "overall": 1.5, "rationale": "specific feedback"},
    ])
    result = score_rubric("r", "d", n_trials=1, judge_runner=judge)

    trial = result["per_trial"][0]
    assert trial["scores"] == {"a": 2, "b": 1}
    assert trial["rationale"] == "specific feedback"


# ---------------------------------------------------------------------------
# n_trials=1: stdev is reported as 0.0 (single-sample variance convention)
# ---------------------------------------------------------------------------

def test_single_trial_reports_zero_stdev():
    judge = _constant_judge({"a": 2}, overall=2.0)
    result = score_rubric("r", "d", n_trials=1, judge_runner=judge)

    assert result["mean"] == {"a": 2.0}
    assert result["stdev"] == {"a": 0.0}
    assert result["overall_stdev"] == 0.0
    assert result["n_trials"] == 1


# ---------------------------------------------------------------------------
# Robustness: trials with mismatched dim sets → fail loudly
# ---------------------------------------------------------------------------

def test_dimension_mismatch_across_trials_raises():
    """The judge is given the same rubric every trial; if the dim set differs,
    the judge has gone off-script — surface that as an error rather than
    silently averaging over partial dims."""
    judge = _sequence_judge([
        {"scores": {"a": 1, "b": 2}, "overall": 1.5, "rationale": "r"},
        {"scores": {"a": 3}, "overall": 3.0, "rationale": "r"},  # missing 'b'
    ])
    with pytest.raises(JudgeInvocationError, match="dimension"):
        score_rubric("r", "d", n_trials=2, judge_runner=judge)


# ---------------------------------------------------------------------------
# Robustness: malformed judge output → fail loudly
# ---------------------------------------------------------------------------

def test_missing_scores_field_raises():
    judge = _sequence_judge([
        {"overall": 2.0, "rationale": "no scores"},
    ])
    with pytest.raises(JudgeInvocationError):
        score_rubric("r", "d", n_trials=1, judge_runner=judge)


def test_non_numeric_score_raises():
    judge = _sequence_judge([
        {"scores": {"a": "two"}, "overall": 2.0, "rationale": "r"},
    ])
    with pytest.raises(JudgeInvocationError):
        score_rubric("r", "d", n_trials=1, judge_runner=judge)


# ---------------------------------------------------------------------------
# build_judge_prompt: must include rubric and deliverable verbatim
# ---------------------------------------------------------------------------

def test_build_judge_prompt_includes_rubric_text():
    prompt = build_judge_prompt("RUBRIC_BODY_HERE", "DELIVERABLE_BODY_HERE")
    assert "RUBRIC_BODY_HERE" in prompt
    assert "DELIVERABLE_BODY_HERE" in prompt


def test_build_judge_prompt_instructs_json_only_output():
    prompt = build_judge_prompt("rubric", "deliverable")
    assert "JSON" in prompt or "json" in prompt


# ---------------------------------------------------------------------------
# JUDGE_OUTPUT_SCHEMA: shape is suitable for `claude --json-schema`
# ---------------------------------------------------------------------------

def test_judge_output_schema_requires_three_top_level_fields():
    required = set(JUDGE_OUTPUT_SCHEMA.get("required", []))
    assert {"scores", "overall", "rationale"} <= required


def test_judge_output_schema_constrains_scores_to_integers_in_range():
    scores_schema = JUDGE_OUTPUT_SCHEMA["properties"]["scores"]
    inner = scores_schema["additionalProperties"]
    assert inner["type"] == "integer"
    assert inner["minimum"] == 0
    assert inner["maximum"] == 3
