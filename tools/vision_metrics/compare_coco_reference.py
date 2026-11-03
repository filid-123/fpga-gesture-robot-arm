"""Optional official pycocotools bbox AP cross-check of the saved predictions.

Requires numpy and pycocotools==2.0.11; no models or images are read.
"""
import argparse
import contextlib
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path
import numpy as np
from pycocotools.coco import COCO
from pycocotools.cocoeval import COCOeval


def compare(folder):
    report = json.loads((folder/'report.json').read_bytes())
    records = json.loads((folder/'predictions.json').read_bytes())
    classes = list(report['detection']['per_class'])
    categories = [{'id': i+1, 'name': n} for i, n in enumerate(classes)]
    ids = {c['name']: c['id'] for c in categories}
    annotations, predictions = [], []
    for i, record in enumerate(records, 1):
        for obj in record['objects']:
            x, y, right, bottom = obj['bbox_xyxy_raw']
            annotations.append({'id': len(annotations)+1, 'image_id': i,
                                'category_id': ids[obj['class_name']], 'iscrowd': 0,
                                'bbox': [x, y, right-x, bottom-y],
                                'area': (right-x)*(bottom-y)})
        # Match this project's explicit global per-image maximum before calling
        # COCO, whose maxDets is otherwise per image/category.
        for obj in sorted(record['detections'], key=lambda d: -d['confidence'])[:100]:
            x, y, right, bottom = obj['bbox_xyxy_raw']
            predictions.append({'image_id': i, 'category_id': ids[obj['class_name']],
                                'score': obj['confidence'], 'bbox': [x, y, right-x, bottom-y]})
    with contextlib.redirect_stdout(io.StringIO()):
        ground = COCO()
        ground.dataset = {'info': {}, 'images': [{'id': i+1} for i in range(len(records))],
                          'annotations': annotations, 'categories': categories}
        ground.createIndex()
        detected = ground.loadRes(predictions)
        evaluation = COCOeval(ground, detected, 'bbox')
        evaluation.evaluate()
        evaluation.accumulate()
    precision = evaluation.eval['precision'][:, :, :, 0, 2]  # area all / maxDets100
    official_all = float(precision[precision > -1].mean())
    at50 = precision[0]
    official_50 = float(at50[at50 > -1].mean())
    differences = {'mAP50': abs(official_50-report['detection']['mAP50']),
                   'mAP50_95': abs(official_all-report['detection']['mAP50_95'])}
    if max(differences.values()) > 1e-12:
        raise ValueError('COCO reference mismatch: '+repr(differences))
    return {'scope': report['scope'], 'pycocotools_version': importlib.metadata.version('pycocotools'),
            'numpy_version': np.__version__, 'bbox_area': 'all', 'maxDets': 100,
            'official_mAP50': official_50, 'official_mAP50_95': official_all,
            'absolute_differences': differences, 'tolerance': 1e-12, 'passed': True,
            'source_predictions_sha256': hashlib.sha256((folder/'predictions.json').read_bytes()).hexdigest()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, default=Path(__file__).resolve().parents[2]/'metrics/evidence/vision_20261103')
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('Fresh output file required')
    value = {'method': 'OFFICIAL_PYCOCOTOOLS_BBOX_REFERENCE_ON_IDENTICAL_SAVED_PREDICTIONS',
             'results': [compare(args.evidence/n) for n in ('final_development_validation', 'final_one_layout_check')],
             'physical_execution': False}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(value))
