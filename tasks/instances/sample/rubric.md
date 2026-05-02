# Rubric: sample task

This rubric is a fixture for schema validation, not a real scoring rubric. The structure below
is what a real rubric looks like.

Each dimension is scored 0–3:

- **0** — Absent or wrong
- **1** — Mentioned but underdeveloped
- **2** — Present and reasonable
- **3** — Specific, grounded in the task repo, demonstrates robotics judgment

## Dimensions

### 1. Hypothesis statement
Is there a clear, falsifiable hypothesis about node/system behavior?
*(0 = no hypothesis; 3 = specific, falsifiable, references measurable signals)*

### 2. Controlled variables
Does the plan distinguish independent variables from confounds, and propose how to hold the
latter fixed?
*(0 = no variables identified; 3 = explicit list with rationale for each)*

### 3. Recorded signals
Does the plan list specific topics/messages to record, with sample rates and rationale?
*(0 = "record everything"; 3 = topic-by-topic justification, plausible rates)*

### 4. Success thresholds
Are thresholds quantitative and tied to the hypothesis?
*(0 = "looks good"; 3 = numeric thresholds with units, derived from requirements)*

### 5. Visualization plan
Does the plan describe how results will be visualized (plotjuggler, matplotlib, foxglove)?
*(0 = absent; 3 = specific tooling + which signals against which)*

### 6. Failure modes considered
Does the plan anticipate at least 3 ways the experiment could fail to produce a clean result,
and propose mitigations?
*(0 = none; 3 = three or more concrete failure modes with mitigations)*

## Scoring output

The LLM judge returns JSON of shape:

```json
{
  "scores": {
    "hypothesis_statement": 2,
    "controlled_variables": 1,
    "recorded_signals": 3,
    "success_thresholds": 2,
    "visualization_plan": 1,
    "failure_modes": 0
  },
  "overall": 1.5,
  "rationale": "..."
}
```
