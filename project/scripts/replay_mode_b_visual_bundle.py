"""Replay raw image through frozen detection, neural top and current pose, no motion.

Default input is a saved red-cube frame from the accepted 10-28 local anchor.
Other images require explicit confirmation that they use the same camera pose.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from verify_mode_b_visual_bundle import digest, local, verify_current


def load_projection():
    path = ROOT/'artifacts/phase3c/top_metric_check_20261028/replay_saved_tops.py'
    spec = importlib.util.spec_from_file_location('bundle_projection_reference', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.projected_top


def project_rows(observation, geometry, dimensions, bounds, project):
    import numpy as np
    from mode_b_eraser_geometry import rectangle_residual
    result = []
    for row in observation['localizations']:
        name = row['class_name']
        out = {'class_name': name, 'status': row['status'], 'top': None,
               'object_centre_desktop_xyz_mm': None, 'physical_execution': False}
        fit = row['pixel_surface']
        if fit:
            rule = dimensions[name]
            top = project(fit, geometry, rule['shape'], rule['size_mm'][2])
            if name == 'red_cube':
                valid = (np.max(abs(np.array(top['opposite_edge_mean_mm'])/30-1)) <= .2
                         and top['max_abs_adjacent_edge_cosine'] <= .15)
            elif name == 'eraser':
                expected = np.sort(rule['size_mm'][:2])
                measured = np.sort(top['opposite_edge_mean_mm'])
                top['rectangle_residual'] = rectangle_residual(top['projected_boundary_xyz_mm'])
                valid = (np.max(abs(measured/expected-1)) <= .22
                         and (top['max_abs_adjacent_edge_cosine'] <= .25
                              or top['rectangle_residual']['within2mm']))
            else:
                valid = (abs(top['diameter_mm']/rule['size_mm'][0]-1) <= .22
                         and top['circle_residual_p95_fraction_radius'] <= .09)
            xy = np.array(top['projected_boundary_xyz_mm'])[:, :2]
            valid = bool(valid and np.all(xy >= bounds[:2]) and np.all(xy <= bounds[2:]))
            out.update(top=top, geometry_gate_pass=valid,
                       status='DESKTOP_CANDIDATE_ONLY' if valid else 'METRIC_GEOMETRY_REJECTED')
            if valid:
                out['object_centre_desktop_xyz_mm'] = top['centre_desktop_xyz_mm'][:2]+[rule['size_mm'][2]/2]
        result.append(out)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--image', type=Path)
    p.add_argument('--same-camera-pose', action='store_true')
    p.add_argument('--out', required=True, type=Path)
    a = p.parse_args()
    if a.out.exists():
        p.error('Fresh output directory required')
    config, freeze, work = verify_current(ROOT)
    if a.image is not None and not a.same_camera_pose:
        p.error('External image requires --same-camera-pose; other poses cannot use this millimetre transform')
    image_path = a.image or local(ROOT, config['metric_sample'])
    import torch
    from pc.mode_b.profile import Profile
    from pc.mode_b.perception import Perception, draw
    from pc.mode_b.surface_ensemble import AlignedSurfaceEnsemble
    from pc.mode_b.tiled_detector import TiledDetector
    from pc.multiobject.dataset import read_image, write_image
    from pc.multiobject.surface import SurfaceRuntime
    from pc.multiobject.yolo import Detector
    from pc.rgb_table_geometry import RGBTableGeometry
    torch.set_num_threads(4)
    frame = read_image(image_path)
    geometry = RGBTableGeometry(local(ROOT, work['table_file']), ROOT)
    geometry.check_frame(frame.shape)
    detector = TiledDetector(Detector(local(ROOT, freeze['detector_package']), 'onnx_cpu'))
    surface = AlignedSurfaceEnsemble(SurfaceRuntime(local(ROOT, freeze['surface_package']), 'torch_cpu'))
    obs = Perception(detector, surface, Profile.load(local(ROOT, freeze['profile']))).infer(frame)
    points = work['pattern_outer_corners_desktop_xyz_mm']
    import numpy as np
    xy = np.array(points)[:, :2]
    bounds = np.r_[xy.min(0), xy.max(0)]
    rows = project_rows(obs, geometry, config['localization_dimensions'], bounds, load_projection())
    a.out.mkdir(parents=True)
    write_image(a.out/'detected.png', draw(frame, obs))
    (a.out/'observation.json').write_text(json.dumps(obs, indent=2)+'\n', encoding='utf8')
    report = {'schema': 'gesture.mode_b.visual_bundle_metric_replay.v1',
              'source_image_sha256': digest(image_path), 'frame_sha256': obs['frame_sha256'],
              'table_sha256': config['current_table_sha256'], 'frame': 'desk_global_mm',
              'units': 'mm', 'localizations': rows, 'offline_snapshot': True,
              'height_source': 'KNOWN_REGISTERED_HEIGHT_NOT_CAMERA_DEPTH',
              'motion_request_created': False, 'robot_base_xyz_mm': None,
              'metric_localization_accepted': False, 'physical_execution': False,
              'path_submissions': 0}
    (a.out/'metric.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf8')
    print(json.dumps({'status': 'OFFLINE_VISUAL_AND_METRIC_REPLAY_COMPLETED',
                      'candidates': [{k:r[k] for k in ('class_name','status','object_centre_desktop_xyz_mm')}
                                     for r in rows], 'physical_execution': False}))


if __name__ == '__main__':
    main()
