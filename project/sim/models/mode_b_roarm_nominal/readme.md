# Nominal RoArm-M3 geometry

This directory contains the existing project's converted official generic RoArm-M3 URDF and seven unchanged STL meshes, reused for Mode B offline kinematic/collision checks. It is not an independently verified physical M3-S calibration or dynamic control model.

Source repository: https://github.com/waveshareteam/roarm_ws/tree/ros2-humble

The source conversion report and original hashes are preserved in `provenance.json`. URDF effort/velocity limits are zero; the planner uses explicitly nominal configuration limits instead. CAD inertial values, joint zero/sign mapping, base placement and gripper opening/contact models have not been validated on the physical arm.

The local conversion package did not include a license file or an upstream commit identifier. License status is recorded as unverified; no additional license grant or version provenance is implied by copying these files. The repository URL identifies the source location, while hashes identify the exact local inputs.

The converted `hand_tcp` describes the fixed-jaw datum. The planner constructs a separate object-width-dependent nominal grasp frame; it must not be treated as a measured physical grasp centre.
