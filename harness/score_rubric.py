"""LLM-judge rubric scorer per ADR-0003 (hybrid scoring) and ADR-0009.

Subprocess `claude -p --json-schema ...` to score a deliverable against a
rubric. The judge runs in an isolated cwd outside this repo (excludes the
project-local agent-skills plugin per ADR-0009) with --disable-slash-commands,
--no-session-persistence, --max-turns 1, and --tools "" — so it cannot grade
work using the same skills that produced it (per ADR-0003's independence
requirement).

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

import atexit
import hashlib
import json
import shutil
import statistics
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Callable

JudgeRunner = Callable[[str], dict]

# Per-trial sidecar filename (T1.7a). Stored alongside result.json in the
# experiment directory; referenced from `result.json.scoring.rubric_scores
# .per_trial[i].judge_io.path` so the heavy data (raw stdout wrapper,
# stderr, full usage record) lives outside result.json itself.
JUDGE_TRIAL_FILENAME_TEMPLATE = "judge-trial-{i}.json"


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
    numeric_scores: dict[str, int] = {}
    for dim, val in scores.items():
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            raise JudgeInvocationError(
                f"trial {trial_index}: dimension {dim!r} has non-numeric score {val!r}"
            )
        as_float = float(val)
        if not as_float.is_integer():
            # The schema constrains scores to integers; a fractional value
            # means the judge ignored the schema. Surface as a judge error
            # rather than coerce, so downstream result.json validation can't
            # blame the writer for a judge regression.
            raise JudgeInvocationError(
                f"trial {trial_index}: dimension {dim!r} score {val!r} is not integer-valued"
            )
        numeric_scores[dim] = int(as_float)

    recomputed_overall = sum(numeric_scores.values()) / len(numeric_scores)
    return {
        "scores": dict(numeric_scores),
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
    experiment_dir: Path | None = None,
) -> dict:
    """Score `deliverable` against `rubric_text`. Returns aggregated trials.

    When `experiment_dir` is provided AND the runner returns a "rich" record
    (one with a `payload` key — see `subprocess_judge_runner`), each trial's
    full subprocess output is persisted to
    `experiment_dir/judge-trial-{i}.json` and a `judge_io = {path,
    total_cost_usd}` reference is stamped onto the corresponding per-trial
    record. When `experiment_dir` is None, behavior is unchanged from before
    T1.7a: the runner's return value is treated as the bare payload and no
    sidecars are written. Test fakes that return bare payloads continue to
    work either way.
    """
    if n_trials < 1:
        raise ValueError(f"n_trials must be ≥1; got {n_trials}")
    runner = judge_runner if judge_runner is not None else subprocess_judge_runner

    prompt = build_judge_prompt(rubric_text, deliverable)
    per_trial: list[dict] = []
    for i in range(n_trials):
        ret = runner(prompt)
        payload = _bare_payload(ret)
        trial = _validate_and_recompute(payload, i)
        if experiment_dir is not None and _is_rich(ret):
            sidecar_path = _write_sidecar(experiment_dir, i, ret)
            trial["judge_io"] = {
                "path": sidecar_path.name,
                "total_cost_usd": _extract_cost(ret),
            }
        per_trial.append(trial)
    return _aggregate(per_trial)


# ---------------------------------------------------------------------------
# Rich-record helpers (T1.7a)
# ---------------------------------------------------------------------------

def _is_rich(ret: dict) -> bool:
    """True if `ret` is a rich JudgeTrial record (vs. a bare payload)."""
    return isinstance(ret, dict) and isinstance(ret.get("payload"), dict)


def _bare_payload(ret: dict) -> dict:
    """Extract the parsed judge payload regardless of runner shape."""
    return ret["payload"] if _is_rich(ret) else ret


def _extract_cost(rich: dict) -> float | None:
    wrapper = rich.get("wrapper") or {}
    cost = wrapper.get("total_cost_usd")
    return cost if isinstance(cost, (int, float)) else None


def _redact_schema_in_cmd(cmd: list[str]) -> list[str]:
    """Replace the --json-schema body with a SHA pointer to keep sidecars compact."""
    out = list(cmd)
    try:
        i = out.index("--json-schema")
        body = out[i + 1]
        sha = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
        out[i + 1] = f"<sha256:{sha}>"
    except (ValueError, IndexError):
        pass
    return out


def _write_sidecar(experiment_dir: Path, trial_index: int, rich: dict) -> Path:
    """Persist one trial's full judge IO; return the sidecar path."""
    cmd = rich.get("cmd") or []
    wrapper = rich.get("wrapper") or {}
    sidecar = {
        "trial_index": trial_index + 1,
        "cmd": _redact_schema_in_cmd(cmd),
        "stdout_wrapper": wrapper,
        "stderr": rich.get("stderr", ""),
        "returncode": rich.get("returncode"),
        "duration_s": rich.get("duration_s"),
        "total_cost_usd": _extract_cost(rich),
        "usage": wrapper.get("usage"),
    }
    experiment_dir.mkdir(parents=True, exist_ok=True)
    path = experiment_dir / JUDGE_TRIAL_FILENAME_TEMPLATE.format(i=trial_index + 1)
    path.write_text(json.dumps(sidecar, indent=2, sort_keys=True))
    return path


