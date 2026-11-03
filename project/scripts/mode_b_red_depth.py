"""Bind one measured red pickup-depth correction; no hardware access."""
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTIVE = ROOT / 'config/ai_pc/mode_b_red_depth_active_20261030.json'


def read(path):
    return json.loads(Path(path).read_bytes())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate(adapter, request):
    if (request['object_class'] != 'red_cube' or adapter['object_class'] != 'red_cube'
            or adapter.get('fingertip_height_adjustment_mm') not in (-8.0, -12.0)
            or adapter.get('desk_command_correction_mm') != [0, 0, 0]):
        raise ValueError('Depth correction is a separate red-only8mm adjustment')
    path = Path(adapter['operator_depth_observation_file'])
    if digest(path) != adapter['operator_depth_observation_sha256']:
        raise ValueError('Red depth observation changed')
    evidence = read(path)
    plan_path, result_path = Path(evidence['source_plan_file']), Path(evidence['source_result_file'])
    if (digest(plan_path) != evidence['source_plan_sha256']
            or digest(result_path) != evidence['source_result_sha256']):
        raise ValueError('Measured red depth baseline changed')
    plan, result = read(plan_path), read(result_path)
    if (evidence['additional_descent_mm'] != -adapter['fingertip_height_adjustment_mm']
            or plan['request']['object_class'] != 'red_cube'
            or plan.get('red_pickup_depth_correction') or plan.get('object_adapter')
            or result['route_sha256'] != evidence['source_plan_sha256'] or result.get('error')
            or result['completed_stages'] != [s['phase'] for s in plan['stages']]
            or evidence['reference_source_centre_mm'] != plan['request']['pickup']['centre_mm']
            or evidence['fixed_primary_anchor_sha256'] != plan['accepted_native_source_anchor_sha256']
            or evidence['table_transform_sha256'] != plan['request']['table_transform_sha256']):
        raise ValueError('Use the completed measured red baseline once, from its fixed anchor')
    if evidence['additional_descent_mm'] == 12.0:
        previous_path = Path(evidence['previous_depth8_result_file'])
        if digest(previous_path) != evidence['previous_depth8_result_sha256']:
            raise ValueError('Previous depth8 result changed')
        previous = read(previous_path)
        previous_plan = read(previous['route_file'])
        if (previous.get('error') or previous_plan['red_pickup_depth_correction']['additional_descent_mm'] != 8.0
                or digest(previous['route_file']) != previous['route_sha256']
                or previous['completed_stages'] != [s['phase'] for s in previous_plan['stages']]):
            raise ValueError('The extra4mm must follow the completed measured depth8 trial')
    if (request['table_transform_sha256'] != evidence['table_transform_sha256']
            or request['source_planning_strategy']['anchor_sha256'] != evidence['fixed_primary_anchor_sha256']):
        raise ValueError('Red depth camera or primary anchor differs from its measurement')
    source, centre = request['pickup']['centre_mm'], evidence['reference_source_centre_mm']
    radius = float(evidence['maximum_xy_distance_mm'])
    if (len(source) != 3 or len(centre) != 3
            or not all(math.isfinite(float(v)) for v in [*source, *centre, radius])
            or not 0 < radius <= 25):
        raise ValueError('Invalid measured red depth neighbourhood')
    distance = math.hypot(source[0] - centre[0], source[1] - centre[1])
    if distance > radius or abs(source[2] - centre[2]) > .01:
        raise ValueError('Red source exceeds the25mm measured depth neighbourhood')
    return {'additional_descent_mm': evidence['additional_descent_mm'], 'reference_source_centre_mm': centre,
            'maximum_xy_distance_mm': radius, 'current_xy_distance_mm': distance,
            'observation_file': str(path), 'observation_sha256': digest(path),
            'physical_correction_accepted': False,
            'policy': 'FIXED_PRIMARY_ANCHOR_ONCE; STATIONARY_OBJECT_AND_DELIVERY_HEIGHT_REBOUND'}


def bind(request):
    if not ACTIVE.exists():
        return
    pointer = read(ACTIVE)
    path = (ROOT / pointer['file']).resolve()
    if (pointer.get('schema') != 'gesture.mode_b.red_depth_active.v1'
            or path.parent != (ROOT / 'config/ai_pc').resolve()
            or digest(path) != pointer['sha256']):
        raise ValueError('Active red depth configuration changed')
    validate(read(path), request)
    request['object_adapter_file'] = str(path)
    request['object_adapter_sha256'] = digest(path)
