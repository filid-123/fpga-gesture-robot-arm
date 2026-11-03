"""Evaluate frozen Mode-B detection AP and learned binary top mIoU, offline only."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

REPOSITORY = Path(__file__).resolve().parents[2]
ROOT = REPOSITORY/'project'
from vision_report_metrics import average_precision, segmentation_metrics, validate_objects, box_iou


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def local(name):
    p = (ROOT/name.replace('\\', '/')).resolve()
    if not p.is_relative_to(ROOT):
        raise ValueError('Project-relative path required')
    return p


def check_overlap(items, manifests):
    """Audit exact bytes/pixels/ancestor hashes and capture-session identifiers.

    This cannot prove absence of near duplicates or undisclosed pretraining.
    """
    groups = {'train': set(), 'validation': set()}
    sessions = {'train': set(), 'validation': set()}

    def hashes(value):
        result = set()
        if isinstance(value, dict):
            for k, v in value.items():
                if k.endswith('sha256') and isinstance(v, str):
                    result.add(v)
                elif isinstance(v, (dict, list)):
                    result.update(hashes(v))
        elif isinstance(value, list):
            for v in value:
                result.update(hashes(v))
        return result

    for manifest in manifests:
        data = json.loads(local(manifest).read_bytes())
        for item in data['items']:
            split = item.get('split')
            if split in groups:
                groups[split].update(hashes(item))
                if item.get('session_id'):
                    sessions[split].add(item['session_id'])
    matches = []
    for item in items:
        for split in groups:
            hit = sorted(hashes(item) & groups[split])
            session = item.get('session_id') in sessions[split]
            if hit or session:
                matches.append({'image': item['image'], 'split': split,
                                'hashes': hit, 'session_overlap': session})
    return {'method': 'EXACT_IMAGE_PIXEL_ANCESTRY_HASH_AND_SESSION',
            'matches': matches, 'near_duplicate_absence_proven': False}


def localization_matches(location, objects, object_index):
    """One pipeline result can cover at most one same-class GT instance."""
    box = location.get('bbox_xyxy_raw')
    if not box:
        return False
    candidates = [(box_iou(box, obj['bbox_xyxy_raw']), i)
                  for i, obj in enumerate(objects)
                  if obj['class_name'] == location['class_name']]
    overlap, best = max(candidates, default=(0., -1))
    return overlap >= .5 and best == object_index


def main():
    global ROOT
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project-root', type=Path, default=ROOT,
                   help='Restored frozen project root; development checkout is also supported')
    p.add_argument('--manifest', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    args = p.parse_args()
    ROOT = args.project_root.resolve()
    sys.path.insert(0, str(ROOT))
    if args.out.exists():
        p.error('Fresh output directory required')
    raw = args.manifest.read_bytes()
    data = json.loads(raw)
    if data.get('schema') != 'gesture.report.vision_eval_set.v1':
        p.error('Explicit evaluation-set manifest required')
    freeze_path = local('artifacts/multiobject/eraser_top_repair_20261027/candidate_freeze_v2.json')
    freeze = json.loads(freeze_path.read_bytes())
    for name, expected in freeze['files_sha256'].items():
        if sha(local(name)) != expected:
            p.error('Frozen runtime/model changed: '+name)
    overlap = check_overlap(data['items'], data['training_manifests'])
    if data['scope'] != 'DEVELOPMENT_VALIDATION' and overlap['matches']:
        p.error('Claimed held-out set overlaps training/selection data')
    # All sources are validated before inference; no untrusted checkpoint code.
    for row in data['items']:
        if sha(local(row['image'])) != row['image_sha256']:
            p.error('Evaluation image hash mismatch: '+row['image'])
    import cv2
    import numpy as np
    import torch
    from pc.multiobject.dataset import read_image
    from pc.multiobject.yolo import Detector, image_digest
    from pc.multiobject.surface import SurfaceRuntime
    from pc.mode_b.tiled_detector import TiledDetector
    from pc.mode_b.surface_ensemble import AlignedSurfaceEnsemble
    from pc.mode_b.profile import Profile, CLASSES
    from pc.mode_b.perception import Perception
    torch.set_num_threads(4)
    detector = TiledDetector(Detector(local(freeze['detector_package']), 'onnx_cpu'))
    surface = AlignedSurfaceEnsemble(SurfaceRuntime(local(freeze['surface_package']), 'torch_cpu'))
    pipe = Perception(detector, surface, Profile.load(local(freeze['profile'])))
    records, roi_rows, pipeline_rows = [], [], []
    confusion = Counter(tp=0, fp=0, fn=0, tn=0)
    by_class = {}
    for index, row in enumerate(data['items']):
        image = read_image(local(row['image']))
        h, w = image.shape[:2]
        if row.get('pixel_sha256') and image_digest(image) != row['pixel_sha256']:
            raise ValueError('Evaluation pixel hash mismatch')
        validate_objects(row['objects'], CLASSES, w, h)
        # Threshold .01 is the lowest supported by the frozen decoder. Record
        # this AP limitation instead of silently using operational .4 scores.
        detections, _ = detector.run(image, confidence=.01)
        records.append({'image': row['image'], 'image_sha256': row['image_sha256'],
                        'objects': row['objects'], 'detections': detections})
        obs = pipe.infer(image, index)
        for object_index, obj in enumerate(row['objects']):
            name = obj['class_name']
            if name not in ('red_cube', 'eraser', 'small_canister') or not obj.get('top_polygon_raw'):
                continue
            box = np.asarray(obj['bbox_xyxy_raw'], float)
            pad = max(box[2:]-box[:2])*.18
            crop = [max(0., box[0]-pad), max(0., box[1]-pad),
                    min(float(w), box[2]+pad), min(float(h), box[3]+pad)]
            prob, (x, y), _ = surface.run(image, crop)
            gt_full = np.zeros((h, w), np.uint8)
            cv2.fillPoly(gt_full, [np.rint(obj['top_polygon_raw']).astype(np.int32)], 1)
            gt = gt_full[y:y+prob.shape[0], x:x+prob.shape[1]].astype(bool)
            pred = prob >= freeze['surface_confidence']
            counts = {'tp': int(np.count_nonzero(pred & gt)),
                      'fp': int(np.count_nonzero(pred & ~gt)),
                      'fn': int(np.count_nonzero(~pred & gt)),
                      'tn': int(np.count_nonzero(~pred & ~gt))}
            confusion.update(counts)
            by_class.setdefault(name, Counter(tp=0, fp=0, fn=0, tn=0)).update(counts)
            roi_rows.append({'image': row['image'], 'class_name': name,
                             **segmentation_metrics(**counts)})
            location = next(v for v in obs['localizations'] if v['class_name'] == name)
            fit = location.get('pixel_surface')
            predicted = np.zeros((h, w), np.uint8)
            poly = (fit.get('quad_pixel_uv') or fit.get('contour_pixel_uv')) if fit else None
            matched = localization_matches(location, row['objects'], object_index)
            if poly and matched:
                cv2.fillPoly(predicted, [np.rint(poly).astype(np.int32)], 1)
            # Empty prediction on a rejected/missing top is scored as zero IoU.
            inter = np.count_nonzero(predicted & gt_full)
            union = np.count_nonzero(predicted | gt_full)
            pipeline_rows.append({'image': row['image'], 'class_name': name,
                                  'status': location['status'], 'available': bool(poly) and matched,
                                  'bbox_match_at_IoU50': matched,
                                  'shape_mask_IoU_missing_as_zero': float(inter/union) if union else 0.})
        print('EVALUATED', index+1, '/', len(data['items']), flush=True)
    classes = {k: segmentation_metrics(**v) for k, v in by_class.items()}
    binary = segmentation_metrics(**confusion) if roi_rows else None
    report = {'schema': 'gesture.report.vision_metrics.v1', 'status': 'COMPLETED',
              'scope': data['scope'], 'independent_layouts': data.get('independent_layouts'),
              'independent_test_accepted': False,
              'label_provenance': data['label_provenance'],
              'human_ground_truth_reviewed': data['human_ground_truth_reviewed'],
              'evaluation_manifest_sha256': hashlib.sha256(raw).hexdigest(),
              'images': len(records), 'ground_truth_instances': sum(len(x['objects']) for x in records),
              'training_overlap_audit': overlap,
              'frozen_manifest_sha256': sha(freeze_path),
              'detector_sha256': detector.info['model_sha256'],
              'surface_sha256': surface.info['model_sha256'],
              'runtime': {'detector': detector.info, 'surface': surface.info},
              'AP_score_floor': .01, 'operational_detection_threshold': .4,
              'detection': average_precision(records, CLASSES),
              'segmentation': {'task': 'BINARY_VISIBLE_TOP_NOT_SIX_CLASS_SEMANTIC_SEGMENTATION',
                               'evaluation_roi': 'GT_BOX_PLUS_18_PERCENT_PADDING',
                               'pipeline': 'FROZEN_FIVE_CROP_PROBABILITY_MEAN_RAW_THRESHOLD_0_7',
                               'conditional_on_ground_truth_box': True,
                               'objects': len(roi_rows), 'pooled_pixels': binary,
                               'per_object_class': classes,
                               'macro_foreground_IoU_over_present_object_classes':
                                   sum(v['foreground_IoU'] for v in classes.values())/len(classes) if classes else None,
                               'per_object': roi_rows},
              'end_to_end_shape_localization': {
                  'operational_thresholds_unchanged': True,
                  'objects': len(pipeline_rows),
                  'available': sum(r['available'] for r in pipeline_rows),
                  'mean_mask_IoU_missing_as_zero': sum(r['shape_mask_IoU_missing_as_zero'] for r in pipeline_rows)/len(pipeline_rows) if pipeline_rows else None,
                  'records': pipeline_rows},
              'millimetre_accuracy_measured': False, 'physical_execution': False,
              'path_submissions': 0, 'NPU_acceptance': 'NOT_EVALUATED',
              'ROCm_acceptance': 'NOT_EVALUATED',
              'evaluator_sha256': sha(Path(__file__)),
              'metrics_source_sha256': sha(Path(__file__).with_name('vision_report_metrics.py'))}
    args.out.mkdir(parents=True)
    for name, value in [('report.json', report), ('predictions.json', records)]:
        (args.out/name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps({'status': report['status'], 'scope': report['scope'],
                      'mAP50': report['detection']['mAP50'],
                      'mAP50_95': report['detection']['mAP50_95'],
                      'binary_mIoU': binary['binary_mIoU'] if binary else None,
                      'independent_test_accepted': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
