"""LLM-judge rubric scorer per ADR-0003 (hybrid scoring) and ADR-0006.

Subprocess `claude --bare -p --json-schema ...` to score a deliverable against
a rubric. `--bare` skips plugins, hooks, CLAUDE.md auto-discovery — the judge
must run with no plugin loaded so it cannot grade work using the same skills
that produced it (per ADR-0003's independence requirement).

N=3 trials by default; aggregates per-dimension mean ± sample stdev so the
non-determinism of the LLM judge is *measured* rather than hidden behind a
single score. Each per-trial overall is recomputed from the score values
(the judge's claimed overall is preserved for audit but not aggregated).

Public surface:
    score_rubric(rubric_text, deliverable, n_trials, judge_runner=None)
        → {per_trial, mean, stdev, overall_mean, overall_stdev, n_trials}

The `judge_runner` callable is injectable for tests; in production it defaults
to `subprocess_judge_runner`, the real `claude` adapter at the bottom of
this module.
"""
from __future__ import annotations

import json
import statistics
import subprocess
from typing import Callable

JudgeRunner = Callable[[str], dict]


class JudgeInvocationError(RuntimeError):
    """Raised when the judge subprocess fails or returns a malformed payload."""


# ---------------------------------------------------------------------------
# Schema and prompt
# ---------------------------------------------------------------------------

# Generic shape — dimension names are not enforced here because they're
# task-specific (they live in the rubric prompt). Only the structural shape
# and per-score 0–3 integer constraint are enforced.
JUDGE_OUTPUT_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "scores": {
            "type": "object",
            "additionalProperties": {
                "type": "integer",
                "minimum": 0,
                "maximum": 3,
            },
        },
        "overall": {"type": "number"},
        "rationale": {"type": "string"},
    },
    "required": ["scores", "overall", "rationale"],
    "additionalProperties": False,
}

_JUDGE_INSTRUCTIONS = """You are an impartial evaluator. Score the deliverable below against the rubric.

Return JSON only — no prose outside the JSON object. The output must match the
schema you have been given:

  - `scores`: an object whose keys are the dimension names from the rubric (use
    snake_case keys exactly as the rubric's "LLM-judge output schema" section
    specifies), and whose values are integers 0, 1, 2, or 3 per the rubric's
    grade descriptions.
  - `overall`: the arithmetic mean of the score values.
  - `rationale`: 2-4 sentences citing specific strengths and weaknesses of the
    deliverable. Reference the rubric dimensions by name.

Use the rubric's grade-level guidance literally. Do not invent dimensions; do
not omit dimensions. If the deliverable is empty or off-topic, score 0 across
the board with a brief rationale explaining why.
"""


def build_judge_prompt(rubric_text: str, deliverable: str) -> str:
    """Compose the judge's prompt. Rubric and deliverable are included verbatim."""
    return (
        _JUDGE_INSTRUCTIONS
        + "\n\n=== RUBRIC ===\n\n"
        + rubric_text
        + "\n\n=== DELIVERABLE TO SCORE ===\n\n"
        + deliverable
    )


# ---------------------------------------------------------------------------
# Per-trial validation + recompute
# ---------------------------------------------------------------------------

def _validate_and_recompute(payload: dict, trial_index: int) -> dict:
    """Check shape; return a normalized per-trial record."""
    if not isinstance(payload, dict):
        raise JudgeInvocationError(
            f"trial {trial_index}: judge returned non-dict payload ({type(payload).__name__})"
        )
    scores = payload.get("scores")
    if not isinstance(scores, dict) or not scores:
        raise JudgeInvocationError(
            f"trial {trial_index}: judge payload missing or empty `scores` field"
        )
    numeric_scores: dict[str, float] = {}
    for dim, val in scores.items():
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            raise JudgeInvocationError(
                f"trial {trial_index}: dimension {dim!r} has non-numeric score {val!r}"
            )
        numeric_scores[dim] = float(val)

    recomputed_overall = sum(numeric_scores.values()) / len(numeric_scores)
    return {
        "scores": {k: int(v) if v.is_integer() else v for k, v in numeric_scores.items()},
        "overall_recomputed": recomputed_overall,
        "overall_judge_reported": payload.get("overall"),
        "rationale": payload.get("rationale", ""),
    }


