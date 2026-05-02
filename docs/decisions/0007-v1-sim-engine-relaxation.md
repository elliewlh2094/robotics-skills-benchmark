# ADR-0007: V1 `sim_engine` criterion relaxed; long-term Gazebo direction unchanged

## Status
Accepted

## Date
2026-05-02

## Context

The original implementation plan locked in: *"Sim baseline = Gazebo + ROS 2. All V1/V2 task repos must run on Gazebo to keep infra setup linear."* This was sensible when read as a long-term sim-platform commitment.

Two facts emerged during V1 task selection that complicate it:

1. **V1's measurable deliverable is a *design* artifact** (`EXPERIMENT.md`), graded by rubric. The agent does not run anything in V1. Whether the underlying repo actually ships with Gazebo integration is not relevant to whether the rubric can grade the agent's plan.

2. **The best-fit V1 task repo is `ros-controls/ros2_control_demos`, `example_2` (DiffBot)**, which uses ros2_control's mock-hardware interface, not Gazebo. Of the three candidates investigated:
   - DiffBot: ~400 LOC, sharp kinematic invariant, mock hardware (no Gazebo).
   - ros2_control_demos `example_9` (Gazebo+RRBot): ~600 LOC, Gazebo-native, but the *invariant under test* is identical to DiffBot's RRBot variant; Gazebo is infrastructure, not the focus.
   - `turtlebot4_simulator`: ~10–15k LOC, Gazebo Harmonic native, but behaviors are fuzzy (Nav2, SLAM, odometry drift) → poor rubric sharpness.

Holding the Gazebo criterion forced V1 toward worse rubric-grading characteristics, working against ADR-0003's signal-quality goal.

## Decision

For V1 only, the task-repo selection criterion is relaxed to:

> **A runnable ROS 2 simulation OR dummy/mock hardware environment, with a discrete node whose behavior has a sharp testable invariant.**

V1 task instance:
- `base_repo`: `https://github.com/ros-controls/ros2_control_demos`
- focus: `example_2` (DiffBot — `example_2/hardware/diffbot_system.cpp`)
- `sim_engine`: `none` (per the existing schema enum; the repo uses ros2_control mock hardware, no sim engine)

The Gazebo + ROS 2 commitment **remains the long-term direction**. Phase 3+ tasks (debugging with running tests, performance optimization, integration, sim-metric verification) require Gazebo and reinstate the criterion.

This is a **V1 scope exception**, not a strategy change. ADR-0007 supersedes only the V1 portion of the original "all V1/V2 tasks must run on Gazebo" wording.

## Alternatives Considered

### Hold the Gazebo criterion for V1
- **Pros:** Continuity with the originally approved plan.
- **Cons:** Forces selection of `example_9` (larger, structurally noisier) or `turtlebot4_simulator` (much larger, fuzzier behaviors), worsening rubric sharpness exactly when V1 most needs it.
- **Rejected.**

### Drop Gazebo from the long-term direction entirely
- **Pros:** No special case to track.
- **Cons:** Loses sim-metric verification path; would force re-architecting Phase 3+ tasks; abandons valuable platform.
- **Rejected.**

### Pick a different mock-hardware repo for V1
- **Pros:** Possible if a better candidate exists.
- **Cons:** No clearly better candidate identified during the comparative investigation. DiffBot has the sharpest invariant of any non-Gazebo option found.
- **Rejected.**

### Author a custom minimal Gazebo-shipping repo for V1
- **Pros:** Honors both the original Gazebo criterion and rubric sharpness.
- **Cons:** Authoring a benchmark task repo from scratch is harness-internal work that delays the loop closing; defeats the "reference real repos" principle.
- **Rejected.**

## Consequences

- ✅ V1 task selection optimizes for rubric grading quality rather than sim-engine compliance.
- ✅ V1 grades the agent's *plan quality* — hypothesis sharpness, controlled variables, signal selection, threshold derivation, visualization, failure-mode awareness, repo grounding — against the runtime this repo actually ships (`controller_manager` + `ros2_control_node` + mock-hardware interface). The agent designs an experiment for the system as it exists; the rubric does not require, and grade-3 does not depend on, bridging to Gazebo.
- ✅ V1 task can be authored against a fresh `ros2_control_demos` HEAD (yesterday's commit at time of writing).
- ⚠️ Phase 3+ task selection must explicitly reinstate the Gazebo criterion. This exception **does not propagate**.
- ⚠️ Anyone reading the original plan will see the "all V1/V2 tasks must run on Gazebo" wording; this ADR is the canonical correction. The plan file itself is a frozen approved-plan artifact and is not being mutated; ADRs supersede.
- ⚠️ The cross-reference table in `docs/roadmap.md` is updated: the V1 column under "Sim engines" reads "any runnable ROS 2 (mock hardware OK)" with a footnote pointing here.

## Related ADRs

- ADR-0003 (hybrid scoring) — V1 grading is rubric-only, which is what this exception serves.
- ADR-0004 (V1 staged activities) — V1 is already narrowed to experiment-design only; this ADR narrows further.
