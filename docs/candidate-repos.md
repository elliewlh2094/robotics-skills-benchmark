# Candidate Repository Knowledge Base

A registry of robotics repositories that have been investigated as potential benchmark task sources. Repos that didn't fit the *current* task get archived here so future task-selection conversations can start from prior work instead of redoing investigations.

> **How to add a new entry.** Invoke the `record-candidate-repo` skill (see `.claude/skills/record-candidate-repo/SKILL.md`). It encodes the template below and walks through the verification steps.
>
> **How to read this file.** Start with the at-a-glance table. Open detailed entries only for repos relevant to the task type you're scoping.

---

## At-a-glance

| Repo | Last investigated | Best long-term fit | Status |
|---|---|---|---|
| [ros-controls/ros2_control_demos](#ros-controlsros2_control_demos) | 2026-05-02 | **V1 (`example_2`)**; `example_9` for Phase 3+ Gazebo verification; multi-robot examples for Phase 5+ | ✅ in use |
| [turtlebot/turtlebot4_simulator](#turtlebotturtlebot4_simulator) | 2026-05-02 | Phase 4+ sim-metric tasks (odometry drift); Phase 3+ if a known bug is identified | 🗄️ archived for later |
| [pal-robotics/tiago_simulation](#pal-roboticstiago_simulation) | 2026-05-02 | Phase 5+ integration tasks (multi-subsystem coordination, manipulation handoff) | 🗄️ archived for later |
| [ROBOTIS-GIT/turtlebot3_simulations](#robotis-gitturtlebot3_simulations) | 2026-05-02 | Phase 4+ sim-metric tasks (well-known platform, lots of priors); fallback if TB4 fragile | 🗄️ archived for later |
| Un-investigated mentions | — | varies | 📋 backlog |

Status legend: ✅ in use, 🗄️ archived for later, 📋 backlog (needs investigation), ❌ rejected (won't fit), 🔄 superseded by newer repo.

---

## ros-controls/ros2_control_demos

- **URL:** https://github.com/ros-controls/ros2_control_demos
- **Default branch:** `master`
- **Latest commit at investigation:** `9b44b9ea777c1318bf20a91498c98c1fcc9e0cc6` (2026-05-01)
- **License:** Apache-2.0
- **Maintenance:** Actively maintained (commit yesterday at time of investigation)

### Description

The official ros2_control framework's demonstration repository. 17 progressive examples (`example_1` … `example_17`), each in its own subdirectory with hardware interface code (typically C++), URDF descriptions, controller configurations, and launch files. Examples scale from minimal single-joint hardware up to multi-robot/chaining/GPIO scenarios.

### Examples table (most-relevant subset)

| Example | Demonstrates | Gazebo? | Invariant sharpness | Approx. LOC | Notable for |
|---|---|---|---|---|---|
| 1 (RRBot) | 2-joint arm, position control with controller switching | No | Sharp: exponential convergence `Δpos = (cmd − pos)/slowdown` | ~500 | RRBot baseline; many later examples extend it |
| **2 (DiffBot)** | Differential drive mobile robot with velocity control | No | Sharp: kinematic integration `pos += vel × Δt` | ~400 | **V1 task source** |
| 9 (Gazebo) | Switches RRBot between mock hardware and Gazebo sim | **Yes** | Same invariant as Ex. 1; Gazebo is infrastructure | ~600 | Phase 3+ when Gazebo verification matters |
| 3–8, 10–17 | Variants, multi-robot, chaining, GPIO, diagnostics | Mostly no | Mostly fuzzy (configuration / orchestration) | 400–2000 | Phase 5+ multi-robot or integration tasks |

### Suitability matrix

| Task type | Fit | Notes |
|---|---|---|
| Rubric — experiment-design | ⭐ Strong (V1) | DiffBot's invariant is the sharpest of any candidate found. Currently V1's task source. |
| Rubric — spec/planning | Possible | Could ask agent to write a spec for adding a new example variant. |
| Test-pass — debugging | Possible | Would require injecting a known bug and writing FAIL_TO_PASS tests. The repo's existing tests are smoke-level. |
| Sim-metric — perf | Weak | Mock hardware doesn't expose real perf characteristics; example_9 with Gazebo would be needed. |
| Integration / multi-robot | Possible (Phase 5+) | Examples 10–17 introduce multi-robot scenarios suitable for integration tasks. |

### Why kept for active use

V1 task instance points at `example_2` per ADR-0007. `example_9` is the natural step-up for Phase 3+ when verification involves running Gazebo. Examples 10+ are reserves for future multi-robot/chaining tasks.

### Risks / caveats

- Repository covers ROS 2 distros; check `master` matches the distro (`humble`, `jazzy`, `rolling`) the V1 environment uses before re-locking the SHA.
- Examples occasionally get reorganized; future SHA pins may need to refer to the example by path (`example_2/`) rather than relying on numbering stability.

---

## turtlebot/turtlebot4_simulator

- **URL:** https://github.com/turtlebot/turtlebot4_simulator
- **Default branch:** `jazzy` (also has `humble`, `iron`, etc.)
- **Latest commit at investigation:** `b7d0f3b973258481f6cd8137bef9240fb567f566` (2024-10-30)
- **License:** BSD-3-Clause
- **Maintenance:** 102 stars, 60 forks, 7 open issues; healthy but not weekly-active

### Description

Official TurtleBot4 simulation packages for ROS 2 Jazzy with **Gazebo Harmonic** (Ignition successor, not Gazebo Classic). Contains 4 packages: `turtlebot4_gz_bringup`, `turtlebot4_gz_gui_plugins`, `turtlebot4_gz_toolbox`, and a metapackage. Provides full Nav2 + SLAM-capable simulation of the TurtleBot4 platform.

### Suitability matrix

| Task type | Fit | Notes |
|---|---|---|
| Rubric — experiment-design | Weak for V1 | Behaviors (Nav2, odometry drift, SLAM) are *fuzzy* — multiple legitimate experiment plans exist; cross-judge variance becomes high. Better suited for sim-metric scoring. |
| Rubric — spec/planning | Possible (Phase 4+) | "Write a spec for a new bringup mode" — concrete enough to grade. |
| Test-pass — debugging | Possible (Phase 3+) | Would need to identify or inject a specific bug with associated FAIL_TO_PASS tests. The platform is widely-used so real bug history exists in the issue tracker. |
| Sim-metric — perf | ⭐ Strong (Phase 4+) | Odometry-drift-vs-distance, costmap update latency, Nav2 goal accuracy under sensor noise — all measurable end-to-end metrics. |
| Integration / multi-robot | Possible (Phase 5+) | TB4's bringup orchestrates Nav2 + SLAM + perception together; integration questions are natural here. |

### Why archived for later

Too large (~10–15k LOC across 4 packages, mixed Py + C++ + QML) and behaviors too fuzzy for a V1 rubric task to grade reliably. The platform's strength — full Nav2/SLAM stack — is exactly the kind of thing that becomes valuable when sim-metric verification (Phase 4+) replaces rubric grading.

### Risks / caveats

- Uses **Gazebo Harmonic**, not Gazebo Classic. If the harness's Phase 3 Dockerfiles target Classic, TB4 forces a parallel Harmonic Dockerfile.
- 6+ months since last commit at investigation time — verify SHA reachability before committing.
- QML files in the GUI plugin package are not part of any robotics task surface and should be excluded from `scope_files`.

---

## pal-robotics/tiago_simulation

- **URL:** https://github.com/pal-robotics/tiago_simulation
- **Default branch:** likely `humble` (Humble LTS); verify before pinning
- **Latest commit at investigation:** `b5eeaac72bbf3c182f244f581e520684f7a22225` (date not confirmed during investigation)
- **License:** check before use; PAL Robotics typically uses Apache-2.0 for open packages
- **Maintenance:** moderate; PAL Robotics actively develops TIAGo

### Description

Simulation packages for the TIAGo mobile manipulator (mobile base + 7-DOF arm + sensor suite). 3 packages: `tiago_gazebo` (sim-specific bringup), `tiago_multi` (multi-robot scenarios), and a `tiago_simulation` metapackage. Integrates with Nav2 and MoveIt2.

### Suitability matrix

| Task type | Fit | Notes |
|---|---|---|
| Rubric — experiment-design (V1 style) | ❌ Weak | Multi-subsystem coupling makes single-invariant experiment design awkward. The agent is forced into "pick narrow" or "pick broad" with no good middle. |
| Test-pass — debugging | Possible (Phase 3+) | Real platform → real bugs exist in history. Pick one with a clear regression test and pin to the parent SHA. |
| Sim-metric — perf | Possible (Phase 4+) | Manipulation timing, control handoff latency between arm and base. |
| **Integration / multi-robot** | ⭐ **Strong (Phase 5+)** | TIAGo's *interesting* questions are integration-flavored: arm-base controller handoff during manipulation, TF tree consistency under concurrent motion, sensor-fusion robustness to arm-induced IMU noise. These are the precise tasks Phase 5+ targets. |
| Spec/planning | Possible | Specs for new manipulation behaviors or pick-and-place scenarios. |

### Why archived for later

TIAGo's complexity is exactly what V1 needs to avoid (multi-subsystem, ~2000+ LOC, fuzzy invariants per subsystem). But that same complexity makes it an excellent fit for the integration task type planned for Phase 5+ — when the harness has sim-metric verification and the rubric system has matured enough to grade integration questions.

### Risks / caveats

- License must be confirmed per package before pinning.
- ROS 2 distro (Humble) may diverge from V1/V2 environment if those move to Jazzy.
- TIAGo MoveIt2 configuration is non-trivial; first task using TIAGo will pay setup overhead in Dockerfile authoring.

---

## ROBOTIS-GIT/turtlebot3_simulations

- **URL:** https://github.com/ROBOTIS-GIT/turtlebot3_simulations
- **Default branch:** `humble` (Humble LTS); also has `iron`, `jazzy` branches
- **Latest commit at investigation:** `9be186fb03d84ed4f293e5c0db71d8c05bbc91f3` (2025-06-27)
- **License:** Apache-2.0
- **Maintenance:** 541 forks, widely deployed in education/research; commits tend to follow ROS 2 distro releases

### Description

Official TurtleBot3 simulation packages for ROS 2 Humble. Contains `turtlebot3_gazebo` (worlds + launch), `turtlebot3_fake_node` (mock hardware for tests without sim), and a `turtlebot3_simulations` metapackage. Provides multiple Gazebo worlds (empty, house, DQN training stages).

### Suitability matrix

| Task type | Fit | Notes |
|---|---|---|
| Rubric — experiment-design | Possible (Phase 2 if needed) | `turtlebot3_fake_node` is a discrete node with a measurable invariant (joint state publishing + odometry integration). Smaller and sharper than TB4. |
| Test-pass — debugging | ⭐ Strong (Phase 3+) | Battle-tested community code; real bug history; small enough to Dockerize. |
| Sim-metric — perf | Possible (Phase 4+) | Odometry drift, Nav2 timing — same shape as TB4 but at smaller scale. |
| Integration / multi-robot | Weak | TB3 is a single-robot platform without manipulation; integration questions are limited. |

### Why archived for later

Strong general-purpose fallback. Was candidate #2 in the original V1 shortlist; lost to DiffBot on sharpness-per-LOC but is the obvious choice if a future task wants a "real robot" baseline at low complexity. Particularly valuable for Phase 3 debugging tasks because community history surfaces real bugs (vs. having to inject synthetic ones).

### Risks / caveats

- 9 launch files (right at the upper bound of "small repo") — bigger than DiffBot but smaller than TB4.
- DQN-stage worlds are tutorial-grade; not suitable for serious benchmarks. Stick to `empty_world.launch.py` and `turtlebot3_house.launch.py`.

---

## Backlog: un-investigated mentions

These have been raised in conversations but not deeply investigated. Each is a candidate for the `record-candidate-repo` skill once a future task brings them into focus.

| Repo | Mentioned for | Notes |
|---|---|---|
| [joshnewans/articubot_one](https://github.com/joshnewans/articubot_one) | Small wheeled-bot tutorial | Active YouTube tutorial series; size unknown; likely good for Phase 3+ |
| [linorobot/linorobot2](https://github.com/linorobot/linorobot2) | Differential-drive platform | Earlier note: "possibly too big, check"; investigate before scoping |
| [methylDragon/ros-tutorial-gazebo-simulation](https://github.com/methylDragon/ros-tutorial-gazebo-simulation) | Tutorial-grade single-robot Gazebo | Tutorial-style; check current activity |
| [ros2/demos](https://github.com/ros2/demos) | Official ROS 2 demos | Likely too big as a whole; subdirectories may be useful |
| [ros2/examples](https://github.com/ros2/examples) | Official ROS 2 examples | Same — useful subdirectories likely exist |
| [ros-navigation/navigation2_tutorials](https://github.com/ros-navigation/navigation2_tutorials) | Nav2 tutorials | Earlier note: "too sprawling"; check sub-tutorials |
| [aws-robotics/aws-robomaker-small-warehouse-world](https://github.com/aws-robotics/aws-robomaker-small-warehouse-world) | Warehouse sim world | Earlier note: "mostly assets, not code"; useful only as a *world* for other repos |
| [robotperf/benchmarks](https://github.com/robotperf/benchmarks) | Robotics performance benchmarks | Found via SWE-bench investigation; reference for sim-metric task design |

---

## Maintenance

- **Re-investigate cadence:** quarterly. Repos rebase and rename; SHAs and branches drift.
- **When you remove a repo:** change status to `❌ rejected` with a one-line reason; do not delete the entry. Negative findings are valuable.
- **When you investigate a backlog mention:** promote it from the backlog table into a full detailed entry. Use the `record-candidate-repo` skill.