def _aggregate(per_trial: list[dict]) -> dict:
    """Compute per-dim and overall mean/stdev across N trials.

    Requires every trial to have the same dimension set; mismatch is a judge
    failure (the rubric is identical across trials) and is raised loudly.
    """
    if not per_trial:
        raise JudgeInvocationError("no trials to aggregate")

    dims = set(per_trial[0]["scores"].keys())
    for i, trial in enumerate(per_trial[1:], start=1):
        trial_dims = set(trial["scores"].keys())
        if trial_dims != dims:
            missing = dims - trial_dims
            extra = trial_dims - dims
            raise JudgeInvocationError(
                f"trial {i} has a different dimension set than trial 0; "
                f"missing={sorted(missing)} extra={sorted(extra)}"
            )

    n = len(per_trial)

    def _stdev(values: list[float]) -> float:
        # Sample stdev requires N≥2; for N=1 the conventional report is 0.0.
        return statistics.stdev(values) if n >= 2 else 0.0

    mean: dict[str, float] = {}
    stdev: dict[str, float] = {}
    for dim in dims:
        vals = [float(t["scores"][dim]) for t in per_trial]
        mean[dim] = statistics.fmean(vals)
        stdev[dim] = _stdev(vals)

    overalls = [t["overall_recomputed"] for t in per_trial]
    return {
        "n_trials": n,
        "per_trial": per_trial,
        "mean": mean,
        "stdev": stdev,
        "overall_mean": statistics.fmean(overalls),
        "overall_stdev": _stdev(overalls),
    }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def score_rubric(
    rubric_text: str,
    deliverable: str,
    *,
    n_trials: int = 3,
    judge_runner: JudgeRunner | None = None,
) -> dict:
    """Score `deliverable` against `rubric_text`. Returns aggregated trials."""
    if n_trials < 1:
        raise ValueError(f"n_trials must be ≥1; got {n_trials}")
    runner = judge_runner if judge_runner is not None else subprocess_judge_runner

    prompt = build_judge_prompt(rubric_text, deliverable)
    per_trial = [
        _validate_and_recompute(runner(prompt), i)
        for i in range(n_trials)
    ]
    return _aggregate(per_trial)


# ---------------------------------------------------------------------------
# Real subprocess adapter (T1.5 verifies this end-to-end)
# ---------------------------------------------------------------------------

DEFAULT_JUDGE_TIMEOUT_S = 600


def subprocess_judge_runner(prompt: str, *, timeout_s: int = DEFAULT_JUDGE_TIMEOUT_S) -> dict:
    """Invoke `claude --bare -p` with structured-output validation. Returns parsed payload.

    `--bare` skips plugins, hooks, and CLAUDE.md auto-discovery — the judge runs
    independently of the plugin under test, satisfying ADR-0003's independence
    requirement and T1.4's permission-denial criterion. `--tools ""` disables
    all tools (the judge produces a single JSON response from one prompt).
    `cwd=/tmp` is belt-and-braces against any path-based context leakage.
    """
    cmd = [
        "claude",
        "--bare",
        "--print",
        "--output-format", "json",
        "--no-session-persistence",
        "--max-turns", "1",
        "--json-schema", json.dumps(JUDGE_OUTPUT_SCHEMA),
        "--tools", "",
        "-p", prompt,
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd="/tmp",
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as e:
        raise JudgeInvocationError(f"claude judge timed out after {timeout_s}s") from e
    except FileNotFoundError as e:
        raise JudgeInvocationError("`claude` binary not found on PATH") from e

    if proc.returncode != 0:
        raise JudgeInvocationError(
            f"claude judge exited {proc.returncode}: {proc.stderr.strip()[:500]}"
        )

    try:
        wrapper = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise JudgeInvocationError(
            f"claude judge wrapper is not JSON: {proc.stdout[:500]!r}"
        ) from e

    # `claude --output-format json` returns {"result": "<string>", ...} for text
    # output. With --json-schema the model emits a JSON string in `result`; some
    # versions inline the parsed object. Handle both.
    payload = wrapper.get("result", wrapper)
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as e:
            raise JudgeInvocationError(
                f"claude judge `result` field is not JSON: {payload[:500]!r}"
            ) from e
    return payload
