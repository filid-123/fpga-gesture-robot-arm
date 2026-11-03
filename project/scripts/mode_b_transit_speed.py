"""Apply the shared, explicit transit policy without changing a grasp adapter."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

PHASES = ['BUFFER', 'PREPLACE', 'RETREAT', 'RETURN_CLEAR']


def apply(plan, profile_path):
    path = Path(profile_path).resolve()
    profile = json.loads(path.read_text(encoding='utf-8-sig'))
    if (profile.get('schema') != 'gesture.mode_b.transit_speed_profile.v1'
            or profile.get('joint_phases') != PHASES
            or profile.get('phase_speed_multiplier') != dict.fromkeys(PHASES, 2.0)
            or profile.get('preserve_lateral_clearance_mm') != 8
            or profile.get('native_spd_max') != 4095
            or profile.get('native_acc_max') != 254
            or plan['request']['object_class'] not in profile['object_classes']
            or plan.get('release_clearance_mm') != 8):
        raise ValueError('Invalid shared transit policy or release clearance')
    basis = profile['red_operator_feedback']
    feedback_path = Path(basis['file'])
    if hashlib.sha256(feedback_path.read_bytes()).hexdigest() != basis['sha256']:
        raise ValueError('Shared speed feedback binding changed')
    feedback = json.loads(feedback_path.read_text(encoding='utf-8-sig'))
    if feedback['status'] != 'OPERATOR_ACCEPTED_POSTRELEASE_SPEED':
        raise ValueError('Shared speed requires accepted red postrelease feedback')
    plan['joint_transit_phases'] = list(PHASES)
    plan['phase_speed_multiplier'] = deepcopy(profile['phase_speed_multiplier'])
    plan['transit_speed_profile'] = {'file': str(path),
        'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'config': profile,
        'physical_trial_of_generated_plan_performed': False}
