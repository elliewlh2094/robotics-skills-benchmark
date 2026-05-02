# Rubric: diffbot-experiment-design

This rubric grades an experiment plan for DiffBot's kinematic integration.
The agent's deliverable is `EXPERIMENT.md` at the root of the
ros2_control_demos repository checkout.

The LLM judge scores each dimension on a 0–3 scale:

- **0** — Absent or wrong
- **1** — Mentioned but underdeveloped (vague, generic, no specifics)
- **2** — Present and reasonable (specific but not deeply grounded)
- **3** — Specific, grounded in this repo's actual code, demonstrates robotics judgment

Maximum: 21 points (7 dimensions × 3). Overall score = mean of dimensions.

---

## Dimensions

### 1. Hypothesis statement
Is the hypothesis falsifiable, quantitative, and tied to observable signals?

- **0** — No hypothesis, or non-testable
- **1** — Qualitative ("position should track velocity") without math
- **2** — Quantitative form (e.g., `pos ≈ v·T`) but no error bound
- **3** — Quantitative + error-bound form (e.g., `|pos − v·T| ≤ Δt·|v|/2`) grounded in the controller's update period

### 2. Controlled variables (independent + confounds)
Are independent variables identified with concrete levels, and confounds named and held constant?

- **0** — No variables identified
- **1** — IVs named without specific levels
- **2** — IVs with concrete levels (e.g., "v ∈ {±0.5, ±1.0, 0} m/s; T ∈ {5, 30, 60} s")
- **3** — Above + explicit confounds list (controller update rate, ROS_DOMAIN_ID, sim/wall clock setting, controller manager startup sequence) with hold-constant strategy

### 3. Recorded signals
Are specific ROS 2 topics named with sample rates and rationale?

- **0** — "Record everything" or no signals named
- **1** — Topics named without rates
- **2** — Topics + rates without rationale
- **3** — Topic-by-topic justification with plausible rates (e.g., `/joint_states` at controller rate ~100 Hz; `/cmd_vel` echo for command audit; `/clock` for sim-time consistency; `/diagnostics` for controller health)

### 4. Success thresholds
Are thresholds quantitative, tied to the hypothesis, and given with units?

- **0** — "Looks good" or no thresholds
- **1** — Qualitative thresholds
- **2** — Numeric thresholds without units, OR units but not derived from the hypothesis
- **3** — Numeric + units + derived from the hypothesis (e.g., "linear regression of measured vs. expected position yields slope 1.0 ± 0.01, R² > 0.999; per-trial residuals bounded by Δt·|v|/2 + 1 mm")

### 5. Visualization plan
Does the plan specify tools and which signals against which?

- **0** — No visualization plan
- **1** — "We will plot the results" without specifics
- **2** — Specific tooling (PlotJuggler, foxglove, matplotlib) without specifying signals
- **3** — Specific tooling + multiple panes/views with signal-by-signal rationale (e.g., commanded vs. actual velocity over time; position vs. ideal integral overlaid; residual histogram per velocity level)

### 6. Failure modes
Are at least three concrete failure modes anticipated, each with a specific mitigation?

- **0** — No failure modes
- **1** — 1–2 generic failure modes
- **2** — 3+ concrete failure modes without mitigations
- **3** — 3+ concrete failure modes with specific mitigations (e.g., "controller manager not started before publisher → silent zero position. Mitigation: 5 s startup wait, assert `/joint_states` rate before recording")

### 7. Repo grounding
Does the plan reference the actual files, nodes, and structure of this repository, or is it a generic experiment-design checklist that could apply to any robot?

- **0** — No repo references; plan would apply to any robot
- **1** — Mentions the repo or "DiffBot" by name without specifics
- **2** — References specific files (e.g., `example_2/hardware/diffbot_system.cpp`) but not their actual content
- **3** — References specific code constructs from this repo (e.g., the `read()`/`write()` lifecycle of the hardware interface, the use of `hw_velocities_` / `hw_positions_` arrays, the Euler-step in `read()`) and uses them to inform experimental decisions; the experimental setup is described in terms of the actual runtime shipped in `example_2/` (controller_manager + ros2_control_node + the mock-hardware interface), not as a generic ROS 2 plan

---

## LLM-judge output schema

The judge must return JSON of the following shape:

```json
{
  "scores": {
    "hypothesis_statement": 0,
    "controlled_variables": 0,
    "recorded_signals": 0,
    "success_thresholds": 0,
    "visualization_plan": 0,
    "failure_modes": 0,
    "repo_grounding": 0
  },
  "overall": 0.0,
  "rationale": "Two to four sentences explaining the scoring, citing specific strengths and weaknesses of the agent's plan."
}
```

`overall` must be the arithmetic mean of the seven dimension scores (range 0.0–3.0).
