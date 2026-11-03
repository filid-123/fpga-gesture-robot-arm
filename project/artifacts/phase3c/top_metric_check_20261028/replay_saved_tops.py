"""Offline projection diagnostics from saved neural top pixels; never live input."""
from pathlib import Path
import argparse
import hashlib
import json
import sys

import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from pc.rgb_table_geometry import RGBTableGeometry
from pc.rgb_workspace_overlay import RGBWorkspaceOverlay


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')


def projected_top(surface, geometry, shape, height_mm):
    """Diagnostic only: project stored contour/quad, never rasterize a fake mask."""
    z=float(height_mm)
    if not np.isfinite(z) or z<=0:
        raise ValueError('Positive finite assumed top height required')
    if shape in ('square','rectangle'):
        uv=np.asarray(surface.get('quad_pixel_uv'),float)
        if uv.shape!=(4,2) or not np.isfinite(uv).all():
            raise ValueError('Four finite saved top corners required')
        points=np.array([geometry.project(p,z) for p in uv])
        edges=np.roll(points[:,:2],-1,axis=0)-points[:,:2]
        lengths=np.linalg.norm(edges,axis=1)
        if np.min(lengths)<1:
            raise ValueError('Degenerate projected quad')
        # Match runtime geometry: average in physical top plane, not image UV.
        centre=points.mean(0)
        adjacent_cosine=(edges*np.roll(edges,-1,axis=0)).sum(1)/(lengths*np.roll(lengths,-1))
        direction=edges[np.argmax(lengths)]
        return {'centre_desktop_xyz_mm':centre.tolist(),
                'projected_boundary_xyz_mm':points.tolist(),
                'edge_lengths_mm':lengths.tolist(),
                'opposite_edge_mean_mm':[(lengths[0]+lengths[2])/2,(lengths[1]+lengths[3])/2],
                'max_abs_adjacent_edge_cosine':float(np.max(np.abs(adjacent_cosine))),
                'long_axis_yaw_mod180_deg':float(np.degrees(np.arctan2(direction[1],direction[0]))%180)}
    if shape!='circle':
        raise ValueError('Unsupported saved top shape')
    uv=np.asarray(surface.get('contour_pixel_uv'),float)
    if uv.ndim!=2 or uv.shape[1]!=2 or len(uv)<5 or not np.isfinite(uv).all():
        raise ValueError('Saved finite circle perimeter required')
    # Runtime bounds contour work similarly; retain original evidence untouched.
    uv=uv[::max(1,len(uv)//160)]
    points=np.array([geometry.project(p,z) for p in uv])
    xy=points[:,:2];origin=xy.mean(0);q=xy-origin
    solution,_,rank,_=np.linalg.lstsq(np.column_stack((2*q,np.ones(len(q)))),(q*q).sum(1),rcond=None)
    radius2=solution[2]+solution[:2]@solution[:2]
    if rank<3 or radius2<=0:
        raise ValueError('Degenerate projected circle')
    centre=origin+solution[:2];radius=np.sqrt(radius2)
    residual=np.abs(np.linalg.norm(xy-centre,axis=1)-radius)
    return {'centre_desktop_xyz_mm':[float(centre[0]),float(centre[1]),z],
            'projected_boundary_xyz_mm':points.tolist(),'diameter_mm':float(2*radius),
            'circle_residual_p95_mm':float(np.percentile(residual,95)),
            'circle_residual_p95_fraction_radius':float(np.percentile(residual,95)/radius),
            'centre_method':'CIRCLE_FIT_AFTER_UNDISTORTION_AND_KNOWN_HEIGHT_PLANE_PROJECTION'}


def run(capture_path, observations, workspace_path, profile_path, out):
    if out.exists():
        raise ValueError('Fresh output directory required')
    overlay=RGBWorkspaceOverlay(workspace_path,ROOT)
    geometry=overlay.geometry
    if geometry.table['table_frame_id']!='desk_global_mm':
        raise ValueError('Explicit global desktop geometry required')
    reg_path=ROOT/geometry.table['desktop_registration_file']
    if sha(reg_path)!=geometry.table['desktop_registration_sha256']:
        raise ValueError('Desktop registration hash mismatch')
    capture=json.loads(capture_path.read_bytes())
    if capture.get('status')!='COMPLETED' or capture.get('used_for_training') is not False:
        raise ValueError('Completed saved check capture required')
    profile=json.loads(profile_path.read_bytes())
    rules={v['name']:v for v in profile['objects'] if v['grasp_target']}
    report={'schema':'gesture.ai_pc.saved_top_metric_diagnostic.v1',
        'status':'OFFLINE_DIAGNOSTIC_ONLY_PHYSICAL_ACCURACY_NOT_VERIFIED',
        'source_capture':str(capture_path),'capture_sha256':sha(capture_path),
        'source_observations':str(observations),'workspace_sha256':sha(workspace_path),
        'table_sha256':geometry.record['table_sha256'],'registration_sha256':sha(reg_path),
        'profile_sha256_file':sha(profile_path),
        'source_record_role':'OLD_SAVED_CHECK_NOT_NEW_CAPTURE_OR_INFERENCE',
        'source_capture_pose_matches_later_calibration':'ASSUMED_FOR_DIAGNOSTIC_NOT_INDEPENDENTLY_VERIFIED',
        'offline_snapshot':True,'camera_access':False,'neural_inference_rerun':False,
        'model_or_threshold_changes':False,'weight_training_performed':False,
        'metric_localization_accepted':False,'physical_execution':False,'path_submissions':0,
        'npu_acceptance':'NOT_RUN','rocm_acceptance':'NOT_RUN',
        'scope':'ONE_OLD_STATIC_LAYOUT_WITH_CORRELATED_FRAMES; DISPERSION_IS_NOT_GROUND_TRUTH_ERROR',
        'records':[],'statistics':{}}
    out.mkdir(parents=True)
    for i,source in enumerate(capture['frames']):
        image_path=ROOT/source['image']
        if sha(image_path)!=source['image_sha256']:
            raise ValueError('Capture image bytes differ')
        frame=cv2.imdecode(np.frombuffer(image_path.read_bytes(),np.uint8),1)
        if frame is None:
            raise ValueError('Source image unreadable')
        geometry.check_frame(frame.shape)
        if hashlib.sha256(np.ascontiguousarray(frame).tobytes()).hexdigest()!=source['pixel_sha256']:
            raise ValueError('Source pixels differ')
        obs_path=observations/f'{i:02d}_observation.json'
        obs=json.loads(obs_path.read_bytes())
        if obs.get('frame_sha256')!=source['pixel_sha256'] or obs.get('frame_index')!=i:
            raise ValueError('Saved observation belongs to a different frame')
        entry={'image':source['image'],'image_sha256':source['image_sha256'],
            'received_utc':source['received_utc'],'observation_sha256':sha(obs_path),'targets':[]}
        display=frame.copy();overlay.draw(display)
        for name,rule in rules.items():
            rows=[r for r in obs['localizations'] if r['class_name']==name]
            row={'class_name':name,'task_id':rule['task_id'],
                 'dimensions_confirmed_by_user':rule.get('dimensions_verified') is True,
                 'height_source':'USER_REGISTERED' if rule.get('dimensions_verified') is True else 'NOMINAL_UNVERIFIED',
                 'metric_localization_verified':False,'physical_execution':False}
            if len(rows)!=1 or rows[0].get('instances')!=1 or not rows[0].get('pixel_surface'):
                row['diagnostic_status']='SAVED_NEURAL_TOP_UNAVAILABLE'
            else:
                surface=rows[0]['pixel_surface'];shape=rule['shape'];dims=rule['dimensions_mm'];z=dims['height']
                projected=projected_top(surface,geometry,shape,z)
                row.update(projected)
                row['assumed_top_height_mm']=z
                if shape in ('square','rectangle'):
                    expected=[dims['side']]*2 if shape=='square' else [dims['length'],dims['width']]
                    relative=np.abs(np.sort(projected['opposite_edge_mean_mm'])-np.sort(expected))/np.sort(expected)
                    row['dimension_relative_error']=relative.tolist()
                    row['same_runtime_shape_dimension_gate_would_pass']=bool(np.max(relative)<=.22
                        and projected['max_abs_adjacent_edge_cosine']<=.25)
                else:
                    relative=abs(projected['diameter_mm']-dims['top_diameter'])/dims['top_diameter']
                    row['dimension_relative_error']=[relative]
                    row['same_runtime_shape_dimension_gate_would_pass']=bool(relative<=.22
                        and projected['circle_residual_p95_fraction_radius']<=.09)
                points=np.asarray(projected['projected_boundary_xyz_mm'])
                low=np.asarray(overlay.config['centre_table_xy_mm'])-np.asarray(overlay.config['size_wh_mm'])/2
                high=low+overlay.config['size_wh_mm']
                row['projected_top_inside_workspace']=bool(np.all((points[:,:2]>=low)&(points[:,:2]<=high)))
                row['diagnostic_status']='PROJECTED_SAVED_PIXELS_ONLY'
                centre=np.array(projected['centre_desktop_xyz_mm'])
                if surface.get('pixel_uv') is not None:
                    saved_centre=np.array(geometry.project(surface['pixel_uv'],z))
                    row['saved_pixel_centre_projected_desktop_xyz_mm']=saved_centre.tolist()
                    row['saved_pixel_centre_vs_physical_corner_mean_xy_mm']=float(
                        np.linalg.norm(saved_centre[:2]-centre[:2]))
                shifts=[]
                for hz in [z-1,z+1]:
                    alt=projected_top(surface,geometry,shape,hz)
                    shifts.append(float(np.linalg.norm(np.array(alt['centre_desktop_xyz_mm'])[:2]-centre[:2])))
                row['max_centre_xy_shift_for_height_plus_minus_1mm']=max(shifts)
                # Every object is explicitly a diagnostic: no runtime accepted flag.
                pixel=overlay.project([centre])[0]
                p=tuple(np.rint(pixel).astype(int))
                cv2.drawMarker(display,p,(255,255,255),cv2.MARKER_CROSS,20,2)
                text=f'{name}: ({centre[0]:.1f},{centre[1]:.1f},{centre[2]:g}) mm'
                cv2.putText(display,text,(max(5,p[0]-125),max(55,p[1]-25)),
                    cv2.FONT_HERSHEY_SIMPLEX,.55,(0,150,255),2)
            entry['targets'].append(row)
        cv2.rectangle(display,(0,0),(1920,40),(0,0,0),-1)
        cv2.putText(display,'SAVED 2026-10-27 / ASSUMED POSE / NO LIVE INPUT / METRIC NOT ACCEPTED',
            (15,28),cv2.FONT_HERSHEY_SIMPLEX,.65,(0,180,255),2)
        (out/f'{i:02d}_diagnostic.png').write_bytes(cv2.imencode('.png',display)[1].tobytes())
        report['records'].append(entry)
    for name in rules:
        rows=[r for entry in report['records'] for r in entry['targets'] if r['class_name']==name]
        usable=[r for r in rows if 'centre_desktop_xyz_mm' in r]
        stats={'saved_frames':len(rows),'projected_frames':len(usable)}
        if usable:
            centres=np.array([r['centre_desktop_xyz_mm'] for r in usable])
            stats.update(centre_mean_desktop_xyz_mm=centres.mean(0).tolist(),
                centre_min_desktop_xyz_mm=centres.min(0).tolist(),
                centre_max_desktop_xyz_mm=centres.max(0).tolist(),
                centre_peak_to_peak_xyz_mm=np.ptp(centres,axis=0).tolist(),
                max_pairwise_centre_xy_distance_mm=float(np.linalg.norm(
                    centres[:,None,:2]-centres[None,:,:2],axis=-1).max()),
                frames_shape_dimension_gate_would_pass=sum(r['same_runtime_shape_dimension_gate_would_pass'] for r in usable),
                frames_top_inside_workspace=sum(r['projected_top_inside_workspace'] for r in usable))
            if 'diameter_mm' in usable[0]:
                stats['diameter_min_max_mm']=[min(r['diameter_mm'] for r in usable),max(r['diameter_mm'] for r in usable)]
            else:
                lengths=np.sort(np.array([r['opposite_edge_mean_mm'] for r in usable]),axis=1)
                stats['short_long_side_mean_mm']=lengths.mean(0).tolist()
                stats['short_long_side_min_mm']=lengths.min(0).tolist()
                stats['short_long_side_max_mm']=lengths.max(0).tolist()
                saved_centres=np.array([r['saved_pixel_centre_projected_desktop_xyz_mm'] for r in usable])
                stats['saved_pixel_centre_projected_peak_to_peak_xyz_mm']=np.ptp(saved_centres,axis=0).tolist()
                stats['saved_pixel_centre_projected_max_pairwise_xy_mm']=float(np.linalg.norm(
                    saved_centres[:,None,:2]-saved_centres[None,:,:2],axis=-1).max())
                stats['max_saved_pixel_centre_vs_physical_corner_mean_xy_mm']=max(
                    r['saved_pixel_centre_vs_physical_corner_mean_xy_mm'] for r in usable)
                stats['centre_estimators_are_different_not_new_stability_acceptance']=True
        report['statistics'][name]=stats
    write(out/'SAVED_TOP_METRIC_DIAGNOSTIC.json',report)
    print(json.dumps({'status':report['status'],'statistics':report['statistics'],'output':str(out)},ensure_ascii=False))
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capture',type=Path,required=True)
    p.add_argument('--observations',type=Path,required=True)
    p.add_argument('--workspace',type=Path,required=True)
    p.add_argument('--profile',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    run(a.capture,a.observations,a.workspace,a.profile,a.out)


if __name__=='__main__':main()
