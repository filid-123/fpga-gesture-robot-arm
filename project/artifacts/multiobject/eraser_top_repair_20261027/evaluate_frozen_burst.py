"""Evaluate an excluded raw burst with explicit, hash-frozen model packages."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

import torch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from pc.mode_b.profile import CLASSES, TASKS, Profile
from pc.mode_b.perception import Perception, draw
from pc.mode_b.tiled_detector import TiledDetector
from pc.multiobject.yolo import Detector
from pc.multiobject.surface import SurfaceRuntime
from pc.multiobject.dataset import read_image, write_image
from pc.multiobject.public_data import sha256


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capture', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--freeze', type=Path, required=True)
    p.add_argument('--empty', action='store_true')
    p.add_argument('--development-replay', action='store_true')
    a = p.parse_args()
    if a.out.exists():
        p.error('Fresh output directory required')
    freeze = json.loads(a.freeze.read_bytes())
    for name, expected in freeze['files_sha256'].items():
        if sha256(ROOT/name) != expected:
            raise ValueError('Frozen file changed: '+name)
    capture = json.loads((a.capture/'capture.json').read_bytes())
    if capture['status'] != 'COMPLETED' or capture['used_for_training'] is not False:
        raise ValueError('A completed, excluded raw capture is required')
    data_path = ROOT/freeze['dataset_manifest']
    if sha256(data_path) != freeze['dataset_sha256']:
        raise ValueError('Dataset manifest differs from the frozen revision')
    data = json.loads(data_path.read_bytes())
    excluded_hashes = {row['image_sha256'] for row in data['items']}
    checked_pixels = set()
    for row in data['items']:
        if row.get('pixel_sha256'):
            checked_pixels.add(row['pixel_sha256'])
    torch.set_num_threads(3)
    detector = Detector(ROOT/freeze['detector_package'], backend='onnx_cpu')
    if freeze['tiled_inference']:
        detector = TiledDetector(detector)
    surface = SurfaceRuntime(ROOT/freeze['surface_package'], backend='torch_cpu')
    if freeze.get('surface_ensemble',False):
        from pc.mode_b.surface_ensemble import AlignedSurfaceEnsemble
        surface=AlignedSurfaceEnsemble(surface)
        if surface.policy!=freeze['surface_spatial_policy']:raise ValueError('Surface policy differs')
    pipe = Perception(detector, surface, Profile.load(ROOT/freeze['profile']),
                      confidence=freeze['detector_confidence'],
                      surface_confidence=freeze['surface_confidence'])
    a.out.mkdir(parents=True)
    rows = []
    for index, source in enumerate(capture['frames']):
        path = ROOT/source['image']
        if sha256(path) != source['image_sha256']:
            raise ValueError('Capture bytes changed')
        if source['image_sha256'] in excluded_hashes or source['pixel_sha256'] in checked_pixels:
            raise ValueError('Check pixels appear in the training/development dataset')
        frame = read_image(path)
        obs = pipe.infer(frame, index)
        if obs['frame_sha256'] != source['pixel_sha256']:
            raise ValueError('Capture pixel hash differs')
        (a.out/f'{index:02d}_observation.json').write_text(json.dumps(obs, indent=2)+'\n', encoding='utf8')
        write_image(a.out/f'{index:02d}_detected.png', draw(frame, obs))
        counts = dict(Counter(o['class_name'] for o in obs['recognitions']))
        top = {o['class_name']: o['status'] for o in obs['localizations']}
        all_tops = (set(top) == set(TASKS.values())
                    and all(top[name] == 'PIXEL_SURFACE_ONLY' for name in TASKS.values()))
        rows.append({'image': source['image'], 'image_sha256': source['image_sha256'],
                     'pixel_sha256': source['pixel_sha256'], 'class_counts': counts,
                     'confidence_by_class': {c: [o['confidence'] for o in obs['recognitions']
                                               if o['class_name'] == c] for c in CLASSES},
                     'top_status': top, 'six_classes_once': counts == dict.fromkeys(CLASSES, 1),
                     'three_surfaces_available': all_tops,
                     'empty_no_detections': not obs['recognitions'], 'total_ms': obs['total_ms']})
    report = {'schema': 'gesture.ai_pc.mode_b_frozen_burst_check.v2', 'status': 'COMPLETED',
              'frames': len(rows), 'independent_arrangements': 1, 'empty_scene': a.empty,
              'frames_six_classes_once': sum(r['six_classes_once'] for r in rows),
              'frames_three_surfaces_available': sum(r['three_surfaces_available'] for r in rows),
              'frames_no_detections': sum(r['empty_no_detections'] for r in rows),
              'model_sha256': detector.info['model_sha256'], 'surface_sha256': surface.info['model_sha256'],
              'candidate_freeze_sha256': sha256(a.freeze), 'tiled_inference': freeze['tiled_inference'],
              'surface_ensemble':freeze.get('surface_ensemble',False),
              'scope': ('PREVIOUS_FAILURE_DEVELOPMENT_REPLAY_NOT_FRESH_VALIDATION' if a.development_replay
                        else 'ONE_FRESH_LAYOUT_SHORT_BURST_NOT_GENERAL_ACCURACY'),
              'visual_and_box_label_review_separate': True,
              'used_for_training_or_checkpoint_selection': False,
              'physical_execution': False, 'path_submissions': 0,
              'metric_localization_accepted': False, 'npu_acceptance': 'NOT_RUN',
              'rocm_acceptance': 'NOT_RUN', 'records': rows}
    (a.out/'summary.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf8')
    print(json.dumps({k: v for k, v in report.items() if k != 'records'}), flush=True)
    for row in rows:
        print(json.dumps(row), flush=True)


if __name__ == '__main__':
    main()