# ---------------------------------------------------------------------------
# Real subprocess adapter (T1.5 verifies this end-to-end)
# ---------------------------------------------------------------------------

DEFAULT_JUDGE_TIMEOUT_S = 600

_JUDGE_CWD: Path | None = None


def _judge_cwd() -> Path:
    """A per-process empty tempdir used as the judge subprocess's cwd.

    Per ADR-0009: cwd outside this repo is load-bearing for excluding the
    project-local agent-skills plugin from the judge's session. A dedicated
    tempdir (vs /tmp) prevents any project-CLAUDE.md or .claude/ that might
    sit in /tmp from being discovered, and contains any stray writes the
    subprocess might emit.

    Cached: one tempdir per Python process, removed at interpreter exit.
    """
    global _JUDGE_CWD
    if _JUDGE_CWD is None:
        _JUDGE_CWD = Path(tempfile.mkdtemp(prefix="robotics-benchmark-judge-cwd-"))
        atexit.register(shutil.rmtree, str(_JUDGE_CWD), True)
    return _JUDGE_CWD


def _build_judge_cmd(prompt: str) -> list[str]:
    """Construct the `claude` command for a single judge invocation.

    Per ADR-0009: judge shares the user's environment (no --bare) but disables
    skills, sessions, and the agentic loop. Local plugins are excluded by cwd.
    Extracted for testability: a unit test asserts that --bare and other
    context-introducing flags (--mcp-config, --agents, --plugin-dir, etc.)
    are NOT present.
    """
    # --max-turns 3: --json-schema is implemented internally as a forced
    # tool round-trip (one assistant turn emits the structured-output tool_use,
    # one user turn delivers the tool_result, one assistant turn emits the
    # final text). 1 turn cannot satisfy this; 3 is the minimum + 1 of headroom.
    # --allowedTools "": empty allowlist = no real tools exposed (the
    # structured-output mechanism is internal, not in the allowlist).
    return [
        "claude",
        "--print",
        "--output-format", "json",
        "--no-session-persistence",
        "--disable-slash-commands",
        "--max-turns", "3",
        "--json-schema", json.dumps(JUDGE_OUTPUT_SCHEMA),
        "--allowedTools", "",
        "-p", prompt,
    ]


def subprocess_judge_runner(
    prompt: str, *, timeout_s: int = DEFAULT_JUDGE_TIMEOUT_S
) -> dict:
    """Invoke `claude` to score a deliverable. Returns a rich JudgeTrial record.

    Per ADR-0009: judge runs without --bare in an isolated cwd. This excludes
    the project-local agent-skills plugin (cwd outside repo) while keeping the
    user's existing OAuth login (keychain). --allowedTools "" + --max-turns 3
    close the tool surface; --disable-slash-commands prevents skill
    auto-resolution; --no-session-persistence prevents cross-call state.

    Return shape (T1.7a): a "rich" record with the parsed payload alongside
    the raw subprocess outputs needed for sidecar capture. `score_rubric`
    extracts `payload` for validation and (when given an `experiment_dir`)
    writes the rest to `experiment_dir/judge-trial-{i}.json`.

        {
            "payload": {scores, overall, rationale},
            "wrapper": <full claude stdout JSON>,
            "stderr": <captured stderr>,
            "returncode": 0,
            "duration_s": <subprocess wall-clock seconds>,
            "cmd": [...],  # argv as passed to subprocess.run
        }
    """
    cmd = _build_judge_cmd(prompt)
    start = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(_judge_cwd()),
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as e:
        raise JudgeInvocationError(f"claude judge timed out after {timeout_s}s") from e
    except FileNotFoundError as e:
        raise JudgeInvocationError("`claude` binary not found on PATH") from e
    duration_s = time.perf_counter() - start

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

    # With --json-schema, the parsed JSON object lands in `structured_output`
    # (the `result` field gets the model's plain-text accompaniment). Older
    # versions may inline JSON in `result`; handle both.
    if "structured_output" in wrapper:
        payload = wrapper["structured_output"]
    else:
        payload = wrapper.get("result", wrapper)
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError as e:
                raise JudgeInvocationError(
                    f"claude judge `result` field is not JSON: {payload[:500]!r}"
                ) from e

    return {
        "payload": payload,
        "wrapper": wrapper,
        "stderr": proc.stderr,
        "returncode": proc.returncode,
        "duration_s": duration_s,
        "cmd": cmd,
    }
