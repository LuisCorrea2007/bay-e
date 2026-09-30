# BAY-E Unified Architecture

BAY-E is being developed as an autonomous companion robot: a warm, persistent
companion layer inspired by Baymax-like interaction, coupled to a future
WALL-E-like mobile body.

## Non-negotiable boundary

The cognitive/model layer **never controls PWM, servos or motor power directly**.

```
Perception -> Context/Memory -> Planner -> Safety Governor -> Robot Adapter -> MCU/ROS 2
```

The safety layer is deterministic and may reject any cognitive request.

## Runtime domains

- **Interface**: the current HTML/CSS/JS console and animated live face.
- **Companion**: emotions, drives, personality, relationship continuity.
- **Memory**: episodic, semantic, people, objects, spatial and routines.
- **World model**: structured entities/relationships; added incrementally.
- **Perception**: camera, audio and physical sensors through replaceable adapters.
- **Cognition**: model router, tools, skills, planner and context assembly.
- **Autonomy**: goals, scheduler and behavior trees.
- **Guardian**: health, recovery, diagnostics and fail-safe behavior.
- **Robotics**: ROS 2/navigation/locomotion/arms/docking adapters.
- **Health**: measurement/trend/alert support only. It is not an autonomous
  diagnosis or prescription system.

## Event contract

Core modules communicate through typed event names, for example:

- `vision.object_detected`
- `audio.voice_detected`
- `memory.created`
- `emotion.changed`
- `goal.created`
- `robot.motion_requested`
- `robot.motion_blocked`
- `guardian.module_degraded`

The web UI remains a client of the core; it is not the owner of robot truth.

## Open-source inspirations audited

We studied the following public repositories for architecture and ideas:
The-Semicolons/Baymax, neild0/BayMax, titungpemba/Baymax-AI,
amanunreal/baymax, laofahai/baymax, joehsmash/baymax,
FelixSeptem/baymax and ParsifalC/NetEaseBaymaxDemo.

We do not copy unlicensed source.  Useful concepts are reimplemented behind
BAY-E-owned interfaces.  MIT/Apache code, if incorporated later, must retain
the required attribution and notices.
