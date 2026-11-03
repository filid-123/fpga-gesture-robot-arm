"""Bind a fresh red-cube burst to a local restart request; no hardware access.

Known-height projection remains a commissioning candidate. This does not mark
the global camera/tool calibration, AMD backends, or physical task accepted.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'artifacts/phase3c/top_metric_check_20261028')]
from replay_saved_tops import projected_top
from pc.rgb_table_geometry import RGBTableGeometry


def read(path):
    return json.loads(Path(path).read_bytes())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf8')


def prepare(capture_dir, perception_dir, output, workspace_path=None, *, successful_high_only=False):
    if output.exists():
        raise ValueError('Fresh output directory required')
    frozen = read(ROOT/'artifacts/multiobject/eraser_top_repair_20261027/candidate_freeze_v2.json')
    for name, expected in frozen['files_sha256'].items():
        if sha(ROOT/name) != expected:
            raise ValueError('Frozen vision source changed: '+name)
    capture = read(capture_dir/'capture.json')
    if capture['status'] != 'COMPLETED' or capture['used_for_training'] is not False or len(capture['frames']) < 3:
        raise ValueError('Completed excluded fresh burst required')
    local_profile=read(ROOT/'config/ai_pc/mode_b_red_grasp_correction_20261028.json')
    if local_profile.get('coordinate_validation_pending') and workspace_path is None:
        raise ValueError('Current camera pose requires coordinate-only registration before a motion request')
    workspace_path=Path(workspace_path or ROOT/local_profile.get('workspace_file','config/ai_pc/rgb_workspace_20261027_desktop_candidate.json'))
    workspace = read(workspace_path)
    table_path = ROOT/workspace['table_file']
    if sha(table_path) != workspace['table_sha256']:
        raise ValueError('Desk geometry binding changed')
    geometry = RGBTableGeometry(table_path, ROOT)
    rows = []
    for index, frame in enumerate(capture['frames']):
        path = perception_dir/f'{index:02d}_observation.json'
        observation = read(path)
        if sha(ROOT/frame['image']) != frame['image_sha256'] or observation['frame_sha256'] != frame['pixel_sha256']:
            raise ValueError('Frame/observation mismatch')
        if [r['class_name'] for r in observation['recognitions']] != ['red_cube']:
            raise ValueError('This local restart requires one red cube and no other recognized objects')
        target = next(r for r in observation['localizations'] if r['class_name'] == 'red_cube')
        if target['instances'] != 1 or target['status'] != 'PIXEL_SURFACE_ONLY':
            raise ValueError('Unique red top required')
        top = projected_top(target['pixel_surface'], geometry, 'square', 30)
        if np.max(np.abs(np.array(top['opposite_edge_mean_mm'])/30-1)) > .2 or top['max_abs_adjacent_edge_cosine'] > .15:
            raise ValueError('Red top size/shape inconsistent with30mm cube')
        corners = np.array(top['projected_boundary_xyz_mm'])
        if not (np.all((corners[:,0] >= 490)&(corners[:,0] <= 690)) and np.all((corners[:,1] >= 215)&(corners[:,1] <= 355))):
            raise ValueError('Red top outside pickup region')
        rows.append({'frame': frame, 'observation_file': str(path.resolve()), 'observation_sha256': sha(path), 'top': top})
    centres = np.array([r['top']['centre_desktop_xyz_mm'] for r in rows])
    spread = float(np.linalg.norm(centres[:,None]-centres[None,:], axis=2).max())
    if spread > 2:
        raise ValueError('Burst target moved or localization was unstable')
    centre = centres.mean(axis=0)
    raw_yaw = rows[0]['top']['long_axis_yaw_mod180_deg']
    prior = read(ROOT/'artifacts/phase3c/mode_b_pc_trial_20261028/current_red_metric_01/red_request_axis_equivalent.json')
    old_yaw = prior['pickup']['yaw_deg']
    yaw = min((raw_yaw+k*90 for k in range(-3,3)), key=lambda v: abs(v-old_yaw))
    report = {'schema':'gesture.mode_b.red_restart_metric.v1', 'capture_file':str((capture_dir/'capture.json').resolve()),
              'capture_sha256':sha(capture_dir/'capture.json'), 'table_file':str(table_path.resolve()),
              'table_sha256':sha(table_path), 'frozen_vision_files_checked':len(frozen['files_sha256']),
              'object_centre_mm':[*centre[:2].tolist(),15.], 'height_source':'KNOWN30MM_NOT_NEW_DEPTH',
              'xy_max_pairwise_repeatability_mm':spread, 'records':rows,
              'metric_localization_accepted':False, 'physical_execution_allowed':False}
    reference = read(ROOT/'config/ai_pc/mode_b_filid_postlift_20261028.json')
    destination = reference['banks'][reference['default_bank']]['H'][:2]+[reference['support_proxy']['top_z_mm']]
    request = {'schema':'gesture.mode_b.motion_request.v1', 'frame':'desk_global_mm',
               'task_id':'mode_b_ttl_restart_red_20261028', 'object_class':'red_cube',
               'pickup':{'centre_mm':report['object_centre_mm'], 'yaw_deg':yaw,
                         'yaw_equivalence':{'raw_long_axis_deg':raw_yaw,'symmetry_deg':90,'selected_deg':yaw}},
               'destination':{'support_centre_mm':destination,'size_xy_mm':reference['support_proxy']['size_xy_mm'], 'rim_height_mm':0},
               'obstacles':[], 'source':'FRESH_POST_REBOOT_PC_COMMISSIONING_BURST',
               'physical_general_mapping_calibrated':False, 'support_size_is_proxy':True}
    output.mkdir(parents=True)
    write(output/'METRIC.json', report)
    request['metric_file_sha256'] = sha(output/'METRIC.json')
    request['table_transform_file']=str(table_path.resolve())
    request['table_transform_sha256']=sha(table_path)
    if successful_high_only:
        # A fixed observed HIGH replay does not move to the detected XY. This
        # diagnostic request cannot enter the dynamic full-pickup planner.
        request['source_planning_strategy']={
            'mode':'TODAY_SUCCESSFUL_HIGH_REGISTRATION_ONLY',
            'source_xy_not_a_motion_target':True,
            'descent_or_loaded_transfer_allowed':False}
    elif local_profile.get('source_planning_mode')=='TODAY_SUCCESSFUL_NATIVE_RELATIVE_TRANSFER':
        anchor_path=ROOT/local_profile['successful_native_source_anchor_file']
        anchor=read(anchor_path)
        if (sha(anchor_path)!=local_profile['successful_native_source_anchor_sha256']
                or anchor['status']!='OPERATOR_ACCEPTED_PICKUP_DELIVERY_HOME'
                or anchor['table_transform_sha256']!=sha(table_path)
                or np.linalg.norm(centre[:2]-anchor['source_camera_centre_mm'][:2])>anchor['maximum_source_transfer_xy_mm']):
            raise ValueError('Fresh source is outside the accepted local native anchor frame/envelope')
        request['source_planning_strategy']={'mode':'TODAY_SUCCESSFUL_NATIVE_RELATIVE_TRANSFER',
            'anchor_file':str(anchor_path.resolve()),'anchor_sha256':sha(anchor_path),
            'historical_wrong_camera_xy_not_reused':True}
    elif local_profile.get('source_planning_mode')=='ABSOLUTE_DESKTOP_ASYMMETRIC_TCP':
        approval_path=ROOT/local_profile['local_coordinate_approval_file']
        approval=read(approval_path)
        if (approval.get('operator_authorized_full_trial') is not True
                or approval.get('table_transform_sha256')!=sha(table_path)
                or np.linalg.norm(centre[:2]-approval['operator_approved_candidate_xy_mm'])>approval['maximum_trial_source_distance_mm']):
            raise ValueError('Fresh source differs from the operator-approved local coordinate trial')
        request['source_planning_strategy']={
            'mode':'ABSOLUTE_DESKTOP_ASYMMETRIC_TCP',
            'operator_approval_file':str(approval_path.resolve()),'operator_approval_sha256':sha(approval_path),
            'historical_camera_source_not_reused':True}
    if geometry.table.get('previous_desktop_to_corrected_desktop') is not None:
        request['desktop_frame_correction']={
            'previous_to_corrected':geometry.table['previous_desktop_to_corrected_desktop'],
            'previous_table_sha256':geometry.table['previous_desktop_table_sha256'],
            'direction_check_file':geometry.table['desktop_registration_file'],
            'direction_check_sha256':geometry.table['desktop_registration_sha256']}
    write(output/'request.json', request)
    print(json.dumps({'pickup':request['pickup'], 'destination':request['destination'], 'repeatability_mm':spread}))
    return report, request


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('capture','perception','output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--workspace',type=Path)
    parser.add_argument('--successful-high-only',action='store_true')
    args = parser.parse_args()
    prepare(args.capture,args.perception,args.output,args.workspace,successful_high_only=args.successful_high_only)
