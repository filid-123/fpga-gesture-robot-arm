"""Bind a frozen three-frame cylinder detection to the local native adapter."""
import argparse
from pathlib import Path
import numpy as np
from prepare_mode_b_red_restart import ROOT, read, sha, write, projected_top, RGBTableGeometry
from mode_b_eraser_geometry import rectangle_residual


def prepare(capture_dir, perception_dir, output, object_name='small_canister'):
    if output.exists():
        raise ValueError('Fresh output directory required')
    if object_name not in ('small_canister','eraser'):raise ValueError('Unsupported object adapter')
    prefix='eraser' if object_name=='eraser' else 'cylinder'
    profile_path=ROOT/f'config/ai_pc/mode_b_{prefix}_grasp_20261028.json'
    active_path=ROOT/f'config/ai_pc/mode_b_{prefix}_grasp_active_20261028.json'
    if active_path.exists():
        active=read(active_path);profile_path=ROOT/active['adapter_file']
        if sha(profile_path)!=active['adapter_sha256']:
            raise ValueError('Active cylinder adapter binding changed')
    profile=read(profile_path)
    local=read(ROOT/'config/ai_pc/mode_b_red_grasp_correction_20261028.json')
    frozen=read(ROOT/'artifacts/multiobject/eraser_top_repair_20261027/candidate_freeze_v2.json')
    for name,expected in frozen['files_sha256'].items():
        if sha(ROOT/name)!=expected:raise ValueError('Frozen vision file changed: '+name)
    capture_path=capture_dir/'capture.json';capture=read(capture_path)
    if capture['status']!='COMPLETED' or capture['used_for_training'] is not False or len(capture['frames'])!=3:
        raise ValueError('Three excluded fresh frames required')
    workspace=read(ROOT/local['workspace_file']);table_path=ROOT/workspace['table_file']
    anchor_path=ROOT/local['successful_native_source_anchor_file'];anchor=read(anchor_path)
    if (sha(anchor_path)!=local['successful_native_source_anchor_sha256']
            or sha(table_path)!=workspace['table_sha256'] or sha(table_path)!=anchor['table_transform_sha256']):
        raise ValueError('Current camera/accepted source bindings changed')
    geometry=RGBTableGeometry(table_path,ROOT);rows=[]
    for index,frame in enumerate(capture['frames']):
        obs_path=perception_dir/f'{index:02d}_observation.json';obs=read(obs_path)
        if sha(ROOT/frame['image'])!=frame['image_sha256'] or obs['frame_sha256']!=frame['pixel_sha256']:
            raise ValueError('Frame/observation mismatch')
        if [r['class_name'] for r in obs['recognitions']]!=[object_name]:
            raise ValueError('One selected object alone required for this commissioning trial')
        candidates=[r for r in obs['localizations'] if r['class_name']==object_name]
        if len(candidates)!=1 or candidates[0]['instances']!=1 or candidates[0]['status']!='PIXEL_SURFACE_ONLY':
            raise ValueError('Unique cylinder top required')
        top=projected_top(candidates[0]['pixel_surface'],geometry,'rectangle' if object_name=='eraser' else 'circle',profile['size_mm'][2])
        if object_name=='eraser':
            expected=np.sort(profile['size_mm'][:2]);measured=np.sort(top['opposite_edge_mean_mm'])
            top['rectangle_residual']=rectangle_residual(top['projected_boundary_xyz_mm'])
            # Rounded ends can skew one predicted corner without changing the
            # physical centre. Keep all frames and raw means; bound the absolute
            # deviation as well as dimensions instead of requiring ideal angles.
            if np.max(abs(measured/expected-1))>.22 or (top['max_abs_adjacent_edge_cosine']>.25 and not top['rectangle_residual']['within2mm']):
                raise ValueError('Top is inconsistent with the registered eraser')
        elif abs(top['diameter_mm']/profile['size_mm'][0]-1)>.22 or top['circle_residual_p95_fraction_radius']>.09:
            raise ValueError('Top is inconsistent with the registered cylinder')
        points=np.array(top['projected_boundary_xyz_mm'])
        if not np.all((points[:,:2]>=[490,215])&(points[:,:2]<=[690,355])):
            raise ValueError('Cylinder top outside pickup region')
        rows.append({'frame':frame,'observation_file':str(obs_path.resolve()),'observation_sha256':sha(obs_path),'top':top})
    centres=np.array([r['top']['centre_desktop_xyz_mm'] for r in rows]);spread=float(np.linalg.norm(centres[:,None]-centres[None,:],axis=2).max())
    centre=centres.mean(0);centre[2]=profile['size_mm'][2]/2
    if spread>2 or np.linalg.norm(centre[:2]-anchor['source_camera_centre_mm'][:2])>anchor['maximum_source_transfer_xy_mm']:
        raise ValueError('Unstable or out-of-envelope cylinder source')
    reference=read(ROOT/'config/ai_pc/mode_b_filid_postlift_20261028.json')
    destination=reference['banks'][reference['default_bank']]['H'][:2]+[reference['support_proxy']['top_z_mm']]
    yaw=anchor['source_yaw_deg']
    if object_name=='eraser':
        angles=np.radians([r['top']['long_axis_yaw_mod180_deg'] for r in rows])
        yaw=float(np.degrees(np.arctan2(np.sin(2*angles).mean(),np.cos(2*angles).mean()))/2%180)
        if max(abs((np.degrees(angles)-yaw+90)%180-90))>5:raise ValueError('Unstable eraser long-axis angle')
    report={'schema':f'gesture.mode_b.{prefix}_restart_metric.v1','capture_file':str(capture_path.resolve()),
        'capture_sha256':sha(capture_path),'table_file':str(table_path.resolve()),'table_sha256':sha(table_path),
        'object_centre_mm':centre.tolist(),'height_source':profile['dimensions_source'],
        'xy_max_pairwise_repeatability_mm':spread,'records':rows,'frozen_vision_files_checked':len(frozen['files_sha256']),
        'metric_localization_accepted':False,'physical_execution_allowed':False}
    output.mkdir(parents=True);write(output/'METRIC.json',report)
    request={'schema':'gesture.mode_b.motion_request.v1','frame':'desk_global_mm',
        'task_id':f'mode_b_ttl_{prefix}_20261028','object_class':object_name,
        'pickup':{'centre_mm':centre.tolist(),'yaw_deg':yaw,
            'yaw_source':'DETECTED_LONG_AXIS_CLOSING_PERPENDICULAR' if object_name=='eraser' else 'AXISYMMETRIC_CYLINDER_KEEP_ACCEPTED_CLOSING_AXIS'},
        'destination':{'support_centre_mm':destination,'size_xy_mm':reference['support_proxy']['size_xy_mm'],'rim_height_mm':0},
        'obstacles':[],'source':f'FRESH_FROZEN_{prefix.upper()}_PC_COMMISSIONING_BURST',
        'object_adapter_file':str(profile_path.resolve()),'object_adapter_sha256':sha(profile_path),
        'table_transform_file':str(table_path.resolve()),'table_transform_sha256':sha(table_path),
        'metric_file_sha256':sha(output/'METRIC.json'),'physical_general_mapping_calibrated':False,
        'source_planning_strategy':{'mode':'TODAY_SUCCESSFUL_NATIVE_RELATIVE_TRANSFER',
            'anchor_file':str(anchor_path.resolve()),'anchor_sha256':sha(anchor_path),
            'physical_cylinder_adapter_accepted':False,'historical_wrong_camera_xy_not_reused':True}}
    write(output/'request.json',request)
    print(__import__('json').dumps({'pickup':request['pickup'],
        'dimensions_mm':[r['top'].get('opposite_edge_mean_mm',r['top'].get('diameter_mm')) for r in rows],'repeatability_mm':spread}))
    return report,request


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('capture','perception','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();prepare(a.capture,a.perception,a.output)
